# 项目 5 第 4 步：翻一翻 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 学生在手机上每天翻一小组错题卡片（只看不写，"我记得 / 我忘了"），选题按规则安排复习间隔；结果进首页和周报，不影响考点掌握度和错题毕业。

**Architecture:** 新表 `flip_log`（迁移 `0017`）；选题规则写成纯函数 `flip_model.py`；接口 `flip.py`（`GET /api/flip/today`、`POST /api/flip/{question_id}`）；首页接口和周报加翻一翻的数字；前端新页面 `/flip`，打开第 3 步留好的 `FLIP_READY` 开关。

**Tech Stack:** Python（FastAPI，Cloudflare Python Worker + D1），Vue 3 `<script setup>` + Element Plus；后端测试是直接运行的脚本（内存 SQLite），前端 `node --test`。

**Spec:** `docs/superpowers/specs/2026-11-21-workspace-and-unify-design.md` 第 7 节（翻一翻）、6.1/6.2/6.4（首页）、11、12；样稿 `docs/superpowers/specs/2026-11-21-workspace-mockup.html` 的翻一翻页面和首页卡片。

## Global Constraints

- 用户 2026-11-21 授权连续做完、自动发布、最后统一核对。
- 迁移 `0017` 只新建表 `flip_log`，不改已有的表；表带 `deleted`；执行前先导出 D1 备份。
- 翻一翻的"我记得 / 我忘了"**不影响**考点掌握度、错题毕业、知识星空颜色；只读这些数据，不写。
- 数字常量写在 `flip_model.py` 顶部：`DAILY_LIMIT = 8`、`FORGOT_GAP_DAYS = 2`、`REMEMBER_GAPS = (3, 7, 14)`（连续记得 1 次隔 3 天、2 次隔 7 天、3 次及以上隔 14 天）。
- "今天"按北京时间（`analytics.now()`）。
- 候选题：已通过核对、未删除（`question_scope.counted('q')`）、没有毕业（`targeted_model.question_state`，取数方式照 `weekly.graduated_count`，时间截止到现在）、题干不为空或者有原图；所有学科、所有年级，没挂考点的也进。
- 排序：① 上次点了"我忘了"且距上次翻已满 2 天；② 从没翻过的，录入时间新的在前；③ 上次点了"我记得"且到期的。今天已经翻过的题不再出现；今天的张数 = 8 − 今天已翻张数，再和候选数取小；同一天内多次打开剩下的卡片和顺序不变（并列按题目编号）。
- 同一道题同一天重复提交只算一次。
- 首页 `/api/home` 的 `flip` 字段 = `{"total": int, "done": int}`（第 3 步前端已按这个形状写好）；`week.flip_days` 是本周翻过卡片的天数；"有学习记录的一天" = 默写或翻一翻，七天打卡条和连续天数都按这个口径。
- 周报：数字里加"这周翻了几天、几张"；打卡日历上翻一翻也算一天；只翻了卡片、没有录入、默写、练习卷时**不算**安静的一周；模型写文字时可以夸坚持翻了，只说翻了多少，不评价忘了多少（不把"忘了"的数字交给模型）；旧的周报没有这项数据，页面照常显示。
- 前端文案：不出现"孩子""父母""爸爸""妈妈"；卡片顺序和两个按钮以样稿为准；翻完显示"今天翻完了"，不能继续刷；没有可翻的题显示"今天没有要翻的"。
- 代码规范照 `CLAUDE.md`。

## Review Focus

1. 一天最多 8 张；同一天反复打开、翻到一半刷新，剩下的卡片和顺序不变，已翻的不再出现。（任务 1 测试）
2. "我忘了"的题满 2 天才再出现；"我记得"的间隔按 3 / 7 / 14 天拉长；中间点了一次"我忘了"，连续记得的次数清零。（任务 1 测试）
3. 毕业的题不出现；翻一翻前后星空、掌握度、毕业状态不变。（任务 1 测试 `flip_does_not_change_mastery`）
4. 同一题同一天连点两次只记一次；网络慢时连点按钮不会翻过两张。（任务 1、3）
5. 首页"这一周"的数字和周报算出来的一致，翻一翻那天算打卡；旧周报（没有 flip 字段）照常显示。（任务 2、3）

---

"跑全部测试"：第 3 步计划里的整套命令，加上 `python cloudflare/scripts/flip_test.py` 和任务 3 新增的前端测试文件。

---

### Task 1：表、选题规则、两个接口

