"""周报：从 D1 读数据，算出一期周报的数字（facts）。

规则（一周怎么算、档位变化怎么判）都在 weekly_model.py；这里只负责取数和组装。
一次 build_facts 的 SQL 条数固定（每个有考点的学科 5 条，再加 10 条），不随题目数、考点数增加。
时间都是北京时间字符串：库里是 26 位（带微秒），窗口是 19 位，可以直接按字符串比较。

推进一步（advance_once）：定时任务和页面接口共用，每次只做当前状态的下一步，
靠一条带条件的 UPDATE 认领这一步（写法参考 scan.py 的 claim_step / finish_step）。
step_started_at 存 19 位北京时间字符串，和 week_end、created_at 同一种写法：列是 TEXT，
按字符串比较就是按时间先后比较（scan.py 存整数秒，这里不照搬，免得一张表里有两种时间写法）。

下面这些模块级名字测试和本机开发服务器会替换，代码里一律直接按名字调用：generate_json、Database、build_facts。
"""

import json
from datetime import datetime, timedelta

from fastapi import APIRouter, HTTPException, Request

import analytics
import auth
import starmap
from database import Database
from flip import flip_counts, flip_dates, load_flip_rows
from mastery_model import leaf_detail, status_of, upper_mastery
from prompts import PromptLibrary
from question_scope import counted, current_student_id
from settings import generate_json
from weekly_model import (CALENDAR_DAYS, STATUS_ORDER, STREAK_LOOKBACK, TIME_FORMAT, TREND_WEEKS, DATE_FORMAT,
                          calendar_days, classify_change, drop_week_adjusts, entry_streak, graduated_in_week,
                          known_before, percent, pick_target, week_activity, week_starts, window)
from weekly_model import RECENT_CHEERS, TEXT_MAX_ATTEMPTS, brief_of, check_text, fallback_text, week_end_before

SCHEMA_VERSION = 1      # facts 结构的版本号
LIST_MAX = 5            # improved / dropped / new_weak 列表最多放几个考点
STALE_SECONDS = 180     # 认领一步后超过这么多秒还没做完，算卡住，可以被重新认领
# 模型请求超时 120 秒（settings.py）比 STALE_SECONDS 短，模型调用进行中认领不会过期，所以正常情况下每期最多调
# TEXT_MAX_ATTEMPTS 次模型；如果某次运行在模型返回之后、记下失败次数之前被中断，这一次不会被记上，可能多调一次
LIST_LIMIT = 60         # 各期简表最多列几期
MODEL_FAILED_TEXT = '文本模型请求失败'     # 写进 error 的固定短句，后面只跟状态码
MODEL_ERROR_TEXT = '文本模型调用出错'      # 不是 HTTP 错误时的固定短句
NOT_FOUND_TEXT = '周报不存在'

router = APIRouter(prefix='/api/weekly-reports')


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
    """期数：这个学生 week_end 更早、已算好数字（facts_ready 或 done）的未删除周报数 + 1。

    一直停在 new 的期不算，免得期数跳号（第 1 期后面直接是第 3 期）。
    """
    row = await db.first("SELECT COUNT(*) AS n FROM weekly_report WHERE student_id=? AND deleted=0 AND week_end<? "
                         "AND status IN ('facts_ready','done')", (student_id, end))
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
    first_day = calendar_first_moment(win)    # 日历第一天 00:00
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


def calendar_first_moment(win):
    """日历第一天的 00:00（19 位时间）：本周日往前共 CALENDAR_DAYS 天。"""
    return (datetime.strptime(win['sunday'], DATE_FORMAT) - timedelta(days=CALENDAR_DAYS - 1)).strftime(TIME_FORMAT)


