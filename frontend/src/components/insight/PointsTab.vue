<template>
  <!-- 学情 · 考点：上半页知识星空，下半页按模块分组的考点明细 -->
  <div class="points-tab">
    <section class="sky" aria-label="知识星空">
      <StarCanvas
        v-if="data"
        ref="canvas_ref"
        :data="data"
        :background="background"
        @hover="on_hover"
        @select="on_select"
      />

      <div class="sky-top">
        <div class="subjects">
          <button
            v-for="subject in subjects"
            :key="subject.id"
            type="button"
            :class="{ on: subject.id === current_id }"
            :aria-pressed="subject.id === current_id"
            @click="choose(subject.id)"
          >{{ subject.name }}</button>
        </div>
        <div v-if="data" class="count"><b class="num">{{ mastered_count }}</b> 颗已掌握</div>
      </div>

      <div class="legend">
        <span><i style="background: rgb(235, 87, 87)"></i>薄弱</span>
        <span><i style="background: rgb(242, 201, 76)"></i>一般</span>
        <span><i style="background: rgb(88, 214, 141)"></i>掌握</span>
        <span><i style="background: rgb(110, 112, 124)"></i>没学</span>
        <span class="hint desktop-only">按住 Ctrl 滚动可缩放</span>
        <span class="hint mobile-only">两指可缩放</span>
      </div>

      <div class="tip" :style="tip_style">{{ tip_text }}</div>

      <div v-if="selected" class="card">
        <div class="name">{{ selected.name }}</div>
        <div class="bar"><i :style="{ width: bar_width, background: bar_color }"></i></div>
        <div class="state">{{ selected_text }}</div>
        <RouterLink v-if="selected.level === 2" class="card-link" :to="{ path: '/questions', query: point_query(current_id, selected) }">
          看这个考点的错题<LineIcon name="arrow" :size="14" />
        </RouterLink>
      </div>

      <div class="toast" :class="{ show: toast_visible }">{{ toast_text }}</div>
      <div v-if="load_error" class="sky-message">{{ load_error }}</div>
      <div v-else-if="!data" class="sky-message">正在读取星空…</div>
    </section>

    <PointTable v-if="data" :groups="groups" :subject-id="current_id" />
  </div>
</template>

<script setup>
// 考点标签：星空的悬停提示、点击卡片、"点亮时刻"播放和记下已看，照原来的知识星空页搬过来
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import StarCanvas from '@/components/starmap/StarCanvas.vue'
import LineIcon from '@/components/ui/LineIcon.vue'
import PointTable from './PointTable.vue'
import { colorOf, statusText } from '@/components/starmap/starmapColors.js'
import { create_request_gate, group_points, point_query, status_of_value } from './insightModel.js'
import { starmapApi } from '@/api/starmap'
import { useCatalogStore } from '@/stores/catalog'

const props = defineProps({
  // 当前学科（由学情页记住，切到单词标签再切回来时还是这一科）
  subjectId: { type: Number, default: null },
})
const emit = defineEmits(['update:subjectId'])

// 背景里若隐若现的淡字
const FORMULAS = ['a²−b²=(a+b)(a−b)', '|a| ≥ 0', '(−1)ⁿ', '3x+5=20', 'S=πr²', '1/(n(n+2))', 'ab+ac=a(b+c)', '−2²=−4',
  '∠AOB+∠BOC', 'x=−b/a', '0.9x−a=b', 'a/b ÷ c/d', '2n+1', '(5−x)²≥0', '|x−1|', 'm³+n²>0', 'LCM(a,b)', '40x−5(x−1)']
const SENTENCES = ['be + doing', 'There is / There are', 'did', 'will + do', 'has done', 'a / an / the', 'more … than',
  'the most …', 'can · must · should', 'What / Where / When', 'How beautiful!', 'and · but · or', '-s / -es', "Tom's"]

const subjects = ref([])
const current_id = ref(null)
const data = ref(null)          // 画星空用的数据（要点亮的考点先画成"较好"）
const groups = ref([])          // 明细表：按接口原样的状态分组
const canvas_ref = ref(null)
const selected = ref(null)
const hovered = ref(null)
const hover_position = ref(null)
const toast_text = ref('')
const toast_visible = ref(false)
const load_error = ref('')
const lit = ref([])             // 这次播放点亮时刻新掌握的考点
let timers = []                 // 点亮时刻的计时器，换学科或离开页面时清掉
let pending_seen = null         // 正在播放、还没记下的 { subject_id, ids }
// 快速切换学科时只用最后一次请求的结果；离开标签后，还没回来的请求一律作废，
// 不会在已经卸载的组件上播放点亮时刻，也不会把没看到的星记成已看
const gate = create_request_gate()

