<template>
  <a-drawer
    v-model:open="visible"
    placement="right"
    :width="drawerWidth"
    :closable="false"
    :body-style="{ padding: 0, background: '#f7f8fd' }"
    :mask-transition-name="props.instant ? '' : undefined"
    :transition-name="props.instant ? '' : undefined"
    class="agent-drawer"
  >
    <div class="agent-shell">
      <!-- 头部 -->
      <div class="agent-header">
        <div class="agent-identity">
          <div class="agent-avatar">
            <span class="avatar-face">🤖</span>
            <span class="avatar-online"></span>
          </div>
          <div class="agent-meta">
            <div class="agent-name">
              小星小探员
              <span class="agent-badge">AI</span>
            </div>
            <div class="agent-desc">小星探行 · 你的专属行程管家</div>
          </div>
        </div>
        <a-button type="text" class="close-btn" @click="visible = false">✕</a-button>
      </div>

      <!-- 上下文状态 -->
      <div class="agent-context">
        <template v-if="plan">
          <span class="ctx-chip">📍 {{ plan.city }}</span>
          <span class="ctx-chip">{{ plan.start_date }} → {{ plan.end_date }}</span>
          <span class="ctx-chip">👥 {{ contextTravelers }} 人</span>
          <span class="ctx-chip">🛣️ {{ contextTransports.join(' / ') || '按推荐' }}</span>
        </template>
        <template v-else>
          <span class="ctx-chip muted">还没有生成攻略，先问我出行建议也可以～</span>
        </template>
      </div>

      <!-- 对话区 -->
      <div ref="scrollRef" class="agent-body">
        <div v-if="messages.length === 0" class="welcome">
          <div class="welcome-emoji">✨</div>
          <div class="welcome-title">我是小星小探员</div>
          <p class="welcome-text">
            我可以帮你<strong>直接修改行程</strong>、调整出行人数与交通偏好，
            也能根据这份攻略回答细节问题。试试下面的问题：
          </p>
          <div class="welcome-chips">
            <button
              v-for="chip in welcomeChips"
              :key="chip"
              type="button"
              class="chip"
              @click="send(chip)"
            >
              {{ chip }}
            </button>
          </div>
        </div>

        <div
          v-for="(msg, index) in messages"
          :key="index"
          class="msg-row"
          :class="msg.role === 'user' ? 'is-user' : 'is-agent'"
        >
          <div v-if="msg.role === 'assistant'" class="msg-avatar">🤖</div>
          <div class="msg-main">
            <div class="bubble" :class="msg.role === 'user' ? 'bubble-user' : 'bubble-agent'">
              <div class="bubble-text">{{ msg.content }}</div>
              <div v-if="msg.time" class="bubble-time">{{ msg.time }}</div>
            </div>
            <div v-if="msg.suggestions && msg.suggestions.length" class="suggestions">
              <button
                v-for="s in msg.suggestions"
                :key="s"
                type="button"
                class="chip chip-sm"
                @click="send(s)"
              >
                {{ s }}
              </button>
            </div>
          </div>
        </div>

        <div v-if="loading" class="msg-row is-agent">
          <div class="msg-avatar">🤖</div>
          <div class="msg-main">
            <div class="bubble bubble-agent typing">
              <span class="dot"></span><span class="dot"></span><span class="dot"></span>
              <span class="typing-text">{{ typingText }}</span>
            </div>
          </div>
        </div>
      </div>

      <!-- 快捷操作 -->
      <div v-if="plan" class="agent-quick">
        <button
          v-for="act in quickActions"
          :key="act.label"
          type="button"
          class="chip chip-quick"
          :disabled="loading"
          @click="send(act.prompt)"
        >
          {{ act.label }}
        </button>
      </div>

      <!-- 输入区 -->
      <div class="agent-footer">
        <a-textarea
          v-model:value="draft"
          :rows="2"
          :maxlength="500"
          placeholder="例如:把第2天改成轻松一点 / 我们 4 个人,多用打车 / 第1天晚饭附近有什么必吃?"
          class="agent-input"
          @press-enter="onEnter"
        />
        <div class="footer-actions">
          <span class="footer-hint">Enter 发送 · Shift+Enter 换行</span>
          <a-button
            type="primary"
            class="send-btn"
            :loading="loading"
            :disabled="!draft.trim()"
            @click="send()"
          >
            发送 🚀
          </a-button>
        </div>
      </div>
    </div>
  </a-drawer>
</template>

<script setup lang="ts">
import { ref, computed, watch, nextTick, onMounted, onUnmounted } from 'vue'
import { message } from 'ant-design-vue'
import { chatWithAgent } from '@/services/api'
import type { ChatMessage, TripPlan } from '@/types'

const props = defineProps<{
  open: boolean
  plan: TripPlan | null
  /** 调试用:跳过抽屉滑入动画,便于自动化截图 */
  instant?: boolean
}>()

const emit = defineEmits<{
  (e: 'update:open', value: boolean): void
  (e: 'plan-updated', plan: TripPlan): void
}>()

