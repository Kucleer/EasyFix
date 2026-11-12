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


def build_database(seed_points=True, check_same_thread=True):
    """建立测试库：旧结构 + 必要的单行记录 + 迁移 0011、0012 + 种子考点（seed_points 为假时不写考点）。

    check_same_thread 为假时连接可以在别的线程里用（HTTP 测试客户端在另一个线程里跑应用）。
    """
    connection = sqlite3.connect(':memory:', check_same_thread=check_same_thread)
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
    for point_id, name, subject_id, level, parent_id, learn_grade in (SEED_POINTS if seed_points else []):
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


# ---------------------------------------------------------------- 任务 2：掌握度纯函数


def ev(kind, at, adjust=None):
    """测试用事件：错题、练习做对、手动调整。"""
    return {'kind': kind, 'at': at, 'seq': {'wrong': 0, 'right': 1, 'adjust': 2}[kind], 'adjust': adjust}


def test_leaf_example_from_spec():
    """设计 4.2 的例子：0.5 → 错 0.35 → 错 0.2 → 对 0.35 → 对 0.5 → 再对（最近 3 次全对）→ 1。"""
    from mastery_model import leaf_mastery
    events = [ev('wrong', '1'), ev('wrong', '2'), ev('right', '3'), ev('right', '4')]
    assert abs(leaf_mastery(events) - 0.5) < 1e-9
    assert leaf_mastery(events + [ev('right', '5')]) == 1


def test_leaf_floor_and_no_events():
    """没有事件时是起点 0.5；连续做错停在下限 0.15。"""
    from mastery_model import leaf_mastery
    assert leaf_mastery([]) == 0.5
    assert abs(leaf_mastery([ev('wrong', str(i)) for i in range(6)]) - 0.15) < 1e-9


def test_leaf_mastered_then_wrong():
    """掌握后再做错，从 1 扣 0.15。"""
    from mastery_model import leaf_mastery
    events = [ev('right', '1'), ev('right', '2'), ev('right', '3'), ev('wrong', '4')]
    assert abs(leaf_mastery(events) - 0.85) < 1e-9


def test_adjustments():
    """手动调整按幅度加减；不算进最近 3 次。"""
    from mastery_model import leaf_mastery
    assert abs(leaf_mastery([ev('adjust', '1', 'up_large')]) - 0.85) < 1e-9
    assert leaf_mastery([ev('adjust', '1', 'set_mastered')]) == 1
    assert leaf_mastery([ev('right', '1'), ev('right', '2'), ev('adjust', '3', 'down_small'), ev('right', '4')]) == 1


def test_adjust_only_point_counts_as_learned():
    """只有一条"降低一点"的考点：0.5 − 0.15 = 0.35。"""
    from mastery_model import leaf_mastery
    assert abs(leaf_mastery([ev('adjust', '1', 'down_small')]) - 0.35) < 1e-9


def test_same_time_wrong_before_right():
    """同一时刻的错题排在练习结果前面。"""
    from mastery_model import sort_events
    events = sort_events([ev('right', '2026-11-01'), ev('wrong', '2026-11-01')])
    assert [e['kind'] for e in events] == ['wrong', 'right']


def test_upper_rules():
    """上层星：已学子考点平均值，最高 0.99；子考点全部变绿且没有没学的子考点才是 1。"""
    from mastery_model import upper_mastery
    assert upper_mastery([1, 1, 1], False) == 1
    assert upper_mastery([1, 1, 1], True) == 0.99
    assert upper_mastery([1, 1, 0.85], False) < 1
    assert abs(upper_mastery([0.5, 0.3], False) - 0.4) < 1e-9
    assert upper_mastery([1] * 11, False) == 1


def test_status_and_recent():
    """状态分档；最近结果只看对错、从旧到新。"""
    from mastery_model import status_of, recent_results
    assert [status_of(v) for v in (None, 0.15, 0.4, 0.7, 0.99, 1)] == [
        'unlearned', 'weak', 'fair', 'good', 'good', 'mastered']
    assert recent_results([ev('wrong', '1'), ev('adjust', '2', 'up_small'), ev('right', '3')]) == ['wrong', 'right']


def test_vocab_progress():
    """词汇比例与阶段；空单词本不报错。"""
    from mastery_model import vocab_progress
    assert vocab_progress(0, 0) == {'ratio': 0, 'stage': 0}
    assert vocab_progress(334, 970)['stage'] == 1
    assert vocab_progress(970, 970) == {'ratio': 1, 'stage': 4}


def test_lighting():
    """第一次没有记录时不播放；之后播放新掌握的，掉出掌握的从已看集合里去掉。"""
    from mastery_model import lighting
    assert lighting({1, 2}, None) == (set(), {1, 2})
    assert lighting({1, 2, 3}, {1, 4}) == ({2, 3}, {1})


# ---------------------------------------------------------------- 任务 3：取数与接口


class FakeEnv:
    """只带 DB 绑定的假 env。"""

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


def request_for(db, payload=None):
    """造一个假请求，并让 starmap、settings 模块直接使用传入的 db。"""
    import settings
    import starmap
    starmap.Database = lambda binding: binding
    settings.Database = lambda binding: binding
    return FakeRequest(payload, db)


