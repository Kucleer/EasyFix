# 考点卷与手机批改（项目 3）实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 家长点一下就能按考点薄弱程度出一份练习卷（考点卷），打印后在手机上点对错完成批改；错题连对 2 次毕业，考点掌握度和错题清理进度对得上。

**Architecture:** 错题状态和选题规则是纯函数（`targeted_model.py`），读取时现算，不存结果；`targeted.py` 负责取数和接口，考点卷就是一份带 `kind='targeted'` 的练习集，列表、PDF、批改、掌握度都沿用现有通路。掌握度规则在 `mastery_model.py` 里加"没清的错题压上限"和"全部毕业才能变绿"。批改接口改成按差值计数并带版本号。前端新增出卷页和两个批改页，入口替换旧的"生成练习"按钮。

**Tech Stack:** Cloudflare Python Worker（FastAPI）+ D1（SQLite）；PDF Worker（`@cloudflare/puppeteer` + KaTeX）；Vue 3 `<script setup>` + Element Plus。不新增依赖。

**Spec:** `docs/superpowers/specs/2026-11-12-weekly-paper-design.md`（下称"设计"）。设计第 15 节（停用错因）是另一个任务，不在本计划内；本计划不新增任何和错因有关的代码，现有的错因显示不动。

## Global Constraints

- 在执行时所在的工作树和功能分支上做，不直接提交到 `main`。生产代码在 `cloudflare/src/`、`cloudflare/pdf/`、`frontend/src/`；`backend/app/` 是旧代码，不改。
- 数据库结构只追加迁移 `cloudflare/migrations/0015_targeted_paper.sql`，只加列，不改不删已有的列，新列都有默认值或可空；只做软删除，查询必须过滤 `deleted=0`。
- 保持 Workers 免费计划：出卷、状态、批改的 SQL 条数固定，不随题目数或考点数增加；每个 `prepare` / `reroll` 请求最多调用一次模型、一次公式校验；PDF 沿用指纹缓存。
- 常量（设计 4.1、4.4、5.1–5.3），全部写成模块常量：
  - 错题毕业 `GRADUATE_STREAK = 2`；考点 `LEAF_N = 3`、`STEP = 0.15`、`FLOOR = 0.15`、`START = 0.5`、非掌握上限 `0.99`（都已在 `mastery_model.py`，不改数值）。
  - 上限公式：`max(0.15, 1 − 0.15 × 待重做错题数)`。
  - 题量 `SIZE_MIN = 1`、`SIZE_MAX = 90`、第一次预填 `SIZE_DEFAULT = 12`；每个考点 `POINT_CAP = 3`；抽查默认 `SPOT_DEFAULT = 1`。
  - 没批改的卷子占题的期限 `OPEN_PAPER_DAYS = 30`；从没出过考点卷时"新错题"的范围 `NEW_DAYS = 7`。
  - 需要度：薄弱 `3`、一般 `2`、较好 `1`，考点下有新错题再 `+1`。
- 取值（接口、数据库、前端三处一致）：
  - 入选原因 `reason`：`new` 新错题、`wrong` 上次做错、`redo` 旧错题重做、`consolidate` 巩固、`check` 验收、`spot` 抽查。
  - 题面 `form`：`original` 原题、`similar` 相似题。分法 `mode`：`spread` 均布（默认）、`focus` 集中。
  - `practice_set.kind`：`manual`（默认）、`targeted`。考点卷的 `question_type` 是 `mixed`。
  - `skip_reason`：`not_done` 没做、`bad_question` 题目有误。
- "能进卷子的题"口径只写一处（`question_scope.py`），掌握度和选题共用：没删除且已核对、题干不为空、年级不低于默认年级（年级为空算当前年级；默认年级没设置时不按年级筛）。
- 时间用现有的北京时间 `analytics.now()`；时间字符串格式和现有一致（`isoformat(' ')`）。
- 代码规范：`snake_case`，函数前中文文档字符串，复杂逻辑中文行内注释；前端 Composition API + `<script setup>` + Element Plus；页面文字用中文，界面上说"学生"不说"孩子"。
- 不提交 `frontend/dist`、`tmp/`、`backups/`。不连接正式环境、不运行 Wrangler，Task 13 除外且每一步要用户同意。
- 每个任务结束前跑一遍已有测试，不能变红：`python cloudflare/scripts/starmap_test.py`、`intake_test.py`、`scan_test.py`、`knowledge_invariants_test.py`、`local_dev_server_test.py`、`phrase_focus_test.py`。

## Review Focus

1. 应用没设置默认年级（`runtime_config` 里 `app.default_grade` 为空）：不按年级筛题，不报错（Task 2 `test_gate_without_default_grade`、Task 5 `test_plan_without_default_grade`）。
2. 这一科没有任何能出的题（新学科，或错题全部毕业且没有已掌握的考点）：`plan` 返回空清单和 `shortfall = 题量`，不报 500；创建空卷返回 422（Task 3 `test_plan_empty_candidates`、Task 5 `test_plan_and_create_with_nothing_to_pick`）。
3. 题量很小而抽查数不小（题量 1、抽查 1）：抽查最多占题量的一半（向下取整），题量 1 时不抽查，那一道题留给最需要练的考点（Task 3 `test_spot_takes_at_most_half`）。
4. 模型返回空题目、空答案或公式校验不过：`prepare` 返回 502，那一行保持"未准备"，再次调用可以重试；带 `fallback` 调用后改成原题、剩余数减一（Task 5 `test_prepare_failure_keeps_item_pending_then_fallback`）。
5. 卷子已删除或已批改后还来 `prepare` / `reroll`，或批改提交里带了不属于这份卷子的题：分别返回 404、409、422，不写入任何数据（Task 5 `test_prepare_and_reroll_reject_closed_paper`、Task 6 `test_grading_rejects_foreign_item`）。

---

## 文件结构

| 文件 | 职责 |
|------|------|
| `cloudflare/migrations/0015_targeted_paper.sql` | 新增 7 个列（Task 1） |
| `cloudflare/src/question_scope.py` | 加"能进卷子的题"的两个条件函数（Task 2） |
| `cloudflare/src/mastery_model.py` | 掌握度新规则（Task 2） |
| `cloudflare/src/starmap.py` | 取数时带上题号、题号顺序、是否算数；节点多返回三个字段（Task 2） |
| `cloudflare/src/targeted_model.py` | 纯函数：错题状态、入选原因、选题（Task 3） |
| `cloudflare/src/prompts.py`、`similar.py` | 新提示词、保存解析、复用规则（Task 4） |
| `cloudflare/src/targeted.py` | 接口：状态、选题、创建、准备相似题、换一道（Task 5） |
| `cloudflare/src/practices.py` | 详情返回新列；批改按差值计数（Task 5、6） |
| `cloudflare/src/pdf.py` | 拆出 `build_payload`，考点卷版式的数据（Task 7） |
| `cloudflare/pdf/targeted-layout.js`、`index.js` | 考点卷的 HTML 版式（Task 7） |
| `cloudflare/scripts/targeted_test.py` | 本计划的后端测试（Task 1–7） |
| `cloudflare/scripts/local_dev_server.py` | 挂上新接口和本机替身（Task 5、7） |
| `cloudflare/scripts/targeted_preflight.py` | 上线前的只读核对（Task 13） |
| `frontend/src/api/targeted.js` | 接口封装（Task 8） |
| `frontend/src/composables/targetedPaper.js`（+ `.test.mjs`） | 前端纯函数：标签、分组、换题、批改标记（Task 8） |
| `frontend/src/views/TargetedPaper.vue` | 出卷页（Task 9） |
| `frontend/src/views/GradeList.vue`、`GradePaper.vue` | 待批改列表、批改一份卷子（Task 10） |
| `frontend/src/router/index.js`、`App.vue`、`views/Home.vue`、`Questions.vue`、`PracticeSets.vue` | 路由和入口（Task 11） |

---

### Task 1: 迁移 0015 与测试骨架

**Files:**
- Create: `cloudflare/migrations/0015_targeted_paper.sql`
- Create: `cloudflare/scripts/targeted_test.py`
- Commit also: `docs/superpowers/specs/2026-11-12-weekly-paper-design.md`、`docs/superpowers/specs/2026-11-10-optimization-roadmap.md`、本计划文件

**Interfaces:**
- Produces（列，后续任务按此读写）：
  - `practice_set.kind TEXT NOT NULL DEFAULT 'manual'`
  - `practice_set.grading_revision INTEGER NOT NULL DEFAULT 0`
  - `practice_set_question.form TEXT`（可空；空表示旧数据，按整份卷子的 `question_type` 判断）
  - `practice_set_question.reason TEXT`、`practice_set_question.knowledge_point_id INTEGER`、`practice_set_question.skip_reason TEXT`（都可空）
  - `similar_question.explanation TEXT`（可空）
- Produces（测试助手，`targeted_test.py`）：
  - `build_db() -> sqlite3.Connection`：`starmap_test.build_database()` 之后再执行 0015。
  - `add_set(c, practice_id, created_at, reviewed_at, items, kind='targeted', deleted=0, subject_id=1)`：`items` 为 `[(错题编号, 做对 True/False/None, 题面 'original'/'similar')]`，`display_order` 按列表顺序；`reviewed_at` 为 `None` 表示还没批改（`reviewed=0`）。
  - `check(name, fn)`、`main()`：和 `starmap_test.py` 同样的登记和汇总写法，失败数作为退出码。

