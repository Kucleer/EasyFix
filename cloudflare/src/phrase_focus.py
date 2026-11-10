"""词组默写的纯函数规则模块。

只包含切词、标注校验、重点计算等纯函数，不依赖 fastapi、数据库或
Cloudflare 运行时，方便在本地直接测试。
"""

import json

# 标注中允许的角色：搭配词、实义词、普通词、占位符
ROLES = ('collocation', 'content', 'plain', 'placeholder')


def normalize_english(english):
    """去掉首尾空白，并把内部连续空白折叠为单个空格。"""
    return ' '.join(str(english or '').split())


def split_tokens(english):
    """把英文按空格切成 token 列表。"""
    normalized = normalize_english(english)
    if not normalized:
        return []
    return normalized.split(' ')


def entry_type_of(english):
    """token 数大于 1 为词组（phrase），否则为单词（word）。"""
    if len(split_tokens(english)) > 1:
        return 'phrase'
    return 'word'


def validate_focus_spec(spec, english):
    """校验并规范化重点标注，不合法时抛出带中文原因的 ValueError。"""
    if not isinstance(spec, dict):
        raise ValueError('标注必须是对象')
    tokens = spec.get('tokens')
    if not isinstance(tokens, list):
        raise ValueError('tokens 必须是列表')
    expected = split_tokens(english)
    if len(tokens) != len(expected):
        raise ValueError('tokens 数量与英文词数不一致')

    normalized_tokens = []
    for index, (item, expected_text) in enumerate(zip(tokens, expected)):
        if not isinstance(item, dict):
            raise ValueError('第 %d 个 token 必须是对象' % (index + 1))
        # 词必须与原英文逐个一致，不允许改写
        if item.get('text') != expected_text:
            raise ValueError('第 %d 个 token 与原英文不一致' % (index + 1))
        role = item.get('role')
        if role not in ROLES:
            raise ValueError('第 %d 个 token 的角色不合法' % (index + 1))
        if role == 'content':
            lemma = item.get('lemma')
            lemma = lemma.strip().lower() if isinstance(lemma, str) else ''
            if not lemma:
                raise ValueError('第 %d 个 token 是实义词，必须有 lemma' % (index + 1))
            gloss = item.get('gloss')
            if not isinstance(gloss, str):
                gloss = ''
            normalized_tokens.append(
                {'text': expected_text, 'role': role, 'lemma': lemma, 'gloss': gloss}
            )
        else:
            # 其他角色只保留 text 和 role
            normalized_tokens.append({'text': expected_text, 'role': role})

    return {
        'version': 1,
        'source_english': normalize_english(english),
        'tokens': normalized_tokens,
    }


def spec_active(row):
    """判断词条的标注是否生效：状态有效、JSON 可解析、且与当前英文一致。"""
    if row.get('focus_status') not in ('draft', 'confirmed'):
        return False
    raw_spec = row.get('focus_spec')
    if not isinstance(raw_spec, str):
        return False
    try:
        spec = json.loads(raw_spec)
    except ValueError:
        return False
    if not isinstance(spec, dict):
        return False
    return spec.get('source_english') == normalize_english(row.get('english'))
