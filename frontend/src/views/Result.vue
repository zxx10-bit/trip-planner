<template>
  <div class="result-page">
    <!-- 顶部操作栏 -->
    <div class="page-header">
      <a-button class="back-button" size="large" @click="goBack">← 返回首页</a-button>

      <div class="header-plan" v-if="tripPlan">
        <span class="plan-city">🧭 {{ tripPlan.city }}</span>
        <span class="plan-dates">{{ tripPlan.start_date }} → {{ tripPlan.end_date }}</span>
        <span class="plan-days">{{ tripPlan.days.length }} 天完整攻略</span>
      </div>

      <a-space size="middle" :wrap="true">
        <a-button v-if="!editMode" @click="toggleEditMode">✏️ 编辑行程</a-button>
        <template v-else>
          <a-button @click="saveChanges" type="primary">💾 保存修改</a-button>
          <a-button @click="cancelEdit">❌ 取消编辑</a-button>
        </template>

        <a-dropdown v-if="!editMode">
          <template #overlay>
            <a-menu>
              <a-menu-item key="image" @click="exportAsImage">📷 导出为图片</a-menu-item>
              <a-menu-item key="pdf" @click="exportAsPDF">📄 导出为PDF</a-menu-item>
            </a-menu>
          </template>
          <a-button>
            📥 导出攻略 <DownOutlined />
          </a-button>
        </a-dropdown>
      </a-space>
    </div>

    <div v-if="tripPlan" class="content-wrapper">
      <!-- 侧边导航 -->
      <aside class="side-nav">
        <a-affix :offset-top="88">
          <div class="nav-card">
            <div class="nav-title">攻略目录</div>
            <a-menu mode="inline" :selected-keys="[activeSection]" @click="scrollToSection">
              <a-menu-item key="overview"><span>📋 行程概览</span></a-menu-item>
              <a-menu-item key="budget" v-if="tripPlan.budget"><span>💰 预算明细</span></a-menu-item>
              <a-menu-item key="map"><span>📍 景点地图</span></a-menu-item>
              <a-sub-menu key="days" title="🛰️ 每日时刻表">
                <a-menu-item v-for="(day, index) in tripPlan.days" :key="`day-${index}`">
                  第{{ day.day_index + 1 }}天 · {{ day.start_time || '—' }}起
                </a-menu-item>
              </a-sub-menu>
              <a-menu-item
                key="weather"
                v-if="tripPlan.weather_info && tripPlan.weather_info.length"
              >
                <span>🌤️ 天气提示</span>
              </a-menu-item>
            </a-menu>
            <button type="button" class="nav-assistant" @click="openAssistant">
              <span class="nav-assistant-icon">🤖</span>
              让小星小探员帮我改
            </button>
          </div>
        </a-affix>
      </aside>

      <!-- 主内容 -->
      <main class="main-content">
        <!-- 概览 + 地图 -->
        <div class="top-info-section">
          <div class="left-info">
            <a-card id="overview" :bordered="false" class="overview-card">
              <template #title>
                <span class="card-title">📋 行程概览</span>
              </template>
              <div class="stat-strip">
                <div class="stat">
                  <div class="stat-value">{{ tripPlan.days.length }}</div>
                  <div class="stat-label">旅行天数</div>
                </div>
                <div class="stat">
                  <div class="stat-value">{{ travelers }}</div>
                  <div class="stat-label">出行人数</div>
                </div>
                <div class="stat">
                  <div class="stat-value">{{ totalAttractions }}</div>
                  <div class="stat-label">景点数量</div>
                </div>
                <div class="stat">
                  <div class="stat-value">{{ totalCommuteText }}</div>
                  <div class="stat-label">总通勤时长</div>
                </div>
              </div>

              <div class="overview-content">
                <div class="info-item">
                  <span class="info-label">📅 日期</span>
                  <span class="info-value">{{ tripPlan.start_date }} 至 {{ tripPlan.end_date }}</span>
                </div>
                <div class="info-item">
                  <span class="info-label">🛬 抵达时刻</span>
                  <span class="info-value">{{ arrivalTime }} 起排布时刻表</span>
                </div>
                <div class="info-item">
                  <span class="info-label">🚏 交通偏好</span>
                  <span class="info-value">{{ transportPrefsText }}</span>
                </div>
                <div class="info-item">
                  <span class="info-label">💡 出行建议</span>
                  <span class="info-value">{{ tripPlan.overall_suggestions }}</span>
                </div>
              </div>
            </a-card>

            <a-card v-if="tripPlan.budget" id="budget" :bordered="false" class="budget-card">
              <template #title>
                <span class="card-title">💰 预算明细</span>
                <span class="card-title-sub">按 {{ travelers }} 人预估</span>
              </template>
              <div class="budget-grid">
                <div class="budget-item">
                  <div class="budget-label">🎫 景点门票</div>
                  <div class="budget-value">¥{{ tripPlan.budget.total_attractions }}</div>
                </div>
                <div class="budget-item">
                  <div class="budget-label">🏨 酒店住宿</div>
                  <div class="budget-value">¥{{ tripPlan.budget.total_hotels }}</div>
                </div>
                <div class="budget-item">
                  <div class="budget-label">🍜 餐饮费用</div>
                  <div class="budget-value">¥{{ tripPlan.budget.total_meals }}</div>
                </div>
                <div class="budget-item">
                  <div class="budget-label">🚇 交通费用</div>
                  <div class="budget-value">¥{{ tripPlan.budget.total_transportation }}</div>
                </div>
              </div>
              <div class="budget-total">
                <span class="total-label">预估总费用</span>
                <span class="total-value">¥{{ tripPlan.budget.total }}</span>
              </div>
              <div class="budget-foot">人均约 ¥{{ perPersonCost }}</div>
            </a-card>
          </div>

          <div class="right-map">
            <a-card id="map" :bordered="false" class="map-card">
              <template #title><span class="card-title">📍 景点地图</span></template>
              <div id="amap-container" style="width: 100%; height: 100%"></div>
            </a-card>
          </div>
        </div>

        <!-- 每日时刻表 -->
        <a-card :bordered="false" class="days-card">
          <template #title>
            <span class="card-title">🛰️ 每日精细时刻表</span>
            <span class="card-title-sub">到达 / 离开 / 下一站 · 通勤自动计算</span>
          </template>

          <a-collapse v-model:activeKey="activeDays" accordion>
            <a-collapse-panel v-for="(day, index) in tripPlan.days" :key="index" :id="`day-${index}`">
              <template #header>
                <div class="day-header">
                  <div class="day-header-left">
                    <span class="day-chip">D{{ day.day_index + 1 }}</span>
                    <span class="day-title">{{ day.date }}</span>
                    <span class="day-time">
                      {{ day.start_time || '—' }}
                      <template v-if="day.end_time"> → {{ day.end_time }}</template>
                    </span>
                  </div>
                  <div class="day-header-right">
                    <span class="day-meta">📍 {{ day.attractions?.length || 0 }} 个景点</span>
                    <span class="day-meta">🚇 {{ dayCommute(day) }}</span>
                  </div>
                </div>
              </template>

              <div v-if="day.description" class="day-desc">📝 {{ day.description }}</div>

              <DayTimeline
                :day="day"
                :edit-mode="editMode"
                :travelers="travelers"
                :image-resolver="resolveAttractionImage"
                @move="(i, dir) => moveTimelineEntry(day, i, dir)"
                @remove="(i) => removeTimelineEntry(day, i)"
              />
            </a-collapse-panel>
          </a-collapse>
        </a-card>

        <!-- 天气 -->
        <a-card
          id="weather"
          v-if="tripPlan.weather_info && tripPlan.weather_info.length"
          :bordered="false"
          class="weather-section"
        >
          <template #title><span class="card-title">🌤️ 天气提示</span></template>
          <a-list :data-source="tripPlan.weather_info" :grid="{ gutter: 16, column: 3 }">
            <template #renderItem="{ item }">
              <a-list-item>
                <a-card size="small" class="weather-card" :bordered="false">
                  <div class="weather-date">{{ item.date }}</div>
                  <div class="weather-info-row">
                    <span class="weather-icon">☀️</span>
                    <div>
                      <div class="weather-label">白天</div>
                      <div class="weather-value">{{ item.day_weather }} {{ item.day_temp }}°C</div>
                    </div>
                  </div>
                  <div class="weather-info-row">
                    <span class="weather-icon">🌙</span>
                    <div>
                      <div class="weather-label">夜间</div>
                      <div class="weather-value">{{ item.night_weather }} {{ item.night_temp }}°C</div>
                    </div>
                  </div>
                  <div class="weather-wind">💨 {{ item.wind_direction }} {{ item.wind_power }}</div>
                </a-card>
              </a-list-item>
            </template>
          </a-list>
        </a-card>
      </main>
    </div>

    <a-empty v-else description="没有找到旅行计划数据">
      <template #image><div style="font-size: 80px">🗺️</div></template>
      <template #description>
        <span style="color: #999">暂无攻略数据,请先生成行程</span>
      </template>
      <a-button type="primary" @click="goBack">返回首页生成攻略</a-button>
    </a-empty>

    <a-back-top :visibility-height="300">
      <div class="back-top-button">↑</div>
    </a-back-top>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import { message } from 'ant-design-vue'
