// 图表主题测试：node --test frontend/src/composables/chartTheme.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { CHART_THEME, readChartTheme } from './chartTheme.js'

test('读不到 CSS 变量时用默认主题', () => {
  assert.deepEqual(readChartTheme(() => ''), CHART_THEME)
})

test('读到的变量覆盖对应颜色，其余不变', () => {
  const theme = readChartTheme(name => (name === '--brand' ? '#000' : ''))
  assert.equal(theme.main, '#000')
  assert.equal(theme.text, CHART_THEME.text)
  assert.equal(theme.line, CHART_THEME.line)
})

test('默认主题用样稿的颜色', () => {
  assert.equal(CHART_THEME.main, '#4f46e5')
  assert.equal(CHART_THEME.text, '#686e89')
  assert.equal(CHART_THEME.strong, '#1f2340')
  assert.equal(CHART_THEME.line, '#e6e5f2')
  assert.equal(CHART_THEME.green, '#17895a')
  assert.equal(CHART_THEME.orange, '#b4641a')
})
