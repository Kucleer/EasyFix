"""登录身份校验（guard）、当前账号信息与切换学生；跟密码有关的接口都在网关 cloudflare/pages/ 里。"""

import hmac
import time
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, RedirectResponse
from database import Database
from identity import admin_only, agent_identity, current_identity, load_identity
from session import SESSION_SECONDS, parse_session, sign_session

router = APIRouter()


async def resolve_identity(request):
    """确认请求的身份：录入口令走管理员家庭，否则验 Cookie 再查库；返回 (身份或 None, 是否录入口令)。"""
    env = request.scope['env']
    token = str(getattr(env, 'ACCESS_TOKEN', ''))
    if token and hmac.compare_digest(request.headers.get('authorization', ''), 'Bearer ' + token):
        return await agent_identity(Database(env.DB), request.headers.get('x-easyfix-student')), True
    parsed = parse_session(str(getattr(env, 'SESSION_SECRET', '')), request.cookies.get('easyfix_session', ''), time.time())
    if parsed is None:
        return None, False
    return await load_identity(Database(env.DB), parsed), False


async def maintenance_enabled(request):
    """读取 D1 维护写开关；读取失败按维护中处理，避免默认放行写入。"""
    try:
        row = await Database(request.scope['env'].DB).first(
            "SELECT value FROM runtime_config WHERE name='write_maintenance' AND deleted=0")
    except Exception:
        return True
    if row is None:
        return False
    return str(row.get('value')).strip().lower() in ('1', 'true', 'on', 'yes')


async def guard(request, call_next):
    """统一保护应用、API 和附件：确认身份、管理员规则、维护开关、来源检查与统计缓存。"""
    path = request.url.path
    if path == '/health':
        return await call_next(request)
    identity, is_agent = await resolve_identity(request)
    if identity is None:
        if path.startswith(('/api/', '/uploads/')):
            return JSONResponse({'detail': '需要登录'}, status_code=401)
        return RedirectResponse('/login', status_code=303)
    # 下游通过 identity.current_identity / question_scope.current_student_id 读取
    request.scope['easyfix'] = identity
    request.scope['easyfix_agent'] = is_agent
    if admin_only(request.method, path) and not identity['is_admin']:
        return JSONResponse({'detail': '只有管理员可以操作'}, status_code=403)
    migration_agent = is_agent
    ready=str(getattr(request.scope['env'],'MIGRATION_READY','')).lower()=='true'
    if not ready and not migration_agent and request.method not in ('GET','HEAD','OPTIONS'):
        return JSONResponse({'detail':'云端正在迁移验证，请暂时继续使用原入口'},status_code=503)
    if request.method not in ('GET', 'HEAD', 'OPTIONS') and await maintenance_enabled(request):
        # 维护开关覆盖 Bearer（Agent）写入；只读请求、健康检查和登录不受影响。
        return JSONResponse({'detail': '系统维护中，请稍后再试'}, status_code=503)
    origin = request.headers.get('origin')
    if request.method not in ('GET', 'HEAD', 'OPTIONS') and origin and origin != str(request.url).split(request.url.path, 1)[0]:
        return JSONResponse({'detail': '请求来源无效'}, status_code=403)
    from cache import lookup,remember,invalidate
    from fastapi.responses import Response
    cached,key=await lookup(request)
    if cached is not None:
        return Response(cached[0],media_type=cached[1],headers={'Cache-Control':'private, no-store','X-Easyfix-Cache':'hit'})
    try:
        response = await call_next(request)
    except Exception as error:
        from knowledge_model import map_error
        mapped = map_error(error)
        if mapped:
            return JSONResponse({'detail': mapped[1]}, status_code=mapped[0])
        return JSONResponse({'detail':'云端处理失败，请稍后重试'},status_code=500)
    if key is not None and response.status_code==200:
        body=b''.join([chunk async for chunk in response.body_iterator])
        media_type=response.headers.get('content-type','application/json').split(';')[0]
        remember(key,body,media_type)
        response=Response(body,status_code=response.status_code,headers=dict(response.headers))
    # 整页识别的推进、改草稿、去掉等请求不改错题库，不清缓存；只有录入、撤回才清
    from scan_model import changes_library
    scan_only = request.url.path.startswith('/api/scan/') and not changes_library(request.method, request.url.path)
    # 周报推进只写周报表，页面会循环调用，不清统计缓存、不记操作日志
    if request.method not in ('GET','HEAD','OPTIONS') and 200<=response.status_code<300 and request.url.path not in ('/api/intake/papers/check','/api/weekly-reports/advance') and not scan_only:
        await invalidate(request)
    response.headers['Cache-Control'] = 'private, no-store'
    return response




def _session_cookie(response, value):
    """给响应写上会话 Cookie（与网关 sessionCookieHeader 相同的属性）。"""
    response.set_cookie('easyfix_session', value, httponly=True, secure=True, samesite='strict',
                        max_age=SESSION_SECONDS, path='/')
    return response


async def family_students(db, user_id):
    """一个家庭的学生列表（没删除的，按排序），每项 {'id', 'name'}。"""
    rows = await db.all('SELECT id, name FROM student WHERE user_id=? AND deleted=0 ORDER BY sort_order, id', (user_id,))
    return [{'id': int(row['id']), 'name': row['name']} for row in rows]


@router.get('/api/auth/me')
async def me(request: Request):
    """当前账号：登录名、名字、是否管理员、当前学生和本家庭全部学生。"""
    identity = current_identity(request)
    db = Database(request.scope['env'].DB)
    user = await db.first('SELECT name FROM app_user WHERE id=?', (identity['user_id'],))
    students = await family_students(db, identity['user_id'])
    current = next((item for item in students if item['id'] == identity['student_id']), None)
    return {'username': identity['username'], 'name': user['name'] if user else '', 'is_admin': identity['is_admin'],
            'student': current, 'students': students}


@router.post('/api/auth/switch-student')
async def switch_student(request: Request):
    """切换到本家庭的另一个学生：重新签发 Cookie（版本不变，有效期重新算 30 天）。"""
    if request.scope.get('easyfix_agent'):
        return JSONResponse({'detail': '录入口令不能切换学生'}, status_code=400)
    identity = current_identity(request)
    payload = await request.json()
    student_id = payload.get('student_id') if isinstance(payload, dict) else None
    if not isinstance(student_id, int) or isinstance(student_id, bool):
        return JSONResponse({'detail': '记录不存在'}, status_code=404)
    db = Database(request.scope['env'].DB)
    row = await db.first('SELECT id FROM student WHERE id=? AND user_id=? AND deleted=0', (student_id, identity['user_id']))
    if row is None:
        return JSONResponse({'detail': '记录不存在'}, status_code=404)
    secret = str(getattr(request.scope['env'], 'SESSION_SECRET', ''))
    value = sign_session(secret, int(time.time()) + SESSION_SECONDS, identity['user_id'], student_id, identity['version'])
    return _session_cookie(JSONResponse({'success': True}), value)
