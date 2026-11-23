// 网关里跟密码有关的接口：登录页、登录、退出、验密码、改密码、管理员重置密码。
// 为什么放在网关：密码哈希（PBKDF2）要花 CPU，Python 后端在免费计划下每个请求只有 10 毫秒，算不完；
// 网关是 JS，用 WebCrypto 原生计算。其余账号接口（/api/auth/me、切换学生、/api/admin/*）在后端。

import { hashPassword, verifyPassword, randomPassword } from './password.js';
import { signSession, sessionCookieHeader, SESSION_SECONDS, identify } from './session.js';

const FAIL_WINDOW_SECONDS = 15 * 60;   // 输错次数的统计窗口：15 分钟
const FAIL_LIMIT = 5;                  // 窗口内最多输错几次
const MIN_PASSWORD_LENGTH = 10;        // 自己改密码时的最短长度
const WRONG_TEXT = '账号或密码不正确';

// 登录页：账号、密码两个输入框；样式沿用原来的共享密码登录页
const LOGIN_PAGE = '<!doctype html><html lang="zh-CN"><meta charset="utf-8">'
  + '<meta name="viewport" content="width=device-width,initial-scale=1"><title>登录 EasyFix</title>'
  + '<style>body{margin:0;min-height:100vh;display:grid;place-items:center;background:#f5f7fb;font:16px system-ui;color:#243149}'
  + 'main{width:min(320px,80vw);padding:32px;background:white;border-radius:16px;box-shadow:0 12px 40px #24314912}'
  + 'h1{margin-top:0}label{display:block;margin:12px 0 6px}input,button{box-sizing:border-box;width:100%;padding:12px;'
  + 'border:1px solid #cbd5e1;border-radius:8px;font:inherit}button{margin-top:20px;color:white;background:#3468df;border:0;'
  + 'cursor:pointer}#error{color:#b42318;min-height:24px}</style>'
  + '<main><h1>EasyFix</h1><p>登录后继续整理错题和练习。</p><form id="login">'
  + '<label for="username">账号</label><input id="username" autocomplete="username" autocapitalize="off" required autofocus>'
  + '<label for="password">密码</label><input id="password" type="password" autocomplete="current-password" required>'
  + '<button>登录</button><p id="error" role="alert"></p></form></main>'
  + '<script>document.getElementById("login").onsubmit=async e=>{e.preventDefault();'
  + 'const b=e.target.querySelector("button"),out=document.getElementById("error");b.disabled=true;out.textContent="";'
  + 'try{const r=await fetch("/api/auth/login",{method:"POST",headers:{"Content-Type":"application/json"},'
  + 'body:JSON.stringify({username:document.getElementById("username").value.trim(),password:document.getElementById("password").value})});'
  + 'if(r.ok){location.replace("/");return}const d=await r.json().catch(()=>({}));out.textContent=d.detail||"登录失败，请重试。"}'
  + 'catch{out.textContent="连接失败，请稍后重试。"}finally{b.disabled=false}};</script></html>';

/** 返回 JSON 响应；和后端一样禁止缓存。 */
function json(data, status = 200, headers = {}) {
  return Response.json(data, { status, headers: { 'Cache-Control': 'private, no-store', ...headers } });
}

/** 北京时间文本（数据库里的时间都是北京时间），例："2026-11-23 20:00:00"。 */
function beijingText() {
  return new Date(Date.now() + 8 * 3600 * 1000).toISOString().replace('T', ' ').slice(0, 19);
}

/** 读 JSON 请求体；不是对象时当作空对象。 */
async function readBody(request) {
  try {
    const value = await request.json();
    return value && typeof value === 'object' && !Array.isArray(value) ? value : {};
  } catch (error) {
    return {};
  }
}

/** 写请求必须同站（没有 Origin 头的按同站处理，和后端一致）。 */
function sameOrigin(request, url) {
  const origin = request.headers.get('Origin');
  return !origin || origin === url.origin;
}

/** 签发会话 Cookie，返回 Set-Cookie 头的值。 */
async function cookieFor(env, userId, studentId, version) {
  const expires = Math.floor(Date.now() / 1000) + SESSION_SECONDS;
  return sessionCookieHeader(await signSession(env.SESSION_SECRET, { expires, userId, studentId, version }));
}

// ---------------------------------------------------------------- 输错次数

/** 读某个登录名的输错记录 {count, first}（first 是第一次输错的秒数），没有返回 null。 */
async function failureState(env, username) {
  const row = await env.DB.prepare('SELECT value FROM request_record WHERE name=? AND deleted=0')
    .bind('login_fail:' + username).first();
  if (!row) return null;
  try {
    return JSON.parse(row.value);
  } catch (error) {
    return null;
  }
}

/** 是否已被锁住：窗口内输错次数达到上限。 */
function locked(state, now) {
  return Boolean(state) && now - state.first < FAIL_WINDOW_SECONDS && state.count >= FAIL_LIMIT;
}

/** 记一次输错：窗口过了就从 1 重新数。 */
async function recordFailure(env, username, state, now) {
  const next = state && now - state.first < FAIL_WINDOW_SECONDS ? { count: state.count + 1, first: state.first } : { count: 1, first: now };
  await env.DB.prepare('INSERT INTO request_record(name,value,deleted,created_at) VALUES(?,?,0,?) '
    + 'ON CONFLICT(name) DO UPDATE SET value=excluded.value,deleted=0,created_at=excluded.created_at')
    .bind('login_fail:' + username, JSON.stringify(next), beijingText()).run();
}

/** 登录成功后清掉输错记录（软删除）。 */
async function clearFailures(env, username) {
  await env.DB.prepare('UPDATE request_record SET deleted=1 WHERE name=?').bind('login_fail:' + username).run();
}

