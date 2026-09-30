"""行程时间轴与推荐生成

在 LLM 生成的初版行程之上,用高德实时数据把行程「做实」:

1. 补齐景点坐标、评分、门票价格(并发地理编码)
2. 为每一天生成带具体时刻的时间轴(抵达 → 景点 → 用餐 → 酒店)
3. 为每一段路程选择交通方式并给出耗时/费用/理由
4. 为午餐、晚餐推荐真实餐厅并填充招牌菜
5. 校正酒店坐标、评分、价格
6. 重新计算预算

本模块每一步失败都会降级处理,绝不会把异常抛给调用方。
"""

import math
import os
import re
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable, Dict, List, Optional, Tuple

from ..models.schemas import (
    Attraction,
    Budget,
    DayPlan,
    Location,
    Meal,
    RestaurantRecommendation,
    TimelineEntry,
    TransportPlan,
    TripPlan,
    TripRequest,
    Venue,
)
from .amap_rest import AmapRest, get_amap_rest
from . import dish_catalog
from .transport import choose_transport

ProgressFn = Optional[Callable[[int, str], None]]

# 一天的结束上限(分钟)
DAY_LIMIT_MIN = 23 * 60
# 用餐时长范围
MEAL_MIN, MEAL_MAX, MEAL_FLOOR = 45, 90, 45
# 时钟驱动的用餐时段(分钟)
LUNCH_MIN, LUNCH_MAX, LUNCH_DURATION = 11 * 60 + 30, 13 * 60 + 30, 60
LUNCH_LATE_MAX = 14 * 60 + 30
DINNER_MIN, DINNER_MAX, DINNER_DURATION = 17 * 60, 19 * 60 + 30, 90
# 餐厅 / 酒店检索半径(米)
RESTAURANT_RADIUS = 1500
HOTEL_RADIUS = 3000
# 餐次中文名
MEAL_LABELS = {"lunch": "午餐", "dinner": "晚餐"}
# 时间轴条目排序:先抵达,再景点;用餐紧跟其锚定的景点之后
PHASE_ORDER = {"arrival": 0, "lunch": 1, "attraction": 2, "dinner": 3, "rest": 4}


def _sort_key(item: dict) -> Tuple[int, int, int, int]:
    """时间轴条目的排序键

    午餐排在其锚定的景点之后(进餐本就是游览该景点之后的安排),
    晚餐排在当天最后一个景点之后。位置使用建表顺序(_pos),而不是生成顺序。
    """
    kind = str(item.get("type") or "")
    anchor = int(item.get("anchor_pos", item.get("anchor_seq", -1)) or 0)
    position = int(item.get("_pos", item.get("seq", 0)) or 0)
    if kind == "meal":
        return (2, anchor + 1, 1, position)
    if kind == "attraction":
        return (2, anchor + 1, 0, position)
    return (PHASE_ORDER.get(kind, 9), 0, 0, position)


def _next_anchor_pos(order: List[dict]) -> int:
    """取下一个可用的锚点位置(保证排在当前所有条目之后)"""
    if not order:
        return 0
    return max(int(item.get("_pos", 0) or 0) for item in order) + 1


def _in_meal_window(clock: int, low: int, high: int) -> bool:
    """判断时钟是否落在用餐时段 [low, high]"""
    return int(low) <= int(clock) <= int(high)


# 住宿类型 → 参考房价(元/晚)
ACCOMMODATION_PRICE = [
    ("青年旅舍", 120), ("民宿", 300), ("客栈", 300), ("经济", 220),
    ("舒适", 450), ("四星", 550), ("高档", 600), ("五星", 900), ("豪华", 900),
]
DEFAULT_HOTEL_PRICE = 350
DEFAULT_MEAL_COST = 80

# 进度上报次数上限
_MAX_PROGRESS_CALLS = 30


# ============ 基础工具 ============

def _parse_hhmm(value: Any, default_min: int = 9 * 60) -> int:
    """把 "HH:MM" 解析成分钟数"""
    try:
        if value is None:
            return default_min
        text = str(value).strip()
        if not text:
            return default_min
        if ":" in text:
            parts = text.split(":")
            hour = int(str(parts[0]).strip() or 0)
            minute = int(str(parts[1]).strip() or 0) if len(parts) > 1 else 0
        elif text.isdigit() and len(text) == 4:
            hour, minute = int(text[:2]), int(text[2:])
        else:
            hour, minute = int(float(text)), 0
        if hour < 0 or hour > 23:
            return default_min
        return hour * 60 + max(0, min(59, minute))
    except Exception:
        return default_min


def _fmt_hhmm(minutes: Any) -> str:
    """把分钟数格式化成 "HH:MM" """
    try:
        value = int(round(float(minutes)))
    except (TypeError, ValueError):
        value = 9 * 60
    value = max(0, value)
    return f"{(value // 60) % 24:02d}:{value % 60:02d}"


def _safe_float(value: Any, default: float = 0.0) -> float:
    """宽松地把任意值转成 float"""
    try:
        if value is None or value == "":
            return default
        result = float(value)
        if math.isnan(result) or math.isinf(result):
            return default
        return result
    except (TypeError, ValueError):
        return default


def _safe_int(value: Any, default: int = 0) -> int:
    """宽松地把任意值转成 int"""
    try:
        if value is None or value == "":
            return default
        return int(round(float(value)))
    except (TypeError, ValueError):
        return default


def _coords_of(obj: Any) -> Optional[Tuple[float, float]]:
    """安全地读取坐标

    Args:
        obj: 具备 location 属性的对象,或 (lng, lat) 元组/列表

    Returns:
        (lng, lat);缺失或为 0 时返回 None
    """
    try:
        if obj is None:
            return None
        if isinstance(obj, (tuple, list)):
            if len(obj) < 2:
                return None
            lng, lat = _safe_float(obj[0]), _safe_float(obj[1])
        elif isinstance(obj, dict):
            location = obj.get("location")
            if isinstance(location, (tuple, list)) and len(location) >= 2:
                lng, lat = _safe_float(location[0]), _safe_float(location[1])
            elif isinstance(location, dict):
                lng = _safe_float(location.get("longitude"))
                lat = _safe_float(location.get("latitude"))
            else:
                lng = _safe_float(obj.get("lng") or obj.get("longitude"))
                lat = _safe_float(obj.get("lat") or obj.get("latitude"))
        else:
            location = getattr(obj, "location", None)
            if location is None:
                return None
            lng = _safe_float(getattr(location, "longitude", 0.0))
            lat = _safe_float(getattr(location, "latitude", 0.0))
        if lng == 0 or lat == 0:
            return None
        if not (-180.0 <= lng <= 180.0) or not (-90.0 <= lat <= 90.0):
            return None
        return (lng, lat)
    except Exception:
        return None


def _make_location(pair: Optional[Tuple[float, float]]) -> Optional[Location]:
    """把坐标元组转成 Location"""
    if not pair:
        return None
    return Location(longitude=round(float(pair[0]), 6), latitude=round(float(pair[1]), 6))


def _travelers(request: TripRequest) -> int:
    """取出行人数(容错)"""
    try:
        count = int(getattr(request, "travelers", 2) or 2)
    except (TypeError, ValueError):
        count = 2
    return max(1, min(20, count))


