# 词组默写优化 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 词组默写时只空出重点词（搭配词和未掌握的生词），按三档递进到完整默写，并按词记录对错。

**Architecture:** 所有判定规则（切词、标注校验、重点计算、档位升降、"牢记"判定、打印文本）集中在一个不依赖数据库的纯函数模块 `phrase_focus.py`，由 `review.py`、`words.py`、`media.py` 和新的标注路由调用。前端把字母格输入抽成独立组件，格子布局和判对放在一个可用 `node --test` 测试的纯 JS 模块里。上线后、父母触发标注前，所有词条行为与现在一致。

**Tech Stack:** Python FastAPI on Cloudflare Workers（Pyodide）+ D1；Vue 3 `<script setup>` + Element Plus；测试用内存 SQLite 的独立脚本和 `node --test`，不引入新依赖。

**Spec:** `docs/superpowers/specs/2026-11-10-phrase-dictation-design.md`（执行者必须同时阅读）

## Global Constraints

- 只改 `cloudflare/src/`、`cloudflare/migrations/`、`cloudflare/scripts/`、`frontend/src/`。不改 `backend/app/`。
- 数据库变更只追加 `cloudflare/migrations/0010_phrase_focus.sql`，不重建表，不改动任何现有计数、间隔、阶段、日志内容。
- 软删除：查询带 `deleted=0`，不做硬删除。
- Workers 免费计划：抽题、提交、打印不得按词逐条查询；一次请求内的生词对照和最近记录各用一次批量查询。LLM 标注每次请求最多 20 条、只调用一次模型。
- 间隔算法不变：答对 `min(interval*2,30)`，答错 `1`。
- 复习提交的幂等机制（`request_record` 中 `word-submit:<session_id>` 指纹）不变。
- 对错由前端判定后提交，服务端不重判。
- 单词条目（`entry_type='word'`）和未标注词组的抽题与提交结果必须与改动前一致。
- 代码规范：Python 变量 `snake_case`，每个函数前写中文文档字符串，复杂逻辑加中文行内注释；前端用 Composition API + `<script setup>`。
- 不在本地脚本或 MCP 里写生产数据；生产写入只在 Task 11、且得到用户明确同意后进行。
- 角色取值固定为 `collocation`、`content`、`plain`、`placeholder`；`focus_status` 取值固定为 `none`、`draft`、`confirmed`；档位为整数 1、2、3。

## Review Focus

1. **英文里有多余空白**（首尾空格、连续空格、制表符）：类型判定、切词、`source_english` 比对都按规范化后的结果，不能因为多一个空格就让标注失效或校验失败。测试在 Task 1。
2. **空出的词里含非字母字符**（`one's`、`o'clock`、`well-known`、句末 `?`）：非字母字符预填，孩子只输入字母，判对不受影响。测试在 Task 8。
3. **LLM 返回不合格**（token 数不对、改写了词、漏了某条、多出不认识的 id、`content` 没有 `lemma`）：不合格的条目保持 `none` 并逐条报告原因，同批合格条目正常保存。测试在 Task 6。
4. **同一场次重复提交**：幂等返回原结果，`dictation_level` 不会被再升或再降一次。测试在 Task 5。
5. **旧版前端页面提交**（缓存的旧页面不带 `token_results` 和 `dictation_level`）：照常接受；已标注词组按档位 3 计，不报错。测试在 Task 5。

---

## 文件结构

| 文件 | 职责 |
| --- | --- |
| `cloudflare/src/phrase_focus.py`（新） | 纯函数：切词、标注校验、重点计算、格子生成、档位与阶段判定、打印文本、标注结果处理 |
| `cloudflare/src/word_focus.py`（新） | 路由 `POST /api/words/focus/annotate`；数据库辅助 `load_focus_context` |
| `cloudflare/src/words.py` | 保存与批量导入接受 `entry_type`、`focus_spec`；列表筛选；`by_type` 统计 |
| `cloudflare/src/review.py` | 抽题返回 `tokens`；提交接受听力、`token_results`、`dictation_level` |
| `cloudflare/src/media.py` | 打印默写按档位输出词组 |
| `cloudflare/src/prompts.py` | 标注 prompt |
| `cloudflare/src/main.py` | 注册 `word_focus` 路由 |
| `cloudflare/migrations/0010_phrase_focus.sql`（新） | 加列与回填 |
| `cloudflare/scripts/phrase_focus_test.py`（新） | 后端全部测试，运行方式同 `knowledge_invariants_test.py` |
| `frontend/src/composables/dictation.js`（新） | 纯 JS：格子布局、判对 |
| `frontend/src/composables/dictation.test.mjs`（新） | `node --test` 测试 |
| `frontend/src/components/DictationInput.vue`（新） | 字母格输入组件 |
| `frontend/src/components/PhraseFocusEditor.vue`（新） | 重点编辑 |
| `frontend/src/views/Words.vue` | 接入以上组件；复习设置、发音规则、列表筛选、标注按钮、打印档位、统计 |
| `frontend/src/api/word.js` | 新增 `annotateFocus` |

后端测试统一运行：`python cloudflare/scripts/phrase_focus_test.py`，脚本结构（`check(name, fn)`、`main()`、失败时非零退出）照搬 `cloudflare/scripts/knowledge_invariants_test.py`。需要数据库的测试复用该文件第 85 行附近的 sqlite 适配类（从该模块导入），并在本脚本的 `SCHEMA` 中自建 `word`、`word_review_log`、`word_review`、`word_review_session`、`practice_set`、`subject`、`request_record`、`tag`、`word_tag` 表；列定义以 `backend/app/models/word.py`、`practice_set.py` 和 `knowledge_invariants_test.py` 中的现有 `SCHEMA` 为准。

---

### Task 1: 纯函数模块——切词、类型、标注校验

**Files:**
- Create: `cloudflare/src/phrase_focus.py`
- Create: `cloudflare/scripts/phrase_focus_test.py`

**Interfaces:**
- Produces:
  - `normalize_english(english: str) -> str`：去首尾空白，内部连续空白折叠为单个空格。
  - `split_tokens(english: str) -> list[str]`：`normalize_english` 后按空格切分。
  - `entry_type_of(english: str) -> str`：token 数大于 1 返回 `'phrase'`，否则 `'word'`。
  - `validate_focus_spec(spec, english: str) -> dict`：通过时返回规范化后的 `{'version':1,'source_english':..., 'tokens':[...]}`；不通过抛 `ValueError(中文原因)`。
  - `spec_active(row: dict) -> bool`：`row['focus_status']` 为 `draft` 或 `confirmed`，`row['focus_spec']`（JSON 文本）可解析，且其 `source_english == normalize_english(row['english'])`。
  - 常量 `ROLES = ('collocation','content','plain','placeholder')`。

- [ ] **Step 1: 写失败的测试**

