"""整页识别录入的本地测试。

任务 3 起用生产结构基线 + 种子数据 + 迁移 0011、0012、0014 建库测试接口。运行：

    python cloudflare/scripts/scan_test.py
"""

import asyncio
import contextlib
import io
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
import auth  # noqa: E402
import cache  # noqa: E402
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
    """清洗：丢掉清单外的考点，难度越界改 3，只留认识的标记；错因已停用，模型给了也丢掉。"""
    raw = {'questions': [{'question_no': '3', 'parsed_question': '比 x 的立方少 3', 'wrong_answer': 'x^2+3',
           'verdict': 'wrong', 'reason': '应为 x^3-3', 'flags': ['broken_formula', 'nonsense'],
           'answer': 'x^3-3', 'analysis': '…', 'knowledge_point_ids': [101, 999, '101'],
           'primary_knowledge_point_id': 999, 'error_types': ['计算错误', '乱写'], 'difficulty': 9}]}
    [item] = scan_model.clean_items(raw, {101, 102})
    assert item['seq'] == 0 and item['state'] == 'open' and item['source'] == 'model' and item['edited'] is False
    assert item['knowledge_point_ids'] == [101]
    assert item['primary_knowledge_point_id'] == 101
    assert 'error_types' not in item and item['difficulty'] == 3
    assert item['flags'] == ['broken_formula']


def test_wrap_bare_math_and_clean_items_use_it():
    """模型没给公式加 \\( \\) 时，清洗把裸公式包好；已经加了边界的、普通文字和题号原样不动。"""
    assert scan_model.wrap_bare_math(r'\frac{61}{40}') == r'\(\frac{61}{40}\)'
    assert (scan_model.wrap_bare_math(r'学生最终答案 9\frac{7}{8}，正确答案 -\frac{359}{248}')
            == r'学生最终答案 \(9\frac{7}{8}\)，正确答案 \(-\frac{359}{248}\)')
    assert scan_model.wrap_bare_math(r'已有 \(\frac{1}{2}\) 和 \frac{3}{4}。') == r'已有 \(\frac{1}{2}\) 和 \(\frac{3}{4}\)。'
    assert scan_model.wrap_bare_math(r'当 \(x=2\) 时为 1') == r'当 \(x=2\) 时为 1'
    assert scan_model.wrap_bare_math('0.8a 元') == '0.8a 元'
    raw = {'questions': [{'question_no': '4', 'parsed_question': r'计算 \(\frac{1}{2}\)', 'verdict': 'wrong',
                          'wrong_answer': r'\frac{21}{40}', 'answer': r'\frac{61}{40}',
                          'reason': r'学生最终答案 \frac{21}{40}，正确答案 \frac{61}{40}', 'analysis': r'先算 \times'}]}
    [item] = scan_model.clean_items(raw, set())
    assert item['answer'] == r'\(\frac{61}{40}\)' and item['wrong_answer'] == r'\(\frac{21}{40}\)'
    assert item['reason'] == r'学生最终答案 \(\frac{21}{40}\)，正确答案 \(\frac{61}{40}\)'
    assert item['parsed_question'] == r'计算 \(\frac{1}{2}\)' and item['analysis'] == r'先算 \(\times\)'
    fill = scan_model.clean_fill({'answer': r'\frac{2x}{a} 支'}, set())
    assert fill['answer'] == r'\(\frac{2x}{a}\) 支'


def test_clean_items_accepts_string_and_float_point_ids():
    """模型把考点编号写成字符串或 101.0 时照样认；bool、非数字、清单外的编号仍然丢掉。"""
    raw = {'questions': [{'parsed_question': '题', 'verdict': 'wrong',
                          'knowledge_point_ids': ['102', 101.0, True, 'x', ' 103 ', 999],
                          'primary_knowledge_point_id': '102'}]}
    [item] = scan_model.clean_items(raw, {101, 102, 103})
    assert item['knowledge_point_ids'] == [102, 101, 103]
    assert item['primary_knowledge_point_id'] == 102


def test_clean_items_primary_none_when_several_points_left():
    """主考点无效且剩多个考点时为 None；有效时保留。"""
    raw = {'questions': [{'parsed_question': 'a', 'verdict': 'wrong', 'knowledge_point_ids': [101, 102],
                          'primary_knowledge_point_id': 5},
                         {'parsed_question': 'b', 'verdict': 'wrong', 'knowledge_point_ids': [101, 102],
                          'primary_knowledge_point_id': 102}]}
    first, second = scan_model.clean_items(raw, {101, 102})
    assert first['primary_knowledge_point_id'] is None and second['primary_knowledge_point_id'] == 102


def test_clean_items_right_items_drop_answer_fields():
    """做对的题清空答案、解析、考点；题干只留前 40 个字（模型给了完整题干也截短）。"""
    [item] = scan_model.clean_items({'questions': [{'parsed_question': 'a', 'verdict': 'right', 'answer': '1',
                                     'knowledge_point_ids': [101]}]}, {101})
    assert item['answer'] == '' and item['knowledge_point_ids'] == [] and item['verdict'] == 'right'
    long_stem = '一' * 30 + '二' * 30
    right, wrong = scan_model.clean_items({'questions': [
        {'parsed_question': long_stem, 'verdict': 'right'},
        {'parsed_question': long_stem, 'verdict': 'wrong'}]}, set())
    assert right['parsed_question'] == '一' * 30 + '二' * 10 and len(right['parsed_question']) == 40
    assert wrong['parsed_question'] == long_stem  # 做错的题保留完整题干


def test_clean_items_bad_types_mark_unsure():
    """字段类型不对或判断不认识的题标为拿不准；不是对象的项丢掉。"""
    items = scan_model.clean_items({'questions': [{'parsed_question': 5, 'verdict': 'wrong'}, 'junk',
                                                  {'parsed_question': 'b', 'verdict': 'maybe'}]}, set())
    assert [i['verdict'] for i in items] == ['unsure', 'unsure']
    assert [i['seq'] for i in items] == [0, 1]
    assert items[0]['parsed_question'] == '' and items[0]['reason']


def test_clean_items_numeric_question_no():
    """题号是数字（非 bool）时转成文字，不降级；bool 仍算类型错误。"""
    items = scan_model.clean_items({'questions': [
        {'question_no': 3, 'parsed_question': 'a', 'verdict': 'wrong'},
        {'question_no': 3.0, 'parsed_question': 'b', 'verdict': 'wrong'},
        {'question_no': 2.5, 'parsed_question': 'c', 'verdict': 'wrong'},
        {'question_no': True, 'parsed_question': 'd', 'verdict': 'wrong'}]}, set())
    assert [i['question_no'] for i in items] == ['3', '3', '2.5', '']
    assert [i['verdict'] for i in items] == ['wrong', 'wrong', 'wrong', 'unsure']


