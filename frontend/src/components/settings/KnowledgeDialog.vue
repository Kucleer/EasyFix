<template>
  <!-- 知识点的新增 / 编辑弹窗；待处理旧目录"转为二级"也走编辑这一路 -->
  <el-dialog v-model="visible" :title="editing ? '编辑知识点' : '新增知识点'" :width="is_mobile ? '92%' : '560px'" @closed="editing = null">
    <el-form :model="form" :label-width="is_mobile ? '80px' : '100px'">
      <el-form-item label="层级" required>
        <el-radio-group v-model="form.level" :disabled="!!editing">
          <el-radio :value="1">一级模块</el-radio>
          <el-radio :value="2">二级考点</el-radio>
        </el-radio-group>
      </el-form-item>
      <el-form-item v-if="form.level === 2" label="所属一级" required>
        <el-select v-model="form.parent_id" placeholder="选择一级模块" style="width: 100%" :disabled="locked" @change="on_parent_change">
          <el-option v-for="module in module_options" :key="module.id" :label="module.name" :value="module.id" />
        </el-select>
      </el-form-item>
      <el-form-item :label="form.level === 1 ? '模块名称' : '考点名称'" required>
        <el-input v-model="form.name" placeholder="请输入名称" />
      </el-form-item>
      <el-form-item label="学科" required>
        <el-select v-model="form.subject_id" placeholder="选择学科" style="width: 100%" :disabled="locked" @change="form.parent_id = null">
          <el-option v-for="s in subjects" :key="s.id" :label="s.name" :value="s.id" />
        </el-select>
      </el-form-item>
      <el-form-item label="编码">
        <el-input v-model="form.code" placeholder="留空自动生成，改名不变" />
      </el-form-item>
      <el-form-item label="排序">
        <el-input-number v-model="form.sort_order" :min="0" :max="9999" controls-position="right" />
      </el-form-item>
      <el-form-item label="年级">
        <el-select v-model="form.grade" placeholder="仅作推荐筛选" clearable style="width: 100%">
          <el-option v-for="g in GRADE_OPTIONS" :key="g.value" :label="g.label" :value="g.value" />
        </el-select>
      </el-form-item>
      <el-form-item label="学期">
        <el-select v-model="form.semester" placeholder="仅作推荐筛选" clearable style="width: 100%">
          <el-option v-for="s in SEMESTER_OPTIONS" :key="s.value" :label="s.label" :value="s.value" />
        </el-select>
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="visible = false">取消</el-button>
      <el-button type="primary" :loading="saving" @click="save">保存</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { computed, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { questionApi } from '@/api/question'
import { useAppConfigStore } from '@/stores/appConfig'
import { refreshKnowledgeColors } from '@/composables/knowledgeColors'
import { use_is_mobile } from '@/composables/useIsMobile'
import { GRADE_OPTIONS, SEMESTER_OPTIONS, KP_MEMORY_KEYS, read_saved_number } from './settingsModel'

const props = defineProps({
  // 当前目录树（一级在外层），用来列出"所属一级"的选项
  tree: { type: Array, default: () => [] },
  subjects: { type: Array, default: () => [] },
  // 页面筛选里选中的学科：新增时没有记住的学科就用它
  filterSubjectId: { type: Number, default: null },
})
const emit = defineEmits(['saved'])

const appConfigStore = useAppConfigStore()
const is_mobile = use_is_mobile()
const visible = ref(false)
const saving = ref(false)
// 正在编辑的那一行；新增时为 null
const editing = ref(null)
const form = reactive({ name: '', subject_id: null, level: 2, parent_id: null, code: '', sort_order: 0, grade: null, semester: null })

// 已经在新树里的节点不能改学科、不能移动；旧目录（level 为空）转为二级时可以选
const locked = computed(() => !!editing.value && editing.value.level != null)
// "所属一级"只列同一学科的一级模块
const module_options = computed(() => (props.tree || [])
  .filter(item => item.level === 1)
  .filter(item => !form.subject_id || item.subject_id === form.subject_id))

/** 读 localStorage 里记住的上次选择 */
function saved(kind) {
  return read_saved_number(globalThis.localStorage, KP_MEMORY_KEYS[kind])
}

/** 选了一级模块后，学科跟着这个模块走 */
function on_parent_change(parent_id) {
  const module = props.tree.find(item => item.id === parent_id)
  if (module) form.subject_id = module.subject_id
}

/** 打开新增弹窗；可传入一级模块作为父级。学科、年级、学期优先用上次记住的 */
function open_new(level = 2, parent = null) {
  editing.value = null
  Object.assign(form, {
    name: '',
    level,
    parent_id: parent?.id ?? null,
    subject_id: parent?.subject_id ?? saved('subject') ?? props.filterSubjectId,
    code: '',
    sort_order: 0,
    grade: saved('grade') ?? appConfigStore.defaultGrade,
    semester: saved('semester') ?? appConfigStore.defaultSemester,
  })
  visible.value = true
}

/** 打开编辑弹窗；旧目录转为二级也用它（复用原 ID，由用户明确选择父级） */
function open_edit(row) {
  editing.value = row
  Object.assign(form, {
    name: row.name,
    subject_id: row.subject_id,
    level: row.level || 2,
    parent_id: row.parent_id || null,
    code: row.code || '',
    sort_order: row.sort_order || 0,
    grade: row.grade,
    semester: row.semester,
  })
  visible.value = true
}

/** 新增时把学科、年级、学期记下来，下次新增直接带入 */
function remember_choice() {
  try {
    localStorage.setItem(KP_MEMORY_KEYS.subject, form.subject_id)
    localStorage.setItem(KP_MEMORY_KEYS.grade, form.grade || '')
    localStorage.setItem(KP_MEMORY_KEYS.semester, form.semester || '')
  } catch {
    // 浏览器不让写就算了，只是下次不能自动带入
  }
}

/** 保存：校验必填项，写入后刷新知识点配色（会让目录 store 里的知识点树失效） */
async function save() {
  if (!form.name.trim()) return ElMessage.warning('请输入知识点名称')
  if (!form.subject_id) return ElMessage.warning('请选择学科')
  if (form.level === 2 && !form.parent_id) return ElMessage.warning('请选择所属一级模块')
  saving.value = true
  const is_edit = !!editing.value
  try {
    const payload = {
      name: form.name.trim(),
      subject_id: form.subject_id,
      level: form.level,
      parent_id: form.level === 2 ? form.parent_id : null,
      sort_order: form.sort_order || 0,
      grade: form.grade,
      semester: form.semester,
    }
    if (form.code.trim()) payload.code = form.code.trim()
    if (is_edit) {
      await questionApi.updateKnowledgePoint(editing.value.id, payload)
      ElMessage.success('更新成功')
    } else {
      await questionApi.createKnowledgePoint(payload)
      ElMessage.success('创建成功')
      remember_choice()
    }
    visible.value = false
    await refreshKnowledgeColors()
    emit('saved')
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || (is_edit ? '更新失败' : '创建失败'))
  } finally {
    saving.value = false
  }
}

defineExpose({ open_new, open_edit })
</script>
