// 学情页的纯函数：考点按模块分组、明细行、最近几次对错、去错题页的地址、单词复习频率图
// 不依赖 Vue，方便用 node --test 测试（见 insightModel.test.mjs）
import { statusText } from '../starmap/starmapColors.js'

// 掌握状态对应的颜色名（样式里用 tone-xxx）
const STATUS_TONE = { weak: 'coral', fair: 'sun', good: 'mint', mastered: 'mint', unlearned: 'grey' }

/** 掌握度（0~1 或 null）换算成状态，口径和后端 status_of 一致 */
export function status_of_value(value) {
  if (value === null || value === undefined) return 'unlearned'
  if (value >= 1) return 'mastered'
  if (value < 0.4) return 'weak'
  if (value < 0.7) return 'fair'
  return 'good'
}

/** 最近几次做题结果（从旧到新）换成显示用的小圆点：[{ key, right, label }] */
export function recent_marks(recent) {
  return (recent || []).map((kind, index) => ({
    key: index,
    right: kind === 'right',
    label: kind === 'right' ? '对' : '错',
  }))
}

/** 一个二级考点换成明细表的一行 */
export function point_row(node) {
  const status = node.status || status_of_value(node.value)
  return {
    id: node.id,
    parent_id: node.parent_id ?? null,
    name: node.name,
    status,
    status_text: statusText(status),
    tone: STATUS_TONE[status] || 'grey',
    recent: recent_marks(node.recent),
    pending: node.pending || 0,
  }
}

/** 一个模块下各考点的小结：几颗已掌握、几颗薄弱、几道待重做 */
export function module_summary(rows) {
  const count = status => rows.filter(row => row.status === status).length
  return {
    total: rows.length,
    mastered: count('mastered'),
    weak: count('weak'),
    pending: rows.reduce((sum, row) => sum + row.pending, 0),
  }
}

/**
 * 把 /api/starmap 的 nodes 按一级模块分组：模块按接口给的顺序，
 * 每个模块下列出它的二级考点；找不到模块的考点放进"其他考点"；没有考点的模块不显示。
 * 返回 [{ id, name, rows, summary }]
 */
export function group_points(nodes) {
  const groups = []
  const by_id = new Map()
  for (const node of nodes || []) {
    if (node.level !== 1) continue
    const group = { id: node.id, name: node.name, rows: [] }
    groups.push(group)
    by_id.set(node.id, group)
  }
  let other = null
  for (const node of nodes || []) {
    if (node.level !== 2) continue
    let group = by_id.get(node.parent_id)
    if (!group) {
      if (!other) other = { id: 'other', name: '其他考点', rows: [] }
      group = other
    }
    group.rows.push(point_row(node))
  }
  if (other) groups.push(other)
  return groups
    .filter(group => group.rows.length)
    .map(group => ({ ...group, summary: module_summary(group.rows) }))
}

/** 点一行去错题页（全部错题标签）看这个考点的题；没有模块时不带一级筛选 */
export function point_query(subject_id, row) {
  const query = { tab: 'all', subject_id: String(subject_id) }
  if (row.parent_id !== null && row.parent_id !== undefined) query.knowledge_parent_id = String(row.parent_id)
  query.knowledge_point_id = String(row.id)
  return query
}

/** 'YYYY-MM-DD' 往前或往后挪 offset 天（按 UTC 算，避免时区和夏令时影响） */
function shift_date(text, offset) {
  const [year, month, day] = text.split('-').map(Number)
  const date = new Date(Date.UTC(year, month - 1, day + offset))
  return date.toISOString().slice(0, 10)
}

/**
 * 单词复习频率：取截至 end_date 的最近 days 天，每天一个点，没复习的日子补 0
 * rows 是接口的 frequency：[{ date: 'YYYY-MM-DD', count }]
 * 返回 [{ date, count }]，从旧到新
 */
export function daily_counts(rows, end_date, days = 60) {
  const counts = new Map((rows || []).map(row => [String(row.date).slice(0, 10), Number(row.count) || 0]))
  const result = []
  for (let offset = days - 1; offset >= 0; offset -= 1) {
    const date = shift_date(end_date, -offset)
    result.push({ date, count: counts.get(date) || 0 })
  }
  return result
}

/** 单词复习频率折线图的 ECharts 配置；theme 来自 useChartTheme() */
export function frequency_option(points, theme) {
  return {
    color: [theme.main],
    tooltip: { trigger: 'axis', formatter: items => `${items[0].axisValue}<br>复习 ${items[0].value} 次` },
    grid: { left: 8, right: 16, top: 16, bottom: 8, containLabel: true },
    xAxis: {
      type: 'category',
      data: points.map(point => point.date),
      boundaryGap: false,
      axisLine: { lineStyle: { color: theme.line } },
      axisTick: { show: false },
      // 横轴只显示"月-日"
      axisLabel: { color: theme.text, formatter: value => value.slice(5) },
    },
    yAxis: {
      type: 'value',
      minInterval: 1,
      axisLabel: { color: theme.text },
      splitLine: { lineStyle: { color: theme.line } },
    },
    series: [{
      type: 'line',
      data: points.map(point => point.count),
      showSymbol: false,
      lineStyle: { width: 2.5 },
      areaStyle: { color: theme.soft, opacity: 0.35 },
    }],
  }
}
