<template>
  <div class="questions">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>错题列表</span>
          <el-button type="primary" @click="$router.push('/upload')">
            <el-icon><Plus /></el-icon>
            新增错题
          </el-button>
        </div>
      </template>

      <!-- 筛选条件 -->
      <div class="filters">
        <el-select v-model="filters.subject_id" placeholder="选择学科" clearable @change="fetchQuestions" style="width: 130px">
          <el-option v-for="s in subjects" :key="s.id" :label="s.name" :value="s.id" />
        </el-select>
        <el-select v-model="filters.difficulty" placeholder="难度" multiple clearable @change="fetchQuestions" style="width: 180px">
          <el-option v-for="i in 5" :key="i" :label="`难度 ${i}`" :value="i" />
        </el-select>
        <el-select v-model="filters.tag_ids" placeholder="标签" multiple clearable @change="fetchQuestions" style="width: 200px">
          <el-option v-for="t in allTags" :key="t.id" :label="t.name" :value="t.id" />
        </el-select>
        <el-input
          v-model="filters.knowledge_point"
          placeholder="搜索知识点"
          clearable
          @change="fetchQuestions"
          style="width: 130px"
        />
        <el-select v-model="filters.grade" placeholder="年级" clearable @change="fetchQuestions" style="width: 100px">
          <el-option v-for="g in gradeOptions" :key="g.value" :label="g.label" :value="g.value" />
        </el-select>
        <el-select v-model="filters.error_type" placeholder="错误类型" multiple clearable @change="fetchQuestions" style="width: 180px">
          <el-option label="计算错误" value="计算" />
          <el-option label="概念错误" value="概念" />
          <el-option label="审题错误" value="审题" />
          <el-option label="粗心错误" value="粗心" />
          <el-option label="其他错误" value="其他" />
        </el-select>
        <el-select v-model="filters.semester" placeholder="学期" clearable @change="fetchQuestions" style="width: 90px">
          <el-option label="上学期" :value="1" />
          <el-option label="下学期" :value="2" />
        </el-select>
        <el-input
          v-model="filters.keyword"
          placeholder="搜索关键词"
          clearable
          @change="fetchQuestions"
          style="width: 150px"
        />
      </div>

      <!-- 错题列表 -->
      <el-table v-model:selection="selectedQuestions" :data="questions.items" stripe style="width: 100%; margin-top: 20px" @selection-change="handleSelectionChange">
        <el-table-column type="selection" width="50" />
        <el-table-column label="题目" min-width="200">
          <template #default="{ row }">
            <div class="question-cell">
              <el-image
                v-if="row.original_image || row.original_images?.length"
                :src="'/uploads/' + (row.original_image || row.original_images[0])"
                :preview-src-list="getImageList(row).map(i => '/uploads/' + i)"
                fit="contain"
                style="width: 50px; height: 50px; margin-right: 8px"
              />
              <div class="text-preview">{{ row.parsed_question || row.original_text || '无文本' }}</div>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="difficulty" label="难度" width="80">
          <template #default="{ row }">
            <el-tag :type="getDifficultyType(row.difficulty)">{{ row.difficulty }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="error_type" label="错误类型" width="100" />
        <el-table-column prop="knowledge_point" label="知识点" width="120" />
        <el-table-column prop="created_at" label="创建时间" width="160">
          <template #default="{ row }">
            {{ formatDate(row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" size="small" @click="viewDetail(row)">查看</el-button>
            <el-button link type="primary" size="small" @click="editQuestion(row)">编辑</el-button>
            <el-button link type="primary" size="small" @click="generateSimilar(row)">相似题</el-button>
            <el-button link type="danger" size="small" @click="deleteQuestion(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>

      <!-- 分页 -->
      <div class="pagination">
        <el-pagination
          v-model:current-page="pagination.page"
          v-model:page-size="pagination.limit"
          :page-sizes="[10, 20, 50, 100]"
          :total="questions.total"
          layout="total, sizes, prev, pager, next"
          @change="fetchQuestions"
        />
      </div>

      <!-- 批量操作栏 -->
      <div v-if="selectedQuestions.length > 0" class="batch-actions">
        <div class="batch-info">
          <span>已选择 <strong>{{ selectedQuestions.length }}</strong> 道错题</span>
        </div>
        <div class="batch-buttons">
          <el-button type="primary" @click="showPrintDialog('original')">打印原题</el-button>
          <el-button type="success" @click="showPrintDialog('similar')">打印相似题</el-button>
          <el-button type="warning" @click="batchGenerateSimilar">批量生成相似题</el-button>
          <el-button @click="clearSelection">取消选择</el-button>
        </div>
      </div>
    </el-card>

    <!-- 详情弹窗 -->
    <el-dialog v-model="detailVisible" title="错题详情" width="900px">
      <div v-if="currentQuestion" class="question-detail">
        <!-- 原图展示 -->
        <div v-if="getImageList(currentQuestion).length" class="detail-images">
          <p class="section-label">原图：</p>
          <div class="image-gallery">
            <el-image
              v-for="(img, idx) in getImageList(currentQuestion)"
              :key="idx"
              :src="'/uploads/' + img"
              :preview-src-list="getImageList(currentQuestion).map(i => '/uploads/' + i)"
              fit="contain"
              style="width: 200px; height: 200px; margin-right: 10px; margin-bottom: 10px"
            />
          </div>
        </div>
        <el-divider />
        <div class="detail-item">
          <label>题目：</label>
          <div class="question-text">{{ currentQuestion.parsed_question || currentQuestion.original_text || '暂无' }}</div>
        </div>
        <div class="detail-item">
          <label>答案：</label>
          <div class="question-text">{{ currentQuestion.answer || '暂无' }}</div>
        </div>
        <div class="detail-item">
          <label>解析：</label>
          <div class="question-text">{{ currentQuestion.analysis || '暂无' }}</div>
        </div>
        <div class="detail-row">
          <div class="detail-item half">
            <label>难度：</label>
            <el-tag :type="getDifficultyType(currentQuestion.difficulty)">{{ currentQuestion.difficulty }}</el-tag>
          </div>
          <div class="detail-item half">
            <label>年级/学期：</label>
            <span>{{ getGradeLabel(currentQuestion.grade) }} / {{ currentQuestion.semester ? (currentQuestion.semester === 1 ? '上学期' : '下学期') : '未设置' }}</span>
          </div>
        </div>
        <div class="detail-row">
          <div class="detail-item half">
            <label>错误类型：</label>
            <span>{{ currentQuestion.error_type || '暂无' }}</span>
          </div>
          <div class="detail-item half">
            <label>知识点：</label>
            <span>{{ currentQuestion.knowledge_point || '暂无' }}</span>
          </div>
        </div>
        <div class="detail-item">
          <label>标签：</label>
          <el-tag v-for="tag in currentQuestion.tags" :key="tag.id" size="small" style="margin-right: 5px">
            {{ tag.name }}
          </el-tag>
          <span v-if="!currentQuestion.tags?.length">暂无</span>
        </div>
        <!-- 相似题 -->
        <div v-if="currentQuestion.similar_questions?.length" class="detail-item">
          <label>相似题：</label>
          <div class="similar-list">
            <div v-for="sq in currentQuestion.similar_questions" :key="sq.id" class="similar-item">
              <p><strong>题目：</strong>{{ sq.similar_text }}</p>
              <p><strong>答案：</strong>{{ sq.similar_answer }}</p>
              <el-divider />
            </div>
          </div>
        </div>
      </div>
    </el-dialog>

    <!-- 编辑弹窗 -->
    <el-dialog v-model="editVisible" title="编辑错题" width="700px">
      <el-form :model="editForm" label-width="100px" style="max-width: 600px">
        <el-form-item label="题目">
          <el-input v-model="editForm.parsed_question" type="textarea" :rows="6" />
        </el-form-item>
        <el-form-item label="答案">
          <el-input v-model="editForm.answer" type="textarea" :rows="4" />
        </el-form-item>
        <el-form-item label="解析">
          <el-input v-model="editForm.analysis" type="textarea" :rows="4" />
        </el-form-item>
        <el-form-item label="难度">
          <el-rate v-model="editForm.difficulty" :max="5" />
        </el-form-item>
        <el-form-item label="错误类型">
          <el-select v-model="editForm.error_type" multiple placeholder="选择错误类型">
            <el-option label="计算错误" value="计算" />
            <el-option label="概念错误" value="概念" />
            <el-option label="审题错误" value="审题" />
            <el-option label="粗心错误" value="粗心" />
            <el-option label="其他错误" value="其他" />
          </el-select>
        </el-form-item>
        <el-form-item label="年级">
          <el-select v-model="editForm.grade" placeholder="选择年级" clearable>
            <el-option v-for="g in gradeOptions" :key="g.value" :label="g.label" :value="g.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="学期">
          <el-select v-model="editForm.semester" placeholder="选择学期" clearable>
            <el-option label="上学期" :value="1" />
            <el-option label="下学期" :value="2" />
          </el-select>
        </el-form-item>
        <el-form-item label="知识点">
          <el-input v-model="editForm.knowledge_point" placeholder="输入知识点" />
        </el-form-item>
        <el-form-item label="标签">
          <el-select v-model="editForm.tag_ids" multiple placeholder="选择标签" style="width: 100%">
            <el-option v-for="tag in allTags" :key="tag.id" :label="tag.name" :value="tag.id" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editVisible = false">取消</el-button>
        <el-button type="primary" :loading="editLoading" @click="saveEdit">保存</el-button>
      </template>
    </el-dialog>

    <!-- 打印设置弹窗 -->
    <el-dialog v-model="printDialogVisible" title="创建练习集" width="500px">
      <el-form :model="printForm" label-width="100px">
        <el-form-item label="练习集名称">
          <el-input v-model="printForm.name" placeholder="请输入练习集名称" />
        </el-form-item>
        <el-form-item label="题目类型">
          <el-tag :type="printForm.questionType === 'original' ? 'primary' : 'success'">
            {{ printForm.questionType === 'original' ? '原题' : '相似题' }}
          </el-tag>
        </el-form-item>
        <el-form-item label="选择题目">
          <span>已选择 <strong>{{ selectedQuestions.length }}</strong> 道错题</span>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="printDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="printLoading" @click="createPracticeSet">创建并生成PDF</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { questionApi } from '@/api/question'

// 年级选项：一年级到六年级，初一/初二/初三，高一/高二/高三
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

const questions = ref({ total: 0, items: [] })
const subjects = ref([])
const allTags = ref([])
const filters = reactive({
  subject_id: null,
  difficulty: null,
  tag_ids: null,
  knowledge_point: '',
  error_type: null,
  keyword: '',
  grade: null,
  semester: null,
})
const pagination = reactive({
  page: 1,
  limit: 20,
})
const detailVisible = ref(false)
const editVisible = ref(false)
const currentQuestion = ref(null)
const editLoading = ref(false)

// 多选相关
const selectedQuestions = ref([])
const printDialogVisible = ref(false)
const printLoading = ref(false)
const printForm = reactive({
  name: '',
  questionType: 'original',
})

const editForm = reactive({
  parsed_question: '',
  answer: '',
  analysis: '',
  difficulty: 3,
  error_type: [],
  knowledge_point: '',
  grade: null,
  semester: null,
  tag_ids: [],
})

const fetchQuestions = async () => {
  try {
    // 构建查询参数，多选值用逗号分隔
    const params = {
      skip: (pagination.page - 1) * pagination.limit,
      limit: pagination.limit,
    }
    if (filters.subject_id) params.subject_id = filters.subject_id
    if (filters.difficulty && filters.difficulty.length) params.difficulty = filters.difficulty.join(',')
    if (filters.tag_ids && filters.tag_ids.length) params.tag_ids = filters.tag_ids.join(',')
    if (filters.knowledge_point) params.knowledge_point = filters.knowledge_point
    if (filters.keyword) params.keyword = filters.keyword
    if (filters.grade) params.grade = filters.grade
    if (filters.semester) params.semester = filters.semester
    if (filters.error_type && filters.error_type.length) params.error_type = filters.error_type.join(',')

    const { data } = await questionApi.list(params)
    questions.value = data
  } catch (error) {
    ElMessage.error('获取错题列表失败')
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

const fetchTags = async () => {
  try {
    const { data } = await questionApi.listTags()
    allTags.value = data
  } catch (error) {
    console.error('获取标签失败:', error)
  }
}

const getImageList = (row) => {
  if (!row) return []
  if (row.original_images && Array.isArray(row.original_images)) {
    return row.original_images
  }
  if (row.original_image) {
    return [row.original_image]
  }
  return []
}

const viewDetail = async (row) => {
  const { data } = await questionApi.get(row.id)
  currentQuestion.value = data
  detailVisible.value = true
}

const editQuestion = (row) => {
  currentQuestion.value = row
  editForm.parsed_question = row.parsed_question || ''
  editForm.answer = row.answer || ''
  editForm.analysis = row.analysis || ''
  editForm.difficulty = row.difficulty || 3
  editForm.error_type = row.error_type ? (Array.isArray(row.error_type) ? row.error_type : row.error_type.split(',').map(e => e.trim()).filter(e => e)) : []
  editForm.knowledge_point = row.knowledge_point || ''
  editForm.grade = row.grade || null
  editForm.semester = row.semester || null
  editForm.tag_ids = row.tags ? row.tags.map(t => t.id) : []
  editVisible.value = true
}

const saveEdit = async () => {
  editLoading.value = true
  try {
    // 处理 error_type 数组转为逗号分隔字符串
    const submitData = {
      ...editForm,
      error_type: Array.isArray(editForm.error_type) ? editForm.error_type.join(',') : editForm.error_type,
    }
    await questionApi.update(currentQuestion.value.id, submitData)
    ElMessage.success('更新成功')
    editVisible.value = false
    fetchQuestions()
  } catch (error) {
    ElMessage.error('更新失败')
  } finally {
    editLoading.value = false
  }
}

const generateSimilar = async (row) => {
  try {
    await ElMessageBox.confirm('将为该错题生成一道相似题目，是否继续？', '生成相似题', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'info',
    })
    const { data } = await questionApi.generateSimilar(row.id)
    ElMessage.success('相似题已生成')
    fetchQuestions()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('生成失败')
    }
  }
}

const deleteQuestion = async (row) => {
  try {
    await ElMessageBox.confirm('确定要删除这道错题吗？', '删除确认', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning',
    })
    await questionApi.delete(row.id)
    ElMessage.success('删除成功')
    fetchQuestions()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('删除失败')
    }
  }
}

const getDifficultyType = (difficulty) => {
  const types = ['', 'success', 'warning', 'warning', 'danger', 'danger']
  return types[difficulty] || 'info'
}

const getGradeLabel = (grade) => {
  if (!grade) return '未设置'
  const g = gradeOptions.find(o => o.value === grade)
  return g ? g.label : `${grade}年级`
}

const formatDate = (dateStr) => {
  if (!dateStr) return ''
  return new Date(dateStr).toLocaleString('zh-CN')
}

// 多选相关方法
const handleSelectionChange = (selection) => {
  selectedQuestions.value = selection
}

const clearSelection = () => {
  selectedQuestions.value = []
}

const showPrintDialog = (type) => {
  printForm.questionType = type
  // 自动生成默认名称
  const now = new Date()
  const dateStr = `${now.getFullYear()}${String(now.getMonth() + 1).padStart(2, '0')}${String(now.getDate()).padStart(2, '0')}`
  printForm.name = `练习集_${dateStr}`
  printDialogVisible.value = true
}

const createPracticeSet = async () => {
  if (!printForm.name.trim()) {
    ElMessage.warning('请输入练习集名称')
    return
  }
  if (selectedQuestions.value.length === 0) {
    ElMessage.warning('请先选择题目')
    return
  }

  printLoading.value = true
  try {
    const questionIds = selectedQuestions.value.map(q => q.id)
    const { data } = await questionApi.createPracticeSet({
      name: printForm.name,
      question_ids: questionIds,
      question_type: printForm.questionType,
    })

    // 自动生成PDF
    const pdfRes = await questionApi.generatePracticeSetPdf(data.id)

    ElMessage.success('练习集已创建，PDF已生成')
    printDialogVisible.value = false
    clearSelection()

    // 打开PDF下载
    window.open(pdfRes.data.pdf_url, '_blank')
  } catch (error) {
    ElMessage.error('创建练习集失败')
  } finally {
    printLoading.value = false
  }
}

const batchGenerateSimilar = async () => {
  if (selectedQuestions.value.length === 0) {
    ElMessage.warning('请先选择题目')
    return
  }

  try {
    await ElMessageBox.confirm(`将为 ${selectedQuestions.value.length} 道错题生成相似题，是否继续？`, '批量生成相似题', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'info',
    })

    const questionIds = selectedQuestions.value.map(q => q.id)
    const { data } = await questionApi.batchGenerateSimilar({ question_ids: questionIds })

    if (data.failed_count > 0) {
      ElMessage.warning(`成功 ${data.success_count} 道，失败 ${data.failed_count} 道`)
    } else {
      ElMessage.success(`成功生成 ${data.success_count} 道相似题`)
    }
    fetchQuestions()
    clearSelection()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('批量生成失败')
    }
  }
}

