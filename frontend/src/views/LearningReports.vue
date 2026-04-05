<template>
  <div class="learning-reports">
    <el-row :gutter="20">
      <el-col :span="24">
        <el-card>
          <template #header>
            <div class="card-header">
              <span>学习状态分析</span>
              <el-button type="primary" @click="showGenerateDialog">
                <el-icon><Plus /></el-icon>
                生成新报告
              </el-button>
            </div>
          </template>

          <!-- 筛选条件 -->
          <div class="filters">
            <el-select v-model="filters.subject_id" placeholder="学科" clearable @change="fetchReports" style="width: 150px">
              <el-option v-for="s in subjects" :key="s.id" :label="s.name" :value="s.id" />
            </el-select>
          </div>

          <!-- 报告列表 -->
          <el-table :data="reports.items" stripe style="width: 100%; margin-top: 20px">
            <el-table-column prop="title" label="报告标题" min-width="200" />
            <el-table-column prop="subject_name" label="学科" width="100">
              <template #default="{ row }">
                {{ row.subject_name || '全科' }}
              </template>
            </el-table-column>
            <el-table-column prop="grade" label="年级" width="80">
              <template #default="{ row }">
                {{ row.grade ? formatGrade(row.grade) : '全部' }}
              </template>
            </el-table-column>
            <el-table-column prop="total_questions" label="错题数" width="80" />
            <el-table-column prop="total_words" label="单词数" width="80" />
            <el-table-column prop="overall_accuracy" label="准确率" width="80">
              <template #default="{ row }">
                <span :style="{ color: getAccuracyColor(row.overall_accuracy) }">
                  {{ row.overall_accuracy }}%
                </span>
              </template>
            </el-table-column>
            <el-table-column prop="created_at" label="生成时间" width="160">
              <template #default="{ row }">
                {{ formatDate(row.created_at) }}
              </template>
            </el-table-column>
            <el-table-column label="操作" width="200" fixed="right">
              <template #default="{ row }">
                <el-button type="primary" size="default" @click="viewReport(row)">查看</el-button>
                <el-button type="danger" size="default" @click="deleteReport(row)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>

          <!-- 分页 -->
          <div class="pagination">
            <el-pagination
              v-model:current-page="pagination.page"
              v-model:page-size="pagination.limit"
              :page-sizes="[10, 20, 50]"
              :total="reports.total"
              layout="total, sizes, prev, pager, next"
              @change="fetchReports"
            />
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 生成报告弹窗 -->
    <el-dialog v-model="generateDialogVisible" title="生成学习分析报告" width="500px">
      <el-form :model="generateForm" label-width="100px">
        <el-form-item label="报告标题">
          <el-input v-model="generateForm.title" placeholder="不填则自动生成" clearable />
        </el-form-item>
        <el-form-item label="学科">
          <el-select v-model="generateForm.subject_id" placeholder="选择学科（可选）" clearable style="width: 100%">
            <el-option v-for="s in subjects" :key="s.id" :label="s.name" :value="s.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="年级">
          <el-select v-model="generateForm.grade" placeholder="选择年级（可选）" clearable style="width: 100%">
            <el-option v-for="g in gradeOptions" :key="g.value" :label="g.label" :value="g.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="时间范围">
          <el-select v-model="generateForm.time_range_days" placeholder="选择时间范围（可选）" clearable style="width: 100%">
            <el-option label="最近7天" :value="7" />
            <el-option label="最近30天" :value="30" />
            <el-option label="最近90天" :value="90" />
            <el-option label="最近365天" :value="365" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="generateDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="generateReport" :loading="generating">生成报告</el-button>
      </template>
    </el-dialog>

    <!-- 报告详情弹窗 -->
    <el-dialog v-model="detailDialogVisible" title="报告详情" width="900px" class="report-detail-dialog">
      <div v-if="currentReport" class="report-content">
        <div class="report-header">
          <h2>{{ currentReport.title }}</h2>
          <div class="report-meta">
            <el-tag v-if="currentReport.subject_name">{{ currentReport.subject_name }}</el-tag>
            <el-tag v-else type="info">全科</el-tag>
            <el-tag v-if="currentReport.grade">{{ formatGrade(currentReport.grade) }}</el-tag>
            <span class="accuracy">整体准确率: <strong>{{ currentReport.overall_accuracy }}%</strong></span>
          </div>
        </div>

        <!-- 整体概况 -->
        <div v-if="currentReport.content?.overview" class="report-section">
          <h3>整体概况</h3>
          <el-row :gutter="20">
            <el-col :span="8">
              <div class="stat-card">
                <div class="stat-value">{{ currentReport.content.overview.total_questions }}</div>
                <div class="stat-label">错题总数</div>
              </div>
            </el-col>
            <el-col :span="8">
              <div class="stat-card">
                <div class="stat-value">{{ currentReport.content.overview.total_words }}</div>
                <div class="stat-label">单词总数</div>
              </div>
            </el-col>
            <el-col :span="8">
              <div class="stat-card">
                <div class="stat-value" :style="{ color: getAccuracyColor(currentReport.content.overview.overall_accuracy) }">
                  {{ currentReport.content.overview.overall_accuracy }}%
                </div>
                <div class="stat-label">整体准确率</div>
              </div>
            </el-col>
          </el-row>
        </div>

        <!-- 错题分析 -->
        <div v-if="currentReport.content?.question_analysis" class="report-section">
          <h3>错题分析</h3>

          <div class="subsection">
            <h4>难度分布</h4>
            <div class="distribution-bars">
              <div v-for="(count, level) in currentReport.content.question_analysis.difficulty_distribution" :key="level" class="bar-item">
                <span class="bar-label">难度 {{ level }}</span>
                <div class="bar-wrapper">
                  <div class="bar" :style="{ width: getPercentage(count, currentReport.total_questions) + '%', backgroundColor: getDifficultyColor(level) }"></div>
                </div>
                <span class="bar-value">{{ count }}</span>
              </div>
            </div>
          </div>

          <div class="subsection">
            <h4>错误类型分布</h4>
            <div class="distribution-bars">
              <div v-for="(count, type) in currentReport.content.question_analysis.error_type_distribution" :key="type" class="bar-item">
                <span class="bar-label">{{ type }}</span>
                <div class="bar-wrapper">
                  <div class="bar" :style="{ width: getPercentage(count, currentReport.total_questions) + '%', backgroundColor: '#409eff' }"></div>
                </div>
                <span class="bar-value">{{ count }}</span>
              </div>
            </div>
          </div>

          <div v-if="currentReport.content.question_analysis.top_error_knowledge_points?.length" class="subsection">
            <h4>高频出错知识点 TOP10</h4>
            <el-table :data="currentReport.content.question_analysis.top_error_knowledge_points">
              <el-table-column prop="point" label="知识点" />
              <el-table-column prop="count" label="错误次数" width="100" />
            </el-table>
          </div>

          <div class="subsection">
            <h4>复习效果</h4>
            <el-row :gutter="20">
              <el-col :span="6">
                <div class="mini-stat">
                  <div class="value">{{ currentReport.content.question_analysis.review_effectiveness?.not_reviewed || 0 }}</div>
                  <div class="label">未复习</div>
                </div>
              </el-col>
              <el-col :span="6">
                <div class="mini-stat">
                  <div class="value">{{ currentReport.content.question_analysis.review_effectiveness?.reviewed_1 || 0 }}</div>
                  <div class="label">复习1次</div>
                </div>
              </el-col>
              <el-col :span="6">
                <div class="mini-stat">
                  <div class="value">{{ currentReport.content.question_analysis.review_effectiveness?.reviewed_multiple || 0 }}</div>
                  <div class="label">复习多次</div>
                </div>
              </el-col>
            </el-row>
          </div>
        </div>

        <!-- 单词分析 -->
        <div v-if="currentReport.content?.word_analysis" class="report-section">
          <h3>单词分析</h3>
          <div class="subsection">
            <div class="mastery-rate">
              <span class="label">总体掌握率：</span>
              <span class="value" :style="{ color: getAccuracyColor(currentReport.content.word_analysis.mastery_rate) }">
                {{ currentReport.content.word_analysis.mastery_rate }}%
              </span>
            </div>
          </div>

          <div v-if="currentReport.content.word_analysis.low_accuracy_words?.length" class="subsection">
            <h4>低准确率单词</h4>
            <div class="word-list">
              <el-tag v-for="w in currentReport.content.word_analysis.low_accuracy_words" :key="w.word" type="warning" style="margin: 5px">
                {{ w.word }} ({{ w.accuracy }}%)
              </el-tag>
            </div>
          </div>

          <div v-if="currentReport.content.word_analysis.recommended_review_interval" class="subsection">
            <el-alert type="info" :closable="false">
              {{ currentReport.content.word_analysis.recommended_review_interval }}
            </el-alert>
          </div>
        </div>

        <!-- 学习建议 -->
        <div v-if="currentReport.content?.suggestions?.length" class="report-section">
          <h3>学习建议</h3>
          <el-card v-for="(s, idx) in currentReport.content.suggestions" :key="idx" class="suggestion-card">
            <el-tag :type="getSuggestionType(s.type)" style="margin-right: 10px">{{ s.type }}</el-tag>
            {{ s.content }}
          </el-card>
        </div>

        <!-- 总结 -->
        <div v-if="currentReport.content?.summary" class="report-section">
          <h3>总结</h3>
          <div class="summary-box">
            <h4>核心发现</h4>
            <ul>
              <li v-for="(f, idx) in currentReport.content.summary.key_findings" :key="idx">{{ f }}</li>
            </ul>
            <h4>优先改进项</h4>
            <ul>
              <li v-for="(p, idx) in currentReport.content.summary.priority_improvements" :key="idx">{{ p }}</li>
            </ul>
          </div>
        </div>
      </div>
      <template #footer>
        <el-button @click="detailDialogVisible = false">关闭</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import { learningReportApi } from '@/api/learning_report'
