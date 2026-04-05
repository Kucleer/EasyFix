<template>
  <div class="upload">
    <el-card>
      <template #header>
        <span class="page-title">新增错题</span>
      </template>

      <!-- 图片上传卡片 -->
      <div class="detail-card" style="margin-bottom: 16px;">
        <div class="card-header-blue">📷 图片上传</div>
        <div class="card-content">
          <el-upload
            ref="uploadRef"
            class="upload-demo"
            drag
            :auto-upload="false"
            :limit="10"
            :on-change="handleFileChange"
            :on-remove="handleFileRemove"
            accept="image/*"
            multiple
          >
            <el-icon class="el-icon--upload"><upload-filled /></el-icon>
            <div class="el-upload__text">拖拽图片到此处或点击上传（可上传多张）</div>
            <template #tip>
              <div class="el-upload__tip">支持 JPEG/PNG/WEBP 格式，每张大小不超过 10MB</div>
            </template>
          </el-upload>
          <!-- 已上传图片预览 -->
          <div v-if="uploadImagePaths.length" class="image-preview-list">
            <div v-for="(img, idx) in uploadImagePaths" :key="idx" class="preview-item">
              <el-image
                :src="'/uploads/' + img"
                :preview-src-list="uploadImagePaths.map(i => '/uploads/' + i)"
                fit="cover"
                class="preview-image"
              />
              <el-button type="danger" size="small" circle @click="removeImage(idx)" class="remove-btn">✕</el-button>
            </div>
          </div>
        </div>
      </div>

      <!-- 基本信息卡片 -->
      <div class="detail-card" style="margin-bottom: 16px;">
        <div class="card-header-blue">📝 基本信息</div>
        <div class="card-content">
          <el-form :model="form" label-width="80px" style="max-width: 600px">
            <el-form-item label="学科" required>
              <el-select v-model="form.subject_id" placeholder="选择学科" style="width: 100%">
                <el-option v-for="s in subjects" :key="s.id" :label="s.name" :value="s.id" />
              </el-select>
            </el-form-item>
            <el-form-item label="年级">
              <el-select v-model="form.grade" placeholder="选择年级" clearable style="width: 100%">
                <el-option v-for="g in gradeOptions" :key="g.value" :label="g.label" :value="g.value" />
              </el-select>
            </el-form-item>
            <el-form-item label="学期">
              <el-select v-model="form.semester" placeholder="选择学期" clearable style="width: 100%">
                <el-option label="上学期" :value="1" />
                <el-option label="下学期" :value="2" />
              </el-select>
            </el-form-item>
          </el-form>
        </div>
      </div>

      <!-- 题目内容卡片 -->
      <div class="detail-card" style="margin-bottom: 16px;">
        <div class="card-header-green">📖 题目内容</div>
        <div class="card-content">
          <el-form :model="form" label-width="80px" style="max-width: 800px">
            <el-form-item label="题目">
              <el-input v-model="form.parsed_question" type="textarea" :rows="6" placeholder="请输入题目" />
            </el-form-item>
            <el-form-item label="答案">
              <el-input v-model="form.answer" type="textarea" :rows="4" placeholder="请输入答案" />
            </el-form-item>
            <el-form-item label="解析">
              <el-input v-model="form.analysis" type="textarea" :rows="4" placeholder="请输入解析" />
            </el-form-item>
          </el-form>
        </div>
      </div>

      <!-- 难度与分类卡片 -->
      <div class="detail-card" style="margin-bottom: 16px;">
        <div class="card-header-orange">⭐ 难度与分类</div>
        <div class="card-content">
          <el-form :model="form" label-width="80px" style="max-width: 600px">
            <el-form-item label="难度">
              <el-rate v-model="form.difficulty" :max="5" show-text :texts="['很简单', '简单', '一般', '较难', '很难']" />
            </el-form-item>
            <el-form-item label="错误类型">
              <el-select v-model="form.error_type" multiple placeholder="选择错误类型" style="width: 100%">
                <el-option v-for="et in filteredErrorTypes" :key="et.id" :label="et.name" :value="et.name" />
              </el-select>
            </el-form-item>
            <el-form-item label="知识点">
              <el-select
                v-model="form.knowledge_point"
                placeholder="选择知识点"
                clearable
                filterable
                allow-create
                style="width: 100%"
              >
                <el-option v-for="kp in knowledgePoints" :key="kp.id" :label="kp.name" :value="kp.name" />
              </el-select>
            </el-form-item>
            <el-form-item label="标签">
              <el-select v-model="form.tag_ids" multiple placeholder="选择标签" style="width: 100%">
                <el-option v-for="tag in allTags" :key="tag.id" :label="tag.name" :value="tag.id" />
              </el-select>
            </el-form-item>
          </el-form>
        </div>
      </div>

      <!-- 提交按钮 -->
      <div class="submit-area">
        <el-button type="primary" size="large" :loading="submitting" @click="submitQuestion">
          保存错题
        </el-button>
      </div>

      <!-- 已提交的错题预览 -->
      <div v-if="submittedQuestion" class="submitted-preview">
        <el-divider />
        <h4>已保存的错题</h4>
        <el-card shadow="never" class="preview-card">
          <div class="preview-item">
            <label>题目：</label>
            <span>{{ submittedQuestion.parsed_question || submittedQuestion.original_text }}</span>
          </div>
          <div class="preview-item">
            <label>答案：</label>
            <span>{{ submittedQuestion.answer || '暂无' }}</span>
          </div>
          <div class="preview-item">
            <label>学科：</label>
            <span>{{ getSubjectName(submittedQuestion.subject_id) }}</span>
          </div>
          <div class="preview-actions">
            <el-button type="primary" size="small" @click="continueAdd">继续录入</el-button>
            <el-button size="small" @click="router.push('/questions')">查看列表</el-button>
          </div>
        </el-card>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { uploadApi, questionApi } from '@/api/question'

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