const visible = computed({
  get: () => props.open,
  set: (value: boolean) => emit('update:open', value)
})

const drawerWidth = ref(window.innerWidth < 560 ? '100%' : 440)
const onResize = () => {
  drawerWidth.value = window.innerWidth < 560 ? '100%' : 440
}
onMounted(() => window.addEventListener('resize', onResize))
onUnmounted(() => window.removeEventListener('resize', onResize))

const messages = ref<ChatMessage[]>([])
const draft = ref('')
const loading = ref(false)
const typingText = ref('正在思考…')
const scrollRef = ref<HTMLElement | null>(null)

/** 助手修改行程时可调整的参数(默认取用户上次填写的表单) */
const contextTravelers = ref(2)
const contextTransports = ref<string[]>([])

const readFormContext = () => {
  const raw = sessionStorage.getItem('tripForm')
  if (!raw) return
  try {
    const form = JSON.parse(raw)
    if (typeof form.travelers === 'number' && form.travelers > 0) {
      contextTravelers.value = form.travelers
    }
    if (Array.isArray(form.transport_preferences) && form.transport_preferences.length) {
      contextTransports.value = form.transport_preferences
    }
  } catch {
    /* 表单缓存损坏时忽略 */
  }
}

watch(
  () => [props.plan, props.open] as const,
  () => {
    if (props.open) readFormContext()
  },
  { immediate: true }
)

const welcomeChips = [
  '帮我看看这份行程安排合理吗？',
  '整体节奏太赶了，帮我放松一点',
  '第1天晚上附近有什么必吃的？',
  '我们 4 个人出行，请重新计算费用'
]

const quickActions = [
  { label: '🎯 放慢节奏', prompt: '整体节奏太赶了，帮我每天减少一个景点，留出更多休息时间' },
  { label: '🚕 改打车为主', prompt: '把交通方式改成以打车为主，并重新计算通勤时间' },
  { label: '🍜 加美食安排', prompt: '帮我多安排一些当地特色美食，并说明每家的招牌菜' },
  { label: '🏨 换酒店', prompt: '帮我换成离当天最后一个景点更近、评分更高的酒店' },
  { label: '👥 改人数', prompt: '我们一共 4 个人出行，请按 4 人重新计算酒店房间和费用' }
]

const nowTime = () => {
  const d = new Date()
  return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
}

const scrollToBottom = async () => {
  await nextTick()
  const el = scrollRef.value
  if (el) el.scrollTop = el.scrollHeight
}

const onEnter = (e: KeyboardEvent) => {
  if (!e.shiftKey) {
    e.preventDefault()
    send()
  }
}

const send = async (text?: string) => {
  const content = (text ?? draft.value).trim()
  if (!content || loading.value) return

  messages.value.push({ role: 'user', content, time: nowTime() })
  draft.value = ''
  loading.value = true
  typingText.value = props.plan ? '正在核对攻略…' : '正在准备建议…'
  scrollToBottom()

  const history = messages.value
    .filter((m) => m.role === 'user' || m.role === 'assistant')
    .slice(0, -1)
    .slice(-8)
    .map((m) => ({ role: m.role, content: m.content }))

  try {
    const res = await chatWithAgent({
      message: content,
      plan: props.plan ?? null,
      history,
      travelers: contextTravelers.value,
      transport_preferences: contextTransports.value
    })

    messages.value.push({
      role: 'assistant',
      content: res.reply || '我在的，请再说一次～',
      suggestions: res.suggestions ?? [],
      time: nowTime()
    })

    if (res.plan) {
      emit('plan-updated', res.plan)
      emit('update:open', true)
      message.success('行程已按你的要求更新 ✨')
    }
  } catch (err: any) {
    messages.value.push({
      role: 'assistant',
      content: err?.message || '小星小探员开小差了，请稍后再试～',
      time: nowTime()
    })
  } finally {
    loading.value = false
    scrollToBottom()
  }
}

defineExpose({ send })
</script>

<style scoped>
.agent-shell {
  display: flex;
  flex-direction: column;
  height: 100vh;
  background: #f7f8fd;
}

/* ============ 头部 ============ */

.agent-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 16px;
  background: linear-gradient(120deg, #5b4ae0 0%, #7c5cf5 55%, #a06bf0 100%);
  color: #fff;
}

.agent-identity {
  display: flex;
  align-items: center;
  gap: 12px;
}

.agent-avatar {
  position: relative;
  width: 44px;
  height: 44px;
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.2);
  border: 1px solid rgba(255, 255, 255, 0.4);
  display: grid;
  place-items: center;
  font-size: 22px;
}

.avatar-online {
  position: absolute;
  right: -2px;
  bottom: -2px;
  width: 12px;
  height: 12px;
  border-radius: 50%;
  background: #46f0c8;
  border: 2px solid #6d5efc;
}

.agent-name {
  font-size: 16px;
  font-weight: 700;
  display: flex;
  align-items: center;
  gap: 6px;
  letter-spacing: 1px;
}