import { DownOutlined } from '@ant-design/icons-vue'
import AMapLoader from '@amap/amap-jsapi-loader'
import html2canvas from 'html2canvas'
import jsPDF from 'jspdf'
import DayTimeline from '@/components/DayTimeline.vue'
import { openAssistant as showAssistant } from '@/services/assistant'
import type { DayPlan, TripPlan, TimelineEntry } from '@/types'
import apiClient from '@/services/api'

const router = useRouter()
const tripPlan = ref<TripPlan | null>(null)
const editMode = ref(false)
const originalPlan = ref<TripPlan | null>(null)
const attractionPhotos = ref<Record<string, string>>({})
const activeSection = ref('overview')
const activeDays = ref<number[]>([0])
let map: any = null

/** 表单上下文(人数 / 交通偏好 / 抵达时刻),用于展示与助手对话 */
const formContext = ref<any>({})

onMounted(async () => {
  const data = sessionStorage.getItem('tripPlan')
  const form = sessionStorage.getItem('tripForm')
  if (form) {
    try {
      formContext.value = JSON.parse(form)
    } catch {
      formContext.value = {}
    }
  }
  if (data) {
    tripPlan.value = JSON.parse(data)
    await loadAttractionPhotos()
    await nextTick()
    initMap()
  }
  window.addEventListener('xx:trip-plan-updated', onPlanUpdatedByAgent)
})

