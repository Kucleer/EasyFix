// 错题页筛选规则的测试。运行：node --test frontend/src/components/questions/questionFilters.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import {
  QUESTION_TABS, default_question_tab, explicit_question_tab,
  grade_label, semester_label, accuracy_range_label, empty_filters, positive_int, route_semester,
  route_filters, route_filter_key, list_params, active_filter_count, reset_filters, remove_filter,
  enter_with_route, change_subject, supersede_entry, pick_module,
  accuracy_value, accuracy_text, visible_knowledge_points, tag_style,
} from './questionFilters.js'

/**
 * 造一份假的依赖：记下调用顺序，以及查列表那一刻的筛选条件和页码。
 * defaults 是 load_defaults 返回的默认年级学期；hooks 里可以放在某一步等待时插进来的动作。
 */
function fake_deps(state, defaults = {}, hooks = {}) {
  const calls = []
  const seen = []
  return {
    calls,
    seen,
    load_defaults: async () => {
      calls.push('defaults')
      await Promise.resolve()
      if (hooks.during_defaults) await hooks.during_defaults()
      return defaults
    },
    load_options: async (subject_id) => {
      calls.push('options:' + subject_id)
      await Promise.resolve()
      if (hooks.during_options) await hooks.during_options(subject_id)
    },
    fetch_list: async () => {
      calls.push('fetch')
      seen.push({ ...state.filters, page: state.page })
    },
  }
}

test('默认标签：有待核对先看待核对，否则看全部错题；地址里的有效标签优先', () => {
  assert.deepEqual(QUESTION_TABS, ['review', 'all', 'papers'])
  assert.equal(default_question_tab(3), 'review')
  assert.equal(default_question_tab(0), 'all')
  assert.equal(default_question_tab(undefined), 'all')
  // 带着筛选参数进来（学情页点考点）：即使有待核对，也打开全部错题
  assert.equal(default_question_tab(3, { subject_id: '1', knowledge_point_id: '9' }), 'all')
  assert.equal(default_question_tab(3, { unclassified: '1' }), 'all')
  assert.equal(default_question_tab(3, { semester: '2' }), 'all')
  assert.equal(default_question_tab(3, { other: 'x' }), 'review')
  assert.equal(explicit_question_tab({ tab: 'papers' }), 'papers')
  assert.equal(explicit_question_tab({ tab: 'all' }), 'all')
  assert.equal(explicit_question_tab({ tab: 'nope' }), null)
  assert.equal(explicit_question_tab({}), null)
})

test('显示文字', () => {
  assert.equal(grade_label(6), '六年级')
  assert.equal(grade_label(7), '初一')
  assert.equal(grade_label(null), '未设置')
  assert.equal(grade_label(15), '15年级')
  assert.equal(semester_label(1), '上学期')
  assert.equal(semester_label(2), '下学期')
  assert.equal(semester_label(null), '')
  assert.equal(accuracy_range_label('0-30'), '0-30% 薄弱')
  assert.equal(accuracy_range_label('x'), 'x')
})

test('地址参数转筛选：没有知识点筛选时，没带年级学期就用默认值；地址里的年级学期优先', () => {
  const defaults = { grade: 6, semester: 1 }
  // 直接打开 /questions：默认年级、默认学期
  assert.deepEqual(route_filters({}, defaults), {
    subject_id: null, knowledge_parent_id: null, knowledge_point_id: null, unclassified: false, grade: 6, semester: 1,
  })
  // 只带学科：照样套默认值
  assert.equal(route_filters({ subject_id: '3' }, defaults).grade, 6)
  assert.equal(route_filters({ subject_id: '3' }, defaults).semester, 1)
  // 地址里带了年级、学期就用地址里的
  assert.equal(route_filters({ grade: '5' }, defaults).grade, 5)
  assert.equal(route_filters({ semester: '2' }, defaults).semester, 2)
  // 学期只认 1、2
  assert.equal(route_filters({ semester: '3' }, defaults).semester, 1)
  assert.equal(route_semester('2'), 2)
  assert.equal(route_semester('x'), null)
  assert.equal(route_filters({}, {}).grade, null)
  assert.equal(positive_int('abc'), null)
  assert.equal(positive_int('-2'), null)
  assert.equal(positive_int(['4']), 4)
})

test('地址参数转筛选：带了知识点筛选（模块、考点或未分类）就不套默认年级学期', () => {
  const defaults = { grade: 6, semester: 1 }
  assert.deepEqual(route_filters({ subject_id: '3', knowledge_parent_id: '10', knowledge_point_id: '11' }, defaults), {
    subject_id: 3, knowledge_parent_id: 10, knowledge_point_id: 11, unclassified: false, grade: null, semester: null,
  })
  assert.equal(route_filters({ knowledge_parent_id: '10' }, defaults).grade, null)
  const unclassified = route_filters({ subject_id: '3', unclassified: '1', knowledge_point_id: '11' }, defaults)
  assert.equal(unclassified.unclassified, true)
  assert.equal(unclassified.knowledge_point_id, null)
  assert.equal(unclassified.grade, null)
  assert.equal(unclassified.semester, null)
  // 地址里自己带了年级学期，照用
  const explicit = route_filters({ knowledge_point_id: '11', grade: '5', semester: '2' }, defaults)
  assert.equal(explicit.grade, 5)
  assert.equal(explicit.semester, 2)
  assert.equal(route_filters({ unclassified: 'true' }, defaults).unclassified, true)
})

