"""首页接口：一次返回首页要显示的全部数字（待核对、待批改、到期单词、翻一翻、连续天数、本周、星空）。

一周的数字直接复用 weekly.py 里的取数函数，口径和周报一致。
"有学习记录的一天" = 那天默写了单词或翻了错题卡片（家长录入错题不算），七天打卡条和连续天数都按这个口径。
"""

from datetime import datetime, timedelta

from fastapi import APIRouter, Request

import analytics
import flip
import starmap
import targeted
import weekly
from database import Database
from home_model import current_week_end, sky_counts, streak_days, top_names, week_days
from question_scope import current_student_id
from weekly_model import DATE_FORMAT, window

router = APIRouter()

STREAK_LOOKBACK_DAYS = 60    # 连续天数最多往前看多少天


async def review_part(db):
    """待核对的错题数，以及有待核对题的最新一份卷子（两条 SQL）。"""
    count = await db.first("SELECT COUNT(*) AS n FROM question WHERE deleted=0 AND review_status='pending'")
    paper = await db.first(
        'SELECT p.id, p.name FROM paper p WHERE p.deleted=0 AND EXISTS('
        "SELECT 1 FROM question q WHERE q.paper_id=p.id AND q.deleted=0 AND q.review_status='pending') "
        'ORDER BY p.paper_date DESC, p.id DESC LIMIT 1')
    return {'count': count['n'], 'latest_paper': {'id': paper['id'], 'name': paper['name']} if paper else None}


async def last_targeted_at(db):
    """最近一份考点卷的创建时间；没有返回 None。"""
    row = await db.first("SELECT created_at FROM practice_set WHERE deleted=0 AND kind='targeted' "
                         'ORDER BY created_at DESC, id DESC LIMIT 1')
    return row['created_at'] if row else None


async def due_word_count(db, moment):
    """到期要复习的单词数：next_review_at 不为空且不晚于 moment（一条 COUNT SQL，口径同 words.word_stats）。"""
    row = await db.first("SELECT COUNT(*) AS n FROM word WHERE deleted=0 AND next_review_at IS NOT NULL "
                         "AND next_review_at<>'' AND next_review_at<=?", (moment.isoformat(' '),))
    return row['n']


def streak_first_moment(moment):
    """连续天数最多往前看到哪一刻：STREAK_LOOKBACK_DAYS 天前那天的 00:00（19 位时间）。"""
    return (moment - timedelta(days=STREAK_LOOKBACK_DAYS - 1)).strftime(DATE_FORMAT) + ' 00:00:00'


async def recent_dictation_dates(db, moment):
    """最近 60 天有单词默写的日期集合（一条 SQL，只算 review_type=1）。"""
    first_day = streak_first_moment(moment)
    rows = await db.all('SELECT DISTINCT substr(reviewed_at,1,10) AS day FROM word_review_log '
                        'WHERE deleted=0 AND review_type=1 AND reviewed_at>=?', (first_day,))
    return {row['day'] for row in rows}


async def build_home(db, request, moment: datetime) -> dict:
    """组装首页数据；moment 是当前北京时间。"""
    week_end = current_week_end(moment)
    win = window(week_end)
    student_id = current_student_id(request)
    subjects = await weekly.load_subjects(db)
    names = {row['id']: row['name'] for row in subjects}
    entries, _entered = await weekly.entries_part(db, win, week_end, names)
    dictation, dictated_dates = await weekly.dictation_part(db, win, week_end)
    # 翻一翻：本周数字和周报同一个函数；日期往前多取到连续天数要看的最早一天，供打卡条和连续天数用
    flip_week, flipped_dates = await weekly.flip_part(db, student_id, win, streak_first_moment(moment))
    practice = await weekly.practice_part(db, win)
    # 配置和默认年级各取一次，每个有考点的学科再算一遍星星（和 build_facts 一样）
    config = await starmap.load_config(request)
    default_grade = await starmap.load_default_grade(request)
    parts = []
    for subject in subjects:
        if subject['has_leaves']:
            parts.append(await weekly.subject_part(db, subject, student_id, win, config, default_grade))
    improved = [item for part in parts for item in part['improved']]
    dropped = [item for part in parts for item in part['dropped']]
    streak_dates = await recent_dictation_dates(db, moment) | flipped_dates
    return {
        'review': await review_part(db),
        'grading': await targeted.pending_grading(db),
        'targeted': {'last_created_at': await last_targeted_at(db)},
        'words': {'due': await due_word_count(db, moment)},
        'flip': await flip.today_progress(db, student_id, moment.strftime(DATE_FORMAT)),
        'streak_days': streak_days(streak_dates, moment.strftime(DATE_FORMAT)),
        'week': {'monday': win['monday'], 'sunday': win['sunday'],
                 'days': week_days(win['monday'], dictated_dates | flipped_dates),
                 'entries': entries['count'], 'papers': practice['papers'],
                 'dictation_days': dictation['days'], 'flip_days': flip_week['days'],
                 'improved': top_names(improved, 3), 'dropped': top_names(dropped, 3)},
        'sky': sky_counts([part['status_counts'] for part in parts]),
    }


@router.get('/api/home')
async def home_view(request: Request):
    """首页：待核对、待批改、考点卷、到期单词、连续天数、本周概况和星空。"""
    db = Database(request.scope['env'].DB)
    return await build_home(db, request, analytics.now())
