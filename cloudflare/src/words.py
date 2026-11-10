"""单词管理、筛选和记忆曲线的 D1 实现。"""

import json
import random
from datetime import datetime, timedelta
from fastapi import APIRouter, HTTPException, Query, Request
from database import Database
from phrase_focus import entry_type_of, normalize_english, validate_focus_spec

router = APIRouter(prefix='/api/words')

ENTRY_TYPES = ('word', 'phrase')
FOCUS_STATUSES = ('none', 'draft', 'confirmed')


def default_dictation_level(entry_type):
    """词组从档位 1 开始，单词保持档位 3。"""
    return 1 if entry_type == 'phrase' else 3


def parse_focus_spec(text):
    """把库里的标注 JSON 文本解析成对象，空值或损坏时返回 None。"""
    if not text:
        return None
    try:
        return json.loads(text)
    except (TypeError, ValueError):
        return None


def level(row):
    """沿用已有正确率分级。"""
    count = row.get('review_count') or 0
    accuracy = (row.get('correct_count') or 0) / count * 100 if count else 0
    return accuracy, 'new' if not count else 'weak' if accuracy == 0 else 'learning' if accuracy <= 60 else 'good' if accuracy <= 80 else 'mastered'


async def decorate(db, row):
    """补充标签和正确率字段。"""
    row['accuracy'], row['accuracy_level'] = level(row)
    row['focus_spec'] = parse_focus_spec(row.get('focus_spec'))
    row['tags'] = await db.all('SELECT t.* FROM tag t JOIN word_tag wt ON wt.tag_id=t.id WHERE wt.word_id=? AND wt.deleted=0 AND t.deleted=0', (row['id'],))
    return row


async def decorate_many(db,rows):
    """合并标签读取，避免每个单词产生一次数据库调用。"""
    tags={}
    for offset in range(0,len(rows),90):
        ids=[row['id'] for row in rows[offset:offset+90]]
        if not ids:continue
        for tag in await db.all('SELECT t.*,wt.word_id FROM tag t JOIN word_tag wt ON wt.tag_id=t.id WHERE t.deleted=0 AND wt.deleted=0 AND wt.word_id IN ('+','.join('?' for _ in ids)+')',ids):
            tags.setdefault(tag.pop('word_id'),[]).append(tag)
    for row in rows:
        row['accuracy'],row['accuracy_level']=level(row)
        row['focus_spec']=parse_focus_spec(row.get('focus_spec'))
        row['tags']=tags.get(row['id'],[])
    return rows


@router.get('')
async def listing(request: Request, skip: int = Query(0, ge=0), limit: int = Query(20, ge=1, le=1000)):
    """按学段、标签、关键词和正确率筛选单词。"""
    return await list_words(Database(request.scope['env'].DB), request.query_params, skip, limit)


async def list_words(db, params, skip, limit):
    """列表查询的数据库实现，params 为带 get 方法的查询参数。"""
    filters, values = ['w.deleted=0'], []
    # 词条类型与标注状态筛选，非法取值与其他筛选一致地忽略
    if params.get('entry_type') in ENTRY_TYPES:
        filters.append('w.entry_type=?')
        values.append(params['entry_type'])
    if params.get('focus_status') in FOCUS_STATUSES:
        filters.append('w.focus_status=?')
        values.append(params['focus_status'])
    for key in ('grade', 'semester'):
        if params.get(key):
            filters.append('w.' + key + '=?')
            values.append(int(params[key]))
    if params.get('keyword'):
        filters.append('(instr(w.english,?)>0 OR instr(w.chinese,?)>0)')
        values.extend([params['keyword']] * 2)
    tags = [int(value) for value in params.get('tag_ids', '').split(',') if value.strip().isdigit()]
    if tags:
        filters.append('EXISTS(SELECT 1 FROM word_tag wt WHERE wt.word_id=w.id AND wt.deleted=0 AND wt.tag_id IN (' + ','.join('?' for _ in tags) + '))')
        values.extend(tags)
    accuracy='COALESCE(w.correct_count*100.0/NULLIF(w.review_count,0),0)'
    levels={'new':'COALESCE(w.review_count,0)=0','weak':'w.review_count>0 AND '+accuracy+'=0','learning':'w.review_count>0 AND '+accuracy+'>0 AND '+accuracy+'<=60','good':accuracy+'>60 AND '+accuracy+'<=80','mastered':accuracy+'>80'}
    if params.get('accuracy_level') in levels:filters.append('('+levels[params['accuracy_level']]+')')
    for key,operator in [('accuracy_min','>='),('accuracy_max','<=')]:
        if params.get(key):filters.append(accuracy+operator+'?');values.append(float(params[key]))
    order={'accuracy':accuracy,'review_count':'COALESCE(w.review_count,0)'}.get(params.get('sort_by'),'w.created_at')
    direction='DESC' if params.get('sort_order','desc')=='desc' else 'ASC'
    where=' AND '.join(filters)
    total=await db.first('SELECT COUNT(*) AS total FROM word w WHERE '+where,values)
    rows=await db.all('SELECT w.* FROM word w WHERE '+where+' ORDER BY '+order+' '+direction+',w.id '+direction+' LIMIT ? OFFSET ?',[*values,limit,skip])
    return {'total':total['total'],'items':await decorate_many(db,rows)}