- [ ] **Step 1: 提交设计文档和计划**

```bash
git add docs/superpowers/specs/2026-11-12-weekly-paper-design.md docs/superpowers/specs/2026-11-10-optimization-roadmap.md docs/superpowers/plans/2026-11-12-targeted-paper.md
git commit -m "docs: targeted paper design and plan"
```

- [ ] **Step 2: 写测试骨架和迁移测试**

```python
def test_migration_adds_columns():
    c = build_db()
    cols = lambda t: {r[1] for r in c.execute('PRAGMA table_info(%s)' % t)}
    assert {'kind', 'grading_revision'} <= cols('practice_set')
    assert {'form', 'reason', 'knowledge_point_id', 'skip_reason'} <= cols('practice_set_question')
    assert 'explanation' in cols('similar_question')

def test_migration_defaults_keep_old_rows_valid():
    c = starmap_test.build_database()
    c.execute("INSERT INTO practice_set(id,name,subject_id,deleted) VALUES(1,'旧卷',1,0)")
    c.executescript(MIGRATION_0015.read_text(encoding='utf-8'))
    row = c.execute('SELECT kind,grading_revision FROM practice_set WHERE id=1').fetchone()
    assert (row['kind'], row['grading_revision']) == ('manual', 0)
```

- [ ] **Step 3: 运行，确认失败**：`python cloudflare/scripts/targeted_test.py`，预期迁移文件不存在而失败。
- [ ] **Step 4: 写 `0015_targeted_paper.sql`**：七条 `ALTER TABLE ... ADD COLUMN`，文件头注释写明"只加列，`ALTER` 不能重复执行"。不建索引（数据量小）。
- [ ] **Step 5: 运行，确认通过**：预期 `2 通过，0 失败`。
- [ ] **Step 6: 提交**

```bash
git add cloudflare/migrations/0015_targeted_paper.sql cloudflare/scripts/targeted_test.py
git commit -m "feat: add migration 0015 for targeted papers"
```

---

### Task 2: 掌握度新规则

对应设计 4.4、4.5、9.3。改项目 2 已上线的规则，不迁移数据。

**Files:**
- Modify: `cloudflare/src/question_scope.py`
- Modify: `cloudflare/src/mastery_model.py`
- Modify: `cloudflare/src/starmap.py`（`load_events`、`compute`）
- Test: `cloudflare/scripts/starmap_test.py`（改旧用例、加新用例）

**Interfaces:**
- Produces（`question_scope.py`）：
  - `stem_ready(alias: str) -> str`：题干不为空的 SQL 条件（`parsed_question` 为空时看 `original_text`，去掉首尾空白后不为空）。
  - `grade_ready(alias: str, min_grade: int | None) -> tuple[str, list]`：`min_grade` 为空时返回 `('1=1', [])`；否则返回 `('(a.grade IS NULL OR a.grade>=?)', [min_grade])`。
- Produces（`mastery_model.py`）：
  - 常量 `GRADUATE_STREAK = 2`。删除 `UPPER_FACTOR`、`UPPER_CAP`、`UPPER_RATIO`、`UPPER_CHILD_MIN`。
  - 事件字典新增可选键：`'qid'`（错题编号）、`'order'`（卷面题号顺序，缺省 0）、`'gate'`（这道题是否算数，缺省假）、`'entered'`（错题的录入时间）。**没有 `'qid'` 或 `'gate'` 为假的事件不参与"待重做""毕业"的统计**，其余照常加减——旧测试里不带这些键的事件因此保持原来的结果。
  - `sort_events(events)`：排序键改为 `(at, seq, order)`。
  - `leaf_detail(events) -> dict`：返回 `{'value': float, 'pending': int, 'all_graduated': bool, 'waive_at': str | None}`。`pending` 是算完后待重做的错题数；`all_graduated` 是算数的错题是否全部毕业（一道都没有时为真）；`waive_at` 是最近一次"直接设为掌握"的时间。
  - `leaf_mastery(events) -> float`：等于 `leaf_detail(events)['value']`。
  - `upper_mastery(child_values: list[float], has_unlearned: bool) -> float`：子考点平均值，最高 `0.99`；`child_values` 不为空、全部等于 1、且 `has_unlearned` 为假时返回 `1.0`。
- Produces（`starmap.py`）：
  - `load_events(db, subject_id, student_id=1, min_grade=None)`：错题事件带 `qid`、`entered`（`q.created_at`）、`gate`（`stem_ready('q')` 且 `grade_ready('q', min_grade)`）；练习事件带 `qid`、`order`（`pq.display_order`）、`gate`（同一条件）。SQL 仍是三条。
  - `compute` 先读应用配置拿默认年级，再调 `load_events`；二级节点多返回 `'pending'`、`'all_graduated'`、`'waive_at'`。返回的元组形状不变。

`leaf_detail` 的回放规则（签名和测试定不下来的部分）：

```
value = 0.5；tracked = {}（qid -> {'practised': 假, 'streak': 0}，只收 gate 为真的错题）；answers = []
按 sort_events 的顺序逐条处理：
  错题事件（source 为 'question'）：gate 为真则登记 tracked[qid]；value = clamp(value − 0.15)；answers 追加 'wrong'
  练习事件：gate 为真且 qid 已登记时，practised = 真，做对 streak += 1，做错 streak = 0
            做对且 value 已经是 1：保持 1；否则 value = clamp(value ± 0.15)
            answers 追加结果
            本条是"对"、answers 最近 3 条全对、tracked 里每道题 streak ≥ 2：value = 1
  手动调整 set_mastered：value = 1；waive_at = 本条时间；
            tracked 里 entered 早于本条时间的题：practised = 真，streak = max(streak, 2)
  其他手动调整：value = clamp(value + 幅度)
  每条处理完：pending = tracked 里 practised 为假或 streak 为 0 的题数；
            value = min(value, max(0.15, 1 − 0.15 × pending))
```

`clamp` 沿用现有的 `[0.15, 0.99]`。

- [ ] **Step 1: 写失败的测试**（加到 `starmap_test.py`；`evq(kind, at, qid, source='practice', order=0, entered=None)` 是带 `gate=True` 的事件助手）

```python
def test_gate_example_two_questions():
    """设计 4.4 的例子：A、B 两道错题，三份卷子后点亮。"""
    events = [evq('wrong', '2026-11-01', 1, 'question'), evq('wrong', '2026-11-01', 2, 'question'),
              evq('right', '2026-11-08', 1, order=0), evq('wrong', '2026-11-08', 2, order=1)]
    assert round(leaf_mastery(events), 2) == 0.2
    events += [evq('right', '2026-11-15', 1, order=0), evq('right', '2026-11-15', 2, order=1)]
    assert round(leaf_mastery(events), 2) == 0.5
    events += [evq('right', '2026-11-22', 2)]
    detail = leaf_detail(events)
    assert detail['value'] == 1.0 and detail['pending'] == 0 and detail['all_graduated'] is True

def test_gate_pending_caps_value():
    """8 道错题，3 道连对 2 次毕业，5 道没重做：最多 0.25，不变绿。"""
    events = [evq('wrong', '2026-11-01', q, 'question') for q in range(1, 9)]
    events += [evq('right', '2026-11-0%d' % day, q) for q in (1, 2, 3) for day in (2, 3)]
    detail = leaf_detail(events)
    assert round(detail['value'], 2) == 0.25 and detail['pending'] == 5

def test_gate_new_wrong_on_mastered_drops_to_085():
    events = [evq('wrong', '2026-11-01', 1, 'question')] + [evq('right', '2026-11-0%d' % d, 1) for d in (2, 3, 4)]
    assert leaf_mastery(events) == 1.0
    assert round(leaf_mastery(events + [evq('wrong', '2026-11-05', 2, 'question')]), 2) == 0.85

def test_gate_single_question_needs_check():
    """只有一道错题：错、对、对之后不是绿色；再做对一道验收题才点亮。"""
    events = [evq('wrong', '2026-11-01', 1, 'question'), evq('right', '2026-11-02', 1), evq('right', '2026-11-03', 1)]
    assert round(leaf_mastery(events), 2) == 0.65
    assert leaf_mastery(events + [evq('right', '2026-11-04', 1)]) == 1.0

def test_gate_three_rights_but_not_all_graduated():
    events = [evq('wrong', '2026-11-01', 1, 'question'), evq('wrong', '2026-11-01', 2, 'question'),
              evq('right', '2026-11-02', 1), evq('right', '2026-11-03', 1), evq('right', '2026-11-04', 2)]
    assert leaf_mastery(events) < 1.0
```

再加这些用例（名称和断言）：
- `test_right_at_one_stays_one`：`set_mastered` 之后做对一次，值仍是 `1.0`。
- `test_set_mastered_waives_older_questions`：先有两道错题（`entered` 早于调整），`set_mastered` 后 `value == 1.0`、`pending == 0`、`waive_at` 等于调整时间；之后来一道新错题（`entered` 晚于调整），值是 `0.85`。
- `test_down_small_on_mastered_stays_085`：点亮后 `down_small`，值是 `0.85`，不被改回 1。
- `test_same_paper_orders_by_number`：同一时刻两条练习结果，`order` 小的先算（交换 `order` 后结果不同）。
- `test_events_without_gate_keep_old_behaviour`：不带 `qid` 的"错、错、对、对、对"仍然是 `1.0`。
- `test_upper_all_children_green`：`upper_mastery([1.0, 1.0], False) == 1.0`；`upper_mastery([1.0, 0.99], False) == 0.99`；`upper_mastery([1.0, 1.0], True) == 0.99`；`upper_mastery([], False) == 0.5`。
- `test_gate_ignores_empty_stem_and_lower_grade`（接口层）：一个考点下三道错题，一道题干为空、一道 `grade=5`、一道 `grade=6`，默认年级 6；节点的 `pending == 1`。
- `test_gate_without_default_grade`（接口层）：不设默认年级时，`grade=5` 的题也算，`pending == 2`。

