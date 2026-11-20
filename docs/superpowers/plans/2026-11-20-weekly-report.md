# 每周周报（项目 4）实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 每周日 20:00 自动生成一期"成长打卡"风格的周报：数字由服务端算，文字由模型对孩子写、鼓励为主；失败能自动重来，打开页面能补做。

**Architecture:** 规则放在纯函数模块 `weekly_model.py`（一周怎么算、变化怎么分类、文字怎么检查、兜底文字），`weekly.py` 负责取数、"推进一步"和三个接口，一期存成 `weekly_report` 表的一行（`facts` 和 `text` 两段 JSON）。后端入口加定时入口，周日 20:00–20:50 每 10 分钟调一次"推进一步"；页面发现最近一期没做完时调同一个接口补做。前端把 `facts` 变成 ECharts 配置的逻辑放在 composable 里，页面只管排版。

**Tech Stack:** Cloudflare Python Worker（FastAPI）+ D1（SQLite）+ Cron Trigger + Workers Logs；Vue 3 `<script setup>` + Element Plus + `vue-echarts`（已有依赖）。不新增依赖。

**Spec:** `docs/superpowers/specs/2026-11-20-weekly-report-design.md`（下称"设计"）；样稿 `docs/superpowers/specs/2026-11-20-weekly-report-mockup.html`（版式、图表类型、文字口吻以它为准）。

## Global Constraints

- 在执行时所在的工作树和功能分支（`feature/weekly-report`）上做，不直接提交到 `main`。生产代码在 `cloudflare/src/`、`frontend/src/`；`backend/app/` 是旧代码，不改。
- 数据库只追加迁移 `cloudflare/migrations/0016_weekly_report.sql`，只新建表；只做软删除，查询必须过滤 `deleted=0`。
- 保持 Workers 免费计划：算数字那一步最多 30 条 D1 查询，写文字那一步最多 6 条，条数不随题目数、考点数增加；每期最多调 3 次模型。
- 时间用现有的北京时间 `analytics.now()`。写进数据库和用来比较的时间都是 `YYYY-MM-DD HH:MM:SS`（19 位）；库里现有时间是 26 位带微秒的同一种写法，可以直接按字符串比较。
- 模块常量（设计 5、6、7 节），都写在 `weekly_model.py`：
  - `REPORT_WEEKDAY = 6`（周日，`datetime.weekday()`）、`REPORT_HOUR = 20`。
  - `CALENDAR_DAYS = 42`、`TREND_WEEKS = 6`、`STREAK_LOOKBACK = 26`。
  - `STATUS_ORDER = ('unlearned', 'weak', 'fair', 'good', 'mastered')`。
  - `CHEER_MAX = 30`、`SUMMARY_MAX = 120`、`CAPTION_MAX = 40`、`RECENT_CHEERS = 8`、`TEXT_MAX_ATTEMPTS = 3`。
  - `BANNED_WORDS = ('爸爸', '妈妈', '父母', '家长', '爸妈')`。
  - 单词默写只算 `review_type = 1`。
- `weekly.py` 的常量：认领过期 `STALE_SECONDS = 180`。定时表达式 `*/10 12 * * sun`（UTC）。
- 状态取值三处一致（数据库、接口、前端）：`new`、`facts_ready`、`done`；文字来源 `model`、`fallback`。
- 所有数字只用"系统在 `T_end` 之前已经知道"的数据（设计 5.1 的表）；按条数算的用 `[T_start, T_end)`，按天算的用周一到周日的自然日。
- 文字对学生说、鼓励为主、不出现 `BANNED_WORDS`；页面上叫"下一个要攻克的"，不出现"薄弱"两个字（环形图图例除外，它和知识星空一致）。
- 日志和 `error` 列里不得出现访问口令、会话密钥、模型密钥和模型返回的原文。
- 代码规范：`snake_case`，函数前中文文档字符串，复杂逻辑中文行内注释；前端 Composition API + `<script setup>` + Element Plus；页面文字用中文。开发者是初学者，代码要简单。
- 不提交 `frontend/dist`、`tmp/`、`backups/`。**不连接正式环境、不运行 Wrangler 的部署或远程命令，Task 7 的第 5 步和 Task 10 除外，且每一步都要先得到用户同意。**
- 每个任务结束前跑一遍已有测试，不能变红：
  `python cloudflare/scripts/starmap_test.py`、`targeted_test.py`、`grading_scan_test.py`、`intake_test.py`、`scan_test.py`、`knowledge_invariants_test.py`、`local_dev_server_test.py`、`phrase_focus_test.py`（都在 `cloudflare/scripts/` 下）；
  `node --test frontend/src/composables/*.test.mjs cloudflare/pages/worker.test.mjs`。

## Review Focus

1. 什么都没做的一周（录入、默写、练习卷都是 0）：照样生成一期，`quiet` 为真，文字不硬夸，奖章一枚不显示，页面不报错（Task 4 `test_fallback_quiet_week`、Task 5 `test_facts_quiet_week`、Task 8 `test_badges_hide_zero`）。
2. 模型返回的文字带了没给过的数字、没给过的考点名或"爸爸妈妈"：这次算失败，连续 3 次后用兜底文字，这一期照样 `done`（Task 4 `test_check_text_*`、Task 6 `test_bad_text_falls_back_after_three`）。
3. 定时任务和页面同时推进同一期：只有一边做，另一边拿到 `busy`，不会算两遍、不会建出两条记录（Task 6 `test_advance_claims_once`）。
4. 正好周日 20:00:00 和 19:59:59：前者算本周这一期已到，后者还是上一期（Task 2 `test_week_end_boundaries`）。
5. 只有一个学科有考点数据，或一级模块少于 3 个：不显示学科切换；雷达图换成条形图（Task 8 `test_single_subject_and_few_modules`）。
6. 文本模型还没配置（`generate_json` 抛 503）：和模型失败一样处理，3 次后兜底（Task 6 `test_bad_text_falls_back_after_three` 里的第二种情况）。

---

## File Structure

| 文件 | 责任 |
| --- | --- |
| `cloudflare/migrations/0016_weekly_report.sql`（新） | 建 `weekly_report` 表和唯一索引 |
| `cloudflare/src/weekly_model.py`（新） | 纯函数：时间窗口、连续周数、日历、变化分类、毕业、文字检查、兜底文字 |
| `cloudflare/src/weekly.py`（新） | 取数 `build_facts`、推进一步 `advance`、定时入口 `run_scheduled`、三个接口 |
| `cloudflare/src/prompts.py`（改） | 加 `_build_weekly_report_prompt` |
| `cloudflare/src/main.py`（改） | 注册路由；入口加定时入口 |
| `cloudflare/wrangler.jsonc`（改） | 定时任务、Workers Logs |
| `cloudflare/scripts/weekly_report_test.py`（新） | 以上后端代码的测试 |
| `cloudflare/scripts/local_dev_server.py`（改） | 挂上 `weekly` 路由和假模型 |
| `frontend/src/composables/weeklyReport.js` + `.test.mjs`（新） | `facts` → 奖章、图表配置、标题 |
| `frontend/src/api/weekly_report.js`（新） | 三个接口的封装 |
| `frontend/src/views/WeeklyReport.vue`（新） | 周报页 |
| `frontend/src/views/LearningReports.vue`（改） | 变成"旧报告"页：去掉生成入口 |
| `frontend/src/router/index.js`、`frontend/src/App.vue`（改） | 路由和导航文字 |

