# CLAUDE.md

本文件为 Claude Code 在本仓库工作时提供指引。实操细则见 `AGENTS.md`，部署、备份与发布记录见 `docs/cloudflare-migration-status.md`。

## 项目概述

EasyFix 是面向学生的错题整理应用：错题录入与归档、两级知识点、单词与词组默写、阅读理解、练习集与 PDF 打印、统计分析、学习报告、激励系统，以及基于 LLM 的相似题与报告生成。

**正式环境自 2026-11-09 起运行在 Cloudflare 上**，入口 https://easyfix-bl2.pages.dev ，需访问密码登录。数据在 D1，附件在私有 R2。

## 录入错题

- 把孩子的作业或卷子照片录入错题，只通过 `tools/easyfix-intake/` 的技能和小工具提交，规范见该目录的 `SKILL.md`；不直接写数据库、不写一次性导入脚本。
- 安装后技能位于用户级目录 `~/.claude/skills/easyfix-intake/`（Claude）和 `~/.agents/skills/easyfix-intake/`（Codex 等），接口地址与访问口令在 `~/.easyfix/intake.json`。

## 开发者背景与协作偏好

- 开发者是编程初学者，偏好简洁易懂的代码和详细注释。
- 无特殊要求时，交流、注释和文档均使用中文。

## 架构概览

| 组件 | 位置 | 说明 |
|------|------|------|
| 前端 | `frontend/` | Vue 3 + Vite + Element Plus + Pinia + ECharts + KaTeX，构建后发布到 Cloudflare Pages（项目 `easyfix`） |
| Pages 网关 | `cloudflare/pages/_worker.js` | 校验会话、提供静态资源、从 R2 直读 `/uploads/` 附件，`/api/` 请求经服务绑定转给后端 Worker |
| 后端 Worker | `cloudflare/src/` | Python Worker `easyfix`：FastAPI + 异步 D1，不开放 workers.dev |
| PDF Worker | `cloudflare/pdf/` | 内部 Worker `easyfix-pdf`：KaTeX 校验 + Browser Run 生成 PDF，无公开路由 |
| 数据库 | D1 `easyfix` | 结构变更只通过 `cloudflare/migrations/` 追加 |
| 附件 | 私有 R2 `easyfix` | 原图、PDF、单词音频 |
| 共享代码 | `shared/math-text.mjs` | 前端与 PDF 共用的公式文本处理 |
| 旧本地后端 | `backend/app/` | 切换前的 FastAPI + SQLAlchemy 版本，仅保留作参考，**不是生产代码** |

`backend/scripts/` 里仍有正在使用的云端工具（前端构建、密钥准备、D1 导出等），其余多为切换前的历史脚本。

### 后端 Worker 模块（`cloudflare/src/`）

| 模块 | 用途 |
|------|------|
| `main.py` | FastAPI 入口，注册路由；`/health`、`/api/subjects`、`/api/upload/file` |
| `auth.py` | 密码登录、签名会话 Cookie、Agent Bearer 令牌、维护写开关 |
| `database.py` / `cache.py` | D1 访问封装与统计缓存 |
| `questions.py` / `similar.py` | 错题 CRUD、批量入库、相似题生成 |
| `knowledge.py` / `knowledge_model.py` / `knowledge_stats.py` | 两级知识点目录、关联与统计 |
| `catalog.py` | 学科、标签、错题本、错误类型等目录 |
| `words.py` / `review.py` / `word_focus.py` / `phrase_focus.py` | 单词本、复习与默写、词组重点标注 |
| `readings.py` | 阅读短文与题目 |
| `practices.py` / `pdf.py` | 练习集、批改、PDF 生成与复用 |
| `targeted.py` / `targeted_model.py` | 考点卷：状态、选题预览、创建、相似题准备与换题；选题与毕业规则的纯函数 |
| `grading_scan.py` / `grading_model.py` | 批改识别预批：逐页读卷面照片、调一次模型按题号比对；比对提示词与输出清洗的纯函数（不写库） |
| `analytics.py` / `reports.py` | 统计分析、学习报告 |
| `motivation.py` | 星星、奖励、成就 |
| `media.py` / `audio_index.py` | 上传、单词音频、打印 |
| `settings.py` / `prompts.py` / `provenance.py` | 应用与 LLM 配置、提示词、阅读来源 |

