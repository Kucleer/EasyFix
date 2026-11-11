# 考点掌握度与知识星空 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 给每个考点建立随做题结果变化的掌握度，并用红黄绿配色、会动的关系图（知识星空）展示，带首页缩略图、点亮时刻和管理设置里的手动调整。

**Architecture:** 掌握度在读取时现算：后端用三条 SQL 取出事件（错题、练习结果、手动调整），交给纯函数模块 `mastery_model.py` 计算，再由 `starmap.py` 组装成一次性返回的接口。教材章节、先学后学连线、英语语法新体系作为种子数据，由生成脚本产出迁移。前端用一个 canvas 绘制组件（d3-force 布局 + d3-zoom 缩放）同时服务星空页和首页缩略图。

**Tech Stack:** Cloudflare Python Worker（FastAPI）+ D1（SQLite）；Vue 3 `<script setup>` + Element Plus + Pinia；新增 `d3-force@3.0.0`、`d3-zoom@3.0.0`。

**Spec:** `docs/superpowers/specs/2026-11-11-knowledge-starmap-design.md`（下称"设计"）。视觉以 `docs/superpowers/specs/2026-11-11-knowledge-starmap-demo.html` 的"红黄绿"模式为准。

## Global Constraints

- 所有命令在工作树 `D:\code\easyfix\.claude\worktrees\project-optimization-plan-b28c5c` 执行；不进入、不修改主目录 `D:\code\easyfix`。
- 生产代码在 `cloudflare/src/` 与 `frontend/src/`；`backend/app/` 是旧代码，不改。
- 数据库结构只追加 `cloudflare/migrations/` 迁移；新表都有 `deleted INTEGER NOT NULL DEFAULT 0` 和 `student_id INTEGER NOT NULL DEFAULT 1`（`knowledge_link`、`textbook_section_point` 这类纯目录表除外，只要 `deleted`）；只做软删除，查询必须过滤 `deleted=0`。
- 统计与掌握度计算只用"算数的题"：错题条件引用 `question_scope.counted('q')`。
- 保持 Workers 免费计划：一次星空请求固定条数的 SQL，不按考点逐个查询。
- 掌握度常量（设计 4.2–4.4、5.3）：起点 `0.5`，每次错 `−0.15`、每次对 `+0.15`，下限 `0.15`，上限 `1`；底层 N=`3`；上层 N=`min(3 × 底层考点数, 30)`，比例 `0.9`；手动调整 `up_small=+0.15`、`up_large=+0.35`、`down_small=−0.15`、`set_mastered=设为 1`；词汇阶段阈值 `0.25/0.5/0.75/1.0`。全部写成 `mastery_model.py` 里的常量。
- 状态分档（设计 4.5）：没学；`0.15–0.4` 薄弱；`0.4–0.7` 一般；`0.7–<1` 较好；`1` 掌握。颜色按掌握度连续渐变：`0.15→0.55` 红 `rgb(235,87,87)` 到黄 `rgb(242,201,76)`，`0.55→1` 黄到绿 `rgb(88,214,141)`；没学 `rgb(110,112,124)`。
- "已掌握 X 颗"和点亮时刻只数最底层考点。
- 星空页不画星芒，只用光晕大小和强弱表示掌握度；悬停不压暗其他星。
- 代码规范：`snake_case`，函数前中文文档字符串，复杂逻辑中文行内注释；前端 Composition API + `<script setup>` + Element Plus。
- 不提交 `frontend/dist`（构建会改动它，结束前 `git checkout -- frontend/dist`）；不提交 `tmp/`、`backups/`。
- 不连接正式环境、不运行 Wrangler，Task 10 除外且每步要用户同意。
- 交流、注释、页面文字用中文。

## Review Focus

1. 只有手动调整、没有任何错题和练习结果的考点：手动调整算作"有记录"，考点变为学过，从 0.5 起按调整计算（Task 2 `test_adjust_only_point_counts_as_learned`、Task 3 `test_starmap_adjust_only_point_is_learned`）。
2. 错题关联了已软删除的考点、关联本身已软删除、错题待核对或已移除：一律不计入（Task 3 `test_starmap_ignores_deleted_and_pending`）。
3. 练习卷已删除、练习题已删除、`is_correct` 为空（还没批改）：不计入（Task 3 同一测试）。
4. 单词本为空：词汇星团比例为 0、阶段 0，不报错（Task 3 `test_starmap_vocab_empty`）。
5. 同一时刻的错题和练习结果、重新批改过的练习卷：错题排在前面，练习只认最新批改（Task 2 `test_same_time_wrong_before_right`）。

---

## 文件结构

