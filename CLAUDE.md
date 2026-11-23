# CLAUDE.md

本文件为 Claude Code 在本仓库工作时提供指引。实操细则见 `AGENTS.md`，部署、备份与发布记录见 `docs/cloudflare-migration-status.md`。

## 项目概述

EasyFix 是面向学生的错题整理应用：错题录入与归档、两级知识点、单词与词组默写、阅读理解、练习集与 PDF 打印、统计分析、学习报告、激励系统，以及基于 LLM 的相似题与报告生成。

**正式环境自 2026-11-09 起运行在 Cloudflare 上**，入口 https://easyfix-bl2.pages.dev ，用账号密码登录（多家庭账号，每个家庭只看得到自己孩子的数据）。数据在 D1，附件在私有 R2。

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
| Pages 网关 | `cloudflare/pages/` | `_worker.js` 校验会话、提供静态资源、从 R2 直读 `/uploads/` 附件（按 `u<家庭编号>/` 前缀只给本家庭）、图片上传直接写入 R2；`auth_routes.js` 登录页和跟密码有关的接口；`session.js` 会话 Cookie 与身份；`password.js` PBKDF2；其余 `/api/` 请求经服务绑定转给后端 Worker。发布时整个目录按 `_worker.js/` 目录形式打包 |
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
| `main.py` | FastAPI 入口，注册路由；`/health`；定时任务入口 |
| `auth.py` / `identity.py` / `session.py` | guard：确认登录身份（Cookie 或 Agent 令牌）、管理员规则、维护写开关；`/api/auth/me`、切换学生；身份查询与附件归属；会话 Cookie 签发与解析 |
| `accounts.py` | 管理员接口 `/api/admin/*`：开家庭、加学生、改学生、停用 |
| `database.py` / `cache.py` | D1 访问封装与统计缓存 |
| `questions.py` / `similar.py` | 错题 CRUD、批量入库、相似题生成 |
| `knowledge.py` / `knowledge_model.py` / `knowledge_stats.py` | 两级知识点目录、关联与统计 |
| `catalog.py` | 学科、标签、错题本等目录 |
| `words.py` / `review.py` / `word_focus.py` / `phrase_focus.py` | 单词本、复习与默写、词组重点标注 |
| `readings.py` | 阅读短文与题目 |
| `practices.py` / `pdf.py` | 练习集、批改、PDF 生成与复用 |
| `targeted.py` / `targeted_model.py` | 考点卷：状态、选题预览、创建、相似题准备与换题；选题与毕业规则的纯函数 |
| `grading_scan.py` / `grading_model.py` | 批改识别预批：逐页读卷面照片、调一次模型按题号比对；比对提示词与输出清洗的纯函数（不写库） |
| `flip.py` / `flip_model.py` | 翻一翻：每天一组（最多 8 张）错题卡片的选题、记录"记得/忘了"（`flip_log` 表，迁移 0017）；只读掌握度和毕业，不改它们；选题规则是纯函数 |
| `home.py` / `home_model.py` | 首页接口 `/api/home`：待办、这一周（直接用周报的计算函数）、星空三个数 |
| `analytics.py` / `reports.py` | `analytics.py` 现在只剩单词学情 `/api/stats/words` 和 `now()`；`reports.py` 学习报告（旧） |
| `weekly.py` / `weekly_model.py` | 每周周报：定时入口与分步推进（算数字 → 写文字）、`/api/weekly-reports`；一周窗口、考点变化、毕业、文字检查与兜底文字的纯函数 |
| `motivation.py` | 星星、奖励、成就 |
| `media.py` / `audio_index.py` | 单词音频、打印（图片上传由 Pages 网关处理） |
| `settings.py` / `prompts.py` / `provenance.py` | 应用与 LLM 配置、提示词、阅读来源 |

完整接口清单见 `docs/cloudflare-api-checklist.md`。

### 前端结构（`frontend/src/`）

