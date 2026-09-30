"""交通方式选择

根据两点间的直线距离、用户的交通偏好、出行人数,挑选最合适的交通方式,
并结合高德实时路径规划结果给出耗时、距离与费用。

任何高德调用失败都会退化为「按直线距离估算」,并清楚地写在 reason 中,
保证行程规划永远有可用的交通方案。
"""

import math
from typing import Any, List, Optional, Tuple

from ..models.schemas import TransportPlan
from .amap_rest import AmapRest

# 交通方式别名 → 标准模式
MODE_ALIASES = {
    "步行": "walking",
    "走路": "walking",
    "walking": "walking",
    "walk": "walking",
    "公交": "bus",
    "公共汽车": "bus",
    "巴士": "bus",
    "bus": "bus",
    "地铁": "subway",
    "metro": "subway",
    "subway": "subway",
    "轨道交通": "subway",
    "打车": "taxi",
    "出租": "taxi",
    "出租车": "taxi",
    "taxi": "taxi",
    "骑行": "cycling",
    "自行车": "cycling",
    "单车": "cycling",
    "bike": "cycling",
    "cycling": "cycling",
    "自驾": "driving",
    "开车": "driving",
    "驾车": "driving",
    "driving": "driving",
}

# 标准模式 → 中文标签
MODE_LABELS = {
    "walking": "步行",
    "bus": "公交",
    "subway": "地铁/公交",
    "taxi": "打车",
    "cycling": "骑行",
    "driving": "自驾",
}

# 标准模式 → 估算速度(km/h)与固定附加耗时(分钟)
ESTIMATE_SPEED = {
    "walking": 12.0,
    "cycling": 15.0,
    "subway": 22.0,
    "bus": 22.0,
    "taxi": 30.0,
    "driving": 30.0,
}
ESTIMATE_OVERHEAD_MIN = {
    "walking": 0.0,
    "cycling": 0.0,
    "subway": 8.0,
    "bus": 8.0,
    "taxi": 4.0,
    "driving": 4.0,
}

# 候选方案:(内部 mode, 中文标签)
_CANDIDATES = {
    "walking": ("walking", "步行"),
    "cycling": ("cycling", "骑行"),
    "transit": ("subway", "地铁/公交"),
    "taxi": ("taxi", "打车"),
    "driving": ("driving", "自驾"),
}


def normalize_mode(value: str) -> str:
    """把用户偏好中的写法统一成标准模式

    Args:
        value: 如 "步行" / "地铁" / "taxi"

    Returns:
        标准模式字符串;无法识别时返回原值的小写形式
    """
    if not value:
        return ""
    text = str(value).strip()
    if text in MODE_ALIASES:
        return MODE_ALIASES[text]
    lowered = text.lower()
    if lowered in MODE_ALIASES:
        return MODE_ALIASES[lowered]
    for alias, mode in MODE_ALIASES.items():
        if alias and alias in text:
            return mode
    return lowered


def _accepted_modes(preferences: Optional[List[str]]) -> List[str]:
    """把偏好列表转换成标准模式集合

    Args:
        preferences: 用户交通偏好

    Returns:
        标准模式列表;偏好为空视为全部接受
    """
    if not preferences:
        return list(_CANDIDATES.keys()) + []

    modes: List[str] = []
    for item in preferences:
        mode = normalize_mode(item)
        if not mode:
            continue
        # subway / bus 都属于 transit 候选
        if mode in ("subway", "bus"):
            if "transit" not in modes:
                modes.append("transit")
        elif mode in _CANDIDATES and mode not in modes:
            modes.append(mode)
        elif mode in ("walking", "cycling", "taxi", "driving") and mode not in modes:
            modes.append(mode)
    return modes


def candidate_order(straight_m: float) -> List[str]:
    """按距离给出候选交通方式的优先顺序

    Args:
        straight_m: 直线距离(米)

    Returns:
        候选键列表,如 ["walking", "cycling", "transit", "taxi"]
    """
    try:
        distance = float(straight_m or 0)
    except (TypeError, ValueError):
        distance = 0.0

    if distance <= 0:
        # 距离未知,给出通用顺序
        return ["transit", "taxi", "walking", "cycling", "driving"]
    if distance < 1200:
        return ["walking", "cycling", "transit", "taxi", "driving"]
    if distance < 3500:
        return ["cycling", "walking", "transit", "taxi", "driving"]
    if distance <= 10000:
        return ["transit", "taxi", "cycling", "driving", "walking"]
    return ["transit", "taxi", "driving", "cycling", "walking"]