const router = useRouter()
const currentStep = ref(0)
const selectedFiles = ref([])
const uploading = ref(false)
const submitting = ref(false)
const ocrResult = ref(null)
const batchOcrResults = ref([])
const ocrFailed = ref(false)
const ocrProgress = ref(0)
const submittedQuestion = ref(null)
const ocrProgressStatus = ref('')
const uploadRef = ref(null)
const uploadImagePaths = ref([])
const isManualEntryMode = ref(false)
const placeholderImage = 'data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIxNTAiIGhlaWdodD0iMTUwIiB2aWV3Qm94PSIwIDAgMTUwIDE1MCI+PHJlY3Qgd2lkdGg9IjE1MCIgaGVpZ2h0PSIxNTAiIGZpbGw9IiNlOGU4ZTgiLz48dGV4dCB4PSIxMjAiIHk9IjgwIiB0ZXh0LWFuY2hvcj0ibWlkZGxlIiBmaWxsPSIjOTk5OTk5Ij7lm77niYIiIHRydW5jYXRlPW9mZnNldD0iMCIvPjwvc3ZnPg=='

const subjects = ref([])
const allTags = ref([])
const knowledgePoints = ref([])
const errorTypes = ref([])
const filteredErrorTypes = ref([]) // 根据知识点过滤后的错误类型
const selectedKnowledgePoint = ref(null) // 当前选中的知识点对象

const form = reactive({
  subject_id: null,
  original_text: '',
  parsed_question: '',
  answer: '',
  analysis: '',
  difficulty: 3,
  error_type: [],  // 存储错误类型名称列表
  knowledge_point: '',  // 存储知识点名称
  grade: localStorage.getItem('lastGrade') ? parseInt(localStorage.getItem('lastGrade')) : null,
  semester: localStorage.getItem('lastSemester') ? parseInt(localStorage.getItem('lastSemester')) : null,
  tag_ids: [],
})

const canProceed = computed(() => {
  return form.parsed_question || ocrResult.value?.full_text || ocrFailed.value
})

const handleFileChange = (file, fileList) => {
  selectedFiles.value = fileList
}

const handleFileRemove = (file, fileList) => {
  selectedFiles.value = fileList
}

const startOCR = async () => {
  if (!selectedFiles.value.length) {
    ElMessage.warning('请先选择图片')
    return
  }

  uploading.value = true
  ocrFailed.value = false
  ocrProgress.value = 10
  ocrProgressStatus.value = ''
  batchOcrResults.value = []
  uploadImagePaths.value = []

  try {
    if (selectedFiles.value.length === 1) {
      // 单张图片
      ocrProgress.value = 30
      const { data } = await uploadApi.uploadImage(selectedFiles.value[0].raw)
      ocrProgress.value = 80
      ocrResult.value = data.ocr_result
      form.original_text = data.ocr_result.full_text || ''
      form.parsed_question = data.ocr_result.full_text || ''
      uploadImagePaths.value = [data.image_path]
      ocrProgress.value = 100
    } else {
      // 多张图片 - 逐张上传
      const results = []
      for (let i = 0; i < selectedFiles.value.length; i++) {
        ocrProgress.value = 30 + Math.floor((i / selectedFiles.value.length) * 50)
        try {
          const { data } = await uploadApi.uploadImage(selectedFiles.value[i].raw)
          results.push({
            image_path: data.image_path,
            ocr_result: data.ocr_result,
            original_filename: selectedFiles.value[i].name,
            success: true,
          })
          uploadImagePaths.value.push(data.image_path)
        } catch (e) {
          results.push({
            image_path: '',
            ocr_result: {},
            original_filename: selectedFiles.value[i].name,
            success: false,
            error: e.message,
          })
        }
      }
      batchOcrResults.value = results
      // 合并所有OCR结果
      const allTexts = results.filter(r => r.ocr_result?.full_text).map(r => r.ocr_result.full_text).join('\n\n')
      ocrResult.value = { full_text: allTexts, blocks: [] }
      form.original_text = allTexts
      form.parsed_question = allTexts
      ocrProgress.value = 100
    }

    ocrFailed.value = !ocrResult.value?.full_text
    currentStep.value = 1
  } catch (error) {
    console.error('OCR error:', error)
    ocrFailed.value = true
    ElMessage.warning('OCR识别超时或失败，您可以手动输入题目信息')
  } finally {
    uploading.value = false
  }
}

