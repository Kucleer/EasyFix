import test from 'node:test'
import assert from 'node:assert/strict'
import {
  weekTitle, badges, calendarOption, visibleSubjects, defaultSubjectId,
  donutOption, modulesOption, gaugeOption, trendOption, practiceLine, flipLine,
} from './weeklyReport.js'

// 一份和设计文档示例一致的 facts
function sample() {
  return {
    schema_version: 1,
    week: { start: '2026-11-15 20:00:00', end: '2026-11-22 20:00:00', monday: '2026-11-16', sunday: '2026-11-22', number: 6 },
    quiet: false,
    entries: { count: 72, prev_count: 58, streak_weeks: 4, by_subject: [{ subject_id: 1, name: '数学', count: 72 }] },
    calendar: [{ date: '2026-10-12', entered: false, dictated: true }],
    dictation: {
      count: 70, correct: 34, accuracy: 48.6, days: 4, prev_count: 250, prev_accuracy: 49.6,
      trend: [
        { monday: '2026-10-12', count: 25, accuracy: 36.0 }, { monday: '2026-10-19', count: 0, accuracy: null },
        { monday: '2026-10-26', count: 0, accuracy: null }, { monday: '2026-11-02', count: 100, accuracy: 50.0 },
        { monday: '2026-11-09', count: 250, accuracy: 49.6 }, { monday: '2026-11-16', count: 70, accuracy: 48.6 },
      ],
    },
    practice: { papers: 0, questions: 0, correct: 0, accuracy: null, prev_papers: 4, prev_accuracy: 51.6, graduated: 0 },
    subjects: [{
      subject_id: 1, name: '数学',
      status_counts: { mastered: 5, good: 0, fair: 8, weak: 35, unlearned: 27 },
      improved: [{ id: 101, name: '合并同类项' }], dropped: [], new_weak: [],
      improved_count: 1, dropped_count: 0,
      modules: [{ id: 100, name: '整式', before: 0.4, after: 0.52 }],
      target: { id: 102, name: '去括号' },
    }],
  }
}

test('标题和奖章', () => {
  const facts = sample()
  assert.equal(weekTitle(facts), '第 6 期 · 11 月 16 日 – 22 日')
  facts.week.monday = '2026-11-30'; facts.week.sunday = '2026-12-06'
  assert.equal(weekTitle(facts), '第 6 期 · 11 月 30 日 – 12 月 6 日')
  assert.deepEqual(badges(sample()).map(b => b.text), ['连续 4 周有录入', '1 个考点变好', '默写 4 天'])
})

test('test_badges_hide_zero：安静的一周一枚奖章都没有', () => {
  const facts = sample()
  facts.entries.streak_weeks = 0; facts.dictation.days = 0
  facts.subjects[0].improved = []; facts.subjects[0].improved_count = 0
  assert.deepEqual(badges(facts), [])
})

test('变好个数优先用不封顶的 improved_count，没有时退回列表长度', () => {
  const facts = sample()
  facts.subjects[0].improved_count = 8
  assert.ok(badges(facts).some(b => b.text === '8 个考点变好'))
  assert.equal(donutOption(facts.subjects[0]).title.text, '+8')
  delete facts.subjects[0].improved_count
  assert.ok(badges(facts).some(b => b.text === '1 个考点变好'))
})

test('毕业奖章', () => {
  const facts = sample()
  facts.practice.graduated = 3
  assert.equal(badges(facts).find(b => b.key === 'graduated').text, '毕业 3 道')
})

test('日历只放亮的格子，值区分三种情况', () => {
  const facts = sample()
  facts.calendar = [{ date: '2026-11-16', entered: true, dictated: false }, { date: '2026-11-17', entered: true, dictated: true },
    { date: '2026-11-18', entered: false, dictated: true }, { date: '2026-11-19', entered: false, dictated: false }]
  assert.deepEqual(calendarOption(facts).series[0].data, [['2026-11-16', 2], ['2026-11-17', 3], ['2026-11-18', 1]])
})

