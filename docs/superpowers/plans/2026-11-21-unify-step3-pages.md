# 项目 5 第 3 步：新菜单、新首页、四页重写 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 换成新菜单（学生用 / 家长用 / 看成果），新首页（每日一句、学生入口、家长待办、这一周、星空三个数），把错题、学情、设置三组页面各重写成一个带标签的页面，同一件事只留一套流程，删掉随之没人用的旧接口。

**Architecture:** 后端新增 `home.py` / `home_model.py`（`GET /api/home`，"这一周"直接调用周报的计算函数）和单词学情小接口 `GET /api/stats/words`；前端新页面用第 2 步的 store、`components/ui/`、`useTabQuery`、`chartTheme`，每个页面一个外壳文件加若干子组件，单个文件尽量不超过 400 行。旧地址一律路由跳转。

**Tech Stack:** Python（FastAPI，Cloudflare Python Worker + D1），Vue 3 `<script setup>` + Pinia + Element Plus + ECharts；后端测试是直接运行的脚本（内存 SQLite），前端测试是 `node --test`。

**Spec:** `docs/superpowers/specs/2026-11-21-workspace-and-unify-design.md` 第 4、5、6、8、10、11 节；版式、配色、文案以样稿 `docs/superpowers/specs/2026-11-21-workspace-mockup.html` 为准。盘点笔记：`.superpowers/sdd/step3-notes.md`（各旧页面的功能清单、行号、接口调用方）。

## Global Constraints

- 用户 2026-11-21 授权第 2–4 步连续做完、每步自动发布、最后统一核对；"每日一句"句库先上线，全部完成后交用户过目。
- 菜单分组文案"学生用""家长用""看成果"；全站不出现"孩子""父母""爸爸妈妈"（周报里对学生说的"你"不变）。
- 页面合并是重写，功能原则上保留；明确去掉的只有设计第 6.6、8.1、8.2 节写出来的几项。
- 第 4 步上线前，首页"翻一翻错题"卡和菜单里的"翻一翻"不显示，学生入口只有"背单词"一张卡（占满一行）。`/api/home` 的翻一翻字段先返回 `null`。
- "这一周"的窗口和算法与周报完全相同：调用 `weekly.py` 的 `entries_part`、`dictation_part`、`practice_part`、`subject_part` 和 `weekly_model` 的窗口函数，不另写一套。当前这一期 = `week_end_before(now) + 7 天`。
- 待批改数：所有还没批改的错题练习卷（`source_type='question'`、未批改、未删除），不限最近 30 天；首页和练习中心、考点卷状态用同一个函数。
- "有学习记录的一天" = 当天有默写记录（`word_review_log.review_type=1`）或翻一翻记录（第 4 步才有）。家长录入不算。
- 不删任何表、列、数据；不新增迁移。旧地址都保留跳转。
- 代码规范照 `CLAUDE.md`；后端函数前写中文文档字符串，`snake_case`；前端 `<script setup>`。
- 不引用外部字体；不新增前端依赖。
- 发布顺序：新增的后端接口先单独部署（任务 1 之后，旧接口都还在）；全部做完后先发前端、再发删掉旧接口的后端。

## Review Focus

1. 首页"这一周"的数字和同一时刻周报算法算出的逐项相同，周日 20:00 一过自动切到下一期。（任务 1 测试 `home_week_matches_weekly_facts`、`current_week_end_rolls_at_sunday_20`）
2. 从学情、卷子详情、旧书签（`/review`、`/papers`、`/star-map`、`/learning-analysis`、`/stats`、`/management`）进来都落到新页面的正确标签，带着的筛选条件（`subject_id`、`knowledge_parent_id`、`knowledge_point_id`、`unclassified`）不丢。（任务 3、5、6、7）
3. 错题页带 `?subject_id=` 进入时，知识点筛选不被清掉，筛选项接口只调一次；电脑上换学科不会带着旧知识点去请求（不再出现"知识点与学科不匹配"）。（任务 5）
4. 手机 375 宽：底部 5 格导航不遮内容，"更多"抽屉能打开所有其余入口，各新页面没有横向滚动。（任务 3–7，每页都在 375 宽下检查）
5. 待核对、待批改数字在首页、菜单红点、点进去看到的列表三处一致。（任务 1、4、5）

