"""错题写入、批量入库、筛选项与练习历史接口。

单题保存与批量入库共用同一套知识点解析与写入语句；分类变化时在同一个
D1 batch 内完成版本守卫、旧关联清理、新关联写入和结构断言。
"""

import html
import json
from datetime import datetime, timedelta

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import Response

from database import Database
from knowledge import (
    decorate_question,
    ensure_guard_rows,
    guard_statement,
    link_statements,
    question_links,
    resolve_many,
    structure_statement,
)
from knowledge_model import map_error, normalize_name_key
from knowledge_stats import knowledge_options, validate_filter_ids

router = APIRouter()
FIELDS = {'error_book_id', 'subject_id', 'original_image', 'original_images', 'original_text',
          'parsed_question', 'grade', 'semester', 'answer', 'analysis', 'analysis_image',
          'difficulty', 'error_type', 'wrong_answer', 'question_no'}


def stamp_now():
    """返回与历史数据一致的北京时间文本。"""
    return (datetime.utcnow() + timedelta(hours=8)).isoformat(' ')


def batch_error(error):
    """把 D1 异常映射为固定 HTTP 错误，无法识别时返回 500。"""
    mapped = map_error(error)
    if mapped:
        raise HTTPException(mapped[0], mapped[1])
    text = str(error)
    if 'UNIQUE constraint failed' in text:
        raise HTTPException(409, '数据重复，请刷新后重试')
    raise HTTPException(500, '错题保存失败，请稍后重试')


def parse_review_reasons(text):
    """把库里的核对原因 JSON 文本转成列表；空值或无法解析时返回空列表。"""
    try:
        value = json.loads(text) if text else []
    except (TypeError, ValueError):
        return []
    return value if isinstance(value, list) else []


async def attach_papers(db, rows):
    """给每道题补上 paper 和 review_reasons；所属卷子用一次查询取出，不逐题查询。"""
    paper_ids = sorted({row['paper_id'] for row in rows if row.get('paper_id') is not None})
    papers = {}
    if paper_ids:
        for paper in await db.all(
                'SELECT id,name,paper_type,exam_kind,paper_date FROM paper '
                'WHERE deleted=0 AND id IN (SELECT value FROM json_each(?))', (json.dumps(paper_ids),)):
            papers[paper['id']] = paper
    for row in rows:
        row['paper'] = papers.get(row.get('paper_id'))
        row['review_reasons'] = parse_review_reasons(row.get('review_reasons'))


async def hydrate(db, row):
    """返回兼容前端的图片数组、标签、相似题、两级知识点与所属卷子。"""
    row['original_images'] = json.loads(row.get('original_images') or 'null')
    row['tags'] = await db.all(
        'SELECT t.* FROM tag t JOIN question_tag qt ON qt.tag_id=t.id '
        'WHERE qt.question_id=? AND qt.deleted=0 AND t.deleted=0', (row['id'],))
    row['similar_questions'] = await db.all(
        'SELECT * FROM similar_question WHERE source_question_id=? AND deleted=0', (row['id'],))
    links = (await question_links(db, [row['id']])).get(row['id'], [])
    await attach_papers(db, [row])
    return decorate_question(row, links)


async def validate_common(db, payload, data, old):
    """校验字段范围、学科、错题本、标签与图片，返回学科行。"""
    for key, low, high in [('grade', 1, 12), ('semester', 1, 2), ('difficulty', 1, 5)]:
        if data.get(key) is not None and (type(data[key]) is not int or not low <= data[key] <= high):
            raise HTTPException(422, key + ' 超出范围')
    subject_id = data.get('subject_id', old['subject_id'] if old else None)
    subject = await db.first('SELECT id,name FROM subject WHERE id=? AND deleted=0', (subject_id,))
    if not subject:
        raise HTTPException(400, '学科不存在')
    if data.get('error_book_id') and not await db.first(
            'SELECT id FROM error_book WHERE id=? AND deleted=0 AND subject_id=?',
            (data['error_book_id'], subject_id)):
        raise HTTPException(400, '错题本不存在或学科不匹配')
    tags = payload.get('tag_ids')
    if tags is not None:
        if not isinstance(tags, list) or any(type(tag) is not int for tag in tags):
            raise HTTPException(422, '标签参数无效')
        unique = sorted(set(tags))
        if unique:
            rows = await db.all(
                "SELECT id FROM tag WHERE deleted=0 AND id IN (SELECT value FROM json_each(?))",
                (json.dumps(unique),))
            if len(rows) != len(unique):
                raise HTTPException(400, '标签不存在')
    if 'original_images' in data:
        if data['original_images'] is not None and not isinstance(data['original_images'], list):
            raise HTTPException(422, '图片列表无效')
        data['original_images'] = (json.dumps(data['original_images'], ensure_ascii=False)
                                   if data['original_images'] is not None else None)
    for key in ('parsed_question', 'answer', 'analysis'):
        if isinstance(data.get(key), str):
            data[key] = html.unescape(data[key])
    return subject


