<template>
  <!-- 待核对：录入时拿不准的题，按卷子分组；通过、编辑后通过、做对了移除 -->
  <section class="review-tab">
    <p class="rv-tip">这些题录入时有拿不准的地方，处理后才会计入统计和练习卷。</p>

    <div v-loading="loading" class="rv-body">
      <div v-if="!loading && !questions.length" class="rv-empty">
        <LineIcon name="check" :size="28" />
        <b>都处理完了</b>
        <span>新录入的题如果有拿不准的地方，会出现在这里。</span>
      </div>

      <section v-for="group in groups" :key="group.paper ? group.paper.id : 'none'" class="rv-group">
        <h2 class="rv-group-title">
          <template v-if="group.paper">
            <router-link :to="'/papers/' + group.paper.id">{{ group.paper.name }}</router-link>
            <span v-if="group.paper.paper_date" class="rv-date"> · {{ group.paper.paper_date }}</span>
          </template>
          <template v-else>没有所属卷子的题</template>
          <em>{{ group.questions.length }} 道</em>
        </h2>

        <article v-for="q in group.questions" :key="q.id" class="rv-card">
          <div class="rv-photo-box">
            <el-image v-if="pageImage(q)" :src="pageImage(q)" :preview-src-list="[pageImage(q)]" preview-teleported fit="contain" class="rv-photo" />
            <div v-else class="rv-photo-empty">这道题没有带照片</div>
          </div>

          <div class="rv-main">
            <div class="rv-head">
              <strong>题号 {{ q.question_no || '未填' }}</strong>
              <span class="rv-reasons">
                <el-tag v-for="r in reasonLabels(q.review_reasons)" :key="r" type="warning" size="small">{{ r }}</el-tag>
              </span>
            </div>
            <p v-if="q.review_note" class="rv-note">说明：{{ q.review_note }}</p>

            <div class="rv-field"><span class="rv-label">题干</span><MathText :text="q.parsed_question || '（空）'" /></div>
            <div class="rv-answers">
              <div class="rv-field"><span class="rv-label">学生的答案</span><MathText :text="q.wrong_answer || '（没有记录）'" /></div>
              <div class="rv-field"><span class="rv-label">正确答案</span><MathText :text="q.answer || '（没有记录）'" /></div>
            </div>
            <div v-if="q.wrong_evidence" class="rv-field"><span class="rv-label">判错依据</span><span>{{ q.wrong_evidence }}</span></div>
            <div class="rv-field">
              <span class="rv-label">考点</span>
              <span v-if="q.knowledge_points?.length" class="rv-kp">
                <KnowledgeTag v-for="kp in q.knowledge_points" :key="kp.id" :point="kp" :primary="!!kp.is_primary" :subject-id="q.subject_id" />
              </span>
              <span v-else class="rv-muted">还没有考点</span>
            </div>

            <div class="rv-actions">
              <el-button type="primary" :loading="busy_id === q.id" @click="approve(q)">通过</el-button>
              <el-button :disabled="busy_id === q.id" @click="open_edit(q)">编辑后通过</el-button>
              <el-button type="danger" plain :disabled="busy_id === q.id" @click="reject(q)">做对了，移除</el-button>
            </div>
          </div>
        </article>
      </section>
    </div>

    <el-dialog v-model="edit_visible" title="编辑后通过" width="720px" destroy-on-close>
      <el-form label-position="top">
        <el-form-item label="题号"><el-input v-model="form.question_no" placeholder="如 二、5" /></el-form-item>
        <el-form-item label="题干"><MathEditor v-model="form.parsed_question" :rows="5" /></el-form-item>
        <el-form-item label="学生的答案"><MathEditor v-model="form.wrong_answer" :rows="3" /></el-form-item>
        <el-form-item label="正确答案"><MathEditor v-model="form.answer" :rows="3" /></el-form-item>
        <el-form-item label="解析"><MathEditor v-model="form.analysis" :rows="4" /></el-form-item>
        <el-form-item label="考点">
          <KnowledgePointPicker v-model="form.knowledge_point_ids" v-model:primary-id="form.primary_knowledge_point_id" :subject-id="editing?.subject_id" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="edit_visible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="save_and_approve">保存并通过</el-button>
      </template>
    </el-dialog>
  </section>