def _estimate(straight_m: float, mode: str) -> Tuple[int, int]:
    """按直线距离估算距离与耗时

    Args:
        straight_m: 直线距离(米)
        mode: 标准模式

    Returns:
        (distance_m, duration_min);耗时 = 路网距离 / 该方式的平均速度
    """
    return _estimate_metric(straight_m, mode, ESTIMATE_SPEED.get(mode, 12.0))


def _estimate_metric(straight_m: float, mode: str, speed_kmh: float) -> Tuple[int, int]:
    """按直线距离与给定速度估算路网距离与耗时

    Args:
        straight_m: 直线距离(米)
        mode: 标准模式
        speed_kmh: 平均速度(km/h)

    Returns:
        (distance_m, duration_min)
    """
    distance = max(0.0, float(straight_m or 0))
    # 实际路网距离通常大于直线距离
    if mode in ("walking", "cycling"):
        road_m = distance * 1.15
    elif mode in ("subway", "bus"):
        road_m = distance * 1.35
    else:
        road_m = distance * 1.30

    speed = float(speed_kmh) if speed_kmh and float(speed_kmh) > 0 else 12.0
    overhead = ESTIMATE_OVERHEAD_MIN.get(mode, 0.0)
    hours = (road_m / 1000.0) / speed
    duration = int(math.ceil(hours * 60.0 + overhead))
    return int(round(road_m)), max(1, duration)


def _trip_distance(route: Optional[dict], straight_m: float, mode: str) -> int:
    """确定用于计费的距离"""
    if route and route.get("distance_m"):
        try:
            value = int(route["distance_m"])
            if value > 0:
                return value
        except (TypeError, ValueError):
            pass
    return _estimate(straight_m, mode)[0]


def _travelers_of(travelers: Any) -> int:
    """安全地取出行人数"""
    try:
        value = int(travelers)
    except (TypeError, ValueError):
        return 2
    return min(20, max(1, value))


# 各方式的耗时上限(分钟):超过则说明该方式并不现实,改试下一个候选
MODE_MAX_MINUTES = {
    "walking": 25,
    "cycling": 45,
}

# 「这种方式根本走不到」的直线距离上限(米)。
# 与 MODE_MAX_MINUTES 保持一致:步行 25 分钟约 1.9 公里,骑行 45 分钟约 11 公里。
# 超出即不再作为候选,否则会输出「步行 25 分钟走 17.6 公里」这种自相矛盾的结果。
WALK_FEASIBLE_M = 2000.0
CYCLE_FEASIBLE_M = 11000.0

# 极短距离(同一位置 / 景点内换场)的阈值(米)
SHORT_LEG_M = 150.0

# 高德返回的距离至少应达到直线距离的这个比例,否则视为不可靠
_MIN_DISTANCE_RATIO = 0.4

# 各方式在「直线距离」下合理的速度区间(km/h)。
# 用直线距离而不是返回的路网距离,才能判断「这段耗时配这段路是否物理」:
# 例如直线 60 公里却报 319 分钟(约 11km/h),对打车明显不合理;
# 直线 1 米却报 3 分钟,则说明路线数据本身失真。
_MODE_SPEED_BAND = {
    "walking": (2.5, 8.0),
    "cycling": (6.0, 25.0),
    "subway": (8.0, 60.0),
    "bus": (8.0, 60.0),
    "taxi": (25.0, 75.0),
    "driving": (25.0, 75.0),
}

# 路网距离通常略大于直线距离,估算速度时做一次折算
_ROAD_FACTOR = 1.25

# 「机动车方式不可能这么快」的下限速度(km/h):
# 高德的公交规划偶尔返回 1 米/1 分钟这类失真结果,用速度下限把它们挡掉。
_MIN_TRANSIT_SPEED_KMH = 8.0
# 摩托化方式(公交/打车/自驾)在直线距离下允许的最短耗时
_MIN_MOTOR_MINUTES = 3

# 各方式「用实际路线距离反推耗时」时的参考速度(km/h)
_DERIVE_SPEED = {
    "walking": 4.5,
    "cycling": 15.0,
    "subway": 20.0,
    "bus": 18.0,
    "taxi": 30.0,
    "driving": 30.0,
}


