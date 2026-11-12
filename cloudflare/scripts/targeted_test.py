"""考点卷（定向出卷）的本地测试。

在 starmap_test 的测试库（旧结构 + 迁移 0011、0012）上再执行迁移 0015。运行：

    python cloudflare/scripts/targeted_test.py
"""

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
sys.path.insert(0, str(ROOT / 'scripts'))

import starmap_test  # noqa: E402  复用建库、适配器等助手

MIGRATION_0015 = ROOT / 'migrations' / '0015_targeted_paper.sql'


def build_db():
    """建立测试库：starmap_test 的库 + 迁移 0015。"""
    connection = starmap_test.build_database()
    connection.executescript(MIGRATION_0015.read_text(encoding='utf-8'))
    connection.commit()
    return connection


def add_set(c, practice_id, created_at, reviewed_at, items, kind='targeted', deleted=0, subject_id=1):
    """插入一份卷子。items 为 [(错题编号, 做对 True/False/None, 题面 'original'/'similar')]。

    reviewed_at 为 None 表示还没批改（reviewed=0）；display_order 按列表顺序。
    """
    c.execute(
        'INSERT INTO practice_set(id,name,subject_id,question_type,kind,deleted,created_at,last_reviewed_at,reviewed) '
        'VALUES(?,?,?,?,?,?,?,?,?)',
        (practice_id, '考点卷%d' % practice_id, subject_id, 'mixed', kind, deleted, created_at, reviewed_at,
         0 if reviewed_at is None else 1))
    for order, (qid, correct, form) in enumerate(items):
        c.execute('INSERT INTO practice_set_question(practice_set_id,question_id,is_correct,display_order,form,deleted) '
                  'VALUES(?,?,?,?,?,0)', (practice_id, qid, correct, order, form))


# ---------------------------------------------------------------- 任务 1：迁移 0015


def test_migration_adds_columns():
    """0015 给三张表加上考点卷需要的列。"""
    c = build_db()
    cols = lambda t: {r[1] for r in c.execute('PRAGMA table_info(%s)' % t)}
    assert {'kind', 'grading_revision'} <= cols('practice_set')
    assert {'form', 'reason', 'knowledge_point_id', 'skip_reason'} <= cols('practice_set_question')
    assert 'explanation' in cols('similar_question')


def test_migration_defaults_keep_old_rows_valid():
    """旧卷子执行迁移后，kind 为 manual、grading_revision 为 0。"""
    c = starmap_test.build_database()
    c.execute("INSERT INTO practice_set(id,name,subject_id,deleted) VALUES(1,'旧卷',1,0)")
    c.executescript(MIGRATION_0015.read_text(encoding='utf-8'))
    row = c.execute('SELECT kind,grading_revision FROM practice_set WHERE id=1').fetchone()
    assert (row['kind'], row['grading_revision']) == ('manual', 0)


def test_add_set_helper_writes_rows():
    """add_set 写入卷子与题目行：未批改为 reviewed=0，顺序和题面正确。"""
    c = build_db()
    add_set(c, 5, '2026-11-01 10:00:00', None, [(11, None, 'original'), (12, True, 'similar')])
    paper = c.execute('SELECT kind,reviewed,question_type FROM practice_set WHERE id=5').fetchone()
    assert (paper['kind'], paper['reviewed'], paper['question_type']) == ('targeted', 0, 'mixed')
    rows = c.execute('SELECT question_id,form,display_order FROM practice_set_question WHERE practice_set_id=5 '
                     'ORDER BY display_order').fetchall()
    assert [(r[0], r[1], r[2]) for r in rows] == [(11, 'original', 0), (12, 'similar', 1)]


TESTS = [
    test_migration_adds_columns,
    test_migration_defaults_keep_old_rows_valid,
    test_add_set_helper_writes_rows,
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