---

## 文件一览

| 文件 | 怎么动 |
| --- | --- |
| `cloudflare/src/home_model.py`、`home.py`、`cloudflare/scripts/home_test.py` | 新建：首页接口 |
| `cloudflare/src/targeted.py`、`targeted_model.py` | 待批改数改成不限 30 天，抽成共用函数 |
| `cloudflare/src/analytics.py` | 新增 `GET /api/stats/words`；删 `summary`、`overview`、`knowledge`、`full`、`llm` 及只为它们服务的函数 |
| `cloudflare/src/knowledge_stats.py`、`similar.py`、`practices.py`、`cache.py`、`auth.py`、`main.py` | 删没人用的；注册新路由 |
| `cloudflare/scripts/local_dev_server.py`、`dead_routes_test.py`、`intake_test.py`、`knowledge_api_test.py`、`knowledge_invariants_test.py` | 登记新模块；清单和用例跟着改 |
| `frontend/src/data/dailyLines.js`、`dailyLines.test.mjs` | 新建：句库和取句 |
| `frontend/src/App.vue`、`router/index.js`、`styles/variables.css` | 新菜单、地址、去掉顶部栏 |
| `frontend/src/views/Home.vue` + `components/home/*` | 重写首页 |
| `frontend/src/views/Questions.vue` + `components/questions/*`；删 `ReviewQueue.vue`、`Papers.vue` | 错题三标签 |
| `frontend/src/views/Insight.vue` + `components/insight/*`；删 `StarMap.vue`、`LearningAnalysis.vue` | 学情两标签 |
| `frontend/src/views/Settings.vue` + `components/settings/*`；删 `Management.vue` | 设置 |
| `frontend/src/views/PaperDetail.vue`、`GradePaper.vue`、`PracticeSets.vue`、`components/ManualQuestionForm.vue` | 改链接；删练习中心里走不到的批改代码 |
| `frontend/src/api/home.js`（新）、`question.js`、`learning_analysis.js` | 接口函数跟着改 |
| `docs/cloudflare-api-checklist.md`、`CLAUDE.md`、`docs/cloudflare-migration-status.md`、路线图 | 文档 |

"跑全部测试"（仓库根目录，每条退出码 0）：

```bash
python cloudflare/scripts/dead_routes_test.py
python cloudflare/scripts/home_test.py
python cloudflare/scripts/knowledge_api_test.py
python cloudflare/scripts/knowledge_invariants_test.py
python cloudflare/scripts/phrase_focus_test.py
python cloudflare/scripts/intake_test.py
python cloudflare/scripts/scan_test.py
python cloudflare/scripts/starmap_test.py
python cloudflare/scripts/targeted_test.py
python cloudflare/scripts/grading_scan_test.py
python cloudflare/scripts/weekly_report_test.py
python cloudflare/scripts/local_dev_server_test.py
node --test cloudflare/pages/worker.test.mjs
node --test frontend/src/stores/catalogModel.test.mjs frontend/src/api/apiLayer.test.mjs frontend/src/components/ui/ui.test.mjs frontend/src/composables/chartTheme.test.mjs frontend/src/composables/dictation.test.mjs frontend/src/composables/weeklyReport.test.mjs frontend/src/data/dailyLines.test.mjs
python -m compileall -q cloudflare/src
python backend/scripts/prepare_cloudflare_frontend.py
```

---

### Task 1：首页接口和单词学情接口（只新增，不删）

**Files:**
- Create: `cloudflare/src/home_model.py`、`cloudflare/src/home.py`、`cloudflare/scripts/home_test.py`
- Modify: `cloudflare/src/targeted_model.py` / `targeted.py`（待批改数）、`cloudflare/src/analytics.py`（新增 `/words`）、`cloudflare/src/main.py`、`cloudflare/src/cache.py`、`cloudflare/scripts/local_dev_server.py`、`cloudflare/scripts/dead_routes_test.py`（KEPT 加 `home.py` 的 `@router.get('/api/home')`、`analytics.py` 的 `@router.get('/words')`）

