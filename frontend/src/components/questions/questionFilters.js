// 错题页"全部错题"的筛选规则（纯函数，不依赖 Vue，方便用 node --test 测）。
// 页面组件 AllTab.vue 只负责把这些函数接到界面和接口上。

// 年级选项：一年级到六年级，初一到初三，高一到高三
export const GRADE_OPTIONS = [
  { label: '一年级', value: 1 },
  { label: '二年级', value: 2 },
  { label: '三年级', value: 3 },
  { label: '四年级', value: 4 },
  { label: '五年级', value: 5 },
  { label: '六年级', value: 6 },
  { label: '初一', value: 7 },
  { label: '初二', value: 8 },
  { label: '初三', value: 9 },
  { label: '高一', value: 10 },
  { label: '高二', value: 11 },
  { label: '高三', value: 12 },
]

// 正确率筛选选项：电脑筛选栏、手机抽屉、已选条件小标签共用
export const ACCURACY_RANGE_OPTIONS = [
  { label: '0-30% 薄弱', value: '0-30' },
  { label: '30-60% 一般', value: '30-60' },
  { label: '60-80% 良好', value: '60-80' },
  { label: '80-100% 掌握', value: '80-100' },
  { label: '无统计', value: 'none' },
]

// 错题页的三个标签：待核对、全部错题、卷子和作业
export const QUESTION_TABS = ['review', 'all', 'papers']

/**
 * 地址里没指定标签时默认打开哪个：有待核对的题就先看待核对，否则看全部错题。
 * 地址里带了筛选参数（比如从学情页点一个考点进来）时一定是要看错题列表，打开全部错题。
 */
export function default_question_tab(pending, query = {}) {
  if (ROUTE_FILTER_KEYS.some(key => query?.[key] != null && query[key] !== '')) return 'all'
  return Number(pending) > 0 ? 'review' : 'all'
}

/** 地址里明确指定了有效标签就返回它，否则返回 null（这时用 default_question_tab） */
export function explicit_question_tab(query) {
  const tab = query && typeof query.tab === 'string' ? query.tab : ''
  return QUESTION_TABS.includes(tab) ? tab : null
}

// 地址里能带进来的筛选参数（学情页、首页、旧书签会带）
export const ROUTE_FILTER_KEYS = ['subject_id', 'knowledge_parent_id', 'knowledge_point_id', 'unclassified', 'grade']

/** 年级的显示文字；没填返回"未设置"，不认识的数字显示成"N年级" */
export function grade_label(grade) {
  if (!grade) return '未设置'
  const option = GRADE_OPTIONS.find(item => item.value === Number(grade))
  return option ? option.label : `${grade}年级`
}

/** 学期的显示文字；1 上学期，2 下学期，其余返回空串 */
export function semester_label(semester) {
  if (semester === 1) return '上学期'
  if (semester === 2) return '下学期'
  return ''
}

/** 正确率筛选值对应的文字，例如 '0-30' → '0-30% 薄弱' */
export function accuracy_range_label(value) {
  return ACCURACY_RANGE_OPTIONS.find(item => item.value === value)?.label || value
}

/** 一份全空的筛选条件（搜索关键词也在里面，电脑和手机共用这一份） */
export function empty_filters() {
  return {
    subject_id: null,
    difficulty: [],
    tag_ids: [],
    knowledge_parent_id: null,
    knowledge_point_id: null,
    unclassified: false,
    grade: null,
    semester: null,
    accuracy_range: null,
    keyword: '',
  }
}

/** 把地址里的值转成正整数；不是正整数返回 null */
export function positive_int(value) {
  const number = Number(Array.isArray(value) ? value[0] : value)
  return Number.isInteger(number) && number > 0 ? number : null
}

/**
 * 从地址参数算出要套用的筛选条件。
 * defaults 是 { grade, semester }（管理中心设的默认年级、学期）：
 * 地址没带 grade 时用默认年级；学期一律用默认学期（和旧页面一样）。
 * 勾了"只看未分类"时不再带知识点（两者互斥）。
 */
export function route_filters(query, defaults = {}) {
  const q = query || {}
  const unclassified = q.unclassified === '1' || q.unclassified === 'true'
  return {
    subject_id: positive_int(q.subject_id),
    knowledge_parent_id: unclassified ? null : positive_int(q.knowledge_parent_id),
    knowledge_point_id: unclassified ? null : positive_int(q.knowledge_point_id),
    unclassified,
    grade: positive_int(q.grade) ?? (defaults.grade ?? null),
    semester: defaults.semester ?? null,
  }
}

/** 地址里筛选参数的"指纹"：只看 ROUTE_FILTER_KEYS，切换标签（?tab=）不算变化 */
export function route_filter_key(query) {
  const q = query || {}
  return ROUTE_FILTER_KEYS.map(key => `${key}=${q[key] ?? ''}`).join('&')
}

