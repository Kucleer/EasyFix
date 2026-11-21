// 周报：把后端的 facts 变成奖章、标题和 ECharts 配置（都是纯函数，不依赖 Vue）
import { colorOf, GREY } from '../components/starmap/starmapColors.js'
import { CHART_THEME } from './chartTheme.js'

// 颜色统一取自图表主题（chartTheme.js），学情页和周报页一致
const MAIN = CHART_THEME.main
const SOFT = CHART_THEME.soft
const GREEN = CHART_THEME.green
const LINE_GREY = CHART_THEME.grey

// 默认的文字、强调文字、线条颜色；页面可以传入 CSS 变量的值覆盖
const DEFAULT_THEME = { text: CHART_THEME.text, strong: CHART_THEME.strong, line: CHART_THEME.line }

// 合并主题：没传的颜色用默认值
function withTheme(theme) {
  return { ...DEFAULT_THEME, ...(theme || {}) }
}

// 'r,g,b' 文本变成 CSS 颜色
function rgb(triple) {
  return `rgb(${triple})`
}

// 一个学科里变好的个数：优先用不封顶的 improved_count，没有时用列表长度
function improvedOf(subject) {
  return subject.improved_count ?? (subject.improved || []).length
}

// 一个学科里变差的个数，规则同上
function droppedOf(subject) {
  return subject.dropped_count ?? (subject.dropped || []).length
}

// 把 '2026-11-16' 拆成 [月, 日]
function monthDay(text) {
  const [, month, day] = text.split('-').map(Number)
  return [month, day]
}

/** 周标题：`第 6 期 · 11 月 16 日 – 22 日`，跨月时后半段也带月份 */
export function weekTitle(facts) {
  const [m1, d1] = monthDay(facts.week.monday)
  const [m2, d2] = monthDay(facts.week.sunday)
  const end = m1 === m2 ? `${d2} 日` : `${m2} 月 ${d2} 日`
  return `第 ${facts.week.number} 期 · ${m1} 月 ${d1} 日 – ${end}`
}

/** 奖章列表 [{key, text}]，数值为 0 的不出现 */
export function badges(facts) {
  const improved = (facts.subjects || []).reduce((sum, s) => sum + improvedOf(s), 0)
  const all = [
    { key: 'streak', n: facts.entries.streak_weeks, text: n => `连续 ${n} 周有录入` },
    { key: 'improved', n: improved, text: n => `${n} 个考点变好` },
    { key: 'dictation', n: facts.dictation.days, text: n => `默写 ${n} 天` },
    { key: 'graduated', n: facts.practice.graduated, text: n => `毕业 ${n} 道` },
  ]
  return all.filter(b => b.n > 0).map(b => ({ key: b.key, text: b.text(b.n) }))
}

/** 打卡日历热力图：值 1 只默写或翻了错题、2 只录入、3 两样都有；没有记录的天不放（后端的 dictated 已包含翻一翻） */
export function calendarOption(facts, theme) {
  const t = withTheme(theme)
  const days = facts.calendar || []
  const data = days
    .map(d => [d.date, (d.dictated ? 1 : 0) + (d.entered ? 2 : 0)])
    .filter(item => item[1] > 0)
  const range = days.length ? [days[0].date, days[days.length - 1].date] : undefined
  return {
    textStyle: { color: t.text, fontFamily: 'inherit' },
    tooltip: { formatter: p => p.value[0] + '：' + ['', '默写或翻了错题', '录了错题', '两样都做了'][p.value[1]] },
    visualMap: {
      show: false, type: 'piecewise', dimension: 1,
      pieces: [{ value: 1, color: '#c9c9f2' }, { value: 2, color: '#8f8fe6' }, { value: 3, color: MAIN }],
    },
    calendar: {
      orient: 'vertical', range, top: 26, left: 44, right: 8, bottom: 4, cellSize: ['auto', 28],
      dayLabel: { firstDay: 1, nameMap: 'ZH', color: t.text },
      monthLabel: { nameMap: 'ZH', color: t.text, margin: 8 },
      yearLabel: { show: false }, splitLine: { show: false },
      itemStyle: { color: 'transparent', borderColor: t.line, borderWidth: 1 },
    },
    series: [{ type: 'heatmap', coordinateSystem: 'calendar', data }],
  }
}

