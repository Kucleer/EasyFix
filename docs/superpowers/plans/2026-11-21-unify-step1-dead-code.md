# 项目 5 第 1 步：清理没人用的代码 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 删掉现在就没有任何调用方的后端接口、走不到的后端代码和没人用的前端接口函数，不改变任何功能。

**Architecture:** 先写一个"接口清单测试"，把"哪些必须没有、哪些必须还在"钉住，再分四块删：独立的后端接口、目录类接口、上传的死代码、前端函数。每块删完跑全部测试。最后先发前端、再发后端。

**Tech Stack:** Python（FastAPI，Cloudflare Python Worker）、Vue 3 + Vite、Node 自带测试（`node --test`）。测试是直接运行的脚本，不用 pytest。

**Spec:** `docs/superpowers/specs/2026-11-21-workspace-and-unify-design.md`（第 10 节是这一步的清单，第 11 节是分步和上线顺序）。

这是项目 5 四步里的第 1 步。第 2–4 步各有单独的计划，等前一步做完再写。

## Global Constraints

- 只删代码，不删任何数据库表、列和数据；不新增迁移。
- **每一条在删除前都要重新搜索确认没有调用方**（设计第 10 节）。搜索范围：`frontend/src`、`cloudflare/pages/_worker.js`、`tools/easyfix-intake/`、`cloudflare/src`（内部调用）、`cloudflare/scripts`、`backend/scripts`。发现有调用方就停下来，不删，在最后的汇报里写明。
- 这四个录入技能在用的接口不能受影响：`GET /api/intake/guide`、`POST /api/intake/papers/check`、`POST /api/intake/papers`、`POST /api/upload/batch-simple`（最后一个由网关 `_worker.js` 处理）。
- 这两组明确保留：`POST /api/rewards/{reward_id}/redeem` 和前端的 `motivationApi.redeemReward`（留给成就项目）；`GET /api/words/{word_id}` 和前端的 `wordApi.get`（助手手工录单词时可能用）。
- 这一步不动的（等第 3 步）：`/api/stats/summary`、`/api/stats/overview`、`/api/stats/knowledge-points`、`/api/stats/analysis/full`、`/api/stats/analysis/llm`、`POST /api/questions/batch-similar`、`POST /api/practice-sets` 里同步生成相似题的分支。它们现在还有页面在用。
- 不碰 `backend/app/`（废弃的旧版）。
- 代码规范照 `CLAUDE.md`：函数前写中文文档字符串，变量和函数用 `snake_case`。
- 提交信息沿用仓库现有写法：英文、`chore(cleanup): ...` 这样的前缀。
- 发布到正式环境前必须先问用户（Task 6）。

## Review Focus

这一步删的都是没人调用的东西，最可能出事的是"顺手多删了一点"。下面五条是任务里的删除动作可能带坏、而用户一定会碰到的地方，每条都在对应任务里有测试或核对：

1. 单词播放读音（`GET /api/words/{word_id}/audio`）和打印单词（`POST /api/words/print-pdf`）还在——它们和要删的上传、生成音频接口在同一个文件 `media.py`。（Task 1 的清单测试 + Task 4）
2. 设置里新增、删除学科和标签，新增、修改、删除错题本，修改成就和奖励还能用——目录接口是一个循环统一注册的，改注册方式容易误伤。（Task 3 的测试）
3. 本地开发服务器还能启动、上传还能用——它登记了路由模块，也自己实现了上传。（每个任务都跑 `local_dev_server_test.py`）
4. 旧报告页还能看、能删——`reports.py` 只删"生成"，列表、详情、删除要留。（Task 1 的清单测试 + Task 2 的核对）
5. 网关仍把普通接口转给后端——`worker.test.mjs` 里测转发的用例恰好用了一个要删的接口当例子，要换例子而不是删用例。（Task 4）

---

## 文件一览