def _route_is_plausible(route: dict, straight_m: float, mode: str) -> bool:
    """判断高德路线的「距离与速度」是否可信(不看耗时上限)

    与 _route_is_sane 的区别:耗时超过该方式上限(步行 60 分钟)仍然算「真实但
    不合适」,可以留作兜底;而距离明显小于直线距离、或速度完全不物理的数据
    属于坏数据,必须整体丢弃。

    Args:
        route: amap.route 的返回值
        straight_m: 两点直线距离(米)
        mode: 标准模式

    Returns:
        True 表示这条路线的距离与速度可信
    """
    if not route:
        return False

    try:
        distance = float(route.get("distance_m") or 0)
        duration = float(route.get("duration_min") or 0)
    except (TypeError, ValueError):
        return False

    straight = max(0.0, float(straight_m or 0))

    if distance <= 0 or duration <= 0:
        return False

    # 距离明显小于直线距离 → 数据不可信
    if straight >= 200 and distance < straight * _MIN_DISTANCE_RATIO:
        return False

    # 速度必须落在这个方式的合理区间内。
    # 这一步同时挡掉两类坏数据:直线 1 米却要 3 分钟(过慢),
    # 以及直线 60 公里只报 20 分钟(过快)。
    band = _MODE_SPEED_BAND.get(mode)
    if band and straight >= 80:
        implied_speed = (straight * _ROAD_FACTOR / 1000.0) / (duration / 60.0)
        low, high = band
        if implied_speed < low or implied_speed > high:
            return False

    return True


def _route_is_sane(route: dict, straight_m: float, mode: str) -> bool:
    """判断高德返回的路线是否可信且适合该方式

    高德的公交规划偶尔会返回 1 米/1 分钟这类明显失真的结果,
    这类数据会让时刻表变得荒谬,因此这里主动拒绝,退化为按距离估算。

    Args:
        route: amap.route 的返回值
        straight_m: 两点直线距离(米)
        mode: 标准模式

    Returns:
        True 表示路线可用
    """
    if not _route_is_plausible(route, straight_m, mode):
        return False

    try:
        duration = float(route.get("duration_min") or 0)
    except (TypeError, ValueError):
        return False

    # 走路的耗时超过上限 → 这段路不适合步行,换下一个候选
    limit = MODE_MAX_MINUTES.get(mode)
    if limit is not None and duration > limit:
        return False

    return True


def _mode_is_feasible(mode: str, straight_m: float) -> bool:
    """按距离判断某种交通方式是否「根本做不到」

    步行 25 分钟最多也就走 2-3 公里,骑行 45 分钟大约 10-15 公里;
    超出这个范围的方式不应该进入候选,否则就会出现「25 分钟走 17.6 公里」。

    Args:
        mode: 标准模式
        straight_m: 两点直线距离(米)

    Returns:
        True 表示该方式在这个距离上可行
    """
    try:
        distance = max(0.0, float(straight_m or 0))
    except (TypeError, ValueError):
        distance = 0.0
    if mode == "walking":
        return distance <= WALK_FEASIBLE_M
    if mode == "cycling":
        return distance <= CYCLE_FEASIBLE_M
    return True


def _mode_travel_minutes(mode: str, distance_m: float) -> int:
    """按该方式的实际路网距离折算真实耗时

    用于「真实路线可信但耗时异常」以及「按直线距离估算」两种场景,
    保证 distance_m 与 duration_min 始终自洽。
    速度取自 _DERIVE_SPEED(步行 4.5km/h、骑行 15km/h、地铁 20km/h、
    公交 18km/h、打车/自驾 30km/h),与真实路况接近,
    避免把「2.9 公里步行 40 分钟」这种真实数据改写成 15 分钟。

    Args:
        mode: 标准模式
        distance_m: 路网距离(米)

    Returns:
        耗时(分钟,至少 1 分钟)
    """
    speed = _DERIVE_SPEED.get(mode) or ESTIMATE_SPEED.get(mode, 12.0)
    overhead = ESTIMATE_OVERHEAD_MIN.get(mode, 0.0)
    distance = max(0.0, float(distance_m or 0))
    duration = int(math.ceil((distance / 1000.0) / speed * 60.0 + overhead))
    return max(1, duration)