/** 页面上显示哪些学科（后端只给有二级考点的学科） */
export function visibleSubjects(facts) {
  return facts.subjects || []
}

/** 默认选中的学科编号：变化（变好 + 变差）最多的，一样多取第一个；没有学科时是 null */
export function defaultSubjectId(facts) {
  let best = null
  let bestChange = -1
  for (const s of visibleSubjects(facts)) {
    const change = improvedOf(s) + droppedOf(s)
    if (change > bestChange) {
      best = s.subject_id
      bestChange = change
    }
  }
  return best
}

// 环形图每一段的状态、名字和颜色（和知识星空一致）
const DONUT_PARTS = [
  { key: 'mastered', name: '已掌握', color: rgb(colorOf(1)) },
  { key: 'good', name: '较好', color: rgb(colorOf(0.85)) },
  { key: 'fair', name: '一般', color: rgb(colorOf(0.55)) },
  { key: 'weak', name: '薄弱', color: rgb(colorOf(0.15)) },
  { key: 'unlearned', name: '还没学', color: rgb(GREY) },
]

/** 考点状态环形图；中间是「+N 本周变好」，N 为 0 时不显示 */
export function donutOption(subject, theme) {
  const t = withTheme(theme)
  const counts = subject.status_counts || {}
  const data = DONUT_PARTS
    .filter(p => counts[p.key] > 0)
    .map(p => ({ value: counts[p.key], name: p.name, itemStyle: { color: p.color } }))
  const improved = improvedOf(subject)
  return {
    textStyle: { color: t.text, fontFamily: 'inherit' },
    tooltip: { trigger: 'item' },
    title: {
      show: improved > 0, text: `+${improved}`, subtext: '本周变好', left: 'center', top: '30%',
      textStyle: { color: GREEN, fontSize: 22, fontWeight: 700 }, subtextStyle: { color: t.text, fontSize: 11 },
    },
    series: [{ type: 'pie', radius: ['60%', '86%'], label: { show: false }, data }],
  }
}

/** 模块掌握度：≥ 3 个模块画雷达图（上周虚线、本周实线），1～2 个画横向条形图，没有返回 null */
export function modulesOption(subject, theme) {
  const t = withTheme(theme)
  const modules = subject.modules || []
  if (modules.length === 0) return null
  const names = modules.map(m => m.name)
  const textStyle = { color: t.text, fontFamily: 'inherit' }

  if (modules.length >= 3) {
    return {
      textStyle,
      radar: {
        radius: '58%', center: ['50%', '54%'],
        indicator: names.map(name => ({ name, max: 1 })),
        axisName: { color: t.text, fontSize: 10 },
        splitLine: { lineStyle: { color: t.line } }, axisLine: { lineStyle: { color: t.line } }, splitArea: { show: false },
      },
      series: [{
        type: 'radar', symbolSize: 3,
        data: [
          // 上周还没学的模块当 0 画
          { name: '上周', value: modules.map(m => m.before ?? 0), lineStyle: { color: LINE_GREY, type: 'dashed' }, itemStyle: { color: LINE_GREY } },
          {
            name: '本周', value: modules.map(m => m.after),
            lineStyle: { color: MAIN, width: 2.5 }, itemStyle: { color: MAIN }, areaStyle: { color: MAIN, opacity: 0.2 },
          },
        ],
      }],
    }
  }

  return {
    textStyle,
    legend: { top: 0, textStyle: { color: t.text, fontSize: 11 } },
    grid: { left: 70, right: 16, top: 28, bottom: 8 },
    tooltip: { trigger: 'axis' },
    xAxis: {
      type: 'value', min: 0, max: 1,
      splitLine: { lineStyle: { color: t.line, type: 'dashed' } }, axisLabel: { color: t.text, fontSize: 10 },
    },
    yAxis: { type: 'category', data: names, axisLine: { lineStyle: { color: t.line } }, axisTick: { show: false }, axisLabel: { color: t.text, fontSize: 10 } },
    series: [
      // 上周没有数据（本周才开始学）的模块不画这根条
      { name: '上周', type: 'bar', barWidth: '30%', itemStyle: { color: LINE_GREY }, data: modules.map(m => m.before ?? null) },
      { name: '本周', type: 'bar', barWidth: '30%', itemStyle: { color: MAIN }, data: modules.map(m => m.after) },
    ],
  }
}