test('环形图顺序固定、0 不放、中间显示变好个数', () => {
  const option = donutOption(sample().subjects[0])
  assert.deepEqual(option.series[0].data.map(d => [d.name, d.value]), [['已掌握', 5], ['一般', 8], ['薄弱', 35], ['还没学', 27]])
  assert.equal(option.title.text, '+1')
  const none = { ...sample().subjects[0], improved: [], improved_count: 0 }
  assert.equal(donutOption(none).title.show, false)
})

test('test_single_subject_and_few_modules', () => {
  const facts = sample()
  assert.equal(visibleSubjects(facts).length, 1)
  assert.equal(defaultSubjectId(facts), 1)
  assert.equal(modulesOption(facts.subjects[0]).series[0].type, 'bar')           // 示例只有 1 个模块
  const many = { ...facts.subjects[0], modules: [1, 2, 3].map(id => ({ id, name: '模块' + id, before: 0.3, after: 0.5 })) }
  assert.equal(modulesOption(many).series[0].type, 'radar')
  assert.equal(modulesOption({ ...many, modules: [] }), null)
  assert.equal(defaultSubjectId({ ...facts, subjects: [] }), null)
})

test('默认学科取变化最多的，一样多取第一个', () => {
  const facts = sample()
  const a = { ...facts.subjects[0], subject_id: 1, improved_count: 1, dropped_count: 0 }
  const b = { ...facts.subjects[0], subject_id: 2, improved_count: 1, dropped_count: 2 }
  const c = { ...facts.subjects[0], subject_id: 3, improved_count: 3, dropped_count: 0 }
  assert.equal(defaultSubjectId({ subjects: [a, b, c] }), 2)
  assert.equal(defaultSubjectId({ subjects: [a, { ...a, subject_id: 9 }] }), 1)
})

test('模块 before 为 null（本周才学）：不崩，本周值保留', () => {
  const base = sample().subjects[0]
  const modules = [1, 2, 3].map(id => ({ id, name: '模块' + id, before: id === 2 ? null : 0.3, after: 0.5 }))
  const radar = modulesOption({ ...base, modules })
  assert.deepEqual(radar.series[0].data[1].value, [0.5, 0.5, 0.5])
  assert.deepEqual(radar.series[0].data[0].value, [0.3, 0, 0.3])
  const bar = modulesOption({ ...base, modules: [{ id: 1, name: '新模块', before: null, after: 0.4 }] })
  assert.equal(bar.series[0].type, 'bar')
  assert.equal(bar.series[0].data[0], null)
  assert.equal(bar.series[1].data[0], 0.4)
})

test('主题颜色可以传入', () => {
  const option = modulesOption(sample().subjects[0], { text: '#111', subtle: '#222', line: '#333' })
  assert.equal(option.xAxis.axisLabel.color, '#111')
})

test('默写和练习卷', () => {
  const facts = sample()
  assert.equal(gaugeOption(facts).series[0].data[0].value, 48.6)
  facts.dictation.accuracy = null
  assert.equal(gaugeOption(facts), null)
  assert.equal(trendOption(sample()).series[0].data.length, 6)
  assert.equal(practiceLine(sample()), null)
  const done = sample(); Object.assign(done.practice, { papers: 2, questions: 10, correct: 7 })
  assert.equal(practiceLine(done), '批改 2 份 · 做对 7 / 10 道')
})

test('翻一翻一行字：旧周报没有 flip、一张没翻时不显示', () => {
  const facts = sample()
  assert.equal(flipLine(facts), null)
  facts.flip = { days: 0, cards: 0 }
  assert.equal(flipLine(facts), null)
  facts.flip = { days: 3, cards: 17 }
  assert.equal(flipLine(facts), '这周翻了 3 天错题，一共 17 张')
})

test('日历提示：第 1 档是默写或翻了错题', () => {
  const option = calendarOption(sample())
  assert.equal(option.tooltip.formatter({ value: ['2026-11-18', 1] }), '2026-11-18：默写或翻了错题')
})
