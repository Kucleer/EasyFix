import test from 'node:test'
import assert from 'node:assert/strict'
import { DAILY_LINES, beijingDate, pickDailyLine } from './dailyLines.js'

test('句库数量足够', () => {
  assert.ok(DAILY_LINES.length >= 90)
})

test('每句不超过 20 字、互不重复、不含禁用词', () => {
  const banned = ['加油', '最棒', '孩子', '父母', '爸爸', '妈妈']
  for (const line of DAILY_LINES) {
    assert.ok(line.length <= 20, `太长：${line}`)
    for (const w of banned) assert.ok(!line.includes(w), `含禁用词 ${w}：${line}`)
  }
  assert.equal(new Set(DAILY_LINES).size, DAILY_LINES.length)
})

test('beijingDate 按 UTC+8 取日期', () => {
  assert.equal(beijingDate(new Date('2026-11-21T16:30:00Z')), '2026-11-22')
  assert.equal(beijingDate(new Date('2026-11-21T15:59:59Z')), '2026-11-21')
})

test('同一天两次取到同一句', () => {
  assert.equal(pickDailyLine('2026-11-21'), pickDailyLine('2026-11-21'))
})

test('连续 30 天相邻两天不同', () => {
  let day = Date.UTC(2026, 10, 1)
  let prev = null
  for (let i = 0; i < 30; i++, day += 86400000) {
    const cur = pickDailyLine(new Date(day).toISOString().slice(0, 10))
    assert.ok(DAILY_LINES.includes(cur))
    if (prev !== null) assert.notEqual(cur, prev)
    prev = cur
  }
})
