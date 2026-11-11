"""整页识别录入的本地测试。

任务 3 起用生产结构基线 + 种子数据 + 迁移 0011、0012、0014 建库测试接口。运行：

    python cloudflare/scripts/scan_test.py
"""

import asyncio
import contextlib
import json
import pathlib
import sys
import traceback

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
sys.path.insert(0, str(ROOT / 'scripts'))

from fastapi import HTTPException  # noqa: E402
from knowledge_invariants_test import SQLiteDB  # noqa: E402  复用生产异步接口的 sqlite 适配器
from intake_test import build_legacy_database  # noqa: E402  生产结构基线 + 种子数据
import pdf  # noqa: E402
import scan  # noqa: E402
import scan_model  # noqa: E402

MIGRATIONS = ROOT / 'migrations'


def configure_output():
    """把标准输出改成 utf-8，避免 Windows GBK 控制台打印中文时报错。"""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding='utf-8', errors='replace')
        except (AttributeError, ValueError):
            pass


def run(coroutine):
    """同步运行一个协程。"""
    return asyncio.run(coroutine)


class FakeEnv:
    """伪造 Worker 的 env，健康检查接口不访问任何绑定。"""


class FakeRequest:
    """伪造 FastAPI 的 Request，只提供 scope。"""

    def __init__(self):
        self.scope = {'env': FakeEnv()}


class FakeOcrClient:
    """替换 scan.ocr_client 的假客户端，健康检查返回预设结果。"""

    def __init__(self, health_result):
        self.health_result = health_result

    async def fetch_health(self, env, timeout_seconds):
        """返回预设的 (状态码, JSON)。"""
        return self.health_result


# ---------------------------------------------------------------- 健康检查

def test_interpret_health():
    """只有 200、ok 为真、契约版本为 1 才算可用。"""
    assert scan_model.interpret_health(200, {'ok': True, 'contract': 1, 'ollama': True}) is True
    assert scan_model.interpret_health(200, {'ok': False, 'contract': 1, 'ollama': False}) is False
    assert scan_model.interpret_health(200, {'ok': True, 'contract': 2}) is False
    assert scan_model.interpret_health(200, None) is False
    assert scan_model.interpret_health(401, {'ok': False}) is False
    assert scan_model.interpret_health(0, None) is False


def with_ocr_client(client, function):
    """临时替换 scan.ocr_client 运行 function，结束后一定还原。"""
    original = scan.ocr_client
    scan.ocr_client = client
    try:
        return function()
    finally:
        scan.ocr_client = original


def test_health_endpoint_hides_host_details():
    """健康检查接口只返回 available，不透出主机的任何字段。"""
    available = FakeOcrClient((200, {'ok': True, 'contract': 1, 'model': 'x'}))
    assert with_ocr_client(available, lambda: run(scan.health(FakeRequest()))) == {'available': True}
    down = FakeOcrClient((0, None))
    assert with_ocr_client(down, lambda: run(scan.health(FakeRequest()))) == {'available': False}


# ---------------------------------------------------------------- 纯规则

def test_clean_items_drops_bad_catalog_and_error_types():
    """清洗：丢掉清单外的考点和错因，难度越界改 3，只留认识的标记。"""
    raw = {'questions': [{'question_no': '3', 'parsed_question': '比 x 的立方少 3', 'wrong_answer': 'x^2+3',
           'verdict': 'wrong', 'reason': '应为 x^3-3', 'flags': ['broken_formula', 'nonsense'],
           'answer': 'x^3-3', 'analysis': '…', 'knowledge_point_ids': [101, 999, '101'],
           'primary_knowledge_point_id': 999, 'error_types': ['计算错误', '乱写'], 'difficulty': 9}]}
    [item] = scan_model.clean_items(raw, {101, 102}, {'计算错误'})
    assert item['seq'] == 0 and item['state'] == 'open' and item['source'] == 'model' and item['edited'] is False
    assert item['knowledge_point_ids'] == [101]
    assert item['primary_knowledge_point_id'] == 101
    assert item['error_types'] == ['计算错误'] and item['difficulty'] == 3
    assert item['flags'] == ['broken_formula']


def test_clean_items_primary_none_when_several_points_left():
    """主考点无效且剩多个考点时为 None；有效时保留。"""
    raw = {'questions': [{'parsed_question': 'a', 'verdict': 'wrong', 'knowledge_point_ids': [101, 102],
                          'primary_knowledge_point_id': 5},
                         {'parsed_question': 'b', 'verdict': 'wrong', 'knowledge_point_ids': [101, 102],
                          'primary_knowledge_point_id': 102}]}
    first, second = scan_model.clean_items(raw, {101, 102}, set())
    assert first['primary_knowledge_point_id'] is None and second['primary_knowledge_point_id'] == 102


def test_clean_items_right_items_drop_answer_fields():
    """做对的题清空答案、解析、考点、错因。"""
    [item] = scan_model.clean_items({'questions': [{'parsed_question': 'a', 'verdict': 'right', 'answer': '1',
                                     'knowledge_point_ids': [101]}]}, {101}, set())
    assert item['answer'] == '' and item['knowledge_point_ids'] == [] and item['verdict'] == 'right'


def test_clean_items_bad_types_mark_unsure():
    """字段类型不对或判断不认识的题标为拿不准；不是对象的项丢掉。"""
    items = scan_model.clean_items({'questions': [{'parsed_question': 5, 'verdict': 'wrong'}, 'junk',
                                                  {'parsed_question': 'b', 'verdict': 'maybe'}]}, set(), set())
    assert [i['verdict'] for i in items] == ['unsure', 'unsure']
    assert [i['seq'] for i in items] == [0, 1]
    assert items[0]['parsed_question'] == '' and items[0]['reason']


def test_clean_items_numeric_question_no():
    """题号是数字（非 bool）时转成文字，不降级；bool 仍算类型错误。"""
    items = scan_model.clean_items({'questions': [
        {'question_no': 3, 'parsed_question': 'a', 'verdict': 'wrong'},
        {'question_no': 3.0, 'parsed_question': 'b', 'verdict': 'wrong'},
        {'question_no': 2.5, 'parsed_question': 'c', 'verdict': 'wrong'},
        {'question_no': True, 'parsed_question': 'd', 'verdict': 'wrong'}]}, set(), set())
    assert [i['question_no'] for i in items] == ['3', '3', '2.5', '']
    assert [i['verdict'] for i in items] == ['wrong', 'wrong', 'wrong', 'unsure']


def test_clean_items_garbage_and_limit():
    """整体不是预期结构时返回空；题数不超过上限。"""
    assert scan_model.clean_items(None, set(), set()) == []
    assert scan_model.clean_items({'questions': 'x'}, set(), set()) == []
    many = {'questions': [{'parsed_question': str(n), 'verdict': 'wrong'} for n in range(200)]}
    assert len(scan_model.clean_items(many, set(), set())) == scan_model.MAX_ITEMS


def test_clean_fill():
    """单题补全只返回六个字段，规则同整页清洗。"""
    fill = scan_model.clean_fill({'answer': '1', 'analysis': 5, 'knowledge_point_ids': [101, 7],
                                  'primary_knowledge_point_id': 7, 'error_types': ['计算错误', 'x'],
                                  'difficulty': 0, 'extra': 'ignored'}, {101}, {'计算错误'})
    assert fill == {'answer': '1', 'analysis': '', 'knowledge_point_ids': [101],
                    'primary_knowledge_point_id': 101, 'error_types': ['计算错误'], 'difficulty': 3}
    assert scan_model.clean_fill(None, {101}, set())['knowledge_point_ids'] == []


