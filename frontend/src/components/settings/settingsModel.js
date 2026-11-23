/**
 * 设置页用到的纯函数和常量（不碰接口、不碰页面，方便 node --test 测试）。
 * 手机紧凑列表的每一行统一成 { key, name, desc, color?, is_parent?, is_child?, actions }，
 * actions 里的 run 由页面传进来的处理函数决定，和电脑端表格里的按钮一一对应。
 */

/** 标签栏：顺序就是页面上的顺序 */
export const SETTINGS_TABS = [
  { key: 'grade', label: '年级与学期' },
  { key: 'subjects', label: '学科' },
  { key: 'tags', label: '标签' },
  { key: 'knowledge', label: '知识点' },
  { key: 'books', label: '错题本' },
  { key: 'starmap', label: '知识星空' },
  { key: 'model', label: '模型' },
]

/** 只有管理员看得到的标签：账号（开家庭、加学生、重置密码） */
const ACCOUNTS_TAB = { key: 'accounts', label: '账号' }
/** 每个人都有的标签：我的账号（看登录名、改自己的密码） */
const ME_TAB = { key: 'me', label: '我的账号' }

/**
 * 按角色决定显示哪些标签。
 * 管理员：七个原有标签 + 账号 + 我的账号；家长：去掉模型（模型密钥只给管理员看），最后是我的账号。
 */
export function tabs_for(is_admin) {
  if (is_admin) return [...SETTINGS_TABS, ACCOUNTS_TAB, ME_TAB]
  return [...SETTINGS_TABS.filter(t => t.key !== 'model'), ME_TAB]
}

/** 学科、知识点这些全站共用的目录，只有管理员能新增、修改、删除 */
export function can_edit_shared(is_admin) {
  return is_admin === true
}

/** 年级选项 1–12 */
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

/** 学期选项 */
export const SEMESTER_OPTIONS = [
  { label: '上学期', value: 1 },
  { label: '下学期', value: 2 },
]

/** 知识点弹窗记住上次选择用的 localStorage 键 */
export const KP_MEMORY_KEYS = {
  subject: 'lastKpSubject',
  grade: 'lastKpGrade',
  semester: 'lastKpSemester',
}

/** 把几个说明字段用「 · 」连成一行，自动跳过空值 */
export function join_desc(...parts) {
  return parts.filter(part => part !== null && part !== undefined && part !== '').join(' · ')
}

/** 库存 -1 表示无限，其余原样显示 */
export function format_stock(value) {
  return value === -1 ? '无限' : value
}

/** 积分值加上正负号，例如 +10、-5 */
export function format_signed(value) {
  return (value >= 0 ? '+' : '') + value
}

/** 从存储里读一个记住的数字；没有或是空串就返回 null */
export function read_saved_number(storage, key) {
  let text = null
  try {
    text = storage?.getItem(key)
  } catch {
    return null
  }
  if (!text) return null
  const value = parseInt(text, 10)
  return Number.isNaN(value) ? null : value
}

/** 知识点树接口的查询参数：只带有值的筛选项 */
export function knowledge_query(filters) {
  const params = {}
  for (const key of ['subject_id', 'grade', 'semester', 'keyword']) {
    if (filters[key]) params[key] = filters[key]
  }
  return params
}

/** 平铺知识点列表接口的返回值里挑出待处理的旧目录 */
export function pick_legacy(data) {
  const flat = Array.isArray(data) ? data : (data?.items || [])
  return flat.filter(item => item.legacy)
}

/** 给错题本补上学科名 */
export function with_subject_names(books, subjects) {
  return (books || []).map(book => ({
    ...book,
    subject_name: (subjects || []).find(s => s.id === book.subject_id)?.name || '',
  }))
}

/** 学科的手机列表行 */
export function subject_rows(list, { remove }) {
  return (list || []).map(row => ({
    key: row.id,
    name: row.name,
    desc: `ID ${row.id}`,
    actions: [{ label: '删除', run: () => remove(row), danger: true }],
  }))
}

