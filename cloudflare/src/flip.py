"""翻一翻：每天一组（最多 8 张）旧错题卡片，学生翻看后点"我记得"或"我忘了"（设计第 7 节）。

选题规则都在 flip_model.py；这里只负责取数、组装卡片和记录结果。
候选题：已核对、没删除（question_scope.counted）、没毕业（targeted_model.question_state，
取数方式和 weekly.graduated_count 一样）、题干不为空或者有原图；所有学科、所有年级，没挂考点的也进。

SQL 条数固定、不随题目数增加：选题 4 条（题目、练习卷结果、"设为掌握"、翻牌记录），
打开今天这一组再加 1 条取卡片内容，记一次结果再加 1 条写入。

翻牌只读掌握度相关的数据、只写 flip_log，不影响考点掌握度、错题毕业和知识星空。

下面这个模块级名字测试和本机开发服务器会替换，代码里一律直接按名字调用：Database。
"""

import json
from datetime import date, timedelta

from fastapi import APIRouter, HTTPException, Request

import analytics
from database import Database
from flip_model import RESULTS, pick_today
from question_scope import counted, current_student_id, stem_ready
from targeted import normal_time
from targeted_model import question_state

router = APIRouter(prefix='/api/flip')

NOT_FOUND_TEXT = '题目不存在或不能翻'


def cutoff_of(today):
    """选题时毕业状态算到哪一刻：today 第二天 00:00（不含）。库里没有未来的数据，所以就是"到现在为止"。"""
    return (date.fromisoformat(today) + timedelta(days=1)).isoformat() + ' 00:00:00'


def image_list(row):
    """一道题的原图列表：original_images 有内容就用它，否则用 original_image（和题目详情的读法一致）。"""
    try:
        images = json.loads(row.get('original_images') or 'null')
    except ValueError:
        images = None
    if isinstance(images, list) and images:
        return [str(item) for item in images if item]
    return [row['original_image']] if row.get('original_image') else []


async def load_question_rows(db):
    """所有已核对、没删除的错题：编号、录入时间、主考点、有没有题干、原图（一条 SQL）。"""
    return await db.all(
        'SELECT q.id, q.created_at AS entered, qk.knowledge_point_id AS point_id, '
        '(' + stem_ready('q') + ') AS has_stem, q.original_image, q.original_images FROM question q '
        'LEFT JOIN question_knowledge_point qk ON qk.question_id=q.id AND qk.deleted=0 AND qk.is_primary=1 '
        'WHERE ' + counted('q') + ' ORDER BY q.id')


async def states_of(db, student_id, cutoff, rows):
    """rows 里每道题在 cutoff 之前的状态 {题目编号: 'todo' | 'consolidating' | 'graduated'}（两条 SQL）。

    结果只取已批改、不是"没做"和"题目有误"的；"直接设为掌握"看主考点上的调整（同 weekly.graduated_count）。
    """
    result_rows = await db.all(
        'SELECT o.question_id AS qid, o.is_correct, o.display_order, ps.last_reviewed_at '
        'FROM practice_set_question o JOIN practice_set ps ON ps.id=o.practice_set_id AND ps.deleted=0 '
        'JOIN question q ON q.id=o.question_id AND ' + counted('q') + ' '
        'WHERE o.deleted=0 AND o.is_correct IS NOT NULL AND o.skip_reason IS NULL AND ps.last_reviewed_at<?',
        (cutoff,))
    adjust_rows = await db.all(
        "SELECT knowledge_point_id AS point_id, created_at FROM mastery_adjustment WHERE deleted=0 AND student_id=? "
        "AND kind='set_mastered' AND created_at<?", (student_id, cutoff))
    waive_at = {}
    for row in adjust_rows:
        at = normal_time(row['created_at'])
        if at is not None and (row['point_id'] not in waive_at or at > waive_at[row['point_id']]):
            waive_at[row['point_id']] = at       # 只要最近一次
    results = {}
    for row in result_rows:
        results.setdefault(row['qid'], []).append({'at': normal_time(row['last_reviewed_at']),
                                                   'order': row['display_order'] or 0,
                                                   'correct': bool(row['is_correct'])})
    states = {}
    for row in rows:
        if row['id'] in states:
            continue      # 万一一题有两个主考点，只算第一行
        states[row['id']] = question_state(results.get(row['id'], []), normal_time(row['entered']),
                                           waive_at.get(row['point_id']))['state']
    return states