def test_needs_rescan():
    """有标记、没重扫过、允许重扫才重扫。"""
    flagged = [{'flags': ['merged'], 'verdict': 'wrong'}]
    assert scan_model.needs_rescan(flagged, False, True) is True
    assert scan_model.needs_rescan(flagged, True, True) is False
    assert scan_model.needs_rescan(flagged, False, False) is False
    assert scan_model.needs_rescan([{'flags': [], 'verdict': 'wrong'}], False, True) is False


def test_interpret_ocr():
    """读图结果分 ok / busy / failed，并给出用户文字。"""
    ok = scan_model.interpret_ocr(200, {'ok': True, 'contract': 1, 'mode': 'normal', 'text': '1. 计算', 'segments': ['1. 计算'], 'elapsed_ms': 5000})
    assert ok['kind'] == 'ok' and ok['text'] == '1. 计算' and ok['elapsed_ms'] == 5000
    assert scan_model.interpret_ocr(503, {'ok': False, 'contract': 1, 'code': 'busy'})['kind'] == 'busy'
    wrong = scan_model.interpret_ocr(200, {'ok': True, 'contract': 2, 'text': 'x'})
    assert wrong['kind'] == 'failed' and '版本不一致' in wrong['user_text']
    for status, body in [(502, {'ok': False, 'code': 'ocr_failed', 'detail': 'Ollama 连不上'}), (0, None),
                         (200, None), (200, {'ok': True, 'contract': 1, 'text': '   '}), (530, None)]:
        result = scan_model.interpret_ocr(status, body)
        assert result['kind'] == 'failed' and result['user_text'] == '读图没成功'
    missing = scan_model.interpret_ocr(200, {'ok': True, 'text': 'x'})
    assert missing['kind'] == 'failed' and '版本不一致' in missing['user_text']
    assert scan_model.interpret_ocr(502, {'ok': False, 'code': 'ocr_failed', 'detail': 'Ollama 连不上'})['detail'] == 'Ollama 连不上'


def test_next_step():
    """按状态和 step_started_at 决定下一步。"""
    now = 10_000
    page = lambda **kw: {'status': 'uploaded', 'step_started_at': None, 'ocr_text': None, **kw}
    assert scan_model.next_step(page(), now) == 'read'
    assert scan_model.next_step(page(status='reading', step_started_at=now - 10), now) == 'working'
    assert scan_model.next_step(page(status='reading', step_started_at=now - 151), now) == 'read'
    assert scan_model.next_step(page(status='analyzing', ocr_text='t'), now) == 'analyze'
    assert scan_model.next_step(page(status='rescanning', ocr_text='t'), now) == 'rescan'
    assert scan_model.next_step(page(status='failed'), now) == 'read'
    assert scan_model.next_step(page(status='failed', ocr_text='t'), now) == 'analyze'
    assert scan_model.next_step(page(status='ready'), now) is None
    assert scan_model.next_step(page(status='closed'), now) is None


def test_accept_all_and_warning():
    """全部录入只含未处理、做错、没有提示的题。"""
    items = [
        {'seq': 0, 'state': 'open', 'verdict': 'wrong', 'flags': [], 'edited': False},
        {'seq': 1, 'state': 'open', 'verdict': 'wrong', 'flags': ['merged'], 'edited': False},
        {'seq': 2, 'state': 'open', 'verdict': 'wrong', 'flags': ['merged'], 'edited': True},
        {'seq': 3, 'state': 'open', 'verdict': 'unsure', 'flags': [], 'edited': False},
        {'seq': 4, 'state': 'accepted', 'verdict': 'wrong', 'flags': [], 'edited': False},
        {'seq': 5, 'state': 'dismissed', 'verdict': 'wrong', 'flags': [], 'edited': False},
        {'seq': 6, 'state': 'open', 'verdict': 'right', 'flags': [], 'edited': False},
    ]
    assert scan_model.accept_all_seqs(items) == [0, 2]
    assert scan_model.has_warning(items[1]) is True and scan_model.has_warning(items[2]) is False


def test_clean_edit():
    """修改校验：合法的原样返回，非法的抛 ScanError，无关字段忽略。"""
    edit = scan_model.clean_edit({'question_no': '7', 'parsed_question': '计算', 'wrong_answer': '', 'answer': '1',
                                  'analysis': '', 'knowledge_point_ids': [101], 'primary_knowledge_point_id': 101,
                                  'error_types': ['计算错误'], 'difficulty': 2, 'state': 'accepted'})
    assert edit['difficulty'] == 2 and edit['knowledge_point_ids'] == [101] and 'state' not in edit
    assert scan_model.clean_edit({'answer': 'x'}) == {'answer': 'x'}
    for bad in [{'difficulty': 6}, {'difficulty': True}, {'knowledge_point_ids': ['1']},
                {'knowledge_point_ids': [101], 'primary_knowledge_point_id': 102}, {'parsed_question': 3},
                {'error_types': '计算错误'}, None]:
        try:
            scan_model.clean_edit(bad)
        except scan_model.ScanError as error:
            assert error.detail and not any(c.isascii() and c.isalpha() for c in error.detail), error.detail
            continue
        raise AssertionError(bad)


def test_question_payload():
    """入库字段拼装：错因逗号连接，原图单元素列表。"""
    page = {'subject_id': 1, 'grade': 6, 'semester': 1, 'image': '2026/11/aaaaaaaa_p.jpg'}
    item = {**scan_model.blank_item(0), 'question_no': '3', 'parsed_question': '题', 'answer': '1', 'analysis': '析',
            'wrong_answer': '2', 'knowledge_point_ids': [101], 'primary_knowledge_point_id': 101,
            'error_types': ['计算错误', '概念错误'], 'difficulty': 4}
    assert scan_model.question_payload(page, item) == {
        'subject_id': 1, 'grade': 6, 'semester': 1, 'question_no': '3', 'parsed_question': '题', 'answer': '1',
        'analysis': '析', 'wrong_answer': '2', 'difficulty': 4, 'error_type': '计算错误,概念错误',
        'knowledge_point_ids': [101], 'primary_knowledge_point_id': 101,
        'original_image': '2026/11/aaaaaaaa_p.jpg', 'original_images': ['2026/11/aaaaaaaa_p.jpg'],
        'wrong_evidence': '页面识别，家长确认'}


def test_changes_library():
    """只有录入、撤回、全部录入三类路径会改动错题库。"""
    assert scan_model.changes_library('POST', '/api/scan/pages/3/items/2/accept') is True
    assert scan_model.changes_library('POST', '/api/scan/pages/3/accept-all') is True
    assert scan_model.changes_library('POST', '/api/scan/pages/3/items/2/withdraw') is True
    for path in ['/api/scan/pages', '/api/scan/pages/3/advance', '/api/scan/pages/3/items/2/dismiss',
                 '/api/scan/pages/3/items/2/restore', '/api/scan/pages/3/items/2/promote',
                 '/api/scan/pages/3/items', '/api/scan/pages/3/close', '/api/scan/pages/x/accept-all',
                 '/api/scan/pages/3/items/2/accept/extra']:
        assert scan_model.changes_library('POST', path) is False
    assert scan_model.changes_library('PUT', '/api/scan/pages/3/items/2') is False