| 文件 | 职责 |
|------|------|
| `cloudflare/migrations/0012_starmap.sql` | 新表与新列（Task 1） |
| `cloudflare/migrations/0013_starmap_seed.sql` | 种子数据，由脚本生成（Task 4） |
| `cloudflare/src/mastery_model.py` | 纯函数：事件排序、底层/上层掌握度、状态、词汇阶段、点亮集合（Task 2） |
| `cloudflare/src/starmap.py` | 取数与接口（Task 3） |
| `cloudflare/scripts/starmap_seed/*.json` | 英语语法体系、章节对应、先学后学连线（Task 4） |
| `cloudflare/scripts/build_starmap_seed.py` | 从 JSON 生成 0013（Task 4） |
| `cloudflare/scripts/starmap_retag.py` | 从映射文件生成英语重新打标的 SQL（Task 5） |
| `cloudflare/scripts/starmap_test.py` | 后端测试（Task 1–5） |
| `frontend/src/components/starmap/starmapColors.js` (+ `.test.mjs`) | 颜色与状态文字（Task 6） |
| `frontend/src/components/starmap/starmapEngine.js` | canvas 绘制与动画（Task 6） |
| `frontend/src/components/starmap/StarCanvas.vue` | 绘制组件（Task 6） |
| `frontend/src/api/starmap.js` | 接口封装（Task 7） |
| `frontend/src/views/StarMap.vue` | 星空页（Task 7） |
| `frontend/src/components/StarMapCard.vue` | 首页缩略图（Task 8） |
| `frontend/src/components/StarMapSettings.vue` | 管理设置里的"知识星空"栏（Task 9） |

---

### Task 1: 迁移 0012

**Files:**
- Create: `cloudflare/migrations/0012_starmap.sql`
- Create: `cloudflare/scripts/starmap_test.py`

**Interfaces:**
- Produces（表与列，后续任务按此读写）：
  - `knowledge_point.learn_grade INTEGER`（可空；英语语法考点"大约几年级学"）
  - `textbook_section(id INTEGER PRIMARY KEY, student_id, subject_id INTEGER NOT NULL, textbook TEXT NOT NULL, chapter_no INTEGER NOT NULL, chapter_name TEXT NOT NULL, section_no TEXT NOT NULL, section_name TEXT NOT NULL, sort_order INTEGER NOT NULL, deleted, created_at TEXT)`，`section_no` 形如 `'4.2'`
  - `textbook_section_point(id INTEGER PRIMARY KEY, section_id INTEGER NOT NULL, knowledge_point_id INTEGER NOT NULL, deleted, created_at TEXT)`
  - `knowledge_link(id INTEGER PRIMARY KEY, from_point_id INTEGER NOT NULL, to_point_id INTEGER NOT NULL, deleted, created_at TEXT)`（先学 → 后学）
  - `mastery_adjustment(id INTEGER PRIMARY KEY, student_id, knowledge_point_id INTEGER NOT NULL, kind TEXT NOT NULL, created_at TEXT NOT NULL, deleted)`，`kind` ∈ `up_small/up_large/set_mastered/down_small`
  - 部分索引：`mastery_adjustment(knowledge_point_id) WHERE deleted=0`、`textbook_section_point(knowledge_point_id) WHERE deleted=0`
  - 测试助手 `build_database() -> sqlite3.Connection`：旧库结构 + 0011 + 0012，种子数据见 Step 1
- 不建外键触发器；`CREATE TABLE IF NOT EXISTS`、`CREATE INDEX IF NOT EXISTS`。

- [ ] **Step 1: 写测试骨架和迁移测试**

`starmap_test.py` 照 `intake_test.py` 的写法：`configure_output()`、复用 `knowledge_invariants_test.SQLiteDB`、`intake_test.build_legacy_database()` 建旧库，依次执行 0011、0012；`check(name, fn)` 登记、`main()` 汇总"通过/失败"并以失败数为退出码。种子：数学（subject 1）一级 `有理数`(100)、二级 `有理数加减`(101)、`有理数乘方`(102)；一级 `线段与角`(110)、二级 `线段和差与中点`(111)、`角平分线`(112)；一级 `分数基础`(120)、二级 `分数大小比较`(121)；英语（subject 2）一级 `动词时态`(200)、二级 `一般现在时`(201, learn_grade 3)、`现在完成时`(202, learn_grade 8)。

```python
def test_migration_adds_tables_and_column():
    db = build_database()
    cols = {r[1] for r in db.execute('PRAGMA table_info(knowledge_point)')}
    assert 'learn_grade' in cols
    for table in ('textbook_section', 'textbook_section_point', 'knowledge_link', 'mastery_adjustment'):
        names = {r[1] for r in db.execute('PRAGMA table_info(%s)' % table)}
        assert 'deleted' in names, table
    assert 'student_id' in {r[1] for r in db.execute('PRAGMA table_info(mastery_adjustment)')}

def test_migration_is_rerunnable():
    db = build_database()
    db.executescript(MIGRATION_0012.read_text(encoding='utf-8'))   # 再执行一次不报错
```

- [ ] **Step 2: 运行，确认失败**：`python cloudflare/scripts/starmap_test.py`，预期迁移文件不存在而失败。
- [ ] **Step 3: 写 `0012_starmap.sql`**：按 Interfaces 建表建索引。`ALTER TABLE knowledge_point ADD COLUMN learn_grade INTEGER` 不能重复执行——测试 `test_migration_is_rerunnable` 只要求建表和索引语句可重跑，所以把 `ALTER` 放在文件第一条语句，测试重跑时去掉第一条语句再执行（用 `sqlite3.complete_statement` 逐条切分）。文件头注释写明"`ALTER` 不可重复执行，其余可重复"。
- [ ] **Step 4: 运行，确认通过**：`python cloudflare/scripts/starmap_test.py`，预期 `2 通过，0 失败`。
- [ ] **Step 5: 提交**

