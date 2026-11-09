"""错题写入、批量入库、筛选项与练习历史接口。"""

import html
import json
from datetime import datetime,timedelta
from fastapi import APIRouter, HTTPException, Request
from database import Database

router = APIRouter()
FIELDS = {'error_book_id', 'subject_id', 'original_image', 'original_images', 'original_text', 'parsed_question', 'grade', 'semester', 'answer', 'analysis', 'analysis_image', 'difficulty', 'error_type', 'knowledge_point'}


async def hydrate(db, row):
    """返回兼容前端的图片数组、标签和相似题。"""
    row['original_images'] = json.loads(row.get('original_images') or 'null')
    row['tags'] = await db.all('SELECT t.* FROM tag t JOIN question_tag qt ON qt.tag_id=t.id WHERE qt.question_id=? AND qt.deleted=0 AND t.deleted=0', (row['id'],))
    row['similar_questions'] = await db.all('SELECT * FROM similar_question WHERE source_question_id=? AND deleted=0', (row['id'],))
    return row


async def save(db, payload, question_id=None, request=None):
    """校验字段、关联和学段后保存，保持 LaTeX 反斜杠原样。"""
    if not isinstance(payload, dict):
        raise HTTPException(422, '请求必须是对象')
    data = {key: value for key, value in payload.items() if key in FIELDS}
    old = await db.first('SELECT * FROM question WHERE id=? AND deleted=0', (question_id,)) if question_id else None
    if question_id and not old:
        raise HTTPException(404, '错题不存在')
    for key, low, high in [('grade', 1, 12), ('semester', 1, 2), ('difficulty', 1, 5)]:
        if data.get(key) is not None and (type(data[key]) is not int or not low <= data[key] <= high):
            raise HTTPException(422, key + ' 超出范围')
    subject_id = data.get('subject_id', old['subject_id'] if old else None)
    subject=await db.first('SELECT id,name FROM subject WHERE id=? AND deleted=0', (subject_id,))
    if not subject:
        raise HTTPException(400, '学科不存在')
    if data.get('error_book_id') and not await db.first('SELECT id FROM error_book WHERE id=? AND deleted=0 AND subject_id=?', (data['error_book_id'], subject_id)):
        raise HTTPException(400, '错题本不存在或学科不匹配')
    tags = payload.get('tag_ids')
    if tags is not None:
        if not isinstance(tags, list) or any(type(tag) is not int for tag in tags):
            raise HTTPException(422, '标签参数无效')
        for tag in set(tags):
            if not await db.first('SELECT id FROM tag WHERE id=? AND deleted=0', (tag,)):
                raise HTTPException(400, '标签不存在')
    if 'original_images' in data:
        if data['original_images'] is not None and not isinstance(data['original_images'], list):
            raise HTTPException(422, '图片列表无效')
        data['original_images'] = json.dumps(data['original_images'], ensure_ascii=False) if data['original_images'] is not None else None
    for key in ('parsed_question', 'answer', 'analysis'):
        if isinstance(data.get(key), str):
            data[key] = html.unescape(data[key])
    if subject['name']=='数学' and request is not None:
        from pdf import validate_math
        await validate_math(request,[data.get(key,old.get(key) if old else '') for key in ('original_text','parsed_question','answer','analysis')])
    now = (datetime.utcnow()+timedelta(hours=8)).isoformat(' ')
    if old:
        data['updated_at'] = now
        row = await db.first('UPDATE question SET ' + ','.join(key + '=?' for key in data) + ' WHERE id=? AND deleted=0 RETURNING *', [*data.values(), question_id])
    else:
        data = {'difficulty': 3, **data, 'deleted': 0, 'review_count': 0, 'correct_count': 0, 'error_count': 0, 'created_at': now}
        row = await db.first('INSERT INTO question(' + ','.join(data) + ') VALUES (' + ','.join('?' for _ in data) + ') RETURNING *', list(data.values()))
    if tags is not None:
        statements = [('UPDATE question_tag SET deleted=1 WHERE question_id=?', (row['id'],))]
        statements += [('INSERT INTO question_tag(question_id,tag_id,deleted) VALUES (?,?,0) ON CONFLICT(question_id,tag_id) DO UPDATE SET deleted=0', (row['id'], tag)) for tag in set(tags)]
        await db.batch(statements)
    return await hydrate(db, row)


@router.post('/api/questions', status_code=201)
async def create(request: Request):
    """创建一条错题。"""
    return await save(Database(request.scope['env'].DB), await request.json(), request=request)


@router.put('/api/questions/{question_id}')
async def update(question_id: int, request: Request):
    """更新未删除的错题。"""
    return await save(Database(request.scope['env'].DB), await request.json(), question_id, request)


@router.delete('/api/questions/{question_id}', status_code=204)
async def delete(question_id: int, request: Request):
    """软删除错题。"""
    db = Database(request.scope['env'].DB)
    if not await db.first('UPDATE question SET deleted=1 WHERE id=? AND deleted=0 RETURNING id', (question_id,)):
        raise HTTPException(404, '错题不存在')
    from fastapi.responses import Response
    return Response(status_code=204)


