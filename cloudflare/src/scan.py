"""整页识别录入的接口：查识别服务、建页、分步推进识别、查页、结束一页。

推进一步的做法：页面反复调"推进"接口，每次只做当前状态的下一步
（读图 → 整理 → 需要时重扫 → 再整理 → ready）。同一页同一时刻只能有一个推进在跑，
靠一条带条件的 UPDATE 认领这一步：认领时写入新状态和开始时间，没认领到就返回"正在处理"。

下面这些模块级名字测试时会被替换，代码里一律通过模块名字调用：
ocr_client、generate_json、sleep、now_seconds、Database。
"""

import asyncio
import json
import time

from fastapi import APIRouter, HTTPException, Request

import ocr_client
from database import Database
from intake import load_catalog, load_error_type_names, read_payload
from intake_model import IMAGE_KEY_PATTERN, is_plain_int
from question_scope import current_student_id
from questions import stamp_now
from scan_model import (BUSY_RETRIES, BUSY_WAIT_SECONDS, HEALTH_TIMEOUT_SECONDS, HOST_TIMEOUT_SECONDS,
                        STALE_SECONDS, build_page_prompt, clean_items, interpret_health, interpret_ocr,
                        needs_rescan, next_step)
from settings import generate_json

router = APIRouter()

sleep = asyncio.sleep
# 每一步认领时写入的状态
CLAIM_STATUS = {'read': 'reading', 'analyze': 'analyzing', 'rescan': 'rescanning'}
UNFINISHED_LIMIT = 5
MISSING_IMAGE_TEXT = '照片找不到了'
MODEL_FAILED_TEXT = '文本模型请求失败，请检查模型配置和余额'


def now_seconds():
    """当前时间，整数秒（step_started_at 用）。"""
    return int(time.time())


def elapsed_ms(started):
    """从 started（time.time() 的值）到现在过了多少毫秒。"""
    return int((time.time() - started) * 1000)


# ---------------------------------------------------------------- 健康检查


@router.get('/api/scan/health')
async def health(request: Request):
    """识别主机是否可用；只返回 available，不透出主机的任何细节。"""
    status, body = await ocr_client.fetch_health(request.scope['env'], HEALTH_TIMEOUT_SECONDS)
    return {'available': interpret_health(status, body)}


# ---------------------------------------------------------------- 页面读写


def page_view(row):
    """把一行 scan_page 转成给页面的内容；不含 OCR 文字。"""
    return {
        'id': row['id'], 'subject_id': row['subject_id'], 'grade': row['grade'], 'semester': row['semester'],
        'image': row['image'], 'status': row['status'], 'error': row['error'], 'rescan_used': row['rescan_used'],
        'items': json.loads(row['items'] or '[]'), 'timings': json.loads(row['timings'] or '{}'),
        'created_at': row['created_at'],
    }


async def load_page(db, page_id, student_id):
    """读当前学生的一页（未删除），找不到就 404。"""
    row = await db.first('SELECT * FROM scan_page WHERE id=? AND student_id=? AND deleted=0', (page_id, student_id))
    if row is None:
        raise HTTPException(404, '这一页不存在')
    return row


def rescan_enabled(env):
    """重扫开关：没设置或不是 off 都算开着。"""
    return str(getattr(env, 'SCAN_RESCAN', '')).lower() != 'off'


async def claim_step(db, page, status, now, rescan=False):
    """用一条条件更新认领这一步：页面还是读到时的状态、且没有别人正在做（或已卡住）才能认领成功。"""
    extra = ',rescan_used=1' if rescan else ''
    row = await db.first(
        'UPDATE scan_page SET status=?,step_started_at=?,updated_at=?' + extra + ' '
        'WHERE id=? AND deleted=0 AND status=? AND (step_started_at IS NULL OR step_started_at<?) RETURNING id',
        (status, now, stamp_now(), page['id'], page['status'], now - STALE_SECONDS))
    return row is not None


async def finish_step(db, page, claimed_status, started_at, fields, timings):
    """一步结束：写入结果、用时，清空 step_started_at。

    只在页面仍是自己认领时的样子才写（状态和开始时间都没变），
    这样中途被结束、或卡住后被别人重新认领的页不会被这次的结果覆盖。
    """
    data = dict(fields, step_started_at=None, updated_at=stamp_now(),
                timings=json.dumps(timings, ensure_ascii=False))
    columns = ','.join(key + '=?' for key in data)
    await db.run('UPDATE scan_page SET ' + columns + ' WHERE id=? AND deleted=0 AND status=? AND step_started_at=?',
                 [*data.values(), page['id'], claimed_status, started_at])


