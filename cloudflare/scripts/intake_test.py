"""录题与卷子功能的本地测试。

用生产库的结构快照（d1_schema_before_0011.sql）加种子数据重建迁移前的库，
再执行迁移 0011。后续任务会在本脚本中追加录入接口、卷子接口等测试。运行：

    python cloudflare/scripts/intake_test.py
"""

import asyncio
import json
import pathlib
import sqlite3
import sys
import traceback
import uuid

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
sys.path.insert(0, str(ROOT / 'scripts'))

from fastapi import HTTPException  # noqa: E402
from fastapi.responses import JSONResponse  # noqa: E402
from knowledge_invariants_test import SQLiteDB  # noqa: E402  复用生产异步接口的 sqlite 适配器
import analytics  # noqa: E402
import intake  # noqa: E402
import settings  # noqa: E402
import practices  # noqa: E402
import similar  # noqa: E402
from knowledge_stats import module_stats  # noqa: E402
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


# ---------------------------------------------------------------- 任务 3 的测试助手


def add_question(connection, subject_id=1, status='approved', point_id=101, grade=6, semester=1):
    """插入一道指定审核状态的题；point_id 不为 None 时再挂上一条主考点关联，返回题目编号。"""
    cursor = connection.execute(
        'INSERT INTO question(subject_id,grade,semester,original_text,parsed_question,'
        'review_count,correct_count,error_count,review_status,deleted,created_at,updated_at) '
        "VALUES(?,?,?,'新题','新题',0,0,0,?,0,'2026-11-01 00:00:00','2026-11-01 00:00:00')",
        (subject_id, grade, semester, status))
    question_id = cursor.lastrowid
    if point_id is not None:
        connection.execute(
            'INSERT INTO question_knowledge_point(question_id,knowledge_point_id,is_primary,source,deleted,'
            "created_at,updated_at) VALUES(?,?,1,'manual',0,'2026-11-01 00:00:00','2026-11-01 00:00:00')",
            (question_id, point_id))
    connection.commit()
    return question_id


class FakeEnv:
    """伪造 Cloudflare 的 env，DB 属性放测试库。"""

    def __init__(self, db):
        self.DB = db


class FakeRequest:
    """伪造 FastAPI 的 Request，只提供 scope 与 json()。"""

    def __init__(self, payload, db):
        self.scope = {'env': FakeEnv(db)}
        self.payload = payload

    async def json(self):
        """返回构造时给定的请求体。"""
        return self.payload


def fake_request(payload, db, module):
    """造一个假请求，并把 module.Database 换成"原样返回 env.DB"的函数。

    替换会一直保留到测试进程结束（协程是在这之后才运行的，不能提前还原）；
    每个测试都自己建库并通过请求的 env 传入，所以不会互相串库。
    """
    module.Database = lambda binding: binding
    return FakeRequest(payload, db)


async def call_endpoint(module, endpoint, payload, db):
    """用假请求调用模块里的接口函数并等待结果。"""
    return await endpoint(fake_request(payload, db, module))


# ---------------------------------------------------------------- 任务 3：统计口径


def test_pending_question_not_counted_in_module_stats():
    """待核对的题不进考点统计；通过后才计入。"""
    c = build_database()
    db = adapter(c)
    before = run(module_stats(db, subject_id=1, level=1))['total_questions']
    pending_id = add_question(c, status='pending')
    assert run(module_stats(db, subject_id=1, level=1))['total_questions'] == before
    c.execute("UPDATE question SET review_status='approved' WHERE id=?", (pending_id,))
    assert run(module_stats(db, subject_id=1, level=1))['total_questions'] == before + 1


def test_pending_question_not_counted_in_grouped_and_primary_counts():
    """待核对的题不进分组统计和一级模块题数。"""
    c = build_database()
    db = adapter(c)
    before = run(analytics.grouped(db, 'grade'))
    before_modules = run(analytics.primary_module_counts(db))
    add_question(c, status='pending')
    assert run(analytics.grouped(db, 'grade')) == before
    assert run(analytics.primary_module_counts(db)) == before_modules


def test_pending_question_not_selected_for_practice():
    """自动选题不会选中待核对的题。"""
    c = build_database()
    db = adapter(c)
    c.execute('UPDATE question SET deleted=1')  # 只留一道待核对的题
    add_question(c, status='pending')
    expect_http(400, lambda: run(call_endpoint(practices, practices.generate_questions,
                                               {'subject_id': 1, 'count': 5}, db)))


def test_pending_question_rejected_by_create_set_and_similar():
    """手工建卷和生成相似题都拒绝待核对的题。"""
    c = build_database()
    db = adapter(c)
    pending_id = add_question(c, status='pending')
    expect_http(400, lambda: run(call_endpoint(practices, practices.create,
                                               {'question_ids': [pending_id]}, db)))
    expect_http(409, lambda: run(similar.generate(pending_id, fake_request({}, db, similar))))


# ---------------------------------------------------------------- 任务 4：录入资料接口


