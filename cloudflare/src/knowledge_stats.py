"""知识点筛选的共享服务：读取筛选项、校验一级/二级筛选组合（questions.py 使用）。"""

from fastapi import HTTPException


async def knowledge_options(db, subject_id=None):
    """从目录读取筛选项，不再依赖题目文本去重。"""
    filters, values = ['deleted=0', 'level IN (1,2)'], []
    if subject_id is not None:
        filters.append('subject_id=?')
        values.append(subject_id)
    rows = await db.all('SELECT id,name,level,parent_id,code,sort_order FROM knowledge_point WHERE '
                        + ' AND '.join(filters) + ' ORDER BY level,sort_order,id', values)
    parents = {row['id']: row['name'] for row in rows if row.get('level') == 1}
    return [{
        'id': row['id'],
        'name': row['name'],
        'level': row['level'],
        'parent_id': row['parent_id'],
        'parent_name': parents.get(row['parent_id']),
        'code': row.get('code'),
        'sort_order': row.get('sort_order') or 0,
    } for row in rows]


async def validate_filter_ids(db, subject_id=None, parent_id=None, point_id=None):
    """校验一级/二级筛选组合属于同一路径，非法组合返回 422。"""
    point = None
    if point_id is not None:
        point = await db.first(
            'SELECT id,level,parent_id,subject_id FROM knowledge_point WHERE id=? AND deleted=0', (point_id,))
        if not point or point.get('level') != 2:
            raise HTTPException(422, '二级知识点筛选无效')
        if subject_id is not None and point.get('subject_id') != subject_id:
            raise HTTPException(422, '知识点与学科不匹配')
        if parent_id is not None and point.get('parent_id') != parent_id:
            raise HTTPException(422, '一级与二级知识点不属于同一路径')
    elif parent_id is not None:
        parent = await db.first(
            'SELECT id,level,subject_id FROM knowledge_point WHERE id=? AND deleted=0', (parent_id,))
        if not parent or parent.get('level') != 1:
            raise HTTPException(422, '一级知识点筛选无效')
        if subject_id is not None and parent.get('subject_id') != subject_id:
            raise HTTPException(422, '知识点与学科不匹配')
    return parent_id, point_id
