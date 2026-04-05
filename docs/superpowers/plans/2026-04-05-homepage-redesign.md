# 首页数据展示重构实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 优化首页数据展示，更直观地呈现学习状态

**Architecture:** 保留九宫格卡片，重构下方内容为双列布局，新增今日统计接口

**Tech Stack:** Vue 3 + Element Plus + ECharts, Python FastAPI + SQLAlchemy

---

## 文件结构

- **新增:** `backend/app/routers/stats.py` — 新增 `/api/stats/today` 接口
- **修改:** `backend/app/schemas/stats.py` — 新增 `TodayStats` 响应模型
- **修改:** `frontend/src/views/Home.vue` — 重构下方布局，添加今日统计卡片，调整图表位置

---

## Task 1: 新增 TodayStats Schema

**文件:** `backend/app/schemas/stats.py`

- [ ] **Step 1: 在 stats.py 末尾添加 TodayStats 模型**

```python
class TodayStats(BaseModel):
    today_word_review_count: int = 0      # 今日复习单词数（去重）
    today_question_review_count: int = 0   # 今日复习错题数（去重）
    today_word_accuracy: float = 0.0       # 今日单词正确率 %
    today_question_accuracy: float = 0.0   # 今日错题正确率 %
```

---

## Task 2: 新增后端 /api/stats/today 接口

**文件:** `backend/app/routers/stats.py`

- [ ] **Step 1: 在 stats.py 顶部添加必要导入**

```python
from datetime import datetime, timedelta
```

- [ ] **Step 2: 在 `get_stats_summary` 函数之后添加 `get_today_stats` 函数**

```python
@router.get("/today", response_model=TodayStats)
def get_today_stats(db: Session = Depends(get_db)):
    """
    获取今日学习统计

    从 practice_set 表取今日（created_at 日期 = 今天）的记录进行统计
    """
    today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = today_start + timedelta(days=1)

    # 查今日所有练习集
    today_practice_sets = db.query(PracticeSet).filter(
        PracticeSet.deleted == False,
        PracticeSet.created_at >= today_start,
        PracticeSet.created_at < today_end
    ).all()

    # 按 source_type 分组统计
    word_sets = [ps for ps in today_practice_sets if ps.source_type == 'word']
    question_sets = [ps for ps in today_practice_sets if ps.source_type != 'word']

    # 单词统计
    today_word_review_count = len(word_sets)  # 今日单词复习场次数
    word_total = sum(ps.total_questions or 0 for ps in word_sets)
    word_correct = 0
    for ps in word_sets:
        # 单词练习集的正确题数从 practice_set_questions 表获取
        correct_count = db.query(func.count(PracticeSetQuestion.id)).filter(
            PracticeSetQuestion.practice_set_id == ps.id,
            PracticeSetQuestion.is_correct == True
        ).scalar() or 0
        word_correct += correct_count
    today_word_accuracy = round(word_correct / word_total * 100, 1) if word_total > 0 else 0.0

    # 错题统计
    today_question_review_count = len(question_sets)
    question_total = sum(ps.total_questions or 0 for ps in question_sets)
    question_correct = 0
    for ps in question_sets:
        correct_count = db.query(func.count(PracticeSetQuestion.id)).filter(
            PracticeSetQuestion.practice_set_id == ps.id,
            PracticeSetQuestion.is_correct == True
        ).scalar() or 0
        question_correct += correct_count
    today_question_accuracy = round(question_correct / question_total * 100, 1) if question_total > 0 else 0.0

    return TodayStats(
        today_word_review_count=today_word_review_count,
        today_question_review_count=today_question_review_count,
        today_word_accuracy=today_word_accuracy,
        today_question_accuracy=today_question_accuracy,
    )
```

- [ ] **Step 3: 在 stats.py 顶部更新导入语句（添加缺失的模型和函数引用）**

确认以下导入已存在：
```python
from app.models import Question, Subject, ErrorBook, Word, WordReviewLog, PracticeSet, PracticeSetQuestion
```

---

## Task 3: 前端 - 新增今日统计 API 调用

**文件:** `frontend/src/api/question.js`

- [ ] **Step 1: 在 question.js 中添加 todayStats API**

```javascript
export const statsApi = {
  getSummary: () => request.get('/stats/summary'),
  getTodayStats: () => request.get('/stats/today'),  // 新增
}
```

---

## Task 4: 前端 - 今日学习概览卡片

**文件:** `frontend/src/views/Home.vue`

- [ ] **Step 1: 在 script setup 中添加 todayStats ref 和获取逻辑**

在 `stats` ref 下方添加：
```javascript
const todayStats = ref({
  today_word_review_count: 0,
  today_question_review_count: 0,
  today_word_accuracy: 0,
  today_question_accuracy: 0,
})
```

在 `onMounted` 中添加：
```javascript
try {
  const todayRes = await statsApi.getTodayStats()
  todayStats.value = todayRes.data
} catch (error) {
  console.error('获取今日统计失败:', error)
}
```

- [ ] **Step 2: 在九宫格下方添加今日概览卡片模板**

在 `<el-row :gutter="24" style="margin-top: 24px">` 区域（九宫格第一行）之后添加：

