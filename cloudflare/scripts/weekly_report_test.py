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
from weekly_model import (calendar_days, entry_streak, percent, week_end_before,  # noqa: E402
                          week_starts, window)

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


TESTS = [
    test_migration_creates_weekly_report,
    test_week_end_boundaries,
    test_window_and_week_starts,
    test_streak_calendar_percent,
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
