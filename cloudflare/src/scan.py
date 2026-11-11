"""整页识别录入的接口：查识别服务、建页、分步推进识别、查页、结束一页，以及逐题操作与录入。

推进一步的做法：页面反复调"推进"接口，每次只做当前状态的下一步
（读图 → 整理 → 需要时重扫 → 再整理 → ready）。同一页同一时刻只能有一个推进在跑，
靠一条带条件的 UPDATE 认领这一步：认领时写入新状态和开始时间，没认领到就返回"正在处理"。

逐题操作（保存修改、去掉、恢复、补成错题、录入、撤回、手工加一道）只在页面是 ready 时允许。
每次只用 json_set 改草稿里的那一项，并以"那一项的状态没变、页面仍是 ready"为条件，
这样同时操作不同的题不会互相覆盖，已结束的页也不会被写。

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
from questions import save as save_question, stamp_now
from scan_model import (ACCEPT_ALL_BATCH, BUSY_RETRIES, BUSY_WAIT_SECONDS, HEALTH_TIMEOUT_SECONDS,
                        HOST_TIMEOUT_SECONDS, STALE_SECONDS, ScanError, accept_all_seqs, blank_item,
                        build_fill_prompt, build_page_prompt, clean_edit, clean_fill, clean_items,
                        interpret_health, interpret_ocr, needs_rescan, next_step, question_payload)
from settings import generate_json

router = APIRouter()

sleep = asyncio.sleep
# 每一步认领时写入的状态
CLAIM_STATUS = {'read': 'reading', 'analyze': 'analyzing', 'rescan': 'rescanning'}
UNFINISHED_LIMIT = 5
MISSING_IMAGE_TEXT = '照片找不到了'
MODEL_FAILED_TEXT = '文本模型请求失败，请检查模型配置和余额'
PAGE_CLOSED_TEXT = '这一页已经结束了，请刷新'
ITEM_CHANGED_TEXT = '这道题刚被别的操作改过，请刷新'
PROMOTED_REASON = '家长补成错题'


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


# ---------------------------------------------------------------- 逐题操作的公共部分


async def load_ready_item(db, page_id, student_id, seq):
    """读一页和其中第 seq 道题：页不是 ready 时 409，序号越界 404。返回 (页, 这一项)。"""
    page = await load_page(db, page_id, student_id)
    if page['status'] != 'ready':
        raise HTTPException(409, PAGE_CLOSED_TEXT)
    items = json.loads(page['items'] or '[]')
    if not 0 <= seq < len(items):
        raise HTTPException(404, '这道题不存在')
    return page, items[seq]


async def write_item(db, page_id, seq, expected_state, item):
    """把草稿第 seq 项整体换成 item；只有页面仍是 ready、这一项仍是 expected_state 时才写。

    返回是否写成功。没写成功说明页已结束，或这一项刚被别的请求改了状态。
    """
    row = await db.first(
        "UPDATE scan_page SET items=json_set(items, '$[' || ? || ']', json(?)), updated_at=? "
        "WHERE id=? AND deleted=0 AND status='ready' AND json_extract(items, '$[' || ? || '].state')=? "
        'RETURNING id',
        (seq, json.dumps(item, ensure_ascii=False), stamp_now(), page_id, seq, expected_state))
    return row is not None


async def raise_write_conflict(db, page_id, student_id):
    """条件写入没成功时，按原因抛 409：页已结束，或这道题刚被别的操作改过。"""
    page = await load_page(db, page_id, student_id)
    if page['status'] != 'ready':
        raise HTTPException(409, PAGE_CLOSED_TEXT)
    raise HTTPException(409, ITEM_CHANGED_TEXT)


async def change_state(request, page_id, seq, from_state, to_state, wrong_state_text):
    """把一道题从 from_state 改成 to_state（去掉、恢复共用），返回最新的页。"""
    db = Database(request.scope['env'].DB)
    student_id = current_student_id(request)
    _, item = await load_ready_item(db, page_id, student_id, seq)
    if item.get('state') != from_state:
        raise HTTPException(409, wrong_state_text)
    if not await write_item(db, page_id, seq, from_state, dict(item, state=to_state)):
        await raise_write_conflict(db, page_id, student_id)
    return page_view(await load_page(db, page_id, student_id))


def copy_payload(payload):
    """question_payload 里的列表引用着草稿项，交给保存逻辑前复制一份，避免被改动。"""
    return {key: list(value) if isinstance(value, list) else value for key, value in payload.items()}


async def accept_one(request, db, page_id, student_id, seq):
    """录入一道：写进错题库并把草稿这一项标为 accepted。

    先保存错题，再用条件更新把这一项从 open 改成 accepted。条件更新没成功时
    （别的请求抢先录了这一道，或者这一页刚被结束），把刚写的错题软删除，避免重复入库。
    保存逻辑抛出的 HTTPException 原样往外抛，前端据此把卡片切到修改状态。
    """
    page, item = await load_ready_item(db, page_id, student_id, seq)
    if item.get('state') == 'accepted':
        return  # 已录入过：直接返回上次的结果，不重复写
    if item.get('state') != 'open':
        raise HTTPException(409, '这道题已经去掉了，先恢复再录入')
    if item.get('verdict') == 'right':
        # 模型认为做对的题没有答案和解析，要先"补成错题"才能录入
        raise HTTPException(409, '这道题模型认为做对了，请先点"补成错题"再录入')
    question = await save_question(db, copy_payload(question_payload(page, item)), request=request)
    accepted = dict(item, state='accepted', question_id=question['id'])
    if await write_item(db, page_id, seq, 'open', accepted):
        return
    # 条件更新输了：刚写的这道不能留在题库里
    await db.run('UPDATE question SET deleted=1 WHERE id=? AND deleted=0', (question['id'],))
    current = await load_page(db, page_id, student_id)
    if current['status'] != 'ready':
        raise HTTPException(409, PAGE_CLOSED_TEXT)


# ---------------------------------------------------------------- 逐题操作接口


@router.post('/api/scan/pages/{page_id}/items')
async def add_item(page_id: int, request: Request):
    """手工加一道：在草稿末尾追加一道空白题，序号等于它的下标。"""
    db = Database(request.scope['env'].DB)
    student_id = current_student_id(request)
    page = await load_page(db, page_id, student_id)
    if page['status'] != 'ready':
        raise HTTPException(409, PAGE_CLOSED_TEXT)
    seq = len(json.loads(page['items'] or '[]'))
    # 以草稿长度没变为条件，两个同时追加的请求不会得到相同的序号
    row = await db.first(
        "UPDATE scan_page SET items=json_insert(items, '$[#]', json(?)), updated_at=? "
        "WHERE id=? AND deleted=0 AND status='ready' AND json_array_length(items)=? RETURNING id",
        (json.dumps(blank_item(seq), ensure_ascii=False), stamp_now(), page_id, seq))
    if row is None:
        await raise_write_conflict(db, page_id, student_id)
    return page_view(await load_page(db, page_id, student_id))


@router.put('/api/scan/pages/{page_id}/items/{seq}')
async def edit_item(page_id: int, seq: int, request: Request):
    """保存修改：校验后合并进这道题并标记"被人改过"；只允许未处理的题，不自动录入。"""
    db = Database(request.scope['env'].DB)
    student_id = current_student_id(request)
    payload = await read_payload(request)
    _, item = await load_ready_item(db, page_id, student_id, seq)
    if item.get('state') != 'open':
        raise HTTPException(409, '已录入或已去掉的题不能修改')
    try:
        edit = clean_edit(payload)
    except ScanError as error:
        raise HTTPException(422, error.detail)
    merged = dict(item, **edit, edited=True)
    # clean_edit 只在两个字段同时给出时核对；合并后再核对一次主考点必须在考点里
    primary = merged.get('primary_knowledge_point_id')
    if primary is not None and primary not in (merged.get('knowledge_point_ids') or []):
        raise HTTPException(422, '主考点必须是所选考点之一')
    if not await write_item(db, page_id, seq, 'open', merged):
        await raise_write_conflict(db, page_id, student_id)
    return page_view(await load_page(db, page_id, student_id))


@router.post('/api/scan/pages/{page_id}/items/{seq}/dismiss')
async def dismiss_item(page_id: int, seq: int, request: Request):
    """去掉一道：open → dismissed，不入库。"""
    return await change_state(request, page_id, seq, 'open', 'dismissed', '只有未处理的题才能去掉')


@router.post('/api/scan/pages/{page_id}/items/{seq}/restore')
async def restore_item(page_id: int, seq: int, request: Request):
    """恢复一道：dismissed → open。"""
    return await change_state(request, page_id, seq, 'dismissed', 'open', '这道题没有被去掉')


@router.post('/api/scan/pages/{page_id}/items/{seq}/promote')
async def promote_item(page_id: int, seq: int, request: Request):
    """补成错题：把模型认为做对的一道移到主列表，再调一次模型补答案、解析、考点、错因、难度。

    先写入移动（source、verdict、reason），模型失败时不回滚移动，返回 fill_error 让前端进入修改状态。
    """
    db = Database(request.scope['env'].DB)
    student_id = current_student_id(request)
    page, item = await load_ready_item(db, page_id, student_id, seq)
    if item.get('verdict') != 'right' or item.get('state') != 'open':
        raise HTTPException(409, '只有模型认为做对、还没处理的题才能补成错题')
    moved = dict(item, source='promoted', verdict='wrong', reason=PROMOTED_REASON)
    if not await write_item(db, page_id, seq, 'open', moved):
        await raise_write_conflict(db, page_id, student_id)
    subject = await db.first('SELECT name FROM subject WHERE id=? AND deleted=0', (page['subject_id'],))
    catalog = await load_catalog(db, page['subject_id'], page['grade'], page['semester'])
    error_type_names = await load_error_type_names(db, page['subject_id'])
    prompt = build_fill_prompt(subject['name'] if subject else '', page['grade'], moved, catalog,
                               sorted(error_type_names))
    fill_error = None
    try:
        raw = await generate_json(request, prompt)
    except HTTPException as error:
        fill_error = error.detail
    except Exception:
        # 生产环境里网络超时等会抛运行时异常，统一给一句模型失败的提示
        fill_error = MODEL_FAILED_TEXT
    if fill_error is None:
        catalog_ids = {point['id'] for group in catalog for point in group['points']}
        filled = dict(moved, **clean_fill(raw, catalog_ids, error_type_names))
        # 补全结果也用条件写：这期间这道题被录入或去掉了就不再覆盖
        await write_item(db, page_id, seq, 'open', filled)
    return {'page': page_view(await load_page(db, page_id, student_id)), 'fill_error': fill_error}


@router.post('/api/scan/pages/{page_id}/items/{seq}/accept')
async def accept_item(page_id: int, seq: int, request: Request):
    """录入一道：写进错题库（已录入过的直接返回），返回最新的页。"""
    db = Database(request.scope['env'].DB)
    student_id = current_student_id(request)
    await accept_one(request, db, page_id, student_id, seq)
    return page_view(await load_page(db, page_id, student_id))


@router.post('/api/scan/pages/{page_id}/accept-all')
async def accept_all(page_id: int, request: Request):
    """全部录入：对"做错了、没提示、未处理"的题逐道录入，每道独立成败。

    一次请求最多录 ACCEPT_ALL_BATCH 道（免费计划限制单次请求的数据库查询次数），
    remaining 是这批做完后仍符合条件、还没录入的题数，前端大于 0 时再调一次。
    注意：这一批里失败的题仍是 open，会计入 remaining，前端遇到失败应先停下处理。
    """
    db = Database(request.scope['env'].DB)
    student_id = current_student_id(request)
    page = await load_page(db, page_id, student_id)
    if page['status'] != 'ready':
        raise HTTPException(409, PAGE_CLOSED_TEXT)
    results = []
    for seq in accept_all_seqs(json.loads(page['items'] or '[]'))[:ACCEPT_ALL_BATCH]:
        try:
            await accept_one(request, db, page_id, student_id, seq)
            results.append({'seq': seq, 'ok': True, 'detail': None})
        except HTTPException as error:
            results.append({'seq': seq, 'ok': False, 'detail': error.detail})
    view = page_view(await load_page(db, page_id, student_id))
    return {'results': results, 'remaining': len(accept_all_seqs(view['items'])), 'page': view}


@router.post('/api/scan/pages/{page_id}/items/{seq}/withdraw')
async def withdraw_item(page_id: int, seq: int, request: Request):
    """撤回录入：这一项回到 open，对应错题软删除。

    两条写入放在同一个 batch（同一事务）里：先删题，条件是草稿这一项仍是 accepted、
    指向这道题、页面仍是 ready；再用同样的条件把草稿改回 open。
    同时来的第二次撤回两条条件都不成立，什么都不做。
    """
    db = Database(request.scope['env'].DB)
    student_id = current_student_id(request)
    _, item = await load_ready_item(db, page_id, student_id, seq)
    if item.get('state') != 'accepted':
        raise HTTPException(409, '这道题还没有录入')
    question_id = item.get('question_id')
    reopened = dict(item, state='open', question_id=None)
    await db.batch([
        ('UPDATE question SET deleted=1 WHERE id=? AND deleted=0 AND EXISTS('
         "SELECT 1 FROM scan_page WHERE id=? AND deleted=0 AND status='ready' "
         "AND json_extract(items, '$[' || ? || '].state')='accepted' "
         "AND json_extract(items, '$[' || ? || '].question_id')=?)",
         (question_id, page_id, seq, seq, question_id)),
        ("UPDATE scan_page SET items=json_set(items, '$[' || ? || ']', json(?)), updated_at=? "
         "WHERE id=? AND deleted=0 AND status='ready' AND json_extract(items, '$[' || ? || '].state')='accepted'",
         (seq, json.dumps(reopened, ensure_ascii=False), stamp_now(), page_id, seq)),
    ])
    page = await load_page(db, page_id, student_id)
    current = json.loads(page['items'] or '[]')[seq]
    if current.get('state') == 'accepted' and current.get('question_id') == question_id:
        # 两条都没生效且这一项没被别人撤回：只可能是页面已经不是 ready
        await raise_write_conflict(db, page_id, student_id)
    return page_view(page)
