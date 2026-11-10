// 录入与卷子相关的中文显示文字和小工具（纯函数，不依赖 Vue）

export const PAPER_TYPE_LABELS = { homework: '作业', chapter_practice: '章节练习', exam: '考试' }
export const EXAM_KIND_LABELS = { unit: '单元测', midterm: '期中', final: '期末', other: '其他' }
export const REVIEW_REASON_LABELS = {
  wrong_unclear: '不确定是否做错',
  text_unclear: '照片模糊或题干拿不准',
  kp_unsure: '考点拿不准',
  other: '其他',
}

// 卷子类型的显示文字；考试带细分，细分为"其他"时只显示"考试"
export function paperTypeLabel(paper) {
  if (!paper) return ''
  const base = PAPER_TYPE_LABELS[paper.paper_type] || paper.paper_type || ''
  if (paper.paper_type === 'exam' && paper.exam_kind && paper.exam_kind !== 'other') {
    const kind = EXAM_KIND_LABELS[paper.exam_kind] || paper.exam_kind
    return `${base} · ${kind}`
  }
  return base
}

// 待核对原因代码转中文，不认识的代码原样返回
export function reasonLabels(codes) {
  if (!Array.isArray(codes)) return []
  return codes.map(code => REVIEW_REASON_LABELS[code] || code)
}

// 分数文字，如 '85 / 100'；没有分数返回空串
export function scoreText(paper) {
  if (!paper) return ''
  const { score, full_score: fullScore } = paper
  if (score === null || score === undefined || fullScore === null || fullScore === undefined) return ''
  // Number() 会让 85.0 显示成 85，85.5 保持原样
  return `${Number(score)} / ${Number(fullScore)}`
}

// 按卷子分组，保持题目原有顺序；没有卷子的题归到最后一组
export function groupByPaper(questions) {
  const groups = []
  const byPaperId = new Map()
  let noPaper = null
  for (const question of questions || []) {
    if (!question.paper) {
      if (!noPaper) noPaper = { paper: null, questions: [] }
      noPaper.questions.push(question)
      continue
    }
    let group = byPaperId.get(question.paper.id)
    if (!group) {
      group = { paper: question.paper, questions: [] }
      byPaperId.set(question.paper.id, group)
      groups.push(group)
    }
    group.questions.push(question)
  }
  if (noPaper) groups.push(noPaper)
  return groups
}

// 题目所在那一页的照片地址，没有照片返回 null
export function pageImage(question) {
  return question && question.original_image ? '/uploads/' + question.original_image : null
}
