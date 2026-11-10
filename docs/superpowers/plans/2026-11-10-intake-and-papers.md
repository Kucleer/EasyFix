# 录入规范与卷子记录 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 Claude / Codex 录题只走一条带校验的接口，每道题带上所属卷子、页码、错误答案和核对状态，并给卷子和考试分数一个存放的地方。

**Architecture:** 一次迁移（`0011`）加上用户表、学生表、卷子表和错题表的新列。后端新增三个模块：`intake_model.py`（纯规则）、`intake.py`（录入与核对接口）、`papers.py`（卷子接口），统计口径收敛到 `question_scope.py` 一处。仓库外的录入由 `tools/easyfix-intake/` 下的技能说明和一个只用标准库的小工具完成。前端新增待核对页、卷子列表页和详情页。

**Tech Stack:** Python FastAPI on Cloudflare Workers、D1（SQLite 方言）、R2；Vue 3 + Element Plus + Pinia + Vite；测试用独立 Python 脚本（内存 SQLite）、`python -m unittest`、`node --test`。

**Spec:** `docs/superpowers/specs/2026-11-10-intake-and-papers-design.md`。执行每个任务前先读设计文档里对应的小节，本计划不重复设计文档已经写明的规则原文。

## Global Constraints

- 只改 `cloudflare/src/`、`cloudflare/migrations/`、`cloudflare/scripts/`、`frontend/src/`、`tools/easyfix-intake/`、`AGENTS.md`、`CLAUDE.md`、`docs/`。不改 `backend/app/`，不改 `cloudflare/pdf/`。
- 所有命令在工作树 `D:\code\easyfix\.claude\worktrees\project-optimization-plan-b28c5c` 里执行。不进入、不修改主目录 `D:\code\easyfix`。
- 数据库只追加 `cloudflare/migrations/0011_intake_papers.sql`：只加表、加列、加索引、回填，不改不删现有列。所有新表带 `deleted`，不做硬删除。
- 新列都带默认值：迁移执行后、新代码上线前，旧代码必须仍能正常读写。
- Workers 免费计划：列表和统计用 SQL 聚合，不按记录逐条查询；公式校验整份卷子只调用一次渲染服务。
- 不在本地脚本或 MCP 里写生产数据。任何动正式环境的步骤（导出备份、执行迁移、部署、往用户目录装文件、配置口令）只在 Task 0 和 Task 12 里出现，每一步执行前都要得到用户明确同意。
- 孩子的卷子照片和据此整理的标准答案是私人资料，只放在被忽略的 `tmp/` 下，不提交、不写进任何文档。
- 访问口令不写进仓库、文档、提交说明、对话和命令输出。
- 取值固定：`paper_type` 为 `homework` / `chapter_practice` / `exam`；`exam_kind` 为 `unit` / `midterm` / `final` / `other`；`review_status` 为 `approved` / `pending` / `rejected`；待核对原因为 `wrong_unclear` / `text_unclear` / `kp_unsure` / `other`；`paper.source` 为 `agent` / `manual` / `history`；`SPEC_VERSION = 1`。
- 代码规范：Python 变量 `snake_case`，每个函数前写中文文档字符串，复杂逻辑加中文行内注释；前端用 Composition API + `<script setup>`、Element Plus。
- 面向用户的文字（页面文案、接口报错、小工具输出、技能说明）用直白的中文，不用术语。
- 勤提交：每个任务结束提交一次，只提交本任务的文件，不提交 `frontend/dist/`、`tmp/`、`backups/`。不推送，推送属于 Task 12。

## Review Focus

1. **这个年级没有考点目录**（比如明年升七年级，目录还只有六年级）：题目不能因为"没有主考点"全部掉进待核对，否则队列就成了必经关卡。目录为空时，没有考点的题直接入库为未分类。测试在 Task 2、Task 5。
2. **提交到一半断网后重试**：同一个 `request_id` 再次提交不重复入库，返回第一次的结果。小工具把 `request_id` 写回文件，重试时沿用。测试在 Task 5、Task 8。
3. **照片超过 10 张，或某一张超过 10MB、不是图片**：小工具分批上传并保持页序；任何一张失败就整体失败并说明是哪一张，不能悄悄少一页导致页码错位。测试在 Task 8。
4. **两位家长同时处理同一道待核对的题**：第二个人得到明确的"已经处理过了"提示（409），不会重复通过，也不会把已移除的题又通过。测试在 Task 6。
5. **缓存着旧页面的浏览器保存错题**（请求里不带 `wrong_answer`、`question_no`）：不清空这些新字段，也不改变核对状态。测试在 Task 6。

---

## 文件结构

| 文件 | 责任 |
| --- | --- |
| `cloudflare/scripts/extract_schema.py`（新） | 从 D1 导出文件里抽出只含结构的 SQL |
| `cloudflare/scripts/d1_schema_before_0011.sql`（新） | 迁移前的正式库结构，测试基线，不含数据 |
| `cloudflare/migrations/0011_intake_papers.sql`（新） | 本项目唯一的迁移 |
| `cloudflare/scripts/intake_test.py`（新） | 本项目后端的全部测试 |
| `cloudflare/src/intake_model.py`（新） | 纯规则：常量、卷子与题目的校验、核对状态判定 |
| `cloudflare/src/question_scope.py`（新） | "计入统计的题"这一个条件的唯一出处，以及当前学生 |
| `cloudflare/src/intake.py`（新） | 录入资料、试提交、正式提交、核对动作、待核对计数 |
| `cloudflare/src/papers.py`（新） | 卷子记录的增删改查 |
| `cloudflare/src/questions.py`（改） | 列表筛选、详情多带字段、保存接受两个新字段 |
| `cloudflare/src/knowledge_stats.py`、`analytics.py`、`reports.py`、`practices.py`、`similar.py`（改） | 引用统计口径 |
| `cloudflare/src/auth.py`、`main.py`（改） | 试提交不触发缓存失效；注册新路由 |
| `tools/easyfix-intake/SKILL.md`、`payload-format.md`（新） | 录入规范（给 Claude / Codex 读的技能）和提交文件格式说明 |
| `tools/easyfix-intake/scenarios.md`（新） | 录入规范的测试场景和验证记录，不含照片 |
| `tools/easyfix-intake/easyfix_intake.py`、`install.py`、`test_easyfix_intake.py`（新） | 小工具、安装脚本、两者的测试 |
| `frontend/src/composables/intakeLabels.js`、`intakeLabels.test.mjs`（新） | 代码转中文、分数显示等纯逻辑 |
| `frontend/src/api/paper.js`（新） | 卷子与核对接口的调用 |
| `frontend/src/stores/reviewCount.js`（新） | 待核对题数，首页和导航共用 |
| `frontend/src/views/ReviewQueue.vue`、`Papers.vue`、`PaperDetail.vue`（新） | 三个新页面 |
| `frontend/src/router/index.js`、`App.vue`、`views/Home.vue`、`views/Questions.vue`（改） | 路由、导航、首页入口、错题页的小改动 |

---

### Task 0: 前置核实（不写产品代码）

设计文档要求把两件有风险的事放在最前面验证，并拿到正式库结构。任何一项结论与设计文档不符，停下来告诉用户，不自行改方案。

**Files:**
- Create: `cloudflare/scripts/extract_schema.py`
- Create: `cloudflare/scripts/d1_schema_before_0011.sql`

**Interfaces:**
- Produces: `cloudflare/scripts/d1_schema_before_0011.sql`，Task 1 起所有后端测试用它建库。

- [ ] **Step 1: 征得用户同意后导出正式库**

向用户说明要做的事（只读导出一份完整备份到被忽略的 `backups/` 目录），得到明确同意后执行。命令和本机环境的注意事项见 `docs/cloudflare-migration-status.md` 末尾 2026-11-10 的记录和启动文档"发布时要注意的环境情况"：Wrangler 4.158.0 取自 `D:/code/easyfix-cloudflare-inspect/cloudflare/node_modules`，去掉代理环境变量直连。导出文件放 `backups/intake_<UTC时间>/remote.sql`，记下 SHA-256。不输出临时下载链接。

- [ ] **Step 2: 写 `extract_schema.py` 并生成结构文件**

`python cloudflare/scripts/extract_schema.py <remote.sql> cloudflare/scripts/d1_schema_before_0011.sql`：把导出文件载入内存 SQLite，从 `sqlite_master` 取出所有 `sql` 非空的表、索引、触发器的建立语句（跳过 `sqlite_` 和 `_cf_` 开头的内部对象），按"表 → 索引 → 触发器"的顺序写出，每条以分号结尾。不写任何数据行。

验证：`python -c "import sqlite3;c=sqlite3.connect(':memory:');c.executescript(open('cloudflare/scripts/d1_schema_before_0011.sql',encoding='utf-8').read());print(len(c.execute(\"select name from sqlite_master where type='table'\").fetchall()))"` 能执行并打印表的数量。

- [ ] **Step 3: 核对设计文档 5.2 的表清单**

用结构文件确认：5.2 里要加 `student_id` 的 17 张表（除 `paper`）都存在；它们都没有名为 `student_id` 的列；`question` 没有 5.4 列出的任何新列；不存在名为 `paper`、`student`、`app_user` 的表。同时在导出文件里查 `error_type` 表的行数，以及 `question.error_type` 里出现过、但不在 `error_type` 表里的取值有多少种（只报数量和取值，不改数据）。

把结论写进提交说明。有表不存在或有重名时停下来报告用户。`error_type` 对不上的情况在 Task 5 Step 1 里处理。

- [ ] **Step 4: 核实贴图在本机留有文件**

已知证据：贴进 Claude 桌面版的图片在 `%TEMP%\claude\...\images\` 下，贴进 Codex 的在 `%TEMP%` 下，对话里都带路径；见过的文件是 1080×1920、120–180KB。用户已经贴过五张真实照片：本机留的文件是 1080×1920（160–250KB），有一张是 1500×2000；印刷字清楚，孩子的手写小字有几处认不准。这一步只剩一件事：请用户判断这样的清晰度够不够核对用。

用户认为不够时停下来商量（备选：录题时由用户给出原图所在的文件夹）。

- [ ] **Step 5: 核实用户级技能目录能被读到**

Claude：当前会话是在主目录打开的，技能列表里已有来自 `~/.claude/skills/` 的技能，视为已核实，记一笔即可。Codex：它和其他几种工具共用 `~/.agents/skills/<名称>/SKILL.md`（这台机器上该目录已存在并有别的技能）。查 Codex 的版本和文档确认这一点。确认不了也不阻塞：Task 12 安装时加上 `--codex-pointer`，在 `~/.codex/AGENTS.md` 里放一段指向说明。把结论记进提交说明。

- [ ] **Step 6: Commit**

```bash
git add cloudflare/scripts/extract_schema.py cloudflare/scripts/d1_schema_before_0011.sql
git commit -m "test: add production schema baseline for project 1"
```

---

### Task 1: 迁移 `0011` 与测试基线

**Files:**
- Create: `cloudflare/migrations/0011_intake_papers.sql`
- Create: `cloudflare/scripts/intake_test.py`

**Interfaces:**
- Consumes: `cloudflare/scripts/d1_schema_before_0011.sql`（Task 0）；`SQLiteDB`、`check` 的写法照 `cloudflare/scripts/knowledge_invariants_test.py` 第 84–159 行，可直接 `from knowledge_invariants_test import SQLiteDB`。
- Produces（`intake_test.py` 里，后续任务都用）:
  - `build_legacy_database() -> sqlite3.Connection`：执行结构文件并写入种子数据，不执行 `0011`。
  - `apply_migration(connection) -> None`：执行 `0011`。
  - `build_database() -> sqlite3.Connection`：上面两步连做。
  - `adapter(connection) -> SQLiteDB`、`run(coro)`、`expect_http(status, function)`、`check(name, function)`、`main()`。
  - 种子数据（编号固定，后续任务的测试直接引用）：学科 `1 数学`、`2 英语`；`write_guard(1,0,0)`、`knowledge_assert(1,1,1)`、`runtime_config` 的 `data_revision`、`taxonomy_version`；考点：一级 `100 分数运算`（数学），二级 `101 分数乘法`、`102 分数除法`（数学，六年级，父级 100），一级 `200 语法`（英语），二级 `201 一般现在时`（英语，六年级，父级 200）；错因 `1 计算错误`（数学）、`2 概念错误`（通用）；旧题 5 道：数学六年级上 2 道（其中 1 道已软删除）、数学六年级下 1 道、数学年级学期为空 1 道、英语六年级上 1 道，`created_at` 各不相同。

迁移内容（列的含义见设计文档第 5 节）：

1. `CREATE TABLE app_user`、`student`，各预置 `id=1` 的一行（"默认用户""默认学生"），用 `INSERT ... ON CONFLICT(id) DO NOTHING`。
2. `CREATE TABLE paper`（设计文档 5.3 的全部列，`images` 默认 `'[]'`，`source` 默认 `'manual'`，`student_id` 默认 1）。
3. 设计文档 5.2 表里列出的 17 张表（除 `paper`）各 `ALTER TABLE ... ADD COLUMN student_id INTEGER NOT NULL DEFAULT 1`。
4. `question` 加设计文档 5.4 的列：`paper_id`、`paper_page`、`question_no`、`wrong_answer`、`wrong_evidence`、`review_status TEXT NOT NULL DEFAULT 'approved'`、`review_reasons`、`review_note`、`reviewed_at`。
5. 回填旧题（含已软删除的行）：按 `(subject_id, grade, semester)` 分组各插一条 `paper`，`paper_type='homework'`、`source='history'`、`images='[]'`、`paper_date` 取组内最早 `created_at` 的日期（全为空时取执行当天）。名称规则：年级学期都有 →"六年级上 数学 历史作业"；有年级无学期 →"六年级 数学 历史作业"；无年级 →"数学 历史作业（年级未填）"。年级用中文数字一到十二，学期 1 为"上"、2 为"下"，学科名取 `subject.name`，学科行不存在时用"未知学科"。然后把每道旧题的 `paper_id` 指向本组的记录（比较年级学期时用 `IS`，空值也要对得上）。
6. 索引三个，见设计文档 5.6，都带 `IF NOT EXISTS` 和 `WHERE deleted=0` 的部分条件。

- [ ] **Step 1: 写失败的测试**

在 `intake_test.py` 里写好上面的助手和种子，再写这些用例（先只调用 `build_legacy_database()` 和 `apply_migration()`）：

```python
def test_migration_seeds_user_and_student():
    c = build_database()
    assert c.execute('SELECT id,name FROM app_user').fetchall()[0][:] == (1, '默认用户')
    row = c.execute('SELECT id,user_id,name FROM student').fetchone()
    assert tuple(row) == (1, 1, '默认学生')

