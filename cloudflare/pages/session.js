// 会话 Cookie 与登录身份（网关用）；格式与后端 cloudflare/src/session.py、identity.py 完全相同，两边要一起改。
// Cookie 值：v2.<过期秒>.<用户编号>.<学生编号>.<会话版本>.<签名hex>
// 签名 = HMAC-SHA256(SESSION_SECRET, "v2.<过期秒>.<用户编号>.<学生编号>.<会话版本>")

const encoder = new TextEncoder();
export const SESSION_SECONDS = 2592000;   // 30 天
const COOKIE_NAME = 'easyfix_session';

// 同一个密钥只导入一次
let cachedKey;
let cachedSecret;

/** 导入（或复用）HMAC 密钥。 */
async function hmacKey(secret) {
  if (cachedSecret !== secret) {
    cachedKey = await crypto.subtle.importKey('raw', encoder.encode(secret), { name: 'HMAC', hash: 'SHA-256' }, false, ['sign', 'verify']);
    cachedSecret = secret;
  }
  return cachedKey;
}

/** 签发 Cookie 值（不带 easyfix_session= 前缀）。 */
export async function signSession(secret, { expires, userId, studentId, version }) {
  const body = `v2.${expires}.${userId}.${studentId}.${version}`;
  const signature = new Uint8Array(await crypto.subtle.sign('HMAC', await hmacKey(secret), encoder.encode(body)));
  return body + '.' + Array.from(signature, (b) => b.toString(16).padStart(2, '0')).join('');
}

/** 解析并验证 Cookie 值；签名不对、过期、不是 v2、密钥为空时返回 null。 */
export async function parseSession(secret, token, nowSeconds) {
  if (!secret || typeof token !== 'string') return null;
  const parts = token.split('.');
  if (parts.length !== 6 || parts[0] !== 'v2' || !parts.slice(1, 5).every((p) => /^[0-9]+$/.test(p))) return null;
  if (!/^[0-9a-f]{64}$/.test(parts[5])) return null;
  const body = parts.slice(0, 5).join('.');
  const signature = Uint8Array.from(parts[5].match(/../g), (x) => parseInt(x, 16));
  if (!await crypto.subtle.verify('HMAC', await hmacKey(secret), signature, encoder.encode(body))) return null;
  const [expires, userId, studentId, version] = parts.slice(1, 5).map(Number);
  if (expires <= nowSeconds) return null;
  return { expires, userId, studentId, version };
}

/** 从请求头里取出会话 Cookie 的值，没有就是空串。 */
export function readSessionCookie(request) {
  const found = (request.headers.get('Cookie') || '').split(';').map((x) => x.trim()).find((x) => x.startsWith(COOKIE_NAME + '='));
  return found ? found.slice(COOKIE_NAME.length + 1) : '';
}

/** 写出 Set-Cookie 头；maxAge 为 0 时就是清除。 */
export function sessionCookieHeader(value, maxAge = SESSION_SECONDS) {
  return `${COOKIE_NAME}=${value}; Max-Age=${maxAge}; Path=/; HttpOnly; Secure; SameSite=Strict`;
}

// 与后端 identity.IDENTITY_SQL 完全相同
export const IDENTITY_SQL = 'SELECT u.id AS user_id, u.username, u.is_admin, u.session_version AS version, s.id AS student_id '
  + 'FROM app_user u JOIN student s ON s.user_id=u.id AND s.deleted=0 '
  + 'WHERE u.id=? AND u.deleted=0 AND u.disabled=0 AND u.session_version=? AND s.id=?';

/** 按 Cookie 解析结果查库确认身份；查不到返回 null。 */
export async function loadIdentity(env, parsed) {
  const row = await env.DB.prepare(IDENTITY_SQL).bind(parsed.userId, parsed.version, parsed.studentId).first();
  if (!row) return null;
  return { userId: Number(row.user_id), username: row.username, isAdmin: Boolean(row.is_admin),
    studentId: Number(row.student_id), version: Number(row.version) };
}

/** 附件归属：audio/ 大家共用；u<编号>/ 属于那个用户；没有前缀的旧附件属于 1 号用户。 */
export function ownsUpload(userId, key) {
  if (typeof key !== 'string' || !key) return false;
  if (key.startsWith('audio/')) return true;
  const match = /^u([0-9]+)\//.exec(key);
  if (match) return Number(match[1]) === Number(userId);
  return Number(userId) === 1;
}

// ---------------------------------------------------------------- 确认请求的身份（网关各处共用）

// 录入口令（ACCESS_TOKEN）代表的身份：管理员家庭（1 号用户）。学生由后端按请求头决定，网关用不到
export const AGENT_IDENTITY = { userId: 1, username: 'agent', isAdmin: true, studentId: null, agent: true };

/** 常量时间比较两个字符串。 */
function constantEqual(left, right) {
  if (left.length !== right.length) return false;
  let diff = 0;
  for (let i = 0; i < left.length; i++) diff |= left.charCodeAt(i) ^ right.charCodeAt(i);
  return diff === 0;
}

/** 录入口令是否正确。 */
export function isAgent(request, env) {
  return Boolean(env.ACCESS_TOKEN) && constantEqual(request.headers.get('Authorization') || '', 'Bearer ' + env.ACCESS_TOKEN);
}

/** 只验 Cookie 的签名和过期时间（不查库），给页面请求用：页面本身不带数据。 */
export async function signedIn(request, env) {
  if (isAgent(request, env)) return true;
  return (await parseSession(env.SESSION_SECRET, readSessionCookie(request), Date.now() / 1000)) !== null;
}

/** 确认身份（验签名后再查库：账号没停用、会话版本没变、学生属于这个账号）；没登录返回 null。 */
export async function identify(request, env) {
  if (isAgent(request, env)) return AGENT_IDENTITY;
  const parsed = await parseSession(env.SESSION_SECRET, readSessionCookie(request), Date.now() / 1000);
  if (!parsed) return null;
  return loadIdentity(env, parsed);
}
