# 练习集批改与正确率统计 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现练习集批改与正确率统计功能，包括列表正确率列、详情原题展示、批改流程、错题正确率字段和筛选

**Architecture:** 后端模型和API修改 + 前端列表和批改流程改造

**Tech Stack:** Vue 3 + FastAPI + SQLAlchemy

---

## 文件修改

### 后端
- Modify: `backend/app/models/question.py` - 添加 error_count, correct_count 字段
- Modify: `backend/app/models/practice_set.py` - PracticeSet 添加 accuracy 字段，PracticeSetQuestion 添加 is_correct 字段
- Modify: `backend/app/routers/practice_set.py` - 更新 mark-reviewed 接口支持批改参数

### 前端
- Modify: `frontend/src/views/PracticeSets.vue` - 列表正确率列、详情原题展示、批改弹窗
- Modify: `frontend/src/views/Questions.vue` - 正确率筛选和列表正确率列

### 数据库
- 执行 ALTER TABLE 添加新字段

---

## 实施步骤

### Task 1: 数据库添加新字段

**Files:**
- Modify: `backend/easyfix.db` (SQLite)

- [ ] **Step 1: 添加 question 表新字段**

```sql
ALTER TABLE question ADD COLUMN error_count INTEGER DEFAULT 0;
ALTER TABLE question ADD COLUMN correct_count INTEGER DEFAULT 0;
```

- [ ] **Step 2: 添加 practice_set_question 表新字段**

```sql
ALTER TABLE practice_set_question ADD COLUMN is_correct BOOLEAN;
```

- [ ] **Step 3: 添加 practice_set 表新字段**

```sql
ALTER TABLE practice_set ADD COLUMN accuracy FLOAT;
```

### Task 2: 后端模型修改

**Files:**
- Modify: `backend/app/models/question.py:24-25`

- [ ] **Step 1: Question 模型添加 error_count 和 correct_count 字段**

在 `review_count` 字段后添加：
```python
error_count = Column(Integer, default=0, nullable=False)  # 错误次数
correct_count = Column(Integer, default=0, nullable=False)  # 正确次数
```

### Task 3: 后端 PracticeSet 模型修改

**Files:**
- Modify: `backend/app/models/practice_set.py:19-22`

- [ ] **Step 1: PracticeSet 模型添加 accuracy 字段**

在 `review_count` 字段后添加：
```python
accuracy = Column(Float, nullable=True)  # 整体正确率百分比
```

- [ ] **Step 2: PracticeSetQuestion 模型添加 is_correct 字段**

在 `display_order` 字段后添加：
```python
is_correct = Column(Boolean, nullable=True)  # 批改是否正确
```

### Task 4: 后端路由和 Schema 修改

**Files:**
- Modify: `backend/app/routers/practice_set.py:29-44`

- [ ] **Step 1: 更新 PracticeSetQuestionResponse 添加原题字段**

修改 `PracticeSetQuestionResponse` 类：
```python
class PracticeSetQuestionResponse(BaseModel):
    id: int
    question_id: int
    similar_question_id: Optional[int] = None
    display_order: int
    question_text: Optional[str] = None
    answer: Optional[str] = None
    phonetic: Optional[str] = None
    difficulty: Optional[int] = None
    is_correct: Optional[bool] = None
    user_answer: Optional[str] = None
    tags: Optional[List[dict]] = None
    # 新增：原题信息
    original_question_text: Optional[str] = None  # 原题题目
    original_answer: Optional[str] = None  # 原题答案
    original_image: Optional[str] = None  # 原题图片

    class Config:
        from_attributes = True
```

- [ ] **Step 2: 更新 PracticeSetResponse 添加 accuracy 字段**

在 `PracticeSetResponse` 的 `review_count` 后添加：
```python
accuracy: Optional[float] = None  # 整体正确率
```

### Task 5: 后端 mark-reviewed 接口修改

**Files:**
- Modify: `backend/app/routers/practice_set.py:461-502`

- [ ] **Step 1: 修改 mark-reviewed 接口支持批改参数**

将原接口签名从：
```python
@router.post("/{practice_set_id}/mark-reviewed")
def mark_reviewed(practice_set_id: int, images: Optional[str] = Form(None), db: Session = Depends(get_db)):
```

