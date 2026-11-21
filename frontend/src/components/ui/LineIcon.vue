<template>
  <!-- 线条图标：路径来自 icons.js，颜色跟随文字颜色 -->
  <svg
    v-if="path"
    class="line-icon"
    viewBox="0 0 24 24"
    :width="size"
    :height="size"
    aria-hidden="true"
  >
    <path :d="path" />
  </svg>
</template>

<script setup>
import { computed } from 'vue'
import { ICON_PATHS } from './icons'

const props = defineProps({
  // 图标名称，见 icons.js；不存在时什么都不画
  name: { type: String, required: true },
  // 边长（像素）
  size: { type: [Number, String], default: 20 },
})

const path = computed(() => ICON_PATHS[props.name] || '')
</script>

<style scoped>
.line-icon {
  fill: none;
  stroke: currentColor;
  stroke-width: 1.9;
  stroke-linecap: round;
  stroke-linejoin: round;
  flex-shrink: 0;
}
</style>
