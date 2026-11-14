"""批改识别预批（读一页、比对）的本地测试。

在 targeted_test 的测试库（starmap_test 的库 + 迁移 0015）上运行，识别主机和文本模型都换成假的。运行：

    python cloudflare/scripts/grading_scan_test.py
"""

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
sys.path.insert(0, str(ROOT / 'scripts'))

import starmap_test  # noqa: E402  复用建库、适配器、运行协程等助手
import targeted_test  # noqa: E402
from fastapi import HTTPException  # noqa: E402
from grading_model import build_judge_prompt, clean_judgement, numbering_changed, wrap_bare_math  # noqa: E402

PAGE_TEXT = '第 1 题 学生写：5x\n第 2 题 学生写：7'


# ---------------------------------------------------------------- 纯函数


def test_clean_judgement_rules():
    """多题号、少题号、题号不属于这份卷子、判定取值不对、页号超范围、重复题号、空答案。"""
    numbers = {1: 101, 2: 102, 3: 103, 4: 104}
    raw = {'answers': [
        {'no': 1, 'student_answer': '5x', 'verdict': 'right', 'page': 1},
        {'no': '2', 'student_answer': '7', 'verdict': 'wrong', 'page': 9},       # 页号不是这次读的页
        {'no': 2, 'student_answer': '8', 'verdict': 'right', 'page': 1},         # 重复题号，只认第一次
        {'no': 3, 'student_answer': '3', 'verdict': 'maybe', 'page': 2},         # 判定取值不对
        {'no': 99, 'student_answer': '1', 'verdict': 'right', 'page': 1},        # 不属于这份卷子
        {'no': True, 'student_answer': '1', 'verdict': 'right'},                 # 布尔值不算题号
        'not a dict',
    ]}
    result = clean_judgement(raw, numbers, {1, 2})
    assert [item['number'] for item in result] == [1, 2, 3, 4]
    assert result[0] == {'id': 101, 'number': 1, 'student_answer': '5x', 'verdict': 'right', 'page': 1}
    assert result[1] == {'id': 102, 'number': 2, 'student_answer': '7', 'verdict': 'wrong', 'page': None}
    assert result[2]['verdict'] == 'unsure' and result[2]['page'] == 2
    assert result[3] == {'id': 104, 'number': 4, 'student_answer': '', 'verdict': 'unsure', 'page': None}


def test_clean_judgement_empty_answer_is_unsure():
    """读不到孩子答案却判了对错的，一律改成拿不准；模型返回的不是对象时全部拿不准。"""
    numbers = {1: 11, 2: 12}
    result = clean_judgement({'answers': [{'no': 1, 'student_answer': '', 'verdict': 'right', 'page': 1},
                                          {'no': 2, 'student_answer': None, 'verdict': 'wrong'}]}, numbers, {1})
    assert [item['verdict'] for item in result] == ['unsure', 'unsure']
    assert [item['verdict'] for item in clean_judgement(['x'], numbers, {1})] == ['unsure', 'unsure']
    assert clean_judgement({'answers': [{'no': 1, 'student_answer': 0.5, 'verdict': 'right'}]},
                           numbers, set())[0]['student_answer'] == '0.5'


def test_numbering_changed():
    """手动组的卷子题数比创建时少就算错开；考点卷题号固定，不算。"""
    questions = [{'id': 1}, {'id': 2}]
    assert numbering_changed({'kind': 'manual', 'total_questions': 3, 'questions': questions}) is True
    assert numbering_changed({'kind': 'manual', 'total_questions': 2, 'questions': questions}) is False
    assert numbering_changed({'kind': 'manual', 'total_questions': None, 'questions': questions}) is False
    assert numbering_changed({'kind': 'targeted', 'total_questions': 3, 'questions': questions}) is False


def test_judge_prompt_content():
    """提示词带每页文字、每道题的题号和标准答案，以及"只看最终答案"的规则。"""
    text = build_judge_prompt('数学', [(1, PAGE_TEXT), (3, '第三页')],
                              [{'number': 1, 'question_text': '计算 3x+2x', 'answer': '5x'},
                               {'number': 2, 'question_text': '计算 3+4', 'answer': '7'}])
    assert PAGE_TEXT in text and '第 3 页' in text and '第三页' in text
    assert '1. 题目：计算 3x+2x\n   标准答案：5x' in text and '2. 题目：计算 3+4\n   标准答案：7' in text
    assert '只看最终答案' in text and 'unsure' in text and '学科：数学' in text
    assert '\\(3^{2025}\\)' in text   # 要求孩子答案里的式子带公式边界