async def load_states(db, student_id, cutoff):
    """所有已核对、没删除的错题在 cutoff 之前的状态（三条 SQL）。测试用它核对"翻牌不改毕业状态"。"""
    return await states_of(db, student_id, cutoff, await load_question_rows(db))


async def load_logs(db, student_id, today):
    """这个学生到 today 为止的全部翻牌记录，按题目分组（一条 SQL）。"""
    rows = await db.all('SELECT question_id, result, flip_date, created_at FROM flip_log WHERE deleted=0 '
                        'AND student_id=? AND flip_date<=? ORDER BY flip_date, created_at, id', (student_id, today))
    logs = {}
    for row in rows:
        logs.setdefault(row['question_id'], []).append(row)
    return logs


async def load_pool(db, student_id, today):
    """取选题要的全部数据（四条 SQL），返回 (候选题列表, 翻牌记录)。

    候选题：没毕业、并且题干不为空或者有原图。
    """
    rows = await load_question_rows(db)
    states = await states_of(db, student_id, cutoff_of(today), rows)
    candidates, seen = [], set()
    for row in rows:
        if row['id'] in seen:
            continue
        seen.add(row['id'])
        if states[row['id']] == 'graduated':
            continue
        if not row['has_stem'] and not image_list(row):
            continue
        candidates.append({'id': row['id'], 'entered': row['entered']})
    return candidates, await load_logs(db, student_id, today)


async def load_cards(db, card_ids):
    """按顺序取卡片内容：学科名、主考点名、题干、原图、错误答案、答案、解析（一条 SQL）。"""
    rows = await db.all(
        'SELECT q.id, s.name AS subject_name, k.name AS point_name, q.parsed_question, q.original_text, '
        'q.original_image, q.original_images, q.wrong_answer, q.answer, q.analysis, q.analysis_image '
        'FROM question q LEFT JOIN subject s ON s.id=q.subject_id '
        'LEFT JOIN question_knowledge_point qk ON qk.question_id=q.id AND qk.deleted=0 AND qk.is_primary=1 '
        'LEFT JOIN knowledge_point k ON k.id=qk.knowledge_point_id AND k.deleted=0 '
        'WHERE q.id IN (SELECT value FROM json_each(?)) ORDER BY q.id', (json.dumps(card_ids),))
    by_id = {}
    for row in rows:
        by_id.setdefault(row['id'], row)
    cards = []
    for question_id in card_ids:
        row = by_id.get(question_id)
        if row is None:
            continue
        # 解析后的题干为空时用原题文字（和 targeted.stem_of、question_scope.stem_ready 一致）
        stem = (row['parsed_question'] or '').strip() or (row['original_text'] or '').strip()
        cards.append({'id': row['id'], 'subject_name': row['subject_name'], 'point_name': row['point_name'],
                      'parsed_question': stem, 'images': image_list(row), 'wrong_answer': row['wrong_answer'],
                      'answer': row['answer'], 'analysis': row['analysis'], 'analysis_image': row['analysis_image']})
    return cards


async def build_today(db, student_id, today):
    """今天这一组还没翻的卡片和进度：{'total', 'done', 'cards'}（五条 SQL；没有卡片时四条）。"""
    candidates, logs = await load_pool(db, student_id, today)
    picked = pick_today(candidates, logs, today)
    cards = await load_cards(db, picked['cards']) if picked['cards'] else []
    return {'total': picked['done'] + len(picked['cards']), 'done': picked['done'], 'cards': cards}


async def today_progress(db, student_id, today) -> dict:
    """今天的进度 {'total', 'done'}，和 /api/flip/today 同一套选题（四条 SQL）；首页用。"""
    candidates, logs = await load_pool(db, student_id, today)
    picked = pick_today(candidates, logs, today)
    return {'total': picked['done'] + len(picked['cards']), 'done': picked['done']}