/** 标签的手机列表行（带颜色圆点） */
export function tag_rows(list, { remove }) {
  return (list || []).map(row => ({
    key: row.id,
    name: row.name,
    color: row.color,
    desc: row.color ? `颜色 ${row.color}` : '默认颜色',
    actions: [{ label: '删除', run: () => remove(row), danger: true }],
  }))
}

/** 一条知识点的手机列表行；操作和表格里的「编辑 / 新增二级 / 删除」一致 */
function knowledge_row(row, is_child, handlers) {
  const is_module = row.level === 1
  return {
    key: row.id,
    name: row.name,
    desc: join_desc(
      row.subject_name,
      is_module ? `子级 ${row.child_count || 0} 个` : '',
      `${row.question_count || 0} 题`,
    ),
    is_parent: is_module && !is_child,
    is_child,
    actions: [
      { label: '编辑', run: () => handlers.edit(row) },
      ...(is_module ? [{ label: '新增二级', run: () => handlers.add_child(row) }] : []),
      { label: '删除', run: () => handlers.remove(row), danger: true },
    ],
  }
}

/** 把两级知识点树摊平成一列：一级在前，紧跟它的二级（相当于全部展开） */
export function knowledge_rows(tree, handlers) {
  const rows = []
  for (const parent of tree || []) {
    rows.push(knowledge_row(parent, false, handlers))
    for (const child of parent.children || []) rows.push(knowledge_row(child, true, handlers))
  }
  return rows
}

/** 待处理旧目录的手机列表行：转为二级 / 软删除（有题目引用时不能删） */
export function legacy_rows(list, { promote, remove }) {
  return (list || []).map(row => ({
    key: row.id,
    name: row.name,
    desc: join_desc(row.subject_name, `${row.question_count || 0} 题`, `ID ${row.id}`),
    actions: [
      { label: '转为二级', run: () => promote(row) },
      { label: '软删除', run: () => remove(row), disabled: row.question_count > 0, danger: true },
    ],
  }))
}

/** 错题本的手机列表行 */
export function book_rows(list, { edit, remove }) {
  return (list || []).map(row => ({
    key: row.id,
    name: row.name,
    desc: join_desc(row.subject_name, row.description),
    actions: [
      { label: '编辑', run: () => edit(row) },
      { label: '删除', run: () => remove(row), danger: true },
    ],
  }))
}

/** 积分行为的手机列表行；预设行为不能删 */
export function star_action_rows(list, { edit, remove }) {
  return (list || []).map(row => ({
    key: row.id,
    name: row.name,
    desc: join_desc(
      `${format_signed(row.star_value)} 积分`,
      row.is_custom ? '自定义' : '预设',
      row.enabled ? '' : '已停用',
    ),
    actions: [
      { label: '编辑', run: () => edit(row) },
      { label: '删除', run: () => remove(row), disabled: row.is_preset, danger: true },
    ],
  }))
}

/** 成就的手机列表行；预设成就不能改也不能删 */
export function achievement_rows(list, { edit, remove }) {
  return (list || []).map(row => ({
    key: row.id,
    name: row.name,
    desc: join_desc(
      `等级 ${row.level}`,
      `${row.trigger_action} × ${row.trigger_count}`,
      `奖励 ${row.reward_stars} 积分`,
    ),
    actions: [
      { label: '编辑', run: () => edit(row), disabled: row.is_preset },
      { label: '删除', run: () => remove(row), disabled: row.is_preset, danger: true },
    ],
  }))
}

/** 奖励的手机列表行 */
export function reward_rows(list, { edit, remove }) {
  return (list || []).map(row => ({
    key: row.id,
    name: row.name,
    desc: join_desc(
      `${row.cost_stars} 积分`,
      `剩余 ${format_stock(row.remaining_stock)} / 总 ${format_stock(row.total_stock)}`,
    ),
    actions: [
      { label: '编辑', run: () => edit(row) },
      { label: '删除', run: () => remove(row), danger: true },
    ],
  }))
}