def _distance_text(meters: Any) -> str:
    """把米数转成中文距离描述"""
    value = _safe_float(meters, 0.0)
    if value <= 0:
        return ""
    if value < 1000:
        return f"约{int(round(value))}米"
    return f"约{value / 1000.0:.1f}公里"


def _default_hotel_price(accommodation: str) -> int:
    """根据住宿偏好推断参考房价"""
    text = str(accommodation or "")
    for keyword, price in ACCOMMODATION_PRICE:
        if keyword in text:
            return price
    return DEFAULT_HOTEL_PRICE


class _ProgressReporter:
    """进度上报器

    * 百分比只增不减
    * 支持按「已完成/总数」在给定区间内线性推进
    * 调用次数有上限,避免刷屏
    """

    def __init__(self, progress: ProgressFn):
        self._progress = progress
        self._calls = 0
        self._last = 0
        self._lock = threading.Lock()
        self.total_days = 1

    def report(self, percent: int, message: str) -> None:
        """上报一次进度"""
        if self._progress is None:
            return
        with self._lock:
            if self._calls >= _MAX_PROGRESS_CALLS:
                return
            value = max(self._last, int(percent))
            self._last = value
            self._calls += 1
        try:
            self._progress(value, message)
        except Exception:
            pass

    def report_step(self, low: int, high: int, done: int, total: int, message: str) -> None:
        """按「已完成/总数」在 [low, high] 区间内推进进度

        Args:
            low: 区间下界(百分比)
            high: 区间上界(百分比)
            done: 已完成数量
            total: 总数量
            message: 中文提示
        """
        try:
            total = max(1, int(total))
            done = max(0, min(int(done), total))
            percent = int(low) + int(round((int(high) - int(low)) * done / float(total)))
        except Exception:
            percent = int(low)
        self.report(percent, message)


# ============ 阶段一:景点坐标与元数据 ============

def _city_center(city: str, amap: AmapRest) -> Optional[Tuple[float, float]]:
    """获取城市中心坐标(兜底用)"""
    try:
        return amap.geocode(city, city)
    except Exception:
        return None


def _resolve_attractions(plan: TripPlan, request: TripRequest, amap: AmapRest,
                         reporter: _ProgressReporter) -> None:
    """补齐所有景点的坐标、评分与门票价格(并发)"""
    reporter.report(62, "正在校准景点坐标…")
    try:
        fallback = _city_center(request.city, amap)
        city = request.city

        # 按名称去重,避免同名景点重复请求
        targets: Dict[str, Attraction] = {}
        for day in plan.days or []:
            for attraction in day.attractions or []:
                name = str(getattr(attraction, "name", "") or "").strip()
                if name and name not in targets:
                    targets[name] = attraction

        def resolve(name: str) -> Tuple[str, Optional[Tuple[float, float]], dict]:
            attraction = targets[name]
            address = str(getattr(attraction, "address", "") or "").strip()
            poi: dict = {}
            coords: Optional[Tuple[float, float]] = None
            try:
                pois = amap.text_search(f"{city}{name}", city, offset=3)
                if pois:
                    poi = pois[0]
                    coords = _coords_of({"location": poi.get("location")})
                if not coords and address:
                    coords = amap.geocode(f"{city}{address}", city)
                if not coords:
                    coords = amap.geocode(f"{city}{name}", city)
                if not coords and address:
                    coords = amap.geocode(address, city)
            except Exception:
                coords = coords or None
            return (name, coords, poi)

        resolved: Dict[str, Tuple[Optional[Tuple[float, float]], dict]] = {}
        names = list(targets.keys())
        if names:
            try:
                with ThreadPoolExecutor(max_workers=min(6, len(names))) as pool:
                    for name, coords, poi in pool.map(resolve, names):
                        resolved[name] = (coords, poi)
            except Exception:
                for name in names:
                    key, coords, poi = resolve(name)
                    resolved[key] = (coords, poi)

        for day in plan.days or []:
            for attraction in day.attractions or []:
                try:
                    name = str(getattr(attraction, "name", "") or "").strip()
                    coords, poi = resolved.get(name, (None, {}))
                    if coords:
                        attraction.location = _make_location(coords)
                    else:
                        coords = _coords_of(attraction)

                    if _safe_float(getattr(attraction, "rating", 0), 0.0) <= 0:
                        rating = _safe_float(poi.get("rating"), 0.0)
                        attraction.rating = round(rating, 1) if rating > 0 else 4.3

                    if _safe_int(getattr(attraction, "ticket_price", 0), 0) <= 0:
                        cost = _safe_float(poi.get("cost"), 0.0)
                        if cost > 0:
                            attraction.ticket_price = int(round(cost))

                    if not str(getattr(attraction, "address", "") or "").strip() and poi.get("address"):
                        attraction.address = str(poi["address"])
                    category = str(getattr(attraction, "category", "") or "").strip()
                    if (not category or category == "景点") and poi.get("type"):
                        parts = [part for part in str(poi["type"]).split(";") if part]
                        attraction.category = parts[-1] if parts else "景点"
                    if not getattr(attraction, "poi_id", "") and poi.get("id"):
                        attraction.poi_id = str(poi["id"])
                    if not getattr(attraction, "image_url", None) and poi.get("photos"):
                        attraction.image_url = str(poi["photos"])

                    # 坐标彻底解析不出来时退化到城市中心,保证行程不断裂
                    if not _coords_of(attraction) and fallback:
                        attraction.location = _make_location(fallback)
                except Exception as exc:
                    print(f"⚠️  景点信息补全失败: {exc}")
    except Exception as exc:
        print(f"⚠️  景点坐标校准失败,继续使用原始数据: {exc}")


# ============ 阶段二:餐厅推荐 ============

_around_cache: Dict[Tuple[str, str, int, str, int], List[dict]] = {}
_around_lock = threading.Lock()


def _cached_around(amap: AmapRest, center: Optional[Tuple[float, float]], keywords: str,
                   radius: int, types: str, offset: int) -> List[dict]:
    """带进程内缓存的周边检索

    缓存键包含坐标与参数;同一个进程内重复查询瞬时返回。
    """
    if not center:
        return []
    key = (f"{center[0]:.5f}", f"{center[1]:.5f}", int(radius), str(types), int(offset))
    with _around_lock:
        if key in _around_cache:
            return _around_cache[key]
    try:
        client = amap if amap is not None else get_amap_rest()
        result = client.around_search(center[0], center[1], keywords, radius, types, offset)
    except Exception:
        result = []
    with _around_lock:
        _around_cache[key] = result
    return result


def _cuisine_of(poi: dict) -> str:
    """从高德 POI 的 type 字段提取菜系关键词(仅取明确指向的菜系)"""
    return dish_catalog.normalize_cuisine(str(poi.get("type") or "")) or ""


