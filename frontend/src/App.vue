<template>
  <div id="app">
    <a-layout class="app-layout">
      <!-- 顶部品牌栏 -->
      <a-layout-header class="app-header">
        <div class="header-inner">
          <div class="brand" @click="goHome">
            <span class="brand-mark">
              <span class="mark-spark">✦</span>
              <span class="mark-compass">🧭</span>
            </span>
            <span class="brand-text">
              <span class="brand-name">小星探行</span>
              <span class="brand-slogan">小星探行，快乐出行</span>
            </span>
          </div>

          <div class="header-right">
            <a-tag class="header-tag">🛰️ 精细时刻表</a-tag>
            <a-tag class="header-tag">🚇 智能通勤</a-tag>
            <a-tag class="header-tag">🍜 高分餐厅</a-tag>
            <a-button type="text" class="assistant-entry" @click="showAssistant">
              <span class="entry-dot"></span>
              召唤小星小探员
            </a-button>
          </div>
        </div>
      </a-layout-header>

      <a-layout-content class="app-content">
        <router-view />
      </a-layout-content>

      <a-layout-footer class="app-footer">
        <span class="footer-brand">小星探行</span>
        <span class="footer-slogan">小星探行，快乐出行</span>
        <span class="footer-meta">基于 HelloAgents 框架 · 高德地图 · AI 智能规划</span>
      </a-layout-footer>
    </a-layout>

    <!-- 右侧悬浮按钮：唤起 AI 助手 -->
    <button class="fab-assistant" type="button" @click="showAssistant">
      <span class="fab-ring"></span>
      <span class="fab-icon">🤖</span>
      <span class="fab-label">小星小探员</span>
    </button>

    <!-- AI 助手侧边栏 -->
    <AgentSidebar
      v-model:open="assistantOpen"
      :plan="currentPlan"
      :instant="instantDrawer"
      @plan-updated="onPlanUpdated"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import AgentSidebar from '@/components/AgentSidebar.vue'
import { assistantOpen, openAssistant } from '@/services/assistant'
import type { TripPlan } from '@/types'

const route = useRoute()
const router = useRouter()

/** 当前攻略:结果页用最新数据,其他页面读 sessionStorage */
const planFromStorage = ref<TripPlan | null>(null)

const readStorage = () => {
  const raw = sessionStorage.getItem('tripPlan')
  try {
    planFromStorage.value = raw ? (JSON.parse(raw) as TripPlan) : null
  } catch {
    planFromStorage.value = null
  }
}

const currentPlan = computed<TripPlan | null>(() => planFromStorage.value)

watch(() => route.fullPath, readStorage, { immediate: true })

const showAssistant = () => {
  readStorage()
  openAssistant()
}

/**
 * 调试开关:?drawer=instant 时跳过抽屉动画。
 * 仅用于自动化截图/端到端测试,不影响正常交互。
 */
const instantDrawer = ref(false)

// 支持通过 /?assistant=1 直接唤起小星小探员(等路由就绪后再判断 query)
router.isReady().then(() => {
  if (route.query.drawer === 'instant') instantDrawer.value = true
  if (route.query.assistant === '1') showAssistant()
})

const goHome = () => {
  if (route.path !== '/') router.push('/')
}

/** 助手改完行程后同步内存与缓存中的攻略,并通知结果页刷新 */
const onPlanUpdated = (plan: TripPlan) => {
  planFromStorage.value = plan
  sessionStorage.setItem('tripPlan', JSON.stringify(plan))
  window.dispatchEvent(new CustomEvent('xx:trip-plan-updated', { detail: plan }))
}
</script>

<style>
:root {
  --xx-primary: #6d5efc;
  --xx-primary-dark: #4c3fd6;
  --xx-accent: #ff8a3d;
  --xx-teal: #14c8b1;
  --xx-ink: #1f2340;
  --xx-muted: #6b7280;
  --xx-line: #e9ecf6;
  --xx-card-shadow: 0 12px 32px rgba(76, 63, 214, 0.1);
}

#app {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', 'Hiragino Sans GB',
    'Microsoft YaHei', Roboto, 'Helvetica Neue', Arial, 'Noto Sans', sans-serif;
  color: var(--xx-ink);
}

/* ============ 布局 ============ */

.app-layout {
  min-height: 100vh;
  background: #f4f6fc;
}

.app-header {
  height: auto;
  line-height: normal;
  padding: 0;
  background: linear-gradient(115deg, #5b4ae0 0%, #7c5cf5 42%, #a06bf0 70%, #ff8a3d 130%);
  box-shadow: 0 6px 24px rgba(76, 63, 214, 0.28);
  position: sticky;
  top: 0;
  z-index: 20;
}

.header-inner {
  max-width: 1440px;
  margin: 0 auto;
  padding: 12px 28px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20px;
  flex-wrap: wrap;
}

.brand {
  display: flex;
  align-items: center;
  gap: 14px;
  cursor: pointer;
  user-select: none;
}

.brand-mark {
  position: relative;
  width: 48px;
  height: 48px;
  border-radius: 16px;
  display: grid;
  place-items: center;
  background: rgba(255, 255, 255, 0.18);
  border: 1px solid rgba(255, 255, 255, 0.45);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.5);
}

.mark-compass {
  font-size: 24px;
  animation: compassSpin 6s ease-in-out infinite;
}

.mark-spark {
  position: absolute;
  top: -6px;
  right: -4px;
  font-size: 15px;
  color: #ffe9a8;
  animation: sparkPulse 2.2s ease-in-out infinite;
}

