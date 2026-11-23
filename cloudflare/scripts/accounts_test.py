"""多家庭账号的本地测试：迁移 0018、会话、身份、管理员接口等。

测试库在 weekly_report_test 的库（迁移到 0017）上再执行 0018。运行：

    python cloudflare/scripts/accounts_test.py
"""

import json
import pathlib
import sqlite3
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
sys.path.insert(0, str(ROOT / 'scripts'))

import starmap_test  # noqa: E402  复用输出、检查助手
import weekly_report_test as weekly_test  # noqa: E402  复用建库（迁移到 0017）

MIGRATION_0018 = ROOT / 'migrations' / '0018_accounts.sql'
run = starmap_test.run


def build_db_before_0018():
    """建立迁移 0018 之前的测试库（到 0017 为止）。"""
    return weekly_test.build_db()


def apply_0018(c):
    """在测试库上执行迁移 0018。"""
    c.executescript(MIGRATION_0018.read_text(encoding='utf-8'))
    c.commit()
    return c


def build_db():
    """建立测试库：到 0017 的库再执行 0018。"""
    return apply_0018(build_db_before_0018())


# ---------------------------------------------------------------- 任务 1：迁移 0018


def test_migration_account_columns():
    """0018 给 app_user 加账号列、给 student 加排序列，1 号用户是管理员。"""
    c = build_db()
    cols = {r[1] for r in c.execute('PRAGMA table_info(app_user)')}
    assert {'username', 'password_hash', 'is_admin', 'session_version', 'disabled',
            'last_login_at', 'updated_at'} <= cols
    row = c.execute('SELECT is_admin,session_version,disabled FROM app_user WHERE id=1').fetchone()
    assert tuple(row) == (1, 1, 0)
    assert 'sort_order' in {r[1] for r in c.execute('PRAGMA table_info(student)')}


def test_username_unique_among_live_users():
    """未删除的用户登录名唯一；已删除的不占用。"""
    c = build_db()
    c.execute("UPDATE app_user SET username='admin' WHERE id=1")
    c.execute("INSERT INTO app_user(id,name,username,deleted) VALUES(2,'旧','li',1)")
    c.execute("INSERT INTO app_user(id,name,username) VALUES(3,'李','li')")   # 已删除的同名不冲突
    try:
        c.execute("INSERT INTO app_user(id,name,username) VALUES(4,'李二','li')")
        assert False, '未删除的登录名应唯一'
    except sqlite3.IntegrityError:
        pass


def test_rebuild_keeps_rows_and_ids():
    """重建 tag、achievement_progress 后，行数、编号、各列内容都不变，外键检查无问题。"""
    c = build_db_before_0018()
    c.execute("INSERT INTO tag(id,name,color,deleted) VALUES(7,'粗心','#f00',0)")
    c.execute("INSERT INTO tag(id,name,color,deleted) VALUES(9,'旧标签',NULL,1)")
    c.execute("INSERT INTO achievement(id,code,name,level,is_preset,is_active,trigger_action,trigger_count) VALUES(3,'a1','初试',1,1,1,'review',1)")
    c.execute('INSERT INTO achievement_progress(id,user_id,achievement_id,current_count,is_unlocked,deleted) '
              'VALUES(4,1,3,2,0,0)')
    tags_before = [tuple(r) for r in c.execute('SELECT id,name,color,deleted,student_id FROM tag ORDER BY id')]
    progress_before = [tuple(r) for r in c.execute(
        'SELECT id,user_id,achievement_id,current_count,is_unlocked,unlocked_at,deleted,student_id '
        'FROM achievement_progress ORDER BY id')]
    apply_0018(c)
    tags_after = [tuple(r) for r in c.execute('SELECT id,name,color,deleted,student_id FROM tag ORDER BY id')]
    progress_after = [tuple(r) for r in c.execute(
        'SELECT id,user_id,achievement_id,current_count,is_unlocked,unlocked_at,deleted,student_id '
        'FROM achievement_progress ORDER BY id')]
    assert tags_before == tags_after and len(tags_after) == 2
    assert progress_before == progress_after and len(progress_after) == 1
    assert c.execute('PRAGMA foreign_key_check').fetchall() == []


def test_second_student_same_tag_name():
    """同一家庭两个学生可以各有一个"粗心"标签；同一学生内不能重名。"""
    c = build_db()
    c.execute("INSERT INTO student(id,user_id,name) VALUES(2,1,'二宝')")
    c.execute("INSERT INTO tag(name,student_id,deleted) VALUES('粗心',1,0)")
    c.execute("INSERT INTO tag(name,student_id,deleted) VALUES('粗心',2,0)")
    try:
        c.execute("INSERT INTO tag(name,student_id,deleted) VALUES('粗心',2,0)")
        assert False, '同一学生内标签应唯一'
    except sqlite3.IntegrityError:
        pass


