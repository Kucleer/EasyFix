// 网关登录与密码接口的测试：用 node 自带的 SQLite 当假的 D1。
// 运行：node --test cloudflare/pages/auth_routes.test.mjs
import test from 'node:test';
import assert from 'node:assert/strict';
import { DatabaseSync } from 'node:sqlite';
import { handleAuthRoute } from './auth_routes.js';
import { hashPassword } from './password.js';
import { parseSession } from './session.js';

const SITE = 'https://easyfix.test';
const SECRET = 'auth-secret';

/** 用 node 自带的 SQLite 做一个假的 D1（只实现 prepare/bind/first/run/all）。 */
function fakeD1(db) {
  return {
    prepare(sql) {
      const make = (values) => ({
        bind: (...next) => make(next),
        async first() { return db.prepare(sql).get(...values) ?? null; },
        async run() {
          const result = db.prepare(sql).run(...values);
          return { meta: { changes: result.changes, last_row_id: Number(result.lastInsertRowid) } };
        },
        async all() { return { results: db.prepare(sql).all(...values) }; },
      });
      return make([]);
    },
  };
}

const SCHEMA = [
  'CREATE TABLE app_user (id INTEGER PRIMARY KEY, name TEXT, username TEXT, password_hash TEXT,',
  '  is_admin INTEGER NOT NULL DEFAULT 0, session_version INTEGER NOT NULL DEFAULT 1,',
  '  disabled INTEGER NOT NULL DEFAULT 0, last_login_at TEXT, updated_at TEXT, deleted INTEGER NOT NULL DEFAULT 0);',
  'CREATE TABLE student (id INTEGER PRIMARY KEY, user_id INTEGER, name TEXT, sort_order INTEGER NOT NULL DEFAULT 0,',
  '  deleted INTEGER NOT NULL DEFAULT 0);',
  'CREATE TABLE request_record (name TEXT PRIMARY KEY, value TEXT NOT NULL, deleted INTEGER NOT NULL DEFAULT 0,',
  '  created_at TEXT NOT NULL);',
  'CREATE TABLE runtime_config (name TEXT PRIMARY KEY, value TEXT NOT NULL, deleted INTEGER NOT NULL DEFAULT 0,',
  '  updated_at TEXT NOT NULL);',
].join('\n');

/** 建一套账号库：管理员 admin（学生 1），家长 li（学生 5、6），没有学生的 empty，停用的 gone。 */
async function authEnv() {
  const db = new DatabaseSync(':memory:');
  db.exec(SCHEMA);
  const users = [[1, 'admin', 'admin-password', 1, 0], [2, 'li', 'li-password-1', 0, 0],
    [3, 'empty', 'empty-password', 0, 0], [4, 'gone', 'gone-password', 0, 1]];
  for (const [id, username, password, isAdmin, disabled] of users) {
    db.prepare('INSERT INTO app_user(id,name,username,password_hash,is_admin,disabled) VALUES(?,?,?,?,?,?)')
      .run(id, username + '家', username, await hashPassword(password, 1000), isAdmin, disabled);
  }
  db.exec("INSERT INTO student(id,user_id,name,sort_order) VALUES(1,1,'大宝',0),(5,2,'小李',1),(6,2,'小李二',0),(9,4,'停用',0)");
  return { db, env: { DB: fakeD1(db), SESSION_SECRET: SECRET, ACCESS_TOKEN: 'agent-token' } };
}

/** 发一个同站的 JSON POST；headers 可带 Cookie。 */
function post(path, body, headers = {}) {
  return new Request(SITE + path, { method: 'POST', body: JSON.stringify(body),
    headers: { 'Content-Type': 'application/json', Origin: SITE, ...headers } });
}

/** 从响应里取出会话 Cookie 的值。 */
function cookieOf(response) {
  return (response.headers.get('Set-Cookie') || '').split(';')[0].split('=').slice(1).join('=');
}

/** 交给登录接口处理。 */
async function call(env, request) {
  return handleAuthRoute(request, env, new URL(request.url));
}

/** 登录并返回带会话 Cookie 的请求头。 */
async function loginAs(env, username, password) {
  return { Cookie: 'easyfix_session=' + cookieOf(await call(env, post('/api/auth/login', { username, password }))) };
}

test('不是登录接口的路径返回 null（交给网关继续处理）', async () => {
  const { env } = await authEnv();
  assert.equal(await call(env, new Request(SITE + '/api/questions')), null);
  assert.equal(await call(env, new Request(SITE + '/api/auth/me')), null);   // 这个由后端处理
});

test('登录页是账号加密码两个输入框', async () => {
  const { env } = await authEnv();
  const response = await call(env, new Request(SITE + '/login'));
  const html = await response.text();
  assert.equal(response.status, 200);
  assert.match(html, /id="username"/);
  assert.match(html, /type="password"/);
});

test('登录成功：签发 Cookie，学生取排在最前的，记下登录时间', async () => {
  const { db, env } = await authEnv();
  const response = await call(env, post('/api/auth/login', { username: 'li', password: 'li-password-1' }));
  assert.equal(response.status, 200);
  assert.deepEqual(await response.json(), { success: true });
  assert.match(response.headers.get('Set-Cookie'), /Max-Age=2592000; Path=\/; HttpOnly; Secure; SameSite=Strict/);
  const parsed = await parseSession(SECRET, cookieOf(response), 1);
  assert.equal(parsed.userId, 2);
  assert.equal(parsed.studentId, 6);   // sort_order 为 0 的排在前面
  assert.ok(db.prepare('SELECT last_login_at FROM app_user WHERE id=2').get().last_login_at);
});