.agent-badge {
  font-size: 10px;
  padding: 1px 6px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.25);
  letter-spacing: 0.5px;
}

.agent-desc {
  font-size: 11.5px;
  color: rgba(255, 255, 255, 0.85);
  margin-top: 2px;
}

.close-btn {
  color: #fff !important;
  font-size: 16px;
}

/* ============ 上下文 ============ */

.agent-context {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  padding: 10px 14px;
  background: #fff;
  border-bottom: 1px solid #ecedf6;
}

.ctx-chip {
  font-size: 11.5px;
  color: #5b54a8;
  background: #f0eeff;
  border-radius: 999px;
  padding: 2px 10px;
}

.ctx-chip.muted {
  color: #8a90a8;
  background: #f3f4f9;
}

/* ============ 对话区 ============ */

.agent-body {
  flex: 1;
  overflow-y: auto;
  padding: 16px 14px 8px;
}

.welcome {
  text-align: center;
  padding: 18px 10px 6px;
}

.welcome-emoji {
  font-size: 32px;
  animation: floatY 3s ease-in-out infinite;
}

.welcome-title {
  font-size: 16px;
  font-weight: 700;
  margin: 6px 0 8px;
  color: #3d3670;
}

.welcome-text {
  font-size: 13px;
  color: #6b7280;
  line-height: 1.7;
  margin: 0 auto 14px;
  max-width: 320px;
}

.welcome-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  justify-content: center;
}

.chip {
  border: 1px solid #e2e0f5;
  background: #fff;
  color: #5b54a8;
  font-size: 12px;
  border-radius: 999px;
  padding: 7px 13px;
  cursor: pointer;
  transition: all 0.2s ease;
  text-align: left;
}

.chip:hover {
  border-color: #6d5efc;
  background: #f5f3ff;
  color: #4c3fd6;
  transform: translateY(-1px);
}

.msg-row {
  display: flex;
  gap: 8px;
  margin-bottom: 14px;
  align-items: flex-start;
}

.msg-row.is-user {
  flex-direction: row-reverse;
}

.msg-avatar {
  width: 30px;
  height: 30px;
  flex-shrink: 0;
  border-radius: 10px;
  background: #efecff;
  display: grid;
  place-items: center;
  font-size: 16px;
}

.msg-main {
  max-width: 82%;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.is-user .msg-main {
  align-items: flex-end;
}

.bubble {
  position: relative;
  padding: 10px 13px;
  border-radius: 14px;
  font-size: 13.5px;
  line-height: 1.68;
  box-shadow: 0 2px 10px rgba(76, 63, 214, 0.06);
}

.bubble-agent {
  background: #fff;
  color: #2c3050;
  border-top-left-radius: 4px;
}

.bubble-user {
  background: linear-gradient(135deg, #6d5efc 0%, #8b5cf6 100%);
  color: #fff;
  border-top-right-radius: 4px;
}

.bubble-text {
  white-space: pre-wrap;
  word-break: break-word;
}

.bubble-time {
  font-size: 10px;
  opacity: 0.55;
  margin-top: 5px;
  text-align: right;
}

.suggestions {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.chip-sm {
  font-size: 11.5px;
  padding: 5px 11px;
}

.typing {
  display: flex;
  align-items: center;
  gap: 5px;
}

.typing-text {
  font-size: 12px;
  color: #8a90a8;
  margin-left: 4px;
}

.dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #b9b4e8;
  animation: blink 1.3s infinite ease-in-out;
}

.dot:nth-child(2) {
  animation-delay: 0.18s;
}

.dot:nth-child(3) {
  animation-delay: 0.36s;
}

/* ============ 快捷操作 ============ */

.agent-quick {
  display: flex;
  gap: 7px;
  padding: 8px 14px;
  overflow-x: auto;
  background: #fbfbff;
  border-top: 1px solid #ecedf6;
}

.agent-quick::-webkit-scrollbar {
  height: 0;
}

.chip-quick {
  white-space: nowrap;
  background: #fff;
}

.chip-quick:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* ============ 输入区 ============ */

.agent-footer {
  padding: 12px 14px 16px;
  background: #fff;
  border-top: 1px solid #ecedf6;
}

.agent-input :deep(textarea) {
  border-radius: 12px !important;
  resize: none;
  font-size: 13px;
}

.footer-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 10px;
}

.footer-hint {
  font-size: 11px;
  color: #a2a7bd;
}

.send-btn {
  border-radius: 999px;
  font-weight: 600;
  height: 36px;
  padding: 0 20px;
}

@keyframes blink {
  0%, 80%, 100% { opacity: 0.3; }
  40% { opacity: 1; }
}

@keyframes floatY {
  0%, 100% { transform: translateY(0); }
  50% { transform: translateY(-7px); }
}
</style>

<style>
.agent-drawer .ant-drawer-body {
  padding: 0 !important;
  overflow: hidden;
}
</style>
