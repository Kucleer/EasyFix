"""两级知识点改造的本地不变量测试。

使用内存 SQLite 复现 D1 相关表结构，执行 0009 迁移，并直接调用生产代码中的
触发器断言、关联写入语句与统计聚合函数。运行：

    python cloudflare/scripts/knowledge_invariants_test.py
"""

import asyncio
import json
import pathlib
import sqlite3
import sys
import traceback

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
sys.path.insert(0, str(ROOT / 'scripts'))

from knowledge import (  # noqa: E402
    bump_taxonomy,
    guard_statement,
    link_statements,
    resolve_many,
    save_directory,
    structure_statement,
)
from knowledge_model import map_error, normalize_name_key  # noqa: E402
from knowledge_stats import module_stats, validate_filter_ids  # noqa: E402
from knowledge_backfill import assertion_sql  # noqa: E402
from questions import save  # noqa: E402
from fastapi import HTTPException  # noqa: E402

SCHEMA = """
CREATE TABLE subject (id INTEGER PRIMARY KEY, name VARCHAR(100) NOT NULL, deleted BOOLEAN NOT NULL DEFAULT 0);
CREATE TABLE error_type (id INTEGER PRIMARY KEY, name VARCHAR(100) NOT NULL, subject_id INTEGER, deleted INTEGER NOT NULL DEFAULT 0);
CREATE TABLE knowledge_point (
  id INTEGER NOT NULL, name VARCHAR(200) NOT NULL, subject_id INTEGER NOT NULL,
  grade INTEGER, semester INTEGER, deleted BOOLEAN NOT NULL, created_at TIMESTAMP,
  CONSTRAINT knowledge_point_pkey PRIMARY KEY (id));
CREATE TABLE kp_error_type (
  id INTEGER NOT NULL, knowledge_point_id INTEGER NOT NULL, error_type_id INTEGER NOT NULL,
  deleted INTEGER NOT NULL DEFAULT 0, CONSTRAINT kp_error_type_pkey PRIMARY KEY (id));
CREATE TABLE question (
  id INTEGER NOT NULL, error_book_id INTEGER, subject_id INTEGER NOT NULL,
  original_image VARCHAR(500), original_images TEXT, original_text TEXT, grade INTEGER,
  semester INTEGER, parsed_question TEXT, answer TEXT, analysis TEXT, analysis_image VARCHAR(500),
  difficulty INTEGER, error_type VARCHAR(50), knowledge_point VARCHAR(200),
  review_count INTEGER NOT NULL, correct_count INTEGER NOT NULL, error_count INTEGER NOT NULL,
  last_reviewed_at TIMESTAMP, deleted BOOLEAN NOT NULL, created_at TIMESTAMP, updated_at TIMESTAMP,
  CONSTRAINT question_pkey PRIMARY KEY (id));
CREATE TABLE question_tag (id INTEGER PRIMARY KEY, question_id INTEGER NOT NULL, tag_id INTEGER NOT NULL, deleted INTEGER NOT NULL DEFAULT 0);
CREATE TABLE tag (id INTEGER PRIMARY KEY, name VARCHAR(100) NOT NULL, color VARCHAR(50), deleted BOOLEAN NOT NULL DEFAULT 0);
CREATE TABLE error_book (id INTEGER PRIMARY KEY, name VARCHAR(200) NOT NULL, subject_id INTEGER, deleted BOOLEAN NOT NULL DEFAULT 0);
CREATE TABLE practice_set (
  id INTEGER NOT NULL, name VARCHAR(200) NOT NULL, notes TEXT, subject_id INTEGER NOT NULL,
  source_type VARCHAR(20), question_type VARCHAR(20), pdf_path VARCHAR(500), total_questions INTEGER,
  reviewed BOOLEAN, review_count INTEGER, accuracy DOUBLE PRECISION, last_reviewed_at TIMESTAMP,
  review_images TEXT, passage_id INTEGER, deleted BOOLEAN NOT NULL, created_at TIMESTAMP,
  CONSTRAINT practice_set_pkey PRIMARY KEY (id));
CREATE TABLE practice_set_question (
  id INTEGER NOT NULL, practice_set_id INTEGER NOT NULL, question_id INTEGER NOT NULL,
  similar_question_id INTEGER, is_correct BOOLEAN, display_order INTEGER,
  deleted INTEGER NOT NULL DEFAULT 0, CONSTRAINT practice_set_question_pkey PRIMARY KEY (id));
CREATE TABLE similar_question (id INTEGER PRIMARY KEY, source_question_id INTEGER NOT NULL, similar_text TEXT, similar_answer TEXT, similarity_score DOUBLE PRECISION, deleted INTEGER NOT NULL DEFAULT 0, generated_at TIMESTAMP);
CREATE TABLE runtime_config (name TEXT PRIMARY KEY, value TEXT NOT NULL, deleted INTEGER NOT NULL DEFAULT 0, updated_at TEXT NOT NULL);
CREATE TABLE request_record (name TEXT PRIMARY KEY, value TEXT NOT NULL, deleted INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL);
CREATE TABLE write_guard (id INTEGER PRIMARY KEY CHECK (id=1), revision INTEGER NOT NULL, deleted INTEGER NOT NULL DEFAULT 0);
CREATE TABLE word (
  id INTEGER PRIMARY KEY, english VARCHAR(200) NOT NULL, chinese VARCHAR(500), phonetic VARCHAR(200),
  grade INTEGER, semester INTEGER, review_count INTEGER NOT NULL DEFAULT 0,
  correct_count INTEGER NOT NULL DEFAULT 0, ease_factor DOUBLE PRECISION, interval INTEGER,
  learning_phase VARCHAR(20), next_review_at TIMESTAMP, last_reviewed_at TIMESTAMP,
  deleted BOOLEAN NOT NULL DEFAULT 0, created_at TIMESTAMP, updated_at TIMESTAMP);
CREATE TABLE learning_report (
  id INTEGER PRIMARY KEY, title VARCHAR(300) NOT NULL, subject_id INTEGER, grade INTEGER,
  time_range_days INTEGER, content TEXT, total_questions INTEGER, total_words INTEGER,
  overall_accuracy DOUBLE PRECISION, deleted BOOLEAN NOT NULL DEFAULT 0, created_at TIMESTAMP);
"""

