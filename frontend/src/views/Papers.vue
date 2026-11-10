<template>
  <div class="papers-page">
    <PageHeading title="卷子和作业" description="每份卷子或作业一条记录，错题和考试分数都挂在它下面">
      <el-button type="primary" @click="createVisible = true">新增记录</el-button>
    </PageHeading>

    <el-card shadow="never">
      <div class="filters">
        <el-select v-model="filters.subject_id" placeholder="全部学科" clearable class="filter-item" @change="onFilterChange">
          <el-option v-for="s in subjects" :key="s.id" :label="s.name" :value="s.id" />
        </el-select>
        <el-select v-model="filters.paper_type" placeholder="全部类型" clearable class="filter-item" @change="onFilterChange">
          <el-option v-for="(label, value) in PAPER_TYPE_LABELS" :key="value" :label="label" :value="value" />
        </el-select>
      </div>

      <el-table v-loading="loading" :data="papers" stripe style="width: 100%" empty-text="还没有记录">
        <el-table-column label="名称" min-width="200">
          <template #default="{ row }">
            <router-link :to="'/papers/' + row.id" class="paper-link">{{ row.name }}</router-link>
            <div class="sub-line">{{ row.subject_name }}</div>
            <!-- 小屏幕上隐藏了类型、日期、分数列，在这里补一行 -->
            <div class="sub-line mobile-only">{{ [paperTypeLabel(row), row.paper_date, scoreText(row)].filter(Boolean).join(' · ') }}</div>
          </template>
        </el-table-column>
        <el-table-column label="类型" width="130" class-name="col-secondary">
          <template #default="{ row }">{{ paperTypeLabel(row) }}</template>
        </el-table-column>
        <el-table-column prop="paper_date" label="日期" width="120" class-name="col-secondary" />
        <el-table-column label="年级学期" width="130" class-name="col-secondary">
          <template #default="{ row }">{{ gradeSemesterText(row) }}</template>
        </el-table-column>
        <el-table-column label="分数" width="110" class-name="col-secondary">
          <template #default="{ row }">{{ scoreText(row) }}</template>
        </el-table-column>
        <el-table-column label="题目数" width="90">
          <template #default="{ row }">{{ row.question_count }}</template>
        </el-table-column>
        <el-table-column label="待核对" width="90">
          <template #default="{ row }">
            <el-tag v-if="row.pending_count > 0" type="warning" size="small">{{ row.pending_count }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="备注" min-width="160" class-name="col-secondary">
          <template #default="{ row }"><span class="notes-text">{{ row.notes }}</span></template>
        </el-table-column>
      </el-table>

      <div class="pagination">
        <el-pagination
          v-model:current-page="pagination.page"
          v-model:page-size="pagination.limit"
          :page-sizes="[10, 20, 50]"
          :total="total"
          layout="total, sizes, prev, pager, next"
          @current-change="fetchPapers"
          @size-change="onFilterChange"
        />
      </div>
    </el-card>

    <PaperFormDialog v-model="createVisible" :subjects="subjects" :default-subject-id="filters.subject_id" @saved="onCreated" />
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import PageHeading from '@/components/PageHeading.vue'
import PaperFormDialog from '@/components/PaperFormDialog.vue'
import { paperApi } from '@/api/paper'
import { questionApi } from '@/api/question'
import { PAPER_TYPE_LABELS, paperTypeLabel, scoreText } from '@/composables/intakeLabels'

const loading = ref(false)
const papers = ref([])
const total = ref(0)
const subjects = ref([])
const createVisible = ref(false)
const filters = reactive({ subject_id: null, paper_type: null })
const pagination = reactive({ page: 1, limit: 20 })

// 年级学期的显示文字，都没填返回空串
function gradeSemesterText(paper) {
  const grades = ['', '一年级', '二年级', '三年级', '四年级', '五年级', '六年级', '初一', '初二', '初三', '高一', '高二', '高三']
  const grade = paper.grade ? grades[paper.grade] || '' : ''
  const semester = paper.semester === 1 ? '上学期' : paper.semester === 2 ? '下学期' : ''
  return [grade, semester].filter(Boolean).join(' ')
}

// 加载学科，供筛选和新增使用
async function fetchSubjects() {
  try {
    const { data } = await questionApi.listSubjects()
    subjects.value = data
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '加载学科失败')
  }
}

// 按筛选和分页加载卷子列表
async function fetchPapers() {
  loading.value = true
  try {
    const params = { skip: (pagination.page - 1) * pagination.limit, limit: pagination.limit }
    if (filters.subject_id) params.subject_id = filters.subject_id
    if (filters.paper_type) params.paper_type = filters.paper_type
    const { data } = await paperApi.list(params)
    papers.value = data.items || []
    total.value = data.total || 0
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '加载卷子列表失败')
  } finally {
    loading.value = false
  }
}

// 筛选或每页条数变了，回到第一页重新加载
function onFilterChange() {
  pagination.page = 1
  fetchPapers()
}

// 新增成功后回到第一页看最新的记录
function onCreated() {
  pagination.page = 1
  fetchPapers()
}

onMounted(() => {
  fetchSubjects()
  fetchPapers()
})
</script>

<style scoped>
.filters { display: flex; gap: 12px; flex-wrap: wrap; margin-bottom: 14px; }
.filter-item { width: 160px; }
.paper-link { color: var(--accent-blue); font-weight: 600; text-decoration: none; }
.paper-link:hover { text-decoration: underline; }
.sub-line { font-size: 12px; color: var(--text-muted); margin-top: 2px; }
.mobile-only { display: none; }
.notes-text { color: var(--text-secondary); font-size: 13px; }
.pagination { display: flex; justify-content: flex-end; margin-top: 16px; }

@media (max-width: 768px) {
  /* 小屏幕隐藏类型、日期、年级学期、分数、备注，名称列占满 */
  .papers-page :deep(.col-secondary) { display: none; }
  .mobile-only { display: block; }
  .filter-item { width: calc(50% - 6px); }
  .pagination { justify-content: center; }
}
</style>
