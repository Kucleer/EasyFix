"""考点卷（定向出卷）的本地测试。

在 starmap_test 的测试库（旧结构 + 迁移 0011、0012）上再执行迁移 0015。运行：

    python cloudflare/scripts/targeted_test.py
"""

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
sys.path.insert(0, str(ROOT / 'scripts'))

import starmap_test  # noqa: E402  复用建库、适配器等助手
from targeted_model import has_figure, plan_paper, question_state, reason_of  # noqa: E402

MIGRATION_0015 = ROOT / 'migrations' / '0015_targeted_paper.sql'


def build_db():
    """建立测试库：starmap_test 的库 + 迁移 0015。"""
    connection = starmap_test.build_database()
    connection.executescript(MIGRATION_0015.read_text(encoding='utf-8'))
    connection.commit()
    return connection


def add_set(c, practice_id, created_at, reviewed_at, items, kind='targeted', deleted=0, subject_id=1):
    """插入一份卷子。items 为 [(错题编号, 做对 True/False/None, 题面 'original'/'similar')]。

    reviewed_at 为 None 表示还没批改（reviewed=0）；display_order 按列表顺序。
    """
    c.execute(
        'INSERT INTO practice_set(id,name,subject_id,question_type,kind,deleted,created_at,last_reviewed_at,reviewed) '
        'VALUES(?,?,?,?,?,?,?,?,?)',
        (practice_id, '考点卷%d' % practice_id, subject_id, 'mixed', kind, deleted, created_at, reviewed_at,
         0 if reviewed_at is None else 1))
    for order, (qid, correct, form) in enumerate(items):
        c.execute('INSERT INTO practice_set_question(practice_set_id,question_id,is_correct,display_order,form,deleted) '
                  'VALUES(?,?,?,?,?,0)', (practice_id, qid, correct, order, form))


# ---------------------------------------------------------------- 任务 1：迁移 0015


def test_migration_adds_columns():
    """0015 给三张表加上考点卷需要的列。"""
    c = build_db()
    cols = lambda t: {r[1] for r in c.execute('PRAGMA table_info(%s)' % t)}
    assert {'kind', 'grading_revision'} <= cols('practice_set')
    assert {'form', 'reason', 'knowledge_point_id', 'skip_reason'} <= cols('practice_set_question')
    assert 'explanation' in cols('similar_question')


def test_migration_defaults_keep_old_rows_valid():
    """旧卷子执行迁移后，kind 为 manual、grading_revision 为 0。"""
    c = starmap_test.build_database()
    c.execute("INSERT INTO practice_set(id,name,subject_id,deleted) VALUES(1,'旧卷',1,0)")
    c.executescript(MIGRATION_0015.read_text(encoding='utf-8'))
    row = c.execute('SELECT kind,grading_revision FROM practice_set WHERE id=1').fetchone()
    assert (row['kind'], row['grading_revision']) == ('manual', 0)


def test_add_set_helper_writes_rows():
    """add_set 写入卷子与题目行：未批改为 reviewed=0，顺序和题面正确。"""
    c = build_db()
    add_set(c, 5, '2026-11-01 10:00:00', None, [(11, None, 'original'), (12, True, 'similar')])
    paper = c.execute('SELECT kind,reviewed,question_type FROM practice_set WHERE id=5').fetchone()
    assert (paper['kind'], paper['reviewed'], paper['question_type']) == ('targeted', 0, 'mixed')
    rows = c.execute('SELECT question_id,form,display_order FROM practice_set_question WHERE practice_set_id=5 '
                     'ORDER BY display_order').fetchall()
    assert [(r[0], r[1], r[2]) for r in rows] == [(11, 'original', 0), (12, 'similar', 1)]


# ---------------------------------------------------------------- 任务 3：错题状态与选题纯函数


def make_question(qid, point_id, wrong_at='2026-10-01', results=None, entered=None, blocked=False):
    """造一道候选错题（plan_paper 的输入形状）。results 为 [(时间, 做对)]，题号顺序按列表先后。"""
    rows = [{'at': at, 'order': i, 'correct': ok} for i, (at, ok) in enumerate(results or [])]
    return {'id': qid, 'point_id': point_id, 'wrong_at': wrong_at, 'entered': entered or wrong_at,
            'results': rows, 'blocked': blocked}


