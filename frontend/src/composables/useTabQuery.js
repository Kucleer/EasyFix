import { ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { pickTab } from './tabQuery'

/**
 * 页内标签和地址 ?tab= 双向同步：
 * - 打开页面时按地址选标签，地址里的标签无效就用默认；
 * - 切换标签时用 router.replace 改地址（不新增历史记录，返回键不会在标签之间来回跳）；
 * - 地址被外部改变（比如从别的页面跳进来）时，标签跟着变。
 */
export function useTabQuery(keys, fallback) {
  const route = useRoute()
  const router = useRouter()
  const tab = ref(pickTab(route.query, keys, fallback))

  watch(() => route.query.tab, () => {
    const wanted = pickTab(route.query, keys, fallback)
    if (wanted !== tab.value) tab.value = wanted
  })

  watch(tab, value => {
    if (route.query.tab === value) return
    router.replace({ query: { ...route.query, tab: value } })
  })

  return tab
}