def test_migration_keeps_question_rows_and_approves_them():
    c = build_legacy_database()
    before = c.execute('SELECT COUNT(*) FROM question').fetchone()[0]
    apply_migration(c)
    assert c.execute('SELECT COUNT(*) FROM question').fetchone()[0] == before == 5
    assert c.execute("SELECT COUNT(*) FROM question WHERE review_status<>'approved'").fetchone()[0] == 0
    assert c.execute('SELECT COUNT(*) FROM question WHERE student_id<>1').fetchone()[0] == 0

def test_migration_builds_history_papers():
    c = build_database()
    names = sorted(r[0] for r in c.execute("SELECT name FROM paper WHERE source='history'"))
    assert names == ['六年级上 数学 历史作业', '六年级上 英语 历史作业',
                     '六年级下 数学 历史作业', '数学 历史作业（年级未填）']
    assert c.execute('SELECT COUNT(*) FROM question WHERE paper_id IS NULL').fetchone()[0] == 0
    # 已软删除的旧题也回填，且和同组未删除的题指向同一条记录
    ids = {r[0] for r in c.execute('SELECT paper_id FROM question WHERE subject_id=1 AND grade=6 AND semester=1')}
    assert len(ids) == 1
    row = c.execute("SELECT paper_type,images,score,paper_date FROM paper WHERE name='六年级上 数学 历史作业'").fetchone()
    assert row[0] == 'homework' and row[1] == '[]' and row[2] is None
    assert row[3] == c.execute('SELECT MIN(date(created_at)) FROM question WHERE subject_id=1 AND grade=6 AND semester=1').fetchone()[0]

def test_old_insert_without_new_columns_still_works():
    c = build_database()
    c.execute("INSERT INTO question(subject_id,review_count,correct_count,error_count,deleted) VALUES(1,0,0,0,0)")
    row = c.execute('SELECT student_id,review_status,paper_id FROM question ORDER BY id DESC LIMIT 1').fetchone()
    assert tuple(row) == (1, 'approved', None)

def test_student_id_added_to_all_listed_tables():
    c = build_database()
    for table in ['question', 'error_book', 'paper', 'word', 'word_review', 'word_review_session',
                  'practice_set', 'learning_report', 'reading_passage', 'tag', 'reward', 'redemption',
                  'star_balance', 'star_record', 'star_action', 'achievement', 'achievement_progress']:
        columns = [r[1] for r in c.execute('PRAGMA table_info(' + table + ')')]
        assert 'student_id' in columns, table
```

- [ ] **Step 2: 运行，确认失败**

Run: `python cloudflare/scripts/intake_test.py`
Expected: 因为 `0011_intake_papers.sql` 不存在而失败。

- [ ] **Step 3: 写迁移文件**

按上面"迁移内容"六条写 `0011_intake_papers.sql`，文件头用两行中文注释说明用途和"只追加"的原则，写法参照 `0010_phrase_focus.sql`。

- [ ] **Step 4: 运行，确认通过**

Run: `python cloudflare/scripts/intake_test.py`
Expected: 5 个用例全部 PASS，退出码 0。

再跑两份旧测试，确认基线没被破坏：`python cloudflare/scripts/knowledge_invariants_test.py`、`python cloudflare/scripts/phrase_focus_test.py`，都应全部通过。

- [ ] **Step 5: Commit**

```bash
git add cloudflare/migrations/0011_intake_papers.sql cloudflare/scripts/intake_test.py
git commit -m "feat: add migration for students, papers and question review fields"
```

---

### Task 2: 纯规则 `intake_model.py`

**Files:**
- Create: `cloudflare/src/intake_model.py`
- Modify: `cloudflare/scripts/intake_test.py`

**Interfaces:**
- Produces:

```python
SPEC_VERSION = 1
PAPER_TYPES = ('homework', 'chapter_practice', 'exam')
EXAM_KINDS = ('unit', 'midterm', 'final', 'other')
REVIEW_REASONS = ('wrong_unclear', 'text_unclear', 'kp_unsure', 'other')
MAX_QUESTIONS = 100

class IntakeError(ValueError):
    """校验失败；detail 是给人看的中文说明。"""
    detail: str

def default_paper_name(subject_name: str, paper_date: str) -> str
def normalize_paper(raw: dict, subject_name: str, today: str) -> dict
def normalize_question(raw: dict, image_count: int, error_type_names: set | None) -> dict
def decide_review(question: dict, catalog_available: bool) -> tuple[str, list[str]]
```

- `normalize_paper` 返回的键：`name`、`paper_type`、`exam_kind`、`paper_date`、`grade`、`semester`、`score`、`full_score`、`images`（列表）、`notes`。不合格时抛 `IntakeError`。规则见设计文档 6.2"卷子部分"。`today` 是 `YYYY-MM-DD`（北京时间），由调用方传入，函数本身不取时间。图片路径格式：`^\d{4}/\d{2}/[0-9a-f]{8}_[^/\\]+$`。
- `normalize_question` 返回的键：`page`、`question_no`、`parsed_question`、`answer`、`analysis`、`wrong_answer`、`wrong_evidence`、`difficulty`、`error_type`、`knowledge_point_ids`、`primary_knowledge_point_id`、`needs_review`、`review_reasons`、`review_note`。文字字段去掉首尾空白，缺省为空字符串（`page`、`primary_knowledge_point_id` 缺省为 `None`，`knowledge_point_ids` 缺省为空列表）。`error_type_names` 为 `None` 或空集合时不校验错因。考点编号在这里只查类型（整数列表），是否在目录里由 Task 5 用 `resolve_many` 查。
- `decide_review` 返回 `('approved', [])` 或 `('pending', [原因...])`，原因去重并保持 `REVIEW_REASONS` 里的顺序。`catalog_available` 为假时，"没有主考点"不算待核对的理由。

- [ ] **Step 1: 写失败的测试**

```python
from intake_model import (IntakeError, MAX_QUESTIONS, decide_review, default_paper_name,
                          normalize_paper, normalize_question)

def expect_intake_error(fragment, function):
    """断言抛出 IntakeError 且说明里包含指定文字。"""

def test_paper_defaults():
    paper = normalize_paper({'subject_id': 1}, '数学', '2026-11-10')
    assert paper['name'] == '数学习题 2026-11-10' == default_paper_name('数学', '2026-11-10')
    assert (paper['paper_type'], paper['exam_kind'], paper['paper_date']) == ('homework', None, '2026-11-10')
    assert paper['images'] == [] and paper['score'] is None and paper['full_score'] is None

def test_paper_blank_name_uses_default_with_given_date():
    paper = normalize_paper({'name': '  ', 'paper_date': '2026-11-08'}, '英语', '2026-11-10')
    assert paper['name'] == '英语习题 2026-11-08'

def test_paper_exam_kind_rules():
    assert normalize_paper({'paper_type': 'exam'}, '数学', '2026-11-10')['exam_kind'] == 'other'
    assert normalize_paper({'paper_type': 'homework', 'exam_kind': 'final'}, '数学', '2026-11-10')['exam_kind'] is None
    expect_intake_error('类型', lambda: normalize_paper({'paper_type': 'quiz'}, '数学', '2026-11-10'))

def test_paper_score_rules():
    ok = normalize_paper({'score': 85, 'full_score': 100}, '数学', '2026-11-10')
    assert (ok['score'], ok['full_score']) == (85, 100)
    for bad in [{'score': 85}, {'full_score': 100}, {'score': 101, 'full_score': 100},
                {'score': -1, 'full_score': 100}, {'score': '85', 'full_score': 100},
                {'score': True, 'full_score': 100}]:
        expect_intake_error('分', lambda bad=bad: normalize_paper(bad, '数学', '2026-11-10'))

def test_paper_date_and_images_rules():
    expect_intake_error('日期', lambda: normalize_paper({'paper_date': '2026-11-11'}, '数学', '2026-11-10'))
    expect_intake_error('日期', lambda: normalize_paper({'paper_date': '11/10'}, '数学', '2026-11-10'))
    assert normalize_paper({'images': ['2026/11/ab12cd34_p1.jpg']}, '数学', '2026-11-10')['images'] == ['2026/11/ab12cd34_p1.jpg']
    for bad in [['../x.jpg'], ['http://a/b.jpg'], 'x', [1]]:
        expect_intake_error('照片', lambda bad=bad: normalize_paper({'images': bad}, '数学', '2026-11-10'))

def test_question_page_rules():
    base = {'parsed_question': '题干', 'wrong_evidence': '老师打叉'}
    assert normalize_question({**base, 'page': 2}, 2, None)['page'] == 2
    for bad in [{**base}, {**base, 'page': 0}, {**base, 'page': 3}, {**base, 'page': '1'}]:
        expect_intake_error('第几张', lambda bad=bad: normalize_question(bad, 2, None))
    assert normalize_question(base, 0, None)['page'] is None
    expect_intake_error('第几张', lambda: normalize_question({**base, 'page': 1}, 0, None))

def test_question_required_and_ranges():
    expect_intake_error('题干', lambda: normalize_question({'parsed_question': '  '}, 0, None))
    assert normalize_question({'parsed_question': '题干'}, 0, None)['difficulty'] == 3
    expect_intake_error('难度', lambda: normalize_question({'parsed_question': '题干', 'difficulty': 6}, 0, None))

def test_question_error_type_rules():
    names = {'计算错误', '概念错误'}
    ok = normalize_question({'parsed_question': '题干', 'error_type': '计算错误, 概念错误'}, 0, names)
    assert ok['error_type'] == '计算错误,概念错误'
    expect_intake_error('错因', lambda: normalize_question({'parsed_question': '题干', 'error_type': '粗心'}, 0, names))
    assert normalize_question({'parsed_question': '题干', 'error_type': '粗心'}, 0, set())['error_type'] == '粗心'

def test_question_review_fields_rules():
    base = {'parsed_question': '题干'}
    expect_intake_error('原因', lambda: normalize_question({**base, 'needs_review': True}, 0, None))
    expect_intake_error('原因', lambda: normalize_question({**base, 'needs_review': True, 'review_reasons': ['blurry']}, 0, None))
    expect_intake_error('考点', lambda: normalize_question({**base, 'knowledge_point_ids': ['101']}, 0, None))

