/**
 * 页内标签与地址 ?tab= 的对应规则（纯函数，方便测试）；和路由同步的写法在 useTabQuery.js。
 */

/** 地址里的 tab 是有效标签就用它，否则用默认标签 */
export function pickTab(query, keys, fallback) {
  const tab = query && typeof query.tab === 'string' ? query.tab : ''
  return keys.includes(tab) ? tab : fallback
}