async def save(db, payload, question_id=None, request=None):
    """校验后在单个 batch 内保存错题、标签与知识点，返回完整响应。"""
    if not isinstance(payload, dict):
        raise HTTPException(422, '请求必须是对象')
    data = {key: value for key, value in payload.items() if key in FIELDS}
    old = await db.first('SELECT * FROM question WHERE id=? AND deleted=0', (question_id,)) if question_id else None
    if question_id and not old:
        raise HTTPException(404, '错题不存在')
    subject = await validate_common(db, payload, data, old)
    subject_id = subject['id']
    if subject['name'] == '数学' and request is not None:
        from pdf import validate_math
        await validate_math(request, [data.get(key, old.get(key) if old else '') for key in
                                      ('original_text', 'parsed_question', 'answer', 'analysis')])
    old_links = (await question_links(db, [question_id])).get(question_id, []) if old else []
    subject_changed = bool(old) and subject_id != old['subject_id']
    resolved, detail = (await resolve_many(
        db, subject_id, [(payload, old, old_links, subject_changed)]))[0]
    if detail:
        raise HTTPException(422, detail)
    if resolved['changed'] and old:
        expected = payload.get('knowledge_revision')
        if expected is None:
            raise HTTPException(409, '分类已变更，请携带 knowledge_revision 后重试')
        if type(expected) is not int:
            raise HTTPException(422, 'knowledge_revision 参数无效')
        if expected != (old.get('knowledge_revision') or 0):
            raise HTTPException(409, '分类已被其他操作修改，请刷新后重试')
    primary_name = resolved['points'][resolved['primary']]['name'] if resolved['primary'] else None
    if resolved['changed'] or not old:
        data['knowledge_point'] = primary_name
    tags = payload.get('tag_ids')
    stamp = stamp_now()
    if old:
        statements = []
        if resolved['changed']:
            await ensure_guard_rows(db)
            statements.append(guard_statement(
                'EXISTS(SELECT 1 FROM write_guard WHERE id=1 AND deleted=0) AND '
                'COALESCE((SELECT knowledge_revision FROM question WHERE id=? AND deleted=0),-1)=?',
                (question_id, old.get('knowledge_revision') or 0)))
            if subject_changed:
                statements.append((
                    'UPDATE question_knowledge_point SET deleted=1,is_primary=0,updated_at=? '
                    'WHERE question_id=? AND deleted=0', (stamp, question_id)))
        data['updated_at'] = stamp
        statements.append((
            'UPDATE question SET ' + ','.join(key + '=?' for key in data)
            + ',knowledge_revision=knowledge_revision+? WHERE id=? AND deleted=0',
            [*data.values(), 1 if resolved['changed'] else 0, question_id]))
        if resolved['changed']:
            statements += link_statements(question_id, resolved['ids'], resolved['primary'],
                                          resolved['source'], stamp)
            statements.append(structure_statement([question_id]))
        if tags is not None:
            statements.append(('UPDATE question_tag SET deleted=1 WHERE question_id=?', (question_id,)))
            statements += [('INSERT INTO question_tag(question_id,tag_id,deleted) VALUES (?,?,0) '
                            'ON CONFLICT(question_id,tag_id) DO UPDATE SET deleted=0', (question_id, tag))
                           for tag in sorted(set(tags))]
        try:
            await db.batch(statements)
        except Exception as error:
            batch_error(error)
        row = await db.first('SELECT * FROM question WHERE id=? AND deleted=0', (question_id,))
        if row is None:
            raise HTTPException(409, '错题已被删除，请刷新后重试')
        return await hydrate(db, row)
    await ensure_guard_rows(db)
    data = {'difficulty': 3, **data, 'deleted': 0, 'review_count': 0, 'correct_count': 0,
            'error_count': 0, 'knowledge_revision': 0, 'created_at': stamp}
    for attempt in range(2):
        maximum = (await db.first('SELECT COALESCE(MAX(id),0) AS id FROM question'))['id']
        data['id'] = maximum + 1
        fields = list(data)
        statements = [
            guard_statement(
                '(SELECT COALESCE(MAX(id),0) FROM question)=? AND '
                'EXISTS(SELECT 1 FROM write_guard WHERE id=1 AND deleted=0)', (maximum,)),
            ('INSERT INTO question(' + ','.join(fields) + ') VALUES ('
             + ','.join('?' for _ in fields) + ')', list(data.values())),
        ]
        if resolved['ids']:
            statements += link_statements(data['id'], resolved['ids'], resolved['primary'],
                                          resolved['source'], stamp)
            statements.append(structure_statement([data['id']]))
        statements += [('INSERT INTO question_tag(question_id,tag_id,deleted) VALUES (?,?,0)',
                        (data['id'], tag)) for tag in sorted(set(tags or []))]
        try:
            await db.batch(statements)
            break
        except Exception as error:
            mapped = map_error(error)
            if mapped and mapped[0] == 409 and attempt == 0:
                continue
            batch_error(error)
    row = await db.first('SELECT * FROM question WHERE id=? AND deleted=0', (data['id'],))
    return await hydrate(db, row)


