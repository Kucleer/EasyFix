"""周报（weekly report）的本地测试。

在 targeted_test 的测试库（含迁移 0015）上再执行迁移 0016。运行：

    python cloudflare/scripts/weekly_report_test.py
"""

import json
import pathlib
import sqlite3
import sys
from datetime import datetime, timedelta

from fastapi import HTTPException

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
sys.path.insert(0, str(ROOT / 'scripts'))

import starmap_test  # noqa: E402  复用输出与检查助手
import targeted_test  # noqa: E402  复用建库（starmap_test 的库 + 0015）
from prompts import PromptLibrary  # noqa: E402
from weekly_model import (FALLBACK_CHEERS, allowed_names, allowed_numbers, brief_of,  # noqa: E402
                          check_text, fallback_text, calendar_days, classify_change, drop_week_adjusts, entry_streak, graduated_in_week,  # noqa: E402
                          known_at, known_before, percent, pick_target, week_activity,
                          week_end_before, week_starts, window)

MIGRATION_0016 = ROOT / 'migrations' / '0016_weekly_report.sql'


def build_db():
    """建立测试库：targeted_test 的库 + 迁移 0016。"""
    connection = targeted_test.build_db()
    connection.executescript(MIGRATION_0016.read_text(encoding='utf-8'))
    connection.commit()
    return connection


# ---------------------------------------------------------------- 任务 1：迁移 0016


def test_migration_creates_weekly_report():
    """0016 新建 weekly_report 表：列齐全，默认值正确，同一学生同一期只能有一条未删除记录。"""
    c = build_db()
    columns = {row[1] for row in c.execute('PRAGMA table_info(weekly_report)')}
    assert columns == {'id', 'student_id', 'week_end', 'status', 'step_started_at', 'facts', 'text',
                       'text_source', 'attempts', 'error', 'created_at', 'updated_at', 'deleted'}
    insert = ("INSERT INTO weekly_report(week_end,created_at,updated_at) "
              "VALUES('2026-11-22 20:00:00','2026-11-22 20:00:05','2026-11-22 20:00:05')")
    c.execute(insert)
    row = c.execute('SELECT student_id,status,attempts,deleted FROM weekly_report').fetchone()
    assert tuple(row) == (1, 'new', 0, 0)
    try:
        c.execute(insert)  # 同一个学生同一期不能有两条
        assert False, '应该被唯一索引拦住'
    except sqlite3.IntegrityError:
        pass
    c.execute('UPDATE weekly_report SET deleted=1')
    c.execute(insert)  # 软删除之后可以再建


# ---------------------------------------------------------------- 任务 2：一周怎么算


def test_week_end_boundaries():
    """周日 20:00 是一期的结束：正好 20:00 算这一期到了，差一秒算上一期；补做、跨年都对。"""
    at = lambda text: datetime.strptime(text, '%Y-%m-%d %H:%M:%S')
    assert week_end_before(at('2026-11-22 20:00:00')) == at('2026-11-22 20:00:00')   # 正好 20:00 算这一期到了
    assert week_end_before(at('2026-11-22 19:59:59')) == at('2026-11-15 20:00:00')
    assert week_end_before(at('2026-11-25 09:00:00')) == at('2026-11-22 20:00:00')   # 周三补做
    assert week_end_before(at('2027-01-03 20:10:00')) == at('2027-01-03 20:00:00')   # 跨年


def test_window_and_week_starts():
    """窗口是 [上周日 20:00, 本周日 20:00)；week_starts 从早到晚列出各周的开始。"""
    end = datetime(2026, 11, 22, 20)
    assert window(end) == {'start': '2026-11-15 20:00:00', 'end': '2026-11-22 20:00:00',
                           'prev_start': '2026-11-08 20:00:00', 'monday': '2026-11-16', 'sunday': '2026-11-22'}
    assert week_starts(end, 3) == ['2026-11-01 20:00:00', '2026-11-08 20:00:00', '2026-11-15 20:00:00']
    assert window(datetime(2026, 12, 6, 20))['monday'] == '2026-11-30'               # 跨月


def test_streak_calendar_percent():
    """连续录入周数、42 天日历、正确率（1 位小数，分母 0 为 None）。"""
    assert entry_streak([72, 58, 46, 218, 0, 54]) == 4
    assert entry_streak([0, 5]) == 0 and entry_streak([]) == 0
    days = calendar_days('2026-11-22', {'2026-11-17'}, {'2026-11-17', '2026-10-12'})
    assert len(days) == 42 and days[0]['date'] == '2026-10-12' and days[-1]['date'] == '2026-11-22'
    assert days[0] == {'date': '2026-10-12', 'entered': False, 'dictated': True}
    assert [d for d in days if d['date'] == '2026-11-17'][0] == {'date': '2026-11-17', 'entered': True, 'dictated': True}
    assert percent(34, 70) == 48.6 and percent(0, 0) is None


def test_known_before_uses_entered_for_questions():
    """错题按录入时间算"系统知道的时间"，卷子日期再早也不算。"""
    late = {'kind': 'wrong', 'source': 'question', 'at': '2026-11-10', 'entered': '2026-11-23 09:00:00.000000', 'qid': 1}
    paper = {'kind': 'right', 'source': 'practice', 'at': '2026-11-20 18:00:00.000000', 'qid': 2}
    assert known_before([late, paper], '2026-11-22 20:00:00') == [paper]      # 卷子日期早、但录入在之后：不算
    assert known_at(late) == '2026-11-23 09:00:00.000000'


