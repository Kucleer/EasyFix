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
    <!-- 错误类型分布 -->
    <el-card class="chart-card" shadow="hover">
      <template #header>
        <div class="card-header-modern">
          <span class="header-title">错误类型分布</span>
          <el-select v-model="selectedSubject" placeholder="选择学科" size="small" style="width: 140px">
            <el-option
              v-for="subject in stats.by_subject"
              :key="subject.subject_id"
              :label="subject.subject_name"
              :value="subject.subject_id"
            />
          </el-select>
        </div>
      </template>
      <div v-if="hasFilteredErrorTypeData" class="chart-container">
        <v-chart :option="errorTypePieOption" autoresize style="height: 260px" />
      </div>
      <el-empty v-else description="暂无数据" />
    </el-card>
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
    <!-- 学科详细数据表格 -->
    <el-card class="subject-table-card" shadow="hover">
      <template #header>
        <div class="card-header-modern">
          <span class="header-title">学科详细数据</span>
          <el-button type="primary" size="small" @click="$router.push('/questions')">查看全部</el-button>
        </div>
      </template>
      <el-table :data="subjectTableData" stripe style="width: 100%">
        <el-table-column type="index" label="#" width="60" align="center" />
        <el-table-column prop="subject_name" label="学科" width="120">
          <template #default="{ row }">
            <el-tag type="primary" plain>{{ row.subject_name }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="错题数" width="100" align="center">
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
                  :stroke-width="8"
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
                style="margin-right: 4px"
              >
                {{ type }} {{ count }}
              </el-tag>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="practice_count" label="练习次数" width="100" align="center">
          <template #default="{ row }">
            <span class="practice-count">{{ row.practice_count || 0 }}</span>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </el-col>
  <el-col :span="12">
    <!-- 准确率曲线图 -->
    <el-card class="chart-card" shadow="hover">
      <template #header>
        <div class="card-header-modern">
          <span class="header-title">准确率曲线</span>
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
        <v-chart :option="dualAccuracyCurveOption" autoresize style="height: 300px" />
      </div>
      <el-empty v-else description="暂无准确率数据" />
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

const selectedSubject = ref('')

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

const hasAccuracyCurve = computed(() => {
  return stats.value.word_accuracy_curve && stats.value.word_accuracy_curve.length > 0
})

const filteredErrorTypeData = computed(() => {
  const bySubject = stats.value.by_subject || []
  if (!selectedSubject.value && bySubject.length > 0) {
    // 默认选中第一个学科（优先选数学）
    const mathSubject = bySubject.find(s => s.subject_name.includes('数学'))
    selectedSubject.value = mathSubject ? mathSubject.subject_id : bySubject[0].subject_id
  }
  const subject = bySubject.find(s => s.subject_id === selectedSubject.value)
  return subject?.error_type_counts || {}
})

const selectedSubjectName = computed(() => {
  const subject = stats.value.by_subject?.find(s => s.subject_id === selectedSubject.value)
  return subject?.subject_name || ''
})

const hasFilteredErrorTypeData = computed(() => {
  return Object.keys(filteredErrorTypeData.value).length > 0
})

const errorTypePieOption = computed(() => {
  const data = filteredErrorTypeData.value
  if (!Object.keys(data).length) return {}
  const colorMap = { '计算': '#f56c6c', '概念': '#e6a23c', '审题': '#909399', '粗心': '#67c23a', '其他': '#409eff' }
  const pieData = Object.entries(data).map(([name, value]) => ({
    name,
    value,
    itemStyle: { color: colorMap[name] || '#409eff' }
  }))
  return {
    tooltip: { trigger: 'item', formatter: '{b}: {c} ({d}%)' },
    legend: { bottom: 10, left: 'center' },
    series: [{
      type: 'pie',
      radius: ['40%', '70%'],
      avoidLabelOverlap: false,
      itemStyle: { borderRadius: 8, borderColor: '#fff', borderWidth: 2 },
      label: { show: true, formatter: '{b}\n{c}题' },
      data: pieData,
    }]
  }
})

const subjectTableData = computed(() => stats.value.by_subject || [])

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

const dualAccuracyCurveOption = computed(() => {
  const data = filteredCurveData.value
  if (!data.length) return {}

  return {
    tooltip: {
      trigger: 'axis',
      formatter: function(params) {
        let result = params[0].name + '<br/>'
        params.forEach(p => {
          result += '<span style="display:inline-block;margin-right:4px;border-radius:10px;width:10px;height:10px;background-color:' + p.color + '"></span>'
          result += p.seriesName + ': ' + p.value + '%<br/>'
        })
        return result
      }
    },
    legend: {
      data: ['单词正确率', '错题正确率'],
      bottom: 0,
    },
    grid: { left: '3%', right: '4%', bottom: '15%', top: '10px', containLabel: true },
    xAxis: {
      type: 'category',
      data: data.map(p => p.date),
    },
    yAxis: {
      type: 'value',
      name: '正确率%',
      min: 0,
      max: 100,
      axisLabel: { formatter: '{value}%' }
    },
    series: [
      {
        name: '单词正确率',
        type: 'line',
        smooth: true,
        symbol: 'circle',
        symbolSize: 8,
        lineStyle: { color: '#67c23a', width: 2 },
        itemStyle: { color: '#67c23a' },
        areaStyle: {
          color: {
            type: 'linear', x: 0, y: 0, x2: 0, y2: 1,
            colorStops: [
              { offset: 0, color: 'rgba(103, 194, 58, 0.25)' },
              { offset: 1, color: 'rgba(103, 194, 58, 0.05)' }
            ]
          }
        },
        data: data.map(p => p.accuracy)
      },
      {
        name: '错题正确率',
        type: 'line',
        smooth: true,
        symbol: 'circle',
        symbolSize: 8,
        lineStyle: { color: '#409eff', width: 2 },
        itemStyle: { color: '#409eff' },
        areaStyle: {
          color: {
            type: 'linear', x: 0, y: 0, x2: 0, y2: 1,
            colorStops: [
              { offset: 0, color: 'rgba(64, 158, 255, 0.25)' },
              { offset: 1, color: 'rgba(64, 158, 255, 0.05)' }
            ]
          }
        },
        data: data.map(p => p.accuracy) // TODO: 后端新增错题准确率曲线后替换此数据
      }
    ]
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

/* 学科详细数据表格 */
.subject-table-card {
  border-radius: 16px;
  border: none;
  background: linear-gradient(145deg, #ffffff 0%, #f5f7fa 100%);
}

.subject-table-card :deep(.el-card__header) {
  border-bottom: 1px solid #ebeef5;
  padding: 16px 20px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  border-radius: 16px 16px 0 0;
}

.subject-table-card :deep(.el-card__body) {
  padding: 0;
}

.subject-table-card .header-title {
  color: #fff;
  font-size: 15px;
  font-weight: 600;
}

.subject-table-card .el-table {
  border-radius: 0 0 16px 16px;
}

.subject-table-card :deep(.el-table__header-wrapper th) {
  background: #f5f7fa !important;
  color: #303133;
  font-weight: 600;
}

.subject-table-card :deep(.el-table__row:hover td) {
  background: #f0f4ff !important;
}

.question-count {
  font-weight: bold;
  color: #409eff;
  font-size: 15px;
}

.practice-count {
  color: #67c23a;
  font-weight: 500;
}

.difficulty-bars {
  display: flex;
  flex-direction: column;
  gap: 5px;
}

.diff-bar-item {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
}

.diff-label {
  width: 40px;
  color: #909399;
  flex-shrink: 0;
}

.diff-count {
  width: 22px;
  text-align: right;
  color: #666;
  font-size: 11px;
  flex-shrink: 0;
}

.error-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}
</style>