def add_question(c, qid, subject_id, created_at, points, status='approved', deleted=0, paper_id=None):
    """插入一道错题和它的考点关联（第一个考点是主考点）。"""
    c.execute('INSERT INTO question(id,subject_id,original_text,parsed_question,review_count,correct_count,error_count,'
              'deleted,created_at,updated_at,review_status,paper_id) VALUES(?,?,?,?,0,0,0,0,?,?,?,?)',
              (qid, subject_id, '题%d' % qid, '题%d' % qid, created_at, created_at, status, paper_id))
    for index, point_id in enumerate(points):
        c.execute('INSERT INTO question_knowledge_point(question_id,knowledge_point_id,is_primary,source,deleted) '
                  'VALUES(?,?,?,?,0)', (qid, point_id, 1 if index == 0 else 0, 'test'))
    if deleted:
        c.execute('UPDATE question SET deleted=1 WHERE id=?', (qid,))


def add_paper(c, paper_id, subject_id, paper_date, source='agent'):
    """插入一份卷子。"""
    c.execute('INSERT INTO paper(id,subject_id,name,paper_date,source,deleted) VALUES(?,?,?,?,?,0)',
              (paper_id, subject_id, '卷子%d' % paper_id, paper_date, source))


def add_practice(c, practice_id, reviewed_at, items, deleted=0, subject_id=1):
    """插入一份已批改的练习卷：items 为 [(错题编号, 是否做对或 None, 是否删除)]。"""
    c.execute('INSERT INTO practice_set(id,name,subject_id,deleted,last_reviewed_at,reviewed) VALUES(?,?,?,?,?,1)',
              (practice_id, '练习%d' % practice_id, subject_id, deleted, reviewed_at))
    for order, (qid, correct, item_deleted) in enumerate(items):
        c.execute('INSERT INTO practice_set_question(practice_set_id,question_id,is_correct,display_order,deleted) '
                  'VALUES(?,?,?,?,?)', (practice_id, qid, correct, order, item_deleted))


def add_section(c, section_id, subject_id, chapter_no, section_no, sort_order, point_ids):
    """插入教材的一节和它对应的考点。"""
    c.execute('INSERT INTO textbook_section(id,subject_id,textbook,chapter_no,chapter_name,section_no,section_name,'
              'sort_order,deleted) VALUES(?,?,?,?,?,?,?,?,0)',
              (section_id, subject_id, '测试教材', chapter_no, '第%d章' % chapter_no, section_no, '节' + section_no,
               sort_order))
    for point_id in point_ids:
        c.execute('INSERT INTO textbook_section_point(section_id,knowledge_point_id,deleted) VALUES(?,?,0)',
                  (section_id, point_id))


def set_config(c, name, value):
    """写入一条应用配置。"""
    import json
    c.execute('INSERT INTO runtime_config(name,value,deleted,updated_at) VALUES(?,?,0,CURRENT_TIMESTAMP) '
              'ON CONFLICT(name) DO UPDATE SET value=excluded.value', (name, json.dumps(value)))


def math_fixture():
    """数学场景：101 两道错题后练习做对一次；章节 4.1→111、4.2→112，进度 4.1；101→102 先学后学。"""
    c = build_database()
    add_question(c, 1, 1, '2026-10-01 08:00:00', [101])
    add_question(c, 2, 1, '2026-10-02 08:00:00', [101])
    add_practice(c, 1, '2026-10-05 08:00:00', [(1, 1, 0)])
    add_section(c, 1, 1, 4, '4.1', 41, [111])
    add_section(c, 2, 1, 4, '4.2', 42, [112])
    c.execute('INSERT INTO knowledge_link(from_point_id,to_point_id,deleted) VALUES(101,102,0)')
    set_config(c, 'starmap', {'progress': {'1': '4.1'}})
    c.commit()
    return c


def view(c, subject_id):
    """调用 GET /api/starmap，返回内容。"""
    import starmap
    db = adapter(c)
    return run(starmap.starmap_view(request_for(db), subject_id))


def by_id(body):
    """把返回的节点按编号整理成字典。"""
    return {node['id']: node for node in body['nodes']}


def expect_http_error(status, coroutine):
    """运行协程，要求抛出指定状态码的 HTTPException。"""
    from fastapi import HTTPException
    try:
        run(coroutine)
    except HTTPException as error:
        assert error.status_code == status, error.status_code
        return
    raise AssertionError('没有抛出 %d' % status)


def test_starmap_basic_math():
    """数学：掌握度、状态、最近结果、学过与没学、连线。"""
    body = view(math_fixture(), 1)
    node = by_id(body)
    assert abs(node[101]['value'] - 0.35) < 1e-9 and node[101]['status'] == 'weak'
    assert node[101]['recent'] == ['wrong', 'wrong', 'right'] and node[101]['wrong_count'] == 2
    assert node[102]['value'] == 0.5                      # 有理数模块没有章节对应 → 学过
    assert node[111]['status'] == 'fair' and node[111]['value'] == 0.5
    assert node[112]['status'] == 'unlearned' and node[112]['value'] is None
    assert node[121]['value'] == 0.5                      # 课本外模块 → 学过
    assert {'source': 100, 'target': 101, 'kind': 'belongs'} in body['links']
    assert {'source': 101, 'target': 102, 'kind': 'prereq'} in body['links']
    assert body['vocab'] is None and body['subject_name'] == '数学'
    assert 200 not in node                                 # 只返回本学科


