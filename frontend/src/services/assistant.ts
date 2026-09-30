/**
 * 轻量共享状态
 *
 * 用于让任意页面都能唤起右侧的「小星小探员」侧边栏,
 * 避免通过 DOM 查询去点击悬浮按钮。
 */

import { ref } from 'vue'

/** AI 助手侧边栏是否展开 */
export const assistantOpen = ref(false)

/** 打开「小星小探员」 */
export function openAssistant() {
  assistantOpen.value = true
}

/** 关闭「小星小探员」 */
export function closeAssistant() {
  assistantOpen.value = false
}