def guide_request(db):
    """造 guide 用的假请求，并把 settings.Database 一并换成测试库。"""
    fake_request({}, db, settings)
    return fake_request({}, db, intake)


def test_guide_returns_catalog_for_grade():
    """六年级数学返回目录、错因和选项标签。"""
    c = build_database()
    db = adapter(c)
    data = run(intake.guide(guide_request(db), subject_id=1, grade=6, semester=1))
    assert data['spec_version'] == 1 and data['subject'] == {'id': 1, 'name': '数学'}
    assert data['subjects'] == [{'id': 1, 'name': '数学'}, {'id': 2, 'name': '英语'}]
    assert data['catalog_available'] is True
    assert data['knowledge_modules'] == [{'id': 100, 'name': '分数运算',
                                          'points': [{'id': 101, 'name': '分数乘法'},
                                                     {'id': 102, 'name': '分数除法'}]}]
    assert data['error_types'] == ['概念错误', '计算错误']
    assert data['paper_types'] == {'homework': '作业', 'chapter_practice': '章节练习', 'exam': '考试'}
    assert data['exam_kinds'] == {'unit': '单元测', 'midterm': '期中', 'final': '期末', 'other': '其他'}
    assert data['review_reasons'] == {'wrong_unclear': '不确定这题是否做错了', 'text_unclear': '照片模糊或题干拿不准',
                                      'kp_unsure': '目录里找不到合适的考点', 'other': '其他'}


def test_guide_accepts_subject_name_and_rejects_unknown():
    """学科可按名称给；没给或找不到返回 400。"""
    c = build_database()
    db = adapter(c)
    assert run(intake.guide(guide_request(db), subject='英语', grade=6))['subject']['id'] == 2
    expect_http(400, lambda: run(intake.guide(guide_request(db), subject='物理')))
    expect_http(400, lambda: run(intake.guide(guide_request(db))))


def test_guide_marks_missing_catalog():
    """七年级没有目录时 catalog_available 为 false。"""
    c = build_database()
    db = adapter(c)
    data = run(intake.guide(guide_request(db), subject_id=1, grade=7))
    assert data['catalog_available'] is False and data['knowledge_modules'] == []


def test_guide_uses_app_default_grade():
    """没给年级学期时用应用默认值；没有默认值就是 null。"""
    c = build_database()
    db = adapter(c)
    data = run(intake.guide(guide_request(db), subject_id=1))
    assert (data['grade'], data['semester'], data['default_grade']) == (None, None, None)
    assert data['catalog_available'] is True
    c.execute("INSERT INTO runtime_config(name,value,deleted,updated_at) VALUES('app','{\"default_grade\":6,\"default_semester\":1}',0,CURRENT_TIMESTAMP)")
    data = run(intake.guide(guide_request(db), subject_id=1))
    assert (data['grade'], data['semester'], data['default_grade'], data['default_semester']) == (6, 1, 6, 1)


def test_guide_rejects_out_of_range_grade_and_semester():
    """年级、学期超出范围返回 422。"""
    c = build_database()
    db = adapter(c)
    expect_http(422, lambda: run(intake.guide(guide_request(db), subject_id=1, grade=13)))
    expect_http(422, lambda: run(intake.guide(guide_request(db), subject_id=1, semester=3)))


def test_load_catalog_filters_and_skips_deleted():
    """目录按年级筛选、跳过已删除的点、没有二级考点的模块不出现。"""
    c = build_database()
    db = adapter(c)
    assert run(intake.load_catalog(db, 2, 6, 1)) == [{'id': 200, 'name': '语法', 'points': [{'id': 201, 'name': '一般现在时'}]}]
    c.execute('UPDATE knowledge_point SET deleted=1 WHERE id=201')
    assert run(intake.load_catalog(db, 2, 6, 1)) == []


def test_load_error_type_names_includes_general():
    """错因含本学科的和通用的；英语只有通用的。"""
    c = build_database()
    db = adapter(c)
    assert run(intake.load_error_type_names(db, 1)) == {'计算错误', '概念错误'}
    assert run(intake.load_error_type_names(db, 2)) == {'概念错误'}


# ---------------------------------------------------------------- 任务 5：试提交与正式提交


async def noop_math_validator(request, texts):
    """默认的公式校验：什么都不做（真实的要调用 Cloudflare 服务绑定）。"""
    return None


def use_failing_math_validator(message):
    """让公式校验抛出 422，说明文字为 message。"""
    async def failing(request, texts):
        raise HTTPException(422, message)
    intake.validate_math = failing


def with_noop_validator(function):
    """装饰测试：运行前先把公式校验换回什么都不做的版本，避免上一个测试的设置串过来。"""
    def wrapper():
        intake.validate_math = noop_math_validator
        function()
    wrapper.__name__ = function.__name__
    wrapper.__doc__ = function.__doc__
    return wrapper


