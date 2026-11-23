# 多家庭账号 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal：** 把共享访问密码换成"账号 + 密码"登录，让少量熟人家庭各自登录，每家只看得到自己孩子的数据。

**Architecture：** 跟密码有关的事全放在 Pages 网关（JS + WebCrypto）：登录、验密码、改密码、管理员重置密码。会话 Cookie 带上用户、学生、会话版本，并做签名。网关和后端每次请求都要先验签名，再查一次 D1 确认身份；后端把身份放进 `request.scope['easyfix']`，`current_student_id()` 从这里读。所有学生数据的查询都带上 `student_id`，由一个扫描源码的测试盯住。附件靠路径前缀 `u<用户编号>/` 判断归属。

**Tech Stack：** Python Worker（FastAPI + D1）、Pages 网关（`_worker.js`）、R2、Vue 3 + Element Plus + Pinia，测试用 `python cloudflare/scripts/*_test.py` 和 `node --test`。

**Spec：** `docs/superpowers/specs/2026-11-23-multi-family-accounts-design.md`（实施者先读完它）

## Global Constraints

- 迁移只追加，唯一例外：0018 里重建 `tag`、`achievement_progress` 两张表（spec 第 6 节）。
- 所有表保留 `deleted`，只做软删除，查询必须过滤已删除记录。
- 保持 Workers 免费计划：Python 后端不算 PBKDF2；每个 API 请求只多一次身份查询。
- 密码只存 `pbkdf2-sha256$迭代次数$盐base64$哈希base64`，任何地方不存、不打印明文；初始密码只在接口返回里出现一次。
- Cookie：`easyfix_session=v2.<过期秒>.<用户编号>.<学生编号>.<会话版本>.<签名hex>`，签名 = HMAC-SHA256(`SESSION_SECRET`, `v2.<过期秒>.<用户编号>.<学生编号>.<会话版本>`)；HttpOnly、Secure、SameSite=Strict、Path=/、Max-Age=2592000（30 天）。旧格式一律当作没登录。
- 别人的数据一律返回 404（`{'detail': '记录不存在'}`），不返回 403。只有"非管理员调管理员接口"返回 403（`{'detail': '只有管理员可以操作'}`）。
- 登录名 `^[a-z0-9_]{3,20}$`；初始密码 12 位随机字符；自己改密码至少 10 位。
- 同一个登录名 15 分钟内输错 5 次，返回 429 `{'detail': '尝试次数太多，请 15 分钟后再试'}`。
- 新上传的图片键：`u<用户编号>/年/月/8位随机_文件名`；练习 PDF：`u<用户编号>/practice_sets/…`；`audio/` 开头的大家都能读；没有 `u` 前缀的旧键只有 1 号用户能读。
- 共用目录（不分学生，只有管理员能写）：`subject`、`knowledge_point` 及其树、`textbook_section`、`textbook_section_point`、`knowledge_link`、`star_action`、`achievement`、模型设置。
- 代码规范照 `CLAUDE.md`：`snake_case`，每个函数写中文文档字符串，前端用 `<script setup>`。
- 部署、执行迁移、改 Cloudflare 密钥前都先问开发者，执行迁移前先导出 D1 备份。

## Review Focus

1. **按编号访问别人的记录**（`GET/PUT/DELETE /api/questions/{id}`、`/api/practice-sets/{id}`、`/api/words/{id}`、`/api/papers/{id}`）：应返回 404，不改数据。由任务 7 和任务 8 的测试 `test_other_student_by_id_is_404` 覆盖。
2. **同一家庭的第二个学生**：建同名标签、累计星星、成就进度时不和第一个学生冲突。由任务 1 的 `test_second_student_same_tag_name` 和任务 8 的 `test_motivation_isolated_per_student` 覆盖。
3. **60 秒缓存期内两个学生先后打开首页**：两人应看到各自的数据。由任务 4 的 `test_cache_key_includes_student` 覆盖。
4. **重置密码、停用账号后，旧 Cookie 的下一次请求**：后端 API、`/uploads/`、图片上传都应返回 401。由任务 3 的 `test_stale_version_rejected` 和任务 4 的 `test_guard_rejects_stale_session` 覆盖。
5. **把别家的图片路径塞进录入、整页识别、批改拍照、复核图片接口**：应拒绝，返回 404 且不写库。由任务 9 的 `test_foreign_image_path_rejected` 覆盖。

---

## 文件结构

| 文件 | 新建/修改 | 职责 |
|------|-----------|------|
| `cloudflare/migrations/0018_accounts.sql` | 新建 | 账号列、重建两张表、换余额索引、复制配置 |
| `cloudflare/scripts/accounts_test.py` | 新建 | 迁移 0018、会话、身份、管理员接口的测试 |
| `cloudflare/pages/password.js` | 新建 | PBKDF2 哈希与校验、随机密码 |
| `cloudflare/pages/session.js` | 新建 | Cookie 签发与解析、身份查询、附件归属（网关用） |
| `cloudflare/pages/auth_routes.js` | 新建 | 网关的 `/login` 和 `/api/auth/*` 密码相关接口 |
| `cloudflare/pages/_worker.js` | 修改 | 接上上面三个模块；上传键加前缀；`/uploads/` 检查归属 |
| `cloudflare/pages/auth.test.mjs` | 新建 | 网关登录、会话、归属的测试 |
| `cloudflare/src/session.py` | 新建 | Cookie 签发与解析（与 `session.js` 同一格式） |
| `cloudflare/src/identity.py` | 新建 | 身份查询、`current_identity`、管理员规则、附件归属 |
| `cloudflare/src/auth.py` | 修改 | `guard` 改用身份；删旧登录；新增 `/api/auth/me`、`/api/auth/switch-student` |
| `cloudflare/src/question_scope.py` | 修改 | `current_student_id` 改为读身份 |
| `cloudflare/src/settings.py` | 修改 | `app`、`starmap` 配置名按学生区分 |
| `cloudflare/src/cache.py` | 修改 | 缓存键带学生；日志写登录名 |
| `cloudflare/src/accounts.py` | 新建 | `/api/admin/*` 家庭与学生管理 |
| `cloudflare/scripts/student_scope_test.py` | 新建 | 扫描 SQL 的防漏测试 |
| 14 个业务模块 + flip/starmap/home/weekly | 修改 | 按学生过滤 |
| `backend/scripts/set_admin_password.py` | 新建 | 本地给 1 号用户设置登录名和密码 |
| `tools/easyfix-intake/easyfix_intake.py` | 修改 | 可选 `student_id` → `X-Easyfix-Student` 头 |
| `frontend/src/stores/account.js`、`frontend/src/api/auth.js`、`frontend/src/App.vue`、`frontend/src/views/Settings.vue`、`frontend/src/components/settings/AccountTab.vue`、`MyAccountTab.vue`、`settingsModel.js` | 新建/修改 | 学生切换、退出、账号标签、按角色显示标签 |

