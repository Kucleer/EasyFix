<template>
  <div class="reading-page">
    <PageHeading title="读一篇，发现一个新世界" description="让阅读成为习惯，也让表达更加自然。" />
    <el-row :gutter="20">
      <!-- 左侧短文列表 -->
      <el-col :xs="24" :sm="10">
        <el-card>
          <template #header>
            <div class="card-header">
              <span>短文库</span>
              <el-button type="primary" size="small" @click="showGenerateDialog = true">
                生成短文
              </el-button>
            </div>
          </template>

          <!-- 筛选 -->
          <div class="filters">
            <el-button size="small" type="primary" plain @click="filters.grade = 6; applyFilters()">六年级新短文</el-button>
            <el-select v-model="filters.topic" placeholder="话题" clearable size="small" @change="applyFilters" style="width: 110px">
              <el-option v-for="t in topics" :key="t" :label="t" :value="t" />
            </el-select>
            <el-select v-model="filters.grade" placeholder="全部年级" clearable size="small" @change="applyFilters" style="width: 90px">
              <el-option v-for="g in 12" :key="g" :label="g + '年级'" :value="g" />
            </el-select>
            <el-select v-model="filters.difficulty" placeholder="难度" clearable size="small" @change="fetchReadings" style="width: 90px">
              <el-option label="⭐" :value="1" />
              <el-option label="⭐⭐" :value="2" />
              <el-option label="⭐⭐⭐" :value="3" />
              <el-option label="⭐⭐⭐⭐" :value="4" />
              <el-option label="⭐⭐⭐⭐⭐" :value="5" />
            </el-select>
          </div>

          <div class="reading-count">共 {{ total }} 篇短文 · 默认显示全部年级</div>
          <!-- 列表 -->
          <div v-if="loading" class="loading">加载中...</div>
          <div v-else-if="loadError" class="empty"><p>{{ loadError }}</p><el-button @click="fetchReadings">重新加载</el-button></div>
          <div v-else-if="readings.length === 0" class="empty"><p>当前条件下没有短文</p><el-button @click="clearFilters">查看全部历史短文</el-button></div>
          <div v-else class="passage-list">
            <div
              v-for="item in readings"
              :key="item.id"
              class="passage-card"
              :class="{ active: selectedId === item.id }"
              @click="selectPassage(item)"
            >
              <div class="passage-title">{{ item.title }}</div>
              <div class="passage-meta">
                <el-tag size="small" type="info">{{ item.topic }}</el-tag>
                <span class="meta-item">{{ item.grade }}年级</span>
                <span class="meta-item">{{ '⭐'.repeat(item.difficulty) }}</span>
                <span class="meta-item">{{ item.word_count || '-' }}词</span>
                <span v-if="item.provenance" class="meta-item">来源 {{ item.provenance.published_at }} · 适龄改写</span>
              </div>
            </div>
          </div>
          <el-pagination v-if="total > pageSize" v-model:current-page="currentPage" :page-size="pageSize" :total="total" layout="prev, pager, next" @current-change="fetchReadings" />
        </el-card>
      </el-col>

      <!-- 右侧详情 -->
      <el-col :xs="24" :sm="14">
        <el-card v-if="selectedPassage">
          <template #header>
            <div class="card-header">
              <span>{{ selectedPassage.title }}</span>
              <div>
                <el-button type="success" size="small" @click="createPracticeSet">
                  创建练习集
                </el-button>
                <el-button type="danger" size="small" @click="deletePassage">
                  删除
                </el-button>
              </div>
            </div>
          </template>

          <el-alert v-if="selectedPassage.provenance" type="info" :closable="false"><template #title>{{ selectedPassage.provenance.source_name }} · 来源发布于 {{ selectedPassage.provenance.published_at }} · AI 适龄改写与配题</template><p>正文、习题和解析已保存在本地。原始来源为科学文章，不是原站分级课程。</p></el-alert>
          <div class="passage-content">
            <p v-for="(para, idx) in contentParagraphs" :key="idx" class="paragraph">
              {{ para }}
            </p>
          </div>

          <el-divider />

          <div class="questions-section">
            <h4>选择题（共 {{ selectedPassage.questions.length }} 题）</h4>
            <div v-for="q in selectedPassage.questions" :key="q.id" class="question-item">
              <p class="question-text">{{ q.question_number }}. {{ q.question_text }}</p>
              <div class="options">
                <div class="option">{{ formatOption('A', q.option_a) }}</div>
                <div class="option">{{ formatOption('B', q.option_b) }}</div>
                <div class="option">{{ formatOption('C', q.option_c) }}</div>
                <div class="option">{{ formatOption('D', q.option_d) }}</div>
              </div>
              <el-button v-if="showAllAnswers" size="small" type="warning" @click="toggleQuestionAnswer(q)">
                {{ q._showAnswer ? '隐藏答案' : '查看答案' }}
              </el-button>
              <div v-if="q._showAnswer" class="answer-box">
                <strong>答案：{{ q.correct_answer }}</strong> —— {{ q.explanation }}
              </div>
            </div>
            <div style="margin-top: 10px">
              <el-button size="small" @click="showAllAnswers = !showAllAnswers">
                {{ showAllAnswers ? '全部隐藏答案' : '全部显示答案' }}
              </el-button>
            </div>
          </div>
        </el-card>

        <el-card v-else>
          <div class="empty-detail">请在左侧选择一篇短文</div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 生成短文弹窗 -->
    <el-dialog v-model="showGenerateDialog" title="生成英语短文" width="450px">
      <el-form :model="generateForm" label-width="80px">
        <el-form-item label="年级">
          <el-select v-model="generateForm.grade" style="width: 100%">
            <el-option v-for="g in 12" :key="g" :label="g + '年级'" :value="g" />
          </el-select>
        </el-form-item>
        <el-form-item label="话题">
          <el-select v-model="generateForm.topic" style="width: 100%">
            <el-option v-for="t in topics" :key="t" :label="t" :value="t" />
          </el-select>
        </el-form-item>
        <el-form-item label="难度">
          <el-rate v-model="generateForm.difficulty" :max="5" show-score />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showGenerateDialog = false">取消</el-button>
        <el-button type="primary" :loading="generating" @click="doGenerate">
          {{ generating ? '生成中...' : '生成' }}
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import PageHeading from '@/components/PageHeading.vue'
import readingProvenance from '@/data/reading-provenance.json'
import { ref, reactive, computed, onMounted } from 'vue'
import { useAppConfigStore } from '@/stores/appConfig'
import { ElMessage, ElMessageBox } from 'element-plus'
import axios from 'axios'

