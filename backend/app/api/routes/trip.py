"""旅行规划API路由"""

import asyncio
import json
import math
import re
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from ...models.schemas import (
    ChatRequest,
    ChatResponse,
    TripPlan,
    TripPlanResponse,
    TripRequest,
    ErrorResponse
)
from ...agents.trip_planner_agent import get_trip_planner_agent
from ...services.amap_rest import get_amap_rest
from ...services.llm_service import get_llm
from ...services.timeline import enrich_plan

router = APIRouter(prefix="/trip", tags=["旅行规划"])

# SSE 响应头
SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "X-Accel-Buffering": "no",
    "Connection": "keep-alive",
}

# 「小星小探员」人设
CHAT_SYSTEM_PROMPT = """你是「小星小探员」,是「小星探行」(口号:小星探行,快乐出行)的旅行规划小助手。

你的能力:
1. 回答用户关于当前行程的问题(时间安排、交通、餐厅、酒店、预算、天气等)
2. 按用户要求修改行程(增删景点、调整顺序、改交通方式、改餐厅、改酒店、改人数等)

**最重要的输出纪律:**
1. **绝对不要输出完整行程 JSON**,也不要把当前计划抄回来。你只需要输出「用户想改什么」。
2. 输出必须精简:reply 控制在 300 个中文字符以内,不要长篇大论,不要罗列大段行程。
3. 后端会依据你给出的 changes 重新计算时刻表、交通、餐厅与预算,所以你不需要自己算。

**输出格式(必须是合法JSON,不要输出任何多余文字):**
```json
{
  "reply": "给用户的中文回答",
  "modified": false,
  "suggestions": ["短问题1","短问题2","短问题3"],
  "changes": null
}
```

需要修改行程时,把 modified 设为 true,并只填写 changes 中**用户要求改的字段**,其余字段全部省略(不要填 null,不要填默认值):

```json
{
  "reply": "已经按 4 人重新安排了房间和预算~",
  "modified": true,
  "suggestions": ["人均花费是多少?","第2天能少走点路吗?","午餐想换成当地小吃"],
  "changes": {
    "travelers": 4,
    "arrival_time": "10:00",
    "transport_preferences": ["地铁","打车"],
    "pace": "relaxed",
    "restaurant_hint": "多安排当地小吃",
    "day_attractions": {
      "2": [ {"name":"故宫博物院","visit_duration":180} ]
    },
    "notes": "对整体行程的文字说明"
  }
}
```

changes 字段说明:
- travelers: 出行人数(整数)
- arrival_time: 抵达城市时刻,"HH:MM"
- transport_preferences: 可接受的交通方式,只允许 步行/公交/地铁/打车/骑行/自驾
- pace: 行程松紧,取值 relaxed(轻松,每天只保留前 2 个景点)/ normal / packed(排满)
- restaurant_hint: 用餐口味或餐厅要求的一句话(例如 "多安排当地小吃")
- day_attractions: 键是**第几天(从 1 开始)**,值会**整体替换**这一天的景点列表。
  每个景点只需要给 name(必填),可选 visit_duration(分钟)。其余地址、坐标、门票、评分由后端补齐,
  你**不要**编造经纬度。
- notes: 对整体行程的补充说明(会被追加到总建议里,不会覆盖原文)

不需要修改行程时:modified 为 false,changes 为 null,只回答用户的问题。
"""



# ============ 计划生成 ============

@router.post(
    "/plan",
    response_model=TripPlanResponse,
    summary="生成旅行计划",
    description="根据用户输入的旅行需求,生成详细的旅行计划"
)
async def plan_trip(request: TripRequest):
    """
    生成旅行计划

    Args:
        request: 旅行请求参数

    Returns:
        旅行计划响应
    """
    try:
        print(f"\n{'='*60}")
        print(f"📥 收到旅行规划请求:")
        print(f"   城市: {request.city}")
        print(f"   日期: {request.start_date} - {request.end_date}")
        print(f"   天数: {request.travel_days}")
        print(f"{'='*60}\n")

        # 获取Agent实例
        print("🔄 获取多智能体系统实例...")
        agent = get_trip_planner_agent()

        # 生成旅行计划
        print("🚀 开始生成旅行计划...")
        trip_plan = agent.plan_trip(request)

        print("✅ 旅行计划生成成功,准备返回响应\n")

        return TripPlanResponse(
            success=True,
            message="旅行计划生成成功",
            data=trip_plan
        )

    except Exception as e:
        print(f"❌ 生成旅行计划失败: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"生成旅行计划失败: {str(e)}"
        )


