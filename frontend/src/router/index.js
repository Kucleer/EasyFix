import { createRouter, createWebHistory } from 'vue-router'

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
    path: '/review',
    name: 'ReviewQueue',
    component: () => import('@/views/ReviewQueue.vue'),
  },
  {
    path: '/papers',
    name: 'Papers',
    component: () => import('@/views/Papers.vue'),
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
    path: '/stats',
    redirect: '/learning-analysis',
  },
  {
    path: '/settings',
    name: 'Settings',
    component: () => import('@/views/Settings.vue'),
  },
  {
    path: '/management',
    name: 'Management',
    component: () => import('@/views/Management.vue'),
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
    // 手机批改：待批改列表；不进侧栏菜单，从首页"专项练习"那一格进入
    path: '/grade',
    name: 'GradeList',
    component: () => import('@/views/GradeList.vue'),
    meta: { title: '待批改' },
  },
  {
    // 手机批改：批改一份卷子（拍照 → 点对错 → 结果）
    path: '/grade/:id',
    name: 'GradePaper',
    component: () => import('@/views/GradePaper.vue'),
    meta: { title: '待批改' },
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
    path: '/learning-reports',
    name: 'LearningReports',
    component: () => import('@/views/LearningReports.vue'),
  },
  {
    path: '/motivation',
    name: 'Motivation',
    component: () => import('@/views/Motivation.vue'),
  },
  {
    path: '/star-map',
    name: 'StarMap',
    component: () => import('@/views/StarMap.vue'),
  },
  {
    path: '/learning-analysis',
    name: 'LearningAnalysis',
    component: () => import('@/views/LearningAnalysis.vue'),
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
