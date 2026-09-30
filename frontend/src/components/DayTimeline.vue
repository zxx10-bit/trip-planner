<template>
  <div class="day-timeline">
    <!-- 当日概览 -->
    <div class="day-summary">
      <div class="summary-item">
        <span class="summary-icon">🕘</span>
        <span class="summary-label">开始</span>
        <span class="summary-value">{{ day.start_time || firstTime }}</span>
      </div>
      <div class="summary-item">
        <span class="summary-icon">🌙</span>
        <span class="summary-label">结束</span>
        <span class="summary-value">{{ day.end_time || '—' }}</span>
      </div>
      <div class="summary-item">
        <span class="summary-icon">📍</span>
        <span class="summary-label">站点</span>
        <span class="summary-value">{{ attractionCount }} 个景点</span>
      </div>
      <div class="summary-item">
        <span class="summary-icon">🚇</span>
        <span class="summary-label">通勤</span>
        <span class="summary-value">{{ totalCommute }}</span>
      </div>
    </div>

    <!-- 没有时刻表时的兜底:展示原始景点安排 -->
    <div v-if="!entries.length" class="no-timeline">
      <a-alert
        type="info"
        show-icon
        message="这一天还没有生成时刻表"
        description="小星小探员可以帮你重新编排这一天的行程。"
      />
      <div v-if="(day.attractions || []).length" class="fallback-attractions">
        <div class="block-title">
          <span class="block-icon">📸</span> 当日计划景点
        </div>
        <a-card
          v-for="(attraction, index) in day.attractions"
          :key="attraction.name"
          size="small"
          class="rest-card"
          :bordered="false"
        >
          <div class="rest-name">
            <span>{{ index + 1 }}. {{ attraction.name }}</span>
            <span v-if="attraction.rating" class="rest-rating">⭐ {{ attraction.rating }}</span>
          </div>
          <div class="chip-row">
            <span v-if="attraction.category" class="pill">{{ attraction.category }}</span>
            <span v-if="attraction.visit_duration" class="pill">
              建议游览 {{ attraction.visit_duration }} 分钟
            </span>
            <span class="pill pill-price">{{ ticketText(attraction.ticket_price) }}</span>
          </div>
          <p v-if="attraction.address" class="tl-address">📍 {{ attraction.address }}</p>
          <p v-if="attraction.description" class="desc">{{ attraction.description }}</p>
        </a-card>
      </div>
    </div>

    <!-- 时刻表 -->
    <div v-else class="timeline">
      <div
        v-for="(entry, index) in entries"
        :key="index"
        class="tl-row"
        :class="[`tl-${entry.type}`, { last: index === entries.length - 1 }]"
      >
        <!-- 左侧时刻 -->
        <div class="tl-time">
          <div class="time-arrive">{{ entry.arrive_time || '—' }}</div>
          <div v-if="entry.leave_time && entry.leave_time !== entry.arrive_time" class="time-leave">
            离开 {{ entry.leave_time }}
          </div>
        </div>

        <!-- 中轴线 -->
        <div class="tl-rail">
          <span class="tl-node">{{ nodeIcon(entry) }}</span>
          <span class="tl-line"></span>
        </div>

        <!-- 右侧内容 -->
        <div class="tl-body">
          <div class="tl-card">
            <div class="tl-card-head">
              <div class="tl-title-wrap">
                <span class="tl-kind">{{ typeLabel(entry) }}</span>
                <span class="tl-title">{{ entry.title }}</span>
              </div>
              <div class="tl-head-right">
                <a-tag v-if="entry.duration_min" class="dur-tag">
                  ⏱ {{ entry.duration_min }} 分钟
                </a-tag>
                <template v-if="editMode && entry.type === 'attraction' && entry.attraction">
                  <a-button size="small" @click="$emit('move', index, 'up')">↑</a-button>
                  <a-button size="small" @click="$emit('move', index, 'down')">↓</a-button>
                  <a-button size="small" danger @click="$emit('remove', index)">🗑</a-button>
                </template>
              </div>
            </div>

            <div v-if="entry.address" class="tl-address">📍 {{ entry.address }}</div>
            <div v-if="entry.notes" class="tl-notes">{{ entry.notes }}</div>

            <!-- 景点信息 -->
            <div v-if="entry.attraction" class="venue-block attraction-block">
              <div class="attraction-body">
                <img
                  class="attraction-thumb"
                  :src="imageOf(entry.title)"
                  :alt="entry.title"
                  @error="onImageError"
                />
                <div class="attraction-info">
                  <div class="chip-row">
                    <span v-if="entry.attraction.rating" class="pill pill-star">
                      ⭐ {{ entry.attraction.rating }}
                    </span>
                    <span v-if="entry.attraction.category" class="pill">
                      {{ entry.attraction.category }}
                    </span>
                    <span class="pill pill-price">
                      {{ ticketText(entry.attraction.ticket_price) }}
                    </span>
                  </div>
                  <p v-if="entry.attraction.description" class="desc">
                    {{ entry.attraction.description }}
                  </p>
                </div>
              </div>
            </div>

            <!-- 餐厅信息 -->
            <div v-if="entry.venue && entry.venue.kind === 'restaurant'" class="venue-block">
              <div class="chip-row">
                <span v-if="entry.venue.rating" class="pill pill-star">
                  ⭐ {{ entry.venue.rating }}
                </span>
                <span v-if="entry.venue.cost" class="pill">
                  人均 ¥{{ Math.round(entry.venue.cost) }}
                </span>
                <span v-if="entry.venue.distance" class="pill">{{ entry.venue.distance }}</span>
                <span v-if="entry.venue.tel" class="pill">☎ {{ entry.venue.tel }}</span>
              </div>
              <p v-if="entry.venue.description" class="desc">{{ entry.venue.description }}</p>
              <div v-if="entry.venue.menu.length" class="menu-row">
                <span class="menu-label">🍽 特色菜品</span>
                <span v-for="dish in entry.venue.menu" :key="dish" class="dish">{{ dish }}</span>
              </div>
            </div>

            <!-- 酒店信息 -->
            <div v-if="entry.venue && entry.venue.kind === 'hotel'" class="venue-block">
              <div class="chip-row">
                <span v-if="entry.venue.rating" class="pill pill-star">
                  ⭐ {{ entry.venue.rating }}
                </span>
                <span v-if="entry.venue.cost" class="pill">
                  ¥{{ Math.round(entry.venue.cost) }}/晚
                </span>
                <span v-for="tag in entry.venue.tags.slice(0, 2)" :key="tag" class="pill">
                  {{ tag }}
                </span>
              </div>
              <p v-if="entry.venue.description" class="desc">{{ entry.venue.description }}</p>
            </div>
          </div>

          <!-- 前往下一站的通勤 -->
          <div v-if="entry.next_transport" class="leg">
            <div class="leg-line"></div>
            <div class="leg-card">
              <div class="leg-head">
                <span class="leg-mode" :class="`mode-${entry.next_transport.mode}`">
                  {{ modeIcon(entry.next_transport.mode) }}
                  {{ entry.next_transport.label }}
                </span>
                <span class="leg-facts">
                  <strong>{{ entry.next_transport.duration_min }}</strong> 分钟
                  <em v-if="entry.next_transport.distance_m">
                    · {{ distanceText(entry.next_transport.distance_m) }}
                  </em>
                  <em v-if="entry.next_transport.cost"> · 约 ¥{{ entry.next_transport.cost }}</em>
                </span>
              </div>
              <div class="leg-summary">
                {{ entry.next_transport.summary }}
              </div>
              <div v-if="entry.next_transport.reason" class="leg-reason">
                💡 {{ entry.next_transport.reason }}
              </div>
              <div v-if="entry.next_transport.detail_lines.length" class="leg-detail">
                <span v-for="(line, i) in entry.next_transport.detail_lines" :key="i" class="leg-detail-item">
                  {{ line }}
                </span>
              </div>
              <div v-if="entry.next_title" class="leg-next">
                下一站 → <strong>{{ entry.next_title }}</strong>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 餐厅推荐 -->
    <div v-if="restaurants.length" class="restaurants">
      <div class="block-title">
        <span class="block-icon">🍜</span> 周边高分餐厅推荐
        <span class="block-sub">按评分与距离排序，已结合 {{ partySizeHint }}</span>
      </div>
      <div class="rest-grid">
        <div v-for="group in restaurants" :key="group.meal_type" class="rest-group">
          <div class="rest-group-head">
            <span class="meal-badge">{{ group.meal_type === 'lunch' ? '午餐' : '晚餐' }}</span>
            <span class="rest-near">邻近 {{ group.near || '当日景点' }}</span>
          </div>
          <a-card
            v-for="venue in group.venues"
            :key="venue.name"
            size="small"
            class="rest-card"
            :bordered="false"
          >
            <div class="rest-name">
              {{ venue.name }}
              <span v-if="venue.rating" class="rest-rating">⭐ {{ venue.rating }}</span>
            </div>
            <div class="chip-row">
              <span v-if="venue.cost" class="pill">人均 ¥{{ Math.round(venue.cost) }}</span>
              <span v-if="venue.distance" class="pill">{{ venue.distance }}</span>
              <span v-for="tag in venue.tags.slice(0, 2)" :key="tag" class="pill">{{ tag }}</span>
            </div>
            <p v-if="venue.description" class="desc">{{ venue.description }}</p>
            <div v-if="venue.menu.length" class="menu-row">
              <span class="menu-label">🍽 招牌</span>
              <span v-for="dish in venue.menu" :key="dish" class="dish">{{ dish }}</span>
            </div>
          </a-card>
        </div>
      </div>
    </div>

    <!-- 其他餐饮安排 -->
    <div v-if="otherMeals.length" class="other-meals">
      <div class="block-title">
        <span class="block-icon">🥢</span> 其他餐饮安排
      </div>
      <div class="meal-list">
        <div v-for="meal in otherMeals" :key="meal.type" class="meal-item">
          <span class="meal-type">{{ mealLabel(meal.type) }}</span>
          <span class="meal-name">{{ meal.name }}</span>
          <span v-if="meal.description" class="meal-desc">{{ meal.description }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { DayPlan, Meal, TimelineEntry } from '@/types'

const props = defineProps<{
  day: DayPlan
  editMode?: boolean
  travelers?: number
  /** 由父组件提供的景点图片解析函数 */
  imageResolver?: (name: string) => string
}>()

defineEmits<{
  (e: 'move', index: number, direction: 'up' | 'down'): void
  (e: 'remove', index: number): void
}>()

const entries = computed<TimelineEntry[]>(() => props.day.timeline ?? [])

const firstTime = computed(() => entries.value[0]?.arrive_time || '—')

const attractionCount = computed(
  () => props.day.attractions?.length ?? entries.value.filter((e) => e.type === 'attraction').length
)

const formatMinutes = (total: number) => {
  const h = Math.floor(total / 60)
  const m = total % 60
  if (h > 0 && m > 0) return `${h}小时${m}分`
  if (h > 0) return `${h}小时`
  return `${m}分钟`
}

const totalCommute = computed(() => {
  const total = entries.value.reduce(
    (sum, entry) => sum + (entry.next_transport?.duration_min ?? 0),
    0
  )
  return total ? formatMinutes(total) : '—'
})

const restaurants = computed(() => props.day.restaurants ?? [])

const partySizeHint = computed(() =>
  props.travelers ? `${props.travelers} 人出行` : '你的出行人数'
)

/** 已经被时刻表吸收的餐次不再重复展示 */
const otherMeals = computed(() => {
  const used = new Set(
    entries.value.filter((e) => e.type === 'meal' && e.meal_type).map((e) => e.meal_type)
  )
  return (props.day.meals ?? []).filter((meal: Meal) => {
    if (meal.type === 'lunch' || meal.type === 'dinner') return !used.has(meal.type)
    return true
  })
})

const modeIcon = (mode: string) => {
  const icons: Record<string, string> = {
    walking: '🚶',
    bus: '🚌',
    subway: '🚇',
    taxi: '🚕',
    cycling: '🚲',
    driving: '🚗'
  }
  return icons[mode] ?? '🚏'
}

const nodeIcon = (entry: TimelineEntry) => {
  if (entry.type === 'arrival') return '🛬'
  if (entry.type === 'attraction') return '📸'
  if (entry.type === 'meal') return '🍽'
  if (entry.type === 'hotel') return '🏨'
  if (entry.type === 'rest') return '☕'
  return '•'
}

const typeLabel = (entry: TimelineEntry) => {
  if (entry.type === 'arrival') return '抵达'
  if (entry.type === 'attraction') return '景点'
  if (entry.type === 'meal') return entry.meal_type === 'dinner' ? '晚餐' : '午餐'
  if (entry.type === 'hotel') return '住宿'
  if (entry.type === 'rest') return '休息'
  return '行程'
}

const mealLabel = (type: string) => {
  const labels: Record<string, string> = {
    breakfast: '早餐',
    lunch: '午餐',
    dinner: '晚餐',
    snack: '小吃'
  }
  return labels[type] || type
}

const ticketText = (price?: number) => {
  if (!price) return '免费 / 暂无票价'
  return `门票 ¥${price}`
}

/** 景点缩略图:优先使用父组件已加载的真实图片 */
const gradientCache: Record<string, string> = {}
const imageOf = (name: string): string => {
  if (props.imageResolver) return props.imageResolver(name)
  if (gradientCache[name]) return gradientCache[name]

  const palettes = [
    ['#6d5efc', '#a06bf0'],
    ['#ff9a62', '#ff6f91'],
    ['#4facfe', '#00f2fe'],
    ['#43e97b', '#38f9d7'],
    ['#fa709a', '#fee140']
  ]
  const [start, end] = palettes[Object.keys(gradientCache).length % palettes.length]
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="200" height="200"><defs><linearGradient id="g" x1="0%" y1="0%" x2="100%" y2="100%"><stop offset="0%" stop-color="${start}"/><stop offset="100%" stop-color="${end}"/></linearGradient></defs><rect width="200" height="200" fill="url(#g)"/></svg>`
  const url = `data:image/svg+xml;base64,${btoa(unescape(encodeURIComponent(svg)))}`
  gradientCache[name] = url
  return url
}

const onImageError = (event: Event) => {
  const img = event.target as HTMLImageElement
  img.src =
    'data:image/svg+xml,%3Csvg xmlns="http://www.w3.org/2000/svg" width="200" height="200"%3E%3Crect width="200" height="200" fill="%23efeffa"/%3E%3C/svg%3E'
}

const distanceText = (metres: number) => {
  if (!metres) return ''
  return metres >= 1000 ? `${(metres / 1000).toFixed(1)} 公里` : `${Math.round(metres)} 米`
}
</script>

<style scoped>
.day-timeline {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

/* ============ 当日概览 ============ */

.day-summary {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
  gap: 10px;
  padding: 14px 16px;
  border-radius: 16px;
  background: linear-gradient(135deg, #f3f1ff 0%, #fdfbff 100%);
  border: 1px solid #e6e2ff;
}

.summary-item {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
}

.summary-icon {
  font-size: 16px;
}

.summary-label {
  color: #8b90a8;
}

.summary-value {
  font-weight: 700;
  color: #4c3fd6;
}

/* ============ 时刻表 ============ */

.timeline {
  position: relative;
  display: flex;
  flex-direction: column;
}

.tl-row {
  display: grid;
  grid-template-columns: 88px 32px 1fr;
  gap: 0;
  align-items: stretch;
}

.tl-time {
  padding-top: 16px;
  text-align: right;
  padding-right: 10px;
}

.time-arrive {
  font-size: 16px;
  font-weight: 800;
  color: #3f3a76;
  font-variant-numeric: tabular-nums;
  letter-spacing: 0.5px;
}

.time-leave {
  font-size: 11px;
  color: #9aa0b8;
  margin-top: 2px;
  font-variant-numeric: tabular-nums;
}

.tl-rail {
  position: relative;
  display: flex;
  flex-direction: column;
  align-items: center;
}

.tl-node {
  width: 32px;
  height: 32px;
  margin-top: 12px;
  border-radius: 50%;
  display: grid;
  place-items: center;
  font-size: 15px;
  background: #fff;
  border: 2px solid #ded9ff;
  box-shadow: 0 4px 12px rgba(109, 94, 252, 0.16);
  z-index: 1;
}

.tl-attraction .tl-node {
  border-color: #6d5efc;
  background: linear-gradient(135deg, #6d5efc, #8b5cf6);
}

.tl-arrival .tl-node {
  border-color: #14c8b1;
  background: linear-gradient(135deg, #14c8b1, #4fd1c5);
}

.tl-meal .tl-node {
  border-color: #ff8a3d;
  background: linear-gradient(135deg, #ffb066, #ff8a3d);
}

.tl-hotel .tl-node {
  border-color: #2f80ed;
  background: linear-gradient(135deg, #56a8ff, #2f80ed);
}

.tl-line {
  flex: 1;
  width: 2px;
  background: linear-gradient(180deg, #e2deff 0%, #eeebff 100%);
}

.tl-row.last .tl-line {
  background: transparent;
}

.tl-body {
  padding: 12px 0 6px 14px;
  min-width: 0;
}

.tl-card {
  padding: 14px 16px;
  border-radius: 16px;
  background: #fff;
  border: 1px solid #edeaf9;
  box-shadow: 0 6px 18px rgba(76, 63, 214, 0.07);
  transition: box-shadow 0.25s ease, transform 0.25s ease;
}

.tl-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 12px 26px rgba(76, 63, 214, 0.12);
}

.tl-card-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 10px;
}

.tl-title-wrap {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  min-width: 0;
}

.tl-kind {
  font-size: 11px;
  font-weight: 700;
  padding: 2px 8px;
  border-radius: 999px;
  background: #f0eeff;
  color: #5b4ae0;
  flex-shrink: 0;
}

.tl-arrival .tl-kind {
  background: #e2fbf5;
  color: #0f9c88;
}

.tl-meal .tl-kind {
  background: #fff1e5;
  color: #d9711f;
}

.tl-hotel .tl-kind {
  background: #e8f2ff;
  color: #2166c0;
}

.tl-title {
  font-size: 15.5px;
  font-weight: 700;
  color: #262a45;
}

.tl-head-right {
  display: flex;
  align-items: center;
  gap: 5px;
  flex-shrink: 0;
}

.dur-tag {
  margin: 0;
  border-radius: 999px;
  background: #f5f4ff;
  border-color: #e4e0ff;
  color: #6b5ce0;
  font-size: 11.5px;
}

.tl-address {
  font-size: 12.5px;
  color: #7b8199;
  margin-top: 7px;
}

.tl-notes {
  font-size: 12.5px;
  color: #6b7280;
  margin-top: 6px;
  padding: 8px 10px;
  border-radius: 10px;
  background: #f8f8fd;
  line-height: 1.7;
}

.venue-block {
  margin-top: 10px;
  padding-top: 10px;
  border-top: 1px dashed #eeecf9;
}

.chip-row {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.pill {
  font-size: 11.5px;
  padding: 2px 9px;
  border-radius: 999px;
  background: #f4f5fb;
  color: #626a86;
}

.pill-star {
  background: #fff6e0;
  color: #b57b12;
  font-weight: 700;
}

.pill-price {
  background: #ffeef0;
  color: #d3455b;
  font-weight: 600;
}

.desc {
  font-size: 12.5px;
  line-height: 1.75;
  color: #5c6280;
  margin: 8px 0 0;
}

.menu-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
  margin-top: 9px;
}

/* ============ 景点缩略图 ============ */

.attraction-body {
  display: flex;
  gap: 12px;
  align-items: flex-start;
}

.attraction-thumb {
  width: 96px;
  height: 72px;
  object-fit: cover;
  border-radius: 10px;
  flex-shrink: 0;
  background: #f1f1fa;
  box-shadow: 0 4px 12px rgba(76, 63, 214, 0.12);
}

.attraction-info {
  flex: 1;
  min-width: 0;
}

@media (max-width: 640px) {
  .attraction-thumb {
    width: 72px;
    height: 58px;
  }
}

.menu-label {
  font-size: 11.5px;
  font-weight: 700;
  color: #d9711f;
}

.dish {
  font-size: 11.5px;
  padding: 3px 10px;
  border-radius: 999px;
  background: linear-gradient(135deg, #fff3e8, #ffe9d6);
  color: #b85c11;
  border: 1px solid #ffe0c4;
}

/* ============ 通勤段落 ============ */

.leg {
  position: relative;
  padding-left: 2px;
}

.leg-line {
  width: 2px;
  height: 14px;
  margin-left: 14px;
  background: repeating-linear-gradient(
    180deg,
    #cfc8f7 0,
    #cfc8f7 4px,
    transparent 4px,
    transparent 8px
  );
}

.leg-card {
  padding: 11px 14px;
  border-radius: 14px;
  background: linear-gradient(135deg, #f7f6ff 0%, #ffffff 100%);
  border: 1px dashed #ddd7ff;
}

.leg-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  flex-wrap: wrap;
}

.leg-mode {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 12.5px;
  font-weight: 700;
  padding: 3px 11px;
  border-radius: 999px;
  background: #ece9ff;
  color: #5449c7;
}

.mode-walking { background: #e6f8f1; color: #12856c; }
.mode-subway { background: #e8f2ff; color: #2166c0; }
.mode-bus { background: #eaf7e9; color: #2c7a34; }
.mode-taxi { background: #fff3e0; color: #c47a11; }
.mode-cycling { background: #eefaf3; color: #13795b; }
.mode-driving { background: #f0eefc; color: #5b4ae0; }

.leg-facts {
  font-size: 12px;
  color: #6b7280;
}

.leg-facts strong {
  color: #4c3fd6;
  font-size: 13.5px;
}

.leg-facts em {
  font-style: normal;
  color: #8b90a8;
}

.leg-summary {
  font-size: 12.5px;
  color: #3f4463;
  font-weight: 600;
  margin-top: 7px;
}

.leg-reason {
  font-size: 12px;
  color: #7b8199;
  margin-top: 5px;
  line-height: 1.7;
}

.leg-detail {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 7px;
}

.leg-detail-item {
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 6px;
  background: #fff;
  border: 1px solid #e9e6fb;
  color: #62639a;
}

.leg-next {
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px dashed #e6e2fb;
  font-size: 12px;
  color: #8b90a8;
}

.leg-next strong {
  color: #4c3fd6;
}

/* ============ 餐厅推荐 ============ */

.block-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 15px;
  font-weight: 700;
  color: #2f3350;
  margin-bottom: 12px;
}

/* ============ 无时刻表时的兜底 ============ */

.no-timeline {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.fallback-attractions {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: 12px;
}

.block-icon {
  font-size: 17px;
}

.block-sub {
  font-size: 11.5px;
  font-weight: 400;
  color: #9aa0b8;
}

.rest-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: 14px;
}

.rest-group-head {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 9px;
}

.meal-badge {
  font-size: 12px;
  font-weight: 700;
  color: #fff;
  background: linear-gradient(135deg, #ffb066, #ff8a3d);
  border-radius: 999px;
  padding: 3px 12px;
}

.rest-near {
  font-size: 11.5px;
  color: #8b90a8;
}

.rest-card {
  border-radius: 14px !important;
  margin-bottom: 10px;
  background: linear-gradient(140deg, #fffdf9 0%, #ffffff 60%);
  border: 1px solid #f3ece2 !important;
  transition: transform 0.22s ease, box-shadow 0.22s ease;
}

.rest-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 10px 22px rgba(255, 138, 61, 0.14);
}

.rest-name {
  font-size: 14px;
  font-weight: 700;
  color: #2f3350;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 7px;
}

.rest-rating {
  font-size: 12px;
  color: #b57b12;
  font-weight: 700;
}

/* ============ 其他餐饮 ============ */

.other-meals {
  padding: 14px 16px;
  border-radius: 16px;
  background: #fbfbff;
  border: 1px solid #eef0f8;
}

.meal-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.meal-item {
  display: flex;
  align-items: baseline;
  gap: 10px;
  font-size: 13px;
  flex-wrap: wrap;
}

.meal-type {
  font-size: 11.5px;
  padding: 2px 9px;
  border-radius: 999px;
  background: #f0eeff;
  color: #5b4ae0;
  flex-shrink: 0;
}

.meal-name {
  font-weight: 600;
  color: #3f4463;
}

.meal-desc {
  font-size: 12px;
  color: #8b90a8;
}

@media (max-width: 640px) {
  .tl-row {
    grid-template-columns: 64px 26px 1fr;
  }
  .time-arrive {
    font-size: 14px;
  }
  .tl-body {
    padding-left: 8px;
  }
}
</style>
