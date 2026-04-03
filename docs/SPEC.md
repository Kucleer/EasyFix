# EasyFix 错题整理系统 - 产品需求文档

## 文档信息

| 项目名称 | EasyFix 错题整理系统 |
|---------|---------------------|
| 当前版本 | v1.0.8 |
| 文档更新 | 2026-04-03 |
| 文档状态 | 进行中 |

---

## 一、项目概述

### 1.1 项目简介

EasyFix 是一款面向学生的本地错题整理软件，主要功能包括：错题图片上传与OCR识别、错题归档整理、多维度统计分析、以及基于LLM的相似题目智能推荐。

### 1.2 目标用户

- 中小学生（一年级至高三年级）
- 家长（辅助孩子整理错题）
- 教师（管理学生错题本）

### 1.3 核心价值

- **便捷录入**：拍照上传，OCR自动识别题目
- **智能整理**：按学科、年级、知识点自动归类
- **统计分析**：多维度了解错题分布，针对性复习
- **相似推荐**：AI生成同类型练习题，举一反三

---

## 二、技术架构

### 2.1 技术栈

| 层级 | 技术选型 | 说明 |
|------|---------|------|
| 前端 | Vue 3 + Element Plus | SPA单页应用 |
| 后端 | Python FastAPI | ASGI高性能框架 |
| 数据库 | MySQL 8.0 | 关系型数据库 |
| OCR | PaddleOCR | 本地离线OCR识别 |
| LLM | Anthropic Claude API / MiniMax | 相似题生成 |
| 文件存储 | 本地文件系统 | 按年月分目录存储 |

### 2.2 项目目录结构

```
EasyFix/
├── backend/                    # 后端项目
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py            # FastAPI入口
│   │   ├── config.py          # 配置管理
│   │   ├── database.py        # 数据库连接
│   │   ├── models/            # ORM模型
│   │   │   ├── question.py    # 错题表
│   │   │   ├── tag.py         # 标签表
│   │   │   ├── subject.py     # 学科表
│   │   │   ├── error_book.py  # 错题本表
│   │   │   ├── similar_question.py  # 相似题表
│   │   │   ├── knowledge_point.py  # 知识点表
│   │   │   └── operation_log.py     # 操作日志表
│   │   ├── schemas/           # Pydantic模型
│   │   ├── routers/           # API路由
│   │   │   ├── question.py    # 错题CRUD
│   │   │   ├── upload.py      # 图片上传+OCR
│   │   │   ├── stats.py       # 统计
│   │   │   ├── similar.py     # 相似题目
│   │   │   ├── subject.py     # 学科管理
│   │   │   ├── tag.py         # 标签管理
│   │   │   ├── error_book.py  # 错题本管理
│   │   │   ├── knowledge_point.py  # 知识点管理
│   │   │   └── config.py      # 系统配置
│   │   └── services/          # 业务逻辑
│   │       ├── ocr.py         # PaddleOCR服务
│   │       ├── llm.py         # LLM API服务
│   │       └── logger.py      # 日志服务
│   └── requirements.txt
├── frontend/                   # 前端项目 Vue3
│   ├── src/
│   │   ├── api/               # API调用
│   │   ├── views/             # 页面组件
│   │   │   ├── Home.vue       # 首页
│   │   │   ├── Questions.vue  # 错题列表
│   │   │   ├── Upload.vue     # 上传页面
│   │   │   ├── Stats.vue      # 统计页面
│   │   │   ├── Settings.vue   # 设置页面
│   │   │   └── Management.vue  # 管理中心
│   │   ├── router/            # 路由配置
│   │   └── main.js
│   └── package.json
├── uploads/                    # 上传文件存储
│   └── images/
│       └── {year}/
│           └── {month}/
│               └── {uuid}_{filename}
├── docs/                       # 文档目录
│   └── SPEC.md                # 本文档
├── CHANGELOG.md               # 变更日志
├── VERSION                    # 版本号文件
└── README.md
```

---

## 三、数据库设计

### 3.1 ER图

```
┌─────────────┐       ┌─────────────┐       ┌─────────────┐
│   Subject    │       │  ErrorBook  │       │     Tag     │
│   (学科)     │──────<│   (错题本)   │       │    (标签)    │
└─────────────┘       └─────────────┘       └─────────────┘
       │                     │                     │
       │                     │                     │
       │              ┌──────┴──────┐              │
       │              │             │              │
       └───────<──────┘             └──────<───────┘
              │     Question      │
              │      (错题)        │
              │                    │
              │              ┌──────┴──────┐
              │              │             │
              │              │             │
       ┌──────┴──────┐       │     QuestionTag
       │  Similar    │       │    (关联表)
       │  Question   │       │
       │  (相似题)    │       │
       └─────────────┘       │─────────────┘
                             │
                      ┌──────┴──────┐
                      │KnowledgePoint│
                      │   (知识点)   │
                      └─────────────┘
```

### 3.2 表结构详情

#### 3.2.1 学科表 (subject)

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | INTEGER | PK, AUTO | 主键 |
| name | VARCHAR(50) | NOT NULL, UNIQUE | 学科名称 |
| deleted | BOOLEAN | DEFAULT FALSE | 软删除标记 |
| created_at | DATETIME | DEFAULT NOW | 创建时间 |

**索引**: `idx_subject_deleted` ON `deleted`

#### 3.2.2 错题本表 (error_book)

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | INTEGER | PK, AUTO | 主键 |
| name | VARCHAR(100) | NOT NULL | 错题本名称 |
| subject_id | INTEGER | FK → subject.id | 所属学科 |
| description | TEXT | | 描述 |
| cover_image | VARCHAR(500) | | 封面图片路径 |
| original_images | TEXT | | JSON数组，存储多张原图路径 |
| deleted | BOOLEAN | DEFAULT FALSE | 软删除标记 |
| created_at | DATETIME | DEFAULT NOW | 创建时间 |
| updated_at | DATETIME | | 更新时间 |

**索引**:
- `idx_error_book_subject` ON `subject_id`
- `idx_error_book_deleted` ON `deleted`

