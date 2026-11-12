"""两级知识点的 HTTP 路由集成测试（本地 SQLite 适配 D1 接口）。

不连接生产 D1；用内存 SQLite 复现 0009 迁移后的结构，验证路由顺序、
请求参数、响应字段与错误映射。运行：

    python cloudflare/scripts/knowledge_api_test.py
"""

import json
import pathlib
import sys
from types import SimpleNamespace

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
sys.path.insert(0, str(ROOT / 'scripts'))

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from analytics import router as analytics_router  # noqa: E402
from knowledge import router as knowledge_router  # noqa: E402
import starmap_test  # noqa: E402  复用建库助手
from practices import router as practices_router  # noqa: E402
from questions import router as questions_router  # noqa: E402
import reports  # noqa: E402
from reports import router as reports_router  # noqa: E402

RESULTS = []
MIGRATION_0015 = ROOT / 'migrations' / '0015_targeted_paper.sql'


def bind(values):
    """把布尔值转换为 SQLite 整数。"""
    return tuple(int(value) if isinstance(value, bool) else value for value in values)


class FakeStatement:
    """模拟 D1PreparedStatement 的异步接口。"""

    def __init__(self, connection, sql, parameters=()):
        self.connection = connection
        self.sql = sql
        self.parameters = parameters

    def bind(self, *values):
        return FakeStatement(self.connection, self.sql, bind(values))

    async def all(self):
        cursor = self.connection.execute(self.sql, self.parameters)
        return SimpleNamespace(results=[dict(row) for row in cursor.fetchall()])

    async def first(self):
        cursor = self.connection.execute(self.sql, self.parameters)
        row = cursor.fetchone()
        return dict(row) if row is not None else None

    async def run(self):
        cursor = self.connection.execute(self.sql, self.parameters)
        return SimpleNamespace(meta={'last_row_id': cursor.lastrowid,
                                     'changes': cursor.rowcount})


class FakeD1:
    """把 sqlite3 适配为 Database 需要的 D1 绑定。"""

    def __init__(self, connection):
        self.connection = connection

    def prepare(self, sql):
        return FakeStatement(self.connection, sql)

    async def batch(self, statements):
        results = []
        self.connection.execute('SAVEPOINT api_batch')
        try:
            for statement in statements:
                cursor = self.connection.execute(statement.sql, statement.parameters)
                results.append({'success': True,
                                'meta': {'last_row_id': cursor.lastrowid,
                                         'changes': cursor.rowcount}})
            self.connection.execute('RELEASE api_batch')
            return results
        except Exception:
            self.connection.execute('ROLLBACK TO api_batch')
            self.connection.execute('RELEASE api_batch')
            raise


def build_client():
    """建立带 DB 注入的隔离应用。"""
    # 用星空测试的库（线上结构基线 + 0011、0012），再补考点卷的 0015：
    # 练习集详情和批改现在要用到这些迁移加的表和列（试卷、学习年级、考点卷字段）
    connection = starmap_test.build_database(seed_points=False, check_same_thread=False)
    connection.executescript(MIGRATION_0015.read_text(encoding='utf-8'))
    connection.execute('INSERT INTO error_type(id,name,subject_id,deleted) VALUES(1,"计算错误",1,0)')
    connection.execute('INSERT INTO error_type(id,name,subject_id,deleted) VALUES(2,"概念错误",NULL,0)')
    from knowledge_invariants_test import seed_tree
    seed_tree(connection)
    connection.commit()
    app = FastAPI()

    @app.middleware('http')
    async def inject(request, call_next):
        request.scope['env'] = SimpleNamespace(DB=FakeD1(connection))
        return await call_next(request)

    app.include_router(knowledge_router)
    app.include_router(questions_router)
    app.include_router(analytics_router)
    app.include_router(reports_router)
    app.include_router(practices_router)
    return TestClient(app), connection


