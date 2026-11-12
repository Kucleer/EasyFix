"""考点卷接口：出卷状态、选题预览、创建、一道一道准备相似题、换相似题（设计 5、6.4、10）。

选题规则在 targeted_model.py（纯函数）；这里只负责取数、校验和写入。
保持 Workers 免费计划：每个接口的 SQL 条数固定，不随题目数或考点数增加；
prepare / reroll 每次最多调用一次模型、一次公式校验。
"""

import datetime
import json

from fastapi import APIRouter, HTTPException, Request

import similar
import starmap
from analytics import now
from database import Database
from intake import read_payload
from intake_model import is_plain_int
from knowledge import question_links
from practices import batch_or_http, get as get_practice
from prompts import PromptLibrary
from question_scope import counted, grade_ready, stem_ready
from targeted_model import (MODES, OPEN_PAPER_DAYS, SIZE_MAX, SIZE_MIN, SPOT_DEFAULT, has_figure, plan_paper)

router = APIRouter(prefix='/api/practice-sets/targeted')

REASONS = ('new', 'wrong', 'redo', 'consolidate', 'check', 'spot')   # 入选原因
FORMS = ('original', 'similar')                                     # 题面：原题、相似题
STEM_LENGTH = 120        # 预览里题干最多显示几个字


# ---------------------------------------------------------------- 小工具


def normal_time(value):
    """把时间统一成能按字符串比较先后的 'YYYY-MM-DD HH:MM:SS'；空值返回 None。

    只有日期（如卷子日期）的补成当天最后一秒：同一天的错题算在出卷之后（"新错题"）。
    """
    if value is None or value == '':
        return None
    text = str(value).replace('T', ' ')
    if len(text) == 10:
        return text + ' 23:59:59'
    return text[:19]


def open_cutoff():
    """没批改的卷子占着题的起点：OPEN_PAPER_DAYS 天前（北京时间），早于它创建的卷子不再占题。"""
    return (now() - datetime.timedelta(days=OPEN_PAPER_DAYS)).isoformat(' ')[:19]


def stem_of(question):
    """题干：解析后的题干为空时用原题文字（和 practices.get、question_scope.stem_ready 一致）。"""
    parsed = (question.get('parsed_question') or '').strip()
    return parsed or (question.get('original_text') or '').strip()


def paper_state(paper):
    """卷子的状态：to_print 还没生成 PDF、to_grade 有 PDF 还没批改、graded 已批改。"""
    if paper['reviewed']:
        return 'graded'
    return 'to_grade' if paper['pdf_path'] else 'to_print'


def paper_summary(paper):
    """出卷页、首页用的卷子摘要；paper 为 None 时返回 None。"""
    if paper is None:
        return None
    return {'id': paper['id'], 'name': paper['name'], 'created_at': paper['created_at'],
            'state': paper_state(paper), 'accuracy': paper['accuracy']}


async def read_optional_payload(request):
    """读取可以不传的请求体：没有内容时当作空对象；有内容但不是对象时 422。"""
    try:
        payload = await request.json()
    except ValueError:
        return {}
    if payload is None:
        return {}
    if not isinstance(payload, dict):
        raise HTTPException(422, '请求内容必须是一个对象')
    return payload


def int_in_range(payload, key, default, low, high, label):
    """取一个整数参数并检查范围；不是 low–high 之间的整数时 422。"""
    value = payload.get(key, default)
    if not is_plain_int(value) or not low <= value <= high:
        raise HTTPException(422, '%s需要是 %d 到 %d 之间的整数' % (label, low, high))
    return value


# ---------------------------------------------------------------- 状态


@router.get('/status')
async def status(request: Request):
    """待批改卷子数（最近 30 天、错题练习集），以及每科最近一份考点卷的出卷日期和状态。"""
    db = Database(request.scope['env'].DB)
    count = await db.first(
        "SELECT COUNT(*) AS total FROM practice_set WHERE deleted=0 AND source_type='question' "
        'AND COALESCE(reviewed,0)=0 AND created_at>=?', (open_cutoff(),))
    # 每科取最新的一份考点卷（子查询按出卷时间、编号倒序取第一份）
    rows = await db.all(
        'SELECT s.id AS subject_id, s.name AS subject_name, p.id, p.name, p.created_at, p.pdf_path, '
        'p.reviewed, p.accuracy FROM subject s LEFT JOIN practice_set p ON p.id=('
        "SELECT x.id FROM practice_set x WHERE x.subject_id=s.id AND x.kind='targeted' AND x.deleted=0 "
        'ORDER BY x.created_at DESC, x.id DESC LIMIT 1) WHERE s.deleted=0 ORDER BY s.id')
    subjects = [{'subject_id': row['subject_id'], 'subject_name': row['subject_name'],
                 'last_paper': paper_summary(row) if row['id'] is not None else None} for row in rows]
    return {'pending_count': count['total'], 'subjects': subjects}


