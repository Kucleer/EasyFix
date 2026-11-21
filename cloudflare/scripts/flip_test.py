"""翻一翻（每天翻几张旧错题卡片）的本地测试。

在 weekly_report_test 的测试库（迁移执行到 0016）上再执行迁移 0017。运行：

    python cloudflare/scripts/flip_test.py
"""

import json
import pathlib
import sqlite3
import sys

from fastapi import HTTPException

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
sys.path.insert(0, str(ROOT / 'scripts'))

import starmap_test  # noqa: E402  复用输出、检查助手和造数据助手
import targeted_test  # noqa: E402
import weekly_report_test as weekly_test  # noqa: E402  复用建库（迁移到 0016）
from flip_model import (DAILY_LIMIT, FORGOT_GAP_DAYS, REMEMBER_GAPS, days_between, due_rank,  # noqa: E402
                        history_state, pick_today)

MIGRATION_0017 = ROOT / 'migrations' / '0017_flip_log.sql'
TODAY = '2026-11-21'
run = starmap_test.run


def build_db():
    """建立测试库：weekly_report_test 的库 + 迁移 0017。"""
    connection = weekly_test.build_db()
    connection.executescript(MIGRATION_0017.read_text(encoding='utf-8'))
    connection.commit()
    return connection


def add_question(c, qid, created_at, points=(101,), subject_id=1, **fields):
    """插入一道已核对的错题（题干"题N"），fields 里的列再单独改写。"""
    status = fields.pop('review_status', 'approved')
    starmap_test.add_question(c, qid, subject_id, created_at, list(points), status=status)
    for column, value in fields.items():
        c.execute('UPDATE question SET %s=? WHERE id=?' % column, (value, qid))


def add_log(c, qid, result, day, created_at=None, deleted=0):
    """直接写一条翻牌记录（造历史数据用）。"""
    c.execute('INSERT INTO flip_log(student_id,question_id,result,flip_date,created_at,deleted) VALUES(1,?,?,?,?,?)',
              (qid, result, day, created_at or day + ' 19:00:00', deleted))


def cand(qid, entered):
    """纯函数测试用的候选题。"""
    return {'id': qid, 'entered': entered}


def log(result, day):
    """纯函数测试用的一条翻牌记录。"""
    return {'result': result, 'flip_date': day, 'created_at': day + ' 19:00:00'}


def adapter(c):
    """把连接包装成异步数据库接口，并让 flip 模块直接使用它。"""
    import flip
    flip.Database = lambda binding: binding
    return starmap_test.adapter(c)


def today_body(c, today=TODAY):
    """直接算某一天的 /api/flip/today 内容。"""
    import flip
    return run(flip.build_today(adapter(c), 1, today))


def post(c, qid, payload, today=TODAY):
    """直接调用 POST /api/flip/{question_id} 的处理函数（时间固定在 today 晚上）。"""
    import analytics
    import flip
    db = adapter(c)
    saved = analytics.now
    from datetime import datetime
    analytics.now = lambda: datetime.strptime(today + ' 20:30:00', '%Y-%m-%d %H:%M:%S')
    try:
        return run(flip.flip_one(qid, targeted_test.request_for(db, payload)))
    finally:
        analytics.now = saved


def expect_status(status, function):
    """运行函数，要求抛出指定状态码的 HTTPException。"""
    try:
        function()
    except HTTPException as error:
        assert error.status_code == status, error.status_code
        return
    raise AssertionError('没有抛出 %d' % status)


def ids(body):
    """卡片的题目编号列表。"""
    return [card['id'] for card in body['cards']]


# ---------------------------------------------------------------- 迁移


def test_migration_creates_flip_log():
    """0017 新建 flip_log：列齐全、默认值对；同一学生同一题同一天只能有一条未删除记录；有按日期查的索引。"""
    c = build_db()
    columns = {row[1] for row in c.execute('PRAGMA table_info(flip_log)')}
    assert columns == {'id', 'student_id', 'question_id', 'result', 'flip_date', 'created_at', 'deleted'}
    insert = ("INSERT INTO flip_log(question_id,result,flip_date,created_at) "
              "VALUES(5,'remember','2026-11-21','2026-11-21 19:00:00')")
    c.execute(insert)
    assert tuple(c.execute('SELECT student_id,deleted FROM flip_log').fetchone()) == (1, 0)
    try:
        c.execute(insert)
        assert False, '应该被唯一索引拦住'
    except sqlite3.IntegrityError:
        pass
    c.execute('UPDATE flip_log SET deleted=1')
    c.execute(insert)  # 软删除之后可以再记
    indexes = {row[1] for row in c.execute("PRAGMA index_list('flip_log')")}
    columns_of = lambda name: [row[2] for row in c.execute("PRAGMA index_info('%s')" % name)]
    assert ['student_id', 'flip_date'] in [columns_of(name) for name in indexes]
    assert ['student_id', 'question_id', 'flip_date'] in [columns_of(name) for name in indexes]


