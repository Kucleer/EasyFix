"""词组默写优化的本地测试。

第一部分是纯函数测试（切词、标注校验、重点计算、格子、档位与阶段），
不依赖数据库。后续任务会在本脚本中追加数据库相关测试。运行：

    python cloudflare/scripts/phrase_focus_test.py
"""

import json
import pathlib
import sys
import traceback

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
sys.path.insert(0, str(ROOT / 'scripts'))

from phrase_focus import (  # noqa: E402
    build_cells,
    entry_type_of,
    focus_indices,
    next_level,
    next_phase,
    normalize_english,
    spec_active,
    split_tokens,
    validate_focus_spec,
)


def configure_output():
    """把标准输出改成 utf-8，避免 Windows GBK 控制台打印中文时报错。"""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding='utf-8', errors='replace')
        except (AttributeError, ValueError):
            pass


def expect_value_error(function):
    """调用函数，要求它必须抛出 ValueError。"""
    try:
        function()
    except ValueError:
        return
    raise AssertionError('期望抛出 ValueError，但没有抛出')


def make_spec(english, token_roles):
    """按 (角色, lemma) 列表构造并校验标注，返回规范化后的 spec。"""
    words = english.split()
    assert len(words) == len(token_roles), '测试夹具的词数与角色数不一致'
    tokens = []
    for text, item in zip(words, token_roles):
        role, lemma = item if isinstance(item, tuple) else (item, None)
        token = {'text': text, 'role': role}
        if lemma is not None:
            token['lemma'] = lemma
        tokens.append(token)
    return validate_focus_spec({'tokens': tokens}, english)


SPEC_GOOD_AT = make_spec('be good at', ['plain', 'plain', 'collocation'])
SPEC_PROUD_OF = make_spec('be proud of', ['plain', ('content', 'proud'), 'collocation'])
SPEC_LOOK_FORWARD = make_spec(
    'look forward to doing sth.',
    ['plain', 'collocation', 'collocation', 'placeholder', 'placeholder'],
)
SPEC_TAKE_PART_IN = make_spec('take part in', ['plain', 'plain', 'collocation'])
SPEC_HELP_WITH = make_spec(
    'help sb. with sth.', ['plain', 'placeholder', 'collocation', 'placeholder']
)
SPEC_A_LOT_OF = make_spec('a lot of', ['plain', 'plain', 'collocation'])
SPEC_ALL_CONTENT = make_spec(
    'make friends', [('content', 'make'), ('content', 'friend')]
)


# ---------------------------------------------------------------- 任务 1


def test_tokens_and_type():
    """切词与词条类型判断。"""
    assert normalize_english('  be   good\tat ') == 'be good at'
    assert split_tokens('help sb. with sth.') == ['help', 'sb.', 'with', 'sth.']
    assert entry_type_of('ice-cream') == 'word'
    assert entry_type_of('a.m.') == 'word'
    assert entry_type_of(' apple ') == 'word'
    assert entry_type_of('be good at') == 'phrase'


def test_validate_focus_spec():
    """标注校验：规范化通过，非法输入抛 ValueError。"""
    spec = {
        'tokens': [
            {'text': 'be', 'role': 'plain'},
            {'text': 'proud', 'role': 'content', 'lemma': 'Proud', 'gloss': '自豪的'},
            {'text': 'of', 'role': 'collocation'},
            {'text': 'sb.', 'role': 'placeholder'},
        ]
    }
    result = validate_focus_spec(spec, ' be  proud of sb. ')
    assert result['version'] == 1
    assert result['source_english'] == 'be proud of sb.'
    assert result['tokens'][1] == {
        'text': 'proud',
        'role': 'content',
        'lemma': 'proud',
        'gloss': '自豪的',
    }
    # 非 content 不保留 lemma/gloss
    assert set(result['tokens'][0]) == {'text', 'role'}
    bad_specs = (
        {'tokens': spec['tokens'][:3]},  # 少一个 token
        {'tokens': [{**spec['tokens'][0], 'text': 'is'}, *spec['tokens'][1:]]},  # 改写了词
        {'tokens': [{**spec['tokens'][0], 'role': 'verb'}, *spec['tokens'][1:]]},  # 非法角色
        {
            'tokens': [
                spec['tokens'][0],
                {'text': 'proud', 'role': 'content'},
                *spec['tokens'][2:],
            ]
        },  # content 无 lemma
        {'tokens': 'x'},
        None,
        [],
    )
    for bad in bad_specs:
        expect_value_error(lambda bad=bad: validate_focus_spec(bad, 'be proud of sb.'))


def test_spec_active():
    """标注是否生效：状态、可解析、与当前英文一致。"""
    spec = json.dumps(validate_focus_spec(SPEC_GOOD_AT, 'be good at'))
    assert spec_active({'english': 'be  good at', 'focus_status': 'draft', 'focus_spec': spec})
    assert spec_active({'english': 'be good at', 'focus_status': 'confirmed', 'focus_spec': spec})
    assert not spec_active({'english': 'be good at', 'focus_status': 'none', 'focus_spec': spec})
    assert not spec_active({'english': 'be good in', 'focus_status': 'confirmed', 'focus_spec': spec})
    assert not spec_active({'english': 'be good at', 'focus_status': 'draft', 'focus_spec': '{bad'})
    assert not spec_active({'english': 'be good at', 'focus_status': 'draft', 'focus_spec': None})


