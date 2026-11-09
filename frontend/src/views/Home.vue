<template>
  <div class="home">
    <!-- Hero -->
    <header class="hero">
      <div class="hero-left">
        <p class="hero-eyebrow">A LITTLE BETTER, EVERY DAY</p>
        <h1 class="hero-title">今天，也进步一点点。</h1>
        <p class="hero-sub">把不懂的弄懂，把会的记牢。</p>
      </div>
      <div class="hero-right">
        <el-select :model-value="selectedGrade" class="grade-select" aria-label="年级" @change="onGradeChange">
          <el-option v-for="g in gradeOptions" :key="g.value" :label="g.label" :value="g.value" />
        </el-select>
        <div class="date-chip">
          <svg class="chip-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <rect x="3" y="4" width="18" height="18" rx="2" />
            <line x1="16" y1="2" x2="16" y2="6" />
            <line x1="8" y1="2" x2="8" y2="6" />
            <line x1="3" y1="10" x2="21" y2="10" />
          </svg>
          <span class="chip-text">{{ todayText }}</span>
        </div>
      </div>
    </header>

    <section class="focus-panel"><div><p class="hero-eyebrow">TODAY'S FOCUS · 今日重点</p><h2>{{ stats.to_review_questions ? '从 ' + stats.to_review_questions + ' 道待复习错题开始' : '从一次认真复习开始' }}</h2><p>回顾上次的难点，让知识掌握得更扎实。</p><el-button type="primary" @click="router.push('/questions')">开始错题复习 <el-icon><Right /></el-icon></el-button></div><div class="focus-total"><strong>{{ learningOverview.today_question_review_count + learningOverview.today_word_review_count }}</strong><span>今日已复习</span></div></section>
    <nav class="home-shortcuts" aria-label="学习快捷入口"><RouterLink to="/questions">错题复习 <span>{{ stats.to_review_questions || 0 }} 道待复习 →</span></RouterLink><RouterLink to="/words">单词温习 <span>{{ stats.word_stats?.to_review_count || 0 }} 个待温习 →</span></RouterLink><RouterLink to="/practice-sets">专项练习 <span>进入练习中心 →</span></RouterLink><RouterLink to="/reading">阅读训练 <span>选一篇开始 →</span></RouterLink></nav>
    <!-- Stats Grid -->
    <section class="stats-grid">
      <div class="stat-card tone-indigo stat-lg" role="link" tabindex="0" @keydown.enter="$router.push('/questions')" @click="$router.push('/questions')">
        <div class="stat-top">
          <span class="stat-label">错题总数</span>
          <div class="stat-icon">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
              <polyline points="14 2 14 8 20 8" />
              <line x1="16" y1="13" x2="8" y2="13" />
              <line x1="16" y1="17" x2="8" y2="17" />
              <line x1="10" y1="9" x2="8" y2="9" />
            </svg>
          </div>
        </div>
        <div class="stat-value">{{ stats.total_questions }}</div>
        <div class="stat-foot">点击查看详情 <span class="arrow">→</span></div>
      </div>

      <div class="stat-card tone-violet" role="link" tabindex="0" @keydown.enter="$router.push('/questions')" @click="$router.push('/questions')">
        <div class="stat-top">
          <span class="stat-label">学科数量</span>
          <div class="stat-icon">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20" />
              <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z" />
            </svg>
          </div>
        </div>
        <div class="stat-value">{{ stats.total_subjects }}</div>
      </div>

      <div class="stat-card tone-sky" role="link" tabindex="0" @keydown.enter="$router.push('/management')" @click="$router.push('/management')">
        <div class="stat-top">
          <span class="stat-label">活跃天数</span>
          <div class="stat-icon">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <rect x="3" y="4" width="18" height="18" rx="2" />
              <line x1="16" y1="2" x2="16" y2="6" />
              <line x1="8" y1="2" x2="8" y2="6" />
              <line x1="3" y1="10" x2="21" y2="10" />
            </svg>
          </div>
        </div>
        <div class="stat-value">{{ stats.active_days || 0 }}</div>
      </div>

      <div class="stat-card tone-emerald" role="link" tabindex="0" @keydown.enter="$router.push('/words')" @click="$router.push('/words')">
        <div class="stat-top">
          <span class="stat-label">待复习(单词)</span>
          <div class="stat-icon">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <circle cx="12" cy="12" r="10" />
              <polyline points="12 6 12 12 16 14" />
            </svg>
          </div>
        </div>
        <div class="stat-value">{{ stats.word_stats?.to_review_count || 0 }}</div>
      </div>

      <div class="stat-card tone-amber" role="link" tabindex="0" @keydown.enter="$router.push('/questions')" @click="$router.push('/questions')">
        <div class="stat-top">
          <span class="stat-label">待复习(错题)</span>
          <div class="stat-icon">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <circle cx="12" cy="12" r="10" />
              <polyline points="12 6 12 12 16 14" />
            </svg>
          </div>
        </div>
        <div class="stat-value">{{ stats.to_review_questions || 0 }}</div>
      </div>

      <div class="stat-card tone-rose" role="link" tabindex="0" @keydown.enter="$router.push('/words')" @click="$router.push('/words')">
        <div class="stat-top">
          <span class="stat-label">复习次数</span>
          <div class="stat-icon">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <polyline points="23 4 23 10 17 10" />
              <polyline points="1 20 1 14 7 14" />
              <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15" />
            </svg>
          </div>
        </div>
        <div class="stat-value">{{ stats.word_stats?.total_reviews || 0 }}</div>
      </div>

      <div class="stat-card tone-fuchsia" role="link" tabindex="0" @keydown.enter="$router.push('/words')" @click="$router.push('/words')">
        <div class="stat-top">
          <span class="stat-label">单词总数</span>
          <div class="stat-icon">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20" />
              <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z" />
            </svg>
          </div>
        </div>
        <div class="stat-value">{{ stats.word_stats?.total_words || 0 }}</div>
      </div>

      <div class="stat-card tone-cyan" role="link" tabindex="0" @keydown.enter="$router.push('/words')" @click="$router.push('/words')">
        <div class="stat-top">
          <span class="stat-label">已复习单词</span>
          <div class="stat-icon">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <polyline points="20 6 9 17 4 12" />
            </svg>
          </div>
        </div>
        <div class="stat-value">{{ stats.word_stats?.reviewed_words || 0 }}</div>
      </div>

      <div class="stat-card tone-lime" role="link" tabindex="0" @keydown.enter="$router.push('/words')" @click="$router.push('/words')">
        <div class="stat-top">
          <span class="stat-label">单词正确率</span>
          <div class="stat-icon">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <circle cx="12" cy="12" r="10" />
              <circle cx="12" cy="12" r="6" />
              <circle cx="12" cy="12" r="2" />
            </svg>
          </div>
        </div>
        <div class="stat-value">{{ stats.word_stats?.accuracy || 0 }}%</div>
      </div>
    </section>

    <!-- Global Grade Switcher -->

    <!-- Content Grid -->
    <section class="content-grid">
      <!-- Learning Overview -->
      <article class="panel">
        <div class="panel-head">
          <h2 class="panel-title">学习概览</h2>
        </div>
        <div class="overview-grid">
          <div class="overview-col">
            <div class="overview-col-title">
              <span class="title-dot dot-slate"></span>昨日
            </div>
            <div class="overview-list">
              <div class="overview-item">
                <span class="ov-dot dot-emerald"></span>
                <span>{{ learningOverview.yesterday_word_review_count }} 复习单词</span>
              </div>
              <div class="overview-item">
                <span class="ov-dot dot-blue"></span>
                <span>{{ learningOverview.yesterday_question_review_count }} 复习错题</span>
              </div>
              <div class="overview-item">
                <span class="ov-dot dot-emerald-light"></span>
                <span>{{ learningOverview.yesterday_word_accuracy }}% 单词正确率</span>
              </div>
              <div class="overview-item">
                <span class="ov-dot dot-blue-light"></span>
                <span>{{ learningOverview.yesterday_question_accuracy }}% 错题正确率</span>
              </div>
            </div>
          </div>
          <div class="overview-col">
            <div class="overview-col-title">
              <span class="title-dot dot-indigo"></span>今日
            </div>
            <div class="overview-list">
              <div class="overview-item">
                <span class="ov-dot dot-emerald"></span>
                <span>{{ learningOverview.today_word_review_count }} 复习单词</span>
              </div>
              <div class="overview-item">
                <span class="ov-dot dot-blue"></span>
                <span>{{ learningOverview.today_question_review_count }} 复习错题</span>
              </div>
              <div class="overview-item">
                <span class="ov-dot dot-emerald-light"></span>
                <span>{{ learningOverview.today_word_accuracy }}% 单词正确率</span>
              </div>
              <div class="overview-item">
                <span class="ov-dot dot-blue-light"></span>
                <span>{{ learningOverview.today_question_accuracy }}% 错题正确率</span>
              </div>
            </div>
          </div>
        </div>
      </article>

      <!-- Error Type Distribution -->
      <article class="panel">
        <div class="panel-head">
          <h2 class="panel-title">错误类型分布</h2>
          <el-select v-model="selectedSubject" placeholder="选择学科" size="small" class="subject-select">
            <el-option
              v-for="subject in stats.by_subject"
              :key="subject.subject_id"
              :label="subject.subject_name"
              :value="subject.subject_id"
            />
          </el-select>
        </div>
        <div v-if="hasFilteredErrorTypeData" class="chart-container">
          <v-chart :option="errorTypePieOption" autoresize style="height: 240px" />
        </div>
        <el-empty v-else description="暂无数据" :image-size="80" />
      </article>

      <!-- Accuracy Curve -->
      <article class="panel panel-full">
        <div class="panel-head">
          <h2 class="panel-title">准确率曲线</h2>
          <el-radio-group v-model="curveRange" size="small" class="curve-tabs">
            <el-radio-button label="week">最近一周</el-radio-button>
            <el-radio-button label="month">最近一月</el-radio-button>
            <el-radio-button label="3months">最近3月</el-radio-button>
            <el-radio-button label="halfyear">最近半年</el-radio-button>
            <el-radio-button label="all">全部</el-radio-button>
          </el-radio-group>
        </div>
        <div v-if="hasAccuracyCurve" class="chart-container">
          <v-chart :option="dualAccuracyCurveOption" autoresize style="height: 300px" />
        </div>
        <el-empty v-else description="暂无准确率数据" :image-size="80" />
      </article>

      <!-- Subject Table -->
      <article class="panel panel-full">
        <div class="panel-head">
          <h2 class="panel-title">学科详细数据</h2>
          <el-button type="primary" size="small" round @click="$router.push('/questions')">查看全部</el-button>
        </div>
        <el-table :data="subjectTableData" stripe class="subject-table">
          <el-table-column type="index" label="#" width="60" align="center" />
          <el-table-column prop="subject_name" label="学科" width="80">
            <template #default="{ row }">
              <el-tag type="primary" plain round>{{ row.subject_name }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="错题数" width="70" align="center">
            <template #default="{ row }">
              <span class="question-count">{{ row.question_count }}</span>
            </template>
          </el-table-column>
          <el-table-column label="难度分布" min-width="240">
            <template #default="{ row }">
              <div class="difficulty-bars">
                <div v-for="i in 5" :key="i" class="diff-bar-item">
                  <span class="diff-label">难度{{ i }}</span>
                  <el-progress
                    :percentage="getPercentage(row.difficulty_distribution?.[i] || 0, row.question_count)"
                    :stroke-width="10"
                    :color="getDifficultyColor(i)"
                    :show-text="false"
                    style="flex:1"
                  />
                  <span class="diff-count">{{ row.difficulty_distribution?.[i] || 0 }}</span>
                </div>
              </div>
            </template>
          </el-table-column>
          <el-table-column label="主要错误类型" min-width="180">
            <template #default="{ row }">
              <div class="error-tags">
                <el-tag
                  v-for="(count, type) in getTopErrorTypes(row.error_type_counts)"
                  :key="type"
                  :type="getErrorTagType(type)"
                  size="small"
                  round
                  style="margin-right: 4px"
                >
                  {{ type }} {{ count }}
                </el-tag>
              </div>
            </template>
          </el-table-column>
          <el-table-column prop="practice_count" label="练习次数" width="120" align="center">
            <template #default="{ row }">
              <span class="practice-count">{{ row.practice_count || 0 }}</span>
            </template>
          </el-table-column>
        </el-table>
      </article>
    </section>
  </div>
</template>

<script setup>
import { Right } from '@element-plus/icons-vue'
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { statsApi, statsOverviewApi } from '@/api/question'
import { useAppConfigStore } from '@/stores/appConfig'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { PieChart, BarChart, LineChart, RadarChart } from 'echarts/charts'
import { TitleComponent, TooltipComponent, LegendComponent, GridComponent, GraphicComponent } from 'echarts/components'
import 'echarts-gl'

use([CanvasRenderer, PieChart, BarChart, LineChart, RadarChart, TitleComponent, TooltipComponent, LegendComponent, GridComponent, GraphicComponent])

const router = useRouter()
const appConfigStore = useAppConfigStore()

const stats = ref({
  total_questions: 0,
  total_subjects: 0,
  total_error_books: 0,
  active_days: 0,
  difficulty_distribution: {},
  error_type_distribution: {},
  by_subject: [],
  word_stats: {
    total_words: 0,
    reviewed_words: 0,
    total_reviews: 0,
    accuracy: 0
  },
  word_accuracy_curve: [],
  question_accuracy_curve: []
})

const selectedSubject = ref('')

const gradeLabelMap = {
  1: '一年级', 2: '二年级', 3: '三年级', 4: '四年级',
  5: '五年级', 6: '六年级', 7: '初一', 8: '初二', 9: '初三',
  10: '高一', 11: '高二', 12: '高三',
}

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

const getGradeLabel = (g) => gradeLabelMap[g] || `${g}年级`

// 全局年级：默认六年级（与管理配置一致），切换后整页联动
const selectedGrade = ref(null)

const onGradeChange = (g) => {
  if (selectedGrade.value === g) return
  selectedGrade.value = g
  loadAllStats()
}

const loadAllStats = async () => {
  const params = {}
  if (selectedGrade.value) params.grade = selectedGrade.value
  try {
    const { data } = await statsApi.getSummary(params)
    stats.value = data
    // 学科筛选在年级变化后可能失效，重置
    if (selectedSubject.value && !data.by_subject?.some(s => s.subject_id === selectedSubject.value)) {
      selectedSubject.value = ''
    }
  } catch (error) {
    console.error('获取统计失败:', error)
  }
  try {
    const overviewRes = await statsOverviewApi.getOverview(params)
    learningOverview.value = overviewRes.data
  } catch (error) {
    console.error('获取学习概览失败:', error)
  }
}

const learningOverview = ref({
  yesterday_word_review_count: 0,
  yesterday_question_review_count: 0,
  yesterday_word_accuracy: 0,
  yesterday_question_accuracy: 0,
  today_word_review_count: 0,
  today_question_review_count: 0,
  today_word_accuracy: 0,
  today_question_accuracy: 0,
})

const curveRange = ref('month')

const todayText = computed(() => {
  const now = new Date()
  const weekdays = ['周日', '周一', '周二', '周三', '周四', '周五', '周六']
  return `${now.getFullYear()}年${now.getMonth() + 1}月${now.getDate()}日 ${weekdays[now.getDay()]}`
})

const getPercentage = (count, total) => {
  if (!total) return 0
  return Math.round((count / total) * 100)
}

const getDifficultyColor = (level) => {
  const colors = ['', '#67c23a', '#85ce61', '#e6a23c', '#f56c6c', '#f56c6c']
  return colors[level] || '#909399'
}

const adjustColor = (hex, amount) => {
  const num = parseInt(hex.replace('#', ''), 16)
  const r = Math.min(255, Math.max(0, (num >> 16) + amount))
  const g = Math.min(255, Math.max(0, ((num >> 8) & 0x00FF) + amount))
  const b = Math.min(255, Math.max(0, (num & 0x0000FF) + amount))
  return '#' + ((r << 16) | (g << 8) | b).toString(16).padStart(6, '0')
}

const getErrorTagType = (type) => {
  const types = { '计算': 'danger', '概念': 'warning', '审题': 'info', '粗心': 'success', '其他': '' }
  return types[type] || ''
}

const getTopErrorTypes = (errorTypeCounts) => {
  if (!errorTypeCounts) return {}
  return Object.fromEntries(Object.entries(errorTypeCounts).sort((a, b) => b[1] - a[1]).slice(0, 3))
}

const hasAccuracyCurve = computed(() => {
  return stats.value.word_accuracy_curve && stats.value.word_accuracy_curve.length > 0
})

const filteredErrorTypeData = computed(() => {
  const bySubject = stats.value.by_subject || []
  if (!selectedSubject.value && bySubject.length > 0) {
    const mathSubject = bySubject.find(s => s.subject_name.includes('数学'))
    selectedSubject.value = mathSubject ? mathSubject.subject_id : bySubject[0].subject_id
  }
  const subject = bySubject.find(s => s.subject_id === selectedSubject.value)
  return subject?.error_type_counts || {}
})

const hasFilteredErrorTypeData = computed(() => {
  return Object.keys(filteredErrorTypeData.value).length > 0
})

const errorTypePieOption = computed(() => {
  const data = filteredErrorTypeData.value
  if (!Object.keys(data).length) return {}
  const colors = ['#4f46e5', '#22c55e', '#f59e0b', '#ef4444', '#06b6d4', '#84cc16', '#f97316', '#8b5cf6', '#ec4899']
  const entries = Object.entries(data).sort((a, b) => b[1] - a[1])
  const total = entries.reduce((sum, [, v]) => sum + v, 0)
  return {
    tooltip: {
      trigger: 'item',
      formatter: '{b}: {c} ({d}%)',
      backgroundColor: '#ffffff',
      borderColor: '#e2e8f0',
      borderWidth: 1,
      textStyle: { color: '#334155' }
    },
    legend: {
      orient: 'vertical',
      right: 8,
      top: 'center',
      itemWidth: 12,
      itemHeight: 12,
      itemGap: 14,
      textStyle: { color: '#64748b', fontSize: 13, lineHeight: 22 },
      formatter: (name) => {
        const item = entries.find(([n]) => n === name)
        if (!item) return name
        const pct = ((item[1] / total) * 100).toFixed(1)
        return `${name}  ${item[1]}  ${pct}%`
      }
    },
    series: [{
      type: 'pie',
      radius: ['32%', '68%'],
      center: ['34%', '50%'],
      avoidLabelOverlap: true,
      itemStyle: {
        borderRadius: 8,
        borderColor: '#ffffff',
        borderWidth: 3,
      },
      label: { show: false },
      emphasis: {
        scaleSize: 8,
        itemStyle: { shadowBlur: 16, shadowColor: 'rgba(79, 70, 229, 0.35)' }
      },
      labelLine: { show: false },
      data: entries.map(([name, value], i) => ({
        name,
        value,
        itemStyle: {
          color: {
            type: 'linear',
            x: 0, y: 0, x2: 1, y2: 1,
            colorStops: [
              { offset: 0, color: colors[i % colors.length] },
              { offset: 1, color: adjustColor(colors[i % colors.length], -24) }
            ]
          }
        }
      }))
    }]
  }
})

const subjectTableData = computed(() => stats.value.by_subject || [])

const filteredCurveData = computed(() => {
  const curve = stats.value.word_accuracy_curve || []
  if (!curve.length) return []

  const now = new Date()
  const range = curveRange.value
  let startDate = null

  if (range === 'week') {
    startDate = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000)
  } else if (range === 'month') {
    startDate = new Date(now.getTime() - 30 * 24 * 60 * 60 * 1000)
  } else if (range === '3months') {
    startDate = new Date(now.getTime() - 90 * 24 * 60 * 60 * 1000)
  } else if (range === 'halfyear') {
    startDate = new Date(now.getTime() - 180 * 24 * 60 * 60 * 1000)
  } else {
    return curve
  }

  return curve.filter(p => new Date(p.date) >= startDate)
})

