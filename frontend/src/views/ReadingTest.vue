<template>
  <div class="reading-test">
    <PageHeading title="阅读练习" description="读懂文章，再从文中寻找答案。" />
    <el-card>
      <template #header>
        <div class="card-header">
          <span>阅读理解测试 - {{ practiceSet?.name || '' }}</span>
          <div>
            <el-button @click="downloadPdf" :loading="downloading" type="success">打印PDF</el-button>
            <el-button @click="goBack">返回</el-button>
          </div>
        </div>
      </template>

      <div v-if="passage" class="test-container">
        <el-row :gutter="20">
          <!-- 短文区 -->
          <el-col :xs="24" :md="12" class="passage-col">
            <div class="passage-scroll">
              <h3>{{ passage.title }}</h3>
              <p v-for="(para, idx) in contentParagraphs" :key="idx" class="paragraph">
                {{ para }}
              </p>
              <div class="meta-bar">
                <el-tag size="small">{{ passage.topic }}</el-tag>
                <span class="meta-item">{{ passage.grade }}年级</span>
                <span class="meta-item">{{ '⭐'.repeat(passage.difficulty) }}</span>
                <span class="meta-item">{{ passage.word_count }}词</span>
              </div>
            </div>
          </el-col>

          <!-- 答题区 -->
          <el-col :xs="24" :md="12" class="answer-col">
            <h4>选择题</h4>
            <div v-for="q in questions" :key="q.id" class="question-block">
              <p class="q-text">{{ q.question_number }}. {{ q.question_text }}</p>
              <el-radio-group v-model="answers[q.id]" class="options-group">
                <el-radio :value="'A'" class="option-item">{{ formatOption('A', q.option_a) }}</el-radio>
                <el-radio :value="'B'" class="option-item">{{ formatOption('B', q.option_b) }}</el-radio>
                <el-radio :value="'C'" class="option-item">{{ formatOption('C', q.option_c) }}</el-radio>
                <el-radio :value="'D'" class="option-item">{{ formatOption('D', q.option_d) }}</el-radio>
              </el-radio-group>
            </div>

            <div class="action-bar">
              <el-button v-if="!testResult" type="primary" size="large" :disabled="!allAnswered" @click="submitTest">
                交卷
              </el-button>
            </div>

            <!-- 结果展示 -->
            <div v-if="testResult" class="result-box" :class="resultRate >= 60 ? 'pass' : 'fail'">
              <h4>测试结果</h4>
              <p class="result-summary">正确：{{ resultCorrect }}/{{ resultTotal }}（{{ resultRate }}%）</p>
              <div v-for="q in questions" :key="q.id" class="result-item">
                <span :class="answers[q.id] === q.correct_answer ? 'correct' : 'wrong'">
                  <strong>Q{{ q.question_number }}:</strong>
                  <template v-if="answers[q.id] === q.correct_answer"> ✓ 正确</template>
                  <template v-else> ✗ 你的答案: {{ answers[q.id] }}, 正确答案: {{ q.correct_answer }}</template>
                </span>
                <p v-if="q.explanation" class="explanation">{{ q.explanation }}</p>
              </div>
            </div>
          </el-col>
        </el-row>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import PageHeading from '@/components/PageHeading.vue'
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import axios from 'axios'
import { useRoute, useRouter } from 'vue-router'

const route = useRoute()
const router = useRouter()
const practiceSetId = route.params.id

const practiceSet = ref(null)
const passage = ref(null)
const questions = ref([])
const answers = ref({})
const testResult = ref(false)
const downloading = ref(false)

const contentParagraphs = computed(() => {
  if (!passage.value) return []
  return passage.value.content.split('\n').filter(p => p.trim())
})

const allAnswered = computed(() => {
  return questions.value.length > 0 && questions.value.every(q => answers.value[q.id])
})

const resultCorrect = computed(() => {
  return questions.value.filter(q => answers.value[q.id] === q.correct_answer).length
})

const resultTotal = computed(() => questions.value.length)