#### 3.2.3 错题表 (question)

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | INTEGER | PK, AUTO | 主键 |
| error_book_id | INTEGER | FK → error_book.id | 所属错题本 |
| subject_id | INTEGER | FK → subject.id | 学科 |
| original_image | VARCHAR(500) | | 单个原图路径（兼容旧数据） |
| original_images | TEXT | | JSON数组，多个图片路径 |
| original_text | TEXT | | OCR识别的原始题目文本 |
| parsed_question | TEXT | | 解析后的题目（结构化） |
| answer | TEXT | | 答案 |
| analysis | TEXT | | 解析 |
| difficulty | INTEGER | DEFAULT 3, CHECK(1-5) | 难度1-5 |
| error_type | VARCHAR(50) | | 错误类型：计算/概念/审题/其他 |
| knowledge_point | VARCHAR(200) | | 知识点 |
| grade | INTEGER | CHECK(1-12) | 年级 |
| semester | INTEGER | CHECK(1-2) | 学期：1=上学期，2=下学期 |
| deleted | BOOLEAN | DEFAULT FALSE | 软删除标记 |
| created_at | DATETIME | DEFAULT NOW | 创建时间 |
| updated_at | DATETIME | | 更新时间 |

**索引**:
- `idx_question_error_book` ON `error_book_id`
- `idx_question_subject` ON `subject_id`
- `idx_question_grade` ON `grade`
- `idx_question_difficulty` ON `difficulty`
- `idx_question_deleted` ON `deleted`

**约束**: `CHECK(difficulty >= 1 AND difficulty <= 5)`

#### 3.2.4 标签表 (tag)

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | INTEGER | PK, AUTO | 主键 |
| name | VARCHAR(50) | NOT NULL, UNIQUE | 标签名称 |
| color | VARCHAR(20) | | 颜色代码 |
| deleted | BOOLEAN | DEFAULT FALSE | 软删除标记 |

#### 3.2.5 错题-标签关联表 (question_tag)

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| question_id | INTEGER | PK, FK → question.id | 错题ID |
| tag_id | INTEGER | PK, FK → tag.id | 标签ID |

#### 3.2.6 相似题目表 (similar_question)

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | INTEGER | PK, AUTO | 主键 |
| source_question_id | INTEGER | FK → question.id | 源错题ID |
| similar_text | TEXT | NOT NULL | 相似题目文本 |
| similar_answer | TEXT | | 相似题目答案 |
| similarity_score | FLOAT | | 相似度得分（预留） |
| deleted | BOOLEAN | DEFAULT FALSE | 软删除标记 |
| generated_at | DATETIME | DEFAULT NOW | 生成时间 |

**索引**: `idx_similar_source` ON `source_question_id`

#### 3.2.7 知识点表 (knowledge_point)

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | INTEGER | PK, AUTO | 主键 |
| name | VARCHAR(200) | NOT NULL | 知识点名称 |
| subject_id | INTEGER | FK → subject.id | 所属学科 |
| grade | INTEGER | CHECK(1-12) | 年级 |
| semester | INTEGER | CHECK(1-2) | 学期 |
| deleted | BOOLEAN | DEFAULT FALSE | 软删除标记 |
| created_at | DATETIME | DEFAULT NOW | 创建时间 |

**索引**:
- `idx_kp_subject` ON `subject_id`
- `idx_kp_grade` ON `grade`

#### 3.2.8 操作日志表 (operation_log)

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER | 主键 |
| operation_type | VARCHAR(50) | 操作类型 |
| target_id | INTEGER | 目标ID |
| target_type | VARCHAR(50) | 目标类型 |
| data | JSON | 操作数据 |
| success | BOOLEAN | 是否成功 |
| error | TEXT | 错误信息 |
| ip_address | VARCHAR(50) | IP地址 |
| user_agent | VARCHAR(500) | 用户代理 |
| created_at | DATETIME | 操作时间 |

#### 3.2.9 单词表 (word)

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | INTEGER | PK, AUTO | 主键 |
| english | VARCHAR(200) | NOT NULL | 英文单词 |
| chinese | VARCHAR(500) | NOT NULL | 中文释义 |
| phonetic | VARCHAR(200) | | 音标 |
| grade | INTEGER | CHECK(1-12) | 年级 |
| semester | INTEGER | CHECK(1-2) | 学期 |
| review_count | INTEGER | DEFAULT 0 | 复习次数 |
| correct_count | INTEGER | DEFAULT 0 | 正确次数 |
| last_reviewed_at | DATETIME | | 最后复习时间 |
| next_review_at | DATETIME | | 下次复习时间 |
| interval | INTEGER | DEFAULT 1 | 复习间隔（天） |
| deleted | BOOLEAN | DEFAULT FALSE | 软删除标记 |
| created_at | DATETIME | DEFAULT NOW | 创建时间 |
| updated_at | DATETIME | | 更新时间 |

**索引**:
- `idx_word_grade` ON `grade`
- `idx_word_deleted` ON `deleted`

#### 3.2.10 单词-标签关联表 (word_tag)

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| word_id | INTEGER | PK, FK → word.id | 单词ID |
| tag_id | INTEGER | PK, FK → tag.id | 标签ID |

#### 3.2.11 单词复习记录表 (word_review_log)

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | INTEGER | PK, AUTO | 主键 |
| word_id | INTEGER | FK → word.id | 单词ID |
| is_correct | BOOLEAN | | 是否正确 |
| user_answer | VARCHAR(200) | | 用户答案 |
| review_type | INTEGER | | 复习题型：1=默写，2=选择 |
| reviewed_at | DATETIME | | 复习时间 |

**索引**: `idx_review_log_word` ON `word_id`

#### 3.2.12 单词复习场次表 (word_review)

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | INTEGER | PK, AUTO | 主键 |
| total_count | INTEGER | | 总单词数 |
| correct_count | INTEGER | | 正确数 |
| error_count | INTEGER | | 错误数 |
| duration | INTEGER | | 用时（秒） |
| created_at | DATETIME | DEFAULT NOW | 创建时间 |

---

## 四、API接口文档

### 4.1 基础信息

- **Base URL**: `http://{host}:{port}/api`
- **默认端口**: 3000
- **认证方式**: 无（本地应用）
- **请求格式**: JSON
- **响应格式**: JSON