onUnmounted(() => {
  window.removeEventListener('xx:trip-plan-updated', onPlanUpdatedByAgent)
})

/** 小星小探员改完行程后,实时刷新当前页面 */
const onPlanUpdatedByAgent = async (event: Event) => {
  const detail = (event as CustomEvent).detail as TripPlan | undefined
  const raw = detail ?? (sessionStorage.getItem('tripPlan') ? JSON.parse(sessionStorage.getItem('tripPlan')!) : null)
  if (!raw) return

  tripPlan.value = raw
  editMode.value = false
  originalPlan.value = null
  await loadAttractionPhotos()
  if (map) {
    map.destroy()
    map = null
  }
  await nextTick()
  initMap()
}

// ============ 统计 ============

const travelers = computed(() => {
  const fromPlan = tripPlan.value?.days?.[0]?.timeline?.find((e) => e.venue?.party_size)
    ?.venue?.party_size
  return formContext.value?.travelers || fromPlan || 2
})

const arrivalTime = computed(
  () =>
    formContext.value?.arrival_time ||
    tripPlan.value?.days?.[0]?.timeline?.find((e) => e.type === 'arrival')?.arrive_time ||
    tripPlan.value?.days?.[0]?.start_time ||
    '09:00'
)

const transportPrefsText = computed(() => {
  const prefs: string[] = formContext.value?.transport_preferences || []
  return prefs.length ? prefs.join(' / ') : '按最优方案推荐'
})

const totalAttractions = computed(
  () => tripPlan.value?.days.reduce((sum, day) => sum + (day.attractions?.length || 0), 0) ?? 0
)

const totalCommuteMinutes = computed(() => {
  let total = 0
  tripPlan.value?.days.forEach((day) => {
    day.timeline?.forEach((entry) => {
      total += entry.next_transport?.duration_min ?? 0
    })
  })
  return total
})

const totalCommuteText = computed(() => {
  const total = totalCommuteMinutes.value
  if (!total) return '—'
  const h = Math.floor(total / 60)
  const m = total % 60
  return h > 0 ? `${h}h${m}m` : `${m}m`
})

const perPersonCost = computed(() => {
  const total = tripPlan.value?.budget?.total ?? 0
  return travelers.value ? Math.round(total / travelers.value) : total
})

const dayCommute = (day: DayPlan) => {
  const total = (day.timeline ?? []).reduce(
    (sum, entry) => sum + (entry.next_transport?.duration_min ?? 0),
    0
  )
  return total ? `${total} 分钟` : '—'
}

// ============ 交互 ============

const goBack = () => router.push('/')

const openAssistant = () => {
  showAssistant()
}

