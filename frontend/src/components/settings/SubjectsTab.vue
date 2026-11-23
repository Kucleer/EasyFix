<template>
  <!-- 设置 · 学科：新增、删除；改完让目录数据 store 失效再重新读。学科全站共用，只有管理员能改 -->
  <div class="subjects-tab">
    <div v-if="editable" class="set-bar">
      <el-button type="primary" @click="dialog_visible = true"><el-icon><Plus /></el-icon>新增学科</el-button>
    </div>
    <MobileList v-if="is_mobile" :rows="rows" />
    <el-table v-else v-loading="loading" :data="subjects" stripe style="width: 100%">
      <el-table-column prop="id" label="ID" width="80" />
      <el-table-column prop="name" label="学科名称" />
      <el-table-column v-if="editable" label="操作" width="160" fixed="right">
        <template #default="{ row }">
          <ListActions :primary="{ label: '删除', run: () => remove(row), danger: true }" :actions="[]" />
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="dialog_visible" title="新增学科" :width="is_mobile ? '92%' : '400px'">
      <el-form :model="form" label-width="80px" @submit.prevent>
        <el-form-item label="学科名称" required>
          <el-input v-model="form.name" placeholder="请输入学科名称" @keyup.enter="create" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialog_visible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="create">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, reactive, ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { questionApi } from '@/api/question'
import { useCatalogStore } from '@/stores/catalog'
import { use_is_mobile } from '@/composables/useIsMobile'
import MobileList from './MobileList.vue'
import { can_edit_shared, subject_rows } from './settingsModel'
import { useAccountStore } from '@/stores/account'

const catalog = useCatalogStore()
const is_mobile = use_is_mobile()
const subjects = computed(() => catalog.subjects)
const loading = ref(false)
const saving = ref(false)
const dialog_visible = ref(false)
const form = reactive({ name: '' })
const accountStore = useAccountStore()
// 学科是全站共用的目录，只有管理员看得到新增、删除按钮
const editable = computed(() => can_edit_shared(accountStore.isAdmin))
const rows = computed(() => subject_rows(subjects.value, { remove })
  .map(row => (editable.value ? row : { ...row, actions: [] })))

/** 读学科列表；force 为真时跳过 store 里已有的数据 */
async function load(force = false) {
  loading.value = true
  try {
    await catalog.loadSubjects(force)
  } catch (e) {
    console.error('获取学科失败:', e)
  } finally {
    loading.value = false
  }
}

/** 学科变了：学科和知识点树都让 store 失效（删学科会影响知识点），再重新读学科 */
function reload_after_change() {
  catalog.invalidate('subjects')
  catalog.invalidate('knowledge')
  load()
}

/** 新增学科 */
async function create() {
  if (!form.name.trim()) {
    ElMessage.warning('请输入学科名称')
    return
  }
  saving.value = true
  try {
    await questionApi.createSubject(form.name.trim())
    ElMessage.success('创建成功')
    dialog_visible.value = false
    form.name = ''
    reload_after_change()
  } catch {
    ElMessage.error('创建失败')
  } finally {
    saving.value = false
  }
}

/** 删除学科（先确认） */
async function remove(row) {
  try {
    await ElMessageBox.confirm(`确定要删除学科“${row.name}”吗？`, '删除确认', { type: 'warning' })
    await questionApi.deleteSubject(row.id)
    ElMessage.success('删除成功')
    reload_after_change()
  } catch (e) {
    if (e !== 'cancel') ElMessage.error(e.response?.data?.detail || '删除失败')
  }
}

onMounted(() => load())
</script>

<style scoped>
.set-bar { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 12px; }
</style>