修改为：
```python
@router.post("/{practice_set_id}/mark-reviewed")
def mark_reviewed(
    practice_set_id: int,
    images: Optional[str] = Form(None),
    is_all_correct: Optional[bool] = Form(None),
    question_results: Optional[str] = Form(None),  # JSON字符串
    db: Session = Depends(get_db)
):
```

- [ ] **Step 2: 更新接口逻辑处理批改结果**

在更新练习集部分后，添加批改逻辑：
```python
# 解析题目结果
results_list = []
if question_results:
    import json
    results_list = json.loads(question_results)

# 获取所有关联题目
ps_questions = db.query(PracticeSetQuestion).filter(
    PracticeSetQuestion.practice_set_id == practice_set_id
).all()

# 统计正确率
correct_count = 0
total_count = len(ps_questions)

for psq in ps_questions:
    question = db.query(Question).filter(Question.id == psq.question_id).first()
    if not question:
        continue

    # 更新复习次数
    question.review_count = (question.review_count or 0) + 1

    # 根据整体批改或逐题批改更新
    if is_all_correct == True:
        # 整体全对
        psq.is_correct = True
        question.correct_count = (question.correct_count or 0) + 1
        correct_count += 1
    elif results_list:
        # 逐题批改
        result = next((r for r in results_list if r.get('question_id') == psq.question_id), None)
        if result is not None:
            psq.is_correct = result.get('is_correct')
            if result.get('is_correct'):
                question.correct_count = (question.correct_count or 0) + 1
                correct_count += 1
            else:
                question.error_count = (question.error_count or 0) + 1

    question.last_reviewed_at = now

# 计算并保存整体正确率
if total_count > 0:
    ps.accuracy = round(correct_count / total_count * 100, 1)
else:
    ps.accuracy = None
```

- [ ] **Step 3: 更新响应返回 accuracy**

修改返回语句：
```python
return {"message": "已标记为复习", "review_count": ps.review_count, "accuracy": ps.accuracy}
```

### Task 6: 前端 PracticeSets.vue - 列表正确率列

**Files:**
- Modify: `frontend/src/views/PracticeSets.vue:75-83`

- [ ] **Step 1: 在题目数列后添加正确率列**

在 `total_questions` 列后添加：
```html
<el-table-column prop="accuracy" label="正确率" width="80" align="center">
  <template #default="{ row }">
    {{ row.accuracy != null ? row.accuracy + '%' : '-' }}
  </template>
</el-table-column>
```

### Task 7: 前端 PracticeSets.vue - 详情原题展示

**Files:**
- Modify: `frontend/src/views/PracticeSets.vue` - 详情Tab题目列表

- [ ] **Step 1: 找到详情Tab题目列表位置，添加原题列**

在详情弹窗的题目列表中添加原题列：
```html
<el-table-column label="原题" min-width="200">
  <template #default="{ row }">
    <div v-if="row.original_question_text" class="original-question">
      {{ row.original_question_text.substring(0, 50) }}{{ row.original_question_text.length > 50 ? '...' : '' }}
    </div>
    <el-image
      v-if="row.original_image"
      :src="'/uploads/' + row.original_image"
      fit="contain"
      style="width: 40px; height: 40px; cursor: pointer;"
      @click="previewImage(row.original_image)"
    />
    <span v-if="!row.original_question_text && !row.original_image" class="text-muted">-</span>
  </template>
</el-table-column>
```

### Task 8: 前端 PracticeSets.vue - 批改弹窗

**Files:**
- Modify: `frontend/src/views/PracticeSets.vue` - 复习标记和批改流程

- [ ] **Step 1: 修改 markReviewed 方法判断来源类型**

将 `markReviewed` 函数修改为：
```javascript
const markReviewed = async (ps) => {
  currentReviewPs.value = ps

  // 单词练习集直接标记已复习
  if (ps.source_type === 'word') {
    try {
      await questionApi.markPracticeSetReviewed(ps.id)
      ElMessage.success('已标记为复习')
      fetchPracticeSets()
    } catch (error) {
      ElMessage.error('操作失败')
    }
    return
  }

  // 错题练习集进入批改流程
  gradingDialogVisible.value = true
  initGrading(ps)
}
```