const retryOCR = () => {
  currentStep.value = 0
  selectedFiles.value = []
  ocrResult.value = null
  batchOcrResults.value = []
  ocrFailed.value = false
  ocrProgress.value = 0
  uploadImagePaths.value = []
  isManualEntryMode.value = false
  uploadRef.value?.clearFiles()
}

// 跳过图片，直接手动录入
const skipToManualEntry = () => {
  isManualEntryMode.value = true
  ocrFailed.value = true
  currentStep.value = 1
}

const submitQuestion = async () => {
  if (!form.subject_id) {
    ElMessage.warning('请完善必填信息')
    return
  }

  submitting.value = true
  try {
    // 处理 error_type 数组转为逗号分隔字符串
    const submitData = {
      ...form,
      error_type: Array.isArray(form.error_type) ? form.error_type.join(',') : form.error_type,
      original_images: uploadImagePaths.value,
      original_image: uploadImagePaths.value[0] || null,
    }
    const { data } = await questionApi.create(submitData)
    ElMessage.success('错题保存成功')
    submittedQuestion.value = data
    // 保存年级和学期到本地
    if (form.grade) localStorage.setItem('lastGrade', form.grade)
    if (form.semester) localStorage.setItem('lastSemester', form.semester)
    // Reset form for next entry but stay on page
    currentStep.value = 0
    selectedFiles.value = []
    ocrResult.value = null
    batchOcrResults.value = []
    ocrFailed.value = false
    ocrProgress.value = 0
    uploadImagePaths.value = []
    uploadRef.value?.clearFiles()
    // Reset form data
    form.original_text = ''
    form.parsed_question = ''
    form.answer = ''
    form.analysis = ''
    form.difficulty = 3
    form.error_type = []
    form.knowledge_point = ''
    form.grade = null
    form.semester = null
    form.tag_ids = []
  } catch (error) {
    ElMessage.error('保存失败: ' + (error.message || '未知错误'))
  } finally {
    submitting.value = false
  }
}

const loadMetaData = async () => {
  // 加载学科列表
  try {
    const { data } = await questionApi.listSubjects()
    // API返回数组，直接使用
    subjects.value = Array.isArray(data) ? data : (data.items || [])
  } catch (e) {
    console.error('加载学科失败:', e)
  }

  try {
    const { data } = await questionApi.listTags()
    // API返回数组，直接使用
    allTags.value = Array.isArray(data) ? data : (data.items || [])
  } catch (e) {
    console.error('加载标签失败:', e)
  }
}

// 加载知识点（根据学科筛选）
const fetchKnowledgePoints = async () => {
  if (!form.subject_id) {
    knowledgePoints.value = []
    return
  }
  try {
    const { data } = await questionApi.listKnowledgePoints({ subject_id: form.subject_id })
    knowledgePoints.value = Array.isArray(data) ? data : (data.items || [])
  } catch (e) {
    console.error('加载知识点失败:', e)
  }
}

// 加载错误类型（根据学科筛选，包含通用的）
const fetchErrorTypes = async () => {
  if (!form.subject_id) {
    errorTypes.value = []
    return
  }
  try {
    const { data } = await questionApi.listErrorTypes({ subject_id: form.subject_id })
    errorTypes.value = Array.isArray(data) ? data : (data.items || [])
  } catch (e) {
    console.error('加载错误类型失败:', e)
  }
}

// 监听学科变化，重新加载知识点和错误类型
watch(() => form.subject_id, () => {
  form.knowledge_point = '' // 切换学科时清空知识点
  form.error_type = [] // 切换学科时清空错误类型
  selectedKnowledgePoint.value = null
  filteredErrorTypes.value = []
  fetchKnowledgePoints()
  fetchErrorTypes()
})