完整接口清单见 `docs/cloudflare-api-checklist.md`。

### 前端结构（`frontend/src/`）

| 目录/文件 | 用途 |
|-----------|------|
| `main.js` / `App.vue` | 应用入口；桌面分组侧栏与手机底部导航 |
| `api/` | Axios 封装（`http.js` 带 GET 去重与短时缓存） |
| `views/` | 页面组件 |
| `composables/` | 默写判分（`dictation.js`）、知识点配色 |
| `stores/appConfig.js` | 默认年级/学期 |
| `router/index.js` | 路由配置 |

| 路径 | 页面 |
|------|------|
| `/` | 首页 |
| `/questions` | 错题列表 |
| `/upload` | 录入错题 |
| `/stats`、`/learning-analysis` | 统计与学习分析 |
| `/practice-sets` | 练习集 |
| `/targeted-paper` | 考点卷：出卷页（选科目、题量、分法，预览后生成） |
| `/grade`、`/grade/:id` | 错题练习卷批改（电脑、手机共用）：待批改列表与批改页（拍照 → 识别预批 → 复核） |
| `/words` | 单词本 |
| `/reading`、`/reading-test/:id` | 阅读理解 |
| `/learning-reports` | 学习报告 |
| `/motivation` | 激励 |
| `/management`、`/settings` | 管理中心、配置 |

## 常用命令

均在仓库根目录执行。Wrangler 固定 4.158.0，先执行一次 `npm install --prefix cloudflare`。

```bash
# 测试
python cloudflare/scripts/phrase_focus_test.py
python cloudflare/scripts/knowledge_invariants_test.py
node --test frontend/src/composables/dictation.test.mjs

# 后端：语法检查后部署 Worker
python -m compileall -q cloudflare/src
node cloudflare/tools/cli.cjs deploy --config cloudflare/wrangler.jsonc

# 前端：构建到 tmp/cloudflare-pages-build
python backend/scripts/prepare_cloudflare_frontend.py
```

Pages 发布、D1 迁移、依赖变更、密钥与回滚的完整命令见 `docs/cloudflare-migration-status.md` 的"日常部署"与"备份与恢复"。

## 必须遵守

- **生产数据只在 D1 / R2**。旧 PostgreSQL 已冻结只读，不要用 `backend/` 下的旧导入脚本或 `.mcp.json` 里的 MySQL 服务写生产数据。
- **禁止重新运行 `sync_cloudflare_d1.py`** 等旧快照同步工具，会覆盖云端新数据。
- 数据库变更只追加 `cloudflare/migrations/` 迁移，执行前先导出 D1 备份。
- 所有表保留 `deleted` 字段，只做软删除；查询必须过滤已删除记录。
- 保持 Workers 免费计划：统计用 SQL 聚合，避免逐记录查询、重复 LLM 调用和重复生成 PDF。
- 访问密码、会话密钥、Agent 令牌只存在 Worker / Pages 密钥和被忽略的 `tmp/cloudflare-config/` 中，不写入仓库或文档。
- `tmp/`、`backups/` 含学生数据与密钥，不得提交或发布。

## 代码规范

- 变量与函数 `snake_case`，函数名用动词或动词短语；类 `PascalCase`；常量全大写下划线。
- 每个函数前写中文文档字符串，复杂逻辑加行内注释。
- 前端使用 Vue 3 Composition API + `<script setup>`，UI 组件用 Element Plus。
- 数学内容使用带边界的 LaTeX：行内 `\(...\)`，独立公式 `\[...\]`，细则见 `AGENTS.md`。
