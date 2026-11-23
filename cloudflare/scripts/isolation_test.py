"""多家庭数据隔离的接口测试：用本机测试环境的真实路由和完整内存库，两个家庭互相看不到、改不到对方的数据。

家庭 1（管理员 admin）：学生 1；家庭 2（li）：学生 5。请求头 x-test-as: "<用户编号>:<学生编号>" 决定以谁的身份请求。
运行：

    python cloudflare/scripts/isolation_test.py
"""

import json
import pathlib
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
sys.path.insert(0, str(ROOT / 'scripts'))

from fastapi.testclient import TestClient  # noqa: E402

import local_dev_server  # noqa: E402  复用完整内存库和路由挂载

ADMIN = '1:1'
OTHER = '2:5'


def build():
    """建库（含 0018）并加上家庭 2，返回 (连接, 测试客户端)。"""
    c = local_dev_server.build_connection()
    c.execute("INSERT INTO app_user(id,name,username,is_admin,session_version,deleted) VALUES(2,'李家','li',0,1,0)")
    c.execute("INSERT INTO student(id,user_id,name,sort_order,deleted) VALUES(5,2,'小李',0,0)")
    c.commit()
    app = local_dev_server.build_app(c, tempfile.mkdtemp(prefix='easyfix_iso_'), None)
    mount_extra_routers(app)

    @app.middleware('http')
    async def act_as(request, call_next):
        """按请求头 x-test-as 放好身份（外层中间件先跑，本机环境的默认身份不会覆盖它）。"""
        value = request.headers.get('x-test-as')
        if value:
            user_id, student_id = (int(part) for part in value.split(':'))
            request.scope['easyfix'] = {'user_id': user_id, 'username': 'u%d' % user_id, 'is_admin': user_id == 1,
                                        'version': 1, 'student_id': student_id}
        return await call_next(request)

    return c, TestClient(app)


def mount_extra_routers(app):
    """本机测试环境没挂的模块（单词、阅读、激励、复习等）在这里补上。"""
    import importlib
    for name in ('words', 'word_focus', 'readings', 'motivation', 'review', 'media'):
        try:
            module = importlib.import_module(name)
            if hasattr(module, 'Database'):   # 和本机测试环境一样：数据库对象由中间件放进 env，原样使用
                module.Database = lambda binding: binding
            app.include_router(module.router)
        except Exception as error:   # 个别模块依赖云端运行时，挂不上就跳过（相应测试会失败提示）
            print('跳过模块 %s：%s' % (name, error))


def call(client, who, method, path, body=None):
    """以某个身份发请求，返回响应。"""
    return client.request(method, path, headers={'x-test-as': who}, json=body)


def add_question(c, qid, student_id, subject_id=2, text=None):
    """直接写一道已核对的错题（英语，免公式校验）。"""
    c.execute('INSERT INTO question(id,subject_id,original_text,parsed_question,review_count,correct_count,'
              'error_count,deleted,created_at,updated_at,review_status,student_id,knowledge_revision) '
              "VALUES(?,?,?,?,0,0,0,0,'2026-11-20 10:00:00','2026-11-20 10:00:00','approved',?,0)",
              (qid, subject_id, text or '题%d' % qid, text or '题%d' % qid, student_id))
    c.commit()


# ---------------------------------------------------------------- 任务 7：错题、目录


def test_question_by_id_is_404_for_other_student():
    """学生 5 读、改、删学生 1 的错题都是 404，那道题原样不变。"""
    c, client = build()
    add_question(c, 9001, 1)
    for method, path, body in (('GET', '/api/questions/9001', None),
                               ('PUT', '/api/questions/9001', {'original_text': '被改了', 'subject_id': 2}),
                               ('DELETE', '/api/questions/9001', None),
                               ('GET', '/api/questions/9001/practice-history', None),
                               ('POST', '/api/questions/9001/similar', None)):
        response = call(client, OTHER, method, path, body)
        assert response.status_code == 404, (method, path, response.status_code, response.text)
    row = c.execute('SELECT original_text,deleted FROM question WHERE id=9001').fetchone()
    assert tuple(row) == ('题9001', 0)
    assert call(client, ADMIN, 'GET', '/api/questions/9001').status_code == 200


def test_question_list_isolated():
    """错题列表只列自己的题，总数也只算自己的。"""
    c, client = build()
    before_admin = call(client, ADMIN, 'GET', '/api/questions?limit=100').json()['total']
    add_question(c, 9001, 1)
    add_question(c, 9002, 5)
    add_question(c, 9003, 5)
    mine = call(client, OTHER, 'GET', '/api/questions?limit=100').json()
    assert mine['total'] == 2 and {item['id'] for item in mine['items']} == {9002, 9003}
    assert call(client, ADMIN, 'GET', '/api/questions?limit=100').json()['total'] == before_admin + 1
    options = call(client, OTHER, 'GET', '/api/questions/filter-options/2').json()
    assert options['knowledge_points'] == []


