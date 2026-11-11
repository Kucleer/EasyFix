"""考点掌握度的计算规则（纯函数，不读数据库、不读时钟）。

规则见设计文档 docs/superpowers/specs/2026-11-11-knowledge-starmap-design.md 第 4 节：
掌握度只看最近的做题结果，不随时间变化；错题扣、练习卷做对加、可以手动调整。

事件统一写成字典：
    {'kind': 'wrong' | 'right' | 'adjust', 'at': 时间字符串, 'seq': 同一时刻内的次序, 'adjust': 调整类型或 None}
seq：错题 0、练习结果 1、手动调整 2，保证同一时刻错题排在练习前面。
"""

START = 0.5          # 学过但没有记录时的起点
STEP = 0.15          # 每次做错扣、做对加的幅度
FLOOR = 0.15         # 下限，和"没学"区分开
LEAF_N = 3           # 最底层考点：最近 3 次全对就是掌握
UPPER_FACTOR = 3     # 上层星：N = 3 × 覆盖的底层考点数
UPPER_CAP = 30       # 上层星的 N 最多 30
UPPER_RATIO = 0.9    # 上层星：最近 N 次里至少九成做对
UPPER_MAX = 0.99     # 上层星不满足掌握条件时的最高值
# 手动调整的幅度；set_mastered 直接设为 1
ADJUST = {'up_small': 0.15, 'up_large': 0.35, 'down_small': -0.15, 'set_mastered': None}
VOCAB_STAGES = (0.25, 0.5, 0.75, 1.0)


def clamp(value):
    """把掌握度限制在 [FLOOR, 1]。"""
    return max(FLOOR, min(1.0, value))


def sort_events(events):
    """按时间、再按同一时刻内的次序排序（错题在前、练习其次、调整最后）。"""
    return sorted(events, key=lambda event: (str(event['at'] or ''), event['seq']))


def answer_events(events):
    """只取对/错事件（手动调整不算做题结果），保持原顺序。"""
    return [event for event in events if event['kind'] in ('wrong', 'right')]


def leaf_mastery(events):
    """最底层考点的掌握度：从 0.5 起按时间逐条加减；最近 3 次全对则为 1。"""
    value = START
    answers = []        # 到目前为止的对/错结果
    for event in sort_events(events):
        if event['kind'] in ('wrong', 'right'):
            answers.append(event['kind'])
            value = clamp(value + (STEP if event['kind'] == 'right' else -STEP))
            # 一旦最近 3 次全对，当场到达掌握；之后再错从 1 往下扣
            if len(answers) >= LEAF_N and all(kind == 'right' for kind in answers[-LEAF_N:]):
                value = 1.0
        elif ADJUST.get(event['adjust'], 0) is None:
            value = 1.0          # 直接设为掌握
        else:
            value = clamp(value + ADJUST.get(event['adjust'], 0))
    return value


def upper_mastery(child_values, events, leaf_count, has_unlearned):
    """上层星的掌握度：子考点平均值；满足"至少 N 次、九成对、没有没学的子考点"时为 1，否则最高 0.99。"""
    average = sum(child_values) / len(child_values) if child_values else START
    window = min(UPPER_FACTOR * leaf_count, UPPER_CAP)
    answers = answer_events(sort_events(events))
    if window and len(answers) >= window and not has_unlearned:
        recent = answers[-window:]
        if sum(event['kind'] == 'right' for event in recent) / window >= UPPER_RATIO:
            return 1.0
    return min(average, UPPER_MAX)


def status_of(value):
    """掌握度对应的状态：没学 / 薄弱 / 一般 / 较好 / 掌握。"""
    if value is None:
        return 'unlearned'
    if value >= 1:
        return 'mastered'
    if value < 0.4:
        return 'weak'
    if value < 0.7:
        return 'fair'
    return 'good'


def recent_results(events, limit=3):
    """最近 limit 次做题结果（'right' / 'wrong'），从旧到新。"""
    return [event['kind'] for event in answer_events(sort_events(events))[-limit:]]


def vocab_progress(mastered, total):
    """词汇星团：已掌握比例，以及按 25%/50%/75%/100% 算出的阶段（0–4）。"""
    ratio = mastered / total if total else 0
    stage = sum(1 for threshold in VOCAB_STAGES if ratio >= threshold)
    return {'ratio': ratio, 'stage': stage}


def lighting(current, seen):
    """点亮时刻：返回 (要播放的考点, 更新后的已看集合)。

    seen 为 None 表示从未记录：不播放，已看集合直接设为当前已掌握的考点；
    否则播放"当前掌握但没看过"的，已看集合去掉已经掉出掌握的考点。
    """
    if seen is None:
        return set(), set(current)
    return set(current) - set(seen), set(seen) & set(current)