def test_week_activity_and_classify():
    """本周有没有做对/做错，以及考点变好、变差、新出现的判定。"""
    start, end = '2026-11-15 20:00:00', '2026-11-22 20:00:00'
    right = {'kind': 'right', 'source': 'practice', 'at': '2026-11-18 10:00:00.000000'}
    adjust = {'kind': 'adjust', 'source': 'adjust', 'at': '2026-11-18 10:00:00.000000', 'adjust': 'set_mastered'}
    assert week_activity([right], start, end) == {'right': True, 'wrong': False}
    assert week_activity([adjust], start, end) == {'right': False, 'wrong': False}
    assert classify_change('weak', 'fair', 'fair', {'right': True, 'wrong': False}) == 'improved'
    assert classify_change('weak', 'mastered', 'weak', {'right': False, 'wrong': False}) is None   # 只有手动调整：不算变好
    # 本周手动调整 + 一次做对：去掉调整后没升档，不算变好；去掉调整后也升档，算变好
    assert classify_change('weak', 'mastered', 'weak', {'right': True, 'wrong': False}) is None
    assert classify_change('weak', 'mastered', 'fair', {'right': True, 'wrong': False}) == 'improved'
    assert classify_change('good', 'fair', 'fair', {'right': False, 'wrong': True}) == 'dropped'
    assert classify_change('good', 'fair', 'good', {'right': False, 'wrong': True}) is None      # 只因手动调整降档
    assert classify_change('good', 'fair', 'fair', {'right': False, 'wrong': False}) is None
    assert classify_change('unlearned', 'weak', 'weak', {'right': False, 'wrong': True}) == 'new_weak'
    assert classify_change('unlearned', 'fair', 'fair', {'right': True, 'wrong': False}) is None
    assert classify_change('fair', 'fair', 'fair', {'right': True, 'wrong': False}) is None
    # 去掉本周的手动调整，更早的调整保留
    old_adjust = dict(adjust, at='2026-11-10 10:00:00.000000')
    assert drop_week_adjusts([old_adjust, right, adjust], start, end) == [old_adjust, right]


def test_pick_target():
    """下一个要攻克的：薄弱或一般、有待重做题、掌握度最低；并列取待重做多的。"""
    leaves = [{'id': 1, 'name': '甲', 'value': 0.35, 'status': 'weak', 'pending': 1},
              {'id': 2, 'name': '乙', 'value': 0.20, 'status': 'weak', 'pending': 0},      # 没有待重做的题：不选
              {'id': 3, 'name': '丙', 'value': 0.35, 'status': 'weak', 'pending': 3},
              {'id': 4, 'name': '丁', 'value': 0.80, 'status': 'good', 'pending': 2}]      # 档位较好：不选
    assert pick_target(leaves)['id'] == 3                                                  # 并列取待重做多的
    assert pick_target([leaves[1], leaves[3]]) is None


def test_graduated_in_week():
    """本周毕业：end 时毕业、start 时没有，且本周有做对的结果；直接设为掌握不算。"""
    start, end = '2026-11-15 20:00:00', '2026-11-22 20:00:00'
    r = lambda at, correct: {'at': at, 'order': 0, 'correct': correct}
    histories = {
        1: {'entered': '2026-11-01 10:00:00', 'waives': [],                                # 本周连对第 2 次：算
            'results': [r('2026-11-10 10:00:00', True), r('2026-11-18 10:00:00', True)]},
        2: {'entered': '2026-11-01 10:00:00', 'waives': [],                                # 上周就毕业了：不算
            'results': [r('2026-11-05 10:00:00', True), r('2026-11-10 10:00:00', True)]},
        3: {'entered': '2026-11-01 10:00:00', 'waives': ['2026-11-18 10:00:00'], 'results': []},   # 只是被设为掌握：不算
        4: {'entered': '2026-11-01 10:00:00', 'waives': [],                                # 第 2 次做对在 T_end 之后：不算
            'results': [r('2026-11-18 10:00:00', True), r('2026-11-23 10:00:00', True)]},
    }
    assert graduated_in_week(histories, start, end) == 1
    # 本周只有 1 次做对（连对 1），又被设为掌握：毕业只因设为掌握，不算
    waived = {5: {'entered': '2026-11-01 10:00:00', 'waives': ['2026-11-19 10:00:00'],
                  'results': [r('2026-11-18 10:00:00', True)]}}
    assert graduated_in_week(waived, start, end) == 0


# ---------------------------------------------------------------- 任务 4：文字检查、兜底文字、提示词


def sample_facts():
    """设计里那份示例 facts：本周日历亮 4 格，趋势补满 6 项。"""
    entered = {'2026-10-13', '2026-11-18'}
    dictated = {'2026-11-16', '2026-11-18', '2026-11-20', '2026-11-21'}
    mondays = ['2026-10-12', '2026-10-19', '2026-10-26', '2026-11-02', '2026-11-09', '2026-11-16']
    trend = [{'monday': monday, 'count': 25, 'accuracy': 36.0} for monday in mondays]
    return {
        'schema_version': 1,
        'week': {'start': '2026-11-15 20:00:00', 'end': '2026-11-22 20:00:00',
                 'monday': '2026-11-16', 'sunday': '2026-11-22', 'number': 6},
        'quiet': False,
        'entries': {'count': 72, 'prev_count': 58, 'streak_weeks': 4,
                    'by_subject': [{'subject_id': 1, 'name': '数学', 'count': 72}]},
        'calendar': calendar_days('2026-11-22', entered, dictated),
        'dictation': {'count': 70, 'correct': 34, 'accuracy': 48.6, 'days': 4,
                      'prev_count': 250, 'prev_accuracy': 49.6, 'trend': trend},
        'practice': {'papers': 0, 'questions': 0, 'correct': 0, 'accuracy': None,
                     'prev_papers': 4, 'prev_accuracy': 51.6, 'graduated': 0},
        'subjects': [{'subject_id': 1, 'name': '数学',
                      'status_counts': {'mastered': 5, 'good': 0, 'fair': 8, 'weak': 35, 'unlearned': 27},
                      'improved': [{'id': 101, 'name': '合并同类项'}], 'dropped': [], 'new_weak': [],
                      'modules': [{'id': 100, 'name': '整式', 'before': 0.4, 'after': 0.52}],
                      'target': {'id': 102, 'name': '去括号'}}],
    }


def good_text():
    """一份能通过检查的文字。"""
    return {'cheer': '「合并同类项」被你拿下一截，这周的你更稳了！',
            'summary': '这周你有 4 天坚持默写单词，一共写了 70 条。「合并同类项」变好了，「去括号」下周我们先攻它。',
            'captions': {'calendar': '这周亮了 4 格。', 'points': {'1': '「合并同类项」变亮了。'},
                         'dictation': '默写了 70 条。', 'practice': '这周还没有做练习卷。'}}


def test_check_text_accepts_good():
    assert check_text(good_text(), brief_of(sample_facts()), []) is None