def test_clean_items_garbage_and_limit():
    """整体不是预期结构时返回空；题数不超过上限。"""
    assert scan_model.clean_items(None, set()) == []
    assert scan_model.clean_items({'questions': 'x'}, set()) == []
    many = {'questions': [{'parsed_question': str(n), 'verdict': 'wrong'} for n in range(200)]}
    assert len(scan_model.clean_items(many, set())) == scan_model.MAX_ITEMS


def test_parse_model_json_repairs_latex_backslashes():
    """模型把 LaTeX 反斜杠原样写进 JSON 时，\\( 不再让整页失败，\\frac、\\begin 不被读成换页、退格符。"""
    raw = '{"questions": [{"parsed_question": "计算 \\(\\frac{1}{2}\\times 3\\)，\\begin{vmatrix} a \\end{vmatrix}"}]}'
    stem = scan_model.parse_model_json(raw)['questions'][0]['parsed_question']
    assert stem == '计算 \\(\\frac{1}{2}\\times 3\\)，\\begin{vmatrix} a \\end{vmatrix}'
    # 写对了的（每个反斜杠两个）原样解析
    good = json.dumps({'a': '\\(x^2\\) \\neq 1'})
    assert scan_model.parse_model_json(good) == {'a': '\\(x^2\\) \\neq 1'}
    # 真正的换行、引号、\\u 转义保留；换行后接中文或大写字母不算 LaTeX
    assert scan_model.parse_model_json('{"a": "第一行\\n第二行 \\"引号\\" \\u4e2d \\nA."}') == {'a': '第一行\n第二行 "引号" 中 \nA.'}
    # 围栏和前后的说明文字去掉
    assert scan_model.parse_model_json('好的，结果如下：\n```json\n{"questions": []}\n```\n以上。') == {'questions': []}


def test_parse_model_json_failure_carries_hint_into_timings():
    """解析不出（比如回答被截断）时抛 ModelJsonError，整理这一步把出错位置附近的原文记进 timings。"""
    try:
        scan_model.parse_model_json('{"questions": [{"parsed_question": "被截断的题')
    except scan_model.ModelJsonError as error:
        assert '共' in error.hint and '被截断' in error.hint
    else:
        raise AssertionError('应该抛 ModelJsonError')

    async def analyze(ocr_text, enhanced_text):
        """模拟 generate_json：解析失败时抛 502，异常链里挂着 ModelJsonError。"""
        try:
            scan_model.parse_model_json('{"a": [1, 2')
        except ValueError as error:
            raise HTTPException(502, '模型没有返回有效的结构化内容') from error

    timings = {}
    fields = run(scan_model.step_analyze(analyze, '文字', None, [], 0, True, timings))
    assert fields['status'] == 'failed' and fields['error'] == '模型没有返回有效的结构化内容'
    assert '位置' in timings['model_parse_hint']


def test_clean_fill():
    """单题补全返回七个字段（含完整题干和学生的答案），规则同整页清洗；错因已停用，模型给了也丢掉。"""
    fill = scan_model.clean_fill({'parsed_question': '完整题干', 'wrong_answer': '3', 'answer': '1', 'analysis': 5,
                                  'knowledge_point_ids': [101, 7], 'primary_knowledge_point_id': 7,
                                  'error_types': ['计算错误', 'x'], 'difficulty': 0, 'extra': 'ignored'},
                                 {101})
    assert fill == {'parsed_question': '完整题干', 'wrong_answer': '3', 'answer': '1', 'analysis': '',
                    'knowledge_point_ids': [101], 'primary_knowledge_point_id': 101, 'difficulty': 3}
    empty = scan_model.clean_fill(None, {101})
    assert empty['knowledge_point_ids'] == [] and empty['parsed_question'] == '' and empty['wrong_answer'] == ''
    assert scan_model.clean_fill({'parsed_question': ['x'], 'difficulty': 5}, set())['parsed_question'] == ''


def test_merge_fill():
    """补全结果合进题目：空的题干、学生的答案沿用原来的，其余以补全为准。"""
    item = {**scan_model.blank_item(0), 'question_no': '3', 'parsed_question': '题干开头', 'wrong_answer': '2'}
    full = scan_model.merge_fill(item, {'parsed_question': '完整的题干', 'wrong_answer': '5', 'answer': '1'})
    assert full['parsed_question'] == '完整的题干' and full['wrong_answer'] == '5' and full['answer'] == '1'
    kept = scan_model.merge_fill(item, {'parsed_question': '  ', 'wrong_answer': '', 'answer': '1'})
    assert kept['parsed_question'] == '题干开头' and kept['wrong_answer'] == '2' and kept['question_no'] == '3'


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
    # 卡住判定是 180 秒：正好 180 秒仍算有人在做，超过才允许重做
    assert scan_model.STALE_SECONDS == 180
    assert scan_model.next_step(page(status='reading', step_started_at=now - 180), now) == 'working'
    assert scan_model.next_step(page(status='reading', step_started_at=now - 181), now) == 'read'
    assert scan_model.next_step(page(status='analyzing', ocr_text='t'), now) == 'analyze'
    assert scan_model.next_step(page(status='rescanning', ocr_text='t'), now) == 'rescan'
    assert scan_model.next_step(page(status='failed'), now) == 'read'
    assert scan_model.next_step(page(status='failed', ocr_text='t'), now) == 'analyze'
    assert scan_model.next_step(page(status='ready'), now) is None
    assert scan_model.next_step(page(status='closed'), now) is None


def test_clean_edit():
    """修改校验：合法的原样返回，非法的抛 ScanError，无关字段忽略。"""
    edit = scan_model.clean_edit({'question_no': '7', 'parsed_question': '计算', 'wrong_answer': '', 'answer': '1',
                                  'analysis': '', 'knowledge_point_ids': [101], 'primary_knowledge_point_id': 101,
                                  'error_types': ['计算错误'], 'difficulty': 2, 'state': 'accepted'})
    assert edit['difficulty'] == 2 and edit['knowledge_point_ids'] == [101] and 'state' not in edit
    # 错因已停用：旧页面传来的错因（格式对不对都一样）直接忽略
    assert 'error_types' not in edit
    assert scan_model.clean_edit({'error_types': '计算错误'}) == {}
    assert scan_model.clean_edit({'answer': 'x'}) == {'answer': 'x'}
    for bad in [{'difficulty': 6}, {'difficulty': True}, {'knowledge_point_ids': ['1']},
                {'knowledge_point_ids': [101], 'primary_knowledge_point_id': 102}, {'parsed_question': 3},
                None]:
        try:
            scan_model.clean_edit(bad)
        except scan_model.ScanError as error:
            assert error.detail and not any(c.isascii() and c.isalpha() for c in error.detail), error.detail
            continue
        raise AssertionError(bad)


