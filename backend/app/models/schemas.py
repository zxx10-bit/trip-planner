"""数据模型定义"""

from typing import List, Optional, Union
from pydantic import BaseModel, Field, field_validator
from datetime import date


# ============ 请求模型 ============

class TripRequest(BaseModel):
    """旅行规划请求"""
    city: str = Field(..., description="目的地城市", example="北京")
    start_date: str = Field(..., description="开始日期 YYYY-MM-DD", example="2025-06-01")
    end_date: str = Field(..., description="结束日期 YYYY-MM-DD", example="2025-06-03")
    travel_days: int = Field(..., description="旅行天数", ge=1, le=30, example=3)
    transportation: str = Field(..., description="交通方式", example="公共交通")
    accommodation: str = Field(..., description="住宿偏好", example="经济型酒店")
    preferences: List[str] = Field(default=[], description="旅行偏好标签", example=["历史文化", "美食"])
    free_text_input: Optional[str] = Field(default="", description="额外要求", example="希望多安排一些博物馆")
    arrival_time: str = Field(default="09:00", description="抵达城市的时刻 HH:MM")
    travelers: int = Field(default=2, ge=1, le=20, description="出行人数")
    transport_preferences: List[str] = Field(default_factory=lambda: ["步行","公交","地铁","打车","骑行"], description="可接受的交通方式偏好")
    
    class Config:
        json_schema_extra = {
            "example": {
                "city": "北京",
                "start_date": "2025-06-01",
                "end_date": "2025-06-03",
                "travel_days": 3,
                "transportation": "公共交通",
                "accommodation": "经济型酒店",
                "preferences": ["历史文化", "美食"],
                "free_text_input": "希望多安排一些博物馆"
            }
        }


class POISearchRequest(BaseModel):
    """POI搜索请求"""
    keywords: str = Field(..., description="搜索关键词", example="故宫")
    city: str = Field(..., description="城市", example="北京")
    citylimit: bool = Field(default=True, description="是否限制在城市范围内")


class RouteRequest(BaseModel):
    """路线规划请求"""
    origin_address: str = Field(..., description="起点地址", example="北京市朝阳区阜通东大街6号")
    destination_address: str = Field(..., description="终点地址", example="北京市海淀区上地十街10号")
    origin_city: Optional[str] = Field(default=None, description="起点城市")
    destination_city: Optional[str] = Field(default=None, description="终点城市")
    route_type: str = Field(default="walking", description="路线类型: walking/driving/transit")


# ============ 响应模型 ============

class Location(BaseModel):
    """地理位置"""
    longitude: float = Field(..., description="经度")
    latitude: float = Field(..., description="纬度")


class Attraction(BaseModel):
    """景点信息"""
    name: str = Field(..., description="景点名称")
    address: str = Field(..., description="地址")
    location: Location = Field(..., description="经纬度坐标")
    visit_duration: int = Field(..., description="建议游览时间(分钟)")
    description: str = Field(..., description="景点描述")
    category: Optional[str] = Field(default="景点", description="景点类别")
    rating: Optional[float] = Field(default=None, description="评分")
    photos: Optional[List[str]] = Field(default_factory=list, description="景点图片URL列表")
    poi_id: Optional[str] = Field(default="", description="POI ID")
    image_url: Optional[str] = Field(default=None, description="图片URL")
    ticket_price: int = Field(default=0, description="门票价格(元)")


class Meal(BaseModel):
    """餐饮信息"""
    type: str = Field(..., description="餐饮类型: breakfast/lunch/dinner/snack")
    name: str = Field(..., description="餐饮名称")
    address: Optional[str] = Field(default=None, description="地址")
    location: Optional[Location] = Field(default=None, description="经纬度坐标")
    description: Optional[str] = Field(default=None, description="描述")
    estimated_cost: int = Field(default=0, description="预估费用(元)")


class Hotel(BaseModel):
    """酒店信息"""
    name: str = Field(..., description="酒店名称")
    address: str = Field(default="", description="酒店地址")
    location: Optional[Location] = Field(default=None, description="酒店位置")
    price_range: str = Field(default="", description="价格范围")
    rating: str = Field(default="", description="评分")
    distance: str = Field(default="", description="距离景点距离")
    type: str = Field(default="", description="酒店类型")
    estimated_cost: int = Field(default=0, description="预估费用(元/晚)")