**Files:**
- Create: `cloudflare/migrations/0017_flip_log.sql`、`cloudflare/src/flip_model.py`、`cloudflare/src/flip.py`、`cloudflare/scripts/flip_test.py`
- Modify: `cloudflare/src/main.py`、`cloudflare/scripts/local_dev_server.py`（`ROUTER_MODULES` 登记 `flip`，并照其他迁移的做法让本地库建出新表）、`cloudflare/scripts/dead_routes_test.py`（KEPT 加两个新路由）

**Interfaces:**
- `flip_log`：`id INTEGER PRIMARY KEY`、`student_id INTEGER NOT NULL DEFAULT 1`、`question_id INTEGER NOT NULL`、`result TEXT NOT NULL`（`'remember'` / `'forget'`）、`flip_date TEXT NOT NULL`（北京日期 `YYYY-MM-DD`）、`created_at TEXT NOT NULL`、`deleted INTEGER NOT NULL DEFAULT 0`；唯一索引 `(student_id, question_id, flip_date) WHERE deleted=0`；另建 `(student_id, flip_date)` 索引。文件头写清用途（照 `0016` 的写法）。
- `flip_model.py`（纯函数）：
  - `history_state(logs: list[dict]) -> dict`：一题的翻牌记录（按时间）→ `{'last_result', 'last_date', 'remember_streak'}`（末尾连续"记得"的次数）
  - `due_rank(state, today) -> tuple | None`：返回排序键（组号 1/2/3 + 组内键），不到期返回 `None`；组 1 按上次翻的日期早的在前，组 2 按录入时间新的在前，组 3 按到期日早的在前；并列都按题目编号
  - `pick_today(candidates, logs_by_question, today) -> dict`：`{'done': 今天已翻张数, 'cards': [题目编号, ...]}`，`cards` 长度 = `min(DAILY_LIMIT - done, 可出的题数)`，不小于 0
  - `days_between(a, b) -> int`（日期文本相减）
- `GET /api/flip/today` → `{"total": done + len(cards), "done": int, "cards": [{"id", "subject_name", "point_name"|null, "parsed_question", "images": [路径...], "wrong_answer"|null, "answer", "analysis"|null, "analysis_image"|null}]}`；`point_name` 取主考点（`question_knowledge_point.is_primary=1`），没有就 `null`；图片沿用 `original_image` / `original_images` 的现有存法（照 `questions.py` 的读取方式）。
- `POST /api/flip/{question_id}` 请求 `{"result": "remember"|"forget"}` → 写一条记录（今天已有这题的记录就不再写，返回已有的）；题目不存在或不在候选范围（未核对、已删除）返回 404；`result` 非法返回 422。返回 `{"done": int, "total": int}`（今天的进度）。
- 首页、周报会复用的取数函数放在 `flip.py`：`async def flip_dates(db, student_id, start, end) -> set[str]`（区间内翻过的日期）、`async def flip_counts(db, student_id, start, end) -> dict`（`{'days', 'cards'}`）、`async def today_progress(db, student_id, today) -> dict`（`{'total', 'done'}`，和 `/api/flip/today` 同一套选题）。

- [ ] **Step 1：写 `flip_test.py`**（照 `weekly_report_test.py` 的写法建库、造数据；迁移按顺序执行到 `0017`）：
  - `pick_today_limits_to_8`、`never_flipped_newest_first`、`forgot_waits_2_days`、`remember_gaps_3_7_14`、`forget_resets_remember_streak`、`today_flipped_excluded_and_order_stable`、`graduated_excluded`、`pending_or_deleted_excluded`、`empty_stem_without_image_excluded`、`post_same_day_twice_records_once`、`post_rejects_bad_result_and_unknown_question`、`flip_does_not_change_mastery`（翻牌前后 `starmap.compute` 的节点状态、`question_state` 相同）、`migration_creates_flip_log`
- [ ] **Step 2：运行，确认失败；Step 3：实现；Step 4：跑全部测试**
- [ ] **Step 5：提交** `feat(flip): flip_log table, daily pick rules and flip endpoints`

---

### Task 2：首页和周报加上翻一翻

**Files:** Modify `cloudflare/src/home.py`、`home_model.py`（如需）、`cloudflare/src/weekly.py`、`weekly_model.py`、`prompts.py`；Test `cloudflare/scripts/home_test.py`、`weekly_report_test.py`