def test_check_text_rejects():
    brief = brief_of(sample_facts())

    def broken(change):
        text = good_text()
        change(text)
        return check_text(text, brief, ['上一期的鼓励'])
    assert broken(lambda t: t.update(summary='这周你默写了 5 天。')) is not None                 # 5 不是给过的数字
    assert broken(lambda t: t.update(summary='「因式分解」变好了。')) is not None                # 没给过的考点名
    assert broken(lambda t: t.update(summary='爸爸妈妈也很开心。')) is not None                  # 提到了父母
    assert broken(lambda t: t.update(summary='「去括号」还是薄弱的。')) is not None              # 不说“薄弱”
    assert broken(lambda t: t.update(cheer='上一期的鼓励')) is not None                          # 和最近的重复
    assert broken(lambda t: t.update(cheer='很' * 31)) is not None                               # 超长
    assert broken(lambda t: t['captions'].pop('dictation')) is not None                          # 缺字段
    assert broken(lambda t: t['captions'].update(points={})) is not None                         # 少了学科的那一句
    assert check_text('不是字典', brief, []) is not None
    assert check_text(None, brief, []) is not None


def test_check_reason_does_not_echo_text():
    brief = brief_of(sample_facts())
    text = good_text()
    text['summary'] = '这周你默写了 9527 天，「秘密考点」。'
    reason = check_text(text, brief, [])
    assert reason and '9527' not in reason and '秘密考点' not in reason


def test_brief_and_allowed():
    brief = brief_of(sample_facts())
    assert brief['calendar_days_lit'] == 4
    assert brief['improved_total'] == 1
    assert 'calendar' not in brief and 'trend' not in brief['dictation']
    numbers = allowed_numbers(brief)
    for value in ('70', '4', '48.6', '49', '11', '22', '16', '6'):
        assert value in numbers, value
    assert '0.52' not in numbers and '0.4' not in numbers                                        # 模块前后值不放进去
    assert allowed_names(brief) == {'数学', '合并同类项', '去括号', '整式'}
    assert 'dropped' not in brief['subjects'][0] and 'new_weak' not in brief['subjects'][0]


def test_dropped_names_not_allowed():
    """变差、新出现的考点名不给模型，文字里点名它们会被拒。"""
    facts = sample_facts()
    facts['subjects'][0]['dropped'] = [{'id': 103, 'name': '因式分解'}]
    facts['subjects'][0]['new_weak'] = [{'id': 104, 'name': '一元一次方程'}]
    brief = brief_of(facts)
    assert brief['subjects'][0]['dropped_count'] == 1                                            # 数量还在
    assert '因式分解' not in allowed_names(brief) and '一元一次方程' not in allowed_names(brief)
    for name in ('因式分解', '一元一次方程'):
        text = good_text()
        text['captions']['points']['1'] = '「%s」要多练。' % name
        assert check_text(text, brief, []) is not None, name


def test_fallback_text_passes_own_check():
    brief = brief_of(sample_facts())
    text = fallback_text(brief, [])
    assert check_text(text, brief, []) is None
    assert text['cheer'] in FALLBACK_CHEERS
    used = list(FALLBACK_CHEERS[:5])
    assert fallback_text(brief, used)['cheer'] not in used                                       # 避开最近用过的


def test_fallback_cheers_pass_check():
    brief = brief_of(sample_facts())
    assert len(FALLBACK_CHEERS) == 12
    for cheer in FALLBACK_CHEERS:
        assert '薄弱' not in cheer, cheer
        text = good_text()
        text['cheer'] = cheer
        assert check_text(text, brief, []) is None, cheer


def test_fallback_quiet_week():
    facts = sample_facts()
    facts['quiet'] = True
    facts['entries'].update(count=0, streak_weeks=0)
    facts['dictation'].update(count=0, correct=0, accuracy=None, days=0)
    for day in facts['calendar'][-7:]:
        day.update(entered=False, dictated=False)
    for subject in facts['subjects']:
        subject.update(improved=[], dropped=[], new_weak=[])
    brief = brief_of(facts)
    text = fallback_text(brief, [])
    assert check_text(text, brief, []) is None
    assert '歇' in text['summary']                                                               # 照实说，不硬夸

def fallback_plain_week(count):
    """不安静、没默写、没变好、没毕业、没目标，只做了 1 份练习卷的一周。"""
    facts = sample_facts()
    facts['entries'].update(count=count, streak_weeks=0)
    facts['dictation'].update(count=0, correct=0, accuracy=None, days=0)
    facts['practice'].update(papers=1, questions=5, correct=3, accuracy=60.0, graduated=0)
    for subject in facts['subjects']:
        subject.update(improved=[], dropped=[], new_weak=[], target=None)
    brief = brief_of(facts)
    return brief, fallback_text(brief, [])


def test_fallback_summary_zero_entries_never_says_zero():
    brief, text = fallback_plain_week(0)
    assert text['summary'] == '这周你做了练习，继续保持。'
    assert check_text(text, brief, []) is None


def test_fallback_summary_with_entries_keeps_old_sentence():
    brief, text = fallback_plain_week(3)
    assert text['summary'] == '这周录了 3 道错题，把它们一道道弄懂就好。'
    assert check_text(text, brief, []) is None



def test_prompt_carries_rules():
    prompt = PromptLibrary()._build_weekly_report_prompt(brief_of(sample_facts()), ['上一期的鼓励'])
    for needle in ('你', '「」', '阿拉伯数字', '上一期的鼓励', '合并同类项', '去括号', '不要用“薄弱”这个词'):
        assert needle in prompt
    assert prompt.count('薄弱') == 1                                                              # 只在那条规则里出现


# ---------------------------------------------------------------- 任务 5：取数 build_facts

WEEK_END = datetime(2026, 11, 22, 20)
add_question = starmap_test.add_question
add_paper = starmap_test.add_paper
add_set = targeted_test.add_set
run = starmap_test.run


def add_dictation(c, word_id, reviewed_at, correct, review_type=1):
    """插入一条单词默写记录；单词不存在时先插一个。"""
    if c.execute('SELECT id FROM word WHERE id=?', (word_id,)).fetchone() is None:
        c.execute("INSERT INTO word(id,english,chinese,review_count,correct_count,deleted,created_at,updated_at) "
                  "VALUES(?,?,'词',0,0,0,'2026-10-01 08:00:00','2026-10-01 08:00:00')", (word_id, 'word%d' % word_id))
    c.execute('INSERT INTO word_review_log(word_id,is_correct,review_type,reviewed_at,deleted) VALUES(?,?,?,?,0)',
              (word_id, correct, review_type, reviewed_at))


def add_adjustment(c, point_id, kind, created_at):
    """插入一条手动调整掌握度的记录。"""
    c.execute('INSERT INTO mastery_adjustment(student_id,knowledge_point_id,kind,created_at,deleted) VALUES(1,?,?,?,0)',
              (point_id, kind, created_at))