test('密码错误 401，同一账号 15 分钟内错满 5 次后直接 429', async () => {
  const { env } = await authEnv();
  for (let i = 0; i < 5; i++) {
    const wrong = await call(env, post('/api/auth/login', { username: 'li', password: 'nope' }));
    assert.equal(wrong.status, 401);
    assert.deepEqual(await wrong.json(), { detail: '账号或密码不正确' });
  }
  const locked = await call(env, post('/api/auth/login', { username: 'li', password: 'li-password-1' }));
  assert.equal(locked.status, 429);
  assert.deepEqual(await locked.json(), { detail: '尝试次数太多，请 15 分钟后再试' });
  // 别的账号不受影响
  assert.equal((await call(env, post('/api/auth/login', { username: 'admin', password: 'admin-password' }))).status, 200);
});

test('登录成功会清掉之前的失败次数', async () => {
  const { env } = await authEnv();
  for (let i = 0; i < 4; i++) await call(env, post('/api/auth/login', { username: 'li', password: 'nope' }));
  assert.equal((await call(env, post('/api/auth/login', { username: 'li', password: 'li-password-1' }))).status, 200);
  for (let i = 0; i < 4; i++) await call(env, post('/api/auth/login', { username: 'li', password: 'nope' }));
  assert.equal((await call(env, post('/api/auth/login', { username: 'li', password: 'li-password-1' }))).status, 200);
});

test('停用账号 401，没有学生的账号 403，不存在的账号 401，格式不对 401', async () => {
  const { env } = await authEnv();
  assert.equal((await call(env, post('/api/auth/login', { username: 'gone', password: 'gone-password' }))).status, 401);
  const empty = await call(env, post('/api/auth/login', { username: 'empty', password: 'empty-password' }));
  assert.equal(empty.status, 403);
  assert.deepEqual(await empty.json(), { detail: '这个账号还没有学生，请联系管理员' });
  assert.equal((await call(env, post('/api/auth/login', { username: 'nobody', password: 'x' }))).status, 401);
  assert.equal((await call(env, post('/api/auth/login', { username: ['li'], password: 1 }))).status, 401);
});

test('跨站来源的登录请求 403', async () => {
  const { env } = await authEnv();
  const request = new Request(SITE + '/api/auth/login', { method: 'POST', body: '{}',
    headers: { 'Content-Type': 'application/json', Origin: 'https://evil.test' } });
  assert.equal((await call(env, request)).status, 403);
});

test('退出登录清掉 Cookie', async () => {
  const { env } = await authEnv();
  const response = await call(env, post('/api/auth/logout', {}));
  assert.equal(response.status, 200);
  assert.match(response.headers.get('Set-Cookie'), /^easyfix_session=; Max-Age=0/);
});

test('设置页验密码：正确 200，错误 401，没登录 401', async () => {
  const { env } = await authEnv();
  const li = await loginAs(env, 'li', 'li-password-1');
  assert.equal((await call(env, post('/api/auth/verify-password', { password: 'li-password-1' }, li))).status, 200);
  assert.equal((await call(env, post('/api/auth/verify-password', { password: 'wrong' }, li))).status, 401);
  assert.equal((await call(env, post('/api/auth/verify-password', { password: 'li-password-1' }))).status, 401);
});

test('改密码：不足 10 位 422，原密码错 401；成功后旧 Cookie 失效，新 Cookie 可用', async () => {
  const { env } = await authEnv();
  const li = await loginAs(env, 'li', 'li-password-1');
  const short = await call(env, post('/api/auth/change-password', { old_password: 'li-password-1', new_password: 'short' }, li));
  assert.equal(short.status, 422);
  const wrongOld = await call(env, post('/api/auth/change-password', { old_password: 'x', new_password: 'new-password-22' }, li));
  assert.equal(wrongOld.status, 401);
  const ok = await call(env, post('/api/auth/change-password', { old_password: 'li-password-1', new_password: 'new-password-22' }, li));
  assert.equal(ok.status, 200);
  const fresh = { Cookie: 'easyfix_session=' + cookieOf(ok) };
  assert.equal((await call(env, post('/api/auth/verify-password', { password: 'new-password-22' }, li))).status, 401);
  assert.equal((await call(env, post('/api/auth/verify-password', { password: 'new-password-22' }, fresh))).status, 200);
});

test('管理员重置密码：非管理员 403，对自己 422，不存在 404，成功返回 12 位新密码且旧登录失效', async () => {
  const { db, env } = await authEnv();
  const admin = await loginAs(env, 'admin', 'admin-password');
  const li = await loginAs(env, 'li', 'li-password-1');
  assert.equal((await call(env, post('/api/auth/admin/set-password', { user_id: 1 }, li))).status, 403);
  assert.equal((await call(env, post('/api/auth/admin/set-password', { user_id: 1 }, admin))).status, 422);
  assert.equal((await call(env, post('/api/auth/admin/set-password', { user_id: 99 }, admin))).status, 404);
  const reset = await call(env, post('/api/auth/admin/set-password', { user_id: 2 }, admin));
  assert.equal(reset.status, 200);
  const { password } = await reset.json();
  assert.equal(password.length, 12);
  assert.equal(db.prepare('SELECT session_version FROM app_user WHERE id=2').get().session_version, 2);
  assert.equal((await call(env, post('/api/auth/verify-password', { password }, li))).status, 401);
  assert.equal((await call(env, post('/api/auth/login', { username: 'li', password }))).status, 200);
});