def check(name, function):
    """执行单个用例并记录结果。"""
    try:
        function()
        RESULTS.append((name, True, ''))
        print('PASS  ' + name)
    except Exception as error:  # noqa: BLE001
        RESULTS.append((name, False, str(error)))
        print('FAIL  ' + name + ': ' + str(error))


def expect_status(response, status):
    """断言状态码，并在失败时输出响应内容。"""
    if response.status_code != status:
        raise AssertionError('期望 HTTP ' + str(status) + '，实际 '
                             + str(response.status_code) + '：' + response.text[:500])
    return response


def test_tree_route_order():
    client, _ = build_client()
    response = expect_status(client.get('/api/knowledge-points/tree', params={'subject_id': 1}), 200)
    data = response.json()
    assert data['total'] >= 2
    names = [item['name'] for item in data['items']]
    assert '有理数' in names and '线段与角' in names
    module = next(item for item in data['items'] if item['name'] == '有理数')
    assert any(child['name'] == '乘方' for child in module['children'])
    assert data['taxonomy_version'] is not None


def test_directory_crud_http():
    client, _ = build_client()
    created = expect_status(client.post('/api/knowledge-points', json={
        'name': '一元一次方程', 'subject_id': 1, 'level': 1, 'sort_order': 5,
    }), 201).json()
    assert created['level'] == 1 and created['code']
    child = expect_status(client.post('/api/knowledge-points', json={
        'name': '解方程', 'subject_id': 1, 'level': 2, 'parent_id': created['id'],
    }), 201).json()
    assert child['parent_name'] == '一元一次方程'
    expect_status(client.post('/api/knowledge-points', json={
        'name': '解方程', 'subject_id': 1, 'level': 2, 'parent_id': created['id'],
    }), 409)
    expect_status(client.post('/api/knowledge-points', json={
        'name': '第三级', 'subject_id': 1, 'level': 3,
    }), 422)
    expect_status(client.post('/api/knowledge-points', json={
        'name': '一级挂错误类型', 'subject_id': 1, 'level': 1, 'error_type_ids': [1],
    }), 422)
    renamed = expect_status(client.put('/api/knowledge-points/' + str(created['id']), json={
        'name': '一元一次方程与解法', 'subject_id': 1, 'level': 1, 'parent_id': None,
    }), 200).json()
    assert renamed['id'] == created['id'] and renamed['name'] == '一元一次方程与解法'
    expect_status(client.delete('/api/knowledge-points/' + str(created['id'])), 409)
    expect_status(client.delete('/api/knowledge-points/' + str(child['id'])), 204)
    expect_status(client.delete('/api/knowledge-points/' + str(created['id'])), 204)


def test_question_http_flow():
    client, connection = build_client()
    connection.execute(
        "INSERT INTO knowledge_point(id,name,name_key,subject_id,level,parent_id,sort_order,deleted,created_at) "
        "VALUES(32,'不可数名词','不可数名词',2,2,30,0,0,CURRENT_TIMESTAMP)")
    connection.commit()
    created = expect_status(client.post('/api/questions', json={
        'subject_id': 2, 'parsed_question': 'This is a book.', 'difficulty': 3,
        'knowledge_point_ids': [31], 'primary_knowledge_point_id': 31,
    }), 201).json()
    question_id = created['id']
    assert created['knowledge_point'] == '可数名词'
    assert created['knowledge_revision'] == 0
    assert created['knowledge_points'][0]['parent_name'] == '名词与数量表达'
    listing = expect_status(client.get('/api/questions', params={
        'subject_id': 2, 'knowledge_parent_id': 30,
    }), 200).json()
    assert listing['total'] == 1
    detail = expect_status(client.get('/api/questions/' + str(question_id)), 200).json()
    assert detail['knowledge_points'][0]['id'] == 31
    # 分类实际变化且版本过期返回 409；正确版本成功
    expect_status(client.put('/api/questions/' + str(question_id), json={
        'knowledge_point_ids': [32], 'primary_knowledge_point_id': 32, 'knowledge_revision': 9,
    }), 409)
    updated = expect_status(client.put('/api/questions/' + str(question_id), json={
        'subject_id': 2, 'knowledge_point_ids': [32], 'primary_knowledge_point_id': 32,
        'knowledge_revision': 0,
    }), 200).json()
    assert updated['knowledge_revision'] == 1
    assert updated['knowledge_point'] == '不可数名词'
    # 旧文本回传当前投影不清空关联
    same = expect_status(client.put('/api/questions/' + str(question_id), json={
        'knowledge_point': '不可数名词',
    }), 200).json()
    assert len(same['knowledge_points']) == 1
    assert same['knowledge_points'][0]['id'] == 32
    # 筛选选项来自目录
    options = expect_status(client.get('/api/questions/filter-options/2'), 200).json()
    assert any(module['name'] == '名词与数量表达' for module in options['knowledge_modules'])
    assert any(point['id'] == 31 for point in options['knowledge_point_options'])
    # 删除题目后二级可删除
    expect_status(client.delete('/api/questions/' + str(question_id)), 204)
    expect_status(client.delete('/api/knowledge-points/32'), 204)


