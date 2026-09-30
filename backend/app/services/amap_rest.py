"""高德地图 Web 服务 REST 客户端

直接调用高德开放平台的 Web 服务 HTTP 接口(不经过 MCP),
提供 POI 检索、地理编码、路径规划等能力,并在进程内做结果缓存。

所有接口调用都做了容错处理:任何异常、任何 status != "1" 的响应都只会返回
空结果或 None,绝不会向上抛出,保证上层行程生成流程永远可以完成。
"""

import math
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import quote

import requests

from ..config import get_settings

# 高德 Web 服务地址
AMAP_REST_BASE = "https://restapi.amap.com/v3"
AMAP_REST_BASE_V4 = "https://restapi.amap.com/v4"

# 请求超时(秒)
REQUEST_TIMEOUT = 8

# 支持中文/英文别名的高德 POI 类型码
TYPE_CODE_MAP: Dict[str, str] = {
    "餐饮": "050000",
    "餐饮服务": "050000",
    "美食": "050000",
    "餐厅": "050000",
    "中餐厅": "050100",
    "外国餐厅": "050200",
    "快餐厅": "050300",
    "休闲餐饮": "050400",
    "咖啡厅": "050500",
    "茶艺馆": "050600",
    "冷饮店": "050700",
    "糕饼店": "050800",
    "甜品店": "050900",
    "住宿": "100000",
    "住宿服务": "100000",
    "酒店": "100000",
    "宾馆": "100000",
    "旅馆": "100000",
    "风景名胜": "110000",
    "景点": "110000",
    "公园": "110101",
    "博物馆": "140100",
}

# 缓存(模块级,应用常驻进程,重复查询瞬时返回)
_cache: Dict[Tuple[str, str], Any] = {}
_cache_lock = threading.Lock()


def _cache_get(key: Tuple[str, str], default: Any = None) -> Any:
    """读取进程内缓存"""
    with _cache_lock:
        return _cache.get(key, default)


def _cache_set(key: Tuple[str, str], value: Any) -> None:
    """写入进程内缓存"""
    with _cache_lock:
        _cache[key] = value


def _to_float(value: Any, default: float = 0.0) -> float:
    """把高德的字符串/空列表/空串统一转成 float"""
    if value is None:
        return default
    if isinstance(value, (int, float)):
        try:
            result = float(value)
        except (TypeError, ValueError):
            return default
        if math.isnan(result) or math.isinf(result):
            return default
        return result
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return default
        try:
            result = float(text)
        except ValueError:
            # 可能是 "约4.9分" 这类文本,尝试提取数字
            digits = ""
            for ch in text:
                if ch.isdigit() or ch == ".":
                    digits += ch
                elif digits:
                    break
            try:
                return float(digits) if digits else default
            except ValueError:
                return default
        if math.isnan(result) or math.isinf(result):
            return default
        return result
    return default


def _to_int(value: Any, default: int = 0) -> int:
    """把高德的字符串统一转成 int"""
    return int(round(_to_float(value, float(default))))


def _parse_location(value: Any) -> Optional[Tuple[float, float]]:
    """解析高德的 "lng,lat" 字符串

    Returns:
        (lng, lat) 元组,无法解析或坐标为 0 时返回 None
    """
    if not value:
        return None
    if isinstance(value, (list, tuple)) and len(value) >= 2:
        lng, lat = _to_float(value[0]), _to_float(value[1])
    else:
        text = str(value).strip()
        if "," not in text:
            return None
        parts = text.split(",")
        if len(parts) < 2:
            return None
        lng, lat = _to_float(parts[0]), _to_float(parts[1])
    if lng == 0 or lat == 0:
        return None
    return (lng, lat)


def _join(value: Any) -> str:
    """把高德返回的 [] / "" / str 统一成字符串"""
    if value is None:
        return ""
    if isinstance(value, (list, tuple)):
        return ",".join(str(v) for v in value if v)
    return str(value)


