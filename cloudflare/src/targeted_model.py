"""考点卷的纯函数：错题状态、入选原因、题面和选题（设计 4.1、5.2、5.3）。

这里不读数据库、不读时钟，同样的输入永远得到同样的输出，方便测试。
时间都用字符串（'2026-11-12' 或 '2026-11-12 10:00:00'），按字符串大小比较先后。
"""

import datetime

from mastery_model import GRADUATE_STREAK

SIZE_MIN = 1            # 题量下限
SIZE_MAX = 90           # 题量上限（和现有练习集一致）
SIZE_DEFAULT = 12       # 第一次出卷预填的题量
POINT_CAP = 3           # 每个考点最多出几道（不够凑满时才放开）
SPOT_DEFAULT = 1        # 默认抽查几道
NEW_DAYS = 7            # 从没出过考点卷时，最近几天的错题算"新错题"
OPEN_PAPER_DAYS = 30    # 没批改的卷子在多少天内占着题
NEED = {'weak': 3, 'fair': 2, 'good': 1}     # 考点状态对应的需要度，其余（掌握）为 0
REASON_ORDER = ('new', 'wrong', 'redo', 'consolidate', 'check')   # 考点内按原因挑题的先后
MODES = ('spread', 'focus')                  # 均布、集中
FIGURE_WORDS = ('如图', '图中', '下图', '右图', '上图', '图示')
RESERVE_LIMIT = 5       # 每个考点最多留几道备选


def question_state(results, entered, waive_at):
    """算一道错题的当前状态（设计 4.1）。

    results：这道题在练习卷里的结果 [{'at', 'order', 'correct'}]，不含"没做"和"题目有误"。
    entered：录入时间；waive_at：考点最近一次"直接设为掌握"的时间或 None。
    返回 {'state': 'todo' | 'consolidating' | 'graduated', 'streak', 'practised', 'last_at'}。
    """
    ordered = sorted(results, key=lambda row: (str(row['at'] or ''), row.get('order') or 0))
    # 录入早于"直接设为掌握"的题，在时间越过 waive_at 的那一刻视同已毕业（和 mastery_model 的回放一致）
    waive_pending = waive_at is not None and str(entered or '') < str(waive_at)
    streak, practised, last_at = 0, False, None
    for row in ordered:
        if waive_pending and str(row['at'] or '') > str(waive_at):
            streak, practised, waive_pending = max(streak, GRADUATE_STREAK), True, False
        practised = True
        streak = streak + 1 if row['correct'] else 0    # 做错一次，连对次数清零
        last_at = row['at']
    if waive_pending:
        # 所有结果都在调整之前（或没有结果）：调整发生在最后
        streak, practised = max(streak, GRADUATE_STREAK), True
    if streak >= GRADUATE_STREAK:
        state = 'graduated'
    elif not practised or streak == 0:
        state = 'todo'
    else:
        state = 'consolidating'
    return {'state': state, 'streak': streak, 'practised': practised, 'last_at': last_at}


def reason_of(state, wrong_at, last_paper_at, today, point):
    """一道题的入选原因（设计 5.2），不能出时返回 None。

    point 是主考点 {'status', 'all_graduated'}；today 是今天的日期字符串。
    """
    if state['state'] == 'graduated':
        if point['status'] == 'mastered':
            return 'spot'           # 已掌握的考点：抽查
        if point['all_graduated']:
            return 'check'          # 错题全部毕业但还没点亮：验收
        return None
    wrong_text = str(wrong_at or '')
    if not state['practised']:
        if last_paper_at:
            is_new = wrong_text > str(last_paper_at)
        else:
            # 从没出过考点卷：今天往前 NEW_DAYS 天（含）以来的错题算新
            day = datetime.date.fromisoformat(str(today)[:10]) - datetime.timedelta(days=NEW_DAYS)
            is_new = wrong_text >= day.isoformat()
        return 'new' if is_new else 'redo'
    if state['streak'] == 0:
        return 'wrong'
    return 'consolidate'


def form_of(state, reason):
    """出原题还是相似题：第一次重做用原题，之后、验收和抽查都用相似题。"""
    if reason in ('check', 'spot') or state['practised']:
        return 'similar'
    return 'original'


def has_figure(stem, review_reasons):
    """题目是否带图：题干里有"如图"等字样，或复核原因里有 figure_needed。"""
    text = stem or ''
    return any(word in text for word in FIGURE_WORDS) or 'figure_needed' in (review_reasons or '')


def make_item(entry):
    """把内部的候选记录变成输出的一行。"""
    return {'question_id': entry['id'], 'point_id': entry['point_id'],
            'reason': entry['reason'], 'form': entry['form']}


def sort_in_point(entries):
    """考点内的先后（第 3 步）：按原因先后；巩固里上次练习早的在前，其他原因里错题日期新的在前；最后按题号。

    每个考点的验收题只留第一道。
    """
    result = []
    for reason in REASON_ORDER:
        group = sorted((e for e in entries if e['reason'] == reason), key=lambda e: e['id'])
        if reason == 'consolidate':
            group.sort(key=lambda e: str(e['last_at'] or ''))
        else:
            group.sort(key=lambda e: str(e['wrong_at'] or ''), reverse=True)   # 稳定排序，同日期仍按题号
        if reason == 'check':
            group = group[:1]
        result.extend(group)
    return result


