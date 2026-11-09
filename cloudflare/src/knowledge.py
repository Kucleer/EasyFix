"""两级知识点目录：树、CRUD、引用保护与题目关联读写。

目录写入与 taxonomy_version 递增在同一 D1 batch 内完成；引用约束由
0081 迁移中的触发器在事务内兜底，应用层先检查以返回可读错误。
"""

import json
from datetime import datetime, timedelta
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import Response

from database import Database
from knowledge_model import (
    build_tree,
    clean_name,
    map_error,
    normalize_id_list,
    normalize_name_key,
    projection_name,
)

router = APIRouter()


def now_stamp():
    """返回与现有数据一致的北京时间文本。"""
    return (datetime.utcnow() + timedelta(hours=8)).isoformat(' ')


def raise_http(error):
    """把 D1 异常映射为固定状态的 HTTP 错误，识别失败时返回 500。"""
    mapped = map_error(error)
    if mapped:
        raise HTTPException(mapped[0], mapped[1])
    text = str(error)
    if 'UNIQUE constraint failed' in text:
        raise HTTPException(409, '同级已存在同名或同编码的知识点')
    raise HTTPException(500, '知识点操作失败，请稍后重试')


async def taxonomy_version(db):
    """读取目录版本号；缺失时按 0 处理，不阻断只读请求。"""
    row = await db.first("SELECT value FROM runtime_config WHERE name='taxonomy_version' AND deleted=0")
    return str(row['value']) if row else '0'


def bump_taxonomy():
    """构造与目录写入同批次的目录版本与统计版本递增语句。"""
    return [
        ("INSERT INTO runtime_config(name,value,deleted,updated_at) VALUES('taxonomy_version','1',0,CURRENT_TIMESTAMP) "
         "ON CONFLICT(name) DO UPDATE SET value=CAST(CAST(runtime_config.value AS INTEGER)+1 AS TEXT),"
         "deleted=0,updated_at=excluded.updated_at", ()),
        ("UPDATE runtime_config SET value=CAST(CAST(value AS INTEGER)+1 AS TEXT) "
         "WHERE name='data_revision' AND deleted=0", ()),
    ]


def guard_statement(condition, parameters=()):
    """构造事务内断言；条件不满足时触发器抛出 KP_GUARD。"""
    return (
        'UPDATE knowledge_assert SET guard=CASE WHEN (' + condition + ') THEN 1 ELSE NULL END WHERE id=1',
        parameters,
    )


def structure_statement(question_ids):
    """断言每道题“有有效关联则恰好一个主考点，无关联则没有主考点”。"""
    packed = json.dumps([int(item) for item in question_ids])
    condition = (
        'NOT EXISTS(SELECT 1 FROM json_each(?) j WHERE '
        '(SELECT COUNT(*) FROM question_knowledge_point l WHERE l.question_id=j.value '
        'AND l.deleted=0 AND l.is_primary=1) <> '
        'CASE WHEN EXISTS(SELECT 1 FROM question_knowledge_point l2 '
        'WHERE l2.question_id=j.value AND l2.deleted=0) THEN 1 ELSE 0 END)'
    )
    return ('UPDATE knowledge_assert SET structure=CASE WHEN (' + condition + ') THEN 1 ELSE NULL END WHERE id=1',
            (packed,))


async def ensure_guard_rows(db):
    """守卫行缺失时失败关闭，避免条件 UPDATE 匹配 0 行后继续写入。"""
    row = await db.first(
        'SELECT (SELECT COUNT(*) FROM write_guard WHERE id=1 AND deleted=0) AS guard,'
        '(SELECT COUNT(*) FROM knowledge_assert WHERE id=1) AS assertion')
    if not row or not row['guard'] or not row['assertion']:
        raise HTTPException(503, '知识点写入守卫缺失，请暂停业务写入并联系维护人员')


async def load_points(db, ids):
    """一次查询读取多个知识点，避免逐 ID 查询。"""
    ids = [int(item) for item in ids]
    if not ids:
        return {}
    rows = await db.all(
        "SELECT * FROM knowledge_point WHERE deleted=0 AND id IN "
        "(SELECT value FROM json_each(?))",
        (json.dumps(ids),))
    return {row['id']: row for row in rows}


