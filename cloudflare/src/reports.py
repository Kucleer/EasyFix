"""学习报告（旧）：只读保留，提供列表、详情和软删除，不再生成新报告。

已保存的报告保持原样展示，不按当前目录重写，也不重新调用模型；
content 带 schema_version=2 的是两级知识点改造后生成的报告。
"""

import json
from fastapi import APIRouter, HTTPException, Query, Request
from database import Database

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
