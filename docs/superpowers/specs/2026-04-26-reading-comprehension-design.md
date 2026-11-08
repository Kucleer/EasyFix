# 英语阅读理解题型设计方案

## 1. 概述

为 EasyFix 增加英语阅读理解题型，支持：
- 通过 LLM 生成适配的英语短文并存入短文库
- 从短文库选择短文，自动生成配套选择题
- 基于短文创建练习集，进行同屏测试并记录答案

## 2. 数据模型

### 2.1 新建数据表

#### ReadingPassage（短文库）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | Integer | 主键 |
| title | String(200) | 短文标题 |
| content | Text | 英文短文内容 |
| topic | String(100) | 话题主题（如：校园生活、科技、文化） |
| grade | Integer | 适用年级 1-12 |
| difficulty | Integer | 难度 1-5 |
| word_count | Integer | 词数 |
| source | String(50) | 来源：generated=LLM生成, manual=手动录入 |
| deleted | Boolean | 软删除标记 |
| created_at | DateTime | 创建时间 |
| updated_at | DateTime | 更新时间 |

#### ReadingQuestion（阅读理解选择题）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | Integer | 主键 |
| passage_id | Integer | 关联短文ID（外键） |
| question_number | Integer | 题号 1-4 |
| question_text | Text | 英文题目 |
| option_a | String(500) | 选项A |
| option_b | String(500) | 选项B |
| option_c | String(500) | 选项C |
| option_d | String(500) | 选项D |
| correct_answer | String(1) | 正确答案 A/B/C/D |
| explanation | Text | 解析 |
| deleted | Boolean | 软删除标记 |
| created_at | DateTime | 创建时间 |

### 2.2 复用现有数据表

#### PracticeSet 新增字段

| 字段 | 类型 | 说明 |
|------|------|------|
| source_type | String(20) | 增加 `reading` 类型 |
| passage_id | Integer | 关联短文ID（仅 source_type=reading 时使用） |

## 3. API 设计

### 3.1 短文库管理

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /api/readings | 短文列表（支持按 topic/grade/difficulty 筛选） |
| GET | /api/readings/{id} | 获取短文详情（含选择题） |
| POST | /api/readings | 创建短文（手动录入） |
| PUT | /api/readings/{id} | 更新短文 |
| DELETE | /api/readings/{id} | 删除短文（软删除） |

### 3.2 短文生成

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | /api/readings/generate | LLM 生成短文 + 选择题 |
| GET | /api/readings/topics | 获取可选话题列表 |

### 3.3 练习集（扩展）

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | /api/practice-sets/generate-from-reading | 从短文生成练习集 |
| GET | /api/practice-sets/{id}/reading-view | 获取阅读理解练习视图（短文+题目同屏） |

## 4. LLM Prompt 设计

### 4.1 短文生成 Prompt

```
你是一位专业的英语教师。请根据以下要求生成一篇英语阅读理解短文。

## 要求
- 年级：{grade}
- 话题：{topic}
- 难度：{difficulty_label}（1=简单, 2=较简单, 3=中等, 4=较难, 5=困难）
- 词数：{word_count_range}

## 输出格式
请以以下JSON格式返回：
{{
    "title": "短文标题（中文或英文均可）",
    "content": "英语短文内容",
    "word_count": 实际词数,
    "topic": "话题"
}}

注意：
- 短文内容应为2-4段，难度与指定等级匹配
- 避免使用过于生僻的词汇
- 内容健康积极，适合对应年级学生阅读
```

### 4.2 选择题生成 Prompt