```bash
git add cloudflare/migrations/0012_starmap.sql cloudflare/scripts/starmap_test.py
git commit -m "feat: add migration 0012 for knowledge star map tables"
```

---

### Task 2: 掌握度纯函数 `mastery_model.py`

**Files:**
- Create: `cloudflare/src/mastery_model.py`
- Modify: `cloudflare/scripts/starmap_test.py`

**Interfaces:**
- Produces（`starmap.py` 调用）：
  - 常量：`START=0.5`、`STEP=0.15`、`FLOOR=0.15`、`LEAF_N=3`、`UPPER_FACTOR=3`、`UPPER_CAP=30`、`UPPER_RATIO=0.9`、`ADJUST={'up_small': 0.15, 'up_large': 0.35, 'down_small': -0.15, 'set_mastered': None}`、`VOCAB_STAGES=(0.25, 0.5, 0.75, 1.0)`
  - 事件：`dict(kind='wrong'|'right'|'adjust', at=str, seq=int, adjust=str|None)`；`seq` 是同一时刻内的次序（错题 0、练习 1、调整 2）
  - `sort_events(events: list[dict]) -> list[dict]`：按 `(at, seq)` 升序
  - `leaf_mastery(events: list[dict]) -> float`
  - `upper_mastery(child_values: list[float], events: list[dict], leaf_count: int, has_unlearned: bool) -> float`
  - `status_of(value: float | None) -> str`：`None→'unlearned'`，`<0.4→'weak'`，`<0.7→'fair'`，`<1→'good'`，`1→'mastered'`
  - `recent_results(events: list[dict], limit: int = 3) -> list[str]`：最近 `limit` 次 `'right'/'wrong'`，从旧到新
  - `vocab_progress(mastered: int, total: int) -> dict(ratio=float, stage=int)`
  - `lighting(current: set[int], seen: set[int] | None) -> tuple[set[int], set[int]]`：返回 `(to_play, seen_after)`；`seen` 为 `None`（从未记录）时 `to_play=set()`、`seen_after=current`；否则 `to_play=current-seen`、`seen_after=seen & current`
- 不导入 `fastapi`、`database`，不读时钟。

- [ ] **Step 1: 写测试**

```python
from mastery_model import (leaf_mastery, upper_mastery, status_of, recent_results, vocab_progress,
                           lighting, sort_events)

def ev(kind, at, adjust=None):
    """测试用事件。"""
    return {'kind': kind, 'at': at, 'seq': {'wrong': 0, 'right': 1, 'adjust': 2}[kind], 'adjust': adjust}

def test_leaf_example_from_spec():
    # 设计 4.2 的例子：0.5 → 错 0.35 → 错 0.2 → 对 0.35 → 对 0.5 → 对（最近 3 次全对）→ 1
    events = [ev('wrong', '1'), ev('wrong', '2'), ev('right', '3'), ev('right', '4')]
    assert abs(leaf_mastery(events) - 0.5) < 1e-9
    assert leaf_mastery(events + [ev('right', '5')]) == 1

def test_leaf_floor_and_no_events():
    assert leaf_mastery([]) == 0.5
    assert abs(leaf_mastery([ev('wrong', str(i)) for i in range(6)]) - 0.15) < 1e-9

def test_leaf_mastered_then_wrong():
    events = [ev('right', '1'), ev('right', '2'), ev('right', '3'), ev('wrong', '4')]
    assert abs(leaf_mastery(events) - 0.85) < 1e-9          # 从 1 扣 0.15

def test_adjustments():
    assert abs(leaf_mastery([ev('adjust', '1', 'up_large')]) - 0.85) < 1e-9
    assert leaf_mastery([ev('adjust', '1', 'set_mastered')]) == 1
    # 手动调整不算进最近 3 次：对、对、调整、对 → 仍是最近 3 次全对
    assert leaf_mastery([ev('right', '1'), ev('right', '2'), ev('adjust', '3', 'down_small'), ev('right', '4')]) == 1

def test_adjust_only_point_counts_as_learned():
    assert abs(leaf_mastery([ev('adjust', '1', 'down_small')]) - 0.35) < 1e-9

def test_same_time_wrong_before_right():
    events = sort_events([ev('right', '2026-11-01'), ev('wrong', '2026-11-01')])
    assert [e['kind'] for e in events] == ['wrong', 'right']

def test_upper_rules():
    rights = [ev('right', str(i)) for i in range(9)]
    assert upper_mastery([1, 1, 1], rights, 3, False) == 1              # N=9，9 次全对
    assert upper_mastery([1, 1, 1], rights[:8], 3, False) == 0.99       # 不足 N 次：封顶 0.99
    assert upper_mastery([1, 1, 1], rights, 3, True) == 0.99            # 有没学的子考点
    eight_of_nine = rights[:8] + [ev('wrong', '9')]
    assert upper_mastery([1, 1, 0.85], eight_of_nine, 3, False) < 1     # 8/9 < 0.9
    assert abs(upper_mastery([0.5, 0.3], [], 2, False) - 0.4) < 1e-9    # 平均值
    # N 封顶 30：11 个考点 N=30
    assert upper_mastery([1] * 11, [ev('right', str(i)) for i in range(30)], 11, False) == 1

def test_status_and_recent():
    assert [status_of(v) for v in (None, 0.15, 0.4, 0.7, 0.99, 1)] == ['unlearned', 'weak', 'fair', 'good', 'good', 'mastered']
    assert recent_results([ev('wrong', '1'), ev('adjust', '2', 'up_small'), ev('right', '3')]) == ['wrong', 'right']

def test_vocab_progress():
    assert vocab_progress(0, 0) == {'ratio': 0, 'stage': 0}
    assert vocab_progress(334, 970)['stage'] == 1
    assert vocab_progress(970, 970) == {'ratio': 1, 'stage': 4}

def test_lighting():
    assert lighting({1, 2}, None) == (set(), {1, 2})
    assert lighting({1, 2, 3}, {1, 4}) == ({2, 3}, {1})
```