@router.post(
    "/plan/stream",
    summary="流式生成旅行计划",
    description="以 SSE 流式返回生成进度与最终旅行计划"
)
async def plan_trip_stream(request: TripRequest):
    """
    流式生成旅行计划(Server-Sent Events)

    事件格式:
      data: {"type":"progress","percent":18,"message":"正在搜索目的地景点…","stage":"attraction"}
      data: {"type":"result","success":true,"message":"旅行计划生成成功","data":{...}}

    Args:
        request: 旅行请求参数

    Returns:
        SSE 流式响应
    """
    loop = asyncio.get_event_loop()
    queue: "asyncio.Queue[Any]" = asyncio.Queue()

    def produce():
        """在工作线程中执行阻塞的规划生成器"""
        stream = None
        try:
            agent = get_trip_planner_agent()
            stream = agent.plan_trip_stream(request)
            for event, payload in stream:
                if event == "progress":
                    data = dict(payload or {})
                    loop.call_soon_threadsafe(queue.put_nowait, {
                        "type": "progress",
                        "percent": int(data.get("percent", 0) or 0),
                        "message": str(data.get("message", "") or ""),
                        "stage": str(data.get("stage", "") or ""),
                    })
                elif event == "result":
                    plan = payload
                    try:
                        body = plan.model_dump() if hasattr(plan, "model_dump") else plan
                    except Exception:
                        body = plan
                    loop.call_soon_threadsafe(queue.put_nowait, {
                        "type": "result",
                        "success": True,
                        "message": "旅行计划生成成功",
                        "data": body,
                    })
        except Exception as exc:
            print(f"❌ 流式生成旅行计划失败: {str(exc)}")
            import traceback
            traceback.print_exc()
            try:
                loop.call_soon_threadsafe(queue.put_nowait, {
                    "type": "error",
                    "message": f"生成旅行计划失败: {str(exc)}",
                })
            except Exception:
                pass
        finally:
            try:
                if stream is not None and hasattr(stream, "close"):
                    stream.close()
            except Exception:
                pass
            try:
                loop.call_soon_threadsafe(queue.put_nowait, None)
            except Exception:
                pass

    async def event_source():
        """把工作线程产出的事件桥接成异步生成器"""
        producer = asyncio.ensure_future(loop.run_in_executor(None, produce))
        try:
            while True:
                item = await queue.get()
                if item is None:
                    break
                yield f"data: {json.dumps(item, ensure_ascii=False)}\n\n"
        except asyncio.CancelledError:
            print("⚠️  客户端中断了流式连接")
            raise
        finally:
            if not producer.done():
                producer.cancel()
            try:
                await producer
            except (asyncio.CancelledError, Exception):
                pass

    return StreamingResponse(
        event_source(),
        media_type="text/event-stream",
        headers=SSE_HEADERS,
    )


# ============ 行程小助手 ============

def _plan_summary(plan: TripPlan) -> str:
    """构建紧凑的中文行程摘要(作为 LLM 上下文,不粘贴整份 JSON)"""
    lines: List[str] = []
    try:
        lines.append(f"城市: {plan.city}")
        lines.append(f"日期: {plan.start_date} 至 {plan.end_date}")
        budget = plan.budget
        if budget is not None:
            lines.append(
                f"预算: 门票{budget.total_attractions}元 + 住宿{budget.total_hotels}元 + "
                f"餐饮{budget.total_meals}元 + 交通{budget.total_transportation}元 = "
                f"合计{budget.total}元"
            )
        for day in plan.days or []:
            lines.append(f"【第{day.day_index + 1}天 {day.date}】{day.description or ''}")
            for entry in day.timeline or []:
                segment = f"  - {entry.arrive_time}"
                if entry.leave_time and entry.leave_time != "次日":
                    segment += f"-{entry.leave_time}"
                segment += f" {entry.title}({entry.type})"
                if entry.next_transport is not None:
                    segment += f" →[{entry.next_transport.mode} {entry.next_transport.duration_min}分钟]"
                lines.append(segment)
            if not day.timeline:
                for attraction in day.attractions or []:
                    lines.append(f"  - 景点: {attraction.name}")
            hotel = day.hotel
            if hotel is not None:
                lines.append(f"  - 酒店: {hotel.name}(评分{hotel.rating or '未知'},"
                             f"{hotel.price_range or '价格未知'},{hotel.distance or ''})")
            for recommendation in day.restaurants or []:
                names = "、".join(venue.name for venue in (recommendation.venues or [])[:3])
                if names:
                    label = "午餐" if recommendation.meal_type == "lunch" else "晚餐"
                    lines.append(f"  - {label}(近{recommendation.near}): {names}")
    except Exception as exc:
        print(f"⚠️  行程摘要生成失败: {str(exc)}")
    return "\n".join(lines) if lines else "暂无行程"


