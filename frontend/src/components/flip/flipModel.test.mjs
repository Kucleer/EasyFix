// 翻一翻的纯逻辑测试。运行：node --test frontend/src/components/flip/flipModel.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { card_tag, card_view, progress_text, progress_dots, page_state, after_record, finish_text } from './flipModel.js'

/** 一张示例卡片（和 /api/flip/today 的 cards 里一项同形状） */
function sample(extra = {}) {
  return {
    id: 7, subject_name: '数学', point_name: '分数除法', parsed_question: '3/4 ÷ 3/8 = ?',
    images: ['questions/a.jpg'], wrong_answer: '9/32', answer: '2', analysis: '除以一个数等于乘它的倒数',
    analysis_image: null, ...extra,
  }
}

test('标签：有考点写"学科 · 考点"，没考点只写学科名', () => {
  assert.equal(card_tag(sample()), '数学 · 分数除法')
  assert.equal(card_tag(sample({ point_name: null })), '数学')
  assert.equal(card_tag(sample({ point_name: '  ' })), '数学')
  assert.equal(card_tag(sample({ point_name: null, subject_name: null })), '错题')
})

test('卡片：有题干时显示题干，原图收在"看原图"里', () => {
  const view = card_view(sample())
  assert.equal(view.stem, '3/4 ÷ 3/8 = ?')
  assert.equal(view.image_only, false)
  assert.deepEqual(view.images, ['/uploads/questions/a.jpg'])
  assert.equal(view.wrong_answer, '9/32')
  assert.equal(view.answer, '2')
  assert.equal(view.analysis, '除以一个数等于乘它的倒数')
  assert.equal(view.analysis_image, '')
})

test('卡片：只有原图没有题干时直接显示原图', () => {
  const view = card_view(sample({ parsed_question: '  ', images: ['a.jpg', 'b.jpg'] }))
  assert.equal(view.stem, '')
  assert.equal(view.image_only, true)
  assert.deepEqual(view.images, ['/uploads/a.jpg', '/uploads/b.jpg'])
})

test('卡片：错误答案为空时不显示"你上次写的"，解析图拼成地址', () => {
  for (const wrong of [null, '', '   ']) {
    assert.equal(card_view(sample({ wrong_answer: wrong })).wrong_answer, '')
  }
  const view = card_view(sample({ analysis: null, analysis_image: 'x/y.png', images: null }))
  assert.equal(view.analysis, '')
  assert.equal(view.analysis_image, '/uploads/x/y.png')
  assert.deepEqual(view.images, [])
})

test('进度文字：第几张按已翻 + 1 数，不超过总数', () => {
  assert.equal(progress_text(0, 8), '第 1 张 / 共 8 张')
  assert.equal(progress_text(3, 8), '第 4 张 / 共 8 张')
  assert.equal(progress_text(8, 8), '第 8 张 / 共 8 张')
})

test('进度条：翻过的、正在翻的、还没翻的', () => {
  assert.deepEqual(progress_dots(2, 4), ['done', 'done', 'now', ''])
  assert.deepEqual(progress_dots(4, 4), ['done', 'done', 'done', 'done'])
  assert.deepEqual(progress_dots(0, 0), [])
})

test('页面状态：没有要翻的 / 翻完了 / 正在翻', () => {
  assert.equal(page_state({ total: 0, done: 0, cards: [] }, 0), 'empty')
  assert.equal(page_state({ total: 3, done: 3, cards: [] }, 0), 'finished')
  assert.equal(page_state({ total: 3, done: 3, cards: [sample(), sample()] }, 2), 'finished')
  assert.equal(page_state({ total: 3, done: 1, cards: [sample(), sample()] }, 1), 'card')
  assert.equal(page_state({ total: 2, done: 2, cards: [sample()] }, 0), 'finished')
})

test('页面状态：手里的卡片翻完了但服务器说还有没翻的，重新取；刚取回来就没卡片时当作翻完', () => {
  // 翻了 2 张，期间录了新题，服务器的总数从 3 变成 5
  assert.equal(page_state({ total: 5, done: 3, cards: [sample(), sample()] }, 2), 'reload')
  assert.equal(page_state({ total: 5, done: 3, cards: [] }, 0), 'finished')
})

test('记下一张后：进度用服务器的，位置往后挪；今天已经记过的题 done 不变也往后挪', () => {
  const today = { total: 3, done: 1, cards: [sample(), sample()] }
  const next = after_record(today, 0, { done: 2, total: 3 })
  assert.deepEqual([next.today.done, next.today.total, next.index], [2, 3, 1])
  assert.equal(next.today.cards, today.cards)
  assert.equal(today.done, 1)
  const again = after_record(today, 0, { done: 1, total: 3 })
  assert.deepEqual([again.today.done, again.index], [1, 1])
  assert.equal(page_state(again.today, again.index), 'card')
  // 总数变多（翻的过程中录了新题），翻完手里的卡后要重新取
  const grown = after_record({ total: 3, done: 2, cards: [sample()] }, 0, { done: 3, total: 5 })
  assert.equal(page_state(grown.today, grown.index), 'reload')
})

test('翻完的话', () => {
  assert.equal(finish_text(8), '8 张都看过了，明天再来。')
})