def test_wrap_bare_math():
    """没边界的 LaTeX 补上 \\(...\\)；已有边界、普通文字、填空横线不动；夹中文的只包式子那几段。"""
    assert wrap_bare_math('3^{2025}') == '\\(3^{2025}\\)'
    assert wrap_bare_math('(1) y+\\frac{1}{20}y') == '\\((1) y+\\frac{1}{20}y\\)'
    assert wrap_bare_math('\\(3^{2025}\\)') == '\\(3^{2025}\\)'
    assert wrap_bare_math('16') == '16' and wrap_bare_math('5x') == '5x' and wrap_bare_math('') == ''
    assert wrap_bare_math('___') == '___' and wrap_bare_math('B') == 'B'
    assert wrap_bare_math('原价 \\frac{5}{4}c 元') == '原价 \\(\\frac{5}{4}c\\) 元'
    assert wrap_bare_math('x=-2，y^2=4') == '\\(x=-2\\)，\\(y^2=4\\)' or \
        wrap_bare_math('x=-2，y^2=4') == 'x=-2，\\(y^2=4\\)'
    # clean_judgement 返回给页面的答案也已补好
    raw = {'answers': [{'no': 1, 'student_answer': '3^{2025}', 'verdict': 'wrong', 'page': 1}]}
    assert clean_judgement(raw, {1: 101}, {1})[0]['student_answer'] == '\\(3^{2025}\\)'


# ---------------------------------------------------------------- 接口用的假主机、假模型


class FakeOcr:
    """假的识别主机：按顺序给出预设返回（最后一个一直重复），记录调用次数；照片键在 images 里才找得到。"""

    def __init__(self, replies=None, images=('a.jpg', 'b.jpg')):
        self.replies = list(replies or [(200, {'ok': True, 'contract': 1, 'text': PAGE_TEXT, 'elapsed_ms': 5})])
        self.images = set(images)
        self.ocr_calls = 0
        self.read_keys = []

    async def read_image(self, env, key):
        """照片键在 images 里时返回假字节，否则 None（照片找不到）。"""
        self.read_keys.append(key)
        return (b'img', 'image/jpeg') if key in self.images else None

    async def fetch_ocr(self, env, content, content_type, mode, timeout_seconds):
        """按顺序返回预设的 (状态码, JSON)。"""
        assert mode == 'normal'                       # 不做强化重扫
        self.ocr_calls += 1
        return self.replies.pop(0) if len(self.replies) > 1 else self.replies[0]


class FakeModel:
    """假的文本模型：返回预设结果或抛出预设异常，记录提示词。"""

    def __init__(self, result=None, error=None):
        self.result = result if result is not None else {'answers': [
            {'no': 1, 'student_answer': '5x', 'verdict': 'right', 'page': 1},
            {'no': 2, 'student_answer': '8', 'verdict': 'wrong', 'page': 1}]}
        self.error = error
        self.prompts = []

    async def __call__(self, request, prompt, max_tokens=None, temperature=None, parse=None):
        """记一次调用；有预设异常就抛出。"""
        self.prompts.append(prompt)
        if self.error is not None:
            raise self.error
        return self.result


def install(ocr=None, model=None):
    """把 grading_scan 的识别主机、模型、等待和数据库换成假的，返回 (模块, 主机, 模型, 还原函数)。"""
    import grading_scan
    ocr, model = ocr or FakeOcr(), model or FakeModel()
    names = {'ocr_client': ocr, 'generate_json': model, 'Database': lambda binding: binding}

    async def no_sleep(seconds):
        """不真等。"""
    names['sleep'] = no_sleep
    saved = {name: getattr(grading_scan, name) for name in names}
    for name, value in names.items():
        setattr(grading_scan, name, value)

    def restore():
        for name, value in saved.items():
            setattr(grading_scan, name, value)
    return grading_scan, ocr, model, restore