def _specific_cuisine(poi: dict) -> str:
    """为**这一家**店推断招牌菜依据的菜系词

    高德的 type 形如 "餐饮服务;中餐厅;北京菜"。必须逐段判断,只把最后一段
    这种具体菜系当作依据:

    * 只用该店自己的 type 与店名,绝不跨店共享任何状态
    * "中餐厅/家常菜/地方菜" 等通用类型不构成菜系,交由城市菜单兜底
    * 咖啡/茶饮/甜品/面包甜点只在店名或 type 明确指向时才生效

    Args:
        poi: 高德的单个 POI

    Returns:
        菜系关键词(可能为空字符串,由城市菜单兜底)
    """
    raw_type = str(poi.get("type") or "")
    parts = [part.strip() for part in raw_type.split(";") if part.strip()]
    name = str(poi.get("name") or "")

    # 1) 优先使用最具体的类型段
    for part in reversed(parts):
        if part in dish_catalog.GENERIC_CUISINE_KEYS:
            continue
        key = dish_catalog.normalize_cuisine(part)
        if key:
            return key

    # 2) 类型不够具体时,看店名是否明确指向某菜系
    if name:
        key = dish_catalog.normalize_cuisine(name)
        if key:
            return key

    return ""


def _venue_tags(poi: dict, cost: float) -> List[str]:
    """生成餐厅标签(菜系 + 人均)"""
    tags: List[str] = []
    parts = [part for part in str(poi.get("type") or "").split(";") if part]
    if len(parts) >= 3 and parts[2] not in tags:
        tags.append(parts[2])
    cuisine = _cuisine_of(poi)
    if cuisine and cuisine not in tags:
        tags.append(cuisine)
    if not tags and parts:
        tags.append(parts[-1])
    if cost > 0:
        tags.append(f"人均约{int(round(cost))}元")
    return tags[:4]


def _sanitize_tel(value: Any) -> str:
    """清洗电话号码

    高德偶尔返回「010-63333357;010-63333367;13009885155」这类多号码串,
    这里按分隔符拆分、去重,只保留第一个;超过 20 个字符的一律留空。

    Args:
        value: 原始电话文本

    Returns:
        单个干净号码,或空字符串
    """
    text = str(value or "").strip()
    if not text:
        return ""
    parts = [part.strip() for part in re.split(r"[;,、;；\s]+", text) if part.strip()]
    if not parts:
        return ""
    first = parts[0]
    if len(first) > 20:
        return ""
    return first


def _sanitize_address(value: Any) -> str:
    """清洗明显重复的地址串

    形如「北京市朝阳区建国路87号;北京市朝阳区建国路87号」的重复地址会被折叠成一个。

    Args:
        value: 原始地址文本

    Returns:
        去重后的地址
    """
    text = str(value or "").strip()
    if not text:
        return ""
    parts = [part.strip() for part in re.split(r"[;；,、]+", text) if part.strip()]
    result: List[str] = []
    for part in parts:
        if part not in result:
            result.append(part)
    merged = ";".join(result)
    # 整串完全重复(无分隔符)时对半裁剪
    if len(merged) >= 8 and len(merged) % 2 == 0:
        half = len(merged) // 2
        if merged[:half] == merged[half:]:
            return merged[:half]
    return merged


def _poi_to_venue(poi: dict, city: str, travelers: int, kind: str = "restaurant",
                  seed: int = 0) -> Optional[Venue]:
    """把高德 POI 转成 Venue"""
    try:
        name = str(poi.get("name") or "").strip()
        if not name:
            return None
        cost = _safe_float(poi.get("cost"), 0.0)
        # 招牌菜只依据本店的类型/店名推断,不共享任何跨店状态
        menu = dish_catalog.signature_dishes(city, _specific_cuisine(poi), name, seed) \
            if kind == "restaurant" else []

        distance_text = _distance_text(_safe_float(poi.get("distance_m"), 0.0))
        rating = _safe_float(poi.get("rating"), 0.0)

        parts: List[str] = []
        if menu:
            parts.append("招牌菜有" + "、".join(menu[:3]))
        if distance_text:
            parts.append(f"距景点{distance_text}")
        if rating > 0:
            parts.append(f"评分{rating:.1f}")
        if cost > 0:
            parts.append(f"人均约{int(round(cost))}元")
        description = ",".join(parts) if parts else f"{city}口碑不错的用餐选择"

        return Venue(
            name=name,
            kind=kind,
            address=_sanitize_address(poi.get("address")),
            location=_make_location(_coords_of({"location": poi.get("location")})),
            rating=round(rating, 1),
            cost=round(cost, 1),
            tags=_venue_tags(poi, cost),
            description=description,
            distance=distance_text,
            tel=_sanitize_tel(poi.get("tel")),
            photo=str(poi.get("photos") or ""),
            party_size=travelers,
            menu=menu,
            source="amap",
        )
    except Exception:
        return None


def _taste_match(poi: dict, keywords: List[str]) -> bool:
    """判断 POI 是否符合口味偏好"""
    if not keywords:
        return False
    text = f"{poi.get('name', '')}|{poi.get('type', '')}"
    return any(keyword and keyword in text for keyword in keywords)


def _fake_venue(city: str, cuisine: str, name: str, travelers: int, seed: int = 0) -> Venue:
    """构造明确标记为 fallback 的兜底餐厅"""
    menu = dish_catalog.signature_dishes(city, cuisine, name, seed)
    return Venue(
        name=name,
        kind="restaurant",
        address=city,
        location=None,
        rating=4.2,
        cost=float(DEFAULT_MEAL_COST),
        tags=[cuisine or "本地菜", f"人均约{DEFAULT_MEAL_COST}元"],
        description="、".join(menu[:3]) + f",{city}本地人气选择(离线推荐)",
        distance="",
        tel="",
        photo="",
        party_size=travelers,
        menu=menu,
        source="fallback",
    )


def _generic_venues(city: str, cuisine: str, travelers: int, seed: int = 0) -> List[Venue]:
    """高德返回为空时,用城市菜谱构造两家兜底餐厅"""
    names = [f"{city}老字号风味馆", f"{city}特色小吃店"]
    return [_fake_venue(city, cuisine, name, travelers, seed + index)
            for index, name in enumerate(names)]


def _search_venues(amap: AmapRest, center: Optional[Tuple[float, float]], city: str,
                   travelers: int, taste_keywords: List[str], seed: int = 0,
                   limit: int = 3) -> List[Venue]:
    """围绕某个景点检索餐厅

    Args:
        amap: 高德 REST 客户端
        center: 检索中心坐标
        city: 城市
        travelers: 出行人数
        taste_keywords: 口味偏好关键词
        seed: 稳定随机种子
        limit: 返回条数上限

    Returns:
        Venue 列表(失败返回空列表)
    """
    if not center:
        return []
    try:
        pois = _cached_around(amap, center, "", RESTAURANT_RADIUS, "050000", 10)
        if not pois:
            return []

        candidates = pois
        if taste_keywords:
            matched = [poi for poi in pois if _taste_match(poi, taste_keywords)]
            if matched:
                candidates = matched

        # 评级门槛逐级放宽 4.0 → 3.5 → 不限
        for threshold in (4.0, 3.5, 0.0):
            filtered = [poi for poi in candidates
                        if _safe_float(poi.get("rating"), 0.0) >= threshold]
            if len(filtered) >= limit or threshold == 0.0:
                candidates = filtered
                break

        ranked = sorted(candidates,
                         key=lambda item: (-_safe_float(item.get("rating"), 0.0),
                                           _safe_float(item.get("distance_m"), 0.0)))
        venues: List[Venue] = []
        for index, poi in enumerate(ranked[:limit]):
            venue = _poi_to_venue(poi, city, travelers, "restaurant", seed + index)
            if venue:
                venues.append(venue)
        return venues
    except Exception as exc:
        print(f"⚠️  餐厅检索失败: {exc}")
        return []


