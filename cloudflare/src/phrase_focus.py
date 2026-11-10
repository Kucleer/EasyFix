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


# 重点计算：只看最近 5 次默写，同一个词错 2 次及以上就加入重点
ERROR_WINDOW = 5
ERROR_THRESHOLD = 2


def has_letter(text):
    """判断 token 中是否含有字母（纯标点 token 永不空出）。"""
    return any(char.isalpha() for char in text)


def focus_indices(spec, mastered_lemmas, recent_token_results):
    """计算需要重点默写的 token 下标（升序）。

    并集 = 所有搭配词 + 未掌握的实义词 + 最近错误次数达到阈值的词（占位符除外）。
    """
    tokens = spec['tokens']
    focus = set()
    for index, token in enumerate(tokens):
        if token['role'] == 'collocation':
            focus.add(index)
        elif token['role'] == 'content' and token.get('lemma') not in mastered_lemmas:
            focus.add(index)

    # 统计每个下标在最近几次默写中答错的次数
    error_counts = {}
    for token_results in recent_token_results:
        for item in token_results:
            index = item.get('i')
            if not isinstance(index, int) or not 0 <= index < len(tokens):
                continue  # 下标越界的记录忽略
            if not item.get('ok'):
                error_counts[index] = error_counts.get(index, 0) + 1
    for index, count in error_counts.items():
        if count >= ERROR_THRESHOLD and tokens[index]['role'] != 'placeholder':
            focus.add(index)
    return sorted(focus)


def build_cells(spec, stored_level, requested_level, focus):
    """生成默写格子，返回 (tokens, 实际档位)。

    每个 token 形如 {'text', 'blank', 'hint'}。
    """
    level = requested_level or stored_level
    # 档位 1 只空重点词；重点为空时无从空起，本次按档位 3 全空
    if level == 1 and not focus:
        level = 3

    cells = []
    for index, token in enumerate(spec['tokens']):
        text = token['text']
        if level == 1:
            blank = index in focus
        else:
            blank = token['role'] != 'placeholder'
        if not has_letter(text):
            blank = False
        hint = None
        if blank and level == 2:
            letter_count = sum(1 for char in text if char.isalpha())
            if letter_count == 1:
                blank = False  # 单字母 token 在档位 2 不空
            else:
                hint = text[0]
        cells.append({'text': text, 'blank': blank, 'hint': hint})
    return cells, level


def next_level(stored_level, ok, review_type, annotated):
    """计算下一次的档位：仅已标注的默写题（review_type 1）答对升、答错降。"""
    if not (annotated and review_type == 1):
        return stored_level
    if ok:
        return min(stored_level + 1, 3)
    return max(stored_level - 1, 1)


def next_phase(old_phase, ok, consecutive, interval, was_due, annotated, review_type, level):
    """计算下一个阶段：在途 / 牢记 / 遗忘点。"""
    # 授予“牢记”：答对、连对 3 次、间隔 7 天以上；已标注的还必须是档位 3 的默写
    grant = ok and consecutive >= 3 and interval >= 7 and (
        not annotated or (review_type == 1 and level == 3)
    )
    # 已标注且已是牢记：答对即保持
    keep = annotated and ok and old_phase == '牢记'
    if grant or keep:
        return '牢记'
    if ok and was_due:
        return '遗忘点'
    return '在途'
