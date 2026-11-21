"""首页（/api/home）用到的纯函数：只做计算，不查库。

日期都是 'YYYY-MM-DD' 字符串；时间都是北京时间。
"""

from datetime import datetime, timedelta

from weekly_model import DATE_FORMAT, week_end_before


def current_week_end(moment):
    """"本周"的结束时刻：下一个周日 20:00（正好周日 20:00 算新的一周已经开始）。"""
    return week_end_before(moment) + timedelta(days=7)


def streak_days(active_dates, today):
    """连续有记录的天数：从今天往前数；今天没有但昨天有，就从昨天开始数；都没有返回 0。"""
    day = datetime.strptime(today, DATE_FORMAT)
    if day.strftime(DATE_FORMAT) not in active_dates:
        day -= timedelta(days=1)
    count = 0
    while day.strftime(DATE_FORMAT) in active_dates:
        count += 1
        day -= timedelta(days=1)
    return count


def week_days(monday, active_dates):
    """周一到周日 7 天，每天 {date, active}；active 看日期在不在集合里。"""
    first = datetime.strptime(monday, DATE_FORMAT)
    days = []
    for offset in range(7):
        date = (first + timedelta(days=offset)).strftime(DATE_FORMAT)
        days.append({'date': date, 'active': date in active_dates})
    return days


def sky_counts(status_counts_list):
    """把各学科的掌握状态数合成三档：weak、middle（fair+good）、lit（mastered）；unlearned 不计。"""
    total = {'weak': 0, 'middle': 0, 'lit': 0}
    for counts in status_counts_list:
        total['weak'] += counts.get('weak', 0)
        total['middle'] += counts.get('fair', 0) + counts.get('good', 0)
        total['lit'] += counts.get('mastered', 0)
    return total


def top_names(items, limit=3):
    """取前 limit 项的 name。"""
    return [item['name'] for item in items[:limit]]
