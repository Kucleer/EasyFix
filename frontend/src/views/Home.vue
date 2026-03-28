<template>
  <div class="home">
    <!-- 总体统计 -->
    <el-row :gutter="20">
      <el-col :span="6">
        <el-card shadow="hover">
          <div class="stat-card">
            <el-icon class="stat-icon" color="#409eff"><Document /></el-icon>
            <div class="stat-content">
              <div class="stat-value">{{ stats.total_questions }}</div>
              <div class="stat-label">错题总数</div>
            </div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover">
          <div class="stat-card">
            <el-icon class="stat-icon" color="#67c23a"><Books /></el-icon>
            <div class="stat-content">
              <div class="stat-value">{{ stats.total_subjects }}</div>
              <div class="stat-label">学科数量</div>
            </div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover">
          <div class="stat-card">
            <el-icon class="stat-icon" color="#e6a23c"><Collection /></el-icon>
            <div class="stat-content">
              <div class="stat-value">{{ stats.total_error_books }}</div>
              <div class="stat-label">错题本数量</div>
            </div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover">
          <div class="stat-card">
            <el-icon class="stat-icon" color="#f56c6c"><Warning /></el-icon>
            <div class="stat-content">
              <div class="stat-value">{{ stats.total_questions }}</div>
              <div class="stat-label">待复习</div>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 按学科统计 -->
    <el-row style="margin-top: 20px">
      <el-col :span="24">
        <el-card>
          <template #header>
            <span>按学科统计</span>
          </template>
          <div v-if="stats.by_subject && stats.by_subject.length">
            <el-row :gutter="20">
              <el-col
                v-for="subject in stats.by_subject"
                :key="subject.subject_id"
                :span="8"
                style="margin-bottom: 20px"
              >
                <el-card shadow="hover" class="subject-card">
                  <template #header>
                    <div class="subject-header">
                      <span class="subject-name">{{ subject.subject_name }}</span>
                      <el-tag type="primary" size="small">{{ subject.question_count }} 题</el-tag>
                    </div>
                  </template>
                  <div class="subject-stats">
                    <!-- 难度分布 -->
                    <div class="stat-section">
                      <div class="section-title">难度分布</div>
                      <div
                        v-for="(count, level) in subject.difficulty_distribution || {}"
                        :key="'d-' + level"
                        class="mini-bar"
                      >
                        <span>难度 {{ level }}</span>
                        <el-progress
                          :percentage="getPercentage(count, subject.question_count)"
                          :stroke-width="8"
                        />
                        <span class="count">{{ count }}</span>
                      </div>
                      <div v-if="!subject.difficulty_distribution || !Object.keys(subject.difficulty_distribution).length" class="no-data">
                        暂无数据
                      </div>
                    </div>
                    <!-- 错误类型分布 -->
                    <div class="stat-section">
                      <div class="section-title">错误类型</div>
                      <div v-if="subject.error_type_counts && Object.keys(subject.error_type_counts).length" class="tag-list">
                        <el-tag
                          v-for="(count, type) in subject.error_type_counts"
                          :key="type"
                          size="small"
                          style="margin: 4px"
                        >
                          {{ type }}: {{ count }}
                        </el-tag>
                      </div>
                      <div v-else class="no-data">暂无数据</div>
                    </div>
                  </div>
                </el-card>
              </el-col>
            </el-row>
          </div>
          <el-empty v-else description="暂无学科数据" />
        </el-card>
      </el-col>
    </el-row>

    <!-- 难度和错误类型总览 -->
    <el-row :gutter="20" style="margin-top: 20px">
      <el-col :span="12">
        <el-card>
          <template #header>
            <span>难度分布</span>
          </template>
          <div v-if="Object.keys(stats.difficulty_distribution || {}).length">
            <div v-for="(count, level) in stats.difficulty_distribution" :key="level" class="dist-item">
              <span>难度 {{ level }}</span>
              <el-progress :percentage="(count / stats.total_questions) * 100" />
              <span>{{ count }} 题</span>
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
          <div v-if="Object.keys(stats.error_type_distribution || {}).length">
            <div v-for="(count, type) in stats.error_type_distribution" :key="type" class="dist-item">
              <span>{{ type }}</span>
              <el-progress :percentage="(count / stats.total_questions) * 100" />
              <span>{{ count }} 题</span>
            </div>
          </div>
          <el-empty v-else description="暂无数据" />
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { statsApi } from '@/api/question'

const stats = ref({
  total_questions: 0,
  total_subjects: 0,
  total_error_books: 0,
  difficulty_distribution: {},
  error_type_distribution: {},
  by_subject: [],
})

const getPercentage = (count, total) => {
  if (!total) return 0
  return Math.round((count / total) * 100)
}

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
  max-width: 1400px;
  margin: 0 auto;
}

.stat-card {
  display: flex;
  align-items: center;
  gap: 20px;
}

.stat-icon {
  font-size: 48px;
}

.stat-value {
  font-size: 32px;
  font-weight: bold;
}

.stat-label {
  color: #666;
  font-size: 14px;
}

.dist-item {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 10px;
}

.dist-item span:first-child {
  width: 60px;
}

.dist-item span:last-child {
  width: 50px;
  text-align: right;
  color: #666;
}

.dist-item .el-progress {
  flex: 1;
}

.subject-card {
  height: 100%;
}

.subject-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.subject-name {
  font-weight: bold;
  font-size: 16px;
}

.subject-stats {
  padding: 10px 0;
}

.stat-section {
  margin-bottom: 15px;
}

.stat-section:last-child {
  margin-bottom: 0;
}

.section-title {
  font-size: 13px;
  color: #666;
  margin-bottom: 8px;
}

.mini-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
  font-size: 12px;
}

.mini-bar span:first-child {
  width: 50px;
  color: #666;
}

.mini-bar .el-progress {
  flex: 1;
}

.mini-bar .count {
  width: 30px;
  text-align: right;
  color: #999;
}

.tag-list {
  display: flex;
  flex-wrap: wrap;
}

.no-data {
  color: #999;
  font-size: 13px;
  text-align: center;
  padding: 10px;
}
</style>