class Venue(BaseModel):
    """地点（餐厅 / 酒店）——由高德实时数据填充"""
    name: str = Field(..., description="地点名称")
    kind: str = Field(..., description="类型: restaurant(餐厅)/hotel(酒店)")
    address: str = Field(default="", description="详细地址")
    location: Optional[Location] = Field(default=None, description="经纬度坐标")
    rating: float = Field(default=0, description="评分")
    cost: float = Field(default=0, description="人均/每晚费用(元)")
    tags: List[str] = Field(default=[], description="标签,如菜系、人均价位")
    description: str = Field(default="", description="中文简介")
    distance: str = Field(default="", description="距离说明,如 距景点320米")
    tel: str = Field(default="", description="联系电话")
    photo: str = Field(default="", description="图片URL")
    party_size: int = Field(default=0, description="适配人数")
    menu: List[str] = Field(default=[], description="招牌菜/特色菜列表")
    source: str = Field(default="amap", description="数据来源: amap/llm/fallback")

    class Config:
        extra = "ignore"


class TransportPlan(BaseModel):
    """两站之间的交通方案"""
    mode: str = Field(..., description="交通方式: walking/bus/subway/taxi/cycling/driving")
    label: str = Field(..., description="中文标签,如 步行/地铁公交/打车")
    duration_min: int = Field(..., description="预计耗时(分钟)")
    distance_m: int = Field(..., description="预计距离(米)")
    cost: int = Field(default=0, description="预计费用(元,按人数计)")
    summary: str = Field(..., description="一句话方案,如 地铁1号线约18分钟")
    reason: str = Field(..., description="选择该方式的原因(结合用户偏好)")
    detail_lines: List[str] = Field(default=[], description="明细行,如具体线路名")

    class Config:
        extra = "ignore"


class TimelineEntry(BaseModel):
    """时间轴上的一条安排"""
    seq: int = Field(..., description="序号,从0开始")
    type: str = Field(..., description="类型: arrival/attraction/meal/hotel/rest")
    title: str = Field(..., description="标题")
    address: str = Field(default="", description="地址")
    location: Optional[Location] = Field(default=None, description="经纬度坐标")
    arrive_time: str = Field(..., description="到达时刻 HH:MM")
    leave_time: str = Field(default="", description="离开时刻 HH:MM,酒店条目为 次日")
    duration_min: int = Field(default=0, description="停留时长(分钟)")
    next_title: str = Field(default="", description="下一站标题")
    next_transport: Optional[TransportPlan] = Field(default=None, description="前往下一站的交通方案")
    notes: str = Field(default="", description="备注")
    venue: Optional[Venue] = Field(default=None, description="关联餐厅/酒店")
    attraction: Optional[Attraction] = Field(default=None, description="关联景点")
    meal_type: str = Field(default="", description="餐饮类型: lunch/dinner")

    class Config:
        extra = "ignore"


class RestaurantRecommendation(BaseModel):
    """某一餐的餐厅推荐"""
    meal_type: str = Field(..., description="餐饮类型: lunch/dinner")
    near: str = Field(..., description="邻近景点名称")
    venues: List[Venue] = Field(default=[], description="推荐餐厅列表")

    class Config:
        extra = "ignore"


class DayPlan(BaseModel):
    """单日行程"""
    date: str = Field(..., description="日期 YYYY-MM-DD")
    day_index: int = Field(..., description="第几天(从0开始)")
    description: str = Field(..., description="当日行程描述")
    transportation: str = Field(..., description="交通方式")
    accommodation: str = Field(..., description="住宿")
    hotel: Optional[Hotel] = Field(default=None, description="推荐酒店")
    attractions: List[Attraction] = Field(default=[], description="景点列表")
    meals: List[Meal] = Field(default=[], description="餐饮列表")
    start_time: str = Field(default="09:00", description="当日开始时刻 HH:MM")
    end_time: str = Field(default="", description="当日结束时刻 HH:MM")
    timeline: List[TimelineEntry] = Field(default=[], description="时间轴行程")
    restaurants: List[RestaurantRecommendation] = Field(default=[], description="餐厅推荐")

    class Config:
        extra = "ignore"