def test_build_page_prompt():
    """整页提示词含考点编号、错因名、OCR 文字（重扫文字）和关键规则。"""
    catalog = [{'id': 1, 'name': '代数', 'points': [{'id': 101, 'name': '一元二次方程'}]}]
    prompt = scan_model.build_page_prompt('数学', 6, 1, '第一遍文字ABC', None, catalog, ['计算错误'])
    assert '101' in prompt and '一元二次方程' in prompt and '计算错误' in prompt and '第一遍文字ABC' in prompt
    for rule in ['不许猜孩子写了什么', '0.5 和 1/2 不算错', '没有作答', '按做错', 'questions']:
        assert rule in prompt, rule
    assert '分段重新读取' not in prompt
    both = scan_model.build_page_prompt('数学', 6, 1, '第一遍文字ABC', '重扫文字XYZ', catalog, ['计算错误'])
    assert '重扫文字XYZ' in both and '分段重新读取' in both and '对照着用' in both


def test_build_fill_prompt():
    """单题补全提示词只含这一道题和要返回的字段。"""
    item = {**scan_model.blank_item(2), 'question_no': '5', 'parsed_question': '题干QQQ', 'wrong_answer': '甲'}
    catalog = [{'id': 1, 'name': '代数', 'points': [{'id': 101, 'name': '方程'}]}]
    prompt = scan_model.build_fill_prompt('数学', 6, item, catalog, ['计算错误'])
    assert '题干QQQ' in prompt and '101' in prompt and '计算错误' in prompt
    for field in ['answer', 'analysis', 'knowledge_point_ids', 'primary_knowledge_point_id', 'error_types', 'difficulty']:
        assert field in prompt


# ---------------------------------------------------------------- 任务 3：建页与分步推进

NOW = 1_800_000_000          # 假的"当前时间"（整数秒）
GOOD_IMAGE = '2026/11/a1b2c3d4_page.jpg'
FIRST_TEXT = '1. 计算 3/4×2/3=  孩子写 1/3\n2. 计算 1/2÷1/4=  孩子写 1/8\n3. 计算 1+1=  孩子写 2'
ENHANCED_TEXT = '重扫读到的文字ENHANCED'


def apply_migrations(connection, names):
    """按顺序执行 migrations 目录里的若干迁移文件。"""
    for name in names:
        connection.executescript((MIGRATIONS / name).read_text(encoding='utf-8'))
    connection.commit()


def build_scan_database():
    """建库：生产结构基线 + 种子数据，再执行 0011、0012、0014。"""
    connection = build_legacy_database()
    apply_migrations(connection, ['0011_intake_papers.sql', '0012_starmap.sql', '0014_scan_page.sql'])
    return connection


class ScanEnv:
    """伪造 Worker 的 env：DB 放测试库，rescan 不为空时设置重扫开关。"""

    def __init__(self, db, rescan=None):
        self.DB = db
        if rescan is not None:
            self.SCAN_RESCAN = rescan


class PageRequest:
    """伪造 FastAPI 的 Request：提供 scope 与 json()。"""

    def __init__(self, db, payload=None, rescan=None):
        self.scope = {'env': ScanEnv(db, rescan)}
        self.payload = payload

    async def json(self):
        """返回构造时给定的请求体。"""
        return self.payload


class YieldingDB(SQLiteDB):
    """每次访问数据库前先让出一次，让两个并发的推进请求真正交错执行。"""

    async def first(self, sql, parameters=()):
        """让出一次再查询。"""
        await asyncio.sleep(0)
        return await super().first(sql, parameters)

    async def run(self, sql, parameters=()):
        """让出一次再写入。"""
        await asyncio.sleep(0)
        return await super().run(sql, parameters)


def ocr_ok(text, mode='normal'):
    """主机读图成功时的返回。"""
    return 200, {'ok': True, 'contract': 1, 'mode': mode, 'text': text, 'segments': [text],
                 'elapsed_ms': 4000, 'model': 'x'}


BUSY = (503, {'ok': False, 'contract': 1, 'code': 'busy', 'detail': '排队已满'})
HOST_FAILED = (502, {'ok': False, 'contract': 1, 'code': 'ocr_failed', 'detail': 'Ollama 连不上'})


class FakeHost:
    """假的识别主机（替换 scan.ocr_client）：按顺序给出预设返回，最后一个一直重复，并记录调用次数。"""

    def __init__(self, normal=(), enhanced=(), image=(b'img', 'image/jpeg'), yield_once=False):
        self.replies = {'normal': list(normal) or [ocr_ok(FIRST_TEXT)],
                        'enhanced': list(enhanced) or [ocr_ok(ENHANCED_TEXT, 'enhanced')]}
        self.calls = {'normal': 0, 'enhanced': 0}
        self.image = image
        self.yield_once = yield_once

    async def read_image(self, env, key):
        """返回预设的图片（None 表示照片找不到）。"""
        return self.image

    async def fetch_ocr(self, env, content, content_type, mode, timeout_seconds):
        """记录一次调用，按顺序返回预设结果。"""
        assert timeout_seconds == scan_model.HOST_TIMEOUT_SECONDS[mode]
        index = self.calls[mode]
        self.calls[mode] += 1
        if self.yield_once:
            await asyncio.sleep(0)  # 让出一次，模拟真实的网络等待
        replies = self.replies[mode]
        return replies[min(index, len(replies) - 1)]


def model_result(first_flags=()):
    """假模型的整页结果：两道错、一道对；first_flags 是第一道题的读图异常标记。"""
    return {'questions': [
        {'question_no': '1', 'parsed_question': '计算 \\(\\frac{3}{4}\\times\\frac{2}{3}\\)', 'wrong_answer': '1/3',
         'verdict': 'wrong', 'reason': '应为 1/2', 'flags': list(first_flags), 'answer': '1/2', 'analysis': '约分',
         'knowledge_point_ids': [101], 'primary_knowledge_point_id': 101, 'error_types': ['计算错误'],
         'difficulty': 2},
        {'question_no': '2', 'parsed_question': '计算 1/2÷1/4', 'wrong_answer': '1/8', 'verdict': 'wrong',
         'reason': '应为 2', 'flags': [], 'answer': '2', 'analysis': '除以一个数等于乘它的倒数',
         'knowledge_point_ids': [102], 'primary_knowledge_point_id': 102, 'error_types': ['概念错误'],
         'difficulty': 3},
        {'question_no': '3', 'parsed_question': '计算 1+1', 'wrong_answer': '2', 'verdict': 'right',
         'reason': '对', 'flags': []},
    ]}


class FakeModel:
    """假的文本模型（替换 scan.generate_json）：按顺序给出预设结果，异常就抛出，记录每次的提示词。"""

    def __init__(self, *replies):
        self.replies = list(replies) or [model_result()]
        self.prompts = []

    async def __call__(self, request, prompt):
        """记录提示词并返回（或抛出）预设结果。"""
        reply = self.replies[min(len(self.prompts), len(self.replies) - 1)]
        self.prompts.append(prompt)
        if isinstance(reply, Exception):
            raise reply
        return reply


class FakeSleep:
    """假的 sleep：只记录等了几次、每次多久，不真的等。"""

    def __init__(self):
        self.waits = []

    async def __call__(self, seconds):
        """记录一次等待。"""
        self.waits.append(seconds)