### 4.2 错题管理

#### 4.2.1 获取错题列表

```
GET /api/questions
```

**Query参数**:

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| skip | int | 否 | 跳过记录数，默认0 |
| limit | int | 否 | 返回数量，默认20，最大100 |
| subject_id | int | 否 | 学科ID |
| error_book_id | int | 否 | 错题本ID |
| difficulty | int | 否 | 难度1-5 |
| error_type | string | 否 | 错误类型 |
| grade | int | 否 | 年级1-12 |
| semester | int | 否 | 学期1-2 |
| keyword | string | 否 | 关键词搜索 |

**响应示例**:
```json
{
  "total": 100,
  "items": [
    {
      "id": 1,
      "error_book_id": 1,
      "subject_id": 1,
      "original_image": "2026/03/xxx.png",
      "original_images": ["2026/03/xxx.png"],
      "original_text": "原始题目文本",
      "parsed_question": "解析后题目",
      "answer": "答案",
      "analysis": "解析",
      "difficulty": 3,
      "error_type": "计算",
      "knowledge_point": "小数除法",
      "grade": 5,
      "semester": 2,
      "created_at": "2026-03-28T10:00:00",
      "tags": [{"id": 1, "name": "易错", "color": "#FF6B6B"}],
      "similar_questions": []
    }
  ]
}
```

#### 4.2.2 获取单条错题

```
GET /api/questions/{question_id}
```

**响应**: 同上单个item结构

#### 4.2.3 创建错题

```
POST /api/questions
```

**请求体**:
```json
{
  "error_book_id": 1,
  "subject_id": 1,
  "original_image": "2026/03/xxx.png",
  "original_images": ["2026/03/xxx.png"],
  "original_text": "原始题目文本",
  "parsed_question": "解析后题目",
  "answer": "答案",
  "analysis": "解析",
  "difficulty": 3,
  "error_type": "计算",
  "knowledge_point": "小数除法",
  "grade": 5,
  "semester": 2,
  "tag_ids": [1, 2]
}
```

#### 4.2.4 更新错题

```
PUT /api/questions/{question_id}
```

**请求体**: 同创建，支持部分更新

#### 4.2.5 删除错题（软删除）

```
DELETE /api/questions/{question_id}
```

**响应**: 204 No Content

#### 4.2.6 批量创建错题

```
POST /api/questions/batch
```

**请求体**:
```json
{
  "error_book_id": 1,
  "subject_id": 1,
  "grade": 5,
  "semester": 2,
  "images": ["2026/03/1.png", "2026/03/2.png"],
  "questions": [
    {
      "original_text": "题目1",
      "parsed_question": "题目1",
      "answer": "答案1",
      "difficulty": 3
    }
  ]
}
```

### 4.3 上传模块

#### 4.3.1 上传单张图片

```
POST /api/upload/image
Content-Type: multipart/form-data
```

**表单字段**:
- `file`: 图片文件

**响应**:
```json
{
  "image_path": "2026/03/xxx.png",
  "ocr_result": {
    "full_text": "识别出的完整文本",
    "blocks": [
      {"text": "block1", "bbox": [x,y,w,h]},
      {"text": "block2", "bbox": [x,y,w,h]}
    ],
    "provider": "paddleocr"
  }
}
```

#### 4.3.2 批量上传图片

```
POST /api/upload/batch
Content-Type: multipart/form-data
```

**表单字段**:
- `files`: 多个图片文件

#### 4.3.3 上传到错题本

```
POST /api/upload/to-error-book/{error_book_id}
Content-Type: multipart/form-data
```

**说明**: 图片保留在错题本中用于对比，不进行OCR识别

### 4.4 单词本模块

#### 4.4.1 获取单词列表

```
GET /api/words
```

**Query参数**:

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| skip | int | 否 | 跳过记录数，默认0 |
| limit | int | 否 | 返回数量，默认20，最大100 |
| grade | int | 否 | 年级1-12 |
| semester | int | 否 | 学期1-2 |
| tag_ids | string | 否 | 标签ID，多个用逗号分隔 |
| keyword | string | 否 | 关键词搜索（英文或中文） |

**响应示例**:
```json
{
  "total": 100,
  "items": [
    {
      "id": 1,
      "english": "apple",
      "chinese": "苹果",
      "phonetic": "/ˈæpl/",
      "grade": 3,
      "semester": 1,
      "review_count": 5,
      "correct_count": 4,
      "last_reviewed_at": "2026-03-29T10:00:00",
      "next_review_at": "2026-04-01T10:00:00",
      "tags": [{"id": 1, "name": "水果", "color": "#67c23a"}],
      "created_at": "2026-03-28T10:00:00"
    }
  ]
}
```

#### 4.4.2 获取单词详情

```
GET /api/words/{word_id}
```

#### 4.4.3 创建单词

```
POST /api/words
```

**请求体**:
```json
{
  "english": "apple",
  "chinese": "苹果",
  "phonetic": "/ˈæpl/",
  "grade": 3,
  "semester": 1,
  "tag_ids": [1, 2]
}
```

#### 4.4.4 更新单词

```
PUT /api/words/{word_id}
```

**请求体**: 同创建，支持部分更新

#### 4.4.5 删除单词（软删除）

```
DELETE /api/words/{word_id}
```

**响应**: 204 No Content

#### 4.4.6 批量创建单词

```
POST /api/words/batch
```

**请求体**:
```json
{
  "words": [
    {"english": "apple", "chinese": "苹果", "phonetic": "/ˈæpl/"},
    {"english": "banana", "chinese": "香蕉"}
  ],
  "grade": 3,
  "semester": 1,
  "tag_ids": [1]
}
```

#### 4.4.7 获取单词统计

```
GET /api/words/stats/summary
```

**响应**:
```json
{
  "total_words": 100,
  "total_reviews": 500,
  "total_correct": 400,
  "accuracy": 80.0,
  "mastered_words": 20,
  "learning_words": 60,
  "new_words": 20,
  "grade_distribution": {"3": 50, "4": 30, "5": 20},
  "review_today": 10,
  "due_words": 25
}
```

#### 4.4.8 开始复习

