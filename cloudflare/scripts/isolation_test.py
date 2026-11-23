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
    for name in ('words', 'word_focus', 'readings', 'motivation', 'review', 'media', 'accounts'):
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


# ---------------------------------------------------------------- 任务 9：图片路径归属

FOREIGN = ('u1/2026/11/aaaaaaaa_x.jpg', '2026/11/aaaaaaaa_x.jpg')   # 1 号家庭的新图、迁移前的旧图
MINE = 'u2/2026/11/bbbbbbbb_y.jpg'


def test_foreign_image_path_rejected():
    """家庭 2 把别家的图片路径交给建题、复核图片、整页识别、录卷子，都被拒绝，表里行数不变。"""
    c, client = build()
    add_practice(c, 7005, 5)
    counts = lambda: tuple(c.execute('SELECT COUNT(*) FROM %s' % table).fetchone()[0]
                           for table in ('question', 'scan_page', 'paper'))
    before = counts()
    for key in FOREIGN:
        response = call(client, OTHER, 'POST', '/api/questions',
                        {'subject_id': 2, 'parsed_question': 'x ___', 'original_image': key})
        assert response.status_code == 404, (key, response.status_code, response.text)
        response = call(client, OTHER, 'PUT', '/api/practice-sets/7005/review-images', {'images': [key]})
        assert response.status_code == 404, (key, response.status_code)
        response = call(client, OTHER, 'POST', '/api/scan/pages', {'image': key, 'subject_id': 2})
        assert response.status_code == 404, (key, response.status_code, response.text)
        check = call(client, OTHER, 'POST', '/api/intake/papers/check', {
            'spec_version': 1, 'parent_reply': '跳过',
            'paper': {'subject_id': 2, 'grade': 6, 'semester': 1, 'name': '', 'paper_type': 'homework', 'images': [key]},
            'questions': []})
        assert any('图片' in str(item) or '照片' in str(item) for item in check.json().get('errors', [])), check.text
    assert counts() == before
    assert c.execute('SELECT review_images FROM practice_set WHERE id=7005').fetchone()[0] is None
    ok = call(client, OTHER, 'POST', '/api/questions', {'subject_id': 2, 'parsed_question': 'y ___', 'original_image': MINE})
    assert ok.status_code == 201, ok.text
    assert call(client, OTHER, 'PUT', '/api/practice-sets/7005/review-images', {'images': [MINE]}).status_code == 200


# ---------------------------------------------------------------- 任务 12：管理员接口


def test_admin_creates_family_and_students():
    """建家庭：用户、学生、年级配置都建好，列表里看得到；可以再加学生、改学生。"""
    c, client = build()
    created = call(client, ADMIN, 'POST', '/api/admin/users',
                   {'username': 'wang_3', 'name': '王家', 'student_name': '小王', 'grade': 4, 'semester': 1})
    assert created.status_code == 201, created.text
    ids = created.json()
    row = c.execute('SELECT username,name,is_admin,disabled,session_version,password_hash FROM app_user WHERE id=?',
                    (ids['user_id'],)).fetchone()
    assert tuple(row) == ('wang_3', '王家', 0, 0, 1, None)
    assert c.execute('SELECT user_id,name FROM student WHERE id=?', (ids['student_id'],)).fetchone()[1] == '小王'
    config = c.execute("SELECT value FROM runtime_config WHERE name=?", ('app:%d' % ids['student_id'],)).fetchone()[0]
    assert json.loads(config) == {'default_grade': 4, 'default_semester': 1}
    more = call(client, ADMIN, 'POST', '/api/admin/users/%d/students' % ids['user_id'],
                {'name': '王二', 'grade': 2, 'semester': 2})
    assert more.status_code == 201, more.text
    edited = call(client, ADMIN, 'PUT', '/api/admin/students/%d' % more.json()['id'], {'name': '王小二', 'grade': 3})
    assert edited.status_code == 200, edited.text
    users = {u['username']: u for u in call(client, ADMIN, 'GET', '/api/admin/users').json()}
    wang = users['wang_3']
    assert [(s['name'], s['grade'], s['semester']) for s in wang['students']] == [('小王', 4, 1), ('王小二', 3, 2)]
    assert wang['disabled'] is False and 'li' in users and 'admin' in users   # 管理员自己的家庭也在列表里


def test_admin_user_validation():
    """登录名格式不对 422；重名 409；停用自己 422；删除最后一个学生 409。"""
    c, client = build()
    bad = call(client, ADMIN, 'POST', '/api/admin/users', {'username': 'Bad Name', 'name': '坏', 'student_name': 'x'})
    assert bad.status_code == 422
    first = call(client, ADMIN, 'POST', '/api/admin/users', {'username': 'zhao', 'name': '赵家', 'student_name': '小赵'})
    assert first.status_code == 201, first.text
    dup = call(client, ADMIN, 'POST', '/api/admin/users', {'username': 'zhao', 'name': '重名', 'student_name': 'x'})
    assert dup.status_code == 409 and dup.json() == {'detail': '登录名已被占用'}
    assert call(client, ADMIN, 'PUT', '/api/admin/users/1', {'disabled': True}).status_code == 422
    last = call(client, ADMIN, 'DELETE', '/api/admin/students/5')
    assert last.status_code == 409 and last.json() == {'detail': '至少要保留一个学生'}
    assert call(client, ADMIN, 'PUT', '/api/admin/users/99', {'name': 'x'}).status_code == 404


def test_admin_disable_ends_sessions():
    """停用家庭：会话版本加 1，这个家庭的身份查询查不出来；再启用后可以重新登录（版本再加 1）。"""
    from identity import load_identity
    import starmap_test
    c, client = build()
    assert call(client, ADMIN, 'PUT', '/api/admin/users/2', {'disabled': True}).status_code == 200
    row = c.execute('SELECT disabled,session_version FROM app_user WHERE id=2').fetchone()
    assert tuple(row) == (1, 2)
    db = starmap_test.adapter(c)
    assert starmap_test.run(load_identity(db, {'user_id': 2, 'student_id': 5, 'version': 2})) is None
    assert call(client, ADMIN, 'PUT', '/api/admin/users/2', {'disabled': False, 'name': '李家改'}).status_code == 200
    assert tuple(c.execute('SELECT disabled,session_version,name FROM app_user WHERE id=2').fetchone()) == (0, 3, '李家改')
    deleted = call(client, ADMIN, 'POST', '/api/admin/users/2/students', {'name': '李三'}).json()
    assert call(client, ADMIN, 'DELETE', '/api/admin/students/%d' % deleted['id']).status_code == 204
    assert c.execute('SELECT deleted FROM student WHERE id=?', (deleted['id'],)).fetchone()[0] == 1


def test_error_book_cover_only():
    """错题本只带封面图（不带原图列表）也能保存；封面必须是本家庭的图。"""
    c, client = build()
    made = call(client, OTHER, 'POST', '/api/error-books', {'name': '英语本', 'subject_id': 2, 'cover_image': MINE})
    assert made.status_code == 201, made.text
    edited = call(client, OTHER, 'PUT', '/api/error-books/%d' % made.json()['id'], {'cover_image': MINE})
    assert edited.status_code == 200, edited.text
    foreign = call(client, OTHER, 'POST', '/api/error-books', {'name': '偷图', 'subject_id': 2, 'cover_image': FOREIGN[0]})
    assert foreign.status_code == 404, foreign.text


TESTS = [
    test_error_book_cover_only,
    test_admin_creates_family_and_students,
    test_admin_user_validation,
    test_admin_disable_ends_sessions,
    test_foreign_image_path_rejected,
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