**Interfaces:**
- `home_model.py`（纯函数，不查库）：
  - `current_week_end(moment: datetime) -> datetime`：`week_end_before(moment) + timedelta(days=7)`
  - `streak_days(active_dates: set[str], today: str) -> int`：从今天往前数连续有记录的天数；今天没有但昨天有，从昨天开始数；都没有返回 0（日期 `YYYY-MM-DD`）
  - `week_days(monday: str, active_dates: set[str]) -> list[dict]`：周一到周日 7 项 `{date, active}`
  - `sky_counts(status_counts_list: list[dict]) -> dict`：`{'weak': Σweak, 'middle': Σ(fair+good), 'lit': Σmastered}`，`unlearned` 不计
  - `top_names(items: list[dict], limit=3) -> list[str]`：取前 `limit` 个 `name`
- `targeted.py`：`async def pending_grading(db) -> dict`，返回 `{'count': int, 'oldest': {'id','name','created_at'} | None}`；条件 `deleted=0 AND source_type='question' AND COALESCE(reviewed,0)=0`，不限日期；`GET /api/practice-sets/targeted/status` 的 `pending_count` 改用它的 `count`（返回字段名不变）。`open_cutoff` 若随之没人用就删掉。
- `GET /api/home`（`home.py`，`router = APIRouter()`）返回：

```json
{
  "review": {"count": 0, "latest_paper": {"id": 1, "name": "…"} },
  "grading": {"count": 0, "oldest": {"id": 1, "name": "…", "created_at": "…"} },
  "targeted": {"last_created_at": "2026-11-20 19:00:00"},
  "words": {"due": 0},
  "flip": null,
  "streak_days": 0,
  "week": {"monday": "…", "sunday": "…", "days": [{"date": "…", "active": true}],
           "entries": 0, "papers": 0, "dictation_days": 0, "flip_days": 0,
           "improved": ["名称"], "dropped": ["名称"]},
  "sky": {"weak": 0, "middle": 0, "lit": 0}
}
```

  - `review.count`：`review_status='pending'` 且未删除；`latest_paper`：有待核对题的卷子里最新的一份（`paper` 表，按 `paper_date DESC, id DESC`），没有就 `null`
  - `targeted.last_created_at`：最近一份 `kind='targeted'` 未删除练习卷的 `created_at`，没有就 `null`
  - `words.due`：`next_review_at` 不为空且 `<= now()`（北京时间）的未删除单词数，用一条 `COUNT` SQL（口径同 `words.py` 的 `due_words`）
  - `week`：`week_end = current_week_end(analytics.now())`，`win = weekly_model.window(week_end)`；`entries = entries_part(...)['count']`，`papers = practice_part(...)['papers']`，`dictation_days = dictation_part(...)['days']`；`improved` / `dropped` 是各学科 `subject_part` 的 `improved` / `dropped` 合在一起后 `top_names(..., 3)`；`days = week_days(win['monday'], 默写日期集合)`
  - `sky`：`sky_counts(各学科 subject_part 的 status_counts)`；只算 `weekly.load_subjects` 里 `has_leaves` 的学科，`config`、`default_grade` 照 `build_facts` 的取法各取一次
  - `streak_days`：最近 60 天默写记录的日期集合 → `streak_days(dates, today)`
  - `flip` 和 `week.flip_days`：先返回 `null` 和 `0`（第 4 步填）
- `GET /api/stats/words`（`analytics.py`）返回 `{"low_accuracy_words": [{"word","accuracy"}], "frequency": [{"date","count"}]}`，SQL 照抄 `analytics.full()` 里 `low`、`frequency` 两条（不再看学科）。
- `cache.py` 的 `PATHS` 加 `/api/home`、`/api/stats/words`。`main.py` 和 `local_dev_server.py` 的 `ROUTER_MODULES` 都登记 `home`。

