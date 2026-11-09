"""学习报告：服务端写入模块指标，模型只生成叙述与建议。

新报告 content 带 schema_version=2 与 taxonomy_version；旧报告保持原样展示，
不按当前目录重写，也不重新调用模型。
"""

import json
from datetime import timedelta
from fastapi import APIRouter, HTTPException, Query, Request
from database import Database
from analytics import now
from knowledge_stats import COUNTING_MODE, module_stats
from settings import generate_json
from prompts import PromptLibrary

router = APIRouter(prefix='/api/learning-reports')


@router.get('/list')
async def listing(request: Request, skip: int = Query(0, ge=0), limit: int = Query(20, ge=1, le=100),
                  subject_id: int | None = None, grade: int | None = Query(None, ge=1, le=12)):
    """分页读取历史报告，不重复调用模型。"""
    db = Database(request.scope['env'].DB)
    filters, values = ['r.deleted=0'], []
    for key, value in [('subject_id', subject_id), ('grade', grade)]:
        if value is not None:
            filters.append('r.' + key + '=?')
            values.append(value)
    where = ' AND '.join(filters)
    count = await db.first('SELECT COUNT(*) AS total FROM learning_report r WHERE ' + where, values)
    rows = await db.all(
        'SELECT r.id,r.title,r.subject_id,s.name AS subject_name,r.grade,r.time_range_days,'
        'r.total_questions,r.total_words,r.overall_accuracy,r.created_at '
        'FROM learning_report r LEFT JOIN subject s ON s.id=r.subject_id AND s.deleted=0 WHERE '
        + where + ' ORDER BY r.created_at DESC,r.id DESC LIMIT ? OFFSET ?', [*values, limit, skip])
    return {'total': count['total'], 'items': rows}


@router.get('/{report_id}')
async def detail(report_id: int, request: Request):
    """读取已保存报告内容；旧报告带 legacy 标记。"""
    row = await Database(request.scope['env'].DB).first(
        'SELECT r.*,s.name AS subject_name FROM learning_report r '
        'LEFT JOIN subject s ON s.id=r.subject_id AND s.deleted=0 WHERE r.id=? AND r.deleted=0',
        (report_id,))
    if not row:
        raise HTTPException(404, '报告不存在')
    row['content'] = json.loads(row['content']) if row['content'] else {}
    row['legacy_schema'] = row['content'].get('schema_version', 1) < 2
    row['schema_version'] = row['content'].get('schema_version', 1)
    return row


@router.delete('/{report_id}')
async def delete(report_id: int, request: Request):
    """软删除报告。"""
    if not await Database(request.scope['env'].DB).first(
            'UPDATE learning_report SET deleted=1 WHERE id=? AND deleted=0 RETURNING id', (report_id,)):
        raise HTTPException(404, '报告不存在')
    return {'message': '删除成功'}


