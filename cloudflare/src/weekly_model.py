"""周报"一周怎么算"的规则（纯函数，不读数据库、不读时钟）。

一期周报的窗口是 [上周日 20:00, 本周日 20:00)：按条数算的数字用这个窗口，
按天算的数字用周一到周日的自然日。时间字符串统一是 'YYYY-MM-DD HH:MM:SS'（19 位）。
所有函数只做计算，"现在几点"由调用方传进来。
"""

from datetime import datetime, timedelta

from targeted import normal_time
from targeted_model import question_state

REPORT_WEEKDAY = 6    # 周日（datetime.weekday() 里周一是 0）
REPORT_HOUR = 20      # 每周日 20:00 出一期
CALENDAR_DAYS = 42    # 日历热力图显示的天数
TREND_WEEKS = 6       # 趋势图显示的周数
STREAK_LOOKBACK = 26  # 计算连续录入周数时最多往前看的周数

STATUS_ORDER = ('unlearned', 'weak', 'fair', 'good', 'mastered')  # 掌握状态，从弱到强

CHEER_MAX = 30        # 鼓励语最多字数
SUMMARY_MAX = 120     # 总结最多字数
CAPTION_MAX = 40      # 每张图的说明最多字数
RECENT_CHEERS = 8     # 生成鼓励语时参考最近几期，避免重复
TEXT_MAX_ATTEMPTS = 3  # 每期最多调用几次模型写文字

BANNED_WORDS = ('爸爸', '妈妈', '父母', '家长', '爸妈')  # 文字是对学生说的，不能出现这些词

TIME_FORMAT = '%Y-%m-%d %H:%M:%S'
DATE_FORMAT = '%Y-%m-%d'


def week_end_before(moment):
    """返回不晚于 moment 的最近一个周日 20:00:00（正好 20:00:00 算这一期已经到了）。"""
    # 先取 moment 当天 20:00，再往前退到最近的周日
    candidate = moment.replace(hour=REPORT_HOUR, minute=0, second=0, microsecond=0)
    candidate = candidate - timedelta(days=(candidate.weekday() - REPORT_WEEKDAY) % 7)
    # 如果当天就是周日但还没到 20:00，就算上一周的
    if candidate > moment:
        candidate = candidate - timedelta(days=7)
    return candidate


def window(week_end):
    """返回这一期的窗口：start/end/prev_start 是 19 位时间，monday/sunday 是 YYYY-MM-DD。"""
    start = week_end - timedelta(days=7)
    return {
        'start': start.strftime(TIME_FORMAT),
        'end': week_end.strftime(TIME_FORMAT),
        'prev_start': (week_end - timedelta(days=14)).strftime(TIME_FORMAT),
        'monday': (week_end - timedelta(days=6)).strftime(DATE_FORMAT),
        'sunday': week_end.strftime(DATE_FORMAT),
    }


def week_starts(week_end, count):
    """往前共 count 个窗口的开始时刻，从早到晚，最后一个是本周的 start。"""
    result = []
    for back in range(count, 0, -1):  # back=1 是本周窗口，back 越大越早
        result.append((week_end - timedelta(days=7 * back)).strftime(TIME_FORMAT))
    return result


def entry_streak(counts):
    """counts 从本周往前排，返回开头连续大于 0 的个数。"""
    streak = 0
    for count in counts:
        if count <= 0:
            break
        streak += 1
    return streak


def calendar_days(sunday, entered, dictated):
    """生成 CALENDAR_DAYS 天的日历，从早到晚，最后一项是 sunday。

    entered、dictated 是"那天有录入/有默写"的日期集合（YYYY-MM-DD）。
    """
    end_day = datetime.strptime(sunday, DATE_FORMAT)
    days = []
    for back in range(CALENDAR_DAYS - 1, -1, -1):
        date = (end_day - timedelta(days=back)).strftime(DATE_FORMAT)
        days.append({'date': date, 'entered': date in entered, 'dictated': date in dictated})
    return days


def percent(correct, total):
    """正确率（百分数，1 位小数）；total 为 0 时返回 None。"""
    if not total:
        return None
    return round(correct * 100 / total, 1)


def known_at(event):
    """这条事件"系统知道的时间"：错题用录入时间，练习结果和手动调整用它们自己的时间。"""
    if event.get('source') == 'question':
        return str(event.get('entered') or event.get('at') or '')
    return str(event.get('at') or '')


def known_before(events, cutoff):
    """留下"知道的时间"早于 cutoff 的事件，顺序不变。"""
    return [event for event in events if known_at(event) < cutoff]


def week_activity(events, start, end):
    """本周（[start, end)）这个考点有没有做对的练习结果、有没有新错题或做错的练习结果。手动调整不算。"""
    activity = {'right': False, 'wrong': False}
    for event in events:
        if not (start <= known_at(event) < end):
            continue
        if event.get('source') == 'practice' and event.get('kind') == 'right':
            activity['right'] = True
        elif event.get('source') == 'question':
            activity['wrong'] = True    # 新录入的错题
        elif event.get('source') == 'practice' and event.get('kind') == 'wrong':
            activity['wrong'] = True    # 做错的练习结果
    return activity


def classify_change(before, after, activity):
    """一个考点两周的档位变化：'improved' / 'dropped' / 'new_weak' / None（设计 5.2）。"""
    before_level = STATUS_ORDER.index(before)
    after_level = STATUS_ORDER.index(after)
    if before == 'unlearned':
        # 上个时刻没学、这个时刻是薄弱：新出现，不算变差
        return 'new_weak' if after == 'weak' else None
    if after_level > before_level and activity['right']:
        return 'improved'     # 升档且本周有做对的练习结果
    if after_level < before_level and activity['wrong']:
        return 'dropped'      # 降档且本周有新错题或做错的练习结果
    return None


def pick_target(leaves):
    """下一个要攻克的：薄弱或一般、还有待重做错题的考点里掌握度最低的；没有返回 None。

    并列时取待重做错题多的，再并列取编号小的。
    """
    candidates = [leaf for leaf in leaves if leaf['status'] in ('weak', 'fair') and leaf['pending'] > 0]
    if not candidates:
        return None
    return min(candidates, key=lambda leaf: (leaf['value'], -leaf['pending'], leaf['id']))


def state_at(history, moment):
    """一道错题在 moment 时刻的状态：只用时间早于 moment 的结果和"设为掌握"。"""
    results = []
    for row in history['results']:
        at = normal_time(row['at'])
        if at is not None and at < moment:
            results.append({'at': at, 'order': row.get('order'), 'correct': row['correct']})
    waives = [normal_time(value) for value in history['waives']]
    earlier = [value for value in waives if value is not None and value < moment]
    waive_at = max(earlier) if earlier else None
    return question_state(results, normal_time(history['entered']), waive_at)['state']


def graduated_in_week(histories, start, end):
    """本周毕业的错题数：end 时已毕业、start 时还不是，并且本周内有做对的结果。"""
    count = 0
    for history in histories.values():
        if state_at(history, end) != 'graduated' or state_at(history, start) == 'graduated':
            continue
        in_week = [row for row in history['results']
                   if row['correct'] and start <= (normal_time(row['at']) or '') < end]
        if in_week:
            count += 1
    return count