- [ ] **Step 1：写 `home_test.py`**（结构照 `weekly_report_test.py`：`check(名称, 函数)`，复用它的 `build_db`、造数据的函数）
  - `current_week_end_rolls_at_sunday_20`：周日 19:59 → 当天 20:00；周日 20:00 → 下周日 20:00
  - `streak_days`：今天有、昨天有、前天没有 → 2；今天没有、昨天有 → 从昨天数；都没有 → 0
  - `week_days` 返回 7 项，周一在前，`active` 按集合
  - `sky_counts` 合并两科、`unlearned` 不计
  - `home_week_matches_weekly_facts`：造一周的录入、默写、批改数据，同一个 `week_end` 下 `/api/home` 的 `week.entries`、`week.papers`、`week.dictation_days` 和 `weekly.build_facts` 的 `entries.count`、`practice.papers`、`dictation.days` 相等
  - `grading_pending_not_limited_to_30_days`：一份 40 天前的未批改错题练习卷计入 `grading.count`，`oldest` 是它；`targeted/status` 的 `pending_count` 相同
  - `home_flip_fields_empty_before_step4`：`flip is None`，`week.flip_days == 0`
  - `stats_words_returns_low_accuracy_and_frequency`
- [ ] **Step 2：运行，确认失败**；**Step 3：实现**；**Step 4：跑全部测试**（`targeted_test.py` 里若有用例断言了 30 天窗口，按新口径改用例，并在汇报里写明）
- [ ] **Step 5：提交** `feat(home): add /api/home and /api/stats/words; pending grading count without 30-day window`
- [ ] **Step 6：部署 Worker**（只新增接口，旧接口都在；照 `docs/cloudflare-migration-status.md` 日常部署；记下前后版本号）。用录入口令读 `/api/home`、`/api/stats/words` 确认 200，记下 `/api/home` 的耗时。

---

### Task 2：每日一句句库

**Files:** Create `frontend/src/data/dailyLines.js`、`frontend/src/data/dailyLines.test.mjs`

**Interfaces:**
- `DAILY_LINES`：约 100 句。对学生说、只鼓励、不说教，贴着她实际在做的事（订正错题、背单词、坚持、考点、星空），不用"加油""你最棒"这类空话；每句不超过 20 个字；不出现"孩子""父母""爸爸妈妈"。
- `beijingDate(now: Date) -> 'YYYY-MM-DD'`：按 UTC+8 取日期（不依赖运行环境的时区）
- `pickDailyLine(dateText: string) -> string`：同一天同一句、相邻两天不同；算法：把日期转成从 2026-01-01 起的天数 `n`，取 `DAILY_LINES[n % DAILY_LINES.length]`

- [ ] **Step 1：写测试**：句数 ≥ 90；每句长度 ≤ 20、互不重复、不含"加油""最棒""孩子""父母""爸爸""妈妈"；`beijingDate(new Date('2026-11-21T16:30:00Z')) === '2026-11-22'`；同一天两次相同；连续 30 天相邻两天都不同
- [ ] **Step 2–4：确认失败 → 写句库和函数 → 通过**
- [ ] **Step 5：提交** `feat(home): daily encouragement lines picked by Beijing date`

---

### Task 3：新菜单、新地址、去掉顶部栏

**Files:** Modify `frontend/src/App.vue`、`frontend/src/router/index.js`、`frontend/src/styles/variables.css`

**菜单（照样稿 `NAV`、`BOTTOM_IDS`，图标用 `LineIcon`）：**

| 分组 | 项 | 地址 |
| --- | --- | --- |
| （无） | 首页 `home` | `/` |
| 学生用 | 单词 `words`、翻一翻 `flip`（第 4 步前隐藏）、阅读 `reading` | `/words`、`/flip`、`/reading` |
| 家长用 | 错题 `questions`（红色数字 = 待核对数，点进 `?tab=review`）、练习 `practice` | `/questions`、`/practice-sets` |
| 看成果 | 周报 `weekly`、学情 `insight` | `/learning-reports`、`/insight` |
| （无） | 设置 `settings` | `/settings` |

- 手机底部 5 格：首页、单词、错题、练习、更多；"更多"抽屉里：（翻一翻）、阅读、周报、学情、设置。
- 去掉顶部栏（面包屑、"录入错题"按钮、"学"标记）；`.app-main` 的上边距相应调整。
- 菜单项高亮：`/upload` 算错题，`/papers/:id` 算错题，`/reading-test/*` 算阅读，`/learning-reports/legacy` 算周报，`/targeted-paper`、`/grade/*` 算练习。
- 一个开关常量 `FLIP_READY = false` 控制翻一翻入口（第 4 步改成 `true`）。

