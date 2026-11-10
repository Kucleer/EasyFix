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
from intake_model import (IntakeError, MAX_QUESTIONS, decide_review, default_paper_name,  # noqa: E402
                          normalize_paper, normalize_question)

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


def expect_intake_error(fragment, function):
    """调用函数，要求它抛出 IntakeError 且说明里包含指定文字。"""
    try:
        function()
    except IntakeError as error:
        assert fragment in error.detail, '说明里没有「%s」：%s' % (fragment, error.detail)
        return
    raise AssertionError('期望抛出 IntakeError（含「%s」），但没有抛出' % fragment)


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


# ---------------------------------------------------------------- 任务 2：纯规则 intake_model


def test_paper_defaults():
    """只传学科时，卷子取默认类型、默认名称和今天的日期。"""
    paper = normalize_paper({'subject_id': 1}, '数学', '2026-11-10')
    assert paper['name'] == '数学习题 2026-11-10' == default_paper_name('数学', '2026-11-10')
    assert (paper['paper_type'], paper['exam_kind'], paper['paper_date']) == ('homework', None, '2026-11-10')
    assert paper['images'] == [] and paper['score'] is None and paper['full_score'] is None


def test_paper_blank_name_uses_default_with_given_date():
    """名称为空白时用默认名称，日期取传入的日期。"""
    paper = normalize_paper({'name': '  ', 'paper_date': '2026-11-08'}, '英语', '2026-11-10')
    assert paper['name'] == '英语习题 2026-11-08'


def test_paper_exam_kind_rules():
    """考试细分只在考试时有效，考试默认 other，类型不认识要报错。"""
    assert normalize_paper({'paper_type': 'exam'}, '数学', '2026-11-10')['exam_kind'] == 'other'
    assert normalize_paper({'paper_type': 'homework', 'exam_kind': 'final'}, '数学', '2026-11-10')['exam_kind'] is None
    expect_intake_error('类型', lambda: normalize_paper({'paper_type': 'quiz'}, '数学', '2026-11-10'))


def test_paper_score_rules():
    """得分和满分要么都填要么都不填，且为不超过满分的非负整数。"""
    ok = normalize_paper({'score': 85, 'full_score': 100}, '数学', '2026-11-10')
    assert (ok['score'], ok['full_score']) == (85, 100)
    half = normalize_paper({'score': 85.5, 'full_score': 100}, '数学', '2026-11-10')
    assert (half['score'], half['full_score']) == (85.5, 100)
    for bad in [{'score': float('nan'), 'full_score': 100}, {'score': 1, 'full_score': float('inf')}]:
        expect_intake_error('分', lambda bad=bad: normalize_paper(bad, '数学', '2026-11-10'))
    for bad in [{'score': 85},{'full_score': 100}, {'score': 101, 'full_score': 100},
                {'score': -1, 'full_score': 100}, {'score': '85', 'full_score': 100},
                {'score': True, 'full_score': 100}]:
        expect_intake_error('分', lambda bad=bad: normalize_paper(bad, '数学', '2026-11-10'))


def test_paper_date_and_images_rules():
    """日期不能是未来或格式不对；照片路径必须是上传接口返回的格式。"""
    expect_intake_error('日期', lambda: normalize_paper({'paper_date': '2026-11-11'}, '数学', '2026-11-10'))
    expect_intake_error('日期', lambda: normalize_paper({'paper_date': '11/10'}, '数学', '2026-11-10'))
    assert normalize_paper({'images': ['2026/11/ab12cd34_p1.jpg']}, '数学', '2026-11-10')['images'] == ['2026/11/ab12cd34_p1.jpg']
    for bad in [['../x.jpg'], ['http://a/b.jpg'], 'x', [1]]:
        expect_intake_error('照片', lambda bad=bad: normalize_paper({'images': bad}, '数学', '2026-11-10'))


