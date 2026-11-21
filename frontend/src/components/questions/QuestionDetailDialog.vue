<template>
  <!-- 错题详情：原图、题目和答案、卷子与作答、解析、信息、标签、练习历史、相似题（只看不改） -->
  <el-dialog :model-value="modelValue" title="错题详情" width="900px" class="qd-dialog" @update:model-value="emit('update:modelValue', $event)">
    <div v-loading="loading" class="qdd">
      <template v-if="question">
        <section v-if="images.length" class="qdd-card">
          <h3>原图</h3>
          <div class="qdd-gallery">
            <el-image v-for="(url, index) in images" :key="url" :src="url" :preview-src-list="images" :initial-index="index" preview-teleported fit="contain" class="qdd-photo" />
          </div>
        </section>

        <div class="qdd-row">
          <section class="qdd-card">
            <h3>题目</h3>
            <div class="qdd-text"><MathText :text="question.parsed_question || question.original_text || '暂无'" /></div>
          </section>
          <section class="qdd-card">
            <h3 class="is-mint">答案</h3>
            <div class="qdd-text"><MathText :text="question.answer || '暂无'" /></div>
          </section>
        </div>

        <section class="qdd-card">
          <h3>卷子与作答</h3>
          <dl class="qdd-meta">
            <div><dt>所属卷子</dt><dd><router-link v-if="question.paper" class="qdd-link" :to="'/papers/' + question.paper.id">{{ question.paper.name }}</router-link><span v-else>无</span></dd></div>
            <div><dt>题号</dt><dd>{{ question.question_no || '未填' }}</dd></div>
            <div class="is-wide"><dt>学生的答案</dt><dd class="qdd-text"><MathText :text="question.wrong_answer || '暂无'" /></dd></div>
            <div class="is-wide"><dt>判错依据</dt><dd>{{ question.wrong_evidence || '暂无' }}</dd></div>
          </dl>
        </section>

        <section class="qdd-card">
          <h3 class="is-sun">解析</h3>
          <div v-if="question.analysis" class="qdd-text"><MathText :text="question.analysis" /></div>
          <el-image
            v-if="question.analysis_image"
            :src="'/uploads/' + question.analysis_image"
            :preview-src-list="['/uploads/' + question.analysis_image]"
            preview-teleported
            fit="contain"
            class="qdd-photo"
          />
          <span v-if="!question.analysis && !question.analysis_image" class="qdd-muted">暂无</span>
        </section>

        <section class="qdd-card">
          <h3>信息</h3>
          <dl class="qdd-meta">
            <div><dt>难度</dt><dd class="qdd-stars">{{ stars(question.difficulty) }}</dd></div>
            <div><dt>年级 / 学期</dt><dd>{{ grade_label(question.grade) }} / {{ semester_label(question.semester) || '未设置' }}</dd></div>
            <div class="is-wide">
              <dt>知识点</dt>
              <dd>
                <span v-if="question.knowledge_points?.length" class="qdd-chips">
                  <KnowledgeTag v-for="point in question.knowledge_points" :key="point.id" :point="point" :primary="!!point.is_primary" :subject-id="question.subject_id" show-path />
                </span>
                <span v-else-if="question.legacy_knowledge_point" class="qdd-legacy">原标签（未迁移）：{{ question.legacy_knowledge_point }}</span>
                <span v-else class="qdd-muted">未分类</span>
              </dd>
            </div>
            <div class="is-wide">
              <dt>标签</dt>
              <dd>
                <span v-if="question.tags?.length" class="qdd-chips">
                  <el-tag v-for="tag in question.tags" :key="tag.id" size="small" :style="tag_style(tag.color)">{{ tag.name }}</el-tag>
                </span>
                <span v-else class="qdd-muted">暂无</span>
              </dd>
            </div>
          </dl>
        </section>

        <section v-if="history.length" class="qdd-card">
          <h3>练习历史</h3>
          <div v-for="(record, index) in history" :key="index" class="qdd-history">
            <span class="qdd-history-date">{{ record.date }}</span>
            <span class="qdd-history-name">{{ record.practice_set_name }}</span>
            <el-tag :type="record.is_correct ? 'success' : 'danger'" size="small">{{ record.is_correct ? '✓ 正确' : '✗ 错误' }}</el-tag>
          </div>
        </section>

        <section v-if="question.similar_questions?.length" class="qdd-card">
          <h3>相似题</h3>
          <div v-for="item in question.similar_questions" :key="item.id" class="qdd-similar">
            <p><strong>题目：</strong><MathText :text="item.similar_text" /></p>
            <p><strong>答案：</strong><MathText :text="item.similar_answer" /></p>
          </div>
        </section>
      </template>
    </div>
  </el-dialog>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import MathText from '@/components/MathText.vue'