```python
def test_tokens_and_type():
    assert normalize_english('  be   good\tat ') == 'be good at'
    assert split_tokens('help sb. with sth.') == ['help', 'sb.', 'with', 'sth.']
    assert entry_type_of('ice-cream') == 'word'
    assert entry_type_of('a.m.') == 'word'
    assert entry_type_of(' apple ') == 'word'
    assert entry_type_of('be good at') == 'phrase'

def test_validate_focus_spec():
    spec = {'tokens': [{'text': 'be', 'role': 'plain'},
                       {'text': 'proud', 'role': 'content', 'lemma': 'Proud', 'gloss': '自豪的'},
                       {'text': 'of', 'role': 'collocation'},
                       {'text': 'sb.', 'role': 'placeholder'}]}
    result = validate_focus_spec(spec, ' be  proud of sb. ')
    assert result['version'] == 1
    assert result['source_english'] == 'be proud of sb.'
    assert result['tokens'][1] == {'text': 'proud', 'role': 'content', 'lemma': 'proud', 'gloss': '自豪的'}
    assert set(result['tokens'][0]) == {'text', 'role'}          # 非 content 不保留 lemma/gloss
    for bad in (
        {'tokens': spec['tokens'][:3]},                               # 少一个 token
        {'tokens': [{**spec['tokens'][0], 'text': 'is'}, *spec['tokens'][1:]]},  # 改写了词
        {'tokens': [{**spec['tokens'][0], 'role': 'verb'}, *spec['tokens'][1:]]},  # 非法角色
        {'tokens': [spec['tokens'][0], {'text': 'proud', 'role': 'content'}, *spec['tokens'][2:]]},  # content 无 lemma
        {'tokens': 'x'}, None, [],
    ):
        expect_value_error(lambda bad=bad: validate_focus_spec(bad, 'be proud of sb.'))

def test_spec_active():
    spec = json.dumps(validate_focus_spec(SPEC_GOOD_AT, 'be good at'))
    assert spec_active({'english': 'be  good at', 'focus_status': 'draft', 'focus_spec': spec})
    assert spec_active({'english': 'be good at', 'focus_status': 'confirmed', 'focus_spec': spec})
    assert not spec_active({'english': 'be good at', 'focus_status': 'none', 'focus_spec': spec})
    assert not spec_active({'english': 'be good in', 'focus_status': 'confirmed', 'focus_spec': spec})
    assert not spec_active({'english': 'be good at', 'focus_status': 'draft', 'focus_spec': '{bad'})
    assert not spec_active({'english': 'be good at', 'focus_status': 'draft', 'focus_spec': None})
```

`SPEC_GOOD_AT` 为 be/plain、good/plain、at/collocation。`expect_value_error` 是脚本内的小助手：调用后必须抛 `ValueError`。

- [ ] **Step 2: 运行确认失败**

Run: `python cloudflare/scripts/phrase_focus_test.py`
Expected: 因 `phrase_focus` 模块不存在而失败。

- [ ] **Step 3: 实现上述函数**

`validate_focus_spec` 的规则：`tokens` 必须是列表；各项 `text` 按顺序等于 `split_tokens(english)`；`role` 属于 `ROLES`；`content` 必须有非空字符串 `lemma`（去空白、转小写后保存），`gloss` 可选，非字符串时存空字符串；其他角色只保留 `text` 和 `role`。

- [ ] **Step 4: 运行确认通过**

Run: `python cloudflare/scripts/phrase_focus_test.py`
Expected: 三项全部通过，退出码 0。

- [ ] **Step 5: Commit**

```bash
git add cloudflare/src/phrase_focus.py cloudflare/scripts/phrase_focus_test.py
git commit -m "feat: add phrase tokenization and focus spec validation"
```

---

### Task 2: 纯函数——重点计算、格子、档位与阶段

**Files:**
- Modify: `cloudflare/src/phrase_focus.py`
- Modify: `cloudflare/scripts/phrase_focus_test.py`

**Interfaces:**
- Consumes: Task 1 的 `validate_focus_spec`。
- Produces:
  - `focus_indices(spec: dict, mastered_lemmas: set[str], recent_token_results: list[list[dict]]) -> list[int]`：升序的 token 下标。`recent_token_results` 是最近若干次默写的 `token_results`（调用方已限定为最近 5 次、当前标注生效之后）。
  - `build_cells(spec: dict, stored_level: int, requested_level: int | None, focus: list[int]) -> tuple[list[dict], int]`：返回 `(tokens, effective_level)`，`tokens` 每项为 `{'text': str, 'blank': bool, 'hint': str | None}`。
  - `next_level(stored_level: int, ok: bool, review_type: int, annotated: bool) -> int`
  - `next_phase(old_phase: str | None, ok: bool, consecutive: int, interval: int, was_due: bool, annotated: bool, review_type: int, level: int) -> str`
  - 常量 `ERROR_WINDOW = 5`、`ERROR_THRESHOLD = 2`。

- [ ] **Step 1: 写失败的测试**

```python
def cloze(spec, stored, requested=None, mastered=(), recent=()):
    """把格子渲染成设计文档第 7 节的显示形式，便于断言。"""
    focus = focus_indices(spec, set(mastered), list(recent))
    tokens, level = build_cells(spec, stored, requested, focus)
    text = ' '.join((t['hint'] or '') + '_' * (len(t['text']) - len(t['hint'] or '')) if t['blank'] else t['text'] for t in tokens)
    return text, level

def test_spec_examples():
    assert cloze(SPEC_GOOD_AT, 1) == ('be good __', 1)
    assert cloze(SPEC_PROUD_OF, 1) == ('be _____ __', 1)
    assert cloze(SPEC_PROUD_OF, 1, mastered={'proud'}) == ('be proud __', 1)
    assert cloze(SPEC_LOOK_FORWARD, 1) == ('look _______ __ doing sth.', 1)
    assert cloze(SPEC_TAKE_PART_IN, 1) == ('take part __', 1)
    assert cloze(SPEC_HELP_WITH, 1) == ('help sb. ____ sth.', 1)

def test_levels_two_and_three():
    assert cloze(SPEC_HELP_WITH, 2) == ('h___ sb. w___ sth.', 2)
    assert cloze(SPEC_HELP_WITH, 3) == ('____ sb. ____ sth.', 3)
    assert cloze(SPEC_HELP_WITH, 1, requested=3) == ('____ sb. ____ sth.', 3)   # 手动选档
    assert cloze(SPEC_A_LOT_OF, 2) == ('a l__ o_', 2)                            # 单字母 token 在档位 2 不空

def test_empty_focus_falls_back_to_full():
    # 无搭配词、content 全部已掌握：本次按档位 3
    assert cloze(SPEC_ALL_CONTENT, 1, mastered={'make', 'friend'}) == ('____ _______', 3)

def test_error_driven_focus():
    wrong_good = [{'i': 1, 'ok': False}, {'i': 2, 'ok': True}]
    assert focus_indices(SPEC_GOOD_AT, set(), [wrong_good]) == [2]               # 错 1 次不够
    assert focus_indices(SPEC_GOOD_AT, set(), [wrong_good, wrong_good]) == [1, 2]
    wrong_sb = [{'i': 1, 'ok': False}]
    assert focus_indices(SPEC_HELP_WITH, set(), [wrong_sb, wrong_sb]) == [2]     # 占位符不会被加入

def test_next_level():
    assert next_level(1, True, 1, True) == 2
    assert next_level(3, True, 1, True) == 3
    assert next_level(2, False, 1, True) == 1
    assert next_level(1, False, 1, True) == 1
    assert next_level(2, True, 2, True) == 2      # 选择题不改档位
    assert next_level(2, True, 3, True) == 2      # 听力不改档位
    assert next_level(1, True, 1, False) == 1     # 未标注不改

def test_next_phase():
    args = dict(consecutive=3, interval=8, was_due=False)
    # 未标注或单词：与旧公式一致
    assert next_phase('在途', True, annotated=False, review_type=2, level=3, **args) == '牢记'
    assert next_phase('牢记', True, consecutive=1, interval=8, was_due=True, annotated=False, review_type=1, level=3) == '遗忘点'
    assert next_phase('牢记', False, annotated=False, review_type=1, level=3, **args) == '在途'
    # 已标注：只在档位 3 的默写授予
    assert next_phase('在途', True, annotated=True, review_type=1, level=3, **args) == '牢记'
    assert next_phase('在途', True, annotated=True, review_type=1, level=1, **args) == '在途'
    assert next_phase('在途', True, annotated=True, review_type=2, level=3, **args) == '在途'
    assert next_phase('在途', True, annotated=True, review_type=3, level=3, **args) == '在途'
    assert next_phase('在途', True, consecutive=3, interval=8, was_due=True, annotated=True, review_type=1, level=1) == '遗忘点'
    # 已标注且已是牢记：答对即保持
    assert next_phase('牢记', True, consecutive=1, interval=2, was_due=True, annotated=True, review_type=2, level=1) == '牢记'
    assert next_phase('牢记', False, annotated=True, review_type=1, level=3, **args) == '在途'
```