def sample_payload(**overrides):
    """返回一份合格的六年级数学卷子请求；spec_version、request_id 改顶层，其余键改 paper。"""
    payload = {
        'spec_version': 1,
        'request_id': uuid.uuid4().hex[:20],
        'paper': {'subject_id': 1, 'grade': 6, 'semester': 1, 'name': '', 'paper_type': 'homework',
                  'images': ['2026/11/aaaaaaaa_p1.jpg', '2026/11/bbbbbbbb_p2.jpg']},
        'questions': [
            {'page': 1, 'question_no': '1', 'parsed_question': '计算 1/2 乘 2/3', 'answer': '1/3',
             'analysis': '分子相乘，分母相乘', 'wrong_answer': '1/6', 'wrong_evidence': '老师打叉',
             'difficulty': 3, 'error_type': '计算错误',
             'knowledge_point_ids': [101], 'primary_knowledge_point_id': 101},
            {'page': 2, 'question_no': '2', 'parsed_question': '计算 1/2 除以 2/3', 'answer': '3/4',
             'analysis': '除以一个数等于乘它的倒数', 'wrong_answer': '1/3', 'wrong_evidence': '老师打叉',
             'difficulty': 3, 'error_type': '计算错误',
             'knowledge_point_ids': [102], 'primary_knowledge_point_id': 102},
        ],
    }
    for key, value in overrides.items():
        if key in ('spec_version', 'request_id'):
            payload[key] = value
        else:
            payload['paper'][key] = value
    return payload


def unpack(result, default_status):
    """把接口返回值统一成 (状态码, 字典)：JSONResponse 取它的状态码并解析内容。"""
    if isinstance(result, JSONResponse):
        return result.status_code, json.loads(result.body)
    return default_status, result


def submit(db, payload):
    """调用正式提交接口，返回 (状态码, 内容)。"""
    return unpack(run(intake.submit_paper(fake_request(payload, db, intake))), 201)


def check_only(db, payload):
    """调用试提交接口，返回 (状态码, 内容)。"""
    return unpack(run(intake.check_paper(fake_request(payload, db, intake))), 200)


@with_noop_validator
def test_submit_writes_paper_and_questions():
    """正式提交写入卷子、题目和考点关联，图片路径和来源都对。"""
    c = build_database(); db = adapter(c)
    status, body = submit(db, sample_payload())
    assert status == 201 and body['approved_count'] == 2 and body['pending_count'] == 0 and body['replayed'] is False
    paper = c.execute("SELECT name,paper_type,source,student_id,images FROM paper WHERE source='agent'").fetchone()
    assert tuple(paper)[:4] == ('数学习题 ' + body['paper']['paper_date'], 'homework', 'agent', 1)
    assert paper[4] == '["2026/11/aaaaaaaa_p1.jpg", "2026/11/bbbbbbbb_p2.jpg"]'
    assert body['paper']['images'] == ['2026/11/aaaaaaaa_p1.jpg', '2026/11/bbbbbbbb_p2.jpg']
    rows = c.execute('SELECT paper_page,original_image,original_images,review_status,grade,semester FROM question WHERE paper_id=? ORDER BY id', (body['paper']['id'],)).fetchall()
    assert [tuple(r) for r in rows] == [
        (1, '2026/11/aaaaaaaa_p1.jpg', '["2026/11/aaaaaaaa_p1.jpg"]', 'approved', 6, 1),
        (2, '2026/11/bbbbbbbb_p2.jpg', '["2026/11/bbbbbbbb_p2.jpg"]', 'approved', 6, 1)]
    sources = {r[0] for r in c.execute('SELECT source FROM question_knowledge_point WHERE question_id IN (SELECT id FROM question WHERE paper_id=?)', (body['paper']['id'],))}
    assert sources == {'agent'}
    # 返回的题带两级考点；旧文字字段是主考点名称
    assert [q['knowledge_point'] for q in body['questions']] == ['分数乘法', '分数除法']
    stored = c.execute('SELECT knowledge_point,knowledge_revision,student_id,subject_id,review_reasons,review_note FROM question WHERE paper_id=? ORDER BY id LIMIT 1', (body['paper']['id'],)).fetchone()
    assert tuple(stored) == ('分数乘法', 0, 1, 1, '[]', '')


@with_noop_validator
def test_check_writes_nothing():
    """试提交不写任何东西。"""
    c = build_database(); db = adapter(c)
    counts = lambda: (c.execute('SELECT COUNT(*) FROM question').fetchone()[0], c.execute('SELECT COUNT(*) FROM paper').fetchone()[0],
                      c.execute('SELECT COUNT(*) FROM request_record').fetchone()[0])
    before = counts()
    status, body = check_only(db, sample_payload())
    assert status == 200 and body['ok'] is True and body['approved_count'] == 2 and counts() == before
    assert body['total_count'] == 2 and body['pending_count'] == 0 and body['errors'] == []