`facts` 的结构（Task 5 产出，Task 4、6、8、9 使用；键名以此为准）：

```json
{
  "schema_version": 1,
  "week": {"start": "2026-11-15 20:00:00", "end": "2026-11-22 20:00:00",
           "monday": "2026-11-16", "sunday": "2026-11-22", "number": 6},
  "quiet": false,
  "entries": {"count": 72, "prev_count": 58, "streak_weeks": 4,
              "by_subject": [{"subject_id": 1, "name": "数学", "count": 72}]},
  "calendar": [{"date": "2026-10-12", "entered": false, "dictated": true}],
  "dictation": {"count": 70, "correct": 34, "accuracy": 48.6, "days": 4,
                "prev_count": 250, "prev_accuracy": 49.6,
                "trend": [{"monday": "2026-10-12", "count": 25, "accuracy": 36.0}]},
  "practice": {"papers": 0, "questions": 0, "correct": 0, "accuracy": null,
               "prev_papers": 4, "prev_accuracy": 51.6, "graduated": 0},
  "subjects": [{"subject_id": 1, "name": "数学",
                "status_counts": {"mastered": 5, "good": 0, "fair": 8, "weak": 35, "unlearned": 27},
                "improved": [{"id": 101, "name": "合并同类项"}], "dropped": [], "new_weak": [],
                "modules": [{"id": 100, "name": "整式", "before": 0.4, "after": 0.52}],
                "target": {"id": 102, "name": "去括号"}}]
}
```

- `calendar` 固定 42 项，从早到晚；`trend` 固定 6 项，从早到晚，最后一项是本周；没有记录的周 `count` 为 0、`accuracy` 为 `null`。
- 正确率是百分数，保留 1 位小数；分母为 0 时是 `null`。
- `subjects` 只含有二级考点的学科，按学科编号从小到大排；`target` 没有时是 `null`；`improved`、`dropped`、`new_weak` 各最多 5 个。

`text` 的结构（Task 4、6 产出，Task 9 使用）：

```json
{"cheer": "…", "summary": "…",
 "captions": {"calendar": "…", "points": {"1": "…"}, "dictation": "…", "practice": "…"}}
```

`captions.points` 的键是学科编号的字符串，`facts.subjects` 里的每个学科都要有一句。

---

### Task 1: 迁移 0016 和测试脚本骨架

**Files:**
- Create: `cloudflare/migrations/0016_weekly_report.sql`
- Create: `cloudflare/scripts/weekly_report_test.py`

**Interfaces:**
- Produces: 表 `weekly_report(id, student_id, week_end, status, step_started_at, facts, text, text_source, attempts, error, created_at, updated_at, deleted)`；测试助手 `build_db()`（`targeted_test.build_db()` 的库再执行迁移 0016）、`TESTS` 列表和 `main()`（写法照抄 `targeted_test.py` 末尾）。

- [ ] **Step 1: 写失败的测试** `test_migration_creates_weekly_report`

```python
c = build_db()
columns = {row[1] for row in c.execute('PRAGMA table_info(weekly_report)')}
assert columns == {'id', 'student_id', 'week_end', 'status', 'step_started_at', 'facts', 'text',
                   'text_source', 'attempts', 'error', 'created_at', 'updated_at', 'deleted'}
insert = ("INSERT INTO weekly_report(week_end,created_at,updated_at) "
          "VALUES('2026-11-22 20:00:00','2026-11-22 20:00:05','2026-11-22 20:00:05')")
c.execute(insert)
row = c.execute('SELECT student_id,status,attempts,deleted FROM weekly_report').fetchone()
assert tuple(row) == (1, 'new', 0, 0)
try:
    c.execute(insert)            # 同一个学生同一期不能有两条
    assert False, '应该被唯一索引拦住'
except sqlite3.IntegrityError:
    pass
c.execute('UPDATE weekly_report SET deleted=1')
c.execute(insert)                # 软删除之后可以再建
```

- [ ] **Step 2: 运行确认失败** `python cloudflare/scripts/weekly_report_test.py`，预期 FAIL（迁移文件不存在）。
- [ ] **Step 3: 写迁移。** `student_id INTEGER NOT NULL DEFAULT 1`、`status TEXT NOT NULL DEFAULT 'new'`、`attempts INTEGER NOT NULL DEFAULT 0`、`deleted INTEGER NOT NULL DEFAULT 0`，`week_end`、`created_at`、`updated_at` 非空，其余可空；`CREATE UNIQUE INDEX idx_weekly_report_week ON weekly_report(student_id, week_end) WHERE deleted=0`。文件开头用中文注释写明用途和"只新建表"。
- [ ] **Step 4: 运行确认通过**，再跑一遍 Global Constraints 里的已有测试。
- [ ] **Step 5: Commit** `feat(weekly): add weekly_report table`

---

### Task 2: 一周怎么算（纯函数）

**Files:**
- Create: `cloudflare/src/weekly_model.py`
- Test: `cloudflare/scripts/weekly_report_test.py`

**Interfaces:**
- Produces:
  - `week_end_before(moment: datetime) -> datetime`：不晚于 `moment` 的最近一个周日 20:00:00。
  - `window(week_end: datetime) -> dict`：`{'start', 'end', 'prev_start', 'monday', 'sunday'}`，前三个是 19 位时间字符串，后两个是 `YYYY-MM-DD`。
  - `week_starts(week_end: datetime, count: int) -> list[str]`：往前共 `count` 个窗口的开始时刻，从早到晚，最后一个是本周的 `start`。
  - `entry_streak(counts: list[int]) -> int`：`counts` 从本周往前排，返回开头连续大于 0 的个数。
  - `calendar_days(sunday: str, entered: set[str], dictated: set[str]) -> list[dict]`：`CALENDAR_DAYS` 项 `{'date', 'entered', 'dictated'}`，从早到晚，最后一项是 `sunday`。
  - `percent(correct: int, total: int) -> float | None`：1 位小数，`total` 为 0 返回 `None`。

- [ ] **Step 1: 写失败的测试**

```python
def test_week_end_boundaries():
    at = lambda text: datetime.strptime(text, '%Y-%m-%d %H:%M:%S')
    assert week_end_before(at('2026-11-22 20:00:00')) == at('2026-11-22 20:00:00')   # 正好 20:00 算这一期到了
    assert week_end_before(at('2026-11-22 19:59:59')) == at('2026-11-15 20:00:00')
    assert week_end_before(at('2026-11-25 09:00:00')) == at('2026-11-22 20:00:00')   # 周三补做
    assert week_end_before(at('2027-01-03 20:10:00')) == at('2027-01-03 20:00:00')   # 跨年

def test_window_and_week_starts():
    end = datetime(2026, 11, 22, 20)
    assert window(end) == {'start': '2026-11-15 20:00:00', 'end': '2026-11-22 20:00:00',
                           'prev_start': '2026-11-08 20:00:00', 'monday': '2026-11-16', 'sunday': '2026-11-22'}
    assert week_starts(end, 3) == ['2026-11-01 20:00:00', '2026-11-08 20:00:00', '2026-11-15 20:00:00']
    assert window(datetime(2026, 12, 6, 20))['monday'] == '2026-11-30'               # 跨月

def test_streak_calendar_percent():
    assert entry_streak([72, 58, 46, 218, 0, 54]) == 4
    assert entry_streak([0, 5]) == 0 and entry_streak([]) == 0
    days = calendar_days('2026-11-22', {'2026-11-17'}, {'2026-11-17', '2026-10-12'})
    assert len(days) == 42 and days[0]['date'] == '2026-10-12' and days[-1]['date'] == '2026-11-22'
    assert days[0] == {'date': '2026-10-12', 'entered': False, 'dictated': True}
    assert [d for d in days if d['date'] == '2026-11-17'][0] == {'date': '2026-11-17', 'entered': True, 'dictated': True}
    assert percent(34, 70) == 48.6 and percent(0, 0) is None
```

