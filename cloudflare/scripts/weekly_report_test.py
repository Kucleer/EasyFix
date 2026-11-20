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
