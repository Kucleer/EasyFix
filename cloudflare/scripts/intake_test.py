"""录题与卷子功能的本地测试。

用生产库的结构快照（d1_schema_before_0011.sql）加种子数据重建迁移前的库，
再执行迁移 0011。后续任务会在本脚本中追加录入接口、卷子接口等测试。运行：

    python cloudflare/scripts/intake_test.py
"""

import asyncio
import pathlib
import sqlite3
import sys
import traceback

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
sys.path.insert(0, str(ROOT / 'scripts'))

from fastapi import HTTPException  # noqa: E402
from knowledge_invariants_test import SQLiteDB  # noqa: E402  复用生产异步接口的 sqlite 适配器

SCHEMA_FILE = ROOT / 'scripts' / 'd1_schema_before_0011.sql'
MIGRATION_FILE = ROOT / 'migrations' / '0011_intake_papers.sql'


def configure_output():
    """把标准输出改成 utf-8，避免 Windows GBK 控制台打印中文时报错。"""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding='utf-8', errors='replace')
        except (AttributeError, ValueError):
            pass


# ---------------------------------------------------------------- 数据库助手

# 一级考点在前、二级在后（触发器要求父级先存在）：(编号, 名称, 学科, 层级, 父级, 年级)
SEED_POINTS = [
    (100, '分数运算', 1, 1, None, None),
    (101, '分数乘法', 1, 2, 100, 6),
    (102, '分数除法', 1, 2, 100, 6),
    (200, '语法', 2, 1, None, None),
    (201, '一般现在时', 2, 2, 200, 6),
]

# 旧题：(编号, 学科, 年级, 学期, 是否软删除, 录入时间)
SEED_QUESTIONS = [
    (1, 1, 6, 1, 0, '2026-03-02 10:00:00'),
    (2, 1, 6, 1, 1, '2026-03-01 09:00:00'),
    (3, 1, 6, 2, 0, '2026-04-05 08:30:00'),
    (4, 1, None, None, 0, '2026-02-10 20:00:00'),
    (5, 2, 6, 1, 0, '2026-03-15 18:00:00'),
]


def build_legacy_database():
    """建立迁移前的内存库：执行生产结构快照并写入种子数据，不执行 0011。"""
    connection = sqlite3.connect(':memory:')
    connection.row_factory = sqlite3.Row
    connection.executescript(SCHEMA_FILE.read_text(encoding='utf-8'))
    # 结构文件里这几张表是空的，必须补上单行记录
    connection.execute('INSERT INTO write_guard(id,revision,deleted) VALUES(1,0,0)')
    connection.execute('INSERT INTO knowledge_assert(id,guard,structure) VALUES(1,1,1)')
    for name in ('data_revision', 'taxonomy_version'):
        connection.execute(
            "INSERT INTO runtime_config(name,value,deleted,updated_at) VALUES(?,'0',0,CURRENT_TIMESTAMP)", (name,))
    for subject_id, name in [(1, '数学'), (2, '英语')]:
        connection.execute('INSERT INTO subject(id,name,deleted) VALUES(?,?,0)', (subject_id, name))
    for point_id, name, subject_id, level, parent_id, grade in SEED_POINTS:
        connection.execute(
            'INSERT INTO knowledge_point(id,name,name_key,subject_id,grade,level,parent_id,sort_order,deleted,created_at) '
            'VALUES(?,?,?,?,?,?,?,0,0,CURRENT_TIMESTAMP)',
            (point_id, name, name.lower(), subject_id, grade, level, parent_id))
    connection.execute('INSERT INTO error_type(id,name,subject_id,deleted) VALUES(1,"计算错误",1,0)')
    connection.execute('INSERT INTO error_type(id,name,subject_id,deleted) VALUES(2,"概念错误",NULL,0)')
    for question_id, subject_id, grade, semester, deleted, created_at in SEED_QUESTIONS:
        connection.execute(
            'INSERT INTO question(id,subject_id,grade,semester,original_text,parsed_question,'
            'review_count,correct_count,error_count,deleted,created_at,updated_at) VALUES(?,?,?,?,?,?,0,0,0,?,?,?)',
            (question_id, subject_id, grade, semester, '题干%d' % question_id, '题干%d' % question_id,
             deleted, created_at, created_at))
    connection.commit()
    return connection


def apply_migration(connection):
    """在连接上执行迁移 0011。"""
    connection.executescript(MIGRATION_FILE.read_text(encoding='utf-8'))
    connection.commit()


def build_database():
    """建立迁移后的内存库：先建旧库，再执行 0011。"""
    connection = build_legacy_database()
    apply_migration(connection)
    return connection


