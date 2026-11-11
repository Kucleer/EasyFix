<template>
  <div class="starmap-page">
    <StarCanvas
      v-if="data"
      ref="canvasRef"
      :data="data"
      :background="background"
      @hover="onHover"
      @select="onSelect"
    />

    <div class="top">
      <div class="tabs">
        <button v-for="s in subjects" :key="s.id" :class="{ on: s.id === subjectId }" @click="choose(s.id)">{{ s.name }}</button>
      </div>
      <div v-if="data" class="count"><b>{{ masteredCount }}</b> 颗已掌握</div>
    </div>

    <div class="legend">
      <span><i style="background: rgb(235, 87, 87)"></i>薄弱</span>
      <span><i style="background: rgb(242, 201, 76)"></i>一般</span>
      <span><i style="background: rgb(88, 214, 141)"></i>掌握</span>
      <span><i style="background: rgb(110, 112, 124)"></i>没学</span>
    </div>

    <div class="tip" :style="tipStyle">{{ tipText }}</div>

    <div v-if="selected" class="card">
      <div class="name">{{ selected.name }}</div>
      <div class="bar"><i :style="{ width: barWidth, background: barColor }"></i></div>
      <div class="state">{{ selectedText }}</div>
    </div>

    <div class="toast" :class="{ show: toastVisible }">{{ toastText }}</div>
    <div v-if="loadError" class="error">{{ loadError }}</div>
  </div>
</template>

<script setup>
// 知识星空页：全屏深色关系图，红黄绿表示掌握程度
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import StarCanvas from '@/components/starmap/StarCanvas.vue'
import { colorOf, statusText } from '@/components/starmap/starmapColors.js'
import { starmapApi, loadStarmapSubjects } from '@/api/starmap'

// 背景里若隐若现的淡字
const FORMULAS = ['a²−b²=(a+b)(a−b)', '|a| ≥ 0', '(−1)ⁿ', '3x+5=20', 'S=πr²', '1/(n(n+2))', 'ab+ac=a(b+c)', '−2²=−4',
  '∠AOB+∠BOC', 'x=−b/a', '0.9x−a=b', 'a/b ÷ c/d', '2n+1', '(5−x)²≥0', '|x−1|', 'm³+n²>0', 'LCM(a,b)', '40x−5(x−1)']
const SENTENCES = ['be + doing', 'There is / There are', 'did', 'will + do', 'has done', 'a / an / the', 'more … than',
  'the most …', 'can · must · should', 'What / Where / When', 'How beautiful!', 'and · but · or', '-s / -es', "Tom's"]

const subjects = ref([])
const subjectId = ref(null)
const data = ref(null)
const canvasRef = ref(null)
const selected = ref(null)
const hovered = ref(null)
const hoverPosition = ref(null)
const toastText = ref('')
const toastVisible = ref(false)
const loadError = ref('')
const lit = ref([])   // 这次播放点亮时刻新掌握的考点
let timers = []       // 点亮时刻的计时器，换学科或离开页面时清掉
let pendingSeen = null  // 正在播放、还没记下的 { subjectId, ids }

const subjectName = computed(() => subjects.value.find(s => s.id === subjectId.value)?.name || '')
const background = computed(() => (subjectName.value === '英语' ? SENTENCES : FORMULAS))
// 接口的已掌握数里已经包含这次要点亮的考点：先减去，点亮一颗加一颗
const masteredCount = computed(() => (data.value?.mastered_count || 0) - (data.value?.to_play?.length || 0) + lit.value.length)

// 悬停时浮出的名称
const tipText = computed(() => hovered.value?.name || '')
const tipStyle = computed(() => (hoverPosition.value
  ? { left: hoverPosition.value[0] + 12 + 'px', top: hoverPosition.value[1] - 10 + 'px', opacity: 1 }
  : { opacity: 0 }))

// 详情卡片
const selectedValue = computed(() => (selected.value?.id === 'vocab' ? selected.value.vocab.ratio : selected.value?.value))
const barWidth = computed(() => Math.round((selectedValue.value ?? 0) * 100) + '%')
const barColor = computed(() => 'rgb(' + colorOf(selectedValue.value ?? null) + ')')
const selectedText = computed(() => {
  const node = selected.value
  if (!node) return ''
  if (node.id === 'vocab') return `已掌握 ${node.vocab.mastered} / ${node.vocab.total} 个词`
  return statusText(node.value === null ? 'unlearned' : node.value >= 1 ? 'mastered' : node.value < 0.4 ? 'weak' : node.value < 0.7 ? 'fair' : 'good')
})

function onHover(node, position) {
  hovered.value = node
  hoverPosition.value = position
}

function onSelect(node) {
  selected.value = node
}

