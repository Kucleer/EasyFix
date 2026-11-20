"""周报（weekly report）的本地测试。

在 targeted_test 的测试库（含迁移 0015）上再执行迁移 0016。运行：

    python cloudflare/scripts/weekly_report_test.py
"""

import pathlib
import sqlite3
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
sys.path.insert(0, str(ROOT / 'scripts'))

import starmap_test  # noqa: E402  复用输出与检查助手
import targeted_test  # noqa: E402  复用建库（starmap_test 的库 + 0015）

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


TESTS = [
    test_migration_creates_weekly_report,
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