旧用例 `test_upper_rules`、`test_upper_requires_learned_children_good` 按新签名重写；`test_starmap_upper_nodes`、`test_starmap_query_count_is_fixed` 的预期按新规则更新，SQL 条数的断言保持"不随数据量变"。

- [ ] **Step 2: 运行，确认新用例失败**：`python cloudflare/scripts/starmap_test.py`。
- [ ] **Step 3: 实现**：按 Interfaces 改 `question_scope.py`、`mastery_model.py`、`starmap.py`。`mastery_model.py` 文件头的规则说明改成指向本设计 4.4。
- [ ] **Step 4: 运行，确认全部通过**：`python cloudflare/scripts/starmap_test.py`，0 失败。
- [ ] **Step 5: 提交**

```bash
git add cloudflare/src/question_scope.py cloudflare/src/mastery_model.py cloudflare/src/starmap.py cloudflare/scripts/starmap_test.py
git commit -m "feat(mastery): pending wrong questions cap a point, green needs all graduated"
```

---

### Task 3: 错题状态与选题纯函数

对应设计 4.1、5.2、5.3。不读数据库、不读时钟。

**Files:**
- Create: `cloudflare/src/targeted_model.py`
- Test: `cloudflare/scripts/targeted_test.py`

**Interfaces:**
- Consumes: `mastery_model.GRADUATE_STREAK`。
- Produces:
  - 常量：`SIZE_MIN = 1`、`SIZE_MAX = 90`、`SIZE_DEFAULT = 12`、`POINT_CAP = 3`、`SPOT_DEFAULT = 1`、`NEW_DAYS = 7`、`OPEN_PAPER_DAYS = 30`、`NEED = {'weak': 3, 'fair': 2, 'good': 1}`、`REASON_ORDER = ('new', 'wrong', 'redo', 'consolidate', 'check')`、`MODES = ('spread', 'focus')`、`FIGURE_WORDS = ('如图', '图中', '下图', '右图', '上图', '图示')`。
  - `question_state(results, entered, waive_at) -> dict`：`results` 是这道题在练习卷里的结果 `[{'at': str, 'order': int, 'correct': bool}]`（不含没做和题目有误）；返回 `{'state': 'todo' | 'consolidating' | 'graduated', 'streak': int, 'practised': bool, 'last_at': str | None}`。按 `(at, order)` 排序后逐条数连对；`entered` 早于 `waive_at` 时，在时间越过 `waive_at` 的那一刻把 `streak` 提到至少 2、`practised` 置真（和 Task 2 的回放一致）。`streak ≥ 2` 是 `graduated`；`practised` 为假或 `streak == 0` 是 `todo`；其余是 `consolidating`。
  - `reason_of(state, wrong_at, last_paper_at, today, point) -> str | None`：`point` 是 `{'status': str, 'all_graduated': bool}`。已毕业：考点 `mastered` 返回 `'spot'`；考点 `all_graduated` 为真返回 `'check'`；否则 `None`。没练过：`wrong_at` 晚于 `last_paper_at`（`last_paper_at` 为空时，`wrong_at` 不早于 `today` 往前 7 天）返回 `'new'`，否则 `'redo'`。最近一次做错返回 `'wrong'`。其余返回 `'consolidate'`。
  - `form_of(state, reason) -> str`：`reason` 是 `check` 或 `spot`，或 `state['practised']` 为真，返回 `'similar'`；否则 `'original'`。
  - `has_figure(stem, review_reasons) -> bool`：题干含 `FIGURE_WORDS` 任一个，或 `review_reasons`（字符串）里有 `figure_needed`。
  - `plan_paper(questions, points, last_paper_at, today, size, mode, spot_count) -> dict`
    - `questions`：`[{'id', 'point_id'（主考点）, 'wrong_at', 'entered', 'results', 'blocked'（在没批改的卷子里）}]`
    - `points`：`{point_id: {'value', 'status', 'pending', 'all_graduated', 'waive_at'}}`
    - 返回 `{'items': [{'question_id', 'point_id', 'reason', 'form'}], 'reserve': {point_id: [同样形状，最多 5 条]}, 'shortfall': int}`。同样的输入永远得到同样的输出。

`plan_paper` 的步骤（签名和测试定不下来的部分）：

```
1. 每道题：state = question_state(results, entered, points[point_id]['waive_at'])；
   reason = reason_of(...)；blocked 为真、reason 为 None、考点 status 为 'unlearned' 的题不参加。
2. 抽查：名额 = min(spot_count, size // 2)。
   取 reason 为 'spot' 的题，按考点分组，每个考点只留 last_at 最早的一道（没练过的排最前）；
   考点之间也按这道题的 last_at 从早到晚，再按考点编号；取前"名额"道。
3. 其余的题按主考点分组（'spot' 的题不进这一步）。考点内排序：
   REASON_ORDER 的先后 → 'consolidate' 之间 last_at 早的在前，其他原因 wrong_at 晚的在前 → 题号。
   每个考点里 'check' 的题只留第一道。
4. 考点的先后：需要度（NEED.get(status, 0) + 有 'new' 的题再加 1）高的在前 → value 低的在前
   → pending 多的在前 → 最近一道错题 wrong_at 晚的在前 → 考点编号。
5. 发名额，要发的数 = size − 第 2 步实际抽到的数：
   spread：第 r 轮（r = 1、2、3）按考点先后，每个考点发它的第 r 道，发满就停。
   focus ：按考点先后，每个考点发它的前 min(3, 有几道) 道，发满就停。
   还没满：放开每个考点 3 道的上限，按同一种方式继续发，直到发满或没有题。
6. shortfall = size − 实际选出的总数。reserve = 每个考点没被选上的题，按第 3 步的顺序取前 5 条。
7. items 的顺序：先是第 5 步发出的顺序，抽查题排在最后。
```

- [ ] **Step 1: 写失败的测试**

```python
def test_question_state_table():
    """设计 4.1 的表。"""
    r = lambda at, ok, order=0: {'at': at, 'order': order, 'correct': ok}
    assert question_state([], '2026-11-01', None)['state'] == 'todo'
    assert question_state([r('2026-11-02', True), r('2026-11-03', False)], '2026-11-01', None)['state'] == 'todo'
    assert question_state([r('2026-11-02', True)], '2026-11-01', None)['state'] == 'consolidating'
    assert question_state([r('2026-11-02', True), r('2026-11-03', True)], '2026-11-01', None)['state'] == 'graduated'
    again = question_state([r('2026-11-02', True), r('2026-11-03', True), r('2026-11-04', False)], '2026-11-01', None)
    assert again['state'] == 'todo' and again['streak'] == 0 and again['practised'] is True

def test_question_state_waived_by_set_mastered():
    assert question_state([], '2026-11-01', '2026-11-05')['state'] == 'graduated'
    assert question_state([], '2026-11-06', '2026-11-05')['state'] == 'todo'
    r = {'at': '2026-11-07', 'order': 0, 'correct': False}
    assert question_state([r], '2026-11-01', '2026-11-05')['state'] == 'todo'

def test_plan_example_spread_and_focus():
    """设计 5.3 的例子：题量 12、抽查 1，8 个薄弱考点 A–H 各有 3 道没练过的旧错题，另有 1 个已掌握的考点。"""
    questions, points = example_fixture()          # 考点编号 1–8 对应 A–H，掌握度依次 0.15、0.16 … 0.22；考点 9 已掌握
    spread = plan_paper(questions, points, None, '2026-11-12', 12, 'spread', 1)
    assert per_point(spread) == {1: 2, 2: 2, 3: 2, 4: 1, 5: 1, 6: 1, 7: 1, 8: 1, 9: 1}
    focus = plan_paper(questions, points, None, '2026-11-12', 12, 'focus', 1)
    assert per_point(focus) == {1: 3, 2: 3, 3: 3, 4: 2, 9: 1}
    assert spread['items'][-1]['reason'] == 'spot' and spread['shortfall'] == 0
```

