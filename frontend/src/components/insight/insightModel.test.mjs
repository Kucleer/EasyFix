// 学情页纯函数的测试。运行：node --test frontend/src/components/insight/insightModel.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import {
  status_of_value, recent_marks, point_row, module_summary, group_points, point_query, daily_counts, frequency_option,
} from './insightModel.js'

// 和 /api/starmap 一样：二级考点在前，一级模块在后
const NODES = [
  { id: 11, name: '乘方', level: 2, parent_id: 1, value: 0.3, status: 'weak', recent: ['right', 'wrong', 'wrong'], pending: 2 },
  { id: 12, name: '混合运算', level: 2, parent_id: 1, value: 1, status: 'mastered', recent: ['right'], pending: 0 },
  { id: 21, name: '线段', level: 2, parent_id: 2, value: null, status: 'unlearned', recent: [], pending: 0 },
  { id: 31, name: '找不到模块', level: 2, parent_id: 99, value: 0.5, status: 'fair', recent: [], pending: 1 },
  { id: 1, name: '有理数', level: 1, parent_id: null, value: 0.6, status: 'fair', recent: [] },
  { id: 2, name: '几何图形', level: 1, parent_id: null, value: null, status: 'unlearned', recent: [] },
  { id: 3, name: '空模块', level: 1, parent_id: null, value: null, status: 'unlearned', recent: [] },
]

test('掌握度换算成状态，和后端口径一致', () => {
  assert.equal(status_of_value(null), 'unlearned')
  assert.equal(status_of_value(undefined), 'unlearned')
  assert.equal(status_of_value(0.1), 'weak')
  assert.equal(status_of_value(0.4), 'fair')
  assert.equal(status_of_value(0.69), 'fair')
  assert.equal(status_of_value(0.7), 'good')
  assert.equal(status_of_value(1), 'mastered')
})

test('最近几次对错：从旧到新，对和错分开', () => {
  assert.deepEqual(recent_marks(['right', 'wrong']), [
    { key: 0, right: true, label: '对' },
    { key: 1, right: false, label: '错' },
  ])
  assert.deepEqual(recent_marks(undefined), [])
})

test('明细行：状态文字、颜色、待重做题数', () => {
  const row = point_row(NODES[0])
  assert.equal(row.status_text, '薄弱')
  assert.equal(row.tone, 'coral')
  assert.equal(row.pending, 2)
  assert.equal(row.recent.length, 3)
  // 没有 status 字段时按掌握度算；没有 pending 时是 0
  const fallback = point_row({ id: 5, name: 'x', level: 2, parent_id: 1, value: 0.8 })
  assert.equal(fallback.status, 'good')
  assert.equal(fallback.status_text, '较好')
  assert.equal(fallback.pending, 0)
  assert.equal(point_row({ id: 6, name: 'y', value: null }).status_text, '还没学')
})

test('模块小结', () => {
  const rows = NODES.slice(0, 2).map(point_row)
  assert.deepEqual(module_summary(rows), { total: 2, mastered: 1, weak: 1, pending: 2 })
})

test('按模块分组：模块顺序照接口，空模块不显示，找不到模块的放最后', () => {
  const groups = group_points(NODES)
  assert.deepEqual(groups.map(group => group.name), ['有理数', '几何图形', '其他考点'])
  assert.deepEqual(groups[0].rows.map(row => row.name), ['乘方', '混合运算'])
  assert.equal(groups[0].summary.mastered, 1)
  assert.equal(groups[2].rows[0].id, 31)
  assert.deepEqual(group_points(undefined), [])
})

test('点一行去错题页的地址', () => {
  assert.deepEqual(point_query(1, { id: 11, parent_id: 1 }), {
    tab: 'all', subject_id: '1', knowledge_parent_id: '1', knowledge_point_id: '11',
  })
  assert.deepEqual(point_query(2, { id: 31, parent_id: null }), {
    tab: 'all', subject_id: '2', knowledge_point_id: '31',
  })
})

test('单词复习频率：补齐没复习的日子，跨月也对', () => {
  const rows = [{ date: '2026-10-30', count: 3 }, { date: '2026-11-02', count: 5 }, { date: '2026-08-01', count: 9 }]
  const points = daily_counts(rows, '2026-11-02', 5)
  assert.deepEqual(points, [
    { date: '2026-10-29', count: 0 },
    { date: '2026-10-30', count: 3 },
    { date: '2026-10-31', count: 0 },
    { date: '2026-11-01', count: 0 },
    { date: '2026-11-02', count: 5 },
  ])
  assert.equal(daily_counts([], '2026-11-21').length, 60)
})

test('频率折线图配置用主题颜色，横轴只显示月-日', () => {
  const theme = { text: '#111', line: '#222', main: '#333', soft: '#444' }
  const option = frequency_option([{ date: '2026-11-01', count: 2 }], theme)
  assert.deepEqual(option.color, ['#333'])
  assert.deepEqual(option.series[0].data, [2])
  assert.equal(option.xAxis.axisLabel.formatter('2026-11-01'), '11-01')
  assert.equal(option.xAxis.axisLabel.color, '#111')
})
