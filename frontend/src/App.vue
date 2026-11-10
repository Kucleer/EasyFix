<template>
  <div class="app-shell">
    <aside class="app-sidebar">
      <RouterLink class="app-brand" to="/"><span class="brand-mark">E</span>EasyFix</RouterLink>
      <nav aria-label="学习导航"><div v-for="group in navigation" :key="group.label" class="nav-group"><p class="nav-label">{{ group.label }}</p><RouterLink v-for="item in group.items" :key="item.path" :to="item.path" class="nav-link" :class="{ active: isActive(item.path) }"><el-icon><component :is="item.icon" /></el-icon><span>{{ item.label }}</span><b v-if="item.badge && reviewCountStore.pending > 0" class="nav-badge">{{ reviewCountStore.pending }}</b></RouterLink></div></nav>
      <p class="sidebar-note">每一次订正，都是新的进步。</p>
    </aside>
    <div class="app-workspace"><header class="app-topbar"><span class="app-breadcrumb">我的学习空间 <span>/</span> <strong>{{ currentTitle }}</strong></span><div class="topbar-actions"><RouterLink to="/upload" class="topbar-add"><el-icon><Plus /></el-icon>录入错题</RouterLink><span class="profile-mark" aria-label="学习空间">学</span></div></header>
      <main class="app-main"><router-view /></main>
    </div>
    <nav class="mobile-navigation" aria-label="手机导航"><RouterLink v-for="item in mobileLinks" :key="item.path" :to="item.path" :class="{ active: isActive(item.path) }"><el-icon><component :is="item.icon" /></el-icon>{{ item.label }}</RouterLink><button :class="{ active: moreOpen }" @click="moreOpen = true"><el-icon><MoreFilled /></el-icon>更多</button></nav>
    <el-drawer v-model="moreOpen" title="学习空间" direction="btt" size="75%"><nav class="mobile-more"><template v-for="group in navigation" :key="group.label"><p class="nav-label">{{ group.label }}</p><RouterLink v-for="item in group.items" :key="item.path" :to="item.path" class="nav-link" :class="{ active: isActive(item.path) }" @click="moreOpen = false"><el-icon><component :is="item.icon" /></el-icon>{{ item.label }}<b v-if="item.badge && reviewCountStore.pending > 0" class="nav-badge">{{ reviewCountStore.pending }}</b></RouterLink></template></nav></el-drawer>
  </div>
</template>
<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { House, Document, Notebook, Tickets, Reading, DataAnalysis, TrendCharts, Trophy, Setting, Grid, Plus, MoreFilled, Warning, Files } from '@element-plus/icons-vue'
import { useAppConfigStore } from '@/stores/appConfig'
import { useReviewCountStore } from '@/stores/reviewCount'
const route = useRoute()
const moreOpen = ref(false)
const navigation = [
  { label: '学习空间', items: [{ path: '/', label: '今日学习', icon: House }, { path: '/questions', label: '我的错题', icon: Document }, { path: '/review', label: '待核对', icon: Warning, badge: true }, { path: '/papers', label: '卷子和作业', icon: Files }, { path: '/words', label: '单词本', icon: Notebook }] },
  { label: '巩固与提升', items: [{ path: '/practice-sets', label: '练习中心', icon: Tickets }, { path: '/reading', label: '阅读空间', icon: Reading }] },
  { label: '成长记录', items: [{ path: '/learning-reports', label: '学习报告', icon: TrendCharts }, { path: '/learning-analysis', label: '知识点分析', icon: DataAnalysis }, { path: '/motivation', label: '我的成就', icon: Trophy }] },
  { label: '管理与设置', items: [{ path: '/management', label: '资料管理', icon: Grid }, { path: '/settings', label: '模型配置', icon: Setting }] },
]
const mobileLinks = [navigation[0].items[0], navigation[0].items[1], navigation[1].items[0]]
const isActive = (path) => route.path === path || (path === '/questions' && route.path === '/upload') || (path === '/reading' && route.path.startsWith('/reading-test/')) || (path === '/papers' && route.path.startsWith('/papers/'))
const currentTitle = computed(() => route.path === '/upload' ? '录入错题' : route.path.startsWith('/reading-test/') ? '阅读练习' : route.path.startsWith('/papers/') ? '卷子和作业' : navigation.flatMap(g => g.items).find(i => i.path === route.path)?.label || '学习空间')
const appConfigStore = useAppConfigStore()
const reviewCountStore = useReviewCountStore()
// 进入应用时加载配置并刷新待核对数量
onMounted(() => { appConfigStore.load(); reviewCountStore.refresh() })
</script>

<style scoped>
/* 导航项后面的数字角标（待核对数量） */
.nav-badge {
  margin-left: auto;
  min-width: 18px;
  height: 18px;
  padding: 0 6px;
  border-radius: 9px;
  background: #f56c6c;
  color: #fff;
  font-size: 11px;
  font-weight: 600;
  line-height: 18px;
  text-align: center;
}
</style>