def make_point(status, value, pending=0, all_graduated=False, waive_at=None):
    """造一个考点的掌握度信息（plan_paper 的 points 值）。"""
    return {'value': value, 'status': status, 'pending': pending, 'all_graduated': all_graduated,
            'waive_at': waive_at}


def mastered_point_question(qid, point_id):
    """已掌握考点下一道已毕业的题（连对 2 次），只能作为抽查题出。"""
    return make_question(qid, point_id, results=[('2026-10-10', True), ('2026-10-20', True)])


def example_fixture():
    """设计 5.3 的例子：考点 1–8（A–H）薄弱，掌握度 0.15、0.16 … 0.22，各 3 道没练过的旧错题；
    考点 9 已掌握，有 1 道已毕业的题。"""
    questions, points = [], {}
    for index in range(8):
        point_id = index + 1
        points[point_id] = make_point('weak', round(0.15 + 0.01 * index, 2), pending=3)
        for k in range(3):
            questions.append(make_question(point_id * 10 + k, point_id))
    points[9] = make_point('mastered', 1.0, all_graduated=True)
    questions.append(mastered_point_question(90, 9))
    return questions, points


def per_point(plan):
    """统计选中的题在各考点上的道数（含抽查题）：{考点编号: 道数}。"""
    counts = {}
    for item in plan['items']:
        counts[item['point_id']] = counts.get(item['point_id'], 0) + 1
    return counts


def test_question_state_table():
    """设计 4.1 的表。"""
    r = lambda at, ok, order=0: {'at': at, 'order': order, 'correct': ok}
    assert question_state([], '2026-11-01', None)['state'] == 'todo'
    assert question_state([r('2026-11-02', True), r('2026-11-03', False)], '2026-11-01', None)['state'] == 'todo'
    assert question_state([r('2026-11-02', True)], '2026-11-01', None)['state'] == 'consolidating'
    assert question_state([r('2026-11-02', True), r('2026-11-03', True)], '2026-11-01', None)['state'] == 'graduated'
    again = question_state([r('2026-11-02', True), r('2026-11-03', True), r('2026-11-04', False)], '2026-11-01', None)
    assert again['state'] == 'todo' and again['streak'] == 0 and again['practised'] is True


def test_question_state_waived_by_set_mastered():
    """录入早于"直接设为掌握"的题视同已毕业；之后做错照常清零。"""
    assert question_state([], '2026-11-01', '2026-11-05')['state'] == 'graduated'
    assert question_state([], '2026-11-06', '2026-11-05')['state'] == 'todo'
    r = {'at': '2026-11-07', 'order': 0, 'correct': False}
    assert question_state([r], '2026-11-01', '2026-11-05')['state'] == 'todo'


def test_question_state_sorts_by_time_and_order():
    """结果按 (时间, 题号) 排序后再数连对，输入顺序不影响；last_at 是最后一次结果的时间。"""
    rows = [{'at': '2026-11-03', 'order': 1, 'correct': True}, {'at': '2026-11-03', 'order': 0, 'correct': False},
            {'at': '2026-11-02', 'order': 0, 'correct': True}]
    state = question_state(rows, '2026-11-01', None)
    assert state['streak'] == 1 and state['state'] == 'consolidating' and state['last_at'] == '2026-11-03'


def test_plan_example_spread_and_focus():
    """设计 5.3 的例子：题量 12、抽查 1，8 个薄弱考点 A–H 各有 3 道没练过的旧错题，另有 1 个已掌握的考点。"""
    questions, points = example_fixture()          # 考点编号 1–8 对应 A–H，掌握度依次 0.15、0.16 … 0.22；考点 9 已掌握
    spread = plan_paper(questions, points, None, '2026-11-12', 12, 'spread', 1)
    assert per_point(spread) == {1: 2, 2: 2, 3: 2, 4: 1, 5: 1, 6: 1, 7: 1, 8: 1, 9: 1}
    focus = plan_paper(questions, points, None, '2026-11-12', 12, 'focus', 1)
    assert per_point(focus) == {1: 3, 2: 3, 3: 3, 4: 2, 9: 1}
    assert spread['items'][-1]['reason'] == 'spot' and spread['shortfall'] == 0


