<template>
  <div class="grade-list">
    <PageHeading title="待批改" description="点开一份卷子，对着学生做完的纸卷点对错。" />

    <!-- 上半：最近 30 天内创建、还没批改的卷子 -->
    <section class="block" v-loading="pendingLoading">
      <h3 class="block-title">待批改的卷子</h3>
      <p v-if="pendingError" class="block-empty">{{ pendingError }}</p>
      <p v-else-if="!pendingLoading && !pendingPapers.length" class="block-empty">没有待批改的卷子</p>
      <RouterLink v-for="paper in pendingPapers" :key="paper.id" :to="`/grade/${paper.id}`" class="paper-card">
        <div class="paper-main">
          <div class="paper-name">{{ paperLabel(paper) }}</div>
          <div class="paper-meta">
            <span v-if="paper.subject_name">{{ paper.subject_name }}</span>
            <span>{{ paper.total_questions || 0 }} 道</span>
            <span>{{ dateText(paper.created_at) }} 创建</span>
          </div>
        </div>
        <el-icon class="paper-arrow"><ArrowRight /></el-icon>
      </RouterLink>
    </section>

    <!-- 下半：最近批改过的 5 份，点进去可以修改 -->
    <section class="block" v-loading="recentLoading">
      <h3 class="block-title">最近批改过的</h3>
      <p v-if="recentError" class="block-empty">{{ recentError }}</p>
      <p v-else-if="!recentLoading && !recentPapers.length" class="block-empty">还没有批改过的卷子</p>
      <RouterLink v-for="paper in recentPapers" :key="paper.id" :to="`/grade/${paper.id}`" class="paper-card">
        <div class="paper-main">
          <div class="paper-name">{{ paperLabel(paper) }}</div>
          <div class="paper-meta">
            <span v-if="paper.subject_name">{{ paper.subject_name }}</span>
            <span>{{ paper.total_questions || 0 }} 道</span>
            <span v-if="paper.last_reviewed_at">{{ dateText(paper.last_reviewed_at) }} 批改</span>
          </div>
        </div>
        <span class="paper-accuracy">{{ accuracyText(paper.accuracy) }}</span>
        <el-icon class="paper-arrow"><ArrowRight /></el-icon>
      </RouterLink>
    </section>
  </div>
</template>

<script setup>
// 待批改列表（设计 8.1）：按手机设计，电脑上也能用。
// 上半是最近 30 天内创建的、没批改的错题练习卷；下半是最近批改过的 5 份。
import { ref, onMounted } from 'vue'
import { ArrowRight } from '@element-plus/icons-vue'
import PageHeading from '@/components/PageHeading.vue'
import { targetedApi } from '@/api/targeted'
import { questionApi } from '@/api/question'
import { paperLabel } from '@/composables/targetedPaper'

const RECENT_LIMIT = 5  // 下半显示几份最近批改过的

const pendingPapers = ref([])
const pendingLoading = ref(false)
const pendingError = ref('')
const recentPapers = ref([])
const recentLoading = ref(false)
const recentError = ref('')

/** 把接口错误转成提示文字，取不到时用 fallback。 */
function error_text(error, fallback) {
  const detail = error?.response?.data?.detail
  return typeof detail === 'string' ? detail : fallback
}

/** '2026-11-15 20:15:00' -> '11月15日'；格式不对时返回空串。 */
function dateText(stamp) {
  const m = /(\d{4})-(\d{2})-(\d{2})/.exec(stamp || '')
  return m ? `${Number(m[2])}月${Number(m[3])}日` : ''
}

/** 正确率文字；没有正确率（比如全部标了"没做"）时显示横线。 */
function accuracyText(accuracy) {
  return accuracy === null || accuracy === undefined ? '—' : `${accuracy}%`
}

/** 读取待批改的卷子（pending 已限定最近 30 天、未批改）。 */
async function load_pending() {
  pendingLoading.value = true
  pendingError.value = ''
  try {
    const { data } = await targetedApi.pending()
    pendingPapers.value = data.items || []
  } catch (error) {
    pendingError.value = error_text(error, '读取待批改的卷子失败')
  } finally {
    pendingLoading.value = false
  }
}

/** 读取最近批改过的几份错题练习卷。 */
async function load_recent() {
  recentLoading.value = true
  recentError.value = ''
  try {
    const { data } = await questionApi.listPracticeSets({ source_type: 'question', reviewed: true, limit: RECENT_LIMIT })
    recentPapers.value = data.items || []
  } catch (error) {
    recentError.value = error_text(error, '读取最近批改的卷子失败')
  } finally {
    recentLoading.value = false
  }
}

onMounted(() => {
  load_pending()
  load_recent()
})
</script>

<style scoped>
.grade-list {
  max-width: 640px;
  margin: 0 auto;
}

.block {
  margin-bottom: 22px;
  min-height: 60px;
}

.block-title {
  margin: 0 0 10px;
  font-size: 15px;
  font-weight: 600;
  color: var(--el-text-color-primary);
}

.block-empty {
  margin: 0;
  padding: 18px 0;
  text-align: center;
  color: var(--el-text-color-secondary);
  font-size: 14px;
}

/* 每份卷子一张卡片，整张可点 */
.paper-card {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 14px 14px;
  margin-bottom: 10px;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 10px;
  background: var(--el-bg-color);
  color: inherit;
  text-decoration: none;
}

.paper-card:active {
  background: var(--el-fill-color-light);
}

.paper-main {
  flex: 1;
  min-width: 0;
}

.paper-name {
  font-size: 15px;
  font-weight: 600;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.paper-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 4px 12px;
  margin-top: 4px;
  font-size: 13px;
  color: var(--el-text-color-secondary);
}

.paper-accuracy {
  font-size: 16px;
  font-weight: 600;
  color: var(--el-color-primary);
}

.paper-arrow {
  color: var(--el-text-color-placeholder);
}
</style>
