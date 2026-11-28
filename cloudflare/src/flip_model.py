"""翻一翻的纯函数：一道题的翻牌历史、到期判断和今天这一组怎么挑（设计 7.2）。

这里不读数据库、不读时钟，同样的输入永远得到同样的输出，方便测试。
日期都是北京日期字符串 'YYYY-MM-DD'；录入时间是 'YYYY-MM-DD HH:MM:SS'（可能带微秒，也可能只有日期）。

排序（前面的先出）：
  组 1：上次点了"我忘了"，且距上次翻已满 FORGOT_GAP_DAYS 天，上次翻的日期早的在前；
  组 2：从没翻过的，录入时间新的在前；
  组 3：上次点了"我记得"且到期的，到期日早的在前。
并列都按题目编号从小到大，所以同一天反复打开，剩下的卡片和顺序不变。
"""

from datetime import date, datetime

DAILY_LIMIT = 8               # 每天最多翻几张
FORGOT_GAP_DAYS = 2           # 点了"我忘了"之后隔几天再出现
REMEMBER_GAPS = (3, 7, 14)    # 连续记得 1 次隔 3 天、2 次隔 7 天、3 次及以上隔 14 天
RESULTS = ('remember', 'forget')

EPOCH = datetime(2000, 1, 1)  # 把录入时间换成秒数时的起点，只用来比较先后


def days_between(a, b) -> int:
    """日期 b 减日期 a 的天数；只看前 10 个字符（日期部分）。"""
    return (date.fromisoformat(str(b)[:10]) - date.fromisoformat(str(a)[:10])).days


def history_state(logs: list) -> dict:
    """一道题的翻牌记录 → {'last_result', 'last_date', 'remember_streak'}。

    logs 里每条是 {'result', 'flip_date', 'created_at'}，顺序不要求，这里按时间重新排；
    remember_streak 是末尾连续"我记得"的次数，中间点过一次"我忘了"就从那之后重新数。
    """
    ordered = sorted(logs, key=lambda row: (str(row['flip_date']), str(row.get('created_at') or '')))
    if not ordered:
        return {'last_result': None, 'last_date': None, 'remember_streak': 0}
    streak = 0
    for row in ordered:
        streak = streak + 1 if row['result'] == 'remember' else 0     # 忘了一次，连续记得清零
    last = ordered[-1]
    return {'last_result': last['result'], 'last_date': str(last['flip_date'])[:10], 'remember_streak': streak}


def remember_gap(streak: int) -> int:
    """连续记得 streak 次之后要隔几天（streak 至少为 1）。"""
    return REMEMBER_GAPS[min(streak, len(REMEMBER_GAPS)) - 1]


def entered_seconds(text) -> int:
    """录入时间换成从 2000-01-01 起的秒数；只有日期的算当天最后一秒，认不出来的算 0。"""
    value = str(text or '').replace('T', ' ')
    if len(value) == 10:
        value += ' 23:59:59'
    try:
        moment = datetime.strptime(value[:19], '%Y-%m-%d %H:%M:%S')
    except ValueError:
        return 0
    return int((moment - EPOCH).total_seconds())


def due_rank(state: dict, today: str):
    """一道题今天的排序键 (组号, 组内键, 题目编号)；今天不该出（今天翻过、还没到期）返回 None。

    state 是 history_state 的结果再加上这道题的 'id' 和 'entered'（录入时间）。
    """
    last_date = state['last_date']
    if last_date is None:
        # 组 2：从没翻过，录入时间新的在前（秒数取负，越新越小）
        return (2, -entered_seconds(state['entered']), state['id'])
    gap = days_between(last_date, today)
    if gap <= 0:
        return None          # 今天已经翻过
    if state['last_result'] == 'forget':
        if gap < FORGOT_GAP_DAYS:
            return None
        return (1, last_date, state['id'])          # 组 1：上次翻得早的在前
    wait = remember_gap(state['remember_streak'])
    if gap < wait:
        return None
    due = date.fromordinal(date.fromisoformat(last_date).toordinal() + wait).isoformat()
    return (3, due, state['id'])                    # 组 3：到期早的在前


def pick_today(candidates: list, logs_by_question: dict, today: str, subject_id=None,
               *, prioritize_pass_rate=False) -> dict:
    """挑今天这一组：{'done': 今天已翻张数, 'cards': [题目编号, ...]}。

    candidates：候选题 [{'id', 'entered'}]（已核对、没删除、没毕业、有题干或原图）；
    logs_by_question：{题目编号: [翻牌记录]}，可以包含已经不在候选里的题——它们今天翻过也算进 done；
    cards 的张数 = DAILY_LIMIT - done 和可出的题数取小，不小于 0。
    """
    completed = [row for logs in logs_by_question.values()
                 if (row := next((entry for entry in logs if str(entry['flip_date'])[:10] == today), None))]
    ranked = []
    for candidate in candidates:
        if subject_id is not None and candidate['subject_id'] != subject_id:
            continue
        state = {**history_state(logs_by_question.get(candidate['id'], [])),
                 'id': candidate['id'], 'entered': candidate['entered']}
        rank = due_rank(state, today)
        if rank is not None:
            if prioritize_pass_rate:
                pass_rate = candidate['pass_rate']
                # 有批改记录的题按通过率从低到高，同通过率仍按原复习顺序。
                rank = (pass_rate is None, pass_rate or 0, *rank)
            ranked.append(rank)
    ranked.sort()
    room = max(DAILY_LIMIT - len(completed), 0)
    done = sum(1 for row in completed if subject_id is None or row.get('subject_id') == subject_id)
    return {'done': done, 'cards': [rank[-1] for rank in ranked[:room]]}
