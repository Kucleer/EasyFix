# AGENTS.md

## 项目简介

EasyFix：学生错题整理应用。前端 Vue 3 + Vite，后端为 Cloudflare Python Worker（FastAPI + D1），附件在私有 R2，正式入口 https://easyfix-bl2.pages.dev （2026-11-09 切换）。

架构与模块说明见 `CLAUDE.md`，本文件只记录实操要点。部署、密钥位置、备份与发布记录见 `docs/cloudflare-migration-status.md`。

## 开发与验证

项目没有 linter、typecheck、CI 和 pre-commit hook，只有几组可直接运行的测试。以下命令均在仓库根目录执行。

```bash
# 后端
python -m compileall -q cloudflare/src                    # 语法检查
python cloudflare/scripts/phrase_focus_test.py            # 词组重点规则
python cloudflare/scripts/knowledge_invariants_test.py    # 两级知识点不变量

# 前端
node --test frontend/src/composables/dictation.test.mjs   # 默写判分
python backend/scripts/prepare_cloudflare_frontend.py     # 生产构建，输出到 tmp/cloudflare-pages-build
```

- 前端依赖在 `frontend/`（`npm install`），构建需要 Node.js 22.12 或更高版本。
- Wrangler 固定 4.158.0：先执行 `npm install --prefix cloudflare`，之后一律通过 `node cloudflare/tools/cli.cjs <命令>` 调用，授权与日志保存在被忽略的 `tmp/cloudflare-config`。
- 本机 `npm run dev`（Vite）在检测到 `backend/config/cloudflare-cutover.json` 的切换完成标记时，会把页面请求跳转到云端入口。这是切换保护，不要为了本地调试去解除旧库只读。

## 关键事实

- **生产代码**：后端在 `cloudflare/src/`，Pages 网关在 `cloudflare/pages/_worker.js`，PDF 在 `cloudflare/pdf/`。`backend/app/` 是切换前的本地版本，修改它不会影响云端。
- **数据库**：D1 `easyfix`。结构变更只追加 `cloudflare/migrations/NNNN_*.sql`，不得重放旧快照覆盖云端数据；执行前先用 `export_remote_cloudflare.py` 导出备份。
- **软删除**：所有表包含 `deleted` 字段，禁止硬删除，查询必须过滤 `deleted=0`。
- **登录与鉴权**：浏览器用访问密码登录，得到 HttpOnly 会话 Cookie；Agent 用 `Authorization: Bearer <ACCESS_TOKEN>`。密码、`SESSION_SECRET`、`ACCESS_TOKEN` 都是 Worker / Pages 密钥，本机副本在 `tmp/cloudflare-config/`，不写入仓库。
- **写入开关**：`MIGRATION_READY=true` 为正常状态，部署时不要关闭。停写维护用 D1 `runtime_config.write_maintenance`，开启后所有非只读请求（含 Bearer）返回 503。
- **附件**：上传走 `POST /api/upload/file`（单张，10MB 以内的 jpg/png/webp）或 `POST /api/upload/batch-simple`，对象键为 `{year}/{month}/{uuid}_{filename}`，通过 `/uploads/<键>` 登录后读取。
- **应用与 LLM 配置**：通过 `/api/config/app`、`/api/config/llm` 读写；LLM 只在主动请求分析、报告、相似题、短文或词组标注时调用。
- **前端 API 层**：`frontend/src/api/http.js` 对 GET 做去重和短时内存缓存，成功写入后清空；新接口注意缓存时长规则。
- **导航**：`frontend/src/App.vue` 是桌面分组侧栏加手机底部导航。
- **MCP**：`.mcp.json` 里的 MySQL 服务指向切换前的本地库，与生产无关，不要用它读写业务数据。

## 新增后端接口步骤

1. 在 `cloudflare/src/` 对应模块里添加路由；新模块需在 `cloudflare/src/main.py` 里 import 并 `app.include_router()`。
2. 用 `database.py` 的 `Database` 访问 D1，多条写入放进同一个 batch；涉及题目知识点的写入沿用 `questions.py` 里已有的写法（`write_guard` 条件与 `question_knowledge_point` 关联同批写入）。
3. 需要新表或新列时追加迁移文件，表必须带 `deleted` 字段。
4. 统计类接口用 SQL 聚合，避免逐记录查询。
5. 在 `docs/cloudflare-api-checklist.md` 补上新接口。

