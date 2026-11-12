import test from 'node:test'
import assert from 'node:assert/strict'
import {
  REASON_LABELS, groupByModule, swapItem, removeItem, toggleForm, createPayload,
  summary, initialMarks, toggleMark, gradePayload, countWrong, paperLabel,
} from './targetedPaper.js'

const make_plan = () => ({
  items: [
    { question_id: 11, point_id: 101, module_id: 1, module_name: '代数', reason: 'new', form: 'original' },
    { question_id: 12, point_id: 102, module_id: 2, module_name: '几何', reason: 'check', form: 'similar' },
    { question_id: 13, point_id: 101, module_id: 1, module_name: '代数', reason: 'wrong', form: 'original' },
  ],
  reserve: { 101: [{ question_id: 21 }, { question_id: 22 }] },
})

test('标签', () => { assert.equal(REASON_LABELS.spot, '抽查') })

test('分组保持出现先后', () => {
  const g = groupByModule(make_plan().items)
  assert.deepEqual(g.map(x => [x.module_id, x.items.length]), [[1, 2], [2, 1]])
})

test('换一道：用同考点的备选替换，被换下的放到备选末尾', () => {
  const plan = make_plan()
  const next = swapItem(plan, 0)
  assert.equal(next.items[0].question_id, 21)
  assert.deepEqual(next.reserve[101].map(i => i.question_id), [22, 11])
  assert.equal(plan.items[0].question_id, 11)
})

test('换一道：没有备选、抽查题原样返回', () => {
  const plan = make_plan()
  assert.equal(swapItem(plan, 1), plan)
  const spot = { items: [{ question_id: 1, point_id: 101, reason: 'spot', form: 'original' }], reserve: { 101: [{ question_id: 2 }] } }
  assert.equal(swapItem(spot, 0), spot)
})

test('删除一道', () => {
  const plan = make_plan()
  assert.deepEqual(removeItem(plan, 0).items.map(i => i.question_id), [12, 13])
  assert.equal(plan.items.length, 3)
})

test('切换形式：check 的题不变', () => {
  const plan = make_plan()
  assert.equal(toggleForm(plan, 0).items[0].form, 'similar')
  assert.equal(toggleForm(plan, 1), plan)
  assert.equal(plan.items[0].form, 'original')
})

test('请求体和汇总', () => {
  const plan = make_plan()
  const body = createPayload(3, '卷', plan)
  assert.deepEqual(body.items[0], { question_id: 11, point_id: 101, reason: 'new', form: 'original' })
  assert.equal(body.subject_id, 3)
  assert.deepEqual(summary(plan), { total: 3, points: 2, similar: 1 })
})

test('批改标记：默认全对，点一下变错，再点变回来', () => {
  const marks = initialMarks([{ id: 1, is_correct: null }, { id: 2, is_correct: false }, { id: 3, is_correct: null, skip_reason: 'not_done' }])
  assert.deepEqual(marks, { 1: 'right', 2: 'wrong', 3: 'not_done' })
  assert.equal(toggleMark('right'), 'wrong'); assert.equal(toggleMark('wrong'), 'right'); assert.equal(toggleMark('bad_question'), 'right')
})

test('提交内容：跳过的题结果为空并带原因', () => {
  const body = gradePayload([{ id: 1, question_id: 9 }, { id: 2, question_id: 8 }], { 1: 'wrong', 2: 'bad_question' }, 3)
  assert.deepEqual(body, { question_results: [{ question_id: 9, is_correct: false, skip_reason: null }, { question_id: 8, is_correct: null, skip_reason: 'bad_question' }], grading_revision: 3 })
})

test('错题数和卷子标签', () => {
  assert.equal(countWrong({ 1: 'wrong', 2: 'right', 3: 'wrong' }), 2)
  assert.equal(paperLabel({ id: 128, name: '数学练习卷', created_at: '2026-11-15T08:00:00' }), '#128 数学练习卷 11月15日')
})
