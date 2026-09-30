<template>
  <div class="home-page">
    <!-- 背景装饰 -->
    <div class="bg-decor" aria-hidden="true">
      <span class="blob blob-1"></span>
      <span class="blob blob-2"></span>
      <span class="blob blob-3"></span>
      <span class="star star-1">✦</span>
      <span class="star star-2">✦</span>
      <span class="star star-3">✦</span>
    </div>

    <!-- 主视觉 -->
    <header class="hero">
      <div class="hero-badge">
        <span class="badge-spark">✦</span> 小星探行 · 快乐出行
      </div>
      <h1 class="hero-title">
        让小星替你<span class="hl">把每一分钟</span>都安排好
      </h1>
      <p class="hero-sub">
        以抵达时刻为起点的精细时刻表 · 自动计算通勤时长与方式 · 景点周边高分餐厅与招牌菜 ·
        当日末站附近的酒店，一份完整攻略直接出发。
      </p>
      <div class="hero-features">
        <div class="feature">
          <span class="feature-icon">🛰️</span>
          <div>
            <div class="feature-title">精细时刻表</div>
            <div class="feature-desc">到达 / 离开 / 下一站</div>
          </div>
        </div>
        <div class="feature">
          <span class="feature-icon">🚇</span>
          <div>
            <div class="feature-title">通勤自动规划</div>
            <div class="feature-desc">匹配你的出行偏好</div>
          </div>
        </div>
        <div class="feature">
          <span class="feature-icon">🍜</span>
          <div>
            <div class="feature-title">高分餐厅推荐</div>
            <div class="feature-desc">含人均与特色菜品</div>
          </div>
        </div>
        <div class="feature">
          <span class="feature-icon">🏨</span>
          <div>
            <div class="feature-title">末站附近酒店</div>
            <div class="feature-desc">按人数推荐房型</div>
          </div>
        </div>
      </div>
    </header>

    <a-card class="form-card" :bordered="false">
      <a-form :model="formData" layout="vertical" @finish="handleSubmit">
        <!-- 第一步:行程基础 -->
        <section class="form-section">
          <div class="section-head">
            <span class="section-index">01</span>
            <div>
              <div class="section-title">行程基础</div>
              <div class="section-tip">时刻表将从你填写的抵达时刻开始计算</div>
            </div>
          </div>

          <a-row :gutter="20">
            <a-col :xs="24" :sm="12" :lg="8">
              <a-form-item name="city" :rules="[{ required: true, message: '请输入目的地城市' }]">
                <template #label><span class="form-label">目的地城市</span></template>
                <a-input
                  v-model:value="formData.city"
                  placeholder="例如:北京"
                  size="large"
                  class="custom-input"
                >
                  <template #prefix><span class="prefix-emoji">🏙️</span></template>
                </a-input>
              </a-form-item>
            </a-col>

            <a-col :xs="24" :sm="12" :lg="6">
              <a-form-item name="start_date" :rules="[{ required: true, message: '请选择开始日期' }]">
                <template #label><span class="form-label">开始日期</span></template>
                <a-date-picker
                  v-model:value="formData.start_date"
                  style="width: 100%"
                  size="large"
                  class="custom-input"
                  placeholder="选择日期"
                />
              </a-form-item>
            </a-col>

            <a-col :xs="24" :sm="12" :lg="6">
              <a-form-item name="end_date" :rules="[{ required: true, message: '请选择结束日期' }]">
                <template #label><span class="form-label">结束日期</span></template>
                <a-date-picker
                  v-model:value="formData.end_date"
                  style="width: 100%"
                  size="large"
                  class="custom-input"
                  placeholder="选择日期"
                />
              </a-form-item>
            </a-col>

            <a-col :xs="24" :sm="12" :lg="4">
              <a-form-item>
                <template #label><span class="form-label">旅行天数</span></template>
                <div class="days-pill">
                  <span class="days-value">{{ formData.travel_days }}</span>
                  <span class="days-unit">天</span>
                </div>
              </a-form-item>
            </a-col>
          </a-row>

          <a-row :gutter="20">
            <a-col :xs="24" :sm="12" :lg="8">
              <a-form-item name="arrival_time">
                <template #label>
                  <span class="form-label">
                    抵达时刻
                    <a-tooltip title="时刻表以该时刻为起点，自动排布当天每一站">
                      <span class="label-help">?</span>
                    </a-tooltip>
                  </span>
                </template>
                <a-time-picker
                  v-model:value="formData.arrival_time"
                  format="HH:mm"
                  minute-step="5"
                  style="width: 100%"
                  size="large"
                  class="custom-input"
                  placeholder="选择抵达时刻"
                />
              </a-form-item>
            </a-col>

            <a-col :xs="24" :sm="12" :lg="8">
              <a-form-item name="travelers">
                <template #label>
                  <span class="form-label">
                    出行人数
                    <a-tooltip title="酒店房型与餐厅推荐、交通费用都会按人数计算">
                      <span class="label-help">?</span>
                    </a-tooltip>
                  </span>
                </template>
                <a-input-number
                  v-model:value="formData.travelers"
                  :min="1"
                  :max="20"
                  size="large"
                  style="width: 100%"
                  class="custom-input"
                  addon-after="人"
                />
                <div class="quick-people">
                  <button
                    v-for="n in peoplePresets"
                    :key="n"
                    type="button"
                    class="mini-chip"
                    :class="{ active: formData.travelers === n }"
                    @click="formData.travelers = n"
                  >
                    {{ n }}人
                  </button>
                </div>
              </a-form-item>
            </a-col>

            <a-col :xs="24" :sm="12" :lg="8">
              <a-form-item name="accommodation">
                <template #label><span class="form-label">住宿偏好</span></template>
                <a-select v-model:value="formData.accommodation" size="large" class="custom-select">
                  <a-select-option value="经济型酒店">💰 经济型酒店</a-select-option>
                  <a-select-option value="舒适型酒店">🏨 舒适型酒店</a-select-option>
                  <a-select-option value="豪华酒店">⭐ 豪华酒店</a-select-option>
                  <a-select-option value="民宿">🏡 民宿</a-select-option>
                  <a-select-option value="青年旅舍">🎒 青年旅舍</a-select-option>
                </a-select>
              </a-form-item>
            </a-col>
          </a-row>
        </section>

        <!-- 第二步:出行偏好 -->
        <section class="form-section">
          <div class="section-head">
            <span class="section-index">02</span>
            <div>
              <div class="section-title">出行偏好</div>
              <div class="section-tip">景点之间的交通方案会优先匹配你勾选的方式</div>
            </div>
          </div>

          <a-row :gutter="20">
            <a-col :xs="24" :lg="12">
              <a-form-item name="transport_preferences">
                <template #label>
                  <span class="form-label">
                    可接受的交通方式
                    <em class="label-count">已选 {{ formData.transport_preferences.length }} 项</em>
                  </span>
                </template>
                <div class="transport-grid">
                  <label
                    v-for="opt in transportOptions"
                    :key="opt.value"
                    class="transport-card"
                    :class="{ active: formData.transport_preferences.includes(opt.value) }"
                  >
                    <input
                      type="checkbox"
                      :value="opt.value"
                      v-model="formData.transport_preferences"
                    />
                    <span class="transport-icon">{{ opt.icon }}</span>
                    <span class="transport-text">
                      <span class="transport-name">{{ opt.label }}</span>
                      <span class="transport-desc">{{ opt.desc }}</span>
                    </span>
                  </label>
                </div>
              </a-form-item>
            </a-col>

            <a-col :xs="24" :lg="12">
              <a-form-item name="preferences">
                <template #label><span class="form-label">旅行偏好</span></template>
                <div class="pref-grid">
                  <button
                    v-for="pref in preferenceOptions"
                    :key="pref.value"
                    type="button"
                    class="pref-card"
                    :class="{ active: formData.preferences.includes(pref.value) }"
                    @click="togglePreference(pref.value)"
                  >
                    <span class="pref-icon">{{ pref.icon }}</span>{{ pref.label }}
                  </button>
                </div>
              </a-form-item>
            </a-col>
          </a-row>
        </section>

        <!-- 第三步:额外要求 -->
        <section class="form-section">
          <div class="section-head">
            <span class="section-index">03</span>
            <div>
              <div class="section-title">额外要求</div>
              <div class="section-tip">过敏、无障碍、想避开人流……都可以写在这里</div>
            </div>
          </div>

          <a-form-item name="free_text_input">
            <a-textarea
              v-model:value="formData.free_text_input"
              placeholder="例如:想去看升旗、需要无障碍设施、对海鲜过敏、希望少走路、有老人同行..."
              :rows="3"
              size="large"
              class="custom-textarea"
            />
          </a-form-item>
        </section>

        <a-form-item class="submit-item">
          <a-button
            type="primary"
            html-type="submit"
            :loading="loading"
            size="large"
            block
            class="submit-button"
          >
            <template v-if="!loading">
              <span class="button-icon">✨</span>
              <span>生成我的完整攻略</span>
            </template>
            <template v-else>
              <span>小星正在探测 {{ formData.city || '目的地' }} …</span>
            </template>
          </a-button>
          <div class="submit-hint">
            <span>🛰️ 实时进度</span>
            <span>⏱️ 通常 1–3 分钟</span>
            <span>💬 生成后可让小星小探员继续调整</span>
          </div>
        </a-form-item>

        <!-- 真实进度面板 -->
        <a-form-item v-if="loading" id="progress-panel">
          <div class="progress-panel">
            <div class="progress-top">
              <div class="progress-status">
                <span class="pulse-dot"></span>
                {{ loadingStatus || '正在连接小星探测引擎…' }}
              </div>
              <div class="progress-percent">{{ Math.round(displayProgress) }}%</div>
            </div>

            <a-progress
              :percent="Math.round(displayProgress)"
              :show-info="false"
              :stroke-color="{ '0%': '#6d5efc', '50%': '#8b5cf6', '100%': '#14c8b1' }"
              :stroke-width="12"
              class="progress-bar"
            />

            <div class="step-track">
              <div
                v-for="step in steps"
                :key="step.label"
                class="step"
                :class="{
                  done: displayProgress >= step.at + 1,
                  active: currentStep === step.label
                }"
              >
                <span class="step-dot">{{ displayProgress >= step.at + 1 ? '✓' : '' }}</span>
                <span class="step-label">{{ step.label }}</span>
              </div>
            </div>

            <div class="progress-meta">
              <span>⏱️ 已用时 {{ elapsedText }}</span>
              <span v-if="streamMode">📡 服务端实时进度</span>
              <span v-else>🎛️ 本地估算进度</span>
            </div>

            <div v-if="logs.length" ref="logRef" class="progress-log">
              <div v-for="(log, i) in logs" :key="i" class="log-line">
                <span class="log-time">{{ log.time }}</span>
                <span class="log-text">{{ log.text }}</span>
              </div>
            </div>

            <div class="progress-note">
              小星正在真实调用地图与 AI 服务，每一步完成都会推进进度，不会卡在 90%。
            </div>
          </div>
        </a-form-item>
      </a-form>
    </a-card>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, watch, onUnmounted, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import { message } from 'ant-design-vue'
