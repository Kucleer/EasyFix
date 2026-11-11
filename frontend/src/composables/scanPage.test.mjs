import test from 'node:test'
import assert from 'node:assert/strict'
import {
  FLAG_TEXTS, warningTexts, stepLabel, hasWarning, acceptAllSeqs, groupItems,
  progressCounts, unsureHint, MAX_UPLOAD_BYTES, needsCompression, scaledSize,
  pageSummary, itemLabel, gradeTermText, knowledgeText, editableFields, zoomAt,
  acceptFailureAction, acceptAllProgressText, runAcceptAll,
} from './scanPage.js'

test('分组', () => {
  const items = [
    { seq: 0, verdict: 'wrong', source: 'model', state: 'open' },
    { seq: 1, verdict: 'right', source: 'model', state: 'open' },
    { seq: 2, verdict: 'unsure', source: 'model', state: 'dismissed' },
    { seq: 3, verdict: 'wrong', source: 'promoted', state: 'accepted' },
    { seq: 4, verdict: 'wrong', source: 'manual', state: 'open' },
  ]
  const { main, right } = groupItems(items)
  assert.deepEqual(main.map(i => i.seq), [0, 3, 4])
  assert.deepEqual(right.map(i => i.seq), [1])
  assert.deepEqual(progressCounts(items), { accepted: 1, remaining: 2 })
})

test('全部录入只含无提示的做错题', () => {
  // 九种情况：未处理 / 已录入 / 已去掉，做错 / 拿不准 / 做对，有无提示、是否改过，手工加的是否保存过
  const items = [
    { seq: 0, state: 'open', verdict: 'wrong', flags: [], edited: false },
    { seq: 1, state: 'open', verdict: 'wrong', flags: ['merged'], edited: false },
    { seq: 2, state: 'open', verdict: 'wrong', flags: ['merged'], edited: true },
    { seq: 3, state: 'open', verdict: 'unsure', flags: [], edited: false },
    { seq: 4, state: 'accepted', verdict: 'wrong', flags: [], edited: false },
    { seq: 5, state: 'dismissed', verdict: 'wrong', flags: [], edited: false },
    { seq: 6, state: 'open', verdict: 'right', flags: [], edited: false },
    // 手工加的题：没保存过的不算，保存过的算
    { seq: 7, state: 'open', verdict: 'wrong', flags: [], edited: false, source: 'manual' },
    { seq: 8, state: 'open', verdict: 'wrong', flags: [], edited: true, source: 'manual' },
  ]
  assert.deepEqual(acceptAllSeqs(items), [0, 2, 8])
  assert.equal(hasWarning(items[1]), true)
  assert.equal(hasWarning(items[2]), false)
})

test('提示文字', () => {
  assert.deepEqual(warningTexts({ flags: ['broken_formula'] }), ['公式可能读错，请对照原图'])
  assert.deepEqual(warningTexts({ flags: [] }), [])
  assert.deepEqual(warningTexts({}), [])
  assert.deepEqual(warningTexts({ flags: ['unknown_flag'] }), [])
  assert.equal(FLAG_TEXTS.figure_needed, '这题有图，请对照原图补条件')
  assert.equal(stepLabel('rescanning'), '正在重扫一次')
  assert.equal(stepLabel('uploaded'), '正在读图')
  assert.equal(stepLabel('reading'), '正在读图')
  assert.equal(stepLabel('analyzing'), '正在整理题目')
  assert.equal(stepLabel('ready'), '')
  assert.equal(unsureHint({ verdict: 'unsure', reason: '' }), '没看清孩子的答案，请对照原图判断')
  assert.equal(unsureHint({ verdict: 'unsure', reason: '字迹潦草' }), '模型拿不准：字迹潦草')
  assert.equal(unsureHint({ verdict: 'wrong', reason: 'x' }), '')
})

test('压缩', () => {
  assert.equal(MAX_UPLOAD_BYTES, 10 * 1024 * 1024)
  assert.equal(needsCompression(10 * 1024 * 1024), false)
  assert.equal(needsCompression(10 * 1024 * 1024 + 1), true)
  assert.deepEqual(scaledSize(6000, 4000, 3000), { width: 3000, height: 2000 })
  assert.deepEqual(scaledSize(4000, 6000, 3000), { width: 2000, height: 3000 })
  assert.deepEqual(scaledSize(1000, 800, 3000), { width: 1000, height: 800 })
})

