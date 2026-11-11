"""知识星空（考点掌握度）的本地测试。

用生产库结构快照建旧库，依次执行迁移 0011、0012，再写入本测试的种子数据。运行：

    python cloudflare/scripts/starmap_test.py
"""

import asyncio
import pathlib
import sqlite3
import sys
import traceback

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
sys.path.insert(0, str(ROOT / 'scripts'))

from knowledge_invariants_test import SQLiteDB  # noqa: E402  复用生产异步接口的 sqlite 适配器

SCHEMA_FILE = ROOT / 'scripts' / 'd1_schema_before_0011.sql'
MIGRATION_0011 = ROOT / 'migrations' / '0011_intake_papers.sql'
MIGRATION_0012 = ROOT / 'migrations' / '0012_starmap.sql'

# 种子考点：(编号, 名称, 学科, 层级, 父级, 学习年级)
SEED_POINTS = [
    (100, '有理数', 1, 1, None, None),
    (101, '有理数加减', 1, 2, 100, None),
    (102, '有理数乘方', 1, 2, 100, None),
    (110, '线段与角', 1, 1, None, None),
    (111, '线段和差与中点', 1, 2, 110, None),
    (112, '角平分线', 1, 2, 110, None),
    (120, '分数基础', 1, 1, None, None),
    (121, '分数大小比较', 1, 2, 120, None),
    (200, '动词时态', 2, 1, None, None),
    (201, '一般现在时', 2, 2, 200, 3),
    (202, '现在完成时', 2, 2, 200, 8),
]


def configure_output():
    """把标准输出改成 utf-8，避免 Windows GBK 控制台打印中文时报错。"""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding='utf-8', errors='replace')
        except (AttributeError, ValueError):
            pass


def split_statements(text):
    """把一段 SQL 拆成一条条完整语句（跳过只有注释的片段）。"""
    result, buffer = [], ''
    for line in text.splitlines(keepends=True):
        if not buffer.strip() and line.strip().startswith('--'):
            continue
        buffer += line
        if sqlite3.complete_statement(buffer):
            result.append(buffer.strip())
            buffer = ''
    return result


def build_database():
    """建立测试库：旧结构 + 必要的单行记录 + 迁移 0011、0012 + 种子考点。"""
    connection = sqlite3.connect(':memory:')
    connection.row_factory = sqlite3.Row
    connection.executescript(SCHEMA_FILE.read_text(encoding='utf-8'))
    connection.execute('INSERT INTO write_guard(id,revision,deleted) VALUES(1,0,0)')
    connection.execute('INSERT INTO knowledge_assert(id,guard,structure) VALUES(1,1,1)')
    for name in ('data_revision', 'taxonomy_version'):
        connection.execute(
            "INSERT INTO runtime_config(name,value,deleted,updated_at) VALUES(?,'0',0,CURRENT_TIMESTAMP)", (name,))
    for subject_id, name in [(1, '数学'), (2, '英语')]:
        connection.execute('INSERT INTO subject(id,name,deleted) VALUES(?,?,0)', (subject_id, name))
    connection.executescript(MIGRATION_0011.read_text(encoding='utf-8'))
    connection.executescript(MIGRATION_0012.read_text(encoding='utf-8'))
    for point_id, name, subject_id, level, parent_id, learn_grade in SEED_POINTS:
        connection.execute(
            'INSERT INTO knowledge_point(id,name,name_key,subject_id,level,parent_id,sort_order,learn_grade,deleted,'
            'created_at) VALUES(?,?,?,?,?,?,?,?,0,CURRENT_TIMESTAMP)',
            (point_id, name, name.lower(), subject_id, level, parent_id, point_id, learn_grade))
    connection.commit()
    return connection


def adapter(connection):
    """把连接包装成生产代码使用的异步数据库接口。"""
    return SQLiteDB(connection)


def run(coroutine):
    """同步运行一个协程。"""
    return asyncio.run(coroutine)


# ---------------------------------------------------------------- 任务 1：迁移 0012


def test_migration_adds_tables_and_column():
    """0012 给考点加学习年级列，并建出四张新表（都有 deleted，调整表有 student_id）。"""
    db = build_database()
    cols = {r[1] for r in db.execute('PRAGMA table_info(knowledge_point)')}
    assert 'learn_grade' in cols
    for table in ('textbook_section', 'textbook_section_point', 'knowledge_link', 'mastery_adjustment'):
        names = {r[1] for r in db.execute('PRAGMA table_info(%s)' % table)}
        assert 'deleted' in names, table
    assert 'student_id' in {r[1] for r in db.execute('PRAGMA table_info(mastery_adjustment)')}
    assert 'student_id' in {r[1] for r in db.execute('PRAGMA table_info(textbook_section)')}


def test_migration_is_rerunnable():
    """除第一条加列语句外，0012 的其余语句可以重复执行。"""
    db = build_database()
    statements = split_statements(MIGRATION_0012.read_text(encoding='utf-8'))
    assert statements[0].upper().startswith('ALTER TABLE KNOWLEDGE_POINT')
    for sql in statements[1:]:
        db.execute(sql)


TESTS = [
    test_migration_adds_tables_and_column,
    test_migration_is_rerunnable,
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
    passed = sum(results)
    print('%d 通过，%d 失败' % (passed, len(results) - passed))
    sys.exit(len(results) - passed)


if __name__ == '__main__':
    main()
