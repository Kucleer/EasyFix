<template>
  <!-- 错题页：待核对 / 全部错题 / 卷子和作业 三个标签，标签和地址 ?tab= 同步 -->
  <div class="questions-page">
    <header class="page-head">
      <h1>错题</h1>
      <p>错题从哪来、核对、管理，都在这一页。</p>
    </header>

    <TabBar v-model="tab" :tabs="tabs" class="page-tabs" />

    <!-- 标签页缓存着：切回来时保留筛选和页码，各标签自己在切回来时刷新一次数据 -->
    <KeepAlive v-if="ready">
      <ReviewTab v-if="tab === 'review'" />
      <AllTab v-else-if="tab === 'all'" />
      <PapersTab v-else />
    </KeepAlive>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import TabBar from '@/components/ui/TabBar.vue'
import ReviewTab from '@/components/questions/ReviewTab.vue'
import AllTab from '@/components/questions/AllTab.vue'
import PapersTab from '@/components/questions/PapersTab.vue'
import { useTabQuery } from '@/composables/useTabQuery'
import { useReviewCountStore } from '@/stores/reviewCount'
import { QUESTION_TABS, default_question_tab, explicit_question_tab } from '@/components/questions/questionFilters'

const route = useRoute()
const reviewCountStore = useReviewCountStore()

// 当前标签；地址里指定了有效标签就用它，否则先按已知的待核对数猜一个，读到最新数字后再定
const tab = useTabQuery(QUESTION_TABS, default_question_tab(reviewCountStore.pending, route.query))
// 标签定下来以后才显示内容，免得先打开一个标签又马上换掉、白查一次
const ready = ref(Boolean(explicit_question_tab(route.query)))

const tabs = computed(() => [
  { key: 'review', label: '待核对', badge: reviewCountStore.pending },
  { key: 'all', label: '全部错题' },
  { key: 'papers', label: '卷子和作业' },
])

onMounted(async () => {
  if (ready.value) return
  // 地址里没指定标签：读一次待核对数，有待核对就先看待核对，否则看全部错题
  await reviewCountStore.refresh()
  // 等数字的这一会儿如果已经手动点了标签，就不再改
  if (!explicit_question_tab(route.query)) tab.value = default_question_tab(reviewCountStore.pending, route.query)
  ready.value = true
})
</script>

<style scoped>
.questions-page { max-width: 1280px; }
.page-head h1 { margin: 0; font-size: 24px; color: var(--ink); }
.page-head p { margin: 4px 0 16px; color: var(--muted); }
.page-tabs { width: fit-content; max-width: 100%; margin-bottom: 16px; }

@media (max-width: 768px) {
  .page-head h1 { font-size: 22px; }
  .page-head p { margin-bottom: 12px; font-size: 13px; }
}
</style>