def fixture(kind='targeted', source_type='question', total=None):
    """数学错题 1、2（答案 5x、7）组成卷子 10，带两张照片。返回 (连接, db)。"""
    c = targeted_test.build_db()
    for qid, answer in ((1, '5x'), (2, '7')):
        starmap_test.add_question(c, qid, 1, '2026-09-0%d 08:00:00' % qid, [101])
        c.execute('UPDATE question SET answer=? WHERE id=?', (answer, qid))
    targeted_test.add_set(c, 10, '2026-11-01 08:00:00', None, [(1, None, 'original'), (2, None, 'original')],
                          kind=kind)
    c.execute('UPDATE practice_set SET review_images=?,source_type=?,total_questions=? WHERE id=10',
              ('["a.jpg", "b.jpg"]', source_type, total if total is not None else 2))
    c.commit()
    return c, starmap_test.adapter(c)


def call(function, db, payload, practice_set_id=10):
    """调一个接口函数，返回结果；抛 HTTPException 时返回 (状态码, 说明)。"""
    try:
        return starmap_test.run(function(practice_set_id, starmap_test.FakeRequest(payload, db)))
    except HTTPException as error:
        return error.status_code, error.detail


def with_install(function, ocr=None, model=None):
    """装上假的依赖运行 function(模块, 主机, 模型)，结束后一定还原。"""
    module, ocr, model, restore = install(ocr, model)
    try:
        return function(module, ocr, model)
    finally:
        restore()


# ---------------------------------------------------------------- 读一页


def test_page_returns_text_by_index():
    """按照片序号从库里取路径交给主机，返回识别文字；只调一次主机。"""
    c, db = fixture()

    def body(module, ocr, model):
        result = call(module.recognize_page, db, {'index': 1})
        assert result == {'index': 1, 'text': PAGE_TEXT}
        assert ocr.read_keys == ['b.jpg'] and ocr.ocr_calls == 1
    with_install(body)


def test_page_host_unavailable_is_503():
    """识别主机连不上、读不出来、一直忙：都是 503（不是 500），提示改为手动批改。"""
    c, db = fixture()
    for reply in [(0, None), (200, {'ok': False, 'contract': 1, 'detail': 'boom'}),
                  (503, {'ok': False, 'contract': 1, 'code': 'busy'})]:
        def body(module, ocr, model):
            status, detail = call(module.recognize_page, db, {'index': 0})
            assert status == 503 and '手动批改' in detail
        with_install(body, ocr=FakeOcr([reply]))


def test_page_busy_then_ok():
    """主机先忙后好：重试后拿到文字。"""
    c, db = fixture()
    ocr = FakeOcr([(503, {'ok': False, 'contract': 1, 'code': 'busy'}),
                   (200, {'ok': True, 'contract': 1, 'text': PAGE_TEXT})])

    def body(module, ocr, model):
        assert call(module.recognize_page, db, {'index': 0})['text'] == PAGE_TEXT
        assert ocr.ocr_calls == 2
    with_install(body, ocr=ocr)


def test_page_validations():
    """序号越界或不是整数 422；照片找不到 404；单词、阅读练习 422；不存在 404。"""
    c, db = fixture()

    def body(module, ocr, model):
        for index in (2, -1, '0', 1.0, None):
            assert call(module.recognize_page, db, {'index': index})[0] == 422
        ocr.images = {'a.jpg'}
        assert call(module.recognize_page, db, {'index': 1})[0] == 404
        assert call(module.recognize_page, db, {'index': 0}, practice_set_id=99)[0] == 404
        assert ocr.ocr_calls == 0
    with_install(body)
    for source_type in ('word', 'reading'):
        c, db = fixture(source_type=source_type)

        def other(module, ocr, model):
            assert call(module.recognize_page, db, {'index': 0})[0] == 422 and ocr.ocr_calls == 0
        with_install(other)


# ---------------------------------------------------------------- 比对


def test_judge_calls_model_once_with_db_answers():
    """比对只调一次模型；题目和答案来自库，不来自请求；返回每题一项，按题号排。"""
    c, db = fixture()
    before = targeted_test.snapshot_tables(c)

    def body(module, ocr, model):
        payload = {'pages': [{'index': 1, 'text': PAGE_TEXT}],
                   'questions': [{'number': 1, 'answer': '伪造的答案'}]}       # 多传的字段被忽略
        result = call(module.recognize_judge, db, payload)
        assert len(model.prompts) == 1
        prompt = model.prompts[0]
        assert '伪造的答案' not in prompt and '标准答案：5x' in prompt and '标准答案：7' in prompt
        assert '第 2 页' in prompt                                          # 页号 = 照片序号 + 1
        ids = [row[0] for row in c.execute('SELECT id FROM practice_set_question WHERE practice_set_id=10 '
                                           'ORDER BY display_order')]
        assert result == {'items': [
            {'id': ids[0], 'number': 1, 'student_answer': '5x', 'verdict': 'right', 'page': None},
            {'id': ids[1], 'number': 2, 'student_answer': '8', 'verdict': 'wrong', 'page': None}]}
    with_install(body)
    assert targeted_test.snapshot_tables(c) == before                        # 不写库


