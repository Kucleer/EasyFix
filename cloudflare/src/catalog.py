"""学科、标签、错题本、知识点和错误类型的 D1 接口。"""

import json
from datetime import datetime
from fastapi import APIRouter, HTTPException, Request
from database import Database

router = APIRouter()
CATALOG = {
    'subjects': ('subject', {'name'}),
    'tags': ('tag', {'name', 'color'}),
    'error-books': ('error_book', {'name', 'subject_id', 'description', 'cover_image', 'original_images'}),
    'error-types': ('error_type', {'name', 'subject_id'}),
    'knowledge-points': ('knowledge_point', {'name', 'subject_id', 'grade', 'semester'}),
}


async def enrich(db, kind, row):
    """补充前端需要的学科名、图片数组和知识点关联。"""
    if kind == 'error-books':
        row['original_images'] = json.loads(row.get('original_images') or '[]')
    if kind in ('knowledge-points', 'error-types'):
        subject = await db.first('SELECT name FROM subject WHERE id=? AND deleted=0', (row.get('subject_id'),))
        row['subject_name'] = subject['name'] if subject else ('通用' if kind == 'error-types' else '')
    if kind == 'knowledge-points':
        row['error_types'] = await db.all('SELECT e.id,e.name FROM error_type e JOIN kp_error_type k ON k.error_type_id=e.id WHERE k.knowledge_point_id=? AND e.deleted=0 AND (e.subject_id IS NULL OR e.subject_id=?)', (row['id'], row['subject_id']))
    return row


def register(kind, table, fields):
    """为固定白名单实体注册路由，所有查询过滤软删除。"""
    async def list_items(request: Request):
        """读取分类数据，错题本提供分页，其余返回列表。"""
        db = Database(request.scope['env'].DB)
        where, values = ['deleted=0'], []
        for key in ('subject_id', 'grade', 'semester'):
            value = request.query_params.get(key)
            if value and key in fields:
                try:
                    value = int(value)
                except ValueError:
                    raise HTTPException(422, '筛选参数无效')
                where.append('(subject_id=? OR subject_id IS NULL)' if kind == 'error-types' else key + '=?')
                values.append(value)
        condition = ' AND '.join(where)
        rows = await db.all('SELECT * FROM ' + table + ' WHERE ' + condition + ' ORDER BY id DESC', values)
        total = len(rows)
        if kind == 'error-books':
            try:
                skip, limit = max(0, int(request.query_params.get('skip', 0))), min(100, max(1, int(request.query_params.get('limit', 20))))
            except ValueError:
                raise HTTPException(422, '分页参数无效')
            rows = rows[skip:skip + limit]
        result = [await enrich(db, kind, row) for row in rows]
        return {'total': total, 'items': result} if kind == 'error-books' else result

    async def get_item(item_id: int, request: Request):
        """读取单个未删除实体。"""
        db = Database(request.scope['env'].DB)
        row = await db.first('SELECT * FROM ' + table + ' WHERE id=? AND deleted=0', (item_id,))
        if not row:
            raise HTTPException(404, '记录不存在')
        return await enrich(db, kind, row)

    async def save_item(request: Request, item_id: int | None = None):
        """校验白名单字段及关联后创建或更新记录。"""
        db = Database(request.scope['env'].DB)
        payload = await request.json()
        if not isinstance(payload, dict):
            raise HTTPException(422, '请求必须为对象')
        data = {key: value for key, value in payload.items() if key in fields}
        old = None
        if item_id is not None:
            old = await db.first('SELECT * FROM ' + table + ' WHERE id=? AND deleted=0', (item_id,))
            if old is None:
                raise HTTPException(404, '记录不存在')
        if (not old or 'name' in data) and (not isinstance(data.get('name'), str) or not data['name'].strip()):
            raise HTTPException(422, '名称不能为空')
        subject_id = data.get('subject_id', old.get('subject_id') if old else None)
        if subject_id is not None and not await db.first('SELECT id FROM subject WHERE id=? AND deleted=0', (subject_id,)):
            raise HTTPException(400, '学科不存在')
        if kind in ('error-books', 'knowledge-points') and subject_id is None:
            raise HTTPException(422, '请选择学科')
        error_ids = payload.get('error_type_ids')
        if kind == 'knowledge-points' and error_ids is not None:
            if not isinstance(error_ids, list) or any(type(item) is not int for item in error_ids):
                raise HTTPException(422, '错误类型参数无效')
            for error_id in set(error_ids):
                if not await db.first('SELECT id FROM error_type WHERE id=? AND deleted=0 AND (subject_id IS NULL OR subject_id=?)', (error_id, subject_id)):
                    raise HTTPException(400, '错误类型不存在或不属于当前学科')
        if 'original_images' in data:
            if data['original_images'] is not None and not isinstance(data['original_images'], list):
                raise HTTPException(422, '图片列表无效')
            data['original_images'] = json.dumps(data['original_images'] or [], ensure_ascii=False)
        if old:
            if data:
                await db.run('UPDATE ' + table + ' SET ' + ','.join(key + '=?' for key in data) + ' WHERE id=? AND deleted=0', [*data.values(), item_id])
        else:
            data['deleted'] = 0
            if table not in ('tag',):
                data['created_at'] = datetime.now().isoformat(' ')
            meta = await db.run('INSERT INTO ' + table + ' (' + ','.join(data) + ') VALUES (' + ','.join('?' for _ in data) + ')', list(data.values()))
            item_id = meta['last_row_id']
        if kind == 'knowledge-points' and error_ids is not None:
            statements = [('DELETE FROM kp_error_type WHERE knowledge_point_id=?', (item_id,))]
            statements += [('INSERT INTO kp_error_type(knowledge_point_id,error_type_id) VALUES (?,?)', (item_id, error_id)) for error_id in set(error_ids)]
            await db.batch(statements)
        return await get_item(item_id, request)

    async def delete_item(item_id: int, request: Request):
        """只执行软删除。"""
        await get_item(item_id, request)
        await Database(request.scope['env'].DB).run('UPDATE ' + table + ' SET deleted=1 WHERE id=? AND deleted=0', (item_id,))
        from fastapi.responses import Response
        return Response(status_code=204)

    router.add_api_route('/api/' + kind, list_items, methods=['GET'])
    router.add_api_route('/api/' + kind, save_item, methods=['POST'], status_code=201)
    router.add_api_route('/api/' + kind + '/{item_id}', get_item, methods=['GET'])
    router.add_api_route('/api/' + kind + '/{item_id}', save_item, methods=['PUT'])
    router.add_api_route('/api/' + kind + '/{item_id}', delete_item, methods=['DELETE'], status_code=204)


for kind, (table, fields) in CATALOG.items():
    register(kind, table, fields)