def test_question_batch_partial_errors():
    client, _ = build_client()
    response = expect_status(client.post('/api/questions/batch', json={
        'subject_id': 2, 'grade': 6, 'semester': 1,
        'questions': [
            {'parsed_question': 'A cat.', 'difficulty': 2,
             'knowledge_point_ids': [31], 'primary_knowledge_point_id': 31},
            {'parsed_question': 'Bad point.', 'difficulty': 2,
             'knowledge_point_ids': [9999], 'primary_knowledge_point_id': 9999},
            {'parsed_question': 'Unknown legacy.', 'difficulty': 2,
             'knowledge_point': '不存在的旧标签'},
        ],
    }), 200).json()
    assert response['success_count'] == 1
    assert len(response['errors']) == 2
    indexes = sorted(item['index'] for item in response['errors'])
    assert indexes == [1, 2]
    question = response['questions'][0]
    assert question['knowledge_point'] == '可数名词'
    assert question['legacy_knowledge_point'] is None
    # 批量入库不会因为单题错误而拒绝整批
    listing = expect_status(client.get('/api/questions', params={'subject_id': 2}), 200).json()
    assert listing['total'] == 1


def test_stats_http():
    client, _ = build_client()
    empty = expect_status(client.get('/api/stats/knowledge-points', params={'subject_id': 1}), 200).json()
    assert empty['level'] == 1
    assert empty['counting_mode'].startswith('level1_primary_share')
    assert any(item['name'] == '有理数' and item['question_count'] == 0 for item in empty['items'])
    expect_status(client.post('/api/questions', json={
        'subject_id': 2, 'parsed_question': 'A cat.', 'difficulty': 2,
        'knowledge_point_ids': [31], 'primary_knowledge_point_id': 31,
    }), 201)
    stats = expect_status(client.get('/api/stats/knowledge-points', params={'subject_id': 2}), 200).json()
    module = next(item for item in stats['items'] if item['name'] == '名词与数量表达')
    assert module['question_count'] == 1 and module['primary_question_count'] == 1
    assert module['accuracy'] is None
    level2 = expect_status(client.get('/api/stats/knowledge-points', params={
        'subject_id': 2, 'level': 2, 'parent_id': 30,
    }), 200).json()
    assert any(item['name'] == '可数名词' and item['question_count'] == 1 for item in level2['items'])
    expect_status(client.get('/api/stats/knowledge-points', params={
        'subject_id': 2, 'level': 2,
    }), 422)


