"""共享密码登录和签名会话；图片与业务接口共用 HttpOnly Cookie。"""

import base64
import hashlib
import hmac
import time
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

router = APIRouter()
LOGIN = '''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>登录 EasyFix</title><style>body{margin:0;min-height:100vh;display:grid;place-items:center;background:#f5f7fb;font:16px system-ui;color:#243149}main{width:min(320px,80vw);padding:32px;background:white;border-radius:16px;box-shadow:0 12px 40px #24314912}h1{margin-top:0}label{display:block;margin-bottom:12px}input,button{box-sizing:border-box;width:100%;padding:12px;border:1px solid #cbd5e1;border-radius:8px;font:inherit}button{margin-top:16px;color:white;background:#3468df;border:0;cursor:pointer}#error{color:#b42318;min-height:24px}</style><main><h1>EasyFix</h1><p>登录后继续整理错题和练习。</p><form id="login"><label for="password">访问密码</label><input id="password" type="password" autocomplete="current-password" required autofocus><button>登录</button><p id="error" role="alert"></p></form></main><script>document.getElementById('login').onsubmit=async e=>{e.preventDefault();const b=e.target.querySelector('button');b.disabled=true;try{const r=await fetch('/api/auth/verify-password',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({password:document.getElementById('password').value})});if(r.ok)location.replace('/');else document.getElementById('error').textContent='密码不正确，请重试。'}catch{document.getElementById('error').textContent='连接失败，请稍后重试。'}finally{b.disabled=false}};</script></html>'''


def valid_session(request):
    """验证会话过期时间和签名，令牌不包含用户数据。"""
    env = request.scope['env']
    secret = str(getattr(env, 'SESSION_SECRET', ''))
    bearer = str(getattr(env, 'ACCESS_TOKEN', ''))
    if bearer and hmac.compare_digest(request.headers.get('authorization', ''), 'Bearer ' + bearer):
        return True
    token = request.cookies.get('easyfix_session', '')
    try:
        expires, signature = token.split('.', 1)
        expected = hmac.new(secret.encode(), expires.encode(), hashlib.sha256).hexdigest()
        return bool(secret) and int(expires) > time.time() and hmac.compare_digest(signature, expected)
    except (ValueError, TypeError):
        return False


async def guard(request, call_next):
    """统一保护应用、API 和附件，并校验浏览器写入来源。"""
    path = request.url.path
    if path in ('/health', '/login', '/api/auth/verify-password'):
        return await call_next(request)
    if not valid_session(request):
        if path.startswith(('/api/', '/uploads/')):
            return JSONResponse({'detail': '需要登录'}, status_code=401)
        return RedirectResponse('/login', status_code=303)
    migration_agent=request.headers.get('authorization','')=='Bearer '+str(getattr(request.scope['env'],'ACCESS_TOKEN',''))
    ready=str(getattr(request.scope['env'],'MIGRATION_READY','')).lower()=='true'
    if not ready and not migration_agent and request.method not in ('GET','HEAD','OPTIONS'):
        return JSONResponse({'detail':'云端正在迁移验证，请暂时继续使用原入口'},status_code=503)
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
    except Exception:
        return JSONResponse({'detail':'云端处理失败，请稍后重试'},status_code=500)
    if key is not None and response.status_code==200:
        body=b''.join([chunk async for chunk in response.body_iterator])
        media_type=response.headers.get('content-type','application/json').split(';')[0]
        remember(key,body,media_type)
        response=Response(body,status_code=response.status_code,headers=dict(response.headers))
    if request.method not in ('GET','HEAD','OPTIONS') and 200<=response.status_code<300 and request.url.path!='/api/stats/analysis/llm':
        await invalidate(request)
    response.headers['Cache-Control'] = 'private, no-store'
    return response


@router.get('/login')
async def login_page():
    """显示共享密码登录页面。"""
    return HTMLResponse(LOGIN, headers={'Cache-Control': 'no-store'})


@router.get('/api/auth/session')
async def session():
    """由统一中间件校验后向前端网关返回登录状态。"""
    return {'authenticated': True}


@router.post('/api/auth/verify-password')
async def login(request: Request):
    """验证已配置密码，签发一天有效的 HttpOnly 会话。"""
    env = request.scope['env']
    password = str(getattr(env, 'ACCESS_PASSWORD', ''))
    secret = str(getattr(env, 'SESSION_SECRET', ''))
    if not password or not secret:
        return JSONResponse({'detail': '登录尚未配置'}, status_code=503)
    payload = await request.json()
    supplied = payload.get('password', '') if isinstance(payload, dict) else ''
    if not isinstance(supplied, str) or not hmac.compare_digest(supplied.encode(), password.encode()):
        return JSONResponse({'detail': '密码错误'}, status_code=401)
    expires = str(int(time.time()) + 86400)
    signature = hmac.new(secret.encode(), expires.encode(), hashlib.sha256).hexdigest()
    response = JSONResponse({'success': True})
    response.set_cookie('easyfix_session', expires + '.' + signature, httponly=True, secure=True, samesite='strict', max_age=86400, path='/')
    return response