def test_decide_review():
    clear = {'wrong_evidence': '老师打叉', 'primary_knowledge_point_id': 101, 'needs_review': False, 'review_reasons': []}
    assert decide_review(clear, True) == ('approved', [])
    assert decide_review({**clear, 'wrong_evidence': ''}, True) == ('pending', ['wrong_unclear'])
    assert decide_review({**clear, 'primary_knowledge_point_id': None}, True) == ('pending', ['kp_unsure'])
    # Review Focus 1：这个年级没有目录时，没有考点不算待核对
    assert decide_review({**clear, 'primary_knowledge_point_id': None}, False) == ('approved', [])
    flagged = {**clear, 'needs_review': True, 'review_reasons': ['other', 'text_unclear'], 'wrong_evidence': ''}
    assert decide_review(flagged, True) == ('pending', ['wrong_unclear', 'text_unclear', 'other'])
    # 孩子的答案留空不影响
    assert decide_review({**clear, 'wrong_answer': ''}, True) == ('approved', [])
```

- [ ] **Step 2: 运行，确认失败**

Run: `python cloudflare/scripts/intake_test.py`
Expected: 因 `intake_model` 模块不存在而失败。

- [ ] **Step 3: 实现 `intake_model.py`**

模块不导入 `fastapi`、`database` 和任何带数据库访问的模块。`bool` 是 `int` 的子类，分数、页码、难度的类型判断要把 `True` / `False` 排除在外。

- [ ] **Step 4: 运行，确认通过**

Run: `python cloudflare/scripts/intake_test.py`
Expected: 全部 PASS。

- [ ] **Step 5: Commit**

```bash
git add cloudflare/src/intake_model.py cloudflare/scripts/intake_test.py
git commit -m "feat: add pure intake rules for papers and questions"
```

---

### Task 3: 统计口径

**Files:**
- Create: `cloudflare/src/question_scope.py`
- Modify: `cloudflare/src/knowledge_stats.py`（`module_stats` 里的 `question_where`，第 53 行；`practice_sql` 里对 `question q` 的连接，第 96 行）
- Modify: `cloudflare/src/analytics.py`（`grouped` 第 23 行、`primary_module_counts` 第 42 行、`summary` 第 63、66、76、82 行、`full` 第 153 行和第 184 行的 `LEFT JOIN question q`）
- Modify: `cloudflare/src/reports.py`（`generate` 里以 `q.deleted=0` 开头的 `filters`）
- Modify: `cloudflare/src/practices.py`（`create_set` 第 127 行之后、`generate_questions` 第 156 行）
- Modify: `cloudflare/src/similar.py`（`generate` 第 18 行之后）
- Modify: `cloudflare/scripts/intake_test.py`

**Interfaces:**
- Produces:

```python
# question_scope.py
COUNTED = "deleted=0 AND review_status='approved'"

def counted(alias: str) -> str:
    """返回带表别名的条件，如 counted('q') -> "q.deleted=0 AND q.review_status='approved'"。"""

def current_student_id(request) -> int:
    """当前学生；目前固定返回 1，多学生上线时只改这里。"""
```

要改的地方和不改的地方，以设计文档第 9 节为准。行号是写计划时的位置，动手前先核对。`practices.create_set` 里：所选题目中有 `review_status` 不是 `approved` 的，抛 `HTTPException(400, '所选题目里有待核对的题，请先处理')`。`similar.generate` 里：原题不是 `approved` 时抛 `HTTPException(409, '这道题还在待核对，处理后才能生成相似题')`。

- [ ] **Step 1: 写失败的测试**

助手 `add_question(connection, subject_id=1, status='approved', point_id=101, grade=6, semester=1) -> int` 直接用 SQL 插一道题并挂上主考点，后续任务也用。

```python
from knowledge_stats import module_stats
import analytics, practices, similar

def test_pending_question_not_counted_in_module_stats():
    c = build_database(); db = adapter(c)
    before = run(module_stats(db, subject_id=1, level=1))['total_questions']
    pending_id = add_question(c, status='pending')
    assert run(module_stats(db, subject_id=1, level=1))['total_questions'] == before
    c.execute("UPDATE question SET review_status='approved' WHERE id=?", (pending_id,))
    assert run(module_stats(db, subject_id=1, level=1))['total_questions'] == before + 1

def test_pending_question_not_counted_in_grouped_and_primary_counts():
    c = build_database(); db = adapter(c)
    before = run(analytics.grouped(db, 'grade'))
    before_modules = run(analytics.primary_module_counts(db))
    add_question(c, status='pending')
    assert run(analytics.grouped(db, 'grade')) == before
    assert run(analytics.primary_module_counts(db)) == before_modules

def test_pending_question_not_selected_for_practice():
    c = build_database(); db = adapter(c)
    c.execute('UPDATE question SET deleted=1')          # 只留一道待核对的题
    add_question(c, status='pending')
    expect_http(400, lambda: run(call_endpoint(practices, practices.generate_questions,
                                               {'subject_id': 1, 'count': 5}, db)))

def test_pending_question_rejected_by_create_set_and_similar():
    c = build_database(); db = adapter(c)
    pending_id = add_question(c, status='pending')
    expect_http(400, lambda: run(call_endpoint(practices, practices.create,
                                               {'question_ids': [pending_id]}, db)))
    expect_http(409, lambda: run(similar.generate(pending_id, fake_request({}, db, similar))))
```

`module_stats` 返回里总题数的键名以实际代码为准（写计划时是 `total_questions`）。`call_endpoint(module, endpoint, payload, db)` 和 `fake_request(payload, db, module)` 是测试助手：照 `phrase_focus_test.py` 第 463–490 行的做法造一个假的 `Request`，并在调用期间把该模块的 `Database` 换成返回 `db` 的函数。`generate_questions` 的"没有符合条件的题目"本来就是 400。

- [ ] **Step 2: 运行，确认失败**

Run: `python cloudflare/scripts/intake_test.py`
Expected: 新增用例失败（待核对的题被计入、被选中）。

- [ ] **Step 3: 新建 `question_scope.py`，逐处替换条件**

每一处把原来的 `deleted=0`（或 `q.deleted=0`）换成 `COUNTED`（或 `counted('q')`），不改动其余筛选和参数顺序。不动的地方：`questions.py` 的列表和详情、`knowledge.py` 的使用计数与删除保护、`catalog.py` 的学科删除保护、`analytics.date_stats`、`practices.get`。

- [ ] **Step 4: 运行，确认通过**

Run: `python cloudflare/scripts/intake_test.py`、`python cloudflare/scripts/knowledge_invariants_test.py`
Expected: 都全部 PASS。

- [ ] **Step 5: Commit**

```bash
git add cloudflare/src/question_scope.py cloudflare/src/knowledge_stats.py cloudflare/src/analytics.py cloudflare/src/reports.py cloudflare/src/practices.py cloudflare/src/similar.py cloudflare/scripts/intake_test.py
git commit -m "feat: count only approved questions in stats and practice selection"
```

---

### Task 4: 录入资料接口 `GET /api/intake/guide`

**Files:**
- Create: `cloudflare/src/intake.py`
- Modify: `cloudflare/src/main.py`（导入并 `app.include_router(intake_router)`）
- Modify: `cloudflare/scripts/intake_test.py`

**Interfaces:**
- Consumes: `intake_model.SPEC_VERSION` 等常量；`settings.load(request, 'app')` 取默认年级学期；`question_scope.current_student_id`。
- Produces:

```python
# intake.py
router = APIRouter()

async def load_catalog(db, subject_id: int, grade: int | None, semester: int | None) -> list[dict]:
    """返回 [{'id','name','points':[{'id','name'}]}]，只含有二级考点的模块。"""

async def load_error_type_names(db, subject_id: int) -> set[str]:
    """该学科可用的错因名称（本学科的加上通用的）。"""

@router.get('/api/intake/guide')
async def guide(request, subject_id: int | None = None, subject: str | None = None,
                grade: int | None = None, semester: int | None = None) -> dict
```

`guide` 的返回：

```json
{
  "spec_version": 1,
  "subject": {"id": 1, "name": "数学"},
  "subjects": [{"id": 1, "name": "数学"}, {"id": 2, "name": "英语"}],
  "grade": 6, "semester": 1,
  "default_grade": 6, "default_semester": 1,
  "catalog_available": true,
  "knowledge_modules": [{"id": 100, "name": "分数运算", "points": [{"id": 101, "name": "分数乘法"}]}],
  "error_types": ["概念错误", "计算错误"],
  "paper_types": {"homework": "作业", "chapter_practice": "章节练习", "exam": "考试"},
  "exam_kinds": {"unit": "单元测", "midterm": "期中", "final": "期末", "other": "其他"},
  "review_reasons": {"wrong_unclear": "不确定这题是否做错了", "text_unclear": "照片模糊或题干拿不准",
                     "kp_unsure": "目录里找不到合适的考点", "other": "其他"}
}
```

规则：`subject_id` 和 `subject`（学科名称）二选一，都没给或找不到 → 400"学科不存在"。`grade`、`semester` 没给时用应用默认值，默认值也没有就是 `null`。考点筛选与 `knowledge.tree` 一致：二级考点的 `grade` 为空或等于所给年级才返回，学期同理；`grade` 为 `null` 时不按年级筛。`catalog_available` 是"筛选后至少有一个二级考点"。`error_types` 按名称排序。

- [ ] **Step 1: 写失败的测试**

```python
import intake

def test_guide_returns_catalog_for_grade():
    c = build_database(); db = adapter(c)
    data = run(intake.guide(fake_request({}, db, intake), subject_id=1, grade=6, semester=1))
    assert data['spec_version'] == 1 and data['subject'] == {'id': 1, 'name': '数学'}
    assert data['catalog_available'] is True
    assert data['knowledge_modules'] == [{'id': 100, 'name': '分数运算',
                                          'points': [{'id': 101, 'name': '分数乘法'}, {'id': 102, 'name': '分数除法'}]}]
    assert data['error_types'] == ['概念错误', '计算错误']
    assert set(data['paper_types']) == {'homework', 'chapter_practice', 'exam'}

def test_guide_accepts_subject_name_and_rejects_unknown():
    c = build_database(); db = adapter(c)
    assert run(intake.guide(fake_request({}, db, intake), subject='英语', grade=6))['subject']['id'] == 2
    expect_http(400, lambda: run(intake.guide(fake_request({}, db, intake), subject='物理')))
    expect_http(400, lambda: run(intake.guide(fake_request({}, db, intake))))

def test_guide_marks_missing_catalog():
    # Review Focus 1：七年级没有目录
    c = build_database(); db = adapter(c)
    data = run(intake.guide(fake_request({}, db, intake), subject_id=1, grade=7))
    assert data['catalog_available'] is False and data['knowledge_modules'] == []

def test_guide_uses_app_default_grade():
    c = build_database(); db = adapter(c)
    c.execute("INSERT INTO runtime_config(name,value,deleted,updated_at) VALUES('app','{\"default_grade\":6,\"default_semester\":1}',0,CURRENT_TIMESTAMP)")
    data = run(intake.guide(fake_request({}, db, intake), subject_id=1))
    assert (data['grade'], data['semester'], data['default_grade']) == (6, 1, 6)
```

`fake_request` 要让 `settings.load` 也读到测试库：调用期间把 `settings.Database` 一并换掉，`env` 上不带 `APP_CONFIG`。

- [ ] **Step 2: 运行，确认失败**

Run: `python cloudflare/scripts/intake_test.py`
Expected: 因 `intake` 模块不存在而失败。

- [ ] **Step 3: 实现 `guide`、`load_catalog`、`load_error_type_names`，在 `main.py` 注册路由**

考点一次查询取出该学科未删除的一、二级行，在 Python 里按年级学期筛选并组装，不逐个模块查询。

- [ ] **Step 4: 运行，确认通过**

Run: `python cloudflare/scripts/intake_test.py`
Expected: 全部 PASS。

- [ ] **Step 5: Commit**

```bash
git add cloudflare/src/intake.py cloudflare/src/main.py cloudflare/scripts/intake_test.py
git commit -m "feat: add intake guide endpoint with catalog and error types"
```

---

### Task 5: 试提交与正式提交

**Files:**
- Modify: `cloudflare/src/intake.py`
- Modify: `cloudflare/src/auth.py:80`（试提交不触发缓存失效和操作日志）
- Modify: `cloudflare/scripts/intake_test.py`

**Interfaces:**
- Consumes: Task 2 的四个函数；Task 4 的 `load_catalog`、`load_error_type_names`；`knowledge.resolve_many`、`ensure_guard_rows`、`guard_statement`、`structure_statement`、`question_links`、`decorate_question`；`questions.stamp_now`、`questions.batch_error`；`pdf.validate_math`；`question_scope.current_student_id`。
- Produces:

```python
@router.post('/api/intake/papers/check')
async def check_paper(request) -> dict            # 永远 200（除版本不一致）

