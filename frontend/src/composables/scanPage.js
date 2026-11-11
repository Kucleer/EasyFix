// 整页识别录入的纯逻辑（不依赖 Vue / 网络，可直接用 node --test 测试）

// 读图异常标记 -> 页面提示文字（设计 6.4）
export const FLAG_TEXTS = {
  broken_formula: '公式可能读错，请对照原图',
  unsolvable: '题干可能缺内容，请对照原图',
  merged: '可能串题，请对照原图',
  figure_needed: '这题有图，请对照原图补条件',
}

// 上传图片大小上限；超过就先压缩
export const MAX_UPLOAD_BYTES = 10 * 1024 * 1024

/** 把一道题的读图异常标记转成提示文字列表（未知标记忽略）。 */
export function warningTexts(item) {
  return ((item && item.flags) || []).map(flag => FLAG_TEXTS[flag]).filter(Boolean)
}

/** 页面状态对应的进度文字，非处理中状态返回空串。 */
export function stepLabel(status) {
  if (status === 'uploaded' || status === 'reading') return '正在读图'
  if (status === 'analyzing') return '正在整理题目'
  if (status === 'rescanning') return '正在重扫一次'
  return ''
}

/** 带读图异常标记且没被人改过，就算有提示（录入前要多问一句，也不进"全部录入"）。 */
export function hasWarning(item) {
  return Boolean(item.flags && item.flags.length) && !item.edited
}

/** "全部录入"包含的题：未处理、判断为做错、没有提示；手工加的要保存过才算（页面按这个顺序逐道调"录入一道"）。 */
export function acceptAllSeqs(items) {
  return items
    .filter(item => item.state === 'open' && item.verdict === 'wrong' && !hasWarning(item))
    // 手工加的空白题没填过内容，不能跟着"全部录入"存成空题
    .filter(item => !(item.source === 'manual' && !item.edited))
    .map(item => item.seq)
}

/** 把题目分成主列表和"模型判对"折叠区，均按 seq 排序。 */
export function groupItems(items) {
  const by_seq = (a, b) => a.seq - b.seq
  // 模型判对且还没处理的题，收进折叠区
  const is_model_right = item => item.verdict === 'right' && item.source === 'model'
  const main = items
    .filter(item => item.state !== 'dismissed' && !is_model_right(item))
    .sort(by_seq)
  const right = items
    .filter(item => is_model_right(item) && item.state === 'open')
    .sort(by_seq)
  return { main, right }
}

/** 主列表里已录入和待处理的数量。 */
export function progressCounts(items) {
  const { main } = groupItems(items)
  return {
    accepted: main.filter(item => item.state === 'accepted').length,
    remaining: main.filter(item => item.state === 'open').length,
  }
}

/** "拿不准"题的提示语；不是 unsure 返回空串。 */
export function unsureHint(item) {
  if (item.verdict !== 'unsure') return ''
  return item.reason ? '模型拿不准：' + item.reason : '没看清孩子的答案，请对照原图判断'
}

/** 文件是否超过上传上限、需要压缩。 */
export function needsCompression(size) {
  return size > MAX_UPLOAD_BYTES
}

/** 等比缩放到长边不超过 max_side，取整；不需要缩小时原样返回。 */
export function scaledSize(width, height, maxSide) {
  const longest = Math.max(width, height)
  if (longest <= maxSide) return { width, height }
  const ratio = maxSide / longest
  return { width: Math.round(width * ratio), height: Math.round(height * ratio) }
}

// ---------------------------------------------------------------- 整理区

// 年级编号 -> 名称（与录入页的年级选项一致）
const GRADE_NAMES = ['', '一年级', '二年级', '三年级', '四年级', '五年级', '六年级',
  '初一', '初二', '初三', '高一', '高二', '高三']

// 原图缩放的上下限
const MIN_ZOOM = 1
const MAX_ZOOM = 4

// 修改表单里能改的字段及其空值
const EDITABLE_DEFAULTS = {
  question_no: '', parsed_question: '', wrong_answer: '', answer: '', analysis: '',
  knowledge_point_ids: [], primary_knowledge_point_id: null, error_types: [], difficulty: 3,
}