```
POST /api/words/review/start
```

**Query参数**:

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| count | int | 否 | 复习单词数量，默认25 |
| grade | int | 否 | 按年级筛选 |
| word_ids | string | 否 | 指定单词ID，多个用逗号分隔 |

**响应**:
```json
{
  "session_id": 1,
  "questions": [
    {
      "word_id": 1,
      "english": "apple",
      "chinese": "苹果",
      "word_length": 5,
      "options": ["香蕉", "苹果", "橙子", "葡萄"]
    }
  ],
  "total": 25
}
```

#### 4.4.9 提交复习结果

```
POST /api/words/review/submit
```

**请求体**:
```json
{
  "results": [
    {
      "word_id": 1,
      "is_correct": true,
      "user_answer": "apple",
      "review_type": 1
    }
  ],
  "duration": 120
}
```

**响应**:
```json
{
  "total": 25,
  "correct": 20,
  "error": 5,
  "accuracy": 80.0
}
```

#### 4.4.10 获取错词列表

```
GET /api/words/errors
```

**说明**: 返回正确率低于60%的单词

#### 4.4.11 生成打印PDF

```
POST /api/words/print-pdf
```

**Query参数**:
- `count`: 单词数量，默认25
- `grade`: 年级筛选

**响应**:
```json
{
  "pdf_url": "/uploads/practice_sets/xxx.pdf"
}
```

### 4.4 相似题模块

#### 4.4.1 生成相似题

```
POST /api/questions/{question_id}/similar
```

**说明**: 调用LLM API基于原题生成一道相似练习题

**响应**:
```json
{
  "id": 1,
  "source_question_id": 4,
  "similar_text": "生成的相似题目",
  "similar_answer": "相似题答案",
  "similarity_score": 0.85,
  "generated_at": "2026-03-28T13:33:17"
}
```

**LLM配置**:
- 模型: `claude-sonnet-4-20250514` (可配置)
- API Key: 从 `config/llm.json` 或环境变量读取
- Base URL: 可配置（用于代理）
- Thinking块: 禁用 (`thinking={"type": "disabled"}`)

### 4.5 学科管理

#### 4.5.1 获取学科列表

```
GET /api/subjects
```

**响应**:
```json
[
  {"id": 1, "name": "数学"},
  {"id": 2, "name": "英语"}
]
```

#### 4.5.2 创建学科

```
POST /api/subjects
```

**请求体**: `{"name": "物理"}`

#### 4.5.3 删除学科（软删除）

```
DELETE /api/subjects/{subject_id}
```

### 4.6 标签管理

#### 4.6.1 获取标签列表

```
GET /api/tags
```

**响应**:
```json
[
  {"id": 1, "name": "易错", "color": "#FF6B6B"},
  {"id": 2, "name": "难题", "color": "#4ECDC4"}
]
```

#### 4.6.2 创建标签

```
POST /api/tags
```

**请求体**: `{"name": "易错", "color": "#FF6B6B"}`

#### 4.6.3 删除标签（软删除）

```
DELETE /api/tags/{tag_id}
```

### 4.7 错题本管理

#### 4.7.1 获取错题本列表

```
GET /api/error-books
```

**响应**:
```json
[
  {
    "id": 1,
    "name": "五下数学错题本",
    "subject_id": 1,
    "subject_name": "数学",
    "description": "五年级下学期",
    "cover_image": "2026/03/cover.png",
    "question_count": 10,
    "created_at": "2026-03-01"
  }
]
```

#### 4.7.2 创建错题本

```
POST /api/error-books
```

**请求体**:
```json
{
  "name": "五下数学错题本",
  "subject_id": 1,
  "description": "五年级下学期"
}
```

#### 4.7.3 更新错题本

```
PUT /api/error-books/{error_book_id}
```

#### 4.7.4 删除错题本（软删除）

```
DELETE /api/error-books/{error_book_id}
```

### 4.8 知识点管理

#### 4.8.1 获取知识点列表

```
GET /api/knowledge-points?subject_id=1&grade=5&semester=2
```

**Query参数**:
- `subject_id`: 学科ID
- `grade`: 年级
- `semester`: 学期

**响应**:
```json
[
  {
    "id": 1,
    "name": "小数除法",
    "subject_id": 1,
    "subject_name": "数学",
    "grade": 5,
    "semester": 2,
    "created_at": "2026-03-01"
  }
]
```

#### 4.8.2 创建知识点

```
POST /api/knowledge-points
```

**请求体**:
```json
{
  "name": "小数除法",
  "subject_id": 1,
  "grade": 5,
  "semester": 2
}
```

#### 4.8.3 删除知识点（软删除）

```
DELETE /api/knowledge-points/{kp_id}
```

### 4.9 统计分析

#### 4.9.1 获取统计概览

```
GET /api/stats/summary
```

**响应**:
```json
{
  "total_questions": 100,
  "total_subjects": 3,
  "total_error_books": 5,
  "difficulty_distribution": {"1": 5, "2": 15, "3": 40, "4": 25, "5": 15},
  "error_type_distribution": {"计算": 40, "概念": 30, "审题": 20, "其他": 10},
  "by_subject": [
    {
      "subject_id": 1,
      "subject_name": "数学",
      "question_count": 60,
      "error_type_counts": {"计算": 30, "概念": 20, "审题": 10},
      "difficulty_distribution": {"1": 3, "2": 10, "3": 25, "4": 15, "5": 7}
    }
  ],
  "by_grade": [
    {
      "grade": 5,
      "question_count": 40,
      "difficulty_distribution": {"1": 2, "2": 8, "3": 15, "4": 10, "5": 5}
    }
  ],
  "by_semester": [
    {
      "semester": 1,
      "question_count": 45,
      "difficulty_distribution": {"1": 2, "2": 7, "3": 18, "4": 12, "5": 6}
    }
  ]
}
```

**统计说明**:
- 所有统计仅包含 `deleted=False` 的记录
- 难度分布: key为难度等级(1-5)，value为该难度错题数量
- 错误类型分布: key为错误类型，value为该类型错题数量

### 4.10 配置管理

#### 4.10.1 获取LLM配置

```
GET /api/config/llm
```