def _normalize_plan(plan: TransportPlan, mode: str, straight: float,
                    fallback_distance_m: int, travelers: int = 2,
                    route: Optional[dict] = None) -> TransportPlan:
    """让 duration_min 与 distance_m 自洽

    如果真实路线的耗时与自己的距离明显矛盾(例如 4.5 公里却写 60 分钟),
    就按该方式的平均速度重算耗时,但**保留真实距离**,绝不把距离截断成
    「25 分钟走 400 米」这种假数据。

    重算耗时后必须重建 summary / detail_lines,否则会出现
    「duration_min=23 但 summary 写着约40分钟」这种自相矛盾的输出。

    Args:
        plan: 原始方案
        mode: 标准模式
        straight: 直线距离(米)
        fallback_distance_m: 没有可用距离时的兜底距离
        travelers: 出行人数(用于重建费用文案)
        route: 原始高德路线(用于重建文案,可为 None)

    Returns:
        自洽的 TransportPlan
    """
    distance = int(plan.distance_m or 0)
    if distance <= 0:
        distance = int(fallback_distance_m or 0)
    if distance <= 0:
        distance = int(max(0.0, straight) * 1.15) if mode in ("walking", "cycling") \
            else int(max(0.0, straight) * 1.30)

    expected = _mode_travel_minutes(mode, distance)
    # 真实耗时与「按平均速度折算」的耗时相差不到 40% 时保留真实值
    if duration_consistent(plan.duration_min, expected):
        duration = int(plan.duration_min)
    else:
        duration = expected

    if duration == int(plan.duration_min) and distance == int(plan.distance_m):
        return plan

    updated = {
        "distance_m": distance,
        "duration_min": max(1, duration),
    }

    # 耗时变了 → 文案必须跟着变,保持「文案与数字一致」
    source = route or {}
    transit_lines = [str(line) for line in (source.get("lines") or []) if line]
    transit_legs = [leg for leg in (source.get("legs") or []) if isinstance(leg, dict)]
    road_hint = str(source.get("road_hint") or "")
    people = max(1, int(travelers or 2))
    updated["summary"] = _build_summary(mode, plan.label, max(1, duration), distance,
                                        plan.cost, people,
                                        transit_lines, road_hint)
    updated["detail_lines"] = _build_detail_lines(
        mode, plan.label, road_hint, distance, max(1, duration), plan.cost,
        people, transit_lines, transit_legs,
    )
    return plan.model_copy(update=updated)


def duration_consistent(duration_min: Any, expected_min: Any, tolerance: float = 0.4) -> bool:
    """判断实际耗时与「按距离折算」的耗时是否自洽(允许 ±40% 误差)"""
    try:
        duration = float(duration_min or 0)
        expected = float(expected_min or 0)
    except (TypeError, ValueError):
        return False
    if duration <= 0 or expected <= 0:
        return False
    return abs(duration - expected) <= expected * tolerance


def _pick_representative_mode(straight: float, accepted: List[str],
                              feasible: List[str]) -> str:
    """所有真实路线都不可用时,挑一个「像样」的方式做估算

    就近走路,中距离优先公共交通,长距离优先打车/自驾。
    """
    def pick(*candidates: str) -> Optional[str]:
        for key in candidates:
            if key in feasible:
                return key
        return None

    if straight <= 1500:
        found = pick("walking", "cycling", "transit", "taxi", "driving")
    elif straight <= 5000:
        found = pick("cycling", "transit", "taxi", "walking", "driving")
    elif straight <= 30000:
        found = pick("transit", "taxi", "driving", "cycling", "walking")
    else:
        found = pick("taxi", "transit", "driving", "cycling", "walking")
    if found:
        return found
    # 用户偏好里只剩不可行的方式时,退回全量可行集合
    for key in ("transit", "taxi", "driving", "cycling", "walking"):
        if key in feasible or key in accepted:
            return key
    return "transit"


def _reason_note(mode: str, straight: float) -> str:
    """生成「方式不适合这段距离」的说明文字"""
    distance_text = _format_km(straight) or "这段距离"
    if mode == "transit":
        return f"距离约{distance_text},超出步行范围,因此改用地铁/公交"
    if mode == "taxi":
        return f"距离约{distance_text},超出步行范围,因此改用打车"
    if mode == "driving":
        return f"距离约{distance_text},超出步行范围,因此改用自驾"
    if mode == "cycling":
        return f"距离约{distance_text},步行太远,因此改用骑行"
    if mode == "walking":
        return f"距离约{distance_text},步行偏远,建议预留充足时间或改乘公共交通"
    return f"距离约{distance_text},已改用{mode}"