def adapter(connection):
    """把连接包装成生产代码使用的异步数据库接口。"""
    return SQLiteDB(connection)


def run(coroutine):
    """同步运行一个协程。"""
    return asyncio.run(coroutine)


def expect_http(status_code, function):
    """调用函数，要求它抛出指定状态码的 HTTPException。"""
    try:
        function()
    except HTTPException as error:
        assert error.status_code == status_code, '期望 %s，实际 %s' % (status_code, error.status_code)
        return
    raise AssertionError('期望 HTTP %s，但没有抛出' % status_code)


# ---------------------------------------------------------------- 任务 1：迁移 0011


def test_migration_seeds_user_and_student():
    """迁移预置默认用户和默认学生。"""
    c = build_database()
    assert c.execute('SELECT id,name FROM app_user').fetchall()[0][:] == (1, '默认用户')
    row = c.execute('SELECT id,user_id,name FROM student').fetchone()
    assert tuple(row) == (1, 1, '默认学生')


def test_migration_keeps_question_rows_and_approves_them():
    """迁移不丢题，旧题全部是已通过且属于学生 1。"""
    c = build_legacy_database()
    before = c.execute('SELECT COUNT(*) FROM question').fetchone()[0]
    apply_migration(c)
    assert c.execute('SELECT COUNT(*) FROM question').fetchone()[0] == before == 5
    assert c.execute("SELECT COUNT(*) FROM question WHERE review_status<>'approved'").fetchone()[0] == 0
    assert c.execute('SELECT COUNT(*) FROM question WHERE student_id<>1').fetchone()[0] == 0


def test_migration_builds_history_papers():
    """旧题按学科、年级、学期回填历史作业卷子，软删除的题也回填。"""
    c = build_database()
    names = sorted(r[0] for r in c.execute("SELECT name FROM paper WHERE source='history'"))
    assert names == ['六年级上 数学 历史作业', '六年级上 英语 历史作业',
                     '六年级下 数学 历史作业', '数学 历史作业（年级未填）']
    assert c.execute('SELECT COUNT(*) FROM question WHERE paper_id IS NULL').fetchone()[0] == 0
    # 已软删除的旧题也回填，且和同组未删除的题指向同一条记录
    ids = {r[0] for r in c.execute('SELECT paper_id FROM question WHERE subject_id=1 AND grade=6 AND semester=1')}
    assert len(ids) == 1
    row = c.execute("SELECT paper_type,images,score,paper_date FROM paper WHERE name='六年级上 数学 历史作业'").fetchone()
    assert row[0] == 'homework' and row[1] == '[]' and row[2] is None
    assert row[3] == c.execute('SELECT MIN(date(created_at)) FROM question WHERE subject_id=1 AND grade=6 AND semester=1').fetchone()[0]


def test_old_insert_without_new_columns_still_works():
    """不写新列的旧式插入仍然成功，并取到默认值。"""
    c = build_database()
    c.execute("INSERT INTO question(subject_id,review_count,correct_count,error_count,deleted) VALUES(1,0,0,0,0)")
    row = c.execute('SELECT student_id,review_status,paper_id FROM question ORDER BY id DESC LIMIT 1').fetchone()
    assert tuple(row) == (1, 'approved', None)


def test_student_id_added_to_all_listed_tables():
    """设计文档 5.2 列出的 17 张表都有 student_id。"""
    c = build_database()
    for table in ['question', 'error_book', 'paper', 'word', 'word_review', 'word_review_session',
                  'practice_set', 'learning_report', 'reading_passage', 'tag', 'reward', 'redemption',
                  'star_balance', 'star_record', 'star_action', 'achievement', 'achievement_progress']:
        columns = [r[1] for r in c.execute('PRAGMA table_info(' + table + ')')]
        assert 'student_id' in columns, table


TESTS = [
    test_migration_seeds_user_and_student,
    test_migration_keeps_question_rows_and_approves_them,
    test_migration_builds_history_papers,
    test_old_insert_without_new_columns_still_works,
    test_student_id_added_to_all_listed_tables,
]


def check(name, function):
    """运行单个测试，打印 PASS/FAIL，返回是否通过。"""
    try:
        function()
    except Exception:
        print('FAIL', name)
        traceback.print_exc()
        return False
    print('PASS', name)
    return True


def main():
    """运行全部测试并打印总数；有失败时以非零状态退出。"""
    configure_output()
    results = [check(function.__name__, function) for function in TESTS]
    passed = sum(1 for ok in results if ok)
    print('%d/%d passed' % (passed, len(results)))
    if passed != len(results):
        sys.exit(1)


if __name__ == '__main__':
    main()