RESULTS = []


class SQLiteDB:
    """把生产代码使用的异步接口适配到 sqlite3。"""

    def __init__(self, connection):
        self.connection = connection

    @staticmethod
    def bind(parameters):
        return tuple(int(value) if isinstance(value, bool) else value for value in parameters)

    async def all(self, sql, parameters=()):
        cursor = self.connection.execute(sql, self.bind(parameters))
        return [dict(row) for row in cursor.fetchall()]

    async def first(self, sql, parameters=()):
        cursor = self.connection.execute(sql, self.bind(parameters))
        row = cursor.fetchone()
        return dict(row) if row is not None else None

    async def run(self, sql, parameters=()):
        cursor = self.connection.execute(sql, self.bind(parameters))
        self.connection.commit()
        return {'last_row_id': cursor.lastrowid}

    async def batch(self, statements):
        results = []
        self.connection.execute('SAVEPOINT knowledge_batch')
        try:
            for sql, parameters in statements:
                cursor = self.connection.execute(sql, self.bind(parameters))
                results.append({'last_row_id': cursor.lastrowid})
            self.connection.execute('RELEASE knowledge_batch')
            return results
        except Exception:
            self.connection.execute('ROLLBACK TO knowledge_batch')
            self.connection.execute('RELEASE knowledge_batch')
            raise


def build_database(check_same_thread=True):
    """建立内存库并应用迁移。"""
    connection = sqlite3.connect(':memory:', check_same_thread=check_same_thread)
    connection.row_factory = sqlite3.Row
    connection.executescript(SCHEMA)
    connection.executescript((ROOT / 'migrations' / '0009_knowledge_hierarchy.sql').read_text(encoding='utf-8'))
    connection.execute("INSERT INTO runtime_config(name,value,deleted,updated_at) VALUES('data_revision','0',0,CURRENT_TIMESTAMP)")
    for subject_id, name in [(1, '数学'), (2, '英语')]:
        connection.execute('INSERT INTO subject(id,name,deleted) VALUES(?,?,0)', (subject_id, name))
    connection.execute('INSERT INTO error_type(id,name,subject_id,deleted) VALUES(1,"计算错误",1,0)')
    connection.execute('INSERT INTO error_type(id,name,subject_id,deleted) VALUES(2,"概念错误",NULL,0)')
    connection.commit()
    return connection


def expect_error(code, callable_):
    """断言操作因指定 KP 错误码失败。"""
    try:
        callable_()
    except Exception as error:  # sqlite3.IntegrityError
        message = str(error)
        if code in message:
            return
        raise AssertionError(f'期望 {code}，实际 {message}')
    raise AssertionError(f'期望 {code} 失败，但操作成功')


def check(name, function):
    """执行单个用例并记录结果。"""
    try:
        function()
        RESULTS.append((name, True, ''))
        print(f'PASS  {name}')
    except Exception as error:  # noqa: BLE001
        RESULTS.append((name, False, str(error)))
        print(f'FAIL  {name}: {error}')
        traceback.print_exc()


def insert_point(connection, point_id, name, subject_id, level, parent_id=None, deleted=0):
    connection.execute(
        'INSERT INTO knowledge_point(id,name,name_key,subject_id,level,parent_id,sort_order,deleted,created_at) '
        'VALUES(?,?,?,?,?,?,0,?,CURRENT_TIMESTAMP)',
        (point_id, name, normalize_name_key(name), subject_id, level, parent_id, deleted))
    connection.commit()