@router.post('/api/intake/papers', status_code=201)
async def submit_paper(request) -> dict           # 201；校验不过 422；版本不一致 409

def hydrate_paper(row: dict) -> dict              # images 从 JSON 文本转成列表，score 等原样；Task 7 复用
```

请求体见设计文档 6.2（没有 `dry_run` 字段，试提交走单独的地址）。

返回：

- 试提交：`{"ok": bool, "errors": [...], "paper": 规范化后的卷子信息, "total_count": n, "approved_count": a, "pending_count": p}`。有错时 `ok` 为假，三个数量为 0。
- 正式提交成功：`{"paper": 卷子记录, "questions": [入库的题], "total_count": n, "approved_count": a, "pending_count": p, "errors": [], "replayed": false}`。
- 正式提交校验不过：HTTP 422，内容 `{"detail": "有 N 处需要修改", "errors": [...]}`（用 `JSONResponse`）。什么都不写入。
- `errors` 的每一项：`{"index": 题目在请求里的序号, "detail": 说明}`；卷子本身的问题 `index` 为 `null`；公式校验的问题 `index` 为 `null`、说明照搬校验器的原话。
- `spec_version` 不等于 `SPEC_VERSION`：HTTP 409，`{"detail": "录入规范版本不一致，请先更新录入规范（重新运行安装脚本）", "spec_version": 1}`。两个接口都检查。
- `request_id`：正式提交必填，8–64 位的字母、数字、连字符，否则 422。先查 `request_record` 里 `name='intake:'+request_id`：有记录就按其中的卷子编号读出卷子和题目返回，`replayed` 为真，状态码 200，不再校验也不写入。没有记录则把这条记录和其他写入放在同一个 `db.batch` 里。

处理顺序（两个接口共用一个内部函数，只在最后一步是否写入上分开）：

1. 版本检查；学科存在（否则卷子级错误）。
2. `normalize_paper`；题目数量 1–100；逐题 `normalize_question`，收集所有错误，不在第一处就停。
3. 对通过了第 2 步的题调用一次 `resolve_many(db, subject_id, entries)`，每项的 `payload` 只含 `knowledge_point_ids` 和 `primary_knowledge_point_id`，不传文字名称。
4. 学科是数学且前面没有错时，把所有题的题干、答案、解析一次交给 `validate_math`。它抛出的 `HTTPException` 转成一条 `index` 为 `null` 的错误。
5. 有任何错误：试提交返回 `ok: false`，正式提交返回 422。
6. 用 `load_catalog` 得到 `catalog_available`，逐题 `decide_review`。
7. 正式提交写入：一个 `db.batch`，依次是守卫语句（同时断言 `question` 和 `paper` 的最大编号没变、`write_guard` 存在）、插入 `paper`（`source='agent'`）、插入所有题、插入考点关联（`source='agent'`）、`structure_statement`、插入 `request_record`。题目的 `original_image` 填它那一页的照片路径，`original_images` 填只含这一张的 JSON 数组；卷子没有照片时两者为空。题目的 `grade`、`semester`、`subject_id`、`student_id`、`paper_id` 取自卷子。编号冲突（409）时重试一次，写法照 `questions.batch` 第 384–416 行。

`auth.py` 第 80 行的条件里，把 `/api/intake/papers/check` 和 `/api/stats/analysis/llm` 一样排除在缓存失效之外。

- [ ] **Step 1: 写失败的测试**

助手 `sample_payload(**overrides) -> dict`：返回一份合格的数学卷子请求，两张照片（`2026/11/aaaaaaaa_p1.jpg`、`2026/11/bbbbbbbb_p2.jpg`），两道题（第 1 题在第 1 页、考点 101、有判错依据；第 2 题在第 2 页、考点 102、有判错依据），`request_id` 每次调用新生成，`spec_version` 为 1。测试里把 `intake.validate_math`（或它在模块里的引用方式）换成可控的假函数，默认什么都不做。

```python
def submit(db, payload):      # 调用 intake.submit_paper，返回 (状态码, 内容)
def check_only(db, payload):  # 调用 intake.check_paper，返回 (状态码, 内容)
# 两个助手的约定：接口直接返回字典时，状态码记为它的默认值（submit 是 201，check 是 200）；
# 返回 JSONResponse 时取它的状态码，并把内容解析成字典。重放时接口返回 JSONResponse(200)。

def test_submit_writes_paper_and_questions():
    c = build_database(); db = adapter(c)
    status, body = submit(db, sample_payload())
    assert status == 201 and body['approved_count'] == 2 and body['pending_count'] == 0 and body['replayed'] is False
    paper = c.execute("SELECT name,paper_type,source,student_id,images FROM paper WHERE source='agent'").fetchone()
    assert tuple(paper)[:4] == ('数学习题 ' + body['paper']['paper_date'], 'homework', 'agent', 1)
    rows = c.execute('SELECT paper_page,original_image,original_images,review_status,grade,semester FROM question WHERE paper_id=? ORDER BY id', (body['paper']['id'],)).fetchall()
    assert [tuple(r) for r in rows] == [
        (1, '2026/11/aaaaaaaa_p1.jpg', '["2026/11/aaaaaaaa_p1.jpg"]', 'approved', 6, 1),
        (2, '2026/11/bbbbbbbb_p2.jpg', '["2026/11/bbbbbbbb_p2.jpg"]', 'approved', 6, 1)]
    sources = {r[0] for r in c.execute('SELECT source FROM question_knowledge_point WHERE question_id IN (SELECT id FROM question WHERE paper_id=?)', (body['paper']['id'],))}
    assert sources == {'agent'}

def test_check_writes_nothing():
    c = build_database(); db = adapter(c)
    counts = lambda: (c.execute('SELECT COUNT(*) FROM question').fetchone()[0], c.execute('SELECT COUNT(*) FROM paper').fetchone()[0])
    before = counts()
    status, body = check_only(db, sample_payload())
    assert status == 200 and body['ok'] is True and body['approved_count'] == 2 and counts() == before

def test_one_bad_question_rejects_whole_paper():
    c = build_database(); db = adapter(c)
    before = c.execute('SELECT COUNT(*) FROM question').fetchone()[0]
    payload = sample_payload(); payload['questions'][1]['knowledge_point_ids'] = [999]; payload['questions'][1]['primary_knowledge_point_id'] = 999
    status, body = submit(db, payload)
    assert status == 422 and [e['index'] for e in body['errors']] == [1]
    assert c.execute('SELECT COUNT(*) FROM question').fetchone()[0] == before
    assert c.execute("SELECT COUNT(*) FROM paper WHERE source='agent'").fetchone()[0] == 0

def test_all_errors_are_reported_together():
    c = build_database(); db = adapter(c)
    payload = sample_payload(score=120, full_score=100); payload['questions'][0]['parsed_question'] = ''
    payload['questions'][1]['page'] = 9
    status, body = check_only(db, payload)
    assert body['ok'] is False and [e['index'] for e in body['errors']] == [None, 0, 1]

def test_knowledge_point_of_other_subject_is_rejected():
    c = build_database(); db = adapter(c)
    payload = sample_payload(); payload['questions'][0].update(knowledge_point_ids=[201], primary_knowledge_point_id=201)
    assert submit(db, payload)[0] == 422

def test_math_error_is_reported_without_index():
    c = build_database(); db = adapter(c)
    use_failing_math_validator('公式边界不匹配')
    status, body = submit(db, sample_payload())
    assert status == 422 and body['errors'] == [{'index': None, 'detail': '公式边界不匹配'}]

def test_pending_decisions_are_stored():
    c = build_database(); db = adapter(c)
    payload = sample_payload()
    payload['questions'][0].update(wrong_evidence='')
    payload['questions'][1].update(needs_review=True, review_reasons=['text_unclear'], review_note='右下角被手挡住')
    status, body = submit(db, payload)
    assert status == 201 and (body['approved_count'], body['pending_count']) == (0, 2)
    rows = c.execute('SELECT review_status,review_reasons,review_note FROM question WHERE paper_id=? ORDER BY id', (body['paper']['id'],)).fetchall()
    assert [tuple(r) for r in rows] == [('pending', '["wrong_unclear"]', ''), ('pending', '["text_unclear"]', '右下角被手挡住')]

def test_no_catalog_for_grade_keeps_questions_approved():
    # Review Focus 1
    c = build_database(); db = adapter(c)
    payload = sample_payload(grade=7)
    for q in payload['questions']:
        q.update(knowledge_point_ids=[], primary_knowledge_point_id=None)
    status, body = submit(db, payload)
    assert status == 201 and body['pending_count'] == 0

def test_same_request_id_is_not_written_twice():
    # Review Focus 2
    c = build_database(); db = adapter(c)
    payload = sample_payload()
    first = submit(db, payload); second = submit(db, payload)
    assert first[0] == 201 and second[0] == 200 and second[1]['replayed'] is True
    assert second[1]['paper']['id'] == first[1]['paper']['id']
    assert c.execute("SELECT COUNT(*) FROM paper WHERE source='agent'").fetchone()[0] == 1

def test_spec_version_mismatch_and_request_id_rules():
    c = build_database(); db = adapter(c)
    assert submit(db, sample_payload(spec_version=2))[0] == 409
    assert check_only(db, sample_payload(spec_version=2))[0] == 409
    bad = sample_payload(); bad['request_id'] = 'x'
    assert submit(db, bad)[0] == 422

def test_paper_without_images_and_backslashes_survive():
    c = build_database(); db = adapter(c)
    payload = sample_payload(images=[])
    for q in payload['questions']:
        q['page'] = None
    payload['questions'][0]['parsed_question'] = r'计算：\(\frac{1}{2}\times\frac{2}{3}\)'
    status, body = submit(db, payload)
    assert status == 201
    row = c.execute('SELECT parsed_question,original_image,original_images FROM question WHERE paper_id=? ORDER BY id LIMIT 1', (body['paper']['id'],)).fetchone()
    assert tuple(row) == (r'计算：\(\frac{1}{2}\times\frac{2}{3}\)', None, None)

def test_question_count_limits():
    c = build_database(); db = adapter(c)
    empty = sample_payload(); empty['questions'] = []
    assert submit(db, empty)[0] == 422
    many = sample_payload(); many['questions'] = [dict(many['questions'][0]) for _ in range(101)]
    assert submit(db, many)[0] == 422
```

- [ ] **Step 2: 运行，确认失败**

Run: `python cloudflare/scripts/intake_test.py`
Expected: 新增用例因 `check_paper`、`submit_paper` 不存在而失败。

- [ ] **Step 3: 实现两个接口，修改 `auth.py`**

错因校验的开关：`load_error_type_names` 返回空集合时不校验。Task 0 Step 3 如果发现正式库里的 `error_type` 表和现有用法对不上，在这里停下来告诉用户差异，由用户决定是先补清单还是暂时不校验；不要自行往正式库里补数据。

- [ ] **Step 4: 运行，确认通过**

Run: `python cloudflare/scripts/intake_test.py`、`python cloudflare/scripts/knowledge_invariants_test.py`
Expected: 都全部 PASS。

- [ ] **Step 5: Commit**

```bash
git add cloudflare/src/intake.py cloudflare/src/auth.py cloudflare/scripts/intake_test.py
git commit -m "feat: add intake check and submit endpoints for whole papers"
```

---

### Task 6: 核对接口与错题接口的改动

**Files:**
- Modify: `cloudflare/src/intake.py`
- Modify: `cloudflare/src/questions.py`（`FIELDS` 第 28 行、`hydrate` 第 49 行、`listing` 第 201–290 行）
- Modify: `cloudflare/scripts/intake_test.py`

**Interfaces:**
- Produces:

```python
# intake.py
@router.get('/api/questions/review/count')
async def review_count(request) -> dict                       # {"pending": 3}

@router.post('/api/questions/{question_id}/review')
async def review_question(question_id: int, request) -> dict  # 返回处理后的题目；移除时返回 {"id":..,"review_status":"rejected"}
```

- `questions.FIELDS` 加 `wrong_answer`、`question_no`。不加 `paper_id`、`review_status`、`wrong_evidence`。
- `questions.listing` 新增参数 `review_status: str | None`（只接受 `approved`、`pending`，否则 422）和 `paper_id: int | None`。
- 列表和详情返回的每道题多带：`review_reasons`（列表，库里为空时是 `[]`）和 `paper`（`{"id","name","paper_type","exam_kind","paper_date"}`，没有所属卷子时为 `null`）。列表用一次查询取出本页所有题的卷子，不逐题查。
- `review_question`：请求体 `{"action": "approve"}` 或 `{"action": "reject"}`，其他取值 422。题目不存在或已删除 404。`review_status` 不是 `pending` → 409"这道题已经处理过了"。通过时没有主考点 → 422"请先选择考点再通过"。写入用带条件的 `UPDATE ... WHERE id=? AND deleted=0 AND review_status='pending' RETURNING id`，没有返回行时同样 409（防两人同时操作）。通过：`review_status='approved'`、`reviewed_at=当前时间`。移除：`deleted=1`、`review_status='rejected'`、`reviewed_at=当前时间`。

- [ ] **Step 1: 写失败的测试**

```python
import questions