import dayjs, { type Dayjs } from 'dayjs'
import { streamTripPlan, generateTripPlan } from '@/services/api'
import type { TripFormData, StreamEvent } from '@/types'

const router = useRouter()

const loading = ref(false)
const loadingProgress = ref(0)
const displayProgress = ref(0)
const loadingStatus = ref('')
const streamMode = ref(true)
const elapsedSeconds = ref(0)
const logs = ref<Array<{ time: string; text: string }>>([])
const logRef = ref<HTMLElement | null>(null)

let streamError = ''
let rafId = 0
let tickTimer: ReturnType<typeof setInterval> | null = null
let clockTimer: ReturnType<typeof setInterval> | null = null
let abortController: AbortController | null = null

type TripFormState = Omit<TripFormData, 'start_date' | 'end_date' | 'arrival_time'> & {
  start_date: Dayjs | null
  end_date: Dayjs | null
  arrival_time: Dayjs | null
}

const formData = reactive<TripFormState>({
  city: '',
  start_date: null,
  end_date: null,
  travel_days: 1,
  arrival_time: dayjs('09:00', 'HH:mm'),
  travelers: 2,
  transport_preferences: ['步行', '公交', '地铁', '打车', '骑行'],
  transportation: '公共交通',
  accommodation: '舒适型酒店',
  preferences: [],
  free_text_input: ''
})