- [ ] **Step 2: 运行，确认失败**（`mastery_model` 不存在）。
- [ ] **Step 3: 实现 `mastery_model.py`**：`leaf_mastery` 先 `sort_events`，逐个处理（错/对 ±STEP，调整按 ADJUST，`set_mastered` 设为 1），每步夹在 `[FLOOR, 1]`；处理完后，若"对/错"事件不少于 `LEAF_N` 且最后 `LEAF_N` 个全为 `right`，返回 1。`upper_mastery`：值 = `child_values` 平均（空列表返回 `START`）；N = `min(UPPER_FACTOR * leaf_count, UPPER_CAP)`；对/错事件不少于 N、最后 N 个里 `right` 比例 ≥ `UPPER_RATIO` 且 `not has_unlearned` 时返回 1，否则返回 `min(平均值, 0.99)`。
- [ ] **Step 4: 运行，确认通过。**
- [ ] **Step 5: 提交**：`git commit -m "feat: add mastery model pure functions"`（只加这两个文件）。

---

### Task 3: 取数与接口 `starmap.py`

**Files:**
- Create: `cloudflare/src/starmap.py`
- Modify: `cloudflare/src/main.py`（注册路由）、`cloudflare/src/cache.py`（`PATHS` 加 `'/api/starmap'`）
- Modify: `cloudflare/scripts/starmap_test.py`

**Interfaces:**
- Consumes: Task 2 全部函数；`question_scope.counted`、`current_student_id`；`settings.load(request, name, default)` / `settings.store(request, name, value)`
- 配置（`runtime_config`，经 `settings.load/store`）：`'starmap'` = `{"progress": {"<subject_id>": "4.2"}, "seen": {"<subject_id>": [point_id, ...]}}`；读不到时 `progress` 为空、`seen` 为 `None`
- Produces（前端 Task 7–9 使用）：
  - `GET /api/starmap?subject_id=1` →
    ```json
    {"subject_id": 1, "subject_name": "数学", "mastered_count": 7,
     "nodes": [{"id": 101, "name": "有理数加减", "level": 2, "parent_id": 100,
                "value": 0.5, "status": "fair", "recent": ["wrong", "right"], "wrong_count": 2}],
     "links": [{"source": 100, "target": 101, "kind": "belongs"}, {"source": 101, "target": 102, "kind": "prereq"}],
     "vocab": null, "to_play": [101]}
    ```
    没学的考点 `value` 为 `null`、`status` 为 `"unlearned"`；英语时 `vocab = {"mastered": 334, "total": 970, "ratio": 0.344, "stage": 1}`。只返回 `level` 1、2 的未删除考点。
  - `POST /api/starmap/seen` 请求 `{"subject_id": 1, "point_ids": [101]}` → `{"seen": [..]}`；存入 `seen[subject] = 旧 seen ∩ 当前已掌握 ∪ point_ids∩当前已掌握`
  - `GET /api/starmap/adjustments?subject_id=1` → `[{"id", "knowledge_point_id", "point_name", "kind", "created_at"}]`（未撤销，按时间倒序）
  - `POST /api/starmap/adjustments` 请求 `{"knowledge_point_id": 101, "kind": "up_small"}` → 201 新记录；对一级考点的调整展开成它每个已学二级考点各一条；`kind` 不合法 422；考点不存在 404
  - `DELETE /api/starmap/adjustments/{id}` → 204（软删除）
  - `GET /api/starmap/progress?subject_id=1` → `{"section_no": "4.2", "sections": [{"section_no", "section_name", "chapter_name"}]}`；`PUT` 同路径请求 `{"section_no": "4.1"}`，不存在的节 422