# ---------------------------------------------------------------- 纯函数


def test_constants():
    """数字常量和设计一致。"""
    assert DAILY_LIMIT == 8 and FORGOT_GAP_DAYS == 2 and REMEMBER_GAPS == (3, 7, 14)
    assert days_between('2026-11-19', '2026-11-21') == 2
    assert days_between('2026-11-30', '2026-12-01') == 1 and days_between('2026-12-31', '2027-01-01') == 1
    assert days_between('2026-11-21', '2026-11-21 08:00:00') == 0     # 只看日期部分


def test_pick_today_limits_to_8():
    """一天最多 8 张；今天翻过几张就少几张；不够 8 张时有几张出几张；不会小于 0。"""
    candidates = [cand(qid, '2026-10-%02d 08:00:00' % qid) for qid in range(1, 13)]
    picked = pick_today(candidates, {}, TODAY)
    assert picked['done'] == 0 and len(picked['cards']) == 8
    flipped = {1: [log('remember', TODAY)], 2: [log('forget', TODAY)], 3: [log('remember', TODAY)]}
    picked = pick_today(candidates, flipped, TODAY)
    assert picked['done'] == 3 and len(picked['cards']) == 5
    assert not {1, 2, 3} & set(picked['cards'])
    assert pick_today(candidates[:4], {}, TODAY) == {'done': 0, 'cards': [4, 3, 2, 1]}
    many = {qid: [log('remember', TODAY)] for qid in range(1, 11)}
    assert pick_today(candidates, many, TODAY) == {'done': 10, 'cards': []}
    # 今天翻过、但已经不在候选里的题（比如刚删掉）也算今天翻过的张数
    gone = {99: [log('remember', TODAY)]}
    assert pick_today(candidates, gone, TODAY)['done'] == 1
    assert pick_today([], {}, TODAY) == {'done': 0, 'cards': []}


def test_never_flipped_newest_first():
    """从没翻过的：录入时间新的在前；录入时间相同按题目编号；只有日期的录入时间也能比较。"""
    candidates = [cand(1, '2026-10-01 08:00:00'), cand(2, '2026-11-20 08:00:00.123456'),
                  cand(3, '2026-11-05 08:00:00'), cand(4, '2026-11-05 08:00:00'), cand(5, '2026-11-10')]
    assert pick_today(candidates, {}, TODAY)['cards'] == [2, 5, 3, 4, 1]


def test_forgot_waits_2_days():
    """点了"我忘了"满 2 天才再出现，而且排在从没翻过的前面；组内上次翻得早的在前。"""
    candidates = [cand(1, '2026-10-01 08:00:00'), cand(2, '2026-11-20 08:00:00'), cand(3, '2026-10-02 08:00:00')]
    logs = {1: [log('forget', '2026-11-20')], 3: [log('forget', '2026-11-19')]}
    assert pick_today(candidates, logs, '2026-11-21')['cards'] == [3, 2]           # 1 只隔了 1 天
    assert pick_today(candidates, logs, '2026-11-22')['cards'] == [3, 1, 2]        # 都满 2 天：19 号翻的在前
    state = {**history_state(logs[1]), 'id': 1, 'entered': '2026-10-01 08:00:00'}
    assert due_rank(state, '2026-11-21') is None
    assert due_rank(state, '2026-11-22')[0] == 1


