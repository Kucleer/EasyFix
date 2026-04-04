<template>
  <div class="stats">
    <el-row :gutter="20">
      <el-col :span="24">
        <el-card>
          <template #header>
            <span>统计分析</span>
            <el-button size="small" @click="fetchStats" style="float: right">
              <el-icon><Refresh /></el-icon>
              刷新
            </el-button>
          </template>

          <el-row :gutter="20">
            <el-col :span="6">
              <div class="stat-item">
                <div class="stat-value">{{ stats.total_questions }}</div>
                <div class="stat-label">错题总数</div>
              </div>
            </el-col>
            <el-col :span="6">
              <div class="stat-item">
                <div class="stat-value">{{ stats.total_subjects }}</div>
                <div class="stat-label">学科数</div>
              </div>
            </el-col>
            <el-col :span="6">
              <div class="stat-item">
                <div class="stat-value">{{ stats.total_error_books }}</div>
                <div class="stat-label">错题本数</div>
              </div>
            </el-col>
            <el-col :span="6">
              <div class="stat-item">
                <div class="stat-value">{{ averageDifficulty }}</div>
                <div class="stat-label">平均难度</div>
              </div>
            </el-col>
          </el-row>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="20" style="margin-top: 20px">
      <el-col :span="12">
        <el-card>
          <template #header>
            <span>难度分布</span>
          </template>
          <div v-if="Object.keys(stats.difficulty_distribution || {}).length" class="chart-container">
            <div v-for="(count, level) in stats.difficulty_distribution" :key="level" class="bar-item">
              <span class="bar-label">难度 {{ level }}</span>
              <div class="bar-wrapper">
                <div class="bar" :style="{ width: getPercentage(count) + '%', backgroundColor: getDifficultyColor(level) }"></div>
              </div>
              <span class="bar-value">{{ count }} ({{ getPercentage(count) }}%)</span>
            </div>
          </div>
          <el-empty v-else description="暂无数据" />
        </el-card>
      </el-col>

      <el-col :span="12">
        <el-card>
          <template #header>
            <span>错误类型分布</span>
          </template>
          <div v-if="Object.keys(stats.error_type_distribution || {}).length" class="chart-container">
            <div v-for="(count, type) in stats.error_type_distribution" :key="type" class="bar-item">
              <span class="bar-label">{{ type }}</span>
              <div class="bar-wrapper">
                <div class="bar" :style="{ width: getPercentage(count) + '%', backgroundColor: '#409eff' }"></div>
              </div>
              <span class="bar-value">{{ count }} ({{ getPercentage(count) }}%)</span>
            </div>
          </div>
          <el-empty v-else description="暂无数据" />
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="20" style="margin-top: 20px">
      <el-col :span="24">
        <el-card>
          <template #header>
            <span>按学科统计</span>
          </template>
          <el-table :data="stats.by_subject || []" stripe style="width: 100%">
            <el-table-column prop="subject_name" label="学科" />
            <el-table-column prop="question_count" label="错题数量" />
            <el-table-column label="错误类型分布">
              <template #default="{ row }">
                <div v-if="Object.keys(row.error_type_counts || {}).length">
                  <el-tag
                    v-for="(count, type) in row.error_type_counts"
                    :key="type"
                    :style="{ marginRight: '5px', marginBottom: '5px', fontSize: '14px' }"
                  >
                    {{ type }}: {{ count }}
                  </el-tag>
                </div>
                <span v-else>暂无</span>
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

const stats = ref({
  total_questions: 0,
  total_subjects: 0,
  total_error_books: 0,
  difficulty_distribution: {},
  error_type_distribution: {},
  by_subject: [],
})

const averageDifficulty = computed(() => {
  const dist = stats.value.difficulty_distribution || {}
  const entries = Object.entries(dist)
  if (!entries.length) return '0'

  let totalScore = 0
  let totalCount = 0
  for (const [level, count] of entries) {
    totalScore += parseInt(level) * count
    totalCount += count
  }
  return totalCount ? (totalScore / totalCount).toFixed(1) : '0'
})

const totalCount = computed(() => {
  return Object.values(stats.value.difficulty_distribution || {}).reduce((a, b) => a + b, 0)
})

const getPercentage = (count) => {
  return totalCount.value ? Math.round((count / totalCount.value) * 100) : 0
}

const getDifficultyColor = (level) => {
  const colors = ['', '#67c23a', '#85ce61', '#e6a23c', '#f56c6c', '#f78989']
  return colors[parseInt(level)] || '#409eff'
}

const fetchStats = async () => {
  try {
    const { data } = await statsApi.getSummary()
    stats.value = data
  } catch (error) {
    console.error('获取统计数据失败:', error)
  }
}

onMounted(fetchStats)
</script>

<style scoped>
.stats {
  max-width: 1200px;
  margin: 0 auto;
}

.stat-item {
  text-align: center;
  padding: 20px;
}

.stat-value {
  font-size: 36px;
  font-weight: bold;
  color: #409eff;
}

.stat-label {
  font-size: 14px;
  color: #666;
  margin-top: 10px;
}

.chart-container {
  padding: 10px;
}

.bar-item {
  display: flex;
  align-items: center;
  margin-bottom: 15px;
}

.bar-label {
  width: 80px;
  font-size: 14px;
}

.bar-wrapper {
  flex: 1;
  height: 20px;
  background-color: #f0f0f0;
  border-radius: 10px;
  overflow: hidden;
  margin: 0 10px;
}

.bar {
  height: 100%;
  border-radius: 10px;
  transition: width 0.3s ease;
}

.bar-value {
  width: 80px;
  text-align: right;
  font-size: 14px;
  color: #666;
}
</style>