</template>

<script setup>
import { computed, onActivated, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import LineIcon from '@/components/ui/LineIcon.vue'
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
const busy_id = ref(null)
const groups = computed(() => groupByPaper(questions.value))

// 编辑框
const edit_visible = ref(false)
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

/** 读取待核对的题（最多 100 道） */
async function fetch_pending() {
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

/** 处理完的题从页面去掉，并刷新菜单、标签和首页上的待核对数 */
function remove_from_list(id) {
  questions.value = questions.value.filter(q => q.id !== id)
  reviewCountStore.refresh()
}

/** 通过 / 移除时的接口错误：409 说明别处处理过了，去掉卡片；422 没有考点，打开编辑框补上 */
function handle_review_error(error, question) {
  const status = error.response?.status
  const detail = error.response?.data?.detail
  if (status === 409) {
    ElMessage.warning('这道题已经被处理过了')
    remove_from_list(question.id)
    return
  }
  if (status === 422) {
    ElMessage.warning(detail || '这道题还没有考点，请先选一个考点')
    open_edit(question)
    return
  }
  ElMessage.error(detail || '操作失败，请稍后再试')
}

/** 直接通过 */
async function approve(question) {
  busy_id.value = question.id
  try {
    await reviewApi.approve(question.id)
    ElMessage.success('已通过')
    remove_from_list(question.id)
  } catch (error) {
    handle_review_error(error, question)
  } finally {
    busy_id.value = null
  }
}

/** 确认后移除（其实做对了） */
async function reject(question) {
  try {
    await ElMessageBox.confirm('确定这道题其实做对了吗？移除后不会出现在错题和统计里。', '做对了，移除', {
      type: 'warning', confirmButtonText: '确定移除', cancelButtonText: '再想想',
    })
  } catch {
    return
  }
  busy_id.value = question.id
  try {
    await reviewApi.reject(question.id)
    ElMessage.success('已移除')
    remove_from_list(question.id)
  } catch (error) {
    handle_review_error(error, question)
  } finally {
    busy_id.value = null
  }
}

/** 打开编辑框，带入这道题当前的内容和读取时的考点版本号 */
function open_edit(question) {
  editing.value = question
  const points = question.knowledge_points || []
  Object.assign(form, {
    question_no: question.question_no || '',
    parsed_question: question.parsed_question || '',
    wrong_answer: question.wrong_answer || '',
    answer: question.answer || '',
    analysis: question.analysis || '',
    knowledge_point_ids: points.map(p => p.id),
    primary_knowledge_point_id: points.find(p => p.is_primary)?.id ?? null,
    knowledge_revision: question.knowledge_revision || 0,
  })
  edit_visible.value = true
}

/** 先保存修改，成功后再通过 */
async function save_and_approve() {
  const question = editing.value
  if (!question) return
  if (form.knowledge_point_ids.length && !form.primary_knowledge_point_id) {
    ElMessage.warning('请为所选考点指定一个主考点')
    return
  }
  saving.value = true
  try {
    const { data: updated } = await questionApi.update(question.id, { ...form })
    // 用返回的最新内容替换页面上的这道题并更新版本号：通过失败后重试不会拿旧版本号去保存
    if (updated && updated.id === question.id) {
      const index = questions.value.findIndex(q => q.id === question.id)
      if (index !== -1) questions.value[index] = updated
      editing.value = updated
      form.knowledge_revision = updated.knowledge_revision || 0
    }
  } catch (error) {
    const detail = error.response?.data?.detail
    ElMessage.error(detail || (error.response?.status === 409 ? '这道题的考点刚被别处改过，请刷新页面后再编辑' : '保存失败'))
    saving.value = false
    return
  }
  try {
    await reviewApi.approve(question.id)
    ElMessage.success('已保存并通过')
    edit_visible.value = false
    remove_from_list(question.id)
  } catch (error) {
    // 保存已成功；通过失败时 409 说明已被处理，其余留在编辑框里重试
    if (error.response?.status === 409) {
      edit_visible.value = false
      handle_review_error(error, question)
    } else {
      ElMessage.error(error.response?.data?.detail || '已保存，但通过失败，请再试一次')
    }
  } finally {
    saving.value = false
  }
}

onMounted(fetch_pending)

// 从别的标签切回来时重新读一次（别处可能已经处理或新录入了）
let activated_before = false
onActivated(() => {
  if (activated_before) fetch_pending()
  activated_before = true
})
</script>

<style scoped>
.rv-tip { margin: 0 0 14px; color: var(--muted); font-size: 13px; }
.rv-body { min-height: 120px; }
.rv-empty {
  display: flex; flex-direction: column; align-items: center; gap: 6px; padding: 40px 20px;
  border-radius: var(--r-lg); background: var(--surface); box-shadow: var(--shadow-1); color: var(--muted); text-align: center;
}
.rv-empty :deep(.line-icon) { color: var(--mint); }
.rv-empty b { color: var(--ink); font-size: 16px; }
.rv-group { margin-bottom: 22px; }
.rv-group-title { display: flex; flex-wrap: wrap; align-items: baseline; gap: 4px 6px; margin: 0 0 10px; font-size: 16px; color: var(--ink); }
.rv-group-title a { color: var(--ink); }
.rv-group-title a:hover { color: var(--brand); }
.rv-date { color: var(--muted); font-weight: 400; font-size: 14px; }
.rv-group-title em { font-style: normal; font-weight: 400; font-size: 12px; color: var(--sun); background: var(--sun-soft); padding: 0 8px; border-radius: 999px; }
.rv-card {
  display: flex; gap: 16px; padding: 16px; margin-bottom: 12px;
  border-radius: var(--r-lg); background: var(--surface); box-shadow: var(--shadow-1);
}
.rv-photo-box { flex: 0 0 240px; }
.rv-photo { width: 240px; height: 300px; border-radius: var(--r-sm); background: var(--bg); cursor: zoom-in; }
.rv-photo-empty {
  width: 240px; min-height: 120px; display: flex; align-items: center; justify-content: center;
  border-radius: var(--r-sm); background: var(--bg); color: var(--muted); font-size: 13px;
}
.rv-main { flex: 1; min-width: 0; }
.rv-head { display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 8px; margin-bottom: 6px; }
.rv-reasons { display: flex; flex-wrap: wrap; gap: 6px; }
.rv-note { margin: 0 0 8px; font-size: 13px; color: var(--muted); }
.rv-field { margin-bottom: 8px; font-size: 14px; color: var(--ink); overflow-wrap: anywhere; }
.rv-label { display: block; margin-bottom: 2px; font-size: 12px; color: var(--muted); }
.rv-answers { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
.rv-kp { display: inline-flex; flex-wrap: wrap; gap: 6px; }
.rv-muted { color: var(--muted); font-size: 13px; }
.rv-actions { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 12px; }
.rv-actions :deep(.el-button) { margin: 0; }

@media (max-width: 768px) {
  .rv-card { flex-direction: column; padding: 12px; }
  .rv-photo-box { flex: none; }
  .rv-photo, .rv-photo-empty { width: 100%; }
  .rv-photo { height: 220px; }
  .rv-answers { grid-template-columns: 1fr; }
  .rv-actions { flex-direction: column; }
  .rv-actions :deep(.el-button) { width: 100%; }
}
</style>
