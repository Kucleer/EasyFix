# 整页识别录入 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在"录入错题"页上传一张整页照片，后端经 Workers VPC 隧道调主机上的本地 OCR，再用现有文本模型拆题判错、补答案考点，家长逐题核对后写进错题库。

**Architecture:** 新迁移 `0014` 只加一张 `scan_page` 表，一张照片一条记录，题目草稿存 JSON。后端三个新模块：`scan_model.py`（纯规则：提示词、清洗、状态判断）、`ocr_client.py`（经 `OCR_HOST` 绑定调主机、从 R2 读图，唯一碰运行时的地方）、`scan.py`（接口，识别分步推进，题目逐道录入复用 `questions.save`）。前端把 `Upload.vue` 改成状态机，手工表单抽成组件原样保留，新增整理区组件。

**Tech Stack:** Python FastAPI on Cloudflare Workers、D1、R2、Workers VPC；Vue 3 + Element Plus + Vite；测试用独立 Python 脚本（内存 SQLite）和 `node --test`。

**Spec:** `docs/superpowers/specs/2026-11-11-page-scan-intake-design.md`（下称"设计"），主机接口以 `docs/superpowers/specs/2026-11-11-ocr-host-service-design.md` 第 4 节为准。每个任务开始前先读设计里对应的小节，本计划不重抄设计已写明的规则。

## Global Constraints