def test_practice_review_version_conflict():
    client, connection = build_client()
    connection.execute(
        "INSERT INTO knowledge_point(id,name,name_key,subject_id,level,parent_id,sort_order,deleted,created_at) "
        "VALUES(32,'不可数名词','不可数名词',2,2,30,0,0,CURRENT_TIMESTAMP)")
    connection.commit()
    question = expect_status(client.post('/api/questions', json={
        'subject_id': 2, 'parsed_question': 'A cat.', 'difficulty': 2,
        'knowledge_point_ids': [31], 'primary_knowledge_point_id': 31,
    }), 201).json()
    question_id = question['id']
    practice = expect_status(client.post('/api/practice-sets', json={
        'name': '并发批改测试', 'question_ids': [question_id], 'question_type': 'original',
    }), 201).json()
    practice_id = practice['id']
    form = {
        'question_results': json.dumps([{'question_id': question_id, 'is_correct': True}]),
        'question_knowledge': json.dumps([{
            'question_id': question_id,
            'knowledge_point_ids': [32],
            'primary_knowledge_point_id': 32,
            'knowledge_revision': 9,
        }]),
    }
    expect_status(client.post('/api/practice-sets/' + str(practice_id) + '/mark-reviewed', data=form), 409)
    # 整批回滚：题目分类、版本、练习批改状态与计数器都不变
    detail = expect_status(client.get('/api/questions/' + str(question_id)), 200).json()
    assert detail['knowledge_revision'] == 0
    assert [point['id'] for point in detail['knowledge_points']] == [31]
    stored = expect_status(client.get('/api/practice-sets/' + str(practice_id)), 200).json()
    assert stored['reviewed'] is False
    assert stored['review_count'] == 0
    assert all(item['is_correct'] is None for item in stored['questions'])


def test_report_metrics_server_written():
    client, _ = build_client()
    expect_status(client.post('/api/questions', json={
        'subject_id': 2, 'parsed_question': 'A cat.', 'difficulty': 2, 'grade': 6, 'semester': 1,
        'knowledge_point_ids': [31], 'primary_knowledge_point_id': 31,
    }), 201)
    captured = {}

    async def fake_generate_json(request, prompt):
        captured['prompt'] = prompt
        return {
            'narrative': {'overall': '整体稳定', 'knowledge_modules': [], 'review_strategy': '保持', 'word_strategy': ''},
            'suggestions': [{'type': '练习', 'content': '继续巩固', 'priority': 1}],
            'summary': {'key_findings': ['稳定'], 'priority_improvements': ['复习']},
        }

    original = reports.generate_json
    reports.generate_json = fake_generate_json
    try:
        generated = expect_status(client.post('/api/learning-reports/generate', json={
            'subject_id': 2, 'grade': 6, 'time_range_days': 30,
        }), 200).json()
        assert generated['schema_version'] == 2
        detail = expect_status(client.get('/api/learning-reports/' + str(generated['id'])), 200).json()
    finally:
        reports.generate_json = original
    assert detail['legacy_schema'] is False
    assert detail['schema_version'] == 2
    content = detail['content']
    assert content['metrics']['modules']
    module = next(item for item in content['metrics']['modules'] if item['name'] == '名词与数量表达')
    assert module['question_count'] == 1
    assert content['overview']['total_questions'] == 1
    assert content['question_analysis']['review_effectiveness']['not_reviewed'] >= 0
    assert content['narrative']['overall'] == '整体稳定'
    assert 'top_error_knowledge_points' not in content['question_analysis']
    prompt = captured['prompt']
    assert '不要输出任何计数' in prompt
    assert 'top_error_knowledge_points' not in prompt


def main():
    check('树接口与路由顺序', test_tree_route_order)
    check('目录 HTTP CRUD', test_directory_crud_http)
    check('题目 HTTP 写入/筛选/旧文本', test_question_http_flow)
    check('批量入库单题错误隔离', test_question_batch_partial_errors)
    check('统计 HTTP 口径', test_stats_http)
    check('批改版本冲突 409 且整批回滚', test_practice_review_version_conflict)
    check('报告指标服务端写入', test_report_metrics_server_written)
    failed = [item for item in RESULTS if not item[1]]
    print('\n合计 {} 项，通过 {} 项，失败 {} 项'.format(
        len(RESULTS), len(RESULTS) - len(failed), len(failed)))
    if failed:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