async def validate_links(db, subject_id, ids, primary_id, require_primary=True):
    """校验题目关联目标：必须存在、未删除、为二级且与题目同学科。"""
    points = await load_points(db, ids)
    for point_id in ids:
        point = points.get(point_id)
        if point is None:
            raise HTTPException(422, '知识点不存在或已删除')
        if point.get('level') != 2:
            raise HTTPException(422, '只能关联二级知识点')
        if point.get('subject_id') != subject_id:
            raise HTTPException(422, '知识点必须与题目同学科')
    if ids:
        if primary_id is None:
            if require_primary:
                raise HTTPException(422, '请为所选知识点指定一个主考点')
        elif type(primary_id) is not int or primary_id not in ids:
            raise HTTPException(422, '主考点必须是已选知识点之一')
    elif primary_id is not None:
        raise HTTPException(422, '未选择知识点时不能指定主考点')
    return points


async def resolve_legacy(db, subject_id, text):
    """把旧文本精确映射到同学科唯一二级；歧义或未知时返回 422。"""
    key = normalize_name_key(text)
    rows = await db.all(
        'SELECT * FROM knowledge_point WHERE subject_id=? AND deleted=0 AND level=2 AND name_key=?',
        (subject_id, key))
    if len(rows) == 1:
        return rows[0]
    if not rows:
        raise HTTPException(422, '知识点“' + str(text) + '”不在目录中，请从列表选择')
    raise HTTPException(422, '知识点“' + str(text) + '”存在多个同名二级，请从列表选择')


async def question_links(db, question_ids):
    """批量装配题目的二级知识点及一级上下文。"""
    ids = [int(item) for item in question_ids]
    if not ids:
        return {}
    rows = await db.all(
        'SELECT l.question_id,l.is_primary,k.id,k.name,k.parent_id,p.name AS parent_name,'
        'k.subject_id,k.level FROM question_knowledge_point l '
        'JOIN knowledge_point k ON k.id=l.knowledge_point_id AND k.deleted=0 '
        'LEFT JOIN knowledge_point p ON p.id=k.parent_id AND p.deleted=0 '
        "WHERE l.deleted=0 AND k.level=2 AND l.question_id IN "
        "(SELECT value FROM json_each(?)) "
        'ORDER BY l.question_id,l.is_primary DESC,k.sort_order,k.id',
        (json.dumps(ids),))
    grouped = {}
    for row in rows:
        grouped.setdefault(row.pop('question_id'), []).append(row)
    return grouped


def decorate_question(row, links):
    """统一写入题目响应的分类字段，兼容投影只输出主考点名。"""
    row['knowledge_points'] = links
    row['knowledge_point'] = projection_name(links)
    row['legacy_knowledge_point'] = row.get('legacy_knowledge_point')
    row['knowledge_revision'] = row.get('knowledge_revision') or 0
    return row


def link_statements(question_id, ids, primary_id, source, stamp, clear_only=False):
    """构造题目关联的软删除、恢复与主考点写入语句。"""
    statements = []
    if clear_only or not ids:
        statements.append((
            'UPDATE question_knowledge_point SET deleted=1,is_primary=0,updated_at=? '
            'WHERE question_id=? AND deleted=0', (stamp, question_id)))
    else:
        marks = ','.join('?' for _ in ids)
        statements.append((
            'UPDATE question_knowledge_point SET deleted=1,is_primary=0,updated_at=? '
            'WHERE question_id=? AND deleted=0 AND knowledge_point_id NOT IN (' + marks + ')',
            (stamp, question_id, *ids)))
    statements.append((
        'UPDATE question_knowledge_point SET is_primary=0 WHERE question_id=? AND is_primary=1 AND deleted=0',
        (question_id,)))
    for point_id in [] if clear_only else ids:
        statements.append((
            'INSERT INTO question_knowledge_point(question_id,knowledge_point_id,is_primary,source,deleted,created_at,updated_at) '
            'VALUES(?,?,0,?,0,?,?) ON CONFLICT(question_id,knowledge_point_id) '
            'DO UPDATE SET deleted=0,is_primary=0,source=excluded.source,updated_at=excluded.updated_at',
            (question_id, point_id, source, stamp, stamp)))
    if primary_id is not None and not clear_only:
        statements.append((
            'UPDATE question_knowledge_point SET is_primary=1,updated_at=? '
            'WHERE question_id=? AND knowledge_point_id=? AND deleted=0',
            (stamp, question_id, primary_id)))
    return statements