def test_review_count_and_listing_filter():
    c = build_database(); db = adapter(c)
    pending_id = add_question(c, status='pending')
    assert run(intake.review_count(fake_request({}, db, intake))) == {'pending': 1}
    listed = run(call_listing(db, review_status='pending'))
    assert [item['id'] for item in listed['items']] == [pending_id]
    assert pending_id in [item['id'] for item in run(call_listing(db))['items']]
    expect_http(422, lambda: run(call_listing(db, review_status='rejected')))

def test_listing_includes_paper_and_reasons():
    c = build_database(); db = adapter(c)
    status, body = submit(db, sample_payload(name='第三章单元测试', paper_type='exam'))
    items = run(call_listing(db, paper_id=body['paper']['id']))['items']
    assert len(items) == 2 and items[0]['paper']['name'] == '第三章单元测试'
    assert items[0]['paper']['paper_type'] == 'exam' and items[0]['review_reasons'] == []

def test_approve_and_reject():
    c = build_database(); db = adapter(c)
    first, second = add_question(c, status='pending'), add_question(c, status='pending')
    out = run(review(db, first, 'approve'))
    assert out['review_status'] == 'approved'
    assert c.execute('SELECT reviewed_at FROM question WHERE id=?', (first,)).fetchone()[0]
    run(review(db, second, 'reject'))
    assert tuple(c.execute('SELECT deleted,review_status FROM question WHERE id=?', (second,)).fetchone()) == (1, 'rejected')
    assert run(intake.review_count(fake_request({}, db, intake))) == {'pending': 0}

def test_second_reviewer_gets_conflict():
    # Review Focus 4
    c = build_database(); db = adapter(c)
    question_id = add_question(c, status='pending')
    run(review(db, question_id, 'reject'))
    expect_http(404, lambda: run(review(db, question_id, 'approve')))      # 已移除的题不能再通过
    other = add_question(c, status='pending'); run(review(db, other, 'approve'))
    expect_http(409, lambda: run(review(db, other, 'approve')))
    expect_http(409, lambda: run(review(db, other, 'reject')))
    assert c.execute('SELECT deleted FROM question WHERE id=?', (other,)).fetchone()[0] == 0

def test_approve_requires_primary_knowledge_point():
    c = build_database(); db = adapter(c)
    question_id = add_question(c, status='pending', point_id=None)
    expect_http(422, lambda: run(review(db, question_id, 'approve')))
    expect_http(422, lambda: run(review(db, question_id, 'archive')))

def test_save_accepts_new_fields_and_old_page_keeps_them():
    # Review Focus 5
    c = build_database(); db = adapter(c)
    question_id = add_question(c, status='pending')
    run(questions.save(db, {'wrong_answer': '3/4', 'question_no': '二、5'}, question_id))
    run(questions.save(db, {'answer': '2/3'}, question_id))                 # 旧页面不带新字段
    row = c.execute('SELECT wrong_answer,question_no,review_status,answer FROM question WHERE id=?', (question_id,)).fetchone()
    assert tuple(row) == ('3/4', '二、5', 'pending', '2/3')
    run(questions.save(db, {'review_status': 'approved', 'paper_id': 999}, question_id))   # 不认识的字段被忽略
    assert tuple(c.execute('SELECT review_status,paper_id FROM question WHERE id=?', (question_id,)).fetchone())[0] == 'pending'
```

`call_listing(db, **params)` 调 `questions.listing`，没给的查询参数要显式传默认值（直接调用函数时 `Query(...)` 默认值不会自动展开）。`review(db, question_id, action)` 调 `intake.review_question`。

- [ ] **Step 2: 运行，确认失败**

Run: `python cloudflare/scripts/intake_test.py`
Expected: 新增用例失败。

- [ ] **Step 3: 实现**

- [ ] **Step 4: 运行，确认通过**

Run: `python cloudflare/scripts/intake_test.py`、`python cloudflare/scripts/knowledge_invariants_test.py`
Expected: 都全部 PASS。

- [ ] **Step 5: Commit**

```bash
git add cloudflare/src/intake.py cloudflare/src/questions.py cloudflare/scripts/intake_test.py
git commit -m "feat: add review actions and paper info on questions"
```

---

### Task 7: 卷子接口 `papers.py`

**Files:**
- Create: `cloudflare/src/papers.py`
- Modify: `cloudflare/src/main.py`
- Modify: `cloudflare/scripts/intake_test.py`

**Interfaces:**
- Consumes: `intake_model.normalize_paper`、`IntakeError`；`intake.hydrate_paper`；`knowledge.question_links`、`decorate_question`；`question_scope.current_student_id`。
- Produces（`router = APIRouter(prefix='/api/papers')`）:

| 接口 | 行为 |
| --- | --- |
| `GET ''` `listing(request, skip=0, limit=20, subject_id=None, paper_type=None)` | `{"total", "items"}`；每项是卷子记录加 `question_count`、`pending_count`、`subject_name`；按 `paper_date` 倒序、`id` 倒序；数量用一条带 `LEFT JOIN question` 和 `GROUP BY` 的 SQL 算出，只数未删除的题 |
| `GET '/{paper_id}'` `detail` | 卷子记录加 `subject_name` 和 `questions`（未删除的题，按 `paper_page`、`id` 排序，带考点和 `review_reasons`）；不存在 404 |
| `POST ''` `create`（201） | 请求体同 6.2 的 `paper` 部分；`source='manual'`；`images` 必须为空，否则 422 |
| `PUT '/{paper_id}'` `update` | 可改 `name`、`paper_type`、`exam_kind`、`paper_date`、`grade`、`semester`、`score`、`full_score`、`notes`。请求里带 `subject_id` 且与原值不同 → 422"学科不能修改"。`source='history'` 的记录只接受 `name` 和 `notes`，带了其他字段 → 422"历史记录只能改名称和备注"。年级或学期变了时，同一个 `db.batch` 里把这份卷子下所有题的 `grade`、`semester` 改成新值 |
| `DELETE '/{paper_id}'` `remove(paper_id, request, with_questions: int = 0)`（204） | `source='history'` → 409"历史记录不能删除"。下面有未删除的题且 `with_questions` 不是 1 → 409"这份记录下还有 N 道题"。`with_questions=1` 时同一个 `db.batch` 里软删除卷子和它的题 |

校验失败的 `IntakeError` 一律转成 `HTTPException(422, error.detail)`。

测试助手（本任务新增）：`add_question_to_paper(connection, paper_id, status='approved') -> int` 插一道挂在指定卷子下的题，学科、年级、学期取自卷子；`call_paper_listing(db, **params)` 调 `papers.listing` 并补齐默认参数；`update_paper(db, paper_id, payload)` 调 `papers.update`。`update` 的做法：把库里的现值和请求里给出的字段合并后交给 `normalize_paper`，这样分数"要么都有要么都没有"等规则对合并后的结果生效；没有给出的字段保持原值。

- [ ] **Step 1: 写失败的测试**

```python
import papers

def test_manual_paper_create_and_list_counts():
    c = build_database(); db = adapter(c)
    created = run(call_endpoint(papers, papers.create, {'subject_id': 1, 'name': '期中考试', 'paper_type': 'exam',
                                                        'exam_kind': 'midterm', 'paper_date': '2026-11-05',
                                                        'score': 92, 'full_score': 100, 'grade': 6, 'semester': 1}, db))
    assert created['source'] == 'manual' and created['images'] == [] and created['score'] == 92
    status, body = submit(db, sample_payload())
    add_question_to_paper(c, body['paper']['id'], status='pending')
    listed = run(call_paper_listing(db, subject_id=1))
    by_id = {item['id']: item for item in listed['items']}
    assert by_id[body['paper']['id']]['question_count'] == 3 and by_id[body['paper']['id']]['pending_count'] == 1
    assert by_id[created['id']]['question_count'] == 0 and by_id[created['id']]['subject_name'] == '数学'
    assert [item['id'] for item in run(call_paper_listing(db, paper_type='exam'))['items']] == [created['id']]

def test_paper_detail_orders_questions_by_page():
    c = build_database(); db = adapter(c)
    status, body = submit(db, sample_payload())
    data = run(papers.detail(body['paper']['id'], fake_request({}, db, papers)))
    assert [q['paper_page'] for q in data['questions']] == [1, 2] and data['questions'][0]['knowledge_points']
    expect_http(404, lambda: run(papers.detail(99999, fake_request({}, db, papers))))

def test_update_rules():
    c = build_database(); db = adapter(c)
    status, body = submit(db, sample_payload()); paper_id = body['paper']['id']
    out = run(update_paper(db, paper_id, {'paper_type': 'exam', 'score': 85, 'full_score': 100, 'grade': 6, 'semester': 2}))
    assert (out['paper_type'], out['exam_kind'], out['score']) == ('exam', 'other', 85)
    assert {tuple(r) for r in c.execute('SELECT grade,semester FROM question WHERE paper_id=?', (paper_id,))} == {(6, 2)}
    expect_http(422, lambda: run(update_paper(db, paper_id, {'score': 120})))          # 合并后超过满分
    expect_http(422, lambda: run(update_paper(db, paper_id, {'subject_id': 2})))
    assert run(update_paper(db, paper_id, {'name': '改个名'}))['score'] == 85           # 没给的字段不变

def test_history_paper_restrictions():
    c = build_database(); db = adapter(c)
    history_id = c.execute("SELECT id FROM paper WHERE source='history' LIMIT 1").fetchone()[0]
    assert run(update_paper(db, history_id, {'name': '五年级旧题', 'notes': '搬家前录的'}))['name'] == '五年级旧题'
    expect_http(422, lambda: run(update_paper(db, history_id, {'grade': 5})))
    expect_http(409, lambda: run(papers.remove(history_id, fake_request({}, db, papers), with_questions=1)))

def test_delete_rules():
    c = build_database(); db = adapter(c)
    status, body = submit(db, sample_payload()); paper_id = body['paper']['id']
    expect_http(409, lambda: run(papers.remove(paper_id, fake_request({}, db, papers), with_questions=0)))
    run(papers.remove(paper_id, fake_request({}, db, papers), with_questions=1))
    assert c.execute('SELECT deleted FROM paper WHERE id=?', (paper_id,)).fetchone()[0] == 1
    assert c.execute('SELECT COUNT(*) FROM question WHERE paper_id=? AND deleted=0', (paper_id,)).fetchone()[0] == 0
    expect_http(404, lambda: run(papers.detail(paper_id, fake_request({}, db, papers))))

def test_manual_paper_rejects_images():
    c = build_database(); db = adapter(c)
    expect_http(422, lambda: run(call_endpoint(papers, papers.create, {'subject_id': 1, 'images': ['2026/11/aaaaaaaa_p1.jpg']}, db)))
```

- [ ] **Step 2: 运行，确认失败**

Run: `python cloudflare/scripts/intake_test.py`
Expected: 因 `papers` 模块不存在而失败。

- [ ] **Step 3: 实现 `papers.py`，在 `main.py` 注册**

- [ ] **Step 4: 运行，确认通过，并做导入检查**

Run: `python cloudflare/scripts/intake_test.py`、`python cloudflare/scripts/knowledge_invariants_test.py`、`python cloudflare/scripts/phrase_focus_test.py`
Expected: 都全部 PASS。

- [ ] **Step 5: Commit**

```bash
git add cloudflare/src/papers.py cloudflare/src/main.py cloudflare/scripts/intake_test.py
git commit -m "feat: add paper records API"
```

---

### Task 8: 录入小工具

**Files:**
- Create: `tools/easyfix-intake/easyfix_intake.py`
- Create: `tools/easyfix-intake/test_easyfix_intake.py`

**Interfaces:**
- Produces（只用 Python 标准库，不导入仓库里的任何模块）:

```python
SPEC_VERSION = 1
UPLOAD_BATCH = 10
MAX_IMAGE_BYTES = 10 * 1024 * 1024
IMAGE_SUFFIXES = ('.jpg', '.jpeg', '.png', '.webp')

class ToolError(Exception):
    """给人看的中文说明和退出码。"""
    def __init__(self, message: str, code: int): ...

