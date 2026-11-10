<template>
  <div v-loading="loading" class="paper-detail-page">
    <el-button link type="primary" class="back-link" @click="router.push('/papers')">&larr; 返回卷子和作业</el-button>

    <el-empty v-if="notFound" description="没有找到这份记录" />

    <template v-if="paper">
      <PageHeading :title="paper.name" :description="headDescription">
        <div class="head-actions">
          <el-button @click="editVisible = true">编辑</el-button>
          <el-button v-if="!isHistory" type="danger" plain :loading="deleting" @click="removePaper">删除</el-button>
        </div>
      </PageHeading>

      <el-card shadow="never" class="info-card">
        <p v-if="isHistory" class="history-note">这是整理旧题时自动建的记录</p>
        <dl class="info-list">
          <div><dt>学科</dt><dd>{{ paper.subject_name }}</dd></div>
          <div><dt>类型</dt><dd>{{ paperTypeLabel(paper) }}</dd></div>
          <div><dt>日期</dt><dd>{{ paper.paper_date || '未填' }}</dd></div>
          <div><dt>年级学期</dt><dd>{{ gradeSemester || '未填' }}</dd></div>
          <div><dt>分数</dt><dd>{{ scoreText(paper) || '未填' }}</dd></div>
        </dl>
        <p v-if="paper.notes" class="notes">备注：{{ paper.notes }}</p>
      </el-card>

      <el-card v-if="imageUrls.length" shadow="never" class="section-card">
        <template #header><strong>照片</strong></template>
        <div class="photo-grid">
          <el-image
            v-for="(url, index) in imageUrls"
            :key="url"
            :src="url"
            :preview-src-list="imageUrls"
            :initial-index="index"
            fit="cover"
            preview-teleported
            class="photo"
          />
        </div>
      </el-card>

      <el-card shadow="never" class="section-card">
        <template #header><strong>错题（{{ questions.length }}）</strong></template>
        <el-empty v-if="!questions.length" description="这份记录下还没有错题" :image-size="80" />
        <component
          :is="q.review_status === 'pending' ? 'router-link' : 'div'"
          v-for="q in questions"
          :key="q.id"
          :to="q.review_status === 'pending' ? '/review' : undefined"
          class="question-row"
          :class="{ clickable: q.review_status === 'pending' }"
        >
          <div class="row-head">
            <strong class="q-no">题号 {{ q.question_no || '未填' }}</strong>
            <el-tag v-if="q.review_status === 'pending'" type="warning" size="small">待核对</el-tag>
          </div>
          <div class="stem"><MathText :text="q.parsed_question || '（空）'" /></div>
          <div class="field"><span class="label">孩子的答案</span><MathText :text="q.wrong_answer || '（没有记录）'" /></div>
          <div class="field">
            <span class="label">考点</span>
            <span v-if="q.knowledge_points?.length" class="kp-list">
              <KnowledgeTag v-for="kp in q.knowledge_points" :key="kp.id" :point="kp" :primary="!!kp.is_primary" />
            </span>
            <span v-else class="muted">还没有考点</span>
          </div>
        </component>
      </el-card>

      <PaperFormDialog v-model="editVisible" :paper="paper" :subjects="[]" @saved="fetchPaper" />
    </template>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import PageHeading from '@/components/PageHeading.vue'
import PaperFormDialog from '@/components/PaperFormDialog.vue'
import MathText from '@/components/MathText.vue'
import KnowledgeTag from '@/components/KnowledgeTag.vue'
import { paperApi } from '@/api/paper'
import { useReviewCountStore } from '@/stores/reviewCount'
import { paperTypeLabel, scoreText } from '@/composables/intakeLabels'

const route = useRoute()
const router = useRouter()
const reviewCountStore = useReviewCountStore()

const loading = ref(false)
const deleting = ref(false)
const notFound = ref(false)
const paper = ref(null)
const editVisible = ref(false)

const isHistory = computed(() => paper.value?.source === 'history')
const questions = computed(() => paper.value?.questions || [])
const imageUrls = computed(() => (paper.value?.images || []).map(key => '/uploads/' + key))