- 函数（便于测试）：`async def load_events(db, subject_id) -> dict[int, list[dict]]`、`async def learned_point_ids(db, request, subject_id, events) -> set[int]`、`async def build_starmap(db, request, subject_id) -> dict`
- 取数用三条 SQL：
  1. 错题：`question q JOIN question_knowledge_point qk (qk.deleted=0) JOIN knowledge_point k (k.deleted=0) LEFT JOIN paper p`，条件 `counted('q') AND q.subject_id=?`；时间 = `CASE WHEN p.source='history' OR p.paper_date IS NULL THEN q.created_at ELSE p.paper_date END`
  2. 练习：`practice_set_question pq JOIN practice_set ps (ps.deleted=0) JOIN question q (counted('q'), q.subject_id=?) JOIN question_knowledge_point qk ...`，条件 `pq.deleted=0 AND pq.is_correct IS NOT NULL`；时间 = `ps.last_reviewed_at`
  3. 调整：`mastery_adjustment WHERE deleted=0 AND student_id=?` 关联考点学科
- "学过"规则（设计 5.4）：有事件的考点算学过；数学按 `progress` 的节，`textbook_section.sort_order` 不大于当前节的节所对应的二级考点算学过；一个二级考点没有对应到任何节时，看同一模块里其他考点对应的章：该模块有对应章且章号大于当前章 → 没学，否则学过；模块完全没有对应章 → 学过；英语：`learn_grade IS NULL OR learn_grade <= 应用默认年级` 算学过；`progress` 未设置时，有章节数据的学科全部按"学过"处理。
- 词汇：`word` 表 `deleted=0`；已掌握 = `review_count>0 AND correct_count*100.0/review_count>80`。只在学科名为"英语"时返回。

- [ ] **Step 1: 写测试**（照 `intake_test.fake_request`/`call_endpoint` 的方式调用接口函数；种子沿用 Task 1，另插错题、练习、调整）

```python
def test_starmap_basic_math():
    # 101 有两道错题、之后练习对 1 次；102 无事件；章节：4.1→111，4.2→112；进度 4.1
    body = call(build_starmap, subject_id=1)
    node = {n['id']: n for n in body['nodes']}
    assert abs(node[101]['value'] - 0.35) < 1e-9 and node[101]['status'] == 'weak'
    assert node[101]['recent'] == ['wrong', 'wrong', 'right'] and node[101]['wrong_count'] == 2
    assert node[102]['value'] == 0.5                       # 有理数没有章节对应 → 学过
    assert node[111]['status'] == 'fair' and node[112]['status'] == 'unlearned'
    assert node[121]['value'] == 0.5                       # 课本外模块 → 学过
    assert {'source': 100, 'target': 101, 'kind': 'belongs'} in body['links']
    assert body['vocab'] is None

def test_starmap_ignores_deleted_and_pending():
    # 待核对错题、软删除错题、软删除关联、软删除考点、删除的练习卷、未批改练习题：都不影响 101
    ...断言 101 的 value、recent、wrong_count 与只有有效数据时相同

def test_starmap_adjust_only_point_is_learned():
    # 给 112（进度之后，没学）加一条 up_small → status 不再是 unlearned，value 0.65
    ...

def test_starmap_english_learn_grade_and_vocab():
    # 应用默认年级 6：201(learn_grade 3) 学过，202(learn_grade 8) 没学；word 3 条，2 条掌握
    ...断言 202 status unlearned，vocab == {'mastered': 2, 'total': 3, 'ratio': 2/3, 'stage': 2}

def test_starmap_vocab_empty():
    ...没有 word 行时 vocab == {'mastered': 0, 'total': 0, 'ratio': 0, 'stage': 0}

def test_starmap_lighting_flow():
    # 第一次请求 to_play 为空；让 101 掌握（再加两次练习对）后 to_play == [101]；
    # POST seen [101] 后再请求 to_play 为空；再加一道错题让 101 掉出，再练对 3 次 → to_play 又是 [101]
    ...

def test_adjustment_endpoints():
    # 新增 up_small 201；对一级 100 的调整展开成 101、102 各一条；kind='bad' → 422；
    # 不存在的考点 → 404；DELETE 后列表里没有、掌握度恢复
    ...

def test_progress_endpoints():
    # GET 返回 sections 按 sort_order；PUT 4.2 后 112 变学过；PUT '9.9' → 422
    ...

def test_starmap_query_count_is_fixed():
    # 包一层计数的 db，两个规模（2 个考点 / 20 个考点）下 build_starmap 的 SQL 条数相同
    ...
```

（`...` 处由实施者按注释写成真正的断言；注释里的数字就是期望值。）

- [ ] **Step 2: 运行，确认失败。**
- [ ] **Step 3: 实现 `starmap.py`**，在 `main.py` 里 `include_router`，在 `cache.py` 的 `PATHS` 加 `'/api/starmap'`。上层考点：`child_values` 只取已学子考点的值，`events` 为所有子考点事件合并，`leaf_count` 为子考点数，`has_unlearned` 为是否有没学的子考点；一级考点全部子考点都没学且自身无事件时，一级考点也是没学。`mastered_count` = 二级考点中 `value == 1` 的个数。`to_play` 用 `lighting(当前已掌握二级考点, seen)`；`seen` 为 `None` 时把 `seen_after` 写回配置（只在这种情况下 GET 会写配置）。
- [ ] **Step 4: 运行全部后端测试**：`python cloudflare/scripts/starmap_test.py`、`intake_test.py`、`knowledge_invariants_test.py`、`phrase_focus_test.py`、`local_dev_server_test.py`，全部通过；`python -m compileall -q cloudflare/src`。
- [ ] **Step 5: 提交**：`git commit -m "feat: add star map API with mastery computed on read"`。

