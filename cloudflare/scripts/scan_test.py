"""整页识别录入的本地测试。

后续任务会在本脚本中追加解析、入库与接口测试。运行：

    python cloudflare/scripts/scan_test.py
"""

import asyncio
import pathlib
import sys
import traceback

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
sys.path.insert(0, str(ROOT / 'scripts'))

import scan  # noqa: E402
import scan_model  # noqa: E402


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