def _meal_hint(day: DayPlan, meal_type: str) -> Optional[Meal]:
    """取 LLM 提供的该餐次信息"""
    for meal in day.meals or []:
        if str(getattr(meal, "type", "") or "").lower() == meal_type:
            return meal
    return None


def _meal_venue(day: DayPlan, meal_type: str, venues: List[Venue], city: str,
                travelers: int, seed: int) -> Tuple[str, str, List[Venue]]:
    """合成用餐条目的标题、备注与餐厅列表

    高德匹配到真实 POI 时,**展示名一律使用高德名称**,LLM 编出来的店名只作为
    补充说明写进 notes,绝不覆盖真实数据(否则会出现「炸酱面馆」卖海鲜的错位)。

    Returns:
        (title, notes, venues)
    """
    hint = _meal_hint(day, meal_type)
    label = MEAL_LABELS.get(meal_type, "用餐")
    hint_name = str(getattr(hint, "name", "") or "").strip() if hint else ""
    hint_desc = str(getattr(hint, "description", "") or "").strip() if hint else ""

    if venues:
        top = venues[0]
        notes = str(top.description or "")
        supplements: List[str] = []
        if hint_name and hint_name != top.name:
            supplements.append(f"你提到的「{hint_name}」附近可一并比较")
        if hint_desc and hint_desc not in notes:
            supplements.append(hint_desc)
        for piece in supplements:
            if piece and piece not in notes:
                notes = f"{notes};{piece}" if notes else piece
        return (str(top.name), notes, venues)

    if hint and hint_name:
        # 高德没有数据 → 沿用 LLM 推荐
        venue = Venue(
            name=hint_name,
            kind="restaurant",
            address=_sanitize_address(hint.address),
            location=getattr(hint, "location", None),
            rating=4.2,
            cost=float(_safe_int(hint.estimated_cost, 0) or DEFAULT_MEAL_COST),
            tags=[f"{label}推荐"],
            description=hint_desc or f"{label}推荐",
            distance="",
            tel="",
            photo="",
            party_size=travelers,
            menu=dish_catalog.signature_dishes(city, "", hint_name, seed),
            source="llm",
        )
        return (hint_name, hint_desc or f"{label}推荐", [venue])

    # 完全没有数据 → 城市菜谱兜底
    venues = _generic_venues(city, "", travelers, seed)
    title = hint_name or f"{city}{label}推荐"
    notes = f"{label}可参考附近人气餐厅,招牌菜:" + "、".join(venues[0].menu[:3])
    return (title, notes, venues)


# ============ 阶段三:酒店 ============

def _poi_to_hotel_venue(poi: dict, travelers: int) -> Optional[Venue]:
    """把高德 POI 转成酒店 Venue"""
    try:
        name = str(poi.get("name") or "").strip()
        if not name:
            return None
        cost = _safe_float(poi.get("cost"), 0.0)
        if cost <= 0:
            cost = float(DEFAULT_HOTEL_PRICE)
        rooms = max(1, int(math.ceil(travelers / 2.0)))
        tags = [f"{int(round(cost))}元/晚", f"{travelers}人建议预订{rooms}间房"]
        parts = [part for part in str(poi.get("type") or "").split(";") if part]
        if len(parts) >= 3:
            tags.insert(0, parts[2])
        rating = _safe_float(poi.get("rating"), 0.0)
        distance_text = _distance_text(_safe_float(poi.get("distance_m"), 0.0))

        parts_desc = []
        if rating > 0:
            parts_desc.append(f"评分{rating:.1f}")
        parts_desc.append(f"参考价约{int(round(cost))}元/晚")
        if distance_text:
            parts_desc.append(f"距最后一个景点{distance_text}")
        parts_desc.append(f"{travelers}人建议预订{rooms}间房")

        return Venue(
            name=name,
            kind="hotel",
            address=_sanitize_address(poi.get("address")),
            location=_make_location(_coords_of({"location": poi.get("location")})),
            rating=round(rating, 1),
            cost=round(cost, 1),
            tags=tags[:4],
            description=",".join(parts_desc),
            distance=distance_text,
            tel=_sanitize_tel(poi.get("tel")),
            photo=str(poi.get("photos") or ""),
            party_size=travelers,
            menu=[],
            source="amap",
        )
    except Exception:
        return None


def _name_similar(left: str, right: str) -> bool:
    """判断两个酒店名是否指向同一家(宽松包含判断)"""
    a = str(left or "").strip().replace(" ", "")
    b = str(right or "").strip().replace(" ", "")
    if not a or not b:
        return False
    if a == b:
        return True
    shorter, longer = (a, b) if len(a) <= len(b) else (b, a)
    if len(shorter) >= 3 and shorter in longer:
        return True
    for suffix in ("大酒店", "酒店", "宾馆", "饭店", "公寓", "客栈", "度假村"):
        shorter = shorter.replace(suffix, "")
        longer = longer.replace(suffix, "")
    return bool(shorter) and len(shorter) >= 2 and shorter in longer


def _resolve_hotel(amap: AmapRest, day: DayPlan, request: TripRequest,
                   anchor: Optional[Tuple[float, float]], travelers: int) -> Optional[Venue]:
    """解析当天酒店的真实信息"""
    hotel = day.hotel
    if hotel is None:
        return None

    city = request.city
    venue: Optional[Venue] = None
    try:
        pois: List[dict] = []
        if hotel.name:
            pois = _cached_around(amap, anchor, str(hotel.name)[:20], HOTEL_RADIUS, "100000", 10)
        if not pois and hotel.name:
            try:
                client = amap if amap is not None else get_amap_rest()
                pois = client.text_search(f"{city}{hotel.name}", city, offset=3)
            except Exception:
                pois = []

        for poi in pois:
            if _name_similar(str(poi.get("name") or ""), str(hotel.name or "")):
                venue = _poi_to_hotel_venue(poi, travelers)
                break

        if venue is None:
            # LLM 酒店无法核对 → 用高德周边评分最高的酒店替代
            nearby = _cached_around(amap, anchor, str(request.accommodation or "酒店")[:20],
                                    HOTEL_RADIUS, "100000", 10)
            if not nearby:
                nearby = _cached_around(amap, anchor, "", HOTEL_RADIUS, "100000", 10)
            nearby = sorted(nearby, key=lambda item: -_safe_float(item.get("rating"), 0.0))
            for poi in nearby:
                candidate = _poi_to_hotel_venue(poi, travelers)
                if candidate:
                    venue = candidate
                    break
    except Exception as exc:
        print(f"⚠️  酒店核对失败: {exc}")

    if venue is None:
        cost = _default_hotel_price(request.accommodation)
        rooms = max(1, int(math.ceil(travelers / 2.0)))
        venue = Venue(
            name=str(hotel.name or f"{city}{request.accommodation or '舒适型酒店'}"),
            kind="hotel",
            address=_sanitize_address(hotel.address) or city,
            location=_coords_of(hotel),
            rating=_safe_float(hotel.rating, 0.0) or 4.2,
            cost=float(cost),
            tags=[f"{cost}元/晚", f"{travelers}人建议预订{rooms}间房",
                  str(request.accommodation or "舒适型酒店")],
            description=f"{request.accommodation or '舒适型'}住宿,参考价约{cost}元/晚,"
                        f"{travelers}人建议预订{rooms}间房",
            distance=str(hotel.distance or ""),
            tel="",
            photo="",
            party_size=travelers,
            menu=[],
            source="llm",
        )

    # 回写原始 Hotel 字段
    try:
        hotel.location = venue.location or _coords_of(hotel)
        if venue.address:
            hotel.address = venue.address
        if venue.rating > 0:
            hotel.rating = f"{venue.rating:.1f}"
        cost = int(round(venue.cost)) if venue.cost > 0 else _default_hotel_price(request.accommodation)
        hotel.price_range = f"{max(50, int(cost * 0.8))}-{int(cost * 1.2)}元"
        hotel.estimated_cost = cost
        if venue.distance:
            hotel.distance = f"距最后一站{venue.distance}"
        elif not hotel.distance:
            hotel.distance = "距主要景点较近"
        if not hotel.type:
            hotel.type = str(request.accommodation or "舒适型酒店")
        if not hotel.address:
            hotel.address = city
    except Exception as exc:
        print(f"⚠️  酒店信息回写失败: {exc}")

    return venue