def _build_mode_texts(mode: str, label: str, route: dict, straight: float,
                      accepted: List[str], bucket_first: str, people: int,
                      over_limit: bool) -> Tuple[str, str, List[str]]:
    """生成 (summary, reason, detail_lines)

    统一入口,保证 summary 只给结论、detail_lines 只给做法,数字不重复。
    """
    distance_m = max(0, int(route.get("distance_m") or 0))
    duration_min = max(1, int(route.get("duration_min") or 1))
    transit_lines = [str(line) for line in (route.get("lines") or []) if line]
    transit_legs = [leg for leg in (route.get("legs") or []) if isinstance(leg, dict)]
    road_hint = str(route.get("road_hint") or "")
    route_cost = int(route.get("cost") or 0)
    cost = _compute_cost(mode, distance_m, people, route_cost)
    note = _reason_note(mode, straight) if (over_limit or mode not in accepted) else ""

    reason = _build_reason(mode, straight, label, accepted, bucket_first, False,
                           transit_lines, note)
    summary = _build_summary(mode, label, duration_min, distance_m, cost, people,
                             transit_lines, road_hint)
    detail_lines = _build_detail_lines(mode, label, road_hint, distance_m, duration_min,
                                       cost, people, transit_lines, transit_legs)
    return summary, reason, detail_lines


def _plan_from_route(mode: str, label: str, route: dict, straight: float,
                     accepted: List[str], bucket_first: str, people: int,
                     estimated: bool) -> TransportPlan:
    """把一条高德路线转换成 TransportPlan

    Args:
        mode: 标准模式
        label: 中文标签
        route: 高德路线(含 distance_m / duration_min / cost / lines / road_hint)
        straight: 直线距离(米)
        accepted: 用户接受的标准模式
        bucket_first: 该距离区间首选的模式
        people: 出行人数
        estimated: 是否按速度估算而来

    Returns:
        TransportPlan
    """
    distance_m = max(0, int(route.get("distance_m") or 0))
    duration_min = max(1, int(route.get("duration_min") or 1))
    transit_lines = [str(line) for line in (route.get("lines") or []) if line]
    transit_legs = [leg for leg in (route.get("legs") or []) if isinstance(leg, dict)]
    road_hint = str(route.get("road_hint") or "")
    route_cost = int(route.get("cost") or 0)
    cost = _compute_cost(mode, distance_m, people, route_cost)

    reason = _build_reason(mode, straight, label, accepted, bucket_first,
                           estimated, transit_lines)
    summary = _build_summary(mode, label, duration_min, distance_m, cost, people,
                             transit_lines, road_hint)
    detail_lines = _build_detail_lines(mode, label, road_hint, distance_m, duration_min,
                                       cost, people, transit_lines, transit_legs)

    return TransportPlan(
        mode=mode,
        label=label,
        duration_min=duration_min,
        distance_m=distance_m,
        cost=cost,
        summary=summary,
        reason=reason,
        detail_lines=detail_lines,
    )


def _estimated_plan(mode: str, label: str, straight: float, accepted: List[str],
                    bucket_first: str, people: int, note: str = "") -> TransportPlan:
    """按直线距离估算一个自洽的方案

    distance_m 与 duration_min 都按「该方式平均速度 × 路网距离」给出,
    两者永远自洽;distance_m 不再被上限截断。
    """
    distance_m, duration_min = _estimate(straight, mode)
    cost = _compute_cost(mode, distance_m, people)
    reason = _build_reason(mode, straight, label, accepted, bucket_first, True, [],
                           note)
    summary = _build_summary(mode, label, duration_min, distance_m, cost, people, [], "")
    detail_lines = _build_detail_lines(mode, label, "", distance_m, duration_min,
                                       cost, people, [], [])
    return TransportPlan(
        mode=mode,
        label=label,
        duration_min=duration_min,
        distance_m=distance_m,
        cost=cost,
        summary=summary,
        reason=reason,
        detail_lines=detail_lines,
    )


def _terminal_plan(straight: float, people: int) -> TransportPlan:
    """直线距离极短(同一位置/景点内换场)时的步行方案

    绝不该给出「地铁 1 分钟 / 6 元」这类付费方案,也不该出现
    「0 米却要 5 分钟」——耗时按真实距离折算,最短 3 分钟。

    Args:
        straight: 直线距离(米)
        people: 出行人数

    Returns:
        TransportPlan(步行,3-5 分钟,0 元)
    """
    distance = max(1, int(round(max(0.0, straight))))
    duration = 3 if distance < 150 else min(5, max(3, _mode_travel_minutes("walking",
                                                                          distance)))
    summary = f"步行 · 约{duration}分钟 · {distance}米"
    detail_lines = ["就在附近,步行即可到达"]
    return TransportPlan(
        mode="walking",
        label="步行",
        duration_min=duration,
        distance_m=distance,
        cost=0,
        summary=summary,
        reason="两地几乎在同一位置,属于同一片区域内换场,步行最直接",
        detail_lines=detail_lines,
    )


