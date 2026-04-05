<template>
  <div class="home">
    <!-- 总体统计 - 彩虹配色 -->
    <el-row :gutter="24">
      <el-col :span="8">
        <div class="stat-card stat-card-red" @click="$router.push('/questions')">
          <div class="stat-glow"></div>
          <div class="stat-icon-wrapper">
            <img src="/icons/错题总数.png" class="stat-icon-img" />
          </div>
          <div class="stat-info">
            <div class="stat-value">{{ stats.total_questions }}</div>
            <div class="stat-label">错题总数</div>
          </div>
        </div>
      </el-col>
      <el-col :span="8">
        <div class="stat-card stat-card-orange" @click="$router.push('/questions')">
          <div class="stat-glow"></div>
          <div class="stat-icon-wrapper">
            <img src="/icons/学科数量.png" class="stat-icon-img" />
          </div>
          <div class="stat-info">
            <div class="stat-value">{{ stats.total_subjects }}</div>
            <div class="stat-label">学科数量</div>
          </div>
        </div>
      </el-col>
      <el-col :span="8">
        <div class="stat-card stat-card-yellow" @click="$router.push('/management')">
          <div class="stat-glow"></div>
          <div class="stat-icon-wrapper">
            <img src="/icons/活跃学习天数.png" class="stat-icon-img" />
          </div>
          <div class="stat-info">
            <div class="stat-value">{{ stats.active_days || 0 }}</div>
            <div class="stat-label">活跃学习天数</div>
          </div>
        </div>
      </el-col>
    </el-row>

<!-- 今日学习概览 + 错误类型分布（双列） -->
<el-row :gutter="24" style="margin-top: 24px">
  <el-col :span="12">
    <!-- 今日学习概览卡片 -->
    <div class="today-overview-card">
      <div class="today-card-header">
        <span class="today-title">今日学习概览</span>
      </div>
      <div class="today-card-content">
        <div class="today-item">
          <div class="today-item-icon word-icon">
            <el-icon><Reading /></el-icon>
          </div>
          <div class="today-item-info">
            <div class="today-value">{{ todayStats.today_word_review_count }}</div>
            <div class="today-label">今日复习单词</div>
          </div>
        </div>
        <div class="today-item">
          <div class="today-item-icon question-icon">
            <el-icon><Document /></el-icon>
          </div>
          <div class="today-item-info">
            <div class="today-value">{{ todayStats.today_question_review_count }}</div>
            <div class="today-label">今日复习错题</div>
          </div>
        </div>
        <div class="today-item">
          <div class="today-item-icon word-accuracy-icon">
            <el-icon><CircleCheck /></el-icon>
          </div>
          <div class="today-item-info">
            <div class="today-value">{{ todayStats.today_word_accuracy }}%</div>
            <div class="today-label">今日单词正确率</div>
          </div>
        </div>
        <div class="today-item">
          <div class="today-item-icon question-accuracy-icon">
            <el-icon><SuccessFilled /></el-icon>
          </div>
          <div class="today-item-info">
            <div class="today-value">{{ todayStats.today_question_accuracy }}%</div>
            <div class="today-label">今日错题正确率</div>
          </div>
        </div>
      </div>
    </div>
  </el-col>
  <el-col :span="12">
    <!-- 错误类型分布（占位，右边 Task 6 会替换） -->
    <div class="placeholder-card">
      <span style="color: #909399; font-size: 14px;">错误类型分布（待实现）</span>
    </div>
  </el-col>
</el-row>

