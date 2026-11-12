"""考点掌握度的计算规则（纯函数，不读数据库、不读时钟）。

基础规则见 docs/superpowers/specs/2026-11-11-knowledge-starmap-design.md 第 4 节（从 0.5 起，错扣、对加）；
"待重做的错题压上限""错题全部毕业才能变绿""一级模块看子考点"这几条见
docs/superpowers/specs/2026-11-12-weekly-paper-design.md 第 4.4、4.5 节。

事件统一写成字典：
    {'kind': 'wrong' | 'right' | 'adjust', 'at': 时间字符串, 'seq': 同一时刻内的次序, 'adjust': 调整类型或 None,
     'source': 'question' | 'practice' | 'adjust'（可选）,
     'qid': 错题编号（可选）, 'order': 卷面题号顺序（可选，缺省 0）,
     'gate': 这道题算不算数（可选，缺省假）, 'entered': 错题的录入时间（可选）}
seq：错题 0、练习结果 1、手动调整 2，保证同一时刻错题排在练习前面。
没有 qid 或 gate 为假的事件照常加减，但不参与"待重做""毕业"的统计。
"""

START = 0.5          # 学过但没有记录时的起点
STEP = 0.15          # 每次做错扣、做对加的幅度
FLOOR = 0.15         # 下限，和"没学"区分开
LEAF_N = 3           # 最底层考点：最近 3 次全对（且错题全部毕业）才是掌握
UPPER_MAX = 0.99     # 不满足掌握条件时的最高值（底层和上层都一样）
GRADUATE_STREAK = 2  # 一道错题在练习卷里连续做对 2 次就毕业
# 手动调整的幅度；set_mastered 直接设为 1
ADJUST = {'up_small': 0.15, 'up_large': 0.35, 'down_small': -0.15, 'set_mastered': None}
VOCAB_STAGES = (0.25, 0.5, 0.75, 1.0)


def clamp(value):
    """把加减后的掌握度限制在 [FLOOR, 0.99]：只有满足掌握条件或"直接设为掌握"才能到 1。"""
    return max(FLOOR, min(UPPER_MAX, value))


def sort_events(events):
    """按时间、同一时刻内的次序（错题在前、练习其次、调整最后）、卷面题号排序。"""
    return sorted(events, key=lambda event: (str(event['at'] or ''), event['seq'], event.get('order') or 0))


def answer_events(events):
    """只取对/错事件（手动调整不算做题结果），保持原顺序。"""
    return [event for event in events if event['kind'] in ('wrong', 'right')]


def is_pending(state):
    """一道错题是不是"待重做"：没在练习卷里做过，或最近一次做错（连对次数为 0）。"""
    return not state['practised'] or state['streak'] == 0


def value_cap(pending):
    """有 pending 道待重做的错题时，掌握度的上限：1 − 0.15 × 待重做数，最低 0.15。"""
    return max(FLOOR, 1 - STEP * pending)


def leaf_detail(events):
    """最底层考点的掌握度明细：按时间逐条回放事件（设计 4.4）。

    返回 {'value': 掌握度, 'pending': 待重做的错题数, 'all_graduated': 算数的错题是否全部毕业,
          'waive_at': 最近一次"直接设为掌握"的时间或 None}。
    """
    value = START
    tracked = {}        # 算数的错题：错题编号 -> {'practised': 做过没有, 'streak': 连对次数, 'entered': 录入时间}
    answers = []        # 到目前为止的对/错结果
    waive_at = None
    for event in sort_events(events):
        qid = event.get('qid')
        counts = bool(event.get('gate')) and qid is not None   # 这条事件的题算不算数
        if event['kind'] in ('wrong', 'right') and event.get('source') == 'question':
            # 错题事件：登记这道题，扣 0.15
            if counts and qid not in tracked:
                entered = str(event.get('entered') or '')
                state = {'practised': False, 'streak': 0, 'entered': entered}
                # 录入早于"直接设为掌握"的题（卷子日期排得靠后时也一样）视同已毕业
                if waive_at is not None and entered < str(waive_at):
                    state['practised'], state['streak'] = True, GRADUATE_STREAK
                tracked[qid] = state
            value = clamp(value - STEP)
            answers.append('wrong')
        elif event['kind'] in ('wrong', 'right'):
            # 练习结果：更新这道错题的连对次数，再加减 0.15
            right = event['kind'] == 'right'
            if counts and qid in tracked:
                state = tracked[qid]
                state['practised'] = True
                state['streak'] = state['streak'] + 1 if right else 0
            if not (right and value >= 1):          # 已经是 1 时做对，保持 1
                value = clamp(value + (STEP if right else -STEP))
            answers.append(event['kind'])
            # 此刻最近 3 次全对、并且算数的错题全部毕业，才跳到 1
            recent_all_right = len(answers) >= LEAF_N and all(kind == 'right' for kind in answers[-LEAF_N:])
            if right and recent_all_right and all(s['streak'] >= GRADUATE_STREAK for s in tracked.values()):
                value = 1.0
        elif ADJUST.get(event['adjust'], 0) is None:
            # 直接设为掌握：之前录入的错题从此视同已毕业
            value = 1.0
            waive_at = event['at']
            for state in tracked.values():
                if state['entered'] < str(waive_at):
                    state['practised'] = True
                    state['streak'] = max(state['streak'], GRADUATE_STREAK)
        else:
            value = clamp(value + ADJUST.get(event['adjust'], 0))
        # 每算一条都按此刻待重做的错题数压一次上限
        value = min(value, value_cap(sum(1 for state in tracked.values() if is_pending(state))))
    pending = sum(1 for state in tracked.values() if is_pending(state))
    all_graduated = all(state['streak'] >= GRADUATE_STREAK for state in tracked.values())
    return {'value': value, 'pending': pending, 'all_graduated': all_graduated, 'waive_at': waive_at}


def leaf_mastery(events):
    """最底层考点的掌握度（只要数值时用）。"""
    return leaf_detail(events)['value']


def upper_mastery(child_values, has_unlearned):
    """一级模块的掌握度：已学子考点的平均值，最高 0.99；
    已学子考点全部为 1、并且没有没学的子考点时为 1（设计 4.5）。"""
    if child_values and not has_unlearned and all(value >= 1 for value in child_values):
        return 1.0
    average = sum(child_values) / len(child_values) if child_values else START
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