@contextlib.contextmanager
def scan_patched(host=None, model=None, sleeper=None, now=NOW):
    """临时替换 scan 模块里的主机、模型、sleep、时间和 Database，结束后一定还原。"""
    replacements = {
        'ocr_client': host or FakeHost(), 'generate_json': model or FakeModel(),
        'sleep': sleeper or FakeSleep(), 'now_seconds': lambda: now, 'Database': lambda binding: binding,
    }
    originals = {name: getattr(scan, name) for name in replacements}
    for name, value in replacements.items():
        setattr(scan, name, value)
    try:
        yield
    finally:
        for name, value in originals.items():
            setattr(scan, name, value)


def expect_http(status_code, function):
    """调用函数，要求它抛出指定状态码的 HTTPException。"""
    try:
        function()
    except HTTPException as error:
        assert error.status_code == status_code, '期望 %s，实际 %s' % (status_code, error.status_code)
        return
    raise AssertionError('期望 HTTP %s，但没有抛出' % status_code)


def new_page(db, **overrides):
    """用接口新建一页（调用方负责先替换 Database），返回页面内容。"""
    payload = {'image': GOOD_IMAGE, 'subject_id': 1, 'grade': 6, 'semester': 1, **overrides}
    return run(scan.create_page(PageRequest(db, payload)))


def advance(db, page_id, rescan=None):
    """推进一页一步，返回 {'busy', 'page'}。"""
    return run(scan.advance_page(page_id, PageRequest(db, rescan=rescan)))


def page_row(connection, page_id):
    """直接从库里读一页的整行（含 OCR 文字）。"""
    return dict(connection.execute('SELECT * FROM scan_page WHERE id=?', (page_id,)).fetchone())


def schema_rows(connection):
    """库里所有对象的 (type, name, sql)。"""
    return set(tuple(row) for row in connection.execute('SELECT type,name,sql FROM sqlite_master').fetchall())


def test_migration_0014_only_adds_scan_page():
    """0014 只新增 scan_page 表和它的索引，已有的表、索引、触发器一个不变；可以重复执行。"""
    connection = build_legacy_database()
    apply_migrations(connection, ['0011_intake_papers.sql', '0012_starmap.sql', '0013_starmap_seed.sql'])
    before = schema_rows(connection)
    apply_migrations(connection, ['0014_scan_page.sql'])
    after = schema_rows(connection)
    assert before <= after
    assert {(kind, name) for kind, name, _ in after - before} == {
        ('table', 'scan_page'), ('index', 'cf_scan_page_student_status')}
    apply_migrations(connection, ['0014_scan_page.sql'])
    assert schema_rows(connection) == after


def test_create_page_validates_image_and_subject():
    """照片路径不合规则 422，学科不存在 400，年级越界 422；合格的建成 uploaded 页。"""
    connection = build_scan_database()
    db = SQLiteDB(connection)
    with scan_patched():
        expect_http(422, lambda: new_page(db, image='../x.jpg'))
        expect_http(422, lambda: new_page(db, image='2026/11/zz_p.jpg'))
        expect_http(400, lambda: new_page(db, subject_id=99))
        expect_http(422, lambda: new_page(db, grade=13))
        expect_http(422, lambda: new_page(db, semester=3))
        page = new_page(db)
    assert page['status'] == 'uploaded' and page['image'] == GOOD_IMAGE and page['items'] == []
    assert page['timings'] == {} and page['rescan_used'] == 0 and 'ocr_text' not in page
    row = page_row(connection, page['id'])
    assert row['student_id'] == 1 and row['subject_id'] == 1 and row['grade'] == 6 and row['semester'] == 1
    assert connection.execute('SELECT COUNT(*) FROM scan_page').fetchone()[0] == 1


def test_advance_happy_path_without_rescan():
    """不重扫：读图 → 整理 → ready，再推不再调用主机和模型。"""
    connection = build_scan_database()
    db = SQLiteDB(connection)
    host, model = FakeHost(), FakeModel()
    with scan_patched(host, model):
        page_id = new_page(db)['id']
        first = advance(db, page_id)
        assert first['busy'] is False and first['page']['status'] == 'analyzing'
        second = advance(db, page_id)
        assert second['busy'] is False and second['page']['status'] == 'ready'
        third = advance(db, page_id)
        assert third['busy'] is False and third['page']['status'] == 'ready'
    page = third['page']
    assert len(page['items']) == 3 and [item['verdict'] for item in page['items']] == ['wrong', 'wrong', 'right']
    assert 'read_ms' in page['timings'] and 'analyze_ms' in page['timings']
    assert page['timings']['host_read_ms'] == 4000 and 'ocr_text' not in page and page['error'] is None
    assert host.calls == {'normal': 1, 'enhanced': 0} and len(model.prompts) == 1
    # 提示词里有读图文字、考点清单和错因清单
    assert FIRST_TEXT in model.prompts[0] and '101' in model.prompts[0] and '计算错误' in model.prompts[0]
    row = page_row(connection, page_id)
    assert row['ocr_text'] == FIRST_TEXT and row['step_started_at'] is None


def test_advance_with_rescan_runs_once():
    """有读图异常标记时重扫一次，两份文字一起再整理；第二次仍有标记也不再重扫。"""
    connection = build_scan_database()
    db = SQLiteDB(connection)
    host, model = FakeHost(), FakeModel(model_result(['merged']), model_result(['merged']))
    with scan_patched(host, model):
        page_id = new_page(db)['id']
        statuses = [advance(db, page_id)['page']['status'] for _ in range(4)]
        assert statuses == ['analyzing', 'rescanning', 'analyzing', 'ready'], statuses
        last = advance(db, page_id)
    assert last['busy'] is False and last['page']['status'] == 'ready'
    assert host.calls == {'normal': 1, 'enhanced': 1} and len(model.prompts) == 2
    assert ENHANCED_TEXT not in model.prompts[0] and ENHANCED_TEXT in model.prompts[1]
    assert FIRST_TEXT in model.prompts[1]
    timings = last['page']['timings']
    for key in ('read_ms', 'analyze_ms', 'rescan_ms', 'analyze2_ms', 'host_read_ms', 'host_rescan_ms'):
        assert key in timings, key
    assert last['page']['rescan_used'] == 1
    assert page_row(connection, page_id)['ocr_text_enhanced'] == ENHANCED_TEXT


def test_rescan_switch_off():
    """SCAN_RESCAN=off 时，带标记也直接 ready，不调重扫。"""
    connection = build_scan_database()
    db = SQLiteDB(connection)
    host, model = FakeHost(), FakeModel(model_result(['merged']))
    with scan_patched(host, model):
        page_id = new_page(db)['id']
        advance(db, page_id, rescan='OFF')
        result = advance(db, page_id, rescan='OFF')
    assert result['page']['status'] == 'ready' and result['page']['rescan_used'] == 0
    assert host.calls['enhanced'] == 0 and len(model.prompts) == 1


def test_rescan_failure_keeps_first_result():
    """重扫失败：直接 ready，保留第一次整理的结果，不再调模型。"""
    connection = build_scan_database()
    db = SQLiteDB(connection)
    host, model = FakeHost(enhanced=[HOST_FAILED]), FakeModel(model_result(['merged']))
    with scan_patched(host, model):
        page_id = new_page(db)['id']
        advance(db, page_id)
        first_items = advance(db, page_id)['page']['items']
        result = advance(db, page_id)
        again = advance(db, page_id)
    page = result['page']
    assert page['status'] == 'ready' and page['items'] == first_items and page['error'] is None
    assert page['rescan_used'] == 1 and page['timings']['host_detail'] == 'Ollama 连不上'
    assert again['busy'] is False and again['page']['status'] == 'ready'
    assert host.calls == {'normal': 1, 'enhanced': 1} and len(model.prompts) == 1