**路由：**
- 新增 `/insight`（任务 6 的页面）；`/review` → `/questions?tab=review`；`/papers` → `/questions?tab=papers`；`/star-map`、`/learning-analysis`、`/stats` → `/insight`；`/management` → `/settings`。跳转保留原来的其余 query（例如 `/learning-analysis?x=1` 不需要，但 `/papers?subject_id=` 要带上）。
- `/motivation` 保留，不在菜单。

- [ ] **Step 1：改 `router/index.js`、`App.vue`、`variables.css`**（新页面还没写好的路由先指向旧组件，任务 5–7 各自替换）
- [ ] **Step 2：构建；用本机预览在 1280 宽和 375 宽各看一次**（本机开发服务器会被切换保护跳到云端，预览方法见任务 8 的说明；做不到就只构建，在汇报里写明）
- [ ] **Step 3：提交** `feat(ui): new grouped menu, mobile bottom nav and route redirects`

---

### Task 4：新首页

**Files:** Rewrite `frontend/src/views/Home.vue`；Create `frontend/src/components/home/`（`DailyLine.vue`、`StudentEntries.vue`、`ParentTodos.vue`、`WeekSummary.vue`、`SkyCard.vue`）、`frontend/src/api/home.js`（`homeApi.get()`，`cache: false`）；Modify `frontend/src/api/question.js`（删 `statsApi`、`statsOverviewApi`）

- 版式、顺序、文案照样稿首页和设计第 6 节：每日一句（上方小字星期和日期，右侧/手机下方"已经连续 N 天"，N 为 0 不显示）→ 学生入口（背单词：`words.due` 个待温习 / 为 0 写"今天的都温习完了"，点进 `/words`；翻一翻卡在 `FLIP_READY` 为假时不渲染，背单词卡占满一行）→ 家长待办三格（待核对 → `/questions?tab=review`，副标题最近卷子名；待批改 → `/practice-sets?pending=1`，副标题最早一份的名称和日期；出一份考点卷 → `/targeted-paper`，副标题"上次出卷是 N 天前"；前两格为 0 时浅色、写"都处理完了"、仍可点）→ 这一周（左：日期范围、七天打卡条、四个数字、变好/变差标签各最多 3 个、"看周报"链接；右：夜色星空卡三个数 `还薄弱 / 一般 / 已点亮`，点进 `/insight`）。
- 打开首页只发 `/api/home` 一个业务请求（外加 `App.vue` 已有的配置和待核对数）。
- 去掉：9 张累计卡、昨日/今日对比、准确率曲线、学科难度表、年级下拉框、旧的 `StarMapCard` 引用（`StarMapCard.vue` 若随之没人用就删）。
- 菜单红点和首页待核对数都用 `reviewCountStore`；首页拿到 `/api/home` 后把 `review.count` 写回 store（保持一致）。

- [ ] **Step 1：实现；构建；375 宽和 1280 宽各看一次**
- [ ] **Step 2：确认 `statsApi`、`statsOverviewApi` 在前端已没有引用后删除**
- [ ] **Step 3：提交** `feat(home): rewrite home page around /api/home`

---

### Task 5：错题页（待核对 / 全部错题 / 卷子和作业）

**Files:** Rewrite `frontend/src/views/Questions.vue` 为外壳；Create `frontend/src/components/questions/`（`ReviewTab.vue`、`AllTab.vue`、`QuestionFilters.vue`、`QuestionList.vue`、`QuestionDetailDialog.vue`、`QuestionEditDialog.vue`、`PapersTab.vue`，按需要拆）；Delete `views/ReviewQueue.vue`、`views/Papers.vue`；Modify `views/PaperDetail.vue`（返回 → `/questions?tab=papers`；待核对行 → `/questions?tab=review`；删除后 → `/questions?tab=papers`）、`components/ManualQuestionForm.vue`（"查看列表" → `/questions?tab=all`）；后端删 `POST /api/questions/batch-similar`（`similar.py`）、`practices.py` `create_set` 里 `question_type=='similar'` 同步生成相似题的分支（`get` 里对旧数据 `question_type=='similar'` 的兼容保留）；前端删 `questionApi.batchGenerateSimilar`