- 在新分支 `feature/page-scan-intake` 上做（执行时按 `superpowers:using-git-worktrees` 建工作树）。勤提交，每个任务结束提交一次，不推送；推送和发布只在 Task 11。
- 只改 `cloudflare/src/`、`cloudflare/migrations/`、`cloudflare/scripts/`、`cloudflare/wrangler.jsonc`、`frontend/src/`、`docs/`。不改 `backend/app/`、`cloudflare/pdf/`、`tools/easyfix-intake/`。
- 第一条路不动：`intake.py`、`intake_model.py`、`papers.py` 一行不改；`load_catalog`、`load_error_type_names`、`IMAGE_KEY_PATTERN`、`current_student_id` 只调用。`questions.py` 只在 `FIELDS` 里加 `'wrong_evidence'`。
- 数据库只追加 `cloudflare/migrations/0014_scan_page.sql`，只建表和索引，带 `deleted` 软删除。
- 绑定和密钥名固定：VPC 服务绑定 `OCR_HOST`，共享口令密钥 `OCR_SHARED_KEY`，重扫开关变量 `SCAN_RESCAN`（值为 `off` 时关闭，缺省开启）。口令值不进仓库、文档、提交说明、对话和日志。
- 主机约定固定值：请求头 `X-EasyFix-OCR-Key`；`contract` 必须是 `1`；`mode` 为 `normal` / `enhanced`；忙时 503 `busy` 等 2 秒重试，最多 3 次；后端超时 `normal` 70 秒、`enhanced` 130 秒；健康检查 3 秒超时。
- 取值固定：页状态 `uploaded` / `reading` / `analyzing` / `rescanning` / `ready` / `failed` / `closed`；判断 `wrong` / `right` / `unsure`；读图异常 `broken_formula` / `unsolvable` / `merged` / `figure_needed`；题目状态 `open` / `accepted` / `dismissed`；判错依据文字 `页面识别，家长确认`。
- 孩子的照片和识别结果不进仓库。回归脚本默认输出到 `%USERPROFILE%\.easyfix\scan-regression\`（仓库的 `tmp/` 并没有整体忽略，不能放那里）。
- 任何动正式环境、Cloudflare 账号、那台主机的步骤（部署、迁移、填密钥）执行前都要得到用户明确同意。
- 代码规范：`snake_case`，每个函数前写中文文档字符串，复杂逻辑加中文行内注释；前端 `<script setup>` + Element Plus，按钮 `size="small"`、右对齐、一张卡片只有一个主色按钮；768px 断点。页面文案用直白中文。

## 与设计的出入（执行前请用户过目）

1. **不刷新缓存、不记日志的接口比设计列的多三个**：新建一页、手工加一道、结束一页。它们都只改草稿，不改错题库。只有录入一道、撤回会刷新（"全部录入"是页面逐道调录入一道）。
2. **"录入一道"用草稿里存好的字段，不再从页面传一遍。** "保存修改"已经把改动存回草稿，录入时以草稿为准，只有一份数据来源。
3. **读图提示在点过"修改"并保存后视为已处理**：不再弹确认（设计 8.5 已定），也算进"全部录入"。
4. **重扫这一步失败时不算整页失败**：保留第一次整理的结果，直接进入可以整理。
5. **`error` 列只存给人看的一句话**；主机返回的 `detail` 记进 `timings.host_detail`，排查时看。

> 2026-11-11 终审后，代码已按确认后的设计重新对齐（A–E）：做对的题只返回题号、题干开头和判断，补成错题时拿整页文字补全；`generate_json` 加可选的 `max_tokens`、`temperature`；超时改为调主机 120 秒、页面等一步 150 秒、卡住判定 180 秒；"全部录入"不再有接口，由页面逐道调用；识别顺序写成 `scan_model.run_page`，后端和独立的回归脚本共用。本计划其余各处的旧写法（70 / 130 秒、全部录入接口、回归脚本起本机服务等）以设计文档为准。

## Review Focus

1. **同一道题被点了两次"录入"，或两台设备同时录入**：错题库里只能多出一道题，第二次拿到同一道题。测试在 Task 4。
2. **手机锁屏或网络断开，推进到一半的请求没回来**：150 秒内再推进返回"正在处理"、不重复调主机；超过 150 秒能接着做。测试在 Task 3。
3. **模型返回的内容乱七八糟**（`questions` 不是数组、考点编号是字符串或不在清单里、主考点不在所选考点里、错因不在清单里、上百道题）：清洗后不报 500，坏的题标"拿不准"。测试在 Task 2。
4. **主机返回的不是约定的 JSON**（隧道返回 HTML 错误页、`contract` 是 2、一直 503 忙、连不上）：这一页变成"读图没成功"可以再试，不报 500。测试在 Task 2、Task 3。
5. **页面开得久，这一页已经在别的设备上点了"下一张"**：再点录入、撤回、修改都返回 409 并提示刷新，不写库。测试在 Task 4。

---

## 文件结构

| 文件 | 责任 |
| --- | --- |
| `cloudflare/migrations/0014_scan_page.sql`（新） | `scan_page` 表和索引 |
| `cloudflare/src/scan_model.py`（新） | 纯规则：常量、提示词、模型返回清洗、主机返回解读、下一步判断、录入候选、编辑校验、组装错题字段 |
| `cloudflare/src/ocr_client.py`（新） | 经 `OCR_HOST` 调主机 `/health`、`/ocr`，从 R2 读图；测试和本机服务整体替换它 |
| `cloudflare/src/scan.py`（新） | 全部 `/api/scan/*` 接口 |
| `cloudflare/src/questions.py`（改） | `FIELDS` 加 `wrong_evidence` |
| `cloudflare/src/main.py`、`auth.py`（改） | 注册路由；只改草稿的扫描接口不触发缓存失效 |
| `cloudflare/wrangler.jsonc`（改） | `vpc_services` 绑定、`SCAN_RESCAN` 变量 |
| `cloudflare/scripts/scan_test.py`（新） | 后端全部测试 |
| `cloudflare/scripts/local_dev_server.py`、`local_dev_server_test.py`（改） | 加 0014、挂 scan 路由、假主机和假模型、可切真主机和真模型 |
| `cloudflare/scripts/scan_regression.py`（新） | 主机上跑 20 张回归图的脚本 |
| `frontend/src/api/scan.js`（新） | 扫描接口调用 |
| `frontend/src/composables/scanPage.js`、`scanPage.test.mjs`（新） | 前端纯逻辑 |
| `frontend/src/components/ManualQuestionForm.vue`（新） | 从 `Upload.vue` 原样搬出的手工表单，加预置图片和学科年级学期 |
| `frontend/src/components/scan/ScanImagePane.vue`、`ScanItemCard.vue`、`ScanWorkspace.vue`（新） | 原图区、题目卡片、整理区 |
| `frontend/src/views/Upload.vue`（改） | 选图 / 识别中 / 整理 / 手工 四态 |

---

### Task 1: 连通性试验（接口骨架 + 主机健康检查）

设计 10.2 要求连通性试验排在所有正式环境改动之前。本任务只做能独立部署、不依赖 `0014` 的那一点：`ocr_client.py`、`scan_model` 里解读健康检查的函数、`GET /api/scan/health`。部署那一步要等主机端回传 VPC 服务编号，**等不到时跳过 Step 6–8，继续 Task 2 起的本机开发，回头再做**。

**Files:**
- Create: `cloudflare/src/ocr_client.py`, `cloudflare/src/scan_model.py`, `cloudflare/src/scan.py`, `cloudflare/scripts/scan_test.py`
- Modify: `cloudflare/src/main.py`, `cloudflare/wrangler.jsonc`

**Interfaces:**
- Produces:
  - `ocr_client.OCR_BINDING = 'OCR_HOST'`、`ocr_client.KEY_SECRET = 'OCR_SHARED_KEY'`、`ocr_client.BASE_URL = 'http://ocr-host'`
  - `async ocr_client.fetch_health(env, timeout_seconds: float) -> tuple[int, dict | None]`：状态码和解析后的 JSON；绑定或口令缺失、连不上、超时、不是 JSON 时返回 `(0, None)` 或 `(状态码, None)`，从不抛异常
  - `async ocr_client.fetch_ocr(env, content: bytes, content_type: str, mode: str, timeout_seconds: float) -> tuple[int, dict | None]`：同上的约定
  - `async ocr_client.read_image(env, key: str) -> tuple[bytes, str] | None`：R2 取图，返回字节和类型（`image/jpg` 归一为 `image/jpeg`），不存在返回 `None`
  - `scan_model.CONTRACT_VERSION = 1`、`scan_model.HEALTH_TIMEOUT_SECONDS = 3`
  - `scan_model.interpret_health(status: int, body: dict | None) -> bool`：200、`ok` 为真、`contract == 1` 才是可用
  - `scan.router`（`APIRouter()`），`GET /api/scan/health` 返回 `{'available': bool}`，不透出主机任何细节
  - `scan_test.py` 的测试框架：`configure_output`、`check`、`main`、`TESTS` 列表，写法照 `intake_test.py`

- [ ] **Step 1: 写失败的测试**（`scan_test.py`）

```python
def test_interpret_health():
    assert scan_model.interpret_health(200, {'ok': True, 'contract': 1, 'ollama': True}) is True
    assert scan_model.interpret_health(200, {'ok': False, 'contract': 1, 'ollama': False}) is False
    assert scan_model.interpret_health(200, {'ok': True, 'contract': 2}) is False
    assert scan_model.interpret_health(200, None) is False
    assert scan_model.interpret_health(401, {'ok': False}) is False
    assert scan_model.interpret_health(0, None) is False

def test_health_endpoint_hides_host_details():
    # 把 scan.ocr_client.fetch_health 换成返回 (200, {'ok': True, 'contract': 1, 'model': 'x'}) 的假函数
    assert run(scan.health(fake_request(None, db))) == {'available': True}
    # 换成返回 (0, None)
    assert run(scan.health(fake_request(None, db))) == {'available': False}
```

- [ ] **Step 2: 运行确认失败** — `python cloudflare/scripts/scan_test.py`，预期 ImportError / 断言失败。

- [ ] **Step 3: 实现上面三个模块的这些函数和 `health` 接口；`main.py` 在 `questions_router` 之前 `include_router(scan_router)`**

`ocr_client` 照 `pdf.call` 的写法用 `env.OCR_HOST.fetch(BASE_URL + path, method=..., headers=..., body=..., signal=AbortSignal.timeout(毫秒))`；图片字节用 `to_js(content)` 传；请求头带 `X-EasyFix-OCR-Key: str(env.OCR_SHARED_KEY)` 和 `Content-Type`。所有异常收在函数内。`scan.py` 用 `import ocr_client`（模块引用，测试替换 `scan.ocr_client`）。

- [ ] **Step 4: 运行确认通过**，再跑 `python -m compileall -q cloudflare/src`。

- [ ] **Step 5: 提交** — `git commit -m "feat(scan): host health check skeleton"`

- [ ] **Step 6: 等主机端回传 VPC 服务编号后，在 `wrangler.jsonc` 加 `"vpc_services": [{"binding": "OCR_HOST", "service_id": "<编号>"}]`**（字段名以当时的 Workers VPC 文档为准）。用户在 Worker 密钥里填 `OCR_SHARED_KEY`（用户本人执行 `wrangler secret put`，值不经过对话）。

- [ ] **Step 7: 问用户同意后部署后端**：`python -m compileall -q cloudflare/src && node cloudflare/tools/cli.cjs deploy --config cloudflare/wrangler.jsonc`。

- [ ] **Step 8: 验证**：带 Agent 令牌请求 `https://easyfix-bl2.pages.dev/api/scan/health`，预期 `{"available": true}`；记下用时。不通时按设计 10.2：先看 `wrangler tail` 报错；若是 Python 用不了这个绑定，停下和用户商量加 JavaScript 转发 Worker（照 `cloudflare/pdf/` 的服务绑定做法）；整体不通也停下和用户商量。结果记进 `docs/cloudflare-migration-status.md`，提交。

---

### Task 2: 纯规则 `scan_model.py`

**Files:**
- Modify: `cloudflare/src/scan_model.py`, `cloudflare/scripts/scan_test.py`

**Interfaces:**
- Consumes: Task 1 的 `CONTRACT_VERSION`
- Produces（全部是纯函数，不访问数据库、网络和时钟）：
  - 常量：`VERDICTS`、`FLAGS`（四个标记到设计 6.4 第三列提示文字的字典）、`ITEM_STATES`、`STALE_SECONDS = 150`、`HOST_TIMEOUT_SECONDS = {'normal': 70, 'enhanced': 130}`、`BUSY_RETRIES = 3`、`BUSY_WAIT_SECONDS = 2`、`WRONG_EVIDENCE = '页面识别，家长确认'`、`MAX_ITEMS = 60`
  - `class ScanError(ValueError)`，属性 `detail`（中文）
  - 草稿一项的结构（下文称 item）：`seq`（等于它在数组里的下标，永不变）、`question_no`、`parsed_question`、`wrong_answer`、`verdict`、`reason`、`flags`（列表）、`answer`、`analysis`、`knowledge_point_ids`（整数列表）、`primary_knowledge_point_id`（整数或 None）、`error_types`（错因名列表）、`difficulty`（1–5）、`state`、`question_id`、`edited`（布尔）、`source`（`model` / `promoted` / `manual`）
  - `build_page_prompt(subject_name: str, grade: int | None, semester: int | None, ocr_text: str, enhanced_text: str | None, catalog: list, error_type_names: list[str]) -> str`：`catalog` 是 `intake.load_catalog` 的返回；提示词满足设计 6.2–6.4，要求返回 `{"questions": [...]}`，每项键名就是 item 的键名（去掉 `seq/state/question_id/edited/source`）；`enhanced_text` 非空时附上并说明它是分段重读的结果、两份对照着用
  - `build_fill_prompt(subject_name: str, grade: int | None, item: dict, catalog: list, error_type_names: list[str]) -> str`：只针对这一道，要求返回 `answer/analysis/knowledge_point_ids/primary_knowledge_point_id/error_types/difficulty`
  - `clean_items(raw, catalog_ids: set[int], error_type_names: set[str]) -> list[dict]`
  - `clean_fill(raw, catalog_ids: set[int], error_type_names: set[str]) -> dict`：只返回那六个字段，规则同 `clean_items`
  - `needs_rescan(items: list[dict], rescan_used: bool, rescan_enabled: bool) -> bool`
  - `interpret_ocr(status: int, body: dict | None) -> dict`：返回 `{'kind': 'ok' | 'busy' | 'failed', 'text': str, 'elapsed_ms': int | None, 'user_text': str, 'detail': str}`
  - `next_step(page: dict, now_seconds: int) -> str | None`：返回 `'read'` / `'analyze'` / `'rescan'` / `'working'` / `None`（不用做）
  - `has_warning(item: dict) -> bool`：有 `flags` 且没被改过
  - `accept_all_seqs(items: list[dict]) -> list[int]`
  - `clean_edit(payload) -> dict`
  - `blank_item(seq: int) -> dict`
  - `question_payload(page: dict, item: dict) -> dict`
  - `changes_library(method: str, path: str) -> bool`

- [ ] **Step 1: 写失败的测试**

```python
def test_clean_items_drops_bad_catalog_and_error_types():
    raw = {'questions': [{'question_no': '3', 'parsed_question': '比 x 的立方少 3', 'wrong_answer': 'x^2+3',
           'verdict': 'wrong', 'reason': '应为 x^3-3', 'flags': ['broken_formula', 'nonsense'],
           'answer': 'x^3-3', 'analysis': '…', 'knowledge_point_ids': [101, 999, '101'],
           'primary_knowledge_point_id': 999, 'error_types': ['计算错误', '乱写'], 'difficulty': 9}]}
    [item] = scan_model.clean_items(raw, {101, 102}, {'计算错误'})
    assert item['seq'] == 0 and item['state'] == 'open' and item['source'] == 'model' and item['edited'] is False
    assert item['knowledge_point_ids'] == [101]
    assert item['primary_knowledge_point_id'] == 101       # 主考点无效、只剩一个考点时用它；剩多个时为 None
    assert item['error_types'] == ['计算错误'] and item['difficulty'] == 3
    assert item['flags'] == ['broken_formula']

def test_clean_items_right_items_drop_answer_fields():
    [item] = scan_model.clean_items({'questions': [{'parsed_question': 'a', 'verdict': 'right', 'answer': '1',
                                     'knowledge_point_ids': [101]}]}, {101}, set())
    assert item['answer'] == '' and item['knowledge_point_ids'] == [] and item['verdict'] == 'right'

def test_clean_items_bad_types_mark_unsure():
    items = scan_model.clean_items({'questions': [{'parsed_question': 5, 'verdict': 'wrong'}, 'junk',
                                                  {'parsed_question': 'b', 'verdict': 'maybe'}]}, set(), set())
    assert [i['verdict'] for i in items] == ['unsure', 'unsure']   # 不是对象的那项丢掉
    assert [i['seq'] for i in items] == [0, 1]
    assert items[0]['parsed_question'] == '' and items[0]['reason']

def test_clean_items_garbage_and_limit():
    assert scan_model.clean_items(None, set(), set()) == []
    assert scan_model.clean_items({'questions': 'x'}, set(), set()) == []
    many = {'questions': [{'parsed_question': str(n), 'verdict': 'wrong'} for n in range(200)]}
    assert len(scan_model.clean_items(many, set(), set())) == scan_model.MAX_ITEMS

def test_needs_rescan():
    flagged = [{'flags': ['merged'], 'verdict': 'wrong'}]
    assert scan_model.needs_rescan(flagged, False, True) is True
    assert scan_model.needs_rescan(flagged, True, True) is False
    assert scan_model.needs_rescan(flagged, False, False) is False
    assert scan_model.needs_rescan([{'flags': [], 'verdict': 'wrong'}], False, True) is False

def test_interpret_ocr():
    ok = scan_model.interpret_ocr(200, {'ok': True, 'contract': 1, 'mode': 'normal', 'text': '1. 计算', 'segments': ['1. 计算'], 'elapsed_ms': 5000})
    assert ok['kind'] == 'ok' and ok['text'] == '1. 计算' and ok['elapsed_ms'] == 5000
    assert scan_model.interpret_ocr(503, {'ok': False, 'contract': 1, 'code': 'busy'})['kind'] == 'busy'
    wrong = scan_model.interpret_ocr(200, {'ok': True, 'contract': 2, 'text': 'x'})
    assert wrong['kind'] == 'failed' and '版本不一致' in wrong['user_text']
    for status, body in [(502, {'ok': False, 'code': 'ocr_failed', 'detail': 'Ollama 连不上'}), (0, None),
                         (200, None), (200, {'ok': True, 'contract': 1, 'text': '   '}), (530, None)]:
        result = scan_model.interpret_ocr(status, body)
        assert result['kind'] == 'failed' and result['user_text'] == '读图没成功'
    assert scan_model.interpret_ocr(502, {'ok': False, 'code': 'ocr_failed', 'detail': 'Ollama 连不上'})['detail'] == 'Ollama 连不上'

def test_next_step():
    now = 10_000
    page = lambda **kw: {'status': 'uploaded', 'step_started_at': None, 'ocr_text': None, **kw}
    assert scan_model.next_step(page(), now) == 'read'
    assert scan_model.next_step(page(status='reading', step_started_at=now - 10), now) == 'working'
    assert scan_model.next_step(page(status='reading', step_started_at=now - 151), now) == 'read'
    assert scan_model.next_step(page(status='analyzing', ocr_text='t'), now) == 'analyze'
    assert scan_model.next_step(page(status='rescanning', ocr_text='t'), now) == 'rescan'
    assert scan_model.next_step(page(status='failed'), now) == 'read'
    assert scan_model.next_step(page(status='failed', ocr_text='t'), now) == 'analyze'
    assert scan_model.next_step(page(status='ready'), now) is None
    assert scan_model.next_step(page(status='closed'), now) is None

def test_accept_all_and_warning():
    items = [
        {'seq': 0, 'state': 'open', 'verdict': 'wrong', 'flags': [], 'edited': False},
        {'seq': 1, 'state': 'open', 'verdict': 'wrong', 'flags': ['merged'], 'edited': False},
        {'seq': 2, 'state': 'open', 'verdict': 'wrong', 'flags': ['merged'], 'edited': True},
        {'seq': 3, 'state': 'open', 'verdict': 'unsure', 'flags': [], 'edited': False},
        {'seq': 4, 'state': 'accepted', 'verdict': 'wrong', 'flags': [], 'edited': False},
        {'seq': 5, 'state': 'dismissed', 'verdict': 'wrong', 'flags': [], 'edited': False},
        {'seq': 6, 'state': 'open', 'verdict': 'right', 'flags': [], 'edited': False},
    ]
    assert scan_model.accept_all_seqs(items) == [0, 2]
    assert scan_model.has_warning(items[1]) is True and scan_model.has_warning(items[2]) is False

def test_clean_edit():
    edit = scan_model.clean_edit({'question_no': '7', 'parsed_question': '计算', 'wrong_answer': '', 'answer': '1',
                                  'analysis': '', 'knowledge_point_ids': [101], 'primary_knowledge_point_id': 101,
                                  'error_types': ['计算错误'], 'difficulty': 2})
    assert edit['difficulty'] == 2 and edit['knowledge_point_ids'] == [101]
    for bad in [{'difficulty': 6}, {'difficulty': True}, {'knowledge_point_ids': ['1']},
                {'knowledge_point_ids': [101], 'primary_knowledge_point_id': 102}, {'parsed_question': 3},
                {'error_types': '计算错误'}, None]:
        try:
            scan_model.clean_edit(bad)
        except scan_model.ScanError:
            continue
        raise AssertionError(bad)

def test_question_payload():
    page = {'subject_id': 1, 'grade': 6, 'semester': 1, 'image': '2026/11/aaaaaaaa_p.jpg'}
    item = {**scan_model.blank_item(0), 'question_no': '3', 'parsed_question': '题', 'answer': '1', 'analysis': '析',
            'wrong_answer': '2', 'knowledge_point_ids': [101], 'primary_knowledge_point_id': 101,
            'error_types': ['计算错误', '概念错误'], 'difficulty': 4}
    assert scan_model.question_payload(page, item) == {
        'subject_id': 1, 'grade': 6, 'semester': 1, 'question_no': '3', 'parsed_question': '题', 'answer': '1',
        'analysis': '析', 'wrong_answer': '2', 'difficulty': 4, 'error_type': '计算错误,概念错误',
        'knowledge_point_ids': [101], 'primary_knowledge_point_id': 101,
        'original_image': '2026/11/aaaaaaaa_p.jpg', 'original_images': ['2026/11/aaaaaaaa_p.jpg'],
        'wrong_evidence': '页面识别，家长确认'}

def test_changes_library():
    assert scan_model.changes_library('POST', '/api/scan/pages/3/items/2/accept') is True
    assert scan_model.changes_library('POST', '/api/scan/pages/3/accept-all') is True
    assert scan_model.changes_library('POST', '/api/scan/pages/3/items/2/withdraw') is True
    for path in ['/api/scan/pages', '/api/scan/pages/3/advance', '/api/scan/pages/3/items/2/dismiss',
                 '/api/scan/pages/3/items/2/restore', '/api/scan/pages/3/items/2/promote',
                 '/api/scan/pages/3/items', '/api/scan/pages/3/close']:
        assert scan_model.changes_library('POST', path) is False
    assert scan_model.changes_library('PUT', '/api/scan/pages/3/items/2') is False
```

另加一条：`build_page_prompt` 的结果里含考点编号、错因名、OCR 文字，`enhanced_text` 给了时也含它；含"不许猜孩子写了什么""0.5 和 1/2 不算错""没有作答按做错"这几条规则的字样。

- [ ] **Step 2: 运行确认失败。**

- [ ] **Step 3: 实现。** 清洗规则：文本字段非字符串 → 置空并把这道题标 `unsure`、`reason` 写"模型返回的内容不完整，请对照原图"；`verdict` 不认识 → `unsure`；考点去掉非整数（含 bool）和不在清单的，去重保序；主考点不在剩下的考点里时，剩一个就用它，否则 `None`；判断为 `right` 的题清空答案、解析、考点、错因，难度置 3。`interpret_ocr` 的 `user_text`：版本不对是"识别服务版本不一致"，其余失败是"读图没成功"。`next_step` 里 `step_started_at` 是整数秒，非空且未超过 `STALE_SECONDS` 时返回 `'working'`。

- [ ] **Step 4: 运行确认通过。**

- [ ] **Step 5: 提交** — `git commit -m "feat(scan): pure rules for page scan"`

---

### Task 3: 迁移 `0014` 与识别分步推进

**Files:**
- Create: `cloudflare/migrations/0014_scan_page.sql`
- Modify: `cloudflare/src/scan.py`, `cloudflare/scripts/scan_test.py`

**Interfaces:**
- Consumes: Task 1 的 `ocr_client.*`；Task 2 的 `next_step`、`interpret_ocr`、`build_page_prompt`、`clean_items`、`needs_rescan`；`intake.load_catalog`、`intake.load_error_type_names`、`intake_model.IMAGE_KEY_PATTERN`、`question_scope.current_student_id`、`settings.generate_json`
- Produces:
  - 表 `scan_page`：`id INTEGER PRIMARY KEY`、`student_id INTEGER NOT NULL DEFAULT 1`、`subject_id INTEGER NOT NULL`、`grade INTEGER`、`semester INTEGER`、`image TEXT NOT NULL`、`status TEXT NOT NULL DEFAULT 'uploaded'`、`step_started_at INTEGER`（整数秒）、`ocr_text TEXT`、`ocr_text_enhanced TEXT`、`rescan_used INTEGER NOT NULL DEFAULT 0`、`items TEXT NOT NULL DEFAULT '[]'`、`error TEXT`、`timings TEXT NOT NULL DEFAULT '{}'`、`deleted INTEGER NOT NULL DEFAULT 0`、`created_at TEXT`、`updated_at TEXT`；索引 `CREATE INDEX IF NOT EXISTS cf_scan_page_student_status ON scan_page(student_id,status) WHERE deleted=0`
  - 模块级可替换项：`scan.now_seconds() -> int`、`scan.sleep`（默认 `asyncio.sleep`）、`scan.ocr_client`、`scan.generate_json`（`from settings import generate_json` 后的名字）
  - `scan.page_view(row) -> dict`：`id, subject_id, grade, semester, image, status, error, rescan_used, items(列表), timings(字典), created_at`，不含 OCR 文字
  - 接口：
    - `POST /api/scan/pages`（201）入参 `{image, subject_id, grade, semester}` → `page_view`
    - `GET /api/scan/pages/unfinished` → `{'items': [page_view...]}`，当前学生、状态不是 `closed` / `failed`、最近 5 条（**路由写在 `/{page_id}` 之前**）
    - `GET /api/scan/pages/{page_id}` → `page_view`
    - `POST /api/scan/pages/{page_id}/advance` → `{'busy': bool, 'page': page_view}`
    - `POST /api/scan/pages/{page_id}/close` → `page_view`

推进一步的写法：先 `next_step`；`None` 直接返回当前页；`'working'` 返回 `busy: True`。否则用条件更新认领：`UPDATE scan_page SET status=?, step_started_at=?, updated_at=? WHERE id=? AND deleted=0 AND status=? AND (step_started_at IS NULL OR step_started_at<?) RETURNING id`，没认领到就返回 `busy: True`。各步认领后的状态和结束后的状态：

| 步骤 | 认领时 status | 成功后 | 失败后 |
| --- | --- | --- | --- |
| read（`ocr_client.read_image` + `fetch_ocr(normal)`，忙时重试） | `reading` | `analyzing`，存 `ocr_text` | `failed`，`error` 为 `user_text` 或"照片找不到了" |
| analyze（`generate_json` 一次） | `analyzing` | 存 `items`；`needs_rescan` 为真时 `rescanning`，否则 `ready` | `failed`，`error` 为 `HTTPException.detail`，`ocr_text` 保留 |
| rescan（`fetch_ocr(enhanced)`，认领时同时 `rescan_used=1`） | `rescanning` | `analyzing`，存 `ocr_text_enhanced` | `ready`（保留第一次的 `items`） |

每步写 `step_started_at=NULL`，用时记进 `timings`（键 `read_ms`、`analyze_ms`、`rescan_ms`、`analyze2_ms`、`host_read_ms`、`host_rescan_ms`、`host_detail`）。重扫开关：`str(getattr(env, 'SCAN_RESCAN', '')).lower() != 'off'`。

- [ ] **Step 1: 写失败的测试。** 建库：生产结构基线 + `0011` + `0012` + `0014`，种子照 `intake_test.build_legacy_database`。假主机和假模型都是记录调用次数的对象。

```python
def test_migration_0014_only_adds_scan_page():
    # 基线 + 0011~0013 后记下 sqlite_master 的 (type,name,sql)，执行 0014 后旧的每一行都不变，新增的只有 scan_page 表和 cf_scan_page_student_status 索引
def test_create_page_validates_image_and_subject():
    # 图片路径 '../x.jpg'、'2026/11/zz_p.jpg' → 422；学科 99 → 400；年级 13 → 422；合格的 → 201、status 'uploaded'、student_id 1
def test_advance_happy_path_without_rescan():
    # 假主机返回一页文字，假模型返回 2 道错 1 道对、都没 flags
    # 连推三次：第一次后 'analyzing'，第二次后 'ready'，第三次 busy False 且不再调主机和模型
    # items 3 项、timings 有 read_ms 和 analyze_ms；主机 normal 调用 1 次、模型 1 次
def test_advance_with_rescan_runs_once():
    # 假模型第一次返回带 merged 的题；推到 ready 共四步：reading→analyzing→rescanning→analyzing→ready
    # 主机 enhanced 调 1 次；第二次模型调用的提示词里含重扫文字；第二次仍返回 merged 也不再重扫；rescan_used == 1
def test_rescan_switch_off():
    # env.SCAN_RESCAN='off' 时带 flags 也直接 ready，主机 enhanced 0 次
def test_rescan_failure_keeps_first_result():
    # 重扫返回 502 → status 'ready'，items 是第一次的
def test_busy_host_retries_then_fails():
    # 主机一直 503 busy → sleep 被调 3 次、主机共 4 次，status 'failed'，error '读图没成功'
    # 主机前两次 503、第三次成功 → 'analyzing'
def test_host_garbage_and_contract_mismatch():
    # (200, None) → failed '读图没成功'；contract 2 → failed '识别服务版本不一致'；host_detail 记进 timings、不在 error 里
def test_model_failure_retry_does_not_reread():
    # 模型抛 HTTPException(502,'模型没有返回有效的结构化内容') → failed，error 为这句；ocr_text 保留
    # 再推一次（模型恢复）→ ready，主机总共只调 1 次
def test_read_failure_retry_rereads():
    # 第一次主机失败 → failed；再推 → 重新读图，主机共 2 次
def test_missing_image_fails_cleanly():
    # read_image 返回 None → failed '照片找不到了'
def test_concurrent_advance_only_one_runs():
    # 页面停在 status 'reading'、step_started_at=now-10 → busy True，主机 0 次
    # 改成 now-151 → 重新认领并读图
    # 直接对条件更新做竞争：两个协程 asyncio.gather 推同一页，假主机里 await 一次让出 → 主机只调 1 次，另一个 busy True
def test_unfinished_and_close():
    # 建 7 页，其中 1 页 closed、1 页 failed、1 页 deleted → unfinished 返回最近 5 条且不含这三页
    # close 后 status 'closed'；关闭的页推进 → busy False 不调用任何东西
def test_unknown_page_is_404():
    # 不存在、已软删除的 page_id 查、推进、关闭都是 404
```

- [ ] **Step 2: 运行确认失败。**

- [ ] **Step 3: 写迁移，实现以上接口。** 模型的提示词用 `load_catalog(db, subject_id, grade, semester)` 和 `sorted(load_error_type_names(...))`；考点编号集合取 `catalog` 里所有 `points` 的 `id`。读图失败时把 `interpret_ocr` 的 `detail` 存进 `timings.host_detail`。

- [ ] **Step 4: 运行确认通过**，并跑 `python cloudflare/scripts/intake_test.py` 确认第一条路没受影响。

- [ ] **Step 5: 提交** — `git commit -m "feat(scan): scan_page table and step-by-step recognition"`

---

### Task 4: 逐题操作与录入

**Files:**
- Modify: `cloudflare/src/scan.py`, `cloudflare/src/questions.py`（`FIELDS` 加 `'wrong_evidence'`）, `cloudflare/scripts/scan_test.py`

**Interfaces:**
- Consumes: Task 2 的 `clean_edit`、`blank_item`、`build_fill_prompt`、`clean_fill`、`accept_all_seqs`、`question_payload`；`questions.save(db, payload, request=request)`
- Produces（`{seq}` 是题目下标；页面不是 `ready` 时一律 409"这一页已经结束了，请刷新"；`seq` 越界 404）：
  - `PUT /api/scan/pages/{page_id}/items/{seq}` 保存修改：`clean_edit` 后写回，`edited=True`；只允许 `open` 的题 → `page_view`
  - `POST .../items` 手工加一道：`blank_item`（`source='manual'`、`verdict='wrong'`）追加到末尾 → `page_view`
  - `POST .../items/{seq}/dismiss`、`/restore`：`open` ↔ `dismissed` → `page_view`
  - `POST .../items/{seq}/promote`：只对 `verdict='right'` 且 `open` 的题；先写 `source='promoted'`、`verdict='wrong'`、`reason='家长补成错题'`，再调一次模型补字段；模型失败不回滚移动 → `{'page': page_view, 'fill_error': str | None}`
  - `POST .../items/{seq}/accept` → `page_view`
  - `POST /api/scan/pages/{page_id}/accept-all` → `{'results': [{'seq', 'ok', 'detail'}], 'page': page_view}`
  - `POST .../items/{seq}/withdraw` → `page_view`

单项写回一律用 `json_set(items, '$[' || ? || ']', json(?))`，并在 `WHERE` 里用 `json_extract(items, '$[' || ? || '].state')=?` 加条件，避免两个请求互相覆盖别的题。

录入的写法：项已是 `accepted` 且有 `question_id` 时直接返回（不重复写）；`dismissed` 返回 409。否则 `questions.save` 写入，再条件更新 `open → accepted` 并存 `question_id`；条件更新没成功（别的请求抢先录了）时，把刚写的错题软删除，返回当前页。`save` 抛出的 `HTTPException` 原样抛给前端（前端据此切到修改状态）。全部录入对 `accept_all_seqs` 逐道调同一个录入函数，每道独立成败。撤回：只对 `accepted` 的题，软删除对应错题，这一项回到 `open`、`question_id=None`。

- [ ] **Step 1: 写失败的测试**（数学题的公式校验在测试里换成什么都不做，另一条换成抛 422）

```python
def test_accept_writes_approved_question_with_page_fields():
    # 准备一页 ready 的草稿（数学、6 年级上、image 'yyyy/mm/xxxxxxxx_p.jpg'），录入 seq 0
    # question 行：review_status 'approved'、paper_id IS NULL、student_id 1、original_image 和 original_images 是这页图片、
    # wrong_evidence '页面识别，家长确认'、wrong_answer、question_no、error_type、difficulty 与草稿一致；主考点关联存在
    # 草稿 seq 0 → state 'accepted'、question_id 为新题编号
def test_accept_twice_writes_once():
    # 同一道连续录入两次 → 题库多 1 道，两次返回的 question_id 相同
def test_accept_race_keeps_one_question():
    # 两个录入用 asyncio.gather 同时跑（save 里让出一次）→ 未删除的新题只有 1 道，草稿 question_id 指向它
def test_accept_rejected_by_save_keeps_item_open():
    # 公式校验抛 422 → 接口抛 422、题库无新题、草稿仍 open
    # 选了考点没主考点（草稿 knowledge_point_ids [101,102]、primary None）→ 422
def test_accept_all_skips_warning_and_unsure():
    # 草稿：wrong 无标记、wrong 有标记未改、wrong 有标记已改、unsure、right、dismissed
    # results 只含第 1、3 道且都 ok；其余草稿状态不变
def test_accept_all_partial_failure():
    # 两道候选，第二道 save 抛 422 → results 第一道 ok、第二道 detail 有说明；第一道仍已入库
def test_withdraw_soft_deletes():
    # 录入后撤回 → 题目 deleted=1、草稿回到 open、question_id None；再次录入得到新的一道
def test_edit_dismiss_restore_manual():
    # 保存修改后 edited True、字段已变；坏字段 422；accepted 的题不能改 → 409
    # dismiss 后 state 'dismissed'，录入 → 409；restore 后回 open
    # 手工加一道 → items 末尾多一项，seq 等于下标、source 'manual'
def test_promote_fills_from_model_and_survives_model_failure():
    # 模型返回补充字段 → 那道 verdict 'wrong'、source 'promoted'、answer 有值、考点经过清洗
    # 模型抛 502 → fill_error 有说明，那道仍是 promoted、字段为空；模型只调 1 次
    # 对 wrong 的题 promote → 409
def test_closed_page_rejects_item_operations():
    # 页 closed 后 保存修改 / 录入 / 撤回 / 去掉 / 补成错题 / 全部录入 都是 409，题库不变
def test_close_leaves_open_items_out_of_library():
    # 一道录入、一道没处理，close → 题库只多 1 道
```

- [ ] **Step 2: 运行确认失败。**

- [ ] **Step 3: 实现。** `questions.FIELDS` 加 `'wrong_evidence'`，其余 `questions.py` 不动。

- [ ] **Step 4: 运行确认通过**，并跑 `intake_test.py`、`knowledge_invariants_test.py`、`starmap_test.py`。

- [ ] **Step 5: 提交** — `git commit -m "feat(scan): per-question accept, edit, dismiss, promote, withdraw"`

---

### Task 5: 接线与本机测试服务

**Files:**
- Modify: `cloudflare/src/auth.py`, `cloudflare/wrangler.jsonc`, `cloudflare/scripts/local_dev_server.py`, `cloudflare/scripts/local_dev_server_test.py`

**Interfaces:**
- Consumes: `scan_model.changes_library`、`scan.router`、`scan.ocr_client`、`scan.generate_json`
- Produces:
  - `auth.guard`：路径以 `/api/scan/` 开头且 `changes_library` 为假时不调用 `invalidate`
  - `wrangler.jsonc` 加 `"vars": {"SCAN_RESCAN": "on"}`
  - `local_dev_server`：执行 `0014`；`ROUTER_MODULES` 在 `'questions'` 之前加 `'scan'`；`build_app(connection, uploads_dir, frontend_dir, ocr_url=None, ocr_key=None, llm_config=None)`；命令行加 `--ocr-url`、`--ocr-key-file`、`--llm-config`
  - `local_dev_server.FakeOcr`：`/health` 可用，`/ocr` 返回固定的一页数学题文字（含一处"5/131"）；`local_dev_server.fake_generate_json(request, prompt)`：整页提示词返回 3 道题（1 道 wrong、1 道 wrong 带 `broken_formula`、1 道 right），补题提示词返回补充字段
  - `local_dev_server.HttpOcr(url, key)`：用 `urllib.request` 直接调主机的 `/health` 和 `/ocr`，返回和 `ocr_client` 一样的 `(状态码, JSON)`
  - `local_dev_server.make_http_generate_json(config: dict)`：照 `settings.generate_json` 的请求格式用 `urllib.request` 调模型，返回同样的结果或抛同样的 `HTTPException`
  - 本机的 `read_image` 从上传目录读文件

- [ ] **Step 1: 写失败的测试**（`local_dev_server_test.py`，用 FastAPI `TestClient`）

```python
def test_scan_flow_with_fakes():
    # 上传一张图 → 新建一页 → 推进直到 ready（不超过 6 次）→ 主列表 2 道
    # 录入第 1 道 → GET /api/questions 能看到它；全部录入不再重复；close 成功
def test_scan_health_with_fake():
    # GET /api/scan/health → {'available': True}
```

`auth.py` 的改动另在 `scan_test.py` 加一条：把 `auth.invalidate` 换成计数函数，用假请求跑 `guard`，`/api/scan/pages/1/advance` 不计数、`/api/scan/pages/1/items/0/accept` 计数一次。

- [ ] **Step 2: 运行确认失败。**
- [ ] **Step 3: 实现。**
- [ ] **Step 4: 运行确认通过**：`python cloudflare/scripts/local_dev_server_test.py`、`python cloudflare/scripts/scan_test.py`。
- [ ] **Step 5: 提交** — `git commit -m "feat(scan): wire routes, cache rule, local dev fakes"`

---

### Task 6: 前端纯逻辑与接口

**Files:**
- Create: `frontend/src/api/scan.js`, `frontend/src/composables/scanPage.js`, `frontend/src/composables/scanPage.test.mjs`

**Interfaces:**
- Consumes: Task 3、4 的接口路径和 `page_view` 结构
- Produces:
  - `scanApi`：`health()`（超时 5000）、`create(data)`、`get(id)`、`unfinished()`、`advance(id)`（超时 180000）、`close(id)`、`addItem(id)`、`saveItem(id, seq, data)`、`dismiss(id, seq)`、`restore(id, seq)`、`promote(id, seq)`（超时 150000）、`accept(id, seq)`、`acceptAll(id)`（超时 120000）、`withdraw(id, seq)`；写法照 `api/question.js`
  - `scanPage.js`：
    - `FLAG_TEXTS`（设计 6.4 第三列原文）、`warningTexts(item) -> string[]`
    - `stepLabel(status) -> string`：`uploaded` / `reading` →"正在读图"，`analyzing` →"正在整理题目"，`rescanning` →"正在重扫一次"，其他 `''`
    - `hasWarning(item) -> boolean`、`acceptAllSeqs(items) -> number[]`（和后端同规则）
    - `groupItems(items) -> {main, right}`：`main` = 非 `dismissed`，且（`verdict !== 'right'` 或 `source !== 'model'`），按 `seq`；`right` = `verdict === 'right'`、`source === 'model'`、`open`
    - `progressCounts(items) -> {accepted, remaining}`：`main` 里 `accepted` 的数和 `open` 的数
    - `unsureHint(item) -> string`：`unsure` 时"模型拿不准：" + `reason`，`reason` 空时"没看清孩子的答案，请对照原图判断"
    - `MAX_UPLOAD_BYTES = 10 * 1024 * 1024`、`needsCompression(size) -> boolean`、`scaledSize(width, height, maxSide) -> {width, height}`（长边不超过 `maxSide`、等比、取整）

- [ ] **Step 1: 写失败的测试**

```js
test('分组', () => {
  const items = [
    { seq: 0, verdict: 'wrong', source: 'model', state: 'open' },
    { seq: 1, verdict: 'right', source: 'model', state: 'open' },
    { seq: 2, verdict: 'unsure', source: 'model', state: 'dismissed' },
    { seq: 3, verdict: 'wrong', source: 'promoted', state: 'accepted' },
    { seq: 4, verdict: 'wrong', source: 'manual', state: 'open' },
  ]
  const { main, right } = groupItems(items)
  assert.deepEqual(main.map(i => i.seq), [0, 3, 4])
  assert.deepEqual(right.map(i => i.seq), [1])
  assert.deepEqual(progressCounts(items), { accepted: 1, remaining: 2 })
})
test('全部录入只含无提示的做错题', () => { /* 同后端 test_accept_all_and_warning 的七项，结果 [0, 2] */ })
test('提示文字', () => {
  assert.deepEqual(warningTexts({ flags: ['broken_formula'] }), ['公式可能读错，请对照原图'])
  assert.equal(stepLabel('rescanning'), '正在重扫一次')
  assert.equal(unsureHint({ verdict: 'unsure', reason: '' }), '没看清孩子的答案，请对照原图判断')
})
test('压缩', () => {
  assert.equal(needsCompression(10 * 1024 * 1024), false)
  assert.equal(needsCompression(10 * 1024 * 1024 + 1), true)
  assert.deepEqual(scaledSize(6000, 4000, 3000), { width: 3000, height: 2000 })
  assert.deepEqual(scaledSize(1000, 800, 3000), { width: 1000, height: 800 })
})
```

- [ ] **Step 2: 运行确认失败** — `node --test frontend/src/composables/scanPage.test.mjs`
- [ ] **Step 3: 实现。**
- [ ] **Step 4: 运行确认通过。**
- [ ] **Step 5: 提交** — `git commit -m "feat(scan): frontend api and pure helpers"`

---

### Task 7: 录入页四态与手工表单抽出

**Files:**
- Create: `frontend/src/components/ManualQuestionForm.vue`
- Modify: `frontend/src/views/Upload.vue`

**Interfaces:**
- Consumes: Task 6 的 `scanApi`、`stepLabel`、`needsCompression`、`scaledSize`；`uploadApi.uploadFile`
- Produces:
  - `ManualQuestionForm.vue`：现在 `Upload.vue` 卡片里的全部内容和逻辑原样搬入，行为不变；新增 props `presetImages: string[]`（已上传的路径，进入时放进已上传预览）、`subjectId`、`grade`、`semester`（有值时作初值）
  - `Upload.vue`：`mode` 为 `pick` / `scanning` / `sorting` / `manual`；`sorting` 时渲染 Task 8 的 `ScanWorkspace`（本任务先放一个占位，Task 8 替换）

各态行为照设计 8.2、8.7、9.5：
- `pick`：学科、年级、学期（沿用 `localStorage` 的 `lastSubjectId` / `lastGrade` / `lastSemester` 和默认学段）；选一张图或拍照（`accept="image/*"`，`capture` 不强制）；"不识别，直接手工录一道"入口。进入时 `scanApi.health()`，失败或 `available: false` 顶部显示"识别暂时用不了，可以先手工录"，此时传图后直接进 `manual` 并带上这张图。进入时 `scanApi.unfinished()`，有记录时顶部显示"上次有一张图没整理完"，"继续"/"不要了"（后者调 `close`）。
- 传图：超过 10MB 时用 canvas 按 `scaledSize(…, 3000)` 缩到 JPEG（质量 0.85，还超就降到 0.7、长边 2400）；只在超限时压缩。上传后 `scanApi.create` → `scanning`。
- `scanning`：原图先显示，旁边显示 `stepLabel`；循环调 `advance`，`busy` 时等 3 秒后 `get`；`ready` → `sorting`；`failed` 显示 `error` 和"再试一次"（再调 `advance`）、"改为手工录"。"取消，改为手工录"：停止循环、`close`、进 `manual` 带上这张图。
- `manual`：`ManualQuestionForm` 带上图片和学科年级学期。
- 整页一道题都没识别出来（`ready` 但 `items` 为空）：提示"没有识别出题目"，可以手工加一道或换一张。

- [ ] **Step 1: 搬出 `ManualQuestionForm.vue`，`Upload.vue` 暂时只渲染它；`npm run build --prefix frontend` 通过；本机测试服务里手工录一道题，确认和改之前一样能保存。**
- [ ] **Step 2: 提交** — `git commit -m "refactor(upload): extract manual question form"`
- [ ] **Step 3: 实现四态。**
- [ ] **Step 4: 验证**：`npm run build --prefix frontend`；用 `python cloudflare/scripts/local_dev_server.py` + 前端构建，在浏览器里走：可用时传图 → 识别中 → 进入整理占位；用 `--ocr-url http://127.0.0.1:1`（连不上）启动，确认顶部提示并直接进手工表单；识别中关掉页面再打开，确认"上次有一张图没整理完"能继续。
- [ ] **Step 5: 提交** — `git commit -m "feat(upload): pick, scanning and manual states"`