@with_noop_validator
def test_one_bad_question_rejects_whole_paper():
    """一道题不合格，整份都不写入。"""
    c = build_database(); db = adapter(c)
    before = c.execute('SELECT COUNT(*) FROM question').fetchone()[0]
    payload = sample_payload(); payload['questions'][1]['knowledge_point_ids'] = [999]; payload['questions'][1]['primary_knowledge_point_id'] = 999
    status, body = submit(db, payload)
    assert status == 422 and [e['index'] for e in body['errors']] == [1]
    assert body['detail'] == '有 1 处需要修改'
    assert c.execute('SELECT COUNT(*) FROM question').fetchone()[0] == before
    assert c.execute("SELECT COUNT(*) FROM paper WHERE source='agent'").fetchone()[0] == 0
    assert c.execute('SELECT COUNT(*) FROM request_record').fetchone()[0] == 0


@with_noop_validator
def test_all_errors_are_reported_together():
    """卷子和各题的错误一起报，卷子级在前，题目按序号。"""
    c = build_database(); db = adapter(c)
    payload = sample_payload(score=120, full_score=100); payload['questions'][0]['parsed_question'] = ''
    payload['questions'][1]['page'] = 9
    status, body = check_only(db, payload)
    assert body['ok'] is False and [e['index'] for e in body['errors']] == [None, 0, 1]
    assert (body['total_count'], body['approved_count'], body['pending_count']) == (0, 0, 0)


@with_noop_validator
def test_knowledge_point_of_other_subject_is_rejected():
    """别的学科的考点被拒绝。"""
    c = build_database(); db = adapter(c)
    payload = sample_payload(); payload['questions'][0].update(knowledge_point_ids=[201], primary_knowledge_point_id=201)
    assert submit(db, payload)[0] == 422


@with_noop_validator
def test_math_error_is_reported_without_index():
    """公式校验的错误没有题号，说明照搬校验器的话。"""
    c = build_database(); db = adapter(c)
    use_failing_math_validator('公式边界不匹配')
    status, body = submit(db, sample_payload())
    assert status == 422 and body['errors'] == [{'index': None, 'detail': '公式边界不匹配'}]
    assert c.execute("SELECT COUNT(*) FROM paper WHERE source='agent'").fetchone()[0] == 0


@with_noop_validator
def test_pending_decisions_are_stored():
    """待核对的原因和备注按约定格式存下来。"""
    c = build_database(); db = adapter(c)
    payload = sample_payload()
    payload['questions'][0].update(wrong_evidence='')
    payload['questions'][1].update(needs_review=True, review_reasons=['text_unclear'], review_note='右下角被手挡住')
    status, body = submit(db, payload)
    assert status == 201 and (body['approved_count'], body['pending_count']) == (0, 2)
    rows = c.execute('SELECT review_status,review_reasons,review_note FROM question WHERE paper_id=? ORDER BY id', (body['paper']['id'],)).fetchall()
    assert [tuple(r) for r in rows] == [('pending', '["wrong_unclear"]', ''), ('pending', '["text_unclear"]', '右下角被手挡住')]


@with_noop_validator
def test_no_catalog_for_grade_keeps_questions_approved():
    """这个年级没有考点目录时，没考点的题照样直接入库。"""
    # Review Focus 1
    c = build_database(); db = adapter(c)
    payload = sample_payload(grade=7)
    for q in payload['questions']:
        q.update(knowledge_point_ids=[], primary_knowledge_point_id=None)
    status, body = submit(db, payload)
    assert status == 201 and body['pending_count'] == 0


@with_noop_validator
def test_same_request_id_is_not_written_twice():
    """同一个 request_id 再交，不重复写入，原样返回第一次的结果。"""
    # Review Focus 2
    c = build_database(); db = adapter(c)
    payload = sample_payload()
    first = submit(db, payload); second = submit(db, payload)
    assert first[0] == 201 and second[0] == 200 and second[1]['replayed'] is True
    assert second[1]['paper']['id'] == first[1]['paper']['id']
    assert [q['id'] for q in second[1]['questions']] == [q['id'] for q in first[1]['questions']]
    assert (second[1]['total_count'], second[1]['approved_count']) == (2, 2)
    assert c.execute("SELECT COUNT(*) FROM paper WHERE source='agent'").fetchone()[0] == 1
    assert c.execute('SELECT COUNT(*) FROM question WHERE paper_id=?', (first[1]['paper']['id'],)).fetchone()[0] == 2


@with_noop_validator
def test_replay_does_not_validate_again():
    """重放只读不校验：即使公式校验现在会失败，也照样返回第一次的结果。"""
    c = build_database(); db = adapter(c)
    payload = sample_payload()
    assert submit(db, payload)[0] == 201
    use_failing_math_validator('不应被调用')
    status, body = submit(db, payload)
    assert status == 200 and body['replayed'] is True


@with_noop_validator
def test_racing_duplicate_request_record_is_a_replay():
    """两次相同提交撞车：记录已被别人写入时，本次按重放处理而不是 500。"""
    c = build_database(); db = adapter(c)
    payload = sample_payload()
    first = submit(db, payload)
    # 模拟"查记录时还没有、写入时已经有了"：隐藏记录一次再恢复，让提交走到写入这一步
    real_first = db.first
    state = {'hidden': True}

    async def blind_first(sql, parameters=()):
        if state['hidden'] and 'FROM request_record' in sql:
            state['hidden'] = False
            return None
        return await real_first(sql, parameters)
    db.first = blind_first
    status, body = submit(db, payload)
    assert status == 200 and body['replayed'] is True and body['paper']['id'] == first[1]['paper']['id']
    assert c.execute("SELECT COUNT(*) FROM paper WHERE source='agent'").fetchone()[0] == 1


