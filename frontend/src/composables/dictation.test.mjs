import test from 'node:test'
import assert from 'node:assert/strict'
import { buildCells, blankTokenCount, judge, shouldPlayBeforeAnswer, diffAnswer, answerSegments } from './dictation.js'

// 把片段数组还原成仅标红部分的字符串，便于断言
const wrongText = segs => segs.filter(s => s.wrong).map(s => s.text).join('|')
const joined = segs => segs.map(s => s.text).join('')

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
test('diffAnswer：完全一致时无错', () => {
  const d = diffAnswer('be good at', 'be good at')
  assert.equal(wrongText(d.expected), '')
  assert.equal(wrongText(d.actual), '')
  assert.equal(joined(d.expected), 'be good at')
  assert.equal(joined(d.actual), 'be good at')
})
test('diffAnswer：只有不同的那个字母算错', () => {
  const d = diffAnswer('earthquake drills', 'earthqueke drills')
  assert.equal(wrongText(d.expected), 'a')   // 正确答案里的 a 漏了
  assert.equal(wrongText(d.actual), 'e')     // 作答里多出的 e
})
test('diffAnswer：整词不同只标该词', () => {
  const d = diffAnswer('be proud of', 'be proud at')
  assert.equal(wrongText(d.expected), 'of')
  assert.equal(wrongText(d.actual), 'at')
})
test('diffAnswer：只写了开头', () => {
  const d = diffAnswer('missing', 'm')
  assert.equal(wrongText(d.expected), 'issing')
  assert.equal(wrongText(d.actual), '')      // 作答没有多余错误部分
})
test('diffAnswer：没有作答', () => {
  const d = diffAnswer('missing', '')
  assert.equal(wrongText(d.expected), 'missing')
  assert.deepEqual(d.actual, [])
})
test('diffAnswer：不区分大小写', () => {
  const d = diffAnswer('Apple', 'apple')
  assert.equal(wrongText(d.expected), '')
  assert.equal(joined(d.expected), 'Apple')  // 保留原大小写
})
test('diffAnswer：多写的字母', () => {
  const d = diffAnswer('blog', 'bloog')
  assert.equal(wrongText(d.expected), '')
  assert.equal(wrongText(d.actual), 'o')     // 多出的一个 o
})
test('diffAnswer：下划线按普通字符处理', () => {
  const d = diffAnswer('a___ of', 'a of')
  assert.equal(wrongText(d.expected), '___')
})
test('answerSegments：有逐词结果时优先按词标红', () => {
  const seg = answerSegments({ english: 'be good at', userAnswer: 'be good in', tokenResults: [{ i: 2, ok: false }] })
  assert.equal(wrongText(seg.expected), 'at')   // 第 2 个词判错
  assert.equal(wrongText(seg.actual), 'in')     // 作答侧仍按字符对比
})
test('answerSegments：无逐词结果回退到字符对比', () => {
  const seg = answerSegments({ english: 'apple', user_answer: 'aple' })
  assert.equal(wrongText(seg.expected), 'p')
})
test('发音规则', () => {
  assert.equal(shouldPlayBeforeAnswer({ english: 'apple' }, 1), true)
  assert.equal(shouldPlayBeforeAnswer({ ...goodAt, dictation_level: 1 }, 1), false)
  assert.equal(shouldPlayBeforeAnswer({ ...goodAt, dictation_level: 2 }, 1), false)
  assert.equal(shouldPlayBeforeAnswer({ ...goodAt, dictation_level: 3 }, 1), true)
  assert.equal(shouldPlayBeforeAnswer({ ...goodAt, dictation_level: 1 }, 3), true)    // 听力题型照旧
})