@router.post('/generate')
async def generate(request: Request):
    """汇总真实指标后生成叙述；模块数值由服务端写入 content.metrics。"""
    payload = await request.json()
    db = Database(request.scope['env'].DB)
    grade = payload.get('grade')
    days = payload.get('time_range_days')
    subject_id = payload.get('subject_id')
    if grade is not None and (type(grade) is not int or not 1 <= grade <= 12):
        raise HTTPException(422, '年级无效')
    if days is not None and (type(days) is not int or not 1 <= days <= 3650):
        raise HTTPException(422, '时间范围无效')
    subject = await db.first('SELECT name FROM subject WHERE id=? AND deleted=0', (subject_id,)) if subject_id else None
    if subject_id and not subject:
        raise HTTPException(404, '学科不存在')
    filters, values = ['q.deleted=0'], []
    for field, value in [('subject_id', subject_id), ('grade', grade)]:
        if value is not None:
            filters.append('q.' + field + '=?')
            values.append(value)
    if days:
        filters.append('q.created_at>=?')
        values.append((now() - timedelta(days=days)).isoformat(' '))
    where = ' AND '.join(filters)
    q = await db.first('SELECT COUNT(*) AS total,COALESCE(SUM(review_count),0) AS reviews,COALESCE(SUM(correct_count),0) AS correct,SUM(COALESCE(review_count,0)=0) AS none,SUM(review_count=1) AS once,SUM(review_count BETWEEN 2 AND 5) AS several,SUM(review_count>5) AS many FROM question q WHERE ' + where, values)
    distributions = {}
    for field in ('difficulty', 'error_type'):
        rows = await db.all('SELECT q.' + field + ' AS name,COUNT(*) AS count FROM question q WHERE ' + where + ' GROUP BY q.' + field, values)
        distributions[field] = {str(row['name']): row['count'] for row in rows if row['name'] is not None}
    modules = await module_stats(db, subject_id=subject_id, grade=grade, days=days,
                                 level=1, practice_days=days)
    points = [{'module_id': item['id'], 'name': item['name'], 'count': item['question_count'],
               'accuracy': item['accuracy'], 'share_percent': item['share_percent']}
              for item in modules['items']]
    wf, wv = ['deleted=0', 'review_count>0'], []
    if grade is not None:
        wf.append('grade=?')
        wv.append(grade)
    if days:
        wf.append('created_at>=?')
        wv.append((now() - timedelta(days=days)).isoformat(' '))
    include_words = not subject or '英' in subject['name']
    w = await db.first('SELECT COUNT(*) AS total,COALESCE(SUM(review_count),0) AS reviews,COALESCE(SUM(correct_count),0) AS correct FROM word WHERE ' + ' AND '.join(wf), wv) if include_words else {'total': 0, 'reviews': 0, 'correct': 0}
    low = await db.all('SELECT english AS word,ROUND(correct_count*100.0/review_count,1) AS accuracy FROM word WHERE ' + ' AND '.join(wf) + ' AND correct_count*1.0/review_count<0.7 ORDER BY accuracy LIMIT 10', wv) if include_words else []
    if not q['total'] and not w['total']:
        raise HTTPException(400, '没有足够的数据生成报告，请调整筛选条件')
    summary = {
        'questions': {'total': q['total'], 'difficulty_distribution': distributions['difficulty'],
                      'error_type_distribution': distributions['error_type'],
                      'knowledge_module_distribution': {item['name']: item['question_count'] for item in modules['items']},
                      'knowledge_modules': points,
                      'unclassified_count': modules['unclassified_count'],
                      'review_distribution': {'未复习': q['none'] or 0, '复习1次': q['once'] or 0,
                                              '复习2-5次': q['several'] or 0, '复习5次以上': q['many'] or 0}},
        'words': {'total': w['total'], 'total_reviews': w['reviews'],
                  'accuracy': round(w['correct'] / w['reviews'] * 100, 1) if w['reviews'] else 0,
                  'low_accuracy_words': low},
    }
    content = await generate_json(
        request, PromptLibrary()._build_learning_report_prompt(
            subject['name'] if subject else None, grade, days, summary))
    if not isinstance(content, dict):
        raise HTTPException(502, '模型没有返回有效的报告内容')
    content['schema_version'] = 2
    content['metrics'] = {
        'taxonomy_version': modules['taxonomy_version'],
        'counting_mode': COUNTING_MODE,
        'level': 1,
        'total_questions': modules['total_questions'],
        'unclassified_count': modules['unclassified_count'],
        'modules': [{key: item[key] for key in
                     ('id', 'name', 'parent_id', 'subject_id', 'subject_name', 'question_count',
                      'primary_question_count', 'share_percent', 'reviewed_question_count',
                      'review_coverage', 'answer_count', 'correct_count', 'accuracy')}
                    for item in modules['items']],
        'time_window': {'question_created_days': days, 'practice_reviewed_days': days},
    }
    content['module_names'] = {str(item['id']): item['name'] for item in modules['items']}
    accuracy = round((q['correct'] + w['correct']) / (q['reviews'] + w['reviews']) * 100, 1) if q['reviews'] + w['reviews'] else 0
    content['overview'] = {'total_questions': q['total'], 'total_words': w['total'], 'overall_accuracy': accuracy}
    title = payload.get('title') or now().strftime('%Y年%m月%d日') + (subject['name'] if subject else '全科') + (' ' + str(grade) + '年级' if grade else '') + ' 学习状态分析'
    row = await db.first(
        'INSERT INTO learning_report(title,subject_id,grade,time_range_days,content,total_questions,'
        'total_words,overall_accuracy,deleted,created_at) VALUES(?,?,?,?,?,?,?,?,0,?) RETURNING id',
        (title, subject_id, grade, days, json.dumps(content, ensure_ascii=False),
         q['total'], w['total'], accuracy, now().isoformat(' ')))
    return {'id': row['id'], 'title': title, 'schema_version': 2,
            'taxonomy_version': modules['taxonomy_version'], 'message': '报告生成成功'}
