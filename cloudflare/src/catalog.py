"""学科、标签、错题本和错误类型的 D1 接口；知识点由 knowledge.py 单独实现。"""

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
    'stars/actions': ('star_action', {'code','name','star_value','icon','enabled'}),
    'achievements': ('achievement', {'code','name','level','description','icon','trigger_action','trigger_count','reward_stars','is_active'}),
    'rewards': ('reward', {'name','description','icon','cost_stars','total_stock','remaining_stock','is_active','image_url'}),
}


async def enrich(db, kind, row):
    """补充前端需要的学科名和图片数组。"""
    for key in ('enabled','is_custom','is_preset','is_active'):
        if key in row:
            row[key] = bool(row[key])
    if kind == 'error-books':
        row['original_images'] = json.loads(row.get('original_images') or '[]')
    if kind == 'error-types':
        subject = await db.first('SELECT name FROM subject WHERE id=? AND deleted=0', (row.get('subject_id'),))
        row['subject_name'] = subject['name'] if subject else '通用'
    return row


def register(kind, table, fields):
    """为固定白名单实体注册路由，所有查询过滤软删除。"""
    async def list_items(request: Request):
        """读取分类数据，错题本提供分页，其余返回列表。"""
        db = Database(request.scope['env'].DB)
        where, values = ['deleted=0'], []
        if kind == 'rewards':where.append('is_active=1')
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
            if kind in ('stars/actions','achievements') and (old.get('is_preset') or kind == 'stars/actions' and not old.get('is_custom')):
                raise HTTPException(400,'预设项目不可修改')
        if (not old or 'name' in data) and (not isinstance(data.get('name'), str) or not data['name'].strip()):
            raise HTTPException(422, '名称不能为空')
        subject_id = data.get('subject_id', old.get('subject_id') if old else None)
        if subject_id is not None and not await db.first('SELECT id FROM subject WHERE id=? AND deleted=0', (subject_id,)):
            raise HTTPException(400, '学科不存在')
        if kind == 'error-books' and subject_id is None:
            raise HTTPException(422, '请选择学科')
        if 'original_images' in data:
            if data['original_images'] is not None and not isinstance(data['original_images'], list):
                raise HTTPException(422, '图片列表无效')
            data['original_images'] = json.dumps(data['original_images'] or [], ensure_ascii=False)
        if old:
            if data:
                await db.run('UPDATE ' + table + ' SET ' + ','.join(key + '=?' for key in data) + ' WHERE id=? AND deleted=0', [*data.values(), item_id])
        else:
            defaults = {'stars/actions':{'star_value':0,'enabled':1,'is_custom':1},'achievements':{'level':1,'reward_stars':0,'is_preset':0,'is_active':1},'rewards':{'total_stock':-1,'remaining_stock':-1,'is_active':1}}
            data = {**defaults.get(kind,{}),**data}
            data['deleted'] = 0
            if table not in ('tag',):
                data['created_at'] = datetime.now().isoformat(' ')
            meta = await db.run('INSERT INTO ' + table + ' (' + ','.join(data) + ') VALUES (' + ','.join('?' for _ in data) + ')', list(data.values()))
            item_id = meta['last_row_id']
        return await get_item(item_id, request)

    async def delete_item(item_id: int, request: Request):
        """只执行软删除；学科仍有知识点或错题时拒绝。"""
        old = await get_item(item_id, request)
        if kind in ('stars/actions','achievements') and (old.get('is_preset') or kind == 'stars/actions' and not old.get('is_custom')):
            raise HTTPException(400,'预设项目不可删除')
        db = Database(request.scope['env'].DB)
        if kind == 'subjects':
            points = await db.first('SELECT COUNT(*) AS count FROM knowledge_point WHERE subject_id=? AND deleted=0', (item_id,))
            questions = await db.first('SELECT COUNT(*) AS count FROM question WHERE subject_id=? AND deleted=0', (item_id,))
            if points['count']:
                raise HTTPException(409, '该学科仍有 ' + str(points['count']) + ' 个有效知识点，不能删除')
            if questions['count']:
                raise HTTPException(409, '该学科仍有 ' + str(questions['count']) + ' 道有效错题，不能删除')
        await db.run('UPDATE ' + table + ' SET deleted=1 WHERE id=? AND deleted=0', (item_id,))
        from fastapi.responses import Response
        return Response(status_code=204)

    router.add_api_route('/api/' + kind, list_items, methods=['GET'])
    router.add_api_route('/api/' + kind, save_item, methods=['POST'], status_code=201)
    router.add_api_route('/api/' + kind + '/{item_id}', get_item, methods=['GET'])
    router.add_api_route('/api/' + kind + '/{item_id}', save_item, methods=['PUT'])
    router.add_api_route('/api/' + kind + '/{item_id}', delete_item, methods=['DELETE'], status_code=204)


for kind, (table, fields) in CATALOG.items():
    register(kind, table, fields)
