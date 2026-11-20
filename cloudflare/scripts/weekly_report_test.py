"""周报（weekly report）的本地测试。

在 targeted_test 的测试库（含迁移 0015）上再执行迁移 0016。运行：

    python cloudflare/scripts/weekly_report_test.py
"""

import pathlib
import sqlite3
import sys
from datetime import datetime

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
sys.path.insert(0, str(ROOT / 'scripts'))

import starmap_test  # noqa: E402  复用输出与检查助手
import targeted_test  # noqa: E402  复用建库（starmap_test 的库 + 0015）
from prompts import PromptLibrary  # noqa: E402
from weekly_model import (FALLBACK_CHEERS, allowed_names, allowed_numbers, brief_of,  # noqa: E402
                          check_text, fallback_text, calendar_days, classify_change, entry_streak, graduated_in_week,  # noqa: E402
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
    assert classify_change('weak', 'fair', {'right': True, 'wrong': False}) == 'improved'
    assert classify_change('weak', 'mastered', {'right': False, 'wrong': False}) is None     # 只有手动调整：不算变好
    assert classify_change('good', 'fair', {'right': False, 'wrong': True}) == 'dropped'
    assert classify_change('good', 'fair', {'right': False, 'wrong': False}) is None
    assert classify_change('unlearned', 'weak', {'right': False, 'wrong': True}) == 'new_weak'
    assert classify_change('unlearned', 'fair', {'right': True, 'wrong': False}) is None
    assert classify_change('fair', 'fair', {'right': True, 'wrong': False}) is None


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


def test_prompt_carries_rules():
    prompt = PromptLibrary()._build_weekly_report_prompt(brief_of(sample_facts()), ['上一期的鼓励'])
    for needle in ('你', '「」', '阿拉伯数字', '上一期的鼓励', '合并同类项', '去括号'):
        assert needle in prompt
    assert '薄弱' not in prompt


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
    c.execute("INSERT INTO weekly_report(week_end,created_at,updated_at) "
              "VALUES('2026-11-15 20:00:00','2026-11-15 20:00:05','2026-11-15 20:00:05')")
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
    test_fallback_text_passes_own_check,
    test_fallback_cheers_pass_check,
    test_fallback_quiet_week,
    test_prompt_carries_rules,
    test_facts_entries_and_calendar,
    test_facts_sunday_night_goes_to_next_week_count_but_same_day_cell,
    test_facts_dictation_only_counts_type_one,
    test_facts_point_changes,
    test_facts_practice_and_graduated,
    test_facts_quiet_week,
    test_facts_query_budget,
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