@with_noop_validator
def test_spec_version_mismatch_and_request_id_rules():
    """版本不一致返回 409；request_id 不合规返回 422。"""
    c = build_database(); db = adapter(c)
    status, body = submit(db, sample_payload(spec_version=2))
    assert status == 409 and body['spec_version'] == 1 and '录入规范' in body['detail']
    assert check_only(db, sample_payload(spec_version=2))[0] == 409
    for bad_id in ['x', 'a' * 65, 'abcdefgh_1', None]:
        bad = sample_payload(); bad['request_id'] = bad_id
        assert submit(db, bad)[0] == 422, bad_id
    # 试提交不要求 request_id
    no_id = sample_payload(); del no_id['request_id']
    assert check_only(db, no_id)[0] == 200


@with_noop_validator
def test_paper_without_images_and_backslashes_survive():
    """没有照片的卷子题目图片为空；题干里的反斜杠原样保存。"""
    c = build_database(); db = adapter(c)
    payload = sample_payload(images=[])
    for q in payload['questions']:
        q['page'] = None
    payload['questions'][0]['parsed_question'] = r'计算：\(\frac{1}{2}\times\frac{2}{3}\)'
    status, body = submit(db, payload)
    assert status == 201
    row = c.execute('SELECT parsed_question,original_image,original_images FROM question WHERE paper_id=? ORDER BY id LIMIT 1', (body['paper']['id'],)).fetchone()
    assert tuple(row) == (r'计算：\(\frac{1}{2}\times\frac{2}{3}\)', None, None)
    assert c.execute('SELECT images FROM paper WHERE id=?', (body['paper']['id'],)).fetchone()[0] == '[]'


@with_noop_validator
def test_question_count_limits():
    """题目数量必须是 1 到 100。"""
    c = build_database(); db = adapter(c)
    empty = sample_payload(); empty['questions'] = []
    assert submit(db, empty)[0] == 422
    many = sample_payload(); many['questions'] = [dict(many['questions'][0]) for _ in range(101)]
    assert submit(db, many)[0] == 422


@with_noop_validator
def test_malformed_paper_and_question_items_are_reported():
    """paper 不是对象、题目项不是对象、错因不在清单里，都按错误报告而不是崩溃。"""
    c = build_database(); db = adapter(c)
    bad_paper = sample_payload(); bad_paper['paper'] = 'x'
    status, body = check_only(db, bad_paper)
    assert body['ok'] is False and body['errors'][0]['index'] is None
    unknown_subject = sample_payload(subject_id=99)
    assert check_only(db, unknown_subject)[1]['errors'][0]['index'] is None
    payload = sample_payload(); payload['questions'][0] = 'not a dict'
    payload['questions'][1]['error_type'] = '粗心'
    status, body = submit(db, payload)
    assert status == 422 and [e['index'] for e in body['errors']] == [0, 1]
    assert '格式不对' in body['errors'][0]['detail'] and '错因' in body['errors'][1]['detail']


@with_noop_validator
def test_math_validator_called_once_and_only_for_math():
    """整份卷子只调用一次公式校验；非数学学科不调用。"""
    c = build_database(); db = adapter(c)
    calls = []

    async def counting(request, texts):
        calls.append(texts)
    intake.validate_math = counting
    assert check_only(db, sample_payload())[1]['ok'] is True
    assert len(calls) == 1 and '计算 1/2 乘 2/3' in calls[0]
    english = sample_payload(subject_id=2)
    for q in english['questions']:
        q.update(knowledge_point_ids=[201], primary_knowledge_point_id=201, error_type='概念错误')
    assert check_only(db, english)[1]['ok'] is True and len(calls) == 1



# ---------------------------------------------------------------- 任务 6：核对接口与错题接口

def call_listing(db, **params):
    """调用 questions.listing；没给的查询参数显式传默认值（直接调用时 Query 默认值不会展开）。"""
    import questions
    values = dict(skip=0, limit=20, subject_id=None, error_book_id=None, grade=None, semester=None,
                  keyword=None, knowledge_point=None, knowledge_parent_id=None, knowledge_point_id=None,
                  unclassified=None, difficulty=None, error_type=None, tag_ids=None, accuracy_range=None,
                  review_status=None, paper_id=None)
    values.update(params)
    return questions.listing(fake_request({}, db, questions), **values)


def review(db, question_id, action):
    """调用核对接口：对指定题执行 approve 或 reject。"""
    return intake.review_question(question_id, fake_request({'action': action}, db, intake))


