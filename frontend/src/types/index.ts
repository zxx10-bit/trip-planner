// 类型定义 —— 小星探行

export interface Location {
  longitude: number
  latitude: number
}

export interface Attraction {
  name: string
  address: string
  location: Location
  visit_duration: number
  description: string
  category?: string
  rating?: number
  image_url?: string
  ticket_price?: number
}

export interface Meal {
  type: 'breakfast' | 'lunch' | 'dinner' | 'snack'
  name: string
  address?: string
  location?: Location
  description?: string
  estimated_cost?: number
}

export interface Hotel {
  name: string
  address: string
  location?: Location
  price_range: string
  rating: string
  distance: string
  type: string
  estimated_cost?: number
}

export interface Budget {
  total_attractions: number
  total_hotels: number
  total_meals: number
  total_transportation: number
  total: number
}

// ============ 交通方案 ============

export type TransportMode =
  | 'walking'
  | 'bus'
  | 'subway'
  | 'taxi'
  | 'cycling'
  | 'driving'

export interface TransportPlan {
  mode: TransportMode
  /** 中文短标签，如「地铁/公交」「步行」 */
  label: string
  duration_min: number
  distance_m: number
  /** 按出行人数计算的总费用(元) */
  cost: number
  /** 一句话方案，如「地铁1号线 · 约18分钟 · 约6元」 */
  summary: string
  /** 选择该方式的原因(结合用户偏好) */
  reason: string
  detail_lines: string[]
}

// ============ 场所(餐厅 / 酒店) ============

export interface Venue {
  name: string
  kind: 'restaurant' | 'hotel'
  address: string
  location?: Location
  rating: number
  /** 人均消费 / 每晚价格(元) */
  cost: number
  tags: string[]
  description: string
  distance: string
  tel: string
  photo: string
  party_size: number
  /** 特色菜品 */
  menu: string[]
  source: string
}

export interface RestaurantRecommendation {
  meal_type: 'lunch' | 'dinner'
  /** 邻近的景点名称 */
  near: string
  venues: Venue[]
}

// ============ 时刻表 ============

export type TimelineEntryType =
  | 'arrival'
  | 'attraction'
  | 'meal'
  | 'hotel'
  | 'rest'

export interface TimelineEntry {
  seq: number
  type: TimelineEntryType
  title: string
  address: string
  location?: Location
  /** HH:MM */
  arrive_time: string
  /** HH:MM，酒店条目为「次日」 */
  leave_time: string
  duration_min: number
  /** 下一站名称 */
  next_title: string
  /** 前往下一站的交通方案 */
  next_transport?: TransportPlan
  notes: string
  venue?: Venue
  attraction?: Attraction
  meal_type: string
}

// ============ 每日行程 ============

export interface DayPlan {
  date: string
  day_index: number
  description: string
  transportation: string
  accommodation: string
  start_time?: string
  end_time?: string
  timeline?: TimelineEntry[]
  restaurants?: RestaurantRecommendation[]
  hotel?: Hotel
  attractions: Attraction[]
  meals: Meal[]
}

export interface WeatherInfo {
  date: string
  day_weather: string
  night_weather: string
  day_temp: number
  night_temp: number
  wind_direction: string
  wind_power: string
}

export interface TripPlan {
  city: string
  start_date: string
  end_date: string
  days: DayPlan[]
  weather_info: WeatherInfo[]
  overall_suggestions: string
  budget?: Budget
}

// ============ 请求 ============

export interface TripFormData {
  city: string
  start_date: string
  end_date: string
  travel_days: number
  /** 抵达城市的时刻 HH:MM —— 时刻表的起点 */
  arrival_time: string
  /** 出行人数 */
  travelers: number
  /** 可接受的交通方式偏好 */
  transport_preferences: string[]
  /** 兼容原有字段 */
  transportation: string
  accommodation: string
  preferences: string[]
  free_text_input: string
}

export interface TripPlanResponse {
  success: boolean
  message: string
  data?: TripPlan
}

/** SSE 进度事件 */
export interface ProgressEvent {
  type: 'progress'
  percent: number
  message: string
  stage?: string
}

export interface ResultEvent {
  type: 'result'
  success: boolean
  message: string
  data?: TripPlan
}

export interface ErrorEvent {
  type: 'error'
  message: string
}

export type StreamEvent = ProgressEvent | ResultEvent | ErrorEvent

// ============ AI 助手 ============

export interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
  /** 助手消息附带的追问建议 */
  suggestions?: string[]
  time?: string
}

export interface ChatRequest {
  message: string
  plan?: TripPlan | null
  history?: Array<{ role: string; content: string }>
  travelers?: number
  transport_preferences?: string[]
}

export interface ChatResponse {
  success: boolean
  reply: string
  plan?: TripPlan | null
  modified: boolean
  suggestions: string[]
}