def _close_brackets(text: str) -> str:
    """补全未闭合的 {} / []

    用一个小状态机扫描:双引号字符串内部的括号(含 \\" 转义)一律忽略。
    扫描结束后按栈逆序补上对应的右括号。

    Args:
        text: 可能被截断的 JSON 文本

    Returns:
        补全括号后的文本
    """
    stack: List[str] = []
    in_string = False
    escaped = False
    for ch in text:
        if in_string:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch in "{[":
            stack.append(ch)
        elif ch in "}]":
            if stack:
                stack.pop()
    if in_string:
        text += '"'
    while stack:
        opener = stack.pop()
        text += "}" if opener == "{" else "]"
    return text


def _repair_json(text: str) -> Optional[dict]:
    """尽力修复被截断的 JSON

    两步走:
      1. 从末尾向前回退,找到最后一个能 json.loads 成功的位置(截断常发生在对象中间)
      2. 用状态机补全未闭合的括号后再试一次

    Args:
        text: 模型输出中的 JSON 片段

    Returns:
        解析出的 dict;无法修复时返回 None
    """
    if not text:
        return None
    candidate = text.strip()
    if not candidate:
        return None

    # 直接解析
    try:
        data = json.loads(candidate)
        if isinstance(data, dict):
            return data
    except Exception:
        pass

    # (a) 回退到最后一个可解析的前缀(限制尝试次数,避免在大文本上做无用功)
    trimmed = candidate.rstrip()
    end = len(trimmed)
    for _ in range(200):
        end = trimmed.rfind("}", 0, end)
        if end <= 0:
            break
        piece = trimmed[:end + 1]
        try:
            data = json.loads(piece)
            if isinstance(data, dict):
                return data
        except Exception:
            end -= 1
            continue

    # (b) 补全未闭合的括号后再试
    try:
        data = json.loads(_close_brackets(candidate))
        if isinstance(data, dict):
            return data
    except Exception:
        pass

    # (c) 先截到最后一段完整内容,再补括号
    last_brace = candidate.rfind("}")
    if last_brace > 0:
        try:
            data = json.loads(_close_brackets(candidate[:last_brace + 1]))
            if isinstance(data, dict):
                return data
        except Exception:
            pass
    return None


def _extract_json(text: str) -> Optional[dict]:
    """从模型输出中宽松地提取 JSON 对象(容忍被截断的输出)"""
    if not text:
        return None
    candidates: List[str] = []
    try:
        if "```json" in text:
            start = text.find("```json") + 7
            end = text.find("```", start)
            if end > start:
                candidates.append(text[start:end].strip())
            else:
                # 没有收尾的围栏 → 视为被截断,取到文本末尾
                candidates.append(text[start:].strip())
        if "```" in text:
            start = text.find("```") + 3
            end = text.find("```", start)
            if end > start:
                candidates.append(text[start:end].strip())
            else:
                candidates.append(text[start:].strip())
        if "{" in text:
            end = text.rfind("}")
            if end > text.find("{"):
                candidates.append(text[text.find("{"):end + 1])
            else:
                candidates.append(text[text.find("{"):])
    except Exception:
        pass

    for candidate in candidates:
        for attempt in (candidate, candidate.strip().lstrip("json").strip()):
            try:
                data = json.loads(attempt)
                if isinstance(data, dict):
                    return data
            except Exception:
                repaired = _repair_json(attempt)
                if isinstance(repaired, dict):
                    return repaired
    # 整段文本本身就是 JSON 的情况
    repaired = _repair_json(text)
    if isinstance(repaired, dict):
        return repaired
    return None