async def flip_part(db, student_id, win, first_moment):
    """翻一翻：本期（[start, end)）翻了几天、几张 {'days', 'cards'}，另返回 [first_moment, end) 里翻过卡片的日期集合（一条 SQL）。

    和默写一样按记录时间算窗口；天数按 flip_date 去重。首页和周报都用它，口径一致。
    """
    rows = await load_flip_rows(db, student_id, min(first_moment, win['start']), win['end'])
    return flip_counts(rows, win['start'], win['end']), flip_dates(rows)


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
    # 去掉本周的手动调整再算一遍周末档位，用来判断变化是不是只因为手动调整（纯计算，不多查库）
    plain_events = {point_id: drop_week_adjusts(point_events, win['start'], win['end'])
                    for point_id, point_events in events.items()}
    plain_after = leaves_at(points, plain_events, sections, progress, default_grade, win['end'])
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
        change = classify_change(before[leaf['id']]['status'], now['status'],
                                 plain_after[leaf['id']]['status'], activity)
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
    flip, flipped_dates = await flip_part(db, student_id, win, calendar_first_moment(win))
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
        # 只翻了卡片的一周也不算安静
        'quiet': (entries['count'] == 0 and dictation['count'] == 0 and practice['papers'] == 0
                  and flip['cards'] == 0),
        'entries': entries,
        # 日历上翻了卡片的那天和默写同一档（都是学生自己学了的一天）
        'calendar': calendar_days(win['sunday'], entered_dates, dictated_dates | flipped_dates),
        'dictation': dictation,
        'practice': practice,
        'flip': flip,
        'subjects': subject_facts,
    }


# ---------------------------------------------------------------- 推进一步


def stamp(moment):
    """datetime 转成库里用的 19 位时间字符串。"""
    return moment.strftime(TIME_FORMAT)


async def ensure_report(db, student_id, week_end, now_text):
    """读这一期的记录；还没有就建一条再读（唯一索引保证同一期只有一条，并发建时另一条什么都不做）。"""
    sql = ('SELECT id,status,step_started_at,facts,attempts FROM weekly_report '
           'WHERE student_id=? AND week_end=? AND deleted=0')
    row = await db.first(sql, (student_id, week_end))
    if row is None:
        await db.run("INSERT INTO weekly_report(student_id,week_end,status,created_at,updated_at) "
                     "VALUES(?,?,'new',?,?) ON CONFLICT DO NOTHING", (student_id, week_end, now_text, now_text))
        row = await db.first(sql, (student_id, week_end))
    return row


async def claim_step(db, row, moment):
    """用一条条件更新认领这一步：状态还是读到时的样子、且没有别人正在做（或已卡住）才算认领成功。"""
    found = await db.first(
        'UPDATE weekly_report SET step_started_at=?,updated_at=? '
        'WHERE id=? AND deleted=0 AND status=? AND (step_started_at IS NULL OR step_started_at<?) RETURNING id',
        (stamp(moment), stamp(moment), row['id'], row['status'], stamp(moment - timedelta(seconds=STALE_SECONDS))))
    return found is not None


async def finish_step(db, row, claimed_at, fields):
    """一步结束：写入 fields，清空 step_started_at；返回是否写进去了。

    只在记录仍是自己认领时的样子才写（状态和认领时间都没变），
    这样卡住后被别人重新认领的那一步，不会被这次迟到的结果覆盖。
    """
    data = dict(fields, step_started_at=None, updated_at=claimed_at)
    columns = ','.join(key + '=?' for key in data)
    found = await db.first(
        'UPDATE weekly_report SET ' + columns + ' WHERE id=? AND deleted=0 AND status=? AND step_started_at=? '
        'RETURNING id', [*data.values(), row['id'], row['status'], claimed_at])
    return found is not None


async def facts_step(db, request, row, week_end, claimed_at):
    """状态 new：算数字并保存，改成 facts_ready。出错时 error 只写异常类型名，状态不变，异常继续抛出。"""
    try:
        facts = await build_facts(db, request, week_end)
    except Exception as error:
        await finish_step(db, row, claimed_at, {'error': type(error).__name__})
        raise
    written = await finish_step(db, row, claimed_at,
                                {'status': 'facts_ready', 'facts': json.dumps(facts, ensure_ascii=False)})
    return 'facts_ready' if written else None


async def recent_cheers(db, student_id, week_end):
    """更早的、已做完的最近几期用过的鼓励语（一条 SQL）。"""
    rows = await db.all(
        "SELECT json_extract(text,'$.cheer') AS cheer FROM weekly_report WHERE student_id=? AND deleted=0 "
        "AND status='done' AND week_end<? ORDER BY week_end DESC LIMIT ?", (student_id, week_end, RECENT_CHEERS))
    return [row['cheer'] for row in rows if row['cheer']]


