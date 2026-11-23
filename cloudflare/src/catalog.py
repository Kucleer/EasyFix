"""学科、标签、错题本和激励配置的 D1 接口；知识点由 knowledge.py 单独实现。"""

import json
from datetime import datetime
from fastapi import APIRouter, HTTPException, Request
from database import Database
from question_scope import current_student_id

router = APIRouter()
# 每项：(表名, 可写字段, 是否按学生分)。
# 标签、错题本、奖品是各学生自己的；学科、加星规则、成就是全站共用目录（写入只有管理员能做，由 guard 拦）
CATALOG = {
    'subjects': ('subject', {'name'}, False),
    'tags': ('tag', {'name', 'color'}, True),
    'error-books': ('error_book', {'name', 'subject_id', 'description', 'cover_image', 'original_images'}, True),
    'stars/actions': ('star_action', {'code','name','star_value','icon','enabled'}, False),
    'achievements': ('achievement', {'code','name','level','description','icon','trigger_action','trigger_count','reward_stars','is_active'}, False),
    'rewards': ('reward', {'name','description','icon','cost_stars','total_stock','remaining_stock','is_active','image_url'}, True),
}
# 可以修改的目录；学科和标签前端只新增、删除，不注册修改接口
EDITABLE_KINDS = {'error-books', 'stars/actions', 'achievements', 'rewards'}


async def enrich(db, kind, row):
    """补充前端需要的学科名和图片数组。"""
    for key in ('enabled','is_custom','is_preset','is_active'):
        if key in row:
            row[key] = bool(row[key])
    if kind == 'error-books':
        row['original_images'] = json.loads(row.get('original_images') or '[]')
    return row


def scope_condition(request, scoped):
    """按学生分的目录返回 (' AND student_id=?', [学生编号])，共用目录返回 ('', [])。"""
    return (' AND student_id=?', [current_student_id(request)]) if scoped else ('', [])


def register(kind, table, fields, scoped):
    """为固定白名单实体注册路由，所有查询过滤软删除；按学生分的目录只读写当前学生的。"""
    async def list_items(request: Request):
        """读取分类数据，错题本提供分页，其余返回列表。"""
        db = Database(request.scope['env'].DB)
        where, values = ['deleted=0'], []
        if scoped:
            where.append('student_id=?')
            values.append(current_student_id(request))
        if kind == 'rewards':where.append('is_active=1')
        for key in ('subject_id', 'grade', 'semester'):
            value = request.query_params.get(key)
            if value and key in fields:
                try:
                    value = int(value)
                except ValueError:
                    raise HTTPException(422, '筛选参数无效')
                where.append(key + '=?')
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
        condition, extra = scope_condition(request, scoped)
        row = await db.first('SELECT * FROM ' + table + ' WHERE id=? AND deleted=0' + condition, (item_id, *extra))
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
        condition, extra = scope_condition(request, scoped)
        if item_id is not None:
            old = await db.first('SELECT * FROM ' + table + ' WHERE id=? AND deleted=0' + condition, (item_id, *extra))
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
        if scoped and ('cover_image' in data or 'original_images' in data):
            from identity import check_uploads, current_identity
            check_uploads(current_identity(request), [data.get('cover_image'), *(data.get('original_images') or [])])
            data['original_images'] = json.dumps(data['original_images'] or [], ensure_ascii=False)
        if old:
            if data:
                await db.run('UPDATE ' + table + ' SET ' + ','.join(key + '=?' for key in data) + ' WHERE id=? AND deleted=0'
                             + condition, [*data.values(), item_id, *extra])
        else:
            defaults = {'stars/actions':{'star_value':0,'enabled':1,'is_custom':1},'achievements':{'level':1,'reward_stars':0,'is_preset':0,'is_active':1},'rewards':{'total_stock':-1,'remaining_stock':-1,'is_active':1}}
            data = {**defaults.get(kind,{}),**data}
            data['deleted'] = 0
            if scoped:
                data['student_id'] = extra[0]
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
            # scope-ok: 删除学科（只有管理员能做）要看全站还有没有这一科的错题
            questions = await db.first('SELECT COUNT(*) AS count FROM question WHERE subject_id=? AND deleted=0', (item_id,))
            if points['count']:
                raise HTTPException(409, '该学科仍有 ' + str(points['count']) + ' 个有效知识点，不能删除')
            if questions['count']:
                raise HTTPException(409, '该学科仍有 ' + str(questions['count']) + ' 道有效错题，不能删除')
        condition, extra = scope_condition(request, scoped)
        await db.run('UPDATE ' + table + ' SET deleted=1 WHERE id=? AND deleted=0' + condition, (item_id, *extra))
        from fastapi.responses import Response
        return Response(status_code=204)

    router.add_api_route('/api/' + kind, list_items, methods=['GET'])
    router.add_api_route('/api/' + kind, save_item, methods=['POST'], status_code=201)
    # 单条读取没有调用方，不注册路由；get_item 仍供保存和删除内部使用
    if kind in EDITABLE_KINDS:
        router.add_api_route('/api/' + kind + '/{item_id}', save_item, methods=['PUT'])
    router.add_api_route('/api/' + kind + '/{item_id}', delete_item, methods=['DELETE'], status_code=204)


for kind, (table, fields, scoped) in CATALOG.items():
    register(kind, table, fields, scoped)