- `/api/home`：`flip = today_progress(...)`；`week.flip_days = flip_counts(本周窗口)['days']`；七天打卡条和 `streak_days` 的日期集合 = 默写日期 ∪ 翻牌日期。
- 周报 `build_facts`：新增 `facts['flip'] = {'days', 'cards'}`（本期窗口）；`calendar_days` 把翻牌日期当作学生有学习的一天（和默写同一档，图例文案在任务 3 改成"默写或翻了错题"）；`quiet` 条件加上"翻了 0 张"；`brief_of` 带上 `flip`（只有天数和张数），`allowed_numbers` 允许这两个数；兜底文字在翻了的时候加一句（例如"这周你翻了 N 天错题卡片，一共 M 张。"）；提示词加一条：可以夸坚持翻错题，只说翻了几天几张，不评价忘了多少。
- 旧数据兼容：`brief_of` 和文字检查读不到 `flip` 时按 0 处理。

- [ ] **Step 1：写测试**：`home_flip_progress_and_days`、`home_streak_counts_flip_days`、`weekly_facts_flip_counts`、`weekly_calendar_marks_flip_day`、`weekly_flip_only_week_not_quiet`、`weekly_brief_without_flip_still_works`（旧 facts）、`weekly_fallback_mentions_flip`、`weekly_prompt_has_flip_rule`
- [ ] **Step 2：确认失败 → 实现 → 跑全部测试**
- [ ] **Step 3：提交** `feat(flip): flip numbers on home and in weekly report`

---

### Task 3：翻一翻页面和入口

**Files:**
- Create: `frontend/src/views/Flip.vue`、`frontend/src/components/flip/`（如 `FlipCard.vue`）、`frontend/src/api/flip.js`（`flipApi.today()`，`cache: false`；`flipApi.record(id, result)`）、纯逻辑模块和 `node --test` 测试
- Modify: `frontend/src/router/index.js`（`/flip`）、`frontend/src/config/features.js`（`FLIP_READY = true`）、`frontend/src/components/home/StudentEntries.vue` / `WeekSummary.vue`（确认按 `flip: {total, done}`、`week.flip_days` 显示正确：今天这组 N 张 / 今天翻完了 / 今天没有要翻的）、周报页 `frontend/src/views/WeeklyReport.vue` 和 `composables/weeklyReport.js`（显示"这周翻了 N 天、M 张"，没有 `flip` 字段的旧周报不显示这一项；日历图例改成"默写或翻了错题"）

- 页面照样稿：卡片正面考点标签（没有考点只写学科名）、题目（`MathText`；只有原图没有题干时直接显示原图）、"你上次写的"（`wrong_answer` 为空时不显示这块）；"想好了，看答案"展开答案和解析；"我记得 / 我忘了"提交后换下一张；翻完显示"今天翻完了"；没有可翻的显示"今天没有要翻的"；顶部显示今天的进度（第几张 / 共几张）。
- 提交时按钮禁用，防止连点翻过两张；提交失败提示并停在当前卡片。
- 手机优先（375 宽），电脑上居中一张卡片；不占手机底部格子（菜单的"更多"和首页大按钮进入）。
- 菜单（`App.vue`）里"学生用"下的翻一翻随 `FLIP_READY` 出现。

- [ ] **Step 1：实现；跑前端测试和构建；375 宽和 1280 宽各看一次**
- [ ] **Step 2：提交** `feat(flip): flip page, menu entry and home/weekly display`

---

### Task 4：发布

- [ ] **Step 1：全部测试；独立审阅整个分支，修掉严重和重要的问题**
- [ ] **Step 2：导出 D1 备份**（照 `docs/cloudflare-migration-status.md` 的"备份与恢复"：`python backend/scripts/export_remote_cloudflare.py <新建备份目录>`，记下文件和 SHA-256）
- [ ] **Step 3：执行迁移 `0017`**（`wrangler d1 execute easyfix --config cloudflare/wrangler.jsonc --remote --file cloudflare/migrations/0017_flip_log.sql --yes`），核对新表为空、其余表行数不变
- [ ] **Step 4：部署 Worker，再发布 Pages**（新接口先上线，前端再打开入口）；核对 `/health`、录入口令读 `/api/flip/today`、`/api/home` 的 `flip` 字段
- [ ] **Step 5：文档**：`docs/cloudflare-api-checklist.md`（两个新接口、`/api/home` 的 `flip`）、`CLAUDE.md`（模块表加 `flip.py`、`flip_model.py`；路由表加 `/flip`；测试命令加 `flip_test.py`）、`docs/cloudflare-migration-status.md` 变更记录、路线图状态行（项目 5 全部上线）；提交、合并、推送
