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

      <!-- 练习集列表 -->
      <div v-if="practiceSets.length" class="practice-set-grid">
        <el-card v-for="ps in practiceSets" :key="ps.id" class="practice-set-card" shadow="hover">
          <template #header>
            <div class="card-header-inner">
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
          :page-sizes="[10, 20, 50]"
          :total="total"
          layout="total, sizes, prev, pager, next"
          @change="fetchPracticeSets"
        />
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { questionApi } from '@/api/question'

const practiceSets = ref([])
const subjects = ref([])
const total = ref(0)
const filters = reactive({
  subject_id: null,
  reviewed: null,
})
const pagination = reactive({
  page: 1,
  limit: 20,
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
  justify-content: space-between;
  align-items: center;
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