| 文件 | 这一步怎么动 |
| --- | --- |
| `cloudflare/scripts/dead_routes_test.py` | 新建：接口清单测试 |
| `cloudflare/src/analytics.py`、`reports.py`、`auth.py`、`motivation.py`、`practices.py`、`questions.py`、`readings.py`、`scan.py`、`words.py`、`knowledge.py`、`media.py` | 删接口和随之没人用的辅助函数、导入 |
| `cloudflare/src/prompts.py` | 删只给"生成旧报告"用的提示词 |
| `cloudflare/src/cache.py` | 路径清单里去掉 `/api/stats/today` |
| `cloudflare/src/catalog.py` | 去掉错因整组、单条读取、学科和标签的修改 |
| `cloudflare/src/main.py` | 删被遮住的 `/api/subjects`、走不到的上传和读附件 |
| `cloudflare/scripts/knowledge_api_test.py`、`scan_test.py`、`cloudflare/pages/worker.test.mjs` | 改掉引用了被删接口的用例 |
| `frontend/src/api/question.js`、`learning_report.js`、`scan.js`、`targeted.js`、`word.js`、`http.js` | 删没人用的函数；缓存规则里去掉 `error-types` |
| `docs/cloudflare-api-checklist.md`、`CLAUDE.md`、`docs/cloudflare-migration-status.md`、`docs/superpowers/specs/2026-11-10-optimization-roadmap.md` | 同步文档 |

全部测试的命令（下文简称"跑全部测试"），在仓库根目录执行，每条都应以退出码 0 结束：

```bash
python cloudflare/scripts/dead_routes_test.py
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
node --test frontend/src/composables/dictation.test.mjs
node --test frontend/src/composables/weeklyReport.test.mjs
python -m compileall -q cloudflare/src
```

开工前先在 `main` 上跑一遍，记下结果作为基线。基线里本来就失败的，不算这一步弄坏的，在最后汇报里单独列出。然后建分支：

```bash
git checkout -b chore/unify-step1-dead-code
```

---

### Task 1：接口清单测试

**Files:**
- Create: `cloudflare/scripts/dead_routes_test.py`

**Interfaces:**
- Produces: 一个可直接运行的脚本，后面每个任务都靠它判断"删对了、没多删"。它**读源码文本**来判断，不导入路由模块（`auth`、`media`、`words` 等模块依赖只在 Cloudflare 上才有的包，本机导不进来）。

- [ ] **Step 1：写测试脚本**

脚本结构参照 `cloudflare/scripts/knowledge_api_test.py` 末尾的写法（`check(名称, 函数)` 收集结果，最后打印"合计 / 通过 / 失败"，有失败就 `raise SystemExit(1)`）。提供一个读文件的小函数 `read_source(name)`，返回 `cloudflare/src/<name>` 的全文。

两张表，逐条断言：

```python
# 必须已经不存在：(文件, 源码里不应再出现的片段)
REMOVED = [
    ('analytics.py', "@router.get('/today')"),
    ('reports.py', "@router.post('/generate')"),
    ('auth.py', "'/api/auth/session'"),
    ('motivation.py', "'/motivation/trigger/{action_code}'"),
    ('practices.py', "'/generate-from-questions'"),
    ('questions.py', "'/api/questions/batch'"),
    ('questions.py', "'/api/questions/debug/{question_id}'"),
    ('readings.py', "@router.post('', status_code=201)"),
    ('readings.py', "@router.put('/{reading_id}')"),
    ('scan.py', "/items/{seq}/restore'"),
    ('words.py', "@router.get('/errors')"),
    ('knowledge.py', "@router.get('/api/knowledge-points/{item_id}')"),
    ('media.py', "'/api/upload/batch-simple'"),
    ('media.py', "'/api/upload/to-error-book/{error_book_id}'"),
    ('media.py', "'/api/rewards/{reward_id}/upload-image'"),
    ('media.py', "'/api/words/generate-audio'"),
    ('main.py', "@app.get('/api/subjects')"),
    ('main.py', "@app.post('/api/upload/file')"),
    ('main.py', "@app.get('/uploads/{key:path}')"),
    ('catalog.py', "'error-types'"),
    ('cache.py', "'/api/stats/today'"),
]

# 必须还在：(文件, 源码里必须出现的片段)
KEPT = [
    ('media.py', "@router.get('/api/words/{word_id}/audio')"),
    ('media.py', "@router.post('/api/words/print-pdf')"),
    ('reports.py', "@router.get('/list')"),
    ('reports.py', "@router.get('/{report_id}')"),
    ('reports.py', "@router.delete('/{report_id}')"),
    ('motivation.py', "/redeem'"),
    ('words.py', "@router.get('/{word_id}')"),
    ('scan.py', "/items/{seq}/dismiss'"),
    ('questions.py', "'/api/questions/filter-options/{subject_id}'"),
    ('main.py', "@app.get('/health')"),
    ('intake.py', "/guide'"),
    ('intake.py', "/papers/check'"),
]
```