- [ ] **Step 2: 添加批改相关状态和方法**

添加以下 ref 和方法：
```javascript
// 批改相关
const gradingDialogVisible = ref(false)
const gradingStep = ref('overall') // 'overall' | 'detail' | 'upload'
const gradingCurrentIndex = ref(0)
const gradingResults = ref({}) // { questionId: true/false }
const currentPsQuestions = ref([])

const initGrading = async (ps) => {
  // 获取练习集详情（含题目）
  const { data } = await questionApi.getPracticeSet(ps.id)
  currentPsQuestions.value = data.questions || []
  gradingResults.value = {}
  gradingCurrentIndex.value = 0
  gradingStep.value = 'overall'
}

const handleOverallGrading = (isAllCorrect) => {
  if (isAllCorrect) {
    // 整体全对
    currentPsQuestions.value.forEach(q => {
      gradingResults.value[q.question_id] = true
    })
    gradingStep.value = 'upload'
  } else {
    // 进入逐题批改
    gradingStep.value = 'detail'
  }
}

const handleQuestionGrading = (questionId, isCorrect) => {
  gradingResults.value[questionId] = isCorrect
  gradingCurrentIndex.value++

  if (gradingCurrentIndex.value >= currentPsQuestions.value.length) {
    // 全部批改完成，进入图片上传
    gradingStep.value = 'upload'
  }
}

const getGradingAccuracy = () => {
  const total = currentPsQuestions.value.length
  if (total === 0) return 0
  const correct = Object.values(gradingResults.value).filter(v => v === true).length
  return Math.round(correct / total * 100)
}

const submitGrading = async () => {
  // 构建批改结果
  const questionResults = Object.entries(gradingResults.value).map(([question_id, is_correct]) => ({
    question_id: parseInt(question_id),
    is_correct
  }))

  // 提交批改
  try {
    await questionApi.markPracticeSetReviewedWithGrading(
      currentReviewPs.value.id,
      questionResults
    )
    ElMessage.success('批改完成')
    gradingDialogVisible.value = false
    fetchPracticeSets()
  } catch (error) {
    ElMessage.error('批改提交失败')
  }
}
```

- [ ] **Step 3: 添加批改弹窗模板**

在 `uploadDialogVisible` 弹窗前添加批改弹窗：
```html
<!-- 整体批改弹窗 -->
<el-dialog v-model="gradingDialogVisible" title="批改练习集" width="500px" destroy-on-close>
  <div v-if="gradingStep === 'overall'" class="grading-overall">
    <p class="grading-tip">共 {{ currentPsQuestions.length }} 道题目</p>
    <p class="grading-question">本次练习整体正确情况如何？</p>
    <div class="grading-buttons">
      <el-button type="success" size="large" @click="handleOverallGrading(true)">全部正确</el-button>
      <el-button type="danger" size="large" @click="handleOverallGrading(false)">有错误</el-button>
    </div>
  </div>

  <!-- 逐题批改 -->
  <div v-if="gradingStep === 'detail'" class="grading-detail">
    <div class="grading-progress">
      {{ gradingCurrentIndex + 1 }} / {{ currentPsQuestions.length }}
      <span class="grading-accuracy">正确率: {{ getGradingAccuracy() }}%</span>
    </div>
    <div class="grading-question-item">
      <p class="question-text">{{ currentPsQuestions[gradingCurrentIndex]?.question_text }}</p>
      <p class="question-answer">答案: {{ currentPsQuestions[gradingCurrentIndex]?.answer }}</p>
    </div>
    <div class="grading-question-buttons">
      <el-button type="success" size="large" @click="handleQuestionGrading(currentPsQuestions[gradingCurrentIndex].question_id, true)">正确</el-button>
      <el-button type="danger" size="large" @click="handleQuestionGrading(currentPsQuestions[gradingCurrentIndex].question_id, false)">错误</el-button>
    </div>
  </div>
</el-dialog>
```

- [ ] **Step 4: 添加批改弹窗样式**