// 年级学期的显示文字
const gradeSemester = computed(() => {
  const grades = ['', '一年级', '二年级', '三年级', '四年级', '五年级', '六年级', '初一', '初二', '初三', '高一', '高二', '高三']
  const p = paper.value
  if (!p) return ''
  const grade = p.grade ? grades[p.grade] || '' : ''
  const semester = p.semester === 1 ? '上学期' : p.semester === 2 ? '下学期' : ''
  return [grade, semester].filter(Boolean).join(' ')
})

// 标题下面的一行说明：学科、类型、日期
const headDescription = computed(() => {
  const p = paper.value
  if (!p) return ''
  return [p.subject_name, paperTypeLabel(p), p.paper_date].filter(Boolean).join(' · ')
})

// 加载这份卷子和它下面的题目
async function fetchPaper() {
  loading.value = true
  try {
    const { data } = await paperApi.get(route.params.id)
    paper.value = data
    notFound.value = false
  } catch (error) {
    if (error.response?.status === 404) {
      paper.value = null
      notFound.value = true
    } else {
      ElMessage.error(error.response?.data?.detail || '加载失败，请稍后再试')
    }
  } finally {
    loading.value = false
  }
}

// 确认后删除：下面有题目时一起删除，成功后回到列表并刷新待核对数量
async function removePaper() {
  const count = questions.value.length
  const message = count > 0 ? `这份记录下有 ${count} 道错题，会一起删除。确定吗？` : '确定删除这份记录吗？'
  try {
    await ElMessageBox.confirm(message, '删除记录', {
      type: 'warning',
      confirmButtonText: '确定删除',
      cancelButtonText: '再想想',
    })
  } catch {
    return // 用户取消
  }
  deleting.value = true
  try {
    await paperApi.remove(paper.value.id, count > 0)
    ElMessage.success('已删除')
    reviewCountStore.refresh()
    router.push('/papers')
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '删除失败，请稍后再试')
  } finally {
    deleting.value = false
  }
}

onMounted(fetchPaper)
</script>

<style scoped>
.paper-detail-page { min-height: 160px; }
.back-link { margin-bottom: 8px; padding: 0; }
.head-actions { display: flex; gap: 8px; flex-shrink: 0; }
.info-card, .section-card { margin-bottom: 16px; }
.history-note { margin: 0 0 10px; font-size: 13px; color: var(--text-muted); }
.info-list { display: flex; flex-wrap: wrap; gap: 8px 32px; margin: 0; }
.info-list dt { font-size: 12px; color: var(--text-muted); }
.info-list dd { margin: 2px 0 0; font-size: 15px; }
.notes { margin: 12px 0 0; font-size: 14px; color: var(--text-secondary); white-space: pre-wrap; }
.photo-grid { display: flex; flex-wrap: wrap; gap: 10px; }
.photo { width: 140px; height: 180px; border-radius: 6px; background: #f5f6f8; cursor: zoom-in; }
.question-row {
  display: block;
  padding: 12px;
  border: 1px solid var(--border-light);
  border-radius: 8px;
  margin-bottom: 10px;
  color: inherit;
  text-decoration: none;
}
.question-row.clickable:hover { border-color: var(--el-color-warning); }
.row-head { display: flex; align-items: center; gap: 8px; margin-bottom: 6px; }
.stem { max-height: 140px; overflow: hidden; margin-bottom: 8px; font-size: 14px; }
.field { margin-bottom: 6px; font-size: 14px; }
.label { display: block; font-size: 12px; color: var(--text-muted); margin-bottom: 2px; }
.kp-list { display: inline-flex; gap: 6px; flex-wrap: wrap; }
.muted { color: var(--text-muted); font-size: 13px; }

@media (max-width: 768px) {
  .info-list { flex-direction: column; gap: 8px; }
  .photo { width: calc(50% - 5px); height: 160px; }
  .head-actions { flex-direction: column; }
}
</style>