两张表里的片段在 2026-11-21 都和源码逐字核对过（`REMOVED` 的 21 条当时都还在，`KEPT` 的 12 条都在）。如果动手时源码已经变了、片段对不上，以源码为准改表，不要改源码。

另外加一个真正导入模块的检查（`catalog` 本机能导入）：

```python
def test_catalog_routes():
    """目录接口只剩该有的：没有错因、没有单条读取、学科和标签不能修改。"""
    import catalog
    routes = {(method, route.path) for route in catalog.router.routes for method in route.methods}
    kinds = ['subjects', 'tags', 'error-books', 'stars/actions', 'achievements', 'rewards']
    for kind in kinds:
        assert ('GET', '/api/' + kind) in routes
        assert ('POST', '/api/' + kind) in routes
        assert ('DELETE', '/api/' + kind + '/{item_id}') in routes
        assert ('GET', '/api/' + kind + '/{item_id}') not in routes
    for kind in ['error-books', 'stars/actions', 'achievements', 'rewards']:
        assert ('PUT', '/api/' + kind + '/{item_id}') in routes
    for kind in ['subjects', 'tags']:
        assert ('PUT', '/api/' + kind + '/{item_id}') not in routes
    assert not any('error-types' in path for _, path in routes)
```

导入 `catalog` 需要把 `cloudflare/src` 加进 `sys.path`，做法照抄 `cloudflare/scripts/knowledge_api_test.py` 开头。

- [ ] **Step 2：运行，确认失败**

Run: `python cloudflare/scripts/dead_routes_test.py`
Expected: `REMOVED` 的 21 条和 `test_catalog_routes` 失败，`KEPT` 的全部通过，退出码 1。如果 `KEPT` 里有失败的，说明片段写错了，回到 Step 1 改表。

- [ ] **Step 3：提交**

```bash
git add cloudflare/scripts/dead_routes_test.py
git commit -m "test(cleanup): pin which routes must go and which must stay"
```

---

### Task 2：删独立的后端接口

**Files:**
- Modify: `cloudflare/src/analytics.py`（`today`，约 116 行起）
- Modify: `cloudflare/src/reports.py`（`generate`，64 行起到文件末尾）
- Modify: `cloudflare/src/auth.py`（`session`，约 96 行）
- Modify: `cloudflare/src/motivation.py`（`trigger_endpoint`，约 141 行）
- Modify: `cloudflare/src/practices.py`（`generate_questions`，约 163 行）
- Modify: `cloudflare/src/questions.py`（`batch` 约 347–456 行、`retired_debug` 约 457 行）
- Modify: `cloudflare/src/readings.py`（`create` 约 74 行、`update` 约 90 行）
- Modify: `cloudflare/src/scan.py`（`restore_item`，约 440 行）
- Modify: `cloudflare/src/words.py`（`errors`，约 136 行）
- Modify: `cloudflare/src/knowledge.py`（`detail`，约 589 行）
- Modify: `cloudflare/src/media.py`（`generate_audio`，约 100 行）
- Modify: `cloudflare/src/prompts.py`、`cloudflare/src/cache.py`
- Test: `cloudflare/scripts/knowledge_api_test.py`、`cloudflare/scripts/scan_test.py`

