"""批改识别预批的两个接口（设计 2026-11-12-grading-recognition-design.md 第 4 节）。

页面一步一步推进：先逐张调"读一页"拿回识别文字，全部读完后调一次"比对"拿回每题的预批结果。
识别文字和预批结果都不写库，接口直接返回给页面，页面在内存里拿着；所以没有新表、没有迁移。

一份卷子正常批改：读图 N 次（N = 照片数，打到自家识别主机）+ 模型 1 次。

下面这些模块级名字测试时会被替换，代码里一律通过模块名字调用：
ocr_client、generate_json、sleep、Database。
"""

import asyncio

from fastapi import APIRouter, HTTPException, Request

import ocr_client
from database import Database
from grading_model import (MAX_PAGE_TEXT, NUMBERING_CHANGED_TEXT, build_judge_prompt, clean_judgement,
                           numbering_changed)
from intake import read_payload
from intake_model import is_plain_int
from practices import get as get_practice
from scan_model import (HOST_TIMEOUT_SECONDS, MISSING_IMAGE_TEXT, SCAN_MAX_TOKENS, SCAN_TEMPERATURE,
                        parse_model_json, read_with_retries)
from settings import generate_json

router = APIRouter(prefix='/api/practice-sets')

sleep = asyncio.sleep
UNAVAILABLE_TEXT = '识别没成功，已改为手动批改'
JUDGE_FAILED_TEXT = '比对没成功，已改为手动批改'
ONLY_QUESTION_TEXT = '只有错题练习卷可以识别批改'


async def load_question_set(db, practice_set_id, details):
    """读一份错题练习卷：不存在或已删除 404，单词、阅读练习 422。"""
    practice = await get_practice(db, practice_set_id, details)
    if practice['source_type'] in ('word', 'reading'):
        raise HTTPException(422, ONLY_QUESTION_TEXT)
    return practice


@router.post('/{practice_set_id}/recognize/page')
async def recognize_page(practice_set_id: int, request: Request):
    """读一张照片：按照片序号从这份卷子的 review_images 里取路径（不接受前端传路径），交给识别主机。

    成功返回 {'index', 'text'}；照片找不到 404；识别主机不可用、忙、读不出来都返回 503，
    页面据此跳过这一页（全部页都没读出来就改为手动批改）。只读图，不写库。
    """
    payload = await read_payload(request)
    index = payload.get('index')
    db = Database(request.scope['env'].DB)
    practice = await load_question_set(db, practice_set_id, False)
    images = practice['review_images'] or []
    if not is_plain_int(index) or not 0 <= index < len(images):
        raise HTTPException(422, '照片序号不对')
    env = request.scope['env']
    image = await ocr_client.read_image(env, images[index])
    if image is None:
        raise HTTPException(404, MISSING_IMAGE_TEXT)
    content, content_type = image

    async def fetch():
        """调一次主机的 /ocr（普通模式，不做强化重扫）。"""
        return await ocr_client.fetch_ocr(env, content, content_type, 'normal', HOST_TIMEOUT_SECONDS['normal'])

    # 主机忙时按约定等待重试；等待用模块里的 sleep（测试时会被换成假的）
    result = await read_with_retries(fetch, lambda seconds: sleep(seconds))
    if result['kind'] != 'ok':
        if result['detail']:
            print('grading recognize page failed: %s' % result['detail'][:80])  # 只记主机细节，不给用户看
        raise HTTPException(503, UNAVAILABLE_TEXT)
    return {'index': index, 'text': result['text']}


def read_pages(payload, image_count):
    """检查比对请求里的各页识别文字，返回 [(页号, 文字)]（页号 = 照片序号 + 1）；格式不对 422。"""
    pages = payload.get('pages')
    if not isinstance(pages, list) or not 1 <= len(pages) <= image_count:
        raise HTTPException(422, '请先识别至少一页照片')
    result, seen = [], set()
    for page in pages:
        if not isinstance(page, dict):
            raise HTTPException(422, '识别文字格式不对')
        index, text = page.get('index'), page.get('text')
        if not is_plain_int(index) or not 0 <= index < image_count or index in seen:
            raise HTTPException(422, '照片序号不对')
        if not isinstance(text, str) or not text.strip() or len(text) > MAX_PAGE_TEXT:
            raise HTTPException(422, '识别文字格式不对')
        seen.add(index)
        result.append((index + 1, text))
    return sorted(result)


@router.post('/{practice_set_id}/recognize/judge')
async def recognize_judge(practice_set_id: int, request: Request):
    """比对：题号、题目、标准答案由服务端从库里取（不从前端传），拼提示词，调一次模型，清洗后返回。

    返回 {'items': [{'id', 'number', 'student_answer', 'verdict', 'page'}]}，每道题一项、按题号排。
    题号可能和纸上对不上时 409；模型出错 502。不写库。
    """
    payload = await read_payload(request)
    db = Database(request.scope['env'].DB)
    practice = await load_question_set(db, practice_set_id, True)
    pages = read_pages(payload, len(practice['review_images'] or []))
    if numbering_changed(practice):
        raise HTTPException(409, NUMBERING_CHANGED_TEXT)
    questions = sorted(practice['questions'], key=lambda item: item['number'])
    if not questions:
        raise HTTPException(422, '这份卷子没有题目')
    prompt = build_judge_prompt(practice.get('subject_name'), pages, questions)
    try:
        raw = await generate_json(request, prompt, max_tokens=SCAN_MAX_TOKENS, temperature=SCAN_TEMPERATURE,
                                  parse=parse_model_json)
    except Exception as error:
        print('grading judge failed: %s' % type(error).__name__)
        raise HTTPException(502, JUDGE_FAILED_TEXT) from error
    numbers = {item['number']: item['id'] for item in questions}
    return {'items': clean_judgement(raw, numbers, {page_no for page_no, _ in pages})}
