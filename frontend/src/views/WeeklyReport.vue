<template>
  <div class="weekly" :class="{ 'is-wide': !is_mobile }">
    <!-- 页头：第几期 + 翻到上一期 / 下一期 -->
    <div v-if="report" class="wr-head">
      <h1>{{ title }}</h1>
      <span class="wr-nav">
        <el-button link type="primary" :disabled="!has_older" @click="go(index + 1)">‹ 上一期</el-button>
        <el-button link type="primary" :disabled="!has_newer" @click="go(index - 1)">下一期 ›</el-button>
      </span>
    </div>

    <!-- 补做时的提示：正在准备 / 还在准备中 -->
    <p v-if="notice" class="wr-notice">{{ notice }}</p>

    <template v-if="facts">
      <!-- 一句鼓励和总结；文字还没好（facts_ready）时不显示 -->
      <div v-if="text.cheer" class="wr-cheer">{{ text.cheer }}</div>
      <div v-if="text.summary" class="wr-summary">{{ text.summary }}</div>

      <!-- 奖章：数值为 0 的不出现 -->
      <div v-if="badge_list.length" class="wr-badges">
        <span v-for="b in badge_list" :key="b.key" class="wr-badge" :class="BADGE_LOOK[b.key].cls">{{ BADGE_LOOK[b.key].icon }} {{ b.text }}</span>
      </div>

      <div class="wr-blocks">
        <!-- 打卡日历 -->
        <section class="wr-block">
          <h2>打卡日历</h2>
          <p class="wr-hint">每个格子是一天，颜色越深做的事越多</p>
          <VChart :option="calendar_option" autoresize class="wr-chart" style="height: 215px" />
          <div class="wr-legend">
            <span><i style="background: #c9c9f2"></i>默写了单词</span>
            <span><i style="background: #8f8fe6"></i>录了错题</span>
            <span><i style="background: #5b5bd6"></i>两样都做了</span>
          </div>
          <p v-if="captions.calendar" class="wr-say">{{ captions.calendar }}</p>
        </section>

        <!-- 学科：考点星星 + 各模块 + 下一个要攻克的 -->
        <section v-if="subject" class="wr-block">
          <div v-if="subjects.length > 1" class="wr-tabs">
            <button v-for="s in subjects" :key="s.subject_id" type="button" :class="{ on: s.subject_id === subject_id }" @click="subject_id = s.subject_id">{{ s.name }}</button>
          </div>
          <div class="wr-two">
            <div :class="{ 'wr-span': !modules_option }">
              <h2>考点星星</h2>
              <p class="wr-hint">和知识星空同一套颜色</p>
              <VChart :option="donut_option" autoresize class="wr-chart" style="height: 170px" />
            </div>
            <div v-if="modules_option">
              <h2>各模块</h2>
              <p class="wr-hint">虚线上周，实线本周</p>
              <VChart :option="modules_option" autoresize class="wr-chart" style="height: 170px" />
            </div>
          </div>
          <p v-if="point_caption" class="wr-say">{{ point_caption }}</p>
          <div v-if="subject.target?.name" class="wr-target">
            <div><small>下一个要攻克的</small><br><b>{{ subject.target.name }}</b></div>
          </div>
        </section>

        <!-- 单词默写：仪表盘 + 近 6 周 -->
        <section class="wr-block">
          <h2>单词默写</h2>
          <p class="wr-hint">本周正确率，和最近几周的条数</p>
          <div class="wr-two">
            <VChart v-if="gauge_option" :option="gauge_option" autoresize class="wr-chart" style="height: 160px" />
            <VChart :option="trend_option" autoresize class="wr-chart" :class="{ 'wr-span': !gauge_option }" style="height: 160px" />
          </div>
          <p v-if="captions.dictation" class="wr-say">{{ captions.dictation }}</p>
        </section>

        <!-- 练习卷：一行数字 + 一句话 -->
        <section class="wr-block">
          <h2>练习卷</h2>
          <p class="wr-hint">这一周批改的考点卷</p>
          <p v-if="practice_line" class="wr-number">{{ practice_line }}</p>
          <p v-if="captions.practice" class="wr-say">{{ captions.practice }}</p>
        </section>
      </div>
    </template>

    <!-- 底部两个普通链接 -->
    <p v-if="ready" class="wr-foot">
      <RouterLink to="/targeted-paper">去出一份考点卷</RouterLink>
      <RouterLink to="/learning-reports/legacy">旧报告</RouterLink>
    </p>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { ElMessage } from 'element-plus'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { HeatmapChart, PieChart, RadarChart, GaugeChart, BarChart } from 'echarts/charts'