- [ ] **Step 2: 运行确认失败**（`weekly_model` 不存在）。
- [ ] **Step 3: 实现上面六个函数和 Global Constraints 里的常量。** 模块文档字符串照 `mastery_model.py` 的写法：说明这是纯函数、不读数据库、不读时钟。
- [ ] **Step 4: 运行确认通过。**
- [ ] **Step 5: Commit** `feat(weekly): week window rules`

---

### Task 3: 考点变化、"下一个要攻克的"、错题毕业（纯函数）

**Files:**
- Modify: `cloudflare/src/weekly_model.py`
- Test: `cloudflare/scripts/weekly_report_test.py`

**Interfaces:**
- Consumes: `starmap.load_events` 的事件字典（`kind`、`at`、`source`、`entered`、`qid` 等，见 `mastery_model.py` 文档字符串）；`mastery_model.status_of`；`targeted_model.question_state(results, entered, waive_at)`；`targeted.normal_time`。
- Produces:
  - `known_at(event: dict) -> str`：这条事件"系统知道的时间"。`source == 'question'` 用 `entered`，其余用 `at`。
  - `known_before(events: list[dict], cutoff: str) -> list[dict]`：留下 `known_at` 早于 `cutoff` 的事件，顺序不变。
  - `week_activity(events: list[dict], start: str, end: str) -> dict`：`{'right': bool, 'wrong': bool}`。`right`：窗口内知道的练习结果里有做对的；`wrong`：窗口内知道的事件里有新录入的错题或做错的练习结果。手动调整不算。
  - `classify_change(before: str, after: str, activity: dict) -> str | None`：返回 `'improved'`、`'dropped'`、`'new_weak'` 或 `None`，规则见设计 5.2。
  - `pick_target(leaves: list[dict]) -> dict | None`：`leaves` 每项 `{'id', 'name', 'value', 'status', 'pending'}`。
  - `graduated_in_week(histories: dict, start: str, end: str) -> int`：`histories` 是 `{错题编号: {'entered': str, 'waives': [时间字符串], 'results': [{'at', 'order', 'correct'}]}}`，`waives` 是这道题主考点上"直接设为掌握"的各次时间。

- [ ] **Step 1: 写失败的测试**

```python
def test_known_before_uses_entered_for_questions():
    late = {'kind': 'wrong', 'source': 'question', 'at': '2026-11-10', 'entered': '2026-11-23 09:00:00.000000', 'qid': 1}
    paper = {'kind': 'right', 'source': 'practice', 'at': '2026-11-20 18:00:00.000000', 'qid': 2}
    assert known_before([late, paper], '2026-11-22 20:00:00') == [paper]      # 卷子日期早、但录入在之后：不算
    assert known_at(late) == '2026-11-23 09:00:00.000000'

def test_week_activity_and_classify():
    start, end = '2026-11-15 20:00:00', '2026-11-22 20:00:00'
    right = {'kind': 'right', 'source': 'practice', 'at': '2026-11-18 10:00:00.000000'}
    adjust = {'kind': 'adjust', 'source': 'adjust', 'at': '2026-11-18 10:00:00.000000', 'adjust': 'set_mastered'}
    assert week_activity([right], start, end) == {'right': True, 'wrong': False}
    assert week_activity([adjust], start, end) == {'right': False, 'wrong': False}
    assert classify_change('weak', 'fair', {'right': True, 'wrong': False}) == 'improved'
    assert classify_change('weak', 'mastered', {'right': False, 'wrong': False}) is None     # 只有手动调整：不算变好
    assert classify_change('good', 'fair', {'right': False, 'wrong': True}) == 'dropped'
    assert classify_change('good', 'fair', {'right': False, 'wrong': False}) is None
    assert classify_change('unlearned', 'weak', {'right': False, 'wrong': True}) == 'new_weak'
    assert classify_change('unlearned', 'fair', {'right': True, 'wrong': False}) is None
    assert classify_change('fair', 'fair', {'right': True, 'wrong': False}) is None

def test_pick_target():
    leaves = [{'id': 1, 'name': '甲', 'value': 0.35, 'status': 'weak', 'pending': 1},
              {'id': 2, 'name': '乙', 'value': 0.20, 'status': 'weak', 'pending': 0},      # 没有待重做的题：不选
              {'id': 3, 'name': '丙', 'value': 0.35, 'status': 'weak', 'pending': 3},
              {'id': 4, 'name': '丁', 'value': 0.80, 'status': 'good', 'pending': 2}]      # 档位较好：不选
    assert pick_target(leaves)['id'] == 3                                                  # 并列取待重做多的
    assert pick_target([leaves[1], leaves[3]]) is None

def test_graduated_in_week():
    start, end = '2026-11-15 20:00:00', '2026-11-22 20:00:00'
    r = lambda at, correct: {'at': at, 'order': 0, 'correct': correct}
    histories = {
        1: {'entered': '2026-11-01 10:00:00', 'waives': [],                                # 本周连对第 2 次：算
            'results': [r('2026-11-10 10:00:00', True), r('2026-11-18 10:00:00', True)]},
        2: {'entered': '2026-11-01 10:00:00', 'waives': [],                                # 上周就毕业了：不算
            'results': [r('2026-11-05 10:00:00', True), r('2026-11-10 10:00:00', True)]},
        3: {'entered': '2026-11-01 10:00:00', 'waives': ['2026-11-18 10:00:00'], 'results': []},   # 只是被设为掌握：不算
        4: {'entered': '2026-11-01 10:00:00', 'waives': [],                                # 第 2 次做对在 T_end 之后：不算
            'results': [r('2026-11-18 10:00:00', True), r('2026-11-23 10:00:00', True)]},
    }
    assert graduated_in_week(histories, start, end) == 1
```

- [ ] **Step 2: 运行确认失败。**
- [ ] **Step 3: 实现。** `graduated_in_week` 对每道题算两次 `question_state`：每次只传时间早于该时刻的结果，`waive_at` 取早于该时刻的最后一次（没有就是 `None`）；"`end` 时 `graduated`、`start` 时不是，并且窗口内有做对的结果"才计数。结果时间先用 `targeted.normal_time` 统一再比较。
- [ ] **Step 4: 运行确认通过。**
- [ ] **Step 5: Commit** `feat(weekly): point change and graduation rules`

---

### Task 4: 文字检查、兜底文字、提示词

**Files:**
- Modify: `cloudflare/src/weekly_model.py`、`cloudflare/src/prompts.py`
- Test: `cloudflare/scripts/weekly_report_test.py`