async def ask_model(request, brief, cheers):
    """调一次文本模型并检查：通过返回 (文字, None)，否则返回 (None, 简短原因)。

    原因只写固定短句（模型请求失败时带上状态码），不写异常里的任何原文，也不写模型返回的内容。
    """
    prompt = PromptLibrary()._build_weekly_report_prompt(brief, cheers)
    try:
        text = await generate_json(request, prompt)
    except HTTPException as error:
        return None, '%s（%s）' % (MODEL_FAILED_TEXT, error.status_code)
    except Exception:
        return None, MODEL_ERROR_TEXT
    reason = check_text(text, brief, cheers)
    return (text, None) if reason is None else (None, reason)


async def text_step(db, request, row, student_id, week_end, claimed_at):
    """状态 facts_ready：调一次模型写文字；失败记次数，到 TEXT_MAX_ATTEMPTS 次当场改用兜底文字。"""
    brief = brief_of(json.loads(row['facts']))
    cheers = await recent_cheers(db, student_id, week_end)
    attempts = row['attempts']
    reason = None
    if attempts < TEXT_MAX_ATTEMPTS:      # 已经失败够次数的（正常不会出现）不再调模型
        text, reason = await ask_model(request, brief, cheers)
        if reason is None:
            written = await finish_step(db, row, claimed_at, {
                'status': 'done', 'text': json.dumps(text, ensure_ascii=False), 'text_source': 'model'})
            return 'done' if written else None
        attempts += 1
    if attempts < TEXT_MAX_ATTEMPTS:
        written = await finish_step(db, row, claimed_at, {'attempts': attempts, 'error': reason})
        return 'facts_ready' if written else None
    fields = {'status': 'done', 'text': json.dumps(fallback_text(brief, cheers), ensure_ascii=False),
              'text_source': 'fallback', 'attempts': attempts}
    if reason:
        fields['error'] = reason
    written = await finish_step(db, row, claimed_at, fields)
    return 'done' if written else None


async def advance_once(request, moment: datetime | None = None) -> dict:
    """把最近一期周报推进一步：new → 算数字 → facts_ready → 写文字 → done；done 什么都不做。

    返回 {'id', 'status', 'busy'}；busy 为真表示这一步正被别人做着（这次什么都没做）。
    moment 是"现在"，缺省用北京时间 analytics.now()；目标是不晚于它的最近一个周日 20:00。
    写文字这一步的 SQL：读记录、认领、读最近鼓励语、写结果共 4 条（线上模型配置再读 1 条），不超过 6 条。
    """
    result, failed_attempts = await advance_step(request, moment or analytics.now())
    return result


async def advance_step(request, moment: datetime):
    """推进一步的实际过程，返回 (结果, 失败次数)。

    结果同 advance_once；失败次数只在这次写文字没成功、还没到兜底时有值（这次之后的 attempts），否则是 None。
    定时任务用它在日志里区分"算好数字"和"写文字失败"，接口照旧只返回结果。
    """
    db = Database(request.scope['env'].DB)
    student_id = current_student_id(request)
    week_end_time = week_end_before(moment)
    week_end = stamp(week_end_time)
    row = await ensure_report(db, student_id, week_end, stamp(moment))
    if row['status'] == 'done':
        return {'id': row['id'], 'status': 'done', 'busy': False}, None
    if not await claim_step(db, row, moment):
        return {'id': row['id'], 'status': row['status'], 'busy': True}, None
    claimed_at = stamp(moment)
    if row['status'] == 'new':
        status = await facts_step(db, request, row, week_end_time, claimed_at)
    else:
        status = await text_step(db, request, row, student_id, week_end, claimed_at)
    if status is None:      # 做完时发现已被别人重新认领，这次的结果没有写进去
        return {'id': row['id'], 'status': row['status'], 'busy': True}, None
    result = {'id': row['id'], 'status': status, 'busy': False}
    if row['status'] == 'facts_ready' and status == 'facts_ready':     # 写文字失败，次数加了 1
        return result, row['attempts'] + 1
    return result, None


