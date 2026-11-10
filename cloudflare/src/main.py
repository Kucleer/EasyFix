"""EasyFix 的 Cloudflare 入口；接口适配期间默认不开放公共路由。"""

import hmac
import json
from fastapi import FastAPI, HTTPException, Request, Query, UploadFile, File
from workers import asgi
from database import Database
from auth import guard, router as auth_router
from catalog import router as catalog_router
from knowledge import router as knowledge_router
from questions import router as questions_router
from word_focus import router as word_focus_router
from words import router as words_router
from readings import router as readings_router
from settings import router as settings_router
from analytics import router as analytics_router
from motivation import router as motivation_router
from practices import router as practices_router
from review import router as review_router
from reports import router as reports_router
from similar import router as similar_router
from media import router as media_router

app = FastAPI(title='EasyFix Cloudflare', docs_url=None, redoc_url=None, openapi_url=None)
Default = asgi.entrypoint(app)


app.middleware('http')(guard)
app.include_router(auth_router)
app.include_router(motivation_router)
app.include_router(practices_router)
app.include_router(review_router)
app.include_router(reports_router)
app.include_router(similar_router)
app.include_router(media_router)
app.include_router(catalog_router)
app.include_router(knowledge_router)
app.include_router(questions_router)
app.include_router(word_focus_router)
app.include_router(words_router)
app.include_router(readings_router)
app.include_router(settings_router)
app.include_router(analytics_router)


@app.get('/health')
async def health(request: Request):
    """提供不包含业务数据的存活检查。"""
    return {'status': 'ok', 'service': 'easyfix', 'migration_complete': str(getattr(request.scope['env'], 'MIGRATION_READY', '')).lower() == 'true'}


@app.get('/api/subjects')
async def subjects(request: Request):
    """读取未删除的学科。"""
    return await Database(request.scope['env'].DB).all('SELECT * FROM subject WHERE deleted=0 ORDER BY id')


@app.post('/api/upload/file')
async def upload_file(request: Request, file: UploadFile = File(...)):
    """将原图写入私有 R2，保持原来的年月路径格式。"""
    from datetime import datetime,timedelta
    from uuid import uuid4
    from pyodide.ffi import to_js
    from js import Object
    allowed = {'image/jpeg', 'image/png', 'image/webp', 'image/jpg'}
    if file.content_type not in allowed:
        raise HTTPException(400, '不支持的文件类型')
    content = await file.read(10 * 1024 * 1024 + 1)
    if not content or len(content) > 10 * 1024 * 1024:
        raise HTTPException(400, '图片为空或超过10MB限制')
    filename = (file.filename or 'image').replace('/', '_').replace('\\', '_')
    key = (datetime.utcnow()+timedelta(hours=8)).strftime('%Y/%m/') + uuid4().hex[:8] + '_' + filename
    metadata = to_js({'httpMetadata': {'contentType': file.content_type}}, dict_converter=Object.fromEntries)
    await request.scope['env'].IMAGES.put(key, to_js(content), metadata)
    return {'path': key, 'original_filename': file.filename, 'size': len(content)}


@app.get('/uploads/{key:path}')
async def image(key: str, request: Request):
    """鉴权后读取私有附件，拒绝路径穿越和任意 HTML 内容。"""
    from fastapi.responses import Response
    from js import Uint8Array
    if not key or any(part in ('', '.', '..') for part in key.split('/')) or '\\' in key:
        raise HTTPException(400, '附件路径无效')
    obj = await request.scope['env'].IMAGES.get(key)
    if obj is None:
        raise HTTPException(404, '附件不存在')
    content = Uint8Array.new(await obj.arrayBuffer()).to_py().tobytes()
    content_type = getattr(obj.httpMetadata, 'contentType', None) or 'application/octet-stream'
    if content_type not in ('image/jpeg', 'image/png', 'image/webp', 'image/jpg','application/pdf','audio/mpeg','audio/wav'):
        content_type = 'application/octet-stream'
    return Response(content, media_type=content_type, headers={'Cache-Control': 'private, max-age=86400', 'X-Content-Type-Options': 'nosniff'})