**Interfaces:**
- Consumes: File Structure 里的 `facts`、`text` 结构。
- Produces:
  - `brief_of(facts: dict) -> dict`：给模型看的那部分。包含 `week`（`monday`、`sunday`、`number`）、`quiet`、`entries`（`count`、`prev_count`、`streak_weeks`）、`calendar_days_lit`（本周周一到周日亮了几格）、`dictation`（`count`、`accuracy`、`days`、`prev_count`、`prev_accuracy`）、`practice`（全部键）、`improved_total`（各科变好的考点合计）、`subjects`（每科 `subject_id`、`name`、`improved`、`dropped`、`new_weak` 的名字列表、`improved_count`、`dropped_count`、`target` 的名字、名字和前后值都保留的 `modules`）。不含 `calendar` 明细和 `trend`。文字里可能用到的每个数量都必须在 `brief` 里有对应的数字，否则兜底文字过不了自己的检查。
  - `allowed_numbers(brief: dict) -> set[str]`：`brief` 里每个数字的写法；小数同时放原样和四舍五入后的整数；再加上 `monday`、`sunday` 的月和日。`modules` 的前后值不放进去。
  - `allowed_names(brief: dict) -> set[str]`：`subjects` 里出现的所有考点名、模块名、学科名。
  - `check_text(text: object, brief: dict, recent_cheers: list[str]) -> str | None`：通过返回 `None`，否则返回一句简短的中文原因（不含模型原文）。
  - `fallback_text(brief: dict, recent_cheers: list[str]) -> dict`：`text` 结构。
  - `FALLBACK_CHEERS: tuple[str, ...]`：见 Step 3。
  - `PromptLibrary._build_weekly_report_prompt(brief: dict, recent_cheers: list[str]) -> str`。

- [ ] **Step 1: 写失败的测试。** 先在测试文件里写一个助手 `sample_facts()`，返回 File Structure 里那份示例（`calendar` 用 `calendar_days` 生成，本周亮 4 格；`trend` 补满 6 项），以及 `good_text()`：

```python
def good_text():
    return {'cheer': '「合并同类项」被你拿下一截，这周的你更稳了！',
            'summary': '这周你有 4 天坚持默写单词，一共写了 70 条。「合并同类项」变好了，「去括号」下周我们先攻它。',
            'captions': {'calendar': '这周亮了 4 格。', 'points': {'1': '「合并同类项」变亮了。'},
                         'dictation': '默写了 70 条。', 'practice': '这周还没有做练习卷。'}}

def test_check_text_accepts_good():
    assert check_text(good_text(), brief_of(sample_facts()), []) is None

def test_check_text_rejects():
    brief = brief_of(sample_facts())
    def broken(change):
        text = good_text(); change(text); return check_text(text, brief, ['上一期的鼓励'])
    assert broken(lambda t: t.update(summary='这周你默写了 5 天。')) is not None                 # 5 不是给过的数字
    assert broken(lambda t: t.update(summary='「因式分解」变好了。')) is not None                # 没给过的考点名
    assert broken(lambda t: t.update(summary='爸爸妈妈也很开心。')) is not None                  # 提到了父母
    assert broken(lambda t: t.update(cheer='上一期的鼓励')) is not None                          # 和最近的重复
    assert broken(lambda t: t.update(cheer='很' * 31)) is not None                               # 超长
    assert broken(lambda t: t['captions'].pop('dictation')) is not None                          # 缺字段
    assert broken(lambda t: t['captions'].update(points={})) is not None                         # 少了学科的那一句
    assert check_text('不是字典', brief, []) is not None
    assert check_text(None, brief, []) is not None

def test_fallback_text_passes_own_check():
    brief = brief_of(sample_facts())
    text = fallback_text(brief, [])
    assert check_text(text, brief, []) is None
    assert text['cheer'] in FALLBACK_CHEERS
    used = list(FALLBACK_CHEERS[:5])
    assert fallback_text(brief, used)['cheer'] not in used                                       # 避开最近用过的

def test_fallback_quiet_week():
    facts = sample_facts()
    facts['quiet'] = True
    facts['entries'].update(count=0, streak_weeks=0)
    facts['dictation'].update(count=0, correct=0, accuracy=None, days=0)
    for day in facts['calendar'][-7:]:
        day.update(entered=False, dictated=False)
    for subject in facts['subjects']:
        subject.update(improved=[], dropped=[], new_weak=[])
    brief = brief_of(facts)
    text = fallback_text(brief, [])
    assert check_text(text, brief, []) is None
    assert '歇' in text['summary']                                                               # 照实说，不硬夸

def test_prompt_carries_rules():
    prompt = PromptLibrary()._build_weekly_report_prompt(brief_of(sample_facts()), ['上一期的鼓励'])
    for needle in ('你', '「」', '阿拉伯数字', '上一期的鼓励', '合并同类项', '去括号'):
        assert needle in prompt
    assert '薄弱' not in prompt
```

- [ ] **Step 2: 运行确认失败。**
- [ ] **Step 3: 实现。**

`check_text` 的检查顺序和规则（设计第 6 节）：结构和类型 → 长度（`CHEER_MAX`、`SUMMARY_MAX`、每句图注 `CAPTION_MAX`，都不能是空串）→ `captions.points` 的键正好是 `brief` 里各学科编号 → 全文不含 `BANNED_WORDS` → 用 `\d+(?:\.\d+)?` 找出的每个数字都在 `allowed_numbers` 里 → 用 `「([^」]*)」` 找出的每个名字都在 `allowed_names` 里 → `cheer` 不在 `recent_cheers` 里。

兜底鼓励句（**这是给用户过目的原文，改动要先问用户**）：

```python
FALLBACK_CHEERS = (
    '又一周过去了，你走的每一步都算数。',
    '坚持本身就是本事，这周你又做到了。',
    '错题不是麻烦，是你变强的线索。',
    '今天比上周多懂一点，就是进步。',
    '慢一点没关系，方向对了就好。',
    '每改对一道错题，你就多了一块拼图。',
    '你认真的样子，本身就很了不起。',
    '难的题先放一放，回头再看，你会发现自己变厉害了。',
    '这周的努力，都会在以后悄悄帮到你。',
    '一点一点来，星星会一颗一颗亮。',
    '敢面对错题的人，才会越来越稳。',
    '给这周的自己点个赞，下周继续。',
)
```

`fallback_text` 的鼓励句：从第 `(期数 − 1) % 句数` 句开始往后找第一句不在 `recent_cheers` 里的。安静的一周固定用"慢一点没关系，方向对了就好。"（已在最近用过时照上面的办法往后找）。

兜底的总结和图注用下面的句式，按条件拼接（数字都来自 `brief`）：

| 位置 | 条件 | 句式 |
| --- | --- | --- |
| 总结 | 安静的一周 | `这周歇了一下，没关系。下周先从默写几个单词开始吧。` |
| 总结 | 默写天数 > 0 | `这周你有 {days} 天默写了单词，一共 {count} 条。` |
| 总结 | 各科变好的考点合计 > 0 | `有 {n} 个考点变好了。` |
| 总结 | 毕业 > 0 | `有 {n} 道错题毕业了。` |
| 总结 | 有"下一个要攻克的"（取第一个学科的） | `下一个要攻克的是「{name}」。` |
| 总结 | 不安静但以上都不满足 | `这周录了 {count} 道错题，把它们一道道弄懂就好。` |
| 日历 | 亮格 > 0 / 否则 | `这周亮了 {n} 格。` / `这周的格子还空着，下周来点亮。` |
| 考点（每科） | 该科变好 > 0 / 否则 | `有 {n} 颗星星变亮了。` / `这周星星没有变化，下周再来。` |
| 默写 | 条数 > 0 / 否则 | `这周默写了 {count} 条。` / `这周没有默写单词。` |
| 练习卷 | 份数 > 0 / 否则 | `这周做了 {papers} 份练习卷，做对 {correct} 道。` / `这周还没有做练习卷。` |