def load_config(environ: dict, config_path: pathlib.Path) -> dict      # {'base_url', 'token'}
def chunk(items: list, size: int) -> list[list]
def check_images(paths: list[str]) -> None                              # 不合格抛 ToolError(code=4)
def build_multipart(paths: list[str]) -> tuple[bytes, str]             # (请求体, Content-Type)
def prepare_payload(payload: dict, new_id) -> tuple[dict, bool]        # 补 spec_version、request_id；第二个值表示是否新补了 request_id
def call(config: dict, method: str, path: str, *, params=None, json_body=None, body=None, content_type=None, opener=None) -> tuple[int, dict]
def main(argv: list[str], *, opener=None, stdout=None) -> int
```

- 配置：环境变量 `EASYFIX_URL`、`EASYFIX_TOKEN` 优先，其次是 `~/.easyfix/intake.json` 的 `base_url`、`token`。缺任何一个 → `ToolError('还没有配置接口地址或访问口令，请先运行 install.py 并填写 ~/.easyfix/intake.json', 4)`。请求头 `Authorization: Bearer <口令>`。口令不出现在任何输出里。
- 命令（`python easyfix_intake.py <命令> ...`），输出都是 UTF-8 的 JSON，打印到标准输出：
  - `guide --subject 名称 [--grade N] [--semester N]` → `GET /api/intake/guide`。
  - `upload 路径...` → 先 `check_images`，再按 10 张一批依次 `POST /api/upload/batch-simple`（表单字段名 `files`），输出 `{"images": [按给出顺序排列的存储路径]}`。任何一张返回 `success: false` 或缺少路径 → `ToolError`，说明是第几张、文件名和原因，退出码 4，不输出部分结果。
  - `check 文件.json` → `POST /api/intake/papers/check`；`ok` 为真退出码 0，为假退出码 2。
  - `submit 文件.json` → 先调 check，不过就按 check 的方式结束；通过后 `POST /api/intake/papers`。文件里没有 `request_id` 时生成一个并**先写回文件再发请求**，重试时沿用。
- 退出码：0 成功；2 内容有问题需要修改；3 录入规范版本不一致（服务端 409 且带 `spec_version`），提示重新运行安装脚本；4 配置、文件或网络问题。
- `opener` 是可替换的发请求函数，测试用它代替真实网络。

- [ ] **Step 1: 写失败的测试**

```python
class IntakeToolTest(unittest.TestCase):
    def test_config_prefers_environment(self): ...
        # 环境变量和文件都有时用环境变量；都没有时 ToolError.code == 4，且说明里不含口令
    def test_chunk_keeps_order(self):
        self.assertEqual(tool.chunk(list(range(23)), 10), [list(range(10)), list(range(10, 20)), [20, 21, 22]])
    def test_check_images_rejects_big_and_non_image(self): ...
        # 11MB 的 .jpg、.pdf 文件、不存在的路径各自抛 ToolError(code=4)，说明里带文件名
    def test_upload_batches_and_keeps_page_order(self):
        # Review Focus 3：23 张图分 3 次请求，输出的 23 个路径与输入顺序一一对应
    def test_upload_fails_as_a_whole_when_one_image_fails(self):
        # Review Focus 3：第 12 张返回 success:false，退出码 4，标准输出里没有 images
    def test_prepare_payload_fills_and_keeps_request_id(self):
        payload, added = tool.prepare_payload({'paper': {}, 'questions': []}, lambda: 'abc-12345')
        self.assertEqual((payload['spec_version'], payload['request_id'], added), (1, 'abc-12345', True))
        again, added = tool.prepare_payload(payload, lambda: 'other-id')
        self.assertEqual((again['request_id'], added), ('abc-12345', False))
    def test_submit_writes_request_id_before_sending(self):
        # Review Focus 2：提交请求抛网络错误后，文件里已经有 request_id；再次 submit 发出的 request_id 相同
    def test_submit_stops_when_check_fails(self):
        # check 返回 ok:false 时不发正式提交，退出码 2，输出里带 errors
    def test_version_mismatch_exit_code(self):
        # 服务端 409 带 spec_version，退出码 3，输出提示重新运行安装脚本
    def test_token_never_printed(self):
        # 任何命令、任何失败路径的输出里都不含口令字符串
```

- [ ] **Step 2: 运行，确认失败**

Run: `python -m unittest tools/easyfix-intake/test_easyfix_intake.py -v`
Expected: 因模块不存在而失败。（目录名带连字符不能当包导入，测试文件用 `importlib` 按路径加载 `easyfix_intake.py`。）

- [ ] **Step 3: 实现小工具**

网络请求用 `urllib.request`。标准输出在 Windows 上显式按 UTF-8 写，避免中文乱码。

- [ ] **Step 4: 运行，确认通过**

Run: `python -m unittest tools/easyfix-intake/test_easyfix_intake.py -v`
Expected: 全部 OK。

- [ ] **Step 5: Commit**

```bash
git add tools/easyfix-intake/easyfix_intake.py tools/easyfix-intake/test_easyfix_intake.py
git commit -m "feat: add standalone intake tool for agents"
```

---

### Task 9: 录入规范（技能）、安装脚本、仓库说明

**REQUIRED SUB-SKILL:** 写和改 `SKILL.md` 时使用 superpowers:writing-skills，并读它目录下的 `testing-skills-with-subagents.md`。核心要求：先看到助手在没有规范时怎么做错，再写规范；写完用同样的场景验证；规范每改一次都重新验证。

**Files:**
- Create: `tools/easyfix-intake/SKILL.md`
- Create: `tools/easyfix-intake/payload-format.md`
- Create: `tools/easyfix-intake/scenarios.md`
- Create: `tools/easyfix-intake/install.py`
- Modify: `tools/easyfix-intake/test_easyfix_intake.py`
- Modify: `AGENTS.md`（"数学公式与 Agent 入库"一节）
- Modify: `CLAUDE.md`（新增一节）

**Interfaces:**
- Consumes: Task 8 的命令和退出码；Task 4、5 的请求与返回格式；Task 2 的 `normalize_paper`、`normalize_question`、`decide_review`（用来在本地检查场景产出的提交文件）。
- Produces:

```python
# install.py
POINTER_MARK = '<!-- easyfix-intake -->'
SKILL_FILES = ('SKILL.md', 'payload-format.md', 'easyfix_intake.py')

def install(home: pathlib.Path, source: pathlib.Path, codex_pointer: bool = False) -> list[str]:
    """把技能文件复制到两个用户级技能目录并准备配置文件；返回做了哪些事的中文说明。"""
```

`install` 做的事，可重复运行：

1. 把 `SKILL_FILES` 复制到 `<home>/.claude/skills/easyfix-intake/`（Claude 读这里）和 `<home>/.agents/skills/easyfix-intake/`（Codex 等其他工具共用的技能目录），覆盖旧文件。
2. `<home>/.easyfix/intake.json` 不存在时创建，内容 `{"base_url": "https://easyfix-bl2.pages.dev", "token": ""}`；已存在时不动。
3. 仅当 `codex_pointer` 为真（命令行参数 `--codex-pointer`，只在 Task 0 Step 5 没能确认 Codex 读取 `~/.agents/skills/` 时才用）：`<home>/.codex/AGENTS.md` 里没有 `POINTER_MARK` 时，在末尾追加一段（以 `POINTER_MARK` 开头）："用户要求把错题或卷子照片录入 EasyFix 时，先读 `~/.agents/skills/easyfix-intake/SKILL.md` 并照做。"已有标记时不重复追加，文件里的其他内容不动。
4. 口令为空时在返回的说明里提醒用户填写，不询问、不读取、不打印口令。

技能文件的分工：

| 文件 | 内容 | 篇幅 |
| --- | --- | --- |
| `SKILL.md` | 什么时候用、核心原则、工作步骤、必须停下来的信号、常见借口与事实对照 | 短，正文一屏半以内 |
| `payload-format.md` | 提交文件的完整格式、每个字段的含义、一份完整的示例、四个待核对原因各自什么时候用、数学公式写法 | 参考资料，用到时才读 |
| 小工具的 `--help` | 四个命令的参数和退出码 | 不在 `SKILL.md` 里重复 |
| `scenarios.md` | 测试场景的文字描述、没有规范时的表现记录、有规范后的结果。**不含照片和孩子的作业内容** | 只留在仓库，不安装 |

`SKILL.md` 的硬性要求：

- 元信息：`name: easyfix-intake`。`description` 以"Use when"开头、第三人称、**只写什么时候用，不概括步骤**（概括了步骤，助手会照着这句话做而不去读正文）。要包含用户会说的词："录入错题""录错题""卷子照片""作业照片""EasyFix"。
- 正文用直白的中文。必须覆盖设计文档 7.3 的各条，但写法按"没有规范时实际出了什么错"来定，见下面 Step 3。
- 调用小工具一律写成 `python <技能目录>/easyfix_intake.py ...`，不写成直接执行脚本。
- 问用户的那句话照原文："这是哪份作业或卷子？如果是考试，多少分？可以回'跳过'。"
- 提交后向用户汇报的内容：录了几道、几道直接入库、几道待核对及各自原因、待核对页地址 `https://easyfix-bl2.pages.dev/review`。

`AGENTS.md`：把"数学公式与 Agent 入库"一节里"使用结构化参数写库，写入后回读核对……正式写入前备份"那一条，改成"录题只通过 `tools/easyfix-intake/` 的技能和小工具提交，规范见该目录的 `SKILL.md`；不直接写数据库"。公式写法的两条保留。`CLAUDE.md`：在"开发命令"之前加一节"录入错题"，三四行，说明同一件事，并注明本文件其余内容描述的是旧版本地系统、正式环境见 `AGENTS.md` 的"Cloudflare 正式环境"。

- [ ] **Step 1: 准备测试场景**

用户已经提供了五张真实照片，存在被忽略的 `tmp/intake-scenarios/` 下，**不提交**：

| 文件 | 内容 | 用来考什么 |
| --- | --- | --- |
| `math-p27.jpg` | 数学校本作业第 27 页，只有 1 道错 | 多数题做对时不能把对的录进来；长斜线表示对 |
| `math-p28.jpg` | 同一份作业第 28 页，只有 1 道对 | 小圈和叉表示错；有涂改看不清的答案 |
| `math-p31.jpg` | 数学第 31 页，大量错，含火柴棒图形题 | 带图形和表格的题；一道大题多个小问 |
| `english-p37.jpg` | 英语第 37 页 | 斜线在这里表示错（与数学相反）；两个部分老师没批改但有明显错误 |
| `chinese-dictation.jpg` | 语文默写，横拍，一张两页 | 系统里没有的学科；拍得不正 |

同目录下的 `answer-key-draft.md` 是初读得到的标准答案草稿。**开始前请用户核对**，重点是英语第 III 部分的 8 道选择题（初读结果是 8 道全错，可能认错了手写字母）和数学第 31 页 A 层第 7 题。核对后改名为 `answer-key.md`。标准答案同样不提交。

在 `scenarios.md` 里写下场景（只写文字描述，不写卷子内容）。至少五个，每个都带现实里会有的压力：

1. 数学第 27、28 两页一起贴，用户只说"录入错题"。
2. 英语第 37 页，用户说"快一点，不用问我了"。
3. 数学第 31 页，用户说"看不清的你自己判断"。
4. 语文默写那张，用户说"录入错题"。
5. 数学第 27 页，用户说"图片可以不上传，直接写库就行"。

所有场景都**不写入正式环境**：让助手产出提交文件（JSON）后停下，不执行 `submit`。在给助手的说明里写清这一点。

- [ ] **Step 2: 看没有规范时怎么做（基线）**

每个场景派一个全新的助手，只给照片路径、用户的那句话，以及仓库现有的 `AGENTS.md`（不给 `SKILL.md`）。要求它照自己的判断完成，并产出打算提交的内容。

把每个助手的做法和原话记进 `scenarios.md`，对照标准答案逐项记录：

- 把做对的题录进去了几道。
- 每道题对应的照片对不对。
- 看不清的地方是猜了还是标出来了。
- 孩子的答案是照抄的还是编的。
- 考点是从清单里选的还是自己写的。
- 有没有打算直接写数据库或临时写脚本，它给出的理由原话是什么。
- 问了用户几个问题。

- [ ] **Step 3: 写 `SKILL.md` 和 `payload-format.md`**

只针对 Step 2 里实际出现的问题来写，不为没出现过的情况加内容。按问题的类型选写法：

