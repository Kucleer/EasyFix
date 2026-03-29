<template>
  <div class="practice-sets">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>练习集管理</span>
        </div>
      </template>

      <!-- 筛选条件 -->
      <div class="filters">
        <el-select v-model="filters.subject_id" placeholder="选择学科" clearable @change="fetchPracticeSets" style="width: 130px">
          <el-option v-for="s in subjects" :key="s.id" :label="s.name" :value="s.id" />
        </el-select>
        <el-select v-model="filters.reviewed" placeholder="复习状态" clearable @change="fetchPracticeSets" style="width: 120px">
          <el-option label="未复习" :value="false" />
          <el-option label="已复习" :value="true" />
        </el-select>
      </div>

      <!-- 批量操作栏 -->
      <div class="batch-actions">
        <el-checkbox v-model="checkAll" :indeterminate="isIndeterminate" @change="handleCheckAllChange">
          全选
        </el-checkbox>
        <span class="selected-count">已选择 {{ selectedIds.length }} 项</span>
        <el-button
          type="primary"
          size="small"
          :disabled="selectedIds.length === 0"
          @click="batchDownloadPdf"
        >
          批量下载PDF
        </el-button>
        <el-button
          type="danger"
          size="small"
          :disabled="selectedIds.length === 0"
          @click="batchDelete"
        >
          批量删除
        </el-button>
      </div>

      <!-- 练习集列表 -->
      <div v-if="practiceSets.length" class="practice-set-grid">
        <el-card v-for="ps in practiceSets" :key="ps.id" class="practice-set-card" shadow="hover">
          <template #header>
            <div class="card-header-inner">
              <el-checkbox
                :model-value="selectedIds.includes(ps.id)"
                @change="(val) => toggleSelect(ps.id, val)"
                style="margin-right: 8px"
              />
              <span class="ps-name">{{ ps.name }}</span>
              <el-tag :type="ps.question_type === 'original' ? 'primary' : 'success'" size="small">
                {{ ps.question_type === 'original' ? '原题' : '相似题' }}
              </el-tag>
            </div>
          </template>
          <div class="ps-content">
            <div class="ps-info">
              <p><strong>学科：</strong>{{ ps.subject_name || '未知' }}</p>
              <p><strong>题目数：</strong>{{ ps.total_questions }}</p>
              <p><strong>复习次数：</strong>{{ ps.review_count }}</p>
              <p><strong>创建时间：</strong>{{ formatDate(ps.created_at) }}</p>
              <p><strong>状态：</strong>
                <el-tag :type="ps.reviewed ? 'success' : 'info'" size="small">
                  {{ ps.reviewed ? '已复习' : '未复习' }}
                </el-tag>
              </p>
            </div>
            <div class="ps-actions">
              <el-button v-if="ps.pdf_path" type="primary" size="small" @click="downloadPdf(ps)">
                下载PDF
              </el-button>
              <el-button v-else type="info" size="small" disabled>无PDF</el-button>
              <el-button type="warning" size="small" @click="markReviewed(ps)" :disabled="ps.reviewed">
                标记已复习
              </el-button>
              <el-button type="danger" size="small" @click="deletePracticeSet(ps)">删除</el-button>
            </div>
          </div>
        </el-card>
      </div>

      <el-empty v-else description="暂无练习集" />

      <!-- 分页 -->
      <div v-if="total > 0" class="pagination">
        <el-pagination
          v-model:current-page="pagination.page"
          v-model:page-size="pagination.limit"
          :page-sizes="[20, 50, 100, 500]"
          :total="total"
          layout="total, sizes, prev, pager, next"
          @change="fetchPracticeSets"
        />
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { questionApi } from '@/api/question'

const practiceSets = ref([])
const subjects = ref([])
const total = ref(0)
const selectedIds = ref([])
const filters = reactive({
  subject_id: null,
  reviewed: null,
})
const pagination = reactive({
  page: 1,
  limit: 1000,
})

// 全选状态
const checkAll = computed({
  get: () => practiceSets.value.length > 0 && selectedIds.value.length === practiceSets.value.length,
  set: (val) => {
    if (val) {
      selectedIds.value = practiceSets.value.map(ps => ps.id)
    } else {
      selectedIds.value = []
    }
  }
})

// 是否半选
const isIndeterminate = computed(() => {
  return selectedIds.value.length > 0 && selectedIds.value.length < practiceSets.value.length
})

