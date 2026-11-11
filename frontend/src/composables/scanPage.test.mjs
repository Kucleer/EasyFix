import test from 'node:test'
import assert from 'node:assert/strict'
import {
  FLAG_TEXTS, warningTexts, stepLabel, hasWarning, acceptAllSeqs, groupItems,
  progressCounts, unsureHint, MAX_UPLOAD_BYTES, needsCompression, scaledSize,
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
  // 与后端 test_accept_all_and_warning 的七项一致
  const items = [
    { seq: 0, state: 'open', verdict: 'wrong', flags: [], edited: false },
    { seq: 1, state: 'open', verdict: 'wrong', flags: ['merged'], edited: false },
    { seq: 2, state: 'open', verdict: 'wrong', flags: ['merged'], edited: true },
    { seq: 3, state: 'open', verdict: 'unsure', flags: [], edited: false },
    { seq: 4, state: 'accepted', verdict: 'wrong', flags: [], edited: false },
    { seq: 5, state: 'dismissed', verdict: 'wrong', flags: [], edited: false },
    { seq: 6, state: 'open', verdict: 'right', flags: [], edited: false },
  ]
  assert.deepEqual(acceptAllSeqs(items), [0, 2])
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
