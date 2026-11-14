// 判断当前是不是手机宽度（≤768px），列表页用它在“表格”和“卡片”之间切换
import { ref, onMounted, onBeforeUnmount } from 'vue'

// 和各页面 CSS 里的 @media (max-width: 768px) 保持一致
export const MOBILE_QUERY = '(max-width: 768px)'

/**
 * 返回一个响应式的 is_mobile：窗口宽度 ≤768px 时为 true，窗口变化时自动更新。
 * 用法：const is_mobile = use_is_mobile()
 */
export function use_is_mobile() {
  const is_mobile = ref(false)
  let media = null
  // 根据媒体查询结果更新 is_mobile
  const update = () => { is_mobile.value = !!media?.matches }

  onMounted(() => {
    media = window.matchMedia(MOBILE_QUERY)
    update()
    media.addEventListener('change', update)
  })
  onBeforeUnmount(() => {
    media?.removeEventListener('change', update)
  })
  return is_mobile
}