def test_remember_gaps_3_7_14():
    """"我记得"：连续 1 次隔 3 天、2 次隔 7 天、3 次及以上隔 14 天；到期的排在最后，到期早的在前。"""
    def due_on(logs):
        """返回这题最早在哪天出现（从最后一次翻牌第二天起逐天找）。"""
        state = {**history_state(logs), 'id': 1, 'entered': '2026-10-01 08:00:00'}
        from datetime import date, timedelta
        day = date.fromisoformat(state['last_date'])
        for _ in range(30):
            day += timedelta(days=1)
            if due_rank(state, day.isoformat()) is not None:
                return day.isoformat()
        return None
    once = [log('remember', '2026-11-01')]
    twice = once + [log('remember', '2026-11-04')]
    three = twice + [log('remember', '2026-11-11')]
    four = three + [log('remember', '2026-11-25')]
    assert due_on(once) == '2026-11-04'
    assert due_on(twice) == '2026-11-11'
    assert due_on(three) == '2026-11-25'
    assert due_on(four) == '2026-12-09'
    candidates = [cand(1, '2026-10-01 08:00:00'), cand(2, '2026-11-20 08:00:00'), cand(3, '2026-10-03 08:00:00'),
                  cand(4, '2026-10-04 08:00:00')]
    logs = {1: [log('remember', '2026-11-17')],             # 11-20 到期
            3: [log('remember', '2026-11-15')],             # 11-18 到期
            4: [log('forget', '2026-11-10')]}               # 忘了：最前
    assert pick_today(candidates, logs, TODAY)['cards'] == [4, 2, 3, 1]
    assert pick_today(candidates, logs, '2026-11-19')['cards'] == [4, 2, 3]       # 1 还没到期


def test_forget_resets_remember_streak():
    """中间点了一次"我忘了"，连续记得的次数清零，重新从隔 3 天算。"""
    logs = [log('remember', '2026-11-01'), log('remember', '2026-11-04'), log('forget', '2026-11-11'),
            log('remember', '2026-11-13')]
    assert history_state(logs) == {'last_result': 'remember', 'last_date': '2026-11-13', 'remember_streak': 1}
    assert history_state([]) == {'last_result': None, 'last_date': None, 'remember_streak': 0}
    assert history_state(logs[:3]) == {'last_result': 'forget', 'last_date': '2026-11-11', 'remember_streak': 0}
    # 记录顺序打乱也按时间算
    assert history_state(list(reversed(logs)))['remember_streak'] == 1
    state = {**history_state(logs), 'id': 1, 'entered': '2026-10-01 08:00:00'}
    assert due_rank(state, '2026-11-15') is None and due_rank(state, '2026-11-16')[0] == 3


# ---------------------------------------------------------------- 取数与接口


def stable_fixture():
    """10 道从没翻过的题：编号越大录入越新。"""
    c = build_db()
    for qid in range(1, 11):
        add_question(c, qid, '2026-11-%02d 08:00:00.000000' % qid)
    c.commit()
    return c


def test_today_flipped_excluded_and_order_stable():
    """同一天反复打开：翻过的不再出现，剩下的卡片和顺序不变；张数加起来还是 8。"""
    c = stable_fixture()
    first = today_body(c)
    assert ids(first) == [10, 9, 8, 7, 6, 5, 4, 3] and first['total'] == 8 and first['done'] == 0
    assert today_body(c) == first                                         # 什么都没翻，再开一次一模一样
    progress = post(c, 10, {'result': 'remember'})
    assert progress == {'done': 1, 'total': 8}
    post(c, 7, {'result': 'forget'})                                      # 跳着翻一张
    again = today_body(c)
    assert ids(again) == [9, 8, 6, 5, 4, 3] and again['total'] == 8 and again['done'] == 2
    for qid in ids(again):
        post(c, qid, {'result': 'remember'})
    done = today_body(c)
    assert done == {'total': 8, 'done': 8, 'cards': []}
    # 第二天：昨天点"忘了"的 7 还没满 2 天，剩下没翻过的 2、1 先出，记得的都没到期
    assert ids(today_body(c, '2026-11-22')) == [2, 1]
    assert ids(today_body(c, '2026-11-23')) == [7, 2, 1]


def test_card_fields():
    """卡片字段：学科名、主考点名、题干、原图、错误答案、答案、解析；没挂考点时 point_name 为 null。"""
    c = build_db()
    add_question(c, 1, '2026-11-20 08:00:00', points=(102, 101), answer='答案1', analysis='解析1',
                 wrong_answer='错的1', analysis_image='a.png', original_image='q1.jpg')
    add_question(c, 2, '2026-11-19 08:00:00', points=(), subject_id=2, answer='答案2',
                 original_images=json.dumps(['p1.jpg', 'p2.jpg']), original_image='p1.jpg')
    c.commit()
    cards = today_body(c)['cards']
    assert cards[0] == {'id': 1, 'subject_name': '数学', 'point_name': '有理数乘方', 'parsed_question': '题1',
                        'images': ['q1.jpg'], 'wrong_answer': '错的1', 'answer': '答案1', 'analysis': '解析1',
                        'analysis_image': 'a.png'}
    assert cards[1] == {'id': 2, 'subject_name': '英语', 'point_name': None, 'parsed_question': '题2',
                        'images': ['p1.jpg', 'p2.jpg'], 'wrong_answer': None, 'answer': '答案2', 'analysis': None,
                        'analysis_image': None}


