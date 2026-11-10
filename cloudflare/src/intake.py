"""录入资料接口：给读图录题的程序一次取全提交前需要的资料。"""

from fastapi import APIRouter, HTTPException, Request

from database import Database
from intake_model import EXAM_KINDS, PAPER_TYPES, REVIEW_REASONS, SPEC_VERSION
import settings

router = APIRouter()

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


async def load_error_type_names(db, subject_id):
    """该学科可用的错因名称（本学科的加上通用的）。"""
    rows = await db.all('SELECT name FROM error_type WHERE deleted=0 AND (subject_id=? OR subject_id IS NULL)',
                        (subject_id,))
    return {row['name'] for row in rows}


@router.get('/api/intake/guide')
async def guide(request: Request, subject_id: int | None = None, subject: str | None = None,
                grade: int | None = None, semester: int | None = None):
    """返回录题规范版本、学科、考点目录、错因和各选项的中文名称。"""
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
    error_types = sorted(await load_error_type_names(db, current['id']))
    return {
        'spec_version': SPEC_VERSION,
        'subject': {'id': current['id'], 'name': current['name']},
        'subjects': [{'id': row['id'], 'name': row['name']} for row in subjects],
        'grade': grade, 'semester': semester,
        'default_grade': default_grade, 'default_semester': default_semester,
        'catalog_available': bool(modules),
        'knowledge_modules': modules,
        'error_types': error_types,
        'paper_types': {key: PAPER_TYPE_LABELS[key] for key in PAPER_TYPES},
        'exam_kinds': {key: EXAM_KIND_LABELS[key] for key in EXAM_KINDS},
        'review_reasons': {key: REVIEW_REASON_LABELS[key] for key in REVIEW_REASONS},
    }
