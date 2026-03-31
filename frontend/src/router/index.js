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
    path: '/upload',
    name: 'Upload',
    component: () => import('@/views/Upload.vue'),
  },
  {
    path: '/stats',
    name: 'Stats',
    component: () => import('@/views/Stats.vue'),
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
    path: '/words',
    name: 'Words',
    component: () => import('@/views/Words.vue'),
  },
  {
    path: '/learning-reports',
    name: 'LearningReports',
    component: () => import('@/views/LearningReports.vue'),
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

export default router