提示词：照 `prompts.py` 里 `_build_learning_report_prompt` 的写法（范围说明 + JSON 数据 + 硬性要求 + 输出格式）。硬性要求逐条对应设计第 6 节的 7 条规矩，并给出 `text` 的 JSON 格式和三个长度上限；把 `recent_cheers` 列出来并要求不重复；安静的一周（`quiet` 为真）要求照实说。提示词里不用"薄弱"这个词，统一说"下一个要攻克的"。

- [ ] **Step 4: 运行确认通过。**
- [ ] **Step 5: Commit** `feat(weekly): text check, fallback text and prompt`

---

### Task 5: 取数 `build_facts`

**Files:**
- Create: `cloudflare/src/weekly.py`
- Test: `cloudflare/scripts/weekly_report_test.py`

**Interfaces:**
- Consumes: Task 2、3 的函数；`starmap.load_points`、`load_events`、`load_sections`、`learned_ids`、`load_config`、`load_default_grade`；`mastery_model.leaf_detail`、`upper_mastery`、`status_of`；`question_scope.counted`、`current_student_id`；`practices.py` 里给 `question_state` 取数的那条查询（参考写法，不直接调用）。
- Produces: `async def build_facts(db, request, week_end: datetime) -> dict`，返回 File Structure 里的 `facts`（`week.number` 由调用方传入的已有期数决定：`build_facts` 自己查"这个学生 `week_end` 更早的未删除记录数 + 1"）。

- [ ] **Step 1: 写失败的测试。** 建库用 `build_db()`，造数据用 `starmap_test.add_question / add_paper / set_config / request_for` 和 `targeted_test.add_set`；另写一个本文件的小助手 `add_dictation(c, word_id, reviewed_at, correct, review_type=1)`（往 `word_review_log` 插一行，需要时先插一个 `word`）。所有测试的 `week_end = datetime(2026, 11, 22, 20)`。

```python
def test_facts_entries_and_calendar():
    # 本周 2 道（其中一道卷子日期在上周、本周才录入）、上周 1 道、T_end 之后 1 道
    ...
    facts = run(build_facts(db, request, WEEK_END))
    assert facts['week'] == {'start': '2026-11-15 20:00:00', 'end': '2026-11-22 20:00:00',
                             'monday': '2026-11-16', 'sunday': '2026-11-22', 'number': 1}
    assert facts['entries']['count'] == 2 and facts['entries']['prev_count'] == 1
    assert facts['entries']['streak_weeks'] == 2
    assert facts['entries']['by_subject'] == [{'subject_id': 1, 'name': '数学', 'count': 2}]
    lit = [d['date'] for d in facts['calendar'] if d['entered']]
    assert '2026-11-23' not in lit and len(facts['calendar']) == 42

def test_facts_sunday_night_goes_to_next_week_count_but_same_day_cell():
    # 2026-11-15 21:00 默写 3 条：条数算进本周，格子亮在 11-15（上周日）；本周"默写 N 天"不含它
    ...
    assert facts['dictation']['count'] == 3 and facts['dictation']['days'] == 0
    assert [d for d in facts['calendar'] if d['date'] == '2026-11-15'][0]['dictated'] is True

def test_facts_dictation_only_counts_type_one():
    # 本周默写题型 4 条对 3 条，选择题型 2 条：只算前者
    ...
    assert (facts['dictation']['count'], facts['dictation']['correct'], facts['dictation']['accuracy']) == (4, 3, 75.0)
    assert len(facts['dictation']['trend']) == 6 and facts['dictation']['trend'][-1]['count'] == 4

def test_facts_point_changes():
    # 考点 101：上周前录入 2 道错题（薄弱），本周练习卷里做对 → 档位升高 → improved
    # 考点 102：只在本周被"直接设为掌握" → 档位升高但不算 improved
    # 考点 111：本周新录入错题，之前没有记录 → 学过的判断按过滤后的事件
    ...
    math = facts['subjects'][0]
    assert [p['id'] for p in math['improved']] == [101]
    assert math['status_counts']['mastered'] >= 1                      # 手动调整照实显示在环形图里
    leaf_total = len([p for p in starmap_test.SEED_POINTS if p[2] == 1 and p[3] == 2])   # 数学的二级考点数
    assert sum(math['status_counts'].values()) == leaf_total
    assert {m['id'] for m in math['modules']} <= {100, 110, 120}
    assert math['target'] is None or math['target']['id'] != 102

def test_facts_practice_and_graduated():
    # 本周批改 1 份（3 题对 2 题），其中一道是连对第 2 次；上周批改 1 份（2 题对 1 题）
    ...
    assert facts['practice'] == {'papers': 1, 'questions': 3, 'correct': 2, 'accuracy': 66.7,
                                 'prev_papers': 1, 'prev_accuracy': 50.0, 'graduated': 1}

def test_facts_quiet_week():
    facts = run(build_facts(db, request, WEEK_END))                     # 库里只有考点目录
    assert facts['quiet'] is True and facts['entries']['streak_weeks'] == 0
    assert facts['dictation']['accuracy'] is None and facts['practice']['accuracy'] is None
    assert all(not d['entered'] and not d['dictated'] for d in facts['calendar'])

def test_facts_query_budget():
    # 给 db 包一层计数：build_facts 一次最多 30 条查询，并且不随题目数变化
    ...
    assert counted_queries <= 30
```

（`...` 处是用上面列的助手造数据，数据内容已在每个测试的注释里写明。）

- [ ] **Step 2: 运行确认失败。**
- [ ] **Step 3: 实现 `build_facts`。** 取数方式固定如下，保证条数不随数据量增加：
  - 录入：一条查询取 `[本周往前第 STREAK_LOOKBACK 个窗口的开始, T_end)` 内所有计入统计的错题的 `created_at` 和 `subject_id`，在 Python 里分到各周、各天、各学科。
  - 默写：一条查询取 `[日历第一天 00:00 和 TREND_WEEKS 个窗口开始 两者中较早的, T_end)` 内 `review_type=1` 的 `reviewed_at`、`is_correct`，在 Python 里分周、分天。
  - 练习卷：一条查询取 `[prev_start, T_end)` 内批改的错题练习卷的每题结果（`practice_set.source_type='question'`、`reviewed=1`、`deleted=0`，题目行 `deleted=0`、`is_correct` 不为空）。
  - 毕业：一条查询取所有计入统计的错题在练习卷里的结果（带录入时间和主考点），一条取"直接设为掌握"的调整，按题组成 Task 3 的 `histories`。
  - 考点：对每个有二级考点的学科调一次 `load_points`、`load_events`、`load_sections`；配置各读一次。两个时刻各自 `known_before` 之后再调 `learned_ids`、`leaf_detail`、`upper_mastery`。
  - `quiet`：本周录入、默写条数、批改份数都是 0。
- [ ] **Step 4: 运行确认通过。**
- [ ] **Step 5: Commit** `feat(weekly): compute weekly facts`

---

### Task 6: 推进一步和三个接口

**Files:**
- Modify: `cloudflare/src/weekly.py`、`cloudflare/src/main.py`（只注册路由）、`cloudflare/scripts/local_dev_server.py`
- Test: `cloudflare/scripts/weekly_report_test.py`、`cloudflare/scripts/local_dev_server_test.py`

