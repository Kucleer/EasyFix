# AGENTS.md

## 项目简介

EasyFix：学生错题整理应用。Vue 3 + Vite 前端，Python FastAPI 后端，默认 SQLite，可切换 MySQL。

完整架构参考见 `CLAUDE.md`，本文件仅记录实操要点。

## 开发命令

项目无测试套件、无 linter、无 typecheck、无 CI、无 pre-commit hook。

```bash
# 后端（从仓库根目录执行）
cd backend
pip install -r requirements.txt
python -m app.main              # 启动服务，默认端口 :8000
# 或：uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# 前端（从仓库根目录执行）
cd frontend
npm install
npm run dev                     # 启动开发服务器 :5173，自动代理 /api 和 /uploads 到 :8000
npm run build                   # 生产构建，输出到 dist/
```

## 关键事实

- **建表方式**：后端启动时通过 `Base.metadata.create_all()` 自动建表，无迁移系统。修改表结构需删除 `backend/easyfix.db`（SQLite）或手动重建表（MySQL）。
- **后端路由数量**：`backend/app/main.py:46-60` 注册了 15 个路由。`CLAUDE.md` 写的 11 个已过时，缺少 `learning_report`、`motivation`、`error_type`、`reading`。
- **前端路由数量**：`frontend/src/router/index.js` 定义了 13 条路由。`CLAUDE.md` 写的 8 条已过时，缺少 `/reading`、`/reading-test/:id`、`/learning-reports`、`/motivation`、`/learning-analysis`。
- **软删除**：所有新模型必须包含 `deleted` 字段，禁止硬删除。
- **配置加载**：`backend/.env` 通过 pydantic-settings 加载，详见 `backend/app/config.py`。`backend/config/` 下的 `llm.json` 通过 `/api/config` 接口运行时覆盖。
- **文件上传路径**：`backend/uploads/images/{year}/{month}/{uuid}_{filename}`。Vite 开发服务器代理 `/uploads`，生产环境由 FastAPI 直接提供静态文件。
- **访问密码**：Settings/Management 页面密码为 `32167`，硬编码在 `backend/app/access_config.py`。
- **MCP 服务**：`.mcp.json` 配置了 MySQL（localhost:3306/easyfix）、browser、playwright。
- **导航菜单**：`frontend/src/App.vue` 桌面分组侧栏与手机底部导航，覆盖学习、练习、成长记录及管理配置。
- **前端 API 层**：`frontend/src/api/` 下有 5 个模块（question、word、learning_report、motivation、learning_analysis），其余 API 直接在组件内调用。

## 新增后端路由步骤

1. 在 `backend/app/routers/<name>.py` 创建路由
2. 在 `backend/app/main.py` 添加 import 并调用 `app.include_router()`
3. 在 `backend/app/routers/__init__.py` 添加导出
4. 在 `backend/app/schemas/` 创建 Pydantic 请求/响应模型
5. 在 `backend/app/models/` 创建或更新 ORM 模型，必须包含 `deleted` 字段

## 新增前端页面步骤

1. 在 `frontend/src/views/<Name>.vue` 创建页面组件
2. 在 `frontend/src/router/index.js` 添加路由配置
3. 在 `frontend/src/App.vue` 分组导航添加链接
4. API 调用写在 `frontend/src/api/` 下，使用 axios

## 代码规范

## 分支与发布流程

- 每次修改先创建独立的 `codex/` 分支，避免直接在主分支开发。
- 仅提交本次任务相关文件，保留工作区已有修改，不提交敏感数据及生成目录。
- 完成构建与必要验证后，将修改分支合并到 `main`，推送远端，再部署 Cloudflare。
- 前端使用 `python backend/scripts/prepare_cloudflare_frontend.py` 构建，按 `docs/cloudflare-migration-status.md` 的日常部署命令发布 Pages；后端有变更时才部署 Worker。
- 部署后核对正式入口与发布状态，记录提交及部署结果。