def plan_knowledge(payload, old_row, old_links, subject_changed):
    """按 4.3 规则解析知识点字段，返回期望状态与是否变化。

    该函数不访问数据库，由调用方先解析旧字段文本，再校验目标。
    """
    old_ids = sorted(point['id'] for point in old_links)
    old_primary = next((point['id'] for point in old_links if point.get('is_primary')), None)
    current = projection_name(old_links)
    has_new = 'knowledge_point_ids' in payload
    plan = {'has_new': has_new, 'legacy': payload.get('knowledge_point'),
            'ids': old_ids, 'primary': old_primary, 'source': 'manual',
            'old_links': old_links, 'subject_changed': bool(subject_changed)}
    if has_new:
        ids = normalize_id_list(payload.get('knowledge_point_ids'))
        if ids is None:
            raise HTTPException(422, '知识点参数无效')
        primary = payload.get('primary_knowledge_point_id')
        if ids and primary is None:
            raise HTTPException(422, '请为所选知识点指定一个主考点')
        if not ids and primary is not None:
            raise HTTPException(422, '未选择知识点时不能指定主考点')
        plan.update(ids=ids, primary=primary)
    elif subject_changed and old_links:
        raise HTTPException(422, '题目改学科时必须同时提交新学科的知识点列表')
    elif isinstance(plan['legacy'], str):
        text = plan['legacy']
        if text.strip() and text != current:
            plan['legacy_match'] = normalize_name_key(text)
            plan['legacy_text'] = text
    elif plan['legacy'] is not None:
        raise HTTPException(422, '知识点文本参数无效')
    return plan


def finish_plan(plan, matched_point):
    """把旧文本匹配结果并入计划，保留原有关联作为次要考点。"""
    if matched_point is not None:
        ids = list(plan['ids'])
        if matched_point['id'] not in ids:
            ids.append(matched_point['id'])
        plan['ids'] = ids
        plan['primary'] = matched_point['id']
    return plan


def validate_plan(plan, points, subject_id):
    """在已加载的知识点映射上校验单个解析结果。"""
    ids, primary = plan['ids'], plan['primary']
    for point_id in ids:
        point = points.get(point_id)
        if point is None or point.get('level') != 2:
            return '只能关联有效的二级知识点'
        if point.get('subject_id') != subject_id:
            return '知识点必须与题目同学科'
    if ids and primary is None:
        return '请为所选知识点指定一个主考点'
    if primary is not None and (type(primary) is not int or primary not in ids):
        return '主考点必须是已选知识点之一'
    if not ids and primary is not None:
        return '未选择知识点时不能指定主考点'
    if plan['has_new'] and isinstance(plan.get('legacy'), str) and plan['legacy'].strip():
        name = points[primary]['name'] if primary else ''
        if plan['legacy'].strip() != name:
            return '知识点新旧字段不一致'
    return None


async def resolve_many(db, subject_id, entries):
    """集合校验多条题目的分类字段，返回 (结果, 错误) 列表。

    entries 每项为 (payload, old_row, old_links, subject_changed)。所有目标
    知识点与旧文本键在一次查询内读取，不按题逐条 SELECT。
    """
    plans = []
    for entry in entries:
        try:
            plans.append(plan_knowledge(*entry))
        except HTTPException as error:
            plans.append(error)
    ids_needed, keys_needed = set(), set()
    for plan in plans:
        if isinstance(plan, HTTPException):
            continue
        ids_needed.update(plan['ids'])
        if plan.get('legacy_text'):
            keys_needed.add(normalize_name_key(plan['legacy_text']))
    points = await load_points(db, sorted(ids_needed)) if ids_needed else {}
    legacy_map = {}
    if keys_needed:
        rows = await db.all(
            "SELECT * FROM knowledge_point WHERE subject_id=? AND deleted=0 AND level=2 AND name_key IN "
            "(SELECT value FROM json_each(?))",
            (subject_id, json.dumps(sorted(keys_needed))))
        for row in rows:
            legacy_map.setdefault(row['name_key'], []).append(row)
    results = []
    for plan in plans:
        if isinstance(plan, HTTPException):
            results.append((None, plan.detail))
            continue
        if plan.get('legacy_text'):
            candidates = legacy_map.get(normalize_name_key(plan['legacy_text']), [])
            if len(candidates) != 1:
                detail = ('知识点“' + plan['legacy_text'] + '”存在多个同名二级，请从列表选择'
                          if candidates else '知识点“' + plan['legacy_text'] + '”不在目录中，请从列表选择')
                results.append((None, detail))
                continue
            finish_plan(plan, candidates[0])
            points.setdefault(candidates[0]['id'], candidates[0])
        error = validate_plan(plan, points, subject_id)
        if error:
            results.append((None, error))
            continue
        old_ids = sorted(point['id'] for point in plan['old_links'])
        old_primary = next((point['id'] for point in plan['old_links'] if point.get('is_primary')), None)
        changed = bool(plan['subject_changed']) or sorted(plan['ids']) != old_ids or plan['primary'] != old_primary
        results.append(({'ids': plan['ids'], 'primary': plan['primary'], 'changed': changed,
                         'source': plan['source'], 'points': points}, None))
    return results