def test_reason_order():
    """同一考点下 new、wrong、redo、consolidate 各一道：按原因先后出，题面分别是原题/相似题。"""
    questions = [
        make_question(1, 1, wrong_at='2026-09-01', results=[('2026-10-01', True)]),    # 巩固
        make_question(2, 1, wrong_at='2026-09-02'),                                  # 旧错题重做
        make_question(3, 1, wrong_at='2026-09-03', results=[('2026-10-02', False)]),   # 上次做错
        make_question(4, 1, wrong_at='2026-11-10'),                                  # 新错题
    ]
    points = {1: make_point('weak', 0.2, pending=3)}
    plan = plan_paper(questions, points, None, '2026-11-12', 4, 'spread', 0)
    assert [item['reason'] for item in plan['items']] == ['new', 'wrong', 'redo', 'consolidate']
    forms = {item['reason']: item['form'] for item in plan['items']}
    assert forms['new'] == 'original' and forms['redo'] == 'original'
    assert forms['wrong'] == 'similar' and forms['consolidate'] == 'similar'


def test_new_uses_last_paper_time():
    """新错题按上一份考点卷的出卷时间算；从没出过卷时取最近 7 天。"""
    todo = question_state([], '2026-10-01', None)
    point = {'status': 'weak', 'all_graduated': False}
    assert reason_of(todo, '2026-11-06', '2026-11-05', '2026-11-12', point) == 'new'
    assert reason_of(todo, '2026-11-04', '2026-11-05', '2026-11-12', point) == 'redo'
    assert reason_of(todo, '2026-11-05', None, '2026-11-12', point) == 'new'
    assert reason_of(todo, '2026-11-04', None, '2026-11-12', point) == 'redo'


def test_spread_many_points():
    """30 个薄弱考点、题量 12、抽查 1：排在最前的 11 个考点各 1 道，外加 1 道抽查。"""
    questions, points = [], {}
    for point_id in range(1, 31):
        points[point_id] = make_point('weak', 0.2, pending=1)
        questions.append(make_question(point_id * 10, point_id))
    points[99] = make_point('mastered', 1.0, all_graduated=True)
    questions.append(mastered_point_question(990, 99))
    plan = plan_paper(questions, points, None, '2026-11-12', 12, 'spread', 1)
    expected = {point_id: 1 for point_id in range(1, 12)}
    expected[99] = 1
    assert per_point(plan) == expected


def test_point_order_four_keys():
    """两个考点只差一个排序键时，先后符合第 4 步（编号大的那个靠排序键赢）。"""
    def first_point(points, questions, last_paper_at=None):
        """题量 1、不抽查时第一道题所在的考点。"""
        plan = plan_paper(questions, points, last_paper_at, '2026-11-12', 1, 'spread', 0)
        return plan['items'][0]['point_id']

    same_q = lambda: [make_question(10, 1), make_question(20, 2)]
    # 需要度：薄弱 > 一般
    assert first_point({1: make_point('fair', 0.3, 1), 2: make_point('weak', 0.3, 1)}, same_q()) == 2
    # 有新错题需要度 +1：一般 + 新错题(3) > 一般 + 上次做错(2)，即使对方的错题日期更新
    questions = [make_question(10, 1, wrong_at='2026-11-11', results=[('2026-11-11', False)]),
                 make_question(20, 2, wrong_at='2026-11-10')]
    points = {1: make_point('fair', 0.5, 1), 2: make_point('fair', 0.5, 1)}
    assert first_point(points, questions, last_paper_at='2026-11-05') == 2
    # 掌握度低的在前
    assert first_point({1: make_point('weak', 0.3, 1), 2: make_point('weak', 0.2, 1)}, same_q()) == 2
    # 待重做多的在前
    assert first_point({1: make_point('weak', 0.3, 1), 2: make_point('weak', 0.3, 2)}, same_q()) == 2
    # 最近一道错题日期新的在前
    questions = [make_question(10, 1, wrong_at='2026-10-01'), make_question(20, 2, wrong_at='2026-10-02')]
    assert first_point({1: make_point('weak', 0.3, 1), 2: make_point('weak', 0.3, 1)}, questions) == 2
    # 全部相同时按考点编号
    assert first_point({1: make_point('weak', 0.3, 1), 2: make_point('weak', 0.3, 1)}, same_q()) == 1


