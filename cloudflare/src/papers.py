"""卷子记录接口：卷子（一次考试或一次作业）的列表、详情、手工新增、修改和删除。"""

from fastapi import APIRouter, HTTPException, Request, Response

from database import Database
from intake import hydrate_paper
from intake_model import PAPER_TYPES, IntakeError, normalize_paper
from knowledge import decorate_question, question_links
from question_scope import current_student_id
from questions import attach_papers, stamp_now

router = APIRouter(prefix='/api/papers')

# 历史记录只允许改的字段
HISTORY_EDITABLE = ('name', 'notes')
# 修改接口可以改的字段
EDITABLE_FIELDS = ('name', 'paper_type', 'exam_kind', 'paper_date', 'grade', 'semester', 'score', 'full_score',
                   'notes')
# 列表和详情共用的统计列：题数与待核对数只数未删除的题
COUNT_COLUMNS = ('s.name AS subject_name, COUNT(q.id) AS question_count, '
                 "COALESCE(SUM(CASE WHEN q.review_status='pending' THEN 1 ELSE 0 END),0) AS pending_count")
COUNT_JOIN = ('FROM paper p JOIN subject s ON s.id=p.subject_id '
              'LEFT JOIN question q ON q.paper_id=p.id AND q.deleted=0 ')


async def read_object(request):
    """读取请求体，必须是 JSON 对象，否则 422。"""
    try:
        payload = await request.json()
    except ValueError:
        raise HTTPException(422, '请求内容不是合法的 JSON')
    if not isinstance(payload, dict):
        raise HTTPException(422, '请求内容必须是一个对象')
    return payload


async def load_paper(db, request, paper_id):
    """读取当前学生未删除的卷子行，不存在时 404。"""
    row = await db.first('SELECT * FROM paper WHERE id=? AND deleted=0 AND student_id=?',
                         (paper_id, current_student_id(request)))
    if not row:
        raise HTTPException(404, '记录不存在')
    return row


@router.get('')
async def listing(request: Request, skip: int = 0, limit: int = 20, subject_id: int | None = None,
                  paper_type: str | None = None):
    """分页读取卷子，每项带学科名、题数和待核对数（一条 SQL 算出）。"""
    if skip < 0:
        raise HTTPException(422, 'skip 不能小于 0')
    if not 1 <= limit <= 100:
        raise HTTPException(422, 'limit 应在 1 到 100 之间')
    if paper_type is not None and paper_type not in PAPER_TYPES:
        raise HTTPException(422, '卷子类型不对，只能是 %s' % '、'.join(PAPER_TYPES))
    db = Database(request.scope['env'].DB)
    conditions = ['p.deleted=0', 'p.student_id=?']
    parameters = [current_student_id(request)]
    if subject_id is not None:
        conditions.append('p.subject_id=?')
        parameters.append(subject_id)
    if paper_type is not None:
        conditions.append('p.paper_type=?')
        parameters.append(paper_type)
    where = 'WHERE ' + ' AND '.join(conditions)
    total = (await db.first('SELECT COUNT(*) AS total FROM paper p ' + where, tuple(parameters)))['total']
    rows = await db.all(
        'SELECT p.*, ' + COUNT_COLUMNS + ' ' + COUNT_JOIN + where +
        ' GROUP BY p.id ORDER BY p.paper_date DESC, p.id DESC LIMIT ? OFFSET ?',
        tuple(parameters) + (limit, skip))
    return {'total': total, 'items': [hydrate_paper(row) for row in rows]}


@router.get('/{paper_id}')
async def detail(paper_id: int, request: Request):
    """读取一份卷子和它下面未删除的题（按页码、编号排序，页码为空的排最后）。"""
    db = Database(request.scope['env'].DB)
    row = await db.first(
        'SELECT p.*, ' + COUNT_COLUMNS + ' ' + COUNT_JOIN +
        'WHERE p.id=? AND p.deleted=0 AND p.student_id=? GROUP BY p.id', (paper_id, current_student_id(request)))
    if not row:
        raise HTTPException(404, '记录不存在')
    questions = await db.all(
        'SELECT * FROM question WHERE paper_id=? AND deleted=0 ORDER BY paper_page IS NULL, paper_page, id',
        (paper_id,))
    # 与错题列表同一形状：考点和核对原因各用一次批量查询装配
    links = await question_links(db, [item['id'] for item in questions])
    await attach_papers(db, questions)
    paper = hydrate_paper(row)
    paper['questions'] = [decorate_question(item, links.get(item['id'], [])) for item in questions]
    return paper


