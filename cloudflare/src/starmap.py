"""知识星空接口：读取时现算每个考点的掌握度，并提供点亮记录、手动调整、学习进度。

计算规则在 mastery_model.py；这里只负责取数和组装。一次星空请求的 SQL 条数固定，
不随考点数量增加（保持 Workers 免费计划）。
"""

from fastapi import APIRouter, HTTPException, Request, Response

import settings
from database import Database
from intake import read_payload
from intake_model import is_plain_int
from mastery_model import (ADJUST, leaf_mastery, lighting, recent_results, status_of, upper_mastery,
                           vocab_progress)
from question_scope import counted, current_student_id
from questions import stamp_now

router = APIRouter(prefix='/api/starmap')

CONFIG_NAME = 'starmap'   # runtime_config 里的配置名：{"progress": {学科: 节号}, "seen": {学科: [考点]}}
# 事件在同一时刻内的次序：错题、练习、调整
SEQ = {'question': 0, 'practice': 1, 'adjust': 2}


async def load_subject(db, subject_id):
    """读取学科，不存在时 404。"""
    row = await db.first('SELECT id,name FROM subject WHERE id=? AND deleted=0', (subject_id,))
    if not row:
        raise HTTPException(404, '学科不存在')
    return row


async def load_points(db, subject_id):
    """读取学科下未删除的一、二级考点。"""
    return await db.all('SELECT id,name,level,parent_id,learn_grade,sort_order FROM knowledge_point '
                        'WHERE deleted=0 AND subject_id=? AND level IN (1,2) ORDER BY sort_order,id', (subject_id,))


async def load_events(db, subject_id, student_id=1):
    """取出这一科全部事件，按二级考点分组：{考点编号: [事件, ...]}（三条 SQL）。"""
    events = {}

    def add(point_id, event):
        """把一条事件挂到考点上。"""
        events.setdefault(point_id, []).append(event)

    # 1. 错题：时间优先用卷子日期；历史作业卷子的日期是回填的，改用录入时间
    rows = await db.all(
        "SELECT qk.knowledge_point_id AS point_id, CASE WHEN p.id IS NULL OR p.source='history' OR p.paper_date IS NULL "
        "THEN q.created_at ELSE p.paper_date END AS at "
        'FROM question q JOIN question_knowledge_point qk ON qk.question_id=q.id AND qk.deleted=0 '
        'JOIN knowledge_point k ON k.id=qk.knowledge_point_id AND k.deleted=0 '
        'LEFT JOIN paper p ON p.id=q.paper_id AND p.deleted=0 '
        'WHERE ' + counted('q') + ' AND q.subject_id=?', (subject_id,))
    for row in rows:
        add(row['point_id'], {'kind': 'wrong', 'at': row['at'], 'seq': SEQ['question'], 'adjust': None,
                              'source': 'question'})
    # 2. 练习卷里重做旧错题的结果（只认最新一次批改）
    rows = await db.all(
        'SELECT qk.knowledge_point_id AS point_id, pq.is_correct AS correct, ps.last_reviewed_at AS at '
        'FROM practice_set_question pq JOIN practice_set ps ON ps.id=pq.practice_set_id AND ps.deleted=0 '
        'JOIN question q ON q.id=pq.question_id AND ' + counted('q') + ' AND q.subject_id=? '
        'JOIN question_knowledge_point qk ON qk.question_id=q.id AND qk.deleted=0 '
        'JOIN knowledge_point k ON k.id=qk.knowledge_point_id AND k.deleted=0 '
        'WHERE pq.deleted=0 AND pq.is_correct IS NOT NULL', (subject_id,))
    for row in rows:
        add(row['point_id'], {'kind': 'right' if row['correct'] else 'wrong', 'at': row['at'],
                              'seq': SEQ['practice'], 'adjust': None, 'source': 'practice'})
    # 3. 手动调整
    rows = await db.all(
        'SELECT a.knowledge_point_id AS point_id, a.kind, a.created_at AS at FROM mastery_adjustment a '
        'JOIN knowledge_point k ON k.id=a.knowledge_point_id AND k.deleted=0 AND k.subject_id=? '
        'WHERE a.deleted=0 AND a.student_id=?', (subject_id, student_id))
    for row in rows:
        add(row['point_id'], {'kind': 'adjust', 'at': row['at'], 'seq': SEQ['adjust'], 'adjust': row['kind'],
                              'source': 'adjust'})
    return events