| 基线里的问题 | 写法 |
| --- | --- |
| 明知道规则但在压力下绕过（直接写库、被催就不问、被要求就猜） | 明确的禁止 + "遇到这些念头就停下"清单 + 借口与事实对照表，借口用 Step 2 记下的原话 |
| 提交内容缺东西（没写页码、没写判错依据、没写原因） | 不写提醒，改成提交文件模板里的必填项，由接口校验退回 |
| 做法该随情况变（没有考点目录、用户已经说了是哪份卷子、拿不到照片路径） | 写成"如果看到 X，就做 Y"，X 必须是能直接观察到的东西 |
| 判断类的错（把做对的题当成错题） | 写成正面的做法：每道题先找到并写下判错依据，找不到依据的题按规则处理 |

不写"除非……否则……"这类留口子的句子；真有例外就单列一条"如果……就……"。

- [ ] **Step 4: 用同样的场景验证**

每个场景再派全新的助手，这次带上 `SKILL.md`（按安装后的目录结构给它，小工具的接口地址指向一个不存在的地址，保证不会真的提交）。判断类的场景（1、2、3）各跑至少 3 次。

用一个临时脚本把每份产出的提交文件过一遍 `normalize_paper`、`normalize_question`、`decide_review`，再对照标准答案。通过的标准：

- 做对的题一道都没录进来；真正的错题没有漏。
- 每道题的页码都对。
- 拍糊的那一页上的题都标了待核对，原因和说明能看懂。
- 没有编造孩子的答案。
- 考点全部来自 `guide` 返回的清单。
- 数学和英语两位老师含义相反的批改符号都判断对了。
- 英语那页老师没批改但写错的题录进来了，且都标了待核对，说明里写了"老师没有批改"。
- 语文那张没有录，并向用户说明了原因。
- 场景 5 里没有直接写库，并向用户说明了原因。
- 每个场景最多问了用户一句话，场景 2 里没有因为被催而漏掉该标的疑问。

结果记进 `scenarios.md`。

- [ ] **Step 5: 补漏洞，重新验证**

Step 4 里出现的新借口或新错误，逐条补进 `SKILL.md`，然后重跑受影响的场景，直到全部通过。同一场景多次运行结果不一致时，说明那句话没有约束力，改写法，不是加字数。记录每一轮改了什么。

三轮之后仍有通不过的项时停下来，把情况如实告诉用户，由用户决定是接受现状还是调整做法。

- [ ] **Step 6: 写安装脚本的失败测试**

```python
class InstallTest(unittest.TestCase):
    def test_install_copies_files_and_creates_config(self):
        # 在临时目录当 home 运行 install：.claude/skills 和 .agents/skills 下的 easyfix-intake 目录里
        # 都有 SKILL_FILES 的三个文件；intake.json 的 base_url 正确、token 为空；
        # 没有创建 .codex/AGENTS.md
    def test_install_is_repeatable_and_keeps_token(self):
        # 先把 token 改成 'secret-value' 再运行一次：token 不变
    def test_codex_pointer_is_added_once_and_keeps_other_content(self):
        # codex_pointer=True 运行两次：POINTER_MARK 只出现一次；文件里原有的内容还在
    def test_install_never_reports_token(self):
        # 返回的说明里不含 'secret-value'
    def test_skill_description_only_says_when_to_use(self):
        # SKILL.md 元信息里 name 是 easyfix-intake；description 以 'Use when' 开头，
        # 含"录入错题"，不含 guide、upload、check、submit 任何一个命令名
    def test_skill_and_format_files_cover_required_content(self):
        # SKILL.md 里有那句提问的原文和待核对页地址；
        # payload-format.md 里有四个原因代码和 paper、questions 两部分的字段
```

Run: `python -m unittest tools/easyfix-intake/test_easyfix_intake.py -v`
Expected: 安装相关的用例失败（`install.py` 还不存在）。

- [ ] **Step 7: 写 `install.py`，改 `AGENTS.md`、`CLAUDE.md`**

`install.py` 直接运行时以 `pathlib.Path.home()` 为 `home`，并逐行打印返回的说明。本任务只在临时目录里测试，**不在用户的真实目录里运行安装**，那是 Task 12 的事。

Run: `python -m unittest tools/easyfix-intake/test_easyfix_intake.py -v`
Expected: 全部 OK。

- [ ] **Step 8: Commit**

确认 `tmp/intake-scenarios/` 没有被加入提交。

```bash
git add tools/easyfix-intake/SKILL.md tools/easyfix-intake/payload-format.md tools/easyfix-intake/scenarios.md tools/easyfix-intake/install.py tools/easyfix-intake/test_easyfix_intake.py AGENTS.md CLAUDE.md
git commit -m "docs: add intake skill tested against real scenarios, installer and repo pointers"
```

---

### Task 10: 前端公共部分与待核对页

**Files:**
- Create: `frontend/src/composables/intakeLabels.js`
- Create: `frontend/src/composables/intakeLabels.test.mjs`
- Create: `frontend/src/api/paper.js`
- Create: `frontend/src/stores/reviewCount.js`
- Create: `frontend/src/views/ReviewQueue.vue`
- Modify: `frontend/src/router/index.js`
- Modify: `frontend/src/App.vue`
- Modify: `frontend/src/views/Home.vue:27`

**Interfaces:**
- Consumes: Task 6、7 的接口。
- Produces:

```js
// composables/intakeLabels.js（纯函数，不依赖 Vue）
export const PAPER_TYPE_LABELS   // { homework: '作业', chapter_practice: '章节练习', exam: '考试' }
export const EXAM_KIND_LABELS    // { unit: '单元测', midterm: '期中', final: '期末', other: '其他' }
export const REVIEW_REASON_LABELS // { wrong_unclear: '不确定是否做错', text_unclear: '照片模糊或题干拿不准', kp_unsure: '考点拿不准', other: '其他' }
export function paperTypeLabel(paper)   // 作业 / 章节练习 / 考试 · 期中；考试且细分为 other 时只显示"考试"
export function reasonLabels(codes)     // 代码数组 → 中文数组；不认识的代码原样返回；空或非数组 → []
export function scoreText(paper)        // '85 / 100'；没有分数 → ''；整数不带小数点，85.5 显示 85.5
export function groupByPaper(questions) // → [{ paper, questions }]，按题目原有顺序分组；没有卷子的题归到 paper 为 null 的一组，排在最后
export function pageImage(question)     // question.original_image 存在 → '/uploads/' + 路径；否则 null

// api/paper.js
export const paperApi  = { list(params), get(id), create(data), update(id, data), remove(id, withQuestions) }
export const reviewApi = { count(), pending(params), approve(id), reject(id) }
// reviewApi.pending 调 GET /questions?review_status=pending

// stores/reviewCount.js
export const useReviewCountStore   // state: pending（数字）；action: refresh()，失败时保持原值不报错
```

路由：`/review` → `ReviewQueue.vue`（name `ReviewQueue`）。

`App.vue`：`navigation` 的"学习空间"分组里，在"我的错题"后面加 `{ path: '/review', label: '待核对', icon: ..., badge: true }`。导航项带 `badge` 且 `pending > 0` 时，在文字后面显示数字（桌面侧栏和"更多"抽屉里都显示）。`onMounted` 里调用 `reviewCountStore.refresh()`。`mobileLinks` 不变。

`Home.vue`：`.home-shortcuts` 里，在"错题复习"后面加一个入口"待核对 <span>N 道待处理 →</span>"，指向 `/review`，数字来自 `useReviewCountStore`；`pending` 为 0 时显示"暂无待处理 →"。进入首页时 `refresh()`。

`ReviewQueue.vue`（布局见设计文档 8.1 的示意图）：

- 页头用 `PageHeading`，标题"待核对"，说明"这些题录入时有拿不准的地方，处理后才会计入统计和练习卷"。
- 进入时 `reviewApi.pending({ limit: 100 })`，用 `groupByPaper` 分组显示；每组标题是卷子名称和日期。
- 每道题一张卡片：左边 `el-image` 显示 `pageImage(question)`，点击用 `el-image-viewer` 放大，没有照片时显示"这道题没有带照片"；右边依次是题号、疑问原因（`reasonLabels` 的结果，用 `el-tag`）、说明（`review_note`）、题干、孩子的答案、正确答案、判错依据、考点（`KnowledgeTag`）。题干和两个答案用 `MathText`。
- 三个按钮："通过"→ `reviewApi.approve`；"编辑后通过"→ 打开本页自己的编辑框（`MathEditor` 编辑题干、正确答案、孩子的答案、解析，`KnowledgePointPicker` 选考点，错因多选，题号输入框），保存时先 `questionApi.update`（带上读取时的 `knowledge_revision`），成功后再 `reviewApi.approve`；"做对了，移除"→ `ElMessageBox.confirm('确定这道题其实做对了吗？移除后不会出现在错题和统计里。')` 后 `reviewApi.reject`。
- 每个动作成功后把这道题从页面上去掉，并 `reviewCountStore.refresh()`。接口返回 409 时提示"这道题已经被处理过了"，同样把它去掉。422（没有考点）时提示接口给的说明，并打开编辑框。
- 列表为空时显示 `el-empty`，文字"都处理完了"。
- 768px 以下：卡片改为上下排列，照片在上，按钮撑满一行。

- [ ] **Step 1: 写失败的测试**

```js
// frontend/src/composables/intakeLabels.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { paperTypeLabel, reasonLabels, scoreText, groupByPaper, pageImage } from './intakeLabels.js'

test('卷子类型显示', () => {
  assert.equal(paperTypeLabel({ paper_type: 'homework' }), '作业')
  assert.equal(paperTypeLabel({ paper_type: 'exam', exam_kind: 'midterm' }), '考试 · 期中')
  assert.equal(paperTypeLabel({ paper_type: 'exam', exam_kind: 'other' }), '考试')
  assert.equal(paperTypeLabel({ paper_type: 'quiz' }), 'quiz')
  assert.equal(paperTypeLabel(null), '')
})
test('待核对原因转中文', () => {
  assert.deepEqual(reasonLabels(['wrong_unclear', 'kp_unsure']), ['不确定是否做错', '考点拿不准'])
  assert.deepEqual(reasonLabels(['mystery']), ['mystery'])
  assert.deepEqual(reasonLabels(null), [])
})
test('分数显示', () => {
  assert.equal(scoreText({ score: 85, full_score: 100 }), '85 / 100')
  assert.equal(scoreText({ score: 85.5, full_score: 100 }), '85.5 / 100')
  assert.equal(scoreText({ score: 0, full_score: 100 }), '0 / 100')
  assert.equal(scoreText({ score: null, full_score: null }), '')
})
test('按卷子分组并保持顺序', () => {
  const a = { id: 1, name: 'A' }, b = { id: 2, name: 'B' }
  const groups = groupByPaper([{ id: 10, paper: a }, { id: 11, paper: null }, { id: 12, paper: b }, { id: 13, paper: a }])
  assert.deepEqual(groups.map(g => [g.paper?.id ?? null, g.questions.map(q => q.id)]), [[1, [10, 13]], [2, [12]], [null, [11]]])
})
test('页面照片地址', () => {
  assert.equal(pageImage({ original_image: '2026/11/ab12cd34_p1.jpg' }), '/uploads/2026/11/ab12cd34_p1.jpg')
  assert.equal(pageImage({ original_image: null }), null)
})
```

- [ ] **Step 2: 运行，确认失败**

Run: `node --test frontend/src/composables/intakeLabels.test.mjs`
Expected: 因模块不存在而失败。

- [ ] **Step 3: 实现 `intakeLabels.js`，运行确认通过**

Run: `node --test frontend/src/composables/intakeLabels.test.mjs frontend/src/composables/dictation.test.mjs`
Expected: 全部通过。

- [ ] **Step 4: 实现 `paper.js`、`reviewCount.js`、`ReviewQueue.vue`，改路由、`App.vue`、`Home.vue`**

`paper.js` 的写法照 `frontend/src/api/question.js` 开头（`axios.create({ baseURL: '/api' })`，基于 `@/api/http`）。

- [ ] **Step 5: 构建并在浏览器里验证**

Run: `npm --prefix frontend run build`
Expected: 构建成功，无新增错误。

浏览器验证沿用项目 0 的做法（见 `docs/superpowers/plans/2026-11-10-phrase-dictation.md` 第 792–803 行）：`npm --prefix frontend run dev` 启动后，用开发者工具让 `/api/questions?review_status=pending`、`/api/questions/review/count` 返回夹具（两份卷子共三道待核对的题，其中一道没有照片、一道含公式），不解除生产保护。逐项确认：