# ---------------------------------------------------------------- 调主机


async def call_host(env, content, content_type, mode):
    """把图片发给主机识别；主机忙时等一会儿重试，重试完仍忙按失败处理。返回 interpret_ocr 的结果。"""
    for attempt in range(BUSY_RETRIES + 1):
        status, body = await ocr_client.fetch_ocr(env, content, content_type, mode, HOST_TIMEOUT_SECONDS[mode])
        result = interpret_ocr(status, body)
        if result['kind'] != 'busy':
            return result
        if attempt < BUSY_RETRIES:
            await sleep(BUSY_WAIT_SECONDS)
    return dict(result, kind='failed', detail=result['detail'] or 'busy')


async def read_page_text(env, page, mode):
    """从 R2 取照片交给主机识别；照片不见了时返回 None，否则返回 interpret_ocr 的结果。"""
    image = await ocr_client.read_image(env, page['image'])
    if image is None:
        return None
    content, content_type = image
    return await call_host(env, content, content_type, mode)


# ---------------------------------------------------------------- 三个步骤


async def run_read(request, db, page, started_at):
    """读图：成功转 analyzing 并存下文字；失败转 failed，用户看提示文字，主机细节记进 timings。"""
    clock = time.time()
    result = await read_page_text(request.scope['env'], page, 'normal')
    timings = json.loads(page['timings'] or '{}')
    timings['read_ms'] = elapsed_ms(clock)
    if result is not None and result['kind'] == 'ok':
        if result['elapsed_ms'] is not None:
            timings['host_read_ms'] = result['elapsed_ms']
        fields = {'status': 'analyzing', 'ocr_text': result['text'], 'error': None}
    elif result is None:
        fields = {'status': 'failed', 'error': MISSING_IMAGE_TEXT}
    else:
        timings['host_detail'] = result['detail']
        fields = {'status': 'failed', 'error': result['user_text']}
    await finish_step(db, page, 'reading', started_at, fields, timings)


async def run_analyze(request, db, page, started_at):
    """整理：调一次文本模型；成功存题目草稿，需要重扫转 rescanning，否则 ready；失败转 failed，读图文字保留。"""
    clock = time.time()
    subject = await db.first('SELECT name FROM subject WHERE id=? AND deleted=0', (page['subject_id'],))
    catalog = await load_catalog(db, page['subject_id'], page['grade'], page['semester'])
    error_type_names = await load_error_type_names(db, page['subject_id'])
    prompt = build_page_prompt(subject['name'] if subject else '', page['grade'], page['semester'],
                               page['ocr_text'], page['ocr_text_enhanced'], catalog, sorted(error_type_names))
    timings = json.loads(page['timings'] or '{}')
    # 重扫后的第二次整理单独记用时
    timing_key = 'analyze2_ms' if page['ocr_text_enhanced'] else 'analyze_ms'
    error_text = None
    try:
        raw = await generate_json(request, prompt)
    except HTTPException as error:
        error_text = error.detail
    except Exception:
        # 生产环境里网络超时等会抛运行时异常，统一给一句模型失败的提示
        error_text = MODEL_FAILED_TEXT
    if error_text is not None:
        if page['ocr_text_enhanced'] and json.loads(page['items'] or '[]'):
            # 重扫后的第二次整理失败：已有第一次的结果，直接 ready 并保留它，失败原因只记进 timings
            timings['analyze2_error'] = error_text
            fields = {'status': 'ready', 'error': None}
        else:
            fields = {'status': 'failed', 'error': error_text}
    else:
        catalog_ids = {point['id'] for group in catalog for point in group['points']}
        items = clean_items(raw, catalog_ids, error_type_names)
        rescan = needs_rescan(items, page['rescan_used'], rescan_enabled(request.scope['env']))
        fields = {'status': 'rescanning' if rescan else 'ready', 'error': None,
                  'items': json.dumps(items, ensure_ascii=False)}
    timings[timing_key] = elapsed_ms(clock)
    await finish_step(db, page, 'analyzing', started_at, fields, timings)


