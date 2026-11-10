// 默写题的格子布局与按词判对（纯逻辑，不依赖 Vue）

const LETTER_RE = /[a-zA-Z]/

/**
 * 生成默写题的字母格子。
 * 无 tokens：沿用旧规则，字母为可填格，其余字符（含空格）为预填格。
 * 有 tokens：词间空格不生成格子，改用下一格的 gapBefore 表示；
 * 不空出的词全部预填；空出的词中字母可填、非字母预填；有 hint 时首字符预填。
 * @param {object} question 题目，含 english 与可选 tokens
 * @returns {Array<{char: string, fixed: boolean, token: number, gapBefore: boolean}>}
 */
export function buildCells(question) {
  const tokens = question.tokens
  if (!Array.isArray(tokens) || tokens.length === 0) {
    return Array.from(question.english || '').map(char => ({
      char, fixed: !LETTER_RE.test(char), token: 0, gapBefore: false,
    }))
  }
  const cells = []
  tokens.forEach((tok, ti) => {
    Array.from(tok.text).forEach((char, ci) => {
      // 首字符在有提示时固定；非字母字符始终固定
      const fixed = !tok.blank || !LETTER_RE.test(char) || (ci === 0 && !!tok.hint)
      cells.push({ char, fixed, token: ti, gapBefore: ti > 0 && ci === 0 })
    })
  })
  return cells
}

/**
 * 统计需要作答的词数（无 tokens 时整题算 1 个）。
 * @param {object} question 题目
 * @returns {number}
 */
export function blankTokenCount(question) {
  const tokens = question.tokens
  if (!Array.isArray(tokens) || tokens.length === 0) return 1
  return tokens.filter(t => t.blank).length
}

/**
 * 判对：把各格内容拼回整条英文，按词（有 tokens）或整句（无 tokens）不区分大小写比较。
 * @param {object} question 题目
 * @param {string[]} answers 与 buildCells 等长的各格内容
 * @returns {{correct: boolean, userAnswer: string, tokenResults: Array<{i: number, ok: boolean}> | null}}
 */
export function judge(question, answers) {
  const cells = buildCells(question)
  // 预填格用格子自带的字符，可填格取用户输入（缺失视为空）
  const chars = cells.map((c, i) => (c.fixed ? c.char : (answers[i] ?? '')))
  const tokens = question.tokens
  if (!Array.isArray(tokens) || tokens.length === 0) {
    const userAnswer = chars.join('')
    return {
      correct: userAnswer.toLowerCase() === (question.english || '').toLowerCase(),
      userAnswer,
      tokenResults: null,
    }
  }
  // 按词拼回文本
  const words = tokens.map(() => '')
  cells.forEach((c, i) => { words[c.token] += chars[i] })
  const tokenResults = []
  tokens.forEach((tok, i) => {
    if (tok.blank) tokenResults.push({ i, ok: words[i].toLowerCase() === tok.text.toLowerCase() })
  })
  return {
    correct: tokenResults.every(r => r.ok),
    userAnswer: words.join(' '),
    tokenResults,
  }
}

/**
 * 把字符按「是否写错」连续归并成片段；只含空格的一段永远不算错。
 * @param {string} text 原文
 * @param {boolean[]} wrongFlags 与 text 等长的逐字符错误标记
 * @returns {Array<{text: string, wrong: boolean}>}
 */
function group_segments(text, wrongFlags) {
  const segments = []
  for (let k = 0; k < text.length; k++) {
    const ch = text[k]
    // 空格对齐和其它字符一样，但只由空格组成的片段永远不标红
    const wrong = ch === ' ' ? false : !!wrongFlags[k]
    const last = segments[segments.length - 1]
    if (last && last.wrong === wrong) last.text += ch
    else segments.push({ text: ch, wrong })
  }
  return segments
}

/**
 * 对比正确答案与实际作答，用最长公共子序列（不区分大小写）对齐字符。
 * expected 中没对上的字符为写错或漏写，actual 中没对上的字符为多写或写错。
 * actual 为空时：expected 全部算错，actual 返回空数组。
 * @param {string} expected 正确答案
 * @param {string} actual 实际作答
 * @returns {{expected: Array<{text: string, wrong: boolean}>, actual: Array<{text: string, wrong: boolean}>}}
 */
