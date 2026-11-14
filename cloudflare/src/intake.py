"""录入资料接口：给读图录题的程序一次取全提交前需要的资料。"""

import hashlib
import json
import re

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

from database import Database
from intake_model import (EXAM_KINDS, MAX_QUESTIONS, PAPER_TYPES, REVIEW_REASONS, SPEC_VERSION, IntakeError,
                          decide_review, is_plain_int, normalize_paper, normalize_question)
from knowledge import (decorate_question, ensure_guard_rows, guard_statement, question_links, resolve_many,
                       structure_statement)
from knowledge_model import map_error
from pdf import validate_math
from question_scope import current_student_id
from questions import batch_error, hydrate as hydrate_question, stamp_now
import settings

router = APIRouter()

REQUEST_ID_PATTERN = re.compile(r'^[A-Za-z0-9-]{8,64}$')
VERSION_MISMATCH_TEXT = '录入规范版本不一致，请先更新录入规范（重新运行安装脚本）'
MAX_PARENT_REPLY_LENGTH = 200
CHANGED_REPLAY_TEXT = ('这个提交文件的内容和第一次提交时不一样，这次没有写入任何内容。'
                       '改过的卷子要重新生成一个提交文件（不要带旧的 request_id）再提交。')
DELETED_REPLAY_TEXT = ('这个提交文件对应的记录已经被删除了，这次没有写入任何内容。'
                       '要重新录入，请重新生成一个提交文件（不要带旧的 request_id）再提交。')
PARENT_REPLY_TEXT = ('还没有写明家长是怎么回答的。提交前要问家长一次"这是哪份作业或卷子？如果是考试，多少分？"，'
                     '把家长的回答（原话、"跳过"或"家长说不用问"）写进 parent_reply。')
# 题目表里由本接口写入的列；每一项在传给数据库的 JSON 里同名
QUESTION_FIELDS = ('id', 'subject_id', 'student_id', 'paper_id', 'paper_page', 'question_no', 'original_image',
                   'original_images', 'original_text', 'parsed_question', 'answer', 'analysis', 'wrong_answer',
                   'wrong_evidence', 'difficulty', 'grade', 'semester', 'knowledge_point',
                   'knowledge_revision', 'review_status', 'review_reasons', 'review_note')

PAPER_TYPE_LABELS = {'homework': '作业', 'chapter_practice': '章节练习', 'exam': '考试'}
EXAM_KIND_LABELS = {'unit': '单元测', 'midterm': '期中', 'final': '期末', 'other': '其他'}
REVIEW_REASON_LABELS = {'wrong_unclear': '不确定这题是否做错了', 'text_unclear': '照片模糊或题干拿不准',
                        'kp_unsure': '目录里找不到合适的考点', 'other': '其他'}


async def load_catalog(db, subject_id, grade, semester):
    """返回 [{'id','name','points':[{'id','name'}]}]，只含有二级考点的模块。"""
    # 一次查出该学科的一、二级行，在 Python 里筛选和组装，避免逐个模块查询
    rows = await db.all('SELECT id,name,level,parent_id,grade,semester FROM knowledge_point '
                        'WHERE deleted=0 AND subject_id=? AND level IN (1,2) ORDER BY sort_order,id', (subject_id,))
    modules = {row['id']: {'id': row['id'], 'name': row['name'], 'points': []} for row in rows if row['level'] == 1}
    for row in rows:
        if row['level'] != 2 or row['parent_id'] not in modules:
            continue
        # 与 knowledge.tree 一致：年级、学期为空表示不限
        if grade is not None and row['grade'] not in (None, grade):
            continue
        if semester is not None and row['semester'] not in (None, semester):
            continue
        modules[row['parent_id']]['points'].append({'id': row['id'], 'name': row['name']})
    return [module for module in modules.values() if module['points']]