- 标签用 `TabBar` + `useTabQuery(['review','all','papers'], 默认: 待核对数 > 0 ? 'review' : 'all')`；待核对标签带红色数字。
- 待核对：功能照 `ReviewQueue.vue` 全部保留（按卷子分组、三种操作、错误处理、操作后刷新 `reviewCountStore`）。
- 全部错题：列表、筛选、详情、编辑、单题生成相似题、删除都保留（盘点笔记里的完整清单）；两个搜索框合成一个（电脑和手机共用一个输入框）；右上角"手工添加"按钮 → `/upload`（电脑和手机相同）；"出练习卷" → `/targeted-paper?subject_id=`。删除待核对的题后刷新 `reviewCountStore`。
- **去掉**：打印原题、打印相似题、创建练习集弹窗、批量生成相似题，以及只为它们服务的多选。
- **修掉**：从地址带 `subject_id`、`knowledge_parent_id`、`knowledge_point_id`、`unclassified`、`grade` 进入时，先按 `subject_id` 取一次筛选项，再套用地址里的知识点筛选，筛选项接口只调一次、地址里的筛选不被清掉；地址里的筛选变化（从别的页面再次跳进来）要重新套用；电脑上换学科时先清掉知识点筛选再请求；任何筛选变化回到第 1 页。
- 卷子和作业：照 `Papers.vue`（筛选、表格/手机卡片、分页、新增记录弹窗）；详情仍去 `/papers/:id`。
- 后端删除前在 `frontend/src`、`tools/easyfix-intake`、`cloudflare/src`、`cloudflare/scripts` 搜调用方；`dead_routes_test.py` 的 REMOVED 加 `('similar.py', "'/batch-similar'")`。

- [ ] **Step 1：后端删除和测试调整，跑全部测试**
- [ ] **Step 2：前端实现；构建；375 宽和 1280 宽各看一次**
- [ ] **Step 3：提交** `feat(questions): one page with review, all and papers tabs; drop manual print and batch similar`

---

### Task 6：学情页（考点 / 单词）

**Files:** Create `frontend/src/views/Insight.vue`、`frontend/src/components/insight/`（`PointsTab.vue`、`PointTable.vue`、`WordsTab.vue`）；Delete `views/StarMap.vue`、`views/LearningAnalysis.vue`、`api/learning_analysis.js`（`SubjectKnowledgeRanking.vue` 旧报告页还在用，保留）；Modify `views/GradePaper.vue`（"点亮了 N 颗星"链接 → `/insight`）；后端删 `analytics.py` 的 `summary`、`overview`、`knowledge`、`full`、`llm` 和只为它们服务的 `grouped`、`primary_module_counts`、`date_stats`（`now` 保留，别的模块在用），`cache.py` 的 `PATHS`、`auth.py` 里对应的路径，`knowledge_stats.py` 里随之只剩测试在用的 `module_stats`、`scoped_filters`、`recency_filter`、`COUNTING_MODE`、`taxonomy_version`（`knowledge_options`、`validate_filter_ids` 保留），以及只测这些的测试用例（`intake_test.py` 1350–1366 附近、`knowledge_api_test.py` 的统计用例、`knowledge_invariants_test.py` 里用到 `module_stats` 的部分）

- 标签 `useTabQuery(['points','words'], 'points')`。
- 考点：学科切换（`catalog.loadStarmapSubjects()`）；上半页 `StarCanvas`（非 mini，图例、悬停提示、点击卡片、"点亮时刻"播放和 `markSeen`，照 `StarMap.vue` 搬过来，高度固定，不再依赖顶部栏高度）；下半页按模块分组、考点展开的明细表（数据全部来自 `/api/starmap` 的 `nodes`）：考点名、掌握状态（`statusText`）、最近几次对错（`recent`）、待重做题数（`pending`）；点一行去 `/questions?tab=all&subject_id=&knowledge_parent_id=&knowledge_point_id=`。手机上明细表用卡片。
- 单词：`GET /api/stats/words` → "需要关注的单词"表、"单词复习频率"折线（用 `ChartCard` + `useChartTheme()`）。
- 去掉：学习建议、一级模块排行、错题复习覆盖、正确率趋势、每周练习分布、难度分布。
- 删除后端前先确认旧报告页 `/learning-reports/legacy` 只读已存结果、不调这些接口（看 `LearningReports.vue` 的接口调用）。
- `dead_routes_test.py`：REMOVED 加 `('analytics.py', "@router.get('/summary')")`、`("analytics.py", "@router.get('/overview')")`、`('analytics.py', "@router.get('/knowledge-points')")`、`('analytics.py', "@router.get('/analysis/full')")`、`('analytics.py', "@router.post('/analysis/llm')")`（以源码里实际的写法为准）。