def insert_question(connection, question_id, subject_id=1, deleted=0, created_at='2026-01-01 00:00:00'):
    connection.execute(
        'INSERT INTO question(id,subject_id,original_text,parsed_question,review_count,correct_count,error_count,'
        'deleted,created_at,knowledge_revision) VALUES(?,?,?,?,0,0,0,?,?,0)',
        (question_id, subject_id, '题干' + str(question_id), '题干' + str(question_id), deleted, created_at))
    connection.commit()


def link(connection, question_id, point_ids, primary, source='manual'):
    """使用生产语句写入关联。"""
    statements = link_statements(question_id, point_ids, primary, source, '2026-01-01 00:00:00')
    for sql, parameters in statements:
        connection.execute(sql, parameters)
    connection.commit()


def seed_tree(connection):
    insert_point(connection, 10, '有理数', 1, 1)
    insert_point(connection, 11, '乘方', 1, 2, 10)
    insert_point(connection, 12, '混合运算', 1, 2, 10)
    insert_point(connection, 20, '线段与角', 1, 1)
    insert_point(connection, 21, '角的和差', 1, 2, 20)
    insert_point(connection, 30, '名词与数量表达', 2, 1)
    insert_point(connection, 31, '可数名词', 2, 2, 30)
    insert_point(connection, 40, '空模块', 1, 1)


def test_name_normalization():
    assert normalize_name_key('  有理数 ') == '有理数'
    assert normalize_name_key('ＡＢＣ') == 'abc'
    assert normalize_name_key('Angle  Sum') == 'angle sum'
    assert normalize_name_key('') == ''
    assert normalize_name_key(None) == ''
    status, detail = map_error('D1_ERROR: KP_LEVEL:知识点层级只能是一级或二级: SQLITE_CONSTRAINT (extended: SQLITE_CONSTRAINT_TRIGGER)')
    assert status == 422 and detail == '知识点层级只能是一级或二级', (status, detail)
    status, detail = map_error('KP_GUARD:题目分类版本冲突，请刷新后重试: SQLITE_CONSTRAINT')
    assert status == 409 and detail == '题目分类版本冲突，请刷新后重试', (status, detail)
    assert map_error('some other database error') is None


def test_tree_constraints():
    connection = build_database()
    seed_tree(connection)
    expect_error('KP_LEVEL', lambda: insert_point(connection, 50, '第三级', 1, 3, 11))
    expect_error('KP_LEVEL', lambda: insert_point(connection, 51, '跨学科子级', 2, 2, 10))
    expect_error('KP_LEVEL', lambda: insert_point(connection, 52, '缺父级', 1, 2, None))
    expect_error('KP_LEVEL', lambda: insert_point(connection, 53, '一级带父级', 1, 1, 10))
    expect_error('UNIQUE', lambda: connection.execute(
        'INSERT INTO knowledge_point(id,name,name_key,subject_id,level,parent_id,sort_order,deleted,created_at) '
        'VALUES(54,"乘方","乘方",1,2,10,0,0,CURRENT_TIMESTAMP)'))
    # 全半角与大小写差异按 name_key 判重
    connection.execute("INSERT INTO knowledge_point(id,name,name_key,subject_id,level,parent_id,sort_order,deleted,created_at) "
                       "VALUES(55,'COUNT','count',2,2,30,0,0,CURRENT_TIMESTAMP)")
    expect_error('UNIQUE', lambda: connection.execute(
        'INSERT INTO knowledge_point(id,name,name_key,subject_id,level,parent_id,sort_order,deleted,created_at) '
        "VALUES(56,'ＣＯＵＮＴ','count',2,2,30,0,0,CURRENT_TIMESTAMP)"))


def test_link_constraints():
    connection = build_database()
    seed_tree(connection)
    insert_question(connection, 100)
    expect_error('KP_LEVEL', lambda: link(connection, 100, [10], 10))
    expect_error('KP_SUBJECT', lambda: link(connection, 100, [31], 31))
    insert_point(connection, 13, '已删除二级', 1, 2, 10, deleted=1)
    expect_error('KP_LEVEL', lambda: link(connection, 100, [13], 13))
    link(connection, 100, [11, 12], 11)
    expect_error('UNIQUE', lambda: connection.execute(
        'UPDATE question_knowledge_point SET is_primary=1 WHERE question_id=100 AND knowledge_point_id=12'))
    link(connection, 100, [12], 12)
    rows = connection.execute(
        'SELECT knowledge_point_id,is_primary,deleted FROM question_knowledge_point '
        'WHERE question_id=100 AND deleted=0 ORDER BY knowledge_point_id').fetchall()
    assert [(row[0], row[1]) for row in rows] == [(12, 1)], rows