- 后端：全部 `snake_case`，函数前写中文文档字符串。
- 前端：Vue 3 Composition API + `<script setup>`，UI 组件用 Element Plus。
- 数据库：只做软删除，查询时必须加 `deleted=False` 过滤。
- 状态管理：应用默认年级/学期使用 `stores/appConfig`，其他业务状态主要在组件内管理。

## OCR 下线

- OCR 服务、图片识别接口与识别配置已移除；单词保留文本及 TXT/CSV 导入。
- 原图附件使用 `/api/upload/file`、`/api/upload/batch-simple`，Agent 结构化入库继续保留。
- 历史 OCR 日志与旧配置文件保留，但旧配置不再加载。

## 数学公式与 Agent 入库

- 图片由 Agent 识别后直接入库；新数学题的正文、答案、解析均使用带边界的 LaTeX：行内 `\(...\)`，独立公式 `\[...\]`。
- 次方必须带花括号，如 `x^{2026}`；分数使用 `\frac{a}{b}`。不写排版 HTML，不批量转换历史 `1/2` 等普通文本。
- 使用结构化参数写库，写入后回读核对反斜杠、题干、答案、解析；正式写入前备份，并先通过生产公式渲染器校验。
- 原图缺字或裁切时不补猜；未展示年级、学期或学生作答时不推断。保留原图关联；不因题型复杂而将学生错误类型强行标为“计算”。
- 具体规范、备份及部署命令见 `docs/math-formula-implementation-plan.md`。两张授权图片的可重复导入脚本为 `backend/scripts/import_math_formula_photos.py`，不传 `--apply` 仅预检。

## Cloudflare 正式环境（2026-11-09 已切换）

- 正式入口：https://easyfix-bl2.pages.dev；云端代码在 `cloudflare/src/`，生产数据源为 D1 / R2。
- 旧 PostgreSQL 已冻结为默认只读，只供切换前数据恢复。不要通过旧本地脚本或 MySQL MCP 写生产数据。
- 旧本地 Vue 页面会跳转云端；本地调试需要先理解 `backend/config/cloudflare-cutover.json` 的切换保护，不能直接解除生产旧库只读。
- 保持 Workers 免费计划；统计优先代码和 SQL 聚合，避免逐记录查询、重复 AI 调用与重复生成 PDF。
- 新数据库变更追加 `cloudflare/migrations/`，不得重放旧快照覆盖云端新数据；继续遵守软删除和公式校验规范。
- 部署、验证证据、密钥位置与恢复限制见 `docs/cloudflare-migration-status.md`。`tmp/`、`backups/` 含敏感数据，不得发布或提交。

## 词组默写与重点标注

- `word.entry_type` 区分 `word` / `phrase`（英文含空白即词组，可在编辑时手动改）。词组的重点存在 `word.focus_spec`（JSON），状态 `focus_status` 为 `none` / `draft`（LLM 起草）/ `confirmed`（父母确认或手动修改）。
- `focus_spec` 写入格式：`{"tokens":[{"text":"be","role":"plain"},{"text":"proud","role":"content","lemma":"proud","gloss":"自豪的"},{"text":"of","role":"collocation"},{"text":"sb.","role":"placeholder"}]}`。`tokens` 的 `text` 必须与英文按空白切分的结果逐个相同；`role` 只能是 `collocation`（搭配词）、`content`（可能的生词，必须带原形 `lemma`）、`plain`（基础词）、`placeholder`（sb./sth./doing 等占位符）。
- Agent 录入词组时可在 `POST /api/words/batch` 或 `PUT /api/words/{id}` 里直接附带 `focus_spec`，校验通过即为 `confirmed`；校验不通过时词条照常入库但不带标注。LLM 起草走 `POST /api/words/focus/annotate`，不会覆盖 `confirmed`。
- 规则全部在 `cloudflare/src/phrase_focus.py`（纯函数），测试：`python cloudflare/scripts/phrase_focus_test.py`、`node --test frontend/src/composables/dictation.test.mjs`。
- 已标注的词组只有在完整默写（档位 3）答对时才会被授予"牢记"。
