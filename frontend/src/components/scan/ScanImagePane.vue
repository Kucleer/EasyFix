<template>
  <div class="scan-image-pane" :class="{ collapsed }">
    <div class="pane-header">
      <span>原图</span>
      <span class="pane-tip desktop-only">滚轮放大，按住拖动，双击复位</span>
      <el-button class="mobile-only" link type="primary" size="small" @click="collapsed = !collapsed">
        {{ collapsed ? '展开' : '收起' }}
      </el-button>
    </div>

    <!-- 电脑端：图框固定，滚轮放大、按住拖动、双击复位 -->
    <div
      ref="frame_ref"
      class="zoom-frame desktop-only"
      :class="{ draggable: view.scale > 1, dragging }"
      @wheel.prevent="handle_wheel"
      @pointerdown="start_drag"
      @pointermove="move_drag"
      @pointerup="end_drag"
      @pointercancel="end_drag"
      @dblclick="reset_view"
    >
      <img :src="src" alt="这一页的原图" draggable="false" :style="image_style" />
    </div>

    <!-- 手机端：点开用 el-image 的预览放大，可收起 -->
    <div class="mobile-body mobile-only">
      <el-image :src="src" :preview-src-list="[src]" fit="contain" :hide-on-click-modal="true" />
    </div>
  </div>
</template>

<script setup>
// 整理区的原图：电脑端固定在左边可缩放拖动，手机端在上方可收起、点开放大
import { ref, reactive, computed, watch } from 'vue'
import { zoomAt } from '@/composables/scanPage'

const props = defineProps({
  src: { type: String, required: true },  // 原图地址
})

// 每次滚轮缩放的倍数
const WHEEL_FACTOR = 1.2

const frame_ref = ref(null)
const collapsed = ref(false)                 // 手机端是否收起
const view = reactive({ scale: 1, x: 0, y: 0 }) // 当前缩放和平移
const dragging = ref(false)
let drag_start = null                        // 按下时的指针位置和平移量

// 平移和缩放都用 transform，变换原点在左上角（与 zoomAt 的约定一致）
const image_style = computed(() => ({
  transform: `translate(${view.x}px, ${view.y}px) scale(${view.scale})`,
}))

/** 把新的缩放结果写回 view。 */
const apply_view = (next) => {
  view.scale = next.scale
  view.x = next.x
  view.y = next.y
}

/** 滚轮：向上放大、向下缩小，围绕指针所在的位置。 */
const handle_wheel = (event) => {
  const rect = frame_ref.value.getBoundingClientRect()
  const point = { x: event.clientX - rect.left, y: event.clientY - rect.top }
  const factor = event.deltaY < 0 ? WHEEL_FACTOR : 1 / WHEEL_FACTOR
  apply_view(zoomAt(view, point, factor))
}

/** 按下鼠标：放大后才能拖动，记下起点。 */
const start_drag = (event) => {
  if (view.scale <= 1 || event.button !== 0) return
  dragging.value = true
  drag_start = { pointer_x: event.clientX, pointer_y: event.clientY, x: view.x, y: view.y }
  event.currentTarget.setPointerCapture(event.pointerId)
}

/** 拖动中：平移量 = 起点平移量 + 指针移动的距离。 */
const move_drag = (event) => {
  if (!dragging.value) return
  view.x = drag_start.x + event.clientX - drag_start.pointer_x
  view.y = drag_start.y + event.clientY - drag_start.pointer_y
}

/** 松开鼠标：结束拖动。 */
const end_drag = () => {
  dragging.value = false
  drag_start = null
}

/** 双击：回到原始大小和位置。 */
const reset_view = () => {
  apply_view({ scale: 1, x: 0, y: 0 })
}

// 换了一张图时复位
watch(() => props.src, reset_view)
</script>

<style scoped>
.scan-image-pane {
  border: 1px solid var(--border-light);
  border-radius: 10px;
  background: #fff;
  padding: 10px;
}

.pane-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
  font-weight: bold;
  color: var(--text-primary);
}

.pane-tip {
  font-size: 12px;
  font-weight: normal;
  color: var(--text-muted);
}

.zoom-frame {
  height: calc(100vh - 140px);
  overflow: hidden;
  background: #f7f7fa;
  border-radius: 6px;
  touch-action: none;
}

.zoom-frame.draggable {
  cursor: grab;
}

.zoom-frame.dragging {
  cursor: grabbing;
}

.zoom-frame img {
  display: block;
  width: 100%;
  height: 100%;
  object-fit: contain;
  transform-origin: 0 0;
  user-select: none;
}

.mobile-body .el-image {
  display: block;
  width: 100%;
  max-height: 45vh;
}

.mobile-only {
  display: none;
}

/* 手机端：只显示可收起的预览图 */
@media (max-width: 768px) {
  .desktop-only {
    display: none;
  }

  .mobile-only {
    display: block;
  }

  .pane-header .mobile-only {
    display: inline-flex;
  }

  .scan-image-pane.collapsed .mobile-body {
    display: none;
  }

  .scan-image-pane.collapsed .pane-header {
    margin-bottom: 0;
  }
}
</style>