def test_question_subject_guard():
    connection = build_database()
    seed_tree(connection)
    insert_question(connection, 101)
    link(connection, 101, [11], 11)
    expect_error('KP_SUBJECT', lambda: connection.execute('UPDATE question SET subject_id=2 WHERE id=101'))
    connection.execute('UPDATE question_knowledge_point SET deleted=1,is_primary=0 WHERE question_id=101')
    connection.execute('UPDATE question SET subject_id=2 WHERE id=101')
    connection.commit()
    assert connection.execute('SELECT subject_id FROM question WHERE id=101').fetchone()[0] == 2


def test_delete_protection():
    connection = build_database()
    seed_tree(connection)
    insert_question(connection, 102)
    link(connection, 102, [11], 11)
    expect_error('KP_INUSE', lambda: connection.execute('UPDATE knowledge_point SET deleted=1 WHERE id=11'))
    expect_error('KP_CHILD', lambda: connection.execute('UPDATE knowledge_point SET deleted=1 WHERE id=10'))
    connection.execute('UPDATE question SET deleted=1 WHERE id=102')
    connection.commit()
    connection.execute('UPDATE knowledge_point SET deleted=1 WHERE id=11')
    connection.commit()
    assert connection.execute('SELECT deleted FROM knowledge_point WHERE id=11').fetchone()[0] == 1
    expect_error('KP_CHILD', lambda: connection.execute('UPDATE knowledge_point SET deleted=1 WHERE id=10'))


def test_move_and_subject_change():
    connection = build_database()
    seed_tree(connection)
    insert_question(connection, 103)
    link(connection, 103, [11], 11)
    expect_error('KP_MOVE', lambda: connection.execute('UPDATE knowledge_point SET parent_id=20 WHERE id=11'))
    expect_error('KP_SUBJECT', lambda: connection.execute('UPDATE knowledge_point SET subject_id=2 WHERE id=11'))
    expect_error('KP_MOVE', lambda: connection.execute('UPDATE knowledge_point SET level=1,parent_id=NULL WHERE id=11'))


def test_error_type_constraint():
    connection = build_database()
    seed_tree(connection)
    expect_error('KP_LEVEL', lambda: connection.execute(
        'INSERT INTO kp_error_type(knowledge_point_id,error_type_id,deleted) VALUES(10,1,0)'))
    connection.execute('INSERT INTO kp_error_type(knowledge_point_id,error_type_id,deleted) VALUES(11,1,0)')
    connection.commit()
    connection.execute('INSERT INTO kp_error_type(knowledge_point_id,error_type_id,deleted) VALUES(10,2,1)')
    connection.commit()
    expect_error('KP_LEVEL', lambda: connection.execute(
        'UPDATE kp_error_type SET deleted=0 WHERE knowledge_point_id=10 AND error_type_id=2'))


def test_subject_delete_guard():
    connection = build_database()
    seed_tree(connection)
    expect_error('KP_INUSE', lambda: connection.execute('UPDATE subject SET deleted=1 WHERE id=1'))
    insert_question(connection, 104, subject_id=2)
    expect_error('KP_INUSE', lambda: connection.execute('UPDATE subject SET deleted=1 WHERE id=2'))


def test_guard_and_structure_assertions():
    connection = build_database()
    seed_tree(connection)
    insert_question(connection, 105)
    connection.execute('UPDATE question SET knowledge_revision=2 WHERE id=105')
    connection.commit()
    guard_sql, guard_values = guard_statement(
        'EXISTS(SELECT 1 FROM write_guard WHERE id=1 AND deleted=0) AND '
        'COALESCE((SELECT knowledge_revision FROM question WHERE id=? AND deleted=0),-1)=?', (105, 2))
    connection.execute(guard_sql, guard_values)
    expect_error('KP_GUARD', lambda: connection.execute(
        *guard_statement('EXISTS(SELECT 1 FROM write_guard WHERE id=1 AND deleted=0) AND '
                         'COALESCE((SELECT knowledge_revision FROM question WHERE id=? AND deleted=0),-1)=?',
                         (105, 1))))
    structure_sql, structure_values = structure_statement([105])
    connection.execute(structure_sql, structure_values)
    connection.execute('INSERT INTO question_knowledge_point(question_id,knowledge_point_id,is_primary,deleted) '
                       'VALUES(105,11,0,0)')
    connection.commit()
    expect_error('KP_STRUCT', lambda: connection.execute(structure_sql, structure_values))


def test_taxonomy_version_bump():
    connection = build_database()
    connection.execute("UPDATE runtime_config SET value='3' WHERE name='taxonomy_version'")
    connection.commit()
    for sql, parameters in bump_taxonomy():
        connection.execute(sql, parameters)
    connection.commit()
    assert connection.execute("SELECT value FROM runtime_config WHERE name='taxonomy_version'").fetchone()[0] == '4'
    assert connection.execute("SELECT value FROM runtime_config WHERE name='data_revision'").fetchone()[0] == '1'


def async_test(coroutine):
    return asyncio.run(coroutine)