# ============ 阶段四:时间轴 ============

def _speed_of(preferences: Optional[List[str]], default: float = 15.0) -> float:
    """取用户可接受交通方式中的最快速度(km/h)

    Args:
        preferences: 用户的交通偏好
        default: 没有可用偏好时的兜底速度

    Returns:
        速度(km/h)
    """
    speeds = {"步行": 12.0, "walking": 12.0, "骑行": 15.0, "cycling": 15.0,
              "公交": 22.0, "bus": 22.0, "地铁": 22.0, "subway": 22.0,
              "打车": 30.0, "taxi": 30.0, "自驾": 30.0, "driving": 30.0}
    best = 0.0
    for item in preferences or []:
        best = max(best, speeds.get(str(item).strip(), 0.0))
    return best if best > 0 else default


def _est_gap_min(distance_m: float, speed_kmh: float) -> int:
    """按直线距离预估两点之间的通勤分钟数

    公式:max(3, ceil(直线距离 * 1.25 / 1000 / 速度 * 60))
    1.25 是路网绕行系数,3 分钟是「同地换场」的最小衔接。

    Args:
        distance_m: 直线距离(米)
        speed_kmh: 速度(km/h)

    Returns:
        预估分钟数
    """
    try:
        distance = max(0.0, float(distance_m or 0))
        speed = float(speed_kmh) if speed_kmh and float(speed_kmh) > 0 else 15.0
    except (TypeError, ValueError):
        distance, speed = 0.0, 15.0
    return max(3, int(math.ceil(distance * 1.25 / 1000.0 / speed * 60.0)))


def _limit_day(order: List[dict], over_min: int) -> int:
    """压缩当天行程,保证不超过 23:00

    先压缩用餐时长(不短于 45 分钟),仍然超时则删掉最不重要的一餐。

    Args:
        order: 当天的条目列表(不含酒店),会被就地修改
        over_min: 当前超出的分钟数

    Returns:
        实际削减的分钟数
    """
    over = max(0, int(over_min or 0))
    if over <= 0:
        return 0
    cut_total = 0

    for item in reversed(order):
        if over <= 0:
            break
        if item.get("type") != "meal" or item.get("deleted"):
            continue
        reducible = max(0, int(item.get("duration_min", 0) or 0) - MEAL_FLOOR)
        cut = min(reducible, over)
        if cut > 0:
            item["duration_min"] = int(item["duration_min"]) - cut
            over -= cut
            cut_total += cut

    while over > 0:
        scores = []
        for index, item in enumerate(order):
            if item.get("type") != "meal" or item.get("deleted"):
                continue
            score = 1 if item.get("meal_type") == "lunch" else 2
            if item.get("late_arrival"):
                score += 10
            scores.append((score, index))
        if not scores:
            break
        scores.sort(key=lambda pair: (-pair[0], -pair[1]))
        victim = order[scores[0][1]]
        victim["deleted"] = True
        removed = int(victim.get("duration_min", 0) or 0)
        over -= removed
        cut_total += removed

    return cut_total