样例标注：`SPEC_PROUD_OF` = be/plain, proud/content(lemma proud), of/collocation；`SPEC_LOOK_FORWARD` = look/plain, forward/collocation, to/collocation, doing/placeholder, sth./placeholder；`SPEC_TAKE_PART_IN` = take/plain, part/plain, in/collocation；`SPEC_HELP_WITH` = help/plain, sb./placeholder, with/collocation, sth./placeholder；`SPEC_A_LOT_OF` = a/plain, lot/plain, of/collocation；`SPEC_ALL_CONTENT`（英文 `make friends`）= make/content(lemma make), friends/content(lemma friend)。

- [ ] **Step 2: 运行确认失败**

Run: `python cloudflare/scripts/phrase_focus_test.py`
Expected: 新增测试因函数未定义而失败。

- [ ] **Step 3: 实现四个函数**

规则（设计文档第 3、4 节）：

- `focus_indices`：并集 =（所有 `collocation`）∪（`lemma` 不在 `mastered_lemmas` 的 `content`）∪（在 `recent_token_results` 中 `ok` 为假的次数 ≥ `ERROR_THRESHOLD` 的下标，排除 `placeholder`）。下标越界的记录忽略。
- `build_cells`：`level = requested_level or stored_level`。档位 1 且 `focus` 为空时 `level = 3`。档位 1 空出 `focus`；档位 2、3 空出所有非 `placeholder`。不含任何字母的 token 永不空出。档位 2 的空出词 `hint` 为首字符，且只有一个字母的 token 不空出；其他情况 `hint` 为 `None`。
- `next_level`：仅当 `annotated and review_type == 1` 时变化，答对 `min(stored+1, 3)`，答错 `max(stored-1, 1)`。
- `next_phase`：

```python
grant = ok and consecutive >= 3 and interval >= 7 and (not annotated or (review_type == 1 and level == 3))
keep = annotated and ok and old_phase == '牢记'
return '牢记' if grant or keep else '遗忘点' if ok and was_due else '在途'
```

- [ ] **Step 4: 运行确认通过**

Run: `python cloudflare/scripts/phrase_focus_test.py`
Expected: 全部通过。

- [ ] **Step 5: Commit**

```bash
git add cloudflare/src/phrase_focus.py cloudflare/scripts/phrase_focus_test.py
git commit -m "feat: add focus selection, dictation levels and phase rules"
```

---

### Task 3: 迁移 0010

**Files:**
- Create: `cloudflare/migrations/0010_phrase_focus.sql`
- Modify: `cloudflare/scripts/phrase_focus_test.py`

**Interfaces:**
- Produces（后续任务依赖的列）：
  - `word.entry_type TEXT NOT NULL DEFAULT 'word'`
  - `word.focus_spec TEXT`
  - `word.focus_status TEXT NOT NULL DEFAULT 'none'`
  - `word.focus_updated_at TEXT`（标注写入时间，用于限定错误驱动只看当前标注之后的记录）
  - `word.dictation_level INTEGER NOT NULL DEFAULT 3`
  - `word_review_log.token_results TEXT`
  - `word_review_log.dictation_level INTEGER`
  - 测试脚本助手 `build_database()`：建旧表结构后执行本迁移，返回连接。

- [ ] **Step 1: 写失败的测试**

```python
def test_migration_backfill():
    connection = build_legacy_database()          # 仅旧表结构
    connection.executescript("""
      INSERT INTO word(id,english,chinese,learning_phase,review_count,correct_count,interval,deleted) VALUES
        (1,'apple','苹果','在途',4,3,4,0),
        (2,'be good at','擅长','在途',2,1,2,0),
        (3,'look forward to','期待','牢记',6,6,16,0),
        (4,' ice-cream ','冰淇淋',NULL,0,0,1,0),
        (5,'take part in','参加','新学',0,0,1,1);
    """)
    before = connection.execute('SELECT id,english,chinese,learning_phase,review_count,correct_count,interval,deleted FROM word ORDER BY id').fetchall()
    apply_migration(connection)
    rows = {r['id']: r for r in connection.execute('SELECT * FROM word')}
    assert [rows[i]['entry_type'] for i in (1, 2, 3, 4, 5)] == ['word', 'phrase', 'phrase', 'word', 'phrase']
    assert [rows[i]['dictation_level'] for i in (1, 2, 3, 4, 5)] == [3, 1, 3, 3, 1]
    assert all(rows[i]['focus_status'] == 'none' and rows[i]['focus_spec'] is None for i in rows)
    after = connection.execute('SELECT id,english,chinese,learning_phase,review_count,correct_count,interval,deleted FROM word ORDER BY id').fetchall()
    assert [tuple(r) for r in before] == [tuple(r) for r in after]     # 原有字段不变
    log_columns = {r['name'] for r in connection.execute('PRAGMA table_info(word_review_log)')}
    assert {'token_results', 'dictation_level'} <= log_columns
```

- [ ] **Step 2: 运行确认失败**

Run: `python cloudflare/scripts/phrase_focus_test.py`
Expected: 迁移文件不存在而失败。

- [ ] **Step 3: 编写迁移**

`ALTER TABLE ... ADD COLUMN` 七次，然后回填：

```sql
UPDATE word SET entry_type='phrase' WHERE instr(trim(english),' ')>0 OR instr(english,char(9))>0;
UPDATE word SET dictation_level=1 WHERE entry_type='phrase' AND COALESCE(learning_phase,'')<>'牢记';
CREATE INDEX IF NOT EXISTS cf_word_entry_focus ON word(entry_type,focus_status) WHERE deleted=0;
```

回填包含已软删除的行。不写其他 `UPDATE`。

- [ ] **Step 4: 运行确认通过**

Run: `python cloudflare/scripts/phrase_focus_test.py`
Expected: 全部通过。

- [ ] **Step 5: Commit**

```bash
git add cloudflare/migrations/0010_phrase_focus.sql cloudflare/scripts/phrase_focus_test.py
git commit -m "feat: add migration for phrase focus columns"
```

---

### Task 4: 单词保存、导入、列表与统计

**Files:**
- Modify: `cloudflare/src/words.py`（`save`、`batch`、`listing`、`stats`）
- Modify: `cloudflare/scripts/phrase_focus_test.py`

**Interfaces:**
- Consumes: `entry_type_of`、`normalize_english`、`validate_focus_spec`（Task 1）；Task 3 的列。
- Produces:
  - `save(db, payload, word_id=None)` 额外接受 `entry_type`、`focus_spec`。
  - `GET /api/words` 接受查询参数 `entry_type`、`focus_status`；每条返回 `entry_type`、`focus_status`、`focus_spec`（解析后的对象或 `null`）、`dictation_level`。
  - `GET /api/words/stats/summary` 增加 `by_type: {'word': {'total': int, 'accuracy': float}, 'phrase': {...}}`，`accuracy = round(sum(correct_count)/sum(review_count)*100, 1)`，无复习时为 0。
  - `POST /api/words/batch` 每条可带 `entry_type`、`focus_spec`；结果项可带 `focus_error`。

- [ ] **Step 1: 写失败的测试**