def test_legacy_compatibility():
    async def scenario():
        connection = build_database()
        seed_tree(connection)
        db = SQLiteDB(connection)
        insert_question(connection, 200)
        link(connection, 200, [11, 12], 11)
        db_row = await db.first('SELECT * FROM question WHERE id=200')
        old_links = [{'id': 11, 'is_primary': 1}, {'id': 12, 'is_primary': 0}]
        # 回传当前主考点名：保留全部关联
        result, detail = (await resolve_many(db, 1, [({'knowledge_point': '乘方'}, db_row, old_links, False)]))[0]
        assert detail is None, detail
        assert result['changed'] is False
        assert sorted(result['ids']) == [11, 12] and result['primary'] == 11
        # 空字符串：视为未修改
        result, detail = (await resolve_many(db, 1, [({'knowledge_point': ''}, db_row, old_links, False)]))[0]
        assert detail is None and result['changed'] is False
        # 精确旧名称：转为新主考点，保留次要关联
        result, detail = (await resolve_many(db, 1, [({'knowledge_point': '混合运算'}, db_row, old_links, False)]))[0]
        assert detail is None, detail
        assert sorted(result['ids']) == [11, 12] and result['primary'] == 12
        # 未知名称与歧义名称拒绝
        result, detail = (await resolve_many(db, 1, [({'knowledge_point': '不存在的点'}, db_row, old_links, False)]))[0]
        assert detail and '不在目录中' in detail
        insert_point(connection, 60, '同名二级', 1, 2, 20)
        connection.execute('UPDATE knowledge_point SET name_key=? WHERE id=60', (normalize_name_key('混合运算'),))
        connection.execute('UPDATE knowledge_point SET parent_id=40 WHERE id=60')
        connection.commit()
        result, detail = (await resolve_many(db, 1, [({'knowledge_point': '混合运算'}, db_row, old_links, False)]))[0]
        assert detail and '多个同名二级' in detail
        # 新旧字段矛盾
        result, detail = (await resolve_many(db, 1, [(
            {'knowledge_point_ids': [11], 'primary_knowledge_point_id': 11, 'knowledge_point': '混合运算'},
            db_row, old_links, False)]))[0]
        assert detail and '不一致' in detail
        # 非空列表必须显式主考点
        result, detail = (await resolve_many(db, 1, [(
            {'knowledge_point_ids': [11, 12]}, db_row, old_links, False)]))[0]
        assert detail and '主考点' in detail
        # 改学科但未提交新关联
        result, detail = (await resolve_many(db, 1, [({}, db_row, old_links, True)]))[0]
        assert detail and '改学科' in detail
        # 空数组明确清空
        result, detail = (await resolve_many(db, 1, [(
            {'knowledge_point_ids': [], 'primary_knowledge_point_id': None}, db_row, old_links, False)]))[0]
        assert detail is None and result['changed'] is True and result['ids'] == []
    async_test(scenario())


def seed_stats_data(connection):
    seed_tree(connection)
    for question_id in (301, 302, 303, 304):
        insert_question(connection, question_id)
    insert_question(connection, 305)
    link(connection, 301, [11, 12], 11)
    link(connection, 302, [11, 21], 11)
    link(connection, 304, [21], 21)


def test_module_stats():
    async def scenario():
        connection = build_database()
        seed_stats_data(connection)
        db = SQLiteDB(connection)
        stats = await module_stats(db, subject_id=1, level=1)
        assert stats['total_questions'] == 5, stats
        assert stats['unclassified_count'] == 2, stats
        by_name = {item['name']: item for item in stats['items']}
        assert by_name['有理数']['question_count'] == 2
        assert by_name['有理数']['primary_question_count'] == 2
        assert by_name['有理数']['share_percent'] == 40.0
        assert by_name['线段与角']['question_count'] == 2
        assert by_name['线段与角']['primary_question_count'] == 1
        assert by_name['线段与角']['share_percent'] == 20.0
        assert by_name['线段与角']['accuracy'] is None
        level2 = await module_stats(db, subject_id=1, level=2, parent_id=10)
        points = {item['name']: item for item in level2['items']}
        assert points['乘方']['question_count'] == 2
        assert points['混合运算']['question_count'] == 1
        assert points['混合运算']['primary_question_count'] == 0
        assert points['乘方']['parent_share_percent'] == 100.0
        assert points['混合运算']['parent_share_percent'] == 0.0
    async_test(scenario())