export function diffAnswer(expected, actual) {
  const exp = expected == null ? '' : String(expected)
  const act = actual == null ? '' : String(actual)
  // 没有作答：正确答案整体标红，作答侧为空
  if (!act) {
    return { expected: group_segments(exp, new Array(exp.length).fill(true)), actual: [] }
  }
  // 不区分大小写的 LCS 动态规划表
  const a = exp.toLowerCase()
  const b = act.toLowerCase()
  const n = a.length
  const m = b.length
  const dp = Array.from({ length: n + 1 }, () => new Array(m + 1).fill(0))
  for (let i = n - 1; i >= 0; i--) {
    for (let j = m - 1; j >= 0; j--) {
      dp[i][j] = a[i] === b[j] ? dp[i + 1][j + 1] + 1 : Math.max(dp[i + 1][j], dp[i][j + 1])
    }
  }
  // 回溯对齐，标记两侧哪些字符被匹配
  const expMatched = new Array(n).fill(false)
  const actMatched = new Array(m).fill(false)
  let i = 0
  let j = 0
  while (i < n && j < m) {
    if (a[i] === b[j]) {
      expMatched[i] = true
      actMatched[j] = true
      i++
      j++
    } else if (dp[i + 1][j] >= dp[i][j + 1]) {
      i++
    } else {
      j++
    }
  }
  return {
    expected: group_segments(exp, expMatched.map(v => !v)),
    actual: group_segments(act, actMatched.map(v => !v)),
  }
}

/**
 * 按逐词结果给正确答案的「词」标红：ok 为 false 的词算错，其余不算。
 * 词按空白切分，索引与 tokenResults 的 i 对应；词间空格不标红。
 * @param {string} english 完整英文
 * @param {Array<{i: number, ok: boolean}>} tokenResults 逐词结果
 * @returns {Array<{text: string, wrong: boolean}>}
 */
function token_segments(english, tokenResults) {
  const okMap = {}
  for (const r of tokenResults) {
    if (r && typeof r.i === 'number') okMap[r.i] = r.ok
  }
  const segments = []
  // 用正则捕获空格串，保留词与词之间的空白
  const parts = (english || '').split(/( +)/)
  let wordIndex = 0
  for (const part of parts) {
    if (part === '') continue
    if (/^ +$/.test(part)) {
      segments.push({ text: part, wrong: false })
      continue
    }
    segments.push({ text: part, wrong: okMap[wordIndex] === false })
    wordIndex++
  }
  return segments
}

/**
 * 计算一条作答的高亮片段：正确答案侧优先用逐词结果，缺失时回退到字符级对比；
 * 实际作答侧始终用字符级对比标红。
 * @param {object} item 含 english、userAnswer/user_answer、可选 tokenResults/token_results
 * @returns {{expected: Array<{text: string, wrong: boolean}>, actual: Array<{text: string, wrong: boolean}>}}
 */
export function answerSegments(item) {
  const english = item.english || ''
  const userAnswer = item.userAnswer ?? item.user_answer ?? ''
  const diff = diffAnswer(english, userAnswer)
  const tokenResults = item.tokenResults ?? item.token_results
  // 有逐词结果时用它高亮正确答案，更贴合「按词判对」的判定
  if (Array.isArray(tokenResults) && tokenResults.length > 0) {
    return { expected: token_segments(english, tokenResults), actual: diff.actual }
  }
  return diff
}

/**
 * 默写题答题前是否自动发音：仅当题型为默写(1)、带 tokens 且等级为 1 或 2 时不发音。
 * @param {object} question 题目
 * @param {number} reviewType 复习题型
 * @returns {boolean}
 */
export function shouldPlayBeforeAnswer(question, reviewType) {
  const hasTokens = Array.isArray(question.tokens) && question.tokens.length > 0
  if (reviewType === 1 && hasTokens && [1, 2].includes(question.dictation_level)) return false
  return true
}