def test_question_payload():
    """入库字段拼装：原图单元素列表；错因已停用，旧草稿里留着的错因也不写入。"""
    page = {'subject_id': 1, 'grade': 6, 'semester': 1, 'image': '2026/11/aaaaaaaa_p.jpg'}
    item = {**scan_model.blank_item(0), 'question_no': '3', 'parsed_question': '题', 'answer': '1', 'analysis': '析',
            'wrong_answer': '2', 'knowledge_point_ids': [101], 'primary_knowledge_point_id': 101,
            'error_types': ['计算错误', '概念错误'], 'difficulty': 4}
    assert scan_model.question_payload(page, item) == {
        'subject_id': 1, 'grade': 6, 'semester': 1, 'question_no': '3', 'parsed_question': '题', 'answer': '1',
        'analysis': '析', 'wrong_answer': '2', 'difficulty': 4,
        'knowledge_point_ids': [101], 'primary_knowledge_point_id': 101,
        'original_image': '2026/11/aaaaaaaa_p.jpg', 'original_images': ['2026/11/aaaaaaaa_p.jpg'],
        'wrong_evidence': '页面识别，家长确认'}


def test_changes_library():
    """只有录入一道、撤回两类路径会改动错题库（全部录入已没有单独的接口）。"""
    assert scan_model.changes_library('POST', '/api/scan/pages/3/items/2/accept') is True
    assert scan_model.changes_library('POST', '/api/scan/pages/3/items/2/withdraw') is True
    for path in ['/api/scan/pages', '/api/scan/pages/3/advance', '/api/scan/pages/3/items/2/dismiss',
                 '/api/scan/pages/3/items/2/restore', '/api/scan/pages/3/items/2/promote',
                 '/api/scan/pages/3/items', '/api/scan/pages/3/close', '/api/scan/pages/3/accept-all',
                 '/api/scan/pages/3/items/2/accept/extra']:
        assert scan_model.changes_library('POST', path) is False
    assert scan_model.changes_library('PUT', '/api/scan/pages/3/items/2') is False


def test_build_page_prompt():
    """整页提示词含考点编号、OCR 文字（重扫文字）和关键规则，不再让模型填错因。"""
    catalog = [{'id': 1, 'name': '代数', 'points': [{'id': 101, 'name': '一元二次方程'}]}]
    prompt = scan_model.build_page_prompt('数学', 6, 1, '第一遍文字ABC', None, catalog)
    assert '101' in prompt and '一元二次方程' in prompt and '第一遍文字ABC' in prompt
    assert 'error_types' not in prompt and '错因' not in prompt
    for rule in ['不许猜学生写了什么', '0.5 和 1/2 不算错', '没有作答', '按做错', 'questions']:
        assert rule in prompt, rule
    assert '分段重新读取' not in prompt
    # 做对的题只要题号、题干开头（不超过 40 个字）和判断，不要完整题干（设计 6.2、决定 16）
    assert '不超过 40 个字' in prompt and '题干开头' in prompt and '不要完整题干' in prompt
    right_rule = next(line for line in prompt.split('\n') if line.startswith('- verdict 为 right'))
    assert 'question_no' in right_rule and 'verdict' in right_rule
    both = scan_model.build_page_prompt('数学', 6, 1, '第一遍文字ABC', '重扫文字XYZ', catalog)
    assert '重扫文字XYZ' in both and '分段重新读取' in both and '对照着用' in both


def test_build_fill_prompt():
    """单题补全提示词含整页文字（有重扫文字时两份）、这道题的题号和题干开头，以及要返回的七个字段（不含错因）。"""
    item = {**scan_model.blank_item(2), 'question_no': '5', 'parsed_question': '题干QQQ', 'wrong_answer': ''}
    catalog = [{'id': 1, 'name': '代数', 'points': [{'id': 101, 'name': '方程'}]}]
    prompt = scan_model.build_fill_prompt('数学', 6, item, '整页文字PAGE', None, catalog)
    assert '整页文字PAGE' in prompt and '题号：5' in prompt and '题干QQQ' in prompt
    assert '101' in prompt and '分段重新读取' not in prompt
    assert 'error_types' not in prompt and '错因' not in prompt
    for field in ['parsed_question', 'wrong_answer', 'answer', 'analysis', 'knowledge_point_ids',
                  'primary_knowledge_point_id', 'difficulty']:
        assert field in prompt, field
    both = scan_model.build_fill_prompt('数学', 6, item, '整页文字PAGE', '重扫文字XYZ', catalog)
    assert '整页文字PAGE' in both and '重扫文字XYZ' in both


# ---------------------------------------------------------------- 识别顺序 run_page（后端和回归脚本共用）


def read_ok(text, elapsed_ms=3000):
    """一次成功的读图结果（interpret_ocr 格式）。"""
    return {'kind': 'ok', 'text': text, 'elapsed_ms': elapsed_ms, 'user_text': '', 'detail': ''}


def read_failed(detail='主机出错'):
    """一次失败的读图结果（interpret_ocr 格式）。"""
    return {'kind': 'failed', 'text': '', 'elapsed_ms': None, 'user_text': '读图没成功', 'detail': detail}


class SequenceFakes:
    """run_page 用的假读图和假整理：按顺序给出预设结果（异常就抛出），并记录调用。"""

    def __init__(self, normal=None, enhanced=None, analyses=()):
        self.reads = {'normal': normal or read_ok('第一遍'), 'enhanced': enhanced or read_ok('重扫', 8000)}
        self.analyses = list(analyses)
        self.calls = []

    async def read_text(self, mode):
        """记录一次读图并返回预设结果。"""
        self.calls.append(('read', mode))
        return self.reads[mode]

    async def analyze(self, ocr_text, enhanced_text):
        """记录一次整理（带两份文字）并返回或抛出预设结果。"""
        self.calls.append(('analyze', ocr_text, enhanced_text))
        reply = self.analyses.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply


FLAGGED = [{'seq': 0, 'verdict': 'wrong', 'flags': ['merged']}]
CLEAN = [{'seq': 0, 'verdict': 'wrong', 'flags': []}]


