# 练习详情页UI优化实现计划

**Goal:** 练习详情页UI与错题详情页风格统一，采用卡片分区式布局

**Architecture:** 统一练习集详情弹窗（PracticeSets.vue）的样式，使用与错题详情页一致的卡片组件

**Tech Stack:** Vue 3 + Element Plus

---

## 文件变更

- **修改:** `frontend/src/views/PracticeSets.vue` — 详情页和单词练习tab改用卡片分区式布局

---

## 实现任务

### Task 1: 错题练习集题目列表改用卡片布局

**文件:** `frontend/src/views/PracticeSets.vue` 第 287-320 行

将现有的 `el-table` 题目列表改为卡片分区展示：

```vue
<!-- 错题练习集题目列表 -->
<div v-if="detailData.source_type !== 'word' && detailData.questions && detailData.questions.length > 0" class="question-list-section">
  <div class="detail-card">
    <div class="card-header-blue">题目列表</div>
    <div class="card-content">
      <div class="question-cards">
        <div
          v-for="(row, idx) in detailData.questions"
          :key="row.id"
          :class="['question-card', row.is_correct ? 'card-correct' : 'card-wrong']"
        >
          <div class="card-header-small">
            <span class="card-index">{{ idx + 1 }}</span>
            <el-tag :type="row.is_correct ? 'success' : 'danger'" size="small">
              {{ row.is_correct ? '正确' : '错误' }}
            </el-tag>
          </div>
          <div class="card-body">
            <div class="question-info">
              <div class="info-row">
                <span class="label">原题：</span>
                <span class="value">{{ row.original_question_text?.substring(0, 100) || '无' }}</span>
              </div>
              <div class="info-row">
                <span class="label">答案：</span>
                <span class="value answer">{{ row.original_answer || '-' }}</span>
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
```

---

### Task 2: 单词练习列表改用卡片布局

**文件:** `frontend/src/views/PracticeSets.vue` 第 325-355 行

将单词练习 tab 改为双列卡片展示：

```vue
<!-- 单词练习页（仅单词复习类型显示） -->
<el-tab-pane v-if="detailData.source_type === 'word'" label="单词练习" name="words">
  <div class="word-practice">
    <div class="detail-card">
      <div class="card-header-green">单词复习结果</div>
      <div class="card-content">
        <div class="word-stats-summary">
          <el-descriptions :column="4" border size="small">
            <el-descriptions-item label="总单词数">{{ detailData.word_review_stats?.total_count || 0 }}</el-descriptions-item>
            <el-descriptions-item label="正确">{{ detailData.word_review_stats?.correct_count || 0 }}</el-descriptions-item>
            <el-descriptions-item label="错误">{{ (detailData.word_review_stats?.total_count || 0) - (detailData.word_review_stats?.correct_count || 0) }}</el-descriptions-item>
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
```

---

### Task 3: 添加统一样式

**文件:** `frontend/src/views/PracticeSets.vue` style 区域

添加与错题详情页一致的卡片样式：

```css
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
  padding: 12px 16px;
  font-weight: bold;
  font-size: 15px;
}

.card-header-green {
  background: linear-gradient(135deg, #67c23a 0%, #5daf34 100%);
  color: #fff;
  padding: 12px 16px;
  font-weight: bold;
  font-size: 15px;
}

.card-header-orange {
  background: linear-gradient(135deg, #e6a23c 0%, #db8b2e 100%);
  color: #fff;
  padding: 12px 16px;
  font-weight: bold;
  font-size: 15px;
}

.card-header-purple {
  background: linear-gradient(135deg, #9c27b0 0%, #862491 100%);
  color: #fff;
  padding: 12px 16px;
  font-weight: bold;
  font-size: 15px;
}

.card-header-gray {
  background: linear-gradient(135deg, #606266 0%, #555558 100%);
  color: #fff;
  padding: 12px 16px;
  font-weight: bold;
  font-size: 15px;
}

.card-header-small {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.card-content {
  padding: 16px;
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
  padding: 12px;
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
}

.info-row {
  margin-bottom: 8px;
}

.info-row .label {
  color: #909399;
  font-size: 13px;
}

.info-row .value {
  color: #303133;
  font-size: 14px;
}

.info-row .value.answer {
  color: #67c23a;
  font-weight: bold;
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
  font-size: 18px;
  font-weight: bold;
  color: #303133;
  margin-bottom: 4px;
}

.word-chinese {
  font-size: 14px;
  color: #606266;
}

.word-result {
  text-align: right;
}

.result-label {
  font-size: 12px;
  color: #909399;
  margin-bottom: 4px;
}

.result-value {
  font-size: 16px;
  font-weight: bold;
}

.text-success {
  color: #67c23a;
}

.text-danger {
  color: #f56c6c;
}

/* 统计摘要 */
.word-stats-summary {
  margin-bottom: 0;
}
```

---

## 验收标准检查

1. ✅ 弹窗宽度扩大到 1200px
2. ✅ 错题列表使用卡片分区布局，与错题详情页风格一致
3. ✅ 单词列表使用卡片布局，双列展示
4. ✅ 正确/错误使用绿色/红色边框区分
5. ✅ 文本大小统一：英文18px bold，中文14px