def _coerce_plan(data: Any, fallback: Optional[TripPlan]) -> Optional[TripPlan]:
    """把模型返回的 plan 数据尽量校正成合法 TripPlan"""
    if not isinstance(data, dict):
        return None

    payload = dict(data)
    if fallback is not None:
        payload.setdefault("city", fallback.city)
        payload.setdefault("start_date", fallback.start_date)
        payload.setdefault("end_date", fallback.end_date)
        payload.setdefault("overall_suggestions", fallback.overall_suggestions or "行程已更新")
        if not payload.get("weather_info"):
            payload["weather_info"] = [item.model_dump() for item in (fallback.weather_info or [])]
    payload.setdefault("weather_info", [])
    payload.setdefault("overall_suggestions", "行程已按你的要求更新")
    payload.setdefault("days", [])

    days = payload.get("days")
    fallback_transport = "公共交通"
    if fallback is not None:
        for day in fallback.days or []:
            if day.transportation:
                fallback_transport = str(day.transportation)
                break
    if isinstance(days, list):
        for index, day in enumerate(days):
            if not isinstance(day, dict):
                continue
            day.setdefault("date", f"第{index + 1}天")
            day.setdefault("day_index", index)
            day.setdefault("description", f"第{index + 1}天行程")
            day.setdefault("transportation", fallback_transport)
            day.setdefault("accommodation", "舒适型酒店")
            day.setdefault("attractions", [])
            day.setdefault("meals", [])
            for attraction in day.get("attractions") or []:
                if isinstance(attraction, dict):
                    attraction.setdefault("address", "")
                    attraction.setdefault("visit_duration", 120)
                    attraction.setdefault("description", "")
                    location = attraction.get("location")
                    if not isinstance(location, dict):
                        attraction["location"] = {"longitude": 0.0, "latitude": 0.0}

    try:
        return TripPlan(**payload)
    except Exception as exc:
        print(f"⚠️  修改后的行程校验失败: {str(exc)}")
        return None


def _default_suggestions() -> List[str]:
    """默认的追问建议"""
    return [
        "第2天能少走点路吗?",
        "帮我把午餐换成当地特色小吃",
        "这几天的交通方式可以更省时间吗?",
        "帮我算一下人均花费是多少",
    ]


# ============ 「修改行程」:紧凑的变更意图 → 重新充实行程 ============

def _clamp_text(value: Any, limit: int) -> str:
    """截断过长的文本"""
    text = str(value or "").strip()
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + "…"


def _request_from_plan(plan: TripPlan, request: ChatRequest,
                       changes: Optional[Dict[str, Any]] = None) -> TripRequest:
    """根据对话请求与行程构造 TripRequest,用于重新充实行程

    Args:
        plan: 当前(或候选)行程
        request: 对话请求
        changes: 用户要求变更的字段(可为空)

    Returns:
        重新计算时刻表/交通/餐厅/预算所需的 TripRequest
    """
    changes = changes or {}

    travelers = changes.get("travelers")
    if travelers is None:
        travelers = request.travelers
    try:
        travelers = max(1, min(20, int(travelers or 2)))
    except (TypeError, ValueError):
        travelers = 2

    transportation = "公共交通"
    accommodation = "舒适型酒店"
    for day in plan.days or []:
        if day.transportation:
            transportation = str(day.transportation)
            break
    for day in plan.days or []:
        if day.accommodation:
            accommodation = str(day.accommodation)
            break

    arrival_time = "09:00"
    if plan.days and plan.days[0].timeline:
        arrival_time = str(plan.days[0].timeline[0].arrive_time or "09:00")
    if changes.get("arrival_time"):
        arrival_time = str(changes["arrival_time"]).strip()[:5]

    preferences = list(changes.get("transport_preferences")
                       or request.transport_preferences or [])

    # restaurant_hint 折进 free_text_input,交给 dish_catalog.taste_keywords 生效
    free_text = str(changes.get("restaurant_hint") or "").strip()

    return TripRequest(
        city=plan.city,
        start_date=plan.start_date,
        end_date=plan.end_date,
        travel_days=max(1, len(plan.days or []) or 1),
        transportation=transportation,
        accommodation=accommodation,
        preferences=[],
        free_text_input=free_text,
        arrival_time=arrival_time,
        travelers=travelers,
        transport_preferences=[str(item) for item in preferences if str(item).strip()],
    )


