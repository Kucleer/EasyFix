# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

EasyFix 是一款面向学生的本地错题整理应用，主要功能包括：错题图片上传与OCR识别、错题归档整理、多维度统计分析、以及基于LLM的相似题目智能推荐。

## 开发命令

### 后端 (Python FastAPI)

```bash
cd backend
pip install -r requirements.txt
python -m app.main        # 启动后端服务 (http://localhost:8000)
# 或使用 uvicorn
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### 前端 (Vue 3 + Vite)

```bash
cd frontend
npm install
npm run dev       # 启动开发服务器 (http://localhost:5173，代理 /api 到 :8000)
npm run build     # 生产构建
```

### 数据库

- 默认使用 SQLite (`backend/easyfix.db`)
- 可通过 `backend/.env` 配置切换到 MySQL (设置 `DB_TYPE=mysql`)
- 表结构通过 `Base.metadata.create_all()` 在 `main.py` 中自动创建

## 架构概览

### 后端结构 (`backend/app/`)

| 目录/文件 | 用途 |
|-----------|------|
| `main.py` | FastAPI 入口，CORS 中间件，路由注册 |
| `config.py` | Pydantic 配置管理 |
| `database.py` | SQLAlchemy 数据库连接 |
| `models/` | ORM 模型（question, word, error_book, subject, tag, knowledge_point, practice_set, similar_question, operation_log） |
| `routers/` | API 路由处理（11个路由模块） |
| `schemas/` | Pydantic 请求/响应模型 |
| `services/` | 业务逻辑（ocr.py, llm.py, multimodal_ocr.py, pdf.py） |

### 前端结构 (`frontend/src/`)

| 目录/文件 | 用途 |
|-----------|------|
| `main.js` | Vue 3 应用入口 |
| `App.vue` | 根组件，包含导航菜单 |
| `api/` | Axios API 调用封装 |
| `views/` | 页面组件（Home, Questions, Upload, Stats, Management, Settings, Words, PracticeSets） |
| `router/index.js` | Vue Router 路由配置 |
| `stores/` | Pinia 状态管理（当前为空） |

### API 路由 (前缀 `/api`)

| 路由 | 用途 |
|------|------|
| `question` | 错题 CRUD |
| `upload` | 图片上传 + OCR |
| `stats` | 统计分析 |
| `similar` | LLM 相似题生成 |
| `word` | 单词本管理 + 复习 |
| `error_book` | 错题本管理 |
| `subject` | 学科管理 |
| `tag` | 标签管理 |
| `knowledge_point` | 知识点管理 |
| `practice_set` | 练习集管理 |
| `config` | LLM/OCR 配置 |

### 前端路由

| 路径 | 页面 |
|------|------|
| `/` | 首页 Dashboard |
| `/questions` | 错题列表 |
| `/upload` | 图片上传 |
| `/stats` | 统计页面 |
| `/management` | 管理中心 |
| `/settings` | 配置页面 |
| `/words` | 单词本 |
| `/practice-sets` | 练习集 |

## 代码规范

### 命名规范
- 变量：`snake_case`
- 函数：动词或动词短语
- 类：`PascalCase`
- 常量：`SNAKE_CASE`

### 数据库
- **所有表必须包含 `deleted` 字段用于软删除**

### 注释要求
- 每个函数前添加中文文档字符串
- 复杂逻辑添加行内注释

## 技术栈

| 层级 | 技术 |
|------|------|
| 前端 | Vue 3 + Element Plus + Vite + Pinia + Vue Router + ECharts |
| 后端 | Python FastAPI + SQLAlchemy + Pydantic |
| 数据库 | MySQL 8.0 / SQLite |
| OCR | PaddleOCR（本地）+ 多模态 LLM（OpenAI/Anthropic/MiniMax） |
| LLM | MiniMax / OpenAI / Anthropic |

## 配置说明

- 后端配置文件：`backend/config/` 目录下的 JSON 文件（llm.json, ocr.json）
- 环境变量：`backend/.env`
- 前端访问密码：`32167`（配置/管理中心）

## 存储结构

上传文件存储在 `backend/uploads/` 目录，按年月分目录：
```
uploads/images/{year}/{month}/{uuid}_{filename}
```
