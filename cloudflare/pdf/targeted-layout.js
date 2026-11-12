// 考点卷的版式：页眉 → 按模块分组的题目 → 另起一页的答案与解析（家长用）→ 页脚提示。
// 纯函数，不依赖浏览器；公式文本通过 index.js 传进来的 field 登记，之后统一渲染。

const SPACES = new Set(['s', 'm', 'l'])
const OPTION_PREFIX = /^(?:[A-Da-d]\s*[.、．)]|\([A-Da-d]\))\s*/

/** 题目总数；payload 格式不对时返回 -1，调用方据此拒绝。 */
export function targetedQuestionCount(payload) {
  if (!payload || !Array.isArray(payload.groups)) return -1
  let total = 0
  for (const group of payload.groups) {
    if (!group || !Array.isArray(group.questions)) return -1
    total += group.questions.length
  }
  return total
}

/** 一道题：题头只有题号，之后是题干、选项和按档位留出的作答空白。 */
function questionHtml(question, field) {
  if (!String(question.question_text || '').trim()) throw new Error(`题目${question.number}缺少题干`)
  let content = field(question.question_text, `题目${question.number}`)
  for (const letter of ['a', 'b', 'c', 'd']) {
    const option = question['option_' + letter]
    if (option) content += field(letter.toUpperCase() + '. ' + String(option).replace(OPTION_PREFIX, ''), '选项' + letter.toUpperCase())
  }
  const space = SPACES.has(question.space) ? question.space : 's'
  return `<section class="question"><div class="question-header">第 ${question.number} 题</div>${content}<div class="answer-space space-${space}"></div></section>`
}

/** 答案页的一行：题号、来源信息，然后是答案和（有的话）解析。 */
function answerHtml(item, field, escape) {
  const meta = [item.point, item.form, item.reason].filter(Boolean).map(escape).join('　|　')
  let content = `<div class="answer-meta">第 ${item.number} 题　${meta}</div>`
  content += `<div class="answer-line">答案：${field(item.answer, '答案' + item.number)}</div>`
  if (String(item.analysis || '').trim()) content += `<div class="answer-line">解析：${field(item.analysis, '解析' + item.number)}</div>`
  return `<div class="answer-row">${content}</div>`
}

/** 放进 <body> 的 HTML。field(text, label) 登记公式文本并返回占位元素，escape 转义普通文字。 */
export function targetedBody(payload, field, escape) {
  const fill = label => `<span class="fill">${label}：<i></i></span>`
  const header = `<header class="paper-header"><h1>${escape(payload.title)}</h1><div class="code">${escape(payload.code)}</div><div class="fills">${fill('姓名')}${fill('日期')}${fill('用时')}</div></header>`
  const groups = payload.groups.map(group =>
    `<section class="group"><h2>${escape(group.title)}</h2>${group.questions.map(question => questionHtml(question, field)).join('')}</section>`).join('')
  const answers = `<section class="answers"><h2>答案与解析（家长用）</h2><div class="code">${escape(payload.code)}</div>${(payload.answers || []).map(item => answerHtml(item, field, escape)).join('')}</section>`
  return `${header}${groups}${answers}<footer class="paper-footer">${escape(payload.footer)}</footer>`
}

/** 这套版式的 CSS：留白三档 15 / 30 / 50 毫米，答案页另起一页，题目不被分页切开。 */
export const TARGETED_STYLE = '@page{size:A4;margin:18mm 16mm 20mm}*{box-sizing:border-box}body{margin:0;color:#111;font-family:"Noto Sans CJK SC","Noto Sans SC",sans-serif;font-size:11pt;line-height:1.9}'
  + 'h1{text-align:center;font-size:18pt;margin:0}h2{font-size:13pt;margin:6mm 0 3mm;border-bottom:2px solid #333}'
  + '.code{text-align:center;color:#555;font-size:10pt}.fills{display:flex;gap:8mm;margin:3mm 0 4mm}.fill{flex:1;display:flex;align-items:baseline;font-size:10pt}.fill i{flex:1;border-bottom:1px solid #333;margin-left:2mm}'
  + '.question{border-top:1px solid #888;padding-top:3mm;margin-bottom:4mm;break-inside:avoid}.question.long{break-inside:auto}.question-header{font-size:9pt;color:#333}'
  + '.math-field{white-space:pre-wrap;overflow-wrap:anywhere}.katex{white-space:nowrap}.katex-display{margin:3mm 0;break-inside:avoid}'
  + '.answer-space{height:12mm}.space-s{height:15mm}.space-m{height:30mm}.space-l{height:50mm}'
  + '.answers{break-before:page}.answer-row{border-top:1px solid #ccc;padding:2mm 0;break-inside:avoid}.answer-meta{font-size:9pt;color:#444}.answer-line{display:flex;gap:1mm}.answer-line .math-field{flex:1}'
  + '.paper-footer{margin-top:8mm;text-align:center;font-size:10pt;color:#555}'