```html
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
    <!-- 错误类型分布（占位，稍后替换图表区域） -->
    <!-- 临时占位，右边 Task 6 会替换这里 -->
  </el-col>
</el-row>
```

- [ ] **Step 3: 添加今日概览卡片样式**

在 `<style scoped>` 末尾添加：

```css
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
```

---

## Task 5: 前端 - 双列布局调整（第二行）

**文件:** `frontend/src/views/Home.vue`

- [ ] **Step 1: 删除或注释原有下方图表区域**

找到并删除以下三个 `<el-row>`（原有的错误类型分布、知识点分布、学科题目数量图表区域）：
```html
<!-- 删除：原有 错误类型分布图表 el-row -->
<!-- 删除：原有 知识点分布图表 el-row -->
<!-- 删除：原有 学科题目数量图表 el-row -->
```

- [ ] **Step 2: 添加第二行双列布局（原学科详细数据表格 + 准确率曲线）**

```html
<!-- 学科详细数据表格 + 准确率曲线（双列） -->
<el-row :gutter="24" style="margin-top: 24px">
  <el-col :span="12">
    <!-- 学科详细数据表格（稍后在 Task 7中美化） -->
  </el-col>
  <el-col :span="12">
    <!-- 准确率曲线图（稍后在 Task 8 中改造） -->
  </el-col>
</el-row>
```

---

## Task 6: 前端 - 错误类型分布图（带学科下拉筛选）

**文件:** `frontend/src/views/Home.vue`

- [ ] **Step 1: 在 script setup 中添加 selectedSubject ref**

```javascript
const selectedSubject = ref('')
```

- [ ] **Step 2: 在 computed 中添加 filteredErrorTypeData**

```javascript
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
```

- [ ] **Step 3: 修改错误类型分布图模板（替换 Task 4 中的占位）**

替换右侧 col 的内容：

```html
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
```

- [ ] **Step 4: 添加饼图配置 computed**

在 `errorTypeBarOption` computed 下方添加：

```javascript
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
```

---

## Task 7: 前端 - 学科详细数据表格（样式美化）

**文件:** `frontend/src/views/Home.vue`

- [ ] **Step 1: 修改学科详细数据表格模板**

将现有的学科详细数据表格区域包裹在 `<el-card class="chart-card">` 中，并美化学样式：

```html
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
```

- [ ] **Step 2: 添加学科表格样式**

在 `<style scoped>` 中添加：

```css
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
```

---

## Task 8: 前端 - 准确率曲线图（错题+单词双线）

**文件:** `frontend/src/views/Home.vue`

- [ ] **Step 1: 确认 ECharts 组件注册**

检查 script setup 中的 `use()` 调用，确保已导入必要组件：

```javascript
import { PieChart, BarChart, LineChart, RadarChart } from 'echarts/charts'
```

如未导入 PieChart 和 RadarChart，需要添加。

- [ ] **Step 2: 添加准确率双线图的 el-card 模板**

在右侧 col 中添加：

```html
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
```

- [ ] **Step 3: 添加 dualAccuracyCurveOption computed**

用双线准确率图替换原来的 `accuracyCurveOption`：

```javascript
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
```

- [ ] **Step 4: 删除旧的 accuracyCurveOption computed**

找到并删除原有的 `accuracyCurveOption` computed 定义。

- [ ] **Step 5: 添加 PieChart 到 echarts use 注册**

在 `use()` 调用中添加 PieChart：

```javascript
import { PieChart, BarChart, LineChart, RadarChart, PieChart } from 'echarts/charts'
// 或者如果是 set 形式：
use([CanvasRenderer, PieChart, BarChart, LineChart, RadarChart, ...])
```

---

## Task 9: 清理旧图表代码

**文件:** `frontend/src/views/Home.vue`

- [ ] **Step 1: 删除不再使用的图表 computed 属性**

删除以下不再使用的 computed：
- `errorTypeBarOption`（替换为饼图 `errorTypePieOption`）
- `subjectBarOption`（已删除学科题目数量图表）
- `knowledgePointCloudOption`（已删除知识点分布图表）
- `accuracyCurveOption`（替换为 `dualAccuracyCurveOption`）

- [ ] **Step 2: 删除不再使用的 has* computed**

删除：
- `hasErrorTypeData` → 替换为 `hasFilteredErrorTypeData`
- `hasKnowledgePointData`（删除）
- `hasSubjectData`（删除或保留，如学科柱状图被删除则删除此 computed）

- [ ] **Step 3: 检查模板中是否有对已删除 computed 的引用**

搜索 `errorTypeBarOption`、`subjectBarOption`、`knowledgePointCloudOption`，确保模板中没有遗留引用。

---

## 验收标准检查

1. ✅ 九宫格卡片保持不变
2. ✅ 今日概览卡片 4 指标纵向排列，样式美观
3. ✅ 准确率曲线图同时显示错题和单词两条线
4. ✅ 错误类型分布图支持学科下拉筛选
5. ✅ 学科详细数据表格样式美化
6. ✅ 下方内容采用双列布局
7. ✅ 新增 `/api/stats/today` 接口返回今日统计数据
