<template>
  <!-- 已录入：收成一行，可以撤回 -->
  <div v-if="item.state === 'accepted'" class="scan-item-card accepted">
    <span class="accepted-text">
      <el-icon class="accepted-icon"><circle-check /></el-icon>
      {{ itemLabel(item) }} 已录入
    </span>
    <el-button link type="primary" size="small" :loading="busy" @click="emit('withdraw')">撤回</el-button>
  </div>

  <div v-else class="scan-item-card">
    <div class="card-head">
      <span class="item-title">{{ itemLabel(item) }}</span>
      <span class="head-tags">
        <el-tag v-if="item.edited" size="small" type="info">改过</el-tag>
        <el-tag size="small" :type="source_tag.type">{{ source_tag.text }}</el-tag>
      </span>
    </div>

    <!-- 录入被拒或补全失败时的提示，放在卡片顶部 -->
    <el-alert v-if="serverError" class="card-alert" type="error" :title="serverError" :closable="false" show-icon />

    <!-- 修改状态 -->
    <el-form v-if="editing" :model="form" label-width="84px" class="edit-form">
      <el-form-item label="题号">
        <el-input v-model="form.question_no" placeholder="如 3 或 二(1)" style="max-width: 200px" />
      </el-form-item>
      <el-form-item label="题干">
        <MathEditor v-model="form.parsed_question" :rows="4" placeholder="题目内容" />
      </el-form-item>
      <el-form-item label="学生的答案">
        <MathEditor v-model="form.wrong_answer" :rows="2" placeholder="学生写的答案" />
      </el-form-item>
      <el-form-item label="正确答案">
        <MathEditor v-model="form.answer" :rows="2" placeholder="正确答案" />
      </el-form-item>
      <el-form-item label="解析">
        <MathEditor v-model="form.analysis" :rows="3" placeholder="解题思路" />
      </el-form-item>
      <el-form-item label="考点">
        <KnowledgePointPicker
          v-model="form.knowledge_point_ids"
          v-model:primary-id="form.primary_knowledge_point_id"
          :subject-id="subjectId"
        />
      </el-form-item>
      <el-form-item label="难度">
        <el-rate v-model="form.difficulty" :max="5" show-text :texts="DIFFICULTY_TEXTS" />
      </el-form-item>
      <div class="card-actions">
        <el-button size="small" :disabled="saving" @click="cancel_edit">取消</el-button>
        <el-button type="primary" size="small" :loading="saving" :disabled="busy && !saving" @click="submit_edit">保存</el-button>
      </div>
    </el-form>

    <!-- 只读状态 -->
    <template v-else>
      <el-alert
        v-for="text in warning_list"
        :key="text"
        class="card-alert"
        type="warning"
        :closable="false"
        show-icon
      >
        <!-- 拿不准的原因来自模型，可能带公式 -->
        <template #title><MathText :text="text" /></template>
      </el-alert>
      <div class="field-row">
        <MathText :text="item.parsed_question || '（没有题干，点修改补上）'" />
      </div>
      <div class="field-grid">
        <div class="field">
          <span class="field-label">学生的答案</span>
          <MathText :text="item.wrong_answer || '—'" />
        </div>
        <div class="field">
          <span class="field-label">正确答案</span>
          <MathText :text="item.answer || '—'" />
        </div>
        <div class="field">
          <span class="field-label">考点</span>
          <span>{{ knowledge_label || '未分类' }}</span>
        </div>
      </div>
      <div v-if="item.reason && item.verdict !== 'unsure'" class="reason">判断理由：<MathText :text="item.reason" /></div>
      <div class="card-actions">
        <!-- 不是错题：浅红描边，表示"移出列表"，和修改（白底）、录入（主色）区分开 -->
        <el-button type="danger" plain size="small" :disabled="busy" @click="emit('dismiss')">不是错题</el-button>
        <el-button size="small" :disabled="busy" @click="start_edit">修改</el-button>
        <el-button type="primary" size="small" :loading="busy" @click="request_accept">录入</el-button>
      </div>
    </template>
  </div>
</template>

<script setup>
// 整理区里的一道题：只读显示、修改表单、录入/不是错题/撤回
import MathText from '@/components/MathText.vue'
import MathEditor from '@/components/MathEditor.vue'
import KnowledgePointPicker from '@/components/KnowledgePointPicker.vue'
import { ref, computed, watch, onMounted, onBeforeUnmount } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { CircleCheck } from '@element-plus/icons-vue'
import {
  hasWarning, warningTexts, unsureHint, itemLabel, knowledgeText, editableFields,
} from '@/composables/scanPage'

const props = defineProps({
  item: { type: Object, required: true },                  // 草稿里的一道题
  subjectId: { type: Number, default: null },              // 这一页的学科，考点选择用
  knowledgeNames: { type: Object, default: () => ({}) },   // 考点编号 -> 名称
  serverError: { type: String, default: '' },              // 录入被拒等提示；非空时自动进修改状态
  busy: { type: Boolean, default: false },                 // 这道题有请求在进行
})

