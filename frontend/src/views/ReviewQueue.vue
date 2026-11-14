<template>
  <div class="review-page">
    <PageHeading title="待核对" description="这些题录入时有拿不准的地方，处理后才会计入统计和练习卷" />

    <div v-loading="loading" class="review-body">
      <el-empty v-if="!loading && !questions.length" description="都处理完了" />

      <section v-for="group in groups" :key="group.paper ? group.paper.id : 'none'" class="paper-group">
        <h2 class="group-title">
          <template v-if="group.paper">
            {{ group.paper.name }}<span v-if="group.paper.paper_date"> · {{ group.paper.paper_date }}</span>
          </template>
          <template v-else>没有所属卷子的题</template>
        </h2>

        <article v-for="q in group.questions" :key="q.id" class="review-card">
          <div class="card-photo">
            <el-image
              v-if="pageImage(q)"
              :src="pageImage(q)"
              fit="contain"
              class="photo"
              @click="previewUrl = pageImage(q)"
            />
            <div v-else class="photo-empty">这道题没有带照片</div>
          </div>

          <div class="card-main">
            <div class="card-head">
              <strong class="q-no">题号 {{ q.question_no || '未填' }}</strong>
              <span class="reasons">
                <el-tag v-for="r in reasonLabels(q.review_reasons)" :key="r" type="warning" size="small">{{ r }}</el-tag>
              </span>
            </div>
            <p v-if="q.review_note" class="note">说明：{{ q.review_note }}</p>

            <div class="field"><span class="label">题干</span><MathText :text="q.parsed_question || '（空）'" /></div>
            <div class="answers">
              <div class="field"><span class="label">学生的答案</span><MathText :text="q.wrong_answer || '（没有记录）'" /></div>
              <div class="field"><span class="label">正确答案</span><MathText :text="q.answer || '（没有记录）'" /></div>
            </div>
            <div v-if="q.wrong_evidence" class="field"><span class="label">判错依据</span><span>{{ q.wrong_evidence }}</span></div>
            <div class="field">
              <span class="label">考点</span>
              <span v-if="q.knowledge_points?.length" class="kp-list">
                <KnowledgeTag v-for="kp in q.knowledge_points" :key="kp.id" :point="kp" :primary="!!kp.is_primary" />
              </span>
              <span v-else class="muted">还没有考点</span>
            </div>

            <div class="actions">
              <el-button type="primary" :loading="busyId === q.id" @click="approve(q)">通过</el-button>
              <el-button :disabled="busyId === q.id" @click="openEdit(q)">编辑后通过</el-button>
              <el-button type="danger" plain :disabled="busyId === q.id" @click="reject(q)">做对了，移除</el-button>
            </div>
          </div>
        </article>
      </section>
    </div>

    <el-image-viewer v-if="previewUrl" :url-list="[previewUrl]" @close="previewUrl = ''" />

    <el-dialog v-model="editVisible" title="编辑后通过" width="720px" class="review-edit-dialog" destroy-on-close>
      <el-form label-position="top">
        <el-form-item label="题号"><el-input v-model="form.question_no" placeholder="如 二、5" /></el-form-item>
        <el-form-item label="题干"><MathEditor v-model="form.parsed_question" :rows="5" /></el-form-item>
        <el-form-item label="学生的答案"><MathEditor v-model="form.wrong_answer" :rows="3" /></el-form-item>
        <el-form-item label="正确答案"><MathEditor v-model="form.answer" :rows="3" /></el-form-item>
        <el-form-item label="解析"><MathEditor v-model="form.analysis" :rows="4" /></el-form-item>
        <el-form-item label="考点">
          <KnowledgePointPicker
            v-model="form.knowledge_point_ids"
            v-model:primary-id="form.primary_knowledge_point_id"
            :subject-id="editing?.subject_id"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="saveAndApprove">保存并通过</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import PageHeading from '@/components/PageHeading.vue'
import MathText from '@/components/MathText.vue'
import MathEditor from '@/components/MathEditor.vue'
import KnowledgePointPicker from '@/components/KnowledgePointPicker.vue'
import { reviewApi } from '@/api/paper'
import { questionApi } from '@/api/question'
import { useReviewCountStore } from '@/stores/reviewCount'
import { groupByPaper, pageImage, reasonLabels } from '@/composables/intakeLabels'

const reviewCountStore = useReviewCountStore()

const loading = ref(false)
const questions = ref([])
const busyId = ref(null)
const previewUrl = ref('')
const groups = computed(() => groupByPaper(questions.value))

// 编辑框状态
const editVisible = ref(false)
const saving = ref(false)
const editing = ref(null)
const form = reactive({
  question_no: '',
  parsed_question: '',
  wrong_answer: '',
  answer: '',
  analysis: '',
  knowledge_point_ids: [],
  primary_knowledge_point_id: null,
  knowledge_revision: 0,
})

// 加载待核对的题
async function fetchPending() {
  loading.value = true
  try {
    const { data } = await reviewApi.pending({ limit: 100 })
    questions.value = data.items || []
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '加载待核对的题失败')
  } finally {
    loading.value = false
  }
}

// 把处理完的题从页面去掉，并刷新导航和首页的数字
function removeFromList(id) {
  questions.value = questions.value.filter(q => q.id !== id)
  reviewCountStore.refresh()
}

// 统一处理通过/移除时的接口错误：409 去掉卡片，422 提示并打开编辑框
function handleReviewError(error, question) {
  const status = error.response?.status
  const detail = error.response?.data?.detail
  if (status === 409) {
    ElMessage.warning('这道题已经被处理过了')
    removeFromList(question.id)
    return
  }
  if (status === 422) {
    // 没有考点：提示接口给的说明，并打开编辑框让人补上
    ElMessage.warning(detail || '这道题还没有考点，请先选一个考点')
    openEdit(question)
    return
  }
  ElMessage.error(detail || '操作失败，请稍后再试')
}