行号是 2026-11-21 的，以函数名为准。

**Interfaces:**
- Consumes: Task 1 的 `dead_routes_test.py`。
- Produces: 无（只删）。

- [ ] **Step 1：逐条重新确认没有调用方**

对上面每个接口，用它路径里最有辨识度的一段在 Global Constraints 列的六个范围里搜一遍，例如：

```bash
grep -rn "generate-from-questions" frontend/src cloudflare/pages/_worker.js tools/easyfix-intake cloudflare/src cloudflare/scripts backend/scripts
```

Expected: 只有接口自己的定义、测试脚本和文档里出现。`tools/easyfix-intake/SKILL.md` 里有一句"不调用旧的 /api/questions/batch"，那是说明，不算调用方。别的地方出现了，就不删这一条，记下来。

- [ ] **Step 2：改引用了这些接口的测试**

- `knowledge_api_test.py`：删掉 `test_question_batch_partial_errors`（约 220 行）和 `main()` 里登记它的那一行——它测的就是要删的批量录入接口。
- `knowledge_api_test.py`：`test_report_metrics_server_written`（约 300–340 行）测的是"生成旧报告"。删掉这个函数和 `main()` 里的 `check('报告指标服务端写入', ...)`。
- `scan_test.py` 的 `test_changes_library`（约 331 行）：从路径列表里去掉 `'/api/scan/pages/3/items/2/restore'` 这一项，其余不动。

- [ ] **Step 3：删接口函数**

每个接口删掉装饰器和整个函数。`reports.py` 只删 `generate`，`listing`、`detail`、`delete` 三个留着。`readings.py` 里 `create`、`update` 调用的 `save`、`detail` 等辅助函数，如果还被 `generate` 等保留的接口使用就留着。

- [ ] **Step 4：删随之没人用的东西**

- 每个改过的文件里，只被刚删掉的函数用到的辅助函数和 `import` 一并删掉。已知的候选：`questions.py` 的 `batch_error`；`reports.py` 顶部的 `timedelta`、`counted`、`COUNTING_MODE`、`module_stats`、`generate_json`、`PromptLibrary`；`scan.py` 里如果 `changes_library` 之外还有只为 `restore` 服务的分支。每删一个先在 `cloudflare/src` 和 `cloudflare/scripts` 里搜函数名，确认没有别处用。
- `prompts.py`：`PromptLibrary` 里只被 `reports.generate` 用到的提示词（在 `reports.py` 删之前先看它调了 `PromptLibrary` 的哪个成员），确认 `similar.py`、`targeted.py`、`weekly.py`、`word_focus.py` 都不用它之后删掉。
- `cache.py` 第 7 行的 `PATHS` 里去掉 `'/api/stats/today'`。
- 装了 pyflakes 的话运行 `python -m pyflakes cloudflare/src`，把它报的、由这次删除造成的"imported but unused"清掉；没装就跳过，不为此安装依赖。

- [ ] **Step 5：跑全部测试**

Expected: `dead_routes_test.py` 里除了 `media.py` 的三条上传、`main.py` 的三条、`catalog.py` 的一条和 `test_catalog_routes` 之外都通过（那些是 Task 3、4 的）；其余脚本和基线一致。

- [ ] **Step 6：核对旧报告页的接口还在**

Run: `grep -n "^@router" cloudflare/src/reports.py`
Expected: 正好三行——`get('/list')`、`get('/{report_id}')`、`delete('/{report_id}')`。

- [ ] **Step 7：提交**

```bash
git add cloudflare/src cloudflare/scripts
git commit -m "chore(cleanup): remove backend endpoints nothing calls"
```

---

### Task 3：目录类接口

**Files:**
- Modify: `cloudflare/src/catalog.py`（`CATALOG` 字典在 9–17 行，`register` 末尾的五条 `add_api_route` 在约 124–128 行）

**Interfaces:**
- Consumes: Task 1 的 `test_catalog_routes`。
- Produces: 无。