async def save_directory(db, payload, item_id=None):
    """创建或更新目录节点，写入与版本递增在同一批处理内。"""
    if not isinstance(payload, dict):
        raise HTTPException(422, '请求必须为对象')
    old = None
    if item_id is not None:
        old = await db.first('SELECT * FROM knowledge_point WHERE id=? AND deleted=0', (item_id,))
        if old is None:
            raise HTTPException(404, '知识点不存在')
    for key in ('grade', 'semester'):
        value = payload.get(key, old.get(key) if old else None)
        if value is not None and (type(value) is not int or not 1 <= value <= (12 if key == 'grade' else 2)):
            raise HTTPException(422, '年级或学期无效')
    level = payload.get('level', old.get('level') if old else None)
    if level not in (1, 2):
        raise HTTPException(422, '知识点层级必须是 1 或 2')
    subject_id = payload.get('subject_id', old.get('subject_id') if old else None)
    if type(subject_id) is not int or not await db.first('SELECT id FROM subject WHERE id=? AND deleted=0', (subject_id,)):
        raise HTTPException(400, '学科不存在')
    parent_id = payload.get('parent_id', old.get('parent_id') if old else None)
    if level == 1:
        if parent_id is not None:
            raise HTTPException(422, '一级知识点不能有父级')
    else:
        parent = await db.first('SELECT * FROM knowledge_point WHERE id=? AND deleted=0', (parent_id,)) if parent_id else None
        if not parent or parent.get('level') != 1 or parent.get('subject_id') != subject_id:
            raise HTTPException(422, '二级知识点必须挂在同一学科的有效一级下')
    name = payload.get('name', old.get('name') if old else None)
    if not isinstance(name, str) or not clean_name(name):
        raise HTTPException(422, '名称不能为空')
    name_key = normalize_name_key(name)
    sort_order = payload.get('sort_order', old.get('sort_order') if old else 0)
    sort_order = 0 if sort_order is None else sort_order
    if type(sort_order) is not int or sort_order < 0 or sort_order > 9999:
        raise HTTPException(422, '排序值无效')
    code = payload.get('code', old.get('code') if old else None)
    if code is not None and (not isinstance(code, str) or not code.strip()):
        raise HTTPException(422, '编码不能为空')
    if isinstance(code, str):
        code = code.strip()
    if not code:
        code = 'KP-' + now_stamp().replace('-', '').replace(':', '').replace(' ', '') + '-' + uuid4().hex[:6].upper()
    error_ids = payload.get('error_type_ids')
    if error_ids is not None:
        if level != 2:
            if error_ids:
                raise HTTPException(422, '错误类型只能配置在二级知识点上')
            error_ids = None
        else:
            if not isinstance(error_ids, list) or any(type(item) is not int for item in error_ids):
                raise HTTPException(422, '错误类型参数无效')
            if error_ids:
                rows = await db.all(
                    "SELECT e.id FROM error_type e WHERE e.deleted=0 AND (e.subject_id IS NULL OR e.subject_id=?) "
                    "AND e.id IN (SELECT value FROM json_each(?))",
                    (subject_id, json.dumps(sorted(set(error_ids)))))
                if len(rows) != len(set(error_ids)):
                    raise HTTPException(400, '错误类型不存在或不属于当前学科')
    # 引用与移动保护：应用层先给出可读错误，触发器在事务内兜底。
    if old:
        child_count = (await db.first(
            'SELECT COUNT(*) AS count FROM knowledge_point WHERE parent_id=? AND deleted=0', (item_id,)))['count']
        usage = (await db.first(
            'SELECT COUNT(DISTINCT q.id) AS count FROM question_knowledge_point l '
            'JOIN question q ON q.id=l.question_id AND q.deleted=0 '
            'WHERE l.knowledge_point_id=? AND l.deleted=0', (item_id,)))['count']
        if level != old.get('level') and (child_count or usage):
            raise HTTPException(409, '有子级或题目关联的知识点不能修改层级')
        if subject_id != old.get('subject_id') and (child_count or usage):
            raise HTTPException(409, '有子级或题目关联的知识点不能修改学科')
        if old.get('level') == 2 and parent_id != old.get('parent_id') and usage:
            raise HTTPException(409, '有题目关联的二级知识点不能移动父级')
        if code is not None and code != old.get('code'):
            if await db.first('SELECT id FROM knowledge_point WHERE code=? AND deleted=0 AND id<>?', (code, item_id)):
                raise HTTPException(409, '知识点编码已存在')
        if name_key != old.get('name_key'):
            duplicate = await db.first(
                'SELECT id FROM knowledge_point WHERE deleted=0 AND name_key=? AND id<>? AND '
                + ('subject_id=? AND level=1' if level == 1 else 'parent_id=? AND level=2'),
                (name_key, item_id, subject_id if level == 1 else parent_id))
            if duplicate:
                raise HTTPException(409, '同级已存在同名知识点')
    else:
        if code and await db.first('SELECT id FROM knowledge_point WHERE code=? AND deleted=0', (code,)):
            raise HTTPException(409, '知识点编码已存在')
        duplicate = await db.first(
            'SELECT id FROM knowledge_point WHERE deleted=0 AND name_key=? AND '
            + ('subject_id=? AND level=1' if level == 1 else 'parent_id=? AND level=2'),
            (name_key, subject_id if level == 1 else parent_id))
        if duplicate:
            raise HTTPException(409, '同级已存在同名知识点')
    stamp = now_stamp()
    data = {'name': clean_name(name), 'name_key': name_key, 'subject_id': subject_id, 'level': level,
            'parent_id': parent_id, 'sort_order': sort_order, 'code': code,
            'grade': payload.get('grade', old.get('grade') if old else None),
            'semester': payload.get('semester', old.get('semester') if old else None),
            'updated_at': stamp}
    versions = bump_taxonomy()
    if not old:
        await ensure_guard_rows(db)
        maximum = (await db.first('SELECT COALESCE(MAX(id),0) AS id FROM knowledge_point'))['id']
        data['id'] = maximum + 1
        data['deleted'] = 0
        data['created_at'] = stamp
        statements = [guard_statement(
            '(SELECT COALESCE(MAX(id),0) FROM knowledge_point)=? AND EXISTS(SELECT 1 FROM write_guard WHERE id=1 AND deleted=0)',
            (maximum,))]
        statements.append((
            'INSERT INTO knowledge_point(' + ','.join(data) + ') VALUES (' + ','.join('?' for _ in data) + ')',
            list(data.values())))
        if error_ids is not None:
            statements += [('INSERT INTO kp_error_type(knowledge_point_id,error_type_id,deleted) VALUES (?,?,0)', (data['id'], error_id))
                           for error_id in sorted(set(error_ids))]
        statements += versions
        try:
            await db.batch(statements)
        except Exception as error:
            raise_http(error)
        return await directory_item(db, data['id'])
    await ensure_guard_rows(db)
    if error_ids is not None:
        statements = [guard_statement('EXISTS(SELECT 1 FROM knowledge_point WHERE id=? AND deleted=0)', (item_id,))]
        statements.append((
            'UPDATE knowledge_point SET ' + ','.join(key + '=?' for key in data) + ' WHERE id=? AND deleted=0',
            [*data.values(), item_id]))
        statements.append(('UPDATE kp_error_type SET deleted=1 WHERE knowledge_point_id=?', (item_id,)))
        statements += [('INSERT INTO kp_error_type(knowledge_point_id,error_type_id,deleted) VALUES (?,?,0) '
                        'ON CONFLICT(knowledge_point_id,error_type_id) DO UPDATE SET deleted=0', (item_id, error_id))
                       for error_id in sorted(set(error_ids))]
    else:
        statements = [guard_statement('EXISTS(SELECT 1 FROM knowledge_point WHERE id=? AND deleted=0)', (item_id,)),
                      ('UPDATE knowledge_point SET ' + ','.join(key + '=?' for key in data) + ' WHERE id=? AND deleted=0',
                       [*data.values(), item_id])]
    statements += versions
    try:
        await db.batch(statements)
    except Exception as error:
        raise_http(error)
    return await directory_item(db, item_id)