---

### Task 1：迁移 0018

**Files:**
- Create: `cloudflare/migrations/0018_accounts.sql`
- Create: `cloudflare/scripts/accounts_test.py`

**Interfaces:**
- Produces：`app_user` 新列 `username TEXT`、`password_hash TEXT`、`is_admin INTEGER NOT NULL DEFAULT 0`、`session_version INTEGER NOT NULL DEFAULT 1`、`disabled INTEGER NOT NULL DEFAULT 0`、`last_login_at TEXT`、`updated_at TEXT`；唯一索引 `idx_app_user_username ON app_user(username) WHERE deleted=0 AND username IS NOT NULL`；`student.sort_order INTEGER NOT NULL DEFAULT 0`；`tag` 唯一索引 `(student_id, name) WHERE deleted=0`；`achievement_progress` 唯一索引 `(student_id, achievement_id) WHERE deleted=0`；`star_balance` 唯一索引 `(student_id) WHERE deleted=0`；`runtime_config` 新行 `app:1`、`starmap:1`。
- `accounts_test.build_db()`：`weekly_report_test.build_db()` 再执行 0018，后面的任务都用它建库。

- [ ] **Step 1：写失败的测试**（`accounts_test.py`，结构照 `flip_test.py`：`TESTS` 列表 + `main()`）

```python
def test_migration_account_columns():
    c = build_db()
    cols = {r[1] for r in c.execute('PRAGMA table_info(app_user)')}
    assert {'username','password_hash','is_admin','session_version','disabled','last_login_at','updated_at'} <= cols
    assert tuple(c.execute('SELECT is_admin,session_version,disabled FROM app_user WHERE id=1').fetchone()) == (1, 1, 0)
    assert 'sort_order' in {r[1] for r in c.execute('PRAGMA table_info(student)')}

def test_rebuild_keeps_rows_and_ids():
    # 建库到 0017 后先插两条标签、一条成就进度，记下 (id, name, student_id)；执行 0018 后逐行相同
    ...
    assert before_tags == after_tags and before_progress == after_progress

def test_second_student_same_tag_name():
    c = build_db()
    c.execute("INSERT INTO student(id,user_id,name) VALUES(2,1,'二宝')")
    c.execute("INSERT INTO tag(name,student_id,deleted) VALUES('粗心',1,0)")
    c.execute("INSERT INTO tag(name,student_id,deleted) VALUES('粗心',2,0)")   # 不报错
    try:
        c.execute("INSERT INTO tag(name,student_id,deleted) VALUES('粗心',2,0)")
        assert False, '同一学生内应唯一'
    except sqlite3.IntegrityError:
        pass

def test_star_balance_unique_per_student():
    # 学生 1、2 各插一行余额不冲突；学生 2 再插一行被拦住；旧索引 cloudflare_star_balance_user 不存在

def test_config_copied_per_student():
    # 0018 前写 runtime_config('app')={"default_grade":6}、('starmap')={"progress":{"1":3}}；之后 app:1、starmap:1 的 value 与原值相同，原行保留
```

- [ ] **Step 2：运行，确认失败**：`python cloudflare/scripts/accounts_test.py`，预期：失败数等于 5（还没有 0018 文件）。

- [ ] **Step 3：写 `0018_accounts.sql`**。按 spec 第 6 节的 7 步重建表：开头 `PRAGMA defer_foreign_keys = on;`；新表的列定义从 `cloudflare/scripts/d1_schema_before_0011.sql` 复制，再加 0011 的 `student_id`；去掉表级 UNIQUE，保留外键；用显式列名 `INSERT … SELECT`。1 号用户 `UPDATE app_user SET is_admin=1`。配置复制写成 `INSERT INTO runtime_config(name,value,deleted,updated_at) SELECT 'app:1',value,0,updated_at FROM runtime_config WHERE name='app' ON CONFLICT(name) DO NOTHING;`，`starmap` 同理。

- [ ] **Step 4：运行，确认通过**：同一命令，预期 `5 通过，0 失败`。再跑 `python cloudflare/scripts/weekly_report_test.py` 和 `python cloudflare/scripts/flip_test.py`，预期全部通过（这两个测试还没执行 0018，只是确认没被影响）。

- [ ] **Step 5：提交**：`git add cloudflare/migrations/0018_accounts.sql cloudflare/scripts/accounts_test.py`，`git commit -m "feat(accounts): migration 0018 for multi-family accounts"`

---

### Task 2：密码哈希（网关）和初始化小工具（本地）

**Files:**
- Create: `cloudflare/pages/password.js`
- Create: `backend/scripts/set_admin_password.py`
- Create: `cloudflare/pages/auth.test.mjs`