```python
def test_save_entry_type_and_focus():
    db = adapter(build_database())
    created = run(save(db, {'english': 'be  proud of', 'chinese': '为…自豪', 'grade': 6}))
    assert (created['entry_type'], created['focus_status'], created['dictation_level']) == ('phrase', 'none', 1)
    single = run(save(db, {'english': 'proud', 'chinese': '自豪的'}))
    assert (single['entry_type'], single['dictation_level']) == ('word', 3)
    # 带标注保存 → confirmed，并写 focus_updated_at
    saved = run(save(db, {'focus_spec': {'tokens': PROUD_OF_TOKENS}}, created['id']))
    assert saved['focus_status'] == 'confirmed' and saved['focus_spec']['source_english'] == 'be proud of'
    assert saved['focus_updated_at']
    # 普通编辑不改变标注状态
    run(db.run("UPDATE word SET focus_status='draft' WHERE id=?", (created['id'],)))
    assert run(save(db, {'chinese': '以…为荣'}, created['id']))['focus_status'] == 'draft'
    # 英文改动 → 标注失效但保留
    changed = run(save(db, {'english': 'be proud in'}, created['id']))
    assert changed['focus_status'] == 'none' and changed['focus_spec'] is not None
    # 只是空白不同不算改动
    run(save(db, {'focus_spec': {'tokens': [{'text': 'be', 'role': 'plain'}, {'text': 'proud', 'role': 'plain'}, {'text': 'in', 'role': 'collocation'}]}}, created['id']))
    assert run(save(db, {'english': ' be  proud in '}, created['id']))['focus_status'] == 'confirmed'
    # 非法标注 → 422，原记录不变
    expect_http(422, lambda: run(save(db, {'focus_spec': {'tokens': PROUD_OF_TOKENS}}, created['id'])))
    # 手动指定类型
    assert run(save(db, {'entry_type': 'word'}, created['id']))['entry_type'] == 'word'
    expect_http(422, lambda: run(save(db, {'entry_type': 'sentence'}, created['id'])))

def test_batch_import_with_focus():
    # 调用 batch 的数据库实现函数 import_words(db, payload)
    result = run(import_words(db, {'words': [
        {'english': 'be good at', 'chinese': '擅长', 'focus_spec': {'tokens': GOOD_AT_TOKENS}},
        {'english': 'take part in', 'chinese': '参加', 'focus_spec': {'tokens': GOOD_AT_TOKENS}},   # 与英文不符
        {'english': 'apple', 'chinese': '苹果'},
    ]}))
    assert result['success_count'] == 3
    assert 'focus_error' in result['results'][1] and 'focus_error' not in result['results'][0]
    rows = {r['english']: r for r in run(db.all('SELECT * FROM word WHERE deleted=0'))}
    assert (rows['be good at']['focus_status'], rows['take part in']['focus_status'], rows['apple']['entry_type']) == ('confirmed', 'none', 'word')

def test_listing_filters_and_stats():
    # 列表与统计的数据库实现函数 list_words(db, params, skip, limit)、word_stats(db)
    assert {r['english'] for r in run(list_words(db, {'entry_type': 'phrase'}, 0, 50))['items']} == PHRASES
    assert {r['english'] for r in run(list_words(db, {'focus_status': 'confirmed'}, 0, 50))['items']} == CONFIRMED
    stats = run(word_stats(db))
    assert stats['by_type']['word']['total'] == WORD_TOTAL and stats['by_type']['phrase']['total'] == PHRASE_TOTAL
    assert stats['by_type']['phrase']['accuracy'] == 50.0      # 夹具：词组合计 correct 3 / review 6
```

- [ ] **Step 2: 运行确认失败**

Run: `python cloudflare/scripts/phrase_focus_test.py`
Expected: 新增测试失败。

- [ ] **Step 3: 实现**

- 把 `batch`、`listing`、`stats` 三个端点的主体分别抽成 `import_words(db, payload)`、`list_words(db, params, skip, limit)`、`word_stats(db)`，端点只负责取 `db` 和参数后转调。现有返回字段和行为不变。
- `save`：新建时 `entry_type` 默认 `entry_type_of(english)`，`dictation_level` 词组为 1、单词为 3。更新时若 `normalize_english(新 english) != normalize_english(旧 english)` 且请求未带 `focus_spec`，置 `focus_status='none'`（`focus_spec` 保留）。请求带 `focus_spec` 时用（更新后的）`english` 校验，`ValueError` 转 `HTTPException(422, 原因)`；通过后存 JSON 文本、`focus_status='confirmed'`、`focus_updated_at=当前时间`。`entry_type` 只接受 `word`、`phrase`。
- `decorate`、`decorate_many`：把 `focus_spec` 解析成对象。
- `import_words`：`focus_spec` 校验失败时该条照常导入、不带标注，并在结果项写 `focus_error`。
- `word_stats` 的 `by_type` 用已加载的 `rows` 计算，不新增查询。

- [ ] **Step 4: 运行确认通过**

Run: `python cloudflare/scripts/phrase_focus_test.py`
Expected: 全部通过。

- [ ] **Step 5: Commit**

```bash
git add cloudflare/src/words.py cloudflare/scripts/phrase_focus_test.py
git commit -m "feat: store entry type and focus spec on words"
```

---

### Task 5: 复习抽题与提交

**Files:**
- Create: `cloudflare/src/word_focus.py`（本任务只放 `load_focus_context`）
- Modify: `cloudflare/src/review.py`
- Modify: `cloudflare/scripts/phrase_focus_test.py`

**Interfaces:**
- Consumes: `spec_active`、`focus_indices`、`build_cells`、`next_level`、`next_phase`、`ERROR_WINDOW`（Task 1、2）。
- Produces:
  - `async load_focus_context(db, rows: list[dict]) -> dict[int, dict]`：对 `rows` 中 `spec_active` 的词组返回 `{word_id: {'spec': dict, 'focus': list[int]}}`。内部恰好两次查询：一次查已"牢记"的 `lemma`（`entry_type='word' AND deleted=0 AND learning_phase='牢记' AND lower(english) IN (...)`），一次查每个词组最近 `ERROR_WINDOW` 条 `review_type=1 AND token_results IS NOT NULL AND reviewed_at >= word.focus_updated_at` 的日志。没有已标注词组时不查询。
  - `async start_session(db, count: int, grade: int | None, word_ids: str | None, entry_type: str | None, dictation_level: int | None) -> dict`
  - `async submit_session(db, payload: dict) -> tuple[dict, bool]`：返回 `(output, first_time)`，`first_time` 为假表示幂等命中。
  - 端点 `POST /api/words/review/start` 新增查询参数 `entry_type`（`word`/`phrase`）、`dictation_level`（1 到 3）。
  - 每道题新增 `entry_type`、`dictation_level`；已标注词组另有 `tokens`（`build_cells` 的输出）。未标注词组和单词不返回 `tokens`，`dictation_level` 为 3。
  - 提交的每条结果可带 `token_results: [{'i': int, 'ok': bool}]`、`dictation_level: 1..3`、`dictation_auto: bool`（缺省为真；为假表示本次档位是手动选的）；`review_type` 接受 1、2、3。
  - 测试助手 `counted_queries(db, coroutine_factory) -> int`：统计适配器上 `first`/`all`/`run`/`batch` 的调用次数。`BASELINE_START_QUERIES` 是同一份数据在没有任何已标注词组时 `start_session` 的调用次数，在测试里现算，不写死。

- [ ] **Step 1: 写失败的测试**

