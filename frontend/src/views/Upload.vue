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
import { ref, reactive, onMounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { UploadFilled } from '@element-plus/icons-vue'
import { uploadApi, questionApi } from '@/api/question'

// 年级选项
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
const submitting = ref(false)
const submittedQuestion = ref(null)
const uploadRef = ref(null)

// 上传相关
const selectedFiles = ref([])
const uploadImagePaths = ref([])

const subjects = ref([])
const allTags = ref([])
const knowledgePoints = ref([])
const errorTypes = ref([])
const filteredErrorTypes = ref([])
const selectedKnowledgePoint = ref(null)

// 表单 - 学科/年级/学期从 localStorage 恢复
const form = reactive({
  subject_id: localStorage.getItem('lastSubjectId') ? parseInt(localStorage.getItem('lastSubjectId')) : null,
  parsed_question: '',
  answer: '',
  analysis: '',
  difficulty: 3,
  error_type: [],
  knowledge_point: '',
  grade: localStorage.getItem('lastGrade') ? parseInt(localStorage.getItem('lastGrade')) : null,
  semester: localStorage.getItem('lastSemester') ? parseInt(localStorage.getItem('lastSemester')) : null,
  tag_ids: [],
})

// 文件选择
const handleFileChange = (file, fileList) => {
  selectedFiles.value = fileList
}

const handleFileRemove = (file, fileList) => {
  selectedFiles.value = fileList
}

// 移除已上传图片
const removeImage = (index) => {
  uploadImagePaths.value.splice(index, 1)
}

// 加载元数据
const loadMetaData = async () => {
  try {
    const { data } = await questionApi.listSubjects()
    subjects.value = Array.isArray(data) ? data : (data.items || [])
  } catch (e) {
    console.error('加载学科失败:', e)
  }

  try {
    const { data } = await questionApi.listTags()
    allTags.value = Array.isArray(data) ? data : (data.items || [])
  } catch (e) {
    console.error('加载标签失败:', e)
  }
}

// 加载知识点
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

// 加载错误类型
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

// 监听学科变化
watch(() => form.subject_id, () => {
  form.knowledge_point = ''
  form.error_type = []
  selectedKnowledgePoint.value = null
  filteredErrorTypes.value = []
  fetchKnowledgePoints()
  fetchErrorTypes()
})

// 监听知识点变化
watch(() => form.knowledge_point, (newVal) => {
  if (!newVal) {
    selectedKnowledgePoint.value = null
    filteredErrorTypes.value = errorTypes.value
    return
  }
  const kp = knowledgePoints.value.find(k => k.name === newVal)
  if (kp && kp.error_types && kp.error_types.length > 0) {
    selectedKnowledgePoint.value = kp
    filteredErrorTypes.value = kp.error_types.map(et => ({ id: et.id, name: et.name }))
  } else {
    selectedKnowledgePoint.value = null
    filteredErrorTypes.value = errorTypes.value
  }
})

// 监听错误类型加载
watch(errorTypes, (newVal) => {
  if (selectedKnowledgePoint.value) {
    filteredErrorTypes.value = selectedKnowledgePoint.value.error_types.map(et => ({ id: et.id, name: et.name }))
  } else {
    filteredErrorTypes.value = newVal
  }
}, { immediate: true })

// 获取学科名称
const getSubjectName = (subjectId) => {
  const s = subjects.value.find(o => o.id === subjectId)
  return s ? s.name : '未知学科'
}

// 上传图片并提交
const submitQuestion = async () => {
  if (!form.subject_id) {
    ElMessage.warning('请选择学科')
    return
  }

  submitting.value = true

  // 先上传图片
  try {
    for (const file of selectedFiles.value) {
      const { data } = await uploadApi.uploadImage(file.raw)
      uploadImagePaths.value.push(data.image_path)
    }
  } catch (e) {
    console.error('图片上传失败:', e)
  }

  try {
    const submitData = {
      ...form,
      error_type: Array.isArray(form.error_type) ? form.error_type.join(',') : form.error_type,
      original_images: uploadImagePaths.value,
      original_image: uploadImagePaths.value[0] || null,
    }
    const { data } = await questionApi.create(submitData)
    ElMessage.success('错题保存成功')
    submittedQuestion.value = data

    // 保存学科/年级/学期到 localStorage
    localStorage.setItem('lastSubjectId', form.subject_id)
    if (form.grade) localStorage.setItem('lastGrade', form.grade)
    if (form.semester) localStorage.setItem('lastSemester', form.semester)

    // 重置表单（保留基本信息）
    form.parsed_question = ''
    form.answer = ''
    form.analysis = ''
    form.difficulty = 3
    form.error_type = []
    form.knowledge_point = ''
    form.tag_ids = []
    selectedFiles.value = []
    uploadImagePaths.value = []
    uploadRef.value?.clearFiles()
  } catch (error) {
    ElMessage.error('保存失败: ' + (error.message || '未知错误'))
  } finally {
    submitting.value = false
  }
}

// 继续录入
const continueAdd = () => {
  submittedQuestion.value = null
}

onMounted(() => {
  loadMetaData()
  if (form.subject_id) {
    fetchKnowledgePoints()
    fetchErrorTypes()
  }
})
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
