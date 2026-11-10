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