const resultRate = computed(() => {
  return resultTotal.value > 0 ? Math.round(resultCorrect.value / resultTotal.value * 100) : 0
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

async function fetchTestData() {
  try {
    const res = await axios.get(`/api/practice-sets/${practiceSetId}`)
    practiceSet.value = res.data

    if (res.data.passage_id) {
      const passageRes = await axios.get(`/api/readings/${res.data.passage_id}`)
      passage.value = passageRes.data
      questions.value = passageRes.data.questions || []
    }
  } catch {
    ElMessage.error('获取测试数据失败')
  }
}

async function submitTest() {
  const results = questions.value.map(q => ({
    question_id: q.id,
    is_correct: answers.value[q.id] === q.correct_answer,
  }))

  try {
    await axios.post(`/api/practice-sets/${practiceSetId}/mark-reviewed`, {
      question_results: JSON.stringify(results),
    })
    testResult.value = true
  } catch {
    ElMessage.error('提交失败')
  }
}

function goBack() {
  router.push('/reading')
}

async function downloadPdf() {
  downloading.value = true
  try {
    const res = await axios.post(`/api/practice-sets/${practiceSetId}/generate-pdf`)
    window.open(res.data.pdf_url, '_blank')
  } catch {
    ElMessage.error('PDF生成失败')
  } finally {
    downloading.value = false
  }
}

onMounted(fetchTestData)
</script>

<style scoped>
.reading-test  {
   padding: 10px;
   }
.card-header  {
   display: flex;
   justify-content: space-between;
   align-items: center;
   }
.test-container  {
   min-height: 500px;
   }
.passage-col  {
   border-right: 1px solid #ebeef5;
   }
.passage-scroll  {
   padding-right: 20px;
   max-height: 600px;
   overflow-y: auto;
   }
.passage-scroll h3  {
   margin-bottom: 16px;
   }
.paragraph  {
   margin-bottom: 12px;
   line-height: 1.8;
   text-indent: 2em;
   }
.meta-bar  {
   margin-top: 20px;
   display: flex;
   gap: 8px;
   align-items: center;
   font-size: 12px;
   color: var(--text-muted);
   flex-wrap: wrap;
   }
.answer-col  {
   padding-left: 20px;
   }
.question-block  {
   margin-bottom: 20px;
   padding: 16px;
   background: #fafafa;
   border-radius: 6px;
   }
.q-text  {
   font-weight: bold;
   margin-bottom: 12px;
   }
.options-group  {
   display: flex;
   flex-direction: column;
   gap: 8px;
   }
.option-item  {
   margin: 0;
   padding: 8px 12px;
   border-radius: 4px;
   white-space: normal;
   height: auto;
   line-height: 1.4;
   }
.option-item:hover  {
   background: #ecf5ff;
   }
.action-bar  {
   text-align: center;
   margin: 20px 0;
   }
.result-box  {
   padding: 16px;
   border-radius: 6px;
   margin-top: 16px;
   }
.result-box.pass  {
   background: #f0f9eb;
   border: 1px solid #e1f3d8;
   }
.result-box.fail  {
   background: #fef0f0;
   border: 1px solid #fde2e2;
   }
.result-summary  {
   font-size: 16px;
   font-weight: bold;
   margin-bottom: 12px;
   }
.result-item  {
   padding: 8px 0;
   border-bottom: 1px solid #ebeef5;
   }
.correct  {
   color: #67c23a;
   }
.wrong  {
   color: #f56c6c;
   }
.explanation  {
   font-size: 13px;
   color: var(--text-muted);
   margin-top: 4px;
   }
@media (max-width: 768px)  {

  .passage-col  {
   border-right: none;
   }
  .passage-scroll  {
   padding-right: 0;
   }
  .answer-col  {
   padding-left: 0;
   }
}
.reading-test {
  padding:0}
.passage-scroll {
  padding-right:20px}
.paragraph {
  font-size:17px;
  line-height:1.95}
.question-block {
  background:#f8f9fc;
  border:1px solid var(--border-light);
  border-radius:9px;
  padding:15px}
.option-item {
  min-height:44px;
  border:1px solid var(--border-light);
  border-radius:7px;
  padding:10px 12px}
.explanation {
  color:var(--text-secondary);
  font-size:14px;
  line-height:1.8}
</style>