```
你是一位专业的英语教师。请为以下英语短文生成4道阅读理解选择题。

## 短文
{passage_content}

## 要求
- 题型：4选1选择题
- 每题必须包含：A/B/C/D 四个选项
- 问题应涵盖：主旨大意、细节理解、推理判断、词义猜测等类型
- 正确答案分布合理（不全部选同一选项）

## 输出格式
请以以下JSON格式返回：
{{
    "questions": [
        {{
            "question_number": 1,
            "question_text": "英文题目",
            "option_a": "A. 选项内容",
            "option_b": "B. 选项内容",
            "option_c": "C. 选项内容",
            "option_d": "D. 选项内容",
            "correct_answer": "A",
            "explanation": "简要解析"
        }},
        ...共4道题
    ]
}}

注意：
- 题目和选项都要用英文
- 选项长度适中，避免过长
- 解析用中文简要说明
```

## 5. 话题列表（预设）

```python
TOPICS = [
    "校园生活", "家庭生活", "日常生活", "兴趣爱好",
    "科技发展", "环境保护", "文化艺术", "体育运动",
    "健康与医疗", "旅行与地理", "节日与习俗", "历史人物",
    "未来职业", "人际交往", "饮食文化", "动物与自然"
]
```

## 6. 难度词数参考

| 难度 | 年级参考 | 词数范围 |
|------|----------|----------|
| 1 | 小学1-3年级 | 80-120词 |
| 2 | 小学4-6年级 | 120-180词 |
| 3 | 初一/初二 | 180-250词 |
| 4 | 初三/高一 | 250-320词 |
| 5 | 高二/高三 | 320-400词 |

## 7. 前端页面设计

### 7.0 导航与路由

导航栏新增独立菜单项「阅读」，路由 `/reading`，插入在「练习」和「统计」之间：

| 菜单 | 路径 | 位置 |
|------|------|------|
| ... | ... | ... |
| 练习 | /practice-sets | |
| **阅读** | **/reading** | **新增，在此位置** |
| 统计 | /stats | |
| ... | ... | ... |

`/reading` 页面作为阅读理解的入口页，整合短文库管理和练习入口。

### 7.1 阅读理解首页（/reading）

整体分两栏布局：
- **左侧**：短文库管理区
  - 列表展示（卡片形式，显示标题、话题、年级、难度、词数）
  - 筛选器：话题下拉、年级下拉、难度星级
  - 操作按钮：生成短文、删除
- **右侧**：选中短文的详情 + 操作
  - 完整短文展示
  - 4道选择题预览（含答案开关）
  - 按钮：「基于此题创建练习集」

### 7.2 生成短文弹窗

- 表单字段：
  - 年级（1-12 下拉选择）
  - 话题（下拉选择，预设16个话题）
  - 难度（1-5 滑块或星级）
- 按钮：生成（调用 LLM）→ 确认保存

### 7.3 练习集测试页面（扩展）

当 `source_type=reading` 时：
- 布局：左侧/上方显示短文（可滚动），右侧/下方显示4道选择题
- 交卷按钮 → 计算正确率 → 记录到练习集复习结果

## 8. 实现计划

### 阶段一：数据模型
1. 新建 `ReadingPassage` 模型和表
2. 新建 `ReadingQuestion` 模型和表
3. 扩展 `PracticeSet` 增加 `passage_id` 字段
4. 创建对应的 Pydantic Schemas

### 阶段二：后端 API
5. 实现短文 CRUD API
6. 实现 LLM 生成短文接口
7. 实现 LLM 生成选择题接口
8. 扩展练习集 API 支持从短文生成

### 阶段三：前端
9. 阅读理解入口页（`/reading`）：短文库列表 + 详情展示
10. 生成短文弹窗组件
11. 阅读理解练习测试页面（在 PracticeSets 中扩展 reading 视图）

## 9. 技术要点

- **事务处理**：短文和选择题在同一事务中创建，确保数据一致性
- **Prompt 缓存**：避免重复调用 LLM，生成后可预览确认再保存
- **软删除**：所有删除操作使用软删除，便于恢复
- **复用 PracticeSet**：借助现有练习集架构，只需扩展 `source_type=reading` 的特殊处理逻辑