@router.get('/api/intake/guide')
async def guide(request: Request, subject_id: int | None = None, subject: str | None = None,
                grade: int | None = None, semester: int | None = None):
    """返回录题规范版本、学科、考点目录和各选项的中文名称（错因已停用，不再返回）。"""
    if grade is not None and not 1 <= grade <= 12:
        raise HTTPException(422, '年级应在 1 到 12 之间')
    if semester is not None and semester not in (1, 2):
        raise HTTPException(422, '学期应为 1 或 2')
    db = Database(request.scope['env'].DB)
    subjects = await db.all('SELECT id,name FROM subject WHERE deleted=0 ORDER BY id')
    # subject_id 优先，否则按名称找
    if subject_id is not None:
        current = next((row for row in subjects if row['id'] == subject_id), None)
    elif subject:
        current = next((row for row in subjects if row['name'] == subject.strip()), None)
    else:
        current = None
    if current is None:
        raise HTTPException(400, '学科不存在')
    app_config = await settings.load(request, 'app')
    default_grade = app_config.get('default_grade')
    default_semester = app_config.get('default_semester')
    if grade is None:
        grade = default_grade
    if semester is None:
        semester = default_semester
    modules = await load_catalog(db, current['id'], grade, semester)
    return {
        'spec_version': SPEC_VERSION,
        'subject': {'id': current['id'], 'name': current['name']},
        'subjects': [{'id': row['id'], 'name': row['name']} for row in subjects],
        'grade': grade, 'semester': semester,
        'default_grade': default_grade, 'default_semester': default_semester,
        'catalog_available': bool(modules),
        'knowledge_modules': modules,
        'paper_types': {key: PAPER_TYPE_LABELS[key] for key in PAPER_TYPES},
        'exam_kinds': {key: EXAM_KIND_LABELS[key] for key in EXAM_KINDS},
        'review_reasons': {key: REVIEW_REASON_LABELS[key] for key in REVIEW_REASONS},
    }


# ---------------------------------------------------------------- 提交一份卷子（试提交与正式提交共用校验）


def hydrate_paper(row):
    """返回卷子记录的副本，其中 images 由 JSON 文本转成列表，其余字段原样。"""
    paper = dict(row)
    paper['images'] = json.loads(paper.get('images') or '[]')
    return paper


def error_item(index, detail):
    """一条问题：index 是题目在请求里的序号，卷子本身或公式的问题为 None。"""
    return {'index': index, 'detail': detail}


async def read_payload(request):
    """读取请求体，必须是 JSON 对象，否则 422。"""
    try:
        payload = await request.json()
    except ValueError:
        raise HTTPException(422, '请求内容不是合法的 JSON')
    if not isinstance(payload, dict):
        raise HTTPException(422, '请求内容必须是一个对象')
    return payload


def version_mismatch_response(payload):
    """录入规范版本和服务端不一致时返回 409 响应，一致时返回 None。"""
    version = payload.get('spec_version')
    if is_plain_int(version) and version == SPEC_VERSION:
        return None
    return JSONResponse({'detail': VERSION_MISMATCH_TEXT, 'spec_version': SPEC_VERSION}, status_code=409)


def valid_request_id(payload):
    """正式提交必须带 request_id：8 到 64 位的字母、数字、连字符；合规返回它，否则返回 None。"""
    request_id = payload.get('request_id')
    if isinstance(request_id, str) and REQUEST_ID_PATTERN.fullmatch(request_id):
        return request_id
    return None


def questions_count_ok(raw_questions):
    """题目必须是列表，且数量在 1 到 100 之间。"""
    return isinstance(raw_questions, list) and 1 <= len(raw_questions) <= MAX_QUESTIONS


def paper_level_errors(raw_paper, raw_questions):
    """检查卷子和题目列表的外形，返回问题列表（卷子必须是对象、题目数量 1 到 100）。"""
    errors = []
    if not isinstance(raw_paper, dict):
        errors.append(error_item(None, '卷子信息（paper）的格式不对，应是一个对象'))
    if not isinstance(raw_questions, list):
        errors.append(error_item(None, '题目（questions）必须是一个列表'))
    elif not raw_questions:
        errors.append(error_item(None, '至少要有 1 道题'))
    elif len(raw_questions) > MAX_QUESTIONS:
        errors.append(error_item(None, '一份卷子最多 %d 道题，现在有 %d 道' % (MAX_QUESTIONS, len(raw_questions))))
    return errors


async def find_subject(db, raw_paper):
    """按卷子里的 subject_id 找学科，找不到返回 None。"""
    subject_id = raw_paper.get('subject_id')
    if not is_plain_int(subject_id):
        return None
    return await db.first('SELECT id,name FROM subject WHERE id=? AND deleted=0', (subject_id,))


def count_images(raw_paper):
    """照片张数；照片字段不是列表（卷子检查已报错）时返回 None，表示无法检查页码。"""
    images = raw_paper.get('images')
    if images is None:
        return 0
    return len(images) if isinstance(images, list) else None