import {
  CalendarComponent, VisualMapComponent, TitleComponent, TooltipComponent, GridComponent, LegendComponent,
} from 'echarts/components'
import { weeklyReportApi } from '@/api/weekly_report'
import { use_is_mobile } from '@/composables/useIsMobile'
import {
  weekTitle, badges, calendarOption, visibleSubjects, defaultSubjectId,
  donutOption, modulesOption, gaugeOption, trendOption, practiceLine,
} from '@/composables/weeklyReport'

// 按需引入要用到的图表类型和组件
use([
  CanvasRenderer, HeatmapChart, PieChart, RadarChart, GaugeChart, BarChart,
  CalendarComponent, VisualMapComponent, TitleComponent, TooltipComponent, GridComponent, LegendComponent,
])

// 打开页面时补做：最多试几次、每次之间等多久
const ADVANCE_MAX_TRIES = 8
const ADVANCE_WAIT_MS = 4000
const PREPARING_TEXT = '正在准备这一期周报…'
const LATER_TEXT = '这一期还在准备中，过一会儿再来看'

// 奖章的图标和颜色
const BADGE_LOOK = {
  streak: { icon: '🔥', cls: '' },
  improved: { icon: '⭐', cls: 'green' },
  dictation: { icon: '✏️', cls: 'orange' },
  graduated: { icon: '🎓', cls: 'green' },
}

// 宽度 ≤768px 时单列，更宽时图表块排两列
const is_mobile = use_is_mobile()

const items = ref([])        // 各期简表，新的在前
const index = ref(0)         // 当前看的是 items 里的第几期
const report = ref(null)     // 当前这一期的完整内容
const notice = ref('')       // 补做时的提示文字
const ready = ref(false)     // 第一次取列表结束后才显示底部链接，避免闪一下
const subject_id = ref(null) // 当前选中的学科
const theme = ref(null)      // 图表用的文字、线条颜色（从页面的 CSS 变量读）
let leaving = false          // 离开页面后停止补做

// 当前这一期的数字和文字；文字还没好时是空对象，各处文字就不显示
const facts = computed(() => report.value?.facts || null)
const text = computed(() => report.value?.text || {})
const captions = computed(() => text.value.captions || {})

const title = computed(() => (facts.value ? weekTitle(facts.value) : `第 ${report.value?.number ?? ''} 期`))
const has_older = computed(() => index.value < items.value.length - 1)
const has_newer = computed(() => index.value > 0)
const badge_list = computed(() => (facts.value ? badges(facts.value) : []))

// 学科切换
const subjects = computed(() => (facts.value ? visibleSubjects(facts.value) : []))
const subject = computed(() => subjects.value.find(s => s.subject_id === subject_id.value) || null)
const point_caption = computed(() => (subject.value ? captions.value.points?.[String(subject.value.subject_id)] : ''))

// 各张图的配置，都带上当前主题颜色
const calendar_option = computed(() => calendarOption(facts.value, theme.value))
const donut_option = computed(() => donutOption(subject.value, theme.value))
const modules_option = computed(() => (subject.value ? modulesOption(subject.value, theme.value) : null))
const gauge_option = computed(() => gaugeOption(facts.value, theme.value))
const trend_option = computed(() => trendOption(facts.value, theme.value))
const practice_line = computed(() => practiceLine(facts.value))

/** 从页面的 CSS 变量读图表要用的颜色；读不到的不传，用默认值 */
function read_theme() {
  const css = getComputedStyle(document.documentElement)
  const colors = {
    text: css.getPropertyValue('--el-text-color-secondary').trim(),
    strong: css.getPropertyValue('--el-text-color-primary').trim(),
    line: css.getPropertyValue('--el-border-color-light').trim(),
  }
  return Object.fromEntries(Object.entries(colors).filter(([, value]) => value))
}

/** 等一会儿 */
function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms))
}

/** 取各期简表；失败时当作一期都没有、并且需要补做 */
async function load_list() {
  try {
    const { data } = await weeklyReportApi.list()
    items.value = data.items || []
    return !!data.due
  } catch {
    items.value = []
    return true
  }
}

/** 打开第 i 期（i 是 items 里的位置） */
async function go(i) {
  const item = items.value[i]
  if (!item) return
  try {
    const { data } = await weeklyReportApi.get(item.id)
    index.value = i
    report.value = data
    subject_id.value = data.facts ? defaultSubjectId(data.facts) : null
  } catch {
    ElMessage.error('这一期打不开，请稍后再试')
  }
}