def _build_day(day: DayPlan, request: TripRequest, amap: AmapRest, day_index: int,
               arrival_coords: Optional[Tuple[float, float]],
               start_coords: Optional[Tuple[float, float]],
               reporter: _ProgressReporter) -> None:
    """为一天生成完整时间轴与餐厅推荐

    餐次由「时钟」驱动:先用预估通勤推进时间,只有真正到了饭点才插入用餐条目。

    Args:
        day: 当天的行程(会被就地修改)
        request: 旅行请求
        amap: 高德 REST 客户端
        day_index: 第几天(从 0 开始)
        arrival_coords: 抵达地坐标(第一天用于「交通枢纽 → 首个景点」)
        start_coords: 当天出发地坐标(后续天用酒店坐标)
        reporter: 进度上报器
    """
    city = request.city
    travelers = _travelers(request)
    preferences = list(getattr(request, "transport_preferences", []) or [])
    tastes = dish_catalog.taste_keywords(str(getattr(request, "free_text_input", "") or ""))
    has_arrival = day_index == 0
    arrival_min = _parse_hhmm(getattr(request, "arrival_time", "09:00"), 9 * 60) \
        if has_arrival else 9 * 60

    # 预估通勤用的速度:以用户可接受交通方式中最快的一种推进时钟
    est_speed = _speed_of(preferences, 15.0)

    total_days = max(1, int(getattr(reporter, "total_days", 1) or 1))

    attractions = [item for item in (day.attractions or []) if _coords_of(item)]
    seed_base = day_index * 7

    order: List[dict] = []
    if has_arrival:
        order.append({
            "type": "arrival", "seq": 0, "_pos": 0,
            "title": f"抵达{city}", "address": "", "location": None,
            "duration_min": 0, "notes": "", "venue": None, "attraction": None,
            "meal_type": "",
        })

    next_seq = len(order) + 1
    attraction_count = len(attractions)
    last_attraction_entry: Optional[dict] = None
    lunch_group: Optional[dict] = None
    lunch_recommendation: Optional[dict] = None
    dinner_recommendation: Optional[dict] = None

    def make_meal(meal_type: str, duration: int, seed: int,
                  anchor_pos: Optional[int] = None) -> dict:
        """生成一个用餐条目

        Args:
            meal_type: lunch / dinner
            duration: 用餐时长(分钟)
            seed: 稳定随机种子
            anchor_pos: 锚定的景点位置;不传则锚定在当前最后一个景点之后

        Returns:
            用餐条目 dict
        """
        nonlocal next_seq, lunch_group, lunch_recommendation, dinner_recommendation
        label = "午餐" if meal_type == "lunch" else "晚餐"
        reporter.report_step(66, 82, 0, 2, f"正在挑选第{day_index + 1}天的{label}餐厅…")
        anchor = last_attraction_entry
        venues, near = _recommend_for_slot(amap, anchor, meal_type, city,
                                           travelers, tastes, seed)
        reporter.report_step(66, 82, 1, 2, f"第{day_index + 1}天的{label}候选已就绪…")
        title, notes, venues = _meal_venue(day, meal_type, venues, city, travelers, seed + 10)
        if anchor_pos is None:
            anchor_pos = int(anchor.get("_pos", 0)) if anchor else _next_anchor_pos(order)
        entry = {
            "type": "meal", "seq": next_seq, "_pos": len(order),
            "anchor_pos": int(anchor_pos),
            "title": title, "address": "", "location": None,
            "duration_min": int(duration), "notes": notes, "meal_type": meal_type,
            "venue": venues[0] if venues else None, "attraction": None,
            "late_arrival": bool(has_arrival and arrival_min > LUNCH_MIN),
        }
        next_seq += 1
        order.append(entry)
        if meal_type == "lunch":
            lunch_group = entry
            lunch_recommendation = {"entry": entry, "near": near, "venues": venues}
        else:
            dinner_recommendation = {"entry": entry, "near": near, "venues": venues}
        return entry

    def append_rest(minutes: int, title: str, notes: str) -> dict:
        """插入一段「自由活动」,把时钟自然推到用餐窗口内

        用餐只能落在窗口里,景点逛完得太早时用这段自由活动填补,
        绝不提前上晚餐/午餐。

        Args:
            minutes: 自由活动时长(分钟)
            title: 条目标题
            notes: 给用户的建议

        Returns:
            新的 rest 条目
        """
        nonlocal next_seq, clock
        duration = max(15, min(180, int(minutes or 0)))
        entry = {
            "type": "rest", "seq": next_seq, "_pos": len(order),
            "anchor_pos": _next_anchor_pos(order),
            "title": title, "address": "", "location": None,
            "duration_min": duration, "notes": notes, "venue": None,
            "attraction": None, "meal_type": "",
        }
        next_seq += 1
        order.append(entry)
        clock += duration
        return entry

    # ---- 按「时钟」推进,逐个安排景点与午餐 ----
    # 午餐必须夹在两个景点之间:时钟走到饭点且后面还有景点时,才在「刚结束的景点」之后插入
    clock = arrival_min
    previous_entry: Optional[dict] = order[0] if order else None
    for index, attraction in enumerate(attractions):
        # 出发前若已进入(或即将进入)饭点,先把午餐吃掉再赶路,
        # 否则一段较长的通勤会把午餐一路拖到 15:00 之后。
        if (lunch_group is None
                and last_attraction_entry is not None
                and _in_meal_window(clock, LUNCH_MIN, LUNCH_LATE_MAX)):
            make_meal("lunch", LUNCH_DURATION, seed_base + 1,
                      anchor_pos=int(last_attraction_entry.get("_pos", 0) or 0))
            clock += LUNCH_DURATION

        # 距上一站的预估通勤
        origin = None
        if previous_entry is not None:
            origin = previous_entry.get("location")
            if previous_entry.get("type") == "arrival":
                origin = arrival_coords or origin
        if origin is None:
            origin = start_coords
        clock += _est_gap_min(AmapRest.haversine_m(origin, _coords_of(attraction)), est_speed)

        entry = {
            "type": "attraction", "seq": next_seq, "_pos": len(order),
            "title": str(getattr(attraction, "name", "") or "景点"),
            "address": _sanitize_address(getattr(attraction, "address", "")),
            "location": _coords_of(attraction),
            "duration_min": max(30, _safe_int(getattr(attraction, "visit_duration", 120), 120)),
            "notes": str(getattr(attraction, "description", "") or ""),
            "venue": None, "attraction": attraction, "meal_type": "",
        }
        next_seq += 1
        order.append(entry)
        last_attraction_entry = entry
        previous_entry = entry
        clock += int(entry["duration_min"])

    # 午餐兜底:窗口内没有自然落点时不硬塞到 14:30 之后 ——
    # 仍在 11:30-14:30 内就补一顿(夹在景点之间),否则不排午餐并给出提示。
    if attraction_count > 0 and lunch_group is None and clock <= DAY_LIMIT_MIN:
        if _in_meal_window(clock, LUNCH_MIN, LUNCH_LATE_MAX):
            make_meal("lunch", LUNCH_DURATION, seed_base + 3,
                      anchor_pos=_next_anchor_pos(order))
            clock += LUNCH_DURATION
        elif last_attraction_entry is not None:
            last_attraction_entry["notes"] = (
                str(last_attraction_entry.get("notes") or "")
                + "(景点结束较晚,午餐可在附近自行解决)").strip()

    # ---- 用餐只落在窗口内:不到点就先补自由活动,绝不提前上菜 ----
    def serve_meal_in_window(meal_type: str, low: int, high: int, duration: int,
                             seed: int) -> bool:
        """把一餐安排在 [low, high] 窗口内

        时钟已经在窗口里 → 直接上菜;
        还没到窗口 → 先插一段「自由活动」把时间推到窗口内再上菜;
        已经过了窗口上界 → 不排这一餐(返回 False),由调用方写提示。

        Args:
            meal_type: lunch / dinner
            low: 窗口开始(分钟)
            high: 窗口结束(分钟)
            duration: 用餐时长(分钟)
            seed: 稳定随机种子

        Returns:
            是否成功排上了这一餐
        """
        nonlocal clock
        if clock < low:
            rest_minutes = low - clock
            if clock >= 16 * 60:
                title = "自由活动"
                notes = "可在附近茶馆歇脚,或提前到餐厅排队"
            else:
                rest_minutes = min(120, max(rest_minutes, 30))
                title = "自由活动 · 可在附近街区逛逛"
                notes = "时间还早,可在附近街区散步或回酒店稍作休息,到点再去吃饭"
            append_rest(rest_minutes, title, notes)
        if _in_meal_window(clock, low, high):
            # 注意:锚点必须在 append_rest 之后再取,否则排序时自由活动会跑到用餐前面
            make_meal(meal_type, duration, seed, anchor_pos=_next_anchor_pos(order))
            clock += duration
            return True
        return False

    # 晚餐:所有景点走完后,只落在 17:00-19:30
    if attraction_count > 0:
        if not serve_meal_in_window("dinner", DINNER_MIN, DINNER_MAX,
                                    DINNER_DURATION, seed_base + 5):
            if clock > 21 * 60:
                tail_entry = order[-1] if order else last_attraction_entry
                if tail_entry is not None:
                    tail_entry["notes"] = (
                        str(tail_entry.get("notes") or "")
                        + "(游览结束较晚,晚餐可自行在附近觅食)").strip()
            elif 19 * 60 + 30 < clock <= 21 * 60:
                # 刚过晚餐窗口(19:30-21:00):先歇一会儿,再排一顿稍晚的晚餐,
                # 总比直接告诉用户「自行觅食」更贴心。
                append_rest(20, "自由活动", "稍作休整,随后安排一顿稍晚的晚餐")
                if not serve_meal_in_window("dinner", DINNER_MIN, 20 * 60 + 30,
                                            DINNER_DURATION, seed_base + 5):
                    tail_entry = order[-1] if order else last_attraction_entry
                    if tail_entry is not None:
                        tail_entry["notes"] = (
                            str(tail_entry.get("notes") or "")
                            + "(用餐时间偏晚,建议在酒店附近解决)").strip()
            elif last_attraction_entry is not None and clock < DINNER_MIN:
                last_attraction_entry["notes"] = (
                    str(last_attraction_entry.get("notes") or "")
                    + "(晚餐时间较紧,可在附近自行觅食)").strip()

    # 晚餐与酒店固定在末尾,午餐严格跟随其锚点景点(_pos 在构造条目时已写入)
    order.sort(key=_sort_key)

    # ---- 酒店 ----
    anchor: Optional[Tuple[float, float]] = _coords_of(last_attraction_entry) \
        if last_attraction_entry is not None else None
    reporter.report_step(84, 88, day_index + 1, total_days,
                         f"正在核对第{day_index + 1}天的住宿…")
    hotel_venue: Optional[Venue] = None
    try:
        hotel_venue = _resolve_hotel(amap, day, request, anchor, travelers)
    except Exception as exc:
        print(f"⚠️  酒店处理失败: {exc}")

    hotel_name = str(getattr(day.hotel, "name", "") or "") if day.hotel else ""
    if not hotel_name:
        hotel_name = f"{city}{request.accommodation or '舒适型酒店'}"
    hotel_coords = _coords_of(hotel_venue)

    hotel_entry = {
        "type": "hotel", "seq": 10 ** 6,
        "title": f"入住 {hotel_name}",
        "address": _sanitize_address(getattr(day.hotel, "address", "")) if day.hotel else "",
        "location": hotel_coords,
        "duration_min": 0, "notes": "办理入住,建议提前电话确认房型与到店时间",
        "venue": hotel_venue, "attraction": None, "meal_type": "",
    }

    debug = bool(os.environ.get("TL_DEBUG"))
    built = [item for item in order if not item.get("deleted")]

    def point_for(entry: Optional[dict]) -> Optional[Tuple[float, float]]:
        """取一个条目的实际坐标(用餐条目用其锚定景点代替)"""
        if entry is None:
            return None
        point = entry.get("location")
        if point is None and entry.get("type") == "meal":
            point = anchor
        return point

    # ---- 计算每段的真实耗时(做 23:00 压缩前先算,压缩后再写时刻) ----
    reporter.report(76, f"正在计算第{day_index + 1}天的通勤路线…")
    for index, item in enumerate(built):
        following = built[index + 1] if index + 1 < len(built) else None
        origin = point_for(item)
        if item.get("type") == "arrival":
            origin = arrival_coords or origin
        if origin is None:
            origin = start_coords

        destination = point_for(following)
        if destination is None:
            destination = hotel_coords or origin

        straight = AmapRest.haversine_m(origin, destination)
        item["_gap_m"] = straight
        transport: Optional[TransportPlan] = None
        try:
            transport = choose_transport(origin, destination, straight, preferences,
                                         travelers, city, amap)
        except Exception as exc:
            print(f"⚠️  交通方案计算失败: {exc}")

        leg_min = int(transport.duration_min) if transport is not None \
            else _est_gap_min(straight, est_speed)
        if origin is not None and destination is not None and straight <= 0:
            # 同一位置内换场(例如就在景点里吃饭)→ 不需要额外通勤时间
            leg_min = 0
        item["next_transport"] = transport
        item["next_title"] = str(following.get("title") if following
                                 else hotel_entry.get("title") or "")
        item["_real_leg"] = int(leg_min)

    # ---- 预估当天总时长,必要时压缩到 23:00 之前 ----
    def projected(times: List[dict]) -> int:
        """按已算出的真实耗时预估从出发到入住酒店的总分钟数"""
        total = 0
        for item in times:
            total += int(item.get("_real_leg", 0) or 0)
            total += int(item.get("duration_min", 0) or 0)
        last_point = point_for(times[-1]) if times else None
        source = last_point or start_coords or arrival_coords
        total += _est_gap_min(AmapRest.haversine_m(source, hotel_coords), 30.0)
        return total

    rough = arrival_min + projected(built)
    if debug:
        print(f"   [rough] {rough} ({_fmt_hhmm(rough)}) limit={DAY_LIMIT_MIN} "
              f"over={rough - DAY_LIMIT_MIN}")

    # _limit_day 返回「实际削减的分钟数」,据此重算时钟,压缩才真正生效
    attempts = 0
    while rough > DAY_LIMIT_MIN and attempts < 4:
        attempts += 1
        cut = _limit_day(built, rough - DAY_LIMIT_MIN)
        if cut <= 0:
            break
        built = [item for item in built if not item.get("deleted")]
        rough -= int(cut)
    if lunch_recommendation and lunch_recommendation["entry"].get("deleted"):
        lunch_recommendation = None
    if dinner_recommendation and dinner_recommendation["entry"].get("deleted"):
        dinner_recommendation = None

    # ---- 串联时间轴:抵达 → 景点/用餐(用真实耗时顺延)→ 酒店 ----
    clock = arrival_min
    for index, item in enumerate(built):
        if index == 0 and not has_arrival:
            point = point_for(item)
            clock += _est_gap_min(AmapRest.haversine_m(start_coords, point), est_speed)
        item["arrive_time"] = clock
        item["leave_time"] = clock + int(item.get("duration_min", 0) or 0)
        clock = item["leave_time"] + int(item.get("_real_leg", 0) or 0)

    if built:
        built[-1]["next_title"] = str(hotel_entry["title"])
        hotel_entry["arrive_time"] = built[-1]["leave_time"] + _est_gap_min(
            AmapRest.haversine_m(point_for(built[-1]) or start_coords, hotel_coords), 30.0)
    else:
        hotel_entry["arrive_time"] = arrival_min
    if hotel_entry["arrive_time"] > DAY_LIMIT_MIN:
        hotel_entry["arrive_time"] = DAY_LIMIT_MIN
        hotel_entry["notes"] = str(hotel_entry["notes"]) + "(到店较晚,建议提前联系酒店)"
    built.append(hotel_entry)
    if debug:
        print("   [built] " + " | ".join(
            f"{_fmt_hhmm(i.get('arrive_time'))} {i.get('title')}" for i in built))

    # ---- 转成 TimelineEntry 并回写 DayPlan ----
    timeline: List[TimelineEntry] = []
    for index, item in enumerate(built):
        try:
            following = built[index + 1] if index + 1 < len(built) else None
            notes = str(item.get("notes") or "")
            if item.get("type") == "arrival":
                notes = notes or "抵达后建议先寄存行李,再前往第一个景点;如行李较多可打车直达。"
            timeline.append(TimelineEntry(
                seq=index,
                type=str(item.get("type") or "attraction"),
                title=str(item.get("title") or ""),
                address=str(item.get("address") or ""),
                location=_make_location(item.get("location")),
                arrive_time=_fmt_hhmm(item.get("arrive_time")),
                leave_time=("次日" if item.get("type") == "hotel"
                            else _fmt_hhmm(item.get("leave_time"))),
                duration_min=max(0, int(item.get("duration_min", 0) or 0)),
                next_title=str(item.get("next_title")
                               or (following.get("title") if following else "")),
                next_transport=item.get("next_transport"),
                notes=notes,
                venue=item.get("venue"),
                attraction=item.get("attraction"),
                meal_type=str(item.get("meal_type") or ""),
            ))
        except Exception as exc:
            print(f"⚠️  时间轴条目生成失败: {exc}")

    day.timeline = timeline
    if timeline:
        day.start_time = timeline[0].arrive_time
        real = [item for item in timeline if item.type != "hotel"]
        day.end_time = real[-1].leave_time if real else timeline[-1].arrive_time

    recommendations: List[RestaurantRecommendation] = []
    for slot in (lunch_recommendation, dinner_recommendation):
        if not slot:
            continue
        try:
            entry = slot["entry"]
            recommendations.append(RestaurantRecommendation(
                meal_type=str(entry.get("meal_type") or ""),
                near=str(slot.get("near") or "附近景点"),
                venues=list(slot.get("venues") or []),
            ))
        except Exception as exc:
            print(f"⚠️  餐厅推荐生成失败: {exc}")
    if recommendations:
        day.restaurants = recommendations