/** 默写正确率仪表盘；还没有正确率（accuracy 为 null）时返回 null */
export function gaugeOption(facts, theme) {
  const t = withTheme(theme)
  const d = facts.dictation
  if (d.accuracy === null || d.accuracy === undefined) return null
  return {
    textStyle: { color: t.text, fontFamily: 'inherit' },
    series: [{
      type: 'gauge', startAngle: 210, endAngle: -30, min: 0, max: 100, radius: '96%', center: ['50%', '58%'],
      progress: { show: true, width: 11, roundCap: true, itemStyle: { color: MAIN } },
      axisLine: { roundCap: true, lineStyle: { width: 11, color: [[1, t.line]] } },
      pointer: { show: false }, axisTick: { show: false }, splitLine: { show: false }, axisLabel: { show: false },
      detail: { offsetCenter: [0, '-2%'], formatter: '{value}%', color: t.strong, fontSize: 24, fontWeight: 700 },
      title: { offsetCenter: [0, '40%'], color: t.text, fontSize: 11 },
      data: [{ value: d.accuracy, name: `${d.count} 条` }],
    }],
  }
}

/** 近 6 周默写条数柱状图，最后一根（本周）用深色 */
export function trendOption(facts, theme) {
  const t = withTheme(theme)
  const trend = facts.dictation.trend || []
  const last = trend.length - 1
  const labels = trend.map((w, i) => {
    if (i === last) return '本周'
    const [m, d] = monthDay(w.monday)
    return `${m}/${d}`
  })
  return {
    textStyle: { color: t.text, fontFamily: 'inherit' },
    grid: { left: 30, right: 4, top: 18, bottom: 22 },
    tooltip: { trigger: 'axis' },
    xAxis: {
      type: 'category', data: labels,
      axisLine: { lineStyle: { color: t.line } }, axisTick: { show: false }, axisLabel: { color: t.text, fontSize: 10, interval: 0, rotate: 30 },
    },
    yAxis: { type: 'value', splitLine: { lineStyle: { color: t.line, type: 'dashed' } }, axisLabel: { color: t.text, fontSize: 10 } },
    series: [{
      type: 'bar', barWidth: '50%',
      data: trend.map((w, i) => ({ value: w.count, itemStyle: { color: i === last ? MAIN : SOFT, borderRadius: [3, 3, 0, 0] } })),
    }],
  }
}

/** 翻一翻一行字：`这周翻了 N 天错题，一共 M 张`；旧周报没有 flip、或者一张没翻时 null */
export function flipLine(facts) {
  const f = facts.flip
  if (!f || !(f.cards > 0)) return null
  return `这周翻了 ${f.days} 天错题，一共 ${f.cards} 张`
}

/** 练习卷一行字：有批改时 `批改 N 份 · 做对 A / B 道`，没有时 null */
export function practiceLine(facts) {
  const p = facts.practice
  if (!p || p.papers <= 0) return null
  return `批改 ${p.papers} 份 · 做对 ${p.correct} / ${p.questions} 道`
}