**Interfaces:**
- Produces（`password.js`）：
  - `PBKDF2_ITERATIONS`：常量，先取 100000，Task 11 实测后再调整。
  - `hashPassword(password: string, iterations = PBKDF2_ITERATIONS) -> Promise<string>`
  - `verifyPassword(password: string, stored: string) -> Promise<boolean>`：迭代次数从 `stored` 里读；格式不对返回 false；比较时用常量时间。
  - `randomPassword(length = 12) -> string`：用 `crypto.getRandomValues`，字母表为 `abcdefghjkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789`（去掉了 0 O 1 l I）。
- Produces（`set_admin_password.py`）：`hash_password(password: str, iterations: int, salt: bytes) -> str`，用 `hashlib.pbkdf2_hmac('sha256', …, dklen=32)`，盐 16 字节，标准 base64。`main()` 交互流程：`input` 读登录名，`getpass` 读两遍密码；生成 SQL `UPDATE app_user SET username=?, password_hash=?, session_version=session_version+1, updated_at=? WHERE id=1`，写进 `tmp/cloudflare-config/` 下的临时 SQL 文件；用 `node cloudflare/tools/cli.cjs d1 execute easyfix --remote --file …` 执行，执行完删掉临时文件。只用 `--dry-run` 时打印 SQL，打印时用 `***` 代替哈希。

- [ ] **Step 1：写失败的测试**（`auth.test.mjs`）

```js
test('hashPassword 和 verifyPassword 往返', async () => {
  const stored = await hashPassword('correct horse', 1000);
  assert.match(stored, /^pbkdf2-sha256\$1000\$[A-Za-z0-9+/=]+\$[A-Za-z0-9+/=]+$/);
  assert.equal(await verifyPassword('correct horse', stored), true);
  assert.equal(await verifyPassword('wrong', stored), false);
  assert.equal(await verifyPassword('x', 'garbage'), false);
});
test('Python 工具生成的哈希能被网关验证', async () => {
  // 固定向量：在 Step 3 里用 set_admin_password.hash_password('easyfix-test', 1000, bytes(range(16))) 算出后填进来
  assert.equal(await verifyPassword('easyfix-test', PY_VECTOR), true);
});
test('randomPassword 长度和字符', () => {
  const p = randomPassword();
  assert.equal(p.length, 12);
  assert.match(p, /^[a-km-np-zA-HJ-NP-Z2-9]+$/);
});
```

- [ ] **Step 2：运行，确认失败**：`node --test cloudflare/pages/auth.test.mjs`，预期报错找不到模块 `./password.js`。
- [ ] **Step 3：实现 `password.js` 和 `set_admin_password.py`**，再用 Python 算出 `PY_VECTOR` 填进测试。
- [ ] **Step 4：运行，确认通过**：同一命令，预期 3 项全部通过。
- [ ] **Step 5：提交**：`git commit -m "feat(accounts): PBKDF2 password hashing and admin password tool"`

---

### Task 3：会话 Cookie（网关 + 后端同格式）与身份查询

**Files:**
- Create: `cloudflare/pages/session.js`、`cloudflare/src/session.py`、`cloudflare/src/identity.py`
- Modify: `cloudflare/pages/auth.test.mjs`、`cloudflare/scripts/accounts_test.py`

**Interfaces:**
- Produces（`session.py`）：
  - `SESSION_SECONDS = 2592000`
  - `sign_session(secret: str, expires: int, user_id: int, student_id: int, version: int) -> str`：返回 Cookie 值（不带 `easyfix_session=`）。
  - `parse_session(secret: str, token: str, now: float) -> dict | None`：返回 `{'expires','user_id','student_id','version'}`；签名错、过期、格式不是 v2、secret 为空，都返回 None。
- Produces（`session.js`）：`signSession(secret, {expires, userId, studentId, version}) -> Promise<string>`；`parseSession(secret, token, nowSeconds) -> Promise<{expires,userId,studentId,version}|null>`；`readSessionCookie(request) -> string`；`sessionCookieHeader(value, maxAge = 2592000) -> string`；`IDENTITY_SQL`；`loadIdentity(env, parsed) -> Promise<{userId,username,isAdmin,studentId,version}|null>`；`ownsUpload(userId, key) -> boolean`。
- Produces（`identity.py`）：
  - `IDENTITY_SQL`：内容与 `session.js` 完全相同。`SELECT u.id AS user_id, u.username, u.is_admin, u.session_version AS version, s.id AS student_id FROM app_user u JOIN student s ON s.user_id=u.id AND s.deleted=0 WHERE u.id=? AND u.deleted=0 AND u.disabled=0 AND u.session_version=? AND s.id=?`
  - `async load_identity(db, parsed: dict) -> dict | None`：返回 `{'user_id','username','is_admin': bool,'version','student_id'}`。
  - `async agent_identity(db, student_header: str | None) -> dict | None`：Bearer 口令对应 1 号用户；带了学生编号就校验它属于 1 号用户，没带就取 `ORDER BY sort_order, id` 的第一个学生。
  - `current_identity(request) -> dict`：读 `request.scope['easyfix']`，没有就抛 `RuntimeError('缺少登录身份')`。宁可报错，也不默认成 1 号学生。
  - `require_admin(request) -> None`：不是管理员就抛 `HTTPException(403, '只有管理员可以操作')`。
  - `admin_only(method: str, path: str) -> bool`：纯函数。管理员专用的有：`/api/admin/` 开头的全部请求；`/api/config/llm` 的 GET 和 POST；对 `/api/subjects`、`/api/knowledge-points`、`/api/stars/actions`、`/api/achievements`（含 `/{id}`）的 POST、PUT、DELETE。实施时对照 `docs/cloudflare-api-checklist.md` 核对一遍，有遗漏的共用目录写接口补进来，并在测试里加一条。
  - `upload_prefix(user_id: int) -> str`：返回 `'u%d/' % user_id`。
  - `owns_upload(identity: dict, key: str) -> bool`：规则与 `ownsUpload` 相同。

- [ ] **Step 1：写失败的测试**