/** 顶部统计：识别出几道（手工加的不算），模型判断几道做错（补成错题的原本判对，不算）。 */
export function pageSummary(items) {
  return {
    total: items.filter(item => item.source !== 'manual').length,
    wrong: items.filter(item => item.source === 'model' && item.verdict === 'wrong').length,
  }
}

/** 卡片上的题目名称："第 3 题"；没填题号时给一句说明。 */
export function itemLabel(item) {
  const no = String(item.question_no || '').trim()
  return no ? `第 ${no} 题` : '没填题号的题'
}

/** 年级学期文字，如"六年级上"；没有年级时返回空串。 */
export function gradeTermText(grade, semester) {
  const name = GRADE_NAMES[grade] || ''
  if (!name) return ''
  if (semester === 1) return name + '上'
  if (semester === 2) return name + '下'
  return name
}

/** 考点名称，主考点排在最前，用顿号连接；目录里找不到的编号忽略。 */
export function knowledgeText(ids, primaryId, names) {
  const ordered = [...(ids || [])].sort((a, b) => (b === primaryId) - (a === primaryId))
  return ordered.map(id => names[id]).filter(Boolean).join('、')
}

/** 取一道题里可修改的字段，作为修改表单的初值（数组复制一份，改表单不影响原题）。 */
export function editableFields(item) {
  const fields = {}
  for (const [key, empty] of Object.entries(EDITABLE_DEFAULTS)) {
    const value = item[key] ?? empty
    fields[key] = Array.isArray(value) ? [...value] : value
  }
  return fields
}

/**
 * 录入一道失败后怎么办（逐道录入和"全部录入"共用），status 是接口返回的状态码（没收到响应时为空）：
 * - 409：这一页或这道题已经变了，刷新这一页；"全部录入"就此停下；
 * - 其他 4xx：后端拒绝了这道题（公式写坏、没选主考点等），卡片切到修改状态，顶部显示原因；
 * - 其他（网络断开、超时、5xx）：只提示错误。
 * "全部录入"遇到任何失败都停在这一道，已录入的不受影响。
 */
export function acceptFailureAction(status) {
  if (status === 409) return 'refresh'
  if (status >= 400 && status < 500) return 'edit'
  return 'report'
}

/** "全部录入"按钮上的进度文字：正在录第 index+1 道，共 total 道，如"正在录入 2/5"。 */
export function acceptAllProgressText(index, total) {
  return `正在录入 ${index + 1}/${total}`
}

/**
 * "全部录入"：按 seqs 的顺序逐道调 acceptOne(seq)（一次录一道，后端没有一次录多道的接口），
 * 每录一道前调 onProgress(index, total)；某一道失败就停在那里，后面的不再录。
 * 返回 { accepted: 成功的道数, failedSeq: 失败的那道（全部成功时为 null）, error: 失败时的异常 }。
 */
export async function runAcceptAll(seqs, acceptOne, onProgress = () => {}) {
  let accepted = 0
  for (let index = 0; index < seqs.length; index += 1) {
    onProgress(index, seqs.length)
    try {
      await acceptOne(seqs[index])
    } catch (error) {
      return { accepted, failedSeq: seqs[index], error }
    }
    accepted += 1
  }
  return { accepted, failedSeq: null, error: null }
}

/**
 * 围绕指针位置缩放原图：view 是 { scale, x, y }（平移量，单位像素，变换原点在左上角），
 * point 是指针在图框里的坐标，factor 是缩放倍数；结果限制在 1–4 倍，回到 1 倍时位置复位。
 */
export function zoomAt(view, point, factor) {
  const scale = Math.min(MAX_ZOOM, Math.max(MIN_ZOOM, view.scale * factor))
  if (scale === MIN_ZOOM) return { scale, x: 0, y: 0 }
  // 指针下的那一点在图上的坐标，缩放后仍应落在指针下
  const image_x = (point.x - view.x) / view.scale
  const image_y = (point.y - view.y) / view.scale
  return { scale, x: point.x - image_x * scale, y: point.y - image_y * scale }
}
