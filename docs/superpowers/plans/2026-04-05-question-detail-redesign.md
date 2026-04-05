# 错题详情页 UI 美化实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 美化错题详情弹窗，采用卡片分区式布局，难度显示统一黄色星星

**Architecture:** 单文件修改 `frontend/src/views/Questions.vue`，重写详情弹窗模板结构和CSS样式

**Tech Stack:** Vue 3 + Element Plus + scoped CSS

---

## 文件变更

- **修改:** `frontend/src/views/Questions.vue` — 详情弹窗模板（HTML结构）和样式（CSS）

---

## 实现任务

### Task 1: 重写详情弹窗模板结构

**文件:** `frontend/src/views/Questions.vue` 第 189-275 行

- [ ] **Step 1: 替换详情弹窗模板**

将原有的简单纵向布局替换为卡片分区式布局：

```html
<!-- 详情弹窗 -->
<el-dialog v-model="detailVisible" title="错题详情" width="900px">
  <div v-if="currentQuestion" class="question-detail">
    <!-- 原图展示区 -->
    <div v-if="getImageList(currentQuestion).length" class="detail-images">
      <div class="detail-card">
        <div class="card-header-blue">原图</div>
        <div class="card-content">
          <div class="image-gallery">
            <el-image
              v-for="(img, idx) in getImageList(currentQuestion)"
              :key="idx"
              :src="'/uploads/' + img"
              :preview-src-list="getImageList(currentQuestion).map(i => '/uploads/' + i)"
              fit="cover"
              class="gallery-image"
            />
          </div>
        </div>
      </div>
    </div>

    <!-- 题目和答案并排 -->
    <div class="detail-row">
      <!-- 题目卡片 -->
      <div class="detail-card flex-1">
        <div class="card-header-blue">题目</div>
        <div class="card-content">
          <div class="question-text" v-html="decodeHTML(currentQuestion.parsed_question || currentQuestion.original_text || '暂无')"></div>
        </div>
      </div>
      <!-- 答案卡片 -->
      <div class="detail-card flex-1">
        <div class="card-header-green">答案</div>
        <div class="card-content">
          <div class="question-text" v-html="decodeHTML(currentQuestion.answer || '暂无')"></div>
        </div>
      </div>
    </div>

    <!-- 解析卡片 -->
    <div class="detail-card">
      <div class="card-header-orange">解析</div>
      <div class="card-content">
        <div v-if="currentQuestion.analysis" class="question-text" v-html="decodeHTML(currentQuestion.analysis)"></div>
        <div v-if="currentQuestion.analysis_image" class="analysis-image">
          <el-image
            :src="'/uploads/' + currentQuestion.analysis_image"
            :preview-src-list="['/uploads/' + currentQuestion.analysis_image]"
            fit="contain"
            class="analysis-img"
          />
        </div>
        <span v-if="!currentQuestion.analysis && !currentQuestion.analysis_image" class="text-muted">暂无</span>
      </div>
    </div>

    <!-- 元数据卡片 -->
    <div class="detail-card">
      <div class="card-header-gray">信息</div>
      <div class="card-content">
        <div class="meta-row">
          <div class="meta-item">
            <label>难度：</label>
            <span class="difficulty-stars-yellow">{{ getDifficultyStars(currentQuestion.difficulty) }}</span>
          </div>
          <div class="meta-item">
            <label>年级/学期：</label>
            <span>{{ getGradeLabel(currentQuestion.grade) }} / {{ currentQuestion.semester ? (currentQuestion.semester === 1 ? '上学期' : '下学期') : '未设置' }}</span>
          </div>
        </div>
        <div class="meta-row">
          <div class="meta-item">
            <label>错误类型：</label>
            <el-tag v-if="currentQuestion.error_type" :type="getErrorTypeType(currentQuestion.error_type)" size="small">
              {{ currentQuestion.error_type }}
            </el-tag>
            <span v-else class="text-muted">暂无</span>
          </div>
          <div class="meta-item">
            <label>知识点：</label>
            <el-tag v-if="currentQuestion.knowledge_point" size="small" type="info">
              {{ currentQuestion.knowledge_point }}
            </el-tag>
            <span v-else class="text-muted">暂无</span>
          </div>
        </div>
      </div>
    </div>

    <!-- 标签区域 -->
    <div class="tags-area">
      <label class="tags-label">标签：</label>
      <el-tag
        v-for="tag in currentQuestion.tags"
        :key="tag.id"
        size="small"
        :style="{ marginRight: '8px', backgroundColor: tag.color || '#409eff', borderColor: tag.color || '#409eff', color: tag.color ? getContrastColor(tag.color) : '#ffffff' }"
      >{{ tag.name }}</el-tag>
      <span v-if="!currentQuestion.tags?.length" class="text-muted">暂无</span>
    </div>

    <!-- 相似题卡片 -->
    <div v-if="currentQuestion.similar_questions?.length" class="detail-card">
      <div class="card-header-purple">相似题</div>
      <div class="card-content">
        <div v-for="sq in currentQuestion.similar_questions" :key="sq.id" class="similar-item">
          <p><strong>题目：</strong><span v-html="decodeHTML(sq.similar_text)"></span></p>
          <p><strong>答案：</strong><span v-html="decodeHTML(sq.similar_answer)"></span></p>
        </div>
      </div>
    </div>
  </div>
</el-dialog>
```