async def load_sections(db, subject_id):
    """读取这一科教材的节，以及每节对应的二级考点（一行一个对应，没有对应的节 point_id 为空）。"""
    return await db.all(
        'SELECT s.id, s.section_no, s.section_name, s.chapter_no, s.chapter_name, s.sort_order, sp.knowledge_point_id '
        'AS point_id FROM textbook_section s LEFT JOIN textbook_section_point sp ON sp.section_id=s.id AND sp.deleted=0 '
        'WHERE s.deleted=0 AND s.subject_id=? ORDER BY s.sort_order, s.id', (subject_id,))


def learned_ids(points, events, sections, progress, default_grade):
    """按设计 5.4 判断哪些二级考点算学过，返回编号集合。"""
    leaves = [p for p in points if p['level'] == 2]
    current = next((s for s in sections if s['section_no'] == progress), None)
    point_sorts, point_chapters = {}, {}
    for row in sections:
        if row['point_id'] is not None:
            point_sorts.setdefault(row['point_id'], []).append(row['sort_order'])
            point_chapters.setdefault(row['point_id'], []).append(row['chapter_no'])
    # 每个模块对应到的章：由它下面已对应到节的考点推出
    module_chapters = {}
    for leaf in leaves:
        module_chapters.setdefault(leaf['parent_id'], []).extend(point_chapters.get(leaf['id'], []))
    result = set()
    for leaf in leaves:
        if events.get(leaf['id']):
            result.add(leaf['id'])                    # 有记录就算学过
        elif leaf['learn_grade'] is not None:
            if default_grade is None or leaf['learn_grade'] <= default_grade:
                result.add(leaf['id'])
        elif current is None:
            result.add(leaf['id'])                    # 没有设置进度或没有章节数据：都算学过
        elif leaf['id'] in point_sorts:
            if min(point_sorts[leaf['id']]) <= current['sort_order']:
                result.add(leaf['id'])
        else:
            chapters = module_chapters.get(leaf['parent_id'])
            if not chapters or min(chapters) <= current['chapter_no']:
                result.add(leaf['id'])                # 课本外的模块、或所在章已经开始学
    return result


async def load_config(request):
    """读取星空配置，缺省为空。"""
    config = await settings.load(request, CONFIG_NAME, {})
    return config if isinstance(config, dict) else {}


async def compute(db, request, subject_id):
    """算出一科的节点、连线和当前已掌握的二级考点；返回 (subject, nodes, links, mastered, config)。"""
    subject = await load_subject(db, subject_id)
    points = await load_points(db, subject_id)
    events = await load_events(db, subject_id, current_student_id(request))
    sections = await load_sections(db, subject_id)
    links_rows = await db.all(
        'SELECT l.from_point_id AS source, l.to_point_id AS target FROM knowledge_link l '
        'JOIN knowledge_point a ON a.id=l.from_point_id AND a.deleted=0 AND a.subject_id=? '
        'JOIN knowledge_point b ON b.id=l.to_point_id AND b.deleted=0 '
        'WHERE l.deleted=0 ORDER BY l.id', (subject_id,))
    config = await load_config(request)
    app = await settings.load(request, 'app', {})
    progress = (config.get('progress') or {}).get(str(subject_id))
    learned = learned_ids(points, events, sections, progress, (app or {}).get('default_grade'))

    nodes, values = [], {}
    leaves = [p for p in points if p['level'] == 2]
    for leaf in leaves:
        point_events = events.get(leaf['id'], [])
        value = leaf_mastery(point_events) if leaf['id'] in learned else None
        values[leaf['id']] = value
        nodes.append({'id': leaf['id'], 'name': leaf['name'], 'level': 2, 'parent_id': leaf['parent_id'],
                      'value': value, 'status': status_of(value), 'recent': recent_results(point_events),
                      'wrong_count': sum(1 for e in point_events if e['source'] == 'question')})
    for module in (p for p in points if p['level'] == 1):
        children = [leaf for leaf in leaves if leaf['parent_id'] == module['id']]
        child_values = [values[c['id']] for c in children if values[c['id']] is not None]
        if child_values:
            merged = [e for c in children for e in events.get(c['id'], [])]
            value = upper_mastery(child_values, merged, len(children), len(child_values) < len(children))
        else:
            value = None
        nodes.append({'id': module['id'], 'name': module['name'], 'level': 1, 'parent_id': None, 'value': value,
                      'status': status_of(value), 'recent': [], 'wrong_count': 0})
    ids = {p['id'] for p in points}
    links = [{'source': leaf['parent_id'], 'target': leaf['id'], 'kind': 'belongs'}
             for leaf in leaves if leaf['parent_id'] in ids]
    links += [{'source': row['source'], 'target': row['target'], 'kind': 'prereq'}
              for row in links_rows if row['source'] in ids and row['target'] in ids]
    mastered = {leaf['id'] for leaf in leaves if values[leaf['id']] == 1}
    return subject, nodes, links, mastered, config