再加这些用例（名称和断言）：
- `test_reason_order`：同一个考点下各有一道 `new`、`wrong`、`redo`、`consolidate` 的题，题量 4 时选出的顺序就是这四个原因的顺序；`new` 的 `form` 是 `original`，`wrong` 和 `consolidate` 是 `similar`。
- `test_new_uses_last_paper_time`：`last_paper_at='2026-11-05'` 时，`wrong_at='2026-11-06'` 没练过的是 `new`，`'2026-11-04'` 的是 `redo`；`last_paper_at=None`、`today='2026-11-12'` 时，`'2026-11-05'` 是 `new`，`'2026-11-04'` 是 `redo`。
- `test_spread_many_points`：30 个薄弱考点、题量 12、抽查 1：`per_point` 是先后排在最前的 11 个考点各 1 道，外加 1 道抽查。
- `test_point_order_four_keys`：四组两两只差一个排序键的考点，先后符合第 4 步。
- `test_cap_lifts_when_short`：只有 2 个考点、各 5 道题、题量 9、抽查 0：`spread` 得到 `{1: 5, 2: 4}`，`shortfall == 0`。
- `test_shortfall_when_exhausted`：只有 4 道能出的题、题量 10：选出 4 道，`shortfall == 6`。
- `test_check_only_one_per_point`：一个考点两道已毕业的题、`all_graduated` 为真、状态 `fair`：只出 1 道，原因 `check`，题面 `similar`。
- `test_blocked_and_unlearned_excluded`：`blocked` 为真的题、考点 `status == 'unlearned'` 的题都不出现在 `items` 和 `reserve` 里。
- `test_spot_zero_and_spot_refund`：`spot_count=0` 时没有抽查题；`spot_count=2` 但只有 1 个已掌握的考点时，抽 1 道，其余名额照常分给别的考点。
- `test_spot_takes_at_most_half`：题量 1、抽查 1：选出的那道题原因不是 `spot`；题量 3、抽查 2：抽查 1 道。
- `test_plan_empty_candidates`：`questions=[]`、题量 12：`items == []`、`shortfall == 12`、`reserve == {}`。
- `test_has_figure`：`'如图，AB=3'` 为真；`review_reasons='["figure_needed"]'` 为真；`'计算 1+1'` 为假。
- `test_plan_is_deterministic`：同样的输入调两次，结果相等；把 `questions` 列表倒序再调，结果仍相等。

- [ ] **Step 2: 运行，确认失败**：`python cloudflare/scripts/targeted_test.py`（模块不存在）。
- [ ] **Step 3: 实现 `targeted_model.py`**。
- [ ] **Step 4: 运行，确认通过**。
- [ ] **Step 5: 提交**

```bash
git add cloudflare/src/targeted_model.py cloudflare/scripts/targeted_test.py
git commit -m "feat(targeted): question state and paper selection rules"
```

---

### Task 4: 相似题——新提示词、保存解析、复用规则

对应设计 6.1–6.3、7.3。

**Files:**
- Modify: `cloudflare/src/prompts.py`
- Modify: `cloudflare/src/similar.py`
- Test: `cloudflare/scripts/targeted_test.py`

**Interfaces:**
- Produces（`prompts.py`）：`PromptLibrary()._build_targeted_prompt(question: str, answer: str, subject: str, knowledge_points, figure: bool) -> str`。在现有 `_build_prompt` 的内容上：不给孩子的错误答案（2026-11-12 修订）；`figure` 为真时要求"不依赖图形，条件全部用文字给出"；要求"解析不超过三句话"。返回的 JSON 字段不变（`similar_question`、`similar_answer`、`explanation`）。提示词里不出现错因。
- Produces（`similar.py`）：
  - `create_similar(db, request, original: dict, prompt: str) -> dict`：调模型、校验题目和答案不为空（空则 502）、数学题校验公式（题目、答案、解析）、写入 `similar_question`（含 `explanation`），返回新行。不触发激励。
  - `reusable_similar(db, question_id: int) -> dict | None`：这道错题最新的一道"带解析、没删除、没被任何未删除练习集里未删除的题目行引用"的相似题；没有返回 `None`。按这条规则，进过卷子的相似题永远不会再被复用，所以批改时标了"题目有误"的相似题不需要另外处理。
  - 现有 `generate` 接口改成调用 `create_similar`（提示词仍用 `_build_prompt`），行为不变，只是多存了解析，激励照旧在 `generate` 里触发。

- [ ] **Step 1: 写失败的测试**（用假的 `generate_json` 和假的公式校验替换 `similar.generate_json`、`pdf.validate_math`）

```python
def test_targeted_prompt_content():
    text = PromptLibrary()._build_targeted_prompt('计算 3x+2x', '5x', '数学', [{'name': '合并同类项', 'parent_name': '简单的代数式', 'is_primary': True}], True)
    assert '不依赖图形' in text and '三句话' in text and '简单的代数式 / 合并同类项' in text
    assert '错因' not in text and '错误类型' not in text and '错误答案' not in text
    plain = PromptLibrary()._build_targeted_prompt('计算 3x+2x', '5x', '数学', [], False)
    assert '错误答案' not in plain and '不依赖图形' not in plain

def test_create_similar_stores_explanation():
    row = run(create_similar(db, request, original, 'prompt'))
    assert row['explanation'] == '合并同类项，系数相加。' and row['deleted'] == 0

def test_reusable_similar_rules():
    # 没解析的旧相似题不复用；被一份没删除的卷子用过的不复用；被已删除的卷子用过的可以复用；已删除的相似题不复用
```

再加 `test_create_similar_rejects_empty`：模型返回的 `similar_question` 为空时抛 502，表里没有新行。

- [ ] **Step 2: 运行，确认失败**。
- [ ] **Step 3: 实现**。
- [ ] **Step 4: 运行，确认通过**；再跑 `python cloudflare/scripts/local_dev_server_test.py`，确认旧的相似题接口没坏。
- [ ] **Step 5: 提交**

```bash
git add cloudflare/src/prompts.py cloudflare/src/similar.py cloudflare/scripts/targeted_test.py
git commit -m "feat(similar): targeted prompt with wrong answer, keep explanation, reuse only unused ones"
```

---

### Task 5: 出卷接口

对应设计 5.1、5.4、5.5、6.4、10、11.1。

**Files:**
- Create: `cloudflare/src/targeted.py`
- Modify: `cloudflare/src/practices.py`（`get`）
- Modify: `cloudflare/src/main.py`（在 `practices_router` **之前** `include_router(targeted_router)`）
- Modify: `cloudflare/scripts/local_dev_server.py`（`mount_routers` 挂上新路由；`similar.generate_json` 换成本机的假模型，返回带解析的固定相似题）
- Test: `cloudflare/scripts/targeted_test.py`

**Interfaces:**
- Consumes: Task 2 的 `starmap.compute`（节点里的 `value`、`status`、`pending`、`all_graduated`、`waive_at`）、`question_scope.stem_ready` / `grade_ready`；Task 3 的 `plan_paper`、`question_state`、`has_figure` 和常量；Task 4 的 `create_similar`、`reusable_similar`、`_build_targeted_prompt`。
- Produces（路由前缀 `/api/practice-sets/targeted`；处理函数依次叫 `status(request)`、`plan(request)`、`create(request)`、`prepare(practice_set_id, request)`、`reroll(practice_set_id, request)`，测试直接调用它们）。`prepare` 和 `reroll` 生成相似题时用 `_build_targeted_prompt`，传入 `has_figure(题干, review_reasons)`（不传错误答案）：

| 接口 | 请求 | 返回 |
|------|------|------|
| `GET /status` | — | `{'pending_count': int, 'subjects': [{'subject_id', 'subject_name', 'last_paper': {'id', 'name', 'created_at', 'state', 'accuracy'} \| None}]}`。`pending_count`：最近 30 天内创建、没批改、没删除、`source_type='question'` 的练习集数。`state`：`to_print`（没有 `pdf_path`）、`to_grade`（有 PDF、没批改）、`graded` |
| `POST /plan` | `{'subject_id': int, 'size': int, 'mode': str, 'spot_count': int, 'include_lower_grades': bool}`；`mode` 缺省 `spread`，`spot_count` 缺省 1，`include_lower_grades` 缺省假 | `{'items': [item], 'reserve': {考点编号: [item]}, 'shortfall': int, 'open_paper_count': int, 'last_paper': 同上 \| None}`。`item` = `{'question_id', 'point_id', 'point_name', 'module_id', 'module_name', 'reason', 'form', 'stem'（题干前 120 个字）, 'has_figure'}`。只算不存，不调模型 |
| `POST ''` | `{'subject_id': int, 'name': str \| None, 'items': [{'question_id', 'point_id', 'reason', 'form'}]}` | 201，`practices.get(db, id)` 的详情。名称缺省 `'<学科名>练习卷 <M>月<D>日'` |
| `POST /{id}/prepare` | `{'fallback': bool}`（可不传） | `{'remaining': int, 'item_id': int \| None, 'fallback': bool}`。处理题号最靠前的一道"题面是相似题但还没有相似题"的题：能复用就复用，否则生成一道；`fallback` 为真时不调模型，直接把这道题的题面改成原题 |
| `POST /{id}/reroll` | `{'item_id': int}` | `{'item_id': int, 'similar_text': str, 'similar_answer': str, 'explanation': str}`。旧的相似题软删除，生成一道新的 |

- 校验（都返回中文说明）：
  - `size` 不是 1–90 的整数、`mode` 不在 `MODES`、`spot_count` 不是 0–90 的整数：422。
  - 创建：`items` 不是 1–90 条、题号重复、有题不是这一科"能进卷子的题"（创建时不看年级，因为家长可能开了"包含低年级"）、`point_id` 不是这道题挂的二级考点、`reason` 或 `form` 取值不对：422；有题已经在别的没批改的卷子里（30 天内）：409。
  - `prepare` / `reroll`：卷子不存在或已删除 404；不是考点卷 422；已批改 409；`reroll` 的 `item_id` 不属于这份卷子或它不是相似题 422。