def test_second_analysis_failure_keeps_first_result():
    """重扫后的第二次整理失败：直接 ready，保留第一次的结果，失败原因只记进 timings。"""
    connection = build_scan_database()
    db = SQLiteDB(connection)
    host = FakeHost()
    model = FakeModel(model_result(['merged']), HTTPException(502, '模型没有返回有效的结构化内容'))
    with scan_patched(host, model):
        page_id = new_page(db)['id']
        advance(db, page_id)
        first_items = advance(db, page_id)['page']['items']
        statuses = [advance(db, page_id)['page']['status'] for _ in range(2)]
        assert statuses == ['analyzing', 'ready'], statuses
        again = advance(db, page_id)
    page = again['page']
    assert again['busy'] is False and page['status'] == 'ready' and page['error'] is None
    assert page['items'] == first_items and page['timings']['analyze2_error'] == '模型没有返回有效的结构化内容'
    assert host.calls == {'normal': 1, 'enhanced': 1} and len(model.prompts) == 2


class InterruptingHost(FakeHost):
    """读图进行到一半时执行 interrupt（模拟页面被结束、或卡住后被别人重新认领）。"""

    def __init__(self, interrupt):
        super().__init__()
        self.interrupt = interrupt

    async def fetch_ocr(self, env, content, content_type, mode, timeout_seconds):
        """先执行打断动作，再正常返回读图结果。"""
        self.interrupt()
        return await super().fetch_ocr(env, content, content_type, mode, timeout_seconds)


def test_late_finisher_does_not_overwrite():
    """一步还没做完页面就被结束、或被别人重新认领：这一步的结果不写回。"""
    connection = build_scan_database()
    db = SQLiteDB(connection)
    with scan_patched():
        page_id = new_page(db)['id']

        def close_now():
            """读图途中结束这一页。"""
            run_sync_close(connection, page_id)

        with scan_patched(InterruptingHost(close_now)):
            advance(db, page_id)
        row = page_row(connection, page_id)
        assert row['status'] == 'closed' and row['ocr_text'] is None and row['timings'] == '{}'

        other_id = new_page(db)['id']

        def reclaim_now():
            """读图途中被另一个请求重新认领（开始时间换成新的）。"""
            connection.execute('UPDATE scan_page SET step_started_at=? WHERE id=?', (NOW + 5, other_id))
            connection.commit()

        with scan_patched(InterruptingHost(reclaim_now)):
            advance(db, other_id)
        row = page_row(connection, other_id)
        assert row['status'] == 'reading' and row['step_started_at'] == NOW + 5 and row['ocr_text'] is None


def run_sync_close(connection, page_id):
    """直接在库里把一页改成 closed（和结束接口写的一样）。"""
    connection.execute("UPDATE scan_page SET status='closed',step_started_at=NULL WHERE id=?", (page_id,))
    connection.commit()


def test_busy_host_retries_then_fails():
    """主机一直忙：等 3 次、共调 4 次后失败；忙两次后成功就继续。"""
    connection = build_scan_database()
    db = SQLiteDB(connection)
    host, sleeper = FakeHost(normal=[BUSY]), FakeSleep()
    with scan_patched(host, sleeper=sleeper):
        page_id = new_page(db)['id']
        page = advance(db, page_id)['page']
    assert sleeper.waits == [scan_model.BUSY_WAIT_SECONDS] * 3 and host.calls['normal'] == 4
    assert page['status'] == 'failed' and page['error'] == '读图没成功'
    host, sleeper = FakeHost(normal=[BUSY, BUSY, ocr_ok(FIRST_TEXT)]), FakeSleep()
    with scan_patched(host, sleeper=sleeper):
        page_id = new_page(db)['id']
        page = advance(db, page_id)['page']
    assert page['status'] == 'analyzing' and host.calls['normal'] == 3 and len(sleeper.waits) == 2


def test_host_garbage_and_contract_mismatch():
    """主机返回乱码或版本不一致都算读图失败；主机的细节只记进 timings，不给用户看。"""
    connection = build_scan_database()
    db = SQLiteDB(connection)
    with scan_patched(FakeHost(normal=[(200, None)])):
        page = advance(db, new_page(db)['id'])['page']
    assert page['status'] == 'failed' and page['error'] == '读图没成功'
    mismatch = (200, {'ok': True, 'contract': 2, 'text': 'x', 'detail': '主机版本 2'})
    with scan_patched(FakeHost(normal=[mismatch])):
        page = advance(db, new_page(db)['id'])['page']
    assert page['status'] == 'failed' and page['error'] == '识别服务版本不一致'
    assert page['timings']['host_detail'] == '主机版本 2' and '主机版本' not in page['error']
    with scan_patched(FakeHost(normal=[HOST_FAILED])):
        page = advance(db, new_page(db)['id'])['page']
    assert page['error'] == '读图没成功' and page['timings']['host_detail'] == 'Ollama 连不上'


def test_model_failure_retry_does_not_reread():
    """模型失败：页面失败并显示模型的报错，读图文字保留；再试只重新整理，不再读图。"""
    connection = build_scan_database()
    db = SQLiteDB(connection)
    host = FakeHost()
    model = FakeModel(HTTPException(502, '模型没有返回有效的结构化内容'), model_result())
    with scan_patched(host, model):
        page_id = new_page(db)['id']
        advance(db, page_id)
        failed = advance(db, page_id)['page']
        assert failed['status'] == 'failed' and failed['error'] == '模型没有返回有效的结构化内容'
        assert page_row(connection, page_id)['ocr_text'] == FIRST_TEXT
        page = advance(db, page_id)['page']
    assert page['status'] == 'ready' and page['error'] is None and len(page['items']) == 3
    assert host.calls['normal'] == 1 and len(model.prompts) == 2


def test_read_failure_retry_rereads():
    """读图失败后再推，会重新读图。"""
    connection = build_scan_database()
    db = SQLiteDB(connection)
    host = FakeHost(normal=[HOST_FAILED, ocr_ok(FIRST_TEXT)])
    with scan_patched(host):
        page_id = new_page(db)['id']
        assert advance(db, page_id)['page']['status'] == 'failed'
        page = advance(db, page_id)['page']
    assert page['status'] == 'analyzing' and page['error'] is None and host.calls['normal'] == 2


def test_missing_image_fails_cleanly():
    """R2 里照片不见了：失败并提示"照片找不到了"，不调主机。"""
    connection = build_scan_database()
    db = SQLiteDB(connection)
    host = FakeHost(image=None)
    with scan_patched(host):
        page = advance(db, new_page(db)['id'])['page']
    assert page['status'] == 'failed' and page['error'] == '照片找不到了' and host.calls['normal'] == 0