```python
def test_start_returns_tokens():
    db = seeded()        # apple(word), be good at(confirmed), be proud of(draft), take part in(none), proud(word 在途)
    data = run(start_session(db, 10, None, None, None, None))
    by = {q['english']: q for q in data['questions']}
    assert 'tokens' not in by['apple'] and by['apple']['dictation_level'] == 3
    assert 'tokens' not in by['take part in'] and by['take part in']['dictation_level'] == 3
    assert [t['blank'] for t in by['be good at']['tokens']] == [False, False, True]
    assert [t['blank'] for t in by['be proud of']['tokens']] == [False, True, True]     # proud 未牢记
    run(db.run("UPDATE word SET learning_phase='牢记' WHERE english='proud'"))
    data = run(start_session(db, 10, None, None, 'phrase', None))
    by = {q['english']: q for q in data['questions']}
    assert set(by) == {'be good at', 'be proud of', 'take part in'}
    assert [t['blank'] for t in by['be proud of']['tokens']] == [False, False, True]
    data = run(start_session(db, 10, None, None, 'phrase', 3))
    assert all(t['blank'] for t in {q['english']: q for q in data['questions']}['be good at']['tokens'])
    assert counted_queries(db, lambda: start_session(db, 10, None, None, None, None)) <= BASELINE_START_QUERIES + 2

def test_submit_levels_and_logs():
    db = seeded(); session, ids = begin(db)
    out, first = run(submit_session(db, {'session_id': session, 'duration': 30, 'results': [
        {'word_id': ids['be good at'], 'is_correct': True, 'user_answer': 'be good at', 'review_type': 1,
         'dictation_level': 1, 'token_results': [{'i': 2, 'ok': True}]},
        {'word_id': ids['be proud of'], 'is_correct': False, 'user_answer': 'be pruod of', 'review_type': 1,
         'dictation_level': 1, 'token_results': [{'i': 1, 'ok': False}, {'i': 2, 'ok': True}]},
        {'word_id': ids['apple'], 'is_correct': True, 'user_answer': 'apple', 'review_type': 1},
        {'word_id': ids['take part in'], 'is_correct': True, 'user_answer': 'take part in', 'review_type': 1},
        {'word_id': ids['proud'], 'is_correct': True, 'user_answer': 'proud', 'review_type': 1}]}))
    assert first and out == {'total': 5, 'correct': 4, 'error': 1, 'accuracy': 80.0}
    words = by_english(db)
    assert words['be good at']['dictation_level'] == 2
    assert words['be proud of']['dictation_level'] == 1
    assert words['apple']['dictation_level'] == 3 and words['take part in']['dictation_level'] == 1   # 未标注：列值不动
    log = latest_log(db, ids['be proud of'])
    assert json.loads(log['token_results']) == [{'i': 1, 'ok': False}, {'i': 2, 'ok': True}] and log['dictation_level'] == 1
    assert latest_log(db, ids['apple'])['token_results'] is None

def test_submit_idempotent_keeps_level():            # Review Focus 4
    db = seeded(); session, ids = begin(db); payload = one_correct_payload(session, ids, level=1)
    run(submit_session(db, payload))
    out, first = run(submit_session(db, payload))
    assert not first and by_english(db)['be good at']['dictation_level'] == 2

def test_submit_from_old_frontend():                 # Review Focus 5
    db = seeded(); session, ids = begin(db, only='be good at')
    out, _ = run(submit_session(db, {'session_id': session, 'duration': 5, 'results': [
        {'word_id': ids['be good at'], 'is_correct': True, 'user_answer': 'be good at', 'review_type': 1}]}))
    assert out['correct'] == 1
    log = latest_log(db, ids['be good at'])
    assert log['dictation_level'] == 3 and log['token_results'] is None
    assert by_english(db)['be good at']['dictation_level'] == 2

def test_manual_level_not_written_back():
    db = seeded(); session, ids = begin(db, only='be good at')
    run(submit_session(db, {'session_id': session, 'duration': 5, 'results': [
        {'word_id': ids['be good at'], 'is_correct': True, 'user_answer': 'be good at', 'review_type': 1,
         'dictation_level': 3, 'dictation_auto': False, 'token_results': [{'i': 0, 'ok': True}, {'i': 1, 'ok': True}, {'i': 2, 'ok': True}]}]}))
    assert by_english(db)['be good at']['dictation_level'] == 1          # 手动选档不写回
    assert latest_log(db, ids['be good at'])['dictation_level'] == 3     # 但日志记实际档位

def test_listening_accepted_and_grant_rules():
    # review_type=3 不再返回 422
    # 已标注词组：连续 3 次答对且间隔≥7，但档位 1 → 阶段不为 牢记；同样条件档位 3 → 牢记
    # 已是 牢记 的已标注词组用选择题答对 → 仍为 牢记
    # 单词：同样条件用选择题 → 牢记（与旧行为一致）

def test_submit_validation():
    # token_results 不是列表、i 不是整数、ok 不是布尔、dictation_level=4、review_type=4 → HTTPException 422

def test_error_driven_uses_only_current_annotation():
    # 标注前的日志（reviewed_at < focus_updated_at）和不带 token_results 的日志不计入错误驱动
```

后四个测试按注释写出完整断言，夹具用 `seeded()`、直接 `UPDATE word` 设置 `interval`、`next_review_at`、`focus_updated_at`，并插入 `word_review_log` 历史行来构造"连续答对"。

- [ ] **Step 2: 运行确认失败**

Run: `python cloudflare/scripts/phrase_focus_test.py`
Expected: 新增测试失败。

- [ ] **Step 3: 实现**

- 把 `start`、`submit` 的主体抽成 `start_session`、`submit_session`。端点保留参数校验的 `Query` 声明，并在 `submit` 端点里保留现有的激励触发（仅 `first_time` 且 `len(results)>=10` 时调用）。
- `start_session`：`entry_type` 过滤加在现有 `filters` 上；`SELECT` 增加 `entry_type,focus_spec,focus_status,focus_updated_at,dictation_level,learning_phase,grade`。抽完词后调用一次 `load_focus_context`，对其中的词调用 `build_cells(spec, stored_level, dictation_level 参数, focus)`。抽词优先级、选项生成、`request_record` 写入不变。
- `submit_session`：校验放宽为 `review_type in (1,2,3)`，并校验新字段形状。对每条结果：`annotated = spec_active(word)`；`level = 提交的 dictation_level or 3`；`phase = next_phase(word['learning_phase'], ok, consecutive, interval, was_due, annotated, review_type, level)`；`new_level = next_level(word['dictation_level'], ok, review_type, annotated)`，但 `dictation_auto` 为假时 `new_level` 保持原值（手动选档只影响本次，不写回；"牢记"仍按实际档位判定）。`interval`、`consecutive`、`was_due`、`next` 的计算保持现有代码。
- 日志插入语句增加 `token_results`（未提交时为 `NULL`）和 `dictation_level`（仅已标注词组写入，其余 `NULL`）；`UPDATE word` 语句增加 `dictation_level`。两者仍通过现有的 `json_each(packed)` 方式一次完成，不增加语句数。

- [ ] **Step 4: 运行确认通过**

Run: `python cloudflare/scripts/phrase_focus_test.py`
Expected: 全部通过。

- [ ] **Step 5: Commit**

```bash
git add cloudflare/src/review.py cloudflare/src/word_focus.py cloudflare/scripts/phrase_focus_test.py
git commit -m "feat: serve focus cells in review and record per-token results"
```

---

### Task 6: LLM 标注

**Files:**
- Modify: `cloudflare/src/phrase_focus.py`（`apply_annotation`）
- Modify: `cloudflare/src/prompts.py`（`_build_phrase_focus_prompt`）
- Modify: `cloudflare/src/word_focus.py`（路由）
- Modify: `cloudflare/src/main.py`（在 `words_router` 之前注册 `word_focus.router`）
- Modify: `cloudflare/scripts/phrase_focus_test.py`

**Interfaces:**
- Consumes: `validate_focus_spec`；`settings.generate_json(request, prompt)`；`settings.load(request, 'app')` 的 `default_grade`。
- Produces:
  - `apply_annotation(rows: list[dict], llm_output, known_words: set[str]) -> dict`，返回 `{'updates': [{'id': int, 'focus_spec': dict}], 'failures': [{'id': int, 'english': str, 'reason': str}], 'missing_lemmas': [{'lemma': str, 'gloss': str, 'grade': int | None, 'semester': int | None, 'source_word_id': int}]}`。`known_words` 是单词本中已有单词条目的小写英文集合。
  - `PromptLibrary._build_phrase_focus_prompt(items: list[dict], default_grade: int | None) -> str`，`items` 每项含 `id`、`english`、`chinese`、`grade`。
  - `async annotate_words(db, word_ids: list[int], generate, default_grade) -> dict`：`generate` 是 `async (prompt) -> 解析后的 JSON`，便于测试注入。
  - `POST /api/words/focus/annotate`，请求体 `{'word_ids': [int, ...]}`（1 到 20 个），响应 `{'annotated': int, 'skipped': [{'id': int, 'reason': str}], 'failures': [...], 'missing_lemmas': [...]}`。
  - 要求模型返回的格式：`{"items": [{"id": 1, "tokens": [{"text": "be", "role": "plain"}, {"text": "proud", "role": "content", "lemma": "proud", "gloss": "自豪的"}]}]}`

