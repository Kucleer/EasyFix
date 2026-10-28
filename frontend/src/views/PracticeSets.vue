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
            {{ row.source_type === 'word' ? '单词复习' : (row.source_type === 'reading' ? '阅读理解' : '错题练习') }}
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
            <el-button type="success" size="default" @click="markReviewed(row)" :disabled="row.reviewed">批改</el-button>
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
    <el-dialog v-model="gradingDialogVisible" title="批改练习集" width="900px" destroy-on-close>
      <!-- 进度头部 -->
      <div class="grading-header">
        <div class="grading-header-left">
          <div class="grading-title">批改进度</div>
          <div class="grading-progress-text">
            <span class="text-green-600 font-bold">{{ gradedCount }}</span> / {{ currentPsQuestions.length }} 已批改
          </div>
        </div>
        <div class="grading-header-right">
          <div class="accuracy-display">
            <span class="accuracy-value">{{ getGradingAccuracy() }}%</span>
            <span class="accuracy-label">正确率</span>
          </div>
        </div>
      </div>

      <!-- 进度条 -->
      <div class="grading-progress-bar">
        <div class="progress-bar">
          <div class="progress-fill" :style="{ width: (gradedCount / currentPsQuestions.length * 100) + '%' }"></div>
        </div>
        <div class="grading-stats">
          <span class="stat-correct">✓ 正确 {{ correctCount }}</span>
          <span class="stat-wrong">✗ 错误 {{ wrongCount }}</span>
          <span class="stat-pending">○ 待批改 {{ currentPsQuestions.length - gradedCount }}</span>
        </div>
      </div>

      <!-- 题目列表 -->
      <div class="grading-question-list">
        <div
          v-for="(question, index) in currentPsQuestions"
          :key="question.question_id"
          :class="['question-row', getQuestionRowClass(question.question_id)]"
        >
          <div class="question-number">{{ index + 1 }}</div>
          <div class="question-content">
            <div class="question-text">
              <template v-if="question.original_question_text"><MathText :text="question.original_question_text" /></template>
              <template v-else-if="question.original_image">
                <el-image
                  :src="'/uploads/' + question.original_image"
                  fit="contain"
                  style="max-width: 60px; max-height: 60px; cursor: pointer;"
                  @click="previewImage(question.original_image)"
                />
              </template>
              <template v-else><span class="text-gray-400">无题目内容</span></template>
            </div>
            <div class="question-answer">
              <span class="answer-label">答案：</span>
              <span class="answer-badge"><MathText :text="question.original_answer || '-'" /></span>
            </div>
          </div>
          <div class="question-actions">
            <button
              :class="['btn-correct', { active: gradingResults[question.question_id] === true }]"
              @click="handleQuestionGrading(question.question_id, true)"
            >✓ 正确</button>
            <button
              :class="['btn-wrong', { active: gradingResults[question.question_id] === false }]"
              @click="handleQuestionGrading(question.question_id, false)"
            >✗ 错误</button>
            <el-button type="primary" @click="showQuestionDetail(question)">查看原题</el-button>
          </div>
        </div>
      </div>

      <template #footer>
        <div class="grading-footer">
          <div class="footer-stats">
            <span class="text-green-600 font-bold">{{ correctCount }}</span> 正确,
            <span class="text-red-600 font-bold">{{ wrongCount }}</span> 错误
          </div>
          <div class="footer-buttons">
            <el-button @click="gradingDialogVisible = false">返回</el-button>
            <el-button
              type="primary"
              @click="submitGrading"
              :disabled="gradedCount < currentPsQuestions.length"
            >提交批改结果</el-button>
          </div>
        </div>
      </template>
    </el-dialog>

    <!-- 查看原题弹层（二合一） -->
    <el-dialog v-model="gradingDetailDialogVisible" :title="isEditingGradingQuestion ? '编辑原题' : '查看原题'" width="800px" destroy-on-close>
      <!-- 查看模式 -->
      <div v-if="gradingQuestionDetail && !isEditingGradingQuestion" class="question-detail-content">
        <el-row :gutter="20">
          <el-col :span="12">
            <div class="detail-block">
              <div class="detail-label">原题</div>
              <div class="detail-value">
                <p v-if="gradingQuestionDetail.original_question_text"><MathText :text="gradingQuestionDetail.original_question_text" /></p>
                <el-image
                  v-if="gradingQuestionDetail.original_image"
                  :src="'/uploads/' + gradingQuestionDetail.original_image"
                  fit="contain"
                  style="max-width: 100%; max-height: 200px;"
                  :preview-src-list="['/uploads/' + gradingQuestionDetail.original_image]"
                />
                <span v-if="!gradingQuestionDetail.original_question_text && !gradingQuestionDetail.original_image" class="text-gray-400">无</span>
              </div>
            </div>
          </el-col>
          <el-col :span="12">
            <div class="detail-block">
              <div class="detail-label">答案</div>
              <div class="detail-value answer-value">
                <MathText :text="gradingQuestionDetail.original_answer || '-'" />
              </div>
            </div>
            <!-- 阅读理解选项 -->
            <div v-if="gradingQuestionDetail.is_reading_question" class="detail-block mt-4">
              <div class="detail-label">选项</div>
              <div class="detail-value reading-options">
                <div class="option-row">{{ formatOption('A', gradingQuestionDetail.option_a) }}</div>
                <div class="option-row">{{ formatOption('B', gradingQuestionDetail.option_b) }}</div>
                <div class="option-row">{{ formatOption('C', gradingQuestionDetail.option_c) }}</div>
                <div class="option-row">{{ formatOption('D', gradingQuestionDetail.option_d) }}</div>
              </div>
            </div>
          </el-col>
        </el-row>
        <div class="detail-meta">
          <span>题目ID: {{ gradingQuestionDetail.question_id }}</span>
          <span v-if="gradingQuestionDetail.knowledge_point">知识点: {{ gradingQuestionDetail.knowledge_point }}</span>
          <span v-if="gradingQuestionDetail.error_type">错误类型: {{ gradingQuestionDetail.error_type }}</span>
        </div>
      </div>

      <!-- 编辑模式 -->
      <div v-if="gradingQuestionDetail && isEditingGradingQuestion" class="question-edit-content">
        <el-form :model="gradingQuestionEditForm" label-width="80px">
          <el-form-item label="题目内容">
            <MathEditor v-model="gradingQuestionEditForm.original_question_text" :rows="3" placeholder="请输入题目内容" />
          </el-form-item>
          <el-form-item label="题目图片">
            <div v-if="gradingQuestionDetail.original_image" class="mb-2">
              <el-image
                :src="'/uploads/' + gradingQuestionDetail.original_image"
                fit="contain"
                style="max-width: 200px; max-height: 150px;"
              />
            </div>
            <el-input v-model="gradingQuestionEditForm.original_image" placeholder="图片路径（可选）" />
          </el-form-item>
          <el-form-item label="答案">
            <MathEditor v-model="gradingQuestionEditForm.original_answer" :rows="3" placeholder="请输入答案" />
          </el-form-item>
          <el-form-item label="知识点">
            <el-input v-model="gradingQuestionEditForm.knowledge_point" placeholder="请输入知识点" />
          </el-form-item>
          <el-form-item label="错误类型">
            <el-input v-model="gradingQuestionEditForm.error_type" placeholder="请输入错误类型" />
          </el-form-item>
          <el-form-item label="难度">
            <el-rate v-model="gradingQuestionEditForm.difficulty" :max="5" show-text :texts="['1星', '2星', '3星', '4星', '5星']" />
          </el-form-item>
        </el-form>
      </div>

      <template #footer>
        <el-button @click="gradingDetailDialogVisible = false">关闭</el-button>
        <template v-if="!isEditingGradingQuestion">
          <el-button type="primary" @click="startEditGradingQuestion">编辑此题</el-button>
        </template>
        <template v-else>
          <el-button @click="cancelEditGradingQuestion">取消</el-button>
          <el-button type="success" @click="saveGradingQuestion" :loading="gradingEditLoading">保存</el-button>
        </template>
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
    <el-dialog v-model="detailDialogVisible" :title="detailData.name || '练习集详情'" width="1200px" class="practice-detail-dialog" @opened="onDetailDialogOpened">
      <el-tabs v-model="detailActiveTab">
        <!-- 详情页 -->
        <el-tab-pane label="详情" name="detail">
          <div class="detail-info">
            <div class="detail-card">
              <div class="card-header-gray">基本信息</div>
              <div class="card-content">
                <el-descriptions :column="2" border size="small">
                  <el-descriptions-item label="名称">{{ detailData.name }}</el-descriptions-item>
                  <el-descriptions-item label="学科">{{ detailData.subject_name }}</el-descriptions-item>
                  <el-descriptions-item label="类型">{{ detailData.source_type === 'word' ? '单词复习' : (detailData.source_type === 'reading' ? '阅读理解' : '错题练习') }}</el-descriptions-item>
                  <el-descriptions-item label="题目数">{{ detailData.total_questions }}</el-descriptions-item>
                  <el-descriptions-item label="复习次数">{{ detailData.review_count }}</el-descriptions-item>
                  <el-descriptions-item label="备注" :span="2">{{ detailData.notes || '无' }}</el-descriptions-item>
                </el-descriptions>
              </div>
            </div>

            <!-- 单词复习统计 -->
            <div v-if="detailData.source_type === 'word' && detailData.word_review_stats" class="word-stats">
              <div class="detail-card">
                <div class="card-header-green">单词复习统计</div>
                <div class="card-content">
                  <el-descriptions :column="4" border size="small">
                    <el-descriptions-item label="复习类型">{{ getReviewTypeLabel(detailData.word_review_stats.review_type) }}</el-descriptions-item>
                    <el-descriptions-item label="总单词数">{{ detailData.word_review_stats.total_count }}</el-descriptions-item>
                    <el-descriptions-item label="正确数">{{ detailData.word_review_stats.correct_count }}</el-descriptions-item>
                    <el-descriptions-item label="准确率">{{ detailData.word_review_stats.accuracy }}%</el-descriptions-item>
                  </el-descriptions>
                </div>
              </div>
            </div>

            <!-- 错题练习集复习图片 -->
            <div v-if="detailData.source_type !== 'word'" class="review-images">
              <div class="detail-card">
                <div class="card-header-orange">
                  <span>复习完成图片</span>
                  <div>
                    <template v-if="!isEditingImages">
                      <el-button type="primary" size="small" @click="startEditImages">编辑图片</el-button>
                    </template>
                    <template v-else>
                      <el-button type="primary" size="small" @click="saveEditImages" :loading="imageEditLoading">保存</el-button>
                      <el-button size="small" @click="cancelEditImages">取消</el-button>
                    </template>
                  </div>
                </div>
                <div class="card-content">
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
              </div>
            </div>

            <!-- 错题练习集题目列表 -->
            <div v-if="detailData.source_type !== 'word' && detailData.questions && detailData.questions.length > 0" class="question-list-section">
              <div class="detail-card">
                <div class="card-header-blue">题目列表</div>
                <div class="card-content">
                  <div class="question-cards">
                    <div
                      v-for="(row, idx) in detailData.questions"
                      :key="row.id"
                      :class="['question-card', row.is_correct === true ? 'card-correct' : row.is_correct === false ? 'card-wrong' : 'card-pending', { 'math-question': hasMathFormula(row.original_question_text) }]"
                    >
                      <div class="card-header-small">
                        <span class="card-index">{{ idx + 1 }}</span>
                        <el-tag :type="row.is_correct === true ? 'success' : row.is_correct === false ? 'danger' : 'info'" size="small">
                          {{ row.is_correct === true ? '正确' : row.is_correct === false ? '错误' : '未批改' }}
                        </el-tag>
                      </div>
                      <div class="card-body">
                        <div class="question-info">
                          <div class="info-row">
                            <span class="label">原题：</span>
                            <span class="value"><MathText :text="row.original_question_text || '无'" /></span>
                          </div>
                          <!-- 阅读理解选项 -->
                          <div v-if="row.is_reading_question" class="reading-options">
                            <div class="option-row">{{ formatOption('A', row.option_a) }}</div>
                            <div class="option-row">{{ formatOption('B', row.option_b) }}</div>
                            <div class="option-row">{{ formatOption('C', row.option_c) }}</div>
                            <div class="option-row">{{ formatOption('D', row.option_d) }}</div>
                          </div>
                          <div class="info-row">
                            <span class="label">答案：</span>
                            <span class="value answer"><MathText :text="row.original_answer || '-'" /></span>
                          </div>
                          <div v-if="row.explanation" class="info-row">
                            <span class="label">解析：</span>
                            <span class="value explanation"><MathText :text="row.explanation" /></span>
                          </div>
                        </div>
                        <div v-if="row.original_image" class="question-image">
                          <el-image
                            :src="'/uploads/' + row.original_image"
                            fit="contain"
                            style="width: 60px; height: 60px; cursor: pointer;"
                            @click="previewImage(row.original_image)"
                          />
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </el-tab-pane>

        <!-- 单词练习页（仅单词复习类型显示） -->
        <el-tab-pane v-if="detailData.source_type === 'word'" label="单词练习" name="words">
          <div class="word-practice">
            <div class="detail-card">
              <div class="card-header-green">复习统计</div>
              <div class="card-content">
                <div class="word-stats-summary">
                  <el-descriptions :column="4" border size="small">
                    <el-descriptions-item label="复习类型">{{ getReviewTypeLabel(detailData.word_review_stats?.review_type) }}</el-descriptions-item>
                    <el-descriptions-item label="总单词数">{{ detailData.word_review_stats?.total_count || 0 }}</el-descriptions-item>
                    <el-descriptions-item label="正确">{{ detailData.word_review_stats?.correct_count || 0 }}</el-descriptions-item>
                    <el-descriptions-item label="用时">{{ formatDuration(detailData.word_review_stats?.duration || 0) }}</el-descriptions-item>
                  </el-descriptions>
                </div>
              </div>
            </div>

            <div class="detail-card">
              <div class="card-header-purple">单词列表</div>
              <div class="card-content">
                <div class="word-cards-grid">
                  <div
                    v-for="(q, idx) in detailData.questions"
                    :key="q.id"
                    :class="['word-card', q.is_correct ? 'card-correct' : 'card-wrong']"
                  >
                    <div class="word-card-header">
                      <span class="word-index">{{ idx + 1 }}</span>
                      <el-tag :type="q.is_correct ? 'success' : 'danger'" size="small">
                        {{ q.is_correct ? '正确' : '错误' }}
                      </el-tag>
                    </div>
                    <div class="word-card-body">
                      <div class="word-main">
                        <div class="word-english">{{ q.question_text }}</div>
                        <div class="word-chinese">{{ q.answer }}</div>
                      </div>
                      <div class="word-result">
                        <div class="result-label">实际默写</div>
                        <div :class="['result-value', q.is_correct ? 'text-success' : 'text-danger']">
                          {{ q.user_answer || '-' }}
                        </div>
                      </div>
                    </div>
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
import MathText from '@/components/MathText.vue'
import MathEditor from '@/components/MathEditor.vue'
import { ref, reactive, computed, onMounted, nextTick } from 'vue'
import { ElMessage, ElMessageBox, ElLoading } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import { questionApi } from '@/api/question'