def test_starmap_uses_paper_date_for_wrong_questions():
    """错题时间优先用卷子日期：卷子 10-01 的错题排在 10-03~10-05 三次练习做对之前 → 掌握。"""
    c = math_fixture()
    add_paper(c, 9, 1, '2026-10-01')
    add_question(c, 3, 1, '2026-10-10 08:00:00', [102], paper_id=9)
    for practice_id, day in ((2, '03'), (3, '04'), (4, '05')):
        add_practice(c, practice_id, '2026-10-%s 09:00:00' % day, [(3, 1, 0)])
    c.commit()
    assert by_id(view(c, 1))[102]['value'] == 1
    # 历史作业卷子的日期不可靠，改用录入时间：三次做对之后再错 → 0.85
    c.execute("UPDATE paper SET source='history' WHERE id=9")
    c.commit()
    assert abs(by_id(view(c, 1))[102]['value'] - 0.85) < 1e-9


def test_starmap_ignores_deleted_and_pending():
    """待核对错题、软删除错题、软删除关联、删除的练习卷和练习题、未批改的练习题都不影响掌握度。"""
    c = math_fixture()
    before = by_id(view(c, 1))[101]
    add_question(c, 10, 1, '2026-10-06 08:00:00', [101], status='pending')
    add_question(c, 11, 1, '2026-10-06 08:00:00', [101], deleted=1)
    add_question(c, 12, 1, '2026-10-06 08:00:00', [101])
    c.execute('UPDATE question_knowledge_point SET deleted=1 WHERE question_id=12')
    add_practice(c, 5, '2026-10-07 08:00:00', [(1, 1, 0)], deleted=1)
    add_practice(c, 6, '2026-10-07 08:00:00', [(1, 1, 1), (2, None, 0)])
    c.commit()
    after = by_id(view(c, 1))[101]
    assert (after['value'], after['recent'], after['wrong_count']) == (
        before['value'], before['recent'], before['wrong_count'])


def test_starmap_adjust_only_point_is_learned():
    """没学的考点只要有一条手动调整，就算学过：0.5 + 0.15 = 0.65。"""
    c = math_fixture()
    c.execute("INSERT INTO mastery_adjustment(knowledge_point_id,kind,created_at) VALUES(112,'up_small','2026-10-08')")
    c.commit()
    node = by_id(view(c, 1))[112]
    assert node['status'] != 'unlearned' and abs(node['value'] - 0.65) < 1e-9


def test_starmap_upper_nodes():
    """一级模块取已学子考点平均值。"""
    node = by_id(view(math_fixture(), 1))
    assert abs(node[100]['value'] - (0.35 + 0.5) / 2) < 1e-9
    assert abs(node[110]['value'] - 0.5) < 1e-9          # 只算已学的 111
    # 101：第 2 题还没重做，待重做 1 道、没有全部毕业
    assert node[101]['pending'] == 1 and node[101]['all_graduated'] is False and node[101]['waive_at'] is None
    assert node[102]['pending'] == 0 and node[102]['all_graduated'] is True


def test_starmap_english_learn_grade_and_vocab():
    """英语：学习年级不高于默认年级的算学过；词汇星团按单词本"正确率超过 80%"算掌握。"""
    c = build_database()
    set_config(c, 'app', {'default_grade': 6, 'default_semester': 1})
    for wid, review, correct in ((1, 5, 5), (2, 10, 9), (3, 4, 1)):
        c.execute("INSERT INTO word(id,english,chinese,review_count,correct_count,deleted,created_at,updated_at) "
                  "VALUES(?,?,'词',?,?,0,'2026-10-01','2026-10-01')", (wid, 'w%d' % wid, review, correct))
    c.commit()
    body = view(c, 2)
    node = by_id(body)
    assert node[201]['value'] == 0.5 and node[202]['status'] == 'unlearned'
    assert body['vocab']['mastered'] == 2 and body['vocab']['total'] == 3 and body['vocab']['stage'] == 2


def test_starmap_vocab_empty():
    """单词本为空时词汇星团是 0，不报错。"""
    body = view(build_database(), 2)
    assert body['vocab'] == {'mastered': 0, 'total': 0, 'ratio': 0, 'stage': 0}


def test_starmap_lighting_flow():
    """第一次不播放；新掌握的播放；看过后不再播放；掉出后再掌握又播放。"""
    import starmap
    c = math_fixture()
    assert view(c, 1)['to_play'] == []
    add_practice(c, 7, '2026-10-06 08:00:00', [(1, 1, 0)])
    add_practice(c, 8, '2026-10-07 08:00:00', [(2, 1, 0)])
    c.commit()
    assert view(c, 1)['to_play'] == []                   # 第 2 题只对了 1 次，没毕业，不点亮
    add_practice(c, 12, '2026-10-07 09:00:00', [(2, 1, 0)])
    c.commit()
    body = view(c, 1)
    assert body['to_play'] == [101] and body['mastered_count'] == 1
    db = adapter(c)
    run(starmap.mark_seen(request_for(db, {'subject_id': 1, 'point_ids': [101]})))
    assert view(c, 1)['to_play'] == []
    add_question(c, 20, 1, '2026-10-08 08:00:00', [101])
    c.commit()
    assert view(c, 1)['to_play'] == []                   # 掉出掌握
    for practice_id, day in ((9, '09'), (10, '10'), (11, '11')):
        add_practice(c, practice_id, '2026-10-%s 08:00:00' % day, [(20, 1, 0)])
    c.commit()
    assert view(c, 1)['to_play'] == [101]


