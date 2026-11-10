<template>
  <el-dialog
    :model-value="modelValue"
    :title="isEdit ? '编辑记录' : '新增记录'"
    width="560px"
    class="paper-form-dialog"
    destroy-on-close
    @update:model-value="emit('update:modelValue', $event)"
    @open="resetForm"
  >
    <el-form label-position="top">
      <p v-if="isHistory" class="history-note">这是整理旧题时自动建的记录</p>

      <el-form-item v-if="!isHistory" label="学科" required>
        <el-select v-model="form.subject_id" placeholder="选择学科" :disabled="isEdit" style="width: 100%">
          <el-option v-for="s in subjectOptions" :key="s.id" :label="s.name" :value="s.id" />
        </el-select>
      </el-form-item>

      <el-form-item label="名称">
        <el-input v-model="form.name" :placeholder="isEdit ? '' : '不填会自动取名'" maxlength="100" />
      </el-form-item>

      <template v-if="!isHistory">
        <el-form-item label="类型">
          <el-radio-group v-model="form.paper_type">
            <el-radio-button v-for="(label, value) in PAPER_TYPE_LABELS" :key="value" :value="value">{{ label }}</el-radio-button>
          </el-radio-group>
        </el-form-item>
        <el-form-item v-if="form.paper_type === 'exam'" label="考试细分">
          <el-radio-group v-model="form.exam_kind">
            <el-radio-button v-for="(label, value) in EXAM_KIND_LABELS" :key="value" :value="value">{{ label }}</el-radio-button>
          </el-radio-group>
        </el-form-item>

        <el-form-item label="日期">
          <el-date-picker v-model="form.paper_date" type="date" value-format="YYYY-MM-DD" placeholder="选择日期" :clearable="false" style="width: 100%" />
        </el-form-item>

        <div class="two-cols">
          <el-form-item label="年级">
            <el-select v-model="form.grade" placeholder="不填" clearable style="width: 100%">
              <el-option v-for="g in GRADE_OPTIONS" :key="g.value" :label="g.label" :value="g.value" />
            </el-select>
          </el-form-item>
          <el-form-item label="学期">
            <el-select v-model="form.semester" placeholder="不填" clearable style="width: 100%">
              <el-option label="上学期" :value="1" />
              <el-option label="下学期" :value="2" />
            </el-select>
          </el-form-item>
        </div>

        <div class="two-cols">
          <el-form-item label="得分">
            <el-input-number v-model="form.score" :min="0" :precision="1" :step="1" :controls="false" placeholder="不填" style="width: 100%" />
          </el-form-item>
          <el-form-item label="满分">
            <el-input-number v-model="form.full_score" :min="0" :precision="1" :step="1" :controls="false" placeholder="不填" style="width: 100%" />
          </el-form-item>
        </div>
        <p v-if="form.paper_type === 'exam'" class="exam-hint">考试建议填上分数</p>
      </template>

      <el-form-item label="备注">
        <el-input v-model="form.notes" type="textarea" :rows="3" maxlength="500" show-word-limit />
      </el-form-item>
    </el-form>

    <template #footer>
      <el-button @click="emit('update:modelValue', false)">取消</el-button>
      <el-button type="primary" :loading="saving" @click="save">保存</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { reactive, ref, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { paperApi } from '@/api/paper'
import { PAPER_TYPE_LABELS, EXAM_KIND_LABELS } from '@/composables/intakeLabels'

const props = defineProps({
  modelValue: Boolean,
  // 为空表示新增，有值表示编辑这份卷子
  paper: { type: Object, default: null },
  subjects: { type: Array, default: () => [] },
  // 新增时默认选中的学科
  defaultSubjectId: { type: Number, default: null },
})
const emit = defineEmits(['update:modelValue', 'saved'])

const GRADE_OPTIONS = [
  { label: '一年级', value: 1 }, { label: '二年级', value: 2 }, { label: '三年级', value: 3 },
  { label: '四年级', value: 4 }, { label: '五年级', value: 5 }, { label: '六年级', value: 6 },
  { label: '初一', value: 7 }, { label: '初二', value: 8 }, { label: '初三', value: 9 },
  { label: '高一', value: 10 }, { label: '高二', value: 11 }, { label: '高三', value: 12 },
]

const isEdit = computed(() => !!props.paper)
const isHistory = computed(() => props.paper?.source === 'history')
// 学科下拉的选项：编辑时学科不可改，只列出这份卷子自己的学科
const subjectOptions = computed(() => props.paper ? [{ id: props.paper.subject_id, name: props.paper.subject_name }] : props.subjects)
const saving = ref(false)
const form = reactive({
  subject_id: null,
  name: '',
  paper_type: 'homework',
  exam_kind: 'unit',
  paper_date: '',
  grade: null,
  semester: null,
  score: null,
  full_score: null,
  notes: '',
})

// 今天的日期，格式 YYYY-MM-DD（按本地时间）
function todayText() {
  const d = new Date()
  const pad = n => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
}

// 数字字段：空值统一成 null，其余转成数字
function numberOrNull(value) {
  return value === null || value === undefined || value === '' ? null : Number(value)
}

// 打开对话框时重置表单：编辑带入现值，新增用默认值
function resetForm() {
  const p = props.paper
  form.subject_id = p ? p.subject_id : (props.defaultSubjectId || null)
  form.name = p ? (p.name || '') : ''
  form.paper_type = p ? p.paper_type : 'homework'
  form.exam_kind = p?.exam_kind || 'unit'
  form.paper_date = p ? (p.paper_date || todayText()) : todayText()
  form.grade = p ? (p.grade ?? null) : null
  form.semester = p ? (p.semester ?? null) : null
  form.score = p ? numberOrNull(p.score) : null
  form.full_score = p ? numberOrNull(p.full_score) : null
  form.notes = p ? (p.notes || '') : ''
}

// 检查得分和满分：要么都填，要么都不填（得分是否超过满分由接口判断）
function checkScores() {
  const score = numberOrNull(form.score)
  const full = numberOrNull(form.full_score)
  if ((score === null) !== (full === null)) {
    ElMessage.warning('得分和满分要一起填，或者都不填')
    return false
  }
  return true
}

// 新增时提交的内容：名称为空不传（由服务器自动取名）
function buildCreateBody() {
  const body = {
    subject_id: form.subject_id,
    paper_type: form.paper_type,
    paper_date: form.paper_date || null,
    grade: form.grade,
    semester: form.semester,
    notes: form.notes.trim() || null,
  }
  if (form.name.trim()) body.name = form.name.trim()
  if (form.paper_type === 'exam') body.exam_kind = form.exam_kind
  const score = numberOrNull(form.score)
  if (score !== null) {
    body.score = score
    body.full_score = numberOrNull(form.full_score)
  }
  return body
}

// 编辑时只提交改过的字段，没改的不传，服务器会保留原值
function buildUpdateBody() {
  const p = props.paper
  const body = {}
  const name = form.name.trim()
  const notes = form.notes.trim() || null
  if (name !== (p.name || '')) body.name = name
  if (notes !== (p.notes || null)) body.notes = notes
  if (isHistory.value) return body // 旧题记录只能改名称和备注

  if (form.paper_type !== p.paper_type) body.paper_type = form.paper_type
  // 考试才有细分：改成非考试时清掉细分
  // 细分下拉默认显示"单元测"，原来没有细分且没动过它时不当作修改
  const kindUntouched = form.paper_type === p.paper_type && form.exam_kind === (p.exam_kind || 'unit')
  const newKind = form.paper_type === 'exam' ? form.exam_kind : null
  if (!kindUntouched && newKind !== (p.exam_kind || null)) body.exam_kind = newKind
  if (form.paper_date && form.paper_date !== p.paper_date) body.paper_date = form.paper_date
  if (form.grade !== (p.grade ?? null)) body.grade = form.grade
  if (form.semester !== (p.semester ?? null)) body.semester = form.semester
  // 得分和满分必须一起提交；两格都清空就一起清成 null
  const score = numberOrNull(form.score)
  const full = numberOrNull(form.full_score)
  if (score !== numberOrNull(p.score) || full !== numberOrNull(p.full_score)) {
    body.score = score
    body.full_score = full
  }
  return body
}

// 保存：新增调 create，编辑调 update，失败时显示接口返回的说明
async function save() {
  if (!isHistory.value) {
    if (!isEdit.value && !form.subject_id) {
      ElMessage.warning('请先选择学科')
      return
    }
    if (!checkScores()) return
  }
  saving.value = true
  try {
    if (isEdit.value) {
      const body = buildUpdateBody()
      if (!Object.keys(body).length) {
        emit('update:modelValue', false)
        return
      }
      await paperApi.update(props.paper.id, body)
      ElMessage.success('已保存')
    } else {
      await paperApi.create(buildCreateBody())
      ElMessage.success('已新增')
    }
    emit('update:modelValue', false)
    emit('saved')
  } catch (error) {
    const detail = error.response?.data?.detail
    ElMessage.error(typeof detail === 'string' ? detail : '保存失败，请检查填写的内容')
  } finally {
    saving.value = false
  }
}
</script>

<style scoped>
.two-cols { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
.exam-hint { margin: -6px 0 14px; font-size: 13px; color: var(--el-color-warning); }
.history-note { margin: 0 0 12px; font-size: 13px; color: var(--text-muted); }

@media (max-width: 768px) {
  .two-cols { grid-template-columns: 1fr; gap: 0; }
}
</style>

<style>
@media (max-width: 768px) {
  .paper-form-dialog.el-dialog { width: 92% !important; }
}
</style>
