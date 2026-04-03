<template>
  <div class="home">
    <!-- 总体统计 - 科技感卡片 -->
    <el-row :gutter="24">
      <el-col :span="6">
        <div class="stat-card stat-card-blue" @click="$router.push('/questions')">
          <div class="stat-glow"></div>
          <div class="stat-icon-wrapper">
            <el-icon class="stat-icon"><Document /></el-icon>
          </div>
          <div class="stat-info">
            <div class="stat-value">{{ stats.total_questions }}</div>
            <div class="stat-label">错题总数</div>
          </div>
        </div>
      </el-col>
      <el-col :span="6">
        <div class="stat-card stat-card-green" @click="$router.push('/questions')">
          <div class="stat-glow"></div>
          <div class="stat-icon-wrapper">
            <el-icon class="stat-icon"><Books /></el-icon>
          </div>
          <div class="stat-info">
            <div class="stat-value">{{ stats.total_subjects }}</div>
            <div class="stat-label">学科数量</div>
          </div>
        </div>
      </el-col>
      <el-col :span="6">
        <div class="stat-card stat-card-orange" @click="$router.push('/management')">
          <div class="stat-glow"></div>
          <div class="stat-icon-wrapper">
            <el-icon class="stat-icon"><Timer /></el-icon>
          </div>
          <div class="stat-info">
            <div class="stat-value">{{ stats.active_days || 0 }}</div>
            <div class="stat-label">活跃学习天数</div>
          </div>
        </div>
      </el-col>
      <el-col :span="6">
        <div class="stat-card stat-card-red" @click="$router.push('/questions')">
          <div class="stat-glow"></div>
          <div class="stat-icon-wrapper">
            <el-icon class="stat-icon"><Warning /></el-icon>
          </div>
          <div class="stat-info">
            <div class="stat-value">{{ stats.total_questions }}</div>
            <div class="stat-label">待复习</div>
          </div>
        </div>
      </el-col>
    </el-row>

    <!-- 单词统计卡片 -->
    <el-row :gutter="24" style="margin-top: 24px">
      <el-col :span="6">
        <div class="stat-card stat-card-purple" @click="$router.push('/words')">
          <div class="stat-glow"></div>
          <div class="stat-icon-wrapper">
            <el-icon class="stat-icon"><Document /></el-icon>
          </div>
          <div class="stat-info">
            <div class="stat-value">{{ stats.word_stats?.total_words || 0 }}</div>
            <div class="stat-label">单词总数</div>
          </div>
        </div>
      </el-col>
      <el-col :span="6">
        <div class="stat-card stat-card-cyan" @click="$router.push('/words')">
          <div class="stat-glow"></div>
          <div class="stat-icon-wrapper">
            <el-icon class="stat-icon"><Refresh /></el-icon>
          </div>
          <div class="stat-info">
            <div class="stat-value">{{ stats.word_stats?.reviewed_words || 0 }}</div>
            <div class="stat-label">已复习单词</div>
          </div>
        </div>
      </el-col>
      <el-col :span="6">
        <div class="stat-card stat-card-teal" @click="$router.push('/words')">
          <div class="stat-glow"></div>
          <div class="stat-icon-wrapper">
            <el-icon class="stat-icon"><Connection /></el-icon>
          </div>
          <div class="stat-info">
            <div class="stat-value">{{ stats.word_stats?.total_reviews || 0 }}</div>
            <div class="stat-label">复习次数</div>
          </div>
        </div>
      </el-col>
      <el-col :span="6">
        <div class="stat-card stat-card-gold" @click="$router.push('/words')">
          <div class="stat-glow"></div>
          <div class="stat-icon-wrapper">
            <el-icon class="stat-icon"><CircleCheck /></el-icon>
          </div>
          <div class="stat-info">
            <div class="stat-value">{{ stats.word_stats?.accuracy || 0 }}%</div>
            <div class="stat-label">单词正确率</div>
          </div>
        </div>
      </el-col>
    </el-row>

    <!-- 单词准确率曲线 -->
    <el-row style="margin-top: 24px">
      <el-col :span="24">
        <el-card class="chart-card" shadow="hover">
          <template #header>
            <div class="card-header-modern">
              <span class="header-title">单词准确率曲线</span>
              <div class="curve-tabs">
                <el-radio-group v-model="curveRange" size="small">
                  <el-radio-button label="week">最近一周</el-radio-button>
                  <el-radio-button label="month">最近一月</el-radio-button>
                  <el-radio-button label="3months">最近3月</el-radio-button>
                  <el-radio-button label="halfyear">最近半年</el-radio-button>
                  <el-radio-button label="all">全部</el-radio-button>
                </el-radio-group>
              </div>
            </div>
          </template>
          <div v-if="hasAccuracyCurve" class="chart-container">
            <v-chart :option="accuracyCurveOption" autoresize style="height: 280px" />
          </div>
          <el-empty v-else description="暂无准确率数据" />
        </el-card>
      </el-col>
    </el-row>

    <!-- 图表区域 -->
    <el-row :gutter="24" style="margin-top: 24px">
      <!-- 难度分布饼图 -->
      <el-col :span="12">
        <el-card class="chart-card" shadow="hover">
          <template #header>
            <div class="card-header-modern">
              <span class="header-title">难度分布</span>
              <el-tag type="warning" size="small">占比分析</el-tag>
            </div>
          </template>
          <div v-if="hasDifficultyData" class="chart-container">
            <v-chart :option="difficultyPieOption" autoresize style="height: 320px" />
          </div>
          <el-empty v-else description="暂无数据" />
        </el-card>
      </el-col>
      <!-- 错误类型分布 -->
      <el-col :span="12">
        <el-card class="chart-card" shadow="hover">
          <template #header>
            <div class="card-header-modern">
              <span class="header-title">错误类型分布</span>
              <el-tag type="danger" size="small">分类统计</el-tag>
            </div>
          </template>
          <div v-if="hasErrorTypeData" class="chart-container">
            <v-chart :option="errorTypeBarOption" autoresize style="height: 320px" />
          </div>
          <el-empty v-else description="暂无数据" />
        </el-card>
      </el-col>
      <!-- 知识点分布 -->
      <el-col :span="12">
        <el-card class="chart-card" shadow="hover">
          <template #header>
            <div class="card-header-modern">
              <span class="header-title">知识点分布</span>
              <el-tag type="success" size="small">高频考点</el-tag>
            </div>
          </template>
          <div v-if="hasKnowledgePointData" class="chart-container">
            <v-chart :option="knowledgePointCloudOption" autoresize style="height: 320px" />
          </div>
          <el-empty v-else description="暂无知识点数据" />
        </el-card>
      </el-col>
    </el-row>

    <!-- 按学科统计 - 雷达图和柱状图 -->
    <el-row :gutter="24" style="margin-top: 24px">
      <el-col :span="12">
        <el-card class="chart-card" shadow="hover">
          <template #header>
            <div class="card-header-modern">
              <span class="header-title">学科难度对比</span>
            </div>
          </template>
          <div v-if="hasSubjectData" class="chart-container">
            <v-chart :option="subjectRadarOption" autoresize style="height: 360px" />
          </div>
          <el-empty v-else description="暂无学科数据" />
        </el-card>
      </el-col>
      <el-col :span="12">
        <el-card class="chart-card" shadow="hover">
          <template #header>
            <div class="card-header-modern">
              <span class="header-title">学科题目数量</span>
            </div>
          </template>
          <div v-if="hasSubjectData" class="chart-container">
            <v-chart :option="subjectBarOption" autoresize style="height: 360px" />
          </div>
          <el-empty v-else description="暂无学科数据" />
        </el-card>
      </el-col>
    </el-row>

    <!-- 详细数据表格 -->
    <el-row style="margin-top: 24px">
      <el-col :span="24">
        <el-card class="chart-card" shadow="hover">
          <template #header>
            <div class="card-header-modern">
              <span class="header-title">学科详细数据</span>
              <el-button type="primary" size="small" @click="$router.push('/questions')">查看全部</el-button>
            </div>
          </template>
          <el-table :data="subjectTableData" stripe style="width: 100%" :header-cell-style="{ background: '#f5f7fa', color: '#303133' }">
            <el-table-column prop="subject_name" label="学科" width="150">
              <template #default="{ row }">
                <el-tag type="primary" plain>{{ row.subject_name }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="question_count" label="题目数量" width="120" sortable>
              <template #default="{ row }">
                <span class="stat-num">{{ row.question_count }}</span>
              </template>
            </el-table-column>
            <el-table-column label="难度分布" min-width="300">
              <template #default="{ row }">
                <div class="mini-bars">
                  <div v-for="i in 5" :key="i" class="mini-bar-item">
                    <span class="mini-label">难度{{ i }}</span>
                    <el-progress
                      :percentage="getPercentage(row.difficulty_distribution?.[i] || 0, row.question_count)"
                      :stroke-width="10"
                      :color="getDifficultyColor(i)"
                      :show-text="false"
                    />
                    <span class="mini-count">{{ row.difficulty_distribution?.[i] || 0 }}</span>
                  </div>
                </div>
              </template>
            </el-table-column>
            <el-table-column label="主要错误类型" min-width="200">
              <template #default="{ row }">
                <div class="error-tags">
                  <el-tag
                    v-for="(count, type) in getTopErrorTypes(row.error_type_counts)"
                    :key="type"
                    :type="getErrorTagType(type)"
                    size="small"
                    style="margin-right: 4px"
                  >
                    {{ type }} {{ count }}
                  </el-tag>
                </div>
              </template>
            </el-table-column>
            <el-table-column prop="practice_count" label="练习次数" width="100" sortable>
              <template #default="{ row }">
                <span class="stat-num">{{ row.practice_count || 0 }}</span>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
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

const hasDifficultyData = computed(() => stats.value.difficulty_distribution && Object.keys(stats.value.difficulty_distribution).length > 0)
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

// 难度分布饼图
const difficultyPieOption = computed(() => ({
  tooltip: { trigger: 'item', formatter: '{b}: {c} ({d}%)' },
  legend: { orient: 'vertical', right: 20, top: 'center' },
  color: ['#67c23a', '#85ce61', '#e6a23c', '#f56c6c', '#f56c6c'],
  series: [{
    type: 'pie',
    radius: ['40%', '70%'],
    center: ['35%', '50%'],
    avoidLabelOverlap: false,
    itemStyle: { borderRadius: 8, borderColor: '#fff', borderWidth: 2 },
    label: { show: false },
    emphasis: {
      label: { show: true, fontSize: 14, fontWeight: 'bold' }
    },
    data: Object.entries(stats.value.difficulty_distribution || {}).map(([k, v]) => ({
      name: `难度${k}`,
      value: v
    }))
  }]
}))

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

// 学科雷达图
const subjectRadarOption = computed(() => {
  const subjects = (stats.value.by_subject || []).slice(0, 4)
  if (!subjects.length) return {}
  const indicators = [1, 2, 3, 4, 5].map(i => ({ name: `难度${i}`, max: 10 }))
  return {
    tooltip: {},
    radar: {
      indicator: indicators,
      center: ['50%', '55%'],
      radius: '65%'
    },
    legend: {
      data: subjects.map(s => s.subject_name),
      bottom: 10
    },
    series: [{
      type: 'radar',
      data: subjects.map(s => ({
        name: s.subject_name,
        value: [1, 2, 3, 4, 5].map(i => s.difficulty_distribution?.[i] || 0)
      }))
    }]
  }
})

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
  background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
  border-radius: 16px;
  padding: 24px;
  cursor: pointer;
  overflow: hidden;
  transition: all 0.3s ease;
  border: 1px solid rgba(255, 255, 255, 0.1);
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
  background: radial-gradient(circle, rgba(255, 255, 255, 0.1) 0%, transparent 60%);
  pointer-events: none;
}

