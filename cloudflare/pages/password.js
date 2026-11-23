// 密码哈希：PBKDF2-SHA256，只在网关里算（Python 后端在免费计划下 CPU 不够）。
// 存储格式：pbkdf2-sha256$迭代次数$盐(base64)$哈希(base64)，迭代次数写在串里，以后能调高。
// backend/scripts/set_admin_password.py 生成的哈希格式与这里完全相同。

const encoder = new TextEncoder();

// 迭代次数：上线前按计划任务 11 实测，取网关免费计划 CPU 下稳定不超限的最大值
export const PBKDF2_ITERATIONS = 50000;

// 随机密码用的字母表：去掉了容易看错的 0 O 1 l I
const PASSWORD_ALPHABET = 'abcdefghjkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789';

/** 把字节数组转成标准 base64。 */
function toBase64(bytes) {
  let text = '';
  for (const byte of bytes) text += String.fromCharCode(byte);
  return btoa(text);
}

/** 把标准 base64 转回字节数组；格式不对时抛错。 */
function fromBase64(text) {
  const raw = atob(text);
  return Uint8Array.from(raw, (ch) => ch.charCodeAt(0));
}

/** 用给定的盐和迭代次数算出 32 字节的 PBKDF2-SHA256 结果。 */
async function derive(password, salt, iterations) {
  const key = await crypto.subtle.importKey('raw', encoder.encode(password), 'PBKDF2', false, ['deriveBits']);
  const bits = await crypto.subtle.deriveBits({ name: 'PBKDF2', hash: 'SHA-256', salt, iterations }, key, 256);
  return new Uint8Array(bits);
}

/** 常量时间比较两个字节数组（长度不同直接不等）。 */
function sameBytes(left, right) {
  if (left.length !== right.length) return false;
  let diff = 0;
  for (let i = 0; i < left.length; i++) diff |= left[i] ^ right[i];
  return diff === 0;
}

/** 生成新密码的存储串：随机 16 字节盐。 */
export async function hashPassword(password, iterations = PBKDF2_ITERATIONS) {
  const salt = crypto.getRandomValues(new Uint8Array(16));
  const hash = await derive(password, salt, iterations);
  return `pbkdf2-sha256$${iterations}$${toBase64(salt)}$${toBase64(hash)}`;
}

/** 校验密码；存储串格式不对、迭代次数不合理时一律返回 false。 */
export async function verifyPassword(password, stored) {
  try {
    const parts = String(stored || '').split('$');
    if (parts.length !== 4 || parts[0] !== 'pbkdf2-sha256' || !/^[0-9]+$/.test(parts[1])) return false;
    const iterations = Number(parts[1]);
    if (iterations < 1 || iterations > 1000000) return false;
    const salt = fromBase64(parts[2]);
    const expected = fromBase64(parts[3]);
    return sameBytes(await derive(String(password), salt, iterations), expected);
  } catch (error) {
    return false;
  }
}

/** 生成随机密码（默认 12 位），用于管理员开家庭和重置密码。 */
export function randomPassword(length = 12) {
  // 拒绝采样：只用小于字母表长度整数倍的随机数，保证每个字符概率相同
  const limit = 256 - (256 % PASSWORD_ALPHABET.length);
  let result = '';
  while (result.length < length) {
    for (const value of crypto.getRandomValues(new Uint8Array(length * 2))) {
      if (value < limit && result.length < length) result += PASSWORD_ALPHABET[value % PASSWORD_ALPHABET.length];
    }
  }
  return result;
}