const hasMathFormula = (text = '') => ['\\(', '\\[', '$$'].some(boundary => (text || '').includes(boundary))

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

// 计算属性
const gradedCount = computed(() => Object.keys(gradingResults.value).length)
const correctCount = computed(() => Object.values(gradingResults.value).filter(v => v === true).length)
const wrongCount = computed(() => Object.values(gradingResults.value).filter(v => v === false).length)

const gradingDetailDialogVisible = ref(false)
const gradingQuestionDetail = ref(null)
const isEditingGradingQuestion = ref(false)
const gradingEditLoading = ref(false)
const gradingQuestionEditForm = reactive({
  original_question_text: '',
  original_image: '',
  original_answer: '',
  knowledge_point: '',
  error_type: '',
  difficulty: 3
})

const showQuestionDetail = (question) => {
  gradingQuestionDetail.value = question
  isEditingGradingQuestion.value = false
  gradingDetailDialogVisible.value = true
}

const startEditGradingQuestion = () => {
  // 填充编辑表单
  gradingQuestionEditForm.original_question_text = gradingQuestionDetail.value.original_question_text || ''
  gradingQuestionEditForm.original_image = gradingQuestionDetail.value.original_image || ''
  gradingQuestionEditForm.original_answer = gradingQuestionDetail.value.original_answer || ''
  gradingQuestionEditForm.knowledge_point = gradingQuestionDetail.value.knowledge_point || ''
  gradingQuestionEditForm.error_type = gradingQuestionDetail.value.error_type || ''
  gradingQuestionEditForm.difficulty = gradingQuestionDetail.value.difficulty || 3
  isEditingGradingQuestion.value = true
}