def test_create_question_belongs_to_creator():
    """学生 5 新建的错题记在学生 5 名下；用学生 1 的标签建题被拒。"""
    c, client = build()
    created = call(client, OTHER, 'POST', '/api/questions', {'subject_id': 2, 'parsed_question': 'apple ___'})
    assert created.status_code == 201, created.text
    assert c.execute('SELECT student_id FROM question WHERE id=?', (created.json()['id'],)).fetchone()[0] == 5
    tag = call(client, ADMIN, 'POST', '/api/tags', {'name': '粗心'}).json()
    refused = call(client, OTHER, 'POST', '/api/questions',
                   {'subject_id': 2, 'parsed_question': 'pear ___', 'tag_ids': [tag['id']]})
    assert refused.status_code == 400, refused.text


def test_catalog_scoped():
    """标签、错题本、奖品按学生分；学科大家共用；两个学生可以有同名标签。"""
    c, client = build()
    admin_tag = call(client, ADMIN, 'POST', '/api/tags', {'name': '粗心'})
    other_tag = call(client, OTHER, 'POST', '/api/tags', {'name': '粗心'})
    assert admin_tag.status_code == 201 and other_tag.status_code == 201, other_tag.text
    assert [t['name'] for t in call(client, OTHER, 'GET', '/api/tags').json()] == ['粗心']
    assert c.execute('SELECT student_id FROM tag WHERE id=?', (other_tag.json()['id'],)).fetchone()[0] == 5
    assert call(client, OTHER, 'DELETE', '/api/tags/%d' % admin_tag.json()['id']).status_code == 404
    book = call(client, ADMIN, 'POST', '/api/error-books', {'name': '数学本', 'subject_id': 1}).json()
    assert call(client, OTHER, 'GET', '/api/error-books').json()['total'] == 0
    assert call(client, OTHER, 'PUT', '/api/error-books/%d' % book['id'], {'name': '改'}).status_code == 404
    assert len(call(client, OTHER, 'GET', '/api/subjects').json()) == len(call(client, ADMIN, 'GET', '/api/subjects').json())


def test_papers_and_review_isolated():
    """卷子详情、待核对数、核对操作都只对自己的学生有效。"""
    c, client = build()
    paper = call(client, ADMIN, 'POST', '/api/papers', {'subject_id': 2, 'name': '单元测', 'paper_type': 'exam',
                                                        'exam_kind': 'unit'})
    assert paper.status_code == 201, paper.text
    assert call(client, OTHER, 'GET', '/api/papers/%d' % paper.json()['id']).status_code == 404
    assert call(client, OTHER, 'GET', '/api/papers').json()['total'] == 0
    add_question(c, 9001, 1)
    c.execute("UPDATE question SET review_status='pending' WHERE id=9001")
    c.commit()
    assert call(client, OTHER, 'GET', '/api/questions/review/count').json() == {'pending': 0}
    assert call(client, ADMIN, 'GET', '/api/questions/review/count').json()['pending'] >= 1
    response = call(client, OTHER, 'POST', '/api/questions/9001/review', {'action': 'reject'})
    assert response.status_code == 404
    assert c.execute('SELECT deleted,review_status FROM question WHERE id=9001').fetchone()[0] == 0


# ---------------------------------------------------------------- 任务 8：单词、练习、阅读、激励、翻一翻


def add_word(c, wid, student_id, english='apple'):
    """直接写一个单词。"""
    c.execute("INSERT INTO word(id,english,chinese,deleted,created_at,updated_at,student_id) "
              "VALUES(?,?,'苹果',0,'2026-11-20 10:00:00','2026-11-20 10:00:00',?)", (wid, english, student_id))
    c.commit()


def add_practice(c, pid, student_id, question_id=None):
    """直接写一份练习集（英语），可带一道题。"""
    c.execute("INSERT INTO practice_set(id,name,subject_id,deleted,created_at,student_id,review_count) "
              "VALUES(?,'练习',2,0,'2026-11-20 10:00:00',?,0)", (pid, student_id))
    if question_id is not None:
        c.execute('INSERT INTO practice_set_question(practice_set_id,question_id,display_order,deleted) '
                  'VALUES(?,?,1,0)', (pid, question_id))
    c.commit()


def add_reading(c, rid, student_id):
    """直接写一篇阅读短文。"""
    c.execute("INSERT INTO reading_passage(id,title,content,topic,grade,difficulty,deleted,created_at,student_id) "
              "VALUES(?,'短文','text','school',6,3,0,'2026-11-20 10:00:00',?)", (rid, student_id))
    c.commit()


