// 翻一翻的纯逻辑：卡片标签、卡片要显示的内容、进度文字和页面状态（不依赖 Vue，方便 node --test）

// 附件在 R2 里存的是"键"，前端统一拼成 /uploads/ 开头的地址（和错题详情一致）
const UPLOADS = '/uploads/'

/** 去掉首尾空白；null、数字等都先变成字符串 */
function clean(value) {
  return value == null ? '' : String(value).trim()
}

/** 把存储键变成图片地址；空键返回空字符串 */
function image_url(key) {
  const text = clean(key)
  return text ? UPLOADS + text : ''
}

/** 卡片顶上的标签：有考点写"学科 · 考点"，没挂考点只写学科名（学科名也没有时写"错题"） */
export function card_tag(card) {
  const subject = clean(card.subject_name) || '错题'
  const point = clean(card.point_name)
  return point ? `${subject} · ${point}` : subject
}

/**
 * 一张卡片要显示的内容（后端卡片 → 页面用的数据）
 * - stem：题干；为空时 image_only 为真，直接显示原图
 * - images：原图地址列表；有题干时页面把它收在"看原图"里
 * - wrong_answer：你上次写的；为空时页面不显示这一块
 */
export function card_view(card) {
  const stem = clean(card.parsed_question)
  const images = (Array.isArray(card.images) ? card.images : []).map(image_url).filter(Boolean)
  return {
    id: card.id,
    tag: card_tag(card),
    stem,
    images,
    image_only: !stem && images.length > 0,
    wrong_answer: clean(card.wrong_answer),
    answer: clean(card.answer),
    analysis: clean(card.analysis),
    analysis_image: image_url(card.analysis_image),
  }
}

/** 顶部的进度文字：第几张按"已翻张数 + 1"数，最多到总数 */
export function progress_text(done, total) {
  const current = Math.min(done + 1, total)
  return `第 ${current} 张 / 共 ${total} 张`
}

/** 顶部进度条每一格的状态：'done' 翻过、'now' 正在翻、'' 还没翻 */
export function progress_dots(done, total) {
  return Array.from({ length: total }, (_, index) => {
    if (index < done) return 'done'
    return index === done ? 'now' : ''
  })
}

/**
 * 页面该显示什么：'empty' 今天没有要翻的、'finished' 今天翻完了、'card' 正在翻
 * today 是 /api/flip/today 的返回，index 是这次打开后翻到 cards 里的第几张
 */
export function page_state(today, index) {
  if (today.total <= 0) return 'empty'
  // 已翻张数到了总数，或者这次拿到的卡片都翻过了，就算翻完（不能继续刷）
  if (today.done >= today.total || index >= today.cards.length) return 'finished'
  return 'card'
}

/** 翻完后的一句话 */
export function finish_text(total) {
  return `${total} 张都看过了，明天再来。`
}