**Interfaces:**
- Consumes: Task 4、5；`settings.generate_json`（在 `weekly.py` 顶部 `from settings import generate_json`，测试和本地开发服务器会替换 `weekly.generate_json`）；`scan.py` 的 `claim_step`（参考写法）。
- Produces:
  - `async def advance_once(request, moment: datetime | None = None) -> dict`：返回 `{'id': int, 'status': str, 'busy': bool}`。`moment` 缺省用 `analytics.now()`。
  - `router = APIRouter(prefix='/api/weekly-reports')`：
    - `GET ''` → `{'items': [{'id', 'number', 'monday', 'sunday', 'status'}], 'due': bool}`，新的在前，最多 60 条，只列 `facts_ready` 和 `done` 的；`due` 表示最近一期不存在或不是 `done`。
    - `GET '/{report_id}'` → `{'id', 'status', 'number', 'monday', 'sunday', 'facts', 'text', 'text_source'}`；`text` 没有时是 `None`；不存在返回 404 `周报不存在`。
    - `POST '/advance'` → `advance_once(request)` 的结果。

- [ ] **Step 1: 写失败的测试。** 用一个可编程的假模型替换 `weekly.generate_json`（记录调用次数，按预设依次返回或抛 `HTTPException`）。

```python
def test_advance_two_steps_then_done():
    first = run(advance_once(request, NOW))
    assert first['status'] == 'facts_ready' and first['busy'] is False and fake.calls == 0
    second = run(advance_once(request, NOW))
    assert second['status'] == 'done' and fake.calls == 1
    assert queries_in_second_step <= 6                               # 给 db 包一层计数，写文字这一步最多 6 条查询
    row = c.execute('SELECT status,text_source,attempts,week_end FROM weekly_report').fetchone()
    assert tuple(row) == ('done', 'model', 0, '2026-11-22 20:00:00')
    third = run(advance_once(request, NOW))
    assert third == {'id': first['id'], 'status': 'done', 'busy': False} and fake.calls == 1   # 做完了不再动
    assert c.execute('SELECT COUNT(*) FROM weekly_report').fetchone()[0] == 1

def test_advance_claims_once():
    # 手工把记录改成"刚被认领"（step_started_at = 现在）：再调返回 busy，不调模型、不重算
    ...
    assert run(advance_once(request, NOW)) == {'id': report_id, 'status': 'facts_ready', 'busy': True}
    # 认领超过 STALE_SECONDS：可以重新认领并做完
    ...
    assert run(advance_once(request, NOW))['status'] == 'done'

def test_bad_text_falls_back_after_three():
    fake.script = [bad_number_text, HTTPException(503, '请先配置文本模型'), HTTPException(502, '文本模型请求失败')]
    run(advance_once(request, NOW))                                  # 算数字
    for expected_attempts in (1, 2):
        assert run(advance_once(request, NOW))['status'] == 'facts_ready'
        assert c.execute('SELECT attempts FROM weekly_report').fetchone()[0] == expected_attempts
    assert run(advance_once(request, NOW))['status'] == 'done'       # 第 3 次失败：用兜底
    row = c.execute('SELECT text_source,attempts,error,text FROM weekly_report').fetchone()
    assert row[0] == 'fallback' and row[1] == 3 and row[2]
    assert 'sk-' not in row[2] and check_text(json.loads(row[3]), brief, []) is None
    assert fake.calls == 3

def test_recent_cheers_are_passed_and_avoided():
    # 先放一期已 done 的旧周报（cheer='旧的鼓励'），假模型第一次返回同一句 → 这次算失败
    ...

def test_list_and_detail():
    # 一期 done、一期只是 new：列表只有前者；due 为 True（最近一期没做完）；详情 404 的文字
    ...

def test_advance_targets_last_ended_week():
    assert run(advance_once(request, datetime(2026, 11, 25, 9)))['status'] == 'facts_ready'
    assert c.execute('SELECT week_end FROM weekly_report').fetchone()[0] == '2026-11-22 20:00:00'
```

- [ ] **Step 2: 运行确认失败。**
- [ ] **Step 3: 实现。**
  - 建记录用 `INSERT ... ON CONFLICT DO NOTHING`（或先查后插并接住唯一索引冲突），保证同一期只有一条。
  - 认领：一条带条件的 `UPDATE ... SET step_started_at=? WHERE id=? AND status=? AND (step_started_at IS NULL OR step_started_at<?) RETURNING id`，没认领到就返回 `busy: True`。每一步做完把 `step_started_at` 清空。
  - 写文字这一步：读最近 `RECENT_CHEERS` 期（`done`、更早的）的 `cheer` → 调模型（`max_tokens` 用默认值）→ `check_text`。失败（模型抛异常或检查不通过）：`attempts + 1`，`error` 写简短原因（模型异常只写状态码和固定说明，不写异常里的任何原文）；`attempts` 达到 `TEXT_MAX_ATTEMPTS` 时当场改用 `fallback_text`，`text_source='fallback'`，状态改 `done`。
  - 算数字这一步出异常：`error` 写异常类型名，状态保持 `new`，清空 `step_started_at`，把异常继续抛出（接口返回 500，定时任务由 Task 7 接住）。
  - `main.py`：`from weekly import router as weekly_router`，`app.include_router(weekly_router)`。
  - `local_dev_server.py`：`ROUTER_MODULES` 加 `'weekly'`；加 `fake_weekly_json`（返回一份能通过 `check_text` 的文字：直接用 `weekly_model.fallback_text` 的结果并把 `cheer` 换成"（假模型）这周也在一点点变好。"），在 `build_app` 里装到 `weekly.generate_json`（给了 `--llm-config` 时用真实模型，写法照 `similar` 那几行）。
  - `local_dev_server_test.py` 加一个测试：`POST /api/weekly-reports/advance` 两次后 `GET /api/weekly-reports` 有一期 `done`。
- [ ] **Step 4: 运行确认通过。**
- [ ] **Step 5: Commit** `feat(weekly): advance step and endpoints`

---

### Task 7: 定时入口和日志配置

**Files:**
- Modify: `cloudflare/src/weekly.py`、`cloudflare/src/main.py`、`cloudflare/wrangler.jsonc`
- Test: `cloudflare/scripts/weekly_report_test.py`

**Interfaces:**
- Consumes: `advance_once`；`auth.maintenance_enabled(request)`。
- Produces: `async def run_scheduled(env) -> str`（返回并 `print` 一行日志）；后端入口同时提供原有 HTTP 行为和 `scheduled(self, controller, env, ctx)`。

- [ ] **Step 1: 写失败的测试**

```python
def test_run_scheduled_advances_and_logs_one_line():
    line = run(run_scheduled(starmap_test.FakeEnv(db)))
    assert line.startswith('weekly ') and '2026-' in line and 'facts_ready' in line and '\n' not in line

def test_run_scheduled_skips_in_maintenance():
    # 维护开关存的是不带引号的原文（auth.maintenance_enabled 直接比较字符串），不能用会转成 JSON 的 set_config
    c.execute("INSERT INTO runtime_config(name,value,deleted,updated_at) VALUES('write_maintenance','on',0,CURRENT_TIMESTAMP)")
    assert 'maintenance' in run(run_scheduled(starmap_test.FakeEnv(db)))
    assert c.execute('SELECT COUNT(*) FROM weekly_report').fetchone()[0] == 0

def test_run_scheduled_never_raises():
    weekly.build_facts = raising_stub                           # 算数字时抛异常
    line = run(run_scheduled(starmap_test.FakeEnv(db)))
    assert 'failed' in line and 'RuntimeError' in line
```

