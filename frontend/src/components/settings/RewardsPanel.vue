<template>
  <!--
    奖励管理：所需积分、库存（-1 表示无限）、奖励图片。
    暂不放在设置页的标签栏里，等成就项目再放回来；组件本身完整可用。
  -->
  <div class="rewards-panel">
    <div class="set-bar">
      <el-button type="primary" @click="open_new"><el-icon><Plus /></el-icon>新增奖励</el-button>
    </div>
    <MobileList v-if="is_mobile" :rows="rows" />
    <el-table v-else v-loading="loading" :data="rewards" stripe style="width: 100%">
      <el-table-column prop="id" label="ID" width="80" />
      <el-table-column prop="name" label="奖励名称" width="150" />
      <el-table-column prop="cost_stars" label="所需积分" width="100" />
      <el-table-column prop="total_stock" label="总库存" width="100">
        <template #default="{ row }">{{ format_stock(row.total_stock) }}</template>
      </el-table-column>
      <el-table-column prop="remaining_stock" label="剩余库存" width="100">
        <template #default="{ row }">{{ format_stock(row.remaining_stock) }}</template>
      </el-table-column>
      <el-table-column label="操作" width="160" fixed="right">
        <template #default="{ row }">
          <ListActions :primary="{ label: '编辑', run: () => open_edit(row) }" :actions="[{ label: '删除', run: () => remove(row), danger: true }]" />
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="dialog_visible" :title="editing ? '编辑奖励' : '新增奖励'" :width="is_mobile ? '92%' : '500px'">
      <el-form :model="form" label-width="100px">
        <el-form-item label="奖励名称" required>
          <el-input v-model="form.name" placeholder="如: 免作业卡" />
        </el-form-item>
        <el-form-item label="奖励描述">
          <el-input v-model="form.description" type="textarea" :rows="2" placeholder="描述奖励的用途或详情" />
        </el-form-item>
        <el-form-item label="所需积分" required>
          <el-input-number v-model="form.cost_stars" :min="0" :max="99999" />
        </el-form-item>
        <el-form-item label="总库存">
          <el-input-number v-model="form.total_stock" :min="-1" :max="99999" placeholder="-1表示无限" />
        </el-form-item>
        <el-form-item label="剩余库存">
          <el-input-number v-model="form.remaining_stock" :min="-1" :max="99999" placeholder="-1表示无限" />
        </el-form-item>
        <el-form-item label="奖励图片">
          <div v-if="form.image_url" class="image-preview">
            <img :src="form.image_url" alt="奖励图片" />
            <el-button type="danger" size="small" @click="form.image_url = ''">删除图片</el-button>
          </div>
          <el-upload v-else :auto-upload="false" :limit="1" accept="image/*" :on-change="upload_image">
            <el-button size="small" type="primary">点击上传图片</el-button>
          </el-upload>
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
import { uploadApi } from '@/api/upload'
import { use_is_mobile } from '@/composables/useIsMobile'
import MobileList from './MobileList.vue'
import { reward_rows, format_stock } from './settingsModel'

const EMPTY_FORM = { name: '', description: '', cost_stars: 0, total_stock: -1, remaining_stock: -1, image_url: '' }

const is_mobile = use_is_mobile()
const rewards = ref([])
const loading = ref(false)
const dialog_visible = ref(false)
const editing = ref(null)
const form = reactive({ ...EMPTY_FORM })
const rows = computed(() => reward_rows(rewards.value, { edit: open_edit, remove }))

/** 读奖励列表 */
async function load() {
  loading.value = true
  try {
    const { data } = await motivationApi.getRewards()
    rewards.value = Array.isArray(data) ? data : (data.items || [])
  } catch (e) {
    console.error('获取奖励列表失败:', e)
  } finally {
    loading.value = false
  }
}

/** 选好图片后立即上传，地址存成 /uploads/ 开头 */
async function upload_image(file) {
  try {
    const { data } = await uploadApi.uploadFile(file.raw)
    form.image_url = '/uploads/' + data.path
    ElMessage.success('图片上传成功')
  } catch (e) {
    console.error('上传失败:', e)
    ElMessage.error('图片上传失败')
  }
  return false
}

/** 打开新增弹窗 */
function open_new() {
  editing.value = null
  Object.assign(form, EMPTY_FORM)
  dialog_visible.value = true
}

/** 打开编辑弹窗 */
function open_edit(row) {
  editing.value = row
  Object.assign(form, {
    name: row.name, description: row.description || '', cost_stars: row.cost_stars,
    total_stock: row.total_stock, remaining_stock: row.remaining_stock, image_url: row.image_url || '',
  })
  dialog_visible.value = true
}

/** 新增或保存修改 */
async function save() {
  if (!form.name.trim()) return ElMessage.warning('请输入奖励名称')
  try {
    if (editing.value) {
      await motivationApi.updateReward(editing.value.id, { ...form })
      ElMessage.success('更新成功')
    } else {
      await motivationApi.createReward({ ...form })
      ElMessage.success('创建成功')
    }
    dialog_visible.value = false
    editing.value = null
    load()
  } catch {
    ElMessage.error('保存失败')
  }
}

/** 删除奖励（先确认） */
async function remove(row) {
  try {
    await ElMessageBox.confirm('确定要删除该奖励吗？', '删除确认', { type: 'warning' })
    await motivationApi.deleteReward(row.id)
    ElMessage.success('删除成功')
    load()
  } catch (e) {
    if (e !== 'cancel') ElMessage.error('删除失败')
  }
}

onMounted(load)
</script>

<style scoped>
.set-bar { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 12px; }
.image-preview { display: flex; flex-direction: column; align-items: flex-start; gap: 8px; }
.image-preview img { width: 100px; height: 100px; object-fit: contain; border: 1px solid var(--line); border-radius: 8px; }
</style>
