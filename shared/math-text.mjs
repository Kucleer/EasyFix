// 页面与 PDF 共用的文本处理和公式边界，禁止把题干作为 HTML 执行。
export const delimiters = [
  { left: '\\[', right: '\\]', display: true },
  { left: '\\(', right: '\\)', display: false },
  { left: '$$', right: '$$', display: true },
]

export function normalizeMathText(value) {
  const textarea = document.createElement('textarea')
  textarea.innerHTML = String(value ?? '')
  return textarea.value.replace(/<br\s*\/?>/gi, '\n')
}

export function renderMathText(element, value, autoRender) {
  const text = normalizeMathText(value)
  element.textContent = text
  const errors = []
  if (/[\x00-\x08\x0b\x0c\x0e-\x1f]/.test(text)) {
    errors.push('包含异常控制字符，请检查 LaTeX 反斜杠转义')
  }
  // auto-render 会忽略未闭合边界，提前报告，防止 PDF 静默打印源码。
  const boundary = /\\\(|\\\)|\\\[|\\\]|\$\$/g
  let open = null
  for (const match of text.matchAll(boundary)) {
    const token = match[0]
    if (!open) {
      if (token === '\\)' || token === '\\]') errors.push('公式缺少起始边界')
      else open = token
    } else {
      const close = delimiters.find(item => item.left === open).right
      if (token === close) open = null
      else errors.push('公式边界不匹配')
    }
  }
  if (open) errors.push('公式缺少结束边界')
  autoRender(element, {
    delimiters,
    trust: false,
    throwOnError: true,
    maxExpand: 200,
    maxSize: 20,
    macros: {},
    errorCallback: () => errors.push('公式语法有误，请检查花括号和 LaTeX 命令'),
  })
  // 未闭合花括号会让 auto-render 把整个区域当作普通文本，不能视为成功。
  const walker = document.createTreeWalker(element, NodeFilter.SHOW_TEXT)
  while (walker.nextNode()) {
    const node = walker.currentNode
    if (!node.parentElement?.closest('.katex') && /\\\(|\\\[|\$\$/.test(node.textContent)) {
      errors.push('公式未完成渲染，请检查花括号和公式边界')
    }
  }
  return [...new Set(errors)]
}

// PDF 模板使用相同模块；不向页面插入来自题干的脚本。
if (typeof window !== 'undefined') window.EasyFixMath = { renderMathText }