def test_run_page_without_rescan():
    """没有读图异常：读一次、整理一次就 ready。"""
    fakes = SequenceFakes(analyses=[CLEAN])
    result = run(scan_model.run_page(fakes.read_text, fakes.analyze, True))
    assert fakes.calls == [('read', 'normal'), ('analyze', '第一遍', None)]
    assert result['status'] == 'ready' and result['items'] == CLEAN and result['error'] is None
    assert result['ocr_text'] == '第一遍' and result['ocr_text_enhanced'] is None and result['rescan_used'] == 0
    assert result['timings']['host_read_ms'] == 3000 and 'read_ms' in result['timings']
    assert 'analyze_ms' in result['timings'] and 'rescan_ms' not in result['timings']


def test_run_page_with_rescan():
    """有读图异常：重扫一次，两份文字一起再整理；第二次仍有异常也不再重扫。开关关掉时不重扫。"""
    fakes = SequenceFakes(analyses=[FLAGGED, FLAGGED])
    result = run(scan_model.run_page(fakes.read_text, fakes.analyze, True))
    assert fakes.calls == [('read', 'normal'), ('analyze', '第一遍', None), ('read', 'enhanced'),
                           ('analyze', '第一遍', '重扫')]
    assert result['status'] == 'ready' and result['rescan_used'] == 1 and result['ocr_text_enhanced'] == '重扫'
    for key in ('read_ms', 'analyze_ms', 'rescan_ms', 'analyze2_ms', 'host_read_ms', 'host_rescan_ms'):
        assert key in result['timings'], key
    off = SequenceFakes(analyses=[FLAGGED])
    result = run(scan_model.run_page(off.read_text, off.analyze, False))
    assert off.calls == [('read', 'normal'), ('analyze', '第一遍', None)] and result['rescan_used'] == 0


def test_run_page_rescan_read_fails():
    """重扫读图失败：保留第一次的结果，直接 ready，主机细节记进 timings。"""
    fakes = SequenceFakes(enhanced=read_failed('切条失败'), analyses=[FLAGGED])
    result = run(scan_model.run_page(fakes.read_text, fakes.analyze, True))
    assert fakes.calls == [('read', 'normal'), ('analyze', '第一遍', None), ('read', 'enhanced')]
    assert result['status'] == 'ready' and result['items'] == FLAGGED and result['rescan_used'] == 1
    assert result['timings']['host_detail'] == '切条失败' and result['ocr_text_enhanced'] is None


def test_run_page_second_analysis_fails():
    """重扫后的第二次整理失败：保留第一次的结果，失败原因记进 timings。"""
    fakes = SequenceFakes(analyses=[FLAGGED, HTTPException(502, '模型没有返回有效的结构化内容')])
    result = run(scan_model.run_page(fakes.read_text, fakes.analyze, True))
    assert result['status'] == 'ready' and result['items'] == FLAGGED and result['error'] is None
    assert result['timings']['analyze2_error'] == '模型没有返回有效的结构化内容'
    assert result['ocr_text_enhanced'] == '重扫'


def test_run_page_first_read_fails():
    """第一次读图失败：页面 failed，不调模型，用户看"读图没成功"，主机细节记进 timings。"""
    fakes = SequenceFakes(normal=read_failed('Ollama 连不上'))
    result = run(scan_model.run_page(fakes.read_text, fakes.analyze, True))
    assert fakes.calls == [('read', 'normal')]
    assert result['status'] == 'failed' and result['error'] == '读图没成功' and result['items'] == []
    assert result['timings']['host_detail'] == 'Ollama 连不上' and result['ocr_text'] is None


def test_run_page_model_fails():
    """第一次整理失败：页面 failed，读图文字保留；带提示文字的用提示文字，运行时异常给统一提示并记类型名。"""
    fakes = SequenceFakes(analyses=[HTTPException(503, '请先配置文本模型')])
    result = run(scan_model.run_page(fakes.read_text, fakes.analyze, True))
    assert result['status'] == 'failed' and result['error'] == '请先配置文本模型' and result['ocr_text'] == '第一遍'
    assert 'model_error_type' not in result['timings'] and 'analyze_ms' in result['timings']
    crashing = SequenceFakes(analyses=[ConnectionError('reset')])
    result = run(scan_model.run_page(crashing.read_text, crashing.analyze, True))
    assert result['status'] == 'failed' and result['error'] == scan_model.MODEL_FAILED_TEXT
    assert result['timings']['model_error_type'] == 'ConnectionError'


def test_read_with_retries():
    """主机忙时等 2 秒重试，最多 3 次；仍忙按失败处理。"""
    busy = (503, {'ok': False, 'contract': 1, 'code': 'busy'})
    replies = [busy, busy, (200, {'ok': True, 'contract': 1, 'text': '文字', 'elapsed_ms': 5})]
    waits = []

    async def fake_sleep(seconds):
        """只记录等待时长。"""
        waits.append(seconds)

    async def fetch():
        """按顺序返回预设结果。"""
        return replies.pop(0) if len(replies) > 1 else replies[0]

    assert run(scan_model.read_with_retries(fetch, fake_sleep))['kind'] == 'ok' and waits == [2, 2]
    replies[:] = [busy]
    waits.clear()
    result = run(scan_model.read_with_retries(fetch, fake_sleep))
    assert result['kind'] == 'failed' and waits == [2, 2, 2]


# ---------------------------------------------------------------- 任务 3：建页与分步推进

NOW = 1_800_000_000          # 假的"当前时间"（整数秒）
GOOD_IMAGE = '2026/11/a1b2c3d4_page.jpg'
FIRST_TEXT = '1. 计算 3/4×2/3=  学生写 1/3\n2. 计算 1/2÷1/4=  学生写 1/8\n3. 计算 1+1=  学生写 2'
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
        self.options = []  # 每次调用传的 max_tokens、temperature

    async def __call__(self, request, prompt, max_tokens=6000, temperature=0.6, parse=None):
        """记录提示词和参数，并返回（或抛出）预设结果。"""
        reply = self.replies[min(len(self.prompts), len(self.replies) - 1)]
        self.prompts.append(prompt)
        self.options.append({'max_tokens': max_tokens, 'temperature': temperature})
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
    # 整理用低随机度、较大的返回长度（设计 6.2）
    assert model.options == [{'max_tokens': 8000, 'temperature': 0.2}]
    # 提示词里有读图文字和考点清单（错因已停用，不再给错因清单）
    assert FIRST_TEXT in model.prompts[0] and '101' in model.prompts[0] and '计算错误' not in model.prompts[0]
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
    assert 'model_error_type' not in failed['timings']  # 带提示文字的失败不记类型名