def normalize_all_questions(raw_questions, image_count):
    """逐题整理，收集全部错误而不是遇到第一处就停；返回 (整理后的题 {序号: 题}, 问题列表)。"""
    questions, errors = {}, []
    for index, raw in enumerate(raw_questions):
        if not isinstance(raw, dict):
            errors.append(error_item(index, '这道题的格式不对，应是一个对象'))
            continue
        try:
            questions[index] = normalize_question(raw, image_count)
        except IntakeError as error:
            errors.append(error_item(index, error.detail))
    return questions, errors


async def resolve_knowledge(db, subject_id, questions):
    """对通过整理的题一次性解析考点（只认编号），把结果记进题里；返回考点方面的问题列表。"""
    indexes = sorted(questions)
    entries = [({'knowledge_point_ids': questions[index]['knowledge_point_ids'],
                 'primary_knowledge_point_id': questions[index]['primary_knowledge_point_id']}, None, [], False)
               for index in indexes]
    resolved = await resolve_many(db, subject_id, entries) if entries else []
    errors = []
    for index, (plan, detail) in zip(indexes, resolved):
        if detail:
            errors.append(error_item(index, detail))
        else:
            questions[index]['plan'] = plan
    return errors


async def check_math_formulas(request, questions):
    """数学卷子：整份的题干、答案、解析一次交给公式校验；校验器的话照搬，返回问题列表。"""
    texts = [questions[index][key] for index in sorted(questions)
             for key in ('parsed_question', 'answer', 'analysis') if questions[index][key]]
    try:
        await validate_math(request, texts)
    except HTTPException as error:
        # 校验服务本身出故障（5xx）不是卷子的问题，不能说成公式有错
        if error.status_code >= 500:
            raise
        return [error_item(None, str(error.detail))]
    return []


async def decide_all(db, subject, paper, questions):
    """按这个年级有没有考点目录，逐题决定直接入库还是待核对，结果记进题里。"""
    catalog = await load_catalog(db, subject['id'], paper['grade'], paper['semester'])
    for question in questions.values():
        question['status'], question['reasons'] = decide_review(question, bool(catalog))


def parent_reply_errors(payload):
    """家长的回答必须写明：文字、去掉首尾空白后不为空、最长 200 个字符；不合格返回一条卷子级问题。"""
    reply = payload.get('parent_reply')
    if isinstance(reply, str) and 1 <= len(reply.strip()) <= MAX_PARENT_REPLY_LENGTH:
        return []
    return [error_item(None, PARENT_REPLY_TEXT)]


async def fill_default_grade(request, raw_paper):
    """年级、学期没给（缺省或为 null）时用应用默认值，两者各自独立补；返回补完后的卷子副本。

    默认值也没有时保持为空。必须在读考点目录、判定待核对之前调用。
    """
    filled = dict(raw_paper)
    if filled.get('grade') is not None and filled.get('semester') is not None:
        return filled
    app_config = await settings.load(request, 'app')
    if filled.get('grade') is None:
        filled['grade'] = app_config.get('default_grade')
    if filled.get('semester') is None:
        filled['semester'] = app_config.get('default_semester')
    return filled


async def validate_submission(request, db, payload):
    """试提交和正式提交共用的全部检查，不写任何数据。

    返回 {'errors': 问题列表, 'subject', 'paper', 'questions': [按序号排好的题]}。
    问题的顺序：卷子和公式的问题（index 为 None）在前，题目的问题按序号。
    """
    raw_paper, raw_questions = payload.get('paper'), payload.get('questions')
    # 家长的回答排在卷子级问题的最前面
    paper_errors = parent_reply_errors(payload) + paper_level_errors(raw_paper, raw_questions)
    result = {'errors': paper_errors, 'subject': None, 'paper': None, 'questions': []}
    if not isinstance(raw_paper, dict):
        return result
    subject = await find_subject(db, raw_paper)
    if subject is None:
        paper_errors.append(error_item(None, '学科不存在'))
        return result
    result['subject'] = subject
    # 先补年级学期：后面的整理、考点目录、待核对判断都用补完之后的值
    raw_paper = await fill_default_grade(request, raw_paper)
    paper = None
    try:
        paper = normalize_paper(raw_paper, subject['name'], stamp_now()[:10])
    except IntakeError as error:
        paper_errors.append(error_item(None, error.detail))
    result['paper'] = paper
    # 题目数量不对、或照片字段本身不对（无法判断页码）时不逐题检查，免得报出一堆连带的错
    image_count = count_images(raw_paper)
    if not questions_count_ok(raw_questions) or image_count is None:
        return result
    questions, question_errors = normalize_all_questions(raw_questions, image_count)
    question_errors += await resolve_knowledge(db, subject['id'], questions)
    # 前面没有任何错时才送检公式，整份卷子只调用一次
    if not paper_errors and not question_errors and subject['name'] == '数学':
        paper_errors += await check_math_formulas(request, questions)
    result['errors'] = paper_errors + sorted(question_errors, key=lambda item: item['index'])
    if result['errors']:
        return result
    await decide_all(db, subject, paper, questions)
    result['questions'] = [questions[index] for index in sorted(questions)]
    return result