def facts_of(db):
    """用 db（异步接口）算 WEEK_END 那一期的 facts。"""
    from weekly import build_facts
    return run(build_facts(db, starmap_test.request_for(db), WEEK_END))


def facts_for(c):
    """提交 c 上的改动，再算 facts。"""
    c.commit()
    return facts_of(starmap_test.adapter(c))


def test_facts_entries_and_calendar():
    """录入按录入时间算周：卷子日期在上周、本周才录入的算本周；T_end 之后的不算。"""
    c = build_db()
    add_question(c, 1, 1, '2026-11-17 10:00:00.000000', [101])                 # 本周
    add_paper(c, 1, 1, '2026-11-10')
    add_question(c, 2, 1, '2026-11-16 09:00:00.000000', [101], paper_id=1)     # 卷子上周、本周录入
    add_question(c, 3, 1, '2026-11-10 10:00:00.000000', [102])                 # 上周
    add_question(c, 4, 1, '2026-11-22 21:00:00.000000', [102])                 # T_end 之后
    add_question(c, 5, 1, '2026-11-18 10:00:00.000000', [102], status='pending')   # 没核对：不算
    facts = facts_for(c)
    assert facts['schema_version'] == 1
    assert facts['week'] == {'start': '2026-11-15 20:00:00', 'end': '2026-11-22 20:00:00',
                             'monday': '2026-11-16', 'sunday': '2026-11-22', 'number': 1}
    assert facts['entries']['count'] == 2 and facts['entries']['prev_count'] == 1
    assert facts['entries']['streak_weeks'] == 2
    assert facts['entries']['by_subject'] == [{'subject_id': 1, 'name': '数学', 'count': 2}]
    lit = [d['date'] for d in facts['calendar'] if d['entered']]
    assert '2026-11-23' not in lit and len(facts['calendar']) == 42
    assert lit == ['2026-11-10', '2026-11-16', '2026-11-17'], lit
    assert facts['quiet'] is False


def test_facts_sunday_night_goes_to_next_week_count_but_same_day_cell():
    """上周日 20:00 之后默写的：条数算本周，格子亮在上周日，"默写 N 天"不含它。"""
    c = build_db()
    for word_id in (1, 2, 3):
        add_dictation(c, word_id, '2026-11-15 21:00:00.000000', True)
    facts = facts_for(c)
    assert facts['dictation']['count'] == 3 and facts['dictation']['days'] == 0
    assert [d for d in facts['calendar'] if d['date'] == '2026-11-15'][0]['dictated'] is True
    assert facts['quiet'] is False


def test_facts_dictation_only_counts_type_one():
    """只算默写题型（review_type=1）：选择题型不算。"""
    c = build_db()
    for index, correct in enumerate((True, True, True, False)):
        add_dictation(c, index + 1, '2026-11-18 19:00:0%d.000000' % index, correct)
    add_dictation(c, 9, '2026-11-18 19:30:00.000000', True, review_type=2)
    add_dictation(c, 9, '2026-11-19 19:30:00.000000', True, review_type=2)
    add_dictation(c, 1, '2026-11-10 19:00:00.000000', False)                   # 上周 1 条
    facts = facts_for(c)
    dictation = facts['dictation']
    assert (dictation['count'], dictation['correct'], dictation['accuracy']) == (4, 3, 75.0)
    assert dictation['days'] == 1 and (dictation['prev_count'], dictation['prev_accuracy']) == (1, 0.0)
    assert len(dictation['trend']) == 6 and dictation['trend'][-1]['count'] == 4
    assert dictation['trend'][-1]['monday'] == '2026-11-16'
    assert dictation['trend'][0] == {'monday': '2026-10-12', 'count': 0, 'accuracy': None}
    assert [d['date'] for d in facts['calendar'] if d['dictated']] == ['2026-11-10', '2026-11-18']


def test_facts_point_changes():
    """考点变好、新出现、手动调整不算变好、下一个要攻克的。"""
    c = build_db()
    # 教材：4.1 → 112，4.2 → 111，进度 4.1：111 没有记录时算没学
    starmap_test.add_section(c, 1, 1, 4, '4.1', 41, [112])
    starmap_test.add_section(c, 2, 1, 4, '4.2', 42, [111])
    starmap_test.set_config(c, 'starmap', {'progress': {'1': '4.1'}})
    # 考点 101：上周前录入 2 道错题（薄弱 0.2），本周练习卷里两道都做对（一般 0.5）
    add_question(c, 1, 1, '2026-11-01 10:00:00.000000', [101])
    add_question(c, 2, 1, '2026-11-02 10:00:00.000000', [101])
    add_set(c, 1, '2026-11-17 10:00:00.000000', '2026-11-18 10:00:00.000000',
            [(1, True, 'original'), (2, True, 'original')])
    # 考点 102：只在本周被"直接设为掌握"
    add_adjustment(c, 102, 'set_mastered', '2026-11-19 10:00:00.000000')
    # 考点 111：本周新录入错题，之前没有记录（之前算没学）
    add_question(c, 3, 1, '2026-11-20 10:00:00.000000', [111])
    facts = facts_for(c)
    math = facts['subjects'][0]
    assert [s['subject_id'] for s in facts['subjects']] == [1, 2]
    assert [p['id'] for p in math['improved']] == [101]
    assert math['improved_count'] == 1 and math['dropped'] == [] and math['dropped_count'] == 0
    assert [p['id'] for p in math['new_weak']] == [111]
    assert math['status_counts']['mastered'] >= 1                      # 手动调整照实显示在环形图里
    leaf_total = len([p for p in starmap_test.SEED_POINTS if p[2] == 1 and p[3] == 2])   # 数学的二级考点数
    assert sum(math['status_counts'].values()) == leaf_total
    assert {m['id'] for m in math['modules']} <= {100, 110, 120}
    assert math['target'] is None or math['target']['id'] != 102
    assert math['target'] == {'id': 111, 'name': '线段和差与中点'}


