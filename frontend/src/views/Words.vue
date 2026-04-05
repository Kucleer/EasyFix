<template>
  <div class="words">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>单词本</span>
          <div>
            <el-button type="primary" @click="showAddDialog">
              <el-icon><Plus /></el-icon>
              新增单词
            </el-button>
            <el-button type="info" @click="showImportDialog">
              <el-icon><Upload /></el-icon>
              导入单词
            </el-button>
            <el-button type="success" @click="startReview">
              <el-icon><Edit /></el-icon>
              开始复习
            </el-button>
            <el-button type="warning" @click="showPrintDialog">
              <el-icon><Printer /></el-icon>
              打印默写
            </el-button>
          </div>
        </div>
      </template>

      <!-- 筛选条件 -->
      <div class="filters">
        <el-input
          v-model="filters.keyword"
          placeholder="搜索单词"
          clearable
          @change="fetchWords"
          style="width: 180px"
        />
        <el-select v-model="filters.grade" placeholder="年级" clearable @change="fetchWords" style="width: 120px">
          <el-option v-for="g in gradeOptions" :key="g.value" :label="g.label" :value="g.value" />
        </el-select>
        <el-select v-model="filters.semester" placeholder="学期" clearable @change="fetchWords" style="width: 100px">
          <el-option label="上学期" :value="1" />
          <el-option label="下学期" :value="2" />
        </el-select>
        <el-select v-model="filters.tag_id" placeholder="标签" clearable @change="fetchWords" style="width: 150px">
          <el-option v-for="t in allTags" :key="t.id" :label="t.name" :value="t.id" />
        </el-select>
      </div>

      <!-- 正确率等级快速筛选 -->
      <div class="accuracy-level-filter" style="margin-top: 10px">
        <el-tag
          v-for="level in accuracyLevelOptions"
          :key="level.value"
          :type="filters.accuracy_level === level.value ? 'primary' : 'info'"
          class="accuracy-level-tag"
          @click="toggleAccuracyLevel(level.value)"
          style="cursor: pointer; margin-right: 8px"
        >
          {{ level.label }}
        </el-tag>
      </div>

      <!-- 单词列表 -->
      <el-table
        ref="tableRef"
        :data="words.items"
        stripe
        style="width: 100%; margin-top: 20px"
        @selection-change="handleSelectionChange"
        @sort-change="handleSortChange"
      >
        <el-table-column type="selection" width="55" />
        <el-table-column prop="english" label="英文" width="150">
          <template #default="{ row }">
            <span class="word-english">{{ row.english }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="chinese" label="中文" min-width="200" />
        <el-table-column prop="phonetic" label="音标" width="150">
          <template #default="{ row }">
            <span class="phonetic">{{ row.phonetic || '-' }}</span>
          </template>
        </el-table-column>
        <el-table-column label="属性" width="150">
          <template #default="{ row }">
            <el-tag v-if="row.grade" :style="{ fontSize: '14px' }">{{ row.grade }}年级</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="复习" width="100">
          <template #default="{ row }">
            <span class="review-info">
              <span class="correct">{{ row.correct_count || 0 }}</span> /
              <span class="total">{{ row.review_count || 0 }}</span>
            </span>
          </template>
        </el-table-column>
        <el-table-column label="正确率" width="120" sortable prop="accuracy">
          <template #default="{ row }">
            <span :style="{ color: getAccuracyColor(row) }">{{ getAccuracyText(row) }}</span>
            <el-tag v-if="row.accuracy_level" :type="getAccuracyLevelTagType(row.accuracy_level)" :style="{ marginLeft: '5px', fontSize: '14px' }">
              {{ getAccuracyLevelText(row.accuracy_level) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="280" fixed="right">
          <template #default="{ row }">
            <el-button type="info" size="default" @click="viewDetail(row)">详情</el-button>
            <el-button type="primary" size="default" @click="editWord(row)">编辑</el-button>
            <el-button type="danger" size="default" @click="deleteWord(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>

      <!-- 分页 -->
      <div class="pagination">
        <el-pagination
          v-model:current-page="pagination.page"
          v-model:page-size="pagination.limit"
          :page-sizes="[10, 20, 50, 100]"
          :total="words.total"
          layout="total, sizes, prev, pager, next"
          @change="fetchWords"
        />
      </div>
    </el-card>

    <!-- 新增/编辑弹窗 -->
    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="500px">
      <el-form :model="form" label-width="80px">
        <el-form-item label="英文" required>
          <el-input v-model="form.english" placeholder="输入英文单词" />
        </el-form-item>
        <el-form-item label="中文" required>
          <el-input v-model="form.chinese" placeholder="输入中文释义" />
        </el-form-item>
        <el-form-item label="音标">
          <el-input v-model="form.phonetic" placeholder="输入音标（可选）" />
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
        <el-form-item label="标签">
          <el-select v-model="form.tag_ids" multiple placeholder="选择标签" style="width: 100%">
            <el-option v-for="t in allTags" :key="t.id" :label="t.name" :value="t.id" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="saveWord">保存</el-button>
      </template>
    </el-dialog>

    <!-- 详情弹窗 -->
    <el-dialog v-model="detailVisible" title="单词详情" width="600px">
      <el-tabs v-if="detailVisible" v-model="activeTab">
        <el-tab-pane label="基本信息" name="info">
          <el-form label-width="80px" size="default">
            <el-form-item label="英文">{{ detailWord.english }}</el-form-item>
            <el-form-item label="中文">{{ detailWord.chinese }}</el-form-item>
            <el-form-item label="音标">{{ detailWord.phonetic || '-' }}</el-form-item>
            <el-form-item label="年级">{{ detailWord.grade ? detailWord.grade + '年级' : '-' }}</el-form-item>
            <el-form-item label="学期">{{ detailWord.semester === 1 ? '上学期' : detailWord.semester === 2 ? '下学期' : '-' }}</el-form-item>
            <el-form-item label="标签">
              <el-tag v-for="t in detailWord.tags" :key="t.id" style="margin-right: 5px">{{ t.name }}</el-tag>
              <span v-if="!detailWord.tags || detailWord.tags.length === 0">-</span>
            </el-form-item>
            <el-form-item label="复习次数">{{ detailWord.review_count || 0 }}</el-form-item>
            <el-form-item label="正确次数">{{ detailWord.correct_count || 0 }}</el-form-item>
            <el-form-item label="正确率">{{ getAccuracyText(detailWord) }}</el-form-item>
          </el-form>
        </el-tab-pane>
        <el-tab-pane label="记忆曲线" name="curve">
          <div v-if="memoryCurve" class="memory-curve">
            <!-- 阶段进度条 -->
            <div class="phase-bar">
              <div class="phase-track">
                <div
                  class="phase-dot"
                  v-for="(phase, idx) in ['新学', '在途', '遗忘点', '牢记']"
                  :key="phase"
                  :class="{ active: memoryCurve.learning_phase === phase }"
                  :style="{ left: phasePosition[phase] + '%', borderColor: memoryCurve.learning_phase === phase ? phaseColors[phase] : '#ddd' }"
                >
                  {{ phase }}
                </div>
              </div>
            </div>

            <!-- 下次复习时间 -->
            <div class="next-review">
              <span v-if="memoryCurve.learning_phase === '遗忘点'">即将到期</span>
              <span v-else-if="memoryCurve.next_review_at">下次复习：{{ formatDate(memoryCurve.next_review_at) }}</span>
              <span v-else>暂未安排复习</span>
            </div>

            <!-- 复习历史 -->
            <div class="review-history">
              <div class="history-title">复习历史：</div>
              <div v-if="memoryCurve.review_history.length === 0" class="history-empty">暂无复习记录</div>
              <div v-else class="history-item">
                <span class="history-date">今天（待复习）</span>
              </div>
              <div v-for="(log, idx) in memoryCurve.review_history" :key="idx" class="history-item">
                <span class="history-date">{{ formatDate(log.reviewed_at) }}</span>
                <span v-if="log.is_correct" class="history-correct">正确</span>
                <span v-else class="history-wrong">错误 【{{ log.user_answer }}】</span>
              </div>
            </div>
          </div>
          <div v-else class="no-curve">加载中...</div>
        </el-tab-pane>
      </el-tabs>
      <template #footer>
        <el-button @click="detailVisible = false">关闭</el-button>
      </template>
    </el-dialog>

    <!-- 复习弹窗 -->
    <el-dialog v-model="reviewVisible" title="单词复习" width="1200px" :close-on-click-modal="false" class="review-dialog">
      <div v-if="reviewStep === 'config'" class="review-config">
        <el-form-item label="复习数量">
          <el-input-number v-model="reviewConfig.count" :min="1" :max="50" />
        </el-form-item>
        <el-form-item label="年级筛选">
          <el-select v-model="reviewConfig.grade" placeholder="全部" clearable style="width: 100%">
            <el-option v-for="g in gradeOptions" :key="g.value" :label="g.label" :value="g.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="题型">
          <el-radio-group v-model="reviewConfig.type">
            <el-radio :label="1">默写英文</el-radio>
            <el-radio :label="2">选择中文</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-button type="primary" @click="startReviewGame" style="width: 100%">开始复习</el-button>
      </div>

      <div v-else-if="reviewStep === 'question'" class="review-question">
        <div class="question-header">
          <span class="progress">{{ currentIndex + 1 }} / {{ reviewQuestions.length }}</span>
          <span class="timer">用时: {{ Math.floor(reviewElapsed / 60) }}:{{ String(reviewElapsed % 60).padStart(2, '0') }}</span>
        </div>
        <!-- 正确/错误结果展示 -->
        <div v-if="currentQuestion.correct !== undefined" :class="['result-display', currentQuestion.correct ? 'correct-display' : 'wrong-display']">
          <div class="result-status">{{ currentQuestion.correct ? '✓ 正确' : '✗ 错误' }}</div>
          <div class="result-answer-large">正确答案: {{ currentQuestion.english }}</div>
          <div v-if="!currentQuestion.correct" class="your-answer">你的答案: {{ currentQuestion.userAnswer || '(未作答)' }}</div>
        </div>

        <div class="question-content">
          <div v-if="reviewConfig.type === 1" class="dictation">
            <div class="chinese">{{ currentQuestion.chinese }}</div>
            <div class="hint-box">
              <div class="hint">提示：{{ currentQuestion.word_length }}个字母</div>
            </div>
            <el-input
              ref="answerInputRef"
              v-model="userAnswer"
              placeholder="输入英文单词"
              @keyup.enter="submitAnswer"
              :disabled="currentQuestion.correct !== undefined"
              class="answer-input"
            />
          </div>

          <div v-else class="choice">
            <div class="english">{{ currentQuestion.english }}</div>
            <el-radio-group v-model="selectedOption" @change="submitAnswer">
              <el-radio v-for="(opt, idx) in currentQuestion.options" :key="idx" :label="opt" :disabled="currentQuestion.correct !== undefined">
                {{ opt }}
              </el-radio>
            </el-radio-group>
          </div>
        </div>

        <div class="question-actions">
          <el-button type="danger" @click="terminateReview">终止答题</el-button>
          <el-button v-if="currentQuestion.correct === undefined" type="primary" @click="submitAnswer">提交</el-button>
          <el-button v-else type="success" @click="finishReview">完成</el-button>
        </div>
      </div>

      <div v-else-if="reviewStep === 'result'" class="review-result">
        <div class="result-summary">
          <div class="big-number">{{ reviewResult.accuracy }}%</div>
          <div class="label">正确率</div>
        </div>
        <div class="result-detail">
          <div>总题数: {{ reviewResult.total }}</div>
          <div>正确: {{ reviewResult.correct }}</div>
          <div>错误: {{ reviewResult.error }}</div>
          <div>用时: {{ Math.floor(reviewResult.duration / 60) }}:{{ String(reviewResult.duration % 60).padStart(2, '0') }}</div>
        </div>
        <!-- 错误单词列表 -->
        <div v-if="reviewResult.error > 0" class="error-word-list">
          <h4>需要复习的单词</h4>
          <div class="error-words">
            <div v-for="(q, idx) in reviewQuestions.filter(q => !q.correct)" :key="idx" class="error-word-item">
              <div class="error-word-info">
                <span class="word-english">{{ q.english }}</span>
                <span class="word-chinese">{{ q.chinese }}</span>
              </div>
              <div class="error-word-user">
                <span class="label">你的答案：</span>
                <span class="user-answer wrong">{{ q.userAnswer || '(未作答)' }}</span>
              </div>
            </div>
          </div>
        </div>
        <el-button type="primary" @click="reviewVisible = false" style="width: 100%">完成</el-button>
      </div>
    </el-dialog>

    <!-- 打印弹窗 -->
    <el-dialog v-model="printDialogVisible" title="打印默写" width="400px">
      <el-form :model="printForm" label-width="80px">
        <el-form-item label="单词数量">
          <el-input-number v-model="printForm.count" :min="5" :max="100" />
        </el-form-item>
        <el-form-item label="年级筛选">
          <el-select v-model="printForm.grade" placeholder="全部" clearable style="width: 100%">
            <el-option v-for="g in gradeOptions" :key="g.value" :label="g.label" :value="g.value" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="printDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="generatePrintPdf">生成PDF</el-button>
      </template>
    </el-dialog>

    <!-- 导入弹窗 -->
    <el-dialog v-model="importDialogVisible" title="导入单词" width="1100px" class="import-dialog">
      <el-form :model="importForm" label-width="100px">
        <el-form-item label="导入方式">
          <el-radio-group v-model="importForm.mode">
            <el-radio label="text">文本粘贴</el-radio>
            <el-radio label="file">文件上传</el-radio>
            <el-radio label="image">图片识别</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item v-if="importForm.mode === 'text'" label="单词格式">
          <el-input
            v-model="importForm.text"
            type="textarea"
            :rows="6"
            placeholder="每行一个单词，格式：英文 中文（用空格分隔）
例如：
apple 苹果
banana 香蕉
orange 橙子"
            @input="onTextChange"
          />
        </el-form-item>
        <el-form-item v-else-if="importForm.mode === 'file'" label="上传文件">
          <el-upload
            ref="uploadRef"
            :auto-upload="false"
            :limit="1"
            accept=".txt,.csv"
            :on-change="handleFileChange"
          >
            <el-button>选择文件</el-button>
            <template #tip>
              <div class="el-upload__tip">支持 .txt 或 .csv 文件，每行一个单词，格式：英文 中文</div>
            </template>
          </el-upload>
        </el-form-item>
        <el-form-item v-else-if="importForm.mode === 'image'" label="上传图片">
          <el-upload
            ref="imageUploadRef"
            :auto-upload="false"
            :limit="1"
            accept="image/*"
            :on-change="handleImageChange"
            :on-remove="handleImageRemove"
          >
            <el-button>选择图片</el-button>
            <template #tip>
              <div class="el-upload__tip">支持 JPG、PNG 格式，图片中的单词文字将被识别提取</div>
            </template>
          </el-upload>
          <!-- OCR识别结果预览 -->
          <div v-if="importForm.ocrText" class="ocr-preview">
            <div class="ocr-label">OCR原始识别：</div>
            <el-input
              v-model="importForm.ocrText"
              type="textarea"
              :rows="4"
              placeholder="OCR识别的原始文本"
              @input="importForm.parsedWords = smartParseWords(importForm.ocrText)"
            />
          </div>
        </el-form-item>

        <!-- 单词预览表格 -->
        <el-form-item v-if="importForm.parsedWords.length > 0" label="单词预览">
          <div class="words-preview">
            <el-table :data="importForm.parsedWords" border stripe size="small" max-height="300">
              <el-table-column prop="english" label="英文" width="150">
                <template #default="{ row }">
                  <el-input v-model="row.english" size="small" />
                </template>
              </el-table-column>
              <el-table-column prop="chinese" label="中文" min-width="150">
                <template #default="{ row }">
                  <el-input v-model="row.chinese" size="small" />
                </template>
              </el-table-column>
              <el-table-column prop="phonetic" label="音标" width="120">
                <template #default="{ row }">
                  <el-input v-model="row.phonetic" size="small" placeholder="可选" />
                </template>
              </el-table-column>
              <el-table-column label="操作" width="60" fixed="right">
                <template #default="{ $index }">
                  <el-button type="danger" size="small" link @click="importForm.parsedWords.splice($index, 1)">删除</el-button>
                </template>
              </el-table-column>
            </el-table>
            <div class="preview-summary">共 {{ importForm.parsedWords.length }} 个单词</div>
          </div>
        </el-form-item>

        <el-form-item label="默认年级">
          <el-select v-model="importForm.grade" placeholder="选择年级（可选）" clearable style="width: 100%">
            <el-option v-for="g in gradeOptions" :key="g.value" :label="g.label" :value="g.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="默认学期">
          <el-select v-model="importForm.semester" placeholder="选择学期（可选）" clearable style="width: 100%">
            <el-option label="上学期" :value="1" />
            <el-option label="下学期" :value="2" />
          </el-select>
        </el-form-item>
        <el-form-item label="标签">
          <el-select v-model="importForm.tag_ids" multiple placeholder="选择标签（可选）" style="width: 100%">
            <el-option v-for="t in allTags" :key="t.id" :label="t.name" :value="t.id" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="importDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="importWords" :loading="importing">导入</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Edit, Printer, Upload } from '@element-plus/icons-vue'
import { wordApi } from '@/api/word'
import { questionApi } from '@/api/question'
import { motivationApi } from '@/api/motivation'

const words = ref({ total: 0, items: [] })
const allTags = ref([])
const filters = reactive({
  keyword: '',
  grade: null,
  semester: null,
  tag_id: null,
  accuracy_level: null,
  sort_by: null,
  sort_order: 'desc',
})
const pagination = reactive({
  page: 1,
  limit: 20,
})

const dialogVisible = ref(false)
const dialogTitle = ref('新增单词')
const isEdit = ref(false)
const currentWordId = ref(null)

const form = reactive({
  english: '',
  chinese: '',
  phonetic: '',
  grade: null,
  semester: null,
  tag_ids: [],
})

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

// 正确率等级选项
const accuracyLevelOptions = ref([
  { label: '全部', value: null },
  { label: '新词', value: 'new' },
  { label: '需加强', value: 'weak' },
  { label: '薄弱', value: 'learning' },
  { label: '一般', value: 'good' },
  { label: '掌握', value: 'mastered' },
])

// 切换正确率等级筛选
const toggleAccuracyLevel = (level) => {
  if (filters.accuracy_level === level) {
    filters.accuracy_level = null
  } else {
    filters.accuracy_level = level
  }
  pagination.page = 1
  fetchWords()
}

// 复习相关
const reviewVisible = ref(false)
const reviewStep = ref('config')
const reviewConfig = reactive({
  count: 25,
  grade: null,
  type: 1,
})
const reviewQuestions = ref([])
const currentIndex = ref(0)
const userAnswer = ref('')
const selectedOption = ref('')
const currentSessionId = ref(null)
const reviewResult = reactive({
  total: 0,
  correct: 0,
  error: 0,
  accuracy: 0,
  duration: 0,
})

// 复习计时器
const reviewStartTime = ref(null)
const reviewTimer = ref(null)
const reviewElapsed = ref(0) // 秒
const answerInputRef = ref(null)

// 打印相关
const printDialogVisible = ref(false)
const printForm = reactive({
  count: 25,
  grade: null,
})

// 导入相关
const importDialogVisible = ref(false)
const importing = ref(false)
const uploadRef = ref()
const imageUploadRef = ref()
const importForm = reactive({
  mode: 'text',
  text: '',
  file: null,
  image: null,
  ocrText: '',
  parsedWords: [],  // 解析后的单词预览
  grade: null,
  semester: null,
  tag_ids: [],
})

const currentQuestion = ref({})
const tableRef = ref()
const selectedWords = ref([])

// 记忆曲线相关
const memoryCurve = ref(null)
const memoryCurveLoading = ref(false)

const fetchMemoryCurve = async (wordId) => {
  memoryCurveLoading.value = true
  try {
    const { data } = await wordApi.getMemoryCurve(wordId)
    memoryCurve.value = data
  } catch (error) {
    console.error('获取记忆曲线失败:', error)
  } finally {
    memoryCurveLoading.value = false
  }
}

// 阶段对应的颜色
const phaseColors = {
  '新学': '#909399',
  '在途': '#409eff',
  '遗忘点': '#e6a23c',
  '牢记': '#67c23a'
}

// 阶段对应的进度位置
const phasePosition = {
  '新学': 12.5,
  '在途': 37.5,
  '遗忘点': 62.5,
  '牢记': 87.5
}

// 格式化日期
const formatDate = (dateStr) => {
  if (!dateStr) return ''
  const date = new Date(dateStr)
  const month = date.getMonth() + 1
  const day = date.getDate()
  return `${month}月${day}日`
}

// 详情弹窗相关
const detailVisible = ref(false)
const detailWord = ref({})
const activeTab = ref('info')

const viewDetail = async (row) => {
  detailWord.value = row
  activeTab.value = 'info'
  memoryCurve.value = null
  detailVisible.value = true
  // 获取记忆曲线
  await fetchMemoryCurve(row.id)
}

// 计算单词正确率
const getAccuracy = (row) => {
  if (!row.review_count || row.review_count === 0) return 0
  return (row.correct_count / row.review_count) * 100
}

// 获取正确率显示文本
const getAccuracyText = (row) => {
  if (!row.review_count || row.review_count === 0) return '--'
  return getAccuracy(row).toFixed(0) + '%'
}

// 获取正确率颜色（100%绿色，0%红色，渐变）
const getAccuracyColor = (row) => {
  if (!row.review_count || row.review_count === 0) return '#909399'
  const accuracy = getAccuracy(row)
  if (accuracy >= 100) return '#67c23a'  // 绿色
  if (accuracy <= 0) return '#f56c6c'    // 红色
  // 渐变色：从红到黄到绿
  if (accuracy < 50) {
    // 红到黄
    const ratio = accuracy / 50
    const r = 245
    const g = Math.round(67 + (183 - 67) * ratio)
    const b = Math.round(108 + (58 - 108) * ratio)
    return `rgb(${r}, ${g}, ${b})`
  } else {
    // 黄到绿
    const ratio = (accuracy - 50) / 50
    const r = Math.round(245 - (245 - 103) * ratio)
    const g = Math.round(183 + (194 - 183) * ratio)
    const b = Math.round(58 + (58 - 58) * ratio)
    return `rgb(${r}, ${g}, ${b})`
  }
}

// 获取正确率等级文字
const getAccuracyLevelText = (level) => {
  const map = {
    'new': '新词',
    'weak': '需加强',
    'learning': '薄弱',
    'good': '一般',
    'mastered': '掌握',
  }
  return map[level] || level
}

// 获取正确率等级标签类型
const getAccuracyLevelTagType = (level) => {
  const map = {
    'new': 'info',
    'weak': 'danger',
    'learning': 'warning',
    'good': '',
    'mastered': 'success',
  }
  return map[level] || 'info'
}

// 处理表格排序变化（使用后端排序）
const handleSortChange = ({ prop, order }) => {
  if (!prop) {
    // 取消排序
    filters.sort_by = null
    filters.sort_order = 'desc'
  } else if (prop === 'accuracy') {
    // 正确率排序需要后端处理
    filters.sort_by = 'accuracy'
    filters.sort_order = order === 'ascending' ? 'asc' : 'desc'
  } else {
    // 其他字段使用后端排序
    filters.sort_by = prop
    filters.sort_order = order === 'ascending' ? 'asc' : 'desc'
  }
  pagination.page = 1 // 重置到第一页
  fetchWords()
}

const fetchWords = async () => {
  try {
    const params = {
      skip: (pagination.page - 1) * pagination.limit,
      limit: pagination.limit,
    }
    if (filters.keyword) params.keyword = filters.keyword
    if (filters.grade) params.grade = filters.grade
    if (filters.semester) params.semester = filters.semester
    if (filters.tag_id) params.tag_ids = filters.tag_id
    if (filters.accuracy_level) params.accuracy_level = filters.accuracy_level
    if (filters.sort_by) {
      params.sort_by = filters.sort_by
      params.sort_order = filters.sort_order
    }

    const { data } = await wordApi.list(params)
    words.value = data
  } catch (error) {
    ElMessage.error('获取单词列表失败')
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

const showAddDialog = () => {
  dialogTitle.value = '新增单词'
  isEdit.value = false
  resetForm()
  dialogVisible.value = true
}

const editWord = (row) => {
  dialogTitle.value = '编辑单词'
  isEdit.value = true
  currentWordId.value = row.id
  form.english = row.english
  form.chinese = row.chinese
  form.phonetic = row.phonetic || ''
  form.grade = row.grade
  form.semester = row.semester
  form.tag_ids = row.tags ? row.tags.map(t => t.id) : []
  dialogVisible.value = true
}

const resetForm = () => {
  form.english = ''
  form.chinese = ''
  form.phonetic = ''
  form.grade = null
  form.semester = null
  form.tag_ids = []
}

const saveWord = async () => {
  if (!form.english || !form.chinese) {
    ElMessage.warning('请填写必填项')
    return
  }

  try {
    if (isEdit.value) {
      await wordApi.update(currentWordId.value, form)
      ElMessage.success('更新成功')
    } else {
      await wordApi.create(form)
      ElMessage.success('创建成功')
    }
    dialogVisible.value = false
    fetchWords()
  } catch (error) {
    ElMessage.error('保存失败')
  }
}

const deleteWord = async (row) => {
  try {
    await ElMessageBox.confirm('确定删除该单词吗？', '提示', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning',
    })
    await wordApi.delete(row.id)
    ElMessage.success('删除成功')
    fetchWords()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('删除失败')
    }
  }
}

// 复习
const startReview = () => {
  reviewStep.value = 'config'
  // 如果有选中单词，默认数量为选中数量
  if (selectedWords.value.length > 0) {
    reviewConfig.count = selectedWords.value.length
  }
  reviewVisible.value = true
}

const handleSelectionChange = (selection) => {
  selectedWords.value = selection
}

const startReviewGame = async () => {
  try {
    const params = {
      count: reviewConfig.count,
    }
    if (reviewConfig.grade) params.grade = reviewConfig.grade
    // 如果有选中单词，传递单词ID列表
    if (selectedWords.value.length > 0) {
      params.word_ids = selectedWords.value.map(w => w.id).join(',')
    }

    const { data } = await wordApi.startReview(params)
    reviewQuestions.value = data.questions.map(q => ({
      ...q,
      correct: undefined,
    }))
    currentSessionId.value = data.session_id
    currentIndex.value = 0
    userAnswer.value = ''
    selectedOption.value = ''
    currentQuestion.value = reviewQuestions.value[0]
    reviewStep.value = 'question'

    // 启动计时器
    reviewStartTime.value = Date.now()
    reviewElapsed.value = 0
    reviewTimer.value = setInterval(() => {
      reviewElapsed.value = Math.floor((Date.now() - reviewStartTime.value) / 1000)
    }, 1000)
  } catch (error) {
    ElMessage.error('获取复习内容失败')
  }
}

const submitAnswer = () => {
  const q = currentQuestion.value
  if (reviewConfig.type === 1) {
    // 默写
    q.correct = userAnswer.value.toLowerCase().trim() === q.english.toLowerCase().trim()
    q.userAnswer = userAnswer.value
  } else {
    // 选择
    q.correct = selectedOption.value === q.chinese
    q.userAnswer = selectedOption.value
  }
  // 显示答案后自动进入下一题
  if (currentIndex.value < reviewQuestions.value.length - 1) {
    setTimeout(() => {
      nextQuestion()
    }, 1500)
  }
}

const nextQuestion = () => {
  currentIndex.value++
  currentQuestion.value = reviewQuestions.value[currentIndex.value]
  userAnswer.value = ''
  selectedOption.value = ''
  setTimeout(() => {
    const input = answerInputRef.value?.$el?.querySelector('input')
    if (input) {
      input.focus()
    } else {
      answerInputRef.value?.focus()
    }
  }, 100)
}

// 终止答题，结算已答题目
const terminateReview = async () => {
  try {
    await ElMessageBox.confirm('确定要终止答题吗？已答题目将按实际结果结算。', '终止确认', {
      confirmButtonText: '确定终止',
      cancelButtonText: '继续答题',
      type: 'warning',
    })
    // 将未作答的题目标记为错误
    for (const q of reviewQuestions.value) {
      if (q.correct === undefined) {
        q.correct = false
      }
    }
    await finishReview()
  } catch (error) {
    // 用户取消，继续答题
  }
}

const finishReview = async () => {
  // 停止计时器
  if (reviewTimer.value) {
    clearInterval(reviewTimer.value)
    reviewTimer.value = null
  }
  const duration = reviewElapsed.value

  const results = reviewQuestions.value.map(q => ({
    word_id: q.word_id,
    is_correct: q.correct,
    user_answer: q.userAnswer || '',
    review_type: reviewConfig.type,
  }))

  try {
    const { data } = await wordApi.submitReview({
      session_id: currentSessionId.value,
      results,
      duration,
    })
    reviewResult.total = data.total
    reviewResult.correct = data.correct
    reviewResult.error = data.error
    reviewResult.accuracy = data.accuracy
    reviewResult.duration = duration
    reviewStep.value = 'result'

    // 调用单词正确率成就检查
    try {
      await motivationApi.triggerWordAccuracy({
        total_count: data.total,
        correct_count: data.correct,
        reason: '单词复习'
      })
    } catch (error) {
      console.error('激励触发失败:', error)
    }
  } catch (error) {
    ElMessage.error('提交结果失败')
  }
}

// 打印
const showPrintDialog = () => {
  printDialogVisible.value = true
}

const generatePrintPdf = async () => {
  try {
    const params = { count: printForm.count }
    if (printForm.grade) params.grade = printForm.grade

    const { data } = await wordApi.printPdf(params)
    window.open(data.pdf_url, '_blank')
    printDialogVisible.value = false
    ElMessage.success('PDF已生成')
  } catch (error) {
    ElMessage.error('生成PDF失败')
  }
}

// 导入
const showImportDialog = () => {
  importForm.mode = 'text'
  importForm.text = ''
  importForm.file = null
  importForm.image = null
  importForm.ocrText = ''
  importForm.parsedWords = []
  importForm.grade = null
  importForm.semester = null
  importForm.tag_ids = []
  importDialogVisible.value = true
}

const handleFileChange = (file) => {
  onFileChange(file)
}

const handleImageChange = async (file) => {
  importForm.image = file.raw
  // 自动调用OCR识别
  await recognizeImage(file.raw)
}

const handleImageRemove = () => {
  importForm.image = null
  importForm.ocrText = ''
  importForm.parsedWords = []
}

// 文本模式变化时更新预览
const onTextChange = () => {
  if (importForm.mode === 'text' && importForm.text.trim()) {
    importForm.parsedWords = smartParseWords(importForm.text)
  }
}

// 文件模式变化时
const onFileChange = (file) => {
  importForm.file = file.raw
  if (file.raw) {
    const reader = new FileReader()
    reader.onload = e => {
      importForm.parsedWords = smartParseWords(e.target.result)
    }
    reader.readAsText(file.raw)
  }
}

const recognizeImage = async (file) => {
  try {
    const formData = new FormData()
    formData.append('file', file)

    const response = await fetch('/api/upload/image', {
      method: 'POST',
      body: formData,
    })

    if (!response.ok) {
      throw new Error('OCR识别失败')
    }

    const result = await response.json()
    if (result.ocr_result && result.ocr_result.full_text) {
      importForm.ocrText = result.ocr_result.full_text
      // 智能分隔单词并更新预览
      importForm.parsedWords = smartParseWords(result.ocr_result.full_text)
      ElMessage.success('图片识别成功，请检查识别结果')
    } else {
      ElMessage.warning('未识别到文字，请上传更清晰的图片')
    }
  } catch (error) {
    console.error('OCR error:', error)
    ElMessage.error('图片识别失败，请尝试其他方式导入')
  }
}

// 智能分隔单词 - 自动识别英文和中文
const smartParseWords = (text) => {
  // 清理OCR噪声字符（保留\n\r）
  const cleaned = text
    .replace(/[\u0001-\u0009\u000B\u000C\u000E-\u001F\u007F-\u009F]/g, '') // 移除控制字符（保留\n\r即10和13）
    .replace(/['']/g, "'")  // 规范化撇号
    .replace(/[""]/g, '"')
    .replace(/（/g, '(').replace(/）/g, ')')  // 规范化中文括号
    .replace(/[ \t]+/g, ' ')   // 规范化空格（保留换行）

  const words = []

  // 按行分割
  const lines = cleaned.split('\n')

  for (const line of lines) {
    const trimmed = line.trim()
    if (!trimmed) continue

    // 分割本行的各个单词（按制表符或连续空格分割）
    // 格式如: "1.mess 杂乱  2.whose 谁的" 或 "1.mess 杂乱\t2.whose 谁的"
    const entries = trimmed.split(/(?:\t|  +)(?=\d+\.)/)

    for (const entry of entries) {
      if (!entry.trim()) continue

      // 去掉序号前缀，如 "1.mess" 或 "1. mess"
      let content = entry.replace(/^\d+\.?\s*/, '').trim()
      if (!content) continue

      let phonetic = ''
      let english = ''
      let chinese = ''

      // 先提取音标 /eɪ/ 或 [音标] 格式（可能在末尾或中间）
      // 提取末尾的 /音标/ 格式
      const phoneticMatch = content.match(/\/([^\/]+)\/$/)
      if (phoneticMatch) {
        phonetic = phoneticMatch[1]
        content = content.replace(/\/[^\/]+\/$/, '').trim()
      }
      // 提取 [音标] 格式
      const bracketPhonetic = content.match(/\[([^\]]+)\]/)
      if (bracketPhonetic) {
        phonetic = bracketPhonetic[1]
        content = content.replace(/\[[^\]]+\]/, '').trim()
      }

      // 去掉末尾的括号注释如 (复数)
      content = content.replace(/\s*\([^)]*\)\s*$/, '').trim()

      // 分离英文和中文
      // 格式1: 英文 + 空格 + 中文（如 "mess 杂乱" 或 "school bag 书包"）
      // 格式2: 只有英文或只有中文
      // 格式3: 英文 + 空格 + 音标（如 "baby /eɪ/"）

      // 尝试按空格分割
      const parts = content.split(/\s+/)

      if (parts.length >= 2) {
        // 检查第一部分是否是纯英文
        const firstPart = parts[0]
        const isEnglish = /^[a-zA-Z][a-zA-Z'-]*$/.test(firstPart) ||
                          /^[a-zA-Z][a-zA-Z'-]*(?:\s+[a-zA-Z][a-zA-Z'-]*)+$/.test(firstPart)

        if (isEnglish) {
          english = firstPart
          // 剩余部分是中文或其他
          const rest = parts.slice(1).join(' ').trim()
          if (rest) {
            // 检查是否是音标格式
            if (rest.startsWith('/') && rest.endsWith('/')) {
              phonetic = rest.slice(1, -1)
            } else {
              chinese = rest
            }
          }
        } else {
          // 第一部分不是纯英文，可能是中文
          chinese = content
        }
      } else if (parts.length === 1) {
        // 只有一个部分
        const part = parts[0]
        if (/^[a-zA-Z][a-zA-Z'-]*$/.test(part) || /^[a-zA-Z][a-zA-Z'-]*(?:\s+[a-zA-Z][a-zA-Z'-]*)+$/.test(part)) {
          // 纯英文
          english = part
        } else {
          // 纯中文
          chinese = part
        }
      }

      if (english || chinese) {
        words.push({
          english: english || '',
          chinese: chinese || '',
          phonetic: phonetic || '',
          original: entry
        })
      }
    }
  }

  return words
}

const parseTextToWords = (text) => {
  const lines = text.trim().split('\n')
  const words = []
  for (const line of lines) {
    const trimmed = line.trim()
    if (!trimmed) continue
    // 智能分隔
    const parsed = smartParseWords(trimmed)
    if (parsed.length > 0) {
      words.push(parsed[0])
    }
  }
  return words
}

const importWords = async () => {
  let words = []

  // 优先使用预览表格中的数据（用户可能已编辑）
  if (importForm.parsedWords && importForm.parsedWords.length > 0) {
    words = importForm.parsedWords.filter(w => w.english && w.chinese)
  } else if (importForm.mode === 'text') {
    if (!importForm.text.trim()) {
      ElMessage.warning('请输入单词内容')
      return
    }
    words = smartParseWords(importForm.text)
  } else if (importForm.mode === 'file') {
    if (!importForm.file) {
      ElMessage.warning('请选择文件')
      return
    }
    // 读取文件内容
    try {
      const reader = new FileReader()
      const fileContent = await new Promise((resolve, reject) => {
        reader.onload = e => resolve(e.target.result)
        reader.onerror = reject
        reader.readAsText(importForm.file)
      })
      words = smartParseWords(fileContent)
    } catch (error) {
      ElMessage.error('读取文件失败')
      return
    }
  } else if (importForm.mode === 'image') {
    if (!importForm.ocrText.trim()) {
      ElMessage.warning('请先上传图片并等待识别完成')
      return
    }
    words = smartParseWords(importForm.ocrText)
  }

  if (words.length === 0) {
    ElMessage.warning('未解析到有效单词')
    return
  }

  importing.value = true
  let successCount = 0
  let failCount = 0

  for (const word of words) {
    try {
      await wordApi.create({
        english: word.english,
        chinese: word.chinese,
        phonetic: word.phonetic || undefined,
        grade: importForm.grade,
        semester: importForm.semester,
        tag_ids: importForm.tag_ids,
      })
      successCount++
    } catch (error) {
      failCount++
    }
  }

  importing.value = false
  importDialogVisible.value = false

  ElMessage.success(`导入完成：成功 ${successCount} 个，失败 ${failCount} 个`)
  fetchWords()
}

onMounted(() => {
  fetchWords()
  fetchTags()
})
</script>

<style scoped>
.words {
  max-width: 1400px;
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

.word-english {
  font-weight: bold;
  color: #409eff;
  font-size: 16px;
}

.phonetic {
  color: #909399;
  font-family: monospace;
}

.review-info .correct {
  color: #67c23a;
  font-weight: bold;
}

.review-info .total {
  color: #909399;
}

.pagination {
  margin-top: 20px;
  display: flex;
  justify-content: flex-end;
}

/* 复习弹窗样式 */
:deep(.review-dialog) {
  --review-scale: 1;
  transform: scale(var(--review-scale));
  transform-origin: center center;
}

:deep(.review-dialog .el-dialog__body) {
  padding: 0;
}

/* 复习弹窗背景虚化 */
:deep(.el-overlay-dialog) {
  backdrop-filter: blur(8px);
  background: rgba(0, 0, 0, 0.3) !important;
}

.review-config {
  padding: 40px;
  font-size: 20px;
}

.review-question {
  padding: 40px;
  display: flex;
  flex-direction: column;
  height: 70vh;
  max-height: 600px;
}

.question-header {
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 40px;
  margin-bottom: 30px;
  flex-shrink: 0;
  position: sticky;
  top: 0;
  background: #fff;
  z-index: 10;
  padding: 10px 0;
}

.progress {
  font-size: 36px;
  font-weight: bold;
  color: #409eff;
}

.timer {
  font-size: 32px;
  color: #909399;
  font-family: monospace;
  font-weight: 600;
}

.result-display {
  text-align: center;
  padding: 24px 48px;
  border-radius: 16px;
  margin-bottom: 30px;
}

.correct-display {
  background: linear-gradient(135deg, #67c23a 0%, #5daf34 100%);
  color: #fff;
}

.wrong-display {
  background: linear-gradient(135deg, #f56c6c 0%, #e64242 100%);
  color: #fff;
}

.result-status {
  font-size: 32px;
  font-weight: bold;
  margin-bottom: 8px;
}

.result-answer-large {
  font-size: 36px;
  font-weight: bold;
}

.your-answer {
  font-size: 24px;
  margin-top: 8px;
  opacity: 0.9;
}

.question-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  justify-content: center;
}

.dictation {
  text-align: center;
  padding: 20px;
}

.dictation .chinese {
  font-size: 72px;
  font-weight: bold;
  color: #303133;
  margin-bottom: 30px;
  letter-spacing: 8px;
}

.dictation .hint-box {
  margin-bottom: 40px;
}

.dictation .hint {
  font-size: 28px;
  color: #606266;
  background: #f5f7fa;
  padding: 12px 32px;
  border-radius: 8px;
  display: inline-block;
  margin-bottom: 20px;
}

.dictation .answer-input {
  max-width: 600px;
  margin: 0 auto;
}

.dictation .answer-input :deep(.el-input__wrapper) {
  padding: 20px 30px;
  border-radius: 12px;
  border: 3px solid #dcdfe6;
  box-shadow: none;
  transition: all 0.3s;
}

.dictation .answer-input :deep(.el-input__wrapper.is-focus) {
  border-color: #409eff;
  box-shadow: 0 0 0 4px rgba(64, 158, 255, 0.1);
}

.dictation .answer-input :deep(.el-input__inner) {
  font-size: 48px;
  text-align: center;
  letter-spacing: 5px;
  height: 80px;
  line-height: 80px;
}

.result {
  margin-top: 30px;
  padding: 16px 32px;
  border-radius: 12px;
  display: inline-block;
  font-size: 28px;
}

.result.correct-result {
  background: #f0f9eb;
  color: #67c23a;
  border: 2px solid #67c23a;
}

.result.wrong-result {
  background: #fef0f0;
  color: #f56c6c;
  border: 2px solid #f56c6c;
}

.correct-answer {
  font-size: 28px;
  font-weight: bold;
}

.wrong-result .correct-answer {
  color: #67c23a;
}

.correct-result .correct-answer {
  color: #909399;
}

/* 答题正确动画 */
@keyframes correctPulse {
  0% { transform: scale(1); }
  50% { transform: scale(1.05); }
  100% { transform: scale(1); }
}

@keyframes correctGlow {
  0% { box-shadow: 0 0 0 0 rgba(103, 194, 58, 0.4); }
  50% { box-shadow: 0 0 30px 10px rgba(103, 194, 58, 0.2); }
  100% { box-shadow: 0 0 0 0 rgba(103, 194, 58, 0); }
}

.result.correct-result {
  animation: correctPulse 0.5s ease-out, correctGlow 0.8s ease-out;
}

.result.correct-result .correct-answer {
  color: #67c23a;
}

/* 答题错误动画 */
@keyframes wrongShake {
  0%, 100% { transform: translateX(0); }
  20%, 60% { transform: translateX(-10px); }
  40%, 80% { transform: translateX(10px); }
}

.result.wrong-result {
  animation: wrongShake 0.5s ease-out;
}

.result.wrong-result .correct-answer {
  color: #f56c6c;
}

.choice {
  text-align: center;
}

.choice .english {
  font-size: 64px;
  font-weight: bold;
  color: #409eff;
  margin-bottom: 50px;
}

.choice .el-radio-group {
  display: flex;
  flex-direction: column;
  gap: 25px;
  align-items: center;
}

.choice .el-radio {
  font-size: 28px;
  padding: 20px 40px;
  min-width: 400px;
}

.choice .el-radio .el-radio__label {
  font-size: 28px;
}

.question-actions {
  margin-top: 40px;
  text-align: center;
  flex-shrink: 0;
}

.question-actions .el-button {
  font-size: 28px;
  padding: 25px 80px;
}

.review-result {
  padding: 60px;
  text-align: center;
}

.result-summary {
  margin-bottom: 60px;
}

.big-number {
  font-size: 144px;
  font-weight: bold;
  color: #409eff;
}

.label {
  font-size: 36px;
  color: #909399;
}

.error-word-list {
  margin-top: 20px;
  padding: 16px;
  background: #fef0f0;
  border-radius: 8px;
  text-align: left;
}

.error-word-list h4 {
  margin: 0 0 12px 0;
  color: #f56c6c;
}

.error-words {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 12px;
}

.error-word-item {
  background: #fff;
  padding: 12px;
  border-radius: 6px;
  border-left: 3px solid #f56c6c;
}

.error-word-info {
  display: flex;
  justify-content: space-between;
  margin-bottom: 8px;
}

.error-word-info .word-english {
  font-weight: bold;
  color: #303133;
}

.error-word-info .word-chinese {
  color: #606266;
}

.error-word-user {
  font-size: 13px;
}

.error-word-user .label {
  color: #909399;
}

.error-word-user .user-answer {
  color: #f56c6c;
}

.result-detail {
  font-size: 32px;
  line-height: 2.5;
  margin-bottom: 60px;
}

.ocr-preview {
  margin-top: 15px;
  padding: 10px;
  background-color: #f5f7fa;
  border-radius: 4px;
}

.ocr-label {
  font-weight: bold;
  margin-bottom: 8px;
  color: #409eff;
}

.words-preview {
  margin-top: 10px;
  border: 1px solid #ebeef5;
  border-radius: 4px;
  padding: 10px;
  background-color: #fafafa;
}

.preview-summary {
  margin-top: 10px;
  text-align: right;
  color: #909399;
  font-size: 14px;
}

/* 记忆曲线样式 */
.memory-curve {
  padding: 20px;
}
.phase-bar {
  margin-bottom: 20px;
}
.phase-track {
  position: relative;
  height: 40px;
  background: #f0f0f0;
  border-radius: 20px;
}
.phase-dot {
  position: absolute;
  top: 50%;
  transform: translate(-50%, -50%);
  padding: 4px 8px;
  background: #fff;
  border-radius: 4px;
  font-size: 12px;
  border: 2px solid #ddd;
}
.phase-dot.active {
  background: #409eff;
  color: #fff;
  border-color: #409eff;
}
.next-review {
  margin-bottom: 20px;
  font-size: 16px;
  color: #666;
}
.review-history {
  border-top: 1px solid #eee;
  padding-top: 15px;
}
.history-title {
  font-weight: bold;
  margin-bottom: 10px;
}
.history-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 0;
  font-size: 14px;
}
.history-date {
  min-width: 100px;
}
.history-correct {
  color: #67c23a;
}
.history-wrong {
  color: #f56c6c;
}

/* 禁用卡片的hover效果 */
.words :deep(.el-card) {
  transition: none;
}
.words :deep(.el-card:hover) {
  transform: none;
  box-shadow: var(--shadow-sm) !important;
}
</style>
