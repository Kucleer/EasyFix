<template>
  <!-- 设置 · 知识点：两级目录（一级模块、二级考点）+ 待处理旧目录 -->
  <div class="knowledge-tab">
    <el-alert
      type="info"
      :closable="false"
      show-icon
      class="kp-tip"
      title="两级目录：一级是知识模块，二级是具体考点。删除有子级或有题目引用的节点会被拒绝；有引用的节点也不能改学科或移动。"
    />
    <!-- 知识点目录全站共用，只有管理员看得到新增、编辑、删除 -->
    <div v-if="editable" class="set-bar">
      <el-button type="primary" @click="dialog_ref.open_new(1)"><el-icon><Plus /></el-icon>新增一级模块</el-button>
      <el-button @click="dialog_ref.open_new(2)"><el-icon><Plus /></el-icon>新增二级考点</el-button>
      <el-button v-if="legacy.length" plain type="warning" @click="show_legacy = !show_legacy">
        待处理旧目录 {{ legacy.length }}
      </el-button>
    </div>
    <div class="filters">
      <el-select v-model="filters.subject_id" placeholder="选择学科" clearable @change="fetch_points">
        <el-option v-for="s in subjects" :key="s.id" :label="s.name" :value="s.id" />
      </el-select>
      <el-select v-model="filters.grade" placeholder="年级" clearable @change="fetch_points">
        <el-option v-for="g in GRADE_OPTIONS" :key="g.value" :label="g.label" :value="g.value" />
      </el-select>
      <el-select v-model="filters.semester" placeholder="学期" clearable @change="fetch_points">
        <el-option v-for="s in SEMESTER_OPTIONS" :key="s.value" :label="s.label" :value="s.value" />
      </el-select>
      <el-input v-model="filters.keyword" placeholder="搜索名称" clearable @change="fetch_points" />
    </div>

    <MobileList v-if="is_mobile" :rows="tree_rows" empty-text="暂无目录数据" />
    <el-table
      v-else
      v-loading="loading"
      :data="tree"
      row-key="id"
      :tree-props="{ children: 'children' }"
      default-expand-all
      stripe
      style="width: 100%"
      empty-text="暂无目录数据"
    >
      <el-table-column label="知识点" min-width="230">
        <template #default="{ row }">
          <KnowledgeTag :point="row" :subject-id="row.subject_id" :show-path="row.level === 2" />
          <el-tag size="small" :type="row.level === 1 ? 'primary' : 'info'">{{ row.level === 1 ? '一级' : '二级' }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="code" label="编码" width="170" />
      <el-table-column prop="subject_name" label="学科" width="90" />
      <el-table-column label="题数" width="80" align="right">
        <template #default="{ row }">{{ row.question_count || 0 }}</template>
      </el-table-column>
      <el-table-column label="子级" min-width="120">
        <template #default="{ row }">
          <span v-if="row.level === 1">子级 {{ row.child_count || 0 }} 个</span>
          <span v-else class="text-muted">—</span>
        </template>
      </el-table-column>
      <el-table-column prop="sort_order" label="排序" width="70" align="right" />
      <el-table-column v-if="editable" label="操作" width="190" fixed="right">
        <template #default="{ row }">
          <ListActions
            :primary="{ label: '编辑', run: () => dialog_ref.open_edit(row) }"
            :actions="[
              ...(row.level === 1 ? [{ label: '新增二级', run: () => dialog_ref.open_new(2, row) }] : []),
              { label: '删除', run: () => remove(row), danger: true },
            ]"
          />
        </template>
      </el-table-column>
    </el-table>

    <div v-if="show_legacy" class="legacy-panel">
      <h4>待处理旧目录（level 为空，不参与新树与新统计）</h4>
      <MobileList v-if="is_mobile" :rows="legacy_list_rows" empty-text="没有待处理旧目录" />
      <el-table v-else :data="legacy" size="small" empty-text="没有待处理旧目录">
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="name" label="原名称" />
        <el-table-column prop="subject_name" label="学科" width="100" />
        <el-table-column label="题数" width="80" align="right">
          <template #default="{ row }">{{ row.question_count || 0 }}</template>
        </el-table-column>
        <el-table-column label="操作" width="160">
          <template #default="{ row }">
            <el-button link type="primary" @click="dialog_ref.open_edit(row)">转为二级</el-button>
            <el-button link type="danger" :disabled="row.question_count > 0" @click="remove(row)">软删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <KnowledgeDialog
      ref="dialog_ref"
      :tree="tree"
      :subjects="subjects"
      :filter-subject-id="filters.subject_id"
      @saved="fetch_points"
    />
  </div>