def test_review_count_and_listing_filter():
    """待核对数量只算待核对题；列表默认带出待核对题，也能只看待核对题。"""
    c = build_database(); db = adapter(c)
    pending_id = add_question(c, status='pending')
    assert run(intake.review_count(fake_request({}, db, intake))) == {'pending': 1}
    listed = run(call_listing(db, review_status='pending'))
    assert [item['id'] for item in listed['items']] == [pending_id]
    assert pending_id in [item['id'] for item in run(call_listing(db))['items']]
    expect_http(422, lambda: run(call_listing(db, review_status='rejected')))


@with_noop_validator
def test_listing_includes_paper_and_reasons():
    """列表按卷子筛选，每题带卷子信息和（空的）核对原因列表。"""
    c = build_database(); db = adapter(c)
    status, body = submit(db, sample_payload(name='第三章单元测试', paper_type='exam'))
    items = run(call_listing(db, paper_id=body['paper']['id']))['items']
    assert len(items) == 2 and items[0]['paper']['name'] == '第三章单元测试'
    assert items[0]['paper']['paper_type'] == 'exam' and items[0]['review_reasons'] == []
    lone = add_question(c)
    row = [item for item in run(call_listing(db))['items'] if item['id'] == lone][0]
    assert row['paper'] is None and row['review_reasons'] == []


def test_review_reasons_parsed_and_detail_has_paper():
    """库里的核对原因文本解析成列表，坏文本给空列表；详情也带 paper。"""
    import questions
    c = build_database(); db = adapter(c)
    question_id = add_question(c, status='pending')
    c.execute('UPDATE question SET review_reasons=? WHERE id=?', ('["wrong_unclear","other"]', question_id))
    c.execute("INSERT INTO paper(id,subject_id,name,paper_type,deleted) VALUES(7,1,'卷子','homework',0)")
    c.execute('UPDATE question SET paper_id=7 WHERE id=?', (question_id,))
    c.commit()
    out = run(questions.detail(question_id, fake_request({}, db, questions)))
    assert out['review_reasons'] == ['wrong_unclear', 'other']
    assert out['paper'] == {'id': 7, 'name': '卷子', 'paper_type': 'homework', 'exam_kind': None, 'paper_date': None}
    c.execute('UPDATE question SET review_reasons=? WHERE id=?', ('不是json', question_id)); c.commit()
    assert run(questions.detail(question_id, fake_request({}, db, questions)))['review_reasons'] == []


def test_approve_and_reject():
    """通过后状态为 approved 并记时间；移除后软删除，待核对数量随之减少。"""
    c = build_database(); db = adapter(c)
    first, second = add_question(c, status='pending'), add_question(c, status='pending')
    out = run(review(db, first, 'approve'))
    assert out['review_status'] == 'approved' and 'paper' in out and out['review_reasons'] == []
    assert c.execute('SELECT reviewed_at FROM question WHERE id=?', (first,)).fetchone()[0]
    assert run(review(db, second, 'reject')) == {'id': second, 'review_status': 'rejected'}
    assert tuple(c.execute('SELECT deleted,review_status FROM question WHERE id=?', (second,)).fetchone()) == (1, 'rejected')
    assert c.execute('SELECT reviewed_at FROM question WHERE id=?', (second,)).fetchone()[0]
    assert run(intake.review_count(fake_request({}, db, intake))) == {'pending': 0}


def test_second_reviewer_gets_conflict():
    """已处理的题再次处理得 409，已移除的题得 404，且不会被改动。"""
    c = build_database(); db = adapter(c)
    question_id = add_question(c, status='pending')
    run(review(db, question_id, 'reject'))
    expect_http(404, lambda: run(review(db, question_id, 'approve')))
    other = add_question(c, status='pending'); run(review(db, other, 'approve'))
    expect_http(409, lambda: run(review(db, other, 'approve')))
    expect_http(409, lambda: run(review(db, other, 'reject')))
    assert c.execute('SELECT deleted FROM question WHERE id=?', (other,)).fetchone()[0] == 0


def test_conditional_update_blocks_late_reviewer():
    """两人同时读到待核对：先到的写入后，晚到的条件更新没有返回行，得 409 且不改数据。"""
    c = build_database(); db = adapter(c)
    question_id = add_question(c, status='pending')
    real_first = db.first

    async def first_with_race(sql, parameters=()):
        """在读取题目之后、条件更新之前，让另一个人先通过这道题。"""
        row = await real_first(sql, parameters)
        if sql.startswith('SELECT id,review_status FROM question'):
            c.execute("UPDATE question SET review_status='approved' WHERE id=?", (question_id,)); c.commit()
        return row
    db.first = first_with_race
    expect_http(409, lambda: run(review(db, question_id, 'reject')))
    assert tuple(c.execute('SELECT deleted,review_status FROM question WHERE id=?', (question_id,)).fetchone()) == (0, 'approved')


def test_approve_requires_primary_knowledge_point():
    """没有主考点不能通过；不认识的操作 422；这两种情况都不改题目。"""
    c = build_database(); db = adapter(c)
    question_id = add_question(c, status='pending', point_id=None)
    expect_http(422, lambda: run(review(db, question_id, 'approve')))
    expect_http(422, lambda: run(review(db, question_id, 'archive')))
    assert c.execute('SELECT review_status FROM question WHERE id=?', (question_id,)).fetchone()[0] == 'pending'
    expect_http(404, lambda: run(review(db, 9999, 'approve')))