async def directory_item(db, item_id, include_legacy=True):
    """读取单个目录节点并附带引用计数与错误类型。"""
    row = await db.first('SELECT * FROM knowledge_point WHERE id=? AND deleted=?', (item_id, 0))
    if not row:
        raise HTTPException(404, '知识点不存在')
    return (await decorate_directory(db, [row], include_legacy))[0]


async def decorate_directory(db, rows, include_legacy=True):
    """批量为目录行补充学科名、父级名、引用计数和错误类型。"""
    if not include_legacy:
        rows = [row for row in rows if row.get('level') is not None]
    ids = [row['id'] for row in rows]
    if not ids:
        return []
    packed = json.dumps(ids)
    subjects = {item['id']: item['name'] for item in await db.all('SELECT id,name FROM subject WHERE deleted=0')}
    parent_ids = sorted({row['parent_id'] for row in rows
                         if row.get('parent_id') is not None and row['parent_id'] not in ids})
    parents = {item['id']: item for item in rows if item.get('level') == 1}
    if parent_ids:
        for item in await db.all(
                "SELECT id,name,subject_id FROM knowledge_point WHERE deleted=0 AND id IN "
                "(SELECT value FROM json_each(?))", (json.dumps(parent_ids),)):
            parents[item['id']] = item
    usage = {item['knowledge_point_id']: item['count'] for item in await db.all(
        'SELECT l.knowledge_point_id,COUNT(DISTINCT q.id) AS count FROM question_knowledge_point l '
        'JOIN question q ON q.id=l.question_id AND q.deleted=0 '
        "WHERE l.deleted=0 AND l.knowledge_point_id IN (SELECT value FROM json_each(?)) "
        'GROUP BY l.knowledge_point_id', (packed,))}
    children = {item['parent_id']: item['count'] for item in await db.all(
        "SELECT parent_id,COUNT(*) AS count FROM knowledge_point WHERE deleted=0 AND level=2 AND parent_id IN "
        "(SELECT value FROM json_each(?)) GROUP BY parent_id", (packed,))}
    error_types = {}
    for item in await db.all(
            'SELECT k.knowledge_point_id,e.id,e.name FROM kp_error_type k '
            'JOIN error_type e ON e.id=k.error_type_id AND e.deleted=0 '
            "WHERE k.deleted=0 AND k.knowledge_point_id IN (SELECT value FROM json_each(?)) "
            'ORDER BY e.id', (packed,)):
        error_types.setdefault(item.pop('knowledge_point_id'), []).append(item)
    result = []
    for row in rows:
        parent = parents.get(row.get('parent_id'))
        result.append({
            'id': row['id'],
            'name': row['name'],
            'name_key': row.get('name_key'),
            'code': row.get('code'),
            'subject_id': row.get('subject_id'),
            'subject_name': subjects.get(row.get('subject_id'), ''),
            'level': row.get('level'),
            'parent_id': row.get('parent_id'),
            'parent_name': parent['name'] if parent else None,
            'sort_order': row.get('sort_order') or 0,
            'grade': row.get('grade'),
            'semester': row.get('semester'),
            'created_at': row.get('created_at'),
            'updated_at': row.get('updated_at'),
            'question_count': usage.get(row['id'], 0),
            'child_count': children.get(row['id'], 0),
            'error_types': error_types.get(row['id'], []),
            'legacy': row.get('level') is None,
        })
    return result