def test_judge_validations():
    """页列表为空、序号越界或重复、文字为空或太长 422；单词练习 422；都不调模型。"""
    c, db = fixture()

    def body(module, ocr, model):
        bad = [{}, {'pages': []}, {'pages': [{'index': 2, 'text': 'x'}]},
               {'pages': [{'index': 0, 'text': 'x'}, {'index': 0, 'text': 'y'}]},
               {'pages': [{'index': 0, 'text': '  '}]}, {'pages': [{'index': 0, 'text': 'x' * 20001}]},
               {'pages': ['x']}, {'pages': [{'index': 0, 'text': 'x'}] * 3}]
        for payload in bad:
            assert call(module.recognize_judge, db, payload)[0] == 422, payload
        assert model.prompts == []
    with_install(body)
    c, db = fixture(source_type='word')

    def word(module, ocr, model):
        assert call(module.recognize_judge, db, {'pages': [{'index': 0, 'text': 'x'}]})[0] == 422
    with_install(word)


def test_judge_refuses_when_numbering_changed():
    """手动组的卷子打印后删过题（题数比创建时少）：409，不调模型。"""
    c, db = fixture(kind='manual', total=3)

    def body(module, ocr, model):
        status, detail = call(module.recognize_judge, db, {'pages': [{'index': 0, 'text': PAGE_TEXT}]})
        assert status == 409 and '题号' in detail and model.prompts == []
    with_install(body)


def test_judge_manual_numbers_follow_order():
    """手动组的卷子题号按题目顺序从 1 编号，和 PDF 上印的"第 N 题"一致。"""
    c, db = fixture(kind='manual')

    def body(module, ocr, model):
        result = call(module.recognize_judge, db, {'pages': [{'index': 0, 'text': PAGE_TEXT}]})
        assert [item['number'] for item in result['items']] == [1, 2]
        assert result['items'][0]['page'] == 1
    with_install(body)


def test_judge_model_error_is_502():
    """模型出错（含没配置模型）时 502，提示改为手动批改。"""
    c, db = fixture()
    for error in (RuntimeError('timeout'), HTTPException(503, '请先配置文本模型')):
        def body(module, ocr, model):
            status, detail = call(module.recognize_judge, db, {'pages': [{'index': 0, 'text': PAGE_TEXT}]})
            assert status == 502 and '手动批改' in detail
        with_install(body, model=FakeModel(error=error))


def test_detail_reports_shown_form():
    """练习详情给出每道题卷面上印的是原题还是相似题。"""
    import practices
    c, db = fixture()
    c.execute("INSERT INTO similar_question(id,source_question_id,similar_text,similar_answer,explanation,deleted,"
              "generated_at) VALUES(5,2,'相似题','9','解析',0,'2026-11-01')")
    c.execute("UPDATE practice_set_question SET form='similar',similar_question_id=5 WHERE question_id=2")
    c.commit()
    detail = starmap_test.run(practices.get(db, 10))
    assert [q['shown_form'] for q in detail['questions']] == ['original', 'similar']
    assert detail['questions'][1]['answer'] == '9'


TESTS = [
    test_clean_judgement_rules,
    test_clean_judgement_empty_answer_is_unsure,
    test_numbering_changed,
    test_judge_prompt_content,
    test_wrap_bare_math,
    test_page_returns_text_by_index,
    test_page_host_unavailable_is_503,
    test_page_busy_then_ok,
    test_page_validations,
    test_judge_calls_model_once_with_db_answers,
    test_judge_validations,
    test_judge_refuses_when_numbering_changed,
    test_judge_manual_numbers_follow_order,
    test_judge_model_error_is_502,
    test_detail_reports_shown_form,
]


def main():
    """运行全部测试并打印总数；有失败时以非零状态退出。"""
    starmap_test.configure_output()
    results = [starmap_test.check(function.__name__, function) for function in TESTS]
    passed = sum(results)
    print('%d 通过，%d 失败' % (passed, len(results) - passed))
    sys.exit(len(results) - passed)


if __name__ == '__main__':
    main()
