// 首页文字小函数的测试。运行：node --test frontend/src/components/home/homeText.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import {
  WEEKDAY_NAMES, greeting_text, short_date_text, week_range_text, days_ago, targeted_hint, day_state,
} from './homeText.js'

test('上方小字：星期和日期', () => {
  assert.equal(greeting_text('2026-11-21'), '周六好 · 11 月 21 日')
  assert.equal(greeting_text('2026-11-16'), '周一好 · 11 月 16 日')
  assert.equal(greeting_text('2026-11-22'), '周日好 · 11 月 22 日')
  assert.equal(greeting_text('不是日期'), '')
})

test('短日期可以带时间', () => {
  assert.equal(short_date_text('2026-11-18 09:30:00'), '11 月 18 日')
  assert.equal(short_date_text('2026-01-05'), '1 月 5 日')
  assert.equal(short_date_text(null), '')
})

test('本周日期范围：同月只写一次月份，跨月写两次', () => {
  assert.equal(week_range_text('2026-11-16', '2026-11-22'), '11 月 16 日 – 22 日')
  assert.equal(week_range_text('2026-11-30', '2026-12-06'), '11 月 30 日 – 12 月 6 日')
  assert.equal(week_range_text('', ''), '这一周')
})

test('几天前：按日期算，不看几点', () => {
  assert.equal(days_ago('2026-11-18 23:59:00', '2026-11-21'), 3)
  assert.equal(days_ago('2026-11-21 00:01:00', '2026-11-21'), 0)
  assert.equal(days_ago('2026-10-31', '2026-11-01'), 1)
  assert.equal(days_ago(null, '2026-11-21'), null)
})

test('考点卷副标题', () => {
  assert.equal(targeted_hint(null, '2026-11-21'), '还没有出过考点卷')
  assert.equal(targeted_hint('2026-11-21 08:00:00', '2026-11-21'), '今天刚出过一份')
  assert.equal(targeted_hint('2026-11-18 08:00:00', '2026-11-21'), '上次出卷是 3 天前')
})

test('打卡条每一天的状态', () => {
  assert.equal(day_state('2026-11-20', true, '2026-11-21'), 'done')
  assert.equal(day_state('2026-11-19', false, '2026-11-21'), '')
  assert.equal(day_state('2026-11-21', true, '2026-11-21'), 'done today')
  assert.equal(day_state('2026-11-21', false, '2026-11-21'), 'today')
  assert.equal(day_state('2026-11-22', false, '2026-11-21'), 'future')
})

test('星期从周一开始，共七天', () => {
  assert.deepEqual(WEEKDAY_NAMES, ['一', '二', '三', '四', '五', '六', '日'])
})