const cancelEditGradingQuestion = () => {
  isEditingGradingQuestion.value = false
}

const saveGradingQuestion = async () => {
  gradingEditLoading.value = true
  try {
    await questionApi.update(gradingQuestionDetail.value.question_id, {
      parsed_question: gradingQuestionEditForm.original_question_text,
      original_image: gradingQuestionEditForm.original_image,
      answer: gradingQuestionEditForm.original_answer,
      knowledge_point: gradingQuestionEditForm.knowledge_point,
      error_type: gradingQuestionEditForm.error_type,
      difficulty: gradingQuestionEditForm.difficulty
    })
    ElMessage.success('保存成功')
    isEditingGradingQuestion.value = false
    // 更新列表中的题目数据
    const idx = currentPsQuestions.value.findIndex(q => q.question_id === gradingQuestionDetail.value.question_id)
    if (idx !== -1) {
      currentPsQuestions.value[idx] = {
        ...currentPsQuestions.value[idx],
        ...gradingQuestionEditForm
      }
    }
  } catch (error) {
    ElMessage.error('保存失败')
  } finally {
    gradingEditLoading.value = false
  }
}

const initGrading = async (ps) => {
  // 获取练习集详情（含题目）
  try {
    const { data } = await questionApi.getPracticeSet(ps.id)
    currentPsQuestions.value = data.questions || []
    gradingResults.value = {}
    gradingStep.value = 'list' // 直接进入列表视图
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
  // 移除自动前进逻辑，支持跳序批改
}

const getQuestionRowClass = (questionId) => {
  if (gradingResults.value[questionId] === true) return 'graded-correct'
  if (gradingResults.value[questionId] === false) return 'graded-wrong'
  return 'graded-pending'
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

// 格式化选项（带字母前缀，避免重复）
const formatOption = (letter, text) => {
  if (!text) return ''
  text = text.trim()
  // 去除已有的选项前缀（A. B. C. D. / A、B、C、D、 / (A) / A) 等各种格式）
  text = text.replace(/^[A-Da-d]\s*[.、．]\s*/, '')
  text = text.replace(/^\([A-Da-d]\)\s*/, '')
  text = text.replace(/^[A-Da-d]\)\s*/, '')
  return letter + '. ' + text
}

// 格式化时长
const formatDuration = (seconds) => {
  if (!seconds && seconds !== 0) return '-'
  if (seconds === 0) return '0秒'
  const mins = Math.floor(seconds / 60)
  const secs = seconds % 60
  return `${mins}分${secs}秒`
}

// 获取复习类型标签
const getReviewTypeLabel = (type) => {
  const labels = { 1: '默写英文', 2: '选择中文', 3: '听力' }
  return labels[type] || '默写英文'
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
    // 获取仍然保留的旧图片（从 editImagesFileList 中筛选 isOld 为 true 的）
    const keptOldImages = editImagesFileList.value
      .filter(f => f.isOld)
      .map(f => f.name)
    // 上传新文件
    let newImagePaths = [...keptOldImages]
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
        newImagePaths = [...keptOldImages, ...uploadedPaths]
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
  white-space: pre-wrap;
  word-break: break-word;
}

.original-question-block,
.original-answer-block {
  margin-bottom: 16px;
}

.original-question-block:last-child,
.original-answer-block:last-child {
  margin-bottom: 0;
}

.block-label {
  font-size: 12px;
  color: #909399;
  margin-bottom: 6px;
  font-weight: bold;
}

.block-content {
  background: #fff;
  padding: 12px;
  border-radius: 6px;
}

.answer-text {
  font-size: 16px;
  color: #67c23a;
  font-weight: bold;
  white-space: pre-wrap;
  word-break: break-word;
  line-height: 1.8;
}

.grading-question-buttons {
  display: flex;
  gap: 20px;
  justify-content: center;
}

.grading-upload {
  padding: 10px 0;
}

/* 禁用卡片的hover效果 */
.practice-sets :deep(.el-card) {
  transition: none;
}
.practice-sets :deep(.el-card:hover) {
  transform: none;
  box-shadow: var(--shadow-sm) !important;
}

.text-success {
  color: #67c23a;
}

.text-danger {
  color: #f56c6c;
}

.el-descriptions--small .el-descriptions__body .el-descriptions__table .el-descriptions__cell {
  font-size: 16px !important;
}
.el-descriptions--small .el-descriptions__body .el-descriptions__table .el-descriptions__label,
.el-descriptions--small .el-descriptions__body .el-descriptions__table .el-descriptions__content {
  font-size: 16px !important;
}

/* 卡片通用样式 */
.detail-card {
  background: #fff;
  border-radius: 12px;
  box-shadow: 0 4px 16px rgba(0,0,0,0.08);
  margin-bottom: 16px;
  overflow: hidden;
}

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

.card-header-purple {
  background: linear-gradient(135deg, #9c27b0 0%, #862491 100%);
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

.card-header-small {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.card-content {
  padding: 20px;
}

/* 题目卡片 */
.question-cards {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 16px;
}

.question-card {
  background: #f5f7fa;
  border-radius: 8px;
  padding: 16px;
  border-left: 4px solid #67c23a;
}

.question-card.card-wrong {
  background: #fef0f0;
  border-left-color: #f56c6c;
}

.card-index {
  font-weight: bold;
  color: #606266;
}

.card-body {
  display: flex;
  justify-content: space-between;
  gap: 12px;
}

.question-info {
  flex: 1;
  min-width: 0;
}

.question-card { min-width: 0; }
.question-card.math-question { grid-column: 1 / -1; }
.math-question .info-row .value { display: block; max-width: 100%; }
.question-image { flex: 0 0 60px; }
.question-card.card-pending { border-left-color: #909399; }

.info-row {
  margin-bottom: 10px;
}

.info-row .label {
  color: #909399;
  font-size: 16px;
}

.info-row .value {
  color: #303133;
  font-size: 16px;
}

.info-row .value.answer {
  color: #67c23a;
  font-weight: bold;
  white-space: pre-wrap;
  word-break: break-word;
  line-height: 1.8;
}

.reading-options {
  margin: 10px 0;
  padding: 10px;
  background: #f5f7fa;
  border-radius: 4px;
  font-size: 14px;
  line-height: 1.8;
}

.reading-options .option-row {
  margin: 4px 0;
}

.info-row .value.explanation {
  color: #909399;
  font-size: 13px;
  white-space: pre-wrap;
  line-height: 1.6;
}

/* 单词卡片网格 */
.word-cards-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 16px;
}

.word-card {
  background: #f5f7fa;
  border-radius: 8px;
  padding: 12px;
  border-left: 4px solid #67c23a;
}

.word-card.card-wrong {
  background: #fef0f0;
  border-left-color: #f56c6c;
}

.word-card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.word-index {
  font-weight: bold;
  color: #606266;
}

.word-card-body {
  display: flex;
  justify-content: space-between;
}

.word-main {
  flex: 1;
}

.word-english {
  font-size: 20px;
  font-weight: bold;
  color: #303133;
  margin-bottom: 6px;
}

.word-chinese {
  font-size: 16px;
  color: #606266;
}

.word-result {
  text-align: right;
}

.result-label {
  font-size: 14px;
  color: #909399;
  margin-bottom: 6px;
}

.result-value {
  font-size: 18px;
  font-weight: bold;
}

/* 统计摘要 */
.word-stats-summary {
  margin-bottom: 0;
}

/* 查看原题弹层样式 */
.question-detail-content {
  padding: 10px 0;
}

.detail-block {
  margin-bottom: 16px;
}

.detail-label {
  font-size: 14px;
  color: #909399;
  margin-bottom: 8px;
  font-weight: bold;
}

.detail-value {
  font-size: 14px;
  color: #303133;
  line-height: 1.6;
}

.detail-value.answer-value {
  font-size: 16px;
  color: #67c23a;
  font-weight: bold;
  white-space: pre-wrap;
  word-break: break-word;
}

.detail-meta {
  display: flex;
  gap: 20px;
  padding: 12px 0;
  border-top: 1px solid #ebeef5;
  margin-top: 16px;
  font-size: 13px;
  color: #606266;
}

.text-gray-400 {
  color: #909399;
}

/* 批改弹层样式 */
.grading-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 20px;
  background: linear-gradient(135deg, #67c23a 0%, #5daf34 100%);
  color: white;
  border-radius: 8px 8px 0 0;
}

.grading-header-left {
  display: flex;
  align-items: center;
  gap: 20px;
}

.grading-title {
  font-size: 18px;
  font-weight: bold;
}

.grading-progress-text {
  font-size: 14px;
  opacity: 0.9;
}

.accuracy-display {
  text-align: right;
}

.accuracy-value {
  font-size: 28px;
  font-weight: bold;
  display: block;
}

.accuracy-label {
  font-size: 12px;
  opacity: 0.8;
}

.grading-progress-bar {
  padding: 16px 20px;
  background: #f5f7fa;
  border-bottom: 1px solid #ebeef5;
}

.progress-bar {
  height: 8px;
  background: #e4e7ed;
  border-radius: 4px;
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  background: linear-gradient(90deg, #67c23a, #85ce61);
  transition: width 0.3s;
}

.grading-stats {
  display: flex;
  gap: 20px;
  margin-top: 10px;
  font-size: 13px;
}

.stat-correct { color: #67c23a; }
.stat-wrong { color: #f56c6c; }
.stat-pending { color: #909399; }

/* 题目列表 */
.grading-question-list {
  max-height: 500px;
  overflow-y: auto;
  padding: 16px 20px;
}

.question-row {
  background: white;
  border-radius: 8px;
  margin-bottom: 12px;
  padding: 16px 20px;
  display: flex;
  align-items: center;
  gap: 16px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.06);
  transition: all 0.2s;
  border-left: 4px solid #e4e7ed;
}

.question-row:hover {
  box-shadow: 0 4px 12px rgba(0,0,0,0.1);
}

.question-row.graded-correct {
  border-left-color: #67c23a;
  background: linear-gradient(90deg, #f0f9eb 0%, white 30%);
}

.question-row.graded-wrong {
  border-left-color: #f56c6c;
  background: linear-gradient(90deg, #fef0f0 0%, white 30%);
}

.question-row.graded-pending {
  border-left-color: #e4e7ed;
}

.question-number {
  width: 40px;
  height: 40px;
  background: #409eff;
  color: white;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: bold;
  flex-shrink: 0;
}

.question-content {
  flex: 1;
  min-width: 0;
}

.question-text {
  font-size: 14px;
  color: #303133;
  margin-bottom: 8px;
  line-height: 1.5;
  word-break: break-word;
}

.question-answer {
  display: flex;
  align-items: center;
  gap: 8px;
}

.answer-label {
  font-size: 13px;
  color: #909399;
}

.answer-badge {
  background: #67c23a;
  color: white;
  padding: 2px 10px;
  border-radius: 4px;
  font-size: 13px;
  font-weight: 500;
  display: inline-block;
  white-space: pre-wrap;
  word-break: break-word;
}

.question-actions {
  display: flex;
  gap: 8px;
  flex-shrink: 0;
}

.btn-correct,
.btn-wrong {
  border: none;
  padding: 8px 16px;
  border-radius: 6px;
  cursor: pointer;
  font-size: 14px;
  transition: all 0.2s;
  color: white;
}

.btn-correct {
  background: #67c23a;
}

.btn-correct:hover {
  background: #5daf34;
  transform: scale(1.02);
}

.btn-correct.active {
  background: #529b2e;
  box-shadow: inset 0 2px 4px rgba(0,0,0,0.15);
}

.btn-wrong {
  background: #f56c6c;
}

.btn-wrong:hover {
  background: #e64242;
  transform: scale(1.02);
}

.btn-wrong.active {
  background: #d93636;
  box-shadow: inset 0 2px 4px rgba(0,0,0,0.15);
}

/* 底部栏 */
.grading-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.footer-stats {
  font-size: 14px;
  color: #606266;
}

.footer-buttons {
  display: flex;
  gap: 10px;
}

/* 查看原题弹层 */
.question-detail-content {
  padding: 10px 0;
}

.detail-block {
  margin-bottom: 16px;
}

.detail-label {
  font-size: 13px;
  color: #909399;
  font-weight: bold;
  margin-bottom: 8px;
}

.detail-value {
  background: #f5f7fa;
  padding: 12px;
  border-radius: 6px;
  font-size: 14px;
  color: #303133;
  line-height: 1.6;
}

.detail-value.answer-value {
  background: #f0f9eb;
  color: #67c23a;
  font-weight: bold;
  font-size: 16px;
  white-space: pre-wrap;
  word-break: break-word;
}

.reading-options .option-row {
  margin: 4px 0;
}

.detail-meta {
  display: flex;
  gap: 20px;
  padding: 12px 0;
  border-top: 1px solid #ebeef5;
  font-size: 13px;
  color: #606266;
}

.detail-meta span {
  display: flex;
  align-items: center;
  gap: 4px;
}
</style>
<style>
.practice-detail-dialog .el-descriptions--small .el-descriptions__body .el-descriptions__table .el-descriptions__cell {
  font-size: 16px !important;
}
.practice-detail-dialog .el-descriptions--small .el-descriptions__body .el-descriptions__table .el-descriptions__label,
.practice-detail-dialog .el-descriptions--small .el-descriptions__body .el-descriptions__table .el-descriptions__content {
  font-size: 16px !important;
}
</style>
