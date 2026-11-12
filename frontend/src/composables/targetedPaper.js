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

// 批改请求体；question_id 是错题编号（后端按它校验），跳过的题 is_correct 为 null。
// 还有"拿不准"的题时不能提交（页面上提交按钮是灰的），这里再拦一次，免得把拿不准当成错提交
export function gradePayload(questions, marks, revision) {
  if (countUnsure(marks) > 0) throw new Error('还有拿不准的题没有定下对错')
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

// 练习中心里点"查看""生成 PDF"时要去的出卷页地址：只有没批改的考点卷回出卷页
// （在那里接着准备相似题、看卷面、生成 PDF）；已批改的考点卷和别的练习返回 null，照旧用详情弹窗
export function resumeLink(paper) {
  if (!paper || paper.kind !== 'targeted' || paper.reviewed) return null
  return `/targeted-paper?paper_id=${paper.id}`
}

// 出卷页带 ?paper_id= 打开时，这份卷子能不能接着准备：是考点卷、没批改、没删除
export function canResume(paper) {
  return !!paper && paper.kind === 'targeted' && !paper.reviewed && !paper.deleted
}

// 题面是相似题、但还没配相似题的题数（出卷页准备进度的总数）
export function pendingSimilarCount(questions) {
  return (questions || []).filter(q => q.form === 'similar' && !q.similar_question_id).length
}

// ---------------------------------------------------------------- 批改识别预批（设计 2026-11-12-grading-recognition-design.md）

// 复核列表里结果的文字：对、错、拿不准、没做、题目有误
export const MARK_LABELS = { right: '对', wrong: '错', unsure: '拿不准', not_done: '没做', bad_question: '题目有误' }

// 识别结果按题目行编号排成字典：{题目行编号: {student_answer, verdict, page}}
export function recognitionMap(items) {
  const map = {}
  for (const item of items || []) map[item.id] = item
  return map
}

// 识别预批合并成复核的初始标记：判对算对、判错算错，其余（拿不准、识别结果里没有的题）都是"拿不准"
export function marksFromRecognition(questions, items) {
  const map = recognitionMap(items)
  const marks = {}
  for (const q of questions || []) {
    const verdict = map[q.id]?.verdict
    marks[q.id] = verdict === 'right' || verdict === 'wrong' ? verdict : 'unsure'
  }
  return marks
}

// "拿不准"的题数；不为 0 时不能提交
export function countUnsure(marks) {
  return Object.values(marks).filter(m => m === 'unsure').length
}

// 要重点看的题：做错的和拿不准的。"只看错的和拿不准的"按这份名单筛，
// 名单在预批时定下，之后改成对的题也不会从眼前消失
export function focusIds(marks) {
  return new Set(Object.keys(marks).filter(id => marks[id] === 'wrong' || marks[id] === 'unsure').map(Number))
}

// 复核列表要显示的题；onlyFocus 为真时只留名单里的，顺序始终按卷面题号
export function visibleQuestions(questions, focus, onlyFocus) {
  const list = questions || []
  return onlyFocus ? list.filter(q => focus.has(q.id)) : list
}

// 卷面上印的是原题还是相似题
export function shownForm(q) {
  return q.shown_form || q.form || 'original'
}

// 手动组的卷子打印后删过题：题号往前挪，和纸上对不上（这时不识别，改为手动批）；考点卷题号固定
export function numberingChanged(paper) {
  if (!paper || paper.kind === 'targeted') return false
  const total = paper.total_questions
  return Number.isInteger(total) && total !== (paper.questions || []).length
}