def test_adjustment_endpoints():
    """新增、展开一级考点、校验、撤销。"""
    import starmap
    c = math_fixture()
    db = adapter(c)
    created = run(starmap.add_adjustment(request_for(db, {'knowledge_point_id': 102, 'kind': 'up_small'})))
    assert created[0]['knowledge_point_id'] == 102 and created[0]['kind'] == 'up_small'
    expanded = run(starmap.add_adjustment(request_for(db, {'knowledge_point_id': 110, 'kind': 'down_small'})))
    assert sorted(item['knowledge_point_id'] for item in expanded) == [111]     # 112 没学，不展开
    expect_http_error(422, starmap.add_adjustment(request_for(db, {'knowledge_point_id': 102, 'kind': 'bad'})))
    expect_http_error(404, starmap.add_adjustment(request_for(db, {'knowledge_point_id': 999, 'kind': 'up_small'})))
    listing = run(starmap.list_adjustments(request_for(db), 1))
    assert {item['knowledge_point_id'] for item in listing} == {102, 111}
    assert abs(by_id(view(c, 1))[102]['value'] - 0.65) < 1e-9
    target = next(item['id'] for item in listing if item['knowledge_point_id'] == 102)
    run(starmap.remove_adjustment(target, request_for(db)))
    assert by_id(view(c, 1))[102]['value'] == 0.5
    assert {item['knowledge_point_id'] for item in run(starmap.list_adjustments(request_for(db), 1))} == {111}


def test_progress_endpoints():
    """读取节列表、修改进度后 112 变成学过、不存在的节 422。"""
    import starmap
    c = math_fixture()
    db = adapter(c)
    body = run(starmap.get_progress(request_for(db), 1))
    assert body['section_no'] == '4.1' and [s['section_no'] for s in body['sections']] == ['4.1', '4.2']
    run(starmap.save_progress(request_for(db, {'section_no': '4.2'}), 1))
    assert by_id(view(c, 1))[112]['value'] == 0.5
    expect_http_error(422, starmap.save_progress(request_for(db, {'section_no': '9.9'}), 1))


class CountingDB(SQLiteDB):
    """记录执行了多少条 SQL 的数据库适配器。"""

    def __init__(self, connection):
        super().__init__(connection)
        self.calls = 0

    async def all(self, sql, parameters=()):
        self.calls += 1
        return await super().all(sql, parameters)

    async def first(self, sql, parameters=()):
        self.calls += 1
        return await super().first(sql, parameters)


def test_starmap_query_count_is_fixed():
    """考点多少不影响 SQL 条数（不逐个考点查询）。"""
    import starmap
    small = math_fixture()
    counter_small = CountingDB(small)
    run(starmap.starmap_view(request_for(counter_small), 1))
    big = math_fixture()
    for offset in range(20):
        big.execute('INSERT INTO knowledge_point(id,name,name_key,subject_id,level,parent_id,sort_order,deleted) '
                    'VALUES(?,?,?,1,2,120,0,0)', (300 + offset, '考点%d' % offset, 'kp%d' % offset))
        add_question(big, 100 + offset, 1, '2026-10-0%d 08:00:00' % (offset % 9 + 1), [300 + offset])
        add_practice(big, 100 + offset, '2026-10-10 08:00:00', [(100 + offset, 1, 0)])
    set_config(big, 'app', {'default_grade': 6, 'default_semester': 1})
    big.commit()
    counter_big = CountingDB(big)
    run(starmap.starmap_view(request_for(counter_big), 1))
    assert counter_small.calls == counter_big.calls, (counter_small.calls, counter_big.calls)


# ---------------------------------------------------------------- 任务 4：种子数据

SEED_0013 = ROOT / 'migrations' / '0013_starmap_seed.sql'
CATALOG_FILE = ROOT / 'scripts' / 'knowledge_grade6_catalog.json'


def build_database_with_catalog():
    """测试库 + 正式考点目录（knowledge_grade6_catalog.json，含旧英语考点），模拟正式库现状。"""
    import json
    from knowledge_model import normalize_name_key
    c = build_database(seed_points=False)
    subjects = {'数学': 1, '英语': 2}
    points = json.loads(CATALOG_FILE.read_text(encoding='utf-8'))['points']
    ids = {}
    for item in sorted(points, key=lambda p: p['level']):
        parent = ids.get(item['code'].rsplit('-', 1)[0]) if item['level'] == 2 else None
        cursor = c.execute(
            'INSERT INTO knowledge_point(code,name,name_key,subject_id,grade,level,parent_id,sort_order,deleted,'
            'created_at) VALUES(?,?,?,?,?,?,?,?,0,CURRENT_TIMESTAMP)',
            (item['code'], item['name'], normalize_name_key(item['name']), subjects[item['subject']], item['grade'],
             item['level'], parent, item['sort_order']))
        ids[item['code']] = cursor.lastrowid
    c.commit()
    return c


def snapshot(c):
    """种子相关表的内容（不含 runtime_config 里的版本号）。"""
    return [list(map(tuple, c.execute('SELECT * FROM %s ORDER BY id' % table).fetchall()))
            for table in ('knowledge_point', 'textbook_section', 'textbook_section_point', 'knowledge_link')]


