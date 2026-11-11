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

/** 带读图异常标记且没被人改过，就算有提示（与后端 has_warning 一致）。 */
export function hasWarning(item) {
  return Boolean(item.flags && item.flags.length) && !item.edited
}

/** "全部录入"包含的题：未处理、判断为做错、没有提示（与后端 accept_all_seqs 一致）。 */
export function acceptAllSeqs(items) {
  return items
    .filter(item => item.state === 'open' && item.verdict === 'wrong' && !hasWarning(item))
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