def test_model_runtime_error_records_type():
    """模型调用抛出运行时异常（如网络超时）：提示统一的模型失败文字，异常类型名记进 timings。"""
    connection = build_scan_database()
    db = SQLiteDB(connection)
    with scan_patched(FakeHost(), FakeModel(TimeoutError('slow'))):
        page_id = new_page(db)['id']
        advance(db, page_id)
        page = advance(db, page_id)['page']
    assert page['status'] == 'failed' and page['error'] == scan.MODEL_FAILED_TEXT
    assert page['timings']['model_error_type'] == 'TimeoutError' and 'slow' not in json.dumps(page['timings'])


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
    """同一页同一时刻只跑一个推进：正在做的返回 busy；卡住超过 180 秒可以重做；并发只有一个认领成功。"""
    connection = build_scan_database()
    db = SQLiteDB(connection)
    host = FakeHost()
    with scan_patched(host):
        page_id = new_page(db)['id']
        connection.execute("UPDATE scan_page SET status='reading',step_started_at=? WHERE id=?", (NOW - 10, page_id))
        connection.commit()
        result = advance(db, page_id)
        assert result['busy'] is True and result['page']['status'] == 'reading' and host.calls['normal'] == 0
        connection.execute('UPDATE scan_page SET step_started_at=? WHERE id=?', (NOW - 181, page_id))
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
                wrong_answer='学生写 %d' % seq, reason='算错了', answer='答案 %d' % seq, analysis='解析 %d' % seq,
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
    assert row['wrong_evidence'] == '页面识别，家长确认' and row['wrong_answer'] == '学生写 0'
    # 草稿里留着旧的错因也不写入（错因已停用）
    assert row['question_no'] == '1' and row['error_type'] is None and row['difficulty'] == 2
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


def test_accept_rejects_empty_question():
    """题干为空（或只有空白）的题不能录入：422"题干不能为空"，题库不变，草稿仍 open。"""
    connection = build_scan_database()
    db = SQLiteDB(connection)
    before, top = live_questions(connection), max_question_id(connection)
    with items_patched():
        page_id = ready_page(connection, db, [draft_item(0, parsed_question='  \t '), scan_model.blank_item(1)])
        for seq in (0, 1):
            try:
                item_call(scan.accept_item, page_id, seq, db)
            except HTTPException as error:
                assert error.status_code == 422 and error.detail == '题干不能为空'
            else:
                raise AssertionError('空题干应被拒绝')
    assert live_questions(connection) == before and max_question_id(connection) == top
    assert [item['state'] for item in stored_items(connection, page_id)] == ['open', 'open']


class CountingDB(SQLiteDB):
    """数每次请求用了几次数据库（all / first / run / batch 各算一次）；batch 前让出一次以便并发交错。"""

    def __init__(self, connection):
        super().__init__(connection)
        self.calls = 0

    async def all(self, sql, parameters=()):
        """计数后查询。"""
        self.calls += 1
        return await super().all(sql, parameters)

    async def first(self, sql, parameters=()):
        """计数并让出一次后查询。"""
        self.calls += 1
        await asyncio.sleep(0)
        return await super().first(sql, parameters)

    async def run(self, sql, parameters=()):
        """计数后写入。"""
        self.calls += 1
        return await super().run(sql, parameters)

    async def batch(self, statements):
        """计数并让出一次后批量写入。"""
        self.calls += 1
        await asyncio.sleep(0)
        return await super().batch(statements)


def test_concurrent_withdraw_acts_once():
    """两个撤回同时到：都不报错，错题只删一次，草稿回到 open。"""
    connection = build_scan_database()
    db = CountingDB(connection)
    with items_patched():
        page_id = ready_page(connection, db, [draft_item(0)])
        question_id = item_call(scan.accept_item, page_id, 0, db)['items'][0]['question_id']

        async def both():
            """同时撤回同一道两次。"""
            return await asyncio.gather(scan.withdraw_item(page_id, 0, PageRequest(db)),
                                        scan.withdraw_item(page_id, 0, PageRequest(db)))

        results = run(both())
    assert all(result['items'][0]['state'] == 'open' for result in results)
    assert connection.execute('SELECT deleted FROM question WHERE id=?', (question_id,)).fetchone()[0] == 1
    item = stored_items(connection, page_id)[0]
    assert item['state'] == 'open' and item['question_id'] is None


def test_withdraw_on_page_closed_midway_is_409():
    """撤回时页刚被结束：错题不删，草稿不变，返回 409。"""
    connection = build_scan_database()
    db = SQLiteDB(connection)
    with items_patched():
        page_id = ready_page(connection, db, [draft_item(0)])
        question_id = item_call(scan.accept_item, page_id, 0, db)['items'][0]['question_id']
    original_batch = db.batch

    async def closing_batch(statements):
        """批量写入前先把这一页结束掉。"""
        connection.execute("UPDATE scan_page SET status='closed' WHERE id=?", (page_id,))
        connection.commit()
        return await original_batch(statements)

    db.batch = closing_batch
    with items_patched():
        expect_http(409, lambda: item_call(scan.withdraw_item, page_id, 0, db))
    assert connection.execute('SELECT deleted FROM question WHERE id=?', (question_id,)).fetchone()[0] == 0
    assert stored_items(connection, page_id)[0]['state'] == 'accepted'


def test_stale_withdraw_keeps_new_question_linked():
    """撤回 W1 读到 Q1 后，W2 撤回 Q1、再录入得到 Q2；W1 的写入不能动 Q2，草稿仍指向 Q2。"""
    connection = build_scan_database()
    db = SQLiteDB(connection)
    plain = SQLiteDB(connection)
    with items_patched():
        page_id = ready_page(connection, db, [draft_item(0)])
        first_id = item_call(scan.accept_item, page_id, 0, db)['items'][0]['question_id']
    original_batch = db.batch
    holder = {}

    async def interleaved_batch(statements):
        """W1 写入前，先让 W2 完整撤回、再重新录入一次。"""
        await scan.withdraw_item(page_id, 0, PageRequest(plain))
        page = await scan.accept_item(page_id, 0, PageRequest(plain))
        holder['second_id'] = page['items'][0]['question_id']
        return await original_batch(statements)

    db.batch = interleaved_batch
    with items_patched():
        result = item_call(scan.withdraw_item, page_id, 0, db)
    second_id = holder['second_id']
    assert second_id != first_id
    deleted = dict(connection.execute('SELECT id,deleted FROM question WHERE id IN (?,?)',
                                      (first_id, second_id)).fetchall())
    assert deleted == {first_id: 1, second_id: 0}
    item = stored_items(connection, page_id)[0]
    assert item['state'] == 'accepted' and item['question_id'] == second_id
    assert result['items'][0]['question_id'] == second_id


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