const readings = ref([])
const topics = ref([])
const selectedId = ref(null)
const selectedPassage = ref(null)
const loading = ref(false)
const loadError = ref('')
const total = ref(0)
const currentPage = ref(1)
const pageSize = 20
const showAllAnswers = ref(false)
const showGenerateDialog = ref(false)
const generating = ref(false)

const appConfigStore = useAppConfigStore()
const filters = reactive({
  topic: '',
  grade: null,
  difficulty: null,
})

const generateForm = reactive({
  grade: null,
  topic: '校园生活',
  difficulty: 3,
})

// 格式化选项（带字母前缀，避免重复）
function formatOption(letter, text) {
  if (!text) return ''
  text = text.trim()
  // 去除已有的选项前缀（A. B. C. D. / A、B、C、D、 / (A) / A) 等各种格式）
  text = text.replace(/^[A-Da-d]\s*[.、．]\s*/, '')
  text = text.replace(/^\([A-Da-d]\)\s*/, '')
  text = text.replace(/^[A-Da-d]\)\s*/, '')
  return letter + '. ' + text
}

const contentParagraphs = computed(() => {
  if (!selectedPassage.value) return []
  return selectedPassage.value.content.split('\n').filter(p => p.trim())
})

async function fetchTopics() {
  try {
    const res = await axios.get('/api/readings/topics')
    topics.value = res.data
  } catch {
    topics.value = []
  }
}

function applyFilters() {
  currentPage.value = 1
  fetchReadings()
}

function clearFilters() {
  Object.assign(filters, { topic: '', grade: null, difficulty: null })
  applyFilters()
}

async function fetchReadings() {
  loading.value = true
  loadError.value = ''
  try {
    const params = { skip: (currentPage.value - 1) * pageSize, limit: pageSize }
    if (filters.topic) params.topic = filters.topic
    if (filters.grade) params.grade = filters.grade
    if (filters.difficulty) params.difficulty = filters.difficulty
    const res = await axios.get('/api/readings', { params })
    readings.value = (res.data.items || []).map(item => ({ ...item, provenance: item.provenance || readingProvenance[item.source] }))
    total.value = res.data.total || 0
    if (selectedId.value && !readings.value.some(item => item.id === selectedId.value)) {
      selectedId.value = null
      selectedPassage.value = null
    }
  } catch {
    loadError.value = '短文加载失败，请重试。'
    ElMessage.error('获取短文列表失败')
  } finally {
    loading.value = false
  }
}