def test_concurrent_advance_only_one_runs():
    """同一页同一时刻只跑一个推进：正在做的返回 busy；卡住超过 150 秒可以重做；并发只有一个认领成功。"""
    connection = build_scan_database()
    db = SQLiteDB(connection)
    host = FakeHost()
    with scan_patched(host):
        page_id = new_page(db)['id']
        connection.execute("UPDATE scan_page SET status='reading',step_started_at=? WHERE id=?", (NOW - 10, page_id))
        connection.commit()
        result = advance(db, page_id)
        assert result['busy'] is True and result['page']['status'] == 'reading' and host.calls['normal'] == 0
        connection.execute('UPDATE scan_page SET step_started_at=? WHERE id=?', (NOW - 151, page_id))
        connection.commit()
        result = advance(db, page_id)
        assert result['busy'] is False and result['page']['status'] == 'analyzing' and host.calls['normal'] == 1
    # 两个推进真正并发：两边都先读到 uploaded，只有一个条件更新能认领成功
    yielding = YieldingDB(connection)
    host = FakeHost(yield_once=True)
    with scan_patched(host):
        page_id = new_page(yielding)['id']

        async def both():
            """同时推进同一页两次。"""
            return await asyncio.gather(scan.advance_page(page_id, PageRequest(yielding)),
                                        scan.advance_page(page_id, PageRequest(yielding)))

        results = run(both())
    assert sorted(result['busy'] for result in results) == [False, True]
    assert host.calls['normal'] == 1 and page_row(connection, page_id)['status'] == 'analyzing'


def test_unfinished_and_close():
    """没整理完的页：当前学生、不含已结束 / 失败 / 已删除，最多最近 5 条；结束后推进什么都不做。"""
    connection = build_scan_database()
    db = SQLiteDB(connection)
    host, model = FakeHost(), FakeModel()
    with scan_patched(host, model):
        ids = [new_page(db)['id'] for _ in range(9)]
        closed = run(scan.close_page(ids[8], PageRequest(db)))
        assert closed['status'] == 'closed'
        connection.execute("UPDATE scan_page SET status='failed' WHERE id=?", (ids[7],))
        connection.execute('UPDATE scan_page SET deleted=1 WHERE id=?', (ids[6],))
        # 别的学生的页不出现
        connection.execute('INSERT INTO scan_page(student_id,subject_id,image) VALUES(2,1,?)', (GOOD_IMAGE,))
        connection.commit()
        unfinished = run(scan.list_unfinished(PageRequest(db)))
        assert [page['id'] for page in unfinished['items']] == list(reversed(ids[1:6]))
        result = advance(db, ids[8])
    assert result['busy'] is False and result['page']['status'] == 'closed'
    assert host.calls == {'normal': 0, 'enhanced': 0} and model.prompts == []


def test_unknown_page_is_404():
    """不存在或已软删除的页，查、推进、结束都是 404。"""
    connection = build_scan_database()
    db = SQLiteDB(connection)
    with scan_patched():
        deleted_id = new_page(db)['id']
        connection.execute('UPDATE scan_page SET deleted=1 WHERE id=?', (deleted_id,))
        connection.commit()
        for page_id in (999, deleted_id):
            expect_http(404, lambda: run(scan.get_page(page_id, PageRequest(db))))
            expect_http(404, lambda: advance(db, page_id))
            expect_http(404, lambda: run(scan.close_page(page_id, PageRequest(db))))
        assert page_row(connection, deleted_id)['status'] == 'uploaded'


# ---------------------------------------------------------------- 任务 4：逐题操作与录入

ITEM_IMAGE = '2026/11/a1b2c3d4_p.jpg'


def draft_item(seq, **overrides):
    """一道完整的"做错了"草稿项（模型来源），可用 overrides 改任意字段。"""
    item = scan_model.blank_item(seq)
    item.update(source='model', question_no=str(seq + 1), parsed_question='计算第 %d 题' % (seq + 1),
                wrong_answer='孩子写 %d' % seq, reason='算错了', answer='答案 %d' % seq, analysis='解析 %d' % seq,
                knowledge_point_ids=[101], primary_knowledge_point_id=101, error_types=['计算错误'], difficulty=2)
    item.update(overrides)
    return item


def ready_page(connection, db, items, status='ready'):
    """建一页（数学、6 年级上、图片 ITEM_IMAGE），直接把状态和草稿写进库，返回页编号。"""
    page_id = new_page(db, image=ITEM_IMAGE)['id']
    connection.execute('UPDATE scan_page SET status=?,items=? WHERE id=?',
                       (status, json.dumps(items, ensure_ascii=False), page_id))
    connection.commit()
    return page_id


async def noop_math(request, texts):
    """公式校验替身：什么都不做。"""


async def yielding_math(request, texts):
    """公式校验替身：让出一次，让两个并发录入真正交错。"""
    await asyncio.sleep(0)


async def failing_math(request, texts):
    """公式校验替身：一律判公式写坏。"""
    raise HTTPException(422, '公式写坏了')


@contextlib.contextmanager
def items_patched(model=None, math=noop_math):
    """在 scan_patched 之外再替换 pdf.validate_math（错题保存逻辑里调用），结束后一定还原。"""
    original = pdf.validate_math
    pdf.validate_math = math
    try:
        with scan_patched(model=model):
            yield
    finally:
        pdf.validate_math = original


def item_call(function, page_id, seq, db, payload=None):
    """调用一个逐题接口（function(page_id, seq, request)）。"""
    return run(function(page_id, seq, PageRequest(db, payload)))


def live_questions(connection):
    """题库里未删除的错题数。"""
    return connection.execute('SELECT COUNT(*) FROM question WHERE deleted=0').fetchone()[0]


def max_question_id(connection):
    """题库里最大的错题编号（含已删除）。"""
    return connection.execute('SELECT COALESCE(MAX(id),0) FROM question').fetchone()[0]


def stored_items(connection, page_id):
    """直接从库里读一页的草稿。"""
    return json.loads(page_row(connection, page_id)['items'])


def test_accept_writes_approved_question_with_page_fields():
    """录入一道：错题是已通过、无卷子、带这页图片和判错依据，字段与草稿一致；草稿标为已录入。"""
    connection = build_scan_database()
    db = SQLiteDB(connection)
    with items_patched():
        page_id = ready_page(connection, db, [draft_item(0), draft_item(1)])
        page = item_call(scan.accept_item, page_id, 0, db)
    item = page['items'][0]
    assert item['state'] == 'accepted' and isinstance(item['question_id'], int)
    assert page['items'][1]['state'] == 'open'
    row = dict(connection.execute('SELECT * FROM question WHERE id=?', (item['question_id'],)).fetchone())
    assert row['deleted'] == 0 and row['review_status'] == 'approved' and row['paper_id'] is None
    assert row['student_id'] == 1 and row['original_image'] == ITEM_IMAGE
    assert json.loads(row['original_images']) == [ITEM_IMAGE]
    assert row['wrong_evidence'] == '页面识别，家长确认' and row['wrong_answer'] == '孩子写 0'
    assert row['question_no'] == '1' and row['error_type'] == '计算错误' and row['difficulty'] == 2
    assert row['subject_id'] == 1 and row['grade'] == 6 and row['semester'] == 1
    assert row['parsed_question'] == '计算第 1 题' and row['answer'] == '答案 0' and row['analysis'] == '解析 0'
    links = connection.execute('SELECT knowledge_point_id,is_primary FROM question_knowledge_point '
                               'WHERE question_id=? AND deleted=0', (item['question_id'],)).fetchall()
    assert [tuple(link) for link in links] == [(101, 1)]


def test_accept_twice_writes_once():
    """同一道连续录入两次：题库只多 1 道，两次的 question_id 相同。"""
    connection = build_scan_database()
    db = SQLiteDB(connection)
    before = live_questions(connection)
    with items_patched():
        page_id = ready_page(connection, db, [draft_item(0)])
        first = item_call(scan.accept_item, page_id, 0, db)
        second = item_call(scan.accept_item, page_id, 0, db)
    assert live_questions(connection) == before + 1
    assert first['items'][0]['question_id'] == second['items'][0]['question_id']