/** 补做最近一期：循环调「推进一步」，做完就刷新列表、显示最新一期 */
async function catch_up() {
  notice.value = PREPARING_TEXT
  let done = false
  for (let tries = 1; tries <= ADVANCE_MAX_TRIES && !leaving; tries++) {
    try {
      const { data } = await weeklyReportApi.advance()
      if (data.status === 'done') {
        done = true
        break
      }
    } catch {
      // 请求失败也算一次，等一会儿再试
    }
    if (tries < ADVANCE_MAX_TRIES) await sleep(ADVANCE_WAIT_MS)
  }
  if (leaving) return
  // 没做完也刷新一次：数字已经算好的那一期可以先看图表
  await load_list()
  if (items.value.length) await go(0)
  notice.value = done ? '' : LATER_TEXT
}

onMounted(async () => {
  theme.value = read_theme()
  const due = await load_list()
  // 有已生成的期就先显示最新一期
  if (items.value.length) await go(0)
  ready.value = true
  if (due) await catch_up()
})

onBeforeUnmount(() => {
  leaving = true
})
</script>

<style scoped>
/* 手机单列；电脑上内容区最宽 960px，图表块排两列 */
.weekly { max-width: 960px; margin: 0 auto; color: var(--text-primary); }
.wr-head { display: flex; align-items: center; justify-content: space-between; gap: 10px; margin-bottom: 10px; }
.wr-head h1 { font-size: 18px; margin: 0; line-height: 1.4; }
.wr-nav { display: flex; gap: 4px; white-space: nowrap; }
.wr-nav .el-button { font-size: 13px; }
.wr-notice { background: var(--bg-primary); border: 1px solid var(--border-light); border-radius: 14px; padding: 12px 14px; font-size: 14px; color: var(--text-secondary); margin: 0 0 10px; }

.wr-cheer { background: #5b5bd6; color: #fff; border-radius: 14px; padding: 14px 16px; font-size: 17px; font-weight: 700; line-height: 1.5; }
.wr-summary { background: var(--bg-primary); border: 1px solid var(--border-light); border-radius: 14px; padding: 12px 14px; font-size: 14px; line-height: 1.7; margin-top: 10px; }

.wr-badges { display: flex; flex-wrap: wrap; gap: 8px; margin: 12px 0 4px; }
.wr-badge { border-radius: 999px; padding: 6px 12px; font-size: 13px; font-weight: 600; background: rgba(91, 91, 214, 0.14); color: #5b5bd6; }
.wr-badge.green { background: rgba(31, 157, 99, 0.16); color: #1f9d63; }
.wr-badge.orange { background: rgba(230, 138, 46, 0.18); color: #b4641a; }

.wr-blocks { display: grid; grid-template-columns: minmax(0, 1fr); gap: 12px; margin-top: 12px; }
.is-wide .wr-blocks { grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); align-items: start; }
.wr-block { background: var(--bg-primary); border: 1px solid var(--border-light); border-radius: 14px; padding: 12px 14px; min-width: 0; }
.wr-block h2 { font-size: 15px; margin: 0 0 2px; }
.wr-hint { color: var(--text-muted); font-size: 12px; margin: 0 0 4px; }
.wr-say { font-size: 14px; line-height: 1.6; margin: 6px 0 0; }
.wr-number { font-size: 16px; font-weight: 600; margin: 8px 0 0; }
.wr-chart { width: 100%; }

.wr-legend { display: flex; gap: 12px; flex-wrap: wrap; font-size: 12px; color: var(--text-muted); margin-top: 2px; }
.wr-legend i { display: inline-block; width: 10px; height: 10px; border-radius: 3px; margin-right: 4px; vertical-align: -1px; }

/* 学科切换 */
.wr-tabs { display: inline-flex; background: var(--bg-secondary); border-radius: 8px; padding: 2px; font-size: 13px; margin-bottom: 6px; }
.wr-tabs button { border: 0; background: transparent; padding: 4px 14px; border-radius: 6px; color: var(--text-muted); cursor: pointer; }
.wr-tabs button.on { background: var(--bg-primary); color: var(--text-primary); font-weight: 600; }

/* 块里左右两半（考点星星 / 各模块，仪表盘 / 近 6 周）；只有一半时占满 */
.wr-two { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); gap: 8px; }
.wr-span { grid-column: 1 / -1; }

.wr-target { display: flex; align-items: center; gap: 10px; background: var(--bg-secondary); border-radius: 10px; padding: 10px 12px; margin-top: 8px; }
.wr-target b { font-size: 15px; }
.wr-target small { color: var(--text-muted); font-size: 12px; }

.wr-foot { text-align: center; margin: 16px 0 6px; font-size: 13px; }
.wr-foot a { color: var(--text-muted); text-decoration: underline; margin: 0 8px; }
</style>