def test_practice_accuracy():
    async def scenario():
        connection = build_database()
        seed_stats_data(connection)
        db = SQLiteDB(connection)
        connection.execute("INSERT INTO practice_set(id,name,subject_id,source_type,question_type,reviewed,deleted,created_at,last_reviewed_at) VALUES(1,'P1',1,'question','original',1,0,'2026-01-01','2026-01-02')")
        connection.execute("INSERT INTO practice_set(id,name,subject_id,source_type,question_type,reviewed,deleted,created_at,last_reviewed_at) VALUES(2,'P2',1,'question','original',1,0,'2026-01-01','2026-01-02')")
        connection.execute("INSERT INTO practice_set(id,name,subject_id,source_type,question_type,reviewed,deleted,created_at,last_reviewed_at) VALUES(3,'P3',1,'question','original',0,0,'2026-01-01',NULL)")
        connection.execute("INSERT INTO practice_set(id,name,subject_id,source_type,question_type,reviewed,deleted,created_at,last_reviewed_at) VALUES(4,'W1',2,'word','original',1,0,'2026-01-01','2026-01-02')")
        rows = [
            (1, 1, 301, 1), (2, 1, 301, 1), (3, 1, 302, 0),
            (4, 2, 304, 1), (5, 3, 304, 0), (6, 4, 301, 1),
        ]
        for row in rows:
            connection.execute('INSERT INTO practice_set_question(id,practice_set_id,question_id,is_correct,display_order,deleted) VALUES(?,?,?,?,0,0)', row)
        connection.commit()
        stats = await module_stats(db, subject_id=1, level=1)
        by_name = {item['name']: item for item in stats['items']}
        # Q1 关联同模块两个二级，同一次作答只计一次；两种作答各计一次。
        assert by_name['有理数']['answer_count'] == 3, by_name['有理数']
        assert by_name['有理数']['correct_count'] == 2
        assert by_name['有理数']['accuracy'] == 66.7
        assert by_name['有理数']['reviewed_question_count'] == 2
        assert by_name['有理数']['review_coverage'] == 100.0
        # 未批改与单词练习不计入；Q302 与 Q304 各一次作答。
        assert by_name['线段与角']['answer_count'] == 2
        assert by_name['线段与角']['correct_count'] == 1
        assert by_name['线段与角']['accuracy'] == 50.0
        # 零作答模块 accuracy 为 None
        assert by_name['空模块']['question_count'] == 0
        assert by_name['空模块']['accuracy'] is None
    async_test(scenario())


def test_stats_time_window():
    async def scenario():
        connection = build_database()
        seed_stats_data(connection)
        connection.execute("UPDATE question SET created_at='2020-01-01 00:00:00' WHERE id IN (301,302)")
        insert_question(connection, 306, created_at='2026-11-10 00:00:00')
        link(connection, 306, [11], 11)
        connection.commit()
        db = SQLiteDB(connection)
        connection.execute("INSERT INTO practice_set(id,name,subject_id,source_type,question_type,reviewed,deleted,created_at,last_reviewed_at) VALUES(1,'P1',1,'question','original',1,0,'2026-01-01',CURRENT_TIMESTAMP)")
        connection.execute('INSERT INTO practice_set_question(id,practice_set_id,question_id,is_correct,display_order,deleted) VALUES(1,1,301,1,0,0)')
        connection.execute('INSERT INTO practice_set_question(id,practice_set_id,question_id,is_correct,display_order,deleted) VALUES(2,1,306,1,0,0)')
        connection.commit()
        stats = await module_stats(db, subject_id=1, days=30, level=1, practice_days=30)
        by_name = {item['name']: item for item in stats['items']}
        # 题数与覆盖率分母只含收录窗口内的 Q306；旧题 Q301 不计入覆盖率分子
        assert by_name['有理数']['question_count'] == 1
        assert by_name['有理数']['reviewed_question_count'] == 1
        assert by_name['有理数']['review_coverage'] == 100.0
        # 正确率不叠加题目收录时间，旧题 Q301 的近期练习仍计入
        assert by_name['有理数']['answer_count'] == 2
        assert by_name['有理数']['accuracy'] == 100.0
    async_test(scenario())


def test_filter_path_validation():
    async def scenario():
        connection = build_database()
        seed_tree(connection)
        db = SQLiteDB(connection)
        await validate_filter_ids(db, 1, 10, 11)
        try:
            await validate_filter_ids(db, 1, 20, 11)
        except Exception as error:
            assert '同一路径' in str(error)
        else:
            raise AssertionError('跨路径筛选未被拒绝')
        try:
            await validate_filter_ids(db, 1, 10, 10)
        except Exception as error:
            assert '二级' in str(error)
        else:
            raise AssertionError('一级被当作二级筛选未被拒绝')
    async_test(scenario())


def test_soft_delete_metrics():
    async def scenario():
        connection = build_database()
        seed_stats_data(connection)
        db = SQLiteDB(connection)
        connection.execute('UPDATE question SET deleted=1 WHERE id=304')
        connection.commit()
        stats = await module_stats(db, subject_id=1, level=1)
        by_name = {item['name']: item for item in stats['items']}
        assert by_name['线段与角']['question_count'] == 1
        assert stats['total_questions'] == 4
        connection.execute('UPDATE question_knowledge_point SET deleted=1 WHERE question_id=302 AND knowledge_point_id=21')
        connection.commit()
        stats = await module_stats(db, subject_id=1, level=1)
        by_name = {item['name']: item for item in stats['items']}
        assert by_name['线段与角']['question_count'] == 0
        assert stats['unclassified_count'] == 2
    async_test(scenario())