class FloatBindingDB(SQLiteDB):
    """模拟 D1：整数参数一律按小数绑定（D1 把 JavaScript 数字当 REAL）。

    用它跑逐题操作，能抓住在 SQL 里用 '$[' || ? || ']' 拼 JSON 路径的写法——那样会拼出 $[4.0]，D1 上直接报错。
    """

    @staticmethod
    def bind(parameters):
        """bool 转 0/1，其余整数转小数。"""
        return tuple(int(value) if isinstance(value, bool) else float(value) if isinstance(value, int) else value
                     for value in parameters)


def test_item_operations_work_when_integers_bind_as_reals():
    """D1 把整数参数绑成小数时，修改、去掉、恢复、补成错题、录入、撤回都照常工作。"""
    connection = build_scan_database()
    db = FloatBindingDB(connection)
    before = live_questions(connection)
    right = scan_model.blank_item(2)
    right.update(source='model', verdict='right', question_no='3', parsed_question='计算 1+1')
    model = FakeModel({'parsed_question': '计算 1+1', 'answer': '2'})
    with items_patched(model=model):
        page_id = ready_page(connection, SQLiteDB(connection), [draft_item(0), draft_item(1), right])
        item_call(scan.edit_item, page_id, 0, db, {'answer': '新答案'})
        item_call(scan.dismiss_item, page_id, 1, db)
        item_call(scan.restore_item, page_id, 1, db)
        result = item_call(scan.promote_item, page_id, 2, db)
        assert result['fill_error'] is None and result['page']['items'][2]['answer'] == '2'
        page = item_call(scan.accept_item, page_id, 0, db)
        assert page['items'][0]['state'] == 'accepted' and page['items'][0]['answer'] == '新答案'
        page = item_call(scan.withdraw_item, page_id, 0, db)
        assert page['items'][0]['state'] == 'open' and page['items'][0]['question_id'] is None
    assert live_questions(connection) == before  # 录入后又撤回，题库不变


def test_promote_fills_from_model_and_survives_model_failure():
    """补成错题：模型拿整页文字补全完整题干、学生的答案等并清洗；模型失败时移动保留、字段为空；做错的题不能补。"""
    connection = build_scan_database()
    db = SQLiteDB(connection)
    right = scan_model.blank_item(0)
    # 模型判对的题只有题号、题干开头和判断
    right.update(source='model', verdict='right', question_no='3', parsed_question='计算 1+1')
    fill = {'parsed_question': '计算 1+1 的结果，并写出过程', 'wrong_answer': '3', 'answer': '2', 'analysis': '一加一',
            'knowledge_point_ids': [101, 999], 'primary_knowledge_point_id': 999,
            'error_types': ['计算错误', '乱写'], 'difficulty': 1}
    model = FakeModel(fill)
    with items_patched(model=model):
        page_id = ready_page(connection, db, [right, draft_item(1)])
        connection.execute('UPDATE scan_page SET ocr_text=?,ocr_text_enhanced=? WHERE id=?',
                           (FIRST_TEXT, ENHANCED_TEXT, page_id))
        connection.commit()
        # 没补成错题之前不能录入
        expect_http(409, lambda: item_call(scan.accept_item, page_id, 0, db))
        result = item_call(scan.promote_item, page_id, 0, db)
        expect_http(409, lambda: item_call(scan.promote_item, page_id, 1, db))
        expect_http(409, lambda: item_call(scan.promote_item, page_id, 0, db))
    item = result['page']['items'][0]
    assert result['fill_error'] is None and len(model.prompts) == 1
    # 提示词里有整页文字（两份）、题号和题干开头；用整页识别的模型参数
    prompt = model.prompts[0]
    assert FIRST_TEXT in prompt and ENHANCED_TEXT in prompt and '题号：3' in prompt and '计算 1+1' in prompt
    assert model.options == [{'max_tokens': 8000, 'temperature': 0.2}]
    assert item['parsed_question'] == '计算 1+1 的结果，并写出过程' and item['wrong_answer'] == '3'
    assert item['verdict'] == 'wrong' and item['source'] == 'promoted' and item['reason'] == '家长补成错题'
    assert item['answer'] == '2' and item['analysis'] == '一加一' and item['difficulty'] == 1
    assert item['knowledge_point_ids'] == [101] and item['primary_knowledge_point_id'] == 101
    assert 'error_types' not in item and item['state'] == 'open'
    failing = FakeModel(HTTPException(502, '文本模型余额不足'))
    with items_patched(model=failing):
        other_id = ready_page(connection, db, [dict(right)])
        result = item_call(scan.promote_item, other_id, 0, db)
    item = result['page']['items'][0]
    assert result['fill_error'] == '文本模型余额不足' and len(failing.prompts) == 1
    assert item['verdict'] == 'wrong' and item['source'] == 'promoted' and item['answer'] == ''
    assert item['knowledge_point_ids'] == [] and item['parsed_question'] == '计算 1+1'
    assert 'model_error_type' not in result['page']['timings']
    crashing = FakeModel(RuntimeError('timeout'))
    with items_patched(model=crashing):
        third_id = ready_page(connection, db, [dict(right)])
        result = item_call(scan.promote_item, third_id, 0, db)
    assert result['fill_error'] == scan.MODEL_FAILED_TEXT and result['page']['items'][0]['source'] == 'promoted'
    # 运行时异常只把类型名记进 timings，不记异常内容
    assert result['page']['timings'] == {'model_error_type': 'RuntimeError'}


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


class GuardRequest:
    """伪造经过 auth.guard 的请求：带 Agent 令牌，迁移已就绪。"""

    def __init__(self, method, path):
        self.method = method
        self.url = type('Url', (), {'path': path, '__str__': lambda self: 'http://test' + path})()
        self.headers = {'authorization': 'Bearer agent-token'}
        self.cookies = {}
        self.scope = {'env': type('Env', (), {'ACCESS_TOKEN': 'agent-token', 'SESSION_SECRET': 's',
                                              'MIGRATION_READY': 'true'})()}