@router.post('', status_code=201)
async def create(request: Request):
    """手工新增一份卷子（例如只记一次考试成绩）；不能带照片。"""
    payload = await read_object(request)
    db = Database(request.scope['env'].DB)
    subject = await db.first('SELECT id,name FROM subject WHERE id=? AND deleted=0', (payload.get('subject_id'),))
    if not subject:
        raise HTTPException(400, '学科不存在')
    if payload.get('images'):
        raise HTTPException(422, '手工新增的记录不能带照片')
    stamp = stamp_now()
    try:
        paper = normalize_paper(payload, subject['name'], stamp[:10])
    except IntakeError as error:
        raise HTTPException(422, error.detail)
    meta = await db.run(
        'INSERT INTO paper(student_id,subject_id,name,paper_type,exam_kind,paper_date,grade,semester,score,'
        "full_score,images,notes,source,deleted,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,'[]',?,'manual',0,?,?)",
        (current_student_id(request), subject['id'], paper['name'], paper['paper_type'], paper['exam_kind'],
         paper['paper_date'], paper['grade'], paper['semester'], paper['score'], paper['full_score'],
         paper['notes'], stamp, stamp))
    row = await db.first('SELECT * FROM paper WHERE id=?', (meta['last_row_id'],))
    return hydrate_paper(row)


@router.put('/{paper_id}')
async def update(paper_id: int, request: Request):
    """修改卷子：把库里的现值和请求给出的字段合并后整体校验；年级或学期变了就同步到题目。"""
    payload = await read_object(request)
    db = Database(request.scope['env'].DB)
    old = await load_paper(db, request, paper_id)
    if old['source'] == 'history' and any(key not in HISTORY_EDITABLE for key in payload):
        raise HTTPException(422, '历史记录只能改名称和备注')
    if 'subject_id' in payload and payload['subject_id'] != old['subject_id']:
        raise HTTPException(422, '学科不能修改')
    subject = await db.first('SELECT name FROM subject WHERE id=?', (old['subject_id'],))
    # 没给的字段保持原值，给了 null 表示清空
    merged = {key: payload[key] if key in payload else old[key] for key in EDITABLE_FIELDS}
    merged['images'] = hydrate_paper(old)['images']
    stamp = stamp_now()
    try:
        paper = normalize_paper(merged, subject['name'] if subject else '', stamp[:10])
    except IntakeError as error:
        raise HTTPException(422, error.detail)
    statements = [(
        'UPDATE paper SET name=?,paper_type=?,exam_kind=?,paper_date=?,grade=?,semester=?,score=?,full_score=?,'
        'notes=?,updated_at=? WHERE id=? AND deleted=0',
        (paper['name'], paper['paper_type'], paper['exam_kind'], paper['paper_date'], paper['grade'],
         paper['semester'], paper['score'], paper['full_score'], paper['notes'], stamp, paper_id))]
    if paper['grade'] != old['grade'] or paper['semester'] != old['semester']:
        # 题目的年级、学期跟着卷子走；已删除的题也一并改，恢复时才不会不一致
        statements.append(('UPDATE question SET grade=?,semester=?,updated_at=? WHERE paper_id=?',
                           (paper['grade'], paper['semester'], stamp, paper_id)))
    await db.batch(statements)
    return hydrate_paper(await db.first('SELECT * FROM paper WHERE id=?', (paper_id,)))


@router.delete('/{paper_id}', status_code=204)
async def remove(paper_id: int, request: Request, with_questions: int = 0):
    """软删除卷子；下面还有题时必须明确带题删除（with_questions=1），历史记录不能删。"""
    db = Database(request.scope['env'].DB)
    old = await load_paper(db, request, paper_id)
    if old['source'] == 'history':
        raise HTTPException(409, '历史记录不能删除')
    count = (await db.first('SELECT COUNT(*) AS total FROM question WHERE paper_id=? AND deleted=0',
                            (paper_id,)))['total']
    if count and with_questions != 1:
        raise HTTPException(409, '这份记录下还有 %d 道题' % count)
    stamp = stamp_now()
    # 卷子和题目在同一个批处理里删除，不会留下指向已删卷子的题
    await db.batch([
        ('UPDATE question SET deleted=1,updated_at=? WHERE paper_id=? AND deleted=0', (stamp, paper_id)),
        ('UPDATE paper SET deleted=1,updated_at=? WHERE id=?', (stamp, paper_id))])
    return Response(status_code=204)