// 读取一科的星空；有新掌握的考点时，等布局稳定后播放点亮时刻
async function load() {
  loadError.value = ''
  selected.value = null
  lit.value = []
  try {
    const { data: body } = await starmapApi.get(subjectId.value)
    // 要点亮的考点先画成"较好"的黄绿色，播放点亮时刻时再变成绿色
    const pending = new Set(body.to_play || [])
    data.value = { ...body, nodes: body.nodes.map(n => (pending.has(n.id) ? { ...n, value: 0.85 } : n)) }
    if (body.to_play?.length) timers.push(setTimeout(() => playMoment(body.to_play), 800))
  } catch (error) {
    loadError.value = error.response?.data?.detail || '星空暂时打不开，请稍后再试'
  }
}

// 记下已看过的点亮考点（用播放开始时的学科，不受之后切换学科影响）
async function flushSeen() {
  const record = pendingSeen
  pendingSeen = null
  if (!record) return
  try {
    await starmapApi.markSeen(record.subjectId, record.ids)
  } catch {
    // 记录失败下次还会再播放一次，不打扰孩子
  }
}

// 停掉正在播放的点亮时刻；没记下的已看记录马上补记
function stopMoment() {
  timers.forEach(clearTimeout)
  timers = []
  toastVisible.value = false
  flushSeen()
}

// 点亮时刻：依次点亮，屏幕中间提示，播放完记下已看
function playMoment(ids) {
  pendingSeen = { subjectId: subjectId.value, ids }
  toastText.value = `点亮了 ${ids.length} 颗星`
  toastVisible.value = true
  ids.forEach((id, index) => timers.push(setTimeout(() => {
    canvasRef.value?.light([id])
    lit.value = [...lit.value, id]
  }, index * 450)))
  timers.push(setTimeout(() => { toastVisible.value = false }, 3200))
  timers.push(setTimeout(flushSeen, ids.length * 450 + 1500))
}

function choose(id) {
  if (id === subjectId.value) return
  stopMoment()
  subjectId.value = id
  data.value = null
  onHover(null, null)   // 换学科时收起上一科悬停的名称
  load()
}

onBeforeUnmount(stopMoment)

onMounted(async () => {
  try {
    subjects.value = await loadStarmapSubjects()
  } catch {
    loadError.value = '星空暂时打不开，请稍后再试'
    return
  }
  if (subjects.value.length) {
    subjectId.value = subjects.value[0].id
    load()
  }
})
</script>

<style scoped>
.starmap-page {
  position: relative;
  margin: -24px -30px -36px;
  height: calc(100vh - 66px);
  overflow: hidden;
  background: #030306;
  color: #e6e9f2;
  user-select: none;
}
.top {
  position: absolute;
  left: 26px;
  top: 20px;
  display: flex;
  align-items: center;
  gap: 18px;
}
.tabs { display: flex; gap: 4px; }
.tabs button {
  border: 0;
  background: none;
  color: rgba(230, 233, 242, 0.45);
  font-size: 15px;
  padding: 4px 10px;
  cursor: pointer;
  letter-spacing: 2px;
}
.tabs button.on { color: #fff; text-shadow: 0 0 12px rgba(255, 255, 255, 0.4); }
.count { font-size: 13px; color: rgba(230, 233, 242, 0.6); letter-spacing: 1px; }
.count b { font-size: 18px; color: rgb(88, 214, 141); }
.legend {
  position: absolute;
  left: 28px;
  bottom: 22px;
  display: flex;
  gap: 16px;
  font-size: 12px;
  color: rgba(230, 232, 240, 0.7);
}
.legend i { display: inline-block; width: 9px; height: 9px; border-radius: 50%; margin-right: 6px; }
.tip {
  position: absolute;
  pointer-events: none;
  font-size: 13px;
  letter-spacing: 1px;
  white-space: nowrap;
  text-shadow: 0 0 10px rgba(0, 0, 0, 0.9);
  transition: opacity 0.15s;
}
.card {
  position: absolute;
  right: 24px;
  bottom: 24px;
  width: 250px;
  padding: 14px 16px;
  border-radius: 12px;
  background: rgba(12, 14, 22, 0.82);
  border: 1px solid rgba(255, 255, 255, 0.12);
  backdrop-filter: blur(6px);
}
.card .name { font-size: 15px; margin-bottom: 8px; }
.card .bar { height: 4px; border-radius: 2px; background: rgba(255, 255, 255, 0.1); overflow: hidden; }
.card .bar i { display: block; height: 100%; }
.card .state { font-size: 12px; color: rgba(230, 233, 242, 0.6); margin-top: 8px; }
.toast {
  position: absolute;
  left: 50%;
  top: 40%;
  transform: translate(-50%, -50%);
  font-size: 34px;
  letter-spacing: 6px;
  color: rgb(88, 214, 141);
  text-shadow: 0 0 24px rgba(88, 214, 141, 0.7);
  pointer-events: none;
  opacity: 0;
  transition: opacity 0.6s;
}
.toast.show { opacity: 1; }
.error {
  position: absolute;
  left: 50%;
  top: 50%;
  transform: translate(-50%, -50%);
  color: rgba(230, 233, 242, 0.7);
}
@media (max-width: 1000px) {
  .starmap-page { margin: -20px; }
}
</style>
