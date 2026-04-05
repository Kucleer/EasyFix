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
        <el-select v-model="filters.subject_id" placeholder="选择学科" clearable @change="fetchQuestions" style="width: 195px">
          <el-option v-for="s in subjects" :key="s.id" :label="s.name" :value="s.id" />
        </el-select>
        <el-select v-model="filters.difficulty" placeholder="难度" multiple clearable @change="fetchQuestions" style="width: 150px">
          <el-option v-for="i in 5" :key="i" :label="'★'.repeat(i)" :value="i" />
        </el-select>
        <el-select v-model="filters.tag_ids" placeholder="标签" multiple clearable @change="fetchQuestions" style="width: 300px">
          <el-option v-for="t in allTags" :key="t.id" :label="t.name" :value="t.id" />
        </el-select>
        <el-select
          v-model="filters.knowledge_point"
          placeholder="知识点"
          clearable
          filterable
          @change="fetchQuestions"
          style="width: 195px"
        >
          <el-option v-for="kp in filterOptions.knowledge_points" :key="kp" :label="kp" :value="kp" />
        </el-select>
        <el-select v-model="filters.grade" placeholder="年级" clearable @change="fetchQuestions" style="width: 150px">
          <el-option v-for="g in gradeOptions" :key="g.value" :label="g.label" :value="g.value" />
        </el-select>
        <el-select v-model="filters.error_type" placeholder="错误类型" multiple clearable @change="fetchQuestions" style="width: 330px">
          <el-option v-for="et in filterOptions.error_types" :key="et" :label="et" :value="et" />
        </el-select>
        <el-select v-model="filters.semester" placeholder="学期" clearable @change="fetchQuestions" style="width: 135px">
          <el-option label="上学期" :value="1" />
          <el-option label="下学期" :value="2" />
        </el-select>
        <el-select v-model="filters.accuracy_range" placeholder="正确率筛选" clearable @change="fetchQuestions" style="width: 150px">
          <el-option label="0-30% 薄弱" :value="'0-30'" />
          <el-option label="30-60% 一般" :value="'30-60'" />
          <el-option label="60-80% 良好" :value="'60-80'" />
          <el-option label="80-100% 掌握" :value="'80-100'" />
          <el-option label="无统计" :value="'none'" />
        </el-select>
        <el-input
          v-model="filters.keyword"
          placeholder="搜索关键词"
          clearable
          @change="fetchQuestions"
          style="width: 225px"
        />
      </div>

      <!-- 已选筛选条件展示 -->
      <div v-if="hasActiveFilters" class="selected-filters">
        <span class="filter-label">已选条件：</span>
        <el-tag v-if="filters.difficulty?.length" v-for="d in filters.difficulty" :key="d" size="small" closable @close="removeFilter('difficulty', d)" :class="'difficulty-filter-' + d">
          {{ getDifficultyStars(d) }}
        </el-tag>
        <el-tag v-if="filters.error_type?.length" v-for="et in filters.error_type" :key="et" :type="getErrorTypeType(et)" size="small" closable @close="removeFilter('error_type', et)">
          {{ et }}
        </el-tag>
        <el-tag v-if="filters.tag_ids?.length" v-for="tagId in filters.tag_ids" :key="tagId" size="small" closable @close="removeFilter('tag_ids', tagId)" :style="getTagStyle(tagId)">
          {{ getTagName(tagId) }}
        </el-tag>
        <el-tag v-if="filters.knowledge_point" size="small" type="info" closable @close="removeFilter('knowledge_point')">
          知识点: {{ filters.knowledge_point }}
        </el-tag>
        <el-tag v-if="filters.subject_id" size="small" closable @close="removeFilter('subject_id')">
          {{ subjects.find(s => s.id === filters.subject_id)?.name }}
        </el-tag>
        <el-tag v-if="filters.grade" size="small" closable @close="removeFilter('grade')">
          {{ getGradeLabel(filters.grade) }}
        </el-tag>
        <el-tag v-if="filters.semester" size="small" closable @close="removeFilter('semester')">
          {{ filters.semester === 1 ? '上学期' : '下学期' }}
        </el-tag>
        <el-button link type="primary" size="small" @click="clearAllFilters">清空</el-button>
      </div>

      <!-- 错题列表 -->
      <el-table v-model:selection="selectedQuestions" :data="questions.items" stripe style="width: 100%; margin-top: 20px" @selection-change="handleSelectionChange">
        <el-table-column type="selection" width="50" />
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column label="题目" min-width="250">
          <template #default="{ row }">
            <div class="question-cell">
              <el-image
                v-if="row.original_image || row.original_images?.length"
                :src="'/uploads/' + (row.original_image || row.original_images[0])"
                fit="contain"
                style="width: 50px; height: 50px; margin-right: 8px; cursor: pointer"
                @click="previewImage('/uploads/' + (row.original_image || row.original_images[0]))"
              />
              <div class="text-preview" v-html="decodeHTML(row.parsed_question || row.original_text || '无文本')"></div>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="difficulty" label="难度" width="120">
          <template #default="{ row }">
            <span class="difficulty-stars" :class="'difficulty-' + row.difficulty">{{ getDifficultyStars(row.difficulty) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="正确率" width="100" sortable :sort-method="(a, b) => getAccuracyValue(a) - getAccuracyValue(b)">
          <template #default="{ row }">
            {{ getAccuracyDisplay(row) }}
          </template>
        </el-table-column>
        <el-table-column label="复习" width="100">
          <template #default="{ row }">
            <span class="review-info">
              <span class="correct">{{ row.correct_count || 0 }}</span> /
              <span class="total">{{ (row.correct_count || 0) + (row.error_count || 0) }}</span>
            </span>
          </template>
        </el-table-column>
        <el-table-column prop="error_type" label="错误类型" width="110">
          <template #default="{ row }">
            <el-tag v-if="row.error_type" :type="getErrorTypeType(row.error_type)" :style="{ marginRight: '4px', fontSize: '14px' }">{{ row.error_type }}</el-tag>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column label="知识点" width="150">
          <template #default="{ row }">
            <el-tag v-if="row.knowledge_point" type="info" :style="{ marginRight: '4px', fontSize: '14px' }">{{ row.knowledge_point }}</el-tag>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column label="标签" width="150">
          <template #default="{ row }">
            <el-tag
              v-for="tag in (row.tags || []).slice(0, 2)"
              :key="tag.id"
              :style="{ marginRight: '4px', backgroundColor: tag.color || '#409eff', borderColor: tag.color || '#409eff', color: tag.color ? getContrastColor(tag.color) : '#ffffff', fontSize: '14px' }"
            >{{ tag.name }}</el-tag>
            <el-tag v-if="(row.tags || []).length > 2" :style="{ fontSize: '14px' }">+{{ row.tags.length - 2 }}</el-tag>
            <span v-if="!row.tags?.length">-</span>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="160">
          <template #default="{ row }">
            {{ formatDate(row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="320" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" size="default" @click="viewDetail(row)">查看</el-button>
            <el-button type="primary" size="default" @click="editQuestion(row)">编辑</el-button>
            <el-button type="primary" size="default" @click="generateSimilar(row)">相似题</el-button>
            <el-button type="danger" size="default" @click="deleteQuestion(row)">删除</el-button>
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
        <!-- 原图展示区 -->
        <div v-if="getImageList(currentQuestion).length" class="detail-images">
          <div class="detail-card">
            <div class="card-header-blue">原图</div>
            <div class="card-content">
              <div class="image-gallery">
                <el-image
                  v-for="(img, idx) in getImageList(currentQuestion)"
                  :key="idx"
                  :src="'/uploads/' + img"
                  fit="cover"
                  class="gallery-image"
                  style="cursor: pointer"
                  @click="previewImage('/uploads/' + img)"
                />
              </div>
            </div>
          </div>
        </div>

        <!-- 题目和答案并排 -->
        <div class="detail-row">
          <!-- 题目卡片 -->
          <div class="detail-card flex-1">
            <div class="card-header-blue">题目</div>
            <div class="card-content">
              <div class="question-text" v-html="decodeHTML(currentQuestion.parsed_question || currentQuestion.original_text || '暂无')"></div>
            </div>
          </div>
          <!-- 答案卡片 -->
          <div class="detail-card flex-1">
            <div class="card-header-green">答案</div>
            <div class="card-content">
              <div class="question-text" v-html="decodeHTML(currentQuestion.answer || '暂无')"></div>
            </div>
          </div>
        </div>

        <!-- 解析卡片 -->
        <div class="detail-card">
          <div class="card-header-orange">解析</div>
          <div class="card-content">
            <div v-if="currentQuestion.analysis" class="question-text" v-html="decodeHTML(currentQuestion.analysis)"></div>
            <div v-if="currentQuestion.analysis_image" class="analysis-image">
              <el-image
                :src="'/uploads/' + currentQuestion.analysis_image"
                fit="contain"
                class="analysis-img"
                style="cursor: pointer"
                @click="previewImage('/uploads/' + currentQuestion.analysis_image)"
              />
            </div>
            <span v-if="!currentQuestion.analysis && !currentQuestion.analysis_image" class="text-muted">暂无</span>
          </div>
        </div>

        <!-- 元数据卡片 -->
        <div class="detail-card">
          <div class="card-header-gray">信息</div>
          <div class="card-content">
            <div class="meta-row">
              <div class="meta-item">
                <label>难度：</label>
                <span class="difficulty-stars-yellow">{{ getYellowStars(currentQuestion.difficulty) }}</span>
              </div>
              <div class="meta-item">
                <label>年级/学期：</label>
                <span>{{ getGradeLabel(currentQuestion.grade) }} / {{ currentQuestion.semester ? (currentQuestion.semester === 1 ? '上学期' : '下学期') : '未设置' }}</span>
              </div>
            </div>
            <div class="meta-row">
              <div class="meta-item">
                <label>错误类型：</label>
                <el-tag v-if="currentQuestion.error_type" :type="getErrorTypeType(currentQuestion.error_type)" size="small">
                  {{ currentQuestion.error_type }}
                </el-tag>
                <span v-else class="text-muted">暂无</span>
              </div>
              <div class="meta-item">
                <label>知识点：</label>
                <el-tag v-if="currentQuestion.knowledge_point" size="small" type="info">
                  {{ currentQuestion.knowledge_point }}
                </el-tag>
                <span v-else class="text-muted">暂无</span>
              </div>
            </div>
          </div>
        </div>

        <!-- 标签区域 -->
        <div class="tags-area">
          <label class="tags-label">标签：</label>
          <el-tag
            v-for="tag in currentQuestion.tags"
            :key="tag.id"
            size="small"
            :style="{ marginRight: '8px', backgroundColor: tag.color || '#409eff', borderColor: tag.color || '#409eff', color: tag.color ? getContrastColor(tag.color) : '#ffffff' }"
          >{{ tag.name }}</el-tag>
          <span v-if="!currentQuestion.tags?.length" class="text-muted">暂无</span>
        </div>

        <!-- 相似题卡片 -->
        <div v-if="currentQuestion.similar_questions?.length" class="detail-card">
          <div class="card-header-purple">相似题</div>
          <div class="card-content">
            <div v-for="sq in currentQuestion.similar_questions" :key="sq.id" class="similar-item">
              <p><strong>题目：</strong><span v-html="decodeHTML(sq.similar_text)"></span></p>
              <p><strong>答案：</strong><span v-html="decodeHTML(sq.similar_answer)"></span></p>
            </div>
          </div>
        </div>
      </div>
    </el-dialog>

    <!-- 编辑弹窗 -->
    <el-dialog v-model="editVisible" title="编辑错题" width="700px">
      <el-form :model="editForm" label-width="100px" style="max-width: 600px">
        <el-form-item label="学科" required>
          <el-select v-model="editForm.subject_id" placeholder="选择学科" style="width: 100%">
            <el-option v-for="s in subjects" :key="s.id" :label="s.name" :value="s.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="原图">
          <div v-if="editForm.original_image" class="original-image-preview">
            <el-image
              :src="'/uploads/' + editForm.original_image"
              fit="contain"
              style="width: 100px; height: 100px; margin-right: 10px; cursor: pointer"
              @click="previewImage('/uploads/' + editForm.original_image)"
            />
            <el-button size="small" @click="editForm.original_image = ''">移除</el-button>
          </div>
          <el-upload
            v-if="!editForm.original_image"
            :show-file-list="false"
            accept="image/*"
            :http-request="handleOriginalImageUpload"
          >
            <el-button size="small" type="primary">上传图片</el-button>
          </el-upload>
        </el-form-item>
        <el-form-item label="题目">
          <el-input v-model="editForm.parsed_question" type="textarea" :rows="6" />
        </el-form-item>
        <el-form-item label="答案">
          <el-input v-model="editForm.answer" type="textarea" :rows="4" />
        </el-form-item>
        <el-form-item label="解析">
          <el-input v-model="editForm.analysis" type="textarea" :rows="4" />
        </el-form-item>
        <el-form-item label="解析图片">
          <div v-if="editForm.analysis_image" class="analysis-image-preview">
            <el-image
              :src="'/uploads/' + editForm.analysis_image"
              fit="contain"
              style="width: 100px; height: 100px; margin-right: 10px; cursor: pointer"
              @click="previewImage('/uploads/' + editForm.analysis_image)"
            />
            <el-button size="small" @click="editForm.analysis_image = ''">移除</el-button>
          </div>
          <el-upload
            v-if="!editForm.analysis_image"
            :show-file-list="false"
            accept="image/*"
            :http-request="handleAnalysisImageUpload"
          >
            <el-button size="small" type="primary">上传图片</el-button>
          </el-upload>
        </el-form-item>
        <el-form-item label="难度">
          <el-rate v-model="editForm.difficulty" :max="5" />
        </el-form-item>
        <el-form-item label="错误类型">
          <el-select v-model="editForm.error_type" multiple placeholder="选择错误类型">
            <el-option
              v-for="et in editFilteredErrorTypes"
              :key="et.id"
              :label="et.name"
              :value="et.name"
            />
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
          <el-select
            v-model="editForm.knowledge_point"
            placeholder="选择知识点"
            clearable
            filterable
            allow-create
            style="width: 100%"
          >
            <el-option
              v-for="kp in editKnowledgePoints"
              :key="kp.id"
              :label="kp.name"
              :value="kp.name"
            />
          </el-select>
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

    <!-- 图片预览弹层 -->
    <el-image-viewer
      v-if="imagePreviewVisible"
      :url-list="[imagePreviewUrl]"
      @close="imagePreviewVisible = false"
    />
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { questionApi, uploadApi } from '@/api/question'

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

// 解码HTML实体（将 &times; 转为 × 等）
const decodeHTML = (html) => {
  if (!html) return ''
  const textarea = document.createElement('textarea')
  textarea.innerHTML = html
  return textarea.value
}

const questions = ref({ total: 0, items: [] })
const subjects = ref([])
const allTags = ref([])

// 编辑弹窗中的知识点和错误类型
const editKnowledgePoints = ref([])
const editErrorTypes = ref([])
const editFilteredErrorTypes = ref([])
const editSelectedKnowledgePoint = ref(null)

const filters = reactive({
  subject_id: null,
  difficulty: null,
  tag_ids: null,
  knowledge_point: '',
  error_type: null,
  keyword: '',
  grade: null,
  semester: null,
  accuracy_range: null,
})

// 动态筛选选项
const filterOptions = reactive({
  error_types: [],
  knowledge_points: [],
})

// 获取筛选选项（按学科）
const fetchFilterOptions = async (subjectId) => {
  if (!subjectId) {
    filterOptions.error_types = []
    filterOptions.knowledge_points = []
    return
  }
  try {
    const { data } = await questionApi.getFilterOptions(subjectId)
    filterOptions.error_types = data.error_types || []
    filterOptions.knowledge_points = data.knowledge_points || []
  } catch (error) {
    console.error('获取筛选选项失败:', error)
  }
}

// 监听学科变化，获取对应的错误类型和知识点选项
watch(() => filters.subject_id, (newVal, oldVal) => {
  if (newVal !== oldVal) {
    filters.knowledge_point = ''
    filters.error_type = null
    fetchFilterOptions(newVal)
  }
})
const pagination = reactive({
  page: 1,
  limit: 20,
})
const detailVisible = ref(false)
const editVisible = ref(false)
const currentQuestion = ref(null)
const imagePreviewVisible = ref(false)
const imagePreviewUrl = ref('')
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
  subject_id: null,
  original_image: '',
  parsed_question: '',
  answer: '',
  analysis: '',
  analysis_image: '',
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
    if (filters.accuracy_range) params.accuracy_range = filters.accuracy_range

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

// 编辑弹窗中根据学科获取知识点
const fetchEditKnowledgePoints = async () => {
  if (!editForm.subject_id) {
    editKnowledgePoints.value = []
    return
  }
  try {
    const { data } = await questionApi.listKnowledgePoints({ subject_id: editForm.subject_id })
    editKnowledgePoints.value = Array.isArray(data) ? data : (data.items || [])
  } catch (e) {
    console.error('加载知识点失败:', e)
  }
}

// 编辑弹窗中根据学科获取错误类型
const fetchEditErrorTypes = async () => {
  if (!editForm.subject_id) {
    editErrorTypes.value = []
    return
  }
  try {
    const { data } = await questionApi.listErrorTypes({ subject_id: editForm.subject_id })
    editErrorTypes.value = Array.isArray(data) ? data : (data.items || [])
  } catch (e) {
    console.error('加载错误类型失败:', e)
  }
}

// 监听编辑弹窗中学科变化，重新加载知识点和错误类型
watch(() => editForm.subject_id, () => {
  editForm.knowledge_point = ''
  editForm.error_type = []
  editSelectedKnowledgePoint.value = null
  editFilteredErrorTypes.value = []
  fetchEditKnowledgePoints()
  fetchEditErrorTypes()
})

// 监听知识点变化，联动过滤错误类型
watch(() => editForm.knowledge_point, (newVal) => {
  if (!newVal) {
    editSelectedKnowledgePoint.value = null
    editFilteredErrorTypes.value = editErrorTypes.value
    return
  }
  const kp = editKnowledgePoints.value.find(k => k.name === newVal)
  if (kp && kp.error_types && kp.error_types.length > 0) {
    editSelectedKnowledgePoint.value = kp
    editFilteredErrorTypes.value = kp.error_types.map(et => ({ id: et.id, name: et.name }))
  } else {
    editSelectedKnowledgePoint.value = null
    editFilteredErrorTypes.value = editErrorTypes.value
  }
})

// 监听errorTypes加载完成，更新filteredErrorTypes
watch(editErrorTypes, (newVal) => {
  if (editSelectedKnowledgePoint.value) {
    editFilteredErrorTypes.value = editSelectedKnowledgePoint.value.error_types.map(et => ({ id: et.id, name: et.name }))
  } else {
    editFilteredErrorTypes.value = newVal
  }
}, { immediate: true })

// 监听知识点加载完成，重新触发知识点→错误类型联动
watch(editKnowledgePoints, () => {
  if (editForm.knowledge_point) {
    const kp = editKnowledgePoints.value.find(k => k.name === editForm.knowledge_point)
    if (kp && kp.error_types && kp.error_types.length > 0) {
      editSelectedKnowledgePoint.value = kp
      editFilteredErrorTypes.value = kp.error_types.map(et => ({ id: et.id, name: et.name }))
    } else {
      editSelectedKnowledgePoint.value = null
      editFilteredErrorTypes.value = editErrorTypes.value
    }
  }
})

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

const handleAnalysisImageUpload = async (options) => {
  const { file } = options
  try {
    const formData = new FormData()
    formData.append('file', file)
    const res = await uploadApi.uploadFile(file)
    if (res.data && res.data.path) {
      editForm.analysis_image = res.data.path
      ElMessage.success('上传成功')
    } else if (res.data && res.data.image_path) {
      editForm.analysis_image = res.data.image_path
      ElMessage.success('上传成功')
    } else if (res.data && res.data.file_path) {
      editForm.analysis_image = res.data.file_path
      ElMessage.success('上传成功')
    } else {
      ElMessage.error('上传失败')
    }
  } catch (error) {
    console.error('上传失败:', error)
    ElMessage.error('上传失败')
  }
}

const handleOriginalImageUpload = async (options) => {
  const { file } = options
  console.log('[DEBUG upload] file:', file.name)
  try {
    const formData = new FormData()
    formData.append('file', file)
    const res = await uploadApi.uploadFile(file)
    console.log('[DEBUG upload] res:', res)
    console.log('[DEBUG upload] res.data:', res.data)
    console.log('[DEBUG upload] res.data.path:', res.data?.path)
    if (res.data && res.data.path) {
      editForm.original_image = res.data.path
      ElMessage.success('上传成功')
    } else if (res.data && res.data.image_path) {
      editForm.original_image = res.data.image_path
      ElMessage.success('上传成功')
    } else if (res.data && res.data.file_path) {
      editForm.original_image = res.data.file_path
      ElMessage.success('上传成功')
    } else {
      ElMessage.error('上传失败')
    }
  } catch (error) {
    console.error('上传失败:', error)
    ElMessage.error('上传失败')
  }
}

const viewDetail = async (row) => {
  const { data } = await questionApi.get(row.id)
  currentQuestion.value = data
  detailVisible.value = true
}

const previewImage = (url) => {
  imagePreviewUrl.value = url
  imagePreviewVisible.value = true
}

const editQuestion = (row) => {
  currentQuestion.value = row
  editForm.subject_id = row.subject_id || null
  editForm.original_image = row.original_image || ''
  editForm.parsed_question = row.parsed_question || ''
  editForm.answer = row.answer || ''
  editForm.analysis = row.analysis || ''
  editForm.analysis_image = row.analysis_image || ''
  editForm.difficulty = row.difficulty || 3
  editForm.error_type = row.error_type ? (Array.isArray(row.error_type) ? row.error_type : row.error_type.split(',').map(e => e.trim()).filter(e => e)) : []
  editForm.knowledge_point = row.knowledge_point || ''
  editForm.grade = row.grade || null
  editForm.semester = row.semester || null
  editForm.tag_ids = row.tags ? row.tags.map(t => t.id) : []
  // 先加载知识点和错误类型，再设置知识点（触发联动）
  fetchEditKnowledgePoints()
  fetchEditErrorTypes()
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
    console.log('[DEBUG saveEdit] currentQuestion.id:', currentQuestion.value.id)
    console.log('[DEBUG saveEdit] submitData.original_image:', submitData.original_image)
    console.log('[DEBUG saveEdit] submitData:', submitData)
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
  const types = ['', 'success', 'success', 'warning', 'warning', 'danger']
  return types[difficulty] || 'info'
}

const getDifficultyStars = (difficulty) => {
  return '★'.repeat(difficulty)
}

// 获取黄色星星（统一黄色）
const getYellowStars = (difficulty) => {
  if (!difficulty) return '☆☆☆☆☆'
  const d = Math.max(0, Math.min(5, difficulty)) // clamp to [0, 5]
  return '★'.repeat(d) + '☆'.repeat(5 - d)
}

const getErrorTypeType = (errorType) => {
  const typeMap = {
    '计算': 'danger',
    '概念': 'warning',
    '审题': 'info',
    '粗心': 'success',
    '其他': '',
  }
  return typeMap[errorType] || ''
}

const getAccuracyDisplay = (row) => {
  const correct = row.correct_count || 0
  const error = row.error_count || 0
  if (correct + error === 0) return '-'
  return Math.round(correct / (correct + error) * 100) + '%'
}

const getAccuracyValue = (row) => {
  const correct = row.correct_count || 0
  const error = row.error_count || 0
  if (correct + error === 0) return -1
  return correct / (correct + error)
}

const hasActiveFilters = computed(() => {
  return filters.difficulty?.length ||
    filters.error_type?.length ||
    filters.tag_ids?.length ||
    filters.knowledge_point ||
    filters.subject_id ||
    filters.grade ||
    filters.semester ||
    filters.accuracy_range
})

const removeFilter = (key, val) => {
  if (key === 'difficulty') {
    filters.difficulty = (filters.difficulty || []).filter(d => d !== val)
  } else if (key === 'error_type') {
    filters.error_type = (filters.error_type || []).filter(e => e !== val)
  } else if (key === 'tag_ids') {
    filters.tag_ids = (filters.tag_ids || []).filter(id => id !== val)
  } else {
    filters[key] = typeof filters[key] === 'number' ? null : (Array.isArray(filters[key]) ? [] : '')
  }
  fetchQuestions()
}

const clearAllFilters = () => {
  filters.difficulty = null
  filters.error_type = null
  filters.tag_ids = null
  filters.knowledge_point = ''
  filters.subject_id = null
  filters.grade = null
  filters.semester = null
  fetchQuestions()
}

const removeDifficulty = (d) => {
  filters.difficulty = filters.difficulty.filter(i => i !== d)
  fetchQuestions()
}

const removeTag = (tagId) => {
  filters.tag_ids = filters.tag_ids.filter(id => id !== tagId)
  fetchQuestions()
}

const removeErrorType = (et) => {
  filters.error_type = filters.error_type.filter(e => e !== et)
  fetchQuestions()
}

const getTagColor = (tagId) => {
  const tag = allTags.value.find(t => t.id === tagId)
  return tag?.color || '#409eff'
}

// 获取标签的样式（背景色和文字色）
const getTagStyle = (tagId) => {
  const bgColor = getTagColor(tagId)
  // 根据背景色亮度计算文字颜色
  const textColor = getContrastColor(bgColor)
  return { backgroundColor: bgColor, borderColor: bgColor, color: textColor }
}

// 根据背景色返回对比色文字
const getContrastColor = (hexColor) => {
  if (!hexColor) return '#ffffff'
  // 移除 # 号
  const color = hexColor.replace('#', '')
  // 解析RGB
  const r = parseInt(color.substr(0, 2), 16)
  const g = parseInt(color.substr(2, 2), 16)
  const b = parseInt(color.substr(4, 2), 16)
  // 计算亮度
  const brightness = (r * 299 + g * 587 + b * 114) / 1000
  return brightness > 128 ? '#000000' : '#ffffff'
}

const getTagName = (tagId) => {
  const tag = allTags.value.find(t => t.id === tagId)
  return tag?.name || ''
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
  gap: 15px;
  flex-wrap: wrap;
  font-size: 16px;
}

.filters :deep(.el-input__wrapper),
.filters :deep(.el-select__wrapper) {
  min-height: 40px !important;
  font-size: 16px !important;
}

.filters :deep(.el-input__inner) {
  font-size: 16px !important;
  height: 40px !important;
}

.filters :deep(.el-select__tags) {
  font-size: 16px !important;
}

.selected-filters {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
  align-items: center;
  padding: 12px 0;
  font-size: 16px;
}

.filter-label {
  font-size: 16px;
  color: #909399;
}

.question-cell {
  display: flex;
  align-items: center;
}

.text-preview {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: normal;
  word-break: break-word;
  line-height: 1.4;
}

.pagination {
  margin-top: 20px;
  display: flex;
  justify-content: flex-end;
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

.analysis-image-preview {
  display: flex;
  align-items: center;
  gap: 10px;
}

.original-image-preview {
  display: flex;
  align-items: center;
  gap: 10px;
}

/* 难度星级样式 */
.difficulty-stars {
  font-size: 14px;
  letter-spacing: 2px;
}

.difficulty-stars.difficulty-1,
.difficulty-stars.difficulty-2 {
  color: #67c23a;
}

.difficulty-stars.difficulty-3 {
  color: #e6a23c;
}

.difficulty-stars.difficulty-4,
.difficulty-stars.difficulty-5 {
  color: #f56c6c;
}

/* 难度筛选标签样式 */
.difficulty-filter-1,
.difficulty-filter-2 {
  color: #67c23a;
  border-color: #67c23a;
}

.difficulty-filter-3 {
  color: #e6a23c;
  border-color: #e6a23c;
}

.difficulty-filter-4,
.difficulty-filter-5 {
  color: #f56c6c;
  border-color: #f56c6c;
}

/* 表格字体加大 */
:deep(.el-table) {
  font-size: 15px;
}

:deep(.el-table th) {
  font-size: 15px;
}

:deep(.el-table td) {
  font-size: 15px;
}

/* 禁用卡片的hover效果 */
.questions :deep(.el-card) {
  transition: none;
}
.questions :deep(.el-card:hover) {
  transform: none;
  box-shadow: var(--shadow-sm) !important;
}

/* ========== 详情页卡片式布局 ========== */
.question-detail {
  padding: 8px;
}

/* 原图展示区 */
.detail-images {
  margin-bottom: 16px;
}

.image-gallery {
  display: flex;
  gap: 12px;
  overflow-x: auto;
  padding: 4px 0;
}

.gallery-image {
  width: 180px;
  height: 180px;
  border-radius: 8px;
  cursor: pointer;
  transition: transform 0.2s;
  flex-shrink: 0;
}

.gallery-image:hover {
  transform: scale(1.05);
}

/* 卡片通用样式 */
.detail-card {
  background: #fff;
  border-radius: 12px;
  box-shadow: 0 4px 16px rgba(0,0,0,0.08);
  margin-bottom: 16px;
  overflow: hidden;
}

.detail-row {
  display: flex;
  gap: 16px;
  margin-bottom: 16px;
}

.flex-1 {
  flex: 1;
}

/* 卡片标题栏 */
.card-header-blue {
  background: linear-gradient(135deg, #409eff 0%, #3a8ee6 100%);
  color: #fff;
  padding: 14px 20px;
  font-weight: bold;
  font-size: 18px;
}

.card-header-green {
  background: linear-gradient(135deg, #67c23a 0%, #5daf34 100%);
  color: #fff;
  padding: 14px 20px;
  font-weight: bold;
  font-size: 18px;
}

.card-header-orange {
  background: linear-gradient(135deg, #e6a23c 0%, #db8b2e 100%);
  color: #fff;
  padding: 14px 20px;
  font-weight: bold;
  font-size: 18px;
}

.card-header-gray {
  background: linear-gradient(135deg, #606266 0%, #555558 100%);
  color: #fff;
  padding: 14px 20px;
  font-weight: bold;
  font-size: 18px;
}

.card-header-purple {
  background: linear-gradient(135deg, #9c27b0 0%, #862491 100%);
  color: #fff;
  padding: 14px 20px;
  font-weight: bold;
  font-size: 18px;
}

/* 卡片内容区 */
.card-content {
  padding: 20px;
}

/* 题目/答案/解析文字 */
.question-text {
  white-space: pre-wrap;
  word-break: break-word;
  line-height: 1.8;
  font-size: 17px;
  color: #303133;
}

/* 解析图片 */
.analysis-image {
  margin-top: 12px;
}

.analysis-img {
  width: 200px;
  height: 200px;
  border-radius: 8px;
  cursor: pointer;
}

/* 元数据行 */
.meta-row {
  display: flex;
  gap: 32px;
  margin-bottom: 12px;
}

.meta-row:last-child {
  margin-bottom: 0;
}

.meta-item {
  display: flex;
  align-items: center;
  gap: 8px;
}

.meta-item label {
  color: #909399;
  font-size: 14px;
}

.meta-item span {
  color: #303133;
  font-size: 14px;
}

/* 黄色星星难度 */
.difficulty-stars-yellow {
  font-size: 18px;
  letter-spacing: 3px;
  color: #f5c518;
}

/* 标签区域 */
.tags-area {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 16px;
}

.tags-label {
  color: #909399;
  font-size: 14px;
}

/* 相似题 */
.similar-item {
  padding: 12px;
  background: #f5f7fa;
  border-radius: 8px;
  margin-bottom: 12px;
}

.similar-item:last-child {
  margin-bottom: 0;
}

.similar-item p {
  margin: 0 0 8px 0;
  line-height: 1.6;
}

.similar-item p:last-child {
  margin-bottom: 0;
}

/* 文字辅助 */
.text-muted {
  color: #c0c4cc;
  font-size: 14px;
}
</style>
