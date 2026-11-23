// 网关账号相关的测试：密码哈希、会话 Cookie、附件归属、登录接口。
// 运行：node --test cloudflare/pages/auth.test.mjs
import test from 'node:test';
import assert from 'node:assert/strict';
import { hashPassword, verifyPassword, randomPassword } from './password.js';

// 由 Python 小工具 set_admin_password.hash_password('easyfix-test', 1000, bytes(range(16))) 算出，
// 用来确认网关能验证本地小工具写进数据库的哈希。
const PY_VECTOR = 'pbkdf2-sha256$1000$AAECAwQFBgcICQoLDA0ODw==$h+uIQrgeOhECYo94YjQuUuwaRjRLwmeM5apkkoKTHHw=';

test('hashPassword 和 verifyPassword 往返', async () => {
  const stored = await hashPassword('correct horse', 1000);
  assert.match(stored, /^pbkdf2-sha256\$1000\$[A-Za-z0-9+/=]+\$[A-Za-z0-9+/=]+$/);
  assert.equal(await verifyPassword('correct horse', stored), true);
  assert.equal(await verifyPassword('wrong', stored), false);
  assert.equal(await verifyPassword('x', 'garbage'), false);
  assert.equal(await verifyPassword('x', ''), false);
});

test('同一密码两次哈希的盐不同', async () => {
  assert.notEqual(await hashPassword('same', 1000), await hashPassword('same', 1000));
});

test('Python 工具生成的哈希能被网关验证', async () => {
  assert.equal(await verifyPassword('easyfix-test', PY_VECTOR), true);
  assert.equal(await verifyPassword('easyfix-tesT', PY_VECTOR), false);
});

test('randomPassword 长度和字符', () => {
  const p = randomPassword();
  assert.equal(p.length, 12);
  assert.match(p, /^[a-km-np-zA-HJ-NP-Z2-9]+$/);
  assert.notEqual(randomPassword(), randomPassword());
});

// ---------------------------------------------------------------- 会话 Cookie 与附件归属

import { signSession, parseSession, ownsUpload, readSessionCookie, sessionCookieHeader } from './session.js';

// 与后端 accounts_test.py 的 GATEWAY_COOKIE 相同：sign_session('s', 2000000000, 3, 7, 2)
const PY_COOKIE = 'v2.2000000000.3.7.2.50e519e3a6ffed8721c1c634a6296672b1fde44747960929abb1a925631b9160';

test('网关与后端的 Cookie 一致', async () => {
  const cookie = await signSession('s', { expires: 2000000000, userId: 3, studentId: 7, version: 2 });
  assert.equal(cookie, PY_COOKIE);
  assert.deepEqual(await parseSession('s', PY_COOKIE, 1), { expires: 2000000000, userId: 3, studentId: 7, version: 2 });
});

test('parseSession 拒绝坏 Cookie', async () => {
  const cookie = await signSession('s', { expires: 2000000000, userId: 3, studentId: 7, version: 2 });
  assert.equal(await parseSession('other', cookie, 1), null);
  assert.equal(await parseSession('s', cookie, 2000000001), null);
  assert.equal(await parseSession('s', '1999999999.' + 'a'.repeat(64), 1), null);
  assert.equal(await parseSession('', cookie, 1), null);
  assert.equal(await parseSession('s', cookie.replace('.3.7.', '.3.8.'), 1), null);
  assert.equal(await parseSession('s', '', 1), null);
});

test('ownsUpload 与后端规则相同', () => {
  assert.ok(ownsUpload(2, 'u2/2026/11/ab_x.jpg') && ownsUpload(2, 'audio/words/x.mp3'));
  assert.ok(!ownsUpload(2, 'u1/2026/11/ab_x.jpg') && !ownsUpload(2, '2026/11/ab_x.jpg'));
  assert.ok(!ownsUpload(2, 'u22/2026/11/ab_x.jpg'));
  assert.ok(ownsUpload(1, '2026/11/ab_x.jpg') && ownsUpload(1, 'practice_sets/a.pdf'));
  assert.ok(!ownsUpload(1, 'u2/2026/11/ab_x.jpg'));
  assert.ok(!ownsUpload(2, '') && !ownsUpload(2, null));
});

test('读取和写出 Cookie 头', () => {
  const request = new Request('https://easyfix.test/', { headers: { Cookie: 'a=1; easyfix_session=v2.x; b=2' } });
  assert.equal(readSessionCookie(request), 'v2.x');
  assert.equal(readSessionCookie(new Request('https://easyfix.test/')), '');
  assert.equal(sessionCookieHeader('v2.x'),
    'easyfix_session=v2.x; Max-Age=2592000; Path=/; HttpOnly; Secure; SameSite=Strict');
  assert.equal(sessionCookieHeader('', 0), 'easyfix_session=; Max-Age=0; Path=/; HttpOnly; Secure; SameSite=Strict');
});
