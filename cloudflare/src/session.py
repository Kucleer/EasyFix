"""会话 Cookie 的签发与解析；格式与网关 cloudflare/pages/session.js 完全相同。

Cookie 值：v2.<过期秒>.<用户编号>.<学生编号>.<会话版本>.<签名hex>
签名 = HMAC-SHA256(SESSION_SECRET, "v2.<过期秒>.<用户编号>.<学生编号>.<会话版本>")
只做纯计算，不查数据库；账号是否停用、版本是否过期由 identity.load_identity 查库确认。
"""

import hashlib
import hmac

SESSION_SECONDS = 2592000   # 30 天
COOKIE_NAME = 'easyfix_session'


def _signature(secret: str, body: str) -> str:
    """算出签名（十六进制小写）。"""
    return hmac.new(secret.encode(), body.encode(), hashlib.sha256).hexdigest()


def sign_session(secret: str, expires: int, user_id: int, student_id: int, version: int) -> str:
    """签发 Cookie 值（不带 easyfix_session= 前缀）。"""
    body = 'v2.%d.%d.%d.%d' % (expires, user_id, student_id, version)
    return body + '.' + _signature(secret, body)


def parse_session(secret: str, token: str, now: float):
    """解析并验证 Cookie 值；签名不对、过期、不是 v2 格式、密钥为空时返回 None。

    返回 {'expires', 'user_id', 'student_id', 'version'}，四个都是整数。
    """
    if not secret or not isinstance(token, str):
        return None
    parts = token.split('.')
    if len(parts) != 6 or parts[0] != 'v2' or not all(part.isdigit() for part in parts[1:5]):
        return None
    body = '.'.join(parts[:5])
    if not hmac.compare_digest(parts[5], _signature(secret, body)):
        return None
    expires, user_id, student_id, version = (int(part) for part in parts[1:5])
    if expires <= now:
        return None
    return {'expires': expires, 'user_id': user_id, 'student_id': student_id, 'version': version}