- [ ] **Step 1：重新确认没有调用方**

```bash
grep -rnE "error-types|(get|put)\(\`/(subjects|tags)/|get\(\`/(error-books|stars/actions|achievements|rewards)/\\$" frontend/src cloudflare/pages/_worker.js tools/easyfix-intake
```

Expected: 只有 `frontend/src/api/http.js` 的缓存规则里出现 `error-types`（Task 5 处理）。前端对目录的修改只有四处，都要保留：`motivation.js` 的 `put(/stars/actions/…)`、`put(/achievements/…)`、`put(/rewards/…)`，`question.js` 的 `put(/error-books/…)`。

- [ ] **Step 2：改 `catalog.py`**

- 从 `CATALOG` 里删掉 `'error-types'` 这一行。数据库的 `error_type` 表不动。
- 在文件里加一个常量 `EDITABLE_KINDS = {'error-books', 'stars/actions', 'achievements', 'rewards'}`（可以修改的目录）。
- `register` 末尾：去掉单条读取那一条 `add_api_route(..., get_item, methods=['GET'])`；`PUT` 那一条只在 `kind in EDITABLE_KINDS` 时注册。
- `get_item` 函数本身留着，`save_item` 和 `delete_item` 内部还在调用它。
- 文件顶部的文档字符串里"错误类型"几个字去掉。
- 文件里专门针对 `error-types` 的分支一并删掉（2026-11-21 时有两处：约 27 行 `if kind == 'error-types':`，约 47 行列表筛选里的 `if kind == 'error-types' else`，后者删分支时保留 `else` 那一半的写法）。

- [ ] **Step 3：运行**

Run: `python cloudflare/scripts/dead_routes_test.py`
Expected: `test_catalog_routes` 和 `catalog.py` 的那条通过。

Run: `python cloudflare/scripts/knowledge_api_test.py` 和 `python cloudflare/scripts/local_dev_server_test.py`
Expected: 和基线一致。`local_dev_server.py` 第 55 行有一份 `ERROR_TYPES` 种子数据，它往表里写数据、不走接口，不用改；如果这两个脚本里有用例请求了 `/api/error-types` 或目录的单条读取，把那个用例改成用列表接口取数据。

- [ ] **Step 4：提交**

```bash
git add cloudflare/src/catalog.py cloudflare/scripts
git commit -m "chore(cleanup): drop error-type routes and unused catalog reads/updates"
```

---

### Task 4：上传的死代码

**Files:**
- Modify: `cloudflare/src/main.py`（`subjects` 约 75 行、`upload_file` 约 81 行、`image` 约 101 行）
- Modify: `cloudflare/src/media.py`（`save_image` 约 16 行、`batch` 约 29 行、`to_book` 约 41 行、`reward_image` 约 54 行）
- Test: `cloudflare/pages/worker.test.mjs`（约 160 行）

**Interfaces:**
- Consumes: Task 1 的清单测试。
- Produces: 无。

背景：生产环境里 `/api/upload/file`、`/api/upload/batch-simple`、`/uploads/` 由网关 `cloudflare/pages/_worker.js` 自己处理（第 26、82、115 行），不转给后端；后端不开放 workers.dev。本地开发服务器 `local_dev_server.py`（183–212 行）另有自己的实现。所以后端这几份谁也走不到。

- [ ] **Step 1：重新确认**

```bash
grep -n "UPLOAD_PATHS\|startsWith('/uploads/')" cloudflare/pages/_worker.js
grep -rn "to-error-book\|upload-image" frontend/src tools/easyfix-intake cloudflare/src
grep -rn "save_image\|media\.batch\|media\.to_book\|main\.image\|main\.upload_file" cloudflare/src cloudflare/scripts
```

Expected: 第一条有输出，证明网关仍在接管；第二条只有 `media.py` 里的定义；第三条只有 `media.py` 内部的互相调用。

- [ ] **Step 2：改 `worker.test.mjs` 的转发用例**

