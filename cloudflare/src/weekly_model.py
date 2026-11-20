"""周报"一周怎么算"的规则（纯函数，不读数据库、不读时钟）。

一期周报的窗口是 [上周日 20:00, 本周日 20:00)：按条数算的数字用这个窗口，
按天算的数字用周一到周日的自然日。时间字符串统一是 'YYYY-MM-DD HH:MM:SS'（19 位）。
所有函数只做计算，"现在几点"由调用方传进来。
"""

import re
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
        # 只因为"直接设为掌握"才毕业的不算：不带 waive 重算，end 时也得是已毕业
        if state_at({**history, 'waives': []}, end) != 'graduated':
            continue
        in_week = [row for row in history['results']
                   if row['correct'] and start <= (normal_time(row['at']) or '') < end]
        if in_week:
            count += 1
    return count


# ---------------------------------------------------------------- 文字：给模型看的数据、检查、兜底

# 兜底鼓励句（用户过目过的原文，不要改动）
FALLBACK_CHEERS = (
    '又一周过去了，你走的每一步都算数。',
    '坚持本身就是本事，这周你又做到了。',
    '错题不是麻烦，是你变强的线索。',
    '今天比上周多懂一点，就是进步。',
    '慢一点没关系，方向对了就好。',
    '每改对一道错题，你就多了一块拼图。',
    '你认真的样子，本身就很了不起。',
    '难的题先放一放，回头再看，你会发现自己变厉害了。',
    '这周的努力，都会在以后悄悄帮到你。',
    '一点一点来，星星会一颗一颗亮。',
    '敢面对错题的人，才会越来越稳。',
    '给这周的自己点个赞，下周继续。',
)
QUIET_CHEER = '慢一点没关系，方向对了就好。'   # 安静的一周固定用这一句


def brief_of(facts):
    """从 facts 里取出给模型看的那部分（不含日历明细和趋势）。文字里会用到的数量都要在这里有数字。"""
    calendar = facts['calendar'][-7:]    # 本周周一到周日
    lit = sum(1 for day in calendar if day['entered'] or day['dictated'])
    dictation = facts['dictation']
    subjects = []
    for subject in facts['subjects']:
        target = subject.get('target')
        subjects.append({
            'subject_id': subject['subject_id'],
            'name': subject['name'],
            'improved': [point['name'] for point in subject['improved']],
            'dropped': [point['name'] for point in subject['dropped']],
            'new_weak': [point['name'] for point in subject['new_weak']],
            # 列表最多 5 个；有真实总数（improved_count / dropped_count）时用总数，没有时退回列表长度
            'improved_count': subject.get('improved_count', len(subject['improved'])),
            'dropped_count': subject.get('dropped_count', len(subject['dropped'])),
            'target': target['name'] if target else None,
            'modules': [{'name': module['name'], 'before': module['before'], 'after': module['after']}
                        for module in subject['modules']],
        })
    return {
        'week': {'monday': facts['week']['monday'], 'sunday': facts['week']['sunday'],
                 'number': facts['week']['number']},
        'quiet': facts['quiet'],
        'entries': {'count': facts['entries']['count'], 'prev_count': facts['entries']['prev_count'],
                    'streak_weeks': facts['entries']['streak_weeks']},
        'calendar_days_lit': lit,
        'dictation': {'count': dictation['count'], 'accuracy': dictation['accuracy'], 'days': dictation['days'],
                      'prev_count': dictation['prev_count'], 'prev_accuracy': dictation['prev_accuracy']},
        'practice': dict(facts['practice']),
        'improved_total': sum(item['improved_count'] for item in subjects),
        'subjects': subjects,
    }


def collect_numbers(value, found):
    """把 value 里所有数字（不含 bool、None）的写法放进 found；modules 的前后值不算。"""
    if isinstance(value, bool) or value is None:
        return
    if isinstance(value, int):
        found.add(str(value))
    elif isinstance(value, float):
        found.add(str(value))
        found.add(str(round(value)))     # 小数也允许写成四舍五入后的整数
    elif isinstance(value, dict):
        for key, item in value.items():
            if key != 'modules':
                collect_numbers(item, found)
    elif isinstance(value, list):
        for item in value:
            collect_numbers(item, found)


def allowed_numbers(brief):
    """brief 里每个数字的写法，再加上 monday、sunday 的月和日。"""
    found = set()
    collect_numbers(brief, found)
    for key in ('monday', 'sunday'):
        _, month, day = brief['week'][key].split('-')
        found.add(str(int(month)))
        found.add(str(int(day)))
    return found


def allowed_names(brief):
    """subjects 里出现的所有考点名、模块名、学科名。"""
    names = set()
    for subject in brief['subjects']:
        names.add(subject['name'])
        names.update(subject['improved'])
        names.update(subject['dropped'])
        names.update(subject['new_weak'])
        if subject['target']:
            names.add(subject['target'])
        for module in subject['modules']:
            names.add(module['name'])
    return names