@router.post('/api/questions/batch')
async def batch(request: Request):
    """预检后在一次事务中批量入库，保留原图与公式，不推断学段。"""
    db = Database(request.scope['env'].DB)
    payload = await request.json()
    questions = payload.get('questions', [])
    if not isinstance(questions, list) or len(questions) > 100:
        raise HTTPException(422, '每批最多100题')
    images = payload.get('images', [])
    if not isinstance(images,list) or any(not isinstance(image,str) for image in images):raise HTTPException(422,'原图列表无效')
    subject=await db.first('SELECT id,name FROM subject WHERE id=? AND deleted=0',(payload.get('subject_id'),))
    if not subject:raise HTTPException(400,'学科不存在')
    if payload.get('error_book_id') and not await db.first('SELECT id FROM error_book WHERE id=? AND subject_id=? AND deleted=0',(payload['error_book_id'],subject['id'])):raise HTTPException(400,'错题本不存在或学科不匹配')
    for key,high in [('grade',12),('semester',2)]:
        if payload.get(key) is not None and (type(payload[key]) is not int or not 1<=payload[key]<=high):raise HTTPException(422,'年级或学期无效')
    records,errors,texts=[],[],[]
    for index,item in enumerate(questions):
        if not isinstance(item,dict) or type(item.get('difficulty',3)) is not int or not 1<=item.get('difficulty',3)<=5:
            errors.append({'index':index,'detail':'题目格式或难度无效'});continue
        record={key:item.get(key) for key in ('original_text','parsed_question','answer','analysis','error_type','knowledge_point')}
        if any(value is not None and not isinstance(value,str) for value in record.values()):errors.append({'index':index,'detail':'题目文本字段无效'});continue
        for key in ('parsed_question','answer','analysis'):
            if record[key]:record[key]=html.unescape(record[key])
        record.update(difficulty=item.get('difficulty',3),subject_id=subject['id'],error_book_id=payload.get('error_book_id'),grade=payload.get('grade'),semester=payload.get('semester'),original_image=images[0] if images else None,original_images=json.dumps(images,ensure_ascii=False))
        records.append(record);texts.extend(record.get(key) for key in ('original_text','parsed_question','answer','analysis'))
    if not records:return {'questions':[],'total_count':len(questions),'success_count':0,'errors':errors}
    if subject['name']=='数学':
        from pdf import validate_math
        await validate_math(request,texts)
    stamp=(datetime.utcnow()+timedelta(hours=8)).isoformat(' ')
    for attempt in range(2):
        maximum=(await db.first('SELECT COALESCE(MAX(id),0) AS id FROM question'))['id']
        for index,record in enumerate(records):record['id']=maximum+index+1
        fields=('id','subject_id','error_book_id','original_image','original_images','original_text','parsed_question','grade','semester','answer','analysis','difficulty','error_type','knowledge_point')
        sql='INSERT INTO question('+','.join(fields)+',review_count,correct_count,error_count,deleted,created_at) SELECT '+','.join("json_extract(value,'$."+key+"')" for key in fields)+',0,0,0,0,? FROM json_each(?)'
        try:
            await db.batch([('UPDATE write_guard SET revision=CASE WHEN (SELECT COALESCE(MAX(id),0) FROM question)=? THEN revision+1 ELSE NULL END WHERE id=1',(maximum,)),(sql,(stamp,json.dumps(records,ensure_ascii=False)))])
            break
        except Exception:
            if attempt:raise HTTPException(409,'题目正在并发更新，请重试本批次')
    rows=await db.all('SELECT * FROM question WHERE id>? AND id<=? AND deleted=0 ORDER BY id',(maximum,maximum+len(records)))
    for row in rows:row['original_images']=json.loads(row['original_images']);row['tags']=[];row['similar_questions']=[]
    return {'questions':rows,'total_count':len(questions),'success_count':len(rows),'errors':errors}


@router.put('/api/questions/debug/{question_id}')
async def retired_debug(question_id:int):
    """旧调试入口下线，业务修改使用正式更新接口。"""
    raise HTTPException(410,'调试接口已下线，请使用正式错题更新接口')


@router.get('/api/questions/filter-options/{subject_id}')
async def filters(subject_id: int, request: Request):
    """返回该学科的去重错误类型和知识点。"""
    rows = await Database(request.scope['env'].DB).all('SELECT DISTINCT error_type,knowledge_point FROM question WHERE subject_id=? AND deleted=0', (subject_id,))
    types = sorted({part.strip() for row in rows for part in (row['error_type'] or '').split(',') if part.strip()})
    return {'error_types': types, 'knowledge_points': sorted({row['knowledge_point'] for row in rows if row['knowledge_point']})}


@router.get('/api/questions/{question_id}/practice-history')
async def history(question_id: int, request: Request):
    """读取已批改练习历史。"""
    db = Database(request.scope['env'].DB)
    if not await db.first('SELECT id FROM question WHERE id=? AND deleted=0', (question_id,)):
        raise HTTPException(404, '错题不存在')
    rows = await db.all('SELECT p.id AS practice_set_id,p.name AS practice_set_name,p.created_at AS date,pq.is_correct FROM practice_set_question pq JOIN practice_set p ON p.id=pq.practice_set_id WHERE pq.deleted=0 AND pq.question_id=? AND pq.is_correct IS NOT NULL AND p.deleted=0 ORDER BY p.created_at DESC', (question_id,))
    for row in rows:
        row['is_correct'] = bool(row['is_correct'])
    return rows