`test('其他接口仍然转给 Python 后端', ...)` 里用 `/api/upload/to-error-book/3` 当"会被转发的上传类请求"的例子。这个用例要留，换一个仍然存在的例子：把那一行换成对 `/api/questions` 的 POST（带一个文件的表单即可，沿用 `uploadRequest`），并把断言里的 `'/api/upload/to-error-book/3'` 换成 `'/api/questions'`。用例要证明的事不变：不在 `UPLOAD_PATHS` 里的请求原样转给后端，R2 里没有写入（`stored.size` 为 0）。

Run: `node --test cloudflare/pages/worker.test.mjs`
Expected: 全部通过（这时后端还没删，用例只测网关）。

- [ ] **Step 3：删 `media.py` 里的四个函数**

删 `batch`、`to_book`、`reward_image` 和只被它们用的 `save_image`。`audio`、`select_print_words`、`print_words` 不动。顶部的 `import`（`uuid4`、`File`、`UploadFile` 等）不再用到的删掉。`cloudflare/scripts/phrase_focus_test.py` 第 1073、1263 行 `import media`，删完跑它确认没受影响。

- [ ] **Step 4：删 `main.py` 里的三个函数**

删 `subjects`、`upload_file`、`image`，以及只为它们导入的名字（`UploadFile`、`File` 等；`HTTPException`、`Database` 如果文件里别处还用就留着）。`health` 和路由注册不动。

- [ ] **Step 5：跑全部测试**

Expected: `dead_routes_test.py` 全部通过；其余和基线一致。

- [ ] **Step 6：提交**

```bash
git add cloudflare/src/main.py cloudflare/src/media.py cloudflare/pages/worker.test.mjs
git commit -m "chore(cleanup): remove backend upload code the gateway already replaced"
```

---

### Task 5：前端没人用的接口函数

**Files:**
- Modify: `frontend/src/api/question.js`（`createBatch` 约 19 行、`getTodayStats` 约 151 行、`getKnowledgePoints` 约 154 行）
- Modify: `frontend/src/api/learning_report.js`（`generate` 约 13 行）
- Modify: `frontend/src/api/scan.js`（`restore` 约 39 行）
- Modify: `frontend/src/api/targeted.js`（`pending` 约 35 行）
- Modify: `frontend/src/api/word.js`（`getErrors` 约 51 行）
- Modify: `frontend/src/api/http.js`（约 12 行的缓存规则）

**Interfaces:**
- Consumes: 无。
- Produces: 无。

注意同名不同物：`word.js` 第 66 行还有一个 `wordApi.createBatch`，`PhraseAnnotateDialog.vue` 在用，**不要删**；要删的是 `question.js` 里的 `questionApi.createBatch`。`learningAnalysisApi.getKnowledgeStats`（`learning_analysis.js`）在用，不要删；要删的是 `question.js` 里 `statsApi.getKnowledgePoints`。

- [ ] **Step 1：重新确认没有使用方**

```bash
grep -rnE "questionApi\.createBatch|getTodayStats|statsApi\.getKnowledgePoints|learningReportApi\.generate|scanApi\.restore|targetedApi\.pending|wordApi\.getErrors" frontend/src
```

Expected: 没有输出。有输出的那个函数就不删。

- [ ] **Step 2：删这 7 个函数**

删函数连同它上面的注释。`http.js` 里 5 分钟缓存的那条正则，去掉其中的 `|error-types`，其余不动。

- [ ] **Step 3：验证**

Run: `node --test frontend/src/composables/dictation.test.mjs` 和 `node --test frontend/src/composables/weeklyReport.test.mjs`
Expected: 通过。

Run: `python backend/scripts/prepare_cloudflare_frontend.py`
Expected: 构建成功，产物在 `tmp/cloudflare-pages-build`，没有"is not exported"或找不到函数的报错。

- [ ] **Step 4：提交**

```bash
git add frontend/src/api
git commit -m "chore(cleanup): remove frontend API helpers nothing uses"
```

---

### Task 6：文档、发布、核对