const scrollToSection = ({ key }: { key: string }) => {
  activeSection.value = key
  const element = document.getElementById(key)
  if (element) element.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

const toggleEditMode = () => {
  editMode.value = true
  originalPlan.value = JSON.parse(JSON.stringify(tripPlan.value))
  message.info('进入编辑模式:保存后会自动重算时刻表')
}

const saveChanges = async () => {
  if (!tripPlan.value) return
  editMode.value = false
  sessionStorage.setItem('tripPlan', JSON.stringify(tripPlan.value))
  message.success('修改已保存')

  if (map) map.destroy()
  await nextTick()
  initMap()
}

const cancelEdit = () => {
  if (originalPlan.value) tripPlan.value = JSON.parse(JSON.stringify(originalPlan.value))
  editMode.value = false
  message.info('已取消编辑')
}

/** 时刻表条目上移 / 下移(同步调整当日景点顺序) */
const moveTimelineEntry = (day: DayPlan, index: number, direction: 'up' | 'down') => {
  const timeline = day.timeline ?? []
  const target = direction === 'up' ? index - 1 : index + 1
  if (target < 0 || target >= timeline.length) return
  if (timeline[index].type !== 'attraction' || timeline[target].type !== 'attraction') {
    message.info('只能调整相邻景点之间的顺序')
    return
  }

  const attractions = day.attractions ?? []
  const from = attractions.findIndex((a) => a.name === timeline[index].title)
  const to = attractions.findIndex((a) => a.name === timeline[target].title)
  if (from === -1 || to === -1) return

  ;[attractions[from], attractions[to]] = [attractions[to], attractions[from]]
  ;[timeline[index], timeline[target]] = [timeline[target], timeline[index]]
  timeline.forEach((entry, i) => (entry.seq = i))
}

const removeTimelineEntry = (day: DayPlan, index: number) => {
  const entry = (day.timeline ?? [])[index]
  if (!entry || entry.type !== 'attraction') return
  if ((day.attractions?.length ?? 0) <= 1) {
    message.warning('每天至少需要保留一个景点')
    return
  }
  day.timeline?.splice(index, 1)
  const attrIndex = (day.attractions ?? []).findIndex((a) => a.name === entry.title)
  if (attrIndex !== -1) day.attractions.splice(attrIndex, 1)
  message.success('已移除该景点,保存后自动重算时刻与通勤')
}

// ============ 图片 ============

const loadAttractionPhotos = async () => {
  if (!tripPlan.value) return
  const promises: Promise<void>[] = []

  tripPlan.value.days.forEach((day) => {
    day.attractions?.forEach((attraction) => {
      promises.push(
        apiClient
          .get('/api/poi/photo', {
            params: { name: attraction.name, city: tripPlan.value!.city }
          })
          .then((response) => {
            const data = response.data
            if (data.success && data.data.photo_url) {
              attractionPhotos.value[attraction.name] = data.data.photo_url
            }
          })
          .catch((err) => console.error(`获取${attraction.name}图片失败:`, err))
      )
    })
  })

  await Promise.all(promises)
}

const getAttractionImage = (name: string, index = 0): string => {
  if (attractionPhotos.value[name]) return attractionPhotos.value[name]

  const colors = [
    { start: '#6d5efc', end: '#a06bf0' },
    { start: '#ff9a62', end: '#ff6f91' },
    { start: '#4facfe', end: '#00f2fe' },
    { start: '#43e97b', end: '#38f9d7' },
    { start: '#fa709a', end: '#fee140' }
  ]
  const { start, end } = colors[index % colors.length]

  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="400" height="300">
    <defs><linearGradient id="grad${index}" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" style="stop-color:${start};stop-opacity:1" />
      <stop offset="100%" style="stop-color:${end};stop-opacity:1" />
    </linearGradient></defs>
    <rect width="400" height="300" fill="url(#grad${index})"/>
    <text x="50%" y="50%" dominant-baseline="middle" text-anchor="middle" font-family="sans-serif" font-size="24" font-weight="bold" fill="white">${name}</text>
  </svg>`

  return `data:image/svg+xml;base64,${btoa(unescape(encodeURIComponent(svg)))}`
}

/** 稳定的图片索引:按景点名在整份攻略中的出现顺序 */
const imageIndexCache = new Map<string, number>()
let imageIndexSeq = 0
const resolveAttractionImage = (name: string): string => {
  if (!imageIndexCache.has(name)) imageIndexCache.set(name, imageIndexSeq++)
  return getAttractionImage(name, imageIndexCache.get(name) ?? 0)
}

async function replaceImagesWithBase64(container: HTMLElement) {
  const imgs = container.querySelectorAll('img')
  const tasks: Promise<void>[] = []
  imgs.forEach((img) => {
    const src = img.getAttribute('src') || ''
    if (!src.startsWith('http')) return
    tasks.push(
      new Promise((resolve) => {
        fetch(`${apiClient.defaults.baseURL}/api/poi/image-proxy?url=${encodeURIComponent(src)}`)
          .then((r) => r.json())
          .then((d) => {
            if (d.success && d.url) {
              img.onload = () => resolve()
              img.src = d.url
            } else resolve()
          })
          .catch(() => resolve())
      })
    )
  })
  await Promise.all(tasks)
}

const buildExportContainer = async () => {
  const element = document.querySelector('.main-content') as HTMLElement
  if (!element) throw new Error('未找到内容元素')

  const exportContainer = document.createElement('div')
  exportContainer.style.width = element.offsetWidth + 'px'
  exportContainer.style.backgroundColor = '#f7f8fd'
  exportContainer.style.padding = '20px'
  exportContainer.innerHTML = element.innerHTML

  const mapContainer = document.getElementById('amap-container')
  if (mapContainer && map) {
    const mapCanvas = mapContainer.querySelector('canvas')
    if (mapCanvas) {
      const snapshot = mapCanvas.toDataURL('image/png')
      const exportMap = exportContainer.querySelector('#amap-container')
      if (exportMap) {
        exportMap.innerHTML = `<img src="${snapshot}" style="width:100%;height:100%;object-fit:cover;" />`
      }
    }
  }

  await replaceImagesWithBase64(exportContainer)
  return exportContainer
}

const exportAsImage = async () => {
  try {
    message.loading({ content: '正在生成图片...', key: 'export', duration: 0 })
    const exportContainer = await buildExportContainer()

    document.body.appendChild(exportContainer)
    const canvas = await html2canvas(exportContainer, {
      backgroundColor: '#f7f8fd',
      scale: 2,
      logging: false,
      useCORS: true,
      allowTaint: true
    })
    document.body.removeChild(exportContainer)

    const link = document.createElement('a')
    link.download = `小星探行_${tripPlan.value?.city}_${new Date().getTime()}.png`
    link.href = canvas.toDataURL('image/png')
    link.click()

    message.success({ content: '图片导出成功!', key: 'export' })
  } catch (error: any) {
    console.error('导出图片失败:', error)
    message.error({ content: `导出图片失败: ${error.message}`, key: 'export' })
  }
}

const exportAsPDF = async () => {
  try {
    message.loading({ content: '正在生成PDF...', key: 'export', duration: 0 })
    const exportContainer = await buildExportContainer()

    document.body.appendChild(exportContainer)
    const canvas = await html2canvas(exportContainer, {
      backgroundColor: '#f7f8fd',
      scale: 2,
      logging: false,
      useCORS: true,
      allowTaint: true
    })
    document.body.removeChild(exportContainer)

    const imgData = canvas.toDataURL('image/png')
    const pdf = new jsPDF({ orientation: 'portrait', unit: 'mm', format: 'a4' })

    const imgWidth = 210
    const imgHeight = (canvas.height * imgWidth) / canvas.width
    let heightLeft = imgHeight
    let position = 0

    pdf.addImage(imgData, 'PNG', 0, position, imgWidth, imgHeight)
    heightLeft -= 297

    while (heightLeft > 0) {
      position = heightLeft - imgHeight
      pdf.addPage()
      pdf.addImage(imgData, 'PNG', 0, position, imgWidth, imgHeight)
      heightLeft -= 297
    }

    pdf.save(`小星探行_${tripPlan.value?.city}_${new Date().getTime()}.pdf`)
    message.success({ content: 'PDF导出成功!', key: 'export' })
  } catch (error: any) {
    console.error('导出PDF失败:', error)
    message.error({ content: `导出PDF失败: ${error.message}`, key: 'export' })
  }
}

// ============ 地图 ============

const initMap = async () => {
  try {
    if (!import.meta.env.VITE_AMAP_WEB_JS_KEY) {
      console.warn('未配置 VITE_AMAP_WEB_JS_KEY,跳过地图渲染')
      return
    }
    const AMap = await AMapLoader.load({
      key: import.meta.env.VITE_AMAP_WEB_JS_KEY,
      version: '2.0',
      plugins: ['AMap.Marker', 'AMap.Polyline', 'AMap.InfoWindow']
    })

    map = new AMap.Map('amap-container', {
      zoom: 12,
      center: [116.397128, 39.916527],
      viewMode: '3D'
    })

    addAttractionMarkers(AMap)
  } catch (error) {
    console.error('地图加载失败:', error)
  }
}

const hasValidCoords = (loc?: { longitude?: number; latitude?: number }) => {
  if (!loc) return false
  const { longitude, latitude } = loc
  return (
    Number.isFinite(longitude) &&
    Number.isFinite(latitude) &&
    longitude !== 0 &&
    latitude !== 0 &&
    Math.abs(longitude!) <= 180 &&
    Math.abs(latitude!) <= 90
  )
}

const addAttractionMarkers = (AMap: any) => {
  if (!tripPlan.value) return

  const markers: any[] = []
  const allAttractions: any[] = []

  tripPlan.value.days.forEach((day, dayIndex) => {
    day.attractions?.forEach((attraction, attrIndex) => {
      // 坐标缺失或非法的景点不参与地图渲染,避免高德抛 NaN 异常
      if (hasValidCoords(attraction.location)) {
        allAttractions.push({ ...attraction, dayIndex, attrIndex })
      }
    })
  })

  allAttractions.forEach((attraction, index) => {
    const marker = new AMap.Marker({
      position: [attraction.location.longitude, attraction.location.latitude],
      title: attraction.name,
      label: {
        content: `<div style="background: linear-gradient(135deg,#6d5efc,#a06bf0); color:#fff; padding:3px 8px; border-radius:8px; font-size:12px; font-weight:600;">${index + 1}</div>`,
        offset: new AMap.Pixel(0, -30)
      }
    })

    const timeEntry = tripPlan.value?.days[attraction.dayIndex]?.timeline?.find(
      (e: TimelineEntry) => e.type === 'attraction' && e.title === attraction.name
    )

    const infoWindow = new AMap.InfoWindow({
      content: `
        <div style="padding: 10px; max-width: 260px;">
          <h4 style="margin: 0 0 8px 0;">${attraction.name}</h4>
          ${timeEntry ? `<p style="margin:4px 0;color:#4c3fd6;"><strong>${timeEntry.arrive_time} - ${timeEntry.leave_time}</strong></p>` : ''}
          <p style="margin: 4px 0;"><strong>地址:</strong> ${attraction.address || '—'}</p>
          <p style="margin: 4px 0;"><strong>游览:</strong> ${attraction.visit_duration} 分钟</p>
          <p style="margin: 4px 0; color: #6d5efc;"><strong>第${attraction.dayIndex + 1}天 第${attraction.attrIndex + 1}站</strong></p>
        </div>`,
      offset: new AMap.Pixel(0, -30)
    })

    marker.on('click', () => infoWindow.open(map, marker.getPosition()))
    markers.push(marker)
  })

  if (markers.length) {
    map.add(markers)
    try {
      map.setFitView(markers)
    } catch (err) {
      console.warn('地图视野自适应失败:', err)
    }
  }
  drawRoutes(AMap, allAttractions)
}

const drawRoutes = (AMap: any, attractions: any[]) => {
  if (attractions.length < 2) return

  const dayGroups: Record<number, any[]> = {}
  attractions.forEach((attr) => {
    if (!dayGroups[attr.dayIndex]) dayGroups[attr.dayIndex] = []
    dayGroups[attr.dayIndex].push(attr)
  })

  const palette = ['#6d5efc', '#ff8a3d', '#14c8b1', '#4facfe', '#f5576c']

  Object.entries(dayGroups).forEach(([dayIndex, dayAttractions]) => {
    if (dayAttractions.length < 2) return
    const path = dayAttractions.map((attr: any) => [
      attr.location.longitude,
      attr.location.latitude
    ])

    map.add(
      new AMap.Polyline({
        path,
        strokeColor: palette[Number(dayIndex) % palette.length],
        strokeWeight: 5,
        strokeOpacity: 0.85,
        strokeStyle: 'solid',
        showDir: true
      })
    )
  })
}
</script>

<style scoped>
.result-page {
  padding: 26px 20px 70px;
  max-width: 1520px;
  margin: 0 auto;
}

/* ============ 顶部 ============ */

.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;
  margin-bottom: 22px;
  padding: 14px 18px;
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.86);
  border: 1px solid #eae7fb;
  box-shadow: 0 10px 26px rgba(76, 63, 214, 0.08);
  backdrop-filter: blur(8px);
  animation: fadeInDown 0.5s ease-out;
}

.back-button {
  border-radius: 999px;
  font-weight: 500;
}

.header-plan {
  display: flex;
  align-items: center;
  gap: 14px;
  flex-wrap: wrap;
  font-size: 13.5px;
  color: #6b7280;
}

.plan-city {
  font-size: 16px;
  font-weight: 800;
  color: #3f3a76;
  letter-spacing: 1px;
}

.plan-days {
  padding: 3px 12px;
  border-radius: 999px;
  background: linear-gradient(135deg, #6d5efc, #a06bf0);
  color: #fff;
  font-size: 12px;
  font-weight: 600;
}

/* ============ 布局 ============ */

.content-wrapper {
  display: flex;
  gap: 22px;
  align-items: flex-start;
}

.side-nav {
  width: 236px;
  flex-shrink: 0;
}

.nav-card {
  border-radius: 18px;
  background: #fff;
  box-shadow: 0 10px 26px rgba(76, 63, 214, 0.09);
  border: 1px solid #eef0f8;
  overflow: hidden;
  padding-bottom: 12px;
}

.nav-title {
  padding: 14px 18px 10px;
  font-size: 13px;
  font-weight: 700;
  color: #3f3a76;
  letter-spacing: 1px;
  border-bottom: 1px solid #f1f2f8;
  margin-bottom: 6px;
}

.side-nav :deep(.ant-menu) {
  border-inline-end: none !important;
  background: transparent;
}

.side-nav :deep(.ant-menu-item),
.side-nav :deep(.ant-menu-submenu-title) {
  margin: 3px 8px !important;
  border-radius: 10px;
  width: auto;
  font-size: 13px;
}

.side-nav :deep(.ant-menu-item-selected) {
  background: linear-gradient(135deg, #6d5efc 0%, #8b5cf6 100%) !important;
  color: #fff !important;
}

.side-nav :deep(.ant-menu-item:hover) {
  background: rgba(109, 94, 252, 0.09) !important;
}

.nav-assistant {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 7px;
  width: calc(100% - 24px);
  margin: 12px 12px 0;
  padding: 10px;
  border: none;
  border-radius: 12px;
  cursor: pointer;
  font-size: 13px;
  font-weight: 600;
  color: #fff;
  background: linear-gradient(135deg, #6d5efc, #a06bf0);
  box-shadow: 0 8px 20px rgba(109, 94, 252, 0.3);
  transition: transform 0.22s ease;
}

.nav-assistant:hover {
  transform: translateY(-2px);
}

.main-content {
  flex: 1;
  min-width: 0;
}

/* ============ 顶部信息区 ============ */

.top-info-section {
  display: flex;
  gap: 20px;
  margin-bottom: 20px;
  align-items: stretch;
}

.left-info {
  flex: 0 0 400px;
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.right-map {
  flex: 1;
  min-width: 0;
}

.card-title {
  font-weight: 700;
  letter-spacing: 0.6px;
}

.card-title-sub {
  margin-left: 10px;
  font-size: 11.5px;
  font-weight: 400;
  color: rgba(255, 255, 255, 0.85);
}

/* ============ 概览 ============ */

.stat-strip {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 10px;
  margin-bottom: 16px;
}

.stat {
  text-align: center;
  padding: 12px 6px;
  border-radius: 12px;
  background: linear-gradient(150deg, #f5f3ff 0%, #ffffff 100%);
  border: 1px solid #ece8ff;
}

.stat-value {
  font-size: 19px;
  font-weight: 800;
  color: #4c3fd6;
  font-variant-numeric: tabular-nums;
  letter-spacing: 0.3px;
}

.stat-label {
  font-size: 11px;
  color: #8b90a8;
  margin-top: 2px;
}

.overview-content {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.info-item {
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.info-label {
  font-size: 12.5px;
  font-weight: 700;
  color: #6b7280;
}

.info-value {
  font-size: 13.5px;
  color: #2f3350;
  line-height: 1.7;
}

/* ============ 预算 ============ */

.budget-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
  margin-bottom: 14px;
}

.budget-item {
  text-align: center;
  padding: 12px 8px;
  border-radius: 14px;
  background: linear-gradient(150deg, #f7f8ff 0%, #ffffff 100%);
  border: 1px solid #eef0fa;
}

.budget-label {
  font-size: 12px;
  color: #7b8199;
  margin-bottom: 6px;
}

.budget-value {
  font-size: 18px;
  font-weight: 800;
  color: #6d5efc;
  font-variant-numeric: tabular-nums;
}

.budget-total {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 15px 18px;
  border-radius: 14px;
  background: linear-gradient(120deg, #6d5efc 0%, #8b5cf6 55%, #ff8a3d 145%);
  color: #fff;
  box-shadow: 0 10px 24px rgba(109, 94, 252, 0.32);
}

.total-label {
  font-size: 14.5px;
  font-weight: 600;
}

.total-value {
  font-size: 26px;
  font-weight: 800;
  font-variant-numeric: tabular-nums;
}

.budget-foot {
  margin-top: 10px;
  text-align: center;
  font-size: 12px;
  color: #98a0b8;
}

/* ============ 地图 ============ */

.map-card {
  height: 100%;
  min-height: 520px;
  display: flex;
  flex-direction: column;
}

.map-card :deep(.ant-card-body) {
  flex: 1;
  padding: 0;
  min-height: 460px;
}

/* ============ 每日 ============ */

.days-card {
  margin-bottom: 20px;
}

.day-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  width: 100%;
  flex-wrap: wrap;
}

.day-header-left {
  display: flex;
  align-items: center;
  gap: 10px;
}

.day-chip {
  font-size: 12px;
  font-weight: 800;
  color: #fff;
  background: linear-gradient(135deg, #6d5efc, #a06bf0);
  border-radius: 8px;
  padding: 3px 9px;
}

.day-title {
  font-size: 15.5px;
  font-weight: 700;
  color: #2f3350;
}

.day-time {
  font-size: 12.5px;
  color: #6d5efc;
  font-weight: 600;
  font-variant-numeric: tabular-nums;
}

.day-header-right {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}

.day-meta {
  font-size: 12px;
  color: #8b90a8;
}

.day-desc {
  font-size: 13px;
  color: #5c6280;
  line-height: 1.8;
  padding: 12px 14px;
  margin-bottom: 16px;
  border-radius: 12px;
  background: #fafbff;
  border-left: 3px solid #6d5efc;
}

/* ============ 天气 ============ */

.weather-section {
  margin-top: 20px;
}

.weather-card {
  border-radius: 14px !important;
  background: linear-gradient(140deg, #e8fbf7 0%, #d7f5ff 100%);
  border: none !important;
  transition: transform 0.25s ease, box-shadow 0.25s ease;
}

.weather-card:hover {
  transform: translateY(-4px);
  box-shadow: 0 12px 24px rgba(20, 200, 177, 0.2);
}

.weather-date {
  font-size: 14.5px;
  font-weight: 700;
  color: #0f7d6c;
  margin-bottom: 10px;
  text-align: center;
}

.weather-info-row {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 7px;
}

.weather-icon {
  font-size: 20px;
}

.weather-label {
  font-size: 11px;
  color: #5c8f86;
}

.weather-value {
  font-size: 14.5px;
  font-weight: 700;
  color: #0f7d6c;
}

.weather-wind {
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px solid rgba(15, 125, 108, 0.16);
  text-align: center;
  color: #0f7d6c;
  font-size: 12.5px;
}

/* ============ 回到顶部 ============ */

.back-top-button {
  width: 48px;
  height: 48px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 22px;
  font-weight: 700;
  color: #fff;
  background: linear-gradient(135deg, #6d5efc, #a06bf0);
  box-shadow: 0 10px 24px rgba(109, 94, 252, 0.4);
  cursor: pointer;
  transition: transform 0.25s ease;
}

.back-top-button:hover {
  transform: scale(1.08);
}

/* ============ 卡片统一风格 ============ */

:deep(.ant-card) {
  border-radius: 18px;
  box-shadow: 0 10px 26px rgba(76, 63, 214, 0.08);
  border: 1px solid #eef0f8;
  transition: box-shadow 0.25s ease;
}

:deep(.ant-card-head) {
  background: linear-gradient(120deg, #6d5efc 0%, #8b5cf6 60%, #a06bf0 100%);
  border-radius: 18px 18px 0 0;
  border-bottom: none;
  min-height: 50px;
}

:deep(.ant-card-head-title) {
  color: #fff !important;
  font-size: 15.5px;
}

:deep(.ant-collapse) {
  border: none;
  background: transparent;
}

:deep(.ant-collapse-item) {
  margin-bottom: 14px;
  border: 1px solid #eef0f8;
  border-radius: 16px;
  overflow: hidden;
  box-shadow: 0 6px 16px rgba(76, 63, 214, 0.05);
}

:deep(.ant-collapse-header) {
  background: linear-gradient(120deg, #f7f6ff 0%, #ffffff 70%);
  padding: 14px 18px !important;
  align-items: center !important;
}

:deep(.ant-collapse-content) {
  border-top: 1px solid #f1f2f8;
}

:deep(.ant-collapse-content-box) {
  padding: 18px;
}

@keyframes fadeInDown {
  from {
    opacity: 0;
    transform: translateY(-16px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

/* ============ 响应式 ============ */

@media (max-width: 1200px) {
  .top-info-section {
    flex-direction: column;
  }
  .left-info {
    flex: none;
  }
  .map-card {
    min-height: 420px;
  }
  .map-card :deep(.ant-card-body) {
    min-height: 360px;
  }
  .content-wrapper {
    flex-direction: column;
  }
  .side-nav {
    width: 100%;
  }
}

@media (max-width: 768px) {
  .result-page {
    padding: 18px 10px 60px;
  }
  .budget-grid {
    grid-template-columns: 1fr;
  }
}
</style>