const peoplePresets = [1, 2, 3, 4, 6]

const transportOptions = [
  { value: '步行', label: '步行', desc: '1.2km 内优先', icon: '🚶' },
  { value: '公交', label: '公交', desc: '含公交线路', icon: '🚌' },
  { value: '地铁', label: '地铁', desc: '中长途优先', icon: '🚇' },
  { value: '打车', label: '打车', desc: '最快但费用高', icon: '🚕' },
  { value: '骑行', label: '骑行', desc: '1–3km 灵活', icon: '🚲' }
]

const preferenceOptions = [
  { value: '历史文化', label: '历史文化', icon: '🏛️' },
  { value: '自然风光', label: '自然风光', icon: '🏞️' },
  { value: '美食', label: '美食', icon: '🍜' },
  { value: '购物', label: '购物', icon: '🛍️' },
  { value: '艺术', label: '艺术', icon: '🎨' },
  { value: '休闲', label: '休闲', icon: '☕' },
  { value: '夜景', label: '夜景', icon: '🌃' },
  { value: '亲子', label: '亲子', icon: '🧸' }
]

const steps = [
  { label: '景点搜索', at: 18 },
  { label: '天气查询', at: 38 },
  { label: '酒店推荐', at: 50 },
  { label: '行程编排', at: 62 },
  { label: '通勤计算', at: 74 },
  { label: '餐厅酒店', at: 88 },
  { label: '攻略整合', at: 96 }
]

const currentStep = computed(() => {
  let label = steps[0].label
  for (const step of steps) {
    if (displayProgress.value >= step.at) label = step.label
  }
  return label
})

