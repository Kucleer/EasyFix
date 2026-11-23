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