- 首页入口和侧栏的数字是 3；处理一道后变成 2。
- 卡片左图右文；点照片能放大；没有照片的那道显示提示文字。
- "通过"发出 `POST /api/questions/<id>/review`，内容 `{"action":"approve"}`。
- "编辑后通过"先发 `PUT`，成功后才发通过。
- "做对了，移除"有二次确认。
- 接口返回 409 时有提示且卡片消失。
- 375px 宽度下卡片上下排列，按钮可点。

无法验证的项如实写进提交说明。

- [ ] **Step 6: Commit**

```bash
git add frontend/src/composables/intakeLabels.js frontend/src/composables/intakeLabels.test.mjs frontend/src/api/paper.js frontend/src/stores/reviewCount.js frontend/src/views/ReviewQueue.vue frontend/src/router/index.js frontend/src/App.vue frontend/src/views/Home.vue
git commit -m "feat: add review queue page with home and nav entries"
```

---

### Task 11: 卷子页面与错题页的小改动

**Files:**
- Create: `frontend/src/views/Papers.vue`
- Create: `frontend/src/views/PaperDetail.vue`
- Modify: `frontend/src/router/index.js`
- Modify: `frontend/src/App.vue`
- Modify: `frontend/src/views/Questions.vue`（表格第 93–94 行、详情框第 159–289 行、编辑框第 292–387 行、`editForm` 第 626–641 行、`editQuestion` 第 827–848 行）

**Interfaces:**
- Consumes: Task 10 的 `paperApi`、`intakeLabels.js`、`useReviewCountStore`；Task 6、7 的接口。

路由：`/papers` → `Papers.vue`（name `Papers`）；`/papers/:id` → `PaperDetail.vue`（name `PaperDetail`）。`App.vue` 的"学习空间"分组里，在"待核对"后面加 `{ path: '/papers', label: '卷子和作业', icon: ... }`；`isActive` 让 `/papers/123` 也算在 `/papers` 上，`currentTitle` 在详情页显示"卷子和作业"。

`Papers.vue`：

- `PageHeading` 标题"卷子和作业"，右侧按钮"新增记录"。
- 筛选：学科、类型。列表用 `el-table`：名称（点击进详情）、类型（`paperTypeLabel`）、日期、分数（`scoreText`，没有就空着）、题目数、待核对数（大于 0 时用橙色 `el-tag`）。分页沿用 `skip` / `limit` 和 `el-pagination`。
- "新增记录"对话框：学科（必填）、名称、类型、考试细分（类型是考试时才出现）、日期（默认今天）、年级、学期、得分、满分、备注。类型选考试时，分数两格下方提示"考试建议填上分数"。保存调 `paperApi.create`，失败时显示接口返回的说明。
- 768px 以下：表格隐藏"题目数"以外的次要列（年级学期、备注），名称列占满。

`PaperDetail.vue`：

- 顶部显示名称、类型、日期、年级学期、分数、备注，右侧"编辑""删除"。
- "编辑"对话框字段同新增（学科不可改）。`source` 为 `history` 时只显示名称和备注两项，页面上注明"这是整理旧题时自动建的记录"，并且不显示"删除"。
- 照片区：`paper.images` 逐张 `el-image`，可点击放大并左右翻看；没有照片时不显示这一区。
- 题目区：每道题一行，显示题号、题干（`MathText`，限高）、孩子的答案、考点、"待核对"标记；点击跳到 `/questions` 并带上能定位这道题的查询参数（没有现成参数时退而求其次：跳到 `/review` 如果是待核对的题，否则只显示不跳转）。
- "删除"：`ElMessageBox.confirm`，下面有题时文字为"这份记录下有 N 道错题，会一起删除。确定吗？"，确认后 `paperApi.remove(id, true)`；没有题时普通确认后 `paperApi.remove(id, false)`。成功后回到列表并 `reviewCountStore.refresh()`。

`Questions.vue`：

- 表格里待核对的题在题干旁边显示橙色 `el-tag`"待核对"。
- 选择列加 `:selectable`，待核对的题不可勾选（不能拿去建练习卷）。
- 详情框里多显示：所属卷子（名称，点击进 `/papers/<id>`；没有时显示"无"）、题号、孩子的答案（`MathText`）、判错依据。
- 编辑框和 `editForm` 加"孩子的答案"（`MathEditor`）和"题号"两项；`editQuestion` 把现值带进去，`saveEdit` 把它们一并提交。

- [ ] **Step 1: 实现两个新页面，改路由和 `App.vue`**

- [ ] **Step 2: 改 `Questions.vue`**

只加上面列出的四处，不重排、不拆分这个文件的其他部分。

- [ ] **Step 3: 构建并在浏览器里验证**

Run: `npm --prefix frontend run build`、`node --test frontend/src/composables/intakeLabels.test.mjs frontend/src/composables/dictation.test.mjs`
Expected: 构建成功；测试全部通过。

用夹具验证（做法同 Task 10 Step 5）：

- 卷子列表显示一条考试（带分数、期中）、一条作业（无分数、有 1 道待核对）、一条历史记录。
- 新增记录：类型切到考试时出现细分和分数提示；得分大于满分时显示接口返回的说明。
- 详情页：照片能翻看；历史记录没有"删除"，编辑框只有两项。
- 删除带题目的记录时，确认框里有题目数量，请求带 `with_questions=1`。
- 错题页：待核对的题有标记且不能勾选；详情里有所属卷子、题号、孩子的答案；编辑保存的请求体里带 `wrong_answer` 和 `question_no`。
- 375px 宽度下三个页面都能正常操作。

无法验证的项如实写进提交说明。

- [ ] **Step 4: Commit**

```bash
git add frontend/src/views/Papers.vue frontend/src/views/PaperDetail.vue frontend/src/router/index.js frontend/src/App.vue frontend/src/views/Questions.vue
git commit -m "feat: add papers pages and show review info on questions"
```

---

### Task 12: 发布与验收

每一步动正式环境或用户目录之前，先向用户说明这一步要做什么、会改变什么，得到明确同意后再执行。一次同意只管一步。环境注意事项见启动文档"发布时要注意的环境情况"和 `docs/cloudflare-migration-status.md` 末尾 2026-11-10 的记录。

**Files:**
- Modify: `docs/cloudflare-migration-status.md`（追加本次变更记录）
- Modify: `docs/superpowers/specs/2026-11-10-project1-kickoff.md`（进度表）、`docs/superpowers/specs/2026-11-10-optimization-roadmap.md`（状态行）

- [ ] **Step 1: 发布前总检查**

Run:
```bash
python cloudflare/scripts/intake_test.py
python cloudflare/scripts/knowledge_invariants_test.py
python cloudflare/scripts/phrase_focus_test.py
python -m unittest tools/easyfix-intake/test_easyfix_intake.py
node --test frontend/src/composables/intakeLabels.test.mjs frontend/src/composables/dictation.test.mjs
npm --prefix frontend run build
```
Expected: 全部通过。然后按 superpowers:requesting-code-review 对整个分支做一次审阅，处理完意见再继续。

- [ ] **Step 2: 备份并演练迁移**（需用户同意）

重新导出一份正式库完整备份（Task 0 的那份可能已经过时），记下 SHA-256。在备份的本地副本上按下面的顺序演练（整体审阅 2026-11-11 给出的清单），把核对结果给用户看：

1. 副本的表结构（`sqlite_master`）与 `cloudflare/scripts/d1_schema_before_0011.sql` 逐项比对。有任何差别就停下来，不发布。
2. 记下执行前的数字：`question` 总行数和未删除行数、每张表的行数、`question` 旧有列的校验值（至少 `id`、`updated_at`、`knowledge_revision`）。
3. 按"学科 + 年级 + 学期"分组看旧题：有没有全部已删除的组、年级为空且学期不止一种的组、年级不在 1–12 或学期不在 1–2 的组、学科已被删除的题。
4. 在一份副本上整份执行 `0011`，在另一份副本上逐条执行，两份结果必须一致。
5. 执行后核对：题目总数、未删除数和旧有列的校验值都没变；`review_status` 全部为 `approved`；没有 `paper_id` 为空的题；`source='history'` 的卷子数等于第 3 步的组数，其中全是已删除题的组对应的卷子 `deleted=1`；题目和它的历史卷子在学科、年级、学期上完全一致（不一致的条数为 0）；5.2 列出的 17 张表都有 `student_id` 且全为 1；其余各表行数不变；`PRAGMA foreign_key_check` 和 `integrity_check` 干净；三个索引都在。
6. 把 `0011` 再整份执行一次，确认它在第一条语句就停下（表已存在），数据没有任何变化。
7. 记下题目最多的那份历史卷子有多少道题。
8. 记下迁移前 `/api/stats/summary` 和 `/api/stats/analysis/full` 的返回，新后端部署后再取一次，必须完全相同（旧题全部是 approved）。

- [ ] **Step 3: 在正式库执行迁移**（需用户同意）

执行前：打开维护开关 `write_maintenance`（做法见 `docs/cloudflare-migration-status.md` 的"备份与恢复"），记下 Time Travel 书签，保留 Step 2 的导出文件。然后按该文档的迁移命令执行 `0011`，在正式库上重复 Step 2 第 5 项的核对，与演练结果逐项比对。核对通过后关闭维护开关，并确认旧版页面还能正常用（打开首页、改一道题、手工加一道题），再进入 Step 4。顺序固定为：迁移 → 后端 → 前端。

**迁移中途失败时**：不要重新执行整个文件（建表和加列的语句不能重复执行，会在第一条就报错）。先查清楚停在哪里：三张新表是否存在、`PRAGMA table_info(question)`、`SELECT COUNT(*) FROM paper WHERE source='history'`、`SELECT COUNT(*) FROM question WHERE paper_id IS NULL`。首选做法是用 Time Travel 恢复到执行前的书签（维护开关开着，不会丢写入），修好问题后整份重跑。只有恢复不可用时，才把"失败的那一条及之后的语句"单独做成一个文件执行；回填旧题的两条语句可以重复执行，不会建出重复的历史卷子。任何不一致都停下来报告，不继续部署。

- [ ] **Step 4: 部署后端，再部署前端**（各需用户同意）

按 `docs/cloudflare-migration-status.md` 的日常部署命令。部署后核对：`/health` 正常；登录后首页、错题页、统计页能打开且数字与部署前一致；`GET /api/intake/guide?subject=数学` 返回六年级的考点清单；待核对页显示"都处理完了"；卷子页能看到历史记录，题目数加起来等于未删除的旧题数；打开题目最多的那份历史记录，先显示 50 道，"加载更多"能一直加载到底。

- [ ] **Step 5: 安装录入规范并配置口令**（需用户同意）

在用户电脑上运行 `python tools/easyfix-intake/install.py`（Task 0 Step 5 没能确认 Codex 读取 `~/.agents/skills/` 时加 `--codex-pointer`），把输出给用户看。访问口令由用户自己填进 `~/.easyfix/intake.json`；如果用户手头没有口令，说明需要重新设置 Worker 的 `ACCESS_TOKEN` 并征得同意后按迁移状态文档的密钥流程处理。全程不在对话和输出里显示口令。然后运行 `python ~/.claude/skills/easyfix-intake/easyfix_intake.py guide --subject 数学`，确认能取到资料。

- [ ] **Step 6: 实测验收**（与用户一起）

请用户在主目录 `D:\code\easyfix` 里分别新开一个 Claude 对话和一个 Codex 对话，各贴一份真实卷子的照片，只说"录入错题"。逐项确认：

- 它用上了录入规范（先取资料、只问了一句"这是哪份作业或卷子"、没有直接写数据库、没有临时写脚本）。
- 回答"跳过"时，卷子名称是"学科 + 习题 + 日期"；回答了名称和分数时，卷子页上显示正确。
- 每道题的原图是它所在的那一页。
- 没有把做对的题录进来；拿不准的题出现在待核对页，原因和说明看得懂。
- 在待核对页分别试一次"通过""编辑后通过""做对了，移除"，首页数字和统计随之变化。
- 手机上打开待核对页和卷子页能正常操作。

任何一项不符合，记下来和用户商量是当场修还是另开任务。

- [ ] **Step 7: 记录并收尾**

在 `docs/cloudflare-migration-status.md` 追加"变更记录：录入规范与卷子记录"，写明分支、提交、迁移、备份文件名和校验值、部署结果、验收结论、未完成或未验证的事项。更新启动文档的进度表和路线图的状态行。提交。推送到远端 `main` 前再问用户一次。

```bash
git add docs/cloudflare-migration-status.md docs/superpowers/specs/2026-11-10-project1-kickoff.md docs/superpowers/specs/2026-11-10-optimization-roadmap.md
git commit -m "docs: record project 1 release"
```
