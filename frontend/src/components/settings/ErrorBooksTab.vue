<template>
  <!-- 设置 · 错题本：新增、编辑、删除 -->
  <div class="books-tab">
    <div class="set-bar">
      <el-button type="primary" @click="open_new"><el-icon><Plus /></el-icon>新增错题本</el-button>
    </div>
    <MobileList v-if="is_mobile" :rows="rows" />
    <el-table v-else v-loading="loading" :data="books" stripe style="width: 100%">
      <el-table-column prop="id" label="ID" width="80" />
      <el-table-column prop="name" label="错题本名称" />
      <el-table-column prop="subject_name" label="学科" width="100" />
      <el-table-column prop="description" label="描述" />
      <el-table-column label="操作" width="160" fixed="right">
        <template #default="{ row }">
          <ListActions :primary="{ label: '编辑', run: () => open_edit(row) }" :actions="[{ label: '删除', run: () => remove(row), danger: true }]" />
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="dialog_visible" :title="editing ? '编辑错题本' : '新增错题本'" :width="is_mobile ? '92%' : '500px'">
      <el-form :model="form" :label-width="is_mobile ? '90px' : '100px'">
        <el-form-item label="错题本名称" required>
          <el-input v-model="form.name" placeholder="请输入错题本名称" />
        </el-form-item>
        <el-form-item label="学科" required>
          <el-select v-model="form.subject_id" placeholder="选择学科" style="width: 100%">
            <el-option v-for="s in catalog.subjects" :key="s.id" :label="s.name" :value="s.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="form.description" type="textarea" :rows="3" placeholder="请输入描述" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialog_visible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="save">保存</el-button>
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
import { book_rows, with_subject_names } from './settingsModel'

const catalog = useCatalogStore()
const is_mobile = use_is_mobile()
const raw_books = ref([])
const loading = ref(false)
const saving = ref(false)
const dialog_visible = ref(false)
// 正在编辑的错题本；新增时为 null
const editing = ref(null)
const form = reactive({ name: '', subject_id: null, description: '' })

// 列表里补上学科名（学科从目录 store 取）
const books = computed(() => with_subject_names(raw_books.value, catalog.subjects))
const rows = computed(() => book_rows(books.value, { edit: open_edit, remove }))

/** 读错题本列表 */
async function load() {
  loading.value = true
  try {
    const { data } = await questionApi.listErrorBooks()
    raw_books.value = data.items || []
  } catch (e) {
    console.error('获取错题本失败:', e)
  } finally {
    loading.value = false
  }
}

/** 打开新增弹窗 */
function open_new() {
  editing.value = null
  Object.assign(form, { name: '', subject_id: null, description: '' })
  dialog_visible.value = true
}

/** 打开编辑弹窗 */
function open_edit(row) {
  editing.value = row
  Object.assign(form, { name: row.name, subject_id: row.subject_id, description: row.description || '' })
  dialog_visible.value = true
}

/** 新增或保存修改 */
async function save() {
  if (!form.name.trim()) return ElMessage.warning('请输入错题本名称')
  if (!form.subject_id) return ElMessage.warning('请选择学科')
  saving.value = true
  try {
    const payload = { ...form }
    if (editing.value) {
      await questionApi.updateErrorBook(editing.value.id, payload)
      ElMessage.success('更新成功')
    } else {
      await questionApi.createErrorBook(payload)
      ElMessage.success('创建成功')
    }
    dialog_visible.value = false
    editing.value = null
    load()
  } catch {
    ElMessage.error('保存失败')
  } finally {
    saving.value = false
  }
}

/** 删除错题本（先确认） */
async function remove(row) {
  try {
    await ElMessageBox.confirm(`确定要删除错题本“${row.name}”吗？`, '删除确认', { type: 'warning' })
    await questionApi.deleteErrorBook(row.id)
    ElMessage.success('删除成功')
    load()
  } catch (e) {
    if (e !== 'cancel') ElMessage.error('删除失败')
  }
}

onMounted(() => {
  catalog.loadSubjects().catch(e => console.error('获取学科失败:', e))
  load()
})
</script>

<style scoped>
.set-bar { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 12px; }
</style>