# ---------------------------------------------------------------- 选题预览


async def load_candidates(db, subject_id, min_grade):
    """取这一科能进卷子的题（一条 SQL）：主考点、题干、录入时间、错题日期、复核原因。

    min_grade 为 None 时不按年级筛（"包含低年级"打开，或没设置默认年级）。
    """
    grade_sql, grade_params = grade_ready('q', min_grade)
    return await db.all(
        'SELECT q.id, q.created_at AS entered, q.parsed_question, q.original_text, q.review_reasons, '
        'qk.knowledge_point_id AS point_id, ' + starmap.WRONG_AT_SQL + ' AS wrong_at '
        'FROM question q JOIN question_knowledge_point qk ON qk.question_id=q.id AND qk.deleted=0 AND qk.is_primary=1 '
        'JOIN knowledge_point k ON k.id=qk.knowledge_point_id AND k.deleted=0 AND k.level=2 '
        'LEFT JOIN paper p ON p.id=q.paper_id AND p.deleted=0 '
        'WHERE ' + counted('q') + ' AND q.subject_id=? AND ' + stem_ready('q') + ' AND ' + grade_sql + ' '
        'ORDER BY q.id', (subject_id, *grade_params))


async def load_practice_rows(db, subject_id):
    """取这一科错题练习集里的题目行（一条 SQL）：结果、题号顺序和所在卷子的信息。"""
    return await db.all(
        'SELECT pq.question_id, pq.is_correct, pq.skip_reason, pq.display_order, ps.id AS set_id, ps.name, '
        'ps.kind, ps.created_at, ps.reviewed, ps.last_reviewed_at, ps.pdf_path, ps.accuracy '
        'FROM practice_set_question pq JOIN practice_set ps ON ps.id=pq.practice_set_id AND ps.deleted=0 '
        'JOIN question q ON q.id=pq.question_id AND q.subject_id=? '
        'WHERE pq.deleted=0', (subject_id,))


def summarize_practice(rows):
    """从练习题目行算出：每道题的结果、被没批改卷子占着的题、上一份考点卷、没批改的考点卷数。

    返回 (results, blocked, last_paper, open_paper_count)。
    """
    cutoff = open_cutoff()
    results, blocked, open_papers, last_paper = {}, set(), set(), None
    for row in rows:
        created = normal_time(row['created_at']) or ''
        unreviewed = not row['reviewed']
        # 结果：只认有对错的行；"没做""题目有误"不算
        if row['is_correct'] is not None and row['skip_reason'] is None:
            results.setdefault(row['question_id'], []).append(
                {'at': normal_time(row['last_reviewed_at']), 'order': row['display_order'] or 0,
                 'correct': bool(row['is_correct'])})
        # 最近 30 天内创建、还没批改的卷子（考点卷和手动组的都算）占着题
        if unreviewed and created >= cutoff:
            blocked.add(row['question_id'])
        if row['kind'] == 'targeted':
            if unreviewed and created >= cutoff:
                open_papers.add(row['set_id'])
            if last_paper is None or (created, row['set_id']) > (normal_time(last_paper['created_at']) or '',
                                                                  last_paper['id']):
                last_paper = {'id': row['set_id'], 'name': row['name'], 'created_at': row['created_at'],
                              'reviewed': row['reviewed'], 'pdf_path': row['pdf_path'], 'accuracy': row['accuracy']}
    return results, blocked, last_paper, len(open_papers)


