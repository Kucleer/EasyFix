import test from 'node:test'
import assert from 'node:assert/strict'
import { paperTypeLabel, reasonLabels, scoreText, groupByPaper, pageImage } from './intakeLabels.js'

test('卷子类型显示', () => {
  assert.equal(paperTypeLabel({ paper_type: 'homework' }), '作业')
  assert.equal(paperTypeLabel({ paper_type: 'exam', exam_kind: 'midterm' }), '考试 · 期中')
  assert.equal(paperTypeLabel({ paper_type: 'exam', exam_kind: 'other' }), '考试')
  assert.equal(paperTypeLabel({ paper_type: 'quiz' }), 'quiz')
  assert.equal(paperTypeLabel(null), '')
})
test('待核对原因转中文', () => {
  assert.deepEqual(reasonLabels(['wrong_unclear', 'kp_unsure']), ['不确定是否做错', '考点拿不准'])
  assert.deepEqual(reasonLabels(['mystery']), ['mystery'])
  assert.deepEqual(reasonLabels(null), [])
})
test('分数显示', () => {
  assert.equal(scoreText({ score: 85, full_score: 100 }), '85 / 100')
  assert.equal(scoreText({ score: 85.5, full_score: 100 }), '85.5 / 100')
  assert.equal(scoreText({ score: 0, full_score: 100 }), '0 / 100')
  assert.equal(scoreText({ score: null, full_score: null }), '')
})
test('按卷子分组并保持顺序', () => {
  const a = { id: 1, name: 'A' }, b = { id: 2, name: 'B' }
  const groups = groupByPaper([{ id: 10, paper: a }, { id: 11, paper: null }, { id: 12, paper: b }, { id: 13, paper: a }])
  assert.deepEqual(groups.map(g => [g.paper?.id ?? null, g.questions.map(q => q.id)]), [[1, [10, 13]], [2, [12]], [null, [11]]])
})
test('页面照片地址', () => {
  assert.equal(pageImage({ original_image: '2026/11/ab12cd34_p1.jpg' }), '/uploads/2026/11/ab12cd34_p1.jpg')
  assert.equal(pageImage({ original_image: null }), null)
})