```css
.grading-overall {
  text-align: center;
  padding: 20px 0;
}

.grading-tip {
  font-size: 16px;
  color: #606266;
  margin-bottom: 20px;
}

.grading-question {
  font-size: 18px;
  font-weight: bold;
  color: #303133;
  margin-bottom: 30px;
}

.grading-buttons {
  display: flex;
  gap: 20px;
  justify-content: center;
}

.grading-detail {
  padding: 10px 0;
}

.grading-progress {
  font-size: 16px;
  color: #606266;
  margin-bottom: 20px;
  display: flex;
  justify-content: space-between;
}

.grading-accuracy {
  color: #409eff;
  font-weight: bold;
}

.grading-question-item {
  background: #f5f7fa;
  padding: 20px;
  border-radius: 8px;
  margin-bottom: 20px;
}

.grading-question-item .question-text {
  font-size: 16px;
  margin-bottom: 10px;
}

.grading-question-item .question-answer {
  font-size: 14px;
  color: #67c23a;
}

.grading-question-buttons {
  display: flex;
  gap: 20px;
  justify-content: center;
}
```

- [ ] **Step 5: API 调用更新**

在 questionApi 中添加新方法：
```javascript
markPracticeSetReviewedWithGrading(practiceSetId, questionResults) {
  return api.post(`/practice-sets/${practiceSetId}/mark-reviewed`, {
    question_results: JSON.stringify(questionResults)
  })
}
```

### Task 9: 前端 Questions.vue - 正确率筛选

**Files:**
- Modify: `frontend/src/views/Questions.vue`

- [ ] **Step 1: 添加正确率筛选选项**

在 filters 定义中添加：
```javascript
accuracy_range: null
```

在模板筛选区域添加：
```html
<el-select v-model="filters.accuracy_range" placeholder="正确率筛选" clearable @change="fetchQuestions" style="width: 130px">
  <el-option label="0-30% 薄弱" :value="[0, 30]" />
  <el-option label="30-60% 一般" :value="[30, 60]" />
  <el-option label="60-80% 良好" :value="[60, 80]" />
  <el-option label="80-100% 掌握" :value="[80, 100]" />
  <el-option label="无统计" :value="'none'" />
</el-select>
```

- [ ] **Step 2: 列表添加正确率列**

在表格中添加正确率列：
```html
<el-table-column label="正确率" width="100" sortable :sort-method="(a, b) => (a.correct_count || 0) / ((a.correct_count || 0) + (a.error_count || 0)) - (b.correct_count || 0) / ((b.correct_count || 0) + (b.error_count || 0))">
  <template #default="{ row }">
    <span v-if="row.correct_count != null || row.error_count != null">
      {{ getAccuracyDisplay(row) }}
    </span>
    <span v-else class="text-muted">-</span>
  </template>
</el-table-column>
```

添加辅助方法：
```javascript
const getAccuracyDisplay = (row) => {
  const correct = row.correct_count || 0
  const error = row.error_count || 0
  if (correct + error === 0) return '-'
  return Math.round(correct / (correct + error) * 100) + '%'
}
```

- [ ] **Step 3: API 参数处理**

在 fetchQuestions 中添加准确率筛选处理：
```javascript
if (filters.accuracy_range) {
  if (filters.accuracy_range === 'none') {
    params.no_accuracy = true
  } else {
    params.accuracy_min = filters.accuracy_range[0]
    params.accuracy_max = filters.accuracy_range[1]
  }
}
```

### Task 10: 验证实现

- [ ] **Step 1: 检查编译是否通过**

运行前端和后端服务确认无编译错误

- [ ] **Step 2: 验证功能**

1. 创建练习集
2. 在练习集列表查看正确率列
3. 点击标记已复习，测试整体批改流程
4. 测试逐题批改流程
5. 在错题列表测试正确率筛选
6. 检查错题详情正确率计算

---

## 验收标准检查

- [ ] 练习集列表显示正确率列，为空显示 "-"
- [ ] 练习集详情显示原题内容
- [ ] 标记已复习时支持整体批改（全部正确/有错误）
- [ ] 标记已复习时支持逐题批改
- [ ] 批改后正确率正确计算
- [ ] 批改后错题的 review_count、correct_count/error_count 正确更新
- [ ] 批改时可以上传完成图片（非必填）
- [ ] 错题列表支持正确率区间筛选
- [ ] 错题列表支持按正确率排序