- [ ] **Step 2: 运行确认失败。**
- [ ] **Step 3: 实现 `run_scheduled`。** 用一个只带 `scope = {'env': env}` 的替身对象当请求（类名 `ScheduledRequest`，放在 `weekly.py`），不改 `settings.load`、`generate_json`、`maintenance_enabled` 的签名。日志一行的格式：`weekly <week_end> <做完后的状态或 busy / maintenance / failed <异常类型名>>`。所有异常都接住，只打印类型名。
- [ ] **Step 4: 改后端入口和配置。**
  - `main.py`：让默认入口同时有原来的 HTTP 处理和 `async def scheduled(self, controller, env, ctx)`（里面只调 `await run_scheduled(env)`）。写法以 Cloudflare 官方文档当时的 Python Workers / FastAPI / Cron Triggers 页面为准；改之前先读这几页，不要凭记忆写。
  - `wrangler.jsonc`：加 `"triggers": {"crons": ["*/10 12 * * sun"]}` 和 `"observability": {"enabled": true}`。
- [ ] **Step 5: 验证入口（设计第 11 节的顺序，做到哪一步写进提交说明）。**
  1. 用 Wrangler / pywrangler 的本地运行方式加载真实的 `main.py`：`/health` 返回 200、未登录调 `/api/subjects` 返回 401、定时入口能被本地触发并打印出那一行日志。
  2. 本地跑不起来：**停下来问用户**，同意后部署一个不带任何绑定、不带定时配置的临时测试 Worker，只验证 HTTP 入口和定时入口能并存，验证完删除。
  3. 两条都走不通：告诉用户只能在正式环境"部署即验证、随时回滚"，由用户决定是否继续；如果入口确实无法并存，停下来告诉用户，改用设计第 4 节的方案二，不要自己换。
- [ ] **Step 6: 运行全部测试确认通过。**
- [ ] **Step 7: Commit** `feat(weekly): scheduled entry and worker logs`

---

### Task 8: 前端 composable（`facts` → 奖章和图表配置）

**Files:**
- Create: `frontend/src/composables/weeklyReport.js`、`frontend/src/composables/weeklyReport.test.mjs`

**Interfaces:**
- Consumes: `facts` 结构；`frontend/src/components/starmap/starmapColors.js` 的 `colorOf`、`GREY`（状态颜色和知识星空一致：`mastered` 用 `colorOf(1)`、`good` 用 `colorOf(0.85)`、`fair` 用 `colorOf(0.55)`、`weak` 用 `colorOf(0.15)`、`unlearned` 用 `GREY`）。
- Produces（都是纯函数，返回普通对象）：
  - `weekTitle(facts) -> string`：`第 6 期 · 11 月 16 日 – 22 日`（跨月时后半段也带月份）。
  - `badges(facts) -> [{key, text}]`：`key` 依次是 `streak`、`improved`、`dictation`、`graduated`；文字 `连续 N 周有录入`、`N 个考点变好`、`默写 N 天`、`毕业 N 道`；数值为 0 的不出现。
  - `calendarOption(facts) -> object`：ECharts 日历热力图配置，`series[0].data` 是 `[日期, 值]`，值 1 只默写、2 只录入、3 两样都有，值为 0 的天不放进去。
  - `visibleSubjects(facts) -> array`、`defaultSubjectId(facts) -> number | null`：变化（变好 + 变差）多的学科，一样多时取第一个。
  - `donutOption(subject) -> object`：环形图，`series[0].data` 按 `mastered, good, fair, weak, unlearned` 的顺序，名字 `已掌握、较好、一般、薄弱、还没学`，数量为 0 的不放；中间文字是 `+N`（N 为变好的个数，0 时不显示）。
  - `modulesOption(subject) -> object`：模块数 ≥ 3 时是雷达图（`series[0].type === 'radar'`，两条：上周虚线、本周实线）；少于 3 时是横向条形图（`series[0].type === 'bar'`，两组）；没有模块时返回 `null`。
  - `gaugeOption(facts) -> object | null`：默写正确率仪表盘；`accuracy` 为 `null` 时返回 `null`。
  - `trendOption(facts) -> object`：近 6 周默写条数柱状图，最后一根是本周。
  - `practiceLine(facts) -> string | null`：有批改时 `批改 N 份 · 做对 A / B 道`，没有时 `null`。

- [ ] **Step 1: 写失败的测试**（`node --test frontend/src/composables/weeklyReport.test.mjs`）。测试文件里放一份和 File Structure 示例一致的 `sample()`。

```js
test('标题和奖章', () => {
  const facts = sample()
  assert.equal(weekTitle(facts), '第 6 期 · 11 月 16 日 – 22 日')
  facts.week.monday = '2026-11-30'; facts.week.sunday = '2026-12-06'
  assert.equal(weekTitle(facts), '第 6 期 · 11 月 30 日 – 12 月 6 日')
  assert.deepEqual(badges(sample()).map(b => b.text), ['连续 4 周有录入', '1 个考点变好', '默写 4 天'])
})
test('test_badges_hide_zero：安静的一周一枚奖章都没有', () => {
  const facts = sample()
  facts.entries.streak_weeks = 0; facts.dictation.days = 0; facts.subjects[0].improved = []
  assert.deepEqual(badges(facts), [])
})
test('日历只放亮的格子，值区分三种情况', () => {
  const facts = sample()
  facts.calendar = [{ date: '2026-11-16', entered: true, dictated: false }, { date: '2026-11-17', entered: true, dictated: true },
    { date: '2026-11-18', entered: false, dictated: true }, { date: '2026-11-19', entered: false, dictated: false }]
  assert.deepEqual(calendarOption(facts).series[0].data, [['2026-11-16', 2], ['2026-11-17', 3], ['2026-11-18', 1]])
})
test('环形图顺序固定、0 不放、中间显示变好个数', () => {
  const option = donutOption(sample().subjects[0])
  assert.deepEqual(option.series[0].data.map(d => [d.name, d.value]), [['已掌握', 5], ['一般', 8], ['薄弱', 35], ['还没学', 27]])
  assert.equal(option.title.text, '+1')
})
test('test_single_subject_and_few_modules', () => {
  const facts = sample()
  assert.equal(visibleSubjects(facts).length, 1)
  assert.equal(defaultSubjectId(facts), 1)
  assert.equal(modulesOption(facts.subjects[0]).series[0].type, 'bar')           // 示例只有 1 个模块
  const many = { ...facts.subjects[0], modules: [1, 2, 3].map(id => ({ id, name: '模块' + id, before: 0.3, after: 0.5 })) }
  assert.equal(modulesOption(many).series[0].type, 'radar')
  assert.equal(modulesOption({ ...many, modules: [] }), null)
  assert.equal(defaultSubjectId({ ...facts, subjects: [] }), null)
})
test('默写和练习卷', () => {
  const facts = sample()
  assert.equal(gaugeOption(facts).series[0].data[0].value, 48.6)
  facts.dictation.accuracy = null
  assert.equal(gaugeOption(facts), null)
  assert.equal(trendOption(sample()).series[0].data.length, 6)
  assert.equal(practiceLine(sample()), null)
  const done = sample(); Object.assign(done.practice, { papers: 2, questions: 10, correct: 7 })
  assert.equal(practiceLine(done), '批改 2 份 · 做对 7 / 10 道')
})
```

