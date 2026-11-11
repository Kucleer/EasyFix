<template>
  <canvas ref="canvasRef" class="star-canvas"></canvas>
</template>

<script setup>
// 知识星空的绘制组件：首页缩略图和星空页共用
import { ref, onMounted, onBeforeUnmount, watch, nextTick } from 'vue'
import { createStarEngine } from './starmapEngine.js'

const props = defineProps({
  data: { type: Object, default: null },        // 接口 /api/starmap 的返回
  mini: { type: Boolean, default: false },      // 缩略图：不能缩放和悬停，粒子更少
  background: { type: Array, default: () => [] }, // 背景里若隐若现的淡字
})
const emit = defineEmits(['hover', 'select'])

const canvasRef = ref(null)
let engine = null

// 按当前数据重建绘制引擎
function build() {
  engine?.destroy()
  engine = null
  if (!props.data || !canvasRef.value) return
  engine = createStarEngine(canvasRef.value, props.data, {
    mini: props.mini,
    background: props.background,
    onHover: (node, position) => emit('hover', node, position),
    onSelect: node => emit('select', node),
  })
}

// 外部调用：播放点亮时刻
function light(ids) {
  engine?.light(ids)
}

defineExpose({ light })

onMounted(() => nextTick(build))
watch(() => props.data, () => nextTick(build))
onBeforeUnmount(() => engine?.destroy())
</script>

<style scoped>
.star-canvas {
  display: block;
  width: 100%;
  height: 100%;
}
</style>
