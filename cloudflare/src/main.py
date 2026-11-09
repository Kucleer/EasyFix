"""EasyFix 的 Cloudflare 入口；接口适配期间默认不开放公共路由。"""

import hmac
import json
from fastapi import FastAPI, HTTPException, Request, Query, UploadFile, File
from workers import asgi
from database import Database
from auth import guard, router as auth_router
from catalog import router as catalog_router
from questions import router as questions_router
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
app.include_router(questions_router)
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


@app.get('/api/questions/{question_id}')
async def question(question_id: int, request: Request):
    """读取错题及其标签和相似题，保留公式原始文本。"""
    db = Database(request.scope['env'].DB)
    row = await db.first('SELECT * FROM question WHERE id=? AND deleted=0', (question_id,))
    if row is None:
        raise HTTPException(404, '错题不存在')
    row['original_images'] = json.loads(row['original_images']) if row['original_images'] else None
    row['tags'] = await db.all('SELECT t.* FROM tag t JOIN question_tag qt ON qt.tag_id=t.id WHERE qt.question_id=? AND qt.deleted=0 AND t.deleted=0', (question_id,))
    row['similar_questions'] = await db.all('SELECT * FROM similar_question WHERE source_question_id=? AND deleted=0', (question_id,))
    return row


@app.get('/api/questions')
async def questions(request: Request, skip: int = Query(0, ge=0), limit: int = Query(20, ge=1, le=100),
                    subject_id: int | None = None, error_book_id: int | None = None,
                    grade: int | None = Query(None, ge=1, le=12), semester: int | None = Query(None, ge=1, le=2),
                    keyword: str | None = None, knowledge_point: str | None = None,
                    difficulty: str | None = None, error_type: str | None = None,
                    tag_ids: str | None = None, accuracy_range: str | None = None):
    """读取错题分页，兼容现有搜索、多选及正确率筛选参数。"""
    db = Database(request.scope['env'].DB)
    filters = ['q.deleted=0']
    values = []
    for name, value in [('subject_id', subject_id), ('error_book_id', error_book_id), ('grade', grade), ('semester', semester)]:
        if value is not None:
            filters.append('q.' + name + '=?')
            values.append(value)
    for name, value in [('difficulty', difficulty), ('error_type', error_type)]:
        choices = [part.strip() for part in (value or '').split(',') if part.strip()]
        if choices:
            filters.append('q.' + name + ' IN (' + ','.join('?' for _ in choices) + ')')
            values.extend(choices)
    if keyword:
        filters.append('(instr(q.original_text,?)>0 OR instr(q.parsed_question,?)>0 OR instr(q.knowledge_point,?)>0)')
        values.extend([keyword] * 3)
    if knowledge_point:
        filters.append('instr(q.knowledge_point,?)>0')
        values.append(knowledge_point)
    tags = [int(part) for part in (tag_ids or '').split(',') if part.strip().isdigit()]
    if tags:
        filters.append('EXISTS (SELECT 1 FROM question_tag qt WHERE qt.question_id=q.id AND qt.deleted=0 AND qt.tag_id IN (' + ','.join('?' for _ in tags) + '))')
        values.extend(tags)
    if accuracy_range == 'none':
        filters.append('q.correct_count+q.error_count=0')
    elif accuracy_range:
        try:
            low, high = [int(part) / 100 for part in accuracy_range.split('-')]
        except ValueError:
            raise HTTPException(422, '正确率筛选格式错误')
        filters.append('(q.correct_count*1.0/NULLIF(q.correct_count+q.error_count,0)) BETWEEN ? AND ?')
        values.extend([low, high])
    where = ' AND '.join(filters)
    total = await db.first('SELECT COUNT(*) AS total FROM question q WHERE ' + where, values)
    rows = await db.all('SELECT q.* FROM question q WHERE ' + where + ' ORDER BY q.created_at DESC,q.id DESC LIMIT ? OFFSET ?', [*values, limit, skip])
    tag_map,similar_map={},{}
    if rows:
        ids=[row['id'] for row in rows]
        marks=','.join('?' for _ in ids)
        for tag in await db.all('SELECT t.*,qt.question_id FROM tag t JOIN question_tag qt ON qt.tag_id=t.id WHERE qt.deleted=0 AND t.deleted=0 AND qt.question_id IN ('+marks+')',ids):
            tag_map.setdefault(tag.pop('question_id'),[]).append(tag)
        for similar in await db.all('SELECT * FROM similar_question WHERE deleted=0 AND source_question_id IN ('+marks+')',ids):
            similar_map.setdefault(similar['source_question_id'],[]).append(similar)
    for row in rows:
        row['original_images'] = json.loads(row['original_images']) if row['original_images'] else None
        row['tags'] = tag_map.get(row['id'],[])
        row['similar_questions'] = similar_map.get(row['id'],[])
    return {'total': total['total'], 'items': rows}


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