def _find_known_attraction(name: str, plan: TripPlan) -> Optional[Any]:
    """在原始行程里按名字找同名景点(用于继承真实的坐标与门票)"""
    target = str(name or "").strip()
    if not target:
        return None
    for day in plan.days or []:
        for attraction in day.attractions or []:
            if str(getattr(attraction, "name", "") or "").strip() == target:
                return attraction
    return None


def _rebuild_attraction(item: Any, plan: TripPlan, city: str) -> Optional[Any]:
    """把一条「变更意图」里的景点补全成完整 Attraction

    只有 name 是必需的;同名景点会继承原始行程里的地址/坐标/门票/评分,
    **绝不凭空编造坐标**,交给 enrich_plan 去地理编码。

    Args:
        item: LLM 给出的景点(字符串或 dict)
        plan: 原始行程(用于继承元数据)
        city: 城市名(用于兜底描述)

    Returns:
        Attraction;无法构造时返回 None
    """
    from ...models.schemas import Attraction, Location

    if isinstance(item, str):
        payload: Dict[str, Any] = {"name": item}
    elif isinstance(item, dict):
        payload = dict(item)
    else:
        return None

    name = str(payload.get("name") or "").strip()
    if not name:
        return None

    known = _find_known_attraction(name, plan)
    duration = payload.get("visit_duration")
    try:
        visit_duration = max(30, int(duration)) if duration is not None else None
    except (TypeError, ValueError):
        visit_duration = None
    if visit_duration is None:
        visit_duration = max(30, int(getattr(known, "visit_duration", 0) or 90
                                    if known is not None else 90))

    address = str(payload.get("address") or "").strip()
    if not address and known is not None:
        address = str(getattr(known, "address", "") or "")
    if not address:
        address = ""

    location = payload.get("location")
    if not isinstance(location, dict) or not location.get("longitude"):
        location = None
        if known is not None and getattr(known, "location", None) is not None:
            location = {
                "longitude": float(getattr(known.location, "longitude", 0.0) or 0.0),
                "latitude": float(getattr(known.location, "latitude", 0.0) or 0.0),
            }
    if not isinstance(location, dict):
        location = {"longitude": 0.0, "latitude": 0.0}

    description = str(payload.get("description") or "").strip()
    if not description and known is not None:
        description = str(getattr(known, "description", "") or "")
    if not description:
        description = f"{city}的{name}"

    category = str(payload.get("category") or "").strip()
    if not category and known is not None:
        category = str(getattr(known, "category", "") or "")
    if not category:
        category = "景点"

    rating = payload.get("rating")
    if rating is None and known is not None:
        rating = getattr(known, "rating", None)

    ticket = payload.get("ticket_price")
    if ticket is None and known is not None:
        ticket = getattr(known, "ticket_price", 0)

    image_url = payload.get("image_url")
    if not image_url and known is not None:
        image_url = getattr(known, "image_url", None)

    try:
        return Attraction(
            name=name,
            address=address,
            location=Location(longitude=float(location.get("longitude") or 0.0),
                              latitude=float(location.get("latitude") or 0.0)),
            visit_duration=int(visit_duration),
            description=description,
            category=category,
            rating=float(rating) if rating not in (None, "") else None,
            photos=list(getattr(known, "photos", []) or []) if known is not None else [],
            poi_id=str(getattr(known, "poi_id", "") or "") if known is not None else "",
            image_url=image_url,
            ticket_price=int(ticket or 0),
        )
    except Exception as exc:
        print(f"⚠️  变更景点构造失败({name}): {str(exc)}")
        return None