def test_seed_sql_applies_and_is_rerunnable():
    """0013 能在有正式目录的库上执行，重复执行结果不变；13 节；英语新考点都有学习年级、年级为空。"""
    c = build_database_with_catalog()
    sql = SEED_0013.read_text(encoding='utf-8')
    c.executescript(sql)
    first = snapshot(c)
    c.executescript(sql)
    assert snapshot(c) == first
    assert c.execute('SELECT COUNT(*) FROM textbook_section WHERE deleted=0').fetchone()[0] == 13
    assert c.execute("SELECT COUNT(*) FROM knowledge_point WHERE code LIKE 'EG-%' AND level=2 AND deleted=0 "
                     "AND (learn_grade IS NULL OR grade IS NOT NULL)").fetchone()[0] == 0
    assert c.execute("SELECT COUNT(*) FROM knowledge_point WHERE code LIKE 'EG-%' AND level=2 AND deleted=0").fetchone()[0] > 0
    # 4.2 角 对应两个考点；每条连线两端都存在
    assert c.execute("SELECT COUNT(*) FROM textbook_section s JOIN textbook_section_point sp ON sp.section_id=s.id "
                     "WHERE s.section_no='4.2'").fetchone()[0] == 2
    assert c.execute('SELECT COUNT(*) FROM knowledge_link').fetchone()[0] == len(
        __import__('json').loads((ROOT / 'scripts' / 'starmap_seed' / 'links.json').read_text(encoding='utf-8')))


def test_seed_builder_rejects_unknown_code():
    """连线里引用了不存在的考点编号时，生成脚本报错并指出编号。"""
    import build_starmap_seed
    english, sections, links = build_starmap_seed.load_inputs()
    try:
        build_starmap_seed.build_sql(english, sections, links + [{'from': 'M6-NOPE-01', 'to': 'M6-RAT-01'}])
    except ValueError as error:
        assert 'M6-NOPE-01' in str(error)
        return
    raise AssertionError('没有报错')


# ---------------------------------------------------------------- 任务 5：英语重新打标


def link_by_code(c, qid, code, primary):
    """按考点编号给错题加一条关联。"""
    point_id = c.execute('SELECT id FROM knowledge_point WHERE code=? AND deleted=0', (code,)).fetchone()[0]
    c.execute('INSERT INTO question_knowledge_point(question_id,knowledge_point_id,is_primary,source,deleted) '
              "VALUES(?,?,?,'manual',0)", (qid, point_id, primary))


def test_retag_replaces_english_links():
    """重新打标：旧关联与旧英语考点软删除，新关联写入且主考点正确，数学不变，重复执行结果不变。"""
    import intake
    from starmap_retag import build_retag_sql
    c = build_database_with_catalog()
    c.executescript(SEED_0013.read_text(encoding='utf-8'))
    for qid, subject_id in ((1, 2), (2, 2), (3, 2), (4, 1)):
        c.execute('INSERT INTO question(id,subject_id,original_text,parsed_question,review_count,correct_count,'
                  "error_count,deleted,created_at,updated_at,knowledge_revision) VALUES(?,?,'题','题',0,0,0,0,"
                  "'2026-10-01','2026-10-01',0)", (qid, subject_id))
    link_by_code(c, 1, 'E6-TEN-01', 1)
    link_by_code(c, 2, 'E6-PRO-01', 1)
    link_by_code(c, 4, 'M6-RAT-07', 1)
    c.commit()
    mapping = [{'question_id': 1, 'point_codes': ['EG-TEN-01'], 'primary_code': 'EG-TEN-01'},
               {'question_id': 2, 'point_codes': ['EG-PRO-01', 'EG-PRO-02'], 'primary_code': 'EG-PRO-02'},
               {'question_id': 3, 'point_codes': [], 'primary_code': None}]
    sql = build_retag_sql(mapping)
    c.executescript(sql)
    c.executescript(sql)
    live = lambda qid: sorted(tuple(r) for r in c.execute(
        'SELECT k.code, l.is_primary FROM question_knowledge_point l JOIN knowledge_point k ON k.id=l.knowledge_point_id '
        'WHERE l.question_id=? AND l.deleted=0', (qid,)).fetchall())
    assert [tuple(r) for r in live(1)] == [('EG-TEN-01', 1)]
    assert [tuple(r) for r in live(2)] == [('EG-PRO-01', 0), ('EG-PRO-02', 1)]
    assert live(3) == []
    assert [tuple(r) for r in live(4)] == [('M6-RAT-07', 1)]
    assert c.execute("SELECT COUNT(*) FROM knowledge_point WHERE code LIKE 'E6-%' AND deleted=0").fetchone()[0] == 0
    assert c.execute('SELECT knowledge_point FROM question WHERE id=2').fetchone()[0] == '物主代词'
    db = adapter(c)
    catalog = run(intake.load_catalog(db, 2, 6, 1))
    codes = {row[0] for row in c.execute('SELECT code FROM knowledge_point WHERE deleted=0 AND subject_id=2')}
    assert catalog and all(code.startswith('EG-') for code in codes)