async def load_vocab(db):
    """词汇星团：单词本里"复习过且正确率超过 80%"的条目数和总数。"""
    row = await db.first('SELECT COUNT(*) AS total, COALESCE(SUM(CASE WHEN review_count>0 AND '
                         'correct_count*100.0/review_count>80 THEN 1 ELSE 0 END),0) AS mastered '
                         'FROM word WHERE deleted=0')
    return {'mastered': row['mastered'], 'total': row['total'], **vocab_progress(row['mastered'], row['total'])}


@router.get('')
async def starmap_view(request: Request, subject_id: int):
    """一科的知识星空：全部考点的掌握度、连线、词汇星团（英语）和要播放的点亮考点。"""
    db = Database(request.scope['env'].DB)
    subject, nodes, links, mastered, config = await compute(db, request, subject_id)
    vocab = await load_vocab(db) if subject['name'] == '英语' else None
    seen_map = config.get('seen') or {}
    seen = seen_map.get(str(subject_id))
    to_play, seen_after = lighting(mastered, set(seen) if seen is not None else None)
    if seen is None or set(seen) != seen_after:
        # 第一次打开：把当前已掌握的记为看过，不一下子全部播放；
        # 之后只在有考点掉出掌握时写回（去掉它，以后再次掌握会重新播放）
        await settings.store(request, CONFIG_NAME, {**config, 'seen': {**seen_map, str(subject_id): sorted(seen_after)}})
    return {'subject_id': subject['id'], 'subject_name': subject['name'], 'mastered_count': len(mastered),
            'nodes': nodes, 'links': links, 'vocab': vocab, 'to_play': sorted(to_play)}


@router.post('/seen')
async def mark_seen(request: Request):
    """点亮时刻播放完后，记下孩子已经看过的已掌握考点。"""
    payload = await read_payload(request)
    subject_id, point_ids = payload.get('subject_id'), payload.get('point_ids')
    if not is_plain_int(subject_id) or not isinstance(point_ids, list) or not all(is_plain_int(i) for i in point_ids):
        raise HTTPException(422, 'subject_id 和 point_ids 格式不对')
    db = Database(request.scope['env'].DB)
    _, _, _, mastered, config = await compute(db, request, subject_id)
    seen_map = config.get('seen') or {}
    old = set(seen_map.get(str(subject_id)) or [])
    seen = (old & mastered) | (set(point_ids) & mastered)
    await settings.store(request, CONFIG_NAME, {**config, 'seen': {**seen_map, str(subject_id): sorted(seen)}})
    return {'seen': sorted(seen)}