def _first_str(value: Any) -> str:
    """取第一个非空字符串"""
    if value is None:
        return ""
    if isinstance(value, (list, tuple)):
        for item in value:
            if item:
                return str(item)
        return ""
    return str(value)


def _photos_of(poi: Dict[str, Any]) -> str:
    """提取 POI 的首张图片 URL"""
    for photo in poi.get("photos") or []:
        if isinstance(photo, dict):
            url = photo.get("url")
            if url:
                return str(url).replace("http://", "https://")
        elif isinstance(photo, str) and photo:
            return photo.replace("http://", "https://")
    return ""


def normalize_types(types: str) -> str:
    """把中文类型名转换为高德 POI 类型码

    Args:
        types: 类型码或中文类型名,如 "050000" / "餐饮服务"

    Returns:
        高德可识别的类型码;无法转换时返回 "050000"(餐饮)
    """
    if not types:
        return "050000"
    text = str(types).strip()
    if text.isdigit():
        return text
    for name, code in TYPE_CODE_MAP.items():
        if name in text:
            return code
    return "050000"


class AmapRest:
    """高德地图 Web 服务 REST 客户端(带进程内缓存)"""

    def __init__(self, api_key: Optional[str] = None):
        """
        Args:
            api_key: 高德 Web 服务 Key;不传则从配置读取
        """
        if api_key is None:
            try:
                api_key = get_settings().amap_api_key
            except Exception:
                api_key = ""
        self.api_key: str = api_key or ""
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "xiaoxing-tanxing/1.0"})

    # ---------- 基础请求 ----------

    def _get(self, url: str, params: Dict[str, Any]) -> Optional[dict]:
        """发起 GET 请求并校验 status 字段

        Returns:
            原始 JSON dict,失败返回 None
        """
        if not self.api_key:
            return None
        try:
            query = dict(params)
            query["key"] = self.api_key
            response = self.session.get(url, params=query, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            data = response.json()
            if not isinstance(data, dict) or data.get("status") != "1":
                return None
            return data
        except Exception:
            return None

    # ---------- POI 检索 ----------

    def text_search(self, keywords: str, city: str, offset: int = 5) -> List[dict]:
        """关键字检索 POI

        Args:
            keywords: 检索关键词
            city: 城市名称
            offset: 返回条数

        Returns:
            规范化后的 POI 列表(失败返回空列表)
        """
        key = ("text", str(keywords), str(city), str(offset))
        cached = _cache_get(key)
        if cached is not None:
            return cached

        result: List[dict] = []
        try:
            params = {
                "keywords": keywords,
                "city": city,
                "citylimit": "true",
                "offset": offset,
                "page": 1,
                "extensions": "all",
            }
            data = self._get(f"{AMAP_REST_BASE}/place/text", params)
            if data:
                for poi in data.get("pois") or []:
                    normalized = self._normalize_poi(poi)
                    if normalized:
                        result.append(normalized)
        except Exception:
            result = []

        _cache_set(key, result)
        return result

    def around_search(self, lng: float, lat: float, keywords: str = "",
                      radius: int = 1500, types: str = "", offset: int = 10) -> List[dict]:
        """周边检索 POI

        Args:
            lng: 中心点经度
            lat: 中心点纬度
            keywords: 关键词
            radius: 检索半径(米)
            types: POI 类型(中文或类型码)
            offset: 返回条数

        Returns:
            规范化后的 POI 列表,每项含 distance_m(失败返回空列表)
        """
        center = _parse_location(f"{lng},{lat}")
        if not center:
            return []

        key = ("around", str(lng), str(lat), str(keywords), str(radius), str(types), str(offset))
        cached = _cache_get(key)
        if cached is not None:
            return cached

        result: List[dict] = []
        try:
            params = {
                "location": f"{lng},{lat}",
                "keywords": keywords or "",
                "radius": radius,
                "types": normalize_types(types),
                "offset": offset,
                "page": 1,
                "extensions": "all",
                "sortrule": "weight",
            }
            data = self._get(f"{AMAP_REST_BASE}/place/around", params)
            if data:
                for poi in data.get("pois") or []:
                    normalized = self._normalize_poi(poi)
                    if normalized:
                        result.append(normalized)
        except Exception:
            result = []

        _cache_set(key, result)
        return result

    def _normalize_poi(self, poi: Dict[str, Any]) -> Optional[dict]:
        """把高德 POI 原始结构规范化

        Args:
            poi: 高德返回的单个 POI

        Returns:
            规范化 dict,无效 POI 返回 None
        """
        try:
            if not isinstance(poi, dict):
                return None
            name = str(poi.get("name") or "").strip()
            if not name:
                return None

            location = _parse_location(poi.get("location"))
            biz_ext = poi.get("biz_ext") if isinstance(poi.get("biz_ext"), dict) else {}

            return {
                "id": str(poi.get("id") or ""),
                "name": name,
                "address": _join(poi.get("address")),
                "lng": location[0] if location else 0.0,
                "lat": location[1] if location else 0.0,
                "location": location,
                "type": _join(poi.get("type")),
                "rating": _to_float(biz_ext.get("rating"), 0.0),
                "cost": _to_float(biz_ext.get("cost"), 0.0),
                "tel": _join(poi.get("tel")),
                "photos": _photos_of(poi),
                "distance": _to_float(poi.get("distance"), 0.0),
                "distance_m": _to_int(poi.get("distance"), 0),
                "cityname": _join(poi.get("cityname")),
                "adname": _join(poi.get("adname")),
                "raw": poi,
            }
        except Exception:
            return None

    # ---------- 地理编码 ----------

    def geocode(self, address: str, city: str = "") -> Optional[Tuple[float, float]]:
        """地理编码:地址 → 经纬度

        Args:
            address: 地址文本
            city: 城市名称(提升准确率)

        Returns:
            (lng, lat),失败返回 None
        """
        if not address:
            return None

        key = ("geo", str(address), str(city))
        cached = _cache_get(key)
        if cached is not None:
            return cached

        result: Optional[Tuple[float, float]] = None
        try:
            params = {"address": address}
            if city:
                params["city"] = city
            data = self._get(f"{AMAP_REST_BASE}/geocode/geo", params)
            if data:
                for item in data.get("geocodes") or []:
                    location = _parse_location(item.get("location"))
                    if location:
                        result = location
                        break
        except Exception:
            result = None

        _cache_set(key, result)
        return result

    # ---------- 路径规划 ----------

    def route(self, origin: Tuple[float, float], destination: Tuple[float, float],
              mode: str = "walking", city: str = "") -> Optional[dict]:
        """路径规划

        Args:
            origin: 起点 (lng, lat)
            destination: 终点 (lng, lat)
            mode: walking / driving / cycling / transit
            city: 城市名称(公交必需)

        Returns:
            {"distance_m": int, "duration_min": int, "cost": int, "lines": List[str]}
            失败返回 None
        """
        try:
            start = _parse_location(f"{origin[0]},{origin[1]}" if origin else None)
            end = _parse_location(f"{destination[0]},{destination[1]}" if destination else None)
            if not start or not end:
                return None

            mode = str(mode or "walking").lower()
            key = ("route", f"{start[0]},{start[1]}", f"{end[0]},{end[1]}", mode, str(city))
            cached = _cache_get(key)
            if cached is not None:
                return cached if cached != "FAILED" else None

            result: Optional[dict] = None
            if mode == "walking":
                result = self._route_v3("walking", start, end)
            elif mode == "driving":
                result = self._route_v3("driving", start, end)
            elif mode == "cycling":
                result = self._route_cycling(start, end)
            elif mode == "transit":
                result = self._route_transit(start, end, city)
            else:
                result = self._route_v3("walking", start, end)

            _cache_set(key, result if result is not None else "FAILED")
            return result
        except Exception:
            return None

    def _route_v3(self, endpoint: str, origin: Tuple[float, float],
                  destination: Tuple[float, float]) -> Optional[dict]:
        """驾车/步行路径规划(v3 接口)"""
        try:
            params = {
                "origin": f"{origin[0]},{origin[1]}",
                "destination": f"{destination[0]},{destination[1]}",
                "extensions": "base",
            }
            data = self._get(f"{AMAP_REST_BASE}/direction/{endpoint}", params)
            if not data:
                return None
            paths = ((data.get("route") or {}).get("paths")) or []
            if not paths:
                return None
            path = paths[0]
            distance_m = _to_int(path.get("distance"), 0)
            duration_min = max(1, int(math.ceil(_to_float(path.get("duration"), 0) / 60.0)))
            if distance_m <= 0:
                return None
            cost = _to_float((data.get("route") or {}).get("taxi_cost"), 0.0)
            # 步行/驾车的首个导航指令含路名与方向,「明细行」用它给出可执行指引
            road_hint = ""
            for step in path.get("steps") or []:
                instruction = str((step or {}).get("instruction") or "").strip()
                if instruction:
                    road_hint = instruction
                    break
            return {
                "distance_m": distance_m,
                "duration_min": duration_min,
                "cost": _to_int(cost, 0),
                "lines": [],
                "road_hint": road_hint,
            }
        except Exception:
            return None

    def _route_cycling(self, origin: Tuple[float, float],
                       destination: Tuple[float, float]) -> Optional[dict]:
        """骑行路径规划(v4 接口,失败时回退驾车距离)"""
        try:
            params = {
                "origin": f"{origin[0]},{origin[1]}",
                "destination": f"{destination[0]},{destination[1]}",
            }
            data = self._get(f"{AMAP_REST_BASE_V4}/direction/bicycling", params)
            if data:
                paths = ((data.get("data") or {}).get("paths")) or []
                if paths:
                    path = paths[0]
                    distance_m = _to_int(path.get("distance"), 0)
                    duration_s = _to_float(path.get("duration"), 0)
                    if distance_m > 0:
                        if duration_s <= 0:
                            duration_s = distance_m / 1000.0 / 15.0 * 3600.0
                        return {
                            "distance_m": distance_m,
                            "duration_min": max(1, int(math.ceil(duration_s / 60.0))),
                            "cost": 0,
                            "lines": [],
                        }
        except Exception:
            pass

        # 骑行接口失败时用驾车路径的距离估算
        try:
            driving = self._route_v3("driving", origin, destination)
            if driving and driving.get("distance_m"):
                distance_m = int(driving["distance_m"])
                return {
                    "distance_m": distance_m,
                    "duration_min": max(1, int(math.ceil(distance_m / 1000.0 / 15.0 * 60.0))),
                    "cost": 0,
                    "lines": [],
                }
        except Exception:
            pass
        return None

    def _route_transit(self, origin: Tuple[float, float], destination: Tuple[float, float],
                       city: str) -> Optional[dict]:
        """公共交通路径规划(城市名需 URL 编码)

        高德公交接口经常返回空的 route.paths,此时视为失败,由上层回退估算。
        """
        try:
            city_name = str(city or "").strip()
            if not city_name:
                return None
            url = (
                f"{AMAP_REST_BASE}/direction/transit/integrated"
                f"?key={quote(self.api_key, safe='')}"
                f"&origin={origin[0]},{origin[1]}"
                f"&destination={destination[0]},{destination[1]}"
                f"&city={quote(city_name)}&cityd={quote(city_name)}"
            )
            response = self.session.get(url, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            data = response.json()
            if not isinstance(data, dict) or data.get("status") != "1":
                return None
            paths = ((data.get("route") or {}).get("paths")) or []
            if not paths:
                return None
            path = paths[0]
            distance_m = _to_int(path.get("distance"), 0)
            if distance_m <= 0:
                return None
            duration_min = max(1, int(math.ceil(_to_float(path.get("duration"), 0) / 60.0)))

            lines: List[str] = []
            # 每一段乘车:线路名 + 上下车站,用于生成可执行的换乘指引
            legs: List[dict] = []
            for segment in path.get("segments") or []:
                bus = (segment or {}).get("bus") or {}
                for line in bus.get("buslines") or []:
                    name = str((line or {}).get("name") or "").strip()
                    if not name:
                        continue
                    if name not in lines:
                        lines.append(name)
                    legs.append({
                        "name": name,
                        "departure_stop": _first_str((line or {}).get("departure_stop")),
                        "arrival_stop": _first_str((line or {}).get("arrival_stop")),
                    })
            cost = _to_float(path.get("cost"), 0.0)
            return {
                "distance_m": distance_m,
                "duration_min": duration_min,
                "cost": _to_int(cost, 0),
                "lines": lines[:4],
                "legs": legs[:4],
                "walking_distance_m": _to_int(path.get("walking_distance"), 0),
            }
        except Exception:
            return None

    def parallel_route(self, legs: List[Tuple[Any, Any, str]], city: str,
                       workers: int = 6) -> List[Optional[dict]]:
        """并发解析多条路径

        Args:
            legs: 待解析路段列表,每项为 (origin, destination, mode)
            city: 城市名称(公交必需)
            workers: 并发线程数

        Returns:
            与 legs 等长的结果列表,失败项为 None(顺序与输入一致)
        """
        if not legs:
            return []

        results: List[Optional[dict]] = [None] * len(legs)
        try:
            with ThreadPoolExecutor(max_workers=max(1, min(workers, len(legs)))) as pool:
                futures = [
                    pool.submit(self.route, leg[0], leg[1], leg[2], city)
                    for leg in legs
                ]
                for index, future in enumerate(futures):
                    try:
                        results[index] = future.result(timeout=REQUEST_TIMEOUT + 6)
                    except Exception:
                        results[index] = None
        except Exception:
            # 线程池不可用时退化为串行
            for index, leg in enumerate(legs):
                if results[index] is None:
                    try:
                        results[index] = self.route(leg[0], leg[1], leg[2], city)
                    except Exception:
                        results[index] = None
        return results

    # ---------- 工具方法 ----------

    @staticmethod
    def haversine_m(a: Optional[Tuple[float, float]],
                    b: Optional[Tuple[float, float]]) -> float:
        """计算两点间直线距离(米)

        Args:
            a: (lng, lat)
            b: (lng, lat)

        Returns:
            直线距离(米),参数无效返回 0.0
        """
        try:
            if not a or not b:
                return 0.0
            lng1, lat1 = _to_float(a[0]), _to_float(a[1])
            lng2, lat2 = _to_float(b[0]), _to_float(b[1])
            if (lng1 == 0 and lat1 == 0) or (lng2 == 0 and lat2 == 0):
                return 0.0
            radius = 6371008.8
            phi1 = math.radians(lat1)
            phi2 = math.radians(lat2)
            d_phi = math.radians(lat2 - lat1)
            d_lambda = math.radians(lng2 - lng1)
            h = (math.sin(d_phi / 2.0) ** 2
                 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2.0) ** 2)
            return 2.0 * radius * math.asin(min(1.0, math.sqrt(h)))
        except Exception:
            return 0.0

    def clear_cache(self) -> None:
        """清空进程内缓存(测试用)"""
        with _cache_lock:
            _cache.clear()


# 全局客户端实例
_amap_rest: Optional[AmapRest] = None


def get_amap_rest() -> AmapRest:
    """获取高德 REST 客户端实例(单例模式)"""
    global _amap_rest
    if _amap_rest is None:
        _amap_rest = AmapRest()
    return _amap_rest
