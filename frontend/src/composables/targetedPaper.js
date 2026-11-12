// 考点卷的纯函数：不碰 DOM、不改传入的对象，方便单独测试。

export const REASON_LABELS = { new: '新错题', wrong: '上次做错', redo: '旧错题重做', consolidate: '巩固', check: '验收', spot: '抽查' }
export const FORM_LABELS = { original: '原题', similar: '相似题' }
export const MODE_LABELS = { spread: '均布', focus: '集中' }
export const STATE_LABELS = { to_print: '待打印', to_grade: '待批改', graded: '已批改' }

// 按模块分组，保持模块第一次出现的先后
export function groupByModule(items) {
  const groups = []
  const index = new Map()
  for (const item of items || []) {
    if (!index.has(item.module_id)) {
      const group = { module_id: item.module_id, module_name: item.module_name, items: [] }
      index.set(item.module_id, group)
      groups.push(group)
    }
    index.get(item.module_id).items.push(item)
  }
  return groups
}

// 换一道：用同考点备选里的第一道替换，被换下的放到备选末尾；
// 抽查题（没有备选）或备选为空时原样返回
export function swapItem(plan, index) {
  const old = plan.items[index]
  if (!old || old.reason === 'spot') return plan
  const reserve = (plan.reserve || {})[old.point_id] || []
  if (!reserve.length) return plan
  const [first, ...rest] = reserve
  const items = plan.items.slice()
  items[index] = { ...old, ...first }
  return { ...plan, items, reserve: { ...plan.reserve, [old.point_id]: [...rest, old] } }
}

// 删除一道题
export function removeItem(plan, index) {
  return { ...plan, items: plan.items.filter((_, i) => i !== index) }
}

// 原题 <-> 相似题；验收（check）和抽查（spot）的题不能切成原题
export function toggleForm(plan, index) {
  const item = plan.items[index]
  if (!item) return plan
  if (item.form === 'similar' && (item.reason === 'check' || item.reason === 'spot')) return plan
  const items = plan.items.slice()
  items[index] = { ...item, form: item.form === 'original' ? 'similar' : 'original' }
  return { ...plan, items }
}

// 创建考点卷的请求体
export function createPayload(subjectId, name, plan) {
  return {
    subject_id: subjectId,
    name,
    items: plan.items.map(i => ({ question_id: i.question_id, point_id: i.point_id, reason: i.reason, form: i.form })),
  }
}

// 题数、涉及的考点数、要准备的相似题数
export function summary(plan) {
  const items = plan.items || []
  return {
    total: items.length,
    points: new Set(items.map(i => i.point_id)).size,
    similar: items.filter(i => i.form === 'similar').length,
  }
}

// 每道题的初始批改标记，key 是题目行编号
export function initialMarks(questions) {
  const marks = {}
  for (const q of questions || []) {
    if (q.skip_reason) marks[q.id] = q.skip_reason
    else marks[q.id] = q.is_correct === false ? 'wrong' : 'right'
  }
  return marks
}

// 点一下：对 <-> 错；跳过状态回到对
export function toggleMark(mark) {
  return mark === 'right' ? 'wrong' : 'right'
}

// 批改请求体；question_id 是错题编号（后端按它校验），跳过的题 is_correct 为 null
export function gradePayload(questions, marks, revision) {
  return {
    question_results: questions.map(q => {
      const mark = marks[q.id] || 'right'
      const skipped = mark === 'not_done' || mark === 'bad_question'
      return { question_id: q.question_id, is_correct: skipped ? null : mark === 'right', skip_reason: skipped ? mark : null }
    }),
    grading_revision: revision,
  }
}

// 标记为做错的题数
export function countWrong(marks) {
  return Object.values(marks).filter(m => m === 'wrong').length
}

// 卷子标签，如 '#128 数学练习卷 11月12日'；名字已含日期（默认名）时不再追加，名字为空时才用创建日期代替
export function paperLabel(paper) {
  const name = (paper.name || '').trim()
  let text = name
  if (!name) {
    // 从创建时间 'YYYY-MM-DD...' 里取出月和日，转成 'M月D日'
    const m = /(\d{4})-(\d{2})-(\d{2})/.exec(paper.created_at || '')
    text = m ? `${Number(m[2])}月${Number(m[3])}日` : ''
  }
  return `#${paper.id} ${text}`.replace(/\s+/g, ' ').trim()
}