def test_facts_adjust_plus_practice_not_improved():
    """本周“直接设为掌握”又做对一题：这一题单独升不了档，不算变好；对照组做对两题能升档，照样算变好。"""
    for right_count, expected in ((1, []), (2, [101])):
        c = build_db()
        # 考点 101：上周前录入 2 道错题（薄弱）
        add_question(c, 1, 1, '2026-11-01 10:00:00.000000', [101])
        add_question(c, 2, 1, '2026-11-02 10:00:00.000000', [101])
        items = [(qid, True, 'original') for qid in (1, 2)[:right_count]]
        add_set(c, 1, '2026-11-17 10:00:00.000000', '2026-11-18 10:00:00.000000', items)
        add_adjustment(c, 101, 'set_mastered', '2026-11-19 10:00:00.000000')
        math = facts_for(c)['subjects'][0]
        assert [p['id'] for p in math['improved']] == expected, (right_count, math['improved'])
        assert math['improved_count'] == len(expected)
        assert math['status_counts']['mastered'] == 1                     # 环形图照实显示调整后的结果


def test_facts_practice_and_graduated():
    """本周批改 1 份（3 题对 2 题），其中一道是连对第 2 次；上周批改 1 份（2 题对 1 题）。"""
    c = build_db()
    for qid in (1, 2, 3):
        add_question(c, qid, 1, '2026-11-01 10:00:00.000000', [101])
    add_set(c, 1, '2026-11-09 10:00:00.000000', '2026-11-10 10:00:00.000000',
            [(1, True, 'original'), (2, False, 'original')])
    add_set(c, 2, '2026-11-17 10:00:00.000000', '2026-11-18 10:00:00.000000',
            [(1, True, 'original'), (2, False, 'original'), (3, True, 'original')])
    add_set(c, 3, '2026-11-19 10:00:00.000000', None, [(2, None, 'original')])         # 没批改：不算
    add_set(c, 4, '2026-11-19 10:00:00.000000', '2026-11-19 12:00:00.000000',
            [(2, True, 'original')], deleted=1)                                         # 已删除：不算
    facts = facts_for(c)
    assert facts['practice'] == {'papers': 1, 'questions': 3, 'correct': 2, 'accuracy': 66.7,
                                 'prev_papers': 1, 'prev_accuracy': 50.0, 'graduated': 1}


def test_facts_quiet_week():
    """库里只有考点目录：安静的一周，比例都是 None，日历全空。"""
    facts = facts_for(build_db())
    assert facts['quiet'] is True and facts['entries']['streak_weeks'] == 0
    assert facts['dictation']['accuracy'] is None and facts['practice']['accuracy'] is None
    assert all(not d['entered'] and not d['dictated'] for d in facts['calendar'])
    assert facts['entries']['by_subject'] == [] and facts['practice']['graduated'] == 0


def budget_fixture(extra):
    """查询条数测试的库：extra 为真时多 7 个考点、每个 2 道旧错题本周都做对（7 个考点变好）。"""
    c = build_db()
    c.execute("INSERT INTO weekly_report(week_end,status,created_at,updated_at) "
              "VALUES('2026-11-15 20:00:00','done','2026-11-15 20:00:05','2026-11-15 20:00:05')")
    add_question(c, 1, 1, '2026-11-17 10:00:00.000000', [101])
    add_dictation(c, 1, '2026-11-18 19:00:00.000000', True)
    if extra:
        for index in range(7):
            point_id, qid = 301 + index, 100 + 2 * index
            c.execute('INSERT INTO knowledge_point(id,name,name_key,subject_id,level,parent_id,sort_order,deleted,'
                      'created_at) VALUES(?,?,?,1,2,120,?,0,CURRENT_TIMESTAMP)',
                      (point_id, '考点%d' % index, 'kp%d' % index, point_id))
            add_question(c, qid, 1, '2026-11-01 10:00:00.000000', [point_id])
            add_question(c, qid + 1, 1, '2026-11-01 11:00:00.000000', [point_id])
            add_set(c, 100 + index, '2026-11-17 10:00:00.000000', '2026-11-18 10:00:00.000000',
                    [(qid, True, 'original'), (qid + 1, True, 'original')])
            add_dictation(c, 10 + index, '2026-11-19 19:00:00.000000', False)
        starmap_test.set_config(c, 'app', {'default_grade': 6, 'default_semester': 1})
    c.commit()
    return c


def test_facts_query_budget():
    """build_facts 一次最多 30 条查询，并且不随题目数、考点数变化；期数 = 更早的未删除周报数 + 1。"""
    small = starmap_test.CountingDB(budget_fixture(False))
    facts_small = facts_of(small)
    big = starmap_test.CountingDB(budget_fixture(True))
    facts_big = facts_of(big)
    counted_queries = big.calls
    assert counted_queries <= 30, counted_queries
    assert small.calls == big.calls, (small.calls, big.calls)
    assert facts_small['week']['number'] == 2
    math = facts_big['subjects'][0]
    assert math['improved_count'] == 7 and len(math['improved']) == 5            # 列表最多 5 个，计数是真实总数
    assert brief_of(facts_big)['subjects'][0]['improved_count'] == 7
    assert brief_of(facts_big)['improved_total'] == 7


def test_report_number_skips_stuck_new():
    """期数只数更早的、已算好数字的期：一直停在 new 的、已删除的都不算，不跳号。"""
    c = build_db()
    rows = [('2026-11-01 20:00:00', 'done', 0), ('2026-11-08 20:00:00', 'new', 0),
            ('2026-11-15 20:00:00', 'facts_ready', 0), ('2026-10-25 20:00:00', 'done', 1)]
    for week_end, status, deleted in rows:
        c.execute("INSERT INTO weekly_report(week_end,status,created_at,updated_at,deleted) "
                  "VALUES(?,?,'2026-11-01 20:00:05','2026-11-01 20:00:05',?)", (week_end, status, deleted))
    assert facts_for(c)['week']['number'] == 3


# ---------------------------------------------------------------- 任务 6：推进一步和接口


NOW = datetime(2026, 11, 22, 20, 30)          # 本期刚结束半小时
FAKE_CHEER = '（假模型）这周也在一点点变好。'


def brief_in_prompt(prompt):
    """从提示词的"本周数据"一节取回给模型看的 brief。"""
    part = prompt.split('## 本周数据\n', 1)[1].split('\n\n## 最近几期', 1)[0]
    return json.loads(part)


def model_text(brief, cheer=FAKE_CHEER):
    """一份能通过检查的模型文字：兜底文字换一句鼓励。"""
    return dict(fallback_text(brief, []), cheer=cheer)


