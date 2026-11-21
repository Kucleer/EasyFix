// 设置页纯函数测试：node --test frontend/src/components/settings/settingsModel.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import {
  SETTINGS_TABS, GRADE_OPTIONS, join_desc, format_stock, format_signed, read_saved_number,
  knowledge_query, pick_legacy, with_subject_names, subject_rows, tag_rows, knowledge_rows,
  legacy_rows, book_rows, star_action_rows, achievement_rows, reward_rows,
} from './settingsModel.js'

/** 只取每行的标签和禁用状态，方便比较 */
const labels = row => row.actions.map(a => [a.label, Boolean(a.disabled), Boolean(a.danger)])

test('标签栏：七个标签，顺序固定', () => {
  assert.deepEqual(SETTINGS_TABS.map(t => t.label), ['年级与学期', '学科', '标签', '知识点', '错题本', '知识星空', '模型'])
  assert.equal(GRADE_OPTIONS.length, 12)
  assert.equal(GRADE_OPTIONS[6].label, '初一')
})

test('join_desc / format_stock / format_signed', () => {
  assert.equal(join_desc('数学', '', null, undefined, '3 题'), '数学 · 3 题')
  assert.equal(format_stock(-1), '无限')
  assert.equal(format_stock(5), 5)
  assert.equal(format_signed(3), '+3')
  assert.equal(format_signed(0), '+0')
  assert.equal(format_signed(-2), '-2')
})

test('read_saved_number：空串、缺失、非数字都是 null', () => {
  const store = { a: '3', b: '', c: 'x' }
  const storage = { getItem: key => (key in store ? store[key] : null) }
  assert.equal(read_saved_number(storage, 'a'), 3)
  assert.equal(read_saved_number(storage, 'b'), null)
  assert.equal(read_saved_number(storage, 'c'), null)
  assert.equal(read_saved_number(storage, 'd'), null)
  assert.equal(read_saved_number({ getItem() { throw new Error('blocked') } }, 'a'), null)
  assert.equal(read_saved_number(undefined, 'a'), null)
})

test('knowledge_query 只带有值的筛选项', () => {
  assert.deepEqual(knowledge_query({ subject_id: 1, grade: null, semester: 2, keyword: '' }), { subject_id: 1, semester: 2 })
  assert.deepEqual(knowledge_query({}), {})
})

test('pick_legacy：数组或 {items}，只留 legacy', () => {
  assert.deepEqual(pick_legacy([{ id: 1, legacy: true }, { id: 2 }]), [{ id: 1, legacy: true }])
  assert.deepEqual(pick_legacy({ items: [{ id: 3, legacy: 1 }] }), [{ id: 3, legacy: 1 }])
  assert.deepEqual(pick_legacy(null), [])
})

test('with_subject_names 补学科名，找不到为空串', () => {
  const books = [{ id: 1, subject_id: 2 }, { id: 2, subject_id: 9 }]
  const result = with_subject_names(books, [{ id: 2, name: '英语' }])
  assert.equal(result[0].subject_name, '英语')
  assert.equal(result[1].subject_name, '')
})

test('学科、标签行', () => {
  const removed = []
  const rows = subject_rows([{ id: 4, name: '数学' }], { remove: row => removed.push(row.id) })
  assert.equal(rows[0].desc, 'ID 4')
  rows[0].actions[0].run()
  assert.deepEqual(removed, [4])
  const tags = tag_rows([{ id: 1, name: '粗心', color: '#f00' }, { id: 2, name: '其他' }], { remove() {} })
  assert.equal(tags[0].color, '#f00')
  assert.equal(tags[0].desc, '颜色 #f00')
  assert.equal(tags[1].desc, '默认颜色')
})

test('知识点树摊平：一级在前、二级缩进，一级多一个"新增二级"', () => {
  const calls = []
  const handlers = {
    edit: row => calls.push(['edit', row.id]),
    add_child: row => calls.push(['add', row.id]),
    remove: row => calls.push(['remove', row.id]),
  }
  const tree = [{
    id: 1, name: '数与代数', level: 1, subject_name: '数学', child_count: 2, question_count: 5,
    children: [{ id: 2, name: '分数', level: 2, subject_name: '数学', question_count: 3 }],
  }]
  const rows = knowledge_rows(tree, handlers)
  assert.equal(rows.length, 2)
  assert.equal(rows[0].is_parent, true)
  assert.equal(rows[0].desc, '数学 · 子级 2 个 · 5 题')
  assert.deepEqual(labels(rows[0]), [['编辑', false, false], ['新增二级', false, false], ['删除', false, true]])
  assert.equal(rows[1].is_child, true)
  assert.equal(rows[1].desc, '数学 · 3 题')
  assert.deepEqual(labels(rows[1]), [['编辑', false, false], ['删除', false, true]])
  rows[0].actions[1].run()
  rows[1].actions[1].run()
  assert.deepEqual(calls, [['add', 1], ['remove', 2]])
  assert.deepEqual(knowledge_rows(null, handlers), [])
})

test('旧目录：有题目引用时不能软删除', () => {
  const rows = legacy_rows([
    { id: 7, name: '旧', subject_name: '数学', question_count: 2 },
    { id: 8, name: '空', question_count: 0 },
  ], { promote() {}, remove() {} })
  assert.equal(rows[0].desc, '数学 · 2 题 · ID 7')
  assert.deepEqual(labels(rows[0]), [['转为二级', false, false], ['软删除', true, true]])
  assert.deepEqual(labels(rows[1]), [['转为二级', false, false], ['软删除', false, true]])
})

test('错题本、积分行为、成就、奖励行', () => {
  const noop = { edit() {}, remove() {} }
  assert.equal(book_rows([{ id: 1, name: '本', subject_name: '数学', description: '期中' }], noop)[0].desc, '数学 · 期中')
  const actions = star_action_rows([{ id: 1, name: '上传', star_value: 2, is_custom: false, enabled: false, is_preset: true }], noop)
  assert.equal(actions[0].desc, '+2 积分 · 预设 · 已停用')
  assert.deepEqual(labels(actions[0]), [['编辑', false, false], ['删除', true, true]])
  const achievements = achievement_rows([{ id: 1, name: '达人', level: 2, trigger_action: 'upload', trigger_count: 10, reward_stars: 5, is_preset: true }], noop)
  assert.equal(achievements[0].desc, '等级 2 · upload × 10 · 奖励 5 积分')
  assert.deepEqual(labels(achievements[0]), [['编辑', true, false], ['删除', true, true]])
  const rewards = reward_rows([{ id: 1, name: '卡', cost_stars: 30, remaining_stock: -1, total_stock: 4 }], noop)
  assert.equal(rewards[0].desc, '30 积分 · 剩余 无限 / 总 4')
})