- `plan` 的取数：`starmap.compute` 之外只加两条 SQL——一条取这一科能进卷子的题（主考点、题干、录入时间、错题日期、`review_reasons`；`include_lower_grades` 为真时不加年级条件），一条取这一科错题练习集里的题目行（结果、题号顺序、卷子的批改时间、创建时间、是否批改、`kind`）。从第二条算出每道题的 `results`、`blocked`、上一份考点卷的创建时间、`open_paper_count`。错题日期的取法和 `starmap.load_events` 一致。
- 创建时的题号顺序（`display_order`）：按模块 `sort_order`、模块编号、考点 `sort_order`、考点编号、请求里的先后排序，保证同一模块、同一考点的题挨在一起。
- Produces（`practices.get`）：
  - 每道题多返回 `form`、`reason`、`knowledge_point_id`、`skip_reason`、`explanation`（相似题的解析）、`analysis`（原题的解析）、`number`（从 1 开始的卷面题号）。
  - 题面取相似题的条件改为：这一行有 `similar_question_id`，并且 `form == 'similar'`，或者 `form` 为空且整份卷子的 `question_type == 'similar'`。
  - 练习集多返回 `kind`、`grading_revision`。

- [ ] **Step 1: 写失败的测试**

```python
def test_plan_endpoint_shape_and_reasons():
    """一科里：考点 101 薄弱（两道没练过的旧错题）、考点 102 有一道上次做错的题。"""
    body = run(targeted.plan(request_for(db, {'subject_id': 1, 'size': 3, 'spot_count': 0})))
    assert sorted(i['reason'] for i in body['items']) == ['redo', 'redo', 'wrong'] and body['shortfall'] == 0
    assert all(i['form'] == ('similar' if i['reason'] == 'wrong' else 'original') for i in body['items'])
    first = body['items'][0]
    assert {'question_id', 'point_id', 'point_name', 'module_id', 'module_name', 'reason', 'form', 'stem', 'has_figure'} <= set(first)

def test_create_then_prepare_until_done():
    paper = run(targeted.create(request_for(db, {'subject_id': 1, 'items': items})))
    assert paper['kind'] == 'targeted' and paper['question_type'] == 'mixed' and paper['total_questions'] == 3
    assert [q['number'] for q in paper['questions']] == [1, 2, 3]
    left = run(targeted.prepare(paper['id'], request_for(db, {})))
    assert left['remaining'] == 0 and calls['model'] == 1          # 只有一道相似题要生成，只调一次模型
    detail = run(practices.get(db, paper['id']))
    similar = [q for q in detail['questions'] if q['form'] == 'similar'][0]
    assert similar['question_text'] == '相似题目' and similar['explanation']
```

再加这些用例（名称和断言）：
- `test_plan_excludes_blocked_and_old_open_papers`：在 10 天前创建、没批改的卷子里的题不出现；在 40 天前创建、没批改的卷子里的题可以出现；`open_paper_count == 1`。
- `test_plan_lower_grades_switch`：默认年级 6，`grade=5` 的题默认不出现，`include_lower_grades` 为真时出现；`grade` 为空的题两种情况都出现。
- `test_plan_without_default_grade`：没设默认年级时 `grade=5` 的题出现，不报错。
- `test_plan_and_create_with_nothing_to_pick`：没有任何错题的学科，`plan` 返回 `items == []`、`shortfall == 题量`；`create` 传空清单返回 422。
- `test_plan_query_count_is_fixed`：5 道题和 60 道题时，`plan` 执行的 SQL 条数相同（用 `starmap_test.CountingDB`）。
- `test_create_validations`：题号重复、别的学科的题、待核对的题、`point_id` 不是它的考点、`reason='x'`，各返回 422；题已在没批改的卷子里返回 409；失败后 `practice_set` 表行数不变。
- `test_create_orders_by_module_and_point`：请求里交错给出两个模块的题，创建后同一模块的题题号相连。
- `test_prepare_reuses_unused_similar`：错题已有一道带解析、没用过的相似题时，`prepare` 不调模型。
- `test_prepare_failure_keeps_item_pending_then_fallback`：假模型抛 502 时 `prepare` 返回 502，再调一次仍处理同一道题；带 `{'fallback': True}` 调用后返回 `fallback == True`、`remaining == 0`，那道题 `form == 'original'`。
- `test_reroll_replaces_similar`：`reroll` 后那一行指向新的相似题，旧相似题 `deleted == 1`，`reusable_similar` 不会再返回它。
- `test_prepare_and_reroll_reject_closed_paper`：已删除的卷子 404；已批改的卷子 409；手动组的卷子 422。
- `test_status_endpoint`：一份有 PDF、没批改的考点卷，`state == 'to_grade'`、`pending_count == 1`；40 天前创建、没批改的旧卷不算进 `pending_count`。
- `test_get_keeps_old_sets_working`：旧的整份相似题练习集（`form` 为空、`question_type='similar'`）仍然显示相似题题面；旧的原题练习集显示原题。

- [ ] **Step 2: 运行，确认失败**。
- [ ] **Step 3: 实现** `targeted.py`、改 `practices.get`、在 `main.py` 和 `local_dev_server.py` 里挂路由。
- [ ] **Step 4: 运行，确认通过**：`python cloudflare/scripts/targeted_test.py`、`python cloudflare/scripts/local_dev_server_test.py`、`python -m compileall -q cloudflare/src`。
- [ ] **Step 5: 提交**

```bash
git add cloudflare/src/targeted.py cloudflare/src/practices.py cloudflare/src/main.py cloudflare/scripts/local_dev_server.py cloudflare/scripts/targeted_test.py
git commit -m "feat(targeted): plan, create, prepare and reroll endpoints"
```

---

### Task 6: 批改按差值计数

对应设计 8.2、8.3、9.2、9.3。

**Files:**
- Modify: `cloudflare/src/practices.py`（`reviewed`）
- Test: `cloudflare/scripts/targeted_test.py`

**Interfaces:**
- Consumes: `starmap.compute`（批改前后各算一次）、`targeted_model.question_state`。
- Produces（`POST /api/practice-sets/{id}/mark-reviewed`，只改 `source_type='question'` 的分支；阅读和单词练习的行为不变）：
  - 请求里 `question_results` 的每一条新增可选的 `skip_reason`（`not_done` / `bad_question` / 不传）；`skip_reason` 有值时这道题的结果按"没批改"存（`is_correct` 为空）。新增可选的 `grading_revision`（整数）。
  - 请求里没提到的题：第一次批改时算没批改；已批改过的卷子，保持原来的结果。`is_all_correct` 为真时所有题算对（现有行为）。
  - `grading_revision` 传了且和库里不一致：409，说明"这份卷子刚被批改过，请刷新后再改"，不写入。
  - 错题计数按差值：对每道题比较旧结果和新结果，`review_count` 加减"是否批改过"的变化，`correct_count`、`error_count` 加减各自的变化，结果不小于 0。
  - 练习集：第一次批改写 `reviewed=1`、`review_count=1`、`last_reviewed_at`；之后只更新 `accuracy`、`review_images`、题目行的 `is_correct` 和 `skip_reason`。每次提交 `grading_revision` 加 1。错题的 `last_reviewed_at` 也只在第一次批改时写。
  - 正确率 = 做对的题数 ÷ 有对错结果的题数，保留一位小数；一道有结果的都没有时为空。
  - 激励只在第一次批改时触发。
  - 返回值在现有字段上增加：`'grading_revision': int`、`'points': [{'id', 'name', 'before', 'after'}]`（批改前后状态或掌握度有变化的二级考点，`before` / `after` 是 `{'value', 'status'}`）、`'newly_mastered': int`、`'graduated': [卷面题号]`（这次批改后刚好连对 2 次的题）。

- [ ] **Step 1: 写失败的测试**

```python
def test_grading_is_idempotent_and_counts_delta():
    """三道题：第一次批 对、错、对；原样再提交一次；再把第 2 题改成对。"""
    first = submit(paper_id, [(1, True), (2, False), (3, True)], revision=0)
    assert first['accuracy'] == 66.7 and first['grading_revision'] == 1
    assert counters(2) == (1, 0, 1)                      # (review_count, correct_count, error_count)
    stamp = db_value('SELECT last_reviewed_at FROM practice_set WHERE id=?', paper_id)
    again = submit(paper_id, [(1, True), (2, False), (3, True)], revision=1)
    assert counters(2) == (1, 0, 1) and again['grading_revision'] == 2
    fixed = submit(paper_id, [(1, True), (2, True), (3, True)], revision=2)
    assert counters(2) == (1, 1, 0) and fixed['accuracy'] == 100.0
    assert db_value('SELECT review_count FROM practice_set WHERE id=?', paper_id) == 1
    assert db_value('SELECT last_reviewed_at FROM practice_set WHERE id=?', paper_id) == stamp

def test_grading_stale_revision_conflicts():
    submit(paper_id, [(1, True)], revision=0)
    expect_http_error(409, mark(paper_id, [(1, False)], revision=0))
    assert counters(1) == (1, 1, 0)
```