---

### Task 4: 种子数据（需要用户审阅）

**Files:**
- Create: `cloudflare/scripts/starmap_seed/english_grammar.json`、`math_sections.json`、`links.json`
- Create: `cloudflare/scripts/build_starmap_seed.py`
- Create: `cloudflare/migrations/0013_starmap_seed.sql`（由脚本生成）
- Modify: `cloudflare/scripts/starmap_test.py`

**Interfaces:**
- JSON 格式：
  - `english_grammar.json`：`[{"code": "EG-TEN", "name": "动词时态", "level": 1, "sort_order": 100}, {"code": "EG-TEN-01", "name": "一般现在时", "level": 2, "parent_code": "EG-TEN", "learn_grade": 3, "sort_order": 101}, ...]`；来源《义务教育英语课程标准（2022 年版）》附录语法项目，另加"语音""交际用语"两个一级模块（同一课标的语言知识部分）。英语学科编号在生成时按名称 `英语` 查。
  - `math_sections.json`：`[{"textbook": "沪教版（五四制，2024）六年级上册", "chapter_no": 4, "chapter_name": "线段与角", "section_no": "4.2", "section_name": "角", "sort_order": 42, "point_codes": ["M6-..."]}, ...]`，覆盖设计 5.1 的 13 节（含"综合与实践"不对应考点）。数学考点用现有 `code`（见 `knowledge_grade6_catalog.json`）。
  - `links.json`：`[{"from": "<code>", "to": "<code>"}]`，数学和英语都写。
- `build_starmap_seed.py`：读三个 JSON，输出 0013。所有插入都用 `INSERT ... SELECT ... WHERE NOT EXISTS (按 code / 按 (textbook, section_no) / 按 (from, to))`，可重复执行；考点 id 用子查询按 `code` 查，不写死；`knowledge_point` 的插入沿用 0009 的字段（`code, name, name_key, level, parent_id, subject_id, grade, sort_order, deleted, created_at, updated_at`），英语新考点 `grade` 为 NULL；插入考点后递增 `runtime_config` 的 `taxonomy_version`。
- 生成脚本在 JSON 引用了不存在的 `code` 时报错退出。

- [ ] **Step 1: 起草三个 JSON**（实施者按设计 5.1、5.2、5.5 起草；数学节号、节名照设计 5.1 的目录；先学后学连线按课本顺序和知识依赖）。
- [ ] **Step 2: 写测试**：

```python
def test_seed_sql_applies_and_is_rerunnable():
    db = build_database_with_catalog()          # 旧库 + 0011 + 0012 + knowledge_grade6_catalog.json 种子
    sql = SEED_0013.read_text(encoding='utf-8')
    db.executescript(sql); first = snapshot(db)
    db.executescript(sql); assert snapshot(db) == first
    assert db.execute("SELECT COUNT(*) FROM textbook_section WHERE deleted=0").fetchone()[0] == 13
    assert db.execute("SELECT COUNT(*) FROM knowledge_point WHERE code LIKE 'EG-%' AND level=2 AND learn_grade IS NULL").fetchone()[0] == 0

def test_seed_builder_rejects_unknown_code():
    ...links 里放一个不存在的 code，build_starmap_seed 抛出含该 code 的错误
```

- [ ] **Step 3: 实现 `build_starmap_seed.py`，生成 0013。**
- [ ] **Step 4: 运行测试，确认通过。**
- [ ] **Step 5: 提交**：`git commit -m "feat: add star map seed data and generator"`。
- [ ] **Step 6: 交用户审阅**（控制者做）：把英语语法清单（含年级）、数学节与考点对应、先学后学连线整理成一页中文清单给用户看；按用户意见改 JSON、重新生成、重跑测试、再提交。审阅通过才能进入 Task 10。

---

### Task 5: 英语重新打标工具

**Files:**
- Create: `cloudflare/scripts/starmap_retag.py`
- Modify: `cloudflare/scripts/starmap_test.py`

**Interfaces:**
- 输入映射文件（放在被忽略的 `tmp/starmap/retag.json`，不提交）：`[{"question_id": 123, "point_codes": ["EG-TEN-04"], "primary_code": "EG-TEN-04"}, {"question_id": 124, "point_codes": [], "primary_code": null}]`（空列表 = 词汇类，不进语法星空）
- `build_retag_sql(mapping: list[dict], old_codes_prefix: str = 'E6-') -> str`：生成一个 SQL 文件：
  1. 映射里每道题：软删除它所有未删除的 `question_knowledge_point`；按 `point_codes` 插入新关联（`source='retag'`，主考点 `is_primary=1`）；更新 `question.knowledge_point` 为主考点名称（无主考点为 NULL）、`knowledge_revision = knowledge_revision + 1`。
  2. 软删除 `code LIKE 'E6-%'` 的旧英语考点。
  3. 递增 `taxonomy_version`、`data_revision`。
  - 每条语句都可以重复执行而结果不变（插入用 `WHERE NOT EXISTS`）。
