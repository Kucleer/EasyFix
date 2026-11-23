"""管理员接口 /api/admin/*：开家庭、加学生、改学生、停用家庭。

只有管理员能调用（guard 里按 identity.admin_only 统一拦，非管理员 403）。
跟密码有关的（设初始密码、重置密码）在网关 cloudflare/pages/auth_routes.js 里，这里不碰密码。
每个学生的默认年级、学期存在 runtime_config 的 'app:<学生编号>'（和设置页"年级与学期"同一处）。
"""

import json
import re

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response

from database import Database
from identity import current_identity
from intake_model import is_plain_int
from questions import stamp_now

router = APIRouter(prefix='/api/admin')

USERNAME_PATTERN = re.compile(r'^[a-z0-9_]{3,20}$')   # 登录名：小写字母、数字、下划线，3–20 位
NAME_MAX = 40                                       # 家庭名、学生名最长几个字


async def read_object(request):
    """读 JSON 请求体，必须是对象。"""
    try:
        payload = await request.json()
    except ValueError:
        raise HTTPException(422, '请求体必须是 JSON')
    if not isinstance(payload, dict):
        raise HTTPException(422, '请求体必须是对象')
    return payload


def clean_name(value, label):
    """名字：去掉首尾空白后不能为空，不能太长。"""
    if not isinstance(value, str) or not value.strip():
        raise HTTPException(422, label + '不能为空')
    if len(value.strip()) > NAME_MAX:
        raise HTTPException(422, '%s最多 %d 个字' % (label, NAME_MAX))
    return value.strip()


def clean_grade(payload, key, high, label):
    """年级（1–12）或学期（1–2）：可以不给（None），给了必须在范围内。"""
    value = payload.get(key)
    if value is None:
        return None
    if not is_plain_int(value) or not 1 <= value <= high:
        raise HTTPException(422, '%s应在 1 到 %d 之间' % (label, high))
    return value


async def save_student_config(db, student_id, grade, semester, merge=None):
    """写这个学生的默认年级学期（'app:<学生编号>'）；merge 是旧值，没给的键沿用旧值。"""
    value = dict(merge or {})
    if grade is not None or 'default_grade' not in value:
        value['default_grade'] = grade if grade is not None else value.get('default_grade')
    if semester is not None or 'default_semester' not in value:
        value['default_semester'] = semester if semester is not None else value.get('default_semester')
    await db.run('INSERT INTO runtime_config(name,value,deleted,updated_at) VALUES(?,?,0,?) '
                 'ON CONFLICT(name) DO UPDATE SET value=excluded.value,deleted=0,updated_at=excluded.updated_at',
                 ('app:%d' % student_id, json.dumps(value, ensure_ascii=False), stamp_now()))


async def load_student_configs(db, student_ids):
    """一次取出这些学生的默认年级学期：{学生编号: {'default_grade', 'default_semester'}}。"""
    if not student_ids:
        return {}
    names = json.dumps(['app:%d' % sid for sid in student_ids])
    rows = await db.all('SELECT name,value FROM runtime_config WHERE deleted=0 AND name IN (SELECT value FROM json_each(?))',
                        (names,))
    result = {}
    for row in rows:
        try:
            result[int(row['name'].split(':', 1)[1])] = json.loads(row['value'])
        except (ValueError, TypeError):
            continue
    return result


async def load_user(db, user_id):
    """读一个没删除的用户，不存在 404。"""
    row = await db.first('SELECT id,username,name,disabled FROM app_user WHERE id=? AND deleted=0', (user_id,))
    if row is None:
        raise HTTPException(404, '记录不存在')
    return row


async def add_student(db, user_id, name, grade, semester):
    """给一个家庭加学生（排在最后），写好默认年级学期，返回学生 {'id','name','grade','semester'}。"""
    stamp = stamp_now()
    order = await db.first('SELECT COALESCE(MAX(sort_order),-1)+1 AS next FROM student WHERE user_id=? AND deleted=0',
                           (user_id,))
    row = await db.first('INSERT INTO student(user_id,name,sort_order,deleted,created_at,updated_at) '
                         'VALUES(?,?,?,0,?,?) RETURNING id', (user_id, name, order['next'], stamp, stamp))
    await save_student_config(db, row['id'], grade, semester)
    return {'id': row['id'], 'name': name, 'grade': grade, 'semester': semester}


@router.get('/users')
async def list_users(request: Request):
    """全部家庭（含管理员自己）：登录名、名字、是否停用、最近登录、学生（带默认年级学期）。三条 SQL。"""
    db = Database(request.scope['env'].DB)
    users = await db.all('SELECT id,username,name,is_admin,disabled,last_login_at FROM app_user WHERE deleted=0 ORDER BY id')
    students = await db.all('SELECT id,user_id,name,sort_order FROM student WHERE deleted=0 ORDER BY sort_order,id')
    configs = await load_student_configs(db, [row['id'] for row in students])
    by_user = {}
    for row in students:
        config = configs.get(row['id'], {})
        by_user.setdefault(row['user_id'], []).append({
            'id': row['id'], 'name': row['name'], 'sort_order': row['sort_order'],
            'grade': config.get('default_grade'), 'semester': config.get('default_semester')})
    return [{'id': row['id'], 'username': row['username'], 'name': row['name'], 'is_admin': bool(row['is_admin']),
             'disabled': bool(row['disabled']), 'last_login_at': row['last_login_at'],
             'students': by_user.get(row['id'], [])} for row in users]