<!-- 单词统计卡片 -->
    <el-row :gutter="24" style="margin-top: 24px">
      <el-col :span="8">
        <div class="stat-card stat-card-green" @click="$router.push('/questions')">
          <div class="stat-glow"></div>
          <div class="stat-icon-wrapper">
            <img src="/icons/待复习(错题).png" class="stat-icon-img" />
          </div>
          <div class="stat-info">
            <div class="stat-value">{{ stats.to_review_questions || 0 }}</div>
            <div class="stat-label">待复习(错题)</div>
          </div>
        </div>
      </el-col>
      <el-col :span="8">
        <div class="stat-card stat-card-cyan" @click="$router.push('/words')">
          <div class="stat-glow"></div>
          <div class="stat-icon-wrapper">
            <img src="/icons/待复习(错题).png" class="stat-icon-img" />
          </div>
          <div class="stat-info">
            <div class="stat-value">{{ stats.word_stats?.to_review_count || 0 }}</div>
            <div class="stat-label">待复习(单词)</div>
          </div>
        </div>
      </el-col>
      <el-col :span="8">
        <div class="stat-card stat-card-blue" @click="$router.push('/words')">
          <div class="stat-glow"></div>
          <div class="stat-icon-wrapper">
            <img src="/icons/复习次数.png" class="stat-icon-img" />
          </div>
          <div class="stat-info">
            <div class="stat-value">{{ stats.word_stats?.total_reviews || 0 }}</div>
            <div class="stat-label">复习次数</div>
          </div>
        </div>
      </el-col>
    </el-row>

    <!-- 第三行 -->
    <el-row :gutter="24" style="margin-top: 24px">
      <el-col :span="8">
        <div class="stat-card stat-card-indigo" @click="$router.push('/words')">
          <div class="stat-glow"></div>
          <div class="stat-icon-wrapper">
            <img src="/icons/单词总数.png" class="stat-icon-img" />
          </div>
          <div class="stat-info">
            <div class="stat-value">{{ stats.word_stats?.total_words || 0 }}</div>
            <div class="stat-label">单词总数</div>
          </div>
        </div>
      </el-col>
      <el-col :span="8">
        <div class="stat-card stat-card-violet" @click="$router.push('/words')">
          <div class="stat-glow"></div>
          <div class="stat-icon-wrapper">
            <img src="/icons/已复习单词.png" class="stat-icon-img" />
          </div>
          <div class="stat-info">
            <div class="stat-value">{{ stats.word_stats?.reviewed_words || 0 }}</div>
            <div class="stat-label">已复习单词</div>
          </div>
        </div>
      </el-col>
      <el-col :span="8">
        <div class="stat-card stat-card-purple" @click="$router.push('/words')">
          <div class="stat-glow"></div>
          <div class="stat-icon-wrapper">
            <img src="/icons/单词正确率.png" class="stat-icon-img" />
          </div>
          <div class="stat-info">
            <div class="stat-value">{{ stats.word_stats?.accuracy || 0 }}%</div>
            <div class="stat-label">单词正确率</div>
          </div>
        </div>
      </el-col>
    </el-row>

    <!-- 学科详细数据表格 + 准确率曲线（双列） -->
<el-row :gutter="24" style="margin-top: 24px">
  <el-col :span="12">
    <!-- 学科详细数据表格（占位，Task 7会填充） -->
    <div class="placeholder-card">
      <span style="color: #909399; font-size: 14px;">学科详细数据表格（待实现）</span>
    </div>
  </el-col>
  <el-col :span="12">
    <!-- 准确率曲线图（占位，Task 8会填充） -->
    <div class="placeholder-card">
      <span style="color: #909399; font-size: 14px;">准确率曲线图（待实现）</span>
    </div>
  </el-col>
</el-row>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { statsApi } from '@/api/question'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { PieChart, BarChart, LineChart, RadarChart } from 'echarts/charts'
import { TitleComponent, TooltipComponent, LegendComponent, GridComponent } from 'echarts/components'

use([CanvasRenderer, PieChart, BarChart, LineChart, RadarChart, TitleComponent, TooltipComponent, LegendComponent, GridComponent])

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
  word_accuracy_curve: []
})

const todayStats = ref({
  today_word_review_count: 0,
  today_question_review_count: 0,
  today_word_accuracy: 0,
  today_question_accuracy: 0,
})