def choose_transport(origin: Optional[Tuple[float, float]],
                     destination: Optional[Tuple[float, float]],
                     straight_m: float, preferences: Optional[List[str]],
                     travelers: int, city: str, amap: AmapRest) -> TransportPlan:
    """选择两站之间最合适的交通方式

    Args:
        origin: 起点 (lng, lat)
        destination: 终点 (lng, lat)
        straight_m: 两点直线距离(米)
        preferences: 用户可接受的交通方式偏好
        travelers: 出行人数
        city: 城市名称(公交规划必需)
        amap: 高德 REST 客户端

    Returns:
        交通方案 TransportPlan
    """
    people = _travelers_of(travelers)
    try:
        straight = float(straight_m or 0)
    except (TypeError, ValueError):
        straight = 0.0

    # 直线距离极短(同一位置/坐标缺失)→ 短距离步行,不消耗任何配额
    if straight < 150:
        return _terminal_plan(straight, people)

    order = candidate_order(straight)
    accepted = _accepted_modes(preferences)
    bucket_first = order[0] if order else "walking"

    # 1) 先按距离剔除「根本做不到」的方式(步行 > 3km、骑行 > 15km)
    feasible = [key for key in order if _mode_is_feasible(key, straight)]
    if not feasible:
        feasible = ["transit", "taxi", "driving"]

    # 2) 再套用用户偏好;偏好里一个都不剩时,用全部可行方式并在 reason 里说明
    preferred = [key for key in feasible if key in accepted]
    fallback_by_distance = not preferred
    filtered = preferred or feasible

    have_points = bool(origin and destination
                       and (origin[0] or origin[1]) and (destination[0] or destination[1]))

    # 真实存在但耗时超过该方式上限的路线留作兜底(只兜底,不擅自截断)
    over_limit_route: Optional[Tuple[str, str, dict]] = None

    for key in filtered:
        mode, label = _CANDIDATES.get(key, ("walking", "步行"))
        route: Optional[dict] = None
        if have_points and amap is not None:
            try:
                route = amap.route(origin, destination, mode, city)
            except Exception:
                route = None
        if not route:
            continue

        if not _route_is_plausible(route, straight, mode):
            # 距离明显小于直线距离 / 速度完全不物理 → 坏数据,整体丢弃
            continue

        if not _route_is_sane(route, straight, mode):
            # 距离可信,只是耗时超过该方式上限 → 留作兜底,继续尝试下一个
            if over_limit_route is None:
                over_limit_route = (mode, label, route)
            continue

        plan = _plan_from_route(mode, label, route, straight, accepted,
                                bucket_first, people, False)
        plan = _normalize_plan(plan, mode, straight, plan.distance_m, people, route)
        if fallback_by_distance:
            # 用户偏好之外的方式被采用 → 在原因里显式说明,并给出真实耗时
            note = _reason_note(mode, straight)
            reason = _build_reason(mode, straight, label, accepted, bucket_first,
                                   False, [str(x) for x in (route.get("lines") or [])],
                                   note)
            plan = plan.model_copy(update={"reason": reason})
        return plan

    # 3) 只用「真实但超上限」的那条路线,保留它的真实距离与真实耗时
    if over_limit_route is not None:
        mode, label, route = over_limit_route
        plan = _plan_from_route(mode, label, route, straight, accepted,
                                bucket_first, people, False)
        plan = _normalize_plan(plan, mode, straight, plan.distance_m, people, route)
        note = _reason_note(mode, straight)
        reason = _build_reason(mode, straight, label, accepted, bucket_first, False,
                               [str(x) for x in (route.get("lines") or [])], note)
        if mode == "walking":
            reason += f",如需坚持步行请预留约{max(1, plan.duration_min // 60 + 1)}小时"
        plan = plan.model_copy(update={"reason": reason})
        return plan

    # 4) 所有候选都拿不到可信路线 → 用直线距离估算一个自洽的方案
    key = _pick_representative_mode(straight, accepted, feasible)
    mode, label = _CANDIDATES.get(key, ("transit", "地铁/公交"))
    note = _reason_note(mode, straight)
    return _estimated_plan(mode, label, straight, accepted, bucket_first, people, note)


