<template>
  <!-- 编辑错题：学科、原图、题目、题号、学生的答案、答案、解析和解析图、难度、年级学期、知识点、标签 -->
  <el-dialog :model-value="modelValue" title="编辑错题" width="700px" destroy-on-close @update:model-value="emit('update:modelValue', $event)">
    <el-form :model="form" label-width="96px" class="qe-form">
      <el-form-item label="学科" required>
        <el-select v-model="form.subject_id" placeholder="选择学科" style="width: 100%" @change="on_subject_change">
          <el-option v-for="s in subjects" :key="s.id" :label="s.name" :value="s.id" />
        </el-select>
      </el-form-item>
      <el-form-item label="原图">
        <div v-if="form.original_image" class="qe-image">
          <el-image :src="'/uploads/' + form.original_image" :preview-src-list="['/uploads/' + form.original_image]" preview-teleported fit="contain" class="qe-thumb" />
          <el-button size="small" @click="form.original_image = ''">移除</el-button>
        </div>
        <el-upload v-else :show-file-list="false" accept="image/*" :http-request="options => upload_to('original_image', options)">
          <el-button size="small" type="primary" :loading="uploading === 'original_image'">上传图片</el-button>
        </el-upload>
      </el-form-item>
      <el-form-item label="题目"><MathEditor v-model="form.parsed_question" :rows="6" /></el-form-item>
      <el-form-item label="题号"><el-input v-model="form.question_no" placeholder="如 二、5" /></el-form-item>
      <el-form-item label="学生的答案"><MathEditor v-model="form.wrong_answer" :rows="3" /></el-form-item>
      <el-form-item label="答案"><MathEditor v-model="form.answer" :rows="4" /></el-form-item>
      <el-form-item label="解析"><MathEditor v-model="form.analysis" :rows="4" /></el-form-item>
      <el-form-item label="解析图片">
        <div v-if="form.analysis_image" class="qe-image">
          <el-image :src="'/uploads/' + form.analysis_image" :preview-src-list="['/uploads/' + form.analysis_image]" preview-teleported fit="contain" class="qe-thumb" />
          <el-button size="small" @click="form.analysis_image = ''">移除</el-button>
        </div>
        <el-upload v-else :show-file-list="false" accept="image/*" :http-request="options => upload_to('analysis_image', options)">
          <el-button size="small" type="primary" :loading="uploading === 'analysis_image'">上传图片</el-button>
        </el-upload>
      </el-form-item>
      <el-form-item label="难度"><el-rate v-model="form.difficulty" :max="5" /></el-form-item>
      <el-form-item label="年级">
        <el-select v-model="form.grade" placeholder="选择年级" clearable>
          <el-option v-for="g in GRADE_OPTIONS" :key="g.value" :label="g.label" :value="g.value" />
        </el-select>
      </el-form-item>
      <el-form-item label="学期">
        <el-select v-model="form.semester" placeholder="选择学期" clearable>
          <el-option label="上学期" :value="1" />
          <el-option label="下学期" :value="2" />
        </el-select>
      </el-form-item>
      <el-form-item label="知识点">
        <KnowledgePointPicker v-model="form.knowledge_point_ids" v-model:primary-id="form.primary_knowledge_point_id" :subject-id="form.subject_id" />
      </el-form-item>
      <el-form-item label="标签">
        <el-select v-model="form.tag_ids" multiple placeholder="选择标签" style="width: 100%">
          <el-option v-for="tag in tags" :key="tag.id" :label="tag.name" :value="tag.id" />
        </el-select>
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="emit('update:modelValue', false)">取消</el-button>
      <el-button type="primary" :loading="saving" @click="save">保存</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import MathEditor from '@/components/MathEditor.vue'
import KnowledgePointPicker from '@/components/KnowledgePointPicker.vue'
import { questionApi } from '@/api/question'
import { uploadApi } from '@/api/upload'
import { GRADE_OPTIONS } from './questionFilters'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  // 要编辑的错题（列表里的那一行）
  question: { type: Object, default: null },
  subjects: { type: Array, default: () => [] },
  tags: { type: Array, default: () => [] },
})
// saved：保存成功；conflict：知识点被别处改过（409），父组件重新读列表
const emit = defineEmits(['update:modelValue', 'saved', 'conflict'])

const saving = ref(false)
// 正在上传哪一张图：'original_image' / 'analysis_image' / ''
const uploading = ref('')
const form = reactive({
  subject_id: null,
  original_image: '',
  parsed_question: '',
  question_no: '',
  wrong_answer: '',
  answer: '',
  analysis: '',
  analysis_image: '',
  difficulty: 3,
  knowledge_point_ids: [],
  primary_knowledge_point_id: null,
  knowledge_revision: 0,
  grade: null,
  semester: null,
  tag_ids: [],
})

/** 用这道题当前的内容填表；带上读取时的知识点版本号，保存时后端据此判断有没有被别处改过 */
function fill(row) {
  const points = row.knowledge_points || []
  Object.assign(form, {
    subject_id: row.subject_id || null,
    original_image: row.original_image || '',
    parsed_question: row.parsed_question || '',
    question_no: row.question_no || '',
    wrong_answer: row.wrong_answer || '',
    answer: row.answer || '',
    analysis: row.analysis || '',
    analysis_image: row.analysis_image || '',
    difficulty: row.difficulty || 3,
    knowledge_point_ids: points.map(point => point.id),
    primary_knowledge_point_id: points.find(point => point.is_primary)?.id ?? null,
    knowledge_revision: row.knowledge_revision || 0,
    grade: row.grade || null,
    semester: row.semester || null,
    tag_ids: (row.tags || []).map(tag => tag.id),
  })
}

// 打开时填表（只在打开那一刻填，之后的修改不会被覆盖）
watch(() => props.modelValue, visible => {
  if (visible && props.question) fill(props.question)
}, { immediate: true })

/** 手动换学科时清空已选知识点（知识点属于学科） */
function on_subject_change() {
  form.knowledge_point_ids = []
  form.primary_knowledge_point_id = null
}

/** 上传一张图片，成功后把存储路径写进表单的对应字段 */
async function upload_to(field, { file }) {
  uploading.value = field
  try {
    const { data } = await uploadApi.uploadFile(file)
    const path = data?.path || data?.image_path || data?.file_path
    if (!path) throw new Error('no path')
    form[field] = path
    ElMessage.success('上传成功')
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '上传失败')
  } finally {
    uploading.value = ''
  }
}

/** 保存；选了知识点必须指定主考点 */
async function save() {
  if (form.knowledge_point_ids.length && !form.primary_knowledge_point_id) {
    ElMessage.warning('请为所选知识点指定主考点')
    return
  }
  saving.value = true
  try {
    await questionApi.update(props.question.id, { ...form })
    ElMessage.success('更新成功')
    emit('update:modelValue', false)
    emit('saved')
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '更新失败')
    if (error.response?.status === 409) emit('conflict')
  } finally {
    saving.value = false
  }
}
</script>

<style scoped>
.qe-form { max-width: 600px; }
.qe-image { display: flex; align-items: center; gap: 10px; }
.qe-thumb { width: 100px; height: 100px; border-radius: 8px; background: var(--bg); cursor: zoom-in; }

@media (max-width: 768px) {
  .qe-form :deep(.el-form-item) { flex-direction: column; align-items: stretch; }
  .qe-form :deep(.el-form-item__label) { justify-content: flex-start; width: auto !important; }
}
</style>