- [ ] **Step 1: 写失败的测试**

```python
def test_apply_annotation_mixed_batch():          # Review Focus 3
    rows = [{'id': 1, 'english': 'be good at', 'grade': 6, 'semester': 1},
            {'id': 2, 'english': 'be proud of', 'grade': 6, 'semester': 1},
            {'id': 3, 'english': 'take part in', 'grade': 6, 'semester': 1},
            {'id': 4, 'english': 'look after', 'grade': 6, 'semester': 1}]
    output = {'items': [
        {'id': 1, 'tokens': GOOD_AT_TOKENS},
        {'id': 2, 'tokens': PROUD_OF_TOKENS},
        {'id': 3, 'tokens': GOOD_AT_TOKENS},                     # 改写了词
        {'id': 99, 'tokens': GOOD_AT_TOKENS},                    # 不认识的 id
        # id 4 被漏掉
    ]}
    result = apply_annotation(rows, output, known_words={'good'})
    assert [u['id'] for u in result['updates']] == [1, 2]
    assert {f['id'] for f in result['failures']} == {3, 4}
    assert result['missing_lemmas'] == [{'lemma': 'proud', 'gloss': '自豪的', 'grade': 6, 'semester': 1, 'source_word_id': 2}]
    for broken in (None, [], {'items': 'x'}, {'items': [None, 5]}):
        assert len(apply_annotation(rows, broken, set())['failures']) == 4

def test_annotate_words_respects_confirmed():
    db = seeded()        # be good at 为 confirmed，be proud of 为 draft，take part in 为 none，apple 为单词
    calls = []
    async def fake(prompt):
        calls.append(prompt)
        return {'items': [{'id': ids['be proud of'], 'tokens': PROUD_OF_TOKENS}, {'id': ids['take part in'], 'tokens': TAKE_PART_IN_TOKENS}]}
    before = by_english(db)['be good at']
    result = run(annotate_words(db, [ids['be good at'], ids['be proud of'], ids['take part in'], ids['apple']], fake, 6))
    assert len(calls) == 1 and 'be good at' not in calls[0] and 'apple' not in calls[0]
    assert result['annotated'] == 2 and {s['id'] for s in result['skipped']} == {ids['be good at'], ids['apple']}
    after = by_english(db)
    assert after['be good at']['focus_spec'] == before['focus_spec'] and after['be good at']['focus_status'] == 'confirmed'
    assert after['take part in']['focus_status'] == 'draft' and after['take part in']['focus_updated_at']
    assert after['take part in']['review_count'] == before_counts['take part in']        # 复习数据不动

def test_annotate_all_skipped_makes_no_llm_call():
    # 全部是 confirmed 或单词 → 不调用 generate，annotated == 0

def test_prompt_contents():
    prompt = PromptLibrary()._build_phrase_focus_prompt([{'id': 7, 'english': 'be good at', 'chinese': '擅长', 'grade': None}], 6)
    for needle in ('be good at', '"id": 7', 'collocation', 'content', 'plain', 'placeholder', 'lemma', 'gloss', 'sb.', 'sth.', '六年级'):
        assert needle in prompt
```

- [ ] **Step 2: 运行确认失败**

Run: `python cloudflare/scripts/phrase_focus_test.py`
Expected: 新增测试失败。

- [ ] **Step 3: 实现**

- `apply_annotation`：按 `id` 匹配；每条用 `validate_focus_spec` 校验，`ValueError` 的消息作为 `reason`；模型漏掉的条目 `reason` 为"模型未返回该词组"；不在 `rows` 里的 `id` 忽略。`missing_lemmas` 收集通过校验的 `content` 中 `lemma` 不在 `known_words` 的项，同一 `lemma` 只出现一次。
- `annotate_words`：一次查询取出这些词；`entry_type!='phrase'` 的跳过（原因"不是词组"），`focus_status='confirmed'` 的跳过（原因"已确认，不覆盖"）。剩余为空则直接返回。否则调用一次 `generate`，一次查询取 `known_words`，再用一次 `db.batch` 把所有 `updates` 写入（`focus_spec`、`focus_status='draft'`、`focus_updated_at`）。更新语句带 `AND focus_status<>'confirmed'`，防止并发下覆盖刚确认的条目。
- prompt 必须包含设计文档第 7 节列出的全部要求：不得增删、改写或重新切分 token；搭配词范围；基础词按年级判断、拿不准标 `content`；占位符清单（sb.、sth.、sp.、doing、do、one's、oneself 及其变体）；`content` 必须给原形和中文释义；只返回 JSON。条目没有年级时用 `default_grade`，年级名称用现有的 `_get_grade_name`。措辞由实现者编写。
- 路由：校验 `word_ids` 为 1 到 20 个互不相同的整数，否则 422；`generate` 传 `lambda prompt: generate_json(request, prompt)`。

- [ ] **Step 4: 运行确认通过**

Run: `python cloudflare/scripts/phrase_focus_test.py`
Expected: 全部通过。

- [ ] **Step 5: Commit**

```bash
git add cloudflare/src/phrase_focus.py cloudflare/src/prompts.py cloudflare/src/word_focus.py cloudflare/src/main.py cloudflare/scripts/phrase_focus_test.py
git commit -m "feat: annotate phrase focus with the configured LLM"
```

---

### Task 7: 打印默写

**Files:**
- Modify: `cloudflare/src/phrase_focus.py`（`print_text`）
- Modify: `cloudflare/src/media.py:108-120`（`print_words`）
- Modify: `cloudflare/scripts/phrase_focus_test.py`

**Interfaces:**
- Consumes: `build_cells`、`spec_active`、`load_focus_context`。
- Produces:
  - `print_text(row: dict, tokens: list[dict] | None) -> str`
  - `POST /api/words/print-pdf` 新增查询参数 `dictation_level: int = Query(1, ge=1, le=3)`。

- [ ] **Step 1: 写失败的测试**

```python
def test_print_text():
    tokens, _ = build_cells(SPEC_GOOD_AT, 1, 1, [2])
    assert print_text({'english': 'be good at', 'chinese': '擅长'}, tokens) == '擅长　be good ____'
    tokens, _ = build_cells(SPEC_HELP_WITH, 1, 2, [2])
    assert print_text({'english': 'help sb. with sth.', 'chinese': '帮助某人做某事'}, tokens) == '帮助某人做某事　h______ sb. w______ sth.'
    assert print_text({'english': 'apple', 'chinese': '苹果'}, None) == '苹果 （5个字母）'
    assert print_text({'english': 'take part in', 'chinese': '参加'}, None) == '参加 （12个字母）'    # 未标注：沿用 LENGTH(english)
```

- [ ] **Step 2: 运行确认失败**

Run: `python cloudflare/scripts/phrase_focus_test.py`
Expected: `print_text` 未定义而失败。

- [ ] **Step 3: 实现**

- `print_text`：`tokens` 为 `None` 时返回现有格式 `中文 + ' （' + len(english) + '个字母）'`。否则为 `中文 + 全角空格 + 各 token 用空格连接`，空出的词写成 `hint（如有）+ 下划线`，下划线数量为 `max(4, 2 × 需填字母数)`，保证纸上有足够书写空间。
- `print_words`：`SELECT` 改为取 `id,english,chinese,entry_type,focus_spec,focus_status,focus_updated_at,dictation_level,grade`；调用一次 `load_focus_context`；对已标注词组用 `build_cells(spec, stored_level, dictation_level 参数, focus)` 后交给 `print_text`。其余（随机抽取、PDF 调用、R2 写入）不变。

