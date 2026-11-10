import test from 'node:test'
import assert from 'node:assert/strict'
import { buildCells, blankTokenCount, judge, shouldPlayBeforeAnswer } from './dictation.js'

const cloze = q => buildCells(q).map(c => (c.gapBefore ? ' ' : '') + (c.fixed ? c.char : '_')).join('')
// 有 tokens 时词间空格不是格子，所以先去掉空格再按格下标取字母；无 tokens 时空格是预填格，原样取
const fill = (q, text) => {
  const t = q.tokens ? text.replace(/ /g, '') : text
  return buildCells(q).map((c, i) => (c.fixed ? c.char : t[i]))
}
const goodAt = { english: 'be good at', tokens: [
  { text: 'be', blank: false, hint: null }, { text: 'good', blank: false, hint: null }, { text: 'at', blank: true, hint: null }] }

test('无 tokens 时与旧字母格一致', () => {
  assert.equal(cloze({ english: "what's up?" }), "____'_ __?")
  assert.equal(blankTokenCount({ english: 'apple' }), 1)
})
test('只空出标记为 blank 的词', () => {
  assert.equal(cloze(goodAt), 'be good __')
  assert.equal(blankTokenCount(goodAt), 1)
})
test('空出的词里非字母字符预填', () => {          // Review Focus 2
  const q = { english: "do one's best", tokens: [
    { text: 'do', blank: false, hint: null }, { text: "one's", blank: true, hint: null }, { text: 'best', blank: true, hint: null }] }
  assert.equal(cloze(q), "do ___'_ ____")
})
test('提示默写首字母固定', () => {
  const q = { english: 'take part', tokens: [{ text: 'take', blank: true, hint: 't' }, { text: 'part', blank: true, hint: 'p' }] }
  assert.equal(cloze(q), 't___ p___')
})
test('按词判对，不区分大小写', () => {
  const q = { english: 'be Proud of', tokens: [
    { text: 'be', blank: false, hint: null }, { text: 'Proud', blank: true, hint: null }, { text: 'of', blank: true, hint: null }] }
  assert.deepEqual(judge(q, fill(q, 'be proud of')), { correct: true, userAnswer: 'be proud of', tokenResults: [{ i: 1, ok: true }, { i: 2, ok: true }] })
  const wrong = judge(q, fill(q, 'be pruod of'))
  assert.equal(wrong.correct, false)
  assert.deepEqual(wrong.tokenResults, [{ i: 1, ok: false }, { i: 2, ok: true }])
  assert.equal(judge(q, buildCells(q).map(c => (c.fixed ? c.char : ''))).correct, false)   // 留空算错
})
test('无 tokens 时 tokenResults 为 null', () => {
  assert.deepEqual(judge({ english: 'Apple' }, 'apple'.split('')), { correct: true, userAnswer: 'apple', tokenResults: null })
})
test('发音规则', () => {
  assert.equal(shouldPlayBeforeAnswer({ english: 'apple' }, 1), true)
  assert.equal(shouldPlayBeforeAnswer({ ...goodAt, dictation_level: 1 }, 1), false)
  assert.equal(shouldPlayBeforeAnswer({ ...goodAt, dictation_level: 2 }, 1), false)
  assert.equal(shouldPlayBeforeAnswer({ ...goodAt, dictation_level: 3 }, 1), true)
  assert.equal(shouldPlayBeforeAnswer({ ...goodAt, dictation_level: 1 }, 3), true)    // 听力题型照旧
})
