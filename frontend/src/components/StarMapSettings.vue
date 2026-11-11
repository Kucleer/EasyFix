<template>
  <div class="starmap-settings">
    <div class="toolbar">
      <el-radio-group v-model="subjectId" @change="loadAll">
        <el-radio-button v-for="s in subjects" :key="s.id" :value="s.id">{{ s.name }}</el-radio-button>
      </el-radio-group>
      <template v-if="sections.length">
        <span class="label">现在学到</span>
        <el-select v-model="sectionNo" placeholder="选择一节" style="width: 260px" @change="saveProgress">
          <el-option v-for="s in sections" :key="s.section_no" :label="`${s.section_no} ${s.section_name}（${s.chapter_name}）`" :value="s.section_no" />
        </el-select>
      </template>
    </div>

    <el-table v-loading="loading" :data="rows" stripe style="width: 100%" max-height="520">
      <el-table-column prop="module" label="模块" width="180" />
      <el-table-column prop="name" label="考点" min-width="180" />
      <el-table-column label="掌握情况" min-width="200">
        <template #default="{ row }">
          <div class="mastery">
            <div class="bar"><i :style="{ width: Math.round((row.value ?? 0) * 100) + '%', background: 'rgb(' + colorOf(row.value) + ')' }"></i></div>
            <span>{{ statusText(row.status) }}</span>
          </div>
        </template>
      </el-table-column>
      <el-table-column label="调整" width="180">
        <template #default="{ row }">
          <el-dropdown trigger="click" @command="kind => adjust(row, kind)">
            <el-button size="small">调整 <el-icon class="el-icon--right"><ArrowDown /></el-icon></el-button>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item v-for="k in KINDS" :key="k.value" :command="k.value">{{ k.label }}</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </template>
      </el-table-column>
    </el-table>

    <h4 class="section-title">调整记录</h4>
    <el-table :data="adjustments" stripe style="width: 100%" empty-text="还没有手动调整">
      <el-table-column prop="point_name" label="考点" min-width="180" />
      <el-table-column label="调整" width="140"><template #default="{ row }">{{ kindLabel(row.kind) }}</template></el-table-column>
      <el-table-column prop="created_at" label="时间" width="200" />
      <el-table-column label="操作" width="100">
        <template #default="{ row }"><el-button link type="danger" @click="undo(row)">撤销</el-button></template>
      </el-table-column>
    </el-table>
  </div>
</template>

<script setup>
// 管理设置里的"知识星空"栏：学习进度、按考点手动调整掌握程度、调整记录与撤销
import { ref, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ArrowDown } from '@element-plus/icons-vue'
import { starmapApi, loadStarmapSubjects } from '@/api/starmap'
import { colorOf, statusText } from '@/components/starmap/starmapColors.js'

const KINDS = [
  { value: 'up_small', label: '提高一点' },
  { value: 'up_large', label: '提高很多' },
  { value: 'set_mastered', label: '直接设为掌握' },
  { value: 'down_small', label: '降低一点' },
]

const subjects = ref([])
const subjectId = ref(null)
const nodes = ref([])
const adjustments = ref([])
const sections = ref([])
const sectionNo = ref(null)
const loading = ref(false)

// 表格：模块行在前、它的考点跟在后面
const rows = computed(() => {
  const modules = nodes.value.filter(n => n.level === 1)
  const result = []
  for (const module of modules) {
    result.push({ ...module, module: module.name, name: '（整个模块）' })
    nodes.value.filter(n => n.parent_id === module.id).forEach(n => result.push({ ...n, module: module.name }))
  }
  return result
})

function kindLabel(kind) {
  return KINDS.find(k => k.value === kind)?.label || kind
}

function showError(error, fallback) {
  ElMessage.error(error.response?.data?.detail || fallback)
}

// 读取这一科的考点掌握情况、调整记录和学习进度
async function loadAll() {
  if (!subjectId.value) return
  loading.value = true
  try {
    const [map, list, progress] = await Promise.all([
      starmapApi.get(subjectId.value), starmapApi.adjustments(subjectId.value), starmapApi.progress(subjectId.value),
    ])
    nodes.value = map.data.nodes
    adjustments.value = list.data
    sections.value = progress.data.sections
    sectionNo.value = progress.data.section_no
  } catch (error) {
    showError(error, '加载失败，请稍后再试')
  } finally {
    loading.value = false
  }
}

async function adjust(row, kind) {
  try {
    await starmapApi.addAdjustment(row.id, kind)
    ElMessage.success('已调整')
    await loadAll()
  } catch (error) {
    showError(error, '调整失败，请稍后再试')
  }
}

async function undo(row) {
  try {
    await ElMessageBox.confirm(`撤销对"${row.point_name}"的"${kindLabel(row.kind)}"？`, '撤销调整', {
      type: 'warning', confirmButtonText: '撤销', cancelButtonText: '再想想',
    })
  } catch {
    return
  }
  try {
    await starmapApi.removeAdjustment(row.id)
    ElMessage.success('已撤销')
    await loadAll()
  } catch (error) {
    showError(error, '撤销失败，请稍后再试')
  }
}

async function saveProgress(value) {
  try {
    await starmapApi.saveProgress(subjectId.value, value)
    ElMessage.success('已保存')
    await loadAll()
  } catch (error) {
    showError(error, '保存失败，请稍后再试')
  }
}

onMounted(async () => {
  try {
    subjects.value = await loadStarmapSubjects()
  } catch (error) {
    showError(error, '加载失败，请稍后再试')
    return
  }
  subjectId.value = subjects.value[0]?.id ?? null
  loadAll()
})
</script>

<style scoped>
.toolbar { display: flex; align-items: center; gap: 14px; margin-bottom: 14px; flex-wrap: wrap; }
.label { color: var(--text-muted); font-size: 13px; }
.mastery { display: flex; align-items: center; gap: 10px; }
.mastery .bar { flex: 1; height: 6px; border-radius: 3px; background: #eef0f5; overflow: hidden; }
.mastery .bar i { display: block; height: 100%; }
.mastery span { width: 48px; font-size: 13px; color: var(--text-secondary); }
.section-title { margin: 22px 0 10px; font-size: 14px; }
</style>