@router.post('/api/questions', status_code=201)
async def create(request: Request):
    """创建一条错题，可同时提交两级知识点。"""
    return await save(Database(request.scope['env'].DB), await request.json(), request=request)


@router.get('/api/questions')
async def listing(request: Request, skip: int = Query(0, ge=0), limit: int = Query(20, ge=1, le=100),
                  subject_id: int | None = None, error_book_id: int | None = None,
                  grade: int | None = Query(None, ge=1, le=12), semester: int | None = Query(None, ge=1, le=2),
                  keyword: str | None = None, knowledge_point: str | None = None,
                  knowledge_parent_id: int | None = Query(None, ge=1),
                  knowledge_point_id: int | None = Query(None, ge=1),
                  unclassified: int | None = Query(None, ge=0, le=1),
                  difficulty: str | None = None, error_type: str | None = None,
                  tag_ids: str | None = None, accuracy_range: str | None = None,
                  review_status: str | None = None, paper_id: int | None = Query(None, ge=1)):
    """读取错题分页；知识点筛选走结构化关联，不再依赖文本子串。"""
    db = Database(request.scope['env'].DB)
    await validate_filter_ids(db, subject_id, knowledge_parent_id, knowledge_point_id)
    if unclassified and (knowledge_parent_id is not None or knowledge_point_id is not None or knowledge_point):
        raise HTTPException(422, '未分类筛选不能与具体知识点筛选项同时使用')
    if review_status is not None and review_status not in ('approved', 'pending'):
        raise HTTPException(422, '核对状态只能是 approved 或 pending')
    filters, values = ['q.deleted=0'], []
    for name, value in [('subject_id', subject_id), ('error_book_id', error_book_id),
                        ('grade', grade), ('semester', semester), ('review_status', review_status),
                        ('paper_id', paper_id)]:
        if value is not None:
            filters.append('q.' + name + '=?')
            values.append(value)
    for name, value in [('difficulty', difficulty), ('error_type', error_type)]:
        choices = [part.strip() for part in (value or '').split(',') if part.strip()]
        if choices:
            filters.append('q.' + name + ' IN (' + ','.join('?' for _ in choices) + ')')
            values.extend(choices)
    if keyword:
        filters.append(
            '(instr(q.original_text,?)>0 OR instr(q.parsed_question,?)>0 OR EXISTS('
            'SELECT 1 FROM question_knowledge_point l '
            'JOIN knowledge_point k ON k.id=l.knowledge_point_id AND k.deleted=0 '
            'LEFT JOIN knowledge_point p ON p.id=k.parent_id AND p.deleted=0 '
            'WHERE l.question_id=q.id AND l.deleted=0 '
            'AND (instr(k.name,?)>0 OR instr(COALESCE(p.name,\'\'),?)>0)))')
        values.extend([keyword] * 4)
    if knowledge_parent_id is not None:
        filters.append('EXISTS (SELECT 1 FROM question_knowledge_point l '
                       'JOIN knowledge_point k ON k.id=l.knowledge_point_id AND k.deleted=0 '
                       'WHERE l.question_id=q.id AND l.deleted=0 AND k.level=2 AND k.parent_id=?)')
        values.append(knowledge_parent_id)
    if unclassified:
        filters.append('NOT EXISTS (SELECT 1 FROM question_knowledge_point l '
                       'JOIN knowledge_point k ON k.id=l.knowledge_point_id AND k.deleted=0 '
                       'WHERE l.question_id=q.id AND l.deleted=0 AND k.level=2)')
    if knowledge_point_id is not None:
        filters.append('EXISTS (SELECT 1 FROM question_knowledge_point l '
                       'JOIN knowledge_point k ON k.id=l.knowledge_point_id AND k.deleted=0 '
                       'WHERE l.question_id=q.id AND l.deleted=0 AND k.level=2 AND k.id=?)')
        values.append(knowledge_point_id)
    elif knowledge_point:
        filters.append('EXISTS (SELECT 1 FROM question_knowledge_point l '
                       'JOIN knowledge_point k ON k.id=l.knowledge_point_id AND k.deleted=0 '
                       'WHERE l.question_id=q.id AND l.deleted=0 AND k.level=2 AND k.name_key=?)')
        values.append(normalize_name_key(knowledge_point))
    tags = [int(part) for part in (tag_ids or '').split(',') if part.strip().isdigit()]
    if tags:
        filters.append('EXISTS (SELECT 1 FROM question_tag qt WHERE qt.question_id=q.id AND qt.deleted=0 '
                       'AND qt.tag_id IN (' + ','.join('?' for _ in tags) + '))')
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
    rows = await db.all('SELECT q.* FROM question q WHERE ' + where
                        + ' ORDER BY q.created_at DESC,q.id DESC LIMIT ? OFFSET ?',
                        [*values, limit, skip])
    tag_map, similar_map = {}, {}
    if rows:
        ids = [row['id'] for row in rows]
        marks = ','.join('?' for _ in ids)
        for tag in await db.all('SELECT t.*,qt.question_id FROM tag t JOIN question_tag qt ON qt.tag_id=t.id '
                                'WHERE qt.deleted=0 AND t.deleted=0 AND qt.question_id IN (' + marks + ')', ids):
            tag_map.setdefault(tag.pop('question_id'), []).append(tag)
        for similar in await db.all('SELECT * FROM similar_question WHERE deleted=0 AND source_question_id IN ('
                                    + marks + ')', ids):
            similar_map.setdefault(similar['source_question_id'], []).append(similar)
    link_map = await question_links(db, [row['id'] for row in rows])
    await attach_papers(db, rows)
    for row in rows:
        row['original_images'] = json.loads(row['original_images']) if row['original_images'] else None
        row['tags'] = tag_map.get(row['id'], [])
        row['similar_questions'] = similar_map.get(row['id'], [])
        decorate_question(row, link_map.get(row['id'], []))
    return {'total': total['total'], 'items': rows}