class FakeModel:
    """可编程的假文本模型：按 script 依次返回文字或抛异常；script 用完后返回一份能通过检查的文字。"""

    def __init__(self):
        self.calls = 0
        self.script = []
        self.prompts = []

    async def __call__(self, request, prompt, max_tokens=None, temperature=None, parse=None):
        self.calls += 1
        self.prompts.append(prompt)
        if self.script:
            answer = self.script.pop(0)
            if isinstance(answer, Exception):
                raise answer
            return answer
        return model_text(brief_in_prompt(prompt))


class CountingAll(starmap_test.SQLiteDB):
    """记录全部 SQL 条数（读和写都算）的数据库适配器。"""

    def __init__(self, connection):
        super().__init__(connection)
        self.calls = 0

    async def all(self, sql, parameters=()):
        self.calls += 1
        return await super().all(sql, parameters)

    async def first(self, sql, parameters=()):
        self.calls += 1
        return await super().first(sql, parameters)

    async def run(self, sql, parameters=()):
        self.calls += 1
        return await super().run(sql, parameters)


def advance_setup(c=None):
    """准备推进用的库、请求和假模型：weekly 模块直接用传入的 db，模型换成假的。"""
    import weekly
    c = c or build_db()
    c.commit()
    db = CountingAll(c)
    request = starmap_test.request_for(db)
    weekly.Database = lambda binding: binding
    fake = FakeModel()
    weekly.generate_json = fake
    return c, db, request, fake


def stored_brief(c):
    """读出库里这一期 facts 对应的 brief。"""
    return brief_of(json.loads(c.execute("SELECT facts FROM weekly_report WHERE week_end='2026-11-22 20:00:00'").fetchone()[0]))


def test_advance_two_steps_then_done():
    """第一次算数字、第二次写文字（最多 6 条查询），做完后再调什么都不动。"""
    from weekly import advance_once
    c, db, request, fake = advance_setup()
    first = run(advance_once(request, NOW))
    assert first['status'] == 'facts_ready' and first['busy'] is False and fake.calls == 0
    db.calls = 0
    second = run(advance_once(request, NOW))
    queries_in_second_step = db.calls
    assert second['status'] == 'done' and fake.calls == 1, second
    assert queries_in_second_step <= 6, queries_in_second_step   # 写文字这一步最多 6 条查询
    row = c.execute('SELECT status,text_source,attempts,week_end FROM weekly_report').fetchone()
    assert tuple(row) == ('done', 'model', 0, '2026-11-22 20:00:00')
    assert json.loads(c.execute('SELECT text FROM weekly_report').fetchone()[0])['cheer'] == FAKE_CHEER
    assert c.execute('SELECT step_started_at FROM weekly_report').fetchone()[0] is None
    third = run(advance_once(request, NOW))
    assert third == {'id': first['id'], 'status': 'done', 'busy': False} and fake.calls == 1   # 做完了不再动
    assert c.execute('SELECT COUNT(*) FROM weekly_report').fetchone()[0] == 1


def test_advance_claims_once():
    """刚被认领的一步再调返回正忙，不调模型；认领超过 STALE_SECONDS 后可以重新认领并做完。"""
    from weekly import STALE_SECONDS, advance_once
    c, db, request, fake = advance_setup()
    report_id = run(advance_once(request, NOW))['id']
    c.execute('UPDATE weekly_report SET step_started_at=?', (NOW.strftime('%Y-%m-%d %H:%M:%S'),))
    c.commit()
    assert run(advance_once(request, NOW)) == {'id': report_id, 'status': 'facts_ready', 'busy': True}
    assert fake.calls == 0
    stale = NOW - timedelta(seconds=STALE_SECONDS + 1)
    c.execute('UPDATE weekly_report SET step_started_at=?', (stale.strftime('%Y-%m-%d %H:%M:%S'),))
    c.commit()
    assert run(advance_once(request, NOW))['status'] == 'done'
    assert fake.calls == 1


def test_bad_text_falls_back_after_three():
    """写文字连续失败 3 次（检查不过、没配模型、模型请求失败）后用兜底文字，error 只有简短原因。"""
    from weekly import advance_once
    c, db, request, fake = advance_setup()
    run(advance_once(request, NOW))                                  # 算数字
    brief = stored_brief(c)
    bad_number_text = dict(model_text(brief), summary='这周你做了 999 道题。')
    fake.script = [bad_number_text, HTTPException(503, '请先配置文本模型'),
                   HTTPException(502, '文本模型请求失败 sk-secret')]
    for expected_attempts, expected_error in ((1, '出现了没给过的数字'), (2, '文本模型请求失败（503）')):
        assert run(advance_once(request, NOW))['status'] == 'facts_ready'
        row = c.execute('SELECT attempts,error FROM weekly_report').fetchone()
        assert tuple(row) == (expected_attempts, expected_error), tuple(row)
    assert run(advance_once(request, NOW))['status'] == 'done'       # 第 3 次失败：用兜底
    row = c.execute('SELECT text_source,attempts,error,text FROM weekly_report').fetchone()
    assert row[0] == 'fallback' and row[1] == 3 and row[2], tuple(row)
    assert 'sk-' not in row[2] and '502' in row[2], row[2]
    assert check_text(json.loads(row[3]), brief, []) is None
    assert fake.calls == 3
    assert run(advance_once(request, NOW))['status'] == 'done' and fake.calls == 3


def test_model_errors_never_echo_text():
    """模型异常和检查失败写进 error 的都是固定短句，不带异常原文。"""
    from weekly import advance_once
    c, db, request, fake = advance_setup()
    run(advance_once(request, NOW))
    fake.script = [RuntimeError('sk-leak raw model output')]
    run(advance_once(request, NOW))
    error = c.execute('SELECT error FROM weekly_report').fetchone()[0]
    assert error and 'sk-' not in error and 'raw' not in error, error


def test_recent_cheers_are_passed_and_avoided():
    """最近几期用过的鼓励语交给模型；模型又写了同一句算失败，下一次重写。"""
    from weekly import advance_once
    c = build_db()
    old_text = json.dumps({'cheer': '旧的鼓励', 'summary': '旧', 'captions': {}}, ensure_ascii=False)
    c.execute("INSERT INTO weekly_report(week_end,status,text,text_source,created_at,updated_at) "
              "VALUES('2026-11-15 20:00:00','done',?,'model','2026-11-15 20:00:05','2026-11-15 20:10:05')",
              (old_text,))
    c, db, request, fake = advance_setup(c)
    run(advance_once(request, NOW))
    brief = stored_brief(c)
    fake.script = [model_text(brief, cheer='旧的鼓励')]
    assert run(advance_once(request, NOW))['status'] == 'facts_ready'
    assert '旧的鼓励' in fake.prompts[0]
    row = c.execute("SELECT attempts,error FROM weekly_report WHERE week_end='2026-11-22 20:00:00'").fetchone()
    assert row[0] == 1 and row[1] == '鼓励语和最近几期重复', tuple(row)
    assert run(advance_once(request, NOW))['status'] == 'done' and fake.calls == 2