# ---------------------------------------------------------------- 定时任务


class ScheduledRequest:
    """定时任务里没有请求对象；现有函数只从 request.scope['env'] 取环境，用这个替身传进去。"""

    def __init__(self, env):
        self.scope = {'env': env}


async def run_scheduled(env) -> str:
    """定时入口：维护开关开着时什么都不做，否则推进一步。

    返回并打印一行日志：weekly <week_end> <做完后的状态 / busy / maintenance / failed 异常类型名>；
    写文字失败时状态后面再跟 text_failed <次数>/<上限>，例如 weekly 2026-11-22 20:00:00 facts_ready text_failed 1/3。
    日志只用固定词和数字：所有异常都接住，只记类型名，不记异常内容和 error 列（避免把密钥或模型原文写进日志）。
    """
    week_end = '-'      # 连时间都没算出来就出错时，日志里这一项写 -
    try:
        request = ScheduledRequest(env)
        moment = analytics.now()
        week_end = stamp(week_end_before(moment))
        if await auth.maintenance_enabled(request):
            outcome = 'maintenance'
        else:
            result, failed_attempts = await advance_step(request, moment)
            outcome = 'busy' if result['busy'] else result['status']
            if failed_attempts is not None:
                outcome += ' text_failed %d/%d' % (failed_attempts, TEXT_MAX_ATTEMPTS)
    except Exception as error:
        outcome = 'failed ' + type(error).__name__
    line = 'weekly %s %s' % (week_end, outcome)
    print(line)
    return line


# ---------------------------------------------------------------- 接口


def week_dates_of(week_end):
    """由 week_end（19 位时间）得到这一期的周一、周日日期。"""
    win = window(datetime.strptime(week_end, TIME_FORMAT))
    return win['monday'], win['sunday']


async def list_reports(request, moment):
    """各期简表（只列 facts_ready 和 done，新的在前，最多 LIST_LIMIT 条）；due 表示最近一期还没做完。"""
    db = Database(request.scope['env'].DB)
    student_id = current_student_id(request)
    rows = await db.all(
        "SELECT id,week_end,status,json_extract(facts,'$.week.number') AS number FROM weekly_report "
        "WHERE student_id=? AND deleted=0 AND status IN ('facts_ready','done') ORDER BY week_end DESC LIMIT ?",
        (student_id, LIST_LIMIT))
    latest = await db.first('SELECT status FROM weekly_report WHERE student_id=? AND week_end=? AND deleted=0',
                            (student_id, stamp(week_end_before(moment))))
    items = []
    for row in rows:
        monday, sunday = week_dates_of(row['week_end'])
        items.append({'id': row['id'], 'number': row['number'], 'monday': monday, 'sunday': sunday,
                      'status': row['status']})
    return {'items': items, 'due': latest is None or latest['status'] != 'done'}


async def report_detail(request, report_id):
    """一期的完整内容；没有 facts / text 时是 None；不存在返回 404。"""
    db = Database(request.scope['env'].DB)
    row = await db.first('SELECT id,week_end,status,facts,text,text_source FROM weekly_report '
                         'WHERE id=? AND student_id=? AND deleted=0', (report_id, current_student_id(request)))
    if row is None:
        raise HTTPException(404, NOT_FOUND_TEXT)
    facts = json.loads(row['facts']) if row['facts'] else None
    monday, sunday = week_dates_of(row['week_end'])
    return {'id': row['id'], 'status': row['status'], 'number': (facts or {}).get('week', {}).get('number'),
            'monday': monday, 'sunday': sunday, 'facts': facts,
            'text': json.loads(row['text']) if row['text'] else None, 'text_source': row['text_source']}


@router.get('')
async def list_view(request: Request):
    """GET /api/weekly-reports：各期简表。"""
    return await list_reports(request, analytics.now())


@router.post('/advance')
async def advance_view(request: Request):
    """POST /api/weekly-reports/advance：把最近一期推进一步（写入，维护开关打开时由中间件返回 503）。"""
    return await advance_once(request)


@router.get('/{report_id}')
async def detail_view(request: Request, report_id: int):
    """GET /api/weekly-reports/{id}：一期的完整内容。"""
    return await report_detail(request, report_id)