def test_directory_crud():
    async def scenario():
        connection = build_database()
        db = SQLiteDB(connection)
        module = await save_directory(db, {'name': '有理数', 'subject_id': 1, 'level': 1, 'sort_order': 10})
        assert module['level'] == 1 and module['code']
        point = await save_directory(db, {'name': '乘方', 'subject_id': 1, 'level': 2,
                                          'parent_id': module['id'], 'error_type_ids': [1]})
        assert point['parent_name'] == '有理数'
        assert [item['name'] for item in point['error_types']] == ['计算错误']
        version = int(connection.execute(
            "SELECT value FROM runtime_config WHERE name='taxonomy_version'").fetchone()[0])
        assert version >= 2
        # 同级重名
        try:
            await save_directory(db, {'name': '乘方', 'subject_id': 1, 'level': 2, 'parent_id': module['id']})
        except HTTPException as error:
            assert error.status_code == 409, error
        else:
            raise AssertionError('同级重名未被拒绝')
        # 三级、跨学科父级、一级挂错误类型
        english = await save_directory(db, {'name': '代词', 'subject_id': 2, 'level': 1})
        for payload, message in [
            ({'name': '三级', 'subject_id': 1, 'level': 3}, '层级'),
            ({'name': '跨学科', 'subject_id': 1, 'level': 2, 'parent_id': english['id']}, '同一学科'),
            ({'name': '一级带错误类型', 'subject_id': 1, 'level': 1, 'error_type_ids': [1]}, '错误类型'),
        ]:
            try:
                await save_directory(db, payload)
            except HTTPException as error:
                assert message in str(error.detail), error.detail
            else:
                raise AssertionError('非法目录写入未被拒绝：' + str(payload))
        # 改名保持 ID，子级父级名随新名显示
        updated = await save_directory(db, {'name': '有理数与运算', 'subject_id': 1,
                                            'level': 1, 'parent_id': None}, module['id'])
        assert updated['id'] == module['id'] and updated['name'] == '有理数与运算'
        refreshed = await save_directory(db, {'name': '乘方', 'subject_id': 1, 'level': 2,
                                              'parent_id': module['id'], 'error_type_ids': []}, point['id'])
        assert refreshed['parent_name'] == '有理数与运算'
        assert refreshed['error_types'] == []
        # 有题目关联的二级不能移动父级
        insert_question(connection, 501)
        link(connection, 501, [point['id']], point['id'])
        another = await save_directory(db, {'name': '线段与角', 'subject_id': 1, 'level': 1})
        try:
            await save_directory(db, {'name': '乘方', 'subject_id': 1, 'level': 2,
                                      'parent_id': another['id']}, point['id'])
        except HTTPException as error:
            assert error.status_code == 409, error
        else:
            raise AssertionError('有引用的二级被移动')
    async_test(scenario())


def test_backfill_assertions():
    def run(item, point_ids, primary):
        connection = build_database()
        seed_tree(connection)
        connection.execute("UPDATE knowledge_point SET code='P11' WHERE id=11")
        connection.execute("UPDATE knowledge_point SET code='P12' WHERE id=12")
        connection.commit()
        insert_question(connection, 700)
        if point_ids:
            link(connection, 700, point_ids, primary)
        guard, structure = assertion_sql([item])
        connection.execute(guard)
        connection.execute(structure)
        return connection

    def expect(code, item, point_ids, primary):
        connection = build_database()
        seed_tree(connection)
        connection.execute("UPDATE knowledge_point SET code='P11' WHERE id=11")
        connection.execute("UPDATE knowledge_point SET code='P12' WHERE id=12")
        connection.commit()
        insert_question(connection, 700)
        if point_ids:
            link(connection, 700, point_ids, primary)
        guard, structure = assertion_sql([item])
        try:
            connection.execute(guard)
            connection.execute(structure)
        except Exception as error:
            if code in str(error):
                return
            raise AssertionError('期望 ' + code + '，实际 ' + str(error))
        raise AssertionError('期望 ' + code + ' 失败，但断言通过')
    full = {'question_id': 700, 'knowledge_revision': 0,
            'codes': ['P11', 'P12'], 'primary_code': 'P11'}
    run(full, [11, 12], 11)
    expect('KP_STRUCT', full, [11], 11)
    expect('KP_STRUCT', full, [11, 12], 12)
    extra = {'question_id': 700, 'knowledge_revision': 0,
             'codes': ['P11'], 'primary_code': 'P11'}
    expect('KP_STRUCT', extra, [11, 12], 11)
    missing = {'question_id': 700, 'knowledge_revision': 0,
               'codes': ['MISSING', 'P11'], 'primary_code': 'P11'}
    expect('KP_GUARD', missing, [11], 11)