def test_facts_error_keeps_new():
    """算数字出错：error 写异常类型名，状态还是 new，清掉认领，异常继续抛出。"""
    import weekly
    c, db, request, fake = advance_setup()
    original = weekly.build_facts

    async def broken(db, request, week_end):
        raise ValueError('secret detail')

    weekly.build_facts = broken
    try:
        try:
            run(weekly.advance_once(request, NOW))
            assert False, '应该抛出'
        except ValueError:
            pass
    finally:
        weekly.build_facts = original
    row = c.execute('SELECT status,error,step_started_at FROM weekly_report').fetchone()
    assert tuple(row) == ('new', 'ValueError', None), tuple(row)
    assert run(weekly.advance_once(request, NOW))['status'] == 'facts_ready'


def test_list_and_detail():
    """列表只列算好数字的期，新的在前；due 看最近一期是否做完；详情不存在返回 404。"""
    import weekly
    c = build_db()
    old_facts = json.dumps({'week': {'number': 1}}, ensure_ascii=False)
    old_text = json.dumps({'cheer': '旧的鼓励'}, ensure_ascii=False)
    c.execute("INSERT INTO weekly_report(week_end,status,facts,text,text_source,created_at,updated_at) "
              "VALUES('2026-11-15 20:00:00','done',?,?,'fallback','2026-11-15 20:00:05','2026-11-15 20:10:05')",
              (old_facts, old_text))
    c.execute("INSERT INTO weekly_report(week_end,created_at,updated_at) "
              "VALUES('2026-11-22 20:00:00','2026-11-22 20:00:05','2026-11-22 20:00:05')")
    c.execute("INSERT INTO weekly_report(week_end,status,facts,created_at,updated_at,deleted) "
              "VALUES('2026-11-08 20:00:00','done','{}','2026-11-08 20:00:05','2026-11-08 20:00:05',1)")
    c, db, request, fake = advance_setup(c)
    listing = run(weekly.list_reports(request, NOW))
    old_id = c.execute("SELECT id FROM weekly_report WHERE week_end='2026-11-15 20:00:00'").fetchone()[0]
    assert listing == {'items': [{'id': old_id, 'number': 1, 'monday': '2026-11-09', 'sunday': '2026-11-15',
                                  'status': 'done'}], 'due': True}, listing
    detail = run(weekly.report_detail(request, old_id))
    assert detail == {'id': old_id, 'status': 'done', 'number': 1, 'monday': '2026-11-09', 'sunday': '2026-11-15',
                      'facts': {'week': {'number': 1}}, 'text': {'cheer': '旧的鼓励'}, 'text_source': 'fallback'}
    new_id = c.execute("SELECT id FROM weekly_report WHERE week_end='2026-11-22 20:00:00'").fetchone()[0]
    fresh = run(weekly.report_detail(request, new_id))
    assert fresh['status'] == 'new' and fresh['text'] is None and fresh['facts'] is None and fresh['number'] is None
    try:
        run(weekly.report_detail(request, 999))
        assert False, '应该 404'
    except HTTPException as error:
        assert error.status_code == 404 and error.detail == '周报不存在'
    run(weekly.advance_once(request, NOW))
    run(weekly.advance_once(request, NOW))
    listing = run(weekly.list_reports(request, NOW))
    assert listing['due'] is False and [item['status'] for item in listing['items']] == ['done', 'done']
    assert listing['items'][0]['number'] == 2 and listing['items'][0]['sunday'] == '2026-11-22'


def test_advance_targets_last_ended_week():
    """周三补做：目标是刚过去的那个周日 20:00。"""
    from weekly import advance_once
    c, db, request, fake = advance_setup()
    assert run(advance_once(request, datetime(2026, 11, 25, 9)))['status'] == 'facts_ready'
    assert c.execute('SELECT week_end FROM weekly_report').fetchone()[0] == '2026-11-22 20:00:00'


def test_router_paths():
    """三个接口挂在 /api/weekly-reports 下。"""
    from weekly import router
    paths = {(route.path, tuple(sorted(route.methods))) for route in router.routes}
    assert paths == {('/api/weekly-reports', ('GET',)), ('/api/weekly-reports/advance', ('POST',)),
                     ('/api/weekly-reports/{report_id}', ('GET',))}, paths


# ---------------------------------------------------------------- 任务 7：定时入口


def scheduled_setup():
    """准备定时入口用的库：weekly 和 auth 都直接用传入的 db，模型换成假的。返回 (连接, db, 还原函数)。"""
    import auth
    c, db, request, fake = advance_setup()
    original = auth.Database
    auth.Database = lambda binding: binding

    def restore():
        """还原 auth 模块的数据库适配。"""
        auth.Database = original

    return c, db, restore


def test_run_scheduled_advances_and_logs_one_line():
    """定时入口推进一步，返回并打印一行日志：weekly <week_end> <状态>。"""
    from weekly import run_scheduled
    c, db, restore = scheduled_setup()
    try:
        line = run(run_scheduled(starmap_test.FakeEnv(db)))
    finally:
        restore()
    assert line.startswith('weekly ') and '2026-' in line and 'facts_ready' in line and '\n' not in line, line
    assert c.execute('SELECT status FROM weekly_report').fetchone()[0] == 'facts_ready'


def test_run_scheduled_skips_in_maintenance():
    """维护开关打开时什么都不做，日志写 maintenance。"""
    from weekly import run_scheduled
    c, db, restore = scheduled_setup()
    # 维护开关存的是不带引号的原文（auth.maintenance_enabled 直接比较字符串），不能用会转成 JSON 的 set_config
    c.execute("INSERT INTO runtime_config(name,value,deleted,updated_at) "
              "VALUES('write_maintenance','on',0,CURRENT_TIMESTAMP)")
    try:
        line = run(run_scheduled(starmap_test.FakeEnv(db)))
    finally:
        restore()
    assert 'maintenance' in line, line
    assert c.execute('SELECT COUNT(*) FROM weekly_report').fetchone()[0] == 0