import { questionApi } from '@/api/question'

const reports = ref({ total: 0, items: [] })
const subjects = ref([])
const filters = reactive({
  subject_id: null,
})
const pagination = reactive({
  page: 1,
  limit: 20,
})

const generateDialogVisible = ref(false)
const generateForm = reactive({
  title: '',
  subject_id: null,
  grade: null,
  time_range_days: null,
})
const generating = ref(false)

const detailDialogVisible = ref(false)
const currentReport = ref(null)

const gradeOptions = [
  { label: '一年级', value: 1 },
  { label: '二年级', value: 2 },
  { label: '三年级', value: 3 },
  { label: '四年级', value: 4 },
  { label: '五年级', value: 5 },
  { label: '六年级', value: 6 },
  { label: '初一', value: 7 },
  { label: '初二', value: 8 },
  { label: '初三', value: 9 },
  { label: '高一', value: 10 },
  { label: '高二', value: 11 },
  { label: '高三', value: 12 },
]

const formatGrade = (grade) => {
  const map = { 1: '一年级', 2: '二年级', 3: '三年级', 4: '四年级', 5: '五年级', 6: '六年级', 7: '初一', 8: '初二', 9: '初三', 10: '高一', 11: '高二', 12: '高三' }
  return map[grade] || `${grade}年级`
}