def test_cap_lifts_when_short():
    """只有 2 个考点、各 5 道题、题量 9：放开 3 道上限后凑满。"""
    questions = [make_question(point_id * 10 + k, point_id) for point_id in (1, 2) for k in range(5)]
    points = {1: make_point('weak', 0.2, 5), 2: make_point('weak', 0.3, 5)}
    plan = plan_paper(questions, points, None, '2026-11-12', 9, 'spread', 0)
    assert per_point(plan) == {1: 5, 2: 4} and plan['shortfall'] == 0
    focus = plan_paper(questions, points, None, '2026-11-12', 9, 'focus', 0)
    assert per_point(focus) == {1: 5, 2: 4} and focus['shortfall'] == 0


def test_shortfall_when_exhausted():
    """只有 4 道能出的题、题量 10：选出 4 道，少 6 道。"""
    questions = [make_question(k, 1 + k % 2) for k in range(4)]
    points = {1: make_point('weak', 0.2, 2), 2: make_point('fair', 0.5, 2)}
    plan = plan_paper(questions, points, None, '2026-11-12', 10, 'spread', 1)
    assert len(plan['items']) == 4 and plan['shortfall'] == 6


def test_check_only_one_per_point():
    """错题全部毕业、还没点亮的考点：只出 1 道验收题，题面是相似题。"""
    questions = [mastered_point_question(1, 1), mastered_point_question(2, 1)]
    points = {1: make_point('fair', 0.65, 0, all_graduated=True)}
    plan = plan_paper(questions, points, None, '2026-11-12', 5, 'spread', 0)
    assert len(plan['items']) == 1
    assert plan['items'][0]['reason'] == 'check' and plan['items'][0]['form'] == 'similar'


def test_blocked_and_unlearned_excluded():
    """在没批改卷子里的题、没学考点下的题，既不选也不进备选。"""
    questions = [make_question(1, 1, blocked=True), make_question(2, 1), make_question(3, 2)]
    points = {1: make_point('weak', 0.2, 2), 2: make_point('unlearned', None, 1)}
    plan = plan_paper(questions, points, None, '2026-11-12', 1, 'spread', 0)
    ids = {item['question_id'] for item in plan['items']}
    ids |= {item['question_id'] for rows in plan['reserve'].values() for item in rows}
    assert ids == {2}
    plan = plan_paper(questions, points, None, '2026-11-12', 10, 'spread', 0)
    assert [item['question_id'] for item in plan['items']] == [2] and plan['reserve'] == {}


def test_spot_zero_and_spot_refund():
    """抽查 0 道时没有抽查题；抽查 2 道但只有 1 个已掌握考点时抽 1 道，剩下的名额照常分。"""
    questions = [make_question(10 + k, 1) for k in range(5)] + [mastered_point_question(90, 9)]
    points = {1: make_point('weak', 0.2, 5), 9: make_point('mastered', 1.0, all_graduated=True)}
    plan = plan_paper(questions, points, None, '2026-11-12', 4, 'spread', 0)
    assert all(item['reason'] != 'spot' for item in plan['items']) and len(plan['items']) == 4
    plan = plan_paper(questions, points, None, '2026-11-12', 6, 'spread', 2)
    assert [item['reason'] for item in plan['items']].count('spot') == 1
    assert per_point(plan) == {1: 5, 9: 1} and plan['shortfall'] == 0


def test_spot_takes_at_most_half():
    """抽查最多占题量一半（向下取整）：题量 1 不抽查；题量 3、抽查 2 只抽 1 道。"""
    questions = [make_question(10 + k, 1) for k in range(3)]
    questions += [mastered_point_question(80, 8), mastered_point_question(90, 9)]
    points = {1: make_point('weak', 0.2, 3), 8: make_point('mastered', 1.0, all_graduated=True),
              9: make_point('mastered', 1.0, all_graduated=True)}
    plan = plan_paper(questions, points, None, '2026-11-12', 1, 'spread', 1)
    assert len(plan['items']) == 1 and plan['items'][0]['reason'] != 'spot'
    plan = plan_paper(questions, points, None, '2026-11-12', 3, 'spread', 2)
    assert [item['reason'] for item in plan['items']].count('spot') == 1 and len(plan['items']) == 3