- [ ] **Step 1：后端删除和测试调整，跑全部测试**
- [ ] **Step 2：前端实现；构建；375 宽和 1280 宽各看一次**
- [ ] **Step 3：提交** `feat(insight): star points and word insight on one page; drop old analysis endpoints`

---

### Task 7：设置页

**Files:** Rewrite `frontend/src/views/Settings.vue` 为外壳；Create `frontend/src/components/settings/`（`GradeTab.vue`、`SubjectsTab.vue`、`TagsTab.vue`、`KnowledgeTab.vue`、`ErrorBooksTab.vue`、`ModelTab.vue`，以及不在标签栏显示的 `StarActionsPanel.vue`、`AchievementsPanel.vue`、`RewardsPanel.vue`）；Delete `views/Management.vue`

- 标签：年级与学期、学科、标签、知识点、错题本、知识星空（`StarMapSettings`）、模型；`useTabQuery`，默认"年级与学期"。
- 进入时验一次访问密码（`authApi.verifyPassword`），本次打开期间切换标签不再验；验过之前不渲染任何标签内容。
- 点到哪个标签才加载哪个标签的数据。
- 各标签功能照盘点笔记里 `Management.vue`、`Settings.vue` 的清单全部保留（含知识点的待处理旧目录、localStorage 记住的筛选、手机紧凑列表）；学科、标签、知识点写入后照第 2 步做法让 store 失效。
- 成就相关三块拆成独立组件保留，标签栏里不显示（`/motivation` 页不受影响）。
- 两个 `configApi` 已在第 2 步合并，这里直接用 `api/config.js`。

- [ ] **Step 1：实现；构建；375 宽和 1280 宽各看一次**
- [ ] **Step 2：提交** `feat(settings): one settings page with lazy tabs and a single password check`

---

### Task 8：收尾、发布、记录

- [ ] **Step 1：练习中心**：删 `PracticeSets.vue` 里已走不到的 `gradingStep`、`gradingCurrentIndex`、`handleOverallGrading`；"待批改 N" 用 `targetedApi.status().pending_count`（任务 1 后已不限 30 天，和列表一致）。
- [ ] **Step 2：全站搜旧地址**（`/review`、`/papers"`、`/star-map`、`/learning-analysis`、`/management`、`/stats`）和"孩子""父母""爸爸妈妈"字样，改成新地址 / 新文案。
- [ ] **Step 3：跑全部测试；`python cloudflare/scripts/dead_routes_test.py` 全过**
- [ ] **Step 4：独立审阅整个分支**（重点见本文 Review Focus），修掉严重和重要的问题
- [ ] **Step 5：预览**：本机 `npm run dev` 会被切换保护跳到云端，用 `vite preview` 打开 `tmp/cloudflare-pages-build`（无后端，只看版式），或者在发布后用正式站点（需要登录，本机没有密码则跳过）；在 375 宽和 1280 宽下看菜单、首页、错题、学情、设置
- [ ] **Step 6：快进合并进本地 `main`；先发 Pages，再部署删了旧接口的 Worker**；核对 `/health` 200、首页跳登录 303、录入口令读 `/api/home` 200、录入小工具 `guide` 正常、被删的 `/api/stats/summary` 等不再出现在 `dead_routes_test` 的 KEPT 里
- [ ] **Step 7：文档**：`docs/cloudflare-api-checklist.md`（删掉的、新增的接口）、`CLAUDE.md`（模块表加 `home.py`、`home_model.py`；前端路由表换成新地址）、`docs/cloudflare-migration-status.md` 变更记录、路线图状态行；提交、合并、推送
- [ ] **Step 8：登录后核对清单**（留到第 4 步完成后一起给用户）：菜单和手机底部导航；首页四块的数字和点进去看到的是否一致；错题三个标签（待核对三种操作、全部错题的筛选/编辑/详情/相似题、卷子新增和详情返回）；学情两个标签；设置七个标签和验密码；旧地址跳转