```python
# accounts_test.py
def test_session_round_trip():
    token = sign_session('s', 2000000000, 3, 7, 2)
    assert token.startswith('v2.2000000000.3.7.2.')
    assert parse_session('s', token, 1.0) == {'expires': 2000000000, 'user_id': 3, 'student_id': 7, 'version': 2}
    assert parse_session('other', token, 1.0) is None
    assert parse_session('s', token, 2000000001.0) is None
    assert parse_session('s', '1999999999.' + 'a'*64, 1.0) is None      # 旧格式
    assert parse_session('', token, 1.0) is None

def test_stale_version_rejected():
    c = build_db(); seed_family(c, user_id=2, username='li', student_ids=(5,))
    parsed = {'user_id': 2, 'student_id': 5, 'version': 1, 'expires': 9e9}
    assert run(load_identity(adapter(c), parsed))['student_id'] == 5
    c.execute('UPDATE app_user SET session_version=2 WHERE id=2')
    assert run(load_identity(adapter(c), parsed)) is None
    c.execute('UPDATE app_user SET session_version=1, disabled=1 WHERE id=2')
    assert run(load_identity(adapter(c), parsed)) is None

def test_identity_rejects_other_familys_student():
    # user 2 带着 1 号家庭的学生编号 → None

def test_owns_upload():
    me = {'user_id': 2}
    assert owns_upload(me, 'u2/2026/11/ab_x.jpg') and owns_upload(me, 'audio/words/x.mp3')
    assert not owns_upload(me, 'u1/2026/11/ab_x.jpg') and not owns_upload(me, '2026/11/ab_x.jpg')
    assert not owns_upload(me, 'u22/2026/11/ab_x.jpg')
    assert owns_upload({'user_id': 1}, '2026/11/ab_x.jpg')

def test_admin_only_rules():
    assert admin_only('POST', '/api/subjects') and admin_only('DELETE', '/api/knowledge-points/3')
    assert admin_only('GET', '/api/config/llm') and admin_only('GET', '/api/admin/users')
    assert not admin_only('GET', '/api/subjects') and not admin_only('POST', '/api/tags')
    assert not admin_only('POST', '/api/rewards') and not admin_only('PUT', '/api/starmap/progress')
```

```js
// auth.test.mjs
test('网关与后端的 Cookie 一致', async () => {
  // PY_COOKIE 是 sign_session('s', 2000000000, 3, 7, 2) 的结果，写死在这里
  assert.equal(await signSession('s', {expires: 2000000000, userId: 3, studentId: 7, version: 2}), PY_COOKIE);
  assert.deepEqual(await parseSession('s', PY_COOKIE, 1), {expires: 2000000000, userId: 3, studentId: 7, version: 2});
});
test('ownsUpload 与后端规则相同', () => { /* 与 test_owns_upload 同样的 6 个断言 */ });
```

`seed_family(c, user_id, username, student_ids, is_admin=0)` 写在 `accounts_test.py` 里，后面的任务都用它造家庭。

- [ ] **Step 2：运行，确认失败**：`python cloudflare/scripts/accounts_test.py` 和 `node --test cloudflare/pages/auth.test.mjs`，预期新加的测试失败。
- [ ] **Step 3：实现三个模块**。HMAC 比较：Python 用 `hmac.compare_digest`，JS 用 `crypto.subtle.verify`。
- [ ] **Step 4：运行，确认通过**：两条命令都全部通过。
- [ ] **Step 5：提交**：`git commit -m "feat(accounts): v2 session cookie and identity lookup"`

---

### Task 4：后端 guard 改用身份；`/api/auth/me`、切换学生；缓存与日志

**Files:**
- Modify: `cloudflare/src/auth.py`、`cloudflare/src/question_scope.py`、`cloudflare/src/cache.py`、`cloudflare/src/main.py`
- Modify（测试替身）：`cloudflare/scripts/` 下所有 `FakeRequest`、`ScheduledRequest` 的用法（`intake_test`、`phrase_focus_test`、`scan_test`、`starmap_test`、`targeted_preflight`、`knowledge_api_test`、`weekly_report_test`、`local_dev_server.py`）
- Test: `cloudflare/scripts/accounts_test.py`

**Interfaces:**
- Consumes：Task 3 的 `parse_session`、`sign_session`、`load_identity`、`agent_identity`、`admin_only`。
- Produces：
  - 每个通过 guard 的请求都有 `request.scope['easyfix']`，内容就是身份字典。
  - `question_scope.current_student_id(request) -> int`：返回 `current_identity(request)['student_id']`。
  - `GET /api/auth/me`：返回 `{'username','name','is_admin','student': {'id','name'},'students': [{'id','name'}]}`，学生按 `sort_order, id` 排序。
  - `POST /api/auth/switch-student {student_id}`：学生不属于当前用户时返回 404；成功时重新签发 Cookie（版本不变，过期时间重新算 30 天），返回 `{'success': True}`。用 Bearer 口令调用时返回 400 `{'detail': '录入口令不能切换学生'}`。
  - 测试替身的默认身份：`{'user_id': 1, 'username': 'admin', 'is_admin': True, 'version': 1, 'student_id': 1}`。
- guard 的顺序：
  1. 只有 `/health` 放行。
  2. 有 Bearer 口令就走 `agent_identity`（读 `X-Easyfix-Student` 头）；否则走 Cookie → `parse_session` → `load_identity`。拿不到身份时，`/api/` 和 `/uploads/` 返回 401，其他路径跳转 `/login`。
  3. 把身份写进 `request.scope['easyfix']`。
  4. `admin_only` 判断为真而身份不是管理员时，返回 403。
  5. 之后的迁移开关、维护开关、来源检查、缓存逻辑保持原样。
- `cache.lookup` 的键改为 `(student_id, str(request.url), revision)`。`invalidate` 写日志时，`operator` 用身份里的 `username`；Bearer 口令请求写 `'agent'`。
- 删掉：`LOGIN` 页面、`/login` 路由、后端的 `/api/auth/verify-password`、对 `ACCESS_PASSWORD` 的引用。