@router.post('/plan')
async def plan(request: Request):
    """按当前掌握度选题，返回选中的题、每个考点的备选和少出的道数。只算不存，不调模型。"""
    payload = await read_payload(request)
    subject_id = payload.get('subject_id')
    if not is_plain_int(subject_id):
        raise HTTPException(422, 'subject_id 必须是整数')
    size = int_in_range(payload, 'size', None, SIZE_MIN, SIZE_MAX, '题量')
    mode = payload.get('mode', 'spread')
    if mode not in MODES:
        raise HTTPException(422, '分法只能是 %s' % '、'.join(MODES))
    spot_count = int_in_range(payload, 'spot_count', SPOT_DEFAULT, 0, SIZE_MAX, '抽查题数')
    include_lower = payload.get('include_lower_grades', False)
    if not isinstance(include_lower, bool):
        raise HTTPException(422, 'include_lower_grades 必须是真或假')

    db = Database(request.scope['env'].DB)
    # 默认年级只读一次，同时交给掌握度计算；掌握度永远按开关关着的口径算（设计 5.1）
    default_grade = await starmap.load_default_grade(request)
    _, nodes, _, _, _ = await starmap.compute(db, request, subject_id, default_grade)
    candidates = await load_candidates(db, subject_id, None if include_lower else default_grade)
    results, blocked, last_paper, open_count = summarize_practice(await load_practice_rows(db, subject_id))

    modules = {node['id']: node['name'] for node in nodes if node['level'] == 1}
    point_info = {node['id']: node for node in nodes if node['level'] == 2}
    points = {pid: {'value': node['value'], 'status': node['status'], 'pending': node['pending'],
                    'all_graduated': node['all_graduated'], 'waive_at': normal_time(node['waive_at'])}
              for pid, node in point_info.items()}
    questions, details = [], {}
    for row in candidates:
        if row['id'] in details:
            continue                    # 防御：主考点不止一个时只取第一条
        stem = stem_of(row)
        details[row['id']] = {'stem': stem[:STEM_LENGTH], 'has_figure': has_figure(stem, row['review_reasons'])}
        questions.append({'id': row['id'], 'point_id': row['point_id'], 'wrong_at': normal_time(row['wrong_at']),
                          'entered': normal_time(row['entered']), 'results': results.get(row['id'], []),
                          'blocked': row['id'] in blocked})
    last_paper_at = normal_time(last_paper['created_at']) if last_paper else None
    picked = plan_paper(questions, points, last_paper_at, now().date().isoformat(), size, mode, spot_count)

    def describe(item):
        """给一条选题结果补上考点、模块名称和题干预览。"""
        node = point_info[item['point_id']]
        return {**item, 'point_name': node['name'], 'module_id': node['parent_id'],
                'module_name': modules.get(node['parent_id']), **details[item['question_id']]}

    return {'items': [describe(item) for item in picked['items']],
            'reserve': {pid: [describe(item) for item in rows] for pid, rows in picked['reserve'].items()},
            'shortfall': picked['shortfall'], 'open_paper_count': open_count, 'last_paper': paper_summary(last_paper)}


# ---------------------------------------------------------------- 创建


def check_items(items):
    """检查创建时的题目清单格式，不对时 422；返回原清单。"""
    if not isinstance(items, list) or not SIZE_MIN <= len(items) <= SIZE_MAX:
        raise HTTPException(422, '请选择 %d 至 %d 道题' % (SIZE_MIN, SIZE_MAX))
    seen = set()
    for index, item in enumerate(items, 1):
        if not isinstance(item, dict) or not is_plain_int(item.get('question_id')) \
                or not is_plain_int(item.get('point_id')):
            raise HTTPException(422, '第 %d 道题的题号或考点格式不对' % index)
        if item.get('reason') not in REASONS:
            raise HTTPException(422, '第 %d 道题的入选原因不对' % index)
        if item.get('form') not in FORMS:
            raise HTTPException(422, '第 %d 道题的题面只能是原题或相似题' % index)
        if item['question_id'] in seen:
            raise HTTPException(422, '同一道题不能出现两次')
        seen.add(item['question_id'])
    return items


def default_name(subject_name):
    """卷子的默认名称，如"数学练习卷 11月12日"。"""
    today = now()
    return '%s练习卷 %d月%d日' % (subject_name, today.month, today.day)