def test_words_practices_readings_by_id_404():
    """学生 5 按编号读、改、删学生 1 的单词、练习集、阅读都是 404，数据不变。"""
    c, client = build()
    add_question(c, 9001, 1)
    add_word(c, 8001, 1)
    add_practice(c, 7001, 1, 9001)
    add_reading(c, 6001, 1)
    for method, path, body in (('GET', '/api/words/8001', None), ('PUT', '/api/words/8001', {'chinese': '改'}),
                               ('DELETE', '/api/words/8001', None),
                               ('GET', '/api/practice-sets/7001', None),
                               ('PUT', '/api/practice-sets/7001', {'name': '改'}),
                               ('DELETE', '/api/practice-sets/7001', None),
                               ('POST', '/api/practice-sets/7001/mark-reviewed', {'results': []}),
                               ('GET', '/api/readings/6001', None), ('DELETE', '/api/readings/6001', None)):
        response = call(client, OTHER, method, path, body)
        assert response.status_code == 404, (method, path, response.status_code, response.text[:200])
    assert c.execute('SELECT chinese,deleted FROM word WHERE id=8001').fetchone()[0] == '苹果'
    assert c.execute('SELECT name,deleted FROM practice_set WHERE id=7001').fetchone()[1] == 0
    assert c.execute('SELECT deleted FROM reading_passage WHERE id=6001').fetchone()[0] == 0


def test_lists_isolated():
    """单词、练习集、阅读列表只列自己的。"""
    c, client = build()
    add_word(c, 8001, 1)
    add_word(c, 8002, 5, 'pear')
    add_practice(c, 7001, 1)
    add_reading(c, 6001, 1)
    words = call(client, OTHER, 'GET', '/api/words?limit=100').json()
    assert [w['english'] for w in words['items']] == ['pear'], words
    practices = call(client, OTHER, 'GET', '/api/practice-sets').json()
    assert practices['total'] == 0, practices
    readings = call(client, OTHER, 'GET', '/api/readings').json()
    assert readings['total'] == 0, readings


def test_motivation_isolated_per_student():
    """同一家庭两个学生：星星余额、流水、奖品各算各的；别人的奖品兑换不了。"""
    c, client = build()
    c.execute("INSERT INTO student(id,user_id,name,sort_order,deleted) VALUES(2,1,'二宝',1,0)")
    c.commit()
    second = '1:2'
    assert call(client, ADMIN, 'POST', '/api/stars/adjust', {'delta': 5, 'reason': '奖励'}).status_code == 200
    assert call(client, ADMIN, 'GET', '/api/stars/balance').json() == {'balance': 5}
    assert call(client, second, 'GET', '/api/stars/balance').json() == {'balance': 0}
    assert call(client, second, 'GET', '/api/stars/records').json()['total'] == 0
    reward = call(client, ADMIN, 'POST', '/api/rewards', {'name': '冰淇淋', 'cost_stars': 3}).json()
    assert call(client, second, 'GET', '/api/rewards').json() == []
    assert call(client, OTHER, 'GET', '/api/rewards').json() == []
    assert call(client, second, 'POST', '/api/rewards/%d/redeem' % reward['id']).status_code == 404
    assert call(client, ADMIN, 'POST', '/api/rewards/%d/redeem' % reward['id']).status_code == 200
    assert call(client, ADMIN, 'GET', '/api/stars/balance').json() == {'balance': 2}
    assert call(client, second, 'POST', '/api/stars/adjust', {'delta': 1, 'reason': '奖励'}).status_code == 200
    assert call(client, second, 'GET', '/api/stars/balance').json() == {'balance': 1}
    rows = c.execute('SELECT student_id,COUNT(*) FROM star_balance WHERE deleted=0 GROUP BY student_id').fetchall()
    assert {r[0]: r[1] for r in rows} == {1: 1, 2: 1}


def test_flip_pool_isolated():
    """学生 5 的翻一翻里没有学生 1 的题。"""
    c, client = build()
    add_question(c, 9001, 1)
    add_question(c, 9002, 5)
    cards = call(client, OTHER, 'GET', '/api/flip/today').json()
    ids = {card['question_id'] if 'question_id' in card else card.get('id') for card in cards.get('cards', [])}
    assert 9001 not in ids, cards


TESTS = [
    test_words_practices_readings_by_id_404,
    test_lists_isolated,
    test_motivation_isolated_per_student,
    test_flip_pool_isolated,
    test_question_by_id_is_404_for_other_student,
    test_papers_and_review_isolated,
    test_question_list_isolated,
    test_create_question_belongs_to_creator,
    test_catalog_scoped,
]


def main():
    """运行全部测试；有失败时以非零状态退出。"""
    local_dev_server.configure_output()
    failed = 0
    for test in TESTS:
        try:
            test()
            print('PASS', test.__name__)
        except Exception as error:   # 断言失败和接口异常都算失败，打印原因
            failed += 1
            print('FAIL', test.__name__, '-', type(error).__name__, str(error)[:300])
    print('%d 通过，%d 失败' % (len(TESTS) - failed, failed))
    sys.exit(failed)


if __name__ == '__main__':
    main()