- [ ] **Step 1：写失败的测试**

```python
def test_guard_rejects_stale_session():
    # 调 guard(假请求, call_next)；Cookie 用版本 1 签发，库里版本已改成 2 → 401 {'detail': '需要登录'}
def test_guard_sets_identity_and_blocks_non_admin():
    # 家庭 2 的 Cookie：GET /api/home 时 call_next 能看到 scope['easyfix']['student_id']==5；POST /api/subjects → 403
def test_agent_token_student_header():
    # Bearer 加 X-Easyfix-Student: 5（属于家庭 2）→ 401；不带头 → 学生 1
def test_cache_key_includes_student():
    # 同一网址、同一 revision，学生 1 remember 之后，学生 5 lookup 不命中
def test_switch_student():
    # 家庭 1 加学生 2；切到 2 → Set-Cookie 里学生编号是 2；切到 5（家庭 2 的）→ 404
def test_me():
    # 返回 username、is_admin、students 的顺序
```

- [ ] **Step 2：运行，确认失败**：`python cloudflare/scripts/accounts_test.py`。
- [ ] **Step 3：实现**。同时给所有测试替身补上默认身份。`local_dev_server.py` 在包装请求时注入默认身份，本机测试环境继续免登录。
- [ ] **Step 4：运行全部后端测试，确认通过**：`accounts_test`、`flip_test`、`home_test`、`weekly_report_test`、`intake_test`、`scan_test`、`starmap_test`、`targeted_test`、`phrase_focus_test`、`knowledge_invariants_test`、`knowledge_api_test`、`grading_scan_test`、`dead_routes_test`、`local_dev_server_test`，每个都输出 `0 失败`。另外跑 `python -m compileall -q cloudflare/src`，预期没有输出。
- [ ] **Step 5：提交**：`git commit -m "feat(accounts): identity-based guard, me and switch-student"`

---

### Task 5：每个学生的配置

**Files:**
- Modify: `cloudflare/src/settings.py`、`cloudflare/src/weekly.py`（`ScheduledRequest`）
- Test: `cloudflare/scripts/accounts_test.py`

**Interfaces:**
- Produces：`settings.PER_STUDENT_CONFIGS = {'app', 'starmap'}`。`settings.load(request, name, default)` 和 `settings.store(request, name, value)` 遇到这两个名字时，实际读写的是 `'%s:%d' % (name, current_student_id(request))`。调用方（intake、starmap、word_focus 等）不用改。`ScheduledRequest(env, identity)` 也带上身份。

- [ ] **Step 1：写失败的测试** `test_app_config_per_student`：学生 1 存 `default_grade=6`，学生 5 读到的是 None；学生 5 存 4 之后，学生 1 读到的仍是 6。`test_starmap_progress_per_student` 同理，用 `PUT /api/starmap/progress` 的处理函数来测。
- [ ] **Step 2：运行，确认失败。**
- [ ] **Step 3：实现。**
- [ ] **Step 4：运行，确认通过**，并重跑 `starmap_test`、`weekly_report_test`、`home_test`。
- [ ] **Step 5：提交**：`git commit -m "feat(accounts): per-student app and starmap config"`

---

### Task 6：防漏测试

**Files:**
- Create: `cloudflare/scripts/student_scope_test.py`

**Interfaces:**
- Produces：
  - `STUDENT_TABLES`：所有带 `student_id` 的学生数据表。`question`、`error_book`、`word`、`word_review`、`word_review_session`、`practice_set`、`learning_report`、`reading_passage`、`tag`、`reward`、`redemption`、`star_balance`、`star_record`、`achievement_progress`、`paper`、`scan_page`、`weekly_report`、`flip_log`、`mastery_adjustment`。
  - `SHARED_TABLES`：`star_action`、`achievement`、`textbook_section`，不检查。
  - 豁免写法：SQL 字符串所在行，或它上一行，写注释 `# scope-ok: <理由>`。
  - `ALLOWED_EXEMPTIONS`：每个文件允许的豁免数，写成字典，初始为空。

- [ ] **Step 1：写测试** `test_every_student_query_is_scoped`。用 `ast` 找出 `cloudflare/src/*.py` 里所有字符串常量，包括拼接后的 `BinOp` 和 f-string 的常量部分。只要字符串里有 `FROM|JOIN|UPDATE|INTO <学生表>`，同一个字符串里就必须出现 `student_id`，否则就得带豁免注释。失败时列出 `文件:行号 表名`。另写 `test_exemption_counts`：每个文件的豁免数等于 `ALLOWED_EXEMPTIONS` 里登记的数。
- [ ] **Step 2：运行，确认失败**：`python cloudflare/scripts/student_scope_test.py`，预期列出 questions、practices、words 等模块里的位置。把这份清单贴进提交说明，作为 Task 7、8 的工作清单。
- [ ] **Step 3：提交**（测试先进仓库，暂时是失败状态，Task 8 结束时全部通过）：`git commit -m "test(accounts): static check that student tables are scoped"`

---

### Task 7：错题、目录、知识点按学生过滤

**Files:**
- Modify: `cloudflare/src/questions.py`、`similar.py`、`review.py`、`catalog.py`、`knowledge.py`、`knowledge_stats.py`（如有学生表查询）、`papers.py`、`intake.py`、`scan.py`（漏掉的查询）
- Test: `cloudflare/scripts/accounts_test.py`

**Interfaces:**
- Consumes：`current_student_id(request)`。
- 规则：
  - 读：查学生表时加上 `student_id=?`。
  - 新增：显式写 `student_id`。
  - 按编号改或删：`WHERE id=? AND student_id=?`，影响 0 行就返回 404 `记录不存在`。
  - 附属表（`question_knowledge_point`、`question_tag` 等）：先确认主表那一行属于当前学生再操作。
  - `catalog.CATALOG` 每一项加第三个元素 `scoped: bool`：`tags`、`error-books`、`rewards` 为 True，`subjects`、`stars/actions`、`achievements` 为 False。