- [ ] **Step 4: 运行确认通过**

Run: `python cloudflare/scripts/phrase_focus_test.py`
Expected: 全部通过。

- [ ] **Step 5: Commit**

```bash
git add cloudflare/src/phrase_focus.py cloudflare/src/media.py cloudflare/scripts/phrase_focus_test.py
git commit -m "feat: print phrase dictation sheets by level"
```

---

### Task 8: 前端纯逻辑——格子布局与判对

**Files:**
- Create: `frontend/src/composables/dictation.js`
- Create: `frontend/src/composables/dictation.test.mjs`

**Interfaces:**
- Consumes: Task 5 的题目字段 `english`、`tokens`。
- Produces:
  - `buildCells(question) -> Array<{char: string, fixed: boolean, token: number, gapBefore: boolean}>`：`token` 是 token 下标（无 `tokens` 时恒为 0），`gapBefore` 表示该格之前是词间空格。
  - `blankTokenCount(question) -> number`
  - `judge(question, answers: string[]) -> {correct: boolean, userAnswer: string, tokenResults: Array<{i: number, ok: boolean}> | null}`：`answers` 与 `buildCells` 的结果等长。
  - `shouldPlayBeforeAnswer(question, reviewType) -> boolean`

- [ ] **Step 1: 写失败的测试**

```js
import test from 'node:test'
import assert from 'node:assert/strict'
import { buildCells, blankTokenCount, judge, shouldPlayBeforeAnswer } from './dictation.js'

const cloze = q => buildCells(q).map(c => (c.gapBefore ? ' ' : '') + (c.fixed ? c.char : '_')).join('')
const fill = (q, text) => buildCells(q).map((c, i) => (c.fixed ? c.char : text[i]))
const goodAt = { english: 'be good at', tokens: [
  { text: 'be', blank: false, hint: null }, { text: 'good', blank: false, hint: null }, { text: 'at', blank: true, hint: null }] }

test('无 tokens 时与旧字母格一致', () => {
  assert.equal(cloze({ english: "what's up?" }), "____'_ __?")
  assert.equal(blankTokenCount({ english: 'apple' }), 1)
})
test('只空出标记为 blank 的词', () => {
  assert.equal(cloze(goodAt), 'be good __')
  assert.equal(blankTokenCount(goodAt), 1)
})
test('空出的词里非字母字符预填', () => {          // Review Focus 2
  const q = { english: "do one's best", tokens: [
    { text: 'do', blank: false, hint: null }, { text: "one's", blank: true, hint: null }, { text: 'best', blank: true, hint: null }] }
  assert.equal(cloze(q), "do ___'_ ____")
})
test('提示默写首字母固定', () => {
  const q = { english: 'take part', tokens: [{ text: 'take', blank: true, hint: 't' }, { text: 'part', blank: true, hint: 'p' }] }
  assert.equal(cloze(q), 't___ p___')
})
test('按词判对，不区分大小写', () => {
  const q = { english: 'be Proud of', tokens: [
    { text: 'be', blank: false, hint: null }, { text: 'Proud', blank: true, hint: null }, { text: 'of', blank: true, hint: null }] }
  assert.deepEqual(judge(q, fill(q, 'be proud of')), { correct: true, userAnswer: 'be proud of', tokenResults: [{ i: 1, ok: true }, { i: 2, ok: true }] })
  const wrong = judge(q, fill(q, 'be pruod of'))
  assert.equal(wrong.correct, false)
  assert.deepEqual(wrong.tokenResults, [{ i: 1, ok: false }, { i: 2, ok: true }])
  assert.equal(judge(q, buildCells(q).map(c => (c.fixed ? c.char : ''))).correct, false)   // 留空算错
})
test('无 tokens 时 tokenResults 为 null', () => {
  assert.deepEqual(judge({ english: 'Apple' }, 'apple'.split('')), { correct: true, userAnswer: 'apple', tokenResults: null })
})
test('发音规则', () => {
  assert.equal(shouldPlayBeforeAnswer({ english: 'apple' }, 1), true)
  assert.equal(shouldPlayBeforeAnswer({ ...goodAt, dictation_level: 1 }, 1), false)
  assert.equal(shouldPlayBeforeAnswer({ ...goodAt, dictation_level: 2 }, 1), false)
  assert.equal(shouldPlayBeforeAnswer({ ...goodAt, dictation_level: 3 }, 1), true)
  assert.equal(shouldPlayBeforeAnswer({ ...goodAt, dictation_level: 1 }, 3), true)    // 听力题型照旧
})
```

- [ ] **Step 2: 运行确认失败**

Run: `node --test frontend/src/composables/dictation.test.mjs`
Expected: 模块不存在而失败。

- [ ] **Step 3: 实现 `dictation.js`**

无 `tokens` 时沿用现有规则：`/[a-zA-Z]/` 的字符为可填格，其余预填（含空格，此时空格是一个 `fixed` 格、`gapBefore` 恒为假，以保持旧版外观）。有 `tokens` 时不为词间空格生成格子，改用下一格的 `gapBefore=true`；显示的词所有字符 `fixed`；空出的词中字母可填、非字母预填；有 `hint` 时首字符 `fixed`。`userAnswer` 是把各格内容拼回整条英文（词间补空格）。

- [ ] **Step 4: 运行确认通过**

Run: `node --test frontend/src/composables/dictation.test.mjs`
Expected: 全部通过。

- [ ] **Step 5: Commit**

```bash
git add frontend/src/composables/dictation.js frontend/src/composables/dictation.test.mjs
git commit -m "feat: add dictation cell layout and per-token judging"
```

---

### Task 9: 默写组件与复习流程

**Files:**
- Create: `frontend/src/components/DictationInput.vue`
- Modify: `frontend/src/views/Words.vue`（复习设置约 230-250 行；默写区约 258-300 行；`dictationCells` 到 `handleLetterKeydown` 约 634-700 行；`startReviewGame`、`submitAnswer`、`nextQuestion`、`finishReview` 约 974-1180 行；相关 scoped 样式）

**Interfaces:**
- Consumes: `buildCells`、`blankTokenCount`、`judge`、`shouldPlayBeforeAnswer`（Task 8）；Task 5 的接口参数。
- Produces:
  - `<DictationInput :question="q" :disabled="bool" :result="{tokenResults, correct} | null" v-model="answers" @submit="...">`，并通过 `defineExpose({ focus, reset })` 暴露两个方法。
  - `reviewConfig` 新增 `entry_type`（`''`、`'word'`、`'phrase'`，默认 `''`）和 `dictation_level`（`0` 表示自动，1 到 3，默认 `0`）。

- [ ] **Step 1: 实现 `DictationInput.vue`**

把 `Words.vue` 中字母格的模板、`letterAnswers`、`activeLetterIdx`、键盘处理、隐藏输入框和 `.letter-*` 样式移入组件，格子来源改为 `buildCells(question)`。行为与现有一致：字母键填入并跳到下一个可填格，退格清空或回退，回车触发 `submit`，点击聚焦。`gapBefore` 的格子左侧留出词间距。提交后按 `result.tokenResults` 给每个空出的词加对或错的样式；无 `tokenResults` 时沿用整条对错样式。

- [ ] **Step 2: 接入 `Words.vue`**