- [ ] **Step 2: 运行确认失败。**
- [ ] **Step 3: 实现。** 图表的具体样式（尺寸、圆角、字号）照样稿里的 ECharts 配置；文字和线条颜色不写死，由页面传入或读 CSS 变量。
- [ ] **Step 4: 运行确认通过。**
- [ ] **Step 5: Commit** `feat(weekly): chart options composable`

---

### Task 9: 周报页、旧报告页、路由和导航

**Files:**
- Create: `frontend/src/api/weekly_report.js`、`frontend/src/views/WeeklyReport.vue`
- Modify: `frontend/src/views/LearningReports.vue`、`frontend/src/router/index.js`、`frontend/src/App.vue`

**Interfaces:**
- Consumes: Task 6 的三个接口；Task 8 的函数。
- Produces: `weeklyReportApi = { list(), get(id), advance() }`（写法照 `frontend/src/api/learning_report.js`）；路由 `/learning-reports` → `WeeklyReport.vue`，`/learning-reports/legacy` → `LearningReports.vue`。

- [ ] **Step 1: 接口封装和路由。** `advance` 的超时 150000 毫秒（和 `scanApi.advance` 一样）。导航里"学习报告"改成"周报"；`App.vue` 里按路径算标题、判断当前项的地方，让 `/learning-reports/legacy` 也归在"周报"下，标题显示"旧报告"。
- [ ] **Step 2: 周报页 `WeeklyReport.vue`。** 版式、各块顺序、文字位置照样稿：页头（标题 + 上一期 / 下一期）→ 鼓励卡片（`text.cheer`）→ 总结（`text.summary`）→ 奖章 → 打卡日历 + 图注 → 学科切换 + 考点星星 + 各模块 + 图注 + "下一个要攻克的" → 单词默写（仪表盘 + 近 6 周）+ 图注 → 练习卷（一行数字 + 图注）→ 底部两个普通链接"去出一份考点卷"（`/targeted-paper`）和"旧报告"（`/learning-reports/legacy`）。
  - 图表用 `vue-echarts`，按需引入的写法照 `LearningAnalysis.vue`；需要 `HeatmapChart`、`PieChart`、`RadarChart`、`GaugeChart`、`BarChart` 和 `CalendarComponent`、`VisualMapComponent`、`TitleComponent`、`TooltipComponent`、`GridComponent`、`LegendComponent`。
  - 手机单列；宽度大于 768px 时内容区最宽 960px，图表块排两列（判断用 `use_is_mobile`）。
  - 状态是 `facts_ready`（文字还没好）的那一期：图表照常显示，文字的位置留空，不显示占位符。
  - 页面上任何地方都不显示 `text_source`、`error`、`attempts`。
- [ ] **Step 3: 打开页面时补做。** 常量 `ADVANCE_MAX_TRIES = 8`、`ADVANCE_WAIT_MS = 4000`。进入页面：取列表 → 有已生成的期就先显示最新一期 → 如果 `due` 为真，显示一条提示"正在准备这一期周报…"并循环调 `advance`（返回 `done` 就停并刷新列表、显示新的一期；`busy` 或没做完就等 `ADVANCE_WAIT_MS` 再试；请求失败也算一次）。到了次数上限还没好：提示换成"这一期还在准备中，过一会儿再来看"。一期都没有、也补不出来时，页面只显示这句提示和底部两个链接，不报错。
- [ ] **Step 4: 旧报告页。** `LearningReports.vue` 去掉"生成报告"按钮、生成对话框和相关代码，页头标题改成"旧报告"，加一个返回周报的链接；看和删旧报告的功能不动。
- [ ] **Step 5: 验证。**
  - `node --test frontend/src/composables/*.test.mjs` 通过；`python backend/scripts/prepare_cloudflare_frontend.py` 构建通过（按 `docs/cloudflare-migration-status.md` 的说法，不要用会弄脏 `frontend/dist` 的方式构建）。
  - 起本地开发服务器（`python cloudflare/scripts/local_dev_server.py`，用它自带的假模型和演示数据），在浏览器里逐块核对：375 宽和 1280 宽各看一遍；第一次进入能看到"正在准备"并自动出现第一期；上一期 / 下一期在只有一期时不可点；浅色和深色下文字都看得清；控制台没有报错。把看到的和样稿不一致的地方改掉。
- [ ] **Step 6: Commit** `feat(weekly): weekly report page`

---

### Task 10: 文档和上线

**Files:**
- Modify: `CLAUDE.md`、`docs/cloudflare-api-checklist.md`、`docs/cloudflare-migration-status.md`、`docs/superpowers/specs/2026-11-10-optimization-roadmap.md`、`docs/superpowers/specs/2026-11-20-weekly-report-design.md`

上线的每一步都要先得到用户同意；命令以 `docs/cloudflare-migration-status.md` 的"日常部署""备份与恢复"为准。

- [ ] **Step 1: 更新文档。** `CLAUDE.md`：后端模块表加 `weekly.py` / `weekly_model.py`，路由表把 `/learning-reports` 改成周报并加 `/learning-reports/legacy`，常用测试命令加 `weekly_report_test.py`；接口清单加三个新接口；设计文档和路线图的状态行改成"实施完成，待上线"。Commit `docs: weekly report docs`。
- [ ] **Step 2: 请用户审阅分支，合并进 `main`。**（按 superpowers:finishing-a-development-branch。）
- [ ] **Step 3: 核对 Workers Logs 的免费额度。** 读 Cloudflare 官方文档的 Workers Logs 页面，确认当时免费计划仍然包含。不在免费范围内：停下来告诉用户，把 `observability` 从配置里去掉再继续。
- [ ] **Step 4: 导出 D1 备份**到 `backups/weekly_report_release_<时间>/`，记下文件校验值。
- [ ] **Step 5: 执行迁移 `0016`**，核对：`weekly_report` 存在且为空，其余表行数不变。
- [ ] **Step 6: 部署后端 Worker。** 部署前记下当前版本号。部署后立刻核对：`/health` 200、未登录调 `/api/subjects` 401、登录页 200、用录入小工具调一次 `guide` 正常。任何一项不对，马上回滚到上一个版本并告诉用户。
- [ ] **Step 7: 构建并发布 Pages**（从 `main` 构建；Pages 是整站替换）。
- [ ] **Step 8: 补出第一期。** 用录入小工具的口令调 `POST /api/weekly-reports/advance` 直到 `done`（或请用户打开周报页），再 `GET` 一次确认 `facts` 和 `text` 都在。请用户在手机上看一眼这一期。
- [ ] **Step 9: 写发布记录。** 在 `docs/cloudflare-migration-status.md` 末尾加一节：提交、迁移、备份位置、Worker 版本（新旧）、Pages 部署（新旧）、Task 7 第 5 步走到了哪一条、是否开了日志。**"未验证"里写明：真实的定时任务要到上线后的第一个周日 20:20 之后才能验证。** Commit 并按用户的意思推送。
- [ ] **Step 10: 上线后的第一个周日 20:20 之后**，查那一期是否由定时任务生成（Workers Logs 里有 `weekly ...` 的日志行，`weekly_report` 里有那一期且 `done`），把结果补进发布记录。没生成：先看日志和 `error` 列找原因，告诉用户，不要直接改定时配置。