const subject_name = computed(() => subjects.value.find(s => s.id === current_id.value)?.name || '')
const background = computed(() => (subject_name.value === '英语' ? SENTENCES : FORMULAS))
// 接口的已掌握数里已经包含这次要点亮的考点：先减去，点亮一颗加一颗
const mastered_count = computed(() => (data.value?.mastered_count || 0) - (data.value?.to_play?.length || 0) + lit.value.length)

// 悬停时浮出的名称
const tip_text = computed(() => hovered.value?.name || '')
const tip_style = computed(() => (hover_position.value
  ? { left: hover_position.value[0] + 12 + 'px', top: hover_position.value[1] - 10 + 'px', opacity: 1 }
  : { opacity: 0 }))

// 详情卡片
const selected_value = computed(() => (selected.value?.id === 'vocab' ? selected.value.vocab.ratio : selected.value?.value))
const bar_width = computed(() => Math.round((selected_value.value ?? 0) * 100) + '%')
const bar_color = computed(() => 'rgb(' + colorOf(selected_value.value ?? null) + ')')
const selected_text = computed(() => {
  const node = selected.value
  if (!node) return ''
  if (node.id === 'vocab') return `已掌握 ${node.vocab.mastered} / ${node.vocab.total} 个词`
  return statusText(status_of_value(node.value))
})

/** 悬停的星和它在画布上的位置 */
function on_hover(node, position) {
  hovered.value = node
  hover_position.value = position
}

/** 点中的星（点空白处为 null，卡片收起） */
function on_select(node) {
  selected.value = node
}

/** 读取一科的星空；有新掌握的考点时，等布局稳定后播放点亮时刻 */
async function load() {
  const token = gate.next()
  load_error.value = ''
  selected.value = null
  lit.value = []
  try {
    const { data: body } = await starmapApi.get(current_id.value)
    if (!gate.is_current(token)) return
    groups.value = group_points(body.nodes)
    // 要点亮的考点先画成"较好"的黄绿色，播放点亮时刻时再变成绿色
    const to_light = new Set(body.to_play || [])
    data.value = { ...body, nodes: body.nodes.map(n => (to_light.has(n.id) ? { ...n, value: 0.85 } : n)) }
    if (body.to_play?.length) timers.push(setTimeout(() => play_moment(body.to_play), 800))
  } catch (error) {
    if (!gate.is_current(token)) return
    load_error.value = error.response?.data?.detail || '星空暂时打不开，请稍后再试'
  }
}

/** 记下已看过的点亮考点（用播放开始时的学科，不受之后切换学科影响） */
async function flush_seen() {
  const record = pending_seen
  pending_seen = null
  if (!record) return
  try {
    await starmapApi.markSeen(record.subject_id, record.ids)
  } catch {
    // 记录失败下次还会再播放一次，不弹提示
  }
}

/** 停掉正在播放的点亮时刻；没记下的已看记录马上补记 */
function stop_moment() {
  timers.forEach(clearTimeout)
  timers = []
  toast_visible.value = false
  flush_seen()
}

/** 点亮时刻：依次点亮，星空中间提示，播放完记下已看 */
function play_moment(ids) {
  if (gate.is_closed()) return   // 已经离开标签：不播放，也不记已看
  pending_seen = { subject_id: current_id.value, ids }
  toast_text.value = `点亮了 ${ids.length} 颗星`
  toast_visible.value = true
  ids.forEach((id, index) => timers.push(setTimeout(() => {
    canvas_ref.value?.light([id])
    lit.value = [...lit.value, id]
  }, index * 450)))
  timers.push(setTimeout(() => { toast_visible.value = false }, 3200))
  timers.push(setTimeout(flush_seen, ids.length * 450 + 1500))
}

/** 换学科：停掉点亮时刻，清掉上一科的画面再读新的 */
function choose(id) {
  if (id === current_id.value) return
  stop_moment()
  current_id.value = id
  emit('update:subjectId', id)
  data.value = null
  groups.value = []
  on_hover(null, null)   // 换学科时收起上一科悬停的名称
  load()
}

// 离开标签：先关闸门让还在路上的请求作废，再停掉点亮时刻（已经开始播放的照常补记已看）
onBeforeUnmount(() => {
  gate.close()
  stop_moment()
})

