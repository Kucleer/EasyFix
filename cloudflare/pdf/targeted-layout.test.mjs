// 考点卷版式的测试：node --test cloudflare/pdf/targeted-layout.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { targetedBody, targetedQuestionCount, TARGETED_STYLE } from './targeted-layout.js'

const payload = {
  template_version: '3', layout: 'targeted', title: '考点卷7', code: '#7',
  groups: [
    { title: '一、有理数（2 题）', questions: [
      { number: 1, question_text: '题一 <b>', option_a: null, option_b: null, option_c: null, option_d: null, space: 's' },
      { number: 2, question_text: '题二', option_a: '甲', option_b: '乙', option_c: null, option_d: null, space: 'l' }] },
    { title: '二、线段与角（1 题）', questions: [
      { number: 3, question_text: '题三', option_a: null, option_b: null, option_c: null, option_d: null, space: 'm' }] }],
  answers: [
    { number: 1, answer: '答案一', analysis: '解析一', point: '有理数 / 加法', form: '原题', reason: '新错题' },
    { number: 2, answer: 'B', analysis: '', point: '有理数 / 乘方', form: '相似题', reason: '上次做错' },
    { number: 3, answer: '答案三', analysis: '解析三', point: '线段与角 / 线段', form: '原题', reason: '抽查' }],
  footer: '手机上从首页的"专项练习"进待批改，找到 #7'
}
const field = (text, label) => `<i data-label="${label}">${text}</i>`
const escape = value => String(value ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]))

test('题号连续，分组标题和答案页都在', () => {
  const html = targetedBody(payload, field, String)
  assert.ok(html.indexOf('一、有理数（2 题）') < html.indexOf('二、线段与角（1 题）'))
  assert.match(html, /class="answers"/)
  assert.ok(html.includes('答案与解析（家长用）') && html.includes('#7'))
  assert.equal((html.match(/class="question"/g) || []).length, 3)
  assert.ok(!html.includes('知识点：') && !html.includes('ID:'))
  assert.deepEqual([...html.matchAll(/第 (\d+) 题/g)].map(m => Number(m[1])).slice(0, 3), [1, 2, 3])
  assert.equal((html.match(/class="group"/g) || []).length, 2)
  assert.ok(html.indexOf('class="answers"') > html.indexOf('data-label="题目3"'))
})

test('留白档位写进 class', () => {
  const html = targetedBody(payload, field, String)
  assert.ok(html.includes('answer-space space-l'))
  assert.ok(html.includes('answer-space space-s') && html.includes('answer-space space-m'))
  assert.match(TARGETED_STYLE, /\.space-s\{height:15mm\}/)
  assert.match(TARGETED_STYLE, /\.space-m\{height:30mm\}/)
  assert.match(TARGETED_STYLE, /\.space-l\{height:50mm\}/)
  assert.match(TARGETED_STYLE, /\.answers\{[^}]*break-before:page/)
  assert.match(TARGETED_STYLE, /\.question\{[^}]*break-inside:avoid/)
})

test('选项和答案走公式登记，普通文字被转义', () => {
  const html = targetedBody(payload, field, escape)
  assert.ok(html.includes('data-label="选项A"') && html.includes('>A. 甲<'))
  assert.ok(html.includes('data-label="答案1"') && html.includes('data-label="解析1"'))
  assert.ok(!html.includes('data-label="解析2"'))  // 没有解析的不登记
  assert.ok(html.includes('有理数 / 加法') && html.includes('上次做错') && html.includes('相似题'))
  assert.ok(html.includes('&quot;专项练习&quot;'))
})

test('缺少题干时报错', () => {
  const bad = structuredClone(payload)
  bad.groups[0].questions[0].question_text = '  '
  assert.throws(() => targetedBody(bad, field, String), /题目1缺少题干/)
})

test('题数', () => assert.equal(targetedQuestionCount(payload), 3))
test('题数：格式不对时返回 -1', () => assert.equal(targetedQuestionCount({}), -1))