</template>

<script setup>
import { computed, reactive, ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { questionApi } from '@/api/question'
import { useCatalogStore } from '@/stores/catalog'
import { useAppConfigStore } from '@/stores/appConfig'
import { refreshKnowledgeColors } from '@/composables/knowledgeColors'
import { use_is_mobile } from '@/composables/useIsMobile'
import MobileList from './MobileList.vue'
import KnowledgeDialog from './KnowledgeDialog.vue'
import { GRADE_OPTIONS, SEMESTER_OPTIONS, can_edit_shared, knowledge_query, pick_legacy, knowledge_rows, legacy_rows } from './settingsModel'
import { useAccountStore } from '@/stores/account'

const catalog = useCatalogStore()
const appConfigStore = useAppConfigStore()
const is_mobile = use_is_mobile()

const subjects = computed(() => catalog.subjects)
const tree = ref([])          // 两级目录（一级在外层，二级在 children）
const legacy = ref([])        // 待处理旧目录（level 为空）
const show_legacy = ref(false)
const loading = ref(false)
const dialog_ref = ref(null)
const filters = reactive({ subject_id: null, grade: null, semester: null, keyword: '' })

const accountStore = useAccountStore()
const editable = computed(() => can_edit_shared(accountStore.isAdmin))

// 手机紧凑列表的行：操作和表格里的按钮一一对应；不是管理员时不给操作
const tree_rows = computed(() => knowledge_rows(tree.value, {
  edit: row => dialog_ref.value.open_edit(row),
  add_child: row => dialog_ref.value.open_new(2, row),
  remove,
}).map(row => (editable.value ? row : { ...row, actions: [] })))
const legacy_list_rows = computed(() => legacy_rows(legacy.value, {
  promote: row => dialog_ref.value.open_edit(row),
  remove,
}))

/**
 * 按筛选读两级目录，同时读一次平铺列表挑出旧目录。
 * 年级、学期、关键词筛选是这一页独有的，所以直接请求接口，不走目录 store。
 */
async function fetch_points() {
  loading.value = true
  try {
    const [tree_res, flat_res] = await Promise.all([
      questionApi.getKnowledgePointTree(knowledge_query(filters)),
      questionApi.listKnowledgePoints({
        include_legacy: 1,
        ...(filters.subject_id ? { subject_id: filters.subject_id } : {}),
      }),
    ])
    tree.value = tree_res.data.items || []
    legacy.value = pick_legacy(flat_res.data)
  } catch (e) {
    console.error('获取知识点失败:', e)
  } finally {
    loading.value = false
  }
}

/** 删除知识点；有子级或题目引用时后端返回 409 和原因 */
async function remove(row) {
  try {
    await ElMessageBox.confirm(`确定要删除“${row.name}”吗？有子级或题目引用时会被拒绝。`, '删除确认', { type: 'warning' })
    await questionApi.deleteKnowledgePoint(row.id)
    ElMessage.success('删除成功')
    await refreshKnowledgeColors()
    fetch_points()
  } catch (e) {
    if (e !== 'cancel') ElMessage.error(e.response?.data?.detail || '删除失败')
  }
}

onMounted(async () => {
  // 筛选默认用设置里的年级、学期
  await appConfigStore.load()
  filters.grade = appConfigStore.defaultGrade
  filters.semester = appConfigStore.defaultSemester
  catalog.loadSubjects().catch(e => console.error('获取学科失败:', e))
  fetch_points()
})
</script>

<style scoped>
.kp-tip { margin-bottom: 12px; }
.set-bar { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 12px; }
.set-bar :deep(.el-button + .el-button) { margin-left: 0; }
.filters { display: flex; flex-wrap: wrap; gap: 10px; margin-bottom: 14px; }
.filters > :nth-child(1) { width: 150px; }
.filters > :nth-child(2) { width: 120px; }
.filters > :nth-child(3) { width: 110px; }
.filters > :nth-child(4) { width: 180px; }
.text-muted { color: var(--muted); }
.legacy-panel { margin-top: 20px; padding-top: 14px; border-top: 1px dashed var(--line); }
.legacy-panel h4 { margin: 0 0 10px; color: var(--ink-2); }

@media (max-width: 768px) {
  /* 筛选两列排开 */
  .filters { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; }
  .filters > * { width: 100% !important; }
}
</style>