onMounted(() => {
  fetchQuestions()
  fetchSubjects()
  fetchTags()
})
</script>

<style scoped>
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

.question-cell {
  display: flex;
  align-items: center;
}

.text-preview {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 300px;
}

.pagination {
  margin-top: 20px;
  display: flex;
  justify-content: flex-end;
}

.question-detail {
  padding: 10px;
}

.detail-images {
  margin-bottom: 15px;
}

.section-label {
  font-weight: bold;
  color: #666;
  margin-bottom: 10px;
}

.image-gallery {
  display: flex;
  flex-wrap: wrap;
}

.detail-item {
  margin-bottom: 15px;
}

.detail-item label {
  font-weight: bold;
  color: #666;
  margin-right: 10px;
}

.detail-row {
  display: flex;
  gap: 20px;
}

.detail-item.half {
  flex: 1;
}

.question-text {
  white-space: pre-wrap;
  word-break: break-word;
  line-height: 1.6;
  max-height: none;
  overflow: visible;
}

.similar-list {
  margin-top: 10px;
}

.similar-item {
  padding: 10px;
  background: #f5f7fa;
  border-radius: 4px;
  margin-bottom: 10px;
}

.batch-actions {
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  background: white;
  padding: 15px 20px;
  box-shadow: 0 -2px 10px rgba(0, 0, 0, 0.1);
  z-index: 100;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.batch-info {
  font-size: 14px;
  color: #606266;
}

.batch-info strong {
  color: #409eff;
  font-size: 16px;
}

.batch-buttons {
  display: flex;
  gap: 10px;
}
</style>