def _compute_cost(mode: str, distance_m: int, travelers: int,
                  route_cost: int = 0) -> int:
    """计算交通费用(元,已按人数折算)

    Args:
        mode: 标准模式
        distance_m: 计费距离(米)
        travelers: 出行人数
        route_cost: 高德返回的费用(若可信则优先)

    Returns:
        费用(元)
    """
    km = max(0.0, distance_m / 1000.0)
    if mode == "taxi":
        cars = max(1, int(math.ceil(travelers / 4.0)))
        per_car = max(10.0, 2.5 * km)
        return int(round(per_car * cars))
    if mode == "driving":
        return int(round(max(0.0, 1.0 * km)))
    if mode in ("subway", "bus"):
        per_person = 2
        if route_cost and 1 <= route_cost <= 20:
            per_person = route_cost
        return per_person * travelers
    return 0


def _per_person_fare(mode: str, total_cost: int, travelers: int) -> int:
    """人均费用"""
    if travelers <= 0:
        return total_cost
    if mode in ("subway", "bus"):
        return int(round(total_cost / float(travelers)))
    return total_cost


def _build_reason(mode: str, straight_m: float, label: str, accepted: List[str],
                  bucket_first: str, estimated: bool, transit_lines: List[str],
                  note: str = "") -> str:
    """生成中文选择理由

    Args:
        note: 额外说明(例如「超出步行范围,因此改用地铁/公交」)。note 本身已经带上
            距离说明,因此这时不再重复距离前缀。
    """
    if straight_m <= 0:
        distance_text = "距离未知"
    elif straight_m < 1000:
        distance_text = f"距离约{int(round(straight_m))}米"
    else:
        distance_text = f"距离约{straight_m / 1000.0:.1f}公里"

    mode_keys = {
        "walking": "walking",
        "cycling": "cycling",
        "taxi": "taxi",
        "driving": "driving",
        "subway": "transit",
        "bus": "transit",
    }
    key = mode_keys.get(mode, mode)
    preferred = key in accepted
    prefix = "" if note else f"{distance_text},"

    if estimated:
        base = f"高德实时路线暂不可用,{distance_text},按平均速度估算{label}耗时,供参考"
    elif key == bucket_first and preferred:
        base = f"{prefix}且在你可接受的交通方式之内,{label}是最省时省心的选择"
    elif not preferred:
        base = f"{prefix}你偏好之外的{label}刚好最合适,故作为备选"
    elif key == bucket_first:
        base = f"{prefix}{label}是这段路程最合适的方式"
    elif transit_lines:
        base = f"{prefix}公共交通可直达,{label}性价比更高"
    else:
        base = f"{prefix}综合耗时与费用,{label}更合适"

    if note:
        return f"{note};{base}"
    return base


def _format_km(distance_m: Any) -> str:
    """把米数格式化成「4.5公里 / 800米」"""
    try:
        value = max(0, int(round(float(distance_m or 0))))
    except (TypeError, ValueError):
        value = 0
    if value <= 0:
        return ""
    if value < 1000:
        return f"{value}米"
    return f"{value / 1000.0:.1f}公里"


def _road_name_of(road_hint: str) -> str:
    """从高德导航指令中提取路名

    高德步行指令形如「沿建国门内大街向西步行450米」,这里只取「沿…」中的路名。

    Args:
        road_hint: 高德返回的原始导航指令

    Returns:
        路名;解析不出来时返回空字符串
    """
    text = str(road_hint or "").strip()
    if not text or not text.startswith("沿"):
        return ""
    body = text[1:]
    name = ""
    for index, ch in enumerate(body):
        if ch in ("向", "步", "骑", "行", "走", "过", "到"):
            name = body[:index]
            break
    else:
        name = body
    name = name.strip(" ,,。.")
    # 明显不是路名的内容直接放弃
    if not name or len(name) > 16 or name.isdigit():
        return ""
    return name