def too_long_or_empty(value, limit):
    """value 不是字符串、是空串或超过 limit 个字时返回 True。"""
    return not isinstance(value, str) or not value.strip() or len(value) > limit


def check_text(text, brief, recent_cheers):
    """检查模型写的文字：通过返回 None，否则返回一句简短的中文原因（不含模型原文）。"""
    # 1. 结构和类型
    if not isinstance(text, dict):
        return '返回的不是对象'
    captions = text.get('captions')
    if not isinstance(captions, dict) or not isinstance(captions.get('points'), dict):
        return '图注结构不对'
    # 2. 长度，都不能是空串
    if too_long_or_empty(text.get('cheer'), CHEER_MAX):
        return '鼓励语为空或超长'
    if too_long_or_empty(text.get('summary'), SUMMARY_MAX):
        return '总结为空或超长'
    for key in ('calendar', 'dictation', 'practice'):
        if too_long_or_empty(captions.get(key), CAPTION_MAX):
            return '图注为空、缺失或超长'
    # 3. points 的键正好是各学科编号
    points = captions['points']
    if set(points) != {str(subject['subject_id']) for subject in brief['subjects']}:
        return '学科图注和学科不对应'
    for value in points.values():
        if too_long_or_empty(value, CAPTION_MAX):
            return '学科图注为空或超长'
    all_text = [text['cheer'], text['summary'], captions['calendar'], captions['dictation'],
                captions['practice']] + list(points.values())
    joined = '\n'.join(all_text)
    # 4. 不含禁用词
    if any(word in joined for word in BANNED_WORDS):
        return '含有不该出现的称呼'
    # 5. 数字都是给过的（「」里的名字可能带数字，先去掉，名字单独检查）
    outside_names = re.sub(r'「[^」]*」', '', joined)
    numbers = allowed_numbers(brief)
    if any(number not in numbers for number in re.findall(r'\d+(?:\.\d+)?', outside_names)):
        return '出现了没给过的数字'
    # 6. 「」里的名字都是给过的
    names = allowed_names(brief)
    if any(name not in names for name in re.findall(r'「([^」]*)」', joined)):
        return '出现了没给过的考点或模块名'
    # 7. 鼓励语不和最近几期重复
    if text['cheer'] in recent_cheers:
        return '鼓励语和最近几期重复'
    return None


def pick_fallback_cheer(brief, recent_cheers):
    """兜底鼓励句：从第 (期数 - 1) % 句数 句开始往后找第一句不在 recent_cheers 里的；安静的一周从固定句开始。"""
    total = len(FALLBACK_CHEERS)
    if brief['quiet']:
        start = FALLBACK_CHEERS.index(QUIET_CHEER)
    else:
        start = (brief['week']['number'] - 1) % total
    for offset in range(total):
        cheer = FALLBACK_CHEERS[(start + offset) % total]
        if cheer not in recent_cheers:
            return cheer
    return FALLBACK_CHEERS[start]    # 全都用过了（正常不会发生）就照起点


def fallback_summary(brief):
    """兜底总结：按条件拼固定句式，数字都来自 brief。"""
    if brief['quiet']:
        return '这周歇了一下，没关系。下周先从默写几个单词开始吧。'
    parts = []
    dictation = brief['dictation']
    if dictation['days'] > 0:
        parts.append('这周你有 %d 天默写了单词，一共 %d 条。' % (dictation['days'], dictation['count']))
    if brief['improved_total'] > 0:
        parts.append('有 %d 个考点变好了。' % brief['improved_total'])
    if brief['practice']['graduated'] > 0:
        parts.append('有 %d 道错题毕业了。' % brief['practice']['graduated'])
    for subject in brief['subjects']:
        if subject['target']:
            parts.append('下一个要攻克的是「%s」。' % subject['target'])
            break
    if not parts:
        parts.append('这周录了 %d 道错题，把它们一道道弄懂就好。' % brief['entries']['count'])
    return ''.join(parts)


def fallback_text(brief, recent_cheers):
    """模型不可用时，用服务端拼出的文字（text 结构）。"""
    lit = brief['calendar_days_lit']
    practice = brief['practice']
    points = {}
    for subject in brief['subjects']:
        if subject['improved_count'] > 0:
            points[str(subject['subject_id'])] = '有 %d 颗星星变亮了。' % subject['improved_count']
        else:
            points[str(subject['subject_id'])] = '这周星星没有变化，下周再来。'
    return {
        'cheer': pick_fallback_cheer(brief, recent_cheers),
        'summary': fallback_summary(brief),
        'captions': {
            'calendar': '这周亮了 %d 格。' % lit if lit > 0 else '这周的格子还空着，下周来点亮。',
            'points': points,
            'dictation': ('这周默写了 %d 条。' % brief['dictation']['count']
                          if brief['dictation']['count'] > 0 else '这周没有默写单词。'),
            'practice': ('这周做了 %d 份练习卷，做对 %d 道。' % (practice['papers'], practice['correct'])
                         if practice['papers'] > 0 else '这周还没有做练习卷。'),
        },
    }