// ---------------------------------------------------------------- 各个接口

/** 登录：账号密码正确、没停用、有学生时签发 Cookie（学生取排在最前的）。 */
async function login(request, env) {
  const body = await readBody(request);
  const username = typeof body.username === 'string' ? body.username.trim() : '';
  const password = typeof body.password === 'string' ? body.password : '';
  if (!username || !password) return json({ detail: WRONG_TEXT }, 401);
  const now = Date.now() / 1000;
  const state = await failureState(env, username);
  if (locked(state, now)) return json({ detail: '尝试次数太多，请 15 分钟后再试' }, 429);
  const user = await env.DB.prepare('SELECT id,password_hash,session_version,disabled FROM app_user WHERE username=? AND deleted=0')
    .bind(username).first();
  const ok = Boolean(user) && !user.disabled && await verifyPassword(password, user.password_hash);
  if (!ok) {
    await recordFailure(env, username, state, now);
    return json({ detail: WRONG_TEXT }, 401);
  }
  const student = await env.DB.prepare('SELECT id FROM student WHERE user_id=? AND deleted=0 ORDER BY sort_order,id LIMIT 1')
    .bind(user.id).first();
  if (!student) return json({ detail: '这个账号还没有学生，请联系管理员' }, 403);
  await clearFailures(env, username);
  await env.DB.prepare('UPDATE app_user SET last_login_at=? WHERE id=?').bind(beijingText(), user.id).run();
  return json({ success: true }, 200, { 'Set-Cookie': await cookieFor(env, user.id, student.id, user.session_version) });
}

/** 读当前账号的密码哈希；录入口令或没登录返回 null。 */
async function currentUser(request, env) {
  const identity = await identify(request, env);
  if (!identity || identity.agent) return null;
  const row = await env.DB.prepare('SELECT password_hash FROM app_user WHERE id=? AND deleted=0').bind(identity.userId).first();
  return row ? { identity, hash: row.password_hash } : null;
}

/** 设置页进入前验一次当前账号的密码。 */
async function verify(request, env) {
  const user = await currentUser(request, env);
  if (!user) return json({ detail: '需要登录' }, 401);
  const body = await readBody(request);
  if (!await verifyPassword(typeof body.password === 'string' ? body.password : '', user.hash)) {
    return json({ detail: '密码不正确' }, 401);
  }
  return json({ success: true });
}

/** 改自己的密码：会话版本加 1（别处的登录失效），给当前浏览器重新签发 Cookie。 */
async function changePassword(request, env) {
  const user = await currentUser(request, env);
  if (!user) return json({ detail: '需要登录' }, 401);
  const body = await readBody(request);
  const fresh = typeof body.new_password === 'string' ? body.new_password : '';
  if (fresh.length < MIN_PASSWORD_LENGTH) return json({ detail: '新密码至少 ' + MIN_PASSWORD_LENGTH + ' 位' }, 422);
  if (!await verifyPassword(typeof body.old_password === 'string' ? body.old_password : '', user.hash)) {
    return json({ detail: '原密码不正确' }, 401);
  }
  const { identity } = user;
  await env.DB.prepare('UPDATE app_user SET password_hash=?,session_version=session_version+1,updated_at=? WHERE id=?')
    .bind(await hashPassword(fresh), beijingText(), identity.userId).run();
  return json({ success: true }, 200,
    { 'Set-Cookie': await cookieFor(env, identity.userId, identity.studentId, identity.version + 1) });
}

/** 管理员给别的家庭设一个随机新密码（只在这次返回里出现）；对方的旧登录全部失效。 */
async function adminSetPassword(request, env) {
  const identity = await identify(request, env);
  if (!identity) return json({ detail: '需要登录' }, 401);
  if (!identity.isAdmin || identity.agent) return json({ detail: '只有管理员可以操作' }, 403);
  const body = await readBody(request);
  const userId = body.user_id;
  if (!Number.isInteger(userId)) return json({ detail: 'user_id 必须是整数' }, 422);
  if (userId === identity.userId) return json({ detail: '请在"我的账号"里改自己的密码' }, 422);
  const target = await env.DB.prepare('SELECT id FROM app_user WHERE id=? AND deleted=0').bind(userId).first();
  if (!target) return json({ detail: '记录不存在' }, 404);
  const password = randomPassword();
  await env.DB.prepare('UPDATE app_user SET password_hash=?,session_version=session_version+1,updated_at=? WHERE id=?')
    .bind(await hashPassword(password), beijingText(), userId).run();
  return json({ password });
}

const POST_ROUTES = {
  '/api/auth/login': login,
  '/api/auth/logout': async () => json({ success: true }, 200, { 'Set-Cookie': sessionCookieHeader('', 0) }),
  '/api/auth/verify-password': verify,
  '/api/auth/change-password': changePassword,
  '/api/auth/admin/set-password': adminSetPassword,
};

/** 处理登录相关的路径；不是这些路径时返回 null，由网关继续处理（转给后端等）。 */
export async function handleAuthRoute(request, env, url) {
  if (url.pathname === '/login' && request.method === 'GET') {
    return new Response(LOGIN_PAGE, { headers: { 'Content-Type': 'text/html; charset=utf-8', 'Cache-Control': 'no-store' } });
  }
  const handler = POST_ROUTES[url.pathname];
  if (!handler) return null;
  if (request.method !== 'POST') return json({ detail: '只支持 POST' }, 405);
  if (!sameOrigin(request, url)) return json({ detail: '请求来源无效' }, 403);
  return handler(request, env);
}