const dualAccuracyCurveOption = computed(() => {
  const wordCurve = filteredCurveData.value
  const questionCurve = stats.value.question_accuracy_curve || []

  const allDates = [...new Set([...wordCurve.map(p => p.date), ...questionCurve.map(p => p.date)])].sort()

  if (!allDates.length) return {}

  const wordMap = new Map(wordCurve.map(p => [p.date, p.accuracy]))
  const questionMap = new Map(questionCurve.map(p => [p.date, p.accuracy]))

  return {
    tooltip: {
      trigger: 'axis',
      backgroundColor: '#ffffff',
      borderColor: '#e2e8f0',
      borderWidth: 1,
      textStyle: { color: '#334155' },
      formatter: function(params) {
        let result = params[0].name + '<br/>'
        params.forEach(p => {
          if (p.value !== null) {
            result += '<span style="display:inline-block;margin-right:4px;border-radius:10px;width:10px;height:10px;background-color:' + p.color + '"></span>'
            result += p.seriesName + ': ' + p.value + '%<br/>'
          }
        })
        return result
      }
    },
    legend: {
      data: ['单词正确率', '错题正确率'],
      bottom: 0,
      textStyle: { color: '#64748b' }
    },
    grid: { left: '3%', right: '4%', bottom: '15%', top: '10px', containLabel: true },
    xAxis: {
      type: 'category',
      data: allDates,
      axisLine: { lineStyle: { color: '#e2e8f0' } },
      axisLabel: { color: '#64748b' }
    },
    yAxis: {
      type: 'value',
      name: '正确率%',
      min: 0,
      max: 100,
      axisLabel: { formatter: '{value}%', color: '#64748b' },
      splitLine: { lineStyle: { color: '#eef2f7' } }
    },
    series: [
      {
        name: '单词正确率',
        type: 'line',
        smooth: true,
        connectNulls: true,
        symbol: 'circle',
        symbolSize: 7,
        lineStyle: { color: '#22c55e', width: 3 },
        itemStyle: { color: '#22c55e' },
        areaStyle: {
          color: {
            type: 'linear', x: 0, y: 0, x2: 0, y2: 1,
            colorStops: [
              { offset: 0, color: 'rgba(34, 197, 94, 0.22)' },
              { offset: 1, color: 'rgba(34, 197, 94, 0.03)' }
            ]
          }
        },
        data: allDates.map(date => wordMap.get(date) ?? null)
      },
      {
        name: '错题正确率',
        type: 'line',
        smooth: true,
        connectNulls: true,
        symbol: 'circle',
        symbolSize: 7,
        lineStyle: { color: '#4f46e5', width: 3 },
        itemStyle: { color: '#4f46e5' },
        areaStyle: {
          color: {
            type: 'linear', x: 0, y: 0, x2: 0, y2: 1,
            colorStops: [
              { offset: 0, color: 'rgba(79, 70, 229, 0.2)' },
              { offset: 1, color: 'rgba(79, 70, 229, 0.03)' }
            ]
          }
        },
        data: allDates.map(date => questionMap.get(date) ?? null)
      }
    ]
  }
})