async def record_flip(db, student_id, question_id, result, today, stamp):
    """记一次翻牌结果，返回今天的进度 {'done', 'total'}（五条 SQL；今天已经记过这题时四条，不再写）。

    题目不在候选范围（不存在、没核对、已删除、已毕业、没有题干也没有原图）时 404。
    """
    candidates, logs = await load_pool(db, student_id, today)
    if question_id not in {candidate['id'] for candidate in candidates}:
        raise HTTPException(404, NOT_FOUND_TEXT)
    today_logs = [row for row in logs.get(question_id, []) if str(row['flip_date'])[:10] == today]
    if not today_logs:
        # 唯一索引兜底：两个请求同时到达时，后到的一条被忽略，不会记两次
        await db.run('INSERT OR IGNORE INTO flip_log(student_id,question_id,result,flip_date,created_at,deleted) '
                     'VALUES(?,?,?,?,?,0)', (student_id, question_id, result, today, stamp))
        logs.setdefault(question_id, []).append({'question_id': question_id, 'result': result,
                                                 'flip_date': today, 'created_at': stamp})
    picked = pick_today(candidates, logs, today)
    return {'done': picked['done'], 'total': picked['done'] + len(picked['cards'])}


async def load_flip_rows(db, student_id, start, end) -> list:
    """created_at 落在 [start, end) 的翻牌记录，每条 {'flip_date', 'created_at'}（一条 SQL）；首页、周报用。

    start、end 是 19 位北京时间（周报窗口是"上周日 20:00 到本周日 20:00"，和默写按 reviewed_at 算一样）；
    库里的 created_at 可能带微秒，按字符串比较就是按时间先后比较。
    """
    # flip_date 就是 created_at 那一天，多加一个 flip_date 条件只是为了用上 (student_id, flip_date) 索引
    return await db.all('SELECT flip_date, created_at FROM flip_log WHERE deleted=0 AND student_id=? '
                        'AND flip_date>=? AND created_at>=? AND created_at<?',
                        (student_id, str(start)[:10], start, end))


def flip_dates(rows) -> set:
    """rows（load_flip_rows 的结果）里翻过卡片的日期集合，按 flip_date（YYYY-MM-DD）。"""
    return {str(row['flip_date'])[:10] for row in rows}


def flip_counts(rows, start, end, week) -> dict:
    """rows 里 created_at 落在 [start, end) 的翻了几天、几张：{'days', 'cards'}。

    张数 = 这些记录的条数（同一题同一天本来就只有一条）。
    天数 = 这些记录里不同的 flip_date，再只留在 week（周一到周日的日期集合）里的，和默写天数的算法一样：
    上周日 20:00 之后翻的算进本期张数，但那天是上周日，不算本期的天数。
    不数"我忘了"有几张：周报只说翻了多少，不评价忘了多少。
    """
    kept = [row for row in rows if start <= str(row['created_at']) < end]
    return {'days': len(flip_dates(kept) & week), 'cards': len(kept)}


async def read_result(request):
    """读请求体里的 result，必须是 remember 或 forget，否则 422。"""
    try:
        payload = await request.json()
    except ValueError:
        raise HTTPException(422, '请求内容不是合法的 JSON')
    result = payload.get('result') if isinstance(payload, dict) else None
    if result not in RESULTS:
        raise HTTPException(422, 'result 只能是 remember 或 forget')
    return result


@router.get('/today')
async def flip_today(request: Request):
    """今天这一组还没翻的卡片，以及今天总共几张、已翻几张。"""
    db = Database(request.scope['env'].DB)
    today = analytics.now().strftime('%Y-%m-%d')
    return await build_today(db, current_student_id(request), today)


@router.post('/{question_id}')
async def flip_one(question_id: int, request: Request):
    """记一次"我记得"或"我忘了"；同一题同一天重复提交只记第一次。返回今天的进度。"""
    result = await read_result(request)
    db = Database(request.scope['env'].DB)
    moment = analytics.now()
    return await record_flip(db, current_student_id(request), question_id, result,
                             moment.strftime('%Y-%m-%d'), moment.isoformat(' '))