// 直接通过
async function approve(question) {
  busyId.value = question.id
  try {
    await reviewApi.approve(question.id)
    ElMessage.success('已通过')
    removeFromList(question.id)
  } catch (error) {
    handleReviewError(error, question)
  } finally {
    busyId.value = null
  }
}

// 二次确认后移除（其实做对了）
async function reject(question) {
  try {
    await ElMessageBox.confirm('确定这道题其实做对了吗？移除后不会出现在错题和统计里。', '做对了，移除', {
      type: 'warning',
      confirmButtonText: '确定移除',
      cancelButtonText: '再想想',
    })
  } catch {
    return // 用户取消
  }
  busyId.value = question.id
  try {
    await reviewApi.reject(question.id)
    ElMessage.success('已移除')
    removeFromList(question.id)
  } catch (error) {
    handleReviewError(error, question)
  } finally {
    busyId.value = null
  }
}

// 打开编辑框，带入这道题当前的内容和读取时的考点版本号
function openEdit(question) {
  editing.value = question
  form.question_no = question.question_no || ''
  form.parsed_question = question.parsed_question || ''
  form.wrong_answer = question.wrong_answer || ''
  form.answer = question.answer || ''
  form.analysis = question.analysis || ''
  const points = question.knowledge_points || []
  form.knowledge_point_ids = points.map(p => p.id)
  form.primary_knowledge_point_id = points.find(p => p.is_primary)?.id ?? null
  form.knowledge_revision = question.knowledge_revision || 0
  editVisible.value = true
}

// 先保存修改，成功后再通过
async function saveAndApprove() {
  const question = editing.value
  if (!question) return
  if (form.knowledge_point_ids.length && !form.primary_knowledge_point_id) {
    ElMessage.warning('请为所选考点指定一个主考点')
    return
  }
  saving.value = true
  try {
    const { data: updated } = await questionApi.update(question.id, {
      question_no: form.question_no,
      parsed_question: form.parsed_question,
      wrong_answer: form.wrong_answer,
      answer: form.answer,
      analysis: form.analysis,
      knowledge_point_ids: form.knowledge_point_ids,
      primary_knowledge_point_id: form.primary_knowledge_point_id,
      knowledge_revision: form.knowledge_revision,
    })
    // 保存成功：用返回的最新内容替换页面上的这道题，并更新版本号，
    // 这样后面通过失败重试时不会拿旧版本号去保存，重新打开编辑框也是已保存的内容
    if (updated && updated.id === question.id) {
      const index = questions.value.findIndex(q => q.id === question.id)
      if (index !== -1) questions.value[index] = updated
      editing.value = updated
      form.knowledge_revision = updated.knowledge_revision || 0
    }
  } catch (error) {
    const detail = error.response?.data?.detail
    if (error.response?.status === 409) {
      ElMessage.error(detail || '这道题的考点刚被别处改过，请刷新页面后再编辑')
    } else {
      ElMessage.error(detail || '保存失败')
    }
    saving.value = false
    return
  }
  try {
    await reviewApi.approve(question.id)
    ElMessage.success('已保存并通过')
    editVisible.value = false
    removeFromList(question.id)
  } catch (error) {
    // 保存已成功；通过失败时，409 说明已被处理，其余留在编辑框里重试
    if (error.response?.status === 409) {
      editVisible.value = false
      handleReviewError(error, question)
    } else {
      ElMessage.error(error.response?.data?.detail || '已保存，但通过失败，请再试一次')
    }
  } finally {
    saving.value = false
  }
}

onMounted(fetchPending)
</script>

<style scoped>
.review-body { min-height: 120px; }
.paper-group { margin-bottom: 22px; }
.group-title { font-size: 16px; margin: 0 0 10px; }
.review-card {
  display: flex;
  gap: 16px;
  background: #fff;
  border: 1px solid var(--border-light);
  border-radius: 10px;
  padding: 14px;
  margin-bottom: 12px;
}
.card-photo { flex: 0 0 240px; }
.photo { width: 240px; height: 300px; background: #f5f6f8; border-radius: 6px; cursor: zoom-in; }
.photo-empty {
  width: 240px;
  min-height: 120px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #f5f6f8;
  border-radius: 6px;
  color: var(--text-muted);
  font-size: 13px;
}
.card-main { flex: 1; min-width: 0; }
.card-head { display: flex; justify-content: space-between; align-items: center; gap: 8px; flex-wrap: wrap; margin-bottom: 6px; }
.reasons { display: flex; gap: 6px; flex-wrap: wrap; }
.note { margin: 0 0 8px; font-size: 13px; color: var(--text-muted); }
.field { margin-bottom: 8px; font-size: 14px; }
.label { display: block; font-size: 12px; color: var(--text-muted); margin-bottom: 2px; }
.answers { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
.kp-list { display: inline-flex; gap: 6px; flex-wrap: wrap; }
.muted { color: var(--text-muted); font-size: 13px; }
.actions { display: flex; gap: 8px; flex-wrap: wrap; margin-top: 12px; }

@media (max-width: 768px) {
  .review-card { flex-direction: column; }
  .card-photo { flex: none; }
  .photo, .photo-empty { width: 100%; }
  .photo { height: 220px; }
  .answers { grid-template-columns: 1fr; }
  .actions { flex-direction: column; }
  .actions :deep(.el-button) { width: 100%; margin-left: 0; }
}
</style>