test('整理区顶部统计与题目名称', () => {
  const items = [
    { seq: 0, source: 'model', verdict: 'wrong' },
    { seq: 1, source: 'model', verdict: 'unsure' },
    { seq: 2, source: 'promoted', verdict: 'wrong' },
    { seq: 3, source: 'model', verdict: 'right' },
    { seq: 4, source: 'manual', verdict: 'wrong' },
  ]
  // 手工加的不算识别出的；补成错题的原本判对，不算模型判错
  assert.deepEqual(pageSummary(items), { total: 4, wrong: 1 })
  assert.equal(itemLabel({ question_no: '3' }), '第 3 题')
  assert.equal(itemLabel({ question_no: '  ' }), '没填题号的题')
  assert.equal(gradeTermText(6, 1), '六年级上')
  assert.equal(gradeTermText(8, 2), '初二下')
  assert.equal(gradeTermText(10, null), '高一')
  assert.equal(gradeTermText(null, 1), '')
})

test('考点名称：主考点在前，未知编号忽略', () => {
  const names = { 1: '分数乘法', 2: '列代数式', 3: '约分' }
  assert.equal(knowledgeText([1, 2, 3], 2, names), '列代数式、分数乘法、约分')
  assert.equal(knowledgeText([1, 99], null, names), '分数乘法')
  assert.equal(knowledgeText([], null, names), '')
})

test('修改表单的初值是可编辑字段的副本', () => {
  const item = {
    seq: 1, question_no: '2', parsed_question: 'q', wrong_answer: 'w', answer: 'a', analysis: 'n',
    knowledge_point_ids: [5], primary_knowledge_point_id: 5, error_types: ['计算错误'], difficulty: 4,
    state: 'open', flags: ['merged'],
  }
  const fields = editableFields(item)
  assert.deepEqual(fields, {
    question_no: '2', parsed_question: 'q', wrong_answer: 'w', answer: 'a', analysis: 'n',
    knowledge_point_ids: [5], primary_knowledge_point_id: 5, error_types: ['计算错误'], difficulty: 4,
  })
  fields.knowledge_point_ids.push(6)
  fields.error_types.push('x')
  assert.deepEqual(item.knowledge_point_ids, [5])
  assert.deepEqual(item.error_types, ['计算错误'])
  // 空值补成默认
  assert.deepEqual(editableFields({ seq: 0 }), {
    question_no: '', parsed_question: '', wrong_answer: '', answer: '', analysis: '',
    knowledge_point_ids: [], primary_knowledge_point_id: null, error_types: [], difficulty: 3,
  })
})

test('录入失败后的处理：409 刷新，其他 4xx 进修改状态，其余只提示', () => {
  assert.equal(acceptFailureAction(409), 'refresh')
  assert.equal(acceptFailureAction(422), 'edit')
  assert.equal(acceptFailureAction(400), 'edit')
  assert.equal(acceptFailureAction(502), 'report')
  assert.equal(acceptFailureAction(undefined), 'report')  // 网络断开、超时：没有状态码
})

test('全部录入的进度文字', () => {
  assert.equal(acceptAllProgressText(0, 5), '正在录入 1/5')
  assert.equal(acceptAllProgressText(1, 5), '正在录入 2/5')
})

test('全部录入：按顺序逐道录入，全部成功', async () => {
  const called = []
  const progress = []
  const result = await runAcceptAll([0, 2, 8], async (seq) => { called.push(seq) },
    (index, total) => progress.push(acceptAllProgressText(index, total)))
  assert.deepEqual(called, [0, 2, 8])
  assert.deepEqual(progress, ['正在录入 1/3', '正在录入 2/3', '正在录入 3/3'])
  assert.deepEqual(result, { accepted: 3, failedSeq: null, error: null })
})

test('全部录入：停在第一道失败的题，后面的不再录，已录的不受影响', async () => {
  const called = []
  const rejected = { response: { status: 422, data: { detail: '公式写坏了' } } }
  const result = await runAcceptAll([0, 2, 8], async (seq) => {
    called.push(seq)
    if (seq === 2) throw rejected
  })
  assert.deepEqual(called, [0, 2])
  assert.equal(result.accepted, 1)
  assert.equal(result.failedSeq, 2)
  assert.equal(result.error, rejected)
  // 没有候选时什么都不做
  assert.deepEqual(await runAcceptAll([], async () => { throw new Error('不该调用') }),
    { accepted: 0, failedSeq: null, error: null })
})

test('原图缩放：围绕指针缩放，限制在 1 到 4 倍', () => {
  const start = { scale: 1, x: 0, y: 0 }
  // 在 (100, 50) 处放大 2 倍：这一点在图上的位置不动
  assert.deepEqual(zoomAt(start, { x: 100, y: 50 }, 2), { scale: 2, x: -100, y: -50 })
  // 超过 4 倍按 4 倍算
  assert.deepEqual(zoomAt({ scale: 3, x: 0, y: 0 }, { x: 0, y: 0 }, 2), { scale: 4, x: 0, y: 0 })
  // 缩回 1 倍时位置复位
  assert.deepEqual(zoomAt({ scale: 2, x: -100, y: -50 }, { x: 10, y: 10 }, 0.25), { scale: 1, x: 0, y: 0 })
})