- 删除已移走的状态和函数，默写区改用组件；提示文字：有 `tokens` 时为"提示：N 个词"（`blankTokenCount`），否则保持"提示：N 个字母"。
- 复习设置增加两项：范围（全部 / 只练单词 / 只练词组）；词组档位（自动 / 重点 / 提示 / 完整），仅题型为"默写英文"时显示。`startReviewGame` 把非默认值作为 `entry_type`、`dictation_level` 参数传给 `wordApi.startReview`。
- `submitAnswer` 的默写分支改用 `judge`，把 `tokenResults` 存到题目上；答错的提示保持显示完整正确答案。
- `finishReview` 的每条结果增加 `dictation_level: q.dictation_level`、`dictation_auto: reviewConfig.dictation_level === 0` 和 `token_results: q.tokenResults`（为 `null` 时不带该字段）。
- 发音：进入题目时仅当 `shouldPlayBeforeAnswer(q, reviewConfig.type)` 为真才调用 `autoPlayWithReplay`；为假时喇叭按钮在作答前禁用，提交后调用一次 `playWordAudio`。`startReviewGame` 和 `nextQuestion` 两处都要改。

- [ ] **Step 3: 构建**

Run: `npm --prefix frontend run build`
Expected: 构建成功，无新增错误。

- [ ] **Step 4: 在浏览器里验证**

本地默认会跳转云端并受切换保护（见 `AGENTS.md` "Cloudflare 正式环境"一节和 `backend/config/cloudflare-cutover.json`），不要为验证而解除生产保护。验证方式：`npm --prefix frontend run dev` 启动后，用开发者工具或 Vite 的 mock 让 `/api/words/review/start` 返回一份夹具（含一个单词、一个未标注词组、档位 1、2、3 各一个已标注词组），逐项确认：

- 单词和未标注词组的外观与输入行为与改动前相同。
- 档位 1 只有重点词是格子，其余为文字；档位 2 首字母已填且不可改；档位 3 占位符显示为文字。
- 档位 1、2 进入题目不出声、喇叭禁用，提交后播放一次；档位 3 和单词进入时自动播放。
- 答错时只有写错的词标红。
- 提交请求体里带 `token_results` 和 `dictation_level`。
- 手机宽度（375px）下长词组换行正常，点击能唤起键盘。

把无法验证的项如实记录在提交说明里。

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/DictationInput.vue frontend/src/views/Words.vue
git commit -m "feat: dictate phrase focus words in the review flow"
```

---

### Task 10: 单词本——类型、标注、重点编辑、打印与统计

**Files:**
- Create: `frontend/src/components/PhraseFocusEditor.vue`
- Modify: `frontend/src/api/word.js`
- Modify: `frontend/src/views/Words.vue`（工具栏约 15-25 行；列表列约 73-111 行；筛选状态约 520-530、870 行；详情弹窗；打印弹窗约 397-412、703-707、1209-1216 行；统计概览）

**Interfaces:**
- Consumes: Task 4 的列表字段与筛选、`by_type`；Task 6 的标注接口；Task 7 的打印参数；现有 `POST /api/words/batch`。
- Produces:
  - `wordApi.annotateFocus(wordIds: number[])` → `POST /words/focus/annotate`，超时 120000 毫秒。
  - `<PhraseFocusEditor :word="row" @saved="...">`

- [ ] **Step 1: 列表与筛选**

英文列在词组后显示"词组"标记，并显示标注状态（未标注 / 待确认 / 已确认）。筛选区增加类型（全部 / 单词 / 词组）和标注状态两个选择，值作为 `entry_type`、`focus_status` 传给列表接口。

- [ ] **Step 2: 标注按钮**

工具栏增加"标注词组重点"。点击后用列表接口取出 `entry_type=phrase` 且 `focus_status=none` 的全部 id（`limit=1000`），每 20 个调用一次 `annotateFocus`，顺序执行，显示进度"已处理 x / 共 y"。单批失败时记录并继续下一批。结束后弹出结果：成功数、失败条目及原因、`missing_lemmas` 列表。没有未标注词组时提示"没有需要标注的词组"。

- [ ] **Step 3: 生词加入单词本**

结果弹窗里 `missing_lemmas` 以可勾选的表格显示（原形、释义可编辑），"加入单词本"按钮把勾选项通过 `POST /api/words/batch` 写入，`grade`、`semester` 用各项自带的值。

- [ ] **Step 4: 重点编辑组件**

`PhraseFocusEditor`：把词组的每个 token 显示为可点击的标签，点击在四种角色间循环，不同角色用不同颜色并附图例（搭配词 / 生词 / 基础词 / 占位符）。角色为生词时显示原形和释义两个输入框，原形默认取该 token 去掉标点的小写形式。未标注时按全部"基础词"起步。保存调用 `wordApi.update(id, { focus_spec: { tokens } })`，成功后触发 `saved`；422 时显示服务端返回的原因。放在词组的详情弹窗中，单词条目不显示。

- [ ] **Step 5: 打印与统计**

打印弹窗增加"词组档位"（重点 / 提示 / 完整，默认重点），作为 `dictation_level` 传给 `wordApi.printPdf`。单词页概览用 `by_type` 把单词和词组的数量、正确率分开显示。

- [ ] **Step 6: 构建并验证**

Run: `npm --prefix frontend run build`
Expected: 构建成功。

按 Task 9 Step 4 的方式用夹具验证：筛选参数正确发出；标注按钮分批、进度、失败条目显示正确；重点编辑保存的请求体符合 `validate_focus_spec` 的格式；打印请求带 `dictation_level`。

- [ ] **Step 7: Commit**

```bash
git add frontend/src/components/PhraseFocusEditor.vue frontend/src/api/word.js frontend/src/views/Words.vue
git commit -m "feat: manage phrase focus in the word book"
```

---

### Task 11: 发布（需用户明确同意后才执行）

**Files:**
- Modify: `docs/cloudflare-migration-status.md`（追加本次发布记录）
- Modify: `AGENTS.md`（补一小节：词组重点的数据约定与 GPT 录入时附带 `focus_spec` 的格式）

本任务会写正式数据库并部署正式环境。**开始前必须向用户确认**，并说明将执行的三件事：远程执行迁移 0010、部署 Worker、部署 Pages。未得到同意则停在 Step 1。

- [ ] **Step 1: 全量自检**

Run: `python cloudflare/scripts/phrase_focus_test.py`
Run: `python cloudflare/scripts/knowledge_invariants_test.py`
Run: `node --test frontend/src/composables/dictation.test.mjs`
Run: `npm --prefix frontend run build`
Expected: 全部通过。

- [ ] **Step 2: 备份正式库**

按 `docs/cloudflare-migration-status.md` 记载的导出命令备份 D1 到 `backups/`，记录文件校验值。`backups/` 不提交。

- [ ] **Step 3: 远程执行迁移**

```bash
node cloudflare/tools/cli.cjs d1 execute easyfix --config cloudflare/wrangler.jsonc --remote --file cloudflare/migrations/0010_phrase_focus.sql --yes
```

执行后用只读查询核对：`word` 总行数与备份一致；`entry_type='phrase'` 的数量与"英文含空格"的数量一致；`focus_status` 全部为 `none`；抽查 5 条词条的 `review_count`、`correct_count`、`interval`、`learning_phase` 与备份相同。

- [ ] **Step 4: 部署 Worker 和 Pages**

Worker：`node cloudflare/tools/cli.cjs deploy --config cloudflare/wrangler.jsonc`
前端：`python backend/scripts/prepare_cloudflare_frontend.py`，再按 `docs/cloudflare-migration-status.md` 的日常部署命令发布 Pages。

- [ ] **Step 5: 正式环境核对**

登录正式入口，确认：单词默写与发布前一致；听力题型能正常提交；单词本出现类型标记和"标注词组重点"按钮。先只选 3 到 5 条词组试标注，核对结果合理后再由用户决定是否全量标注。

- [ ] **Step 6: 记录并提交**

在 `docs/cloudflare-migration-status.md` 追加迁移编号、备份位置与校验值、部署结果；在 `AGENTS.md` 补充约定。

```bash
git add docs/cloudflare-migration-status.md AGENTS.md
git commit -m "docs: record phrase dictation release"
```