def test_accept_race_keeps_one_question():
    """两个录入同时跑：两边都写了错题，输掉条件更新的那道被软删除，只留 1 道，草稿指向它。"""
    connection = build_scan_database()
    db = SQLiteDB(connection)
    before, top = live_questions(connection), max_question_id(connection)
    with items_patched(math=yielding_math):
        page_id = ready_page(connection, db, [draft_item(0)])

        async def both():
            """同时录入同一道两次。"""
            return await asyncio.gather(scan.accept_item(page_id, 0, PageRequest(db)),
                                        scan.accept_item(page_id, 0, PageRequest(db)))

        results = run(both())
    assert live_questions(connection) == before + 1
    question_id = stored_items(connection, page_id)[0]['question_id']
    created = connection.execute('SELECT id,deleted FROM question WHERE id>? ORDER BY id', (top,)).fetchall()
    assert len(created) == 2 and sorted(row['deleted'] for row in created) == [0, 1]
    assert [row['id'] for row in created if row['deleted'] == 0] == [question_id]
    assert all(result['items'][0]['question_id'] == question_id for result in results)


def test_accept_rejected_by_save_keeps_item_open():
    """保存逻辑拒绝（公式写坏、选了考点没主考点）：抛 422，题库不变，草稿仍 open。"""
    connection = build_scan_database()
    db = SQLiteDB(connection)
    before = live_questions(connection)
    with items_patched(math=failing_math):
        page_id = ready_page(connection, db, [draft_item(0)])
        expect_http(422, lambda: item_call(scan.accept_item, page_id, 0, db))
    with items_patched():
        no_primary = draft_item(0, knowledge_point_ids=[101, 102], primary_knowledge_point_id=None)
        other_id = ready_page(connection, db, [no_primary])
        expect_http(422, lambda: item_call(scan.accept_item, other_id, 0, db))
    assert live_questions(connection) == before
    for check_id in (page_id, other_id):
        item = stored_items(connection, check_id)[0]
        assert item['state'] == 'open' and item['question_id'] is None


def test_accept_all_skips_warning_and_unsure():
    """全部录入只录"做错了、没提示（或有提示但改过）、未处理"的题，其余不动。"""
    connection = build_scan_database()
    db = SQLiteDB(connection)
    items = [
        draft_item(0),
        draft_item(1, flags=['broken_formula']),
        draft_item(2, flags=['merged'], edited=True),
        draft_item(3, verdict='unsure'),
        draft_item(4, verdict='right'),
        draft_item(5, state='dismissed'),
    ]
    with items_patched():
        page_id = ready_page(connection, db, items)
        result = run(scan.accept_all(page_id, PageRequest(db)))
    assert [(entry['seq'], entry['ok']) for entry in result['results']] == [(0, True), (2, True)]
    states = [item['state'] for item in result['page']['items']]
    assert states == ['accepted', 'open', 'accepted', 'open', 'open', 'dismissed']


def test_accept_all_partial_failure():
    """两道候选，第二道被保存逻辑拒绝：第一道成功入库，第二道带说明。"""
    connection = build_scan_database()
    db = SQLiteDB(connection)
    before = live_questions(connection)
    items = [draft_item(0), draft_item(1, knowledge_point_ids=[101, 102], primary_knowledge_point_id=None)]
    with items_patched():
        page_id = ready_page(connection, db, items)
        result = run(scan.accept_all(page_id, PageRequest(db)))
    first, second = result['results']
    assert first == {'seq': 0, 'ok': True, 'detail': None}
    assert second['seq'] == 1 and second['ok'] is False and second['detail']
    assert live_questions(connection) == before + 1
    assert [item['state'] for item in result['page']['items']] == ['accepted', 'open']


def test_withdraw_soft_deletes():
    """录入后撤回：错题软删除，草稿回到 open；再次录入得到新的一道；没录入的不能撤回。"""
    connection = build_scan_database()
    db = SQLiteDB(connection)
    with items_patched():
        page_id = ready_page(connection, db, [draft_item(0)])
        expect_http(409, lambda: item_call(scan.withdraw_item, page_id, 0, db))
        first_id = item_call(scan.accept_item, page_id, 0, db)['items'][0]['question_id']
        page = item_call(scan.withdraw_item, page_id, 0, db)
        assert page['items'][0]['state'] == 'open' and page['items'][0]['question_id'] is None
        assert connection.execute('SELECT deleted FROM question WHERE id=?', (first_id,)).fetchone()[0] == 1
        expect_http(409, lambda: item_call(scan.withdraw_item, page_id, 0, db))
        second_id = item_call(scan.accept_item, page_id, 0, db)['items'][0]['question_id']
    assert second_id != first_id
    assert connection.execute('SELECT deleted FROM question WHERE id=?', (second_id,)).fetchone()[0] == 0


def test_edit_dismiss_restore_manual():
    """保存修改、去掉、恢复、手工加一道；越界的序号 404。"""
    connection = build_scan_database()
    db = SQLiteDB(connection)
    with items_patched():
        page_id = ready_page(connection, db, [draft_item(0), draft_item(1)])
        page = item_call(scan.edit_item, page_id, 0, db,
                         {'answer': '新答案', 'knowledge_point_ids': [101, 102], 'primary_knowledge_point_id': 102})
        item = page['items'][0]
        assert item['edited'] is True and item['answer'] == '新答案' and item['primary_knowledge_point_id'] == 102
        assert item['knowledge_point_ids'] == [101, 102] and item['parsed_question'] == '计算第 1 题'
        assert page['items'][1]['edited'] is False
        expect_http(422, lambda: item_call(scan.edit_item, page_id, 0, db, {'difficulty': 9}))
        # 只改考点、去掉了原来的主考点：合并后主考点不在考点里 → 422
        expect_http(422, lambda: item_call(scan.edit_item, page_id, 0, db, {'knowledge_point_ids': [101]}))
        assert stored_items(connection, page_id)[0]['knowledge_point_ids'] == [101, 102]
        expect_http(404, lambda: item_call(scan.edit_item, page_id, 5, db, {'answer': 'x'}))
        expect_http(404, lambda: item_call(scan.dismiss_item, page_id, -1, db))
        item_call(scan.accept_item, page_id, 1, db)
        expect_http(409, lambda: item_call(scan.edit_item, page_id, 1, db, {'answer': 'x'}))
        page = item_call(scan.dismiss_item, page_id, 0, db)
        assert page['items'][0]['state'] == 'dismissed'
        expect_http(409, lambda: item_call(scan.accept_item, page_id, 0, db))
        expect_http(409, lambda: item_call(scan.dismiss_item, page_id, 0, db))
        page = item_call(scan.restore_item, page_id, 0, db)
        assert page['items'][0]['state'] == 'open'
        expect_http(409, lambda: item_call(scan.restore_item, page_id, 0, db))
        page = run(scan.add_item(page_id, PageRequest(db)))
    added = page['items'][-1]
    assert len(page['items']) == 3 and added['seq'] == 2 and added['source'] == 'manual'
    assert added['verdict'] == 'wrong' and added['state'] == 'open'


