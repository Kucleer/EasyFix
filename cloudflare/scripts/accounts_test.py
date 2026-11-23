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


TESTS = [
    test_migration_account_columns,
    test_username_unique_among_live_users,
    test_rebuild_keeps_rows_and_ids,
    test_second_student_same_tag_name,
    test_achievement_progress_unique_per_student,
    test_star_balance_unique_per_student,
    test_config_copied_per_student,
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