- 命令行：`python cloudflare/scripts/starmap_retag.py tmp/starmap/retag.json tmp/starmap/retag.sql`

- [ ] **Step 1: 写测试**：在测试库里放 3 道英语题（2 道有旧 `E6-` 关联），映射成新考点和空列表；执行生成的 SQL 两次；断言旧关联全部 `deleted=1`、新关联各一条且主考点正确、空映射的题没有未删除关联、`E6-` 考点全部 `deleted=1`、数学关联不变；`intake.load_catalog(db, 英语, 6, 1)` 只返回 `EG-` 考点。
- [ ] **Step 2: 运行，确认失败。**
- [ ] **Step 3: 实现。**
- [ ] **Step 4: 运行，确认通过。**
- [ ] **Step 5: 提交**：`git commit -m "feat: add English retag SQL builder"`。

（映射文件本身在 Task 10 由控制者只读正式库题目后起草，拿不准的题给用户看。）

---

### Task 6: 绘制组件

**Files:**
- Modify: `frontend/package.json`、`frontend/package-lock.json`（`npm --prefix frontend install d3-force@3.0.0 d3-zoom@3.0.0`）
- Create: `frontend/src/components/starmap/starmapColors.js`、`starmapColors.test.mjs`、`starmapEngine.js`、`StarCanvas.vue`

**Interfaces:**
- Consumes: Task 3 的 `nodes`、`links`、`vocab` 结构
- Produces:
  - `starmapColors.js`：`colorOf(value: number | null) -> string`（`'r,g,b'`，按 Global Constraints 的渐变）；`statusText(status: string) -> string`（`unlearned→'还没学'`、`weak→'薄弱'`、`fair→'一般'`、`good→'较好'`、`mastered→'已掌握'`）
  - `starmapEngine.js`：`createStarEngine(canvas: HTMLCanvasElement, data: {nodes, links, vocab}, options: {mini: boolean, background: string[]}) -> {setHover(id|null), findAt(x, y) -> node|null, screenOf(id) -> [x, y], light(ids: number[]), resize(), destroy()}`。词汇星团作为一个 `id: 'vocab'` 的特殊节点，大小随 `stage` 长大。
  - `StarCanvas.vue`：props `data`、`mini`（布尔）、`background`（背景淡字数组）；emits `hover(node|null)`、`select(node|null)`；暴露方法 `light(ids)`。
- 视觉照 demo 的红黄绿模式：圆点 + 光晕，光晕大小和强弱随掌握度；没有星芒；连线颜色取两端中间色，点亮的连线（两端掌握度都 ≥ 0.45）上有流动光点；背景微尘、淡装饰网络、淡字；整图缓慢漂移；悬停的星有扩散光环、相连线变亮变粗、流动加快，其他星不变暗；`light(ids)` 播放迸发粒子和光环。
- `document.hidden` 时停止 `requestAnimationFrame`，可见时恢复；`destroy()` 解除所有监听。
- 缩略图（`mini`）不响应缩放和悬停，粒子和背景数量减少。

- [ ] **Step 1: 写 `starmapColors.test.mjs`**：

```js
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { colorOf, statusText } from './starmapColors.js'

test('颜色按掌握度渐变', () => {
  assert.equal(colorOf(null), '110,112,124')
  assert.equal(colorOf(0.15), '235,87,87')
  assert.equal(colorOf(0.55), '242,201,76')
  assert.equal(colorOf(1), '88,214,141')
})
test('状态文字', () => {
  assert.deepEqual(['unlearned', 'weak', 'fair', 'good', 'mastered'].map(statusText), ['还没学', '薄弱', '一般', '较好', '已掌握'])
})
```

- [ ] **Step 2: 运行，确认失败**：`node --test frontend/src/components/starmap/starmapColors.test.mjs`。
- [ ] **Step 3: 安装依赖，实现四个文件**（从 demo 的 canvas 代码移植，去掉金色模式和星芒，按上面的接口拆分）。
- [ ] **Step 4: 运行颜色测试通过；`npm --prefix frontend run build` 通过；`git checkout -- frontend/dist`。**
- [ ] **Step 5: 提交**（不含 `frontend/dist`）：`git commit -m "feat: add canvas star map renderer"`。

---

### Task 7: 星空页

**Files:**
- Create: `frontend/src/api/starmap.js`、`frontend/src/views/StarMap.vue`
- Modify: `frontend/src/router/index.js`（`/star-map`）、`frontend/src/App.vue`（"成长记录"组加 `{ path: '/star-map', label: '知识星空', icon: Star }`）

