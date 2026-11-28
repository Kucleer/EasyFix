import { createRouter, createWebHistory } from 'vue-router'

/**
 * 生成"旧地址跳到新地址"的跳转函数：原地址上的其余参数（如 subject_id）原样带过去。
 * tab 有值时作为新页面的标签放在最前面；原地址自己的 tab 不带（旧页面的标签名对新页面没有意义）。
 */
function redirect_to(path, tab = '') {
  return (to) => {
    const { tab: _old_tab, ...rest } = to.query
    const query = tab ? { tab, ...rest } : rest
    return { path, query, hash: to.hash }
  }
}

const routes = [
  {
    path: '/',
    name: 'Home',
    component: () => import('@/views/Home.vue'),
  },
  {
    path: '/questions',
    name: 'Questions',
    component: () => import('@/views/Questions.vue'),
  },
  {
    // 待核对合进错题页的"待核对"标签
    path: '/review',
    redirect: redirect_to('/questions', 'review'),
  },
  {
    // 卷子和作业合进错题页的"卷子和作业"标签，筛选参数照带
    path: '/papers',
    redirect: redirect_to('/questions', 'papers'),
  },
  {
    path: '/papers/:id',
    name: 'PaperDetail',
    component: () => import('@/views/PaperDetail.vue'),
  },
  {
    path: '/upload',
    name: 'Upload',
    component: () => import('@/views/Upload.vue'),
  },
  {
    // 旧的统计页、知识星空、知识点分析都合进学情页
    path: '/stats',
    redirect: redirect_to('/insight'),
  },
  {
    path: '/star-map',
    redirect: redirect_to('/insight'),
  },
  {
    path: '/learning-analysis',
    redirect: redirect_to('/insight'),
  },
  {
    // 学情：考点（知识星空 + 考点明细）和单词两个标签
    path: '/insight',
    name: 'Insight',
    component: () => import('@/views/Insight.vue'),
  },
  {
    path: '/settings',
    name: 'Settings',
    component: () => import('@/views/Settings.vue'),
  },
  {
    // 资料管理合进设置页
    path: '/management',
    redirect: redirect_to('/settings'),
  },
  {
    path: '/practice-sets',
    name: 'PracticeSets',
    component: () => import('@/views/PracticeSets.vue'),
  },
  {
    // 出练习卷（考点卷）：可带 ?subject_id= 预选学科，或 ?paper_id= 接着准备一份没批改的考点卷；不进侧栏菜单
    path: '/targeted-paper',
    name: 'TargetedPaper',
    component: () => import('@/views/TargetedPaper.vue'),
    meta: { title: '出练习卷' },
  },
  {
    // 练习只有一个列表：旧的待批改地址跳到练习中心，只看待批改的卷子
    path: '/grade',
    redirect: { path: '/practice-sets', query: { pending: '1' } },
  },
  {
    // 手机批改：批改一份卷子（拍照 → 点对错 → 结果）
    path: '/grade/:id',
    name: 'GradePaper',
    component: () => import('@/views/GradePaper.vue'),
    meta: { title: '批改' },
  },
  {
    path: '/reading',
    name: 'Reading',
    component: () => import('@/views/Reading.vue'),
  },
  {
    path: '/reading-test/:id',
    name: 'ReadingTest',
    component: () => import('@/views/ReadingTest.vue'),
  },
  {
    path: '/words',
    name: 'Words',
    component: () => import('@/views/Words.vue'),
  },
  {
    // 翻一翻：每天一组旧错题卡片（菜单"更多"和首页大卡进入，不占手机底部格子）
    path: '/flip',
    name: 'Flip',
    component: () => import('@/views/Flip.vue'),
    meta: { title: '翻一翻' },
  },
  {
    path: '/flip/english',
    redirect: '/flip',
  },
  {
    // 周报：每周一期，打开时会自动补做还没生成好的那一期
    path: '/learning-reports',
    name: 'WeeklyReport',
    component: () => import('@/views/WeeklyReport.vue'),
  },
  {
    // 旧报告：以前生成的学习报告，只能看和删
    path: '/learning-reports/legacy',
    name: 'LearningReports',
    component: () => import('@/views/LearningReports.vue'),
    meta: { title: '旧报告' },
  },
  {
    // 成就：不在菜单里，地址保留，能直接打开
    path: '/motivation',
    name: 'Motivation',
    component: () => import('@/views/Motivation.vue'),
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

// 发布新版本后，部署前就打开的页面还在用旧的入口文件，点进别的页面时会去要已经不存在的旧页面文件，
// 加载失败（报 "Failed to fetch dynamically imported module"）。这时直接整页打开目标地址，拿到新版本。
// 用 sessionStorage 记一下，同一个地址只自动刷新一次，避免真出错时无限刷新。
const RELOAD_KEY = 'easyfix-chunk-reload'
const CHUNK_ERROR = /Failed to fetch dynamically imported module|Importing a module script failed|error loading dynamically imported module/i

router.onError((error, to) => {
  if (!CHUNK_ERROR.test(String(error?.message || error))) return
  const target = to?.fullPath || window.location.pathname
  let last = null
  try { last = sessionStorage.getItem(RELOAD_KEY) } catch { /* 隐私模式等读不到时照样刷新 */ }
  if (last === target) return
  try { sessionStorage.setItem(RELOAD_KEY, target) } catch { /* 忽略 */ }
  window.location.assign(target)
})

// 正常进入页面后清掉记录，下次发布还能再自动刷新一次
router.afterEach(() => {
  try { sessionStorage.removeItem(RELOAD_KEY) } catch { /* 忽略 */ }
})

export default router