def test_question_save_path():
    async def scenario():
        connection = build_database()
        seed_tree(connection)
        db = SQLiteDB(connection)
        row = await save(db, {
            'subject_id': 1, 'parsed_question': '题干', 'difficulty': 3,
            'knowledge_point_ids': [11, 12], 'primary_knowledge_point_id': 11,
        }, request=None)
        question_id = row['id']
        assert row['knowledge_revision'] == 0
        assert row['knowledge_point'] == '乘方'
        assert sorted(point['id'] for point in row['knowledge_points']) == [11, 12]
        assert next(point for point in row['knowledge_points'] if point['is_primary'])['id'] == 11
        # 只改内容不传分类：不要求版本，保留全部关联
        updated = await save(db, {'parsed_question': '新题干'}, question_id, request=None)
        assert updated['knowledge_revision'] == 0
        assert sorted(point['id'] for point in updated['knowledge_points']) == [11, 12]
        # 分类变化必须携带读取时的版本
        try:
            await save(db, {'knowledge_point_ids': [12], 'primary_knowledge_point_id': 12,
                            'knowledge_revision': 9}, question_id, request=None)
        except HTTPException as error:
            assert error.status_code == 409, error
        else:
            raise AssertionError('过期版本未被拒绝')
        changed = await save(db, {'knowledge_point_ids': [12], 'primary_knowledge_point_id': 12,
                                  'knowledge_revision': 0}, question_id, request=None)
        assert changed['knowledge_revision'] == 1
        assert [point['id'] for point in changed['knowledge_points']] == [12]
        assert changed['knowledge_point'] == '混合运算'
        # 旧客户端回传当前主考点名：保留多考点
        multi = await save(db, {'knowledge_point_ids': [11, 12], 'primary_knowledge_point_id': 11,
                                'knowledge_revision': 1}, question_id, request=None)
        assert multi['knowledge_revision'] == 2
        same = await save(db, {'knowledge_point': '乘方'}, question_id, request=None)
        assert same['knowledge_revision'] == 2
        assert sorted(point['id'] for point in same['knowledge_points']) == [11, 12]
        # 空数组明确清空
        cleared = await save(db, {'knowledge_point_ids': [], 'knowledge_revision': 2},
                             question_id, request=None)
        assert cleared['knowledge_points'] == []
        assert cleared['knowledge_point'] is None
        assert cleared['knowledge_revision'] == 3
        # 改学科但未提交新关联被拒绝
        back = await save(db, {'knowledge_point_ids': [11], 'primary_knowledge_point_id': 11,
                               'knowledge_revision': 3}, question_id, request=None)
        assert back['knowledge_revision'] == 4
        try:
            await save(db, {'subject_id': 2, 'knowledge_revision': 4}, question_id, request=None)
        except HTTPException as error:
            assert error.status_code == 422 and '改学科' in str(error.detail), error
        else:
            raise AssertionError('改学科未要求新关联')
        # 同批次先清旧关联再改学科
        moved = await save(db, {'subject_id': 2, 'knowledge_point_ids': [31], 'primary_knowledge_point_id': 31,
                                'knowledge_revision': 4}, question_id, request=None)
        assert moved['knowledge_revision'] == 5
        assert moved['knowledge_point'] == '可数名词'
        assert [point['id'] for point in moved['knowledge_points']] == [31]
    async_test(scenario())


def main():
    check('名称规范化', test_name_normalization)
    check('目录层级与重名约束', test_tree_constraints)
    check('题目关联约束', test_link_constraints)
    check('题目改学科保护', test_question_subject_guard)
    check('删除引用保护', test_delete_protection)
    check('移动与改学科保护', test_move_and_subject_change)
    check('错误类型只挂二级', test_error_type_constraint)
    check('学科删除保护', test_subject_delete_guard)
    check('版本守卫与结构断言', test_guard_and_structure_assertions)
    check('目录版本递增', test_taxonomy_version_bump)
    check('旧文本兼容规则', test_legacy_compatibility)
    check('一级/二级聚合口径', test_module_stats)
    check('模块练习正确率', test_practice_accuracy)
    check('时间窗口口径', test_stats_time_window)
    check('筛选组合校验', test_filter_path_validation)
    check('软删除后的指标', test_soft_delete_metrics)
    check('目录 CRUD 与引用保护', test_directory_crud)
    check('回填集合完整性断言', test_backfill_assertions)
    check('单题保存原子路径', test_question_save_path)
    failed = [item for item in RESULTS if not item[1]]
    print('\n合计 {} 项，通过 {} 项，失败 {} 项'.format(
        len(RESULTS), len(RESULTS) - len(failed), len(failed)))
    if failed:
        for name, _, detail in failed:
            print('失败：' + name + ' -> ' + detail)
        raise SystemExit(1)


if __name__ == '__main__':
    main()