const curveRange = ref('month')

const getPercentage = (count, total) => {
  if (!total) return 0
  return Math.round((count / total) * 100)
}

const getDifficultyColor = (level) => {
  const colors = ['', '#67c23a', '#85ce61', '#e6a23c', '#f56c6c', '#f56c6c']
  return colors[level] || '#909399'
}

const getErrorTagType = (type) => {
  const types = { '计算': 'danger', '概念': 'warning', '审题': 'info', '粗心': 'success', '其他': '' }
  return types[type] || ''
}

const getTopErrorTypes = (errorTypeCounts) => {
  if (!errorTypeCounts) return {}
  return Object.fromEntries(Object.entries(errorTypeCounts).sort((a, b) => b[1] - a[1]).slice(0, 3))
}

const hasErrorTypeData = computed(() => stats.value.error_type_distribution && Object.keys(stats.value.error_type_distribution).length > 0)
const hasSubjectData = computed(() => stats.value.by_subject && stats.value.by_subject.length > 0)
const hasKnowledgePointData = computed(() => {
  const kpCounts = stats.value.by_subject?.[0]?.knowledge_point_counts
  return kpCounts && Object.keys(kpCounts).length > 0
})

const hasAccuracyCurve = computed(() => {
  return stats.value.word_accuracy_curve && stats.value.word_accuracy_curve.length > 0
})

const subjectTableData = computed(() => stats.value.by_subject || [])

// 错误类型柱状图
const errorTypeBarOption = computed(() => ({
  tooltip: { trigger: 'axis' },
  grid: { left: '3%', right: '4%', bottom: '3%', top: '10px', containLabel: true },
  xAxis: { type: 'category', data: Object.keys(stats.value.error_type_distribution || {}), axisLabel: { rotate: 0 } },
  yAxis: { type: 'value', name: '数量' },
  series: [{
    type: 'bar',
    barWidth: '50%',
    itemStyle: {
      color: (params) => {
        const colors = { '计算': '#f56c6c', '概念': '#e6a23c', '审题': '#909399', '粗心': '#67c23a', '其他': '#409eff' }
        return colors[params.name] || '#409eff'
      },
      borderRadius: [4, 4, 0, 0]
    },
    data: Object.values(stats.value.error_type_distribution || {})
  }]
}))

// 学科柱状图
const subjectBarOption = computed(() => {
  const subjects = stats.value.by_subject || []
  return {
    tooltip: { trigger: 'axis' },
    grid: { left: '3%', right: '4%', bottom: '3%', top: '10px', containLabel: true },
    xAxis: { type: 'category', data: subjects.map(s => s.subject_name), axisLabel: { rotate: 15 } },
    yAxis: { type: 'value', name: '题目数' },
    series: [{
      type: 'bar',
      barWidth: '40%',
      itemStyle: {
        color: {
          type: 'linear', x: 0, y: 0, x2: 0, y2: 1,
          colorStops: [
            { offset: 0, color: '#409eff' },
            { offset: 1, color: '#67c23a' }
          ]
        },
        borderRadius: [8, 8, 0, 0]
      },
      data: subjects.map(s => s.question_count)
    }]
  }
})

// 知识点柱状图
const knowledgePointCloudOption = computed(() => {
  const kpCounts = stats.value.by_subject?.[0]?.knowledge_point_counts || {}
  const entries = Object.entries(kpCounts).sort((a, b) => b[1] - a[1]).slice(0, 10)
  if (!entries.length) return {}

  return {
    tooltip: { trigger: 'axis' },
    grid: { left: '3%', right: '4%', bottom: '3%', top: '10px', containLabel: true },
    xAxis: { type: 'category', data: entries.map(([name]) => name.length > 8 ? name.slice(0, 8) + '...' : name), axisLabel: { rotate: 30 } },
    yAxis: { type: 'value', name: '题目数' },
    series: [{
      type: 'bar',
      barWidth: '50%',
      itemStyle: {
        color: {
          type: 'linear', x: 0, y: 0, x2: 0, y2: 1,
          colorStops: [
            { offset: 0, color: '#e6a23c' },
            { offset: 1, color: '#f56c6c' }
          ]
        },
        borderRadius: [4, 4, 0, 0]
      },
      data: entries.map(([, value]) => value)
    }]
  }
})