@router.get('/stats/summary')
async def stats(request: Request):
    """统计单词、练习场次、复习日志及到期情况。"""
    return await word_stats(Database(request.scope['env'].DB))


def type_summary(rows, entry_type):
    """用已加载的行汇总某类词条的数量与正确率，无复习时正确率为 0。"""
    selected = [row for row in rows if (row.get('entry_type') or 'word') == entry_type]
    reviews = sum(row['review_count'] or 0 for row in selected)
    corrects = sum(row['correct_count'] or 0 for row in selected)
    accuracy = round(corrects / reviews * 100, 1) if reviews else 0
    return {'total': len(selected), 'accuracy': accuracy}


async def word_stats(db):
    """统计的数据库实现。"""
    rows = await db.all('SELECT * FROM word WHERE deleted=0')
    logs = await db.first('SELECT COUNT(*) AS total,SUM(is_correct) AS correct,SUM(date(reviewed_at)=date(?,"+8 hours")) AS today FROM word_review_log WHERE deleted=0', (datetime.utcnow().isoformat(' '),))
    sessions = await db.first('SELECT COUNT(*) AS total FROM word_review_session s LEFT JOIN practice_set p ON p.id=s.practice_set_id WHERE s.deleted=0 AND (s.practice_set_id IS NULL OR p.deleted=0)')
    now = datetime.utcnow() + timedelta(hours=8)
    mastered = sum((row['review_count'] or 0) >= 5 and level(row)[0] >= 90 for row in rows)
    new = sum(not row['review_count'] for row in rows)
    due = sum(bool(row['next_review_at']) and datetime.fromisoformat(row['next_review_at']) <= now for row in rows)
    distribution = {}
    for row in rows:
        if row['grade'] is not None:
            distribution[str(row['grade'])] = distribution.get(str(row['grade']), 0) + 1
    return {'total_words': len(rows), 'total_reviews': sessions['total'], 'total_correct': logs['correct'] or 0,
            'accuracy': round((logs['correct'] or 0) / logs['total'] * 100, 1) if logs['total'] else 0,
            'mastered_words': mastered, 'new_words': new, 'learning_words': len(rows) - mastered - new,
            'grade_distribution': distribution, 'review_today': logs['today'] or 0, 'due_words': due, 'to_review_count': new + due,
            'by_type': {entry_type: type_summary(rows, entry_type) for entry_type in ENTRY_TYPES}}


@router.get('/errors')
async def errors(request: Request, skip: int = Query(0, ge=0), limit: int = Query(20, ge=1, le=1000)):
    """返回有复习记录且正确率低于60%的单词。"""
    db = Database(request.scope['env'].DB)
    rows = await db.all('SELECT w.* FROM word w JOIN word_review_log l ON l.word_id=w.id AND l.deleted=0 WHERE w.deleted=0 AND w.review_count>0 GROUP BY w.id HAVING AVG(l.is_correct)<0.6 ORDER BY w.review_count DESC')
    return {'total': len(rows), 'items': await decorate_many(db,rows[skip:skip + limit])}


@router.get('/{word_id}/memory-curve')
async def curve(word_id: int, request: Request):
    """读取真实复习日志和记忆阶段。"""
    db = Database(request.scope['env'].DB)
    row = await db.first('SELECT * FROM word WHERE id=? AND deleted=0', (word_id,))
    if not row:
        raise HTTPException(404, '单词不存在')
    history = await db.all('SELECT reviewed_at,is_correct,user_answer FROM word_review_log WHERE word_id=? AND deleted=0 ORDER BY reviewed_at DESC', (word_id,))
    for log in history:
        log['is_correct'] = bool(log['is_correct'])
    return {'word_id': word_id, 'learning_phase': row['learning_phase'] or '新学', 'interval': row['interval'] or 1, 'next_review_at': row['next_review_at'], 'review_history': history}


@router.get('/{word_id}')
async def detail(word_id: int, request: Request):
    """读取单词详情。"""
    db = Database(request.scope['env'].DB)
    row = await db.first('SELECT * FROM word WHERE id=? AND deleted=0', (word_id,))
    if not row:
        raise HTTPException(404, '单词不存在')
    return await decorate(db, row)


