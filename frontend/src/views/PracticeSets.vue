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
        <el-date-picker
          v-model="filters.date_range"
          type="daterange"
          range-separator="至"
          start-placeholder="开始日期"
          end-placeholder="结束日期"
          value-format="YYYY-MM-DD"
          style="width: 400px"
          @change="fetchPracticeSets"
        />
      </div>

      <!-- 批量操作栏 -->
      <div class="batch-actions">
        <span class="selected-count">已选择 {{ selectedIds.length }} 项</span>
        <el-button
          type="primary"
          size="default"
          :disabled="selectedIds.length === 0"
          @click="batchDownloadPdf"
        >
          批量下载PDF
        </el-button>
        <el-button
          type="danger"
          size="default"
          :disabled="selectedIds.length === 0"
          @click="batchDelete"
        >
          批量删除
        </el-button>
      </div>

      <!-- 练习集列表 -->
      <el-table
        v-if="practiceSets.length"
        :data="practiceSets"
        row-key="id"
        @selection-change="handleSelectionChange"
        style="width: 100%"
      >
        <el-table-column type="selection" width="40" />
        <el-table-column prop="name" label="名称" width="1200">
          <template #default="{ row }">
            <span class="ps-name">{{ row.name }}</span>
            <el-tag :type="row.question_type === 'original' ? 'primary' : 'success'" :style="{ marginLeft: '8px', fontSize: '14px' }">
              {{ row.question_type === 'original' ? '原题' : '相似题' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="subject_name" label="学科" width="100" />
        <el-table-column prop="source_type" label="类型" width="100">
          <template #default="{ row }">
            {{ row.source_type === 'word' ? '单词复习' : '错题练习' }}
          </template>
        </el-table-column>
        <el-table-column prop="total_questions" label="题目数" width="80" align="center" />
        <el-table-column prop="review_count" label="复习次数" width="80" align="center" />
        <el-table-column prop="accuracy" label="正确率" width="80" align="center">
          <template #default="{ row }">
            <span v-if="row.source_type === 'word' && row.word_review_stats?.accuracy != null">
              {{ row.word_review_stats.accuracy }}%
            </span>
            <span v-else-if="row.accuracy != null">{{ row.accuracy }}%</span>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column prop="reviewed" label="状态" width="80" align="center">
          <template #default="{ row }">
            <el-tag :type="row.reviewed ? 'success' : 'info'" :style="{ fontSize: '14px' }">
              {{ row.reviewed ? '已复习' : '未复习' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="160">
          <template #default="{ row }">
            {{ formatDate(row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="420" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" size="default" @click="showDetail(row)">查看详情</el-button>
            <el-button v-if="row.pdf_path" type="primary" size="default" @click="downloadPdf(row)">下载PDF</el-button>
            <el-button v-else type="info" size="default" disabled>无PDF</el-button>
            <el-button type="warning" size="default" @click="markReviewed(row)" :disabled="row.reviewed">标记已复习</el-button>
            <el-button type="danger" size="default" @click="deletePracticeSet(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>

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

    <!-- 批改弹窗 -->
    <el-dialog v-model="gradingDialogVisible" title="批改练习集" width="600px" destroy-on-close>
      <!-- 整体批改 -->
      <div v-if="gradingStep === 'overall'" class="grading-overall">
        <p class="grading-tip">共 {{ currentPsQuestions.length }} 道题目</p>
        <p class="grading-question">本次练习整体正确情况如何？</p>
        <div class="grading-buttons">
          <el-button type="success" size="large" @click="handleOverallGrading(true)">全部正确</el-button>
          <el-button type="danger" size="large" @click="handleOverallGrading(false)">有错误</el-button>
        </div>
      </div>

      <!-- 逐题批改 -->
      <div v-if="gradingStep === 'detail'" class="grading-detail">
        <div class="grading-progress">
          <span>{{ gradingCurrentIndex + 1 }} / {{ currentPsQuestions.length }}</span>
          <span class="grading-accuracy">正确率: {{ getGradingAccuracy() }}%</span>
        </div>
        <div class="grading-question-item">
          <p class="question-text">{{ currentPsQuestions[gradingCurrentIndex]?.question_text || currentPsQuestions[gradingCurrentIndex]?.original_question_text }}</p>
          <p class="question-answer">答案: {{ currentPsQuestions[gradingCurrentIndex]?.answer || currentPsQuestions[gradingCurrentIndex]?.original_answer }}</p>
        </div>
        <div class="grading-question-buttons">
          <el-button type="success" size="large" @click="handleQuestionGrading(currentPsQuestions[gradingCurrentIndex].question_id, true)">正确</el-button>
          <el-button type="danger" size="large" @click="handleQuestionGrading(currentPsQuestions[gradingCurrentIndex].question_id, false)">错误</el-button>
        </div>
      </div>

      <!-- 图片上传（批改完成后） -->
      <div v-if="gradingStep === 'upload'" class="grading-upload">
        <p class="grading-tip">批改完成，正确率: {{ getGradingAccuracy() }}%</p>
        <p class="grading-subtip">可选：上传复习完成的图片</p>
        <el-upload
          ref="uploadRef"
          :auto-upload="false"
          :multiple="true"
          :limit="9"
          accept="image/*"
          list-type="picture-card"
          :on-change="handleImageChange"
          :on-remove="handleImageRemove"
          :file-list="reviewImages"
        >
          <el-icon><Plus /></el-icon>
        </el-upload>
      </div>

      <template #footer>
        <el-button v-if="gradingStep === 'detail'" @click="gradingStep = 'overall'">返回</el-button>
        <el-button @click="gradingDialogVisible = false">取消</el-button>
        <el-button v-if="gradingStep === 'upload'" type="primary" @click="submitGrading" :loading="uploadLoading">完成</el-button>
      </template>
    </el-dialog>

    <!-- 复习完成上传图片弹窗 -->
    <el-dialog v-model="uploadDialogVisible" title="上传复习完成图片" width="600px" destroy-on-close>
      <div class="upload-tips">请上传复习完成的图片（可上传多张）</div>
      <el-upload
        ref="uploadRef"
        :auto-upload="false"
        :multiple="true"
        :limit="9"
        accept="image/*"
        list-type="picture-card"
        :on-change="handleImageChange"
        :on-remove="handleImageRemove"
        :file-list="reviewImages"
      >
        <el-icon><Plus /></el-icon>
      </el-upload>
      <template #footer>
        <el-button @click="uploadDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="confirmMarkReviewed" :loading="uploadLoading">确认</el-button>
      </template>
    </el-dialog>

    <!-- 练习集详情弹窗 -->
    <el-dialog v-model="detailDialogVisible" :title="detailData.name || '练习集详情'" width="900px" @opened="onDetailDialogOpened">
      <el-tabs v-model="detailActiveTab">
        <!-- 详情页 -->
        <el-tab-pane label="详情" name="detail">
          <div class="detail-info">
            <el-descriptions :column="2" border>
              <el-descriptions-item label="名称">{{ detailData.name }}</el-descriptions-item>
              <el-descriptions-item label="学科">{{ detailData.subject_name }}</el-descriptions-item>
              <el-descriptions-item label="类型">{{ detailData.source_type === 'word' ? '单词复习' : '错题练习' }}</el-descriptions-item>
              <el-descriptions-item label="题目数">{{ detailData.total_questions }}</el-descriptions-item>
              <el-descriptions-item label="复习次数">{{ detailData.review_count }}</el-descriptions-item>
              <el-descriptions-item label="备注" :span="2">{{ detailData.notes || '无' }}</el-descriptions-item>
            </el-descriptions>

            <!-- 单词复习统计 -->
            <div v-if="detailData.source_type === 'word' && detailData.word_review_stats" class="word-stats">
              <h4>单词复习统计</h4>
              <el-descriptions :column="3" border>
                <el-descriptions-item label="总单词数">{{ detailData.word_review_stats.total_count }}</el-descriptions-item>
                <el-descriptions-item label="正确数">{{ detailData.word_review_stats.correct_count }}</el-descriptions-item>
                <el-descriptions-item label="准确率">{{ detailData.word_review_stats.accuracy }}%</el-descriptions-item>
                <el-descriptions-item label="用时" :span="2">{{ formatDuration(detailData.word_review_stats?.duration ?? 0) }}</el-descriptions-item>
              </el-descriptions>
            </div>

            <!-- 错题练习集复习图片 -->
            <div v-if="detailData.source_type !== 'word'" class="review-images">
              <h4>
                复习完成图片
                <el-button v-if="!isEditingImages" type="primary" size="small" style="margin-left: 12px;" @click="startEditImages">编辑图片</el-button>
                <template v-else>
                  <el-button type="primary" size="small" @click="saveEditImages" :loading="imageEditLoading">保存</el-button>
                  <el-button size="small" @click="cancelEditImages">取消</el-button>
                </template>
              </h4>
              <div v-if="!isEditingImages" class="image-grid">
                <template v-if="detailData.review_images && detailData.review_images.length > 0">
                  <div v-for="(img, idx) in detailData.review_images" :key="idx" class="image-item">
                    <el-image
                      :src="'/uploads/' + img"
                      :preview-src-list="detailData.review_images.map(i => '/uploads/' + i)"
                      fit="cover"
                      style="width: 120px; height: 120px; border-radius: 8px; cursor: pointer;"
                    />
                  </div>
                </template>
                <el-empty v-else description="暂无复习图片" :image-size="60" />
              </div>
              <!-- 编辑模式 -->
              <div v-else class="image-edit-grid">
                <el-upload
                  ref="imageEditUploadRef"
                  :auto-upload="false"
                  :multiple="true"
                  :limit="9"
                  accept="image/*"
                  list-type="picture-card"
                  :on-change="handleEditImageChange"
                  :on-remove="handleEditImageRemove"
                  :file-list="editImagesFileList"
                >
                  <el-icon><Plus /></el-icon>
                </el-upload>
              </div>
            </div>

            <!-- 错题练习集题目列表 -->
            <div v-if="detailData.source_type !== 'word' && detailData.questions && detailData.questions.length > 0" class="question-list-section">
              <h4>题目列表</h4>
              <el-table :data="detailData.questions" border style="width: 100%">
                <el-table-column type="index" label="序号" width="60" align="center" />
                <el-table-column label="原题" min-width="200">
                  <template #default="{ row }">
                    <div v-if="row.original_question_text" class="original-question">
                      {{ row.original_question_text.substring(0, 50) }}{{ row.original_question_text.length > 50 ? '...' : '' }}
                    </div>
                    <el-image
                      v-if="row.original_image"
                      :src="'/uploads/' + row.original_image"
                      fit="contain"
                      style="width: 40px; height: 40px; cursor: pointer;"
                      @click="previewImage(row.original_image)"
                    />
                    <span v-if="!row.original_question_text && !row.original_image" class="text-muted">-</span>
                  </template>
                </el-table-column>
                <el-table-column label="答案" min-width="100">
                  <template #default="{ row }">
                    {{ row.original_answer || '-' }}
                  </template>
                </el-table-column>
                <el-table-column label="批改" width="80" align="center">
                  <template #default="{ row }">
                    <el-tag v-if="row.is_correct === true" type="success" size="small">正确</el-tag>
                    <el-tag v-else-if="row.is_correct === false" type="danger" size="small">错误</el-tag>
                    <span v-else class="text-muted">-</span>
                  </template>
                </el-table-column>
              </el-table>
            </div>
          </div>
        </el-tab-pane>

        <!-- 单词练习页（仅单词复习类型显示） -->
        <el-tab-pane v-if="detailData.source_type === 'word'" label="单词练习" name="words">
          <div class="word-practice">
            <div class="word-stats-bar">
              <span>总单词数：{{ detailData.word_review_stats?.total_count || 0 }}</span>
              <span>正确：{{ detailData.word_review_stats?.correct_count || 0 }}</span>
              <span>错误：{{ (detailData.word_review_stats?.total_count || 0) - (detailData.word_review_stats?.correct_count || 0) }}</span>
              <span>用时：{{ formatDuration(detailData.word_review_stats?.duration || 0) }}</span>
            </div>
            <div class="word-list">
              <div v-for="(q, idx) in detailData.questions" :key="q.id" class="word-item" :class="{'is-correct': q.is_correct, 'is-wrong': !q.is_correct}">
                <div class="word-header">
                  <span class="word-index">{{ idx + 1 }}</span>
                  <span class="word-english">{{ q.question_text }}</span>
                  <span v-if="q.phonetic" class="word-phonetic">{{ q.phonetic }}</span>
                  <el-tag v-for="tag in q.tags" :key="tag.id" size="small" type="info" style="margin-left: 8px;">{{ tag.name }}</el-tag>
                  <span class="word-result" :class="q.is_correct ? 'correct' : 'wrong'">
                    {{ q.is_correct ? '✓ 正确' : '✗ 错误' }}
                  </span>
                </div>
                <div class="word-content">
                  <div class="word-answer">
                    <span class="label">答案：</span>
                    <span class="value">{{ q.answer }}</span>
                  </div>
                  <div v-if="!q.is_correct && q.user_answer" class="word-user-answer">
                    <span class="label">你的答案：</span>
                    <span class="value wrong">{{ q.user_answer }}</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </el-tab-pane>

        <!-- 编辑页 -->
        <el-tab-pane label="编辑" name="edit">
          <el-form :model="detailForm" label-width="80px">
            <el-form-item label="名称">
              <el-input v-model="detailForm.name" placeholder="请输入练习集名称" />
            </el-form-item>
            <el-form-item label="备注">
              <el-input v-model="detailForm.notes" type="textarea" :rows="4" placeholder="请输入备注" />
            </el-form-item>
          </el-form>
          <div style="text-align: right;">
            <el-button type="primary" @click="saveDetail" :loading="detailLoading">保存</el-button>
          </div>
        </el-tab-pane>
      </el-tabs>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, nextTick } from 'vue'
import { ElMessage, ElMessageBox, ElLoading } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import { questionApi } from '@/api/question'

const practiceSets = ref([])
const subjects = ref([])
const total = ref(0)
const selectedIds = ref([])
const filters = reactive({
  subject_id: null,
  reviewed: null,
  date_range: null,
})
const pagination = reactive({
  page: 1,
  limit: 1000,
})

// 复习完成上传相关
const uploadDialogVisible = ref(false)
const uploadLoading = ref(false)
const reviewImages = ref([])
const currentReviewPs = ref(null)
const uploadRef = ref()

// 详情弹窗相关
const detailDialogVisible = ref(false)
const detailActiveTab = ref('detail')
const detailData = ref({})
const detailLoading = ref(false)
const detailForm = reactive({
  name: '',
  notes: ''
})

// 图片编辑相关
const isEditingImages = ref(false)
const imageEditLoading = ref(false)
const editImagesFileList = ref([])
const editImagesUploaded = ref([])
const imageEditUploadRef = ref()


const fetchPracticeSets = async () => {
  try {
    const params = {
      skip: (pagination.page - 1) * pagination.limit,
      limit: pagination.limit,
      subject_id: filters.subject_id,
      reviewed: filters.reviewed,
    }
    if (filters.date_range && filters.date_range.length === 2) {
      params.start_date = filters.date_range[0]
      params.end_date = filters.date_range[1]
    }
    const { data } = await questionApi.listPracticeSets(params)
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

const handleSelectionChange = (selection) => {
  selectedIds.value = selection.map(row => row.id)
}

const downloadPdf = (ps) => {
  if (ps.pdf_path) {
    window.open(`/uploads/${ps.pdf_path}`, '_blank')
  }
}

const markReviewed = async (ps) => {
  currentReviewPs.value = ps

  // 单词练习集直接标记已复习
  if (ps.source_type === 'word') {
    try {
      await questionApi.markPracticeSetReviewed(ps.id)
      ElMessage.success('已标记为复习')
      fetchPracticeSets()
    } catch (error) {
      ElMessage.error('操作失败')
    }
    return
  }

  // 错题练习集进入批改流程
  gradingDialogVisible.value = true
  initGrading(ps)
}

// ============ 批改相关 ============
const gradingDialogVisible = ref(false)
const gradingStep = ref('overall') // 'overall' | 'detail' | 'upload'
const gradingCurrentIndex = ref(0)
const gradingResults = ref({}) // { questionId: true/false }
const currentPsQuestions = ref([])

const initGrading = async (ps) => {
  // 获取练习集详情（含题目）
  try {
    const { data } = await questionApi.getPracticeSet(ps.id)
    currentPsQuestions.value = data.questions || []
    gradingResults.value = {}
    gradingCurrentIndex.value = 0
    gradingStep.value = 'overall'
  } catch (error) {
    ElMessage.error('获取练习集详情失败')
    gradingDialogVisible.value = false
  }
}

const handleOverallGrading = (isAllCorrect) => {
  if (isAllCorrect) {
    // 整体全对
    currentPsQuestions.value.forEach(q => {
      gradingResults.value[q.question_id] = true
    })
    gradingStep.value = 'upload'
  } else {
    // 进入逐题批改
    gradingStep.value = 'detail'
  }
}

const handleQuestionGrading = (questionId, isCorrect) => {
  gradingResults.value[questionId] = isCorrect
  gradingCurrentIndex.value++

  if (gradingCurrentIndex.value >= currentPsQuestions.value.length) {
    // 全部批改完成，进入图片上传
    gradingStep.value = 'upload'
  }
}

const getGradingAccuracy = () => {
  const total = currentPsQuestions.value.length
  if (total === 0) return 0
  const correct = Object.values(gradingResults.value).filter(v => v === true).length
  return Math.round(correct / total * 100)
}

const submitGrading = async () => {
  // 构建批改结果
  const questionResults = Object.entries(gradingResults.value).map(([question_id, is_correct]) => ({
    question_id: parseInt(question_id),
    is_correct
  }))

  // 先提交批改
  try {
    await questionApi.markPracticeSetReviewedWithGrading(
      currentReviewPs.value.id,
      questionResults
    )
    ElMessage.success('批改完成')
    gradingDialogVisible.value = false

    // 如果有图片，进入图片上传；否则完成
    if (reviewImages.value.length > 0) {
      uploadDialogVisible.value = true
    } else {
      fetchPracticeSets()
    }
  } catch (error) {
    ElMessage.error('批改提交失败')
  }
}

const handleImageChange = (file, fileList) => {
  reviewImages.value = fileList
}

const handleImageRemove = (file, fileList) => {
  reviewImages.value = fileList
}

const confirmMarkReviewed = async () => {
  if (!currentReviewPs.value) return

  try {
    uploadLoading.value = true

    // 如果有图片，先上传（使用简单上传接口，不调用OCR/LLM）
    let imagePaths = []
    if (reviewImages.value.length > 0) {
      const formData = new FormData()
      reviewImages.value.forEach(file => {
        formData.append('files', file.raw)
      })

      // 使用简单批量上传接口，不进行OCR识别
      const uploadRes = await fetch('/api/upload/batch-simple', {
        method: 'POST',
        body: formData,
      })
      const uploadData = await uploadRes.json()
      if (uploadData.images) {
        // 只提取图片路径
        imagePaths = uploadData.images
          .filter(img => img.success)
          .map(img => img.image_path)
      }
    }

    // 更新练习集图片（不重复标记已复习）
    await questionApi.updatePracticeSetReviewImages(currentReviewPs.value.id, imagePaths)

    uploadDialogVisible.value = false

    // 显示完成庆祝
    await ElMessageBox.alert(
      '<div style="text-align: center;">' +
      '<div style="font-size: 80px; margin-bottom: 10px;">🎉</div>' +
      '<div style="font-size: 24px; font-weight: bold; color: #67c23a;">复习完成！</div>' +
      '<div style="font-size: 16px; color: #909399; margin-top: 10px;">继续保持，下次会更棒！</div>' +
      '</div>',
      '恭喜',
      {
        confirmButtonText: '确定',
        dangerouslyUseHTMLString: true,
      }
    )

    fetchPracticeSets()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('操作失败')
    }
  } finally {
    uploadLoading.value = false
  }
}

// 查看详情
const showDetail = async (ps) => {
  try {
    const { data } = await questionApi.getPracticeSetDetail(ps.id)
    detailData.value = data
    detailForm.name = data.name
    detailForm.notes = data.notes || ''
    detailDialogVisible.value = true
  } catch (error) {
    ElMessage.error('获取详情失败')
  }
}

// 弹窗打开后确保详情tab选中
const onDetailDialogOpened = async () => {
  await nextTick()
  detailActiveTab.value = 'detail'
}

// 保存详情
const saveDetail = async () => {
  try {
    detailLoading.value = true
    await questionApi.updatePracticeSet(detailData.value.id, {
      name: detailForm.name,
      notes: detailForm.notes,
    })
    ElMessage.success('保存成功')
    detailDialogVisible.value = false
    fetchPracticeSets()
  } catch (error) {
    ElMessage.error('保存失败')
  } finally {
    detailLoading.value = false
  }
}

// 格式化时长
const formatDuration = (seconds) => {
  if (!seconds && seconds !== 0) return '-'
  if (seconds === 0) return '0秒'
  const mins = Math.floor(seconds / 60)
  const secs = seconds % 60
  return `${mins}分${secs}秒`
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

const previewImage = (imagePath) => {
  if (imagePath) {
    window.open('/uploads/' + imagePath, '_blank')
  }
}

// 图片编辑相关
const startEditImages = () => {
  // 初始化已上传的图片列表
  editImagesUploaded.value = [...(detailData.value.review_images || [])]
  editImagesFileList.value = (detailData.value.review_images || []).map((img, idx) => ({
    name: img,
    url: '/uploads/' + img,
    status: 'success',
    isOld: true,
  }))
  isEditingImages.value = true
}

const handleEditImageChange = (file, fileList) => {
  editImagesFileList.value = fileList
}

const handleEditImageRemove = (file, fileList) => {
  editImagesFileList.value = fileList
}

const cancelEditImages = () => {
  isEditingImages.value = false
  editImagesFileList.value = []
  editImagesUploaded.value = []
}

const saveEditImages = async () => {
  try {
    imageEditLoading.value = true

    // 分离新上传的文件和已有的图片
    const newFiles = editImagesFileList.value.filter(f => !f.isOld)
    let newImagePaths = [...editImagesUploaded.value]

    // 上传新文件
    if (newFiles.length > 0) {
      const formData = new FormData()
      newFiles.forEach(file => {
        formData.append('files', file.raw)
      })

      const uploadRes = await fetch('/api/upload/batch-simple', {
        method: 'POST',
        body: formData,
      })
      const uploadData = await uploadRes.json()
      if (uploadData.images) {
        const uploadedPaths = uploadData.images
          .filter(img => img.success)
          .map(img => img.image_path)
        newImagePaths = [...editImagesUploaded.value, ...uploadedPaths]
      }
    }

    // 更新练习集图片
    await questionApi.updatePracticeSetReviewImages(detailData.value.id, newImagePaths)

    ElMessage.success('图片更新成功')
    isEditingImages.value = false

    // 刷新详情
    const { data } = await questionApi.getPracticeSetDetail(detailData.value.id)
    detailData.value = data
  } catch (error) {
    ElMessage.error('更新图片失败')
  } finally {
    imageEditLoading.value = false
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

:deep(.el-range-separator) {
  width: 5% !important;
}

:deep(.el-date-editor) {
  width: 400px !important;
}

:deep(.el-date-editor .el-input__wrapper) {
  width: 400px !important;
}

:deep(.el-date-editor.el-range-editor) {
  width: 400px !important;
  max-width: 400px !important;
  min-width: 400px !important;
}

:deep(.el-date-editor.el-range-editor .el-range-input) {
  width: 100% !important;
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

.upload-tips {
  margin-bottom: 15px;
  color: #909399;
  font-size: 14px;
}

.detail-info {
  padding: 10px 0;
}

.detail-info h4 {
  margin: 20px 0 10px;
  color: #303133;
  font-size: 16px;
}

.word-stats {
  margin-top: 20px;
}

.review-images {
  margin-top: 20px;
}

.image-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.image-item {
  position: relative;
}

.image-edit-grid {
  min-height: 150px;
}

.question-list-section {
  margin-top: 20px;
}

.original-question {
  font-size: 13px;
  color: #606266;
  line-height: 1.4;
}

/* 单词练习样式 */
.word-practice {
  padding: 10px 0;
}

.word-stats-bar {
  display: flex;
  gap: 20px;
  padding: 12px 15px;
  background-color: #f5f7fa;
  border-radius: 4px;
  margin-bottom: 20px;
  font-size: 14px;
  color: #606266;
}

.word-stats-bar span {
  margin-right: 15px;
}

.word-list {
  max-height: 500px;
  overflow-y: auto;
}

.word-item {
  border: 1px solid #ebeef5;
  border-radius: 8px;
  padding: 12px 15px;
  margin-bottom: 10px;
  background-color: #fff;
}

.word-item.is-correct {
  border-left: 4px solid #67c23a;
}

.word-item.is-wrong {
  border-left: 4px solid #f56c6c;
}

.word-header {
  display: flex;
  align-items: center;
  margin-bottom: 8px;
}

.word-index {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  background-color: #409eff;
  color: #fff;
  border-radius: 50%;
  font-size: 12px;
  margin-right: 10px;
}

.word-english {
  font-weight: bold;
  font-size: 16px;
  color: #303133;
}

.word-phonetic {
  margin-left: 8px;
  color: #909399;
  font-size: 13px;
}

.word-result {
  margin-left: auto;
  font-weight: bold;
  font-size: 14px;
}

.word-result.correct {
  color: #67c23a;
}

.word-result.wrong {
  color: #f56c6c;
}

.word-content {
  padding-left: 34px;
}

.word-answer {
  margin-bottom: 4px;
}

.word-answer .label,
.word-user-answer .label {
  color: #909399;
  font-size: 13px;
}

.word-answer .value {
  color: #303133;
  font-size: 14px;
}

.word-user-answer .value.wrong {
  color: #f56c6c;
}

/* 批改弹窗样式 */
.grading-overall {
  text-align: center;
  padding: 30px 0;
}

.grading-tip {
  font-size: 16px;
  color: #606266;
  margin-bottom: 20px;
}

.grading-subtip {
  font-size: 14px;
  color: #909399;
  margin-bottom: 15px;
}

.grading-question {
  font-size: 18px;
  font-weight: bold;
  color: #303133;
  margin-bottom: 30px;
}

.grading-buttons {
  display: flex;
  gap: 20px;
  justify-content: center;
}

.grading-detail {
  padding: 10px 0;
}

.grading-progress {
  font-size: 16px;
  color: #606266;
  margin-bottom: 20px;
  display: flex;
  justify-content: space-between;
}

.grading-accuracy {
  color: #409eff;
  font-weight: bold;
}

.grading-question-item {
  background: #f5f7fa;
  padding: 20px;
  border-radius: 8px;
  margin-bottom: 20px;
}

.grading-question-item .question-text {
  font-size: 16px;
  margin-bottom: 10px;
  color: #303133;
}

.grading-question-item .question-answer {
  font-size: 14px;
  color: #67c23a;
}

.grading-question-buttons {
  display: flex;
  gap: 20px;
  justify-content: center;
}

.grading-upload {
  padding: 10px 0;
}
</style>