再加这些用例（名称和断言）：
- `test_grading_skip_reasons`：一道题 `not_done`、一道 `bad_question`、一道做对：正确率 `100.0`；两道跳过的题 `is_correct` 为空、`skip_reason` 存下、错题计数不变；`starmap.load_events` 里没有这两道题的练习事件。
- `test_grading_skip_then_correct`：先标 `not_done`，再改成做对：`review_count` 从 0 变 1，`skip_reason` 清空。
- `test_grading_without_revision_still_works`：不带 `grading_revision`（电脑旧弹窗）可以提交，版本号照样加 1。
- `test_grading_partial_payload_keeps_others`：已批改的卷子只提交一道题的修改，其他题结果不变。
- `test_grading_rejects_foreign_item`：结果里带了不属于这份卷子的题号，或 `is_correct` 不是布尔值，或 `skip_reason='x'`：422，库里没有任何变化。
- `test_grading_motivation_only_first_time`：两次提交，激励的 `trigger` 只被调用一次（用假的 `motivation.trigger` 计数）。
- `test_grading_reports_changes`：批改后返回的 `points` 里有主考点的前后状态；一道题从"连对 1 次"变成"连对 2 次"时，它的卷面题号出现在 `graduated` 里；考点点亮时 `newly_mastered == 1`。
- `test_grading_reading_and_word_sets_unchanged`：阅读练习的批改照旧按次数加一，返回里没有 `points`。

- [ ] **Step 2: 运行，确认失败**。
- [ ] **Step 3: 实现**：改 `reviewed`。知识点编辑（`knowledge_review_statements`）那一段不动。
- [ ] **Step 4: 运行，确认通过**；再跑 `python cloudflare/scripts/starmap_test.py` 和 `local_dev_server_test.py`。
- [ ] **Step 5: 提交**

```bash
git add cloudflare/src/practices.py cloudflare/scripts/targeted_test.py
git commit -m "feat(grading): count by delta, revision check, skip reasons"
```

---

### Task 7: 考点卷的 PDF 版式

对应设计 7.1、7.2。

**Files:**
- Modify: `cloudflare/src/pdf.py`
- Create: `cloudflare/pdf/targeted-layout.js`
- Create: `cloudflare/pdf/targeted-layout.test.mjs`
- Modify: `cloudflare/pdf/index.js`
- Modify: `cloudflare/scripts/local_dev_server.py`（`pdf.generate_practice` 的本机替身）
- Test: `cloudflare/scripts/targeted_test.py`

**Interfaces:**
- Consumes: Task 5 的 `practices.get` 详情（`kind`、每题的 `number`、`form`、`reason`、`knowledge_points`、`explanation`、`analysis`、`answer`）。
- Produces（`pdf.py`）：
  - `build_payload(practice: dict) -> dict`：从 `generate_practice` 里拆出来的纯函数。`kind != 'targeted'` 时返回和现在完全相同的内容（`template_version` 仍是 `'2'`，保证旧 PDF 的指纹不变）。
  - 考点卷的内容：

    ```
    {'template_version': '3', 'layout': 'targeted', 'title': 练习集名称, 'code': '#<练习集编号>',
     'groups': [{'title': '一、有理数（3 题）', 'questions': [{'number', 'question_text',
                 'option_a'..'option_d', 'space': 's' | 'm' | 'l'}]}],
     'answers': [{'number', 'answer', 'analysis', 'point': '模块 / 考点', 'form': '原题' | '相似题', 'reason': 中文原因}],
     'footer': '手机上从首页的"专项练习"进待批改，找到 #<练习集编号>'}
    ```

  - 分组按一级模块，组内保持题号顺序；组标题的序号用中文数字"一、二、三…"。`analysis`：相似题用 `explanation`，原题用 `analysis`。`space`：有选项是 `'s'`；否则按答案长度，不超过 20 个字 `'s'`、不超过 80 个字 `'m'`、更长 `'l'`。
  - `generate_practice` 改成调用 `build_payload`，指纹和缓存逻辑不变。
- Produces（`cloudflare/pdf/targeted-layout.js`）：
  - `export function targetedBody(payload, field, escape) -> string`：返回放进 `<body>` 的 HTML。`field(text, label)` 是 `index.js` 里现有的那个登记公式文本并返回占位元素的函数。结构：页眉（标题、`code`、姓名 / 日期 / 用时三条填写线）→ 每组一个 `<section class="group">`（组标题 + 题目；题头只有题号）→ `<section class="answers">`（另起一页，标题"答案与解析（家长用）"，每题一行）→ 页脚提示。
  - `export const TARGETED_STYLE: string`：这套版式的 CSS。留白三档高度 `.space-s{height:15mm}`、`.space-m{height:30mm}`、`.space-l{height:50mm}`；`.answers{break-before:page}`；题目 `break-inside:avoid`。
  - `export function targetedQuestionCount(payload) -> number`。
- `index.js`：`payload.layout === 'targeted'` 时用上面的函数拼页面（题数上限仍是 100，用 `targetedQuestionCount` 数）；否则走原来的分支，一个字符都不改。

- [ ] **Step 1: 写失败的测试**

`targeted_test.py`：

```python
def test_build_payload_targeted():
    payload = pdf.build_payload(paper_detail)             # 两个模块共 3 道题，第 2 道是相似题
    assert payload['template_version'] == '3' and payload['layout'] == 'targeted' and payload['code'] == '#7'
    assert [g['title'] for g in payload['groups']] == ['一、有理数（2 题）', '二、线段与角（1 题）']
    assert [q['number'] for g in payload['groups'] for q in g['questions']] == [1, 2, 3]
    second = payload['answers'][1]
    assert second['form'] == '相似题' and second['analysis'] == '相似题的解析' and second['reason'] == '上次做错'
    assert payload['answers'][0]['analysis'] == '原题的解析'

def test_build_payload_manual_unchanged():
    assert pdf.build_payload(old_detail) == EXPECTED_OLD_PAYLOAD      # 和改动前 generate_practice 发出的内容逐字段相同
```

再加 `test_build_payload_space_sizes`：有选项的题 `'s'`，答案 10 个字 `'s'`、50 个字 `'m'`、200 个字 `'l'`。

`targeted-layout.test.mjs`（`node --test`）：

```js
test('题号连续，分组标题和答案页都在', () => {
  const html = targetedBody(payload, (text, label) => `<i data-label="${label}">${text}</i>`, String)
  assert.ok(html.indexOf('一、有理数（2 题）') < html.indexOf('二、线段与角（1 题）'))
  assert.match(html, /class="answers"/)
  assert.ok(html.includes('答案与解析（家长用）') && html.includes('#7'))
  assert.equal((html.match(/class="question"/g) || []).length, 3)
  assert.ok(!html.includes('知识点：') && !html.includes('ID:'))
})
test('留白档位写进 class', () => { /* space 为 'l' 的题带 space-l */ })
test('题数', () => assert.equal(targetedQuestionCount(payload), 3))
```

- [ ] **Step 2: 运行，确认失败**：`python cloudflare/scripts/targeted_test.py`、`node --test cloudflare/pdf/targeted-layout.test.mjs`。
- [ ] **Step 3: 实现** `pdf.py`、`targeted-layout.js`、`index.js`。
- [ ] **Step 4: 本机替身**：`local_dev_server.py` 把 `pdf.generate_practice` 换成本机函数——调用 `pdf.build_payload`，把内容写成 `<uploads>/practice_sets/<编号>.json`，更新 `practice_set.pdf_path`，返回 `{'pdf_url': '/uploads/practice_sets/<编号>.json'}`。本机没有浏览器渲染，这样可以走通流程并检查版式数据。
- [ ] **Step 5: 运行，确认通过**：两条测试命令，加 `python cloudflare/scripts/local_dev_server_test.py`、`node --check cloudflare/pdf/index.js`。
- [ ] **Step 6: 提交**

```bash
git add cloudflare/src/pdf.py cloudflare/pdf/targeted-layout.js cloudflare/pdf/targeted-layout.test.mjs cloudflare/pdf/index.js cloudflare/scripts/local_dev_server.py cloudflare/scripts/targeted_test.py
git commit -m "feat(pdf): targeted paper layout with grouped questions and answer pages"
```

---

### Task 8: 前端接口封装和纯函数

**Files:**
- Create: `frontend/src/api/targeted.js`
- Create: `frontend/src/composables/targetedPaper.js`
- Create: `frontend/src/composables/targetedPaper.test.mjs`

**Interfaces:**
- Produces（`api/targeted.js`，写法照 `api/starmap.js`，都不走前端短时缓存）：`targetedApi.status()`、`plan(params)`、`create(payload)`、`prepare(id, fallback = false)`、`reroll(id, itemId)`、`detail(id)`（`GET /practice-sets/{id}`）、`generatePdf(id)`、`grade(id, payload)`（`POST /practice-sets/{id}/mark-reviewed`）、`pending()`（`GET /practice-sets`，参数 `source_type=question`、`reviewed=false`、`limit=50`、`start_date` 为 30 天前的日期）、`uploadImages(files)`（`POST /upload/batch-simple`）。
- Produces（`composables/targetedPaper.js`，都是不碰 DOM 的纯函数）：
  - `REASON_LABELS = { new: '新错题', wrong: '上次做错', redo: '旧错题重做', consolidate: '巩固', check: '验收', spot: '抽查' }`、`FORM_LABELS = { original: '原题', similar: '相似题' }`、`MODE_LABELS = { spread: '均布', focus: '集中' }`、`STATE_LABELS = { to_print: '待打印', to_grade: '待批改', graded: '已批改' }`。
  - `groupByModule(items) -> [{ module_id, module_name, items }]`：保持出现的先后。
  - `swapItem(plan, index) -> plan`：把第 `index` 道题换成同一考点备选里的第一道，被换下的题放到该考点备选的末尾；没有备选时原样返回。不改传入的对象。
  - `removeItem(plan, index) -> plan`、`toggleForm(plan, index) -> plan`（原题 ↔ 相似题；原因是 `check`、`spot` 的题不能切成原题，原样返回）。
  - `createPayload(subjectId, name, plan) -> object`：`POST ''` 的请求体。
  - `summary(plan) -> { total, points, similar }`：题数、涉及的考点数、要准备的相似题数。
  - `initialMarks(questions) -> { [题目行编号]: 'right' | 'wrong' | 'not_done' | 'bad_question' }`：没批改过的题默认 `'right'`；批改过的按 `is_correct` 和 `skip_reason` 还原。
  - `toggleMark(mark) -> mark`：`'right'` ↔ `'wrong'`；两种跳过状态点一下回到 `'right'`。
  - `gradePayload(questions, marks, revision) -> object`：`{ question_results: [{ question_id, is_correct, skip_reason }], grading_revision }`；跳过的题 `is_correct` 为 `null`。
  - `countWrong(marks) -> number`。
  - `paperLabel(paper) -> string`：如 `'#128 数学练习卷 11月15日'`。