async def save(db, payload, word_id=None):
    """校验并保存单词及标签，所有移除均使用软删除。"""
    fields = {'english', 'chinese', 'phonetic', 'grade', 'semester'}
    data = {key: value for key, value in payload.items() if key in fields}
    old = await db.first('SELECT * FROM word WHERE id=? AND deleted=0', (word_id,)) if word_id else None
    if word_id and not old:
        raise HTTPException(404, '单词不存在')
    for key in ('english', 'chinese'):
        if (not old or key in data) and (not isinstance(data.get(key), str) or not data[key].strip()):
            raise HTTPException(422, key + ' 不能为空')
    for key, high in [('grade', 12), ('semester', 2)]:
        if data.get(key) is not None and (type(data[key]) is not int or not 1 <= data[key] <= high):
            raise HTTPException(422, '年级或学期无效')
    tags = payload.get('tag_ids')
    if tags is not None:
        if not isinstance(tags, list) or any(type(tag) is not int for tag in tags):
            raise HTTPException(422, '标签参数无效')
        for tag in set(tags):
            if not await db.first('SELECT id FROM tag WHERE id=? AND deleted=0', (tag,)):
                raise HTTPException(400, '标签不存在')
    requested_type = payload.get('entry_type')
    if requested_type is not None and requested_type not in ENTRY_TYPES:
        raise HTTPException(422, '词条类型只能是 word 或 phrase')
    now = (datetime.utcnow() + timedelta(hours=8)).isoformat(' ')
    data['updated_at'] = now
    # 重点标注：用更新后的英文校验，任何写库之前完成，失败时原记录不变
    english = data['english'] if 'english' in data else old['english']
    if payload.get('focus_spec') is not None:
        try:
            checked_spec = validate_focus_spec(payload['focus_spec'], english)
        except ValueError as error:
            raise HTTPException(422, str(error))
        data['focus_spec'] = json.dumps(checked_spec, ensure_ascii=False)
        data['focus_status'] = 'confirmed'
        data['focus_updated_at'] = now
    elif old and 'english' in data and normalize_english(data['english']) != normalize_english(old['english']):
        # 英文真的改了（只是空白不同不算）：标注失效，但内容保留
        data['focus_status'] = 'none'
    if requested_type is not None:
        data['entry_type'] = requested_type
    if old:
        row = await db.first('UPDATE word SET ' + ','.join(key + '=?' for key in data) + ' WHERE id=? AND deleted=0 RETURNING *', [*data.values(), word_id])
    else:
        # 新建时类型默认按英文判断，档位由类型决定
        data.setdefault('entry_type', entry_type_of(english))
        data.setdefault('focus_status', 'none')
        data['dictation_level'] = default_dictation_level(data['entry_type'])
        data.update(deleted=0, created_at=now, review_count=0, correct_count=0, ease_factor=250, interval=1, learning_phase='新学')
        row = await db.first('INSERT INTO word(' + ','.join(data) + ') VALUES (' + ','.join('?' for _ in data) + ') RETURNING *', list(data.values()))
    if tags is not None:
        statements = [('UPDATE word_tag SET deleted=1 WHERE word_id=?', (row['id'],))]
        statements += [('INSERT INTO word_tag(word_id,tag_id,deleted) VALUES (?,?,0) ON CONFLICT(word_id,tag_id) DO UPDATE SET deleted=0', (row['id'], tag)) for tag in set(tags)]
        await db.batch(statements)
    return await decorate(db, row)


@router.post('', status_code=201)
async def create(request: Request):
    """创建文本单词。"""
    return await save(Database(request.scope['env'].DB), await request.json())


@router.post('/batch')
async def batch(request: Request):
    """用一次事务批量写入 TXT、CSV 单词，避免每词多次调用 D1。"""
    return await import_words(Database(request.scope['env'].DB), await request.json())


def check_import_item(word, payload, valid_tags):
    """校验批量导入的一条记录，返回 (字段, 标签列表, 是否有效)。"""
    keys = ('english', 'chinese', 'phonetic', 'grade', 'semester')
    data = {key: word.get(key) for key in keys} if isinstance(word, dict) else {}
    # 单条没有填写年级、学期时沿用整批的设置
    data['grade'] = data.get('grade') or payload.get('grade')
    data['semester'] = data.get('semester') or payload.get('semester')
    if isinstance(word, dict):
        tags = word.get('tag_ids') or payload.get('tag_ids') or []
    else:
        tags = []
    english, chinese = data.get('english'), data.get('chinese')
    valid = isinstance(english, str) and 0 < len(english.strip()) <= 200
    valid = valid and isinstance(chinese, str) and bool(chinese.strip())
    for key, high in (('grade', 12), ('semester', 2)):
        valid = valid and (data.get(key) is None or (type(data[key]) is int and 1 <= data[key] <= high))
    valid = valid and isinstance(tags, list)
    valid = valid and all(type(tag) is int and tag in valid_tags for tag in tags)
    # 词条类型可选，给了就必须是 word 或 phrase
    if valid and isinstance(word, dict) and word.get('entry_type') is not None:
        valid = word['entry_type'] in ENTRY_TYPES
    return data, tags, valid


