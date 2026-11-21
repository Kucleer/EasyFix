<template>
  <!-- 设置 · 标签：名称 + 颜色，新增、删除；改完让目录数据 store 失效再重新读 -->
  <div class="tags-tab">
    <div class="set-bar">
      <el-button type="primary" @click="dialog_visible = true"><el-icon><Plus /></el-icon>新增标签</el-button>
    </div>
    <MobileList v-if="is_mobile" :rows="rows" />
    <el-table v-else v-loading="loading" :data="tags" stripe style="width: 100%">
      <el-table-column prop="id" label="ID" width="80" />
      <el-table-column prop="name" label="标签名称" />
      <el-table-column prop="color" label="颜色" width="120">
        <template #default="{ row }">
          <el-tag :style="{ backgroundColor: row.color, color: '#fff' }">{{ row.color || '默认' }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="160" fixed="right">
        <template #default="{ row }">
          <ListActions :primary="{ label: '删除', run: () => remove(row), danger: true }" :actions="[]" />
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="dialog_visible" title="新增标签" :width="is_mobile ? '92%' : '400px'">
      <el-form :model="form" label-width="80px" @submit.prevent>
        <el-form-item label="标签名称" required>
          <el-input v-model="form.name" placeholder="请输入标签名称" @keyup.enter="create" />
        </el-form-item>
        <el-form-item label="颜色">
          <el-color-picker v-model="form.color" />
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
import { tag_rows } from './settingsModel'

const DEFAULT_COLOR = '#409eff'

const catalog = useCatalogStore()
const is_mobile = use_is_mobile()
const tags = computed(() => catalog.tags)
const loading = ref(false)
const saving = ref(false)
const dialog_visible = ref(false)
const form = reactive({ name: '', color: DEFAULT_COLOR })
const rows = computed(() => tag_rows(tags.value, { remove }))

/** 读标签列表（store 里已有就直接用） */
async function load() {
  loading.value = true
  try {
    await catalog.loadTags()
  } catch (e) {
    console.error('获取标签失败:', e)
  } finally {
    loading.value = false
  }
}

/** 标签变了：让 store 失效再重新读 */
function reload_after_change() {
  catalog.invalidate('tags')
  load()
}

/** 新增标签 */
async function create() {
  if (!form.name.trim()) {
    ElMessage.warning('请输入标签名称')
    return
  }
  saving.value = true
  try {
    await questionApi.createTag(form.name.trim(), form.color)
    ElMessage.success('创建成功')
    dialog_visible.value = false
    form.name = ''
    form.color = DEFAULT_COLOR
    reload_after_change()
  } catch {
    ElMessage.error('创建失败')
  } finally {
    saving.value = false
  }
}

/** 删除标签（先确认） */
async function remove(row) {
  try {
    await ElMessageBox.confirm(`确定要删除标签“${row.name}”吗？`, '删除确认', { type: 'warning' })
    await questionApi.deleteTag(row.id)
    ElMessage.success('删除成功')
    reload_after_change()
  } catch (e) {
    if (e !== 'cancel') ElMessage.error('删除失败')
  }
}

onMounted(load)
</script>

<style scoped>
.set-bar { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 12px; }
</style>