def test_retag_rejects_bad_mapping():
    """主考点不在考点列表里、或编号不是英语新体系，生成时报错。"""
    from starmap_retag import build_retag_sql
    for bad in ([{'question_id': 1, 'point_codes': ['EG-TEN-01'], 'primary_code': 'EG-TEN-02'}],
                [{'question_id': 1, 'point_codes': ['M6-RAT-07'], 'primary_code': 'M6-RAT-07'}]):
        try:
            build_retag_sql(bad)
        except ValueError:
            continue
        raise AssertionError('没有报错：%r' % bad)


# ---------------------------------------------------------------- 整体审阅后的修复


def test_leaf_no_green_without_three_rights():
    """不靠"最近 3 次全对"或"直接设为掌握"，加加减减最多到 0.99，不算掌握。"""
    from mastery_model import leaf_mastery
    mixed = [ev(k, '%02d' % i) for i, k in enumerate(['right', 'right', 'wrong', 'right', 'right', 'wrong', 'right', 'right'])]
    assert leaf_mastery(mixed) < 1
    assert leaf_mastery([ev('right', '1'), ev('adjust', '2', 'up_large')]) < 1
    assert leaf_mastery([ev('adjust', '1', 'up_large'), ev('adjust', '2', 'up_small')]) < 1


def test_upper_requires_learned_children_good():
    """模块要变绿，已学的子考点都要变绿；只有"较好"不够。"""
    from mastery_model import upper_mastery
    assert upper_mastery([0.5, 0.5, 1], False) < 1
    assert upper_mastery([0.7, 0.85, 1], False) < 1
    assert upper_mastery([0.99, 1, 1], False) == 0.99


def retag_fixture():
    """有正式目录、0013 和三道英语题、一道数学题的库。"""
    c = build_database_with_catalog()
    c.executescript(SEED_0013.read_text(encoding='utf-8'))
    for qid, subject_id in ((1, 2), (2, 2), (3, 2), (4, 1)):
        c.execute('INSERT INTO question(id,subject_id,original_text,parsed_question,review_count,correct_count,'
                  "error_count,deleted,created_at,updated_at,knowledge_revision) VALUES(?,?,'题','题',0,0,0,0,"
                  "'2026-10-01','2026-10-01',0)", (qid, subject_id))
    link_by_code(c, 1, 'E6-TEN-01', 1)
    link_by_code(c, 2, 'E6-PRO-01', 1)
    link_by_code(c, 4, 'M6-RAT-07', 1)
    c.commit()
    return c


def live_links(c, qid):
    """一道题当前未删除的考点关联：[(编号, 是否主考点)]。"""
    return sorted(tuple(r) for r in c.execute(
        'SELECT k.code, l.is_primary FROM question_knowledge_point l JOIN knowledge_point k ON k.id=l.knowledge_point_id '
        'WHERE l.question_id=? AND l.deleted=0', (qid,)).fetchall())


def test_retag_rerun_with_changed_mapping():
    """映射改过后可以重新执行：A → B → A，结果和第一次 A 一样，主考点可以换。"""
    from starmap_retag import build_retag_sql
    c = retag_fixture()
    a = [{'question_id': 1, 'point_codes': ['EG-TEN-01'], 'primary_code': 'EG-TEN-01'},
         {'question_id': 2, 'point_codes': ['EG-PRO-01', 'EG-PRO-02'], 'primary_code': 'EG-PRO-02'},
         {'question_id': 3, 'point_codes': [], 'primary_code': None}]
    b = [{'question_id': 1, 'point_codes': ['EG-TEN-01', 'EG-TEN-03'], 'primary_code': 'EG-TEN-03'},
         {'question_id': 2, 'point_codes': ['EG-PRO-01'], 'primary_code': 'EG-PRO-01'},
         {'question_id': 3, 'point_codes': ['EG-NOU-01'], 'primary_code': 'EG-NOU-01'}]
    c.executescript(build_retag_sql(a))
    first = [live_links(c, q) for q in (1, 2, 3)]
    c.executescript(build_retag_sql(b))
    assert live_links(c, 1) == [('EG-TEN-01', 0), ('EG-TEN-03', 1)] and live_links(c, 3) == [('EG-NOU-01', 1)]
    c.executescript(build_retag_sql(a))
    assert [live_links(c, q) for q in (1, 2, 3)] == first


def test_retag_never_touches_non_english_questions():
    """映射里混进了数学题：数学题的关联和考点文字都不变。"""
    from starmap_retag import build_retag_sql
    c = retag_fixture()
    mapping = [{'question_id': 1, 'point_codes': ['EG-TEN-01'], 'primary_code': 'EG-TEN-01'},
               {'question_id': 2, 'point_codes': ['EG-PRO-01'], 'primary_code': 'EG-PRO-01'},
               {'question_id': 4, 'point_codes': [], 'primary_code': None}]
    c.execute("UPDATE question SET knowledge_point='有理数加减' WHERE id=4")
    c.commit()
    c.executescript(build_retag_sql(mapping))
    assert live_links(c, 4) == [('M6-RAT-07', 1)]
    assert c.execute('SELECT knowledge_point FROM question WHERE id=4').fetchone()[0] == '有理数加减'


