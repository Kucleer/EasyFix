<template>
  <!-- 学情页：考点（知识星空 + 考点明细）/ 单词 两个标签，标签和地址 ?tab= 同步 -->
  <div class="insight-page">
    <header class="page-head">
      <h1>学情</h1>
      <p>每个考点现在掌握得怎么样，哪些单词还要多练。</p>
    </header>

    <TabBar v-model="tab" :tabs="TABS" class="page-tabs" />

    <PointsTab v-if="tab === 'points'" v-model:subject-id="subject_id" />
    <WordsTab v-else />
  </div>
</template>

<script setup>
import { ref } from 'vue'
import TabBar from '@/components/ui/TabBar.vue'
import PointsTab from '@/components/insight/PointsTab.vue'
import WordsTab from '@/components/insight/WordsTab.vue'
import { useTabQuery } from '@/composables/useTabQuery'

const TABS = [
  { key: 'points', label: '考点' },
  { key: 'words', label: '单词' },
]

const tab = useTabQuery(['points', 'words'], 'points')
// 考点标签当前看的学科；切到单词再切回来时还是这一科
const subject_id = ref(null)
</script>

<style scoped>
.insight-page { max-width: 1280px; }
.page-head h1 { margin: 0; font-size: 24px; color: var(--ink); }
.page-head p { margin: 4px 0 16px; color: var(--muted); }
.page-tabs { width: fit-content; max-width: 100%; margin-bottom: 16px; }
</style>
