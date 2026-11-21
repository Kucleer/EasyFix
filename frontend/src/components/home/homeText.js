// 首页用到的几个纯函数：日期怎么写、几天前、打卡条每一天的状态。
// 日期一律是北京时间的 'YYYY-MM-DD' 文本（后端给的时间也是北京时间），不依赖运行环境的时区。

// 一周七天的叫法，从周一开始（和周报、/api/home 的 week.days 顺序一致）
export const WEEKDAY_NAMES = ['一', '二', '三', '四', '五', '六', '日']

/**
 * 把 'YYYY-MM-DD'（或 'YYYY-MM-DD HH:MM:SS'）拆成年、月、日三个数字；格式不对返回 null
 */
function parse_date(text) {
  const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(text || '')
  if (!match) return null
  return { year: Number(match[1]), month: Number(match[2]), day: Number(match[3]) }
}

/**
 * 一个日期是从 1970-01-01 起的第几天（按 UTC 计算，只用来算两天相差几天）
 */
function day_number(parts) {
  return Math.round(Date.UTC(parts.year, parts.month - 1, parts.day) / 86400000)
}

/**
 * 日期是星期几：0 表示周一，6 表示周日
 */
function weekday_index(parts) {
  // 1970-01-01 是周四，周四在 WEEKDAY_NAMES 里排第 3 个
  return ((day_number(parts) + 3) % 7 + 7) % 7
}

/**
 * 每日一句上方的小字，例如 '周六好 · 11 月 21 日'
 */
export function greeting_text(today_text) {
  const parts = parse_date(today_text)
  if (!parts) return ''
  return `周${WEEKDAY_NAMES[weekday_index(parts)]}好 · ${parts.month} 月 ${parts.day} 日`
}

/**
 * 短日期，例如 '2026-11-18 09:30:00' → '11 月 18 日'；格式不对返回空字符串
 */
export function short_date_text(text) {
  const parts = parse_date(text)
  return parts ? `${parts.month} 月 ${parts.day} 日` : ''
}

/**
 * 本周的日期范围：同一个月写 '11 月 16 日 – 22 日'，跨月写 '11 月 30 日 – 12 月 6 日'
 */
export function week_range_text(monday, sunday) {
  const start = parse_date(monday)
  const end = parse_date(sunday)
  if (!start || !end) return '这一周'
  const end_text = start.month === end.month ? `${end.day} 日` : `${end.month} 月 ${end.day} 日`
  return `${start.month} 月 ${start.day} 日 – ${end_text}`
}

/**
 * 从某个日期（可以带时间）到今天过了几天；任一日期格式不对返回 null
 */
export function days_ago(from_text, today_text) {
  const from = parse_date(from_text)
  const today = parse_date(today_text)
  if (!from || !today) return null
  return day_number(today) - day_number(from)
}

/**
 * "出一份考点卷"那一格的副标题
 * 没出过：'还没有出过考点卷'；今天出过：'今天刚出过一份'；其余：'上次出卷是 N 天前'
 */
export function targeted_hint(last_created_at, today_text) {
  const days = days_ago(last_created_at, today_text)
  if (days === null) return '还没有出过考点卷'
  if (days <= 0) return '今天刚出过一份'
  return `上次出卷是 ${days} 天前`
}

/**
 * 打卡条上一天的样式名：'done' 有学习记录，'today' 今天，'future' 还没到；可以同时有 done 和 today
 */
export function day_state(date_text, active, today_text) {
  const names = []
  if (active) names.push('done')
  if (date_text === today_text) names.push('today')
  else if (date_text > today_text) names.push('future')
  return names.join(' ')
}