def _build_summary(mode: str, label: str, duration_min: int, distance_m: int,
                   cost: int, travelers: int, transit_lines: List[str],
                   road_hint: str = "") -> str:
    """生成一句话交通方案(结论)

    Args:
        mode: 标准模式
        label: 中文标签
        duration_min: 耗时(分钟)
        distance_m: 距离(米)
        cost: 费用(元,公交已按人数折算)
        travelers: 出行人数
        transit_lines: 公共交通线路名
        road_hint: 高德导航指令(仅步行/骑行用于取路名)

    Returns:
        形如「地铁1号线 · 约22分钟 · 约6元/人」的结论行
    """
    per_person = _per_person_fare(mode, cost, travelers)
    distance_text = _format_km(distance_m)

    if mode in ("subway", "bus"):
        if transit_lines:
            head = transit_lines[0]
            if len(transit_lines) > 1:
                head = f"{transit_lines[0]}等{len(transit_lines)}条线路"
        else:
            head = label
        return f"{head} · 约{duration_min}分钟 · 约{per_person}元/人"

    if mode in ("walking", "cycling"):
        name = _road_name_of(road_hint)
        if name:
            return f"{label} · 沿{name} · 约{duration_min}分钟 · {distance_text}"
        if distance_text:
            return f"{label} · 约{duration_min}分钟 · {distance_text}"
        return f"{label} · 约{duration_min}分钟"

    if mode == "taxi":
        return f"{label} · 约{duration_min}分钟 · 约{cost}元"

    if mode == "driving":
        return f"{label} · 约{duration_min}分钟 · 约{cost}元(油费)"

    return f"{label} · 约{duration_min}分钟"


def _build_detail_lines(mode: str, label: str, road_hint: str, distance_m: int,
                        duration_min: int, cost: int, travelers: int,
                        transit_lines: List[str], transit_legs: List[dict]) -> List[str]:
    """生成交通明细行(怎么做 / 注意什么)

    与 summary 分工:summary 给结论,detail_lines 给可执行的做法,
    因此**任何已经出现在 summary 里的数字都不再重复**。

    Args:
        mode: 标准模式
        label: 中文标签
        road_hint: 高德导航指令(步行/骑行取路名)
        distance_m: 距离(米)
        duration_min: 耗时(分钟)
        cost: 费用(元)
        travelers: 出行人数
        transit_lines: 公共交通线路名
        transit_legs: 每段乘车的线路与上下车站

    Returns:
        明细行列表(可能为空)
    """
    detail_lines: List[str] = []

    if mode in ("subway", "bus"):
        for index, leg in enumerate(transit_legs or []):
            name = str((leg or {}).get("name") or "").strip()
            if not name:
                continue
            departure = str((leg or {}).get("departure_stop") or "").strip()
            arrival = str((leg or {}).get("arrival_stop") or "").strip()
            if departure and arrival:
                detail_lines.append(f"第{index + 1}程 乘坐{name}({departure}上 · {arrival}下)")
            else:
                detail_lines.append(f"第{index + 1}程 乘坐{name}")
        if not detail_lines:
            for line in transit_lines or []:
                detail_lines.append(f"乘坐{line}")
        if not detail_lines:
            # 高德没给出具体线路名 → 至少给一条可执行的提示
            detail_lines.append("建议用地图App确认具体线路与上车站点")
        if len(transit_legs or []) > 1:
            detail_lines.append("中途需要换乘,建议预留等车时间并留意末班车时刻")
        elif detail_lines:
            detail_lines.append("请留意线路方向与末班车时刻")
        return detail_lines

    if mode in ("walking", "cycling"):
        # 极短距离(同景点内换场 / 就在隔壁)不必给导航指引
        if distance_m < SHORT_LEG_M:
            detail_lines.append("就在紧邻位置,按现场指示牌走过去即可")
            return detail_lines
        name = _road_name_of(road_hint)
        if name:
            detail_lines.append(f"沿{name}一路直行,按导航提示过街")
        elif distance_m >= 3000:
            detail_lines.append("距离较远,建议改乘地铁/公交或打车")
        elif distance_m >= 1200:
            detail_lines.append("沿主路直行,过街请走人行横道")
        else:
            detail_lines.append("出站后沿导航直走,注意路口指示牌")
        if mode == "walking":
            if distance_m >= 2000:
                detail_lines.append("路程较长,建议穿运动鞋并适当补水")
        else:
            detail_lines.append("注意骑行安全,尽量走非机动车道")
        return detail_lines

    if mode == "taxi":
        cars = max(1, int(math.ceil(max(1, travelers) / 4.0)))
        detail_lines.append(f"约{cars}辆车 · 全程{_format_km(distance_m) or '待定'}")
        detail_lines.append("高峰时段建议提前叫车,上车后确认打表计费")
        return detail_lines

    if mode == "driving":
        cars = max(1, int(math.ceil(max(1, travelers) / 4.0)))
        detail_lines.append(f"全程{_format_km(distance_m) or '待定'} · 约{cars}辆车")
        detail_lines.append("注意限行与停车位,出发前确认目的地停车场")
        return detail_lines

    return detail_lines