def summarize(statuses):
    """统计总数、直接入库数、待核对数。"""
    approved = sum(1 for status in statuses if status == 'approved')
    return {'total_count': len(statuses), 'approved_count': approved, 'pending_count': len(statuses) - approved}


def check_body(result):
    """试提交的返回内容；有错时三个数量为 0。"""
    if result['errors']:
        counts = summarize([])
    else:
        counts = summarize([question['status'] for question in result['questions']])
    paper = None
    if result['paper'] is not None:
        paper = {**result['paper'], 'subject_id': result['subject']['id']}
    return {'ok': not result['errors'], 'errors': result['errors'], 'paper': paper, **counts}


def invalid_response(errors):
    """正式提交校验不过：422，带问题清单。"""
    return JSONResponse({'detail': '有 %d 处需要修改' % len(errors), 'errors': errors}, status_code=422)


# ---------------------------------------------------------------- 正式提交：写入与重放


def payload_fingerprint(payload):
    """整个请求体的内容指纹：键排序后的紧凑 JSON 的 UTF-8 字节做 SHA-256，返回十六进制文字。"""
    text = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(',', ':'))
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


async def find_replay_record(db, request_id):
    """这个 request_id 以前提交过就返回 (卷子编号, 内容指纹)，没有返回 None。

    记录的值是“卷子编号:内容指纹”；没有冒号的（只可能是手工插入的旧格式）指纹为 None，表示不比较。
    """
    record = await db.first('SELECT value FROM request_record WHERE name=? AND deleted=0', ('intake:' + request_id,))
    if not record:
        return None
    paper_id, _, fingerprint = record['value'].partition(':')
    return int(paper_id), (fingerprint or None)


async def replay_conflict(db, paper_id, stored_fingerprint, fingerprint):
    """重放时的两种不能照旧返回的情况：内容变了、卷子已被删除；都不是返回 None。

    响应体里故意不带 spec_version，小工具靠它区分“版本不一致”。
    """
    if stored_fingerprint is not None and stored_fingerprint != fingerprint:
        return JSONResponse({'detail': CHANGED_REPLAY_TEXT}, status_code=409)
    paper = await db.first('SELECT deleted FROM paper WHERE id=?', (paper_id,))
    if paper is None or paper['deleted']:
        return JSONResponse({'detail': DELETED_REPLAY_TEXT}, status_code=409)
    return None


async def load_result_body(db, paper_id, replayed):
    """读出卷子和它的题目，组成正式提交的返回内容（首次成功和重放共用）。"""
    paper = await db.first('SELECT * FROM paper WHERE id=?', (paper_id,))
    rows = await db.all('SELECT * FROM question WHERE paper_id=? AND deleted=0 ORDER BY id', (paper_id,))
    links = await question_links(db, [row['id'] for row in rows])
    for row in rows:
        row['original_images'] = json.loads(row['original_images'] or 'null')
        row['review_reasons'] = json.loads(row['review_reasons'] or '[]')
        row['tags'] = []
        row['similar_questions'] = []
        decorate_question(row, links.get(row['id'], []))
    counts = summarize([row['review_status'] for row in rows])
    return {'paper': hydrate_paper(paper), 'questions': rows, **counts, 'errors': [], 'replayed': replayed}


