<template>
  <!--
    成就管理：预设成就只能看，自定义成就可以改、删。
    暂不放在设置页的标签栏里，等成就项目再放回来；组件本身完整可用。
  -->
  <div class="achievements-panel">
    <div class="set-bar">
      <el-button type="primary" @click="open_new"><el-icon><Plus /></el-icon>新增成就</el-button>
    </div>
    <MobileList v-if="is_mobile" :rows="rows" />
    <el-table v-else v-loading="loading" :data="achievements" stripe style="width: 100%">
      <el-table-column prop="id" label="ID" width="80" />
      <el-table-column prop="name" label="成就名称" width="120" />
      <el-table-column prop="level" label="等级" width="80" />
      <el-table-column prop="trigger_action" label="触发行为" width="150" />
      <el-table-column prop="trigger_count" label="触发次数" width="100" />
      <el-table-column prop="reward_stars" label="奖励积分" width="100" />
      <el-table-column prop="is_preset" label="类型" width="100">
        <template #default="{ row }"><el-tag :type="row.is_preset ? 'primary' : 'warning'">{{ row.is_preset ? '预设' : '自定义' }}</el-tag></template>
      </el-table-column>
      <el-table-column label="操作" width="160" fixed="right">
        <template #default="{ row }">
          <ListActions :primary="{ label: '编辑', run: () => open_edit(row), disabled: row.is_preset }" :actions="[{ label: '删除', run: () => remove(row), disabled: row.is_preset, danger: true }]" />
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="dialog_visible" :title="editing ? '编辑成就' : '新增成就'" :width="is_mobile ? '92%' : '500px'">
      <el-form :model="form" label-width="100px">
        <el-form-item label="成就名称" required>
          <el-input v-model="form.name" placeholder="如: 学习达人" />
        </el-form-item>
        <el-form-item label="等级" required>
          <el-input-number v-model="form.level" :min="1" :max="10" />
        </el-form-item>
        <el-form-item label="触发行为" required>
          <el-select v-model="form.trigger_action" placeholder="选择触发行为" style="width: 100%">
            <el-option v-for="a in star_actions" :key="a.code" :label="a.name" :value="a.code" />
          </el-select>
        </el-form-item>
        <el-form-item label="触发次数" required>
          <el-input-number v-model="form.trigger_count" :min="1" :max="9999" />
        </el-form-item>
        <el-form-item label="奖励积分" required>
          <el-input-number v-model="form.reward_stars" :min="0" :max="9999" />
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
import { achievement_rows } from './settingsModel'

const EMPTY_FORM = { name: '', level: 1, trigger_action: '', trigger_count: 1, reward_stars: 0 }

const is_mobile = use_is_mobile()
const achievements = ref([])
const star_actions = ref([])   // 触发行为的下拉选项
const loading = ref(false)
const dialog_visible = ref(false)
const editing = ref(null)
const form = reactive({ ...EMPTY_FORM })
const rows = computed(() => achievement_rows(achievements.value, { edit: open_edit, remove }))

/** 接口可能直接返回数组，也可能是 { items } */
const as_list = data => (Array.isArray(data) ? data : (data?.items || []))

/** 读成就列表 */
async function load() {
  loading.value = true
  try {
    const { data } = await motivationApi.getAchievements()
    achievements.value = as_list(data)
  } catch (e) {
    console.error('获取成就列表失败:', e)
  } finally {
    loading.value = false
  }
}

/** 读积分行为，作为"触发行为"的选项 */
async function load_actions() {
  try {
    const { data } = await motivationApi.getActions()
    star_actions.value = as_list(data)
  } catch (e) {
    console.error('获取行为列表失败:', e)
  }
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
    name: row.name, level: row.level, trigger_action: row.trigger_action,
    trigger_count: row.trigger_count, reward_stars: row.reward_stars,
  })
  dialog_visible.value = true
}

/** 新增或保存修改 */
async function save() {
  if (!form.name.trim()) return ElMessage.warning('请输入成就名称')
  if (!form.trigger_action) return ElMessage.warning('请选择触发行为')
  try {
    if (editing.value) {
      await motivationApi.updateAchievement(editing.value.id, { ...form })
      ElMessage.success('更新成功')
    } else {
      await motivationApi.createAchievement({ ...form })
      ElMessage.success('创建成功')
    }
    dialog_visible.value = false
    editing.value = null
    load()
  } catch {
    ElMessage.error('保存失败')
  }
}

/** 删除成就（预设成就不能删） */
async function remove(row) {
  try {
    await ElMessageBox.confirm('确定要删除该成就吗？', '删除确认', { type: 'warning' })
    await motivationApi.deleteAchievement(row.id)
    ElMessage.success('删除成功')
    load()
  } catch (e) {
    if (e !== 'cancel') ElMessage.error('删除失败')
  }
}

onMounted(() => {
  load()
  load_actions()
})
</script>

<style scoped>
.set-bar { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 12px; }
</style>