const formatDate = (dateStr) => {
  const d = new Date(dateStr)
  return d.toLocaleString('zh-CN')
}

const getAccuracyColor = (accuracy) => {
  if (accuracy >= 80) return '#67c23a'
  if (accuracy >= 60) return '#e6a23c'
  return '#f56c6c'
}

const getDifficultyColor = (level) => {
  const colors = { '1': '#67c23a', '2': '#85ce61', '3': '#e6a23c', '4': '#f56c6c', '5': '#f78989' }
  return colors[level] || '#409eff'
}

const getPercentage = (count, total) => {
  if (!total) return 0
  return Math.round((count / total) * 100)
}

const getSuggestionType = (type) => {
  const map = { '练习': 'primary', '记忆': 'success', '复习': 'warning', '策略': 'info' }
  return map[type] || 'info'
}

const fetchReports = async () => {
  try {
    const params = {
      skip: (pagination.page - 1) * pagination.limit,
      limit: pagination.limit,
    }
    if (filters.subject_id) params.subject_id = filters.subject_id

    const { data } = await learningReportApi.list(params)
    reports.value = data
  } catch (error) {
    ElMessage.error('获取报告列表失败')
  }
}

const fetchSubjects = async () => {
  try {
    const { data } = await questionApi.listSubjects()
    subjects.value = data
  } catch (error) {
    console.error('获取学科列表失败:', error)
  }
}

const showGenerateDialog = () => {
  generateForm.title = ''
  generateForm.subject_id = null
  generateForm.grade = null
  generateForm.time_range_days = null
  generateDialogVisible.value = true
}