## 新增前端页面步骤

1. 在 `frontend/src/views/<Name>.vue` 创建页面组件。
2. 在 `frontend/src/router/index.js` 添加路由。
3. 在 `frontend/src/App.vue` 的分组导航里添加入口。
4. API 调用写在 `frontend/src/api/` 下，使用带缓存的 axios 实例。

## 分支与发布流程

- 每次修改先创建独立分支（如 `codex/`、`claude/` 前缀），不直接在 `main` 上开发。
- 只提交本次任务相关文件，保留工作区已有修改，不提交敏感数据和生成目录。
- 完成构建与必要验证后，把分支合并到 `main` 并推送远端，再部署 Cloudflare。
- 前端按 `docs/cloudflare-migration-status.md` 的日常部署命令发布 Pages；后端有变更时才部署 Worker；PDF 模板未变时不重发 PDF Worker。
- 部署后核对正式入口与发布状态，把提交、Worker 版本、Pages 部署和未验证的范围记入 `docs/cloudflare-migration-status.md`。

## 代码规范

- 后端：全部 `snake_case`，函数前写中文文档字符串。
- 前端：Vue 3 Composition API + `<script setup>`，UI 组件用 Element Plus。
- 状态管理：默认年级/学期用 `stores/appConfig`，其他业务状态主要在组件内管理。

## 数学公式与 Agent 入库

- OCR 已下线：图片由 Agent 识别后结构化入库，单词保留文本和 TXT/CSV 导入。
- 入库通道是云端接口：`POST /api/questions/batch`（每批最多 100 题，可附 `images` 原图键列表）或 `POST /api/questions`，带 Bearer 令牌。不要用 `backend/scripts/` 下的旧导入脚本直连数据库。
- 新数学题的正文、答案、解析均使用带边界的 LaTeX：行内 `\(...\)`，独立公式 `\[...\]`。次方必须带花括号，如 `x^{2026}`；分数用 `\frac{a}{b}`。不写排版 HTML，不批量转换历史 `1/2` 等普通文本。
- 接口会用 KaTeX 校验公式；写入后回读核对反斜杠、题干、答案、解析。批量写入前先导出 D1 备份。
- 原图缺字或裁切时不补猜；未展示年级、学期或学生作答时不推断。不因题型复杂而把学生错误类型强行标为"计算"。
- 知识点使用两级目录：写入时带 `knowledge_point_ids`、`primary_knowledge_point_id`，修改分类时带读取到的 `knowledge_revision`，规格见 `docs/knowledge-hierarchy-final-plan.md`。
- 公式书写规范的来由见 `docs/math-formula-implementation-plan.md`；该文档里的 PostgreSQL 备份与本地部署部分已不适用。

## 词组默写与重点标注

- `word.entry_type` 区分 `word` / `phrase`（英文含空白即词组，可在编辑时手动改）。词组的重点存在 `word.focus_spec`（JSON），状态 `focus_status` 为 `none` / `draft`（LLM 起草）/ `confirmed`（父母确认或手动修改）。
- `focus_spec` 写入格式：`{"tokens":[{"text":"be","role":"plain"},{"text":"proud","role":"content","lemma":"proud","gloss":"自豪的"},{"text":"of","role":"collocation"},{"text":"sb.","role":"placeholder"}]}`。`tokens` 的 `text` 必须与英文按空白切分的结果逐个相同；`role` 只能是 `collocation`（搭配词）、`content`（可能的生词，必须带原形 `lemma`）、`plain`（基础词）、`placeholder`（sb./sth./doing 等占位符）。
- Agent 录入词组时可在 `POST /api/words/batch` 或 `PUT /api/words/{id}` 里直接附带 `focus_spec`，校验通过即为 `confirmed`；校验不通过时词条照常入库但不带标注。LLM 起草走 `POST /api/words/focus/annotate`，不会覆盖 `confirmed`。
- 规则全部在 `cloudflare/src/phrase_focus.py`（纯函数），测试：`python cloudflare/scripts/phrase_focus_test.py`、`node --test frontend/src/composables/dictation.test.mjs`。
- 已标注的词组只有在完整默写（档位 3）答对时才会被授予"牢记"。