- [ ] **Step 1：写失败的测试** `test_other_student_by_id_is_404`：学生 5 对学生 1 的错题调 GET、PUT、DELETE 和相似题生成，都返回 404，库里那一行没有变化。`test_question_list_isolated`：两个学生各有 2 道题，列表各自只看到 2 道。`test_catalog_scoped`：学生 5 看不到学生 1 的标签和错题本，但看得到全部学科。
- [ ] **Step 2：运行，确认失败。**
- [ ] **Step 3：实现。**
- [ ] **Step 4：运行，确认通过**：`accounts_test` 通过；`student_scope_test` 的清单里这些文件已经清空；`intake_test`、`scan_test`、`knowledge_invariants_test`、`knowledge_api_test` 都通过。
- [ ] **Step 5：提交**：`git commit -m "feat(accounts): scope questions, catalog and knowledge by student"`

---

### Task 8：单词、练习、阅读、激励、翻一翻等其余模块

**Files:**
- Modify: `words.py`、`word_focus.py`、`phrase_focus.py`（如有）、`media.py`、`readings.py`、`analytics.py`、`practices.py`、`targeted.py`、`pdf.py`、`grading_scan.py`、`reports.py`、`motivation.py`、`flip.py`（`load_question_rows` 加 `student_id` 参数）、`starmap.py`、`home.py`、`weekly.py` 里剩下的查询
- Test: `cloudflare/scripts/accounts_test.py`

**Interfaces:**
- `flip.load_question_rows(db, student_id)`：签名多了 `student_id`，调用方跟着改。
- `motivation.py`：所有写死的 `user_id=1` 改成按当前学生过滤；新增行写 `student_id`，同时 `user_id` 写成身份里的 `user_id`。余额的 `ON CONFLICT` 目标改为 `(student_id) WHERE deleted=0`。
- PDF 的 R2 键改成 `upload_prefix(user_id) + 'practice_sets/…'`（`pdf.py:140`、`media.py:89`）。

- [ ] **Step 1：写失败的测试**：
  - `test_other_student_by_id_is_404`，补上练习集、单词、阅读、卷子。
  - `test_motivation_isolated_per_student`：学生 1 和学生 2 同属家庭 1，各自加星，余额互不影响；成就进度互不影响；学生 2 看不到学生 1 的奖品。
  - `test_flip_pool_isolated`：学生 5 的翻一翻候选里没有学生 1 的题。
  - `test_pdf_key_prefixed`：生成的键以 `u2/practice_sets/` 开头。
- [ ] **Step 2：运行，确认失败。**
- [ ] **Step 3：实现。**
- [ ] **Step 4：运行，确认通过**：`python cloudflare/scripts/student_scope_test.py` 全部通过；所有后端测试（Task 4 Step 4 那份清单）都输出 `0 失败`。
- [ ] **Step 5：提交**：`git commit -m "feat(accounts): scope words, practices, motivation and flip by student"`

---

### Task 9：附件归属（网关）与图片路径校验（后端）

**Files:**
- Modify: `cloudflare/pages/_worker.js`、`cloudflare/pages/worker.test.mjs`、`cloudflare/src/intake.py`、`scan.py`、`grading_scan.py`、`practices.py`（`review-images`）、`questions.py`（如果接收图片路径）
- Test: `cloudflare/pages/auth.test.mjs`、`cloudflare/scripts/accounts_test.py`

**Interfaces:**
- Consumes：`session.js` 的 `parseSession`、`loadIdentity`、`ownsUpload`；`identity.py` 的 `owns_upload`、`upload_prefix`。
- 网关：
  - `authenticated(request, env)` 改为 `identify(request, env) -> Promise<identity|null>`。Bearer 口令对应 `{userId: 1, isAdmin: true}`。
  - `saveImage(env, file, userId)` 生成的键前面加 `u<userId>/`。
  - `/uploads/<key>` 在 `ownsUpload` 为假时返回 404 `{detail: '附件不存在'}`。
  - 页面请求（HTML）只验签名，不查库。
  - `logUpload` 的 `operator` 写登录名。
- 后端：凡是请求体里有图片路径的接口，每个路径都要过 `owns_upload`，有一个不通过就返回 404 `{'detail': '图片不存在'}`，并且不写库。

- [ ] **Step 1：写失败的测试**
  - 网关：
    - `上传键带用户前缀`
    - `读别人的附件返回 404`
    - `旧附件只有 1 号用户能读`
    - `音频谁都能读`
    - `会话版本过期时上传返回 401`
  - 后端：`test_foreign_image_path_rejected`。家庭 2 把 `u1/…` 和 `2026/11/…` 提交给录入、整页识别建页、批改识别、复核图片四个接口，都返回 404，相关表的行数不变。
- [ ] **Step 2：运行，确认失败**：`node --test cloudflare/pages/worker.test.mjs cloudflare/pages/auth.test.mjs`，再跑 `python cloudflare/scripts/accounts_test.py`。
- [ ] **Step 3：实现。**
- [ ] **Step 4：运行，确认通过**：上面两条命令，再加 `scan_test`、`intake_test`、`grading_scan_test`。
- [ ] **Step 5：提交**：`git commit -m "feat(accounts): per-family upload ownership"`

---

### Task 10：周报定时任务按学生推进

**Files:**
- Modify: `cloudflare/src/weekly.py`、`cloudflare/wrangler.jsonc`
- Test: `cloudflare/scripts/weekly_report_test.py`

**Interfaces:**
- Produces：`async pick_scheduled_student(db, week_end: str) -> int | None`：在没停用、没删除用户下的没删除学生里，按 `student.id` 找第一个"这一期周报不存在，或状态不是 `done`"的学生。`run_scheduled` 用它选学生，再用这个学生的身份构造 `ScheduledRequest`；没有学生要推进时，日志写 `weekly <week_end> idle`。
- cron 改为 `"*/10 12-15 * * sun"`（北京时间周日 20:00–23:50，共 24 次）。**写计划时的决定**：不等实测不够再改，现在就放宽，每次触发的开销不变。

