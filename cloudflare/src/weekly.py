"""周报：从 D1 读数据，算出一期周报的数字（facts）。

规则（一周怎么算、档位变化怎么判）都在 weekly_model.py；这里只负责取数和组装。
一次 build_facts 的 SQL 条数固定（每个有考点的学科 5 条，再加 9 条），不随题目数、考点数增加。
时间都是北京时间字符串：库里是 26 位（带微秒），窗口是 19 位，可以直接按字符串比较。
"""

from datetime import datetime, timedelta

import starmap
from mastery_model import leaf_detail, status_of, upper_mastery
from question_scope import counted, current_student_id
from weekly_model import (CALENDAR_DAYS, STATUS_ORDER, STREAK_LOOKBACK, TIME_FORMAT, TREND_WEEKS, DATE_FORMAT,
                          calendar_days, classify_change, entry_streak, graduated_in_week, known_before, percent,
                          pick_target, week_activity, week_starts, window)

SCHEMA_VERSION = 1      # facts 结构的版本号
LIST_MAX = 5            # improved / dropped / new_weak 列表最多放几个考点


def week_index(moment, starts):
    """moment 落在第几个窗口（starts 从早到晚，每个窗口 7 天）；早于第一个窗口返回 None。"""
    index = None
    for position, start in enumerate(starts):
        if moment >= start:
            index = position      # 找到不晚于 moment 的最后一个开始时刻
    return index


def monday_of(start):
    """窗口开始（周日 20:00）的第二天就是那一周的周一。"""
    return (datetime.strptime(start, TIME_FORMAT) + timedelta(days=1)).strftime(DATE_FORMAT)


def week_dates(monday):
    """周一到周日 7 个日期（YYYY-MM-DD）。"""
    first = datetime.strptime(monday, DATE_FORMAT)
    return {(first + timedelta(days=offset)).strftime(DATE_FORMAT) for offset in range(7)}


async def report_number(db, student_id, end):
    """期数：这个学生 week_end 更早的未删除周报数 + 1。"""
    row = await db.first('SELECT COUNT(*) AS n FROM weekly_report WHERE student_id=? AND deleted=0 AND week_end<?',
                         (student_id, end))
    return row['n'] + 1


async def load_subjects(db):
    """全部学科，带"有没有二级考点"的标记，按编号从小到大。"""
    return await db.all(
        'SELECT s.id, s.name, EXISTS(SELECT 1 FROM knowledge_point k WHERE k.subject_id=s.id AND k.deleted=0 '
        'AND k.level=2) AS has_leaves FROM subject s WHERE s.deleted=0 ORDER BY s.id')


async def entries_part(db, win, week_end, names):
    """录入：本周、上周的条数，连续有录入的周数，本周分学科条数；另返回有录入的日期集合（一条 SQL）。"""
    starts = week_starts(week_end, STREAK_LOOKBACK)
    rows = await db.all('SELECT q.created_at, q.subject_id FROM question q WHERE ' + counted('q') +
                        ' AND q.created_at>=? AND q.created_at<?', (starts[0], win['end']))
    counts = [0] * len(starts)      # 每个窗口的条数，从早到晚
    by_subject = {}
    dates = set()
    for row in rows:
        created = str(row['created_at'])
        dates.add(created[:10])     # 按天算：时间的前 10 位就是那一天
        index = week_index(created, starts)
        counts[index] += 1
        if index == len(starts) - 1:
            by_subject[row['subject_id']] = by_subject.get(row['subject_id'], 0) + 1
    entries = {
        'count': counts[-1],
        'prev_count': counts[-2],
        'streak_weeks': entry_streak(list(reversed(counts))),    # entry_streak 要从本周往前排
        'by_subject': [{'subject_id': subject_id, 'name': names.get(subject_id, ''), 'count': count}
                       for subject_id, count in sorted(by_subject.items())],
    }
    return entries, dates