- [ ] **Step 1: 写失败的测试**（照 `scanPage.test.mjs` 的写法）

```js
test('换一道：用同考点的备选替换，被换下的放到备选末尾', () => {
  const next = swapItem(plan, 0)
  assert.equal(next.items[0].question_id, 21)
  assert.deepEqual(next.reserve[101].map(i => i.question_id), [22, 11])
  assert.equal(plan.items[0].question_id, 11)                 // 不改原对象
})
test('批改标记：默认全对，点一下变错，再点变回来', () => {
  const marks = initialMarks([{ id: 1, is_correct: null }, { id: 2, is_correct: false }, { id: 3, is_correct: null, skip_reason: 'not_done' }])
  assert.deepEqual(marks, { 1: 'right', 2: 'wrong', 3: 'not_done' })
  assert.equal(toggleMark('right'), 'wrong'); assert.equal(toggleMark('wrong'), 'right'); assert.equal(toggleMark('bad_question'), 'right')
})
test('提交内容：跳过的题结果为空并带原因', () => {
  const body = gradePayload([{ id: 1, question_id: 9 }, { id: 2, question_id: 8 }], { 1: 'wrong', 2: 'bad_question' }, 3)
  assert.deepEqual(body, { question_results: [{ question_id: 9, is_correct: false, skip_reason: null }, { question_id: 8, is_correct: null, skip_reason: 'bad_question' }], grading_revision: 3 })
})
```

再加：`groupByModule` 的顺序；`toggleForm` 对 `check` 的题不变；`summary` 的三个数；`swapItem` 没有备选时原样返回；`countWrong`。

- [ ] **Step 2: 运行，确认失败**：`node --test frontend/src/composables/targetedPaper.test.mjs`。
- [ ] **Step 3: 实现**两个文件。
- [ ] **Step 4: 运行，确认通过**。
- [ ] **Step 5: 提交**

```bash
git add frontend/src/api/targeted.js frontend/src/composables/targetedPaper.js frontend/src/composables/targetedPaper.test.mjs
git commit -m "feat(frontend): targeted paper api and helpers"
```

---

### Task 9: 出卷页

对应设计 11.1。

**Files:**
- Create: `frontend/src/views/TargetedPaper.vue`
- Modify: `frontend/src/router/index.js`（路由 `/targeted-paper`，页面标题"出练习卷"）
- Modify: `frontend/src/App.vue`（`currentTitle` 里给 `/targeted-paper` 返回"出练习卷"；不加侧栏菜单）

**Interfaces:**
- Consumes: Task 8 的 `targetedApi` 和 `targetedPaper.js` 的全部函数；现有的 `/api/subjects`、`MathText.vue`、`PageHeading.vue`。
- Produces: 路由 `/targeted-paper`，可带查询参数 `subject_id` 预选学科。

页面行为（实现时照这个做，样式留给实施者，电脑和手机宽度都要能用）：

1. **顶部一行小字**：这一科上一份考点卷的出卷日期和状态（`plan` 返回的 `last_paper`）；`open_paper_count > 0` 时另起一行提醒"还有 N 份没批改"。
2. **设置区**：学科、题量（数字输入，1–90，预填 `last_paper` 的题数，没有就 12）、分法（均布 / 集中，每次打开默认均布）、其中抽查几道（默认 1，可以 0）、"包含低年级的错题"开关（默认关）、"重新选题"按钮。改任何一项都重新调用 `plan`（输入停下 400 毫秒后再调）。
3. **题目清单**：`groupByModule` 分组。每题一行：题干（`MathText` 渲染，最多两行）、考点名、原因标签、"原题 / 相似题"、`has_figure` 时的"有图"标签；操作"换一道""删掉""原题 / 相似题"。`shortfall > 0` 时在清单下方说明"能出的题不够，少出了 N 道"。清单为空时显示"这一科现在没有可以出的题"，并禁用下面的按钮。
4. **底部**：`summary` 的三个数，卷子名称输入框（可留空用默认名），按钮"生成并打印"。
5. **点了以后**：调用 `create`；然后循环调用 `prepare` 直到 `remaining == 0`，显示进度"正在准备相似题 3 / 6"。某次 `prepare` 失败：自动再试一次；还失败就带 `fallback` 调用，并在那道题上标"相似题没生成成功，已改用原题"。
6. **准备完**：清单变成只读的卷面预览（重新取 `detail`）。相似题可以展开看题目、答案、解析，旁边有"换一道相似题"（调 `reroll`）。这一步不能再增删题目。按钮"生成 PDF"（调 `generatePdf`，成功后新窗口打开）和"删掉重出"（确认后软删除这份卷子，回到第 2 步）。
7. 页面刷新后不恢复没创建的清单；已创建的卷子可以从练习中心再次打开生成 PDF。

- [ ] **Step 1: 实现页面和路由**。
- [ ] **Step 2: 构建检查**：`npm run build --prefix frontend`，预期成功；然后 `git checkout -- frontend/dist`（如果构建改动了它）。
- [ ] **Step 3: 本机走查**：`python cloudflare/scripts/local_dev_server.py --frontend-dir <构建目录>` 起本机环境（先按 Task 12 Step 1 的办法准备测试数据），在 1280 宽和 390 宽下各走一遍：改题量和分法后清单重选；换一道、删掉、切换题面；生成并打印的进度；预览里展开相似题、换一道相似题；生成 PDF 后打开的是 Task 7 的 JSON。
- [ ] **Step 4: 提交**

```bash
git add frontend/src/views/TargetedPaper.vue frontend/src/router/index.js frontend/src/App.vue
git commit -m "feat(frontend): targeted paper page"
```

---

### Task 10: 手机批改页

对应设计 8.1–8.3。

**Files:**
- Create: `frontend/src/views/GradeList.vue`
- Create: `frontend/src/views/GradePaper.vue`
- Modify: `frontend/src/router/index.js`（`/grade`、`/grade/:id`）
- Modify: `frontend/src/App.vue`（`currentTitle`：`/grade` 开头返回"待批改"）

**Interfaces:**
- Consumes: Task 8 的 `targetedApi.pending / detail / grade / uploadImages` 和 `initialMarks / toggleMark / gradePayload / countWrong / paperLabel / groupByModule`；现有的图片压缩函数（`Upload.vue` 里的 `shrink_image` 和 `composables/scanPage.js` 的 `needsCompression`、`scaledSize`——把 `shrink_image` 挪进 `scanPage.js` 导出，两个页面共用）；现有接口 `PUT /api/practice-sets/{id}/review-images`。
- Produces: 路由 `/grade`（待批改列表）、`/grade/:id`（批改一份卷子）。

页面行为（按手机 390 宽设计，电脑上也能用）：

**`GradeList.vue`**
- 上半：待批改的卷子（`pending()` 的结果，只显示最近 30 天内创建的），每份一张卡片：`paperLabel`、题数、创建日期，点了进 `/grade/:id`。没有时显示"没有待批改的卷子"。
- 下半：最近批改过的 5 份（`GET /practice-sets`，`source_type=question`、`reviewed=true`、`limit=5`），显示正确率，点了也进 `/grade/:id` 可以改。

**`GradePaper.vue`**
- 进入时取 `detail`。还没批改：从第一步开始；已批改：直接到第二步，顶部显示"已于 M 月 D 日 HH:mm 批改"。
- **第一步 拍照**：`<input type="file" accept="image/*" capture="environment" multiple>`，另有"从相册选"（不带 `capture`）。选中后先压缩（长边 1600，质量 0.8）再上传，上传完调用 `review-images` 保存。可以"跳过"。
- **第二步 点对错**：题号方格按模块分段（有 `knowledge_points` 时用主考点的模块名分段，旧卷子没有就不分段），方格里是卷面题号。默认绿色"对"；点一下变红"错"，再点变回。长按（或点方格右上角的小按钮）打开底部抽屉：显示这道题的题面、答案、解析，以及"没做""题目有误""恢复"三个按钮；标了的方格是灰色。顶部固定显示"做错 X 道 / 共 N 道"。底部按钮"提交"。
- **提交**：调用 `grade`，带进入时读到的 `grading_revision`。返回 409：提示"这份卷子刚被批改过，已为你刷新"，重新取 `detail` 并重置标记。
- **第三步 结果**：正确率；`points` 里变好和变差的考点各列出来（"有理数加减：一般 → 较好"）；`newly_mastered > 0` 时显示"点亮了 N 颗星"，链接到 `/star-map`；`graduated` 不为空时显示"第 3、5 题毕业了"；有做错的题时显示"做错的题会在下一份卷子里换成相似题再出现"。按钮"返回待批改"。