@router.get('/adjustments')
async def list_adjustments(request: Request, subject_id: int):
    """列出这一科未撤销的手动调整，最新的在前。"""
    db = Database(request.scope['env'].DB)
    return await db.all(
        'SELECT a.id, a.knowledge_point_id, k.name AS point_name, a.kind, a.created_at FROM mastery_adjustment a '
        'JOIN knowledge_point k ON k.id=a.knowledge_point_id AND k.deleted=0 AND k.subject_id=? '
        'WHERE a.deleted=0 AND a.student_id=? ORDER BY a.created_at DESC, a.id DESC',
        (subject_id, current_student_id(request)))


@router.post('/adjustments', status_code=201)
async def add_adjustment(request: Request):
    """新增一次手动调整；对一级考点的调整展开到它下面每个已学的二级考点。"""
    payload = await read_payload(request)
    point_id, kind = payload.get('knowledge_point_id'), payload.get('kind')
    if kind not in ADJUST:
        raise HTTPException(422, '调整类型只能是 %s' % '、'.join(ADJUST))
    if not is_plain_int(point_id):
        raise HTTPException(422, 'knowledge_point_id 必须是整数')
    db = Database(request.scope['env'].DB)
    point = await db.first('SELECT id,subject_id,level FROM knowledge_point WHERE id=? AND deleted=0 AND level IN (1,2)',
                           (point_id,))
    if not point:
        raise HTTPException(404, '考点不存在')
    targets = [point_id]
    if point['level'] == 1:
        _, nodes, _, _, _ = await compute(db, request, point['subject_id'])
        targets = [n['id'] for n in nodes if n['parent_id'] == point_id and n['value'] is not None]
        if not targets:
            raise HTTPException(422, '这个模块下还没有学过的考点')
    stamp = stamp_now()
    student_id = current_student_id(request)
    await db.batch([('INSERT INTO mastery_adjustment(student_id,knowledge_point_id,kind,created_at,deleted) '
                     'VALUES(?,?,?,?,0)', (student_id, target, kind, stamp)) for target in targets])
    placeholders = ','.join('?' * len(targets))
    return await db.all('SELECT id, knowledge_point_id, kind, created_at FROM mastery_adjustment WHERE deleted=0 AND '
                        'created_at=? AND kind=? AND knowledge_point_id IN (' + placeholders + ') ORDER BY id',
                        (stamp, kind, *targets))


@router.delete('/adjustments/{adjustment_id}', status_code=204)
async def remove_adjustment(adjustment_id: int, request: Request):
    """撤销一次手动调整（软删除）。"""
    db = Database(request.scope['env'].DB)
    row = await db.first('SELECT id FROM mastery_adjustment WHERE id=? AND deleted=0', (adjustment_id,))
    if not row:
        raise HTTPException(404, '调整记录不存在')
    await db.run('UPDATE mastery_adjustment SET deleted=1 WHERE id=?', (adjustment_id,))
    return Response(status_code=204)


def section_list(sections):
    """把节和考点的对应行整理成不重复的节列表（按顺序）。"""
    result, seen = [], set()
    for row in sections:
        if row['id'] not in seen:
            seen.add(row['id'])
            result.append({'section_no': row['section_no'], 'section_name': row['section_name'],
                           'chapter_name': row['chapter_name']})
    return result


@router.get('/progress')
async def get_progress(request: Request, subject_id: int):
    """读取这一科"现在学到哪一节"和可选的节。"""
    db = Database(request.scope['env'].DB)
    await load_subject(db, subject_id)
    config = await load_config(request)
    return {'section_no': (config.get('progress') or {}).get(str(subject_id)),
            'sections': section_list(await load_sections(db, subject_id))}


@router.put('/progress')
async def save_progress(request: Request, subject_id: int):
    """修改这一科"现在学到哪一节"；节必须存在。"""
    payload = await read_payload(request)
    db = Database(request.scope['env'].DB)
    await load_subject(db, subject_id)
    section_no = payload.get('section_no')
    if section_no not in {s['section_no'] for s in section_list(await load_sections(db, subject_id))}:
        raise HTTPException(422, '没有这一节')
    config = await load_config(request)
    progress = {**(config.get('progress') or {}), str(subject_id): section_no}
    await settings.store(request, CONFIG_NAME, {**config, 'progress': progress})
    return {'section_no': section_no}