def test_save_accepts_new_fields_and_old_page_keeps_them():
    """保存接口认 wrong_answer、question_no；旧页面不带时保持原值；不认识的字段被忽略。"""
    import questions
    c = build_database(); db = adapter(c)
    question_id = add_question(c, status='pending')
    run(questions.save(db, {'wrong_answer': '3/4', 'question_no': '二、5'}, question_id))
    run(questions.save(db, {'answer': '2/3'}, question_id))
    row = c.execute('SELECT wrong_answer,question_no,review_status,answer FROM question WHERE id=?', (question_id,)).fetchone()
    assert tuple(row) == ('3/4', '二、5', 'pending', '2/3')
    run(questions.save(db, {'review_status': 'approved', 'paper_id': 999, 'wrong_evidence': 'x'}, question_id))
    row = c.execute('SELECT review_status,paper_id,wrong_evidence FROM question WHERE id=?', (question_id,)).fetchone()
    assert tuple(row) == ('pending', None, None)


# ---------------------------------------------------------------- 任务 7：卷子接口

import papers  # noqa: E402


def add_question_to_paper(connection, paper_id, status='approved'):
    """插入一道挂在指定卷子下的题，学科、年级、学期取自卷子，返回题目编号。"""
    paper = connection.execute('SELECT subject_id,grade,semester FROM paper WHERE id=?', (paper_id,)).fetchone()
    question_id = add_question(connection, subject_id=paper[0], status=status, grade=paper[1], semester=paper[2])
    connection.execute('UPDATE question SET paper_id=? WHERE id=?', (paper_id, question_id))
    connection.commit()
    return question_id


def call_paper_listing(db, **params):
    """调用 papers.listing；没给的查询参数显式传默认值。"""
    values = dict(skip=0, limit=20, subject_id=None, paper_type=None)
    values.update(params)
    return papers.listing(fake_request({}, db, papers), **values)


def update_paper(db, paper_id, payload):
    """调用 papers.update。"""
    return papers.update(paper_id, fake_request(payload, db, papers))


def test_manual_paper_create_and_list_counts():
    """手工新增的卷子来源为 manual；列表的题数和待核对数一次算出，只数未删除的题。"""
    c = build_database(); db = adapter(c)
    created = run(call_endpoint(papers, papers.create, {'subject_id': 1, 'name': '期中考试', 'paper_type': 'exam',
                                                        'exam_kind': 'midterm', 'paper_date': '2026-11-05',
                                                        'score': 92, 'full_score': 100, 'grade': 6, 'semester': 1}, db))
    assert created['source'] == 'manual' and created['images'] == [] and created['score'] == 92
    stored = c.execute('SELECT source,images,student_id,exam_kind FROM paper WHERE id=?', (created['id'],)).fetchone()
    assert tuple(stored) == ('manual', '[]', 1, 'midterm')
    status, body = submit(db, sample_payload())
    extra = add_question_to_paper(c, body['paper']['id'], status='pending')
    gone = add_question_to_paper(c, body['paper']['id'])
    c.execute('UPDATE question SET deleted=1 WHERE id=?', (gone,)); c.commit()
    listed = run(call_paper_listing(db, subject_id=1))
    by_id = {item['id']: item for item in listed['items']}
    assert by_id[body['paper']['id']]['question_count'] == 3 and by_id[body['paper']['id']]['pending_count'] == 1
    assert by_id[created['id']]['question_count'] == 0 and by_id[created['id']]['subject_name'] == '数学'
    assert listed['total'] == len(listed['items']) and isinstance(by_id[created['id']]['images'], list)
    assert [item['id'] for item in run(call_paper_listing(db, paper_type='exam'))['items']] == [created['id']]
    expect_http(422, lambda: run(call_paper_listing(db, paper_type='quiz')))
    expect_http(422, lambda: run(call_paper_listing(db, limit=0)))


def test_paper_detail_orders_questions_by_page():
    """详情的题目按页码排序并带考点；不存在的卷子 404。"""
    c = build_database(); db = adapter(c)
    status, body = submit(db, sample_payload())
    data = run(papers.detail(body['paper']['id'], fake_request({}, db, papers)))
    assert [q['paper_page'] for q in data['questions']] == [1, 2] and data['questions'][0]['knowledge_points']
    assert data['subject_name'] == '数学' and data['question_count'] == 2 and data['questions'][0]['review_reasons'] == []
    expect_http(404, lambda: run(papers.detail(99999, fake_request({}, db, papers))))