async def dictation_part(db, win, week_end):
    """单词默写（只算 review_type=1）：本周、上周、近 6 周趋势、本周默写天数；另返回有默写的日期集合（一条 SQL）。"""
    starts = week_starts(week_end, TREND_WEEKS)
    first_day = (datetime.strptime(win['sunday'], DATE_FORMAT)
                 - timedelta(days=CALENDAR_DAYS - 1)).strftime(TIME_FORMAT)    # 日历第一天 00:00
    rows = await db.all('SELECT reviewed_at, is_correct FROM word_review_log WHERE deleted=0 AND review_type=1 '
                        'AND reviewed_at>=? AND reviewed_at<?', (min(first_day, starts[0]), win['end']))
    totals = [0] * len(starts)
    rights = [0] * len(starts)
    dates = set()
    for row in rows:
        reviewed = str(row['reviewed_at'])
        dates.add(reviewed[:10])
        index = week_index(reviewed, starts)
        if index is not None:       # 比趋势第一周还早的只用来点亮日历
            totals[index] += 1
            rights[index] += 1 if row['is_correct'] else 0
    this_week = week_dates(win['monday'])
    dictation = {
        'count': totals[-1], 'correct': rights[-1], 'accuracy': percent(rights[-1], totals[-1]),
        'days': len(dates & this_week),       # 按自然日：周一到周日有默写的天数
        'prev_count': totals[-2], 'prev_accuracy': percent(rights[-2], totals[-2]),
        'trend': [{'monday': monday_of(start), 'count': totals[i], 'accuracy': percent(rights[i], totals[i])}
                  for i, start in enumerate(starts)],
    }
    return dictation, dates


async def practice_part(db, win):
    """错题练习卷：本周、上周批改的份数和每题结果（一条 SQL）。"""
    rows = await db.all(
        'SELECT ps.id AS set_id, ps.last_reviewed_at AS at, pq.is_correct FROM practice_set ps '
        'LEFT JOIN practice_set_question pq ON pq.practice_set_id=ps.id AND pq.deleted=0 AND pq.is_correct IS NOT NULL '
        "WHERE ps.deleted=0 AND ps.reviewed=1 AND ps.source_type='question' "
        'AND ps.last_reviewed_at>=? AND ps.last_reviewed_at<?', (win['prev_start'], win['end']))
    weeks = {'this': {'sets': set(), 'questions': 0, 'correct': 0},
             'prev': {'sets': set(), 'questions': 0, 'correct': 0}}
    for row in rows:
        week = weeks['this'] if str(row['at']) >= win['start'] else weeks['prev']
        week['sets'].add(row['set_id'])
        if row['is_correct'] is not None:      # LEFT JOIN 没对上题目时这一列为空
            week['questions'] += 1
            week['correct'] += 1 if row['is_correct'] else 0
    this, prev = weeks['this'], weeks['prev']
    return {'papers': len(this['sets']), 'questions': this['questions'], 'correct': this['correct'],
            'accuracy': percent(this['correct'], this['questions']),
            'prev_papers': len(prev['sets']), 'prev_accuracy': percent(prev['correct'], prev['questions'])}


async def graduated_count(db, win, student_id):
    """本周毕业的错题数（两条 SQL）：取数方式和 practices.load_history 一致。"""
    rows = await db.all(
        'SELECT q.id AS qid, q.created_at AS entered, qk.knowledge_point_id AS point_id, '
        'o.is_correct, o.display_order, ps.last_reviewed_at FROM question q '
        'LEFT JOIN question_knowledge_point qk ON qk.question_id=q.id AND qk.deleted=0 AND qk.is_primary=1 '
        'JOIN practice_set_question o ON o.question_id=q.id AND o.deleted=0 '
        'AND o.is_correct IS NOT NULL AND o.skip_reason IS NULL '
        'JOIN practice_set ps ON ps.id=o.practice_set_id AND ps.deleted=0 '
        'WHERE ' + counted('q') + ' AND q.created_at<? AND ps.last_reviewed_at<?', (win['end'], win['end']))
    # "直接设为掌握"：{考点: [时间, ...]}，一道题看它主考点上的调整
    adjust_rows = await db.all(
        "SELECT knowledge_point_id AS point_id, created_at FROM mastery_adjustment WHERE deleted=0 AND student_id=? "
        "AND kind='set_mastered' AND created_at<?", (student_id, win['end']))
    waives = {}
    for row in adjust_rows:
        waives.setdefault(row['point_id'], []).append(row['created_at'])
    histories = {}
    for row in rows:
        history = histories.setdefault(row['qid'], {'entered': row['entered'], 'results': [],
                                                    'waives': waives.get(row['point_id'], [])})
        history['results'].append({'at': row['last_reviewed_at'], 'order': row['display_order'] or 0,
                                   'correct': bool(row['is_correct'])})
    return graduated_in_week(histories, win['start'], win['end'])