**Interfaces:**
- `starmapApi`：`get(subjectId)`、`markSeen(subjectId, pointIds)`、`adjustments(subjectId)`、`addAdjustment(pointId, kind)`、`removeAdjustment(id)`、`progress(subjectId)`、`saveProgress(subjectId, sectionNo)`（对应 Task 3 的接口）
- 页面：全屏深色（占满内容区，隐藏页面内边距）；顶部左侧"数学 / 英语"切换（学科 id 从现有的学科列表接口 `GET /api/subjects` 按名称"数学""英语"取）和"已掌握 X 颗"；左下角图例（薄弱 / 一般 / 掌握 / 没学）；悬停浮出考点名称；点击在右下角显示小卡片（名称、掌握度条、`statusText`，英语词汇显示"已掌握 m / n 个词"）。
- 进入页面或切换学科时，若 `to_play` 非空：等布局稳定（约 800ms）后依次 `light(ids)`，屏幕中间浮现"点亮了 N 颗星"，播放完调用 `markSeen`。
- 背景淡字：数学用 demo 里的公式数组，英语用语法句式数组，写在页面里。

- [ ] **Step 1: 实现 `starmap.js`、`StarMap.vue`、路由和导航。**
- [ ] **Step 2: `npm --prefix frontend run build` 通过；`git checkout -- frontend/dist`。**
- [ ] **Step 3: 提交**：`git commit -m "feat: add star map page"`。

（浏览器检查由控制者在本机测试环境做，见 Task 9 Step 3。）

---

### Task 8: 首页缩略图

**Files:**
- Create: `frontend/src/components/StarMapCard.vue`
- Modify: `frontend/src/views/Home.vue`

**Interfaces:**
- 卡片标题"我的知识星空"，内含 `StarCanvas`（`mini`），左下角"X 颗星已掌握"（数学 + 英语的 `mastered_count` 之和），点击进入 `/star-map`；数据加载失败时显示一行灰字"星空暂时打不开"，不影响首页其他部分。
- 位置放在首页"学习概览"之前、紧跟页头；宽度占满一行，高度约 260px。

- [ ] **Step 1: 实现并接入首页。**
- [ ] **Step 2: 构建通过；恢复 `frontend/dist`。**
- [ ] **Step 3: 提交**：`git commit -m "feat: add star map card on home page"`。

---

### Task 9: 管理设置的"知识星空"栏 + 页面整体检查

**Files:**
- Create: `frontend/src/components/StarMapSettings.vue`
- Modify: `frontend/src/views/Management.vue`（新增 `<el-tab-pane label="知识星空" name="starmap">`）
- Modify: `cloudflare/scripts/local_dev_server.py`（种子里加入 0012、0013 的执行，使本机测试环境能显示星空）、`local_dev_server_test.py`（加一条 `GET /api/starmap?subject_id=1` 返回 200 且 `nodes` 非空的测试）

**Interfaces:**
- 栏内：学科切换；数学显示"现在学到哪一节"下拉（选项来自 `progress` 接口，保存后提示"已保存"）；考点表格（模块、考点、当前状态与掌握度条、操作下拉：提高一点 / 提高很多 / 直接设为掌握 / 降低一点）；下方"调整记录"表格，每行可撤销（二次确认）。
- 操作成功后刷新表格；失败显示接口返回的 `detail`。

- [ ] **Step 1: 实现设置栏和本机测试环境改动；`local_dev_server_test.py` 通过。**
- [ ] **Step 2: 构建通过；恢复 `frontend/dist`；提交**：`git commit -m "feat: add star map settings and local harness support"`。
- [ ] **Step 3: 浏览器检查**（控制者做，本机测试环境 + 内置浏览器，1280×800）：星空页数学/英语切换、悬停高亮且其他星不变暗、点击卡片、缩放拖动、词汇星团、点亮时刻（用设置栏"直接设为掌握"制造一颗新掌握）、首页缩略图、设置栏的进度和调整与撤销、页面切走再回来动画恢复。问题记下来修完再进入 Task 10。

---

### Task 10: 发布与验收（每一步都要用户同意）

- [ ] **Step 1: 总检查**：全部后端测试、`node --test` 前端测试、构建；按 superpowers:requesting-code-review 做整体审阅并处理意见。
- [ ] **Step 2: 起草英语重新打标映射**：只读查询正式库英语错题（题干、旧考点），起草 `tmp/starmap/retag.json`；拿不准的题列给用户确认；`starmap_retag.py` 生成 `tmp/starmap/retag.sql`。
- [ ] **Step 3: 备份并演练**：导出正式库完整备份；在本机副本上依次执行 0012、0013、`retag.sql`；核对：题目数不变；英语题的未删除新关联数与映射一致；`E6-` 考点全部软删除；数学关联数不变；`GET /api/starmap`（用本机测试环境指向副本的方式或直接调用 `build_starmap`）数学、英语都能返回且没学/学过符合 4.2 进度；把结果给用户看。
- [ ] **Step 4: 正式迁移**：打开维护开关、记录回退点；执行 0012、0013、`retag.sql`；重复 Step 3 的核对；关闭维护开关。
- [ ] **Step 5: 部署后端，再部署前端。**
- [ ] **Step 6: 验收**：用户登录后看星空页、首页缩略图、管理设置；控制者检查数字（已掌握数、词汇数）和页面。
- [ ] **Step 7: 记录**：`docs/cloudflare-migration-status.md` 追加变更记录；路线图项目 2 状态更新；推送前再问用户。