---

### Task 8: 整理区

**Files:**
- Create: `frontend/src/components/scan/ScanImagePane.vue`, `frontend/src/components/scan/ScanItemCard.vue`, `frontend/src/components/scan/ScanWorkspace.vue`
- Modify: `frontend/src/views/Upload.vue`（换掉占位）

**Interfaces:**
- Consumes: Task 6 的全部 `scanApi` 和 `scanPage.js`；`MathText`、`MathEditor`、`KnowledgePointPicker`（`v-model`、`v-model:primary-id`、`subject-id`）、`PageHeading`
- Produces:
  - `ScanImagePane`：props `src`；电脑端 `position: sticky` 固定，滚轮放大（1–4 倍）、按住拖动、双击复位；手机端可收起，点开用 `el-image` 预览放大
  - `ScanItemCard`：props `item`、`subjectId`、`errorTypes`（名字列表）；emits `save(fields)`、`accept`、`dismiss`、`withdraw`；内部 `editing` 状态；props `serverError`（录入被拒时的提示，非空时自动进修改状态并显示在卡片顶部）
  - `ScanWorkspace`：props `page`、`subjectName`；emits `update(page)`、`next`

照设计 8.3–8.6 的排法和文字：
- 顶部一行"识别出 N 道题，模型判断 M 道做错"。电脑端（>768px）左原图右列表；手机端原图在上、底部固定"全部录入 / 下一张"条。
- 卡片只读：题号、题干、孩子的答案、正确答案、考点、错因（公式用 `MathText`），带读图提示用黄色 `el-alert` 写 `warningTexts`，拿不准写 `unsureHint`，判断理由小字显示。右下三个 small 按钮：文字按钮"不是错题"、普通"修改"、主色"录入"。
- 修改态：题号、题干、孩子的答案、正确答案、解析、考点、错因、难度，底部"取消""保存"；保存调 `saveItem`，回只读，不自动录入。
- `hasWarning` 的题第一次点"录入"先 `ElMessageBox.confirm('这道题可能读错了，对照过原图了吗？')`。
- 录入成功的卡片收成一行"第 N 题 已录入"带"撤回"。
- "不是错题"不二次确认，`ElNotification` 带"撤销"按钮约 5 秒，点了调 `restore`。
- 折叠区"模型认为做对的 N 道"默认收起（主列表为空时自动展开并显示"模型没发现做错的题"），每行题号和题干开头、"补成错题"按钮；`fill_error` 非空时提示"没补上答案和解析，可以点修改自己填"。
- "＋ 手工加一道"调 `addItem`，新卡片直接进修改态。
- 底部"已录入 X 道，还剩 Y 道"、"全部录入（K）"（K 为 `acceptAllSeqs` 长度，0 时禁用）、"下一张"；还有 `open` 的题时先问"还有 Y 道没处理，不要了吗？"，确认后 `close` 并回 `pick`，学科年级学期保留。
- 所有接口失败都用 `ElMessage.error(后端 detail)`，409 时提示刷新并重新 `get` 这一页。