const elapsedText = computed(() => {
  const s = elapsedSeconds.value
  const m = Math.floor(s / 60)
  const rest = s % 60
  return m > 0 ? `${m}分${String(rest).padStart(2, '0')}秒` : `${rest}秒`
})

/** 平滑把进度条推向真实进度,避免数值跳跃 */
const animateProgress = () => {
  const target = loadingProgress.value
  if (displayProgress.value < target) {
    displayProgress.value = Math.min(target, displayProgress.value + 0.45)
  } else if (displayProgress.value > target) {
    displayProgress.value = target
  }
  rafId = requestAnimationFrame(animateProgress)
}

const pushLog = (text: string) => {
  const d = new Date()
  const time = `${String(d.getMinutes()).padStart(2, '0')}:${String(d.getSeconds()).padStart(2, '0')}`
  if (logs.value[logs.value.length - 1]?.text === text) return
  logs.value.push({ time, text })
  if (logs.value.length > 40) logs.value.shift()
  // 让日志始终停在最新一条
  nextTick(() => {
    const el = logRef.value
    if (el) el.scrollTop = el.scrollHeight
  })
}

// 日期变化 → 自动计算天数
watch([() => formData.start_date, () => formData.end_date], ([start, end]) => {
  if (start && end) {
    const days = end.diff(start, 'day') + 1
    if (days > 0 && days <= 30) {
      formData.travel_days = days
    } else if (days > 30) {
      message.warning('旅行天数不能超过30天')
      formData.end_date = null
    } else {
      message.warning('结束日期不能早于开始日期')
      formData.end_date = null
    }
  }
})

const togglePreference = (value: string) => {
  const list = formData.preferences
  const index = list.indexOf(value)
  if (index === -1) list.push(value)
  else list.splice(index, 1)
}

/** 兼容后端原有 transportation 字段 */
const deriveLegacyTransportation = (prefs: string[]): string => {
  if (!prefs.length) return '混合'
  const transit = prefs.some((p) => p === '公交' || p === '地铁')
  if (transportOptions.every((o) => prefs.includes(o.value))) return '混合'
  if (transit && prefs.includes('步行')) return '公共交通'
  if (transit) return '公共交通'
  if (prefs.includes('步行') && prefs.length === 1) return '步行'
  if (prefs.includes('骑行') && prefs.length === 1) return '骑行'
  if (prefs.includes('打车') && prefs.length === 1) return '自驾'
  return '混合'
}

const stopTimers = () => {
  if (rafId) cancelAnimationFrame(rafId)
  rafId = 0
  if (tickTimer) clearInterval(tickTimer)
  tickTimer = null
  if (clockTimer) clearInterval(clockTimer)
  clockTimer = null
}

onUnmounted(() => {
  stopTimers()
  abortController?.abort()
})

const handleStreamEvent = (event: StreamEvent) => {
  if (event.type === 'progress') {
    loadingProgress.value = Math.max(loadingProgress.value, Math.min(99, event.percent))
    if (event.message) {
      loadingStatus.value = event.message
      pushLog(event.message)
    }
  } else if (event.type === 'result') {
    if (event.success && event.data) {
      finishWithPlan(event.data)
    } else {
      streamError = event.message || '生成失败'
    }
  } else if (event.type === 'error') {
    streamError = event.message || '生成失败'
  }
}

const finishWithPlan = (plan: any) => {
  loadingProgress.value = 100
  displayProgress.value = 100
  loadingStatus.value = '✅ 攻略已生成,正在准备展示…'
  sessionStorage.setItem('tripPlan', JSON.stringify(plan))
  message.success('完整攻略生成成功!')
  setTimeout(() => router.push('/result'), 420)
}