def test_update_rules():
    """改卷子：没给的字段不变，合并后再校验，年级学期同步到题目，学科不能改。"""
    c = build_database(); db = adapter(c)
    status, body = submit(db, sample_payload()); paper_id = body['paper']['id']
    out = run(update_paper(db, paper_id, {'paper_type': 'exam', 'score': 85, 'full_score': 100, 'grade': 6, 'semester': 2}))
    assert (out['paper_type'], out['exam_kind'], out['score']) == ('exam', 'other', 85)
    assert {tuple(r) for r in c.execute('SELECT grade,semester FROM question WHERE paper_id=?', (paper_id,))} == {(6, 2)}
    expect_http(422, lambda: run(update_paper(db, paper_id, {'score': 120})))
    expect_http(422, lambda: run(update_paper(db, paper_id, {'subject_id': 2})))
    assert run(update_paper(db, paper_id, {'name': '改个名'}))['score'] == 85
    stored = c.execute('SELECT name,score,images FROM paper WHERE id=?', (paper_id,)).fetchone()
    assert stored[0] == '改个名' and stored[1] == 85 and len(json.loads(stored[2])) == 2
    expect_http(404, lambda: run(update_paper(db, 99999, {'name': 'x'})))


def test_history_paper_restrictions():
    """历史记录只能改名称和备注，不能删除。"""
    c = build_database(); db = adapter(c)
    history_id = c.execute("SELECT id FROM paper WHERE source='history' LIMIT 1").fetchone()[0]
    assert run(update_paper(db, history_id, {'name': '五年级旧题', 'notes': '搬家前录的'}))['name'] == '五年级旧题'
    expect_http(422, lambda: run(update_paper(db, history_id, {'grade': 5})))
    expect_http(409, lambda: run(papers.remove(history_id, fake_request({}, db, papers), with_questions=1)))


def test_delete_rules():
    """有题时必须明确带题删除；带题删除一次软删卷子和题目。"""
    c = build_database(); db = adapter(c)
    status, body = submit(db, sample_payload()); paper_id = body['paper']['id']
    expect_http(409, lambda: run(papers.remove(paper_id, fake_request({}, db, papers), with_questions=0)))
    assert c.execute('SELECT deleted FROM paper WHERE id=?', (paper_id,)).fetchone()[0] == 0
    response = run(papers.remove(paper_id, fake_request({}, db, papers), with_questions=1))
    assert response.status_code == 204
    assert c.execute('SELECT deleted FROM paper WHERE id=?', (paper_id,)).fetchone()[0] == 1
    assert c.execute('SELECT COUNT(*) FROM question WHERE paper_id=? AND deleted=0', (paper_id,)).fetchone()[0] == 0
    expect_http(404, lambda: run(papers.detail(paper_id, fake_request({}, db, papers))))
    expect_http(404, lambda: run(papers.remove(paper_id, fake_request({}, db, papers), with_questions=1)))


def test_manual_paper_rejects_images():
    """手工新增的卷子不能带照片；学科必须存在。"""
    c = build_database(); db = adapter(c)
    expect_http(422, lambda: run(call_endpoint(papers, papers.create, {'subject_id': 1, 'images': ['2026/11/aaaaaaaa_p1.jpg']}, db)))
    expect_http(400, lambda: run(call_endpoint(papers, papers.create, {'subject_id': 999}, db)))


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
    test_pending_question_not_counted_in_module_stats,
    test_pending_question_not_counted_in_grouped_and_primary_counts,
    test_pending_question_not_selected_for_practice,
    test_pending_question_rejected_by_create_set_and_similar,
    test_guide_returns_catalog_for_grade,
    test_guide_accepts_subject_name_and_rejects_unknown,
    test_guide_marks_missing_catalog,
    test_guide_uses_app_default_grade,
    test_guide_rejects_out_of_range_grade_and_semester,
    test_load_catalog_filters_and_skips_deleted,
    test_load_error_type_names_includes_general,
    test_submit_writes_paper_and_questions,
    test_check_writes_nothing,
    test_one_bad_question_rejects_whole_paper,
    test_all_errors_are_reported_together,
    test_knowledge_point_of_other_subject_is_rejected,
    test_math_error_is_reported_without_index,
    test_pending_decisions_are_stored,
    test_no_catalog_for_grade_keeps_questions_approved,
    test_same_request_id_is_not_written_twice,
    test_replay_does_not_validate_again,
    test_racing_duplicate_request_record_is_a_replay,
    test_spec_version_mismatch_and_request_id_rules,
    test_paper_without_images_and_backslashes_survive,
    test_question_count_limits,
    test_malformed_paper_and_question_items_are_reported,
    test_math_validator_called_once_and_only_for_math,
    test_review_count_and_listing_filter,
    test_listing_includes_paper_and_reasons,
    test_review_reasons_parsed_and_detail_has_paper,
    test_approve_and_reject,
    test_second_reviewer_gets_conflict,
    test_conditional_update_blocks_late_reviewer,
    test_approve_requires_primary_knowledge_point,
    test_save_accepts_new_fields_and_old_page_keeps_them,
    test_manual_paper_create_and_list_counts,
    test_paper_detail_orders_questions_by_page,
    test_update_rules,
    test_history_paper_restrictions,
    test_delete_rules,
    test_manual_paper_rejects_images,
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