onMounted(async () => {
  try {
    const list = await useCatalogStore().loadStarmapSubjects()
    if (gate.is_closed()) return   // 学科还没读回来就已经离开了标签
    subjects.value = list
  } catch {
    if (gate.is_closed()) return
    load_error.value = '星空暂时打不开，请稍后再试'
    return
  }
  if (!subjects.value.length) {
    load_error.value = '还没有可以看星空的学科'
    return
  }
  // 学情页记着的学科还在就用它，否则用第一科
  const remembered = subjects.value.find(s => s.id === props.subjectId)
  choose(remembered ? remembered.id : subjects.value[0].id)
})
</script>

<style scoped>
/* 星空：固定高度的夜色卡片，不随顶部栏或窗口高度变化 */
.sky {
  position: relative;
  height: 460px;
  overflow: hidden;
  border-radius: var(--r-lg);
  background: var(--night);
  box-shadow: var(--shadow-2);
  color: #e6e9f2;
  user-select: none;
}
.sky-top {
  position: absolute;
  left: 18px;
  top: 14px;
  right: 18px;
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 6px 16px;
  pointer-events: none;   /* 空白处不挡住画布的拖动 */
}
.subjects { display: flex; gap: 4px; pointer-events: auto; }
.subjects button {
  min-height: 36px;
  border: 0;
  border-radius: 999px;
  background: none;
  color: rgba(230, 233, 242, 0.55);
  font: inherit;
  font-size: 15px;
  padding: 4px 14px;
  cursor: pointer;
  letter-spacing: 2px;
}
.subjects button.on { color: #fff; background: rgba(255, 255, 255, 0.1); text-shadow: 0 0 12px rgba(255, 255, 255, 0.4); }
.subjects button:focus-visible { outline: 3px solid #a5a0f5; outline-offset: 2px; }
.count { font-size: 13px; color: rgba(230, 233, 242, 0.7); letter-spacing: 1px; }
.count b { font-size: 18px; color: rgb(88, 214, 141); }
.legend {
  position: absolute;
  left: 20px;
  bottom: 16px;
  display: flex;
  flex-wrap: wrap;
  gap: 6px 16px;
  font-size: 12px;
  color: rgba(230, 232, 240, 0.75);
  pointer-events: none;
}
.legend i { display: inline-block; width: 9px; height: 9px; border-radius: 50%; margin-right: 6px; }
.legend .hint { color: rgba(230, 232, 240, 0.5); }
.mobile-only { display: none; }
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
  right: 16px;
  bottom: 16px;
  width: 250px;
  padding: 14px 16px;
  border-radius: 14px;
  background: rgba(12, 14, 30, 0.85);
  border: 1px solid rgba(255, 255, 255, 0.12);
  backdrop-filter: blur(6px);
}
.card .name { font-size: 15px; margin-bottom: 8px; }
.card .bar { height: 4px; border-radius: 2px; background: rgba(255, 255, 255, 0.1); overflow: hidden; }
.card .bar i { display: block; height: 100%; }
.card .state { font-size: 12px; color: rgba(230, 233, 242, 0.65); margin-top: 8px; }
.card-link {
  display: inline-flex; align-items: center; gap: 4px; margin-top: 10px;
  color: #d7d4ff; font-size: 13px; font-weight: 600; text-decoration: none;
}
.card-link:focus-visible { outline: 3px solid #a5a0f5; outline-offset: 2px; }
.toast {
  position: absolute;
  left: 50%;
  top: 42%;
  transform: translate(-50%, -50%);
  font-size: 34px;
  letter-spacing: 6px;
  white-space: nowrap;
  color: rgb(88, 214, 141);
  text-shadow: 0 0 24px rgba(88, 214, 141, 0.7);
  pointer-events: none;
  opacity: 0;
  transition: opacity 0.6s;
}
.toast.show { opacity: 1; }
.sky-message {
  position: absolute;
  left: 50%;
  top: 50%;
  transform: translate(-50%, -50%);
  color: rgba(230, 233, 242, 0.75);
}
.num { font-family: var(--font-num); font-variant-numeric: tabular-nums; font-weight: 700; }

@media (max-width: 768px) {
  .sky { height: 360px; border-radius: var(--r-md); }
  .sky-top { left: 10px; top: 10px; right: 10px; }
  .legend { left: 14px; bottom: 12px; gap: 4px 12px; }
  .desktop-only { display: none; }
  .mobile-only { display: inline; }
  .card { left: 10px; right: 10px; bottom: 10px; width: auto; }
  .toast { font-size: 24px; letter-spacing: 4px; }
}
</style>