const handleSubmit = async () => {  if (!formData.start_date || !formData.end_date) {
    message.error('请选择日期')
    return
  }
  if (!formData.transport_preferences.length) {
    message.warning('请至少选择一种可接受的交通方式')
    return
  }

  loading.value = true
  loadingProgress.value = 0
  displayProgress.value = 0
  logs.value = []
  elapsedSeconds.value = 0
  streamMode.value = true
  streamError = ''
  loadingStatus.value = '🚀 正在初始化规划引擎…'
  pushLog('🚀 正在初始化规划引擎…')

  rafId = requestAnimationFrame(animateProgress)
  clockTimer = setInterval(() => {
    elapsedSeconds.value += 1
  }, 1000)

  const requestData: TripFormData = {
    city: formData.city,
    start_date: formData.start_date.format('YYYY-MM-DD'),
    end_date: formData.end_date.format('YYYY-MM-DD'),
    travel_days: formData.travel_days,
    arrival_time: (formData.arrival_time ?? dayjs('09:00', 'HH:mm')).format('HH:mm'),
    travelers: formData.travelers,
    transport_preferences: [...formData.transport_preferences],
    transportation: deriveLegacyTransportation(formData.transport_preferences),
    accommodation: formData.accommodation,
    preferences: formData.preferences,
    free_text_input: formData.free_text_input
  }

  sessionStorage.setItem('tripForm', JSON.stringify(requestData))
  sessionStorage.removeItem('tripPlan')

  try {
    abortController = new AbortController()
    await streamTripPlan(requestData, handleStreamEvent, abortController.signal)
    // 流已结束:可能拿到了攻略,也可能服务端报告了错误
    if (streamError) throw new Error(streamError)
    if (!sessionStorage.getItem('tripPlan')) {
      throw new Error('服务端未返回攻略数据')
    }
  } catch (error: any) {
    console.warn('流式生成失败,回退到普通请求:', error)
    streamMode.value = false
    loadingStatus.value = '🔁 实时通道不可用,已切换为常规生成…'
    pushLog('🔁 已切换为常规生成模式')
    try {
      const response = await generateTripPlan(requestData)
      if (response.success && response.data) {
        finishWithPlan(response.data)
      } else {
        throw new Error(response.message || '生成失败')
      }
    } catch (fallbackError: any) {
      message.error(fallbackError?.message || '生成旅行计划失败,请稍后重试')
      stopTimers()
      loading.value = false
      loadingProgress.value = 0
      displayProgress.value = 0
      return
    }
  } finally {
    stopTimers()
    setTimeout(() => {
      loading.value = false
    }, 900)
  }
}

/**
 * 调试开关:?progress=demo 时展示进度面板的静态预览。
 * 仅用于自动化截图/端到端测试,不影响正常提交逻辑。
 */
if (new URLSearchParams(window.location.search).get('progress') === 'demo') {
  loading.value = true
  loadingProgress.value = 62
  displayProgress.value = 62
  elapsedSeconds.value = 74
  streamMode.value = true
  loadingStatus.value = '正在挑选附近餐厅…'
  logs.value = [
    { time: '09:41', text: '🚀 正在初始化规划引擎…' },
    { time: '09:41', text: '🛰️ 小星探员已就位,开始采集目的地信息' },
    { time: '09:41', text: '正在搜索目的地景点…' },
    { time: '09:42', text: '正在查询当地天气…' },
    { time: '09:42', text: '正在筛选住宿…' },
    { time: '09:43', text: '正在编排每日行程…' },
    { time: '09:43', text: '正在校准景点坐标…' },
    { time: '09:43', text: '正在串起每一段路程…' },
    { time: '09:44', text: '正在挑选附近餐厅…' }
  ]
}
</script>