def test_run_scheduled_never_raises():
    """算数字时抛异常：定时入口接住，日志只写 failed 和异常类型名，不带异常内容。"""
    import weekly
    c, db, restore = scheduled_setup()
    original = weekly.build_facts

    async def raising_stub(db, request, week_end):
        raise RuntimeError('secret detail')

    weekly.build_facts = raising_stub
    try:
        line = run(weekly.run_scheduled(starmap_test.FakeEnv(db)))
    finally:
        weekly.build_facts = original
        restore()
    assert 'failed' in line and 'RuntimeError' in line and 'secret' not in line, line


def test_run_scheduled_never_raises_even_before_week_end():
    """连"现在"都取不到时也不抛出：week_end 写 -，后面照样是 failed 类型名。"""
    import weekly
    c, db, restore = scheduled_setup()
    original = weekly.analytics.now

    def broken_now():
        raise RuntimeError('secret detail')

    weekly.analytics.now = broken_now
    try:
        line = run(weekly.run_scheduled(starmap_test.FakeEnv(db)))
    finally:
        weekly.analytics.now = original
        restore()
    assert line == 'weekly - failed RuntimeError', line


def test_run_scheduled_logs_failed_text_attempt():
    """写文字失败（还没到兜底）：日志写 text_failed 次数/上限，只有固定词和数字，不带异常内容；算数字那次不带。"""
    import weekly
    c, db, restore = scheduled_setup()
    fake = weekly.generate_json
    try:
        first = run(weekly.run_scheduled(starmap_test.FakeEnv(db)))
        fake.script = [RuntimeError('secret model output')]
        second = run(weekly.run_scheduled(starmap_test.FakeEnv(db)))
        third = run(weekly.run_scheduled(starmap_test.FakeEnv(db)))   # 这次模型成功
    finally:
        restore()
    assert first.endswith(' facts_ready') and 'text_failed' not in first, first
    assert second.endswith(' facts_ready text_failed 1/3') and 'secret' not in second, second
    assert third.endswith(' done'), third
    assert c.execute('SELECT attempts FROM weekly_report').fetchone()[0] == 1


def guard_revision_after(method, path):
    """让 auth.guard 用真实的 cache.invalidate 处理一个成功的写请求，返回之后的 data_revision 和 operation_log 条数。"""
    import auth
    import cache
    from fastapi.responses import JSONResponse
    c = build_db()
    db = starmap_test.SQLiteDB(c)

    class GuardRequest:
        """伪造经过 guard 的请求：带 Agent 令牌，迁移已就绪。"""

        def __init__(self):
            self.method = method
            self.url = type('Url', (), {'path': path, '__str__': lambda self: 'http://test' + path})()
            self.headers = {'authorization': 'Bearer agent-token'}
            self.cookies = {}
            self.scope = {'env': type('Env', (), {'ACCESS_TOKEN': 'agent-token', 'SESSION_SECRET': 's',
                                                  'MIGRATION_READY': 'true', 'DB': db})()}

    async def not_in_maintenance(request):
        """维护开关关闭。"""
        return False

    async def call_next(request):
        """下游处理成功。"""
        return JSONResponse({'id': 1, 'status': 'facts_ready', 'busy': False})

    original_database, original_maintenance = cache.Database, auth.maintenance_enabled
    cache.Database, auth.maintenance_enabled = (lambda binding: binding), not_in_maintenance
    try:
        response = run(auth.guard(GuardRequest(), call_next))
    finally:
        cache.Database, auth.maintenance_enabled = original_database, original_maintenance
    assert response.status_code == 200, response.status_code
    revision = c.execute("SELECT value FROM runtime_config WHERE name='data_revision'").fetchone()[0]
    logs = c.execute('SELECT COUNT(*) FROM operation_log').fetchone()[0]
    return revision, logs


def test_advance_does_not_bump_data_revision():
    """页面循环调推进接口不清统计缓存：data_revision 不变、不写 operation_log；普通写请求照旧加一。"""
    assert guard_revision_after('POST', '/api/weekly-reports/advance') == ('0', 0)
    assert guard_revision_after('POST', '/api/questions') == ('1', 1)   # 对照：证明这个测试能看出清缓存


TESTS = [
    test_migration_creates_weekly_report,
    test_week_end_boundaries,
    test_window_and_week_starts,
    test_streak_calendar_percent,
    test_known_before_uses_entered_for_questions,
    test_week_activity_and_classify,
    test_pick_target,
    test_graduated_in_week,
    test_check_text_accepts_good,
    test_check_text_rejects,
    test_check_reason_does_not_echo_text,
    test_brief_and_allowed,
    test_dropped_names_not_allowed,
    test_fallback_text_passes_own_check,
    test_fallback_cheers_pass_check,
    test_fallback_quiet_week,
    test_fallback_summary_zero_entries_never_says_zero,
    test_fallback_summary_with_entries_keeps_old_sentence,
    test_prompt_carries_rules,
    test_facts_entries_and_calendar,
    test_facts_sunday_night_goes_to_next_week_count_but_same_day_cell,
    test_facts_dictation_only_counts_type_one,
    test_facts_point_changes,
    test_facts_adjust_plus_practice_not_improved,
    test_facts_practice_and_graduated,
    test_facts_quiet_week,
    test_facts_query_budget,
    test_report_number_skips_stuck_new,
    test_advance_two_steps_then_done,
    test_advance_claims_once,
    test_bad_text_falls_back_after_three,
    test_model_errors_never_echo_text,
    test_recent_cheers_are_passed_and_avoided,
    test_facts_error_keeps_new,
    test_list_and_detail,
    test_advance_targets_last_ended_week,
    test_router_paths,
    test_run_scheduled_advances_and_logs_one_line,
    test_run_scheduled_skips_in_maintenance,
    test_run_scheduled_never_raises,
    test_run_scheduled_never_raises_even_before_week_end,
    test_run_scheduled_logs_failed_text_attempt,
    test_advance_does_not_bump_data_revision,
]


def check(name, function):
    """运行单个测试，打印 PASS/FAIL，返回是否通过。"""
    return starmap_test.check(name, function)


def main():
    """运行全部测试并打印总数；有失败时以非零状态退出。"""
    starmap_test.configure_output()
    results = [check(function.__name__, function) for function in TESTS]
    passed = sum(results)
    print('%d 通过，%d 失败' % (passed, len(results) - passed))
    sys.exit(len(results) - passed)


if __name__ == '__main__':
    main()
