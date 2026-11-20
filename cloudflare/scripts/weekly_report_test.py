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
from weekly_model import (calendar_days, classify_change, entry_streak, graduated_in_week,  # noqa: E402
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


TESTS = [
    test_migration_creates_weekly_report,
    test_week_end_boundaries,
    test_window_and_week_starts,
    test_streak_calendar_percent,
    test_known_before_uses_entered_for_questions,
    test_week_activity_and_classify,
    test_pick_target,
    test_graduated_in_week,
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