@router.post('', status_code=201)
async def create(request: Request):
    """按最终确定的题目清单创建考点卷；相似题这时还没生成，由 prepare 一道一道补。"""
    payload = await read_payload(request)
    subject_id, name = payload.get('subject_id'), payload.get('name')
    if not is_plain_int(subject_id):
        raise HTTPException(422, 'subject_id 必须是整数')
    if name is not None and not isinstance(name, str):
        raise HTTPException(422, '卷子名称必须是文字')
    items = check_items(payload.get('items'))
    db = Database(request.scope['env'].DB)
    subject = await starmap.load_subject(db, subject_id)
    ids = json.dumps([item['question_id'] for item in items])

    # 这些题挂的二级考点，以及模块、考点的排序；创建时不看年级（家长可能开了"包含低年级"）
    rows = await db.all(
        'SELECT q.id AS question_id, k.id AS point_id, k.sort_order AS point_sort, k.parent_id AS module_id, '
        'm.sort_order AS module_sort FROM question q '
        'JOIN question_knowledge_point qk ON qk.question_id=q.id AND qk.deleted=0 '
        'JOIN knowledge_point k ON k.id=qk.knowledge_point_id AND k.deleted=0 AND k.level=2 '
        'LEFT JOIN knowledge_point m ON m.id=k.parent_id AND m.deleted=0 '
        'WHERE ' + counted('q') + ' AND q.subject_id=? AND ' + stem_ready('q') + ' '
        'AND q.id IN (SELECT value FROM json_each(?))', (subject_id, ids))
    links = {(row['question_id'], row['point_id']): row for row in rows}
    usable = {row['question_id'] for row in rows}
    for item in items:
        if item['question_id'] not in usable:
            raise HTTPException(422, '错题 %d 不是这一科能进卷子的题' % item['question_id'])
        if (item['question_id'], item['point_id']) not in links:
            raise HTTPException(422, '考点 %d 不是错题 %d 挂的二级考点' % (item['point_id'], item['question_id']))

    # 最近 30 天内没批改的卷子里已经有的题，不能再出（避免同一道题同时在两份卷子上）
    busy = await db.all(
        'SELECT DISTINCT pq.question_id FROM practice_set_question pq '
        'JOIN practice_set ps ON ps.id=pq.practice_set_id AND ps.deleted=0 AND COALESCE(ps.reviewed,0)=0 '
        'AND ps.created_at>=? WHERE pq.deleted=0 AND pq.question_id IN (SELECT value FROM json_each(?))',
        (open_cutoff(), ids))
    if busy:
        raise HTTPException(409, '错题 %s 已经在没批改的卷子里' % '、'.join(str(row['question_id']) for row in busy))

    # 题号顺序：模块排序 → 模块编号 → 考点排序 → 考点编号 → 请求里的先后，同一模块、同一考点的题挨在一起
    def order_key(pair):
        """排序键。"""
        index, item = pair
        link = links[(item['question_id'], item['point_id'])]
        return (link['module_sort'] or 0, link['module_id'] or 0, link['point_sort'] or 0, item['point_id'], index)

    ordered = [item for _, item in sorted(enumerate(items), key=order_key)]
    stamp = now().isoformat(' ')
    paper = await db.first(
        "INSERT INTO practice_set(name,subject_id,source_type,question_type,kind,total_questions,reviewed,review_count,"
        "grading_revision,deleted,created_at) VALUES(?,?,'question','mixed','targeted',?,0,0,0,0,?) RETURNING id",
        ((name or '').strip() or default_name(subject['name']), subject_id, len(ordered), stamp))
    statements = [('INSERT INTO practice_set_question(practice_set_id,question_id,similar_question_id,display_order,'
                   'form,reason,knowledge_point_id,deleted) VALUES(?,?,NULL,?,?,?,?,0)',
                   (paper['id'], item['question_id'], index, item['form'], item['reason'], item['point_id']))
                  for index, item in enumerate(ordered)]
    try:
        await batch_or_http(db, statements)
    except Exception:
        # 题目行没写进去：把空卷子软删除，不留下半份卷子
        await db.run('UPDATE practice_set SET deleted=1 WHERE id=?', (paper['id'],))
        raise
    return await get_practice(db, paper['id'])


# ---------------------------------------------------------------- 准备相似题、换相似题


async def load_open_paper(db, practice_set_id):
    """读取一份还能改题面的考点卷：不存在或已删除 404，不是考点卷 422，已批改 409。"""
    paper = await db.first('SELECT id,kind,reviewed FROM practice_set WHERE id=? AND deleted=0', (practice_set_id,))
    if not paper:
        raise HTTPException(404, '练习卷不存在')
    if paper['kind'] != 'targeted':
        raise HTTPException(422, '只有考点卷可以准备或更换相似题')
    if paper['reviewed']:
        raise HTTPException(409, '这份卷子已经批改，不能再改题面')
    return paper


# 题目行连同错题内容（生成相似题要用）；调用方在后面接 WHERE 条件
ITEM_SQL = ('SELECT pq.id AS item_id, pq.form, pq.similar_question_id, q.id, q.parsed_question, q.original_text, '
            'q.answer, q.wrong_answer, q.review_reasons, s.name AS subject_name FROM practice_set_question pq '
            'JOIN question q ON q.id=pq.question_id AND q.deleted=0 '
            'JOIN subject s ON s.id=q.subject_id ')