test('地址指纹只看筛选参数，切换标签不算变化', () => {
  const a = route_filter_key({ subject_id: '3', tab: 'all' })
  assert.equal(a, route_filter_key({ subject_id: '3', tab: 'review' }))
  assert.notEqual(a, route_filter_key({ subject_id: '3', knowledge_point_id: '9' }))
  assert.notEqual(a, route_filter_key({ subject_id: '3', semester: '2' }))
})

test('查询参数：多选用逗号，空的不带，关键词去掉首尾空格', () => {
  const filters = { ...empty_filters(), subject_id: 2, difficulty: [1, 3], tag_ids: [5], unclassified: true, keyword: '  分数 ', semester: 1 }
  assert.deepEqual(list_params(filters, 3, 20), {
    skip: 40, limit: 20, subject_id: 2, difficulty: '1,3', tag_ids: '5', unclassified: 1, keyword: '分数', semester: 1,
  })
  assert.deepEqual(list_params(empty_filters(), 1, 50), { skip: 0, limit: 50 })
})

test('已选筛选计数：多选算一项，关键词不算', () => {
  assert.equal(active_filter_count(empty_filters()), 0)
  assert.equal(active_filter_count({ ...empty_filters(), difficulty: [1, 2], grade: 6, keyword: 'x' }), 2)
})

test('去掉一项筛选、清空', () => {
  const filters = { ...empty_filters(), subject_id: 2, knowledge_parent_id: 10, knowledge_point_id: 11, difficulty: [1, 2], keyword: 'k' }
  remove_filter(filters, 'difficulty', 1)
  assert.deepEqual(filters.difficulty, [2])
  remove_filter(filters, 'knowledge_parent_id')
  assert.equal(filters.knowledge_point_id, null)
  filters.knowledge_parent_id = 10
  remove_filter(filters, 'subject_id')
  assert.equal(filters.subject_id, null)
  assert.equal(filters.knowledge_parent_id, null)
  filters.grade = 6
  remove_filter(filters, 'grade')
  assert.equal(filters.grade, null)
  filters.accuracy_range = '0-30'
  reset_filters(filters)
  assert.deepEqual(filters, { ...empty_filters(), keyword: 'k' })
})

test('选一级模块：清掉二级考点，并取消"只看未分类"（两者不能同时带）', () => {
  const filters = { ...empty_filters(), subject_id: 3, unclassified: true, knowledge_point_id: 9 }
  pick_module(filters, 10)
  assert.equal(filters.knowledge_parent_id, 10)
  assert.equal(filters.knowledge_point_id, null)
  assert.equal(filters.unclassified, false)
  assert.equal(list_params(filters, 1, 20).unclassified, undefined)
  // 清掉模块不会反过来勾上未分类，也不会改别的
  const cleared = { ...empty_filters(), unclassified: true }
  pick_module(cleared, '')
  assert.equal(cleared.knowledge_parent_id, null)
  assert.equal(cleared.unclassified, true)
})

test('从地址进入：先按学科取一次筛选项，再套知识点筛选，再查列表，知识点不被清掉', async () => {
  const state = { filters: { ...empty_filters(), difficulty: [3], keyword: '旧' }, page: 4 }
  const deps = fake_deps(state, { grade: 6, semester: 1 })
  await enter_with_route(state, { subject_id: '3', knowledge_parent_id: '10', knowledge_point_id: '11' }, deps)
  // 筛选项只取一次，而且在查列表之前
  assert.deepEqual(deps.calls, ['defaults', 'options:3', 'fetch'])
  // 查列表那一刻：知识点在、旧的其余筛选清掉、没套默认年级学期、回到第 1 页
  assert.deepEqual(deps.seen, [{
    ...empty_filters(), subject_id: 3, knowledge_parent_id: 10, knowledge_point_id: 11, grade: null, semester: null, page: 1,
  }])
})

test('直接打开 /questions：套默认年级学期，只查一次', async () => {
  const state = { filters: empty_filters(), page: 1 }
  const deps = fake_deps(state, { grade: 6, semester: 2 })
  await enter_with_route(state, {}, deps)
  assert.deepEqual(deps.calls, ['defaults', 'options:null', 'fetch'])
  assert.equal(deps.seen[0].grade, 6)
  assert.equal(deps.seen[0].semester, 2)
})