def test_graduated_excluded():
    """毕业的题不出现（连对 2 次，或主考点"直接设为掌握"）；还在巩固、做错过的照常出现。"""
    c = build_db()
    for qid in range(1, 5):
        add_question(c, qid, '2026-11-0%d 08:00:00' % qid, points=(101,) if qid != 4 else (102,))
    targeted_test.add_set(c, 1, '2026-11-10 08:00:00', '2026-11-10 20:00:00',
                          [(1, True, 'original'), (2, True, 'original'), (3, False, 'original')])
    targeted_test.add_set(c, 2, '2026-11-12 08:00:00', '2026-11-12 20:00:00',
                          [(1, True, 'similar'), (3, True, 'similar')])
    c.execute("INSERT INTO mastery_adjustment(student_id,knowledge_point_id,kind,created_at,deleted) "
              "VALUES(1,102,'set_mastered','2026-11-15 08:00:00',0)")
    c.commit()
    assert ids(today_body(c)) == [3, 2]          # 1 连对 2 次毕业；4 的考点设为掌握；2 巩固中；3 做错后做对 1 次
    expect_status(404, lambda: post(c, 1, {'result': 'remember'}))


def test_pending_or_deleted_excluded():
    """没核对的、已删除的不出现，也不能记。"""
    c = build_db()
    add_question(c, 1, '2026-11-01 08:00:00', review_status='pending')
    add_question(c, 2, '2026-11-02 08:00:00', deleted=1)
    add_question(c, 3, '2026-11-03 08:00:00')
    c.commit()
    assert ids(today_body(c)) == [3]
    expect_status(404, lambda: post(c, 1, {'result': 'remember'}))
    expect_status(404, lambda: post(c, 2, {'result': 'remember'}))


def test_empty_stem_without_image_excluded():
    """题干（解析题干和原题文字）都空、又没有原图的不出现；只有原图的照常出现。"""
    c = build_db()
    add_question(c, 1, '2026-11-01 08:00:00', parsed_question='  \n', original_text='')
    add_question(c, 2, '2026-11-02 08:00:00', parsed_question='', original_text=None, original_image='only.jpg')
    add_question(c, 3, '2026-11-03 08:00:00', parsed_question=None, original_text=None,
                 original_images=json.dumps(['x.jpg']))
    add_question(c, 4, '2026-11-04 08:00:00', parsed_question=None, original_text=None, original_images='[]')
    add_question(c, 5, '2026-11-05 08:00:00', parsed_question='', original_text='原题文字')
    c.commit()
    body = today_body(c)
    assert ids(body) == [5, 3, 2]
    cards = {card['id']: card for card in body['cards']}
    assert cards[2]['images'] == ['only.jpg'] and cards[3]['images'] == ['x.jpg']
    assert cards[5]['parsed_question'] == '原题文字'      # 解析题干为空时用原题文字


def test_post_same_day_twice_records_once():
    """同一题同一天连点两次只记一次（第一次的结果为准）；第二天可以再记。"""
    c = stable_fixture()
    assert post(c, 5, {'result': 'remember'}) == {'done': 1, 'total': 8}
    assert post(c, 5, {'result': 'forget'}) == {'done': 1, 'total': 8}
    rows = c.execute('SELECT result,flip_date FROM flip_log WHERE question_id=5').fetchall()
    assert [tuple(row) for row in rows] == [('remember', TODAY)]
    post(c, 5, {'result': 'forget'}, today='2026-11-25')
    assert c.execute('SELECT COUNT(*) FROM flip_log WHERE question_id=5').fetchone()[0] == 2


def test_post_rejects_bad_result_and_unknown_question():
    """result 不是 remember / forget 返回 422；题目不存在返回 404；都不写记录。"""
    c = stable_fixture()
    for payload in ({'result': 'maybe'}, {}, {'result': None}, ['remember']):
        expect_status(422, lambda: post(c, 3, payload))
    expect_status(404, lambda: post(c, 999, {'result': 'remember'}))
    assert c.execute('SELECT COUNT(*) FROM flip_log').fetchone()[0] == 0