.brand-text {
  display: flex;
  flex-direction: column;
  line-height: 1.25;
}

.brand-name {
  font-size: 25px;
  font-weight: 800;
  color: #fff;
  letter-spacing: 3px;
  text-shadow: 0 2px 10px rgba(31, 20, 80, 0.35);
}

.brand-slogan {
  font-size: 12.5px;
  letter-spacing: 2.6px;
  color: rgba(255, 255, 255, 0.9);
}

.header-right {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.header-tag {
  background: rgba(255, 255, 255, 0.16);
  border: 1px solid rgba(255, 255, 255, 0.32);
  color: #fff;
  border-radius: 999px;
  margin: 0;
  font-size: 12.5px;
  padding: 3px 11px;
}

.assistant-entry {
  color: #fff !important;
  border-radius: 999px;
  height: 36px;
  padding: 0 16px;
  font-weight: 600;
  background: rgba(255, 255, 255, 0.16);
  border: 1px solid rgba(255, 255, 255, 0.4);
  display: inline-flex;
  align-items: center;
  gap: 8px;
}

.assistant-entry:hover {
  background: rgba(255, 255, 255, 0.3) !important;
  color: #fff !important;
}

.entry-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #46f0c8;
  box-shadow: 0 0 0 0 rgba(70, 240, 200, 0.7);
  animation: dotPulse 1.8s infinite;
}

.app-content {
  min-height: calc(100vh - 190px);
}

.app-footer {
  text-align: center;
  background: transparent;
  color: var(--xx-muted);
  padding: 22px 16px 34px;
  display: flex;
  flex-direction: column;
  gap: 6px;
  align-items: center;
}

.footer-brand {
  font-weight: 700;
  color: var(--xx-primary-dark);
  letter-spacing: 2px;
}

.footer-slogan {
  font-size: 13px;
  color: var(--xx-accent);
  letter-spacing: 1.6px;
}

.footer-meta {
  font-size: 12px;
  color: #9aa2b8;
}

/* ============ 悬浮按钮 ============ */

.fab-assistant {
  position: fixed;
  right: 26px;
  bottom: 96px;
  z-index: 60;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
  width: 76px;
  height: 76px;
  padding: 0;
  border: none;
  border-radius: 50%;
  cursor: pointer;
  color: #fff;
  background: linear-gradient(140deg, #6d5efc 0%, #a06bf0 55%, #ff8a3d 130%);
  box-shadow: 0 14px 34px rgba(109, 94, 252, 0.45);
  transition: transform 0.25s ease, box-shadow 0.25s ease;
}

.fab-assistant:hover {
  transform: translateY(-4px) scale(1.04);
  box-shadow: 0 18px 42px rgba(109, 94, 252, 0.55);
}

.fab-assistant:active {
  transform: translateY(-1px) scale(0.99);
}

.fab-ring {
  position: absolute;
  inset: -8px;
  border-radius: 50%;
  border: 2px solid rgba(109, 94, 252, 0.45);
  animation: ringPulse 2.6s ease-out infinite;
  pointer-events: none;
}

.fab-icon {
  font-size: 26px;
  line-height: 1;
  margin-top: 6px;
}

.fab-label {
  font-size: 10.5px;
  font-weight: 700;
  letter-spacing: 0.4px;
}

/* ============ 动画 ============ */

@keyframes compassSpin {
  0%, 100% { transform: rotate(-12deg); }
  50% { transform: rotate(12deg); }
}

@keyframes sparkPulse {
  0%, 100% { opacity: 0.35; transform: scale(0.85); }
  50% { opacity: 1; transform: scale(1.15); }
}

@keyframes dotPulse {
  0% { box-shadow: 0 0 0 0 rgba(70, 240, 200, 0.7); }
  70% { box-shadow: 0 0 0 9px rgba(70, 240, 200, 0); }
  100% { box-shadow: 0 0 0 0 rgba(70, 240, 200, 0); }
}

@keyframes ringPulse {
  0% { transform: scale(0.92); opacity: 0.9; }
  70% { transform: scale(1.18); opacity: 0; }
  100% { transform: scale(1.18); opacity: 0; }
}

/* ============ 全局美化 ============ */

.ant-card {
  border-radius: 16px;
}

.ant-btn {
  border-radius: 10px;
}

.ant-btn-primary {
  background: linear-gradient(135deg, #6d5efc 0%, #8b5cf6 100%);
  border: none;
  box-shadow: 0 6px 18px rgba(109, 94, 252, 0.3);
}

.ant-btn-primary:not(:disabled):hover {
  background: linear-gradient(135deg, #5b4ae0 0%, #7c4ce8 100%) !important;
}

::-webkit-scrollbar {
  width: 10px;
  height: 10px;
}

::-webkit-scrollbar-thumb {
  background: rgba(109, 94, 252, 0.3);
  border-radius: 8px;
  border: 2px solid transparent;
  background-clip: content-box;
}

::-webkit-scrollbar-thumb:hover {
  background: rgba(109, 94, 252, 0.5);
  background-clip: content-box;
}

::-webkit-scrollbar-track {
  background: transparent;
}

@media (max-width: 768px) {
  .header-inner {
    padding: 10px 16px;
  }
  .header-tag {
    display: none;
  }
  .brand-name {
    font-size: 21px;
  }
  .fab-assistant {
    right: 16px;
    bottom: 80px;
    width: 66px;
    height: 66px;
  }
}
</style>