@router.get('/api/questions/{question_id}')
async def detail(question_id: int, request: Request):
    """读取单题详情，返回知识点路径与版本。"""
    db = Database(request.scope['env'].DB)
    row = await db.first('SELECT * FROM question WHERE id=? AND deleted=0', (question_id,))
    if row is None:
        raise HTTPException(404, '错题不存在')
    return await hydrate(db, row)


@router.put('/api/questions/{question_id}')
async def update(question_id: int, request: Request):
    """更新未删除的错题；分类变化必须携带读取时的 knowledge_revision。"""
    return await save(Database(request.scope['env'].DB), await request.json(), question_id, request)


@router.delete('/api/questions/{question_id}', status_code=204)
async def delete(question_id: int, request: Request):
    """软删除错题，保留关联与旧文本以便恢复。"""
    db = Database(request.scope['env'].DB)
    if not await db.first('UPDATE question SET deleted=1 WHERE id=? AND deleted=0 RETURNING id', (question_id,)):
        raise HTTPException(404, '错题不存在')
    return Response(status_code=204)


@router.post('/api/questions/batch')
async def batch(request: Request):
    """预检后在一次事务中批量入库；单题知识点错误只进入该题 errors。"""
    db = Database(request.scope['env'].DB)
    payload = await request.json()
    questions = payload.get('questions', [])
    if not isinstance(questions, list) or len(questions) > 100:
        raise HTTPException(422, '每批最多100题')
    images = payload.get('images', [])
    if not isinstance(images, list) or any(not isinstance(image, str) for image in images):
        raise HTTPException(422, '原图列表无效')
    subject = await db.first('SELECT id,name FROM subject WHERE id=? AND deleted=0', (payload.get('subject_id'),))
    if not subject:
        raise HTTPException(400, '学科不存在')
    if payload.get('error_book_id') and not await db.first(
            'SELECT id FROM error_book WHERE id=? AND subject_id=? AND deleted=0',
            (payload['error_book_id'], subject['id'])):
        raise HTTPException(400, '错题本不存在或学科不匹配')
    for key, high in [('grade', 12), ('semester', 2)]:
        if payload.get(key) is not None and (type(payload[key]) is not int or not 1 <= payload[key] <= high):
            raise HTTPException(422, '年级或学期无效')
    records, errors, texts, entries, indexes = [], [], [], [], []
    for index, item in enumerate(questions):
        if (not isinstance(item, dict) or type(item.get('difficulty', 3)) is not int
                or not 1 <= item.get('difficulty', 3) <= 5):
            errors.append({'index': index, 'detail': '题目格式或难度无效'})
            continue
        record = {key: item.get(key) for key in
                  ('original_text', 'parsed_question', 'answer', 'analysis', 'error_type')}
        if any(value is not None and not isinstance(value, str) for value in record.values()):
            errors.append({'index': index, 'detail': '题目文本字段无效'})
            continue
        for key in ('parsed_question', 'answer', 'analysis'):
            if record[key]:
                record[key] = html.unescape(record[key])
        record.update(difficulty=item.get('difficulty', 3), subject_id=subject['id'],
                      error_book_id=payload.get('error_book_id'), grade=payload.get('grade'),
                      semester=payload.get('semester'), original_image=images[0] if images else None,
                      original_images=json.dumps(images, ensure_ascii=False),
                      knowledge_revision=0, legacy_knowledge_point=None)
        entries.append(({key: item[key] for key in
                         ('knowledge_point_ids', 'primary_knowledge_point_id', 'knowledge_point')
                         if key in item}, None, [], False))
        records.append(record)
        indexes.append(index)
        texts.extend(record.get(key) for key in ('original_text', 'parsed_question', 'answer', 'analysis'))
    if subject['name'] == '数学' and records:
        from pdf import validate_math
        await validate_math(request, texts)
    resolved_list = await resolve_many(db, subject['id'], entries) if entries else []
    valid_records, valid_plans = [], []
    for position, (resolved, detail) in enumerate(resolved_list):
        if detail:
            errors.append({'index': indexes[position], 'detail': detail})
            continue
        valid_records.append(records[position])
        valid_plans.append(resolved)
    errors.sort(key=lambda item: item['index'])
    if not valid_records:
        return {'questions': [], 'total_count': len(questions), 'success_count': 0, 'errors': errors}
    await ensure_guard_rows(db)
    valid_records = [
        {**record, 'knowledge_point': (plan['points'][plan['primary']]['name'] if plan['primary'] else None)}
        for record, plan in zip(valid_records, valid_plans)]
    stamp = stamp_now()
    ids = []
    for attempt in range(2):
        maximum = (await db.first('SELECT COALESCE(MAX(id),0) AS id FROM question'))['id']
        for offset, record in enumerate(valid_records):
            record['id'] = maximum + offset + 1
        ids = [record['id'] for record in valid_records]
        fields = ('id', 'subject_id', 'error_book_id', 'original_image', 'original_images', 'original_text',
                  'parsed_question', 'grade', 'semester', 'answer', 'analysis', 'difficulty', 'error_type',
                  'knowledge_point', 'knowledge_revision', 'legacy_knowledge_point')
        sql = ('INSERT INTO question(' + ','.join(fields) + ',review_count,correct_count,error_count,deleted,created_at) '
               'SELECT ' + ','.join("json_extract(value,'$." + key + "')" for key in fields)
               + ',0,0,0,0,? FROM json_each(?)')
        statements = [guard_statement(
            '(SELECT COALESCE(MAX(id),0) FROM question)=? AND '
            'EXISTS(SELECT 1 FROM write_guard WHERE id=1 AND deleted=0)', (maximum,)),
            (sql, (stamp, json.dumps(valid_records, ensure_ascii=False)))]
        pairs = [{'question_id': record['id'], 'ids': plan['ids'], 'primary': plan['primary']}
                 for record, plan in zip(valid_records, valid_plans) if plan['ids']]
        if pairs:
            statements.append((
                'INSERT INTO question_knowledge_point(question_id,knowledge_point_id,is_primary,source,deleted,created_at,updated_at) '
                "SELECT json_extract(p.value,'$.question_id'),i.value,"
                "CASE WHEN i.value=json_extract(p.value,'$.primary') THEN 1 ELSE 0 END,"
                "'agent',0,?,? FROM json_each(?) p, json_each(json_extract(p.value,'$.ids')) i",
                (stamp, stamp, json.dumps(pairs, ensure_ascii=False))))
            statements.append(structure_statement(ids))
        try:
            await db.batch(statements)
            break
        except Exception as error:
            mapped = map_error(error)
            if mapped and mapped[0] == 409 and attempt == 0:
                continue
            batch_error(error)
    rows = await db.all('SELECT * FROM question WHERE deleted=0 AND id IN ('
                        + ','.join('?' for _ in ids) + ') ORDER BY id', ids)
    link_map = await question_links(db, ids)
    for row in rows:
        row['original_images'] = json.loads(row['original_images'])
        row['tags'] = []
        row['similar_questions'] = []
        decorate_question(row, link_map.get(row['id'], []))
    return {'questions': rows, 'total_count': len(questions), 'success_count': len(rows), 'errors': errors}