**响应**:
```json
{
  "api_key": "sk-xxx",
  "base_url": "https://api.minimax.chat",
  "model": "MiniMax-Text-01"
}
```

#### 4.10.2 更新LLM配置

```
PUT /api/config/llm
```

**请求体**:
```json
{
  "api_key": "sk-xxx",
  "base_url": "https://api.minimax.chat",
  "model": "MiniMax-Text-01"
}
```

### 4.11 练习集管理

#### 4.11.1 获取练习集列表

```
GET /api/practice-sets
```

**Query参数**:

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| skip | int | 否 | 跳过记录数，默认0 |
| limit | int | 否 | 返回数量，默认20 |
| subject_id | int | 否 | 学科ID |
| reviewed | bool | 否 | 复习状态 |
| source_type | string | 否 | 来源类型：question/word |
| start_date | string | 否 | 创建时间起（YYYY-MM-DD） |
| end_date | string | 否 | 创建时间止（YYYY-MM-DD） |

**响应示例**:
```json
{
  "total": 10,
  "items": [
    {
      "id": 1,
      "name": "练习集名称",
      "subject_id": 1,
      "subject_name": "数学",
      "source_type": "question",
      "question_type": "original",
      "total_questions": 10,
      "reviewed": false,
      "review_count": 0,
      "created_at": "2026-04-01T10:00:00"
    }
  ]
}
```

#### 4.11.2 获取练习集详情

```
GET /api/practice-sets/{practice_set_id}
```

**响应示例**:
```json
{
  "id": 1,
  "name": "练习集名称",
  "notes": "备注",
  "subject_id": 1,
  "subject_name": "数学",
  "source_type": "word",
  "question_type": "original",
  "total_questions": 10,
  "reviewed": true,
  "review_count": 1,
  "last_reviewed_at": "2026-04-01T12:00:00",
  "review_images": null,
  "created_at": "2026-04-01T10:00:00",
  "questions": [
    {
      "id": 1,
      "question_id": 10,
      "question_text": "apple",
      "answer": "苹果",
      "phonetic": null,
      "is_correct": true,
      "user_answer": "apple",
      "tags": [{"id": 1, "name": "水果"}]
    }
  ],
  "word_review_stats": {
    "total_count": 10,
    "correct_count": 8,
    "accuracy": 80.0,
    "duration": 120,
    "reviewed_at": "2026-04-01T12:00:00"
  }
}
```

#### 4.11.3 创建练习集

```
POST /api/practice-sets
```

**请求体**:
```json
{
  "name": "练习集名称",
  "question_ids": [1, 2, 3],
  "source_type": "question",
  "question_type": "original"
}
```

#### 4.11.4 标记已复习

```
POST /api/practice-sets/{practice_set_id}/mark-reviewed
```

**Form参数**:
- `images`: 可选，复习完成图片的JSON字符串

#### 4.11.5 批量删除

```
POST /api/practice-sets/batch-delete
```

**请求体**:
```json
{
  "ids": [1, 2, 3]
}
```

---

## 五、前端页面

### 5.1 页面列表

| 路径 | 页面 | 说明 |
|------|------|------|
| / | Home | 首页/仪表盘 |
| /questions | Questions | 错题列表 |
| /upload | Upload | 上传新错题 |
| /stats | Stats | 统计分析 |
| /management | Management | 管理中心 |
| /settings | Settings | 系统设置 |
| /words | Words | 单词本 |
| /practice-sets | PracticeSets | 练习集 |

### 5.2 错题列表页 (Questions.vue)

**功能特性**:
- 错题表格展示（支持分页）
- 多条件筛选：学科、难度、年級、学期、关键词
- 图片预览（支持多图画廊）
- 操作按钮：查看详情、编辑、生成相似题、删除
- 相似题列表展示

**组件结构**:
```
Questions.vue
├── el-card (卡片容器)
│   ├── card-header (标题栏)
│   │   └── el-button (新增错题)
│   ├── filters (筛选区域)
│   │   ├── el-select (学科筛选)
│   │   ├── el-select (难度筛选)
│   │   ├── el-select (年级筛选)
│   │   ├── el-select (学期筛选)
│   │   └── el-input (关键词搜索)
│   ├── el-table (错题列表)
│   │   └── 操作列: 查看/编辑/相似题/删除
│   └── el-pagination (分页)
├── el-dialog (详情弹窗)
│   ├── 原图展示
│   ├── 题目/答案/解析
│   ├── 难度/年级/学期
│   ├── 错误类型/知识点
│   └── 相似题列表
└── el-dialog (编辑弹窗)
    └── el-form (编辑表单)
```

**年级选项** (中文标签):
```javascript
[
  { label: '一年级', value: 1 },
  { label: '二年级', value: 2 },
  { label: '三年级', value: 3 },
  { label: '四年级', value: 4 },
  { label: '五年级', value: 5 },
  { label: '六年级', value: 6 },
  { label: '初一', value: 7 },
  { label: '初二', value: 8 },
  { label: '初三', value: 9 },
  { label: '高一', value: 10 },
  { label: '高二', value: 11 },
  { label: '高三', value: 12 }
]
```

**难度标签颜色**:
```javascript
const types = ['', 'success', 'warning', 'warning', 'danger', 'danger']
// 1=success(绿), 2-3=warning(橙), 4-5=danger(红)
```

### 5.3 上传页 (Upload.vue)

**功能特性**:
- 拖拽/点击上传图片
- 批量上传多张图片
- OCR识别结果展示
- 图片预览
- 保存后显示预览

**组件结构**:
```
Upload.vue
├── el-card (上传卡片)
│   ├── el-upload (上传组件)
│   │   ├── drag=true (拖拽模式)
│   │   ├── multiple=true (多文件)
│   │   └── accept="image/*"
│   └── 上传提示文字
├── OCR结果展示区
│   ├── 图片缩略图
│   └── 识别文本
├── 错题信息表单
│   ├── el-select (选择错题本)
│   ├── el-select (选择学科)
│   ├── el-select (年级)
│   ├── el-select (学期)
│   ├── el-rate (难度评分)
│   ├── el-select (错误类型)
│   ├── el-input (知识点)
│   └── el-select (标签多选)
└── 操作按钮
    └── 保存 / 重置
```

