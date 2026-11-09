"""阅读理解短文与配套题的云端接口。"""

from datetime import datetime, timedelta
from fastapi import APIRouter, HTTPException, Query, Request
from database import Database
from settings import generate_json
from provenance import PROVENANCE

router = APIRouter(prefix='/api/readings')
TOPICS = ['校园生活','家庭生活','日常生活','兴趣爱好','科技发展','环境保护','文化艺术','体育运动','健康与医疗','旅行与地理','节日与习俗','历史人物','未来职业','人际交往','饮食文化','动物与自然']
Q_FIELDS = ('question_number', 'question_text', 'option_a', 'option_b', 'option_c', 'option_d', 'correct_answer', 'explanation')


async def decorate(db, row):
    """加载未删除的配套选择题。"""
    row['questions'] = await db.all('SELECT * FROM reading_question WHERE passage_id=? AND deleted=0 ORDER BY question_number', (row['id'],))
    row['deleted'] = bool(row['deleted'])
    row['provenance']=PROVENANCE.get(row['source'])
    return row


@router.get('/topics')
async def topics():
    """返回现有话题列表。"""
    return TOPICS


@router.get('')
async def listing(request: Request, skip: int = Query(0, ge=0), limit: int = Query(20, ge=1, le=100), topic: str | None = None, grade: int | None = Query(None, ge=1, le=12), difficulty: int | None = Query(None, ge=1, le=5)):
    """分页筛选短文。"""
    db = Database(request.scope['env'].DB)
    filters, values = ['deleted=0'], []
    for key, value in [('topic', topic), ('grade', grade), ('difficulty', difficulty)]:
        if value is not None:
            filters.append(key + '=?')
            values.append(value)
    where = ' AND '.join(filters)
    count = await db.first('SELECT COUNT(*) AS total FROM reading_passage WHERE ' + where, values)
    rows = await db.all('SELECT * FROM reading_passage WHERE ' + where + ' ORDER BY created_at DESC,id DESC LIMIT ? OFFSET ?', [*values, limit, skip])
    return {'total': count['total'], 'items': [await decorate(db, row) for row in rows]}


@router.get('/{reading_id}')
async def detail(reading_id: int, request: Request):
    """读取短文与题目详情。"""
    db = Database(request.scope['env'].DB)
    row = await db.first('SELECT * FROM reading_passage WHERE id=? AND deleted=0', (reading_id,))
    if not row:
        raise HTTPException(404, '短文不存在')
    return await decorate(db, row)


async def save(request, payload):
    """校验全部配套题后创建短文，避免补猜缺少的答案。"""
    for key in ('title', 'content', 'topic'):
        if not isinstance(payload.get(key), str) or not payload[key].strip():
            raise HTTPException(422, key + ' 不能为空')
    if type(payload.get('grade')) is not int or not 1 <= payload['grade'] <= 12:
        raise HTTPException(422, '年级无效')
    questions = payload.get('questions', [])
    if not isinstance(questions, list) or not 1 <= len(questions) <= 4:
        raise HTTPException(422, '需要1至4道配套题')
    for question in questions:
        if any(not question.get(key) for key in Q_FIELDS[:-1]) or question['correct_answer'] not in ('A', 'B', 'C', 'D'):
            raise HTTPException(422, '题目、选项或答案缺失')
    db = Database(request.scope['env'].DB)
    data = {key: payload[key] for key in ('title', 'content', 'topic', 'grade')}
    data.update(difficulty=payload.get('difficulty', 3), word_count=payload.get('word_count') or len(payload['content'].split()), source=payload.get('source', 'manual'), deleted=0, created_at=(datetime.utcnow()+timedelta(hours=8)).isoformat(' '))
    row = await db.first('INSERT INTO reading_passage(' + ','.join(data) + ') VALUES (' + ','.join('?' for _ in data) + ') RETURNING *', list(data.values()))
    await db.batch([('INSERT INTO reading_question(passage_id,' + ','.join(Q_FIELDS) + ',deleted,created_at) VALUES (' + ','.join('?' for _ in range(11)) + ')', [row['id'], *[question.get(key) for key in Q_FIELDS], 0, data['created_at']]) for question in questions])
    return await decorate(db, row)


@router.post('', status_code=201)
async def create(request: Request):
    """手动创建阅读理解。"""
    return await save(request, await request.json())


@router.post('/generate', status_code=201)
async def generate(request: Request):
    """按明确指定的学段和话题生成短文与四道题。"""
    payload = await request.json()
    if type(payload.get('grade')) is not int or not 1 <= payload['grade'] <= 12:
        raise HTTPException(422, '请选择年级')
    result = await generate_json(request, '请生成适合' + str(payload['grade']) + '年级、话题为' + str(payload.get('topic', '校园生活')) + '、难度' + str(payload.get('difficulty', 3)) + '的英语阅读理解。返回JSON对象，包含title,content,questions。questions恰好4题，每题包含question_number,question_text,option_a,option_b,option_c,option_d,correct_answer(A-D),explanation。')
    return await save(request, {**result, 'grade': payload['grade'], 'topic': payload.get('topic', '校园生活'), 'difficulty': payload.get('difficulty', 3), 'source': 'generated'})


@router.put('/{reading_id}')
async def update(reading_id: int, request: Request):
    """更新现有短文信息。"""
    await detail(reading_id, request)
    payload = await request.json()
    data = {key: value for key, value in payload.items() if key in ('title', 'topic', 'grade', 'difficulty')}
    if data:
        await Database(request.scope['env'].DB).run('UPDATE reading_passage SET ' + ','.join(key + '=?' for key in data) + ' WHERE id=? AND deleted=0', [*data.values(), reading_id])
    return await detail(reading_id, request)


@router.delete('/{reading_id}', status_code=204)
async def delete(reading_id: int, request: Request):
    """软删除短文，不删除原始题目。"""
    await detail(reading_id, request)
    await Database(request.scope['env'].DB).run('UPDATE reading_passage SET deleted=1 WHERE id=?', (reading_id,))
    from fastapi.responses import Response
    return Response(status_code=204)