@router.put('/api/questions/debug/{question_id}')
async def retired_debug(question_id: int):
    """旧调试入口下线，业务修改使用正式更新接口。"""
    raise HTTPException(410, '调试接口已下线，请使用正式错题更新接口')


@router.get('/api/questions/filter-options/{subject_id}')
async def filters(subject_id: int, request: Request):
    """返回错误类型与目录筛选项，保留旧字段供过渡。"""
    db = Database(request.scope['env'].DB)
    rows = await db.all('SELECT DISTINCT error_type,knowledge_point FROM question WHERE subject_id=? AND deleted=0',
                        (subject_id,))
    types = sorted({part.strip() for row in rows for part in (row['error_type'] or '').split(',') if part.strip()})
    options = await knowledge_options(db, subject_id)
    modules = []
    for option in options:
        if option['level'] == 1:
            modules.append({**option, 'children': []})
    module_map = {module['id']: module for module in modules}
    for option in options:
        if option['level'] == 2 and option['parent_id'] in module_map:
            module_map[option['parent_id']]['children'].append(option)
    return {'error_types': types,
            'knowledge_points': sorted({row['knowledge_point'] for row in rows if row['knowledge_point']}),
            'knowledge_point_options': options,
            'knowledge_modules': modules}


@router.get('/api/questions/{question_id}/practice-history')
async def history(question_id: int, request: Request):
    """读取已批改练习历史。"""
    db = Database(request.scope['env'].DB)
    if not await db.first('SELECT id FROM question WHERE id=? AND deleted=0', (question_id,)):
        raise HTTPException(404, '错题不存在')
    rows = await db.all(
        'SELECT p.id AS practice_set_id,p.name AS practice_set_name,p.created_at AS date,pq.is_correct '
        'FROM practice_set_question pq JOIN practice_set p ON p.id=pq.practice_set_id '
        'WHERE pq.deleted=0 AND pq.question_id=? AND pq.is_correct IS NOT NULL AND p.deleted=0 '
        'ORDER BY p.created_at DESC', (question_id,))
    for row in rows:
        row['is_correct'] = bool(row['is_correct'])
    return rows