def test_retag_stops_when_an_english_question_is_missing():
    """映射漏了一道还挂着旧英语考点的题：执行时报错停下，而不是悄悄删掉它的考点。"""
    from starmap_retag import build_retag_sql
    c = retag_fixture()
    mapping = [{'question_id': 1, 'point_codes': ['EG-TEN-01'], 'primary_code': 'EG-TEN-01'}]   # 漏了第 2 题
    try:
        c.executescript(build_retag_sql(mapping))
    except sqlite3.DatabaseError:
        c.rollback()
        return
    raise AssertionError('漏题时没有报错')


# ---------------------------------------------------------------- 考点卷 Task 2：掌握度新规则


def evq(kind, at, qid, source='practice', order=0, entered=None):
    """测试用事件：带错题编号、算数（gate 为真）。错题事件的录入时间缺省等于 at。"""
    is_question = source == 'question'
    return {'kind': kind, 'at': at, 'seq': 0 if is_question else 1, 'adjust': None, 'source': source,
            'qid': qid, 'order': order, 'gate': True,
            'entered': (entered or at) if is_question else None}


def test_gate_example_two_questions():
    """设计 4.4 的例子：A、B 两道错题，三份卷子后点亮。"""
    from mastery_model import leaf_detail, leaf_mastery
    events = [evq('wrong', '2026-11-01', 1, 'question'), evq('wrong', '2026-11-01', 2, 'question'),
              evq('right', '2026-11-08', 1, order=0), evq('wrong', '2026-11-08', 2, order=1)]
    assert round(leaf_mastery(events), 2) == 0.2
    events += [evq('right', '2026-11-15', 1, order=0), evq('right', '2026-11-15', 2, order=1)]
    assert round(leaf_mastery(events), 2) == 0.5
    events += [evq('right', '2026-11-22', 2)]
    detail = leaf_detail(events)
    assert detail['value'] == 1.0 and detail['pending'] == 0 and detail['all_graduated'] is True


def test_gate_pending_caps_value():
    """8 道错题，3 道连对 2 次毕业，5 道没重做：最多 0.25，不变绿。"""
    from mastery_model import leaf_detail
    events = [evq('wrong', '2026-11-01', q, 'question') for q in range(1, 9)]
    events += [evq('right', '2026-11-0%d' % day, q) for q in (1, 2, 3) for day in (2, 3)]
    detail = leaf_detail(events)
    assert round(detail['value'], 2) == 0.25 and detail['pending'] == 5


def test_gate_new_wrong_on_mastered_drops_to_085():
    """已掌握的考点来一道新错题，从 1 掉到 0.85。"""
    from mastery_model import leaf_mastery
    events = [evq('wrong', '2026-11-01', 1, 'question')] + [evq('right', '2026-11-0%d' % d, 1) for d in (2, 3, 4)]
    assert leaf_mastery(events) == 1.0
    assert round(leaf_mastery(events + [evq('wrong', '2026-11-05', 2, 'question')]), 2) == 0.85


def test_gate_single_question_needs_check():
    """只有一道错题：错、对、对之后不是绿色；再做对一道验收题才点亮。"""
    from mastery_model import leaf_mastery
    events = [evq('wrong', '2026-11-01', 1, 'question'), evq('right', '2026-11-02', 1), evq('right', '2026-11-03', 1)]
    assert round(leaf_mastery(events), 2) == 0.65
    assert leaf_mastery(events + [evq('right', '2026-11-04', 1)]) == 1.0


def test_gate_three_rights_but_not_all_graduated():
    """最近 3 次全对，但第 2 题只对了 1 次：不变绿。"""
    from mastery_model import leaf_mastery
    events = [evq('wrong', '2026-11-01', 1, 'question'), evq('wrong', '2026-11-01', 2, 'question'),
              evq('right', '2026-11-02', 1), evq('right', '2026-11-03', 1), evq('right', '2026-11-04', 2)]
    assert leaf_mastery(events) < 1.0


def test_right_at_one_stays_one():
    """直接设为掌握后再做对一次，仍是 1（不掉到 0.99）。"""
    from mastery_model import leaf_mastery
    assert leaf_mastery([ev('adjust', '2026-11-01', 'set_mastered'), evq('right', '2026-11-02', 1)]) == 1.0


def test_set_mastered_waives_older_questions():
    """直接设为掌握：之前录入的错题视同毕业；之后录入的新错题照常压上限。"""
    from mastery_model import leaf_detail, leaf_mastery
    events = [evq('wrong', '2026-11-01', 1, 'question'), evq('wrong', '2026-11-02', 2, 'question'),
              ev('adjust', '2026-11-05', 'set_mastered')]
    detail = leaf_detail(events)
    assert detail['value'] == 1.0 and detail['pending'] == 0 and detail['waive_at'] == '2026-11-05'
    later = events + [evq('wrong', '2026-11-06', 3, 'question')]
    assert round(leaf_mastery(later), 2) == 0.85


def test_down_small_on_mastered_stays_085():
    """点亮后手动"降低一点"是 0.85，不会被改回 1。"""
    from mastery_model import leaf_mastery
    events = [evq('wrong', '2026-11-01', 1, 'question')] + [evq('right', '2026-11-0%d' % d, 1) for d in (2, 3, 4)]
    assert leaf_mastery(events) == 1.0
    assert round(leaf_mastery(events + [ev('adjust', '2026-11-05', 'down_small')]), 2) == 0.85


