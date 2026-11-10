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
    entry_type_of,
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


TESTS = [
    test_tokens_and_type,
    test_validate_focus_spec,
    test_spec_active,
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