def count_invalidations(method, path):
    """让 guard 处理一个成功的请求，返回 cache.invalidate 被调用了几次。"""
    from fastapi.responses import JSONResponse
    calls = []

    async def counting_invalidate(request):
        """只计数，不碰数据库。"""
        calls.append(request.url.path)

    async def not_in_maintenance(request):
        """维护开关关闭。"""
        return False

    async def call_next(request):
        """下游处理成功。"""
        return JSONResponse({'ok': True})

    # guard 在函数里才导入 invalidate，所以要换 cache 模块里的，不是 auth 里的
    original_invalidate, original_maintenance = cache.invalidate, auth.maintenance_enabled
    cache.invalidate, auth.maintenance_enabled = counting_invalidate, not_in_maintenance
    try:
        response = run(auth.guard(GuardRequest(method, path), call_next))
    finally:
        cache.invalidate, auth.maintenance_enabled = original_invalidate, original_maintenance
    assert response.status_code == 200, response.status_code
    return len(calls)


def test_guard_clears_cache_only_when_scan_changes_library():
    """整页识别的推进不清缓存，录入清一次；其他写请求照旧清。"""
    assert count_invalidations('POST', '/api/scan/pages/1/advance') == 0
    assert count_invalidations('PUT', '/api/scan/pages/1/items/0') == 0
    assert count_invalidations('POST', '/api/scan/pages/1/items/0/accept') == 1
    assert count_invalidations('POST', '/api/scan/pages/1/items/0/withdraw') == 1
    # 全部录入已经没有单独的接口（页面逐道调录入一道），旧路径也不清缓存
    assert count_invalidations('POST', '/api/scan/pages/1/accept-all') == 0
    assert count_invalidations('POST', '/api/questions') == 1


class FakeRegressionHost:
    """回归脚本用的假识别主机：按图片内容返回文字；内容是 BOOM 时抛异常（模拟一张坏图），记录调用。"""

    def __init__(self, healthy=True):
        self.healthy = healthy
        self.calls = []

    def health(self):
        """返回健康检查结果。"""
        return (200, {'ok': True, 'contract': 1}) if self.healthy else (0, None)

    def ocr(self, content, content_type, mode):
        """按图片内容返回读图结果。"""
        self.calls.append((content, content_type, mode))
        if content == b'BOOM':
            raise RuntimeError('图片坏了')
        text = '%s-%s' % (content.decode('ascii'), mode)
        return 200, {'ok': True, 'contract': 1, 'mode': mode, 'text': text, 'elapsed_ms': 7}


def fake_regression_model(prompt):
    """回归脚本用的假模型：带 FLAG 的页第一次整理打读图异常标记，重扫后不再打；还给一道做对的题。"""
    flagged = 'FLAG' in prompt and 'OCR_ENHANCED' not in prompt
    return {'questions': [
        {'question_no': '1', 'parsed_question': '计算 1+2', 'wrong_answer': '4', 'verdict': 'wrong',
         'reason': '应为 3', 'flags': ['merged'] if flagged else [], 'answer': '3', 'analysis': '相加',
         'knowledge_point_ids': [], 'error_types': ['计算错误'], 'difficulty': 2},
        {'question_no': '2', 'parsed_question': '计算 2+2', 'verdict': 'right'},
    ]}


def test_regression_script_runs_standalone_with_fakes():
    """回归脚本：注入假主机假模型（不联网）跑三张图，一张坏图不拖垮整批；结果文件齐全；不打印口令。"""
    import csv
    import tempfile
    import scan_regression

    with tempfile.TemporaryDirectory(prefix='easyfix_scan_test_') as temp_dir:
        temp = pathlib.Path(temp_dir)
        images, out = temp / 'images', temp / 'out'
        images.mkdir()
        (images / 'a.png').write_bytes(b'PLAIN')
        (images / 'b.jpg').write_bytes(b'FLAG')
        (images / 'c_bad.webp').write_bytes(b'BOOM')
        (images / 'notes.txt').write_text('不是图片', encoding='utf-8')
        key_file, config_file = temp / 'key.txt', temp / 'llm.json'
        key_file.write_text('﻿SECRET-KEY-123\n', encoding='utf-8')
        config_file.write_text(json.dumps({'provider': 'openai', 'api_key': 'SECRET-API-456',
                                           'base_url': 'https://example.invalid/v1', 'model': 'm'}),
                               encoding='utf-8')
        host = FakeRegressionHost()
        made = {}

        def make_host(url, key):
            """记录脚本传进来的地址和口令，返回假主机。"""
            made['host'] = (url, key)
            return host

        def make_model(config):
            """记录配置，返回假模型。"""
            made['model'] = config
            return fake_regression_model

        base = ['--images', str(images), '--ocr-key-file', str(key_file), '--llm-config', str(config_file)]
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = scan_regression.main(base + ['--out', str(out)], make_host, make_model)
        printed = output.getvalue()
        assert code == 0, (code, printed)
        assert made['host'] == ('http://127.0.0.1:11436', 'SECRET-KEY-123') and made['model']['model'] == 'm'
        assert 'SECRET-KEY-123' not in printed and 'SECRET-API-456' not in printed
        assert '中位数' in printed and '最大' in printed
        # 图片类型按扩展名给；带 FLAG 的那页重扫了一次
        assert (b'PLAIN', 'image/png', 'normal') in host.calls and (b'FLAG', 'image/jpeg', 'enhanced') in host.calls
        assert (b'PLAIN', 'image/png', 'enhanced') not in host.calls
        with open(out / 'summary.csv', encoding='utf-8-sig', newline='') as file:
            rows = list(csv.DictReader(file))
        assert [row['图名'] for row in rows] == ['a.png', 'b.jpg', 'c_bad.webp'], rows
        assert [row['状态'] for row in rows] == ['ready', 'ready', 'error'], rows
        assert [row['是否重扫'] for row in rows[:2]] == ['否', '是'] and 'RuntimeError' in rows[2]['备注']
        assert sorted(path.name for path in out.glob('*.json')) == ['a.png.json', 'b.jpg.json']
        saved = json.loads((out / 'b.jpg.json').read_text(encoding='utf-8'))
        assert saved['status'] == 'ready' and saved['rescan_used'] == 1 and saved['error'] is None
        assert saved['ocr_text'] == 'FLAG-normal' and saved['ocr_text_enhanced'] == 'FLAG-enhanced'
        assert {'read_ms', 'analyze_ms', 'rescan_ms', 'analyze2_ms'} <= set(saved['timings'])
        assert isinstance(saved['total_ms'], int) and len(saved['items']) == 2
        table = (out / '对照表.md').read_text(encoding='utf-8')
        for text in ('## a.png（ready）', '## b.jpg（ready，重扫过）', '## c_bad.webp（error）',
                     '### 模型判错（1 道）', '### 模型判对（1 道）', '第 2 题：计算 2+2'):
            assert text in table, text

        def expect_refusal(argv, words, make=make_host):
            """跑一次，要求返回 2 并打印包含 words 的中文说明。"""
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                code = scan_regression.main(argv, make, make_model)
            assert code == 2 and words in output.getvalue(), (code, output.getvalue())
            assert 'SECRET' not in output.getvalue()

        # 识别服务不可用：不跑，也不写结果
        out_down = temp / 'down'
        expect_refusal(base + ['--out', str(out_down)], '识别服务不可用',
                       make=lambda url, key: FakeRegressionHost(healthy=False))
        assert not out_down.exists()
        # 配置文件问题：中文提示，不抛堆栈
        expect_refusal(['--images', str(images), '--ocr-key-file', str(temp / 'nope.txt'),
                        '--llm-config', str(config_file), '--out', str(out)], '--ocr-key-file')
        (temp / 'bad.json').write_text('{"api_key": "SECRET-x"}', encoding='utf-8')
        expect_refusal(['--images', str(images), '--ocr-key-file', str(key_file),
                        '--llm-config', str(temp / 'bad.json'), '--out', str(out)], 'base_url')
        # 图片目录或结果目录在仓库里：拒绝运行
        expect_refusal(['--images', str(ROOT / 'scripts'), '--ocr-key-file', str(key_file),
                        '--llm-config', str(config_file), '--out', str(out)], '仓库')
        expect_refusal(base + ['--out', str(ROOT / 'scripts' / 'out')], '仓库')