onMounted(async () => {
  // 默认使用管理配置中的年级（当前为六年级）
  try {
    await appConfigStore.load()
    selectedGrade.value = appConfigStore.defaultGrade || 6
  } catch {
    selectedGrade.value = 6
  }
  await loadAllStats()
})
</script>

<style scoped>
.home {
  margin:0 auto}
.hero {
  display:flex;
  align-items:center;
  justify-content:space-between;
  gap:15px;
  margin-bottom:18px}
.hero-eyebrow {
  font-size:10px;
  font-weight:700;
  letter-spacing:1.6px;
  color:var(--accent-blue);
  margin:0 0 5px}
.hero-title {
  font-size:27px;
  letter-spacing:-.7px;
  margin:0 0 5px;
  color:var(--text-primary)}
.hero-sub {
  font-size:13px;
  margin:0;
  color:var(--text-muted)}
.hero-right { display:flex; align-items:center; flex-wrap:wrap; gap:12px; }
.grade-select { width:120px; }
.date-chip {
  display:flex;
  align-items:center;
  gap:7px;
  font-size:12px;
  color:var(--text-muted)}
.chip-icon {
  width:17px;
  height:17px}
.focus-panel {
  display:flex;
  align-items:center;
  justify-content:space-between;
  gap:20px;
  background:#eeedfc;
  border:1px solid #e1def9;
  border-radius:12px;
  padding:22px 25px;
  margin-bottom:14px}