# ---------------------------------------------------------------- 任务 2


def cloze(spec, stored, requested=None, mastered=(), recent=()):
    """把格子渲染成设计文档第 7 节的显示形式，便于断言。"""
    focus = focus_indices(spec, set(mastered), list(recent))
    tokens, level = build_cells(spec, stored, requested, focus)
    parts = []
    for token in tokens:
        if token['blank']:
            # 空出的词：先显示提示（如有），其余字符用下划线
            hint = token['hint'] or ''
            parts.append(hint + '_' * (len(token['text']) - len(hint)))
        else:
            parts.append(token['text'])
    return ' '.join(parts), level


def test_spec_examples():
    """设计文档中的档位 1 示例。"""
    assert cloze(SPEC_GOOD_AT, 1) == ('be good __', 1)
    assert cloze(SPEC_PROUD_OF, 1) == ('be _____ __', 1)
    assert cloze(SPEC_PROUD_OF, 1, mastered={'proud'}) == ('be proud __', 1)
    assert cloze(SPEC_LOOK_FORWARD, 1) == ('look _______ __ doing sth.', 1)
    assert cloze(SPEC_TAKE_PART_IN, 1) == ('take part __', 1)
    assert cloze(SPEC_HELP_WITH, 1) == ('help sb. ____ sth.', 1)


def test_levels_two_and_three():
    """档位 2 给首字母提示，档位 3 全空（占位符除外）。"""
    assert cloze(SPEC_HELP_WITH, 2) == ('h___ sb. w___ sth.', 2)
    assert cloze(SPEC_HELP_WITH, 3) == ('____ sb. ____ sth.', 3)
    assert cloze(SPEC_HELP_WITH, 1, requested=3) == ('____ sb. ____ sth.', 3)  # 手动选档
    assert cloze(SPEC_A_LOT_OF, 2) == ('a l__ o_', 2)  # 单字母 token 在档位 2 不空


def test_empty_focus_falls_back_to_full():
    """无搭配词且实义词全已掌握时，本次按档位 3。"""
    assert cloze(SPEC_ALL_CONTENT, 1, mastered={'make', 'friend'}) == ('____ _______', 3)


def test_error_driven_focus():
    """最近错误次数达到阈值的词加入重点，占位符除外。"""
    wrong_good = [{'i': 1, 'ok': False}, {'i': 2, 'ok': True}]
    assert focus_indices(SPEC_GOOD_AT, set(), [wrong_good]) == [2]  # 错 1 次不够
    assert focus_indices(SPEC_GOOD_AT, set(), [wrong_good, wrong_good]) == [1, 2]
    wrong_sb = [{'i': 1, 'ok': False}]
    assert focus_indices(SPEC_HELP_WITH, set(), [wrong_sb, wrong_sb]) == [2]  # 占位符不会被加入


def test_next_level():
    """档位只在已标注的默写题中升降。"""
    assert next_level(1, True, 1, True) == 2
    assert next_level(3, True, 1, True) == 3
    assert next_level(2, False, 1, True) == 1
    assert next_level(1, False, 1, True) == 1
    assert next_level(2, True, 2, True) == 2  # 选择题不改档位
    assert next_level(2, True, 3, True) == 2  # 听力不改档位
    assert next_level(1, True, 1, False) == 1  # 未标注不改


def test_next_phase():
    """“牢记”阶段规则。"""
    args = dict(consecutive=3, interval=8, was_due=False)
    # 未标注或单词：与旧公式一致
    assert next_phase('在途', True, annotated=False, review_type=2, level=3, **args) == '牢记'
    assert next_phase('牢记', True, consecutive=1, interval=8, was_due=True, annotated=False, review_type=1, level=3) == '遗忘点'
    assert next_phase('牢记', False, annotated=False, review_type=1, level=3, **args) == '在途'
    # 已标注：只在档位 3 的默写授予
    assert next_phase('在途', True, annotated=True, review_type=1, level=3, **args) == '牢记'
    assert next_phase('在途', True, annotated=True, review_type=1, level=1, **args) == '在途'
    assert next_phase('在途', True, annotated=True, review_type=2, level=3, **args) == '在途'
    assert next_phase('在途', True, annotated=True, review_type=3, level=3, **args) == '在途'
    assert next_phase('在途', True, consecutive=3, interval=8, was_due=True, annotated=True, review_type=1, level=1) == '遗忘点'
    # 已标注且已是牢记：答对即保持
    assert next_phase('牢记', True, consecutive=1, interval=2, was_due=True, annotated=True, review_type=2, level=1) == '牢记'
    assert next_phase('牢记', False, annotated=True, review_type=1, level=3, **args) == '在途'


TESTS = [
    test_tokens_and_type,
    test_validate_focus_spec,
    test_spec_active,
    test_spec_examples,
    test_levels_two_and_three,
    test_empty_focus_falls_back_to_full,
    test_error_driven_focus,
    test_next_level,
    test_next_phase,
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