async function selectPassage(item) {
  selectedId.value = item.id
  selectedPassage.value = null
  try {
    const res = await axios.get(`/api/readings/${item.id}`)
    selectedPassage.value = { ...res.data, provenance: res.data.provenance || readingProvenance[res.data.source] }
  } catch {
    ElMessage.error('获取短文详情失败')
  }
}

function toggleQuestionAnswer(q) {
  q._showAnswer = !q._showAnswer
}

async function doGenerate() {
  generating.value = true
  try {
    await axios.post('/api/readings/generate', generateForm)
    ElMessage.success('生成成功')
    showGenerateDialog.value = false
    await fetchReadings()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '生成失败')
  } finally {
    generating.value = false
  }
}

async function deletePassage() {
  if (!selectedPassage.value) return
  try {
    await ElMessageBox.confirm('确定删除这篇短文？')
    await axios.delete(`/api/readings/${selectedPassage.value.id}`)
    ElMessage.success('删除成功')
    selectedPassage.value = null
    selectedId.value = null
    await fetchReadings()
  } catch {
    // 取消删除
  }
}

async function createPracticeSet() {
  if (!selectedPassage.value) return
  try {
    const res = await axios.post('/api/practice-sets/generate-from-reading', {
      passage_id: selectedPassage.value.id,
    })
    ElMessage.success('练习集创建成功')
    window.location.href = `/reading-test/${res.data.id}`
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '创建失败')
  }
}

onMounted(async () => {
  await appConfigStore.load()
  if (generateForm.grade == null && appConfigStore.defaultGrade != null) {
    generateForm.grade = appConfigStore.defaultGrade
  }
  fetchTopics()
  await fetchReadings()
})
</script>

<style scoped>
.reading-count { font-size: 12px; color: var(--text-muted); margin-bottom: 10px; }
.reading-page  {
   padding: 10px;
   }
.card-header  {
   display: flex;
   justify-content: space-between;
   align-items: center;
   flex-wrap: wrap;
   gap: 8px;
   }
.filters  {
   display: flex;
   gap: 8px;
   margin-bottom: 15px;
   flex-wrap: wrap;
   }
.passage-list  {
   max-height: 600px;
   overflow-y: auto;
   }
.passage-card  {
   padding: 12px;
   border: 1px solid #ebeef5;
   border-radius: 6px;
   margin-bottom: 8px;
   cursor: pointer;
   transition: all 0.2s;
   }
.passage-card:hover  {
   border-color: var(--accent-blue);
   }
.passage-card.active  {
   border-color: var(--accent-blue);
   background-color: #ecf5ff;
   }
.passage-title  {
   font-weight: bold;
   margin-bottom: 6px;
   }
.passage-meta  {
   display: flex;
   gap: 8px;
   align-items: center;
   font-size: 12px;
   color: var(--text-muted);
   flex-wrap: wrap;
   }
.passage-content  {
   line-height: 1.8;
   font-size: 14px;
   }
.paragraph  {
   margin-bottom: 10px;
   text-indent: 2em;
   }
.question-item  {
   margin-bottom: 16px;
   padding: 12px;
   background: #fafafa;
   border-radius: 4px;
   }
.question-text  {
   font-weight: bold;
   margin-bottom: 8px;
   }
.option  {
   padding: 4px 0;
   }
.answer-box  {
   margin-top: 6px;
   padding: 6px 10px;
   background: #fdf6ec;
   border-radius: 4px;
   color: #e6a23c;
   font-size: 13px;
   }
.loading, .empty, .empty-detail  {
   text-align: center;
   padding: 40px;
   color: var(--text-muted);
   }
@media (max-width: 768px)  {

  .passage-list  {
   max-height: 300px;
   }
}
.reading-page {
  padding:0}
.passage-card {
  padding:14px;
  border-radius:9px;
  border-color:var(--border-light);
  margin-bottom:9px}
.passage-card.active {
  background:#eeedff;
  border-color:var(--accent-blue)}
.passage-title {
  font-size:15px}
.passage-content {
  font-size:16px;
  line-height:1.9}
.answer-box {
  color:#8b641f;
  background:#fff6e6}
.passage-meta {
  color:var(--text-muted)}
</style>
