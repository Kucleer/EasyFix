import test from 'node:test'
import assert from 'node:assert/strict'
import {
  REASON_LABELS, groupByModule, swapItem, removeItem, toggleForm, createPayload,
  summary, initialMarks, toggleMark, gradePayload, countWrong, paperLabel,
  resumeLink, canResume, pendingSimilarCount,
  recognitionMap, marksFromRecognition, countUnsure, focusIds, visibleQuestions, shownForm, numberingChanged,
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
})

test('卷子标签：默认名已含日期时不重复追加日期', () => {
  assert.equal(paperLabel({ id: 128, name: '数学练习卷 11月12日', created_at: '2026-11-12T08:00:00' }), '#128 数学练习卷 11月12日')
})

test('卷子标签：名字为空时用创建日期', () => {
  assert.equal(paperLabel({ id: 128, name: '', created_at: '2026-11-15T08:00:00' }), '#128 11月15日')
  assert.equal(paperLabel({ id: 128, name: '  ', created_at: '2026-11-15T08:00:00' }), '#128 11月15日')
})

test('没批改的考点卷从练习中心回到出卷页；已批改、别的练习不跳', () => {
  assert.equal(resumeLink({ id: 7, kind: 'targeted', reviewed: false }), '/targeted-paper?paper_id=7')
  assert.equal(resumeLink({ id: 7, kind: 'targeted', reviewed: true }), null)
  assert.equal(resumeLink({ id: 7, kind: 'manual', reviewed: false }), null)
  assert.equal(resumeLink({ id: 7, reviewed: false }), null)
})

test('出卷页能不能接着准备一份卷子', () => {
  assert.equal(canResume({ id: 7, kind: 'targeted', reviewed: false, deleted: 0 }), true)
  assert.equal(canResume({ id: 7, kind: 'targeted', reviewed: true }), false)
  assert.equal(canResume({ id: 7, kind: 'targeted', reviewed: false, deleted: 1 }), false)
  assert.equal(canResume({ id: 7, kind: 'manual', reviewed: false }), false)
  assert.equal(canResume(null), false)
})

test('还没准备的相似题数', () => {
  const questions = [
    { form: 'similar', similar_question_id: null },
    { form: 'similar', similar_question_id: 5 },
    { form: 'original', similar_question_id: null },
  ]
  assert.equal(pendingSimilarCount(questions), 1)
  assert.equal(pendingSimilarCount(undefined), 0)
})

// ---------------------------------------------------------------- 批改识别预批

const review_questions = [{ id: 1 }, { id: 2 }, { id: 3 }, { id: 4 }]
const recognized = [
  { id: 1, verdict: 'right', student_answer: '5x', page: 1 },
  { id: 2, verdict: 'wrong', student_answer: '8', page: 1 },
  { id: 3, verdict: 'unsure', student_answer: '', page: null },
]

test('预批合并成初始标记：对、错照搬，拿不准和没有结果的题都是拿不准', () => {
  assert.deepEqual(marksFromRecognition(review_questions, recognized), { 1: 'right', 2: 'wrong', 3: 'unsure', 4: 'unsure' })
  assert.deepEqual(marksFromRecognition(review_questions, []), { 1: 'unsure', 2: 'unsure', 3: 'unsure', 4: 'unsure' })
  assert.equal(recognitionMap(recognized)[2].student_answer, '8')
})

test('拿不准没处理时不能提交', () => {
  const marks = marksFromRecognition(review_questions, recognized)
  assert.equal(countUnsure(marks), 2)
  assert.throws(() => gradePayload(review_questions.map(q => ({ ...q, question_id: q.id })), marks, 0))
  const done = { ...marks, 3: 'right', 4: 'not_done' }
  assert.equal(countUnsure(done), 0)
  const payload = gradePayload(review_questions.map(q => ({ ...q, question_id: q.id * 10 })), done, 2)
  assert.deepEqual(payload.question_results.map(r => r.is_correct), [true, false, true, null])
  assert.equal(payload.grading_revision, 2)
})

test('只看错的和拿不准的：名单在预批时定下，按卷面题号排', () => {
  const focus = focusIds(marksFromRecognition(review_questions, recognized))
  assert.deepEqual([...focus].sort(), [2, 3, 4])
  assert.deepEqual(visibleQuestions(review_questions, focus, true).map(q => q.id), [2, 3, 4])
  assert.deepEqual(visibleQuestions(review_questions, focus, false).map(q => q.id), [1, 2, 3, 4])
})

test('卷面题面和题号是否错开', () => {
  assert.equal(shownForm({ shown_form: 'similar', form: 'original' }), 'similar')
  assert.equal(shownForm({ form: null }), 'original')
  assert.equal(numberingChanged({ kind: 'manual', total_questions: 3, questions: [{}, {}] }), true)
  assert.equal(numberingChanged({ kind: 'manual', total_questions: 2, questions: [{}, {}] }), false)
  assert.equal(numberingChanged({ kind: 'targeted', total_questions: 3, questions: [{}] }), false)
})