// save 的第二个参数是回调 finish(ok)：保存成功才回到只读，失败留在表单里不丢内容
// editing-change(是否在修改)：让整理区知道哪些题的表单开着（全部录入前要提醒）
const emit = defineEmits(['save', 'accept', 'dismiss', 'withdraw', 'editing-change'])

const DIFFICULTY_TEXTS = ['很简单', '简单', '一般', '较难', '很难']

const editing = ref(false)
const saving = ref(false)
const form = ref(editableFields(props.item))
const warning_confirmed = ref(false)  // 带提示的题已经确认过对照原图

// 标题右边的来源标签
const source_tag = computed(() => {
  if (props.item.source === 'manual') return { type: 'info', text: '手工加的' }
  if (props.item.source === 'promoted') return { type: 'primary', text: '补成的错题' }
  if (props.item.verdict === 'unsure') return { type: 'warning', text: '模型拿不准' }
  return { type: 'danger', text: '模型判断：做错了' }
})

// 黄色提示：读图异常（改过的不再提示）和拿不准的原因
const warning_list = computed(() => {
  const texts = hasWarning(props.item) ? warningTexts(props.item) : []
  const hint = unsureHint(props.item)
  return hint ? [...texts, hint] : texts
})

const knowledge_label = computed(() =>
  knowledgeText(props.item.knowledge_point_ids, props.item.primary_knowledge_point_id, props.knowledgeNames))

/** 进入修改状态，表单按这道题的当前内容重新填。 */
const start_edit = () => {
  form.value = editableFields(props.item)
  editing.value = true
}

/** 取消修改，回到只读。 */
const cancel_edit = () => {
  editing.value = false
}

/** 保存：先做和后端一样的考点检查，再交给上层调接口；成功才回只读。 */
const submit_edit = () => {
  const fields = editableFields(form.value)
  if (fields.knowledge_point_ids.length && !fields.primary_knowledge_point_id) {
    ElMessage.warning('选了考点就要选一个主考点')
    return
  }
  saving.value = true
  emit('save', fields, (ok) => {
    saving.value = false
    if (ok) editing.value = false
  })
}

/** 录入：带读图提示的题第一次先确认对照过原图。 */
const request_accept = async () => {
  if (hasWarning(props.item) && !warning_confirmed.value) {
    try {
      await ElMessageBox.confirm('这道题可能读错了，对照过原图了吗？', '录入前确认', {
        confirmButtonText: '对照过了，录入',
        cancelButtonText: '再看看',
        type: 'warning',
      })
    } catch {
      return  // 点了"再看看"
    }
    warning_confirmed.value = true
  }
  emit('accept')
}

// 录入被拒（或补全失败）时自动进修改状态；已经在改的保留正在填的内容
watch(() => props.serverError, (text) => {
  if (text && !editing.value) start_edit()
})

// 表单开关变化时告诉整理区
watch(editing, (value) => emit('editing-change', value))

// 这道题已经录入或去掉了（比如被"全部录入"带走），表单不再有意义，收起来，撤回后看到的是最新内容
watch(() => props.item.state, (state) => {
  if (state !== 'open') editing.value = false
})

// 卡片被移走（比如去掉）时，表单也随之关掉，告诉整理区
onBeforeUnmount(() => {
  if (editing.value) emit('editing-change', false)
})

onMounted(() => {
  if (props.serverError) {
    start_edit()
    return
  }
  // 手工加的空白题一出现就直接进修改状态
  if (props.item.source === 'manual' && props.item.state === 'open' && !props.item.edited) start_edit()
})
</script>

<style scoped>
.scan-item-card {
  border: 1px solid var(--border-light);
  border-radius: 10px;
  background: #fff;
  padding: 12px 14px;
}

.scan-item-card.accepted {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 14px;
  background: #f4fbf0;
}

.accepted-text {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  color: var(--text-primary);
}

.accepted-icon {
  color: #67c23a;
}

.card-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.item-title {
  font-weight: bold;
  color: var(--text-primary);
}

.head-tags {
  display: inline-flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 4px;
}

.card-alert {
  margin-bottom: 8px;
}

.field-row {
  margin-bottom: 8px;
  line-height: 1.7;
  overflow-wrap: anywhere;
}

.field-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 6px 16px;
}

.field {
  display: flex;
  gap: 8px;
  min-width: 0;
  overflow-wrap: anywhere;
}

.field-label {
  flex: none;
  color: var(--text-muted);
}

.reason {
  margin-top: 8px;
  font-size: 12px;
  color: var(--text-muted);
}

.card-actions {
  display: flex;
  justify-content: flex-end;
  align-items: center;
  gap: 8px;
  margin-top: 10px;
}

.edit-form :deep(.el-form-item) {
  margin-bottom: 12px;
}

/* 手机端：字段一行一个，表单标签放在上面 */
@media (max-width: 768px) {
  .field-grid {
    grid-template-columns: 1fr;
  }

  .edit-form :deep(.el-form-item) {
    display: block;
  }

  .edit-form :deep(.el-form-item__label) {
    justify-content: flex-start;
    width: auto !important;
  }

  .edit-form :deep(.el-form-item__content) {
    margin-left: 0 !important;
  }
}
</style>
