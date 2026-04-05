# 首页数据展示重构设计方案

**Goal:** 优化首页数据展示，更直观地呈现学习状态

**Architecture:** 保留九宫格卡片，重构下方内容为双列布局，新增今日统计接口

**Tech Stack:** Vue 3 + Element Plus + ECharts

---

## 页面布局

```
┌─────────────────────────────────────────────────┐
│  九宫格统计卡片（3×3，保持不变）                   │
├────────────────────┬────────────────────────────┤
│                    │                            │
│  今日学习概览卡片    │  错误类型分布              │
│  (4指标纵向排列)     │  (带学科下拉筛选)          │
│                    │                            │
├────────────────────┼────────────────────────────┤
│                    │                            │
│  学科详细数据表格     │  准确率曲线图              │
│  (样式美化)          │  (错题+单词双线)           │
│                    │                            │
└────────────────────┴────────────────────────────┘
```

---

## 文件变更

- **新增:** `backend/app/routers/stats.py` — 新增 `/api/stats/today` 接口
- **新增:** `backend/app/schemas/stats.py` — 新增 `TodayStats` 响应模型
- **修改:** `frontend/src/views/Home.vue` — 重构下方布局，添加今日统计卡片，调整图表位置

---

## 实现任务

### Task 1: 新增后端今日统计接口

**文件:** `backend/app/routers/stats.py`

**新增接口:** `GET /api/stats/today`

**响应模型:**
```python
class TodayStats(BaseModel):
    today_word_review_count: int = 0      # 今日复习单词数（去重）
    today_question_review_count: int = 0   # 今日复习错题数（去重）
    today_word_accuracy: float = 0.0       # 今日单词正确率 %
    today_question_accuracy: float = 0.0  # 今日错题正确率 %
```

**统计逻辑:**
- 从 `practice_set` 表取 `created_at` 日期 = 今天的记录
- 单词复习数：`source_type === 'word'` 的题目去重计数
- 错题复习数：`source_type !== 'word'` 的题目去重计数
- 正确率：各类型中 `is_correct = true` 的题目比例

**路由注册:** 在 `stats.py` 中添加新路由函数

---

### Task 2: 新增 TodayStats Schema

**文件:** `backend/app/schemas/stats.py`

**新增模型:**
```python
class TodayStats(BaseModel):
    today_word_review_count: int = 0
    today_question_review_count: int = 0
    today_word_accuracy: float = 0.0
    today_question_accuracy: float = 0.0
```

---

### Task 3: 前端 - 今日学习概览卡片

**文件:** `frontend/src/views/Home.vue`

**样式要求:**
- 深色渐变背景（深蓝/紫色渐变：`#667eea` → `#764ba2`）
- 4个指标纵向排列在卡片内
- 每个指标包含：图标 + 数字 + 标签
- 数字白色大字（28px），标签白色小字（14px）
- 图标使用 SVG 或 Element Plus 图标

**4个指标（纵向排列）:**
| 指标 | 字段 | 图标 |
|------|------|------|
| 今日复习单词数 | `today_word_review_count` | 单词本图标 |
| 今日复习错题数 | `today_question_review_count` | 错题本图标 |
| 今日单词正确率 | `today_word_accuracy` | 百分号图标 |
| 今日错题正确率 | `today_question_accuracy` | 勾选图标 |

**调用接口:** `GET /api/stats/today`

---

### Task 4: 前端 - 准确率曲线图（错题+单词双线）

**文件:** `frontend/src/views/Home.vue`

**图表要求:**
- 在同一个图表中显示两条线
- 错题准确率线：蓝色 `#409eff`
- 单词正确率线：绿色 `#67c23a`
- 共用同一 Y 轴（0-100%）
- 悬浮提示分别显示两条线的数值
- 保留时间范围筛选（周/月/3月/半年/全部）

**数据来源:**
- 错题准确率曲线：从现有 `word_accuracy_curve` 数据中提取（需后端新增错题准确率曲线字段）
- 单词正确率曲线：使用现有 `word_accuracy_curve`

**备注:** 需要确认后端是否已有错题准确率曲线数据，如有则直接使用；如无则复用单词曲线作为替代展示

---

### Task 5: 前端 - 错误类型分布图（带学科筛选）

**文件:** `frontend/src/views/Home.vue`

**功能要求:**
- 添加学科下拉选择器，默认选中第一个学科（如果有数学则默认数学）
- 切换学科后，图表数据动态更新
- 下拉选项从 `stats.by_subject` 数据中提取 `subject_name`

**图表样式:**
- 饼图或柱状图，取决于数据特点
- 错误类型颜色：计算=#f56c6c, 概念=#e6a23c, 审题=#909399, 粗心=#67c23a, 其他=#409eff

---

### Task 6: 前端 - 学科详细数据表格（样式美化）

**文件:** `frontend/src/views/Home.vue`

**美化内容:**
- 表头添加渐变背景色（`#667eea` → `#764ba2`）
- 序号列居中显示
- 难度分布列使用 Element Plus `el-progress` 彩色进度条
- 错题数列使用醒目颜色（蓝色 `#409eff`）
- 表格行 hover 高亮
- 增加圆角（`border-radius: 12px`）和阴影
- 保持 `el-table` 的 stripe 属性

---

### Task 7: 前端 - 双列布局调整

**文件:** `frontend/src/views/Home.vue`

**布局结构:**
```
<el-row> 九宫格卡片
<el-row> 左：今日概览卡片  右：错误类型分布图
<el-row> 左：学科详细表格  右：准确率曲线图
```

**样式:**
- 使用 `gutter: 24` 控制列间距
- 左列 `span="12"`，右列 `span="12"`
- 每列内部使用 `<el-row>` 上下排列子模块

---

## 验收标准检查

1. ✅ 九宫格卡片保持不变
2. ✅ 今日概览卡片 4 指标纵向排列，样式美观
3. ✅ 准确率曲线图同时显示错题和单词两条线
4. ✅ 错误类型分布图支持学科下拉筛选
5. ✅ 学科详细数据表格样式美化
6. ✅ 下方内容采用双列布局
7. ✅ 新增 `/api/stats/today` 接口返回今日统计数据
