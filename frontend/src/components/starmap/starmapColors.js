// 知识星空的颜色和状态文字：红（薄弱）→ 黄（一般）→ 绿（掌握），没学的是灰色

const RED = [235, 87, 87]
const YELLOW = [242, 201, 76]
const GREEN = [88, 214, 141]
export const GREY = '110,112,124'

// 两个颜色之间按比例取中间色
function mix(a, b, k) {
  const t = Math.min(1, Math.max(0, k))
  return a.map((x, i) => Math.round(x + (b[i] - x) * t))
}

// 掌握度对应的颜色（'r,g,b' 文本）：0.15→0.55 由红到黄，0.55→1 由黄到绿；没学（null）是灰色
export function colorOf(value) {
  if (value === null || value === undefined) return GREY
  const color = value < 0.55 ? mix(RED, YELLOW, (value - 0.15) / 0.4) : mix(YELLOW, GREEN, (value - 0.55) / 0.45)
  return color.join(',')
}

// 把颜色调亮一些（k 为 0~1，越大越接近白色）
export function lighten(color, k) {
  return color.split(',').map(x => Math.round(Number(x) + (255 - Number(x)) * k)).join(',')
}

// 两种颜色的中间色，用于连线
export function between(a, b) {
  return mix(a.split(',').map(Number), b.split(',').map(Number), 0.5).join(',')
}

const STATUS_TEXT = { unlearned: '还没学', weak: '薄弱', fair: '一般', good: '较好', mastered: '已掌握' }

// 状态对应的中文
export function statusText(status) {
  return STATUS_TEXT[status] || ''
}