@router.get('/api/knowledge-points/tree')
async def tree(request: Request, subject_id: int | None = Query(None, ge=1),
               grade: int | None = Query(None, ge=1, le=12), semester: int | None = Query(None, ge=1, le=2),
               keyword: str | None = None):
    """返回两级树和 taxonomy_version；树筛选按子级匹配再补齐父级。"""
    db = Database(request.scope['env'].DB)
    filters, values = ['deleted=0', 'level IN (1,2)'], []
    if subject_id is not None:
        filters.append('subject_id=?')
        values.append(subject_id)
    if keyword and keyword.strip():
        filters.append('instr(name,?)>0')
        values.append(keyword.strip())
    rows = await db.all('SELECT * FROM knowledge_point WHERE ' + ' AND '.join(filters)
                        + ' ORDER BY level,sort_order,id', values)
    graded = []
    for row in rows:
        if row.get('level') == 2 and (grade is not None or semester is not None):
            if grade is not None and row.get('grade') not in (None, grade):
                continue
            if semester is not None and row.get('semester') not in (None, semester):
                continue
        graded.append(row)
    parent_ids = {row['id'] for row in graded if row.get('level') == 1}
    for row in graded:
        if row.get('level') == 2:
            parent_ids.add(row.get('parent_id'))
    included = [row for row in graded if row.get('level') == 2 or row['id'] in parent_ids]
    decorated = await decorate_directory(db, included)
    for item in decorated:
        item['children'] = []
    return {'taxonomy_version': await taxonomy_version(db),
            'total': len([item for item in decorated if item.get('level') == 1]),
            'items': build_tree(decorated)}