def order_points(groups, points):
    """考点的先后（第 4 步）：需要度高 → 掌握度低 → 待重做多 → 最近错题日期新 → 编号小。

    用几次稳定排序实现：先按次要的键排，再按主要的键排。
    """
    ids = sorted(groups)
    latest = {pid: max(str(e['wrong_at'] or '') for e in groups[pid]) for pid in ids}
    ids.sort(key=lambda pid: latest[pid], reverse=True)

    def main_key(pid):
        """需要度（越高越前，所以取负）、掌握度、待重做数（越多越前，取负）。"""
        info = points[pid]
        need = NEED.get(info['status'], 0) + (1 if any(e['reason'] == 'new' for e in groups[pid]) else 0)
        return (-need, info['value'] if info['value'] is not None else 0, -(info['pending'] or 0))

    ids.sort(key=main_key)
    return ids


def deal(order, groups, picked, want, mode, cap):
    """按分法发名额，往 picked 里追加，直到发满 want 道或没有可发的题。

    picked：{考点: 已发道数}；cap：每个考点最多发到第几道（None 表示不限）。
    返回这一次按顺序发出的候选记录。
    """
    dealt = []
    if mode == 'focus':
        # 集中：一个考点一个考点地发，每个发到上限
        for pid in order:
            limit = len(groups[pid]) if cap is None else min(cap, len(groups[pid]))
            while picked[pid] < limit and len(dealt) < want:
                dealt.append(groups[pid][picked[pid]])
                picked[pid] += 1
        return dealt
    # 均布：一轮一轮地发，每轮每个考点发一道
    rounds = max((len(groups[pid]) for pid in order), default=0)
    if cap is not None:
        rounds = min(rounds, cap)
    for round_index in range(rounds):
        for pid in order:
            if len(dealt) >= want:
                return dealt
            if picked[pid] == round_index and round_index < len(groups[pid]):
                dealt.append(groups[pid][round_index])
                picked[pid] += 1
    return dealt


def plan_paper(questions, points, last_paper_at, today, size, mode, spot_count):
    """选题（设计 5.3）。

    questions：[{'id', 'point_id'（主考点）, 'wrong_at', 'entered', 'results', 'blocked'}]
    points：{考点编号: {'value', 'status', 'pending', 'all_graduated', 'waive_at'}}
    返回 {'items': [{'question_id', 'point_id', 'reason', 'form'}],
          'reserve': {考点编号: 同样形状的备选，最多 5 条}, 'shortfall': 少出的道数}。
    """
    # 1. 算每道题的状态、原因和题面，去掉不能出的题
    entries = []
    for question in sorted(questions, key=lambda q: q['id']):
        point = points.get(question['point_id'])
        if question.get('blocked') or point is None or point['status'] == 'unlearned':
            continue
        state = question_state(question.get('results') or [], question.get('entered'), point.get('waive_at'))
        reason = reason_of(state, question.get('wrong_at'), last_paper_at, today, point)
        if reason is None:
            continue
        entries.append({'id': question['id'], 'point_id': question['point_id'], 'wrong_at': question.get('wrong_at'),
                        'last_at': state['last_at'], 'reason': reason, 'form': form_of(state, reason)})

    # 2. 抽查：最多占题量的一半；每个已掌握考点只留最久没练的一道，考点之间也按最久没练的先抽
    spot_quota = max(0, min(spot_count or 0, size // 2))
    best_spot = {}
    for entry in entries:
        if entry['reason'] != 'spot':
            continue
        key = (entry['last_at'] is not None, str(entry['last_at'] or ''), entry['id'])   # 没练过的排最前
        old = best_spot.get(entry['point_id'])
        if old is None or key < old[0]:
            best_spot[entry['point_id']] = (key, entry)
    spot_points = sorted(best_spot, key=lambda pid: (best_spot[pid][0][:2], pid))
    spots = [best_spot[pid][1] for pid in spot_points[:spot_quota]]

    # 3. 其余的题按主考点分组，考点内排好
    groups = {}
    for entry in entries:
        if entry['reason'] != 'spot':
            groups.setdefault(entry['point_id'], []).append(entry)
    groups = {pid: sort_in_point(group) for pid, group in groups.items()}

    # 4. 考点排先后
    order = order_points(groups, points)

    # 5. 发名额：先按每个考点 3 道的上限发，不够再放开上限
    want = max(0, size - len(spots))
    picked = {pid: 0 for pid in order}
    dealt = deal(order, groups, picked, want, mode, POINT_CAP)
    if len(dealt) < want:
        dealt += deal(order, groups, picked, want - len(dealt), mode, None)

    # 6. 少出的道数和备选（每个考点没选上的题，按考点内顺序前 5 条）
    chosen = dealt + spots
    reserve = {}
    for pid in order:
        rest = groups[pid][picked[pid]:][:RESERVE_LIMIT]
        if rest:
            reserve[pid] = [make_item(entry) for entry in rest]

    # 7. 先是发出的顺序，抽查题排在最后
    return {'items': [make_item(entry) for entry in chosen], 'reserve': reserve,
            'shortfall': size - len(chosen)}