async def import_words(db, payload):
    """批量导入的数据库实现；标注不合法的条目照常导入，并在结果里带 focus_error。"""
    words = payload.get('words', [])
    if not isinstance(words, list) or len(words) > 1000:
        raise HTTPException(422, '每批最多1000词')
    valid_tags = {row['id'] for row in await db.all('SELECT id FROM tag WHERE deleted=0')}
    records, results = [], []
    for word in words:
        data, tags, valid = check_import_item(word, payload, valid_tags)
        if not valid:
            results.append({'english': data.get('english'), 'success': False, 'error': '单词字段、学段或标签无效'})
            continue
        entry_type = word.get('entry_type') or entry_type_of(data['english'])
        record = {
            **data,
            'tags': list(set(tags)),
            'position': len(results),
            'entry_type': entry_type,
            'dictation_level': default_dictation_level(entry_type),
            'focus_spec': None,
            'focus_status': 'none',
            'focus_updated_at': None,
        }
        result = {'english': data['english'], 'success': True}
        if word.get('focus_spec') is not None:
            try:
                checked_spec = validate_focus_spec(word['focus_spec'], data['english'])
                record['focus_spec'] = json.dumps(checked_spec, ensure_ascii=False)
                record['focus_status'] = 'confirmed'
            except ValueError as error:
                result['focus_error'] = str(error)
        records.append(record)
        results.append(result)
    if not records:
        return {'success_count': 0, 'fail_count': len(results), 'results': results}
    stamp = (datetime.utcnow() + timedelta(hours=8)).isoformat(' ')
    for record in records:
        if record['focus_status'] == 'confirmed':
            record['focus_updated_at'] = stamp
    insert_sql = (
        "INSERT INTO word(id,english,chinese,phonetic,grade,semester,review_count,correct_count,"
        "ease_factor,interval,learning_phase,deleted,created_at,updated_at,"
        "entry_type,focus_spec,focus_status,focus_updated_at,dictation_level) "
        "SELECT json_extract(value,'$.id'),json_extract(value,'$.english'),json_extract(value,'$.chinese'),"
        "json_extract(value,'$.phonetic'),json_extract(value,'$.grade'),json_extract(value,'$.semester'),"
        "0,0,250,1,'新学',0,?,?,"
        "json_extract(value,'$.entry_type'),json_extract(value,'$.focus_spec'),"
        "json_extract(value,'$.focus_status'),json_extract(value,'$.focus_updated_at'),"
        "json_extract(value,'$.dictation_level') FROM json_each(?)"
    )
    for attempt in range(2):
        # 用写入保护行保证并发时 id 区间没有被别人占用，冲突则整批重试一次
        maximum = (await db.first('SELECT COALESCE(MAX(id),0) AS id FROM word'))['id']
        links = []
        for index, record in enumerate(records):
            record['id'] = maximum + index + 1
            results[record['position']]['id'] = record['id']
            links.extend({'word': record['id'], 'tag': tag} for tag in record['tags'])
        packed = json.dumps(records, ensure_ascii=False)
        statements = [
            ('UPDATE write_guard SET revision=CASE WHEN (SELECT COALESCE(MAX(id),0) FROM word)=? THEN revision+1 ELSE NULL END WHERE id=1', (maximum,)),
            (insert_sql, (stamp, stamp, packed)),
        ]
        if links:
            statements.append((
                "INSERT INTO word_tag(word_id,tag_id,deleted) SELECT json_extract(value,'$.word'),json_extract(value,'$.tag'),0 FROM json_each(?)",
                (json.dumps(links),),
            ))
        try:
            await db.batch(statements)
            break
        except Exception:
            if attempt:
                raise HTTPException(409, '单词正在并发更新，请重试本批次')
    return {'success_count': len(records), 'fail_count': len(results) - len(records), 'results': results}


@router.put('/{word_id}')
async def update(word_id: int, request: Request):
    """更新单词。"""
    return await save(Database(request.scope['env'].DB), await request.json(), word_id)


@router.delete('/{word_id}', status_code=204)
async def delete(word_id: int, request: Request):
    """软删除单词。"""
    if not await Database(request.scope['env'].DB).first('UPDATE word SET deleted=1 WHERE id=? AND deleted=0 RETURNING id', (word_id,)):
        raise HTTPException(404, '单词不存在')
    from fastapi.responses import Response
    return Response(status_code=204)