@router.post('/users', status_code=201)
async def create_user(request: Request):
    """开一个家庭：建用户（还没有密码，由网关接口生成初始密码）和第一个学生。"""
    payload = await read_object(request)
    username = payload.get('username')
    if not isinstance(username, str) or not USERNAME_PATTERN.match(username):
        raise HTTPException(422, '登录名只能用小写字母、数字、下划线，3 到 20 位')
    name = clean_name(payload.get('name'), '家庭名字')
    # 先校验学生，免得建了用户才发现学生不对
    student_name = clean_name(payload.get('student_name'), '学生名字')
    grade = clean_grade(payload, 'grade', 12, '年级')
    semester = clean_grade(payload, 'semester', 2, '学期')
    db = Database(request.scope['env'].DB)
    if await db.first('SELECT id FROM app_user WHERE username=? AND deleted=0', (username,)):
        raise HTTPException(409, '登录名已被占用')
    stamp = stamp_now()
    try:
        user = await db.first('INSERT INTO app_user(name,username,is_admin,session_version,disabled,deleted,created_at,'
                              'updated_at) VALUES(?,?,0,1,0,0,?,?) RETURNING id', (name, username, stamp, stamp))
    except Exception as error:   # 两个请求同时用同一个登录名：唯一索引拦住后一个
        if 'UNIQUE' in str(error):
            raise HTTPException(409, '登录名已被占用')
        raise
    student = await add_student(db, user['id'], student_name, grade, semester)
    return {'user_id': user['id'], 'student_id': student['id']}


@router.put('/users/{user_id}')
async def update_user(user_id: int, request: Request):
    """改家庭名字、停用或启用；停用和启用都让这个家庭的旧登录失效（会话版本加 1）。"""
    payload = await read_object(request)
    db = Database(request.scope['env'].DB)
    old = await load_user(db, user_id)
    data = {}
    if 'name' in payload:
        data['name'] = clean_name(payload['name'], '家庭名字')
    if 'disabled' in payload:
        if not isinstance(payload['disabled'], bool):
            raise HTTPException(422, 'disabled 必须是真或假')
        if payload['disabled'] and user_id == current_identity(request)['user_id']:
            raise HTTPException(422, '不能停用自己')
        if bool(old['disabled']) != payload['disabled']:
            data['disabled'] = int(payload['disabled'])
    if not data:
        return {'id': user_id}
    columns = ','.join(key + '=?' for key in data)
    bump = ',session_version=session_version+1' if 'disabled' in data else ''
    await db.run('UPDATE app_user SET ' + columns + bump + ',updated_at=? WHERE id=? AND deleted=0',
                 (*data.values(), stamp_now(), user_id))
    return {'id': user_id}


@router.post('/users/{user_id}/students', status_code=201)
async def create_student(user_id: int, request: Request):
    """给一个家庭再加一个学生。"""
    payload = await read_object(request)
    db = Database(request.scope['env'].DB)
    await load_user(db, user_id)
    return await add_student(db, user_id, clean_name(payload.get('name'), '学生名字'),
                             clean_grade(payload, 'grade', 12, '年级'), clean_grade(payload, 'semester', 2, '学期'))


async def load_student(db, student_id):
    """读一个没删除的学生（带所属家庭），不存在 404。"""
    row = await db.first('SELECT id,user_id,name FROM student WHERE id=? AND deleted=0', (student_id,))
    if row is None:
        raise HTTPException(404, '记录不存在')
    return row


@router.put('/students/{student_id}')
async def update_student(student_id: int, request: Request):
    """改学生名字、排序、默认年级学期（没给的保持不变）。"""
    payload = await read_object(request)
    db = Database(request.scope['env'].DB)
    await load_student(db, student_id)
    data = {}
    if 'name' in payload:
        data['name'] = clean_name(payload['name'], '学生名字')
    if 'sort_order' in payload:
        if not is_plain_int(payload['sort_order']):
            raise HTTPException(422, 'sort_order 必须是整数')
        data['sort_order'] = payload['sort_order']
    grade = clean_grade(payload, 'grade', 12, '年级')
    semester = clean_grade(payload, 'semester', 2, '学期')
    if data:
        await db.run('UPDATE student SET ' + ','.join(key + '=?' for key in data) + ',updated_at=? WHERE id=? AND deleted=0',
                     (*data.values(), stamp_now(), student_id))
    if grade is not None or semester is not None:
        old = (await load_student_configs(db, [student_id])).get(student_id)
        await save_student_config(db, student_id, grade, semester, merge=old)
    return {'id': student_id}


@router.delete('/students/{student_id}', status_code=204)
async def delete_student(student_id: int, request: Request):
    """软删除学生；一个家庭至少要留一个学生（否则这个家庭登录不了）。"""
    db = Database(request.scope['env'].DB)
    student = await load_student(db, student_id)
    count = await db.first('SELECT COUNT(*) AS n FROM student WHERE user_id=? AND deleted=0', (student['user_id'],))
    if count['n'] <= 1:
        raise HTTPException(409, '至少要保留一个学生')
    await db.run('UPDATE student SET deleted=1,updated_at=? WHERE id=? AND deleted=0', (stamp_now(), student_id))
    return Response(status_code=204)
