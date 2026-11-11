import { test } from 'node:test'
import assert from 'node:assert/strict'
import { colorOf, statusText } from './starmapColors.js'

test('颜色按掌握度渐变', () => {
  assert.equal(colorOf(null), '110,112,124')
  assert.equal(colorOf(0.15), '235,87,87')
  assert.equal(colorOf(0.55), '242,201,76')
  assert.equal(colorOf(1), '88,214,141')
})

test('状态文字', () => {
  assert.deepEqual(['unlearned', 'weak', 'fair', 'good', 'mastered'].map(statusText), ['还没学', '薄弱', '一般', '较好', '已掌握'])
})