### 5.4 统计分析页 (Stats.vue)

**功能特性**:
- 总览卡片：总错题数、总学科数、总错题本数
- 难度分布图表
- 错误类型分布
- 按学科/年级/学期统计

### 5.5 管理中心 (Management.vue)

**功能特性**:
- Tabs切换：学科/标签/错题类型/知识点/错题本
- CRUD操作：创建、编辑、删除
- 软删除处理

**Tab页签**:
1. **学科管理**: 学科列表、添加学科
2. **标签管理**: 标签列表(带颜色)、添加标签
3. **错题类型**: 预设类型（计算/概念/审题/其他）
4. **知识点管理**: 知识点列表（按学科+年级+学期筛选）
5. **错题本管理**: 错题本列表

### 5.6 设置页 (Settings.vue)

**功能特性**:
- LLM API配置（API Key、Base URL、模型选择）
- 保存配置到 `config/llm.json`

### 5.7 单词本页面 (Words.vue)

**功能特性**:
- 单词列表展示（支持分页、筛选，默认每页20条）
- 多条件筛选：关键词、年级、学期、标签
- 单词CRUD管理（创建、编辑、删除）
- 多种导入方式：文本粘贴、文件上传、图片OCR识别
- 在线复习：默写英文、选择题两种题型
- 多选复习：支持勾选单词后进行专项复习
- PDF打印：生成单词默写PDF
- 复习统计：正确率、复习次数、错词记录
- 复习计时：实时显示用时，结果页面显示总用时
- 复习背景虚化：弹窗背景模糊效果

**导入方式**:
1. **文本粘贴**: 每行一个单词，格式：英文 中文（用空格分隔）
2. **文件上传**: 支持 .txt 或 .csv 文件
3. **图片识别**: 上传单词图片，自动OCR识别提取文字

**复习题型**:
| 题型 | 说明 |
|------|------|
| 默写英文 | 显示中文和字母提示，输入英文答案 |
| 选择中文 | 显示英文，从4个中文选项中选择正确答案 |

**复习流程**:
1. 选择复习数量和年级筛选（可选）
2. 系统随机抽取单词（或使用多选的单词）
3. 逐题展示，计时开始
4. 用户作答，实时显示用时
5. 记录正确/错误
6. 显示复习结果统计（含总用时）

### 5.8 练习集页面 (PracticeSets.vue)

**功能特性**:
- 练习集CRUD管理
- 从错题列表勾选题目加入练习集
- 批量生成相似题
- 生成PDF打印（支持原题/相似题）
- 练习集列表表格展示
- 多条件筛选：学科、复习状态、创建时间范围
- 单词练习集详情页展示单词题目列表
- 单词复习统计：总单词数、正确数、用时等
- 复习完成上传图片功能

**练习集列表筛选**:
| 字段 | 类型 | 说明 |
|------|------|------|
| 学科 | el-select | 按学科筛选 |
| 复习状态 | el-select | 已复习/未复习 |
| 创建时间 | el-date-picker | 日期范围筛选 |

**练习集详情页标签页**:
1. **详情**: 练习集基本信息、统计、复习图片
2. **单词练习**: 单词复习题目列表（含正确/错误状态、用户答案）

---

## 六、年级与学期说明

### 6.1 年级编码

| value | label | 说明 |
|-------|-------|------|
| 1 | 一年级 | 小学一年级 |
| 2 | 二年级 | 小学二年级 |
| 3 | 三年级 | 小学三年级 |
| 4 | 四年级 | 小学四年级 |
| 5 | 五年级 | 小学五年级 |
| 6 | 六年级 | 小学六年级 |
| 7 | 初一 | 初一（七年级） |
| 8 | 初二 | 初二（八年级） |
| 9 | 初三 | 初三（九年级） |
| 10 | 高一 | 高一（十年级） |
| 11 | 高二 | 高二（十一年级） |
| 12 | 高三 | 高三（十二年级） |

### 6.2 学期编码

| value | label | 说明 |
|-------|-------|------|
| 1 | 上学期 | 第一学期 |
| 2 | 下学期 | 第二学期 |

---

## 七、软删除机制

### 7.1 实现方式

所有数据表均包含 `deleted` 布尔字段：
```sql
ALTER TABLE xxx ADD COLUMN deleted BOOLEAN DEFAULT FALSE NOT NULL;
```

### 7.2 查询过滤

所有列表查询API默认过滤 `deleted = FALSE` 的记录：
```python
query = db.query(Question).filter(Question.deleted == False)
```

### 7.3 删除操作

删除操作执行软删除（设置 `deleted = True`），而非物理删除：
```python
question.deleted = True
db.commit()
```

---

## 八、配置管理

### 8.1 LLM配置文件

**路径**: `backend/config/llm.json`

**结构**:
```json
{
  "api_key": "your-api-key",
  "base_url": "https://api.minimax.chat",
  "model": "MiniMax-Text-01"
}
```

### 8.2 系统配置

**路径**: `backend/.env`

**变量**:
```
ANTHROPIC_API_KEY=xxx
DATABASE_URL=mysql://user:pass@localhost:3306/easyfix
UPLOAD_DIR=./uploads
MAX_UPLOAD_SIZE=10485760  # 10MB
```

---

## 九、激励系统

### 9.1 功能概述

激励系统通过积分、成就、奖励三大模块，激励用户持续使用应用学习。

### 9.2 积分规则

| 行为代码 | 行为名称 | 积分值 | 说明 |
|---------|---------|-------|------|
| upload_question | 上传错题 | 10 | 每上传一道错题 |
| review_practice_set | 复习练习集 | 5 | 每次完成练习集复习 |
| generate_similar | 生成相似题 | 3 | 每生成一道相似题 |
| review_word | 背单词 | 2 | 每次完成单词复习 |
| create_practice_set | 创建练习集 | 5 | 每创建一个练习集 |
| daily_login | 每日登录 | 1 | 每日签到 |
| continuous_7day | 连续7天学习 | 50 | 连续学习7天达成 |

### 9.3 成就体系

#### 成就列表