async def generate_for(db, request, question):
    """为一道错题调一次模型生成相似题（含解析）并写入，返回新行。

    模型出错、返回空内容或公式校验不过都按 502 返回，调用方的题目行保持不变，可以重试。
    """
    stem = stem_of(question)
    links = (await question_links(db, [question['id']])).get(question['id'], [])
    prompt = PromptLibrary()._build_targeted_prompt(
        stem, question['answer'] or '', question['subject_name'], links, question['wrong_answer'],
        has_figure(stem, question['review_reasons']))
    try:
        return await similar.create_similar(db, request, question, prompt)
    except HTTPException as error:
        if 400 <= error.status_code < 500:
            # 公式校验不过等：对前端来说都是"这道生成失败"，统一成 502
            raise HTTPException(502, '相似题生成失败：%s' % error.detail) from error
        raise


@router.post('/{practice_set_id}/prepare')
async def prepare(practice_set_id: int, request: Request):
    """处理题号最靠前的一道"题面是相似题但还没有相似题"的题：能复用就复用，否则生成一道。

    带 {'fallback': true} 时不调模型，直接把这道题改成原题。前端反复调用直到 remaining 为 0。
    """
    payload = await read_optional_payload(request)
    fallback = payload.get('fallback', False)
    if not isinstance(fallback, bool):
        raise HTTPException(422, 'fallback 必须是真或假')
    db = Database(request.scope['env'].DB)
    await load_open_paper(db, practice_set_id)
    pending = await db.all(
        ITEM_SQL + "WHERE pq.practice_set_id=? AND pq.deleted=0 AND pq.form='similar' "
        'AND pq.similar_question_id IS NULL ORDER BY pq.display_order, pq.id', (practice_set_id,))
    if not pending:
        return {'remaining': 0, 'item_id': None, 'fallback': False}
    target = pending[0]
    # 两条 UPDATE 都只改"仍是相似题、仍没配相似题"的行：另一个页面同时在准备这份卷子、
    # 已经先写好这一道时，这边的写入不生效，不会把别人配好的相似题覆盖掉
    if fallback:
        await db.run("UPDATE practice_set_question SET form='original' WHERE id=? AND deleted=0 "
                     "AND form='similar' AND similar_question_id IS NULL", (target['item_id'],))
    else:
        row = await similar.reusable_similar(db, target['id'])
        if row is None:
            row = await generate_for(db, request, target)
        await db.run("UPDATE practice_set_question SET similar_question_id=? WHERE id=? AND deleted=0 "
                     "AND form='similar' AND similar_question_id IS NULL", (row['id'], target['item_id']))
    # 剩余题数按库里重新数（固定一条 SQL，条件和上面的 pending 相同），别的页面同时写过时也准确
    left = await db.first(
        'SELECT COUNT(*) AS count FROM practice_set_question pq JOIN question q ON q.id=pq.question_id AND q.deleted=0 '
        "WHERE pq.practice_set_id=? AND pq.deleted=0 AND pq.form='similar' AND pq.similar_question_id IS NULL",
        (practice_set_id,))
    return {'remaining': left['count'], 'item_id': target['item_id'], 'fallback': fallback}


@router.post('/{practice_set_id}/reroll')
async def reroll(practice_set_id: int, request: Request):
    """把卷子里一道相似题换成新生成的一道；旧的软删除，以后不再复用。"""
    payload = await read_payload(request)
    db = Database(request.scope['env'].DB)
    await load_open_paper(db, practice_set_id)
    item_id = payload.get('item_id')
    target = None
    if is_plain_int(item_id):
        target = await db.first(ITEM_SQL + 'WHERE pq.id=? AND pq.practice_set_id=? AND pq.deleted=0',
                                (item_id, practice_set_id))
    if target is None or target['form'] != 'similar':
        raise HTTPException(422, '这道题不属于这份卷子，或者不是相似题')
    row = await generate_for(db, request, target)
    statements = [('UPDATE practice_set_question SET similar_question_id=? WHERE id=? AND deleted=0',
                   (row['id'], item_id))]
    if target['similar_question_id']:
        statements.append(('UPDATE similar_question SET deleted=1 WHERE id=? AND deleted=0',
                           (target['similar_question_id'],)))
    await batch_or_http(db, statements)
    return {'item_id': item_id, 'similar_text': row['similar_text'], 'similar_answer': row['similar_answer'],
            'explanation': row['explanation']}