| 目录/文件 | 用途 |
|-----------|------|
| `main.js` / `App.vue` | 应用入口；桌面分组侧栏与手机底部导航 |
| `api/` | Axios 封装（`http.js` 带 GET 去重与短时缓存）；同一个接口只留一个函数，页面不直接写地址（`apiLayer.test.mjs` 钉住） |
| `views/` | 页面组件 |
| `components/home/`、`components/questions/`、`components/insight/`、`components/settings/` | 首页、错题（待核对 / 全部 / 卷子三个标签）、学情（考点 / 单词）、设置（七个标签）各页的组件与纯函数 |
| `data/dailyLines.js` | 首页每日一句 |
| `config/features.js` | 功能开关（`FLIP_READY` 已为开；以后没做完的功能先在这里藏起来） |
| `components/flip/` | 翻一翻的卡片组件与纯函数 |
| `components/ui/` | 共用组件：线条图标 `LineIcon`、图表卡 `ChartCard`、页内标签栏 `TabBar` |
| `composables/` | 默写判分（`dictation.js`）、知识点配色、图表主题（`chartTheme.js`）、页内标签与地址同步（`useTabQuery.js`） |
| `stores/` | `account.js` 当前账号与学生（切换学生后整页刷新）；`appConfig.js` 当前学生的默认年级/学期；`catalog.js` 学科、标签、知识点树集中存放（目录写入后调用 `invalidate`）；`reviewCount.js` 待核对数量 |
| `router/index.js` | 路由配置 |

| 路径 | 页面 |
|------|------|
| `/` | 首页 |
| `/questions?tab=review\|all\|papers` | 错题：待核对、全部错题、卷子 |
| `/papers/:id` | 卷子详情 |
| `/upload` | 手工添加错题 |
| `/insight?tab=points\|words` | 学情：考点、单词 |
| `/settings` | 设置（管理员多一个"账号"标签；每个人都有"我的账号"改密码） |
| `/practice-sets` | 练习中心：所有练习一个列表（错题练习卷、单词、阅读），待批改的卷子也在这里筛选和批改 |
| `/targeted-paper` | 考点卷：出卷页（选科目、题量、分法，预览后生成） |
| `/grade/:id` | 错题练习卷批改（电脑、手机共用）：拍照 → 识别预批 → 复核；`/grade` 跳到练习中心并只看待批改的卷子 |
| `/words` | 单词本 |
| `/flip` | 翻一翻（学生用；手机在"更多"里）：每天一组错题卡片，翻看后点"我记得"或"我忘了" |
| `/reading`、`/reading-test/:id` | 阅读理解 |
| `/learning-reports` | 周报（每周日 20:00 自动生成，打开页面时补做） |
| `/learning-reports/legacy` | 旧报告（只看和删，不再生成） |
| `/motivation` | 激励（不在菜单） |

旧地址 `/review`、`/papers`、`/stats`、`/learning-analysis`、`/star-map`、`/management` 在路由里重定向到新地址。

## 常用命令

均在仓库根目录执行。Wrangler 固定 4.158.0，先执行一次 `npm install --prefix cloudflare`。

```bash
# 测试
python cloudflare/scripts/phrase_focus_test.py
python cloudflare/scripts/knowledge_invariants_test.py
python cloudflare/scripts/weekly_report_test.py
python cloudflare/scripts/home_test.py
python cloudflare/scripts/flip_test.py
python cloudflare/scripts/accounts_test.py
python cloudflare/scripts/isolation_test.py
python cloudflare/scripts/student_scope_test.py
node --test cloudflare/pages/worker.test.mjs cloudflare/pages/auth.test.mjs cloudflare/pages/auth_routes.test.mjs
node --test frontend/src/composables/dictation.test.mjs frontend/src/composables/weeklyReport.test.mjs frontend/src/composables/chartTheme.test.mjs
node --test frontend/src/stores/catalogModel.test.mjs frontend/src/api/apiLayer.test.mjs frontend/src/components/ui/ui.test.mjs
node --test frontend/src/data/dailyLines.test.mjs frontend/src/components/home/homeText.test.mjs frontend/src/components/questions/questionFilters.test.mjs frontend/src/components/insight/insightModel.test.mjs frontend/src/components/settings/settingsModel.test.mjs
node --test frontend/src/components/flip/flipModel.test.mjs

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
- 会话密钥、Agent 令牌只存在 Worker / Pages 密钥和被忽略的 `tmp/cloudflare-config/` 中，不写入仓库或文档；账号密码只存 PBKDF2 哈希，明文不进库、不进日志。
- 学生数据的读写必须带 `student_id`（`current_student_id(request)`），按编号访问别人的记录返回 404；新查询要让 `cloudflare/scripts/student_scope_test.py` 通过。
- `tmp/`、`backups/` 含学生数据与密钥，不得提交或发布。

## 代码规范

- 变量与函数 `snake_case`，函数名用动词或动词短语；类 `PascalCase`；常量全大写下划线。
- 每个函数前写中文文档字符串，复杂逻辑加行内注释。
- 前端使用 Vue 3 Composition API + `<script setup>`，UI 组件用 Element Plus。
- 数学内容使用带边界的 LaTeX：行内 `\(...\)`，独立公式 `\[...\]`，细则见 `AGENTS.md`。