@router.get('/api/knowledge-points')
async def listing(request: Request, subject_id: int | None = Query(None, ge=1),
                  level: int | None = Query(None, ge=1, le=2), parent_id: int | None = Query(None, ge=1),
                  grade: int | None = Query(None, ge=1, le=12), semester: int | None = Query(None, ge=1, le=2),
                  keyword: str | None = None, include_legacy: int = Query(0, ge=0, le=1)):
    """平铺读取目录，保留原有数组响应并增加两级字段。"""
    db = Database(request.scope['env'].DB)
    filters, values = ['deleted=0'], []
    for key, value in (('subject_id', subject_id), ('parent_id', parent_id), ('grade', grade), ('semester', semester)):
        if value is not None:
            filters.append(key + '=?')
            values.append(value)
    if level is not None:
        filters.append('level=?')
        values.append(level)
    elif not include_legacy:
        filters.append('level IN (1,2)')
    if keyword and keyword.strip():
        filters.append('instr(name,?)>0')
        values.append(keyword.strip())
    rows = await db.all('SELECT * FROM knowledge_point WHERE ' + ' AND '.join(filters)
                        + ' ORDER BY level,sort_order,id', values)
    return await decorate_directory(db, rows, include_legacy)


@router.get('/api/knowledge-points/{item_id}')
async def detail(item_id: int, request: Request):
    """读取单个未删除的知识点节点。"""
    return await directory_item(Database(request.scope['env'].DB), item_id)


@router.post('/api/knowledge-points', status_code=201)
async def create(request: Request):
    """创建一级或二级知识点，非法层级、跨学科与重名返回明确错误。"""
    return await save_directory(Database(request.scope['env'].DB), await request.json())


@router.put('/api/knowledge-points/{item_id}')
async def update(item_id: int, request: Request):
    """更新目录节点；有引用时禁止改学科、改层级与移动。"""
    return await save_directory(Database(request.scope['env'].DB), await request.json(), item_id)


@router.delete('/api/knowledge-points/{item_id}', status_code=204)
async def delete(item_id: int, request: Request):
    """软删除目录节点；有有效子级或题目关联时返回 409 和数量。"""
    db = Database(request.scope['env'].DB)
    item = await db.first('SELECT * FROM knowledge_point WHERE id=? AND deleted=0', (item_id,))
    if not item:
        raise HTTPException(404, '知识点不存在')
    child_count = (await db.first('SELECT COUNT(*) AS count FROM knowledge_point WHERE parent_id=? AND deleted=0',
                                  (item_id,)))['count']
    usage = (await db.first(
        'SELECT COUNT(DISTINCT q.id) AS count FROM question_knowledge_point l '
        'JOIN question q ON q.id=l.question_id AND q.deleted=0 '
        'WHERE l.knowledge_point_id=? AND l.deleted=0', (item_id,)))['count']
    if child_count:
        raise HTTPException(409, '该一级知识点仍有 ' + str(child_count) + ' 个有效二级，不能删除')
    if usage:
        raise HTTPException(409, '该二级知识点仍被 ' + str(usage) + ' 道有效错题引用，不能删除')
    await ensure_guard_rows(db)
    try:
        await db.batch([
            guard_statement('EXISTS(SELECT 1 FROM knowledge_point WHERE id=? AND deleted=0)', (item_id,)),
            ('UPDATE knowledge_point SET deleted=1,updated_at=? WHERE id=? AND deleted=0', (now_stamp(), item_id)),
            ('UPDATE kp_error_type SET deleted=1 WHERE knowledge_point_id=?', (item_id,)),
            *bump_taxonomy(),
        ])
    except Exception as error:
        raise_http(error)
    return Response(status_code=204)