def build_question_records(checked, student_id):
    """把检查通过的题整理成要写入的记录（编号和卷子编号稍后补上）。"""
    paper, subject = checked['paper'], checked['subject']
    records = []
    for question in checked['questions']:
        # 题目的原图是它那一页的照片；卷子没有照片时为空
        key = paper['images'][question['page'] - 1] if question['page'] is not None else None
        plan = question['plan']
        records.append({
            'subject_id': subject['id'], 'student_id': student_id, 'paper_page': question['page'],
            'question_no': question['question_no'], 'original_image': key,
            'original_images': json.dumps([key], ensure_ascii=False) if key else None,
            'original_text': question['parsed_question'], 'parsed_question': question['parsed_question'],
            'answer': question['answer'], 'analysis': question['analysis'],
            'wrong_answer': question['wrong_answer'], 'wrong_evidence': question['wrong_evidence'],
            'difficulty': question['difficulty'],
            'grade': paper['grade'], 'semester': paper['semester'],
            # 旧的文字字段保存主考点名称，没有考点时为空
            'knowledge_point': plan['points'][plan['primary']]['name'] if plan['primary'] else None,
            'knowledge_revision': 0, 'review_status': question['status'],
            'review_reasons': json.dumps(question['reasons'], ensure_ascii=False),
            'review_note': question['review_note'],
            'knowledge_ids': plan['ids'], 'primary': plan['primary'],
        })
    return records


def build_write_statements(checked, records, request_id, fingerprint, student_id, stamp, max_question_id,
                           max_paper_id):
    """拼出一次提交的全部写入语句：守卫、卷子、题目、考点关联、结构断言、防重复记录。"""
    paper, subject = checked['paper'], checked['subject']
    paper_id = max_paper_id + 1
    for offset, record in enumerate(records):
        record['id'] = max_question_id + offset + 1
        record['paper_id'] = paper_id
    # 守卫：题目和卷子的最大编号都没变（没有别的写入插进来），并且守卫行存在
    statements = [guard_statement(
        '(SELECT COALESCE(MAX(id),0) FROM question)=? AND (SELECT COALESCE(MAX(id),0) FROM paper)=? AND '
        'EXISTS(SELECT 1 FROM write_guard WHERE id=1 AND deleted=0)', (max_question_id, max_paper_id))]
    statements.append((
        'INSERT INTO paper(id,student_id,subject_id,name,paper_type,exam_kind,paper_date,grade,semester,score,'
        "full_score,images,notes,source,deleted,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,'agent',0,?,?)",
        (paper_id, student_id, subject['id'], paper['name'], paper['paper_type'], paper['exam_kind'],
         paper['paper_date'], paper['grade'], paper['semester'], paper['score'], paper['full_score'],
         json.dumps(paper['images'], ensure_ascii=False), paper['notes'], stamp, stamp)))
    statements.append((
        'INSERT INTO question(' + ','.join(QUESTION_FIELDS) + ',review_count,correct_count,error_count,deleted,'
        'created_at,updated_at) SELECT ' + ','.join("json_extract(value,'$." + key + "')" for key in QUESTION_FIELDS)
        + ',0,0,0,0,?,? FROM json_each(?)',
        (stamp, stamp, json.dumps(records, ensure_ascii=False))))
    pairs = [{'question_id': record['id'], 'ids': record['knowledge_ids'], 'primary': record['primary']}
             for record in records if record['knowledge_ids']]
    if pairs:
        statements.append((
            'INSERT INTO question_knowledge_point(question_id,knowledge_point_id,is_primary,source,deleted,'
            'created_at,updated_at) '
            "SELECT json_extract(p.value,'$.question_id'),i.value,"
            "CASE WHEN i.value=json_extract(p.value,'$.primary') THEN 1 ELSE 0 END,"
            "'agent',0,?,? FROM json_each(?) p, json_each(json_extract(p.value,'$.ids')) i",
            (stamp, stamp, json.dumps(pairs, ensure_ascii=False))))
    statements.append(structure_statement([record['id'] for record in records]))
    # 防重复记录放在同一个事务里：同一个编号撞车时这里会因主键冲突整批回滚
    statements.append(('INSERT INTO request_record(name,value,deleted,created_at) VALUES(?,?,0,?)',
                       ('intake:' + request_id, '%d:%s' % (paper_id, fingerprint), stamp)))
    return paper_id, statements


async def write_submission(db, request, checked, request_id, fingerprint):
    """用一个 db.batch 写入整份卷子；返回 (卷子编号, 是否其实是重放, 已有记录的指纹)。

    编号冲突（守卫失败，409）时重新取编号重试一次，写法同 questions.batch。
    """
    await ensure_guard_rows(db)
    student_id = current_student_id(request)
    stamp = stamp_now()
    for attempt in range(2):
        maximums = await db.first('SELECT (SELECT COALESCE(MAX(id),0) FROM question) AS question_id,'
                                  '(SELECT COALESCE(MAX(id),0) FROM paper) AS paper_id')
        records = build_question_records(checked, student_id)
        paper_id, statements = build_write_statements(
            checked, records, request_id, fingerprint, student_id, stamp, maximums['question_id'],
            maximums['paper_id'])
        try:
            await db.batch(statements)
            return paper_id, False, None
        except Exception as error:
            # 别的相同提交已经写成功：本次按重放处理，不报 500
            existing = await find_replay_record(db, request_id)
            if existing is not None:
                return existing[0], True, existing[1]
            mapped = map_error(error)
            if mapped and mapped[0] == 409 and attempt == 0:
                continue
            batch_error(error)