/** 按筛选条件和页码拼出 questionApi.list 的参数；多选值用逗号连起来，空的不带 */
export function list_params(filters, page, limit) {
  const params = { skip: (page - 1) * limit, limit }
  if (filters.subject_id) params.subject_id = filters.subject_id
  if (filters.difficulty?.length) params.difficulty = filters.difficulty.join(',')
  if (filters.tag_ids?.length) params.tag_ids = filters.tag_ids.join(',')
  if (filters.knowledge_parent_id) params.knowledge_parent_id = filters.knowledge_parent_id
  if (filters.knowledge_point_id) params.knowledge_point_id = filters.knowledge_point_id
  if (filters.unclassified) params.unclassified = 1
  if (filters.keyword && filters.keyword.trim()) params.keyword = filters.keyword.trim()
  if (filters.grade) params.grade = filters.grade
  if (filters.semester) params.semester = filters.semester
  if (filters.accuracy_range) params.accuracy_range = filters.accuracy_range
  return params
}

/** 已选了几项筛选（手机"筛选"按钮上的数字）；多选项算一项，搜索关键词不算 */
export function active_filter_count(filters) {
  return [
    filters.subject_id,
    filters.difficulty?.length,
    filters.tag_ids?.length,
    filters.knowledge_parent_id,
    filters.knowledge_point_id,
    filters.unclassified,
    filters.grade,
    filters.semester,
    filters.accuracy_range,
  ].filter(Boolean).length
}

/** 清掉知识点筛选（一级模块和二级考点） */
export function clear_knowledge(filters) {
  filters.knowledge_parent_id = null
  filters.knowledge_point_id = null
}

/** 把筛选项全部清空，搜索关键词保留（"清空"和手机抽屉的"重置"用） */
export function reset_filters(filters) {
  const keyword = filters.keyword
  Object.assign(filters, empty_filters(), { keyword })
}

/**
 * 去掉一项筛选（已选条件小标签上的 ×）。
 * 去掉学科或一级模块时，属于它的下级知识点一起去掉；多选项只去掉点的那一个值。
 */
export function remove_filter(filters, key, value) {
  if (key === 'difficulty' || key === 'tag_ids') {
    filters[key] = (filters[key] || []).filter(item => item !== value)
  } else if (key === 'unclassified') {
    filters.unclassified = false
  } else if (key === 'subject_id' || key === 'knowledge_parent_id') {
    if (key === 'subject_id') filters.subject_id = null
    clear_knowledge(filters)
  } else {
    filters[key] = null
  }
}

/**
 * 从地址进入（或停在页面上时地址里的筛选变了）：
 * 1. 筛选先全部清空，只放进地址带来的学科、年级、学期；
 * 2. 按这个学科取一次筛选项（知识点下拉要用）；
 * 3. 再套上地址里的知识点筛选（这一步在取筛选项之后，不会被任何"换学科就清知识点"的逻辑清掉）；
 * 4. 回到第 1 页，查列表。
 * state = { filters, page }；deps = { load_options(subject_id), fetch_list() }，都可以是异步函数。
 */
export async function enter_with_route(state, query, defaults, deps) {
  const wanted = route_filters(query, defaults)
  Object.assign(state.filters, empty_filters(), {
    subject_id: wanted.subject_id,
    grade: wanted.grade,
    semester: wanted.semester,
  })
  await deps.load_options(wanted.subject_id)
  state.filters.knowledge_parent_id = wanted.knowledge_parent_id
  state.filters.knowledge_point_id = wanted.knowledge_point_id
  state.filters.unclassified = wanted.unclassified
  state.page = 1
  await deps.fetch_list()
}

/**
 * 电脑上换学科：先清掉知识点筛选、回到第 1 页，再查列表；
 * 同时取新学科的筛选项（和查列表同时进行，互不等待）。
 */
export async function change_subject(state, subject_id, deps) {
  state.filters.subject_id = subject_id || null
  clear_knowledge(state.filters)
  state.page = 1
  await Promise.all([deps.load_options(state.filters.subject_id), deps.fetch_list()])
}

/** 一道题的正确率（0~1）；还没练过返回 -1，排序时排在最前 */
export function accuracy_value(row) {
  const correct = row.correct_count || 0
  const wrong = row.error_count || 0
  if (correct + wrong === 0) return -1
  return correct / (correct + wrong)
}

/** 正确率的显示文字，例如 '67%'；还没练过显示 '-' */
export function accuracy_text(row) {
  const value = accuracy_value(row)
  return value < 0 ? '-' : `${Math.round(value * 100)}%`
}

/** 标签小块的颜色：背景用标签色，文字按背景亮度取黑或白；没设颜色用主色 */
export function tag_style(color) {
  const background = /^#[0-9a-fA-F]{6}$/.test(color || '') ? color : '#4f46e5'
  const r = parseInt(background.slice(1, 3), 16)
  const g = parseInt(background.slice(3, 5), 16)
  const b = parseInt(background.slice(5, 7), 16)
  const brightness = (r * 299 + g * 587 + b * 114) / 1000
  return { backgroundColor: background, borderColor: background, color: brightness > 128 ? '#000000' : '#ffffff' }
}

/** 列表里显示的知识点：主考点在前，其余按编号，最多 limit 个 */
export function visible_knowledge_points(row, limit = 3) {
  const points = [...(row.knowledge_points || [])]
  points.sort((left, right) => {
    if (Boolean(left.is_primary) !== Boolean(right.is_primary)) return left.is_primary ? -1 : 1
    return (left.id || 0) - (right.id || 0)
  })
  return points.slice(0, limit)
}