def _recommend_for_slot(amap: AmapRest, anchor_entry: Optional[dict], meal_type: str, city: str,
                        travelers: int, tastes: List[str],
                        seed: int) -> Tuple[List[Venue], str]:
    """为某个餐次检索餐厅

    Returns:
        (venues, 邻近景点名)
    """
    anchor_name = ""
    center: Optional[Tuple[float, float]] = None
    if anchor_entry is not None:
        center = anchor_entry.get("location")
        attraction = anchor_entry.get("attraction")
        if attraction is not None:
            anchor_name = str(getattr(attraction, "name", "") or "")
        if not anchor_name:
            anchor_name = str(anchor_entry.get("title") or "")
    venues = _search_venues(amap, center, city, travelers, tastes, seed)
    return venues, anchor_name


# ============ 预算 ============

def _merge_budget(plan: TripPlan, request: TripRequest) -> Budget:
    """根据充实后的行程重新计算预算"""
    travelers = _travelers(request)
    rooms = max(1, int(math.ceil(travelers / 2.0)))
    days = plan.days or []
    nights = max(1, len(days) - 1) if days else 0

    tickets = 0
    meals = 0
    hotels = 0
    transport = 0

    for day in days:
        for attraction in day.attractions or []:
            tickets += max(0, _safe_int(getattr(attraction, "ticket_price", 0), 0)) * travelers

        day_meal_total = 0
        for recommendation in day.restaurants or []:
            venues = [venue for venue in (recommendation.venues or [])
                      if _safe_float(getattr(venue, "cost", 0), 0) > 0]
            if venues:
                day_meal_total += _safe_int(_safe_float(venues[0].cost, 0.0), 0) * travelers
                continue
            for meal in (day.meals or []):
                if str(meal.type or "") == str(recommendation.meal_type or ""):
                    day_meal_total += max(0, _safe_int(meal.estimated_cost, 0))
                    break
        if day_meal_total <= 0:
            day_meal_total = sum(max(0, _safe_int(meal.estimated_cost, 0))
                                 for meal in (day.meals or []))
        if day_meal_total <= 0:
            day_meal_total = DEFAULT_MEAL_COST * travelers
        meals += day_meal_total

        if day.hotel is not None:
            unit = _safe_int(getattr(day.hotel, "estimated_cost", 0), 0)
            if unit <= 0:
                unit = _default_hotel_price(request.accommodation)
            hotels += unit * rooms

        for entry in day.timeline or []:
            transport += max(0, _safe_int(getattr(entry.next_transport, "cost", 0), 0))

    if hotels == 0:
        hotels = _default_hotel_price(request.accommodation) * rooms * nights

    return Budget(
        total_attractions=int(tickets),
        total_hotels=int(hotels),
        total_meals=int(meals),
        total_transportation=int(transport),
        total=int(tickets + hotels + meals + transport),
    )