def test_achievement_progress_unique_per_student():
    """两个学生同一成就各有一条进度；同一学生同一成就只能有一条。"""
    c = build_db()
    c.execute("INSERT INTO achievement(id,code,name,level,is_preset,is_active,trigger_action,trigger_count) VALUES(3,'a1','初试',1,1,1,'review',1)")
    c.execute('INSERT INTO achievement_progress(user_id,achievement_id,current_count,student_id) VALUES(1,3,0,1)')
    c.execute('INSERT INTO achievement_progress(user_id,achievement_id,current_count,student_id) VALUES(1,3,0,2)')
    try:
        c.execute('INSERT INTO achievement_progress(user_id,achievement_id,current_count,student_id) VALUES(1,3,0,2)')
        assert False, '同一学生同一成就应唯一'
    except sqlite3.IntegrityError:
        pass


def test_star_balance_unique_per_student():
    """余额按学生唯一，旧的按 user_id 唯一的索引已删除。"""
    c = build_db()
    names = {r[1] for r in c.execute("SELECT type,name FROM sqlite_master WHERE type='index'")}
    assert 'cloudflare_star_balance_user' not in names
    c.execute('INSERT INTO star_balance(user_id,balance,student_id) VALUES(1,0,1)')
    c.execute('INSERT INTO star_balance(user_id,balance,student_id) VALUES(1,0,2)')
    try:
        c.execute('INSERT INTO star_balance(user_id,balance,student_id) VALUES(1,0,2)')
        assert False, '同一学生只能有一行余额'
    except sqlite3.IntegrityError:
        pass


def test_config_copied_per_student():
    """0018 把全局的 app、starmap 配置复制成 1 号学生的 app:1、starmap:1，原行保留。"""
    c = build_db_before_0018()
    for name, value in (('app', {'default_grade': 6}), ('starmap', {'progress': {'1': 3}})):
        c.execute("INSERT INTO runtime_config(name,value,deleted,updated_at) VALUES(?,?,0,'2026-11-20 10:00:00')",
                  (name, json.dumps(value)))
    apply_0018(c)
    rows = dict(c.execute("SELECT name,value FROM runtime_config WHERE name IN ('app','app:1','starmap','starmap:1')"))
    assert json.loads(rows['app:1']) == {'default_grade': 6} and 'app' in rows
    assert json.loads(rows['starmap:1']) == {'progress': {'1': 3}} and 'starmap' in rows


# ---------------------------------------------------------------- 任务 3：会话与身份


def adapter(c):
    """把连接包装成生产代码使用的异步数据库接口。"""
    return starmap_test.adapter(c)


def seed_family(c, user_id, username, student_ids, is_admin=0, disabled=0):
    """造一个家庭：用户 + 若干学生（学生名为"学生N"，排序按给定顺序）。"""
    c.execute('INSERT INTO app_user(id,name,username,is_admin,disabled,session_version,deleted) VALUES(?,?,?,?,?,1,0)',
              (user_id, username + '家', username, is_admin, disabled))
    for order, student_id in enumerate(student_ids):
        c.execute('INSERT INTO student(id,user_id,name,sort_order,deleted) VALUES(?,?,?,?,0)',
                  (student_id, user_id, '学生%d' % student_id, order))
    c.commit()


def test_session_round_trip():
    """Cookie 签发后能原样解析；换密钥、过期、旧格式、空密钥都解析不出。"""
    from session import parse_session, sign_session
    token = sign_session('s', 2000000000, 3, 7, 2)
    assert token.startswith('v2.2000000000.3.7.2.')
    assert parse_session('s', token, 1.0) == {'expires': 2000000000, 'user_id': 3, 'student_id': 7, 'version': 2}
    assert parse_session('other', token, 1.0) is None
    assert parse_session('s', token, 2000000001.0) is None
    assert parse_session('s', '1999999999.' + 'a' * 64, 1.0) is None
    assert parse_session('', token, 1.0) is None
    assert parse_session('s', token.replace('.3.7.', '.3.8.'), 1.0) is None   # 改学生编号签名就对不上
    assert parse_session('s', '', 1.0) is None


def test_session_matches_gateway_vector():
    """与网关测试里写死的 Cookie 完全一致（两边格式相同）。"""
    from session import sign_session
    assert sign_session('s', 2000000000, 3, 7, 2) == GATEWAY_COOKIE


def test_stale_version_rejected():
    """会话版本对不上、账号停用时，身份查询返回 None。"""
    from identity import load_identity
    c = build_db()
    seed_family(c, 2, 'li', (5,))
    parsed = {'user_id': 2, 'student_id': 5, 'version': 1, 'expires': 9999999999}
    identity = run(load_identity(adapter(c), parsed))
    assert identity == {'user_id': 2, 'username': 'li', 'is_admin': False, 'version': 1, 'student_id': 5}
    c.execute('UPDATE app_user SET session_version=2 WHERE id=2')
    assert run(load_identity(adapter(c), parsed)) is None
    c.execute('UPDATE app_user SET session_version=1, disabled=1 WHERE id=2')
    assert run(load_identity(adapter(c), parsed)) is None