@router.post('/api/intake/papers/check')
async def check_paper(request: Request):
    """试提交：做全部检查，不写入任何数据；除版本不一致（409）外总是 200。"""
    payload = await read_payload(request)
    mismatch = version_mismatch_response(payload)
    if mismatch:
        return mismatch
    db = Database(request.scope['env'].DB)
    return check_body(await validate_submission(request, db, payload))


@router.post('/api/intake/papers', status_code=201)
async def submit_paper(request: Request):
    """正式提交：检查通过后一次写入卷子、全部题目和考点关联，有任何问题就什么都不写。"""
    payload = await read_payload(request)
    mismatch = version_mismatch_response(payload)
    if mismatch:
        return mismatch
    request_id = valid_request_id(payload)
    if request_id is None:
        return JSONResponse({'detail': 'request_id 必填，应是 8 到 64 位的字母、数字和连字符'}, status_code=422)
    db = Database(request.scope['env'].DB)
    # 重放：同一个编号提交过，直接读出第一次的结果，不再检查也不写入
    fingerprint = payload_fingerprint(payload)
    previous = await find_replay_record(db, request_id)
    if previous is not None:
        conflict = await replay_conflict(db, previous[0], previous[1], fingerprint)
        return conflict or JSONResponse(await load_result_body(db, previous[0], True), status_code=200)
    checked = await validate_submission(request, db, payload)
    if checked['errors']:
        return invalid_response(checked['errors'])
    paper_id, replayed, stored_fingerprint = await write_submission(db, request, checked, request_id, fingerprint)
    if replayed:
        # 撞车时别人先写入了：同样要核对内容和卷子状态
        conflict = await replay_conflict(db, paper_id, stored_fingerprint, fingerprint)
        if conflict:
            return conflict
    body = await load_result_body(db, paper_id, replayed)
    return JSONResponse(body, status_code=200) if replayed else body


@router.get('/api/questions/review/count')
async def review_count(request: Request):
    """返回等待家长核对的题目数量。"""
    db = Database(request.scope['env'].DB)
    row = await db.first("SELECT COUNT(*) AS total FROM question WHERE deleted=0 AND review_status='pending'")
    return {'pending': row['total']}


@router.post('/api/questions/{question_id}/review')
async def review_question(question_id: int, request: Request):
    """通过或移除一道待核对的题；条件更新保证两人同时操作时只有一人成功。"""
    payload = await read_payload(request)
    action = payload.get('action')
    db = Database(request.scope['env'].DB)
    row = await db.first('SELECT id,review_status FROM question WHERE id=? AND deleted=0', (question_id,))
    if row is None:
        raise HTTPException(404, '错题不存在')
    if action not in ('approve', 'reject'):
        raise HTTPException(422, '操作只能是 approve 或 reject')
    if row['review_status'] != 'pending':
        raise HTTPException(409, '这道题已经处理过了')
    if action == 'approve' and await db.first(
            'SELECT 1 AS ok FROM question_knowledge_point WHERE question_id=? AND deleted=0 AND is_primary=1',
            (question_id,)) is None:
        raise HTTPException(422, '请先选择考点再通过')
    stamp = stamp_now()
    # 通过只改状态，移除同时软删除；WHERE 里再次要求待核对，晚到的一方拿不到返回行
    changes = "review_status='approved'" if action == 'approve' else "deleted=1,review_status='rejected'"
    done = await db.first(
        'UPDATE question SET ' + changes + ',reviewed_at=?,updated_at=? '
        "WHERE id=? AND deleted=0 AND review_status='pending' RETURNING id", (stamp, stamp, question_id))
    if done is None:
        raise HTTPException(409, '这道题已经处理过了')
    if action == 'reject':
        return {'id': question_id, 'review_status': 'rejected'}
    return await hydrate_question(db, await db.first('SELECT * FROM question WHERE id=?', (question_id,)))