def test_question_page_rules():
    """有照片时页码必填且在范围内；没有照片时页码必须为空。"""
    base = {'parsed_question': '题干', 'wrong_evidence': '老师打叉'}
    assert normalize_question({**base, 'page': 2}, 2, None)['page'] == 2
    for bad in [{**base}, {**base, 'page': 0}, {**base, 'page': 3}, {**base, 'page': '1'}]:
        expect_intake_error('第几张', lambda bad=bad: normalize_question(bad, 2, None))
    assert normalize_question(base, 0, None)['page'] is None
    expect_intake_error('第几张', lambda: normalize_question({**base, 'page': 1}, 0, None))


def test_question_required_and_ranges():
    """题干必填，难度默认 3 且限定 1 到 5。"""
    expect_intake_error('题干', lambda: normalize_question({'parsed_question': '  '}, 0, None))
    assert normalize_question({'parsed_question': '题干'}, 0, None)['difficulty'] == 3
    expect_intake_error('难度', lambda: normalize_question({'parsed_question': '题干', 'difficulty': 6}, 0, None))


def test_question_error_type_rules():
    """错因逐项对照清单；清单为空或没传时不校验。"""
    names = {'计算错误', '概念错误'}
    ok = normalize_question({'parsed_question': '题干', 'error_type': '计算错误, 概念错误'}, 0, names)
    assert ok['error_type'] == '计算错误,概念错误'
    expect_intake_error('错因', lambda: normalize_question({'parsed_question': '题干', 'error_type': '粗心'}, 0, names))
    assert normalize_question({'parsed_question': '题干', 'error_type': '粗心'}, 0, set())['error_type'] == '粗心'


def test_question_review_fields_rules():
    """标记待核对必须给出合法原因；考点编号必须是整数。"""
    base = {'parsed_question': '题干'}
    expect_intake_error('原因', lambda: normalize_question({**base, 'needs_review': True}, 0, None))
    expect_intake_error('原因', lambda: normalize_question({**base, 'needs_review': True, 'review_reasons': ['blurry']}, 0, None))
    expect_intake_error('考点', lambda: normalize_question({**base, 'knowledge_point_ids': ['101']}, 0, None))


def test_decide_review():
    """判断直接入库还是待核对，原因去重并按固定顺序排列。"""
    clear = {'wrong_evidence': '老师打叉', 'primary_knowledge_point_id': 101, 'needs_review': False, 'review_reasons': []}
    assert decide_review(clear, True) == ('approved', [])
    assert decide_review({**clear, 'wrong_evidence': ''}, True) == ('pending', ['wrong_unclear'])
    assert decide_review({**clear, 'primary_knowledge_point_id': None}, True) == ('pending', ['kp_unsure'])
    # Review Focus 1：这个年级没有目录时，没有考点不算待核对
    assert decide_review({**clear, 'primary_knowledge_point_id': None}, False) == ('approved', [])
    flagged = {**clear, 'needs_review': True, 'review_reasons': ['other', 'text_unclear'], 'wrong_evidence': ''}
    assert decide_review(flagged, True) == ('pending', ['wrong_unclear', 'text_unclear', 'other'])
    # 孩子的答案留空不影响
    assert decide_review({**clear, 'wrong_answer': ''}, True) == ('approved', [])


def test_max_questions_constant():
    """一份卷子最多 100 道题。"""
    assert MAX_QUESTIONS == 100


TESTS = [
    test_migration_seeds_user_and_student,
    test_migration_keeps_question_rows_and_approves_them,
    test_migration_builds_history_papers,
    test_old_insert_without_new_columns_still_works,
    test_student_id_added_to_all_listed_tables,
    test_paper_defaults,
    test_paper_blank_name_uses_default_with_given_date,
    test_paper_exam_kind_rules,
    test_paper_score_rules,
    test_paper_date_and_images_rules,
    test_question_page_rules,
    test_question_required_and_ranges,
    test_question_error_type_rules,
    test_question_review_fields_rules,
    test_decide_review,
    test_max_questions_constant,
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