- [ ] **Step 1：写失败的测试** `test_scheduled_moves_to_next_student`：学生 1 本期已经 `done`，学生 5 还没有周报，`run_scheduled` 应建出学生 5 的那一期；两个都 `done` 时返回 `idle`；停用用户的学生跳过。
- [ ] **Step 2：运行，确认失败。**
- [ ] **Step 3：实现。**
- [ ] **Step 4：运行，确认通过**：`python cloudflare/scripts/weekly_report_test.py`。
- [ ] **Step 5：提交**：`git commit -m "feat(accounts): weekly cron walks all students"`

---

### Task 11：网关的登录与密码接口

**Files:**
- Create: `cloudflare/pages/auth_routes.js`
- Modify: `cloudflare/pages/_worker.js`、`cloudflare/pages/password.js`（按实测调 `PBKDF2_ITERATIONS`）
- Test: `cloudflare/pages/auth.test.mjs`

**Interfaces:**
- Consumes：Task 2、Task 3 的网关模块。
- Produces：`handleAuthRoute(request, env, url) -> Promise<Response|null>`。不是下面这些路径时返回 null，`_worker.js` 继续往下处理。
  - `GET /login`：登录页，有账号、密码两个输入框，错误提示统一为"账号或密码不正确"。样式沿用现有登录页。登录成功后跳转到 `/`。
  - `POST /api/auth/login {username, password}`：
    - 成功：签发 Cookie（学生取 `ORDER BY sort_order, id` 的第一个），更新 `last_login_at`，清掉失败计数，返回 `{success: true}`。
    - 失败：返回 401 `{detail: '账号或密码不正确'}`，失败计数加 1，计数存在 `request_record` 的 `login_fail:<username>` 里。
    - 15 分钟内失败满 5 次：返回 429。
    - 账号下没有学生：返回 403 `{detail: '这个账号还没有学生，请联系管理员'}`。
  - `POST /api/auth/logout`：清 Cookie（`Max-Age=0`），返回 `{success: true}`。
  - `POST /api/auth/verify-password {password}`：要求已登录，校验当前账号的密码。正确返回 `{success: true}`，错误返回 401。
  - `POST /api/auth/change-password {old_password, new_password}`：新密码不足 10 位返回 422；旧密码错误返回 401。成功后写新哈希、`session_version+1`，用新版本重新签发 Cookie。
  - `POST /api/auth/admin/set-password {user_id}`：要求管理员；不能对自己用，对自己用返回 422 `{detail: '请在"我的账号"里改自己的密码'}`。成功后生成 `randomPassword()`，写哈希、`session_version+1`，返回 `{password}`。
  - 所有写请求都和后端一样检查 `Origin`。
- 迭代次数实测办法：部署到预览分支前，在本地用 `wrangler pages dev` 对 `/api/auth/login` 连续请求 20 次，看日志里的 CPU 时间。取不超过 10 毫秒的最大值（候选 100000、50000、20000、10000）。连 10000 都超时，就停下来报告开发者（spec 5.8）。

- [ ] **Step 1：写失败的测试**：
  - 登录成功时 Cookie 格式正确，且 `last_login_at` 已写入。
  - 密码错误返回 401，第 6 次返回 429。
  - 停用的账号返回 401。
  - 没有学生的账号返回 403。
  - `verify-password` 正确返回 200，错误返回 401。
  - `change-password` 不足 10 位返回 422；成功后旧 Cookie 失效。
  - `admin/set-password`：非管理员返回 403，对自己用返回 422，成功时返回 12 位密码且版本加 1。
  - 假 D1 照 `worker.test.mjs` 的 `makeEnv` 扩展，用一个 `Map` 存用户、学生和 `request_record`。
- [ ] **Step 2：运行，确认失败**：`node --test cloudflare/pages/auth.test.mjs`。
- [ ] **Step 3：实现。**
- [ ] **Step 4：运行，确认通过**：`node --test cloudflare/pages/auth.test.mjs cloudflare/pages/worker.test.mjs`。
- [ ] **Step 5：提交**：`git commit -m "feat(accounts): gateway login, password change and admin reset"`

---

### Task 12：管理员接口 `/api/admin/*`

**Files:**
- Create: `cloudflare/src/accounts.py`
- Modify: `cloudflare/src/main.py`（注册路由）
- Test: `cloudflare/scripts/accounts_test.py`

**Interfaces:**
- Produces（guard 已经按 `admin_only` 拦住了非管理员）：
  - `GET /api/admin/users`：返回 `[{id, username, name, disabled, last_login_at, students: [{id, name, grade, semester}]}]`。`grade` 和 `semester` 来自对应学生的 `app:<学生编号>` 配置。
  - `POST /api/admin/users {username, name, student_name, grade, semester}`：登录名格式不对返回 422；登录名已被占用返回 409 `{'detail': '登录名已被占用'}`。成功后建用户（不设密码），建学生，写入 `app:<学生编号>`，返回 `{user_id, student_id}`。前端拿到后再调网关的 `admin/set-password` 生成初始密码。
  - `PUT /api/admin/users/{id} {name?, disabled?}`：停用自己返回 422；停用或启用时 `session_version+1`。
  - `POST /api/admin/users/{id}/students {name, grade, semester}`
  - `PUT /api/admin/students/{id} {name?, grade?, semester?, sort_order?}`
  - `DELETE /api/admin/students/{id}`：软删除；如果是这个家庭最后一个学生，返回 409 `{'detail': '至少要保留一个学生'}`。
- 管理员自己的家庭也能用这些接口加学生、改学生。