def _has_attractions(plan: TripPlan) -> bool:
    """判断行程是否包含可用景点"""
    for day in plan.days or []:
        if day.attractions:
            return True
    return False


def plan_has_attractions(plan: TripPlan) -> bool:
    """对外暴露:判断行程是否包含可用的景点"""
    return _has_attractions(plan)


# ============ 对外入口 ============

def enrich_plan(plan: TripPlan, request: TripRequest, amap: AmapRest,
                progress: ProgressFn = None) -> TripPlan:
    """用高德实时数据充实行程(时间轴 / 交通 / 餐厅 / 酒店 / 预算)

    Args:
        plan: LLM 生成的原始行程
        request: 用户请求(提供人数、偏好、抵达时间等)
        amap: 高德 REST 客户端
        progress: 进度回调 (percent, 中文消息)

    Returns:
        充实后的行程;发生灾难性失败时原样返回输入 plan
    """
    reporter = _ProgressReporter(progress)
    try:
        if plan is None:
            return plan

        days = list(plan.days or [])
        reporter.total_days = max(1, len(days))

        # 阶段一:景点坐标与元数据
        reporter.report(62, "正在校准景点坐标…")
        _resolve_attractions(plan, request, amap, reporter)

        # 抵达点坐标(用于第一天「交通枢纽 → 首个景点」的衔接)
        arrival_coords: Optional[Tuple[float, float]] = None
        reporter.report(64, "正在定位抵达地点…")
        try:
            free_text = str(getattr(request, "free_text_input", "") or "")
            for keyword in ("机场", "火车站", "高铁站", "长途汽车站", "南站", "北站", "东站", "西站"):
                if keyword in free_text:
                    arrival_coords = amap.geocode(f"{request.city}{keyword}", request.city)
                    if arrival_coords:
                        break
            if not arrival_coords:
                arrival_coords = amap.geocode(request.city, request.city)
        except Exception:
            arrival_coords = None

        # 阶段二:逐日时间轴(交通 / 餐厅 / 酒店都在这里真实计算)
        # 进度在 62→88 的区间里按「已完成天数」比例推进,每天开始与结束各报一次
        city_center = _city_center(request.city, amap) or arrival_coords
        day_start_coords = city_center
        total_days = max(1, len(days))
        for day_index, day in enumerate(days):
            reporter.report(62 + int(round(8 * day_index / float(total_days))),
                            f"正在编排第{day_index + 1}天行程…")
            try:
                _build_day(day, request, amap, day_index, arrival_coords,
                           day_start_coords, reporter)
            except Exception as exc:
                print(f"⚠️  第{day_index + 1}天时间轴生成失败: {exc}")
            reporter.report(62 + int(round(8 * (day_index + 1) / float(total_days))),
                            f"第{day_index + 1}天行程已排好…")
            # 第二天从「今天入住的酒店」出发
            if day.timeline:
                for entry in reversed(day.timeline):
                    if entry.type == "hotel":
                        day_start_coords = _coords_of(entry.location) or day_start_coords
                        break

        # 阶段三:预算
        reporter.report(92, "正在重新计算预算…")
        try:
            plan.budget = _merge_budget(plan, request)
        except Exception as exc:
            print(f"⚠️  预算重算失败: {exc}")

        return plan
    except Exception as exc:
        print(f"⚠️  行程充实失败,返回原始计划: {exc}")
        import traceback
        traceback.print_exc()
        return plan