def test_regression_catalog_and_model_request():
    """回归脚本的考点编号按文件位置、稳定；模型请求照线上格式并用整页识别的参数；回复解析同线上。"""
    import scan_regression

    points = json.loads(scan_regression.CATALOG_FILE.read_text(encoding='utf-8'))['points']
    catalog = scan_regression.load_catalog('数学', 6, 1)
    assert catalog and catalog == scan_regression.load_catalog('数学', 6, 1)
    for group in catalog:
        assert points[group['id'] - 1]['level'] == 1 and points[group['id'] - 1]['name'] == group['name']
        for point in group['points']:
            source = points[point['id'] - 1]
            assert source['level'] == 2 and source['subject'] == '数学' and source['name'] == point['name']
    url, headers, body, anthropic = scan_regression.build_model_request(
        {'api_key': 'k', 'base_url': 'https://x.example/v1/', 'model': 'm'}, '提示词')
    assert url == 'https://x.example/v1/chat/completions' and not anthropic
    assert headers['Authorization'] == 'Bearer k' and body['max_tokens'] == 8000 and body['temperature'] == 0.2
    assert body['messages'][0]['role'] == 'system' and body['messages'][1]['content'] == '提示词'
    url, headers, body, anthropic = scan_regression.build_model_request(
        {'provider': 'anthropic', 'api_key': 'k', 'base_url': 'https://x.example/anthropic', 'model': 'm'}, 'p')
    assert anthropic and url == 'https://x.example/anthropic/v1/messages' and headers['x-api-key'] == 'k'
    assert body['temperature'] == 0.2 and body['thinking'] == {'type': 'disabled'} and body['max_tokens'] == 8000
    fenced = json.dumps({'choices': [{'message': {'content': '```json\n{"questions": []}\n```'}}]})
    assert scan_regression.parse_model_reply(fenced, False) == {'questions': []}
    blocks = json.dumps({'content': [{'type': 'text', 'text': '{"a": 1}'}]})
    assert scan_regression.parse_model_reply(blocks, True) == {'a': 1}
    for bad in ('不是 JSON', json.dumps({'choices': []}), json.dumps({'choices': [{'message': {'content': '半截{'}}]})):
        try:
            scan_regression.parse_model_reply(bad, False)
        except scan_regression.ModelError as error:
            assert error.detail == '模型没有返回有效的结构化内容'
        else:
            raise AssertionError(bad)


def test_regression_script_imports_only_stdlib():
    """回归脚本在主机上只靠标准库和 httpx：导入时不加载 fastapi、本机测试服务，httpx 也只在建真实客户端时才导入。"""
    import subprocess
    code = ('import sys; sys.path.insert(0, %r); import scan_regression; '
            "print(sorted(name for name in ('fastapi', 'starlette', 'local_dev_server', 'httpx', 'scan', 'settings') "
            'if name in sys.modules))') % str(ROOT / 'scripts')
    result = subprocess.run([sys.executable, '-c', code], capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == '[]', result.stdout


TESTS = [
    test_interpret_health,
    test_parse_model_json_repairs_latex_backslashes,
    test_parse_model_json_failure_carries_hint_into_timings,
    test_item_operations_work_when_integers_bind_as_reals,
    test_health_endpoint_hides_host_details,
    test_clean_items_drops_bad_catalog_and_error_types,
    test_clean_items_accepts_string_and_float_point_ids,
    test_wrap_bare_math_and_clean_items_use_it,
    test_clean_items_primary_none_when_several_points_left,
    test_clean_items_right_items_drop_answer_fields,
    test_clean_items_bad_types_mark_unsure,
    test_clean_items_numeric_question_no,
    test_clean_items_garbage_and_limit,
    test_clean_fill,
    test_needs_rescan,
    test_interpret_ocr,
    test_next_step,
    test_clean_edit,
    test_question_payload,
    test_changes_library,
    test_build_page_prompt,
    test_build_fill_prompt,
    test_merge_fill,
    test_run_page_without_rescan,
    test_run_page_with_rescan,
    test_run_page_rescan_read_fails,
    test_run_page_second_analysis_fails,
    test_run_page_first_read_fails,
    test_run_page_model_fails,
    test_read_with_retries,
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
    test_model_runtime_error_records_type,
    test_read_failure_retry_rereads,
    test_missing_image_fails_cleanly,
    test_concurrent_advance_only_one_runs,
    test_unfinished_and_close,
    test_unknown_page_is_404,
    test_accept_writes_approved_question_with_page_fields,
    test_accept_twice_writes_once,
    test_accept_race_keeps_one_question,
    test_accept_rejected_by_save_keeps_item_open,
    test_accept_rejects_empty_question,
    test_withdraw_soft_deletes,
    test_edit_dismiss_restore_manual,
    test_promote_fills_from_model_and_survives_model_failure,
    test_closed_page_rejects_item_operations,
    test_page_closed_during_accept_drops_question,
    test_close_leaves_open_items_out_of_library,
    test_guard_clears_cache_only_when_scan_changes_library,
    test_concurrent_withdraw_acts_once,
    test_withdraw_on_page_closed_midway_is_409,
    test_stale_withdraw_keeps_new_question_linked,
    test_regression_script_runs_standalone_with_fakes,
    test_regression_catalog_and_model_request,
    test_regression_script_imports_only_stdlib,
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