| 成就代码 | 名称 | 级别 | 触发条件 | 奖励积分 |
|---------|------|------|---------|---------|
| first_upload | 首次上传 | 1 | 上传1道错题 | 20 |
| upload_master | 上传达人 | 1/2/3 | 上传10/50/200道错题 | 50/100/200 |
| review_master | 练习高手 | 1/2/3 | 复习10/50/200次练习集 | 30/80/150 |
| word_master | 单词达人 | 1/2/3 | 背50/200/500个单词 | 50/100/200 |
| similar_master | 相似题专家 | 1/2/3 | 生成20/100/300道相似题 | 60/120/250 |

#### 成就进度计算

| 触发行为 | 数据来源 |
|---------|---------|
| upload_question | Question 表计数 |
| review_practice_set | PracticeSet.review_count 累计 |
| generate_similar | SimilarQuestion 表计数 |
| review_word | Word.review_count 累计 |
| create_practice_set | PracticeSet 表计数 |

### 9.4 数据库表结构

#### 9.4.1 行为配置表 (star_action)

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | INTEGER | PK, AUTO | 主键 |
| code | VARCHAR(50) | NOT NULL, UNIQUE | 行为代码 |
| name | VARCHAR(100) | NOT NULL | 行为名称 |
| star_value | INTEGER | NOT NULL | 积分值 |
| icon | VARCHAR(500) | | 图标 |
| enabled | BOOLEAN | DEFAULT TRUE | 是否启用 |
| is_custom | BOOLEAN | DEFAULT FALSE | 是否自定义 |
| deleted | BOOLEAN | DEFAULT FALSE | 软删除 |
| created_at | DATETIME | DEFAULT NOW | 创建时间 |

#### 9.4.2 积分余额表 (star_balance)

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | INTEGER | PK, AUTO | 主键 |
| user_id | INTEGER | DEFAULT 1 | 用户ID |
| balance | INTEGER | DEFAULT 0 | 积分余额 |
| updated_at | DATETIME | | 更新时间 |

#### 9.4.3 积分记录表 (star_record)

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | INTEGER | PK, AUTO | 主键 |
| user_id | INTEGER | DEFAULT 1 | 用户ID |
| action_code | VARCHAR(50) | NOT NULL | 行为代码 |
| star_delta | INTEGER | NOT NULL | 积分变动 |
| balance_after | INTEGER | NOT NULL | 变动后余额 |
| reason | VARCHAR(200) | | 原因说明 |
| created_at | DATETIME | DEFAULT NOW | 创建时间 |

#### 9.4.4 成就定义表 (achievement)

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | INTEGER | PK, AUTO | 主键 |
| code | VARCHAR(50) | NOT NULL | 成就代码 |
| name | VARCHAR(100) | NOT NULL | 成就名称 |
| level | INTEGER | DEFAULT 1 | 级别 |
| description | VARCHAR(500) | | 描述 |
| icon | VARCHAR(500) | | 图标 |
| trigger_action | VARCHAR(50) | NOT NULL | 触发行为代码 |
| trigger_count | INTEGER | NOT NULL | 触发计数 |
| reward_stars | INTEGER | DEFAULT 0 | 奖励积分 |
| is_preset | BOOLEAN | DEFAULT FALSE | 是否预设 |
| is_active | BOOLEAN | DEFAULT TRUE | 是否启用 |
| deleted | BOOLEAN | DEFAULT FALSE | 软删除 |
| created_at | DATETIME | DEFAULT NOW | 创建时间 |

**唯一索引**: `(code, level)`

#### 9.4.5 成就进度表 (achievement_progress)

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | INTEGER | PK, AUTO | 主键 |
| user_id | INTEGER | DEFAULT 1 | 用户ID |
| achievement_id | INTEGER | FK → achievement.id | 成就ID |
| current_count | INTEGER | DEFAULT 0 | 当前进度 |
| is_unlocked | BOOLEAN | DEFAULT FALSE | 是否解锁 |
| unlocked_at | DATETIME | | 解锁时间 |

**唯一索引**: `(user_id, achievement_id)`

#### 9.4.6 奖励表 (reward)

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | INTEGER | PK, AUTO | 主键 |
| name | VARCHAR(100) | NOT NULL | 奖励名称 |
| description | TEXT | | 描述 |
| icon | VARCHAR(500) | | 图标 |
| cost_stars | INTEGER | NOT NULL | 所需积分 |
| total_stock | INTEGER | DEFAULT -1 | 总库存（-1无限） |
| remaining_stock | INTEGER | DEFAULT -1 | 剩余库存 |
| is_active | BOOLEAN | DEFAULT TRUE | 是否上架 |
| deleted | BOOLEAN | DEFAULT FALSE | 软删除 |
| created_at | DATETIME | DEFAULT NOW | 创建时间 |

#### 9.4.7 奖励兑换记录表 (redemption)

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | INTEGER | PK, AUTO | 主键 |
| user_id | INTEGER | DEFAULT 1 | 用户ID |
| reward_id | INTEGER | FK → reward.id | 奖励ID |
| star_cost | INTEGER | NOT NULL | 消耗积分 |
| redeemed_at | DATETIME | DEFAULT NOW | 兑换时间 |

### 9.5 API 接口

#### 积分模块

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /api/stars/balance | 获取积分余额 |
| GET | /api/stars/records | 获取积分记录列表 |
| GET | /api/stars/actions | 获取行为配置列表 |
| POST | /api/stars/actions | 创建自定义行为 |
| PUT | /api/stars/actions/{id} | 更新行为配置 |
| DELETE | /api/stars/actions/{id} | 删除行为配置 |

#### 成就模块

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /api/achievements | 获取成就列表 |
| GET | /api/achievements/progress | 获取成就进度 |
| POST | /api/achievements | 创建自定义成就 |
| PUT | /api/achievements/{id} | 更新成就 |
| DELETE | /api/achievements/{id} | 删除成就 |

#### 奖励模块

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /api/rewards | 获取奖励列表 |
| POST | /api/rewards | 创建奖励 |
| PUT | /api/rewards/{id} | 更新奖励 |
| DELETE | /api/rewards/{id} | 删除奖励 |
| POST | /api/rewards/{id}/redeem | 兑换奖励 |
| GET | /api/rewards/redemptions | 获取兑换记录 |