def test_same_paper_orders_by_number():
    """同一份卷子同一时刻的两条结果，按卷面题号先后算（交换题号结果不同）。"""
    from mastery_model import leaf_mastery
    base = [evq('wrong', '2026-11-01', 1, 'question'), evq('wrong', '2026-11-01', 2, 'question')]
    right_first = base + [evq('right', '2026-11-08', 1, order=0), evq('wrong', '2026-11-08', 2, order=1)]
    wrong_first = base + [evq('right', '2026-11-08', 1, order=1), evq('wrong', '2026-11-08', 2, order=0)]
    assert round(leaf_mastery(right_first), 2) == 0.2
    assert round(leaf_mastery(wrong_first), 2) == 0.3


def test_events_without_gate_keep_old_behaviour():
    """不带错题编号的事件不参与"待重做""毕业"：错、错、对、对、对仍然是 1。"""
    from mastery_model import leaf_detail
    detail = leaf_detail([ev(k, str(i)) for i, k in enumerate(['wrong', 'wrong', 'right', 'right', 'right'])])
    assert detail['value'] == 1.0 and detail['pending'] == 0 and detail['all_graduated'] is True


def test_upper_all_children_green():
    """一级模块：子考点全部为 1 且没有没学的才是 1，否则平均值最高 0.99；没有子考点时 0.5。"""
    from mastery_model import upper_mastery
    assert upper_mastery([1.0, 1.0], False) == 1.0
    assert upper_mastery([1.0, 0.99], False) == 0.99
    assert upper_mastery([1.0, 1.0], True) == 0.99
    assert upper_mastery([], False) == 0.5


def gate_fixture(default_grade):
    """考点 121 下三道错题：一道题干为空、一道五年级、一道六年级；default_grade 为空时不写应用配置。"""
    c = build_database()
    if default_grade is not None:
        set_config(c, 'app', {'default_grade': default_grade, 'default_semester': 1})
    for qid, grade in ((1, 6), (2, 5), (3, 6)):
        add_question(c, qid, 1, '2026-10-0%d 08:00:00' % qid, [121])
        c.execute('UPDATE question SET grade=? WHERE id=?', (grade, qid))
    c.execute("UPDATE question SET parsed_question=NULL, original_text='  ' WHERE id=1")
    c.commit()
    return c


def test_gate_ignores_empty_stem_and_lower_grade():
    """题干为空、年级低于默认年级的错题不算待重做。"""
    assert by_id(view(gate_fixture(6), 1))[121]['pending'] == 1


def test_gate_without_default_grade():
    """没设默认年级时不按年级筛：五年级的题也算，题干为空的仍不算。"""
    assert by_id(view(gate_fixture(None), 1))[121]['pending'] == 2


def test_question_scope_helpers():
    """题干条件与年级条件的 SQL 片段。"""
    from question_scope import grade_ready, stem_ready
    assert grade_ready('q', None) == ('1=1', [])
    assert grade_ready('a', 6) == ('(a.grade IS NULL OR a.grade>=?)', [6])
    c = sqlite3.connect(':memory:')
    c.execute('CREATE TABLE q(parsed_question TEXT, original_text TEXT)')
    rows = [(None, None), ('  ', ' \n '), (None, '原题'), (' ', '原题'), ('解析', None), ('解析', '')]
    c.executemany('INSERT INTO q VALUES(?,?)', rows)
    ready = [r[0] for r in c.execute('SELECT ' + stem_ready('q') + ' FROM q')]
    assert ready == [0, 0, 1, 1, 1, 1], ready


TESTS = [
    test_migration_adds_tables_and_column,
    test_migration_is_rerunnable,
    test_leaf_example_from_spec,
    test_leaf_floor_and_no_events,
    test_leaf_mastered_then_wrong,
    test_adjustments,
    test_adjust_only_point_counts_as_learned,
    test_same_time_wrong_before_right,
    test_upper_rules,
    test_status_and_recent,
    test_vocab_progress,
    test_lighting,
    test_starmap_basic_math,
    test_starmap_uses_paper_date_for_wrong_questions,
    test_starmap_ignores_deleted_and_pending,
    test_starmap_adjust_only_point_is_learned,
    test_starmap_upper_nodes,
    test_starmap_english_learn_grade_and_vocab,
    test_starmap_vocab_empty,
    test_starmap_lighting_flow,
    test_adjustment_endpoints,
    test_progress_endpoints,
    test_starmap_query_count_is_fixed,
    test_seed_sql_applies_and_is_rerunnable,
    test_seed_builder_rejects_unknown_code,
    test_retag_replaces_english_links,
    test_retag_rejects_bad_mapping,
    test_leaf_no_green_without_three_rights,
    test_upper_requires_learned_children_good,
    test_retag_rerun_with_changed_mapping,
    test_retag_never_touches_non_english_questions,
    test_retag_stops_when_an_english_question_is_missing,
    test_gate_example_two_questions,
    test_gate_pending_caps_value,
    test_gate_new_wrong_on_mastered_drops_to_085,
    test_gate_single_question_needs_check,
    test_gate_three_rights_but_not_all_graduated,
    test_right_at_one_stays_one,
    test_set_mastered_waives_older_questions,
    test_down_small_on_mastered_stays_085,
    test_same_paper_orders_by_number,
    test_events_without_gate_keep_old_behaviour,
    test_upper_all_children_green,
    test_gate_ignores_empty_stem_and_lower_grade,
    test_gate_without_default_grade,
    test_question_scope_helpers,
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