def _apply_changes(plan: TripPlan, changes: Dict[str, Any],
                   request: ChatRequest) -> Optional[TripPlan]:
    """把「变更意图」落到行程上,返回**重新充实过**的新行程

    约定:
      * 绝不修改传入的 plan(先深拷贝)
      * 只处理 changes 里出现的字段,其余保持原样
      * 最后统一走 enrich_plan,让时刻表/交通/餐厅/酒店/预算重算一遍

    Args:
        plan: 当前行程
        changes: LLM 给出的变更字段
        request: 对话请求

    Returns:
        充实后的新行程;changes 为空时返回 None
    """
    if not isinstance(changes, dict) or not changes:
        return None

    candidate = plan.model_copy(deep=True)
    city = str(candidate.city or "")
    applied: List[str] = []

    # ---- 人数:刷新所有地点的适配人数与酒店房间数 ----
    travelers: Optional[int] = None
    if changes.get("travelers") is not None:
        try:
            travelers = max(1, min(20, int(changes["travelers"])))
        except (TypeError, ValueError):
            travelers = None
    if travelers is not None:
        rooms = max(1, int(math.ceil(travelers / 2.0)))
        room_tag = f"{travelers}人建议预订{rooms}间房"
        for day in candidate.days or []:
            for venue in _venues_of_day(day):
                try:
                    venue.party_size = travelers
                except Exception:
                    continue
            for entry in day.timeline or []:
                venue = getattr(entry, "venue", None)
                if venue is None:
                    continue
                try:
                    venue.party_size = travelers
                    if str(getattr(venue, "kind", "")) == "hotel":
                        tags = [tag for tag in (venue.tags or [])
                                if "间房" not in str(tag)]
                        tags.append(room_tag)
                        venue.tags = tags[:4]
                except Exception:
                    continue
        applied.append(f"{travelers}人")

    # ---- 松紧:relaxed 只保留每天前 2 个景点并把游览时长 +20% ----
    pace = str(changes.get("pace") or "").strip().lower()
    if pace in ("relaxed", "normal", "packed"):
        for day in candidate.days or []:
            attractions = list(day.attractions or [])
            if not attractions:
                continue
            if pace == "relaxed":
                attractions = attractions[:2]
                for attraction in attractions:
                    current = int(getattr(attraction, "visit_duration", 0) or 90)
                    attraction.visit_duration = max(30, int(round(current * 1.2)))
            day.attractions = attractions
        applied.append(f"节奏={pace}")

    # ---- 逐日替换景点列表 ----
    day_attractions = changes.get("day_attractions")
    if isinstance(day_attractions, dict) and day_attractions:
        days = list(candidate.days or [])
        for raw_key, raw_items in day_attractions.items():
            try:
                day_no = int(str(raw_key).strip())
            except (TypeError, ValueError):
                continue
            if day_no < 1 or day_no > len(days):
                print(f"⚠️  第{day_no}天不存在,忽略该天的景点修改")
                continue
            if isinstance(raw_items, str):
                raw_items = [raw_items]
            if not isinstance(raw_items, list):
                continue
            rebuilt = []
            for item in raw_items:
                attraction = _rebuild_attraction(item, plan, city)
                if attraction is not None:
                    rebuilt.append(attraction)
            if rebuilt:
                days[day_no - 1].attractions = rebuilt
                applied.append(f"第{day_no}天景点")

    # ---- 文字说明:追加,不覆盖 ----
    notes = str(changes.get("notes") or "").strip()
    if notes:
        existing = str(candidate.overall_suggestions or "").strip()
        candidate.overall_suggestions = f"{existing}\n{notes}" if existing else notes
        applied.append("补充说明")

    if not applied:
        return None

    if not _has_attractions(candidate):
        print("⚠️  变更后的行程没有任何景点,放弃本次修改")
        return None

    print(f"🔧 应用行程变更: {', '.join(applied)}")
    rebuilt_request = _request_from_plan(candidate, request, changes)
    return enrich_plan(candidate, rebuilt_request, get_amap_rest())


def _has_attractions(plan: TripPlan) -> bool:
    """判断行程是否至少有一个景点"""
    for day in plan.days or []:
        if day.attractions:
            return True
    return False


def _venues_of_day(day: Any) -> List[Any]:
    """收集一天里出现的所有地点(餐厅 + 酒店)"""
    venues: List[Any] = []
    for recommendation in day.restaurants or []:
        venues.extend(recommendation.venues or [])
    for entry in day.timeline or []:
        if getattr(entry, "venue", None) is not None:
            venues.append(entry.venue)
    return venues