.focus-panel h2 {
  font-size:22px;
  margin:3px 0 7px}
.focus-panel p:not(.hero-eyebrow) {
  font-size:13px;
  color:#60617e;
  margin:0 0 15px}
.focus-panel .el-icon {
  margin-left:10px}
.focus-total {
  display:flex;
  flex-direction:column;
  align-items:center;
  min-width:140px;
  color:var(--accent-blue)}
.focus-total strong {
  font-size:37px;
  line-height:1.3}
.focus-total span {
  font-size:12px}
.home-shortcuts {
  display:grid;
  grid-template-columns:repeat(4,minmax(0,1fr));
  gap:10px;
  margin-bottom:16px}
.home-shortcuts a {
  background:#fff;
  border:1px solid var(--border-light);
  border-radius:9px;
  padding:11px 14px;
  display:flex;
  align-items:center;
  justify-content:space-between;
  gap:6px;
  font-size:13px}
.home-shortcuts a:hover {
  border-color:#aaa5f2}
.home-shortcuts span {
  font-size:11px;
  color:var(--text-muted)}
.stats-grid {
  display:grid;
  grid-template-columns:repeat(5,minmax(0,1fr));
  gap:10px;
  margin-bottom:18px}
.stat-card {
  position:relative;
  cursor:pointer;
  background:#fff;
  border:1px solid var(--border-light);
  border-radius:10px;
  padding:13px 15px;
  transition:border-color .15s}
.stat-card:hover {
  border-color:#aaa5f2}
.stat-top {
  display:flex;
  justify-content:space-between;
  align-items:center;
  gap:5px;
  margin-bottom:6px}
.stat-label {
  font-size:12px;
  color:var(--text-muted)}
.stat-icon {
  width:25px;
  height:25px;
  border-radius:7px;
  display:grid;
  place-items:center;
  background:#eeedff;
  color:var(--accent-blue)}
.stat-icon svg {
  width:16px;
  height:16px}
.stat-value {
  font-size:27px;
  line-height:1.2;
  font-weight:700;
  color:var(--text-primary)}
.stat-foot {
  display:none}
.grade-switch-bar {
  display:flex;
  align-items:center;
  flex-wrap:wrap;
  gap:12px;
  background:white;
  border:1px solid var(--border-light);
  border-radius:10px;
  padding:12px 15px;
  margin-bottom:18px}
.grade-switch-label {
  font-size:12px;
  color:var(--text-muted)}
.grade-switch-chips {
  display:flex;
  flex-wrap:wrap;
  gap:5px;
  flex:1}
.grade-switch-chip {
  border:1px solid transparent;
  background:#f6f7fb;
  border-radius:6px;
  font-size:12px;
  padding:5px 9px;
  color:var(--text-secondary);
  cursor:pointer}
.grade-switch-chip.active {
  background:#eeedff;
  border-color:#d2cff8;
  color:var(--accent-blue)}
.grade-switch-note {
  font-size:11px;
  color:var(--text-muted)}
.content-grid {
  display:grid;
  grid-template-columns:1fr 1fr;
  gap:16px}
.panel {
  background:#fff;
  border:1px solid var(--border-light);
  border-radius:11px;
  padding:18px;
  min-width:0}
.panel-full {
  grid-column:1/-1}
.panel-head {
  display:flex;
  align-items:center;
  justify-content:space-between;
  flex-wrap:wrap;
  gap:10px;
  margin-bottom:14px}
.panel-title {
  font-size:17px;
  margin:0}
.subject-select {
  width:140px}
.overview-grid {
  display:grid;
  grid-template-columns:1fr 1fr;
  gap:12px}
.overview-col {
  padding:13px;
  border:1px solid var(--border-light);
  border-radius:8px;
  background:var(--bg-tertiary)}
.overview-col-title {
  display:flex;
  align-items:center;
  gap:8px;
  font-size:13px;
  font-weight:600;
  margin-bottom:10px}
.overview-list {
  display:flex;
  flex-direction:column;
  gap:7px}
.overview-item {
  display:flex;
  align-items:center;
  gap:8px;
  font-size:13px;
  color:var(--text-secondary)}
.title-dot,.ov-dot {
  width:7px;
  height:7px;
  border-radius:50%;
  flex-shrink:0}
.dot-slate {
  background:#8c94a9}
.dot-indigo,.dot-blue {
  background:#655bea}
.dot-emerald {
  background:#358364}
.dot-emerald-light {
  background:#86bca3}
.dot-blue-light {
  background:#aaa5f2}
.chart-container {
  padding:4px 0}
.subject-table {
  width:100%}
.question-count {
  color:var(--accent-blue);
  font-weight:650}
.practice-count {
  color:var(--success)}
.difficulty-bars {
  display:flex;
  flex-direction:column;
  gap:5px}
.diff-bar-item {
  display:flex;
  align-items:center;
  gap:8px;
  font-size:12px}
.diff-label {
  width:40px;
  flex-shrink:0;
  color:var(--text-muted)}
.diff-count {
  width:22px;
  text-align:right;
  color:var(--text-muted);
  font-size:11px}
.error-tags {
  display:flex;
  gap:4px;
  flex-wrap:wrap}
@media(max-width:1200px) {
  .stats-grid {
  grid-template-columns:repeat(3,minmax(0,1fr))}
.home-shortcuts {
  grid-template-columns:repeat(2,minmax(0,1fr))}
}
@media(max-width:768px) {
  .hero {
  align-items:start;
  flex-direction:column;
  gap:8px}
.hero-title {
  font-size:23px}
.focus-panel {
  padding:18px}
.focus-panel h2 {
  font-size:19px}
.focus-total {
  display:none}
.stats-grid {
  grid-template-columns:repeat(3,minmax(0,1fr));
  gap:8px}
.stat-card {
  padding:11px}
.stat-value {
  font-size:23px}
.stat-icon {
  display:none}
.content-grid {
  grid-template-columns:1fr}
.panel {
  padding:14px}
.home-shortcuts a {
  flex-direction:column;
  align-items:start;
  padding:10px;
  min-height:54px}
.grade-switch-chip {
  min-height:36px}
.overview-grid {
  gap:8px}
.overview-col {
  padding:10px}
.overview-item {
  font-size:12px}
}
</style>