const generateReport = async () => {
  generating.value = true
  try {
    const data = {}
    if (generateForm.title) data.title = generateForm.title
    if (generateForm.subject_id) data.subject_id = generateForm.subject_id
    if (generateForm.grade) data.grade = generateForm.grade
    if (generateForm.time_range_days) data.time_range_days = generateForm.time_range_days

    const { data: result } = await learningReportApi.generate(data)
    ElMessage.success(result.message)
    generateDialogVisible.value = false
    fetchReports()

    // 自动打开新生成的报告
    viewReport({ id: result.id })
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '生成报告失败')
  } finally {
    generating.value = false
  }
}

const viewReport = async (row) => {
  try {
    const { data } = await learningReportApi.get(row.id)
    currentReport.value = data
    detailDialogVisible.value = true
  } catch (error) {
    ElMessage.error('获取报告详情失败')
  }
}

const deleteReport = async (row) => {
  try {
    await ElMessageBox.confirm('确定删除该报告吗？', '提示', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning',
    })
    await learningReportApi.delete(row.id)
    ElMessage.success('删除成功')
    fetchReports()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('删除失败')
    }
  }
}

onMounted(() => {
  fetchReports()
  fetchSubjects()
})
</script>

<style scoped>
.learning-reports {
  max-width: 1200px;
  margin: 0 auto;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.filters {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}

.pagination {
  margin-top: 20px;
  display: flex;
  justify-content: flex-end;
}

/* 报告详情弹窗样式 */
.report-content {
  max-height: 70vh;
  overflow-y: auto;
}

.report-header {
  text-align: center;
  margin-bottom: 30px;
  padding-bottom: 20px;
  border-bottom: 1px solid #eee;
}

.report-header h2 {
  margin: 0 0 15px 0;
}

.report-meta {
  display: flex;
  justify-content: center;
  gap: 10px;
  align-items: center;
}

.report-meta .accuracy {
  margin-left: 20px;
  font-size: 16px;
}

.report-section {
  margin-bottom: 30px;
}

.report-section h3 {
  color: #409eff;
  border-left: 4px solid #409eff;
  padding-left: 10px;
  margin-bottom: 15px;
}

.subsection {
  margin-bottom: 20px;
}

.subsection h4 {
  color: #606266;
  margin-bottom: 10px;
}

.stat-card {
  text-align: center;
  padding: 20px;
  background: #f5f7fa;
  border-radius: 8px;
}

.stat-card .stat-value {
  font-size: 32px;
  font-weight: bold;
  color: #409eff;
}

.stat-card .stat-label {
  font-size: 14px;
  color: #909399;
  margin-top: 5px;
}

.mini-stat {
  text-align: center;
  padding: 15px;
  background: #f5f7fa;
  border-radius: 8px;
}

.mini-stat .value {
  font-size: 24px;
  font-weight: bold;
  color: #409eff;
}

.mini-stat .label {
  font-size: 12px;
  color: #909399;
}

.distribution-bars {
  padding: 10px 0;
}

.bar-item {
  display: flex;
  align-items: center;
  margin-bottom: 10px;
}

.bar-label {
  width: 80px;
  font-size: 14px;
}

.bar-wrapper {
  flex: 1;
  height: 20px;
  background-color: #f0f0f0;
  border-radius: 10px;
  overflow: hidden;
  margin: 0 10px;
}

.bar {
  height: 100%;
  border-radius: 10px;
  transition: width 0.3s ease;
}

.bar-value {
  width: 40px;
  text-align: right;
  font-size: 14px;
}

.suggestion-card {
  margin-bottom: 10px;
}

.summary-box {
  background: #f5f7fa;
  padding: 20px;
  border-radius: 8px;
}

.summary-box h4 {
  margin: 10px 0;
  color: #409eff;
}

.summary-box ul {
  margin: 0;
  padding-left: 20px;
}

.summary-box li {
  margin: 5px 0;
  line-height: 1.6;
}

.word-list {
  display: flex;
  flex-wrap: wrap;
}

/* 禁用卡片的hover效果 */
.learning-reports :deep(.el-card) {
  transition: none;
}
.learning-reports :deep(.el-card:hover) {
  transform: none;
  box-shadow: var(--shadow-sm) !important;
}
</style>