<style scoped>
.home-page {
  position: relative;
  padding: 26px 20px 64px;
  overflow: hidden;
  background: linear-gradient(180deg, #f4f6fc 0%, #f7f8fd 100%);
}

/* ============ 背景 ============ */

.bg-decor {
  position: absolute;
  inset: 0;
  pointer-events: none;
  overflow: hidden;
}

.blob {
  position: absolute;
  border-radius: 50%;
  filter: blur(64px);
  opacity: 0.3;
}

.blob-1 {
  width: 420px;
  height: 420px;
  top: 40px;
  left: -160px;
  background: radial-gradient(circle at 30% 30%, #a99bff, #6d5efc);
}

.blob-2 {
  width: 360px;
  height: 360px;
  top: 420px;
  right: -180px;
  background: radial-gradient(circle at 40% 40%, #ffc79a, #ff8a3d);
  opacity: 0.26;
}

.blob-3 {
  width: 320px;
  height: 320px;
  bottom: -140px;
  left: 30%;
  background: radial-gradient(circle at 50% 50%, #9ff3e5, #14c8b1);
  opacity: 0.22;
}

.star {
  position: absolute;
  color: #fff;
  text-shadow: 0 0 14px rgba(255, 255, 255, 0.9), 0 0 24px rgba(109, 94, 252, 0.8);
  animation: twinkle 4s ease-in-out infinite;
  z-index: 2;
}

.star-1 { top: 96px; left: 8%; font-size: 18px; }
.star-2 { top: 200px; right: 9%; font-size: 22px; animation-delay: 1.2s; }
.star-3 { top: 62px; right: 26%; font-size: 14px; animation-delay: 2.4s; }

@keyframes twinkle {
  0%, 100% { opacity: 0.25; transform: scale(0.85) rotate(0deg); }
  50% { opacity: 0.9; transform: scale(1.1) rotate(20deg); }
}

/* ============ 主视觉 ============ */

.hero {
  position: relative;
  z-index: 1;
  max-width: 1100px;
  margin: 0 auto 26px;
  padding: 40px 34px 30px;
  text-align: center;
  border-radius: 28px;
  overflow: hidden;
  background:
    radial-gradient(120% 150% at 8% 0%, rgba(255, 255, 255, 0.24) 0%, rgba(255, 255, 255, 0) 55%),
    linear-gradient(122deg, #3b2fa8 0%, #5b47d6 38%, #7b52e0 62%, #a8529e 82%, #d4643c 108%);
  box-shadow: 0 24px 60px rgba(59, 47, 168, 0.32);
  animation: riseIn 0.6s ease-out;
}

/* 面板内的柔光,替代此前溢出的光斑,保证文字对比度 */
.hero::after {
  content: '';
  position: absolute;
  inset: 0;
  pointer-events: none;
  background:
    radial-gradient(38% 60% at 88% 12%, rgba(255, 175, 110, 0.34) 0%, rgba(255, 175, 110, 0) 70%),
    radial-gradient(45% 70% at 4% 96%, rgba(20, 200, 177, 0.24) 0%, rgba(20, 200, 177, 0) 72%);
}

.hero > * {
  position: relative;
  z-index: 1;
}

.hero-badge {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 7px 18px;
  border-radius: 999px;
  font-size: 13px;
  font-weight: 600;
  letter-spacing: 1.4px;
  color: #4c3fd6;
  background: rgba(255, 255, 255, 0.94);
  box-shadow: 0 6px 20px rgba(20, 12, 60, 0.22);
}

.badge-spark {
  color: #ff8a3d;
  animation: twinkle 2.4s ease-in-out infinite;
}

.hero-title {
  font-size: clamp(28px, 4.4vw, 48px);
  font-weight: 800;
  color: #fff;
  margin: 18px 0 14px;
  letter-spacing: 1px;
  line-height: 1.25;
  text-shadow: 0 6px 26px rgba(49, 35, 120, 0.35);
}

.hero-title .hl {
  background: linear-gradient(100deg, #ffe9a8 0%, #ffc27a 50%, #ff9d5c 100%);
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
}

.hero-sub {
  font-size: 14.5px;
  line-height: 1.9;
  color: rgba(255, 255, 255, 0.93);
  max-width: 760px;
  margin: 0 auto 24px;
}

.hero-features {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(190px, 1fr));
  gap: 11px;
  text-align: left;
}

.feature {
  display: flex;
  align-items: center;
  gap: 11px;
  padding: 12px 14px;
  border-radius: 15px;
  background: rgba(255, 255, 255, 0.14);
  border: 1px solid rgba(255, 255, 255, 0.28);
  backdrop-filter: blur(8px);
  transition: transform 0.25s ease, background 0.25s ease;
}

.feature:hover {
  transform: translateY(-3px);
  background: rgba(255, 255, 255, 0.24);
}

.feature-icon {
  font-size: 22px;
}

.feature-title {
  font-size: 13.5px;
  font-weight: 700;
  color: #fff;
  text-shadow: 0 1px 6px rgba(20, 12, 60, 0.35);
}

.feature-desc {
  font-size: 11.5px;
  color: rgba(255, 255, 255, 0.86);
}

/* ============ 表单卡片 ============ */

.form-card {
  position: relative;
  z-index: 1;
  max-width: 1100px;
  margin: 0 auto;
  border-radius: 26px;
  box-shadow: 0 30px 70px rgba(49, 35, 120, 0.22);
  background: rgba(255, 255, 255, 0.97) !important;
  animation: riseIn 0.7s ease-out;
}

.form-section {
  margin-bottom: 26px;
  padding: 22px 24px 8px;
  border-radius: 18px;
  background: linear-gradient(150deg, #fafbff 0%, #ffffff 60%);
  border: 1px solid var(--xx-line);
  transition: box-shadow 0.3s ease, transform 0.3s ease;
}

.form-section:hover {
  box-shadow: 0 12px 30px rgba(109, 94, 252, 0.1);
  transform: translateY(-2px);
}

.section-head {
  display: flex;
  align-items: center;
  gap: 14px;
  margin-bottom: 18px;
  padding-bottom: 14px;
  border-bottom: 1px dashed #e6e4f7;
}

.section-index {
  font-size: 14px;
  font-weight: 800;
  color: #fff;
  background: linear-gradient(135deg, #6d5efc, #a06bf0);
  border-radius: 12px;
  padding: 7px 11px;
  letter-spacing: 1px;
  box-shadow: 0 6px 16px rgba(109, 94, 252, 0.3);
}

.section-title {
  font-size: 17px;
  font-weight: 700;
  color: var(--xx-ink);
}

.section-tip {
  font-size: 12.5px;
  color: var(--xx-muted);
  margin-top: 2px;
}

.form-label {
  font-size: 14px;
  font-weight: 600;
  color: #4a4f6b;
}

.label-count {
  font-style: normal;
  font-size: 11.5px;
  color: #8b7cf6;
  margin-left: 6px;
}

.label-help {
  display: inline-grid;
  place-items: center;
  width: 15px;
  height: 15px;
  margin-left: 5px;
  border-radius: 50%;
  font-size: 10px;
  color: #fff;
  background: #b9b2f0;
  cursor: help;
}

.prefix-emoji {
  color: #6d5efc;
}

/* ============ 输入控件 ============ */

.custom-input :deep(.ant-input),
.custom-input :deep(.ant-picker),
.custom-input :deep(.ant-input-number) {
  border-radius: 12px;
  border: 1.6px solid #e8e8f4;
  transition: all 0.25s ease;
}

.custom-input :deep(.ant-input:hover),
.custom-input :deep(.ant-picker:hover),
.custom-input :deep(.ant-input-number:hover) {
  border-color: #a99bff;
}

.custom-input :deep(.ant-input:focus),
.custom-input :deep(.ant-picker-focused),
.custom-input :deep(.ant-input-number-focused) {
  border-color: #6d5efc;
  box-shadow: 0 0 0 3.5px rgba(109, 94, 252, 0.12);
}

.custom-select :deep(.ant-select-selector) {
  border-radius: 12px !important;
  border: 1.6px solid #e8e8f4 !important;
  transition: all 0.25s ease;
}

.custom-select:hover :deep(.ant-select-selector) {
  border-color: #a99bff !important;
}

.custom-select :deep(.ant-select-focused .ant-select-selector) {
  border-color: #6d5efc !important;
  box-shadow: 0 0 0 3.5px rgba(109, 94, 252, 0.12) !important;
}

.custom-textarea :deep(.ant-input) {
  border-radius: 12px;
  border: 1.6px solid #e8e8f4;
  transition: all 0.25s ease;
}

.custom-textarea :deep(.ant-input:hover) {
  border-color: #a99bff;
}

.custom-textarea :deep(.ant-input:focus) {
  border-color: #6d5efc;
  box-shadow: 0 0 0 3.5px rgba(109, 94, 252, 0.12);
}

/* ============ 天数 ============ */

.days-pill {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 40px;
  border-radius: 12px;
  background: linear-gradient(135deg, #6d5efc 0%, #8b5cf6 100%);
  color: #fff;
  box-shadow: 0 6px 16px rgba(109, 94, 252, 0.28);
}

.days-value {
  font-size: 22px;
  font-weight: 800;
  margin-right: 3px;
}

.days-unit {
  font-size: 13px;
  opacity: 0.9;
}

/* ============ 人数快捷 ============ */

.quick-people {
  display: flex;
  gap: 6px;
  margin-top: 8px;
}

.mini-chip {
  border: 1px solid #e8e8f4;
  background: #fff;
  color: #6b7280;
  border-radius: 999px;
  font-size: 11.5px;
  padding: 3px 10px;
  cursor: pointer;
  transition: all 0.2s ease;
}

.mini-chip:hover {
  border-color: #a99bff;
  color: #5b4ae0;
}

.mini-chip.active {
  background: linear-gradient(135deg, #6d5efc, #8b5cf6);
  border-color: transparent;
  color: #fff;
}

/* ============ 交通方式卡片 ============ */

.transport-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
  gap: 10px;
}

.transport-card {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 11px 13px;
  border-radius: 14px;
  border: 1.6px solid #e8e8f4;
  background: #fff;
  cursor: pointer;
  transition: all 0.22s ease;
  user-select: none;
}

.transport-card input {
  display: none;
}

.transport-card:hover {
  border-color: #b9b2f0;
  transform: translateY(-2px);
}

.transport-card.active {
  border-color: #6d5efc;
  background: linear-gradient(140deg, #f3f1ff 0%, #ffffff 100%);
  box-shadow: 0 8px 20px rgba(109, 94, 252, 0.16);
}

.transport-card.active .transport-name {
  color: #4c3fd6;
}

.transport-icon {
  font-size: 20px;
}

.transport-text {
  display: flex;
  flex-direction: column;
  line-height: 1.35;
}

.transport-name {
  font-size: 13.5px;
  font-weight: 600;
  color: #3f4463;
}

.transport-desc {
  font-size: 11px;
  color: #9aa0b8;
}

/* ============ 偏好卡片 ============ */

.pref-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(108px, 1fr));
  gap: 9px;
}

.pref-card {
  display: flex;
  align-items: center;
  gap: 7px;
  padding: 10px 12px;
  border-radius: 12px;
  border: 1.6px solid #e8e8f4;
  background: #fff;
  color: #4a4f6b;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.22s ease;
}

.pref-card:hover {
  border-color: #b9b2f0;
  transform: translateY(-2px);
}

.pref-card.active {
  border-color: transparent;
  background: linear-gradient(135deg, #6d5efc, #8b5cf6);
  color: #fff;
  box-shadow: 0 8px 20px rgba(109, 94, 252, 0.28);
}

.pref-icon {
  font-size: 15px;
}

/* ============ 提交 ============ */

.submit-item {
  margin-bottom: 4px;
}

.submit-button {
  height: 56px;
  border-radius: 999px;
  font-size: 17px;
  font-weight: 700;
  letter-spacing: 1px;
  border: none;
  background: linear-gradient(120deg, #6d5efc 0%, #8b5cf6 52%, #ff8a3d 140%);
  box-shadow: 0 12px 30px rgba(109, 94, 252, 0.4);
  transition: transform 0.25s ease, box-shadow 0.25s ease;
}

.submit-button:hover {
  transform: translateY(-2px);
  box-shadow: 0 16px 38px rgba(109, 94, 252, 0.48);
}

.button-icon {
  margin-right: 8px;
}

.submit-hint {
  display: flex;
  justify-content: center;
  gap: 18px;
  flex-wrap: wrap;
  margin-top: 12px;
  font-size: 12px;
  color: #98a0b8;
}

/* ============ 进度面板 ============ */

.progress-panel {
  padding: 20px 22px;
  border-radius: 18px;
  background: linear-gradient(150deg, #f6f5ff 0%, #ffffff 65%);
  border: 1.6px solid #e4e0ff;
  box-shadow: inset 0 1px 0 #fff;
}

.progress-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
}

.progress-status {
  display: flex;
  align-items: center;
  gap: 9px;
  font-size: 14.5px;
  font-weight: 600;
  color: #4c3fd6;
}

.pulse-dot {
  width: 9px;
  height: 9px;
  border-radius: 50%;
  background: #14c8b1;
  box-shadow: 0 0 0 0 rgba(20, 200, 177, 0.6);
  animation: pulseDot 1.6s infinite;
}

.progress-percent {
  font-size: 22px;
  font-weight: 800;
  color: #6d5efc;
  font-variant-numeric: tabular-nums;
}

.progress-bar :deep(.ant-progress-inner) {
  background: #eceafd;
  border-radius: 999px;
}

.progress-bar :deep(.ant-progress-bg) {
  border-radius: 999px;
  transition: width 0.25s linear;
}

/* 步骤轨道 */
.step-track {
  display: flex;
  gap: 6px;
  margin: 14px 0 12px;
  overflow-x: auto;
  padding-bottom: 4px;
}

.step-track::-webkit-scrollbar {
  height: 0;
}

.step {
  display: flex;
  align-items: center;
  gap: 5px;
  padding: 5px 11px;
  border-radius: 999px;
  background: #f1f0fb;
  color: #9aa0b8;
  font-size: 11.5px;
  white-space: nowrap;
  transition: all 0.25s ease;
}

.step.active {
  background: linear-gradient(135deg, #6d5efc, #a06bf0);
  color: #fff;
  box-shadow: 0 6px 16px rgba(109, 94, 252, 0.32);
}

.step.done {
  background: #e2fbf5;
  color: #0f9c88;
}

.step-dot {
  font-size: 10px;
  font-weight: 700;
}

.progress-meta {
  display: flex;
  gap: 16px;
  flex-wrap: wrap;
  font-size: 12px;
  color: #8b90a8;
  margin-bottom: 12px;
}

.progress-log {
  max-height: 190px;
  overflow-y: auto;
  padding: 10px 12px;
  border-radius: 12px;
  background: #1f2138;
  font-size: 12px;
  line-height: 1.9;
  scroll-behavior: smooth;
}

.log-line {
  display: flex;
  gap: 10px;
}

.log-time {
  color: #6f7ba8;
  font-variant-numeric: tabular-nums;
}

.log-text {
  color: #d9dcf0;
}

.progress-note {
  margin-top: 12px;
  font-size: 11.5px;
  color: #98a0b8;
  text-align: center;
}

/* ============ 动画 ============ */

@keyframes riseIn {
  from {
    opacity: 0;
    transform: translateY(24px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

@keyframes pulseDot {
  0% { box-shadow: 0 0 0 0 rgba(20, 200, 177, 0.6); }
  70% { box-shadow: 0 0 0 10px rgba(20, 200, 177, 0); }
  100% { box-shadow: 0 0 0 0 rgba(20, 200, 177, 0); }
}

@media (max-width: 768px) {
  .home-page {
    padding: 28px 12px 60px;
  }
  .form-section {
    padding: 18px 16px 6px;
  }
  .submit-hint {
    gap: 10px;
  }
}
</style>