@router.post(
    "/chat",
    response_model=ChatResponse,
    summary="行程小助手对话",
    description="就当前行程提问,或让「小星小探员」修改行程"
)
async def chat_with_planner(request: ChatRequest):
    """
    行程小助手对话

    Args:
        request: 对话请求(含当前行程)

    Returns:
        对话响应;任何异常都返回 200 + success=False
    """
    try:
        user_message = str(request.message or "").strip()
        if not user_message:
            return ChatResponse(
                success=True,
                reply="你想聊点什么呢?可以问我行程的时间安排、交通、餐厅或者预算～",
                plan=None,
                modified=False,
                suggestions=_default_suggestions(),
            )

        summary = _plan_summary(request.plan) if request.plan is not None else "当前还没有行程。"

        context_lines = [
            "**当前行程摘要:**",
            summary,
            "",
            f"**出行人数:** {max(1, min(20, int(request.travelers or 2)))}人",
        ]
        if request.transport_preferences:
            context_lines.append(f"**可接受交通方式:** {', '.join(str(x) for x in request.transport_preferences)}")
        context_lines.append("**提醒:** 不要输出完整行程 JSON,只按约定输出 reply/modified/suggestions/changes。")
        context_lines.append(f"**用户需求:** {user_message}")
        user_content = "\n".join(context_lines)

        messages: List[Dict[str, str]] = [{"role": "system", "content": CHAT_SYSTEM_PROMPT}]
        for item in (request.history or [])[-6:]:
            try:
                role = str(item.get("role") or "user")
                content = str(item.get("content") or "")
                if role in ("user", "assistant") and content:
                    messages.append({"role": role, "content": content[:2000]})
            except Exception:
                continue
        messages.append({"role": "user", "content": user_content})

        # max_tokens 必须显式给:HelloAgentsLLM 默认 None 会退化成服务商默认值(约 4096),
        # 曾导致输出被截断成非法 JSON。这里按「只要变更意图」的体量给 2000。
        raw = get_llm().invoke(messages, temperature=0.4, max_tokens=2000)
        data = _extract_json(raw)

        if not isinstance(data, dict):
            # 解析彻底失败 → 只把模型文本当回答,绝不当行程
            return ChatResponse(
                success=True,
                reply=_clamp_text(raw, 1500) or "小星小探员没太听懂,可以换个说法再问我一次～",
                plan=None,
                modified=False,
                suggestions=_default_suggestions(),
            )

        reply = _clamp_text(data.get("reply") or "", 1500) or "我在呢,有什么可以帮你的?"
        modified = bool(data.get("modified"))
        changes = data.get("changes") if isinstance(data.get("changes"), dict) else None
        new_plan: Optional[TripPlan] = None

        # 兼容老的 plan 直出格式(仍然支持,但不再是主路径)
        legacy_plan = data.get("plan")
        if modified and not changes and isinstance(legacy_plan, dict):
            candidate = _coerce_plan(legacy_plan, request.plan)
            if candidate is not None:
                try:
                    candidate = enrich_plan(candidate,
                                            _request_from_plan(candidate, request),
                                            get_amap_rest())
                    new_plan = candidate
                except Exception as exc:
                    print(f"⚠️  修改后的行程充实失败: {str(exc)}")
                    new_plan = candidate
            changes = None

        if modified and changes and request.plan is not None:
            try:
                new_plan = _apply_changes(request.plan, changes, request)
            except Exception as exc:
                print(f"⚠️  行程变更应用失败: {str(exc)}")
                import traceback
                traceback.print_exc()
                new_plan = None
            if new_plan is None:
                modified = False
                reply += "\n(这次修改没能落到具体行程上,原行程保持不变)"
        elif modified and not changes and new_plan is None:
            # modified=true 但没有任何可执行的变更 → 按「未修改」处理
            modified = False
            reply += "\n(这次没有识别出需要改动的具体内容,原行程保持不变)"

        suggestions = [str(item) for item in (data.get("suggestions") or []) if str(item).strip()]
        if len(suggestions) < 3:
            for fallback in _default_suggestions():
                if len(suggestions) >= 4:
                    break
                if fallback not in suggestions:
                    suggestions.append(fallback)

        return ChatResponse(
            success=True,
            reply=reply,
            plan=new_plan,
            modified=bool(new_plan is not None and modified),
            suggestions=suggestions[:4],
        )

    except Exception as exc:
        print(f"❌ 行程小助手对话失败: {str(exc)}")
        import traceback
        traceback.print_exc()
        return ChatResponse(
            success=False,
            reply="小星小探员暂时连接不上,请稍后再试～",
            plan=None,
            modified=False,
            suggestions=_default_suggestions(),
        )


@router.get(
    "/health",
    summary="健康检查",
    description="检查旅行规划服务是否正常"
)
async def health_check():
    """健康检查"""
    try:
        # 检查Agent是否可用
        agent = get_trip_planner_agent()

        return {
            "status": "healthy",
            "service": "trip-planner",
            "agent_name": agent.attraction_agent.name,
            "tools_count": len(agent.attraction_agent.list_tools()),
            "enricher": "ready"
        }
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail=f"服务不可用: {str(e)}"
        )