- [ ] **Step 1: 把 `shrink_image` 挪到 `scanPage.js`**（函数名和行为不变），`Upload.vue` 改成从那里引入；跑 `node --test frontend/src/composables/scanPage.test.mjs` 确认没坏。
- [ ] **Step 2: 实现两个页面和路由**。
- [ ] **Step 3: 构建检查**：`npm run build --prefix frontend` 成功。
- [ ] **Step 4: 本机走查**（390 宽）：从列表进一份卷子 → 跳过拍照 → 点两道错、一道标"没做" → 提交看到结果 → 再进同一份卷子看到上次的标记 → 改一道 → 提交成功。另开一个窗口模拟第二个人：两边都打开同一份卷子，一边提交后另一边再提交，看到"刚被批改过"的提示并刷新。再走一遍拍照（电脑上是选文件），确认图片出现在练习中心的详情里。
- [ ] **Step 5: 提交**

```bash
git add frontend/src/views/GradeList.vue frontend/src/views/GradePaper.vue frontend/src/router/index.js frontend/src/App.vue frontend/src/composables/scanPage.js frontend/src/views/Upload.vue
git commit -m "feat(frontend): grade papers on the phone"
```

---

### Task 11: 入口

对应设计 5.5、11.1、11.3、11.4。首页不新增入口。

**Files:**
- Modify: `frontend/src/views/Questions.vue`
- Modify: `frontend/src/views/PracticeSets.vue`
- Modify: `frontend/src/views/Home.vue`

**Interfaces:**
- Consumes: `targetedApi.status()`、路由 `/targeted-paper`、`/grade`。

要做的改动：

- **`Questions.vue`**：顶部"生成练习"按钮改名"出练习卷"，点了跳到 `/targeted-paper`（当前筛选了学科时带上 `subject_id`）。删除"生成练习"弹窗和它的脚本（`generateDialogVisible`、`generateForm`、`showGenerateDialog`、`generatePractice` 等）。勾选后的"打印原题""打印相似题""批量生成相似题"不动。`api/question.js` 里的 `generateFromQuestions` 删掉；后端接口不删。
- **`PracticeSets.vue`**：卡片标题栏右侧加两个控件——主按钮"出练习卷"（跳 `/targeted-paper`），链接"待批改 N"（`N` 来自 `status().pending_count`，为 0 时不显示，点了跳 `/grade`）。列表"名称"列的标签：`kind === 'targeted'` 显示"考点卷"，否则保持现在的"原题 / 相似题"。考点卷那一行的"批改"操作改成跳到 `/grade/:id`（已批改的也可以点，文字是"改批改"）；其他练习集的批改弹窗不动。
- **`Home.vue`**：快捷入口里"专项练习"那一格，`pending_count > 0` 时链接指向 `/grade`、右边的小字是"N 份待批改 →"；否则保持现在的 `/practice-sets` 和"进入练习中心 →"。进入首页时调用一次 `status()`，失败时按 0 处理，不提示错误。首页其他部分不动。

- [ ] **Step 1: 实现三处改动**。
- [ ] **Step 2: 检查没有残留**：在 `frontend/src` 里搜 `generateFromQuestions`、`generateDialogVisible`、`generate-from-questions`，预期都没有结果。
- [ ] **Step 3: 构建检查**：`npm run build --prefix frontend` 成功；`node --test frontend/src/composables/*.test.mjs` 全部通过。
- [ ] **Step 4: 本机走查**：错题列表点"出练习卷"进出卷页并带上学科；练习中心页头两个控件；考点卷的标签和"批改"跳转；首页那一格在有和没有待批改时的文字和去向。
- [ ] **Step 5: 提交**

```bash
git add frontend/src/views/Questions.vue frontend/src/views/PracticeSets.vue frontend/src/views/Home.vue frontend/src/api/question.js
git commit -m "feat(frontend): entry points for targeted papers, replace old generate dialog"
```

---

### Task 12: 整条流程走查与文档

**Files:**
- Modify: `cloudflare/scripts/local_dev_server.py`（只在缺测试数据时改 `seed_catalog` / `build_connection`）
- Modify: `docs/cloudflare-api-checklist.md`、`CLAUDE.md`（后端模块表加 `targeted.py`、`targeted_model.py`；路由表加 `/targeted-paper`、`/grade`）
- Modify: `docs/superpowers/specs/2026-11-11-knowledge-starmap-design.md`（第 4 节开头加一句："4.2、4.3 的掌握条件已被 `2026-11-12-weekly-paper-design.md` 的 4.4、4.5 修改，以那份为准。"）
- Modify: `docs/superpowers/specs/2026-11-10-optimization-roadmap.md`（状态行改为项目 3 开发完成待上线；项目 3 的条目按设计第 2、13 节更新：频率和题量手动、不按天数排间隔、连对 2 次毕业、首页不加入口）

- [ ] **Step 1: 准备本机测试数据**：本机环境起来后，通过界面或接口录入 8–10 道数学错题，分在 3 个二级考点下，其中一道题干带"如图"；确认应用默认年级是 6。如果本机环境的种子目录里没有二级考点，在 `seed_catalog` 里补上（只影响本机测试）。
- [ ] **Step 2: 走完整条流程**（电脑 1280 宽出卷，手机 390 宽批改），逐项核对设计：
  1. 出卷页选数学、题量 6、均布、抽查 1 → 清单里的原因和题面符合设计 5.2；"有图"标签出现在带"如图"的题上。
  2. 切到集中 → 清单变成前两个考点各 3 道。
  3. 生成并打印 → 相似题逐道准备 → 预览 → 生成 PDF（本机是 JSON）：分组标题、题号连续、答案页的"原题 / 相似题"和原因都对。
  4. 手机批改：全对提交 → 结果页有考点变化。
  5. 再出一份：上一份里做对的题，原题的变成相似题；刚才的卷子不再占着题。
  6. 第二份里把同一道题再做对 → 结果页提示这道题毕业。
  7. 星空页：有没重做错题的考点不是绿色；错题全部毕业、最近 3 次全对的考点是绿色。
- [ ] **Step 3: 跑全部测试**

```bash
python cloudflare/scripts/targeted_test.py
python cloudflare/scripts/starmap_test.py
python cloudflare/scripts/intake_test.py
python cloudflare/scripts/scan_test.py
python cloudflare/scripts/knowledge_invariants_test.py
python cloudflare/scripts/local_dev_server_test.py
python cloudflare/scripts/phrase_focus_test.py
node --test frontend/src/composables/*.test.mjs cloudflare/pdf/targeted-layout.test.mjs
python -m compileall -q cloudflare/src
```

预期全部通过。

- [ ] **Step 4: 更新文档**，提交

```bash
git add docs CLAUDE.md cloudflare/scripts/local_dev_server.py
git commit -m "docs: targeted paper modules, routes and roadmap status"
```

---

### Task 13: 上线前核对与发布

每一步都要用户同意后再做。命令和顺序以 `docs/cloudflare-migration-status.md` 的"日常部署""备份与恢复"为准。

**Files:**
- Create: `cloudflare/scripts/targeted_preflight.py`
- Modify: `docs/cloudflare-migration-status.md`（新增一节变更记录）

**Interfaces:**
- Produces: `python cloudflare/scripts/targeted_preflight.py --db <本机 SQLite 副本>`。只读，不连接正式环境。打印：
  1. 每一科按旧规则是绿色、按新规则不再是绿色的二级考点（编号、名称、新掌握度、待重做错题数），以及合计几颗。旧规则在脚本里单独实现一小段（最近 3 次全对或手动设为掌握，之后再错往下扣），不依赖已经改掉的代码。
  2. 题干为空的错题数（没删除、已核对）。
  3. 30 天以前创建、一直没批改的错题练习集数；30 天以内的数。
  4. 按新规则，每一科题量 12、均布、抽查 1 时第一份卷子会选到的题（题号、考点、原因）。

- [ ] **Step 1: 写 `targeted_preflight.py`**，用 `targeted_test.py` 的测试库跑一遍确认能出结果；提交。
- [ ] **Step 2: 导出 D1 备份**（用户同意后），在备份副本上执行迁移 0015 演练，核对：各表行数不变，新列默认值正确。
- [ ] **Step 3: 在演练后的副本上跑 `targeted_preflight.py`**，把四项结果给用户看。用户确认可以接受星空颜色的变化后再继续。
- [ ] **Step 4: 执行迁移 0015**（正式 D1）。
- [ ] **Step 5: 部署后端 Worker**，核对 `/health`。
- [ ] **Step 6: 部署 PDF Worker**。
- [ ] **Step 7: 构建并发布前端**。
- [ ] **Step 8: 上线后核对**（登录后）：出一份 6 道题的数学考点卷并生成真实的 PDF，检查分组、题号、留白、公式、答案页；在手机上批改这份卷子；看星空页。用完把这份测试卷删除。
- [ ] **Step 9: 写变更记录**（备份位置和校验值、迁移前后核对、各部署的版本号和上一版本、核对结果、没验证的项），提交。

---

## 不在本计划内

- 停用错因（设计第 15 节），已记入路线图的待办，单独做。
- 电脑端批改弹窗的重做；首页整体版式；周报。
- 让模型凭考点出新题；把图印进 PDF；二维码。