def test_flip_does_not_change_mastery():
    """翻牌前后：知识星空的节点状态、每道题的毕业状态都不变，掌握度相关的表一行没动。"""
    import flip
    import starmap
    c = build_db()
    for qid in range(1, 5):
        add_question(c, qid, '2026-11-0%d 08:00:00' % qid, points=(101 + qid % 2,))
    targeted_test.add_set(c, 1, '2026-11-10 08:00:00', '2026-11-10 20:00:00',
                          [(1, True, 'original'), (2, False, 'original'), (3, True, 'original')])
    c.commit()

    def snapshot():
        """星空节点、错题状态、相关表行数。"""
        db = adapter(c)
        request = targeted_test.request_for(db)
        _, nodes, _, mastered, _ = run(starmap.compute(db, request, 1))
        states = run(flip.load_states(db, 1, '2026-11-22 00:00:00'))
        counts = [c.execute('SELECT COUNT(*) FROM %s' % table).fetchone()[0]
                  for table in ('practice_set', 'practice_set_question', 'mastery_adjustment', 'question')]
        return [(n['id'], n['value'], n['status']) for n in nodes], sorted(mastered), states, counts
    before = snapshot()
    assert before[2] == {1: 'consolidating', 2: 'todo', 3: 'consolidating', 4: 'todo'}
    post(c, 1, {'result': 'remember'})
    post(c, 2, {'result': 'forget'})
    post(c, 4, {'result': 'forget'})
    assert snapshot() == before


def test_helpers_for_home_and_weekly():
    """flip_dates / flip_counts 按北京日期区间（含两端）统计；today_progress 和 /api/flip/today 一致。"""
    import flip
    c = stable_fixture()
    add_log(c, 1, 'remember', '2026-11-15')
    add_log(c, 2, 'forget', '2026-11-16')
    add_log(c, 3, 'remember', '2026-11-16')
    add_log(c, 4, 'remember', '2026-11-18')
    add_log(c, 5, 'remember', '2026-11-18', deleted=1)          # 删除的不算
    add_log(c, 6, 'remember', '2026-11-23')
    c.commit()
    db = adapter(c)
    assert run(flip.flip_dates(db, 1, '2026-11-16', '2026-11-22')) == {'2026-11-16', '2026-11-18'}
    assert run(flip.flip_counts(db, 1, '2026-11-16', '2026-11-22')) == {'days': 2, 'cards': 3}
    assert run(flip.flip_counts(db, 1, '2026-12-01', '2026-12-07')) == {'days': 0, 'cards': 0}
    assert run(flip.flip_dates(db, 2, '2026-11-01', '2026-11-30')) == set()     # 别的学生
    post(c, 10, {'result': 'remember'})
    body = today_body(c)
    assert run(flip.today_progress(db, 1, TODAY)) == {'total': body['total'], 'done': body['done']} \
        == {'total': 8, 'done': 1}


class CountingDB(starmap_test.CountingDB):
    """记录 SQL 条数（含写入）的适配器。"""

    async def run(self, sql, parameters=()):
        self.calls += 1
        return await super().run(sql, parameters)


def test_query_count_is_fixed():
    """题目、翻牌记录多少不影响 SQL 条数：打开 5 条，记一次 5 条。"""
    import flip
    small = stable_fixture()
    big = stable_fixture()
    for qid in range(11, 60):
        add_question(big, qid, '2026-10-01 08:00:00', points=(101 + qid % 2,))
        add_log(big, qid, 'remember' if qid % 3 else 'forget', '2026-11-%02d' % (qid % 20 + 1))
    targeted_test.add_set(big, 1, '2026-11-10 08:00:00', '2026-11-10 20:00:00',
                          [(qid, True, 'original') for qid in range(11, 30)])
    big.commit()
    counts = []
    for c in (small, big):
        adapter(c)
        db = CountingDB(c)
        run(flip.build_today(db, 1, TODAY))
        opened = db.calls
        db.calls = 0
        run(flip.record_flip(db, 1, 1, 'remember', TODAY, TODAY + ' 20:00:00'))
        counts.append((opened, db.calls))
    assert counts[0] == counts[1] == (5, 5), counts


TESTS = [
    test_migration_creates_flip_log,
    test_constants,
    test_pick_today_limits_to_8,
    test_never_flipped_newest_first,
    test_forgot_waits_2_days,
    test_remember_gaps_3_7_14,
    test_forget_resets_remember_streak,
    test_today_flipped_excluded_and_order_stable,
    test_card_fields,
    test_graduated_excluded,
    test_pending_or_deleted_excluded,
    test_empty_stem_without_image_excluded,
    test_post_same_day_twice_records_once,
    test_post_rejects_bad_result_and_unknown_question,
    test_flip_does_not_change_mastery,
    test_helpers_for_home_and_weekly,
    test_query_count_is_fixed,
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