- [ ] **Step 1：写失败的测试**：
  - 建家庭的完整流程：建好后 `GET` 能看到这个家庭，学生年级正确。
  - 登录名格式不对返回 422；重名返回 409。
  - 停用自己返回 422。
  - 停用别人后，该家庭的 `load_identity` 返回 None。
  - 删除最后一个学生返回 409。
  - 非管理员调 `/api/admin/users` 返回 403（经 guard）。
- [ ] **Step 2：运行，确认失败。**
- [ ] **Step 3：实现。**
- [ ] **Step 4：运行，确认通过**，再跑 `python -m compileall -q cloudflare/src` 和 `dead_routes_test`。
- [ ] **Step 5：提交**：`git commit -m "feat(accounts): admin family and student management API"`

---

### Task 13：前端

**Files:**
- Create: `frontend/src/stores/account.js`、`frontend/src/components/settings/AccountTab.vue`、`frontend/src/components/settings/MyAccountTab.vue`
- Modify: `frontend/src/api/auth.js`（新增 `me`、`switchStudent`、`logout`、`changePassword`、`adminUsers` 系列、`adminSetPassword`）、`frontend/src/App.vue`、`frontend/src/views/Settings.vue`、`frontend/src/components/settings/settingsModel.js`、`settingsModel.test.mjs`；年级、学科、知识点、星空、激励各标签里的写按钮
- Test: `frontend/src/components/settings/settingsModel.test.mjs`、`frontend/src/api/apiLayer.test.mjs`

**Interfaces:**
- Produces：
  - `settingsModel.tabs_for(is_admin: boolean) -> Array<{key,label}>`：
    - 管理员：现有七个标签，加 `{key:'accounts',label:'账号'}`，再加 `{key:'me',label:'我的账号'}`。
    - 非管理员：去掉 `model`，加 `me`。
  - `settingsModel.can_edit_shared(is_admin) -> boolean`。学科、知识点标签用它隐藏写按钮；星空标签只隐藏教材目录的编辑入口；激励面板只隐藏加星规则和成就的编辑。
  - `useAccountStore`：状态有 `username`、`name`、`isAdmin`、`student`、`students`、`loaded`；动作有 `load()`（调 `/api/auth/me`）、`switchTo(student_id)`（成功后 `location.reload()`）、`logout()`（成功后 `location.replace('/login')`）。
  - App.vue：
    - 侧栏品牌下方显示当前学生名字；学生多于一个时，点开是下拉切换。
    - 侧栏底部加"退出登录"。
    - 手机"更多"面板顶部显示学生名字，下面放切换和退出。
  - AccountTab（管理员）：
    - 家庭表格：登录名、名字、学生、状态、最近登录。
    - 操作：新建家庭（建好后弹窗显示初始密码一次，提示"请复制发给对方，关掉后不再显示"）、加学生、改学生、重置密码（同样只显示一次）、停用和启用。
  - MyAccountTab：显示登录名和学生列表；改密码表单（旧密码、新密码、确认新密码，前端也检查至少 10 位）。
  - 接口照 `apiLayer.test.mjs` 的规矩写在 `api/auth.js`，页面里不直接写地址。

- [ ] **Step 1：写失败的测试**：`tabs_for(true)` 的 key 顺序为 `['grade','subjects','tags','knowledge','books','starmap','model','accounts','me']`；`tabs_for(false)` 不含 `model` 和 `accounts`，最后一个是 `me`；`can_edit_shared(false) === false`。
- [ ] **Step 2：运行，确认失败**：`node --test frontend/src/components/settings/settingsModel.test.mjs`。
- [ ] **Step 3：实现。**
- [ ] **Step 4：运行，确认通过**：把 `CLAUDE.md` 里列的前端测试全跑一遍，再跑 `python backend/scripts/prepare_cloudflare_frontend.py`，预期构建成功。然后用 `local_dev_server.py` 和前端开发服务器在浏览器里点一遍：切换学生、设置页标签按角色显示、账号标签建家庭。本机测试环境默认是管理员。
- [ ] **Step 5：提交**：`git commit -m "feat(accounts): account store, student switcher, account settings tabs"`

---

### Task 14：录入工具、文档与发布

**Files:**
- Modify: `tools/easyfix-intake/easyfix_intake.py`、`test_easyfix_intake.py`、`SKILL.md`（说明可选的 `student_id`）
- Modify: `CLAUDE.md`（登录方式、新模块、新测试命令）、`AGENTS.md`（如有相关段落）、`docs/cloudflare-api-checklist.md`、`docs/cloudflare-migration-status.md`

**Interfaces:**
- `easyfix_intake.py`：`config.get('student_id')` 有值时，每个请求都带 `X-Easyfix-Student: <值>` 头。

- [ ] **Step 1：写失败的测试** `test_student_header_sent`：配置里有 `student_id=2` 时请求头带上它；没有时不带。
- [ ] **Step 2：运行，确认失败**：`python tools/easyfix-intake/test_easyfix_intake.py`。
- [ ] **Step 3：实现并更新文档。**
- [ ] **Step 4：运行全部测试**：`CLAUDE.md` 列出的测试加上本计划新增的（`accounts_test`、`student_scope_test`、`auth.test.mjs`），全部通过。
- [ ] **Step 5：提交**：`git commit -m "docs(accounts): intake student header and account docs"`
- [ ] **Step 6：发布**。每一步先问开发者，得到同意后再执行。顺序按 spec 5.9：
  1. 开维护开关，导出 D1 备份。
  2. 执行 0018，核对 spec 第 6 节第 7 步的各项。
  3. 开发者在终端运行 `python backend/scripts/set_admin_password.py`。
  4. 同时部署 Worker 和 Pages。
  5. 关维护开关。
  6. 按 spec 5.9 第 5 步核对：建测试家庭、确认它的数据全空、读开发者家的附件返回 404，测完停用测试家庭。
  7. 删除 `ACCESS_PASSWORD` 密钥。
  8. 在 `docs/cloudflare-migration-status.md` 记录这次发布，并提交。
