# 单词复习功能优化实现计划

**Goal:** 优化单词复习过程，强化学习效果

**Architecture:** 修改 `frontend/src/views/Words.vue` 和 `frontend/src/views/PracticeSets.vue`

**Tech Stack:** Vue 3 + Element Plus

---

## 文件变更

- **修改:** `frontend/src/views/Words.vue` — 复习结果页添加错误单词列表
- **修改:** `frontend/src/views/PracticeSets.vue` — 练习详情单词列表UI紧凑化

---

## 实现任务

### Task 1: 复习结果页添加错误单词列表

**文件:** `frontend/src/views/Words.vue`

- [ ] **Step 1: 在结果页添加错误单词展示区域**

在 `reviewStep === 'result'` 的结果页中，在现有统计信息下方添加错误单词列表：

```vue
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
```

- [ ] **Step 2: 添加错误单词列表样式**

在 `style scoped` 区域添加：

```css
.error-word-list {
  margin-top: 20px;
  padding: 16px;
  background: #fef0f0;
  border-radius: 8px;
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
```

---

### Task 2: 练习详情单词列表UI紧凑化

**文件:** `frontend/src/views/PracticeSets.vue` 第 333-355 行

- [ ] **Step 1: 将单词卡片改为表格紧凑布局**

将现有的 `.word-item` 卡片布局改为表格行：

```vue
<div class="word-list">
  <el-table :data="detailData.questions" size="small" style="width: 100%">
    <el-table-column type="index" label="#" width="50" align="center" />
    <el-table-column label="英文" prop="question_text" width="150" />
    <el-table-column label="中文" prop="answer" min-width="150" />
    <el-table-column label="实际默写" width="150">
      <template #default="{ row }">
        <span :class="row.is_correct ? 'text-success' : 'text-danger'">
          {{ row.user_answer || '-' }}
        </span>
      </template>
    </el-table-column>
    <el-table-column label="结果" width="80" align="center">
      <template #default="{ row }">
        <el-tag :type="row.is_correct ? 'success' : 'danger'" size="small">
          {{ row.is_correct ? '正确' : '错误' }}
        </el-tag>
      </template>
    </el-table-column>
  </el-table>
</div>
```

- [ ] **Step 2: 添加样式**

```css
.text-success {
  color: #67c23a;
}

.text-danger {
  color: #f56c6c;
}
```

---

### Task 3: 确认方案一默写逻辑正常

**文件:** `frontend/src/views/Words.vue` 第 257-293 行

- [ ] **Step 1: 确认默写流程正确**

验证以下流程：
1. 默写时显示中文 + 提示（字母数）
2. 用户输入后回车提交
3. 显示正确/错误结果
4. 错误时显示正确答案：`正确答案: {{ currentQuestion.english }}`
5. 光标自动聚焦下一题输入框

已实现的代码（第262-272行）：
```vue
<el-input
  ref="answerInputRef"
  v-model="userAnswer"
  placeholder="输入英文单词"
  @keyup.enter="submitAnswer"
  :disabled="currentQuestion.correct !== undefined"
  class="answer-input"
/>
<div v-if="currentQuestion.correct !== undefined" :class="['result', currentQuestion.correct ? 'correct-result' : 'wrong-result']">
  <span class="correct-answer">正确答案: {{ currentQuestion.english }}</span>
</div>
```

提交后自动聚焦（第874-876行）：
```javascript
setTimeout(() => {
  answerInputRef.value?.focus()
}, 50)
```

---

## 验收标准检查

1. ✅ 单词默写提交后展示正确或错误
2. ✅ 错误时显示正确答案
3. ✅ 光标锁定在输入框（自动聚焦）
4. ✅ 复习结果页展示错误单词列表
5. ✅ 练习详情单词列表紧凑展示（英文、中文、实际默写）