test('从地址进入：未分类、没带学科也照样只查一次，年级用地址里的', async () => {
  const state = { filters: empty_filters(), page: 1 }
  const deps = fake_deps(state, { grade: 6, semester: 2 })
  await enter_with_route(state, { unclassified: '1', grade: '5' }, deps)
  assert.deepEqual(deps.calls, ['defaults', 'options:null', 'fetch'])
  assert.equal(deps.seen[0].unclassified, true)
  assert.equal(deps.seen[0].grade, 5)
  assert.equal(deps.seen[0].semester, null)
})

test('地址里的筛选变了再进来：重新套用新的知识点', async () => {
  const state = { filters: empty_filters(), page: 1 }
  const deps = fake_deps(state)
  await enter_with_route(state, { subject_id: '3', knowledge_parent_id: '10', knowledge_point_id: '11' }, deps)
  state.page = 5
  await enter_with_route(state, { subject_id: '4', knowledge_parent_id: '20', knowledge_point_id: '21' }, deps)
  assert.deepEqual(deps.calls, ['defaults', 'options:3', 'fetch', 'defaults', 'options:4', 'fetch'])
  assert.equal(deps.seen[1].knowledge_point_id, 21)
  assert.equal(deps.seen[1].page, 1)
})

test('过时的进入会停下：取筛选项期间又从地址进来，旧的知识点不会落到新学科上', async () => {
  const state = { filters: empty_filters(), page: 1 }
  let second = null
  const deps = fake_deps(state, {}, {
    // 第一次进入（学科 3）等筛选项时，第二次进入（学科 4）开始
    during_options: async (subject_id) => {
      if (subject_id === 3 && !second) {
        second = enter_with_route(state, { subject_id: '4', knowledge_parent_id: '20', knowledge_point_id: '21' }, deps)
        await second
      }
    },
  })
  await enter_with_route(state, { subject_id: '3', knowledge_parent_id: '10', knowledge_point_id: '11' }, deps)
  // 只查了一次，是第二次进入的；第一次进入没有再写知识点也没有再查
  assert.equal(deps.seen.length, 1)
  assert.deepEqual(
    [deps.seen[0].subject_id, deps.seen[0].knowledge_parent_id, deps.seen[0].knowledge_point_id],
    [4, 20, 21])
  assert.deepEqual([state.filters.subject_id, state.filters.knowledge_point_id], [4, 21])
})

test('过时的进入会停下：等默认值或筛选项期间用户自己换了学科，以用户的为准', async () => {
  // 等筛选项期间换学科
  let state = { filters: empty_filters(), page: 1 }
  let deps = fake_deps(state, {}, {
    during_options: async (subject_id) => {
      if (subject_id === 3) await change_subject(state, 5, deps)
    },
  })
  await enter_with_route(state, { subject_id: '3', knowledge_parent_id: '10', knowledge_point_id: '11' }, deps)
  assert.equal(state.filters.subject_id, 5)
  assert.equal(state.filters.knowledge_parent_id, null)
  assert.ok(deps.seen.every(seen => seen.knowledge_parent_id == null), '不会带着旧知识点去查')
  // 等默认值期间手动改了筛选（父组件会调用 supersede_entry）
  state = { filters: empty_filters(), page: 1 }
  deps = fake_deps(state, { grade: 6 }, { during_defaults: async () => { supersede_entry(state) } })
  await enter_with_route(state, { subject_id: '3', knowledge_point_id: '11' }, deps)
  assert.deepEqual(deps.calls, ['defaults'])
  assert.equal(state.filters.subject_id, null)
})

test('电脑上换学科：查列表时知识点已经清掉，并回到第 1 页', async () => {
  const state = { filters: { ...empty_filters(), subject_id: 3, knowledge_parent_id: 10, knowledge_point_id: 11, unclassified: false }, page: 3 }
  const deps = fake_deps(state)
  await change_subject(state, 4, deps)
  assert.deepEqual(deps.calls, ['options:4', 'fetch'])
  assert.equal(deps.seen[0].subject_id, 4)
  assert.equal(deps.seen[0].knowledge_parent_id, null)
  assert.equal(deps.seen[0].knowledge_point_id, null)
  assert.equal(deps.seen[0].page, 1)
  await change_subject(state, undefined, deps)
  assert.equal(state.filters.subject_id, null)
})

test('正确率和列表里的知识点', () => {
  assert.equal(accuracy_value({}), -1)
  assert.equal(accuracy_text({}), '-')
  assert.equal(accuracy_text({ correct_count: 2, error_count: 1 }), '67%')
  const row = { knowledge_points: [{ id: 5 }, { id: 2 }, { id: 9, is_primary: 1 }, { id: 1 }] }
  assert.deepEqual(visible_knowledge_points(row).map(point => point.id), [9, 1, 2])
  assert.deepEqual(visible_knowledge_points(row, 2).map(point => point.id), [9, 1])
})

test('标签颜色：浅色底配黑字，深色底配白字，没颜色用主色', () => {
  assert.deepEqual(tag_style('#ffffff'), { backgroundColor: '#ffffff', borderColor: '#ffffff', color: '#000000' })
  assert.equal(tag_style('#000000').color, '#ffffff')
  assert.equal(tag_style(null).backgroundColor, '#4f46e5')
})