- [ ] **Step 1: 实现三个组件，接进 `Upload.vue`。**
- [ ] **Step 2: 验证**：`node --test frontend/src/composables/scanPage.test.mjs`、`npm run build --prefix frontend`；本机测试服务里在浏览器走一遍：录入、修改后录入、带提示的题弹确认、不是错题和撤销、展开判对的补成错题、手工加一道、全部录入、撤回、下一张的确认。再用浏览器把视口切到手机宽度（375）走一遍，确认原图可收起、底部条固定、没有横向滚动。截图留在暂存目录，不进仓库。
- [ ] **Step 3: 提交** — `git commit -m "feat(upload): sorting workspace for scanned page"`

---

### Task 9: 回归脚本

**Files:**
- Create: `cloudflare/scripts/scan_regression.py`
- Modify: `cloudflare/scripts/scan_test.py`（加一条用假主机假模型跑脚本的测试）

**Interfaces:**
- Consumes: Task 5 的 `build_app(..., ocr_url, ocr_key, llm_config)`、`HttpOcr`、`make_http_generate_json`
- Produces: `python cloudflare/scripts/scan_regression.py --images <目录> --ocr-url http://127.0.0.1:11436 --ocr-key-file <文件> --llm-config <文件> [--out <目录>] [--subject 数学 --grade 6 --semester 1]`
  - 用 `TestClient` 在进程内起本机服务（临时内存库），对目录里每张 `.jpg/.jpeg/.png/.webp` 按文件名顺序：上传、新建一页、推进到 `ready` 或 `failed`
  - `--out` 默认 `%USERPROFILE%\.easyfix\scan-regression\<日期时间>\`；每张图存 `<图名>.json`（完整 `page_view` 加 `ocr_text`、`ocr_text_enhanced`），另存 `summary.csv`：图名、状态、题数、做错数、拿不准数、带提示数、是否重扫、各步用时、总用时；最后打印用时中位数和最大值
  - 口令和模型密钥只从给定文件读，不打印
  - `--images` 指向仓库目录内时拒绝运行并说明（防止结果进仓库）

- [ ] **Step 1: 写失败的测试**：用 `FakeOcr` 和 `fake_generate_json` 跑两张小图到临时目录，`summary.csv` 两行、每张一个 JSON、状态都是 `ready`。
- [ ] **Step 2: 运行确认失败。**
- [ ] **Step 3: 实现。** 脚本头部写清楚怎么在主机上跑、结果怎么对照交接文档的 61 道目标题人工评分（数哪几项见设计 12.2 第 1 条）。
- [ ] **Step 4: 运行确认通过。**
- [ ] **Step 5: 提交** — `git commit -m "feat(scan): regression runner for the OCR host"`

---

### Task 10: 全量自测与代码审查

- [ ] **Step 1: 跑全部测试**，全部通过才往下：

```bash
python -m compileall -q cloudflare/src
python cloudflare/scripts/scan_test.py
python cloudflare/scripts/intake_test.py
python cloudflare/scripts/knowledge_invariants_test.py
python cloudflare/scripts/knowledge_api_test.py
python cloudflare/scripts/starmap_test.py
python cloudflare/scripts/phrase_focus_test.py
python cloudflare/scripts/local_dev_server_test.py
node --test frontend/src/composables/
npm run build --prefix frontend
```

- [ ] **Step 2: 对照设计第 2 节"要避免的结果"和本计划 Review Focus 逐条自查**，并 `git diff main -- cloudflare/src/intake.py cloudflare/src/intake_model.py cloudflare/src/papers.py tools/` 确认为空。
- [ ] **Step 3: 整个分支做一次代码审查**（`superpowers:requesting-code-review`），修完再提交。

---

### Task 11: 发布（每一步先问用户）

前提：Task 1 的连通性试验已通过；主机端已回传强化重扫的回归结果（或用户决定先关掉重扫，`SCAN_RESCAN` 设为 `off`）。

- [ ] **Step 1: 导出正式库备份**，在备份副本上演练 `0014`（做法照 `docs/cloudflare-migration-status.md`"备份与恢复"），确认旧表不变。
- [ ] **Step 2: 正式库执行 `0014`**：`node cloudflare/tools/cli.cjs d1 migrations apply easyfix --remote --config cloudflare/wrangler.jsonc`（以状态文档里的写法为准）。
- [ ] **Step 3: 确认 `OCR_SHARED_KEY` 已由用户填好；部署后端**，`/api/scan/health` 返回可用。
- [ ] **Step 4: 构建并发布前端**：`python backend/scripts/prepare_cloudflare_frontend.py`，再按状态文档发布 Pages。
- [ ] **Step 5: 实测验收**（设计 12.2）：用户在主机上跑 `scan_regression.py` 并人工评分；手机、电脑各走一遍；关掉主机识别服务确认提示和手工录；用 Claude 录一份卷子确认第一条路正常。
- [ ] **Step 6: 记录**：结果写进 `docs/cloudflare-migration-status.md`；更新 `ocr-ollama-handoff.md` 里过期的"对接边界"一节；`CLAUDE.md` 模块表加 `scan.py`、`scan_model.py`、`ocr_client.py`。提交。