class WeatherInfo(BaseModel):
    """天气信息"""
    date: str = Field(..., description="日期 YYYY-MM-DD")
    day_weather: str = Field(default="", description="白天天气")
    night_weather: str = Field(default="", description="夜间天气")
    day_temp: Union[int, str] = Field(default=0, description="白天温度")
    night_temp: Union[int, str] = Field(default=0, description="夜间温度")
    wind_direction: str = Field(default="", description="风向")
    wind_power: str = Field(default="", description="风力")

    @field_validator('day_temp', 'night_temp', mode='before')
    @classmethod
    def parse_temperature(cls, v):
        """解析温度,移除°C等单位"""
        if isinstance(v, str):
            # 移除°C, ℃等单位符号
            v = v.replace('°C', '').replace('℃', '').replace('°', '').strip()
            try:
                return int(v)
            except ValueError:
                return 0
        return v


class Budget(BaseModel):
    """预算信息"""
    total_attractions: int = Field(default=0, description="景点门票总费用")
    total_hotels: int = Field(default=0, description="酒店总费用")
    total_meals: int = Field(default=0, description="餐饮总费用")
    total_transportation: int = Field(default=0, description="交通总费用")
    total: int = Field(default=0, description="总费用")


class TripPlan(BaseModel):
    """旅行计划"""
    city: str = Field(..., description="目的地城市")
    start_date: str = Field(..., description="开始日期")
    end_date: str = Field(..., description="结束日期")
    days: List[DayPlan] = Field(..., description="每日行程")
    weather_info: List[WeatherInfo] = Field(default=[], description="天气信息")
    overall_suggestions: str = Field(..., description="总体建议")
    budget: Optional[Budget] = Field(default=None, description="预算信息")


class TripPlanResponse(BaseModel):
    """旅行计划响应"""
    success: bool = Field(..., description="是否成功")
    message: str = Field(default="", description="消息")
    data: Optional[TripPlan] = Field(default=None, description="旅行计划数据")


class ChatRequest(BaseModel):
    """旅行助手对话请求"""
    message: str = Field(..., description="用户提问或修改要求")
    plan: Optional[TripPlan] = Field(default=None, description="当前旅行计划(用于上下文)")
    history: List[dict] = Field(default=[], description="历史对话,元素形如 {\"role\":\"user\",\"content\":\"...\"}")
    travelers: int = Field(default=2, description="出行人数")
    transport_preferences: List[str] = Field(default=[], description="可接受的交通方式偏好")

    class Config:
        extra = "ignore"


class ChatResponse(BaseModel):
    """旅行助手对话响应"""
    success: bool = Field(default=True, description="是否成功")
    reply: str = Field(..., description="助手的中文回答")
    plan: Optional[TripPlan] = Field(default=None, description="修改后的完整旅行计划,无修改时为 null")
    modified: bool = Field(default=False, description="是否修改了行程")
    suggestions: List[str] = Field(default=[], description="可继续追问的短问题")

    class Config:
        extra = "ignore"


class POIInfo(BaseModel):
    """POI信息"""
    id: str = Field(..., description="POI ID")
    name: str = Field(..., description="名称")
    type: str = Field(..., description="类型")
    address: str = Field(..., description="地址")
    location: Location = Field(..., description="经纬度坐标")
    tel: Optional[str] = Field(default=None, description="电话")


class POISearchResponse(BaseModel):
    """POI搜索响应"""
    success: bool = Field(..., description="是否成功")
    message: str = Field(default="", description="消息")
    data: List[POIInfo] = Field(default=[], description="POI列表")


class RouteInfo(BaseModel):
    """路线信息"""
    distance: float = Field(..., description="距离(米)")
    duration: int = Field(..., description="时间(秒)")
    route_type: str = Field(..., description="路线类型")
    description: str = Field(..., description="路线描述")


class RouteResponse(BaseModel):
    """路线规划响应"""
    success: bool = Field(..., description="是否成功")
    message: str = Field(default="", description="消息")
    data: Optional[RouteInfo] = Field(default=None, description="路线信息")


class WeatherResponse(BaseModel):
    """天气查询响应"""
    success: bool = Field(..., description="是否成功")
    message: str = Field(default="", description="消息")
    data: List[WeatherInfo] = Field(default=[], description="天气信息")


# ============ 错误响应 ============

class ErrorResponse(BaseModel):
    """错误响应"""
    success: bool = Field(default=False, description="是否成功")
    message: str = Field(..., description="错误消息")
    error_code: Optional[str] = Field(default=None, description="错误代码")