.stat-card-blue { border-left: 4px solid #409eff; }
.stat-card-green { border-left: 4px solid #67c23a; }
.stat-card-orange { border-left: 4px solid #e6a23c; }
.stat-card-red { border-left: 4px solid #f56c6c; }
.stat-card-purple { border-left: 4px solid #9c27b0; }
.stat-card-cyan { border-left: 4px solid #00bcd4; }
.stat-card-teal { border-left: 4px solid #009688; }
.stat-card-gold { border-left: 4px solid #ffc107; }

.stat-icon-wrapper {
  width: 60px;
  height: 60px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 16px;
}

.stat-card-blue .stat-icon-wrapper { background: rgba(64, 158, 255, 0.2); }
.stat-card-green .stat-icon-wrapper { background: rgba(103, 194, 58, 0.2); }
.stat-card-orange .stat-icon-wrapper { background: rgba(230, 162, 60, 0.2); }
.stat-card-red .stat-icon-wrapper { background: rgba(245, 108, 108, 0.2); }
.stat-card-purple .stat-icon-wrapper { background: rgba(156, 39, 176, 0.2); }
.stat-card-cyan .stat-icon-wrapper { background: rgba(0, 188, 212, 0.2); }
.stat-card-teal .stat-icon-wrapper { background: rgba(0, 150, 136, 0.2); }
.stat-card-gold .stat-icon-wrapper { background: rgba(255, 193, 7, 0.2); }

.stat-icon {
  font-size: 28px;
}

.stat-card-blue .stat-icon { color: #409eff; }
.stat-card-green .stat-icon { color: #67c23a; }
.stat-card-orange .stat-icon { color: #e6a23c; }
.stat-card-red .stat-icon { color: #f56c6c; }
.stat-card-purple .stat-icon { color: #9c27b0; }
.stat-card-cyan .stat-icon { color: #00bcd4; }
.stat-card-teal .stat-icon { color: #009688; }
.stat-card-gold .stat-icon { color: #ffc107; }

.stat-info {
  position: relative;
  z-index: 1;
}

.stat-value {
  font-size: 36px;
  font-weight: bold;
  color: #fff;
  line-height: 1;
  text-shadow: 0 2px 10px rgba(0, 0, 0, 0.3);
}

.stat-label {
  font-size: 14px;
  color: rgba(255, 255, 255, 0.7);
  margin-top: 8px;
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
</style>