def test_spot_prefers_longest_unpractised_point():
    """抽查先抽最久没练过的考点。"""
    questions = [make_question(80, 8, results=[('2026-10-10', True), ('2026-10-25', True)]),
                 make_question(90, 9, results=[('2026-10-10', True), ('2026-10-20', True)])]
    points = {8: make_point('mastered', 1.0, all_graduated=True), 9: make_point('mastered', 1.0, all_graduated=True)}
    plan = plan_paper(questions, points, None, '2026-11-12', 2, 'spread', 1)
    assert [(item['question_id'], item['reason'], item['form']) for item in plan['items']] == [(90, 'spot', 'similar')]


def test_plan_empty_candidates():
    """没有能出的题：空清单、少出题量那么多道、没有备选。"""
    plan = plan_paper([], {}, None, '2026-11-12', 12, 'spread', 1)
    assert plan == {'items': [], 'reserve': {}, 'shortfall': 12}


def test_reserve_keeps_unselected_in_order():
    """备选是每个考点没被选上的题，按考点内顺序，最多 5 条。"""
    questions = [make_question(10 + k, 1, wrong_at='2026-10-%02d' % (k + 1)) for k in range(9)]
    points = {1: make_point('weak', 0.2, 9)}
    plan = plan_paper(questions, points, None, '2026-11-12', 3, 'spread', 0)
    assert [item['question_id'] for item in plan['items']] == [18, 17, 16]
    assert [item['question_id'] for item in plan['reserve'][1]] == [15, 14, 13, 12, 11]
    assert plan['reserve'][1][0] == {'question_id': 15, 'point_id': 1, 'reason': 'redo', 'form': 'original'}


def test_has_figure():
    """题干里有"如图"等字样，或复核原因里有 figure_needed，就是带图的题。"""
    assert has_figure('如图，AB=3', None) is True
    assert has_figure('计算', '["figure_needed"]') is True
    assert has_figure('计算 1+1', None) is False
    assert has_figure(None, '') is False


def test_plan_is_deterministic():
    """同样的输入结果一样；把 questions 倒序也一样。"""
    questions, points = example_fixture()
    first = plan_paper(questions, points, None, '2026-11-12', 12, 'spread', 1)
    assert plan_paper(questions, points, None, '2026-11-12', 12, 'spread', 1) == first
    assert plan_paper(list(reversed(questions)), points, None, '2026-11-12', 12, 'spread', 1) == first
    focus = plan_paper(questions, points, None, '2026-11-12', 12, 'focus', 1)
    assert plan_paper(list(reversed(questions)), points, None, '2026-11-12', 12, 'focus', 1) == focus


TESTS = [
    test_migration_adds_columns,
    test_migration_defaults_keep_old_rows_valid,
    test_add_set_helper_writes_rows,
    test_question_state_table,
    test_question_state_waived_by_set_mastered,
    test_question_state_sorts_by_time_and_order,
    test_plan_example_spread_and_focus,
    test_reason_order,
    test_new_uses_last_paper_time,
    test_spread_many_points,
    test_point_order_four_keys,
    test_cap_lifts_when_short,
    test_shortfall_when_exhausted,
    test_check_only_one_per_point,
    test_blocked_and_unlearned_excluded,
    test_spot_zero_and_spot_refund,
    test_spot_takes_at_most_half,
    test_spot_prefers_longest_unpractised_point,
    test_plan_empty_candidates,
    test_reserve_keeps_unselected_in_order,
    test_has_figure,
    test_plan_is_deterministic,
]


def check(name, function):
    """运行单个测试，打印 PASS/FAIL，返回是否通过。"""
    return starmap_test.check(name, function)


def main():
    """运行全部测试并打印总数；有失败时以非零状态退出。"""
    starmap_test.configure_output()
    results = [check(function.__name__, function) for function in TESTS]
    passed = sum(results)
    print('%d 通过，%d 失败' % (passed, len(results) - passed))
    sys.exit(len(results) - passed)


if __name__ == '__main__':
    main()