const fetchPracticeSets = async () => {
  try {
    const { data } = await questionApi.listPracticeSets({
      skip: (pagination.page - 1) * pagination.limit,
      limit: pagination.limit,
      ...filters,
    })
    practiceSets.value = data.items
    total.value = data.total
  } catch (error) {
    ElMessage.error('获取练习集列表失败')
  }
}

const fetchSubjects = async () => {
  try {
    const { data } = await questionApi.listSubjects()
    subjects.value = data
  } catch (error) {
    console.error('获取学科失败:', error)
  }
}

const toggleSelect = (id, checked) => {
  if (checked) {
    if (!selectedIds.value.includes(id)) {
      selectedIds.value.push(id)
    }
  } else {
    selectedIds.value = selectedIds.value.filter(i => i !== id)
  }
}

const handleCheckAllChange = (val) => {
  if (val) {
    selectedIds.value = practiceSets.value.map(ps => ps.id)
  } else {
    selectedIds.value = []
  }
}

const downloadPdf = (ps) => {
  if (ps.pdf_path) {
    window.open(`/uploads/${ps.pdf_path}`, '_blank')
  }
}

const markReviewed = async (ps) => {
  try {
    await ElMessageBox.confirm('确定要标记为已复习吗？', '确认', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'info',
    })
    await questionApi.markPracticeSetReviewed(ps.id)
    ElMessage.success('已标记为复习')
    fetchPracticeSets()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('操作失败')
    }
  }
}

const deletePracticeSet = async (ps) => {
  try {
    await ElMessageBox.confirm('确定要删除这个练习集吗？', '删除确认', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning',
    })
    await questionApi.deletePracticeSet(ps.id)
    ElMessage.success('删除成功')
    fetchPracticeSets()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('删除失败')
    }
  }
}

// 批量下载PDF
const batchDownloadPdf = async () => {
  if (selectedIds.value.length === 0) {
    ElMessage.warning('请先选择要下载的练习集')
    return
  }
  try {
    const { data } = await questionApi.batchDownloadPracticeSetsPdf(selectedIds.value)
    const results = data.results || []
    const successCount = results.filter(r => r.pdf_url).length

    if (successCount === 0) {
      ElMessage.warning('所选练习集都没有可下载的PDF')
      return
    }

    // 逐个打开PDF链接
    for (const result of results) {
      if (result.pdf_url) {
        window.open(result.pdf_url, '_blank')
      }
    }
    ElMessage.success(`已开始下载 ${successCount} 个PDF文件`)
  } catch (error) {
    ElMessage.error('批量下载失败')
  }
}

// 批量删除
const batchDelete = async () => {
  if (selectedIds.value.length === 0) {
    ElMessage.warning('请先选择要删除的练习集')
    return
  }
  try {
    await ElMessageBox.confirm(
      `确定要删除选中的 ${selectedIds.value.length} 个练习集吗？此操作不可恢复。`,
      '批量删除确认',
      {
        confirmButtonText: '确定删除',
        cancelButtonText: '取消',
        type: 'warning',
      }
    )
    await questionApi.batchDeletePracticeSets(selectedIds.value)
    ElMessage.success('批量删除成功')
    selectedIds.value = []
    fetchPracticeSets()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('批量删除失败')
    }
  }
}

const formatDate = (dateStr) => {
  if (!dateStr) return ''
  return new Date(dateStr).toLocaleString('zh-CN')
}

onMounted(() => {
  fetchPracticeSets()
  fetchSubjects()
})
</script>

<style scoped>
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.card-header-inner {
  display: flex;
  align-items: center;
}

.card-header-inner .ps-name {
  flex: 1;
  margin-right: 8px;
}

.ps-name {
  font-weight: bold;
  font-size: 14px;
}

.filters {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  margin-bottom: 20px;
}

.batch-actions {
  display: flex;
  align-items: center;
  gap: 15px;
  padding: 12px 15px;
  background-color: #f5f7fa;
  border-radius: 4px;
  margin-bottom: 20px;
}

.selected-count {
  color: #606266;
  font-size: 13px;
  margin-right: auto;
}

.practice-set-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 20px;
  margin-top: 20px;
}

.practice-set-card {
  margin-bottom: 0;
}

.ps-content {
  padding: 10px 0;
}

.ps-info {
  margin-bottom: 15px;
}

.ps-info p {
  margin: 5px 0;
  font-size: 13px;
  color: #606266;
}

.ps-actions {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}

.pagination {
  margin-top: 20px;
  display: flex;
  justify-content: flex-end;
}
</style>