async def run_rescan(request, db, page, started_at):
    """强化重扫：成功转 analyzing 并存下重扫文字；失败直接 ready，保留第一次的题目草稿。"""
    clock = time.time()
    result = await read_page_text(request.scope['env'], page, 'enhanced')
    timings = json.loads(page['timings'] or '{}')
    timings['rescan_ms'] = elapsed_ms(clock)
    if result is not None and result['kind'] == 'ok':
        if result['elapsed_ms'] is not None:
            timings['host_rescan_ms'] = result['elapsed_ms']
        fields = {'status': 'analyzing', 'ocr_text_enhanced': result['text']}
    else:
        timings['host_detail'] = result['detail'] if result is not None else MISSING_IMAGE_TEXT
        fields = {'status': 'ready'}
    await finish_step(db, page, 'rescanning', started_at, fields, timings)


STEP_RUNNERS = {'read': run_read, 'analyze': run_analyze, 'rescan': run_rescan}


# ---------------------------------------------------------------- 接口


@router.post('/api/scan/pages', status_code=201)
async def create_page(request: Request):
    """新建一页：检查照片路径、学科、年级、学期，建一条 uploaded 记录。"""
    payload = await read_payload(request)
    image = payload.get('image')
    if not isinstance(image, str) or not IMAGE_KEY_PATTERN.fullmatch(image):
        raise HTTPException(422, '照片路径格式不对，请使用上传照片后返回的路径')
    subject_id = payload.get('subject_id')
    if not is_plain_int(subject_id):
        raise HTTPException(422, '学科格式不对')
    grade = payload.get('grade')
    if grade is not None and not (is_plain_int(grade) and 1 <= grade <= 12):
        raise HTTPException(422, '年级应在 1 到 12 之间')
    semester = payload.get('semester')
    if semester is not None and not (is_plain_int(semester) and semester in (1, 2)):
        raise HTTPException(422, '学期应为 1 或 2')
    db = Database(request.scope['env'].DB)
    if await db.first('SELECT id FROM subject WHERE id=? AND deleted=0', (subject_id,)) is None:
        raise HTTPException(400, '学科不存在')
    stamp = stamp_now()
    row = await db.first(
        "INSERT INTO scan_page(student_id,subject_id,grade,semester,image,status,items,timings,deleted,"
        "created_at,updated_at) VALUES(?,?,?,?,?,'uploaded','[]','{}',0,?,?) RETURNING *",
        (current_student_id(request), subject_id, grade, semester, image, stamp, stamp))
    return page_view(row)


# 必须写在 /api/scan/pages/{page_id} 之前，否则 unfinished 会被当成页编号
@router.get('/api/scan/pages/unfinished')
async def list_unfinished(request: Request):
    """当前学生没整理完的页（不是已结束、失败），最近的 5 条。"""
    db = Database(request.scope['env'].DB)
    rows = await db.all(
        "SELECT * FROM scan_page WHERE student_id=? AND deleted=0 AND status NOT IN ('closed','failed') "
        'ORDER BY id DESC LIMIT ?', (current_student_id(request), UNFINISHED_LIMIT))
    return {'items': [page_view(row) for row in rows]}


@router.get('/api/scan/pages/{page_id}')
async def get_page(page_id: int, request: Request):
    """查一页的状态和题目草稿。"""
    db = Database(request.scope['env'].DB)
    return page_view(await load_page(db, page_id, current_student_id(request)))


@router.post('/api/scan/pages/{page_id}/advance')
async def advance_page(page_id: int, request: Request):
    """推进一步：做当前状态的下一步；别人正在做时返回 busy。"""
    db = Database(request.scope['env'].DB)
    student_id = current_student_id(request)
    page = await load_page(db, page_id, student_id)
    now = now_seconds()
    step = next_step(page, now)
    if step is None:
        return {'busy': False, 'page': page_view(page)}
    if step == 'working':
        return {'busy': True, 'page': page_view(page)}
    claimed_status = CLAIM_STATUS[step]
    if not await claim_step(db, page, claimed_status, now, rescan=step == 'rescan'):
        # 条件更新没认领到：同一时刻已有别的请求在做这一步
        return {'busy': True, 'page': page_view(await load_page(db, page_id, student_id))}
    await STEP_RUNNERS[step](request, db, page, now)
    return {'busy': False, 'page': page_view(await load_page(db, page_id, student_id))}


@router.post('/api/scan/pages/{page_id}/close')
async def close_page(page_id: int, request: Request):
    """结束一页：状态改为 closed。"""
    db = Database(request.scope['env'].DB)
    student_id = current_student_id(request)
    await load_page(db, page_id, student_id)
    await db.run("UPDATE scan_page SET status='closed',step_started_at=NULL,updated_at=? WHERE id=? AND deleted=0",
                 (stamp_now(), page_id))
    return page_view(await load_page(db, page_id, student_id))
