import axios from 'axios'
import type {
  TripFormData,
  TripPlanResponse,
  StreamEvent,
  ChatRequest,
  ChatResponse
} from '@/types'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

const apiClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: 120000, // 2分钟超时
  headers: {
    'Content-Type': 'application/json'
  }
})

// 请求拦截器
apiClient.interceptors.request.use(
  (config) => {
    console.log('发送请求:', config.method?.toUpperCase(), config.url)
    return config
  },
  (error) => {
    console.error('请求错误:', error)
    return Promise.reject(error)
  }
)

// 响应拦截器
apiClient.interceptors.response.use(
  (response) => {
    console.log('收到响应:', response.status, response.config.url)
    return response
  },
  (error) => {
    console.error('响应错误:', error.response?.status, error.message)
    return Promise.reject(error)
  }
)

/**
 * 生成旅行计划
 */
export async function generateTripPlan(formData: TripFormData): Promise<TripPlanResponse> {
  try {
    const response = await apiClient.post<TripPlanResponse>('/api/trip/plan', formData)
    return response.data
  } catch (error: any) {
    console.error('生成旅行计划失败:', error)
    throw new Error(error.response?.data?.detail || error.message || '生成旅行计划失败')
  }
}

/**
 * 流式生成旅行计划(SSE)
 *
 * 后端在生成攻略的每个真实阶段推送进度事件,前端据此驱动进度条,
 * 因此进度不会「卡在 90%」。
 *
 * @param formData 表单数据
 * @param onEvent  每个事件回调
 * @param signal   用于取消请求
 */
export async function streamTripPlan(
  formData: TripFormData,
  onEvent: (event: StreamEvent) => void,
  signal?: AbortSignal
): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/api/trip/plan/stream`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Accept: 'text/event-stream'
    },
    body: JSON.stringify(formData),
    signal
  })

  if (!response.ok) {
    const text = await response.text().catch(() => '')
    throw new Error(text || `服务端返回 ${response.status}`)
  }
  if (!response.body) {
    throw new Error('浏览器不支持流式响应')
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder('utf-8')
  let buffer = ''

  const dispatch = (raw: string) => {
    const payload = raw
      .split('\n')
      .filter((line) => line.startsWith('data:'))
      .map((line) => line.slice(5).trim())
      .join('')

    if (!payload || payload === '[DONE]') return

    try {
      onEvent(JSON.parse(payload) as StreamEvent)
    } catch (err) {
      console.warn('无法解析进度事件:', payload)
    }
  }

  for (;;) {
    const { done, value } = await reader.read()
    if (done) break

    buffer += decoder.decode(value, { stream: true })

    // SSE 事件以空行分隔
    let boundary = buffer.indexOf('\n\n')
    while (boundary !== -1) {
      dispatch(buffer.slice(0, boundary))
      buffer = buffer.slice(boundary + 2)
      boundary = buffer.indexOf('\n\n')
    }
  }

  if (buffer.trim()) dispatch(buffer)
}

/**
 * 与「小星小探员」对话:修改行程 / 答疑
 */
export async function chatWithAgent(payload: ChatRequest): Promise<ChatResponse> {
  try {
    const response = await apiClient.post<ChatResponse>('/api/trip/chat', payload)
    return response.data
  } catch (error: any) {
    console.error('AI 助手对话失败:', error)
    return {
      success: false,
      reply:
        error.response?.data?.detail ||
        '小星小探员暂时连接不上，请稍后再试～',
      modified: false,
      suggestions: []
    }
  }
}

/**
 * 健康检查
 */
export async function healthCheck(): Promise<any> {
  try {
    const response = await apiClient.get('/health')
    return response.data
  } catch (error: any) {
    console.error('健康检查失败:', error)
    throw new Error(error.message || '健康检查失败')
  }
}

export default apiClient
export { API_BASE_URL }
