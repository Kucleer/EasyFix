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
python cloudflare/scripts/weekly_report_test.py           # 周报：一周窗口、取数、推进、定时入口
python cloudflare/scripts/home_test.py                  # 首页接口
python cloudflare/scripts/flip_test.py                  # 翻一翻：选题规则、记录、不影响毕业

# 前端
node --test frontend/src/composables/dictation.test.mjs   # 默写判分
node --test frontend/src/composables/weeklyReport.test.mjs  # 周报图表配置
node --test frontend/src/stores/catalogModel.test.mjs frontend/src/api/apiLayer.test.mjs frontend/src/components/ui/ui.test.mjs frontend/src/composables/chartTheme.test.mjs  # 目录 store、接口层、共用组件、图表主题
node --test frontend/src/data/dailyLines.test.mjs frontend/src/components/home/homeText.test.mjs frontend/src/components/questions/questionFilters.test.mjs frontend/src/components/insight/insightModel.test.mjs frontend/src/components/settings/settingsModel.test.mjs  # 首页、错题、学情、设置的纯函数
node --test frontend/src/components/flip/flipModel.test.mjs  # 翻一翻的纯函数
python backend/scripts/prepare_cloudflare_frontend.py     # 生产构建，输出到 tmp/cloudflare-pages-build
```

- 前端依赖在 `frontend/`（`npm install`），构建需要 Node.js 22.12 或更高版本。
- Wrangler 固定 4.158.0：先执行 `npm install --prefix cloudflare`，之后一律通过 `node cloudflare/tools/cli.cjs <命令>` 调用，授权与日志保存在被忽略的 `tmp/cloudflare-config`。
- 本机 `npm run dev`（Vite）在检测到 `backend/config/cloudflare-cutover.json` 的切换完成标记时，会把页面请求跳转到云端入口。这是切换保护，不要为了本地调试去解除旧库只读。

## 关键事实

- **生产代码**：后端在 `cloudflare/src/`，Pages 网关在 `cloudflare/pages/_worker.js`，PDF 在 `cloudflare/pdf/`。`backend/app/` 是切换前的本地版本，修改它不会影响云端。
- **数据库**：D1 `easyfix`。结构变更只追加 `cloudflare/migrations/NNNN_*.sql`，不得重放旧快照覆盖云端数据；执行前先用 `export_remote_cloudflare.py` 导出备份。
- **软删除**：所有表包含 `deleted` 字段，禁止硬删除，查询必须过滤 `deleted=0`。
- **登录与鉴权**：多家庭账号（设计见 `docs/superpowers/specs/2026-11-23-multi-family-accounts-design.md`）。浏览器用"账号 + 密码"登录（网关 `cloudflare/pages/auth_routes.js`，密码只存 PBKDF2 哈希），得到 HttpOnly 会话 Cookie `v2.过期.用户.学生.版本.签名`；网关和后端每个请求都验签名并查一次 D1 确认账号没停用、版本没变、学生属于这个账号。Agent 用 `Authorization: Bearer <ACCESS_TOKEN>`，代表管理员家庭，可带 `X-Easyfix-Student` 指定学生。`SESSION_SECRET`、`ACCESS_TOKEN` 是 Worker / Pages 密钥，本机副本在 `tmp/cloudflare-config/`，不写入仓库；管理员密码用 `backend/scripts/set_admin_password.py` 设置。
- **按学生隔离**：所有学生数据表的读写都带 `student_id`（`question_scope.current_student_id(request)`），按编号访问别人的记录一律 404；`cloudflare/scripts/student_scope_test.py` 扫描源码盯住漏掉的查询，确实不需要过滤的语句写 `# scope-ok: 理由` 并在测试里登记条数。学科、两级知识点、教材章节、加星规则、成就定义是全站共用目录，只有管理员能改（`identity.admin_only`）。
- **写入开关**：`MIGRATION_READY=true` 为正常状态，部署时不要关闭。停写维护用 D1 `runtime_config.write_maintenance`，开启后所有非只读请求（含 Bearer）返回 503。
- **附件**：上传走 `POST /api/upload/file`（单张，10MB 以内的 jpg/png/webp）或 `POST /api/upload/batch-simple`，对象键为 `u{用户编号}/{year}/{month}/{uuid}_{filename}`（多家庭账号之前的旧附件没有 `u` 前缀，只有 1 号用户能读），通过 `/uploads/<键>` 登录后读取，网关按前缀只给本家庭的附件。
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
- 录入孩子作业或卷子的错题，只通过 `tools/easyfix-intake/` 的技能和小工具提交（录入接口 `/api/intake/...`），规范见该目录的 `SKILL.md`；不直接写数据库、不写一次性导入脚本，也不要用 `backend/scripts/` 下的旧导入脚本。技能安装在 `~/.claude/skills/easyfix-intake/` 与 `~/.agents/skills/easyfix-intake/`，接口地址与口令在 `~/.easyfix/intake.json`。
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