import { questionApi } from '@/api/question'
import { grade_label, semester_label, tag_style } from './questionFilters'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  // 要看的错题编号；打开时按它读取详情和练习历史
  questionId: { type: Number, default: null },
})
const emit = defineEmits(['update:modelValue'])

const loading = ref(false)
const question = ref(null)
const history = ref([])

// 原图地址列表：多张图优先，没有就用单张
const images = computed(() => {
  const q = question.value
  if (!q) return []
  const keys = Array.isArray(q.original_images) && q.original_images.length ? q.original_images : (q.original_image ? [q.original_image] : [])
  return keys.map(key => '/uploads/' + key)
})

/** 难度星星：实心 + 空心共 5 颗 */
function stars(difficulty) {
  const d = Math.max(0, Math.min(5, Number(difficulty) || 0))
  return '★'.repeat(d) + '☆'.repeat(5 - d)
}

/** 读取详情和练习历史；练习历史读不到就当没有 */
async function load(id) {
  loading.value = true
  question.value = null
  history.value = []
  try {
    const { data } = await questionApi.get(id)
    question.value = data
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '读取错题详情失败')
    emit('update:modelValue', false)
    return
  } finally {
    loading.value = false
  }
  try {
    const { data } = await questionApi.practiceHistory(id)
    history.value = data || []
  } catch {
    history.value = []
  }
}

// 每次打开都重新读，保证看到的是最新内容
watch(() => [props.modelValue, props.questionId], ([visible, id]) => {
  if (visible && id) load(id)
}, { immediate: true })
</script>

<style scoped>
.qdd { min-height: 120px; }
.qdd-card { margin-bottom: 14px; padding: 14px 16px; border: 1px solid var(--line); border-radius: var(--r-md); background: var(--surface); }
.qdd-card h3 { margin: 0 0 10px; font-size: 14px; font-weight: 600; color: var(--brand-deep); }
.qdd-card h3.is-mint { color: var(--mint-deep); }
.qdd-card h3.is-sun { color: var(--sun); }
.qdd-row { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }
.qdd-text { white-space: pre-wrap; overflow-wrap: anywhere; line-height: 1.8; font-size: 15px; color: var(--ink); }
.qdd-gallery { display: flex; gap: 12px; overflow-x: auto; padding: 2px 0; }
.qdd-photo { width: 180px; height: 180px; flex: none; border-radius: 8px; background: var(--bg); cursor: zoom-in; }
.qdd-meta { display: grid; grid-template-columns: 1fr 1fr; gap: 10px 24px; margin: 0; }
.qdd-meta > div { display: flex; gap: 8px; align-items: baseline; min-width: 0; }
.qdd-meta > div.is-wide { grid-column: 1 / -1; }
.qdd-meta dt { flex: none; color: var(--muted); font-size: 13px; }
.qdd-meta dd { margin: 0; min-width: 0; font-size: 14px; color: var(--ink); }
.qdd-link { color: var(--brand); font-weight: 600; }
.qdd-stars { color: #f5c518; letter-spacing: 3px; font-size: 16px; }
.qdd-chips { display: inline-flex; flex-wrap: wrap; gap: 6px; }
.qdd-legacy { color: var(--muted); font-size: 12px; font-style: italic; }
.qdd-muted { color: var(--muted); font-size: 13px; }
.qdd-history { display: flex; align-items: center; gap: 12px; padding: 8px 0; border-bottom: 1px solid var(--line); }
.qdd-history:last-child { border-bottom: 0; }
.qdd-history-date { min-width: 140px; color: var(--muted); font-size: 13px; }
.qdd-history-name { flex: 1; font-size: 14px; color: var(--ink); }
.qdd-similar { padding: 12px; margin-bottom: 10px; border-radius: 8px; background: var(--bg); }
.qdd-similar:last-child { margin-bottom: 0; }
.qdd-similar p { margin: 0 0 6px; line-height: 1.6; }

@media (max-width: 768px) {
  .qdd-row, .qdd-meta { grid-template-columns: 1fr; }
  .qdd-meta > div { flex-direction: column; gap: 2px; }
  .qdd-photo { width: 140px; height: 140px; }
  .qdd-history { flex-wrap: wrap; gap: 4px 10px; }
  .qdd-history-date { min-width: 0; }
}
</style>