// 单词准确率曲线
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
    return curve // 'all' - 返回全部
  }

  return curve.filter(p => new Date(p.date) >= startDate)
})

const accuracyCurveOption = computed(() => {
  const data = filteredCurveData.value
  if (!data.length) return {}

  return {
    tooltip: {
      trigger: 'axis',
      formatter: '{b}: {c}%'
    },
    grid: { left: '3%', right: '4%', bottom: '3%', top: '10px', containLabel: true },
    xAxis: {
      type: 'category',
      data: data.map(p => p.date),
      axisLabel: { rotate: 0 }
    },
    yAxis: {
      type: 'value',
      name: '正确率%',
      min: 0,
      max: 100,
      axisLabel: { formatter: '{value}%' }
    },
    series: [{
      type: 'line',
      smooth: true,
      symbol: 'circle',
      symbolSize: 8,
      lineStyle: { color: '#409eff', width: 2 },
      itemStyle: { color: '#409eff' },
      areaStyle: {
        color: {
          type: 'linear',
          x: 0, y: 0, x2: 0, y2: 1,
          colorStops: [
            { offset: 0, color: 'rgba(64, 158, 255, 0.3)' },
            { offset: 1, color: 'rgba(64, 158, 255, 0.05)' }
          ]
        }
      },
      data: data.map(p => p.accuracy)
    }]
  }
})

onMounted(async () => {
  try {
    const { data } = await statsApi.getSummary()
    stats.value = data
  } catch (error) {
    console.error('获取统计失败:', error)
  }
  try {
    const todayRes = await statsApi.getTodayStats()
    todayStats.value = todayRes.data
  } catch (error) {
    console.error('获取今日统计失败:', error)
  }
})
</script>

<style scoped>
.home {
  max-width: 1600px;
  margin: 0 auto;
  padding: 20px;
}

/* 科技感统计卡片 */
.stat-card {
  position: relative;
  border-radius: 16px;
  padding: 16px;
  cursor: pointer;
  overflow: hidden;
  transition: all 0.3s ease;
  border: 1px solid rgba(255, 255, 255, 0.2);
  display: flex;
  align-items: flex-end;
  height: 130px;
}

.stat-card:hover {
  transform: translateY(-5px);
  box-shadow: 0 20px 40px rgba(0, 0, 0, 0.3);
}

.stat-glow {
  position: absolute;
  top: -50%;
  left: -50%;
  width: 200%;
  height: 200%;
  background: radial-gradient(circle, rgba(255, 255, 255, 0.15) 0%, transparent 60%);
  pointer-events: none;
}

