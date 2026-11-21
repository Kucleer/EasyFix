/**
 * 图表主题：学情页、周报页的 ECharts 图表共用同一套颜色。
 * 默认值取自样稿（docs/superpowers/specs/2026-11-21-workspace-mockup.html），
 * 页面上能读到 CSS 变量时以变量为准（变量定义在 styles/variables.css）。
 */

// 默认颜色：文字、强调文字、线条、主色、主色浅、绿（进步）、橙（留意）、灰（上周、对比）
export const CHART_THEME = {
  text: '#686e89',
  strong: '#1f2340',
  line: '#e6e5f2',
  main: '#4f46e5',
  soft: '#c7c4f7',
  green: '#17895a',
  orange: '#b4641a',
  grey: '#b4b4bb',
}

// 主题里的颜色对应的 CSS 变量；soft、grey 没有对应变量，总用默认值
const CSS_VARIABLES = {
  text: '--muted',
  strong: '--ink',
  line: '--line',
  main: '--brand',
  green: '--mint',
  orange: '--sun',
}

/** 用 getVar(变量名) 读 CSS 变量，读不到（空字符串）的用默认值，返回完整主题 */
export function readChartTheme(getVar) {
  const theme = { ...CHART_THEME }
  for (const [key, name] of Object.entries(CSS_VARIABLES)) {
    const value = String(getVar(name) || '').trim()
    if (value) theme[key] = value
  }
  return theme
}

/** 在组件里调用：从页面根元素读 CSS 变量得到主题 */
export function useChartTheme() {
  const css = getComputedStyle(document.documentElement)
  return readChartTheme(name => css.getPropertyValue(name))
}