def test_identity_rejects_other_familys_student():
    """带着别家学生编号的 Cookie 查不出身份；学生被删除后也查不出。"""
    from identity import load_identity
    c = build_db()
    seed_family(c, 2, 'li', (5, 6))
    assert run(load_identity(adapter(c), {'user_id': 2, 'student_id': 1, 'version': 1})) is None
    c.execute('UPDATE student SET deleted=1 WHERE id=6')
    assert run(load_identity(adapter(c), {'user_id': 2, 'student_id': 6, 'version': 1})) is None


def test_agent_identity():
    """录入口令代表 1 号家庭：不指定学生取排在最前的，指定别家学生查不出。"""
    from identity import agent_identity
    c = build_db()
    c.execute("UPDATE app_user SET username='admin' WHERE id=1")
    c.execute("INSERT INTO student(id,user_id,name,sort_order) VALUES(2,1,'二宝',1)")
    seed_family(c, 3, 'li', (5,))
    assert run(agent_identity(adapter(c), None))['student_id'] == 1
    assert run(agent_identity(adapter(c), '2'))['student_id'] == 2
    assert run(agent_identity(adapter(c), '5')) is None
    assert run(agent_identity(adapter(c), 'abc')) is None
    assert run(agent_identity(adapter(c), None))['is_admin'] is True


def test_owns_upload():
    """附件归属：自己前缀的、音频能读；别家的、旧附件（非 1 号用户）不能读。"""
    from identity import owns_upload, upload_prefix
    me = {'user_id': 2}
    assert upload_prefix(2) == 'u2/'
    assert owns_upload(me, 'u2/2026/11/ab_x.jpg') and owns_upload(me, 'audio/words/x.mp3')
    assert not owns_upload(me, 'u1/2026/11/ab_x.jpg') and not owns_upload(me, '2026/11/ab_x.jpg')
    assert not owns_upload(me, 'u22/2026/11/ab_x.jpg')
    assert owns_upload({'user_id': 1}, '2026/11/ab_x.jpg') and owns_upload({'user_id': 1}, 'practice_sets/a.pdf')
    assert not owns_upload({'user_id': 1}, 'u2/2026/11/ab_x.jpg')
    assert not owns_upload(me, '') and not owns_upload(me, None)


def test_admin_only_rules():
    """管理员专用接口：管理接口、模型设置、共用目录的写入。"""
    from identity import admin_only
    assert admin_only('POST', '/api/subjects') and admin_only('DELETE', '/api/subjects/3')
    assert admin_only('DELETE', '/api/knowledge-points/3') and admin_only('PUT', '/api/knowledge-points/3')
    assert admin_only('POST', '/api/stars/actions') and admin_only('PUT', '/api/achievements/2')
    assert admin_only('GET', '/api/config/llm') and admin_only('POST', '/api/config/llm')
    assert admin_only('GET', '/api/admin/users') and admin_only('POST', '/api/admin/users')
    assert not admin_only('GET', '/api/subjects') and not admin_only('GET', '/api/knowledge-points/tree')
    assert not admin_only('POST', '/api/tags') and not admin_only('POST', '/api/rewards')
    assert not admin_only('PUT', '/api/starmap/progress') and not admin_only('GET', '/api/stars/actions')
    assert not admin_only('POST', '/api/subjectsx')


# 网关测试 auth.test.mjs 里的 PY_COOKIE 是同一个值
GATEWAY_COOKIE = 'v2.2000000000.3.7.2.50e519e3a6ffed8721c1c634a6296672b1fde44747960929abb1a925631b9160'


TESTS = [
    test_migration_account_columns,
    test_username_unique_among_live_users,
    test_rebuild_keeps_rows_and_ids,
    test_second_student_same_tag_name,
    test_achievement_progress_unique_per_student,
    test_star_balance_unique_per_student,
    test_config_copied_per_student,
    test_session_round_trip,
    test_session_matches_gateway_vector,
    test_stale_version_rejected,
    test_identity_rejects_other_familys_student,
    test_agent_identity,
    test_owns_upload,
    test_admin_only_rules,
]


def main():
    """运行全部测试并打印总数；有失败时以非零状态退出。"""
    starmap_test.configure_output()
    results = [starmap_test.check(function.__name__, function) for function in TESTS]
    passed = sum(results)
    print('%d 通过，%d 失败' % (passed, len(results) - passed))
    sys.exit(len(results) - passed)


if __name__ == '__main__':
    main()
