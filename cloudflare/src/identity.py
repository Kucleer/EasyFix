"""登录身份：查库确认 Cookie 里的用户和学生、录入口令的身份、管理员规则、附件归属。

身份是一个字典：{'user_id', 'username', 'is_admin', 'version', 'student_id'}。
guard 确认身份后放进 request.scope['easyfix']，业务代码通过 current_identity / current_student_id 读取。
网关 cloudflare/pages/session.js 里有同样的身份查询和附件归属规则，两边要一起改。
"""

import re

from fastapi import HTTPException

# 一条 SQL 同时确认：用户没删除、没停用、会话版本一致，学生属于这个用户且没删除
IDENTITY_SQL = ('SELECT u.id AS user_id, u.username, u.is_admin, u.session_version AS version, s.id AS student_id '
                'FROM app_user u JOIN student s ON s.user_id=u.id AND s.deleted=0 '
                'WHERE u.id=? AND u.deleted=0 AND u.disabled=0 AND u.session_version=? AND s.id=?')

# 录入口令（ACCESS_TOKEN）代表的用户：管理员家庭
AGENT_USER_ID = 1

# 共用目录：对这些路径（含 /{编号}）的写请求只有管理员能做
SHARED_CATALOG_PATHS = ('/api/subjects', '/api/knowledge-points', '/api/stars/actions', '/api/achievements')
WRITE_METHODS = ('POST', 'PUT', 'PATCH', 'DELETE')


def _identity_from_row(row):
    """把查询结果整理成身份字典。"""
    return {'user_id': int(row['user_id']), 'username': row['username'], 'is_admin': bool(row['is_admin']),
            'version': int(row['version']), 'student_id': int(row['student_id'])}


async def load_identity(db, parsed: dict):
    """按 Cookie 解析结果查库确认身份；查不到（停用、版本过期、学生不属于用户）返回 None。"""
    row = await db.first(IDENTITY_SQL, (parsed['user_id'], parsed['version'], parsed['student_id']))
    return _identity_from_row(row) if row else None


async def agent_identity(db, student_header):
    """录入口令的身份：管理员家庭；请求头指定了学生就校验它属于管理员家庭，否则取排在最前的学生。"""
    if student_header is None or str(student_header).strip() == '':
        row = await db.first(
            'SELECT u.id AS user_id, u.username, u.is_admin, u.session_version AS version, s.id AS student_id '
            'FROM app_user u JOIN student s ON s.user_id=u.id AND s.deleted=0 '
            'WHERE u.id=? AND u.deleted=0 ORDER BY s.sort_order, s.id LIMIT 1', (AGENT_USER_ID,))
    else:
        text = str(student_header).strip()
        if not text.isdigit():
            return None
        row = await db.first(
            'SELECT u.id AS user_id, u.username, u.is_admin, u.session_version AS version, s.id AS student_id '
            'FROM app_user u JOIN student s ON s.user_id=u.id AND s.deleted=0 '
            'WHERE u.id=? AND u.deleted=0 AND s.id=?', (AGENT_USER_ID, int(text)))
    return _identity_from_row(row) if row else None


def current_identity(request) -> dict:
    """读取 guard 确认过的身份；没有身份就报错，宁可失败也不默认成 1 号学生。"""
    identity = request.scope.get('easyfix')
    if not identity:
        raise RuntimeError('缺少登录身份')
    return identity


def require_admin(request) -> None:
    """当前身份不是管理员时抛 403。"""
    if not current_identity(request).get('is_admin'):
        raise HTTPException(403, '只有管理员可以操作')


def admin_only(method: str, path: str) -> bool:
    """判断一个请求是不是只有管理员能做（纯函数，guard 用它统一拦截）。"""
    if path.startswith('/api/admin/') or path == '/api/admin':
        return True
    if path == '/api/config/llm':
        return True
    if method.upper() in WRITE_METHODS:
        return any(path == base or path.startswith(base + '/') for base in SHARED_CATALOG_PATHS)
    return False


def upload_prefix(user_id: int) -> str:
    """新附件的路径前缀，例：upload_prefix(2) -> 'u2/'。"""
    return 'u%d/' % user_id


_USER_PREFIX = re.compile(r'^u([0-9]+)/')


def check_uploads(identity: dict, keys) -> None:
    """提交上来的图片路径都必须属于当前家庭（空值跳过，带 /uploads/ 前缀的先去掉）；有一张不是就 404。"""
    for key in keys:
        if key is None or key == '':
            continue
        if isinstance(key, str) and key.startswith('/uploads/'):
            key = key[len('/uploads/'):]
        if not owns_upload(identity, key):
            raise HTTPException(404, '图片不存在')


def owns_upload(identity: dict, key) -> bool:
    """判断附件是否属于当前用户：audio/ 大家共用；u<编号>/ 属于那个用户；没有前缀的旧附件属于 1 号用户。"""
    if not isinstance(key, str) or not key:
        return False
    if key.startswith('audio/'):
        return True
    match = _USER_PREFIX.match(key)
    if match:
        return int(match.group(1)) == int(identity['user_id'])
    return int(identity['user_id']) == 1