def test_promote_fills_from_model_and_survives_model_failure():
    """补成错题：模型补全字段并清洗；模型失败时移动保留、字段为空；做错的题不能补。"""
    connection = build_scan_database()
    db = SQLiteDB(connection)
    right = scan_model.blank_item(0)
    right.update(source='model', verdict='right', question_no='3', parsed_question='计算 1+1', wrong_answer='2',
                 reason='对')
    fill = {'answer': '2', 'analysis': '一加一', 'knowledge_point_ids': [101, 999], 'primary_knowledge_point_id': 999,
            'error_types': ['计算错误', '乱写'], 'difficulty': 1}
    model = FakeModel(fill)
    with items_patched(model=model):
        page_id = ready_page(connection, db, [right, draft_item(1)])
        result = item_call(scan.promote_item, page_id, 0, db)
        expect_http(409, lambda: item_call(scan.promote_item, page_id, 1, db))
        expect_http(409, lambda: item_call(scan.promote_item, page_id, 0, db))
    item = result['page']['items'][0]
    assert result['fill_error'] is None and len(model.prompts) == 1 and '计算 1+1' in model.prompts[0]
    assert item['verdict'] == 'wrong' and item['source'] == 'promoted' and item['reason'] == '家长补成错题'
    assert item['answer'] == '2' and item['analysis'] == '一加一' and item['difficulty'] == 1
    assert item['knowledge_point_ids'] == [101] and item['primary_knowledge_point_id'] == 101
    assert item['error_types'] == ['计算错误'] and item['state'] == 'open'
    failing = FakeModel(HTTPException(502, '文本模型余额不足'))
    with items_patched(model=failing):
        other_id = ready_page(connection, db, [dict(right)])
        result = item_call(scan.promote_item, other_id, 0, db)
    item = result['page']['items'][0]
    assert result['fill_error'] == '文本模型余额不足' and len(failing.prompts) == 1
    assert item['verdict'] == 'wrong' and item['source'] == 'promoted' and item['answer'] == ''
    assert item['knowledge_point_ids'] == []
    crashing = FakeModel(RuntimeError('timeout'))
    with items_patched(model=crashing):
        third_id = ready_page(connection, db, [dict(right)])
        result = item_call(scan.promote_item, third_id, 0, db)
    assert result['fill_error'] == scan.MODEL_FAILED_TEXT and result['page']['items'][0]['source'] == 'promoted'


def test_closed_page_rejects_item_operations():
    """页结束后（或还没 ready），所有逐题操作都是 409，题库和草稿不变。"""
    connection = build_scan_database()
    db = SQLiteDB(connection)
    before = live_questions(connection)
    right = draft_item(1, verdict='right')
    accepted = draft_item(2, state='accepted', question_id=1)
    for status in ('closed', 'analyzing'):
        with items_patched():
            page_id = ready_page(connection, db, [draft_item(0), right, accepted], status=status)
            items_before = page_row(connection, page_id)['items']
            expect_http(409, lambda: item_call(scan.edit_item, page_id, 0, db, {'answer': 'x'}))
            expect_http(409, lambda: item_call(scan.accept_item, page_id, 0, db))
            expect_http(409, lambda: item_call(scan.withdraw_item, page_id, 2, db))
            expect_http(409, lambda: item_call(scan.dismiss_item, page_id, 0, db))
            expect_http(409, lambda: item_call(scan.restore_item, page_id, 0, db))
            expect_http(409, lambda: item_call(scan.promote_item, page_id, 1, db))
            expect_http(409, lambda: run(scan.accept_all(page_id, PageRequest(db))))
            expect_http(409, lambda: run(scan.add_item(page_id, PageRequest(db))))
        assert page_row(connection, page_id)['items'] == items_before
    assert live_questions(connection) == before
    assert connection.execute('SELECT deleted FROM question WHERE id=1').fetchone()[0] == 0


def test_page_closed_during_accept_drops_question():
    """录入的保存逻辑跑到一半页被结束：刚写的错题软删除，接口返回 409，草稿不变。"""
    connection = build_scan_database()
    db = SQLiteDB(connection)
    before = live_questions(connection)
    holder = {}

    async def closing_math(request, texts):
        """公式校验时顺便把这一页结束掉。"""
        connection.execute("UPDATE scan_page SET status='closed' WHERE id=?", (holder['page_id'],))
        connection.commit()

    with items_patched(math=closing_math):
        holder['page_id'] = ready_page(connection, db, [draft_item(0)])
        expect_http(409, lambda: item_call(scan.accept_item, holder['page_id'], 0, db))
    assert live_questions(connection) == before
    assert stored_items(connection, holder['page_id'])[0]['state'] == 'open'


def test_close_leaves_open_items_out_of_library():
    """一道录入、一道没处理，结束这一页：题库只多 1 道。"""
    connection = build_scan_database()
    db = SQLiteDB(connection)
    before = live_questions(connection)
    with items_patched():
        page_id = ready_page(connection, db, [draft_item(0), draft_item(1)])
        item_call(scan.accept_item, page_id, 0, db)
        page = run(scan.close_page(page_id, PageRequest(db)))
    assert page['status'] == 'closed' and live_questions(connection) == before + 1
    assert [item['state'] for item in page['items']] == ['accepted', 'open']


TESTS = [
    test_interpret_health,
    test_health_endpoint_hides_host_details,
    test_clean_items_drops_bad_catalog_and_error_types,
    test_clean_items_primary_none_when_several_points_left,
    test_clean_items_right_items_drop_answer_fields,
    test_clean_items_bad_types_mark_unsure,
    test_clean_items_numeric_question_no,
    test_clean_items_garbage_and_limit,
    test_clean_fill,
    test_needs_rescan,
    test_interpret_ocr,
    test_next_step,
    test_accept_all_and_warning,
    test_clean_edit,
    test_question_payload,
    test_changes_library,
    test_build_page_prompt,
    test_build_fill_prompt,
    test_migration_0014_only_adds_scan_page,
    test_create_page_validates_image_and_subject,
    test_advance_happy_path_without_rescan,
    test_advance_with_rescan_runs_once,
    test_rescan_switch_off,
    test_rescan_failure_keeps_first_result,
    test_second_analysis_failure_keeps_first_result,
    test_late_finisher_does_not_overwrite,
    test_busy_host_retries_then_fails,
    test_host_garbage_and_contract_mismatch,
    test_model_failure_retry_does_not_reread,
    test_read_failure_retry_rereads,
    test_missing_image_fails_cleanly,
    test_concurrent_advance_only_one_runs,
    test_unfinished_and_close,
    test_unknown_page_is_404,
    test_accept_writes_approved_question_with_page_fields,
    test_accept_twice_writes_once,
    test_accept_race_keeps_one_question,
    test_accept_rejected_by_save_keeps_item_open,
    test_accept_all_skips_warning_and_unsure,
    test_accept_all_partial_failure,
    test_withdraw_soft_deletes,
    test_edit_dismiss_restore_manual,
    test_promote_fills_from_model_and_survives_model_failure,
    test_closed_page_rejects_item_operations,
    test_page_closed_during_accept_drops_question,
    test_close_leaves_open_items_out_of_library,
]


def check(name, function):
    """运行单个测试，打印 PASS/FAIL，返回是否通过。"""
    try:
        function()
    except Exception:
        print('FAIL', name)
        traceback.print_exc()
        return False
    print('PASS', name)
    return True


def main():
    """运行全部测试并打印总数；有失败时以非零状态退出。"""
    configure_output()
    results = [check(function.__name__, function) for function in TESTS]
    passed = sum(1 for ok in results if ok)
    print('%d/%d passed' % (passed, len(results)))
    if passed != len(results):
        sys.exit(1)


if __name__ == '__main__':
    main()