**Files:**
- Modify: `docs/cloudflare-api-checklist.md`
- Modify: `CLAUDE.md`
- Modify: `docs/cloudflare-migration-status.md`
- Modify: `docs/superpowers/specs/2026-11-10-optimization-roadmap.md`

**Interfaces:**
- Consumes: 前五个任务的全部改动。
- Produces: 线上版本；给用户的核对清单。

- [ ] **Step 1：同步文档**

- `docs/cloudflare-api-checklist.md`：删掉已删接口对应的条目（约第 7、24、47、51、60、62、63、64、68、73、80、87、88、91、97、101、115、121 行，以实际删掉的接口为准）。`POST /api/upload/batch-simple`、`POST /api/upload/file` 的条目保留，在后面注明"由 Pages 网关处理"。`POST /api/questions/batch-similar` 这一步没删，条目保留。
- `CLAUDE.md`"后端 Worker 模块"表里 `main.py` 那一行，现在写的是"FastAPI 入口，注册路由；`/health`、`/api/subjects`、`/api/upload/file`"，改成"FastAPI 入口，注册路由；`/health`；定时任务入口"。`catalog.py` 那一行的"错误类型"去掉。
- 路线图第 4 行的状态里，项目 5 改成"第 1 步（清理没人用的代码）已上线（日期）"，等 Step 5 发布完再写日期。

- [ ] **Step 2：跑全部测试，再做一次整体搜索**

跑全部测试，Expected: 和基线一致，`dead_routes_test.py` 全过。

```bash
git diff main --stat
```

Expected: 只有"文件一览"里列出的文件。多出来的文件逐个说明原因或还原。

- [ ] **Step 3：请用户确认可以发布**

向用户汇报：删了哪些、哪几条因为发现有调用方而没删、测试结果、基线里本来就失败的测试（如果有）。**得到用户明确同意后才继续。** 同时问清楚是合并进 `main` 后再发布，还是从分支发布（之前的项目两种都有过）。

- [ ] **Step 4：发布**

照 `docs/cloudflare-migration-status.md` 的"日常部署"做，顺序是**先前端（Pages）、后后端（Worker）**。部署工具的实际情况（wrangler 的位置、代理、偶发的 10021 错误）见该文档；这一步没有数据库迁移，不需要开维护开关。记下发布前后的 Worker 版本号和 Pages 部署号，回滚要用。

- [ ] **Step 5：发布后核对**

不用登录就能核对的：

```bash
curl -s -o /dev/null -w "%{http_code}\n" https://easyfix-bl2.pages.dev/health
curl -s -o /dev/null -w "%{http_code}\n" https://easyfix-bl2.pages.dev/api/intake/guide
curl -s -o /dev/null -w "%{http_code}\n" https://easyfix-bl2.pages.dev/
```

Expected: 第一条 200；第二条 401（没带令牌）；第三条是登录页的跳转或 200。

需要登录的，本机没有访问密码，交给用户核对。把下面这份清单发给用户：

1. 打开首页、错题列表、练习中心、单词本、周报，页面正常显示。
2. 单词本里点一个单词的读音，能播放。
3. 管理中心：新增一个测试标签再删掉；改一个错题本的名称再改回去。
4. 错题列表里打开一道带图的题，原图能显示。
5. 周报页的"旧报告"能打开一份旧报告。
6. 用录入技能录一张照片（或等下次正常录入时留意是否成功）。

- [ ] **Step 6：写变更记录并提交**

在 `docs/cloudflare-migration-status.md` 末尾追加"变更记录：清理没人用的代码（项目 5 第 1 步，日期）"，格式照前面几条记录：分支和提交、删了什么（按类别写数量，不必逐条列）、保留了什么及原因、发布前后的 Worker 版本号和 Pages 部署号、核对结果、未验证的事项（用户还没核对完的清单项）。补上路线图状态行的日期。

```bash
git add docs CLAUDE.md
git commit -m "docs: record dead-code cleanup release"
```

推送到远端 `main` 之前再问用户一次。