def leaves_at(points, events, sections, progress, default_grade, moment):
    """moment 时刻每个二级考点的掌握度：{考点: {'value', 'status', 'pending'}}。

    只用"知道的时间"早于 moment 的事件；"学过没有"也按过滤后的事件判断。
    """
    filtered = {}
    for point_id, point_events in events.items():
        kept = known_before(point_events, moment)
        if kept:
            filtered[point_id] = kept
    learned = starmap.learned_ids(points, filtered, sections, progress, default_grade)
    result = {}
    for leaf in points:
        if leaf['level'] != 2:
            continue
        detail = leaf_detail(filtered.get(leaf['id'], []))
        value = detail['value'] if leaf['id'] in learned else None
        result[leaf['id']] = {'value': value, 'status': status_of(value), 'pending': detail['pending']}
    return result


def module_value(module, points, values):
    """一级模块的掌握度：和 starmap.compute 一样，只看下面已学的二级考点；都没学时是 None。"""
    children = [leaf for leaf in points if leaf['level'] == 2 and leaf['parent_id'] == module['id']]
    child_values = [values[child['id']]['value'] for child in children if values[child['id']]['value'] is not None]
    if not child_values:
        return None
    return round(upper_mastery(child_values, len(child_values) < len(children)), 2)


async def subject_part(db, subject, student_id, win, config, default_grade):
    """一个学科的考点星星：环形图、变好/变差/新出现、雷达图、下一个要攻克的（五条 SQL）。"""
    subject_id = subject['id']
    points = await starmap.load_points(db, subject_id)
    events = await starmap.load_events(db, subject_id, student_id, default_grade)
    sections = await starmap.load_sections(db, subject_id)
    progress = (config.get('progress') or {}).get(str(subject_id))
    before = leaves_at(points, events, sections, progress, default_grade, win['start'])
    after = leaves_at(points, events, sections, progress, default_grade, win['end'])
    status_counts = {status: 0 for status in STATUS_ORDER}
    changes = {'improved': [], 'dropped': [], 'new_weak': []}
    target_leaves = []
    for leaf in points:
        if leaf['level'] != 2:
            continue
        now = after[leaf['id']]
        status_counts[now['status']] += 1
        # 本周有没有做对/做错：用全部事件，week_activity 自己按"知道的时间"挑本周的
        activity = week_activity(events.get(leaf['id'], []), win['start'], win['end'])
        change = classify_change(before[leaf['id']]['status'], now['status'], activity)
        if change:
            changes[change].append({'id': leaf['id'], 'name': leaf['name']})
        target_leaves.append({'id': leaf['id'], 'name': leaf['name'], **now})
    target = pick_target(target_leaves)
    modules = []
    for module in (p for p in points if p['level'] == 1):
        value_after = module_value(module, points, after)
        if value_after is None:
            continue          # 值为空的模块不画
        modules.append({'id': module['id'], 'name': module['name'],
                        'before': module_value(module, points, before), 'after': value_after})
    return {'subject_id': subject_id, 'name': subject['name'], 'status_counts': status_counts,
            'improved': changes['improved'][:LIST_MAX], 'improved_count': len(changes['improved']),
            'dropped': changes['dropped'][:LIST_MAX], 'dropped_count': len(changes['dropped']),
            'new_weak': changes['new_weak'][:LIST_MAX], 'modules': modules,
            'target': {'id': target['id'], 'name': target['name']} if target else None}


async def build_facts(db, request, week_end: datetime) -> dict:
    """算出 week_end 那一期周报的全部数字（facts 结构见设计文档和 global-constraints）。"""
    win = window(week_end)
    student_id = current_student_id(request)
    number = await report_number(db, student_id, win['end'])
    subjects = await load_subjects(db)
    names = {row['id']: row['name'] for row in subjects}
    entries, entered_dates = await entries_part(db, win, week_end, names)
    dictation, dictated_dates = await dictation_part(db, win, week_end)
    practice = await practice_part(db, win)
    practice['graduated'] = await graduated_count(db, win, student_id)
    # 教材进度和默认年级用当前配置，不追溯
    config = await starmap.load_config(request)
    default_grade = await starmap.load_default_grade(request)
    subject_facts = []
    for subject in subjects:
        if subject['has_leaves']:
            subject_facts.append(await subject_part(db, subject, student_id, win, config, default_grade))
    return {
        'schema_version': SCHEMA_VERSION,
        'week': {'start': win['start'], 'end': win['end'], 'monday': win['monday'], 'sunday': win['sunday'],
                 'number': number},
        'quiet': entries['count'] == 0 and dictation['count'] == 0 and practice['papers'] == 0,
        'entries': entries,
        'calendar': calendar_days(win['sunday'], entered_dates, dictated_dates),
        'dictation': dictation,
        'practice': practice,
        'subjects': subject_facts,
    }