---

### Task 2: 添加黄色星星显示函数

**文件:** `frontend/src/views/Questions.vue` 第 594 行附近（getDifficultyStars 函数后）

- [ ] **Step 1: 添加黄色星星样式函数**

在 `getDifficultyStars` 函数后添加新的黄色星星渲染函数：

```javascript
// 获取黄色星星（统一黄色）
const getYellowStars = (difficulty) => {
  if (!difficulty) return '☆☆☆☆☆'
  return '★'.repeat(difficulty) + '☆'.repeat(5 - difficulty)
}
```

---

### Task 3: 添加卡片样式 CSS

**文件:** `frontend/src/views/Questions.vue` 末尾 `<style scoped>` 内

- [ ] **Step 1: 添加卡片基础样式**

在 CSS 末尾添加：

```css
/* ========== 详情页卡片式布局 ========== */
.question-detail {
  padding: 8px;
}

/* 原图展示区 */
.detail-images {
  margin-bottom: 16px;
}

.image-gallery {
  display: flex;
  gap: 12px;
  overflow-x: auto;
  padding: 4px 0;
}

.gallery-image {
  width: 180px;
  height: 180px;
  border-radius: 8px;
  cursor: pointer;
  transition: transform 0.2s;
  flex-shrink: 0;
}

.gallery-image:hover {
  transform: scale(1.05);
}

/* 卡片通用样式 */
.detail-card {
  background: #fff;
  border-radius: 12px;
  box-shadow: 0 4px 16px rgba(0,0,0,0.08);
  margin-bottom: 16px;
  overflow: hidden;
}

.detail-row {
  display: flex;
  gap: 16px;
  margin-bottom: 16px;
}

.flex-1 {
  flex: 1;
}

/* 卡片标题栏 */
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

.card-header-gray {
  background: linear-gradient(135deg, #606266 0%, #555558 100%);
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

/* 卡片内容区 */
.card-content {
  padding: 16px;
}

/* 题目/答案/解析文字 */
.question-text {
  white-space: pre-wrap;
  word-break: break-word;
  line-height: 1.8;
  font-size: 15px;
  color: #303133;
}

/* 解析图片 */
.analysis-image {
  margin-top: 12px;
}

.analysis-img {
  width: 200px;
  height: 200px;
  border-radius: 8px;
  cursor: pointer;
}

/* 元数据行 */
.meta-row {
  display: flex;
  gap: 32px;
  margin-bottom: 12px;
}

.meta-row:last-child {
  margin-bottom: 0;
}

.meta-item {
  display: flex;
  align-items: center;
  gap: 8px;
}

.meta-item label {
  color: #909399;
  font-size: 14px;
}

.meta-item span {
  color: #303133;
  font-size: 14px;
}

/* 黄色星星难度 */
.difficulty-stars-yellow {
  font-size: 18px;
  letter-spacing: 3px;
  color: #f5c518;
}

/* 标签区域 */
.tags-area {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 16px;
}

.tags-label {
  color: #909399;
  font-size: 14px;
}

/* 相似题 */
.similar-item {
  padding: 12px;
  background: #f5f7fa;
  border-radius: 8px;
  margin-bottom: 12px;
}

.similar-item:last-child {
  margin-bottom: 0;
}

.similar-item p {
  margin: 0 0 8px 0;
  line-height: 1.6;
}

.similar-item p:last-child {
  margin-bottom: 0;
}

/* 文字辅助 */
.text-muted {
  color: #c0c4cc;
  font-size: 14px;
}
```

---

### Task 4: 验证实现

- [ ] **Step 1: 检查模板语法**

确认所有 Vue 模板指令正确闭合，无语法错误

- [ ] **Step 2: 检查样式冲突**

确认新增样式未与现有样式冲突，hover 效果正常

- [ ] **Step 3: 检查星星显示**

确认 `getYellowStars` 函数正确导入到模板中（需在 getDifficultyStars 调用处也使用新函数，或直接替换模板中对 difficulty 的显示）

---

## 验收标准检查

1. ✅ 详情页显示为卡片分区式布局
2. ✅ 难度显示为大号黄色星星（与难度数字对应，如难度4显示 ★★★★☆）
3. ✅ 题目/答案/解析/元数据/相似题各有独立卡片和对应颜色标题栏
4. ✅ 卡片有圆角和阴影，视觉效果有层次感
5. ✅ 原图展示支持横向滚动和点击预览