// 监听知识点变化，联动过滤错误类型
watch(() => form.knowledge_point, (newVal) => {
  if (!newVal) {
    selectedKnowledgePoint.value = null
    // 如果清空了知识点，显示该学科下的所有错误类型
    filteredErrorTypes.value = errorTypes.value
    return
  }
  // 查找选中的知识点
  const kp = knowledgePoints.value.find(k => k.name === newVal)
  if (kp && kp.error_types && kp.error_types.length > 0) {
    // 如果知识点有关联的错误类型，只显示关联的
    selectedKnowledgePoint.value = kp
    filteredErrorTypes.value = kp.error_types.map(et => ({ id: et.id, name: et.name }))
  } else {
    // 如果没有关联，显示该学科下的所有错误类型
    selectedKnowledgePoint.value = null
    filteredErrorTypes.value = errorTypes.value
  }
  // 清空已选的错误类型
  form.error_type = []
})

// 监听errorTypes加载完成，更新filteredErrorTypes
watch(errorTypes, (newVal) => {
  if (selectedKnowledgePoint.value) {
    // 如果有选中的知识点，使用关联的错误类型
    filteredErrorTypes.value = selectedKnowledgePoint.value.error_types.map(et => ({ id: et.id, name: et.name }))
  } else {
    // 否则使用所有可用错误类型
    filteredErrorTypes.value = newVal
  }
}, { immediate: true })

const getSubjectName = (subjectId) => {
  const s = subjects.value.find(o => o.id === subjectId)
  return s ? s.name : '未知学科'
}

const continueAdd = () => {
  submittedQuestion.value = null
}

const removeImage = (index) => {
  uploadImagePaths.value.splice(index, 1)
}

onMounted(loadMetaData)
</script>

<style scoped>
.upload {
  max-width: 900px;
  margin: 0 auto;
}

/* 禁用上传页面卡片的hover效果 */
.upload :deep(.el-card) {
  transition: none;
}
.upload :deep(.el-card:hover) {
  transform: none;
  box-shadow: var(--shadow-sm) !important;
}

.step-content {
  min-height: 300px;
}

.loading {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 15px;
  padding: 60px;
}

.loading-icon {
  font-size: 64px;
  color: #409eff;
}

.loading-tips {
  text-align: center;
  color: #666;
}

.ocr-info {
  margin-top: 10px;
}

.manual-entry {
  margin-top: 20px;
  padding: 20px;
  background: #f5f7fa;
  border-radius: 8px;
}

.batch-item {
  display: flex;
  gap: 15px;
  padding: 10px;
}

.batch-text {
  flex: 1;
  font-size: 14px;
  line-height: 1.6;
}

.no-text {
  color: #999;
  font-style: italic;
}

.submitted-preview {
  margin-top: 20px;
  padding-top: 10px;
}

.submitted-preview h4 {
  margin: 10px 0;
  color: #409eff;
}

.preview-card {
  background: #f5f7fa;
}

.preview-item {
  margin-bottom: 10px;
}

.preview-item label {
  font-weight: bold;
  color: #666;
  margin-right: 8px;
}

.preview-actions {
  margin-top: 15px;
  display: flex;
  gap: 10px;
}

.manual-entry-placeholder {
  margin-top: 30px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 20px;
  border: 2px dashed #dcdfe6;
  border-radius: 8px;
  background: #f5f7fa;
}

.manual-entry-placeholder .el-image {
  max-width: 300px;
  max-height: 200px;
  opacity: 0.5;
  pointer-events: none;
}

.placeholder-tip {
  margin-top: 10px;
  color: #909399;
  font-size: 12px;
}

.page-title {
  font-size: 18px;
  font-weight: 600;
}

.detail-card {
  border: 1px solid #e4e7ed;
  border-radius: 8px;
  overflow: hidden;
}

.card-header-blue {
  background: linear-gradient(135deg, #409eff 0%, #66b1ff 100%);
  color: white;
  padding: 12px 16px;
  font-weight: 600;
  font-size: 14px;
}

.card-header-green {
  background: linear-gradient(135deg, #67c23a 0%, #85ce61 100%);
  color: white;
  padding: 12px 16px;
  font-weight: 600;
  font-size: 14px;
}

.card-header-orange {
  background: linear-gradient(135deg, #e6a23c 0%, #ebb563 100%);
  color: white;
  padding: 12px 16px;
  font-weight: 600;
  font-size: 14px;
}

.card-content {
  padding: 16px;
}

.submit-area {
  display: flex;
  justify-content: center;
  padding: 20px 0;
}

.image-preview-list {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  margin-top: 16px;
}

.preview-item {
  position: relative;
  width: 120px;
  height: 120px;
  border-radius: 8px;
  overflow: hidden;
  border: 2px solid #e4e7ed;
}

.preview-image {
  width: 100%;
  height: 100%;
}

.remove-btn {
  position: absolute;
  top: 4px;
  right: 4px;
  opacity: 0;
  transition: opacity 0.3s;
}

.preview-item:hover .remove-btn {
  opacity: 1;
}
</style>