.stat-card-red { background: linear-gradient(135deg, #ff6b6b 0%, #ee5a5a 100%); }
.stat-card-orange { background: linear-gradient(135deg, #ffa502 0%, #ff9500 100%); }
.stat-card-yellow { background: linear-gradient(135deg, #f1c40f 0%, #f39c12 100%); }
.stat-card-green { background: linear-gradient(135deg, #2ed573 0%, #26a65b 100%); }
.stat-card-cyan { background: linear-gradient(135deg, #00bcd4 0%, #00acc1 100%); }
.stat-card-blue { background: linear-gradient(135deg, #409eff 0%, #3c8af0 100%); }
.stat-card-indigo { background: linear-gradient(135deg, #6360db 0%, #5558d4 100%); }
.stat-card-violet { background: linear-gradient(135deg, #8e44ad 0%, #7d3c98 100%); }
.stat-card-purple { background: linear-gradient(135deg, #9c27b0 0%, #8e24a0 100%); }
.stat-card-teal { background: linear-gradient(135deg, #009688 0%, #00897b 100%); }
.stat-card-gold { background: linear-gradient(135deg, #ffc107 0%, #ffb300 100%); }

.stat-icon-wrapper {
  display: flex;
  align-items: center;
  justify-content: center;
  margin-right: 12px;
  flex-shrink: 0;
  height: 78px;
  width: 78px;
}

.stat-icon-img {
  height: 100%;
  width: auto;
  object-fit: contain;
}

.stat-info {
  position: relative;
  z-index: 1;
  flex: 1;
  text-align: right;
}

.stat-value {
  font-size: 30px;
  font-weight: bold;
  color: #fff;
  line-height: 1;
  text-shadow: 0 2px 10px rgba(0, 0, 0, 0.3);
}

.stat-label {
  font-size: 32px;
  color: rgba(255, 255, 255, 0.9);
  margin-top: 6px;
  font-weight: 600;
  letter-spacing: 1px;
}

.stat-trend {
  position: absolute;
  top: 20px;
  right: 20px;
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  padding: 4px 8px;
  border-radius: 8px;
}

.stat-trend.up {
  color: #67c23a;
  background: rgba(103, 194, 58, 0.15);
}

.stat-trend.down {
  color: #f56c6c;
  background: rgba(245, 108, 108, 0.15);
}

/* 图表卡片 */
.chart-card {
  border-radius: 16px;
  border: none;
  background: linear-gradient(145deg, #ffffff 0%, #f5f7fa 100%);
}

.chart-card :deep(.el-card__header) {
  border-bottom: 1px solid #ebeef5;
  padding: 16px 20px;
}

.card-header-modern {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.header-title {
  font-size: 16px;
  font-weight: 600;
  color: #303133;
}

.curve-tabs {
  display: flex;
  align-items: center;
}

.chart-container {
  padding: 10px 0;
}

/* 表格样式 */
.stat-num {
  font-weight: bold;
  color: #409eff;
  font-size: 16px;
}

.mini-bars {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.mini-bar-item {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
}

.mini-label {
  width: 45px;
  color: #909399;
}

.mini-bar-item .el-progress {
  flex: 1;
}

.mini-count {
  width: 25px;
  text-align: right;
  color: #666;
  font-size: 11px;
}

.error-tags {
  display: flex;
  flex-wrap: wrap;
}

/* 今日学习概览卡片 */
.today-overview-card {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  border-radius: 16px;
  overflow: hidden;
  box-shadow: 0 8px 24px rgba(102, 126, 234, 0.3);
}

.today-card-header {
  padding: 16px 20px;
  border-bottom: 1px solid rgba(255,255,255,0.2);
}

.today-title {
  color: #fff;
  font-size: 16px;
  font-weight: 600;
}

.today-card-content {
  padding: 20px;
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}

.today-item {
  display: flex;
  align-items: center;
  gap: 12px;
}

.today-item-icon {
  width: 44px;
  height: 44px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 20px;
  flex-shrink: 0;
}

.word-icon { background: rgba(255,255,255,0.25); color: #fff; }
.question-icon { background: rgba(255,255,255,0.25); color: #fff; }
.word-accuracy-icon { background: rgba(103,194,58,0.3); color: #a8e6a3; }
.question-accuracy-icon { background: rgba(64,158,255,0.3); color: #a0cfff; }

.today-item-info {
  flex: 1;
}

.today-value {
  font-size: 24px;
  font-weight: bold;
  color: #fff;
  line-height: 1.2;
}

.today-label {
  font-size: 12px;
  color: rgba(255,255,255,0.8);
  margin-top: 2px;
}

/* 占位卡片 */
.placeholder-card {
  background: #f5f7fa;
  border-radius: 16px;
  height: 280px;
  display: flex;
  align-items: center;
  justify-content: center;
  border: 2px dashed #dcdfe6;
}
</style>