#### 概览与触发

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /api/motivation/overview | 获取激励概览 |
| POST | /api/motivation/trigger/{action_code} | 触发积分行为（内部调用） |

### 9.6 前端页面

#### 激励中心页面 (Motivation.vue)

- **积分成就 Tab**：展示积分余额、今日获取、成就徽章墙
- **奖励商城 Tab**：展示可用奖励列表，支持兑换
- **积分明细弹窗**：展示积分获取/消耗历史记录

---

## 十、版本历史

### v1.0.8 (2026-04-03)

**新增功能**:
- 激励中心页面（积分成就、奖励商城）
- 激励系统后端 API
- 激励数据初始化服务

**改进**:
- 前端从后端 API 获取实时数据
- 成就数据根据练习集实际数据计算

**修复**:
- element-plus/icons-vue 图标名称错误

**数据库变更**:
- 新增 star_action、star_balance、star_record 表
- 新增 achievement、achievement_progress 表
- 新增 reward、redemption 表

### v1.0.7 (2026-04-02)

**新增功能**:
- 练习集详情页新增"单词练习"标签页
- 练习集列表新增日期筛选功能

**改进**:
- 练习集列表从卡片布局改为表格布局
- 练习集详情页默认显示详情标签页
- 移除详情页"最近复习"字段
- Element Plus 语言设置为中文

**修复**:
- 单词练习集 API 未返回 `is_correct`、`user_answer`、`tags` 等字段
- 历史单词复习练习集的学科错误（数学→英语）

**数据库变更**:
- practice_set 表新增 review_images 字段

### v1.0.6 (2026-03-31)

**新增功能**:
- 单词复习计时功能（实时用时显示）
- 复习背景虚化效果

**改进**:
- 单词复习布局优化（提示框与输入框分行显示）
- 单词复习学科设置为"英语"学科
- 单词表默认每页展示20条

**修复**:
- 历史单词复习练习集的学科错误（已修复为"英语"）
- 单词复习结果duration参数未传递问题

### v1.0.3 (2026-03-28)

**新增功能**:
- 错题多选操作（勾选题目）
- 练习集管理（创建、查看、删除）
- 批量生成相似题
- 打印练习集PDF（原题/相似题可选）
- 复习记录与复习次数追踪
- 练习集页面（PracticeSets.vue）

**数据库变更**:
- Question表新增 `review_count`（复习次数）、`last_reviewed_at`（最后复习时间）字段
- 新增 `practice_set` 表（练习集）
- 新增 `practice_set_question` 表（练习集-题目关联）

**新增API**:
| 方法 | 路径 | 说明 |
|------|------|------|
| POST | /api/practice-sets | 创建练习集 |
| GET | /api/practice-sets | 获取练习集列表 |
| GET | /api/practice-sets/{id} | 获取练习集详情 |
| POST | /api/practice-sets/{id}/generate-pdf | 生成PDF |
| POST | /api/practice-sets/{id}/mark-reviewed | 标记已复习 |
| DELETE | /api/practice-sets/{id} | 删除练习集 |
| POST | /api/questions/batch-similar | 批量生成相似题 |

**PDF生成**:
- 使用weasyprint库生成PDF
- A4纸张，保留空白答题区域
- 页眉显示练习集名称和日期

**前端变更**:
- Questions.vue新增多选列和批量操作栏
- 新增PracticeSets.vue练习集管理页面
- 导航菜单新增"练习集"入口

### v1.0.2 (2026-03-28)

**修复**:
- LLM相似题返回空内容（MiniMax思考块问题）
- 添加 `thinking={"type": "disabled"}` 禁用MiniMax思考块
- 相似题生成功能对数学题目正常工作

### v1.0.1 (2026-03-28)

**新增功能**:
- 错题支持年级和学期（一年级至高三年级，上学期/下学期）
- 标签管理与题目关联
- 按年级和学期统计
- 管理中心（错题本、学科、标签、错误类型、知识点）
- 上传后预览
- 原图展示
- 错题编辑功能

**改进**:
- 年级下拉框显示中文标签
- 搜索框宽度调整
- 题目文本框高度增加

**修复**:
- 学科下拉框数据加载问题
- 数据库缺少grade/semester列
- 图片上传目录路径问题

### v1.0.0 (2026-03-28)

**新增功能**:
- 错题上传与OCR识别（PaddleOCR）
- 错题CRUD管理（支持软删除）
- 错题多条件筛选与分页
- 相似题目AI生成（Anthropic/MiniMax API）
- 多维度统计分析
- 学科、标签、错题本、知识点管理
- 管理中心（Management页面）
- 年级中文标签（一年级至高三）
- 图片上传至 `uploads/` 目录
- LLM配置持久化（config/llm.json）

**技术特性**:
- Anthropic SDK 集成
- 禁用LLM思考块（防止返回空内容）
- 软删除机制全表覆盖
- 按年月分目录存储图片

**修复问题**:
- 学科下拉框数据加载问题
- 图片路径 `/uploads/` 前缀问题
- LLM返回内容为空（思考块）问题

---

## 十、待办事项

- [ ] 批量导入错题功能
- [ ] 错题复习提醒
- [ ] 导出功能（PDF/Excel）
- [ ] 多语言支持
- [ ] 用户认证与权限管理
- [ ] 数据备份与恢复

---

## 附录

### A. 错误类型定义

| 类型 | 说明 |
|------|------|
| 计算 | 计算错误、粗心大意 |
| 概念 | 概念理解不清 |
| 审题 | 审题不仔细、理解偏差 |
| 其他 | 其他类型错误 |

### B. 初始标签

| 名称 | 颜色 |
|------|------|
| 易错 | #FF6B6B |
| 难题 | #4ECDC4 |
| 重点 | #45B7D1 |
| 技巧 | #96CEB4 |

### C. API状态码

| 状态码 | 说明 |
|--------|------|
| 200 | 成功 |
| 201 | 创建成功 |
| 204 | 删除成功（无内容返回） |
| 400 | 请求参数错误 |
| 404 | 资源不存在 |
| 500 | 服务器内部错误 |
