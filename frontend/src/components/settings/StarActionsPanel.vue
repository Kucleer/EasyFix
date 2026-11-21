<template>
  <!--
    积分行为配置 + 手动调整积分。
    暂不放在设置页的标签栏里，等成就项目再放回来；组件本身完整可用。
  -->
  <div class="star-actions-panel">
    <div class="adjust-box">
      <h4>积分调整</h4>
      <el-form :model="adjust_form" :inline="!is_mobile">
        <el-form-item label="积分变动">
          <el-input-number v-model="adjust_form.delta" :min="-9999" :max="9999" controls-position="right" style="width: 120px" />
          <span class="hint">（正数增加，负数减少）</span>
        </el-form-item>
        <el-form-item label="调整原因" required>
          <el-input v-model="adjust_form.reason" placeholder="请输入调整原因" maxlength="200" show-word-limit class="reason-input" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="adjusting" @click="adjust">确认调整</el-button>
        </el-form-item>
      </el-form>
      <div v-if="balance !== null" class="adjust-result">
        调整后积分余额：<span class="balance-value">{{ balance }}</span>
      </div>
    </div>

    <div class="set-bar">
      <el-button type="primary" @click="open_new"><el-icon><Plus /></el-icon>新增行为</el-button>
    </div>
    <MobileList v-if="is_mobile" :rows="rows" />
    <el-table v-else v-loading="loading" :data="actions" stripe style="width: 100%">
      <el-table-column prop="id" label="ID" width="80" />
      <el-table-column prop="code" label="行为代码" width="150" />
      <el-table-column prop="name" label="行为名称" width="120" />
      <el-table-column prop="star_value" label="积分值" width="100">
        <template #default="{ row }">
          <span :class="row.star_value >= 0 ? 'text-up' : 'text-down'">{{ format_signed(row.star_value) }}</span>
        </template>
      </el-table-column>
      <el-table-column prop="enabled" label="启用" width="80">
        <template #default="{ row }"><el-tag :type="row.enabled ? 'success' : 'info'">{{ row.enabled ? '是' : '否' }}</el-tag></template>
      </el-table-column>
      <el-table-column prop="is_custom" label="类型" width="100">
        <template #default="{ row }"><el-tag :type="row.is_custom ? 'warning' : 'primary'">{{ row.is_custom ? '自定义' : '预设' }}</el-tag></template>
      </el-table-column>
      <el-table-column label="操作" width="160" fixed="right">
        <template #default="{ row }">
          <ListActions :primary="{ label: '编辑', run: () => open_edit(row) }" :actions="[{ label: '删除', run: () => remove(row), disabled: row.is_preset, danger: true }]" />
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="dialog_visible" :title="editing ? '编辑行为' : '新增行为'" :width="is_mobile ? '92%' : '500px'">
      <el-form :model="form" label-width="100px">
        <el-form-item label="行为代码" required>
          <el-input v-model="form.code" placeholder="如: upload_question" :disabled="!!editing" />
        </el-form-item>
        <el-form-item label="行为名称" required>
          <el-input v-model="form.name" placeholder="如: 上传错题" />
        </el-form-item>
        <el-form-item label="积分值" required>
          <el-input-number v-model="form.star_value" :min="-999" :max="999" />
        </el-form-item>
        <el-form-item label="启用">
          <el-switch v-model="form.enabled" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialog_visible = false">取消</el-button>
        <el-button type="primary" @click="save">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, reactive, ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { motivationApi } from '@/api/motivation'
import { use_is_mobile } from '@/composables/useIsMobile'
import MobileList from './MobileList.vue'
import { star_action_rows, format_signed } from './settingsModel'

const is_mobile = use_is_mobile()
const actions = ref([])
const loading = ref(false)
const dialog_visible = ref(false)
const editing = ref(null)
const form = reactive({ code: '', name: '', star_value: 0, enabled: true })
const rows = computed(() => star_action_rows(actions.value, { edit: open_edit, remove }))

// 积分调整
const adjust_form = reactive({ delta: 0, reason: '' })
const adjusting = ref(false)
const balance = ref(null)

/** 读积分行为列表 */
async function load() {
  loading.value = true
  try {
    const { data } = await motivationApi.getActions()
    actions.value = Array.isArray(data) ? data : (data.items || [])
  } catch (e) {
    console.error('获取行为列表失败:', e)
  } finally {
    loading.value = false
  }
}

/** 读当前积分余额 */
async function fetch_balance() {
  try {
    const { data } = await motivationApi.getBalance()
    balance.value = data.balance
  } catch (e) {
    console.error('获取积分余额失败:', e)
  }
}

/** 手动加减积分，必须写原因 */
async function adjust() {
  if (!adjust_form.reason.trim()) return ElMessage.warning('请输入调整原因')
  adjusting.value = true
  try {
    const { data } = await motivationApi.adjustStars({ delta: adjust_form.delta, reason: adjust_form.reason })
    balance.value = data.new_balance
    adjust_form.delta = 0
    adjust_form.reason = ''
    ElMessage.success('积分调整成功')
    fetch_balance()
  } catch (e) {
    ElMessage.error(e.detail || '调整失败')
  } finally {
    adjusting.value = false
  }
}

/** 打开新增弹窗 */
function open_new() {
  editing.value = null
  Object.assign(form, { code: '', name: '', star_value: 0, enabled: true })
  dialog_visible.value = true
}

/** 打开编辑弹窗（行为代码不能改） */
function open_edit(row) {
  editing.value = row
  Object.assign(form, { code: row.code, name: row.name, star_value: row.star_value, enabled: row.enabled })
  dialog_visible.value = true
}

/** 新增或保存修改 */
async function save() {
  if (!form.code.trim()) return ElMessage.warning('请输入行为代码')
  if (!form.name.trim()) return ElMessage.warning('请输入行为名称')
  try {
    if (editing.value) {
      await motivationApi.updateAction(editing.value.id, { ...form })
      ElMessage.success('更新成功')
    } else {
      await motivationApi.createAction({ ...form })
      ElMessage.success('创建成功')
    }
    dialog_visible.value = false
    editing.value = null
    load()
  } catch {
    ElMessage.error('保存失败')
  }
}

/** 删除行为（预设行为不能删） */
async function remove(row) {
  try {
    await ElMessageBox.confirm('确定要删除该行为吗？', '删除确认', { type: 'warning' })
    await motivationApi.deleteAction(row.id)
    ElMessage.success('删除成功')
    load()
  } catch (e) {
    if (e !== 'cancel') ElMessage.error('删除失败')
  }
}

onMounted(load)
</script>

<style scoped>
.adjust-box { margin-bottom: 20px; padding: 16px; border: 1px solid var(--line); border-radius: var(--r-sm); background: #f8f7fd; }
.adjust-box h4 { margin: 0 0 12px; color: var(--ink); }
.hint { margin-left: 8px; color: var(--muted); }
.reason-input { width: 300px; }
.adjust-result { margin-top: 12px; color: var(--ink-2); }
.balance-value { font-size: 18px; font-weight: 700; color: var(--brand); }
.set-bar { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 12px; }
.text-up { color: var(--mint); font-weight: 700; }
.text-down { color: var(--coral); font-weight: 700; }

@media (max-width: 768px) {
  .adjust-box { padding: 12px; }
  .reason-input { width: 100%; }
}
</style>
