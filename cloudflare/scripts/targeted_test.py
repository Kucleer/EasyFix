"""考点卷（定向出卷）的本地测试。

在 starmap_test 的测试库（旧结构 + 迁移 0011、0012）上再执行迁移 0015。运行：

    python cloudflare/scripts/targeted_test.py
"""

import json
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
        'INSERT INTO practice_set(id,name,subject_id,source_type,question_type,kind,deleted,created_at,last_reviewed_at,'
        "reviewed) VALUES(?,?,?,'question',?,?,?,?,?,?)",
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


# ---------------------------------------------------------------- 任务 4：相似题提示词、保存解析、复用规则


def similar_env(monkeypatch_result):
    """替换 similar.generate_json 与 pdf.validate_math，返回 (similar 模块, 校验调用记录, 还原函数)。"""
    import pdf
    import similar
    calls = []
    saved = (similar.generate_json, pdf.validate_math)

    async def fake_generate(request, prompt):
        calls.append(('model', prompt))
        return monkeypatch_result

    async def fake_validate(request, texts):
        calls.append(('math', list(texts)))

    similar.generate_json, pdf.validate_math = fake_generate, fake_validate

    def restore():
        similar.generate_json, pdf.validate_math = saved
    return similar, calls, restore


def similar_fixture():
    """建库、写一道数学错题，返回 (连接, 异步 db, 假请求, 原题行)。"""
    c = build_db()
    starmap_test.add_question(c, 11, 1, '2026-10-01', [101])
    c.commit()
    db = starmap_test.adapter(c)
    original = dict(c.execute('SELECT q.*,s.name AS subject_name FROM question q JOIN subject s ON s.id=q.subject_id '
                              'WHERE q.id=11').fetchone())
    return c, db, starmap_test.FakeRequest(None, db), original


def test_targeted_prompt_content():
    """提示词带无图要求、三句话限制和考点路径；不出现错因和错误答案。"""
    from prompts import PromptLibrary
    text = PromptLibrary()._build_targeted_prompt(
        '计算 3x+2x', '5x', '数学', [{'name': '合并同类项', 'parent_name': '简单的代数式', 'is_primary': True}], True)
    assert '不依赖图形' in text and '三句话' in text and '简单的代数式 / 合并同类项' in text
    assert '错因' not in text and '错误类型' not in text and '错误答案' not in text
    plain = PromptLibrary()._build_targeted_prompt('计算 3x+2x', '5x', '数学', [], False)
    assert '错误答案' not in plain and '不依赖图形' not in plain



def test_create_similar_stores_explanation():
    """create_similar 写入带解析的新行，数学题校验一次公式。"""
    c, db, request, original = similar_fixture()
    similar, calls, restore = similar_env(
        {'similar_question': '计算 4x+x', 'similar_answer': '5x', 'explanation': '合并同类项，系数相加。'})
    try:
        row = starmap_test.run(similar.create_similar(db, request, original, 'prompt'))
    finally:
        restore()
    assert row['explanation'] == '合并同类项，系数相加。' and row['deleted'] == 0 and row['source_question_id'] == 11
    assert [kind for kind, _ in calls] == ['model', 'math'] and calls[0][1] == 'prompt'


def test_create_similar_rejects_empty():
    """模型返回空题目时抛 502，表里没有新行。"""
    from fastapi import HTTPException
    c, db, request, original = similar_fixture()
    similar, calls, restore = similar_env({'similar_question': '', 'similar_answer': '5x', 'explanation': '解析'})
    try:
        try:
            starmap_test.run(similar.create_similar(db, request, original, 'prompt'))
            raise AssertionError('应当抛出 502')
        except HTTPException as error:
            assert error.status_code == 502
    finally:
        restore()
    assert c.execute('SELECT COUNT(*) FROM similar_question').fetchone()[0] == 0


def test_reusable_similar_rules():
    """没解析的不复用；被没删除卷子用过的不复用；被已删除卷子用过的可复用；已删除的不复用；取最新一道。"""
    import similar
    c, db, request, original = similar_fixture()

    def add(sid, explanation, deleted=0):
        c.execute('INSERT INTO similar_question(id,source_question_id,similar_text,similar_answer,explanation,deleted,'
                  'generated_at) VALUES(?,?,?,?,?,?,?)', (sid, 11, '题', '答', explanation, deleted, '2026-11-01'))

    def use(sid, set_id, deleted=0):
        c.execute('INSERT INTO practice_set_question(practice_set_id,question_id,similar_question_id,display_order,'
                  'form,deleted) VALUES(?,?,?,0,?,?)', (set_id, 11, sid, 'similar', deleted))

    pick = lambda: (lambda row: row and row['id'])(starmap_test.run(similar.reusable_similar(db, 11)))
    add(1, None)
    assert pick() is None                               # 旧相似题没有解析
    add(2, '解析')
    assert pick() == 2
    add_set(c, 7, '2026-11-02 10:00:00', None, [])
    use(2, 7)
    assert pick() is None                               # 被没删除的卷子用过
    c.execute('UPDATE practice_set SET deleted=1 WHERE id=7')
    assert pick() == 2                                  # 卷子已删除，可再用
    c.execute('UPDATE practice_set SET deleted=0 WHERE id=7')
    c.execute('UPDATE practice_set_question SET deleted=1 WHERE practice_set_id=7')
    assert pick() == 2                                  # 题目行已删除，可再用
    add(3, '解析', deleted=1)
    assert pick() == 2                                  # 已删除的相似题不复用
    add(4, '解析')
    assert pick() == 4                                  # 取最新


# ---------------------------------------------------------------- 任务 5：出卷接口


def days_ago(days):
    """北京时间 days 天前的时间文本（'YYYY-MM-DD HH:MM:SS'），测试按当前时钟造"最近 30 天"的数据。"""
    import datetime
    from analytics import now
    return (now() - datetime.timedelta(days=days)).isoformat(' ')[:19]


def request_for(db, payload=None):
    """造一个假请求，让 targeted、starmap、settings 模块直接使用传入的 db。"""
    import targeted
    targeted.Database = lambda binding: binding
    return starmap_test.request_for(db, payload)


def install_fakes():
    """替换 similar.generate_json 与 pdf.validate_math。

    返回 (calls, restore)：calls['model']、calls['math'] 是调用次数；改 calls['result'] 换模型的返回，
    把 calls['error'] 设成异常对象时假模型抛出它。
    """
    import pdf
    import similar
    calls = {'model': 0, 'math': 0, 'error': None, 'prompts': [],
             'result': {'similar_question': '相似题目', 'similar_answer': '相似答案', 'explanation': '相似解析'}}
    saved = (similar.generate_json, pdf.validate_math)

    async def fake_generate(request, prompt):
        calls['model'] += 1
        calls['prompts'].append(prompt)
        if calls['error'] is not None:
            raise calls['error']
        return dict(calls['result'])

    async def fake_validate(request, texts):
        calls['math'] += 1

    similar.generate_json, pdf.validate_math = fake_generate, fake_validate

    def restore():
        similar.generate_json, pdf.validate_math = saved
    return calls, restore


def with_fakes(function):
    """测试装饰器：运行期间装上假模型，结束后还原；被装饰的函数第一个参数是 calls。"""
    def wrapper():
        calls, restore = install_fakes()
        try:
            function(calls)
        finally:
            restore()
    wrapper.__name__ = function.__name__
    wrapper.__doc__ = function.__doc__
    return wrapper


def paper_fixture():
    """数学：考点 101 两道没练过的旧错题（1、2），考点 102 一道上次做错的题（3）。返回 (连接, db)。"""
    c = build_db()
    starmap_test.add_question(c, 1, 1, '2026-09-01 08:00:00', [101])
    starmap_test.add_question(c, 2, 1, '2026-09-02 08:00:00', [101])
    starmap_test.add_question(c, 3, 1, '2026-09-03 08:00:00', [102])
    c.execute("UPDATE question SET wrong_answer='错的答案', answer='对的答案' WHERE id=3")
    add_set(c, 1, '2026-09-10 08:00:00', '2026-09-11 08:00:00', [(3, 0, 'original')], kind='manual')
    c.commit()
    return c, starmap_test.adapter(c)


def plan_body(db, **payload):
    """调用 plan，返回结果。"""
    import targeted
    return starmap_test.run(targeted.plan(request_for(db, {'subject_id': 1, **payload})))


def plan_ids(db, **payload):
    """plan 选中的错题编号集合。"""
    return {item['question_id'] for item in plan_body(db, **payload)['items']}


def create_items(body):
    """把 plan 的结果变成 create 的 items。"""
    return [{key: item[key] for key in ('question_id', 'point_id', 'reason', 'form')} for item in body['items']]


def create_paper(db, items, **extra):
    """调用 create，返回卷子详情。"""
    import targeted
    return starmap_test.run(targeted.create(request_for(db, {'subject_id': 1, 'items': items, **extra})))


def test_plan_endpoint_shape_and_reasons():
    """一科里：考点 101 薄弱（两道没练过的旧错题）、考点 102 有一道上次做错的题。"""
    c, db = paper_fixture()
    body = plan_body(db, size=3, spot_count=0)
    assert sorted(i['reason'] for i in body['items']) == ['redo', 'redo', 'wrong'] and body['shortfall'] == 0
    assert all(i['form'] == ('similar' if i['reason'] == 'wrong' else 'original') for i in body['items'])
    first = body['items'][0]
    assert {'question_id', 'point_id', 'point_name', 'module_id', 'module_name', 'reason', 'form', 'stem',
            'has_figure'} <= set(first)
    assert first['module_name'] == '有理数' and first['stem'].startswith('题')
    assert body['open_paper_count'] == 0 and body['last_paper'] is None


def test_plan_validations():
    """题量、分法、抽查数不对时 422。"""
    import targeted
    c, db = paper_fixture()
    for payload in ({'size': 0}, {'size': 91}, {'size': '3'}, {'size': True}, {'size': 3, 'mode': 'x'},
                    {'size': 3, 'spot_count': -1}, {'size': 3, 'spot_count': 91}):
        starmap_test.expect_http_error(422, targeted.plan(request_for(db, {'subject_id': 1, **payload})))


@with_fakes
def test_create_then_prepare_until_done(calls):
    """按 plan 的结果创建考点卷，再一道一道准备相似题。"""
    import practices
    import targeted
    c, db = paper_fixture()
    items = create_items(plan_body(db, size=3, spot_count=0))
    paper = starmap_test.run(targeted.create(request_for(db, {'subject_id': 1, 'items': items})))
    assert paper['kind'] == 'targeted' and paper['question_type'] == 'mixed' and paper['total_questions'] == 3
    assert [q['number'] for q in paper['questions']] == [1, 2, 3]
    assert paper['name'].startswith('数学练习卷 ') and paper['name'].endswith('日')
    left = starmap_test.run(targeted.prepare(paper['id'], request_for(db, {})))
    assert left['remaining'] == 0 and calls['model'] == 1          # 只有一道相似题要生成，只调一次模型
    detail = starmap_test.run(practices.get(db, paper['id']))
    similar = [q for q in detail['questions'] if q['form'] == 'similar'][0]
    assert similar['question_text'] == '相似题目' and similar['explanation']
    assert similar['answer'] == '相似答案' and similar['reason'] == 'wrong' and similar['knowledge_point_id'] == 102
    done = starmap_test.run(targeted.prepare(paper['id'], request_for(db, {})))
    assert done == {'remaining': 0, 'item_id': None, 'fallback': False} and calls['model'] == 1

@with_fakes
def test_prepare_prompt_ignores_wrong_answer(calls):
    """错题记着孩子当时的错误答案时，准备相似题的提示词里也不出现它（设计：相似题只根据错题本身出）。"""
    c, db = paper_fixture()        # 错题 3 的 wrong_answer 是"错的答案"
    paper = create_paper(db, [{'question_id': 3, 'point_id': 102, 'reason': 'wrong', 'form': 'similar'}])
    starmap_test.run(__import__('targeted').prepare(paper['id'], request_for(db, {})))
    assert calls['model'] == 1
    assert calls['prompts'] and all('错的答案' not in prompt and '错误答案' not in prompt for prompt in calls['prompts'])


def test_plan_excludes_blocked_and_old_open_papers():
    """10 天前没批改的卷子占着题；40 天前没批改的卷子不占题；open_paper_count 只算 30 天内的。"""
    c, db = paper_fixture()
    add_set(c, 50, days_ago(10), None, [(1, None, 'original')])
    add_set(c, 51, days_ago(40), None, [(2, None, 'original')])
    c.commit()
    body = plan_body(db, size=10)
    ids = {item['question_id'] for item in body['items']}
    assert 1 not in ids and 2 in ids and body['open_paper_count'] == 1
    assert body['last_paper']['id'] == 50 and body['last_paper']['state'] == 'to_print'


def grade_fixture(default_grade):
    """考点 101 下三道题：五年级、年级为空、六年级；default_grade 为空时不写应用配置。"""
    c = build_db()
    if default_grade is not None:
        starmap_test.set_config(c, 'app', {'default_grade': default_grade, 'default_semester': 1})
    for qid, grade in ((1, 5), (2, None), (3, 6)):
        starmap_test.add_question(c, qid, 1, '2026-09-0%d 08:00:00' % qid, [101])
        c.execute('UPDATE question SET grade=? WHERE id=?', (grade, qid))
    c.commit()
    return starmap_test.adapter(c)


def test_plan_lower_grades_switch():
    """默认年级 6：五年级的题默认不出，打开"包含低年级"后出；年级为空的题都出。"""
    db = grade_fixture(6)
    assert plan_ids(db, size=10) == {2, 3}
    assert plan_ids(db, size=10, include_lower_grades=True) == {1, 2, 3}


def test_plan_without_default_grade():
    """没设默认年级时五年级的题也出，不报错。"""
    assert plan_ids(grade_fixture(None), size=10) == {1, 2, 3}


def test_plan_and_create_with_nothing_to_pick():
    """没有错题的学科：plan 返回空清单、shortfall 等于题量；create 传空清单 422。"""
    import targeted
    c, db = paper_fixture()
    body = starmap_test.run(targeted.plan(request_for(db, {'subject_id': 2, 'size': 12})))
    assert body['items'] == [] and body['shortfall'] == 12 and body['reserve'] == {}
    starmap_test.expect_http_error(422, targeted.create(request_for(db, {'subject_id': 2, 'items': []})))


def test_plan_query_count_is_fixed():
    """5 道题和 60 道题时 plan 执行的 SQL 条数相同。"""
    import targeted

    def count(total):
        """建 total 道题（分在四个考点上，部分做过），返回 plan 执行的 SQL 条数。"""
        c = build_db()
        points = (101, 102, 111, 112)
        for qid in range(1, total + 1):
            starmap_test.add_question(c, qid, 1, '2026-09-%02d 08:00:00' % (qid % 28 + 1), [points[qid % 4]])
        add_set(c, 1, '2026-10-01 08:00:00', '2026-10-02 08:00:00',
                [(qid, qid % 2 == 0, 'original') for qid in range(1, total + 1, 3)])
        add_set(c, 2, days_ago(3), None, [(2, None, 'original')])
        c.commit()
        counter = starmap_test.CountingDB(c)
        starmap_test.run(targeted.plan(request_for(counter, {'subject_id': 1, 'size': 12})))
        return counter.calls

    small, big = count(5), count(60)
    assert small == big, (small, big)


def test_create_validations():
    """题号重复、别科的题、待核对的题、考点不对、原因不对 422；题在没批改的卷子里 409；失败不写卷子。"""
    import targeted
    c, db = paper_fixture()
    starmap_test.add_question(c, 20, 2, '2026-09-01 08:00:00', [201])
    starmap_test.add_question(c, 21, 1, '2026-09-01 08:00:00', [101], status='pending')
    starmap_test.add_question(c, 22, 1, '2026-09-01 08:00:00', [111])
    add_set(c, 60, days_ago(5), None, [(22, None, 'original')])
    c.commit()
    before = c.execute('SELECT COUNT(*) FROM practice_set').fetchone()[0]

    def item(qid, point, reason='redo', form='original'):
        """一条创建用的题目。"""
        return {'question_id': qid, 'point_id': point, 'reason': reason, 'form': form}

    bad = [
        [item(1, 101), item(1, 101)],            # 题号重复
        [item(20, 201)],                         # 别的学科
        [item(21, 101)],                         # 待核对
        [item(1, 102)],                          # 不是它挂的考点
        [item(1, 101, reason='x')],              # 原因不对
        [item(1, 101, form='x')],                # 题面不对
        [item(1, 100)],                          # 一级考点
        'x',
    ]
    for items in bad:
        starmap_test.expect_http_error(422, targeted.create(request_for(db, {'subject_id': 1, 'items': items})))
    starmap_test.expect_http_error(409, targeted.create(request_for(db, {'subject_id': 1, 'items': [item(22, 111)]})))
    assert c.execute('SELECT COUNT(*) FROM practice_set').fetchone()[0] == before


def test_create_orders_by_module_and_point():
    """请求里交错给出两个模块的题，创建后同一模块、同一考点的题题号相连。"""
    c, db = paper_fixture()
    starmap_test.add_question(c, 11, 1, '2026-09-05 08:00:00', [111])
    starmap_test.add_question(c, 12, 1, '2026-09-06 08:00:00', [111])
    c.commit()

    def item(qid, point):
        """一条创建用的题目。"""
        return {'question_id': qid, 'point_id': point, 'reason': 'redo', 'form': 'original'}

    paper = create_paper(db, [item(11, 111), item(1, 101), item(12, 111), item(3, 102), item(2, 101)],
                         name='自定义名称')
    assert [q['question_id'] for q in paper['questions']] == [1, 2, 3, 11, 12]
    assert [q['number'] for q in paper['questions']] == [1, 2, 3, 4, 5] and paper['name'] == '自定义名称'


@with_fakes
def test_prepare_reuses_unused_similar(calls):
    """错题已有一道带解析、没用过的相似题时，prepare 直接复用，不调模型。"""
    import practices
    import targeted
    c, db = paper_fixture()
    c.execute("INSERT INTO similar_question(id,source_question_id,similar_text,similar_answer,explanation,deleted,"
              "generated_at) VALUES(9,3,'旧相似题','旧答案','旧解析',0,'2026-10-01')")
    c.commit()
    paper = create_paper(db, create_items(plan_body(db, size=3, spot_count=0)))
    left = starmap_test.run(targeted.prepare(paper['id'], request_for(db, {})))
    assert left['remaining'] == 0 and left['fallback'] is False and calls['model'] == 0
    detail = starmap_test.run(practices.get(db, paper['id']))
    similar = [q for q in detail['questions'] if q['form'] == 'similar'][0]
    assert similar['similar_question_id'] == 9 and similar['question_text'] == '旧相似题'


@with_fakes
def test_prepare_failure_keeps_item_pending_then_fallback(calls):
    """模型出错时 502，那一行保持未准备；再调仍处理同一道；带 fallback 后改成原题。"""
    from fastapi import HTTPException
    import pdf
    import targeted
    c, db = paper_fixture()
    paper = create_paper(db, create_items(plan_body(db, size=3, spot_count=0)))
    item_id = c.execute("SELECT id FROM practice_set_question WHERE practice_set_id=? AND form='similar'",
                        (paper['id'],)).fetchone()[0]
    calls['error'] = HTTPException(502, '模型出错')
    starmap_test.expect_http_error(502, targeted.prepare(paper['id'], request_for(db, {})))
    starmap_test.expect_http_error(502, targeted.prepare(paper['id'], request_for(db, {})))
    assert calls['model'] == 2
    row = c.execute('SELECT form,similar_question_id FROM practice_set_question WHERE id=?', (item_id,)).fetchone()
    assert (row[0], row[1]) == ('similar', None)
    # 公式校验不过（渲染服务返回 4xx）也按 502 处理
    calls['error'] = None

    async def bad_math(request, texts):
        """公式校验失败。"""
        raise HTTPException(422, '公式有误')
    pdf.validate_math = bad_math
    starmap_test.expect_http_error(502, targeted.prepare(paper['id'], request_for(db, {})))
    assert c.execute('SELECT COUNT(*) FROM similar_question').fetchone()[0] == 0
    left = starmap_test.run(targeted.prepare(paper['id'], request_for(db, {'fallback': True})))
    assert left == {'remaining': 0, 'item_id': item_id, 'fallback': True} and calls['model'] == 3
    row = c.execute('SELECT form,similar_question_id FROM practice_set_question WHERE id=?', (item_id,)).fetchone()
    assert (row[0], row[1]) == ('original', None)


@with_fakes
def test_reroll_replaces_similar(calls):
    """reroll 后那一行指向新的相似题，旧的软删除，reusable_similar 不再返回旧的。"""
    import similar
    import targeted
    c, db = paper_fixture()
    paper = create_paper(db, create_items(plan_body(db, size=3, spot_count=0)))
    starmap_test.run(targeted.prepare(paper['id'], request_for(db, {})))
    item_id, old_id = c.execute("SELECT id,similar_question_id FROM practice_set_question WHERE practice_set_id=? "
                                "AND form='similar'", (paper['id'],)).fetchone()
    calls['result'] = {'similar_question': '新相似题', 'similar_answer': '新答案', 'explanation': '新解析'}
    body = starmap_test.run(targeted.reroll(paper['id'], request_for(db, {'item_id': item_id})))
    assert body == {'item_id': item_id, 'similar_text': '新相似题', 'similar_answer': '新答案', 'explanation': '新解析'}
    new_id = c.execute('SELECT similar_question_id FROM practice_set_question WHERE id=?', (item_id,)).fetchone()[0]
    assert new_id != old_id and calls['model'] == 2
    assert c.execute('SELECT deleted FROM similar_question WHERE id=?', (old_id,)).fetchone()[0] == 1
    reusable = starmap_test.run(similar.reusable_similar(db, 3))
    assert reusable is None or reusable['id'] != old_id
    # 原题行、别的卷子的行、格式不对的编号不能 reroll
    original_id = c.execute("SELECT id FROM practice_set_question WHERE practice_set_id=? AND form='original'",
                            (paper['id'],)).fetchone()[0]
    for bad in (original_id, 99999, 'x'):
        starmap_test.expect_http_error(422, targeted.reroll(paper['id'], request_for(db, {'item_id': bad})))
    assert calls['model'] == 2


@with_fakes
def test_prepare_and_reroll_reject_closed_paper(calls):
    """已删除 404；已批改 409；手动组的卷子 422；都不写数据、不调模型。"""
    import targeted
    c, db = paper_fixture()
    add_set(c, 70, days_ago(1), None, [(3, None, 'similar')], deleted=1)
    add_set(c, 71, days_ago(1), days_ago(0), [(3, None, 'similar')])
    add_set(c, 72, days_ago(1), None, [(3, None, 'similar')], kind='manual')
    c.commit()
    for paper_id, status in ((70, 404), (71, 409), (72, 422), (99999, 404)):
        found = c.execute('SELECT id FROM practice_set_question WHERE practice_set_id=?', (paper_id,)).fetchone()
        item_id = found[0] if found else 1
        starmap_test.expect_http_error(status, targeted.prepare(paper_id, request_for(db, {})))
        starmap_test.expect_http_error(status, targeted.reroll(paper_id, request_for(db, {'item_id': item_id})))
    assert calls['model'] == 0 and c.execute('SELECT COUNT(*) FROM similar_question').fetchone()[0] == 0
    linked = c.execute('SELECT COUNT(*) FROM practice_set_question WHERE similar_question_id IS NOT NULL').fetchone()[0]
    forms = {row[0] for row in c.execute('SELECT form FROM practice_set_question WHERE practice_set_id IN (70,71,72)')}
    assert linked == 0 and forms == {'similar'}


def test_status_endpoint():
    """有 PDF、没批改的考点卷：to_grade，算进 pending_count；40 天前没批改的旧卷不算。"""
    import targeted
    c, db = paper_fixture()
    add_set(c, 80, days_ago(40), None, [(1, None, 'original')])
    add_set(c, 81, days_ago(2), None, [(2, None, 'original')])
    c.execute("UPDATE practice_set SET pdf_path='2026/11/a.pdf' WHERE id=81")
    add_set(c, 82, days_ago(1), days_ago(0), [(1, True, 'original')], subject_id=2)
    c.execute('UPDATE practice_set SET accuracy=83.3 WHERE id=82')
    c.commit()
    body = starmap_test.run(targeted.status(request_for(db)))
    assert body['pending_count'] == 1
    subjects = {row['subject_id']: row for row in body['subjects']}
    assert subjects[1]['subject_name'] == '数学'
    assert subjects[1]['last_paper']['id'] == 81 and subjects[1]['last_paper']['state'] == 'to_grade'
    assert subjects[2]['last_paper']['state'] == 'graded' and subjects[2]['last_paper']['accuracy'] == 83.3
    assert set(subjects[1]['last_paper']) == {'id', 'name', 'created_at', 'state', 'accuracy'}


def test_get_keeps_old_sets_working():
    """旧的整份相似题练习集（form 为空）仍显示相似题题面；旧的原题练习集显示原题；新字段都有。"""
    import practices
    c, db = paper_fixture()
    c.execute("INSERT INTO similar_question(id,source_question_id,similar_text,similar_answer,deleted,generated_at) "
              "VALUES(5,1,'旧相似题','旧相似答案',0,'2026-09-05')")
    c.execute("UPDATE question SET answer='原答案', analysis='原解析' WHERE id=1")
    for set_id, question_type in ((90, 'similar'), (91, 'original')):
        c.execute("INSERT INTO practice_set(id,name,subject_id,source_type,question_type,deleted,created_at,reviewed) "
                  "VALUES(?,?,1,'question',?,0,'2026-09-06 08:00:00',0)", (set_id, '旧卷%d' % set_id, question_type))
        c.execute('INSERT INTO practice_set_question(practice_set_id,question_id,similar_question_id,display_order) '
                  'VALUES(?,1,5,0)', (set_id,))
    c.commit()
    old_similar = starmap_test.run(practices.get(db, 90))
    question = old_similar['questions'][0]
    assert question['question_text'] == '旧相似题' and question['answer'] == '旧相似答案'
    assert question['number'] == 1 and question['analysis'] == '原解析' and question['form'] is None
    assert old_similar['kind'] == 'manual' and old_similar['grading_revision'] == 0
    old_original = starmap_test.run(practices.get(db, 91))
    question = old_original['questions'][0]
    assert question['question_text'] == '题1' and question['answer'] == '原答案'
    assert {'reason', 'knowledge_point_id', 'skip_reason', 'explanation'} <= set(question)


# ---------------------------------------------------------------- 任务 6：批改按差值计数


class GradeRequest(starmap_test.FakeRequest):
    """批改接口的假请求：在 FakeRequest 上补一个 JSON 的 content-type 请求头。"""

    def __init__(self, payload, db):
        super().__init__(payload, db)
        self.headers = {'content-type': 'application/json'}


def grade_request(db, payload):
    """造批改用的假请求，并让 practices、starmap、settings 直接使用传入的 db。"""
    import practices
    practices.Database = lambda binding: binding
    starmap_test.request_for(db)          # 顺带替换 starmap、settings 的 Database
    return GradeRequest(payload, db)


def with_motivation(function):
    """测试装饰器：把 motivation.trigger 换成计数的假函数，被装饰的函数第一个参数是计数字典。"""
    def wrapper():
        import motivation
        calls = {'trigger': 0}
        saved = motivation.trigger

        async def fake_trigger(db, code, reason=None):
            calls['trigger'] += 1
        motivation.trigger = fake_trigger
        try:
            function(calls)
        finally:
            motivation.trigger = saved
    wrapper.__name__ = function.__name__
    wrapper.__doc__ = function.__doc__
    return wrapper


def grading_fixture():
    """数学：错题 1、2、3 都在考点 101；考点卷 10 按顺序放 1、2、3，还没批改。返回 (连接, db)。"""
    c = build_db()
    for qid in (1, 2, 3):
        starmap_test.add_question(c, qid, 1, '2026-09-0%d 08:00:00' % qid, [101])
    add_set(c, 10, '2026-11-01 08:00:00', None, [(1, None, 'original'), (2, None, 'original'), (3, None, 'original')])
    c.commit()
    return c, starmap_test.adapter(c)


def mark(db, paper_id, pairs, revision=None, **extra):
    """返回批改协程。pairs 为 [(错题编号, 做对 True/False 或其它值)]；revision 为 None 时不带版本号。"""
    import practices
    payload = {'question_results': [{'question_id': qid, 'is_correct': correct} for qid, correct in pairs], **extra}
    if revision is not None:
        payload['grading_revision'] = revision
    return practices.reviewed(paper_id, grade_request(db, payload))


def submit(db, paper_id, pairs, revision=None, **extra):
    """提交一次批改，返回结果。"""
    return starmap_test.run(mark(db, paper_id, pairs, revision, **extra))


def counters(c, qid):
    """错题的 (review_count, correct_count, error_count)。"""
    return tuple(c.execute('SELECT review_count,correct_count,error_count FROM question WHERE id=?', (qid,)).fetchone())


def db_value(c, sql, *params):
    """取一条 SQL 的第一个值。"""
    return c.execute(sql, params).fetchone()[0]


def snapshot_tables(c):
    """把批改会写的几张表整体取出来，用来确认失败时没有任何改动。"""
    return [[tuple(row) for row in c.execute('SELECT * FROM %s ORDER BY id' % table)]
            for table in ('question', 'practice_set', 'practice_set_question')]


@with_motivation
def test_grading_is_idempotent_and_counts_delta(calls):
    """三道题：第一次批 对、错、对；原样再提交一次；再把第 2 题改成对。"""
    c, db = grading_fixture()
    first = submit(db, 10, [(1, True), (2, False), (3, True)], revision=0)
    assert first['accuracy'] == 66.7 and first['grading_revision'] == 1
    assert counters(c, 2) == (1, 0, 1)                      # (review_count, correct_count, error_count)
    stamp = db_value(c, 'SELECT last_reviewed_at FROM practice_set WHERE id=?', 10)
    assert stamp is not None
    again = submit(db, 10, [(1, True), (2, False), (3, True)], revision=1)
    assert counters(c, 2) == (1, 0, 1) and again['grading_revision'] == 2
    assert counters(c, 1) == (1, 1, 0)
    fixed = submit(db, 10, [(1, True), (2, True), (3, True)], revision=2)
    assert counters(c, 2) == (1, 1, 0) and fixed['accuracy'] == 100.0
    assert db_value(c, 'SELECT review_count FROM practice_set WHERE id=?', 10) == 1
    assert db_value(c, 'SELECT last_reviewed_at FROM practice_set WHERE id=?', 10) == stamp
    assert db_value(c, 'SELECT grading_revision FROM practice_set WHERE id=?', 10) == 3


@with_motivation
def test_grading_stale_revision_conflicts(calls):
    """带了过期的版本号：409，不写入。"""
    c, db = grading_fixture()
    submit(db, 10, [(1, True)], revision=0)
    before = snapshot_tables(c)
    starmap_test.expect_http_error(409, mark(db, 10, [(1, False)], revision=0))
    assert counters(c, 1) == (1, 1, 0) and snapshot_tables(c) == before


@with_motivation
def test_grading_guard_blocks_concurrent_submit(calls):
    """读到卷子之后、写入之前别人先提交了（版本号已变）：事务内断言让整批回滚，409，不重复计数。"""
    import practices
    c, db = grading_fixture()
    saved = practices.get

    async def stale_get(binding, practice_id, details=True):
        """先读到旧的卷子，再模拟另一个人抢先提交（库里版本号加 1）。"""
        row = await saved(binding, practice_id, details)
        c.execute('UPDATE practice_set SET grading_revision=grading_revision+1 WHERE id=?', (practice_id,))
        return row
    practices.get = stale_get
    try:
        before = snapshot_tables(c)
        starmap_test.expect_http_error(409, mark(db, 10, [(1, True)]))
    finally:
        practices.get = saved
    assert snapshot_tables(c)[0] == before[0] and counters(c, 1) == (0, 0, 0)
    assert db_value(c, 'SELECT reviewed FROM practice_set WHERE id=10') == 0 and calls['trigger'] == 0


@with_motivation
def test_grading_skip_reasons(calls):
    """没做、题目有误不算进正确率和错题计数，也不产生练习事件。"""
    import starmap
    c, db = grading_fixture()
    payload = [{'question_id': 1, 'skip_reason': 'not_done'},
               {'question_id': 2, 'is_correct': False, 'skip_reason': 'bad_question'},
               {'question_id': 3, 'is_correct': True}]
    import practices
    body = starmap_test.run(practices.reviewed(10, grade_request(db, {'question_results': payload,
                                                                      'grading_revision': 0})))
    assert body['accuracy'] == 100.0
    rows = {row[0]: (row[1], row[2]) for row in c.execute(
        'SELECT question_id,is_correct,skip_reason FROM practice_set_question WHERE practice_set_id=10')}
    assert rows == {1: (None, 'not_done'), 2: (None, 'bad_question'), 3: (1, None)}
    assert counters(c, 1) == (0, 0, 0) and counters(c, 2) == (0, 0, 0) and counters(c, 3) == (1, 1, 0)
    events = starmap_test.run(starmap.load_events(db, 1))
    practice_qids = {e['qid'] for point in events.values() for e in point if e['source'] == 'practice'}
    assert practice_qids == {3}


@with_motivation
def test_grading_skip_then_correct(calls):
    """先标没做，再改成做对：review_count 从 0 变 1，skip_reason 清空。"""
    import practices
    c, db = grading_fixture()
    starmap_test.run(practices.reviewed(10, grade_request(db, {
        'question_results': [{'question_id': 1, 'skip_reason': 'not_done'}], 'grading_revision': 0})))
    assert counters(c, 1) == (0, 0, 0)
    submit(db, 10, [(1, True)], revision=1)
    assert counters(c, 1) == (1, 1, 0)
    assert db_value(c, 'SELECT skip_reason FROM practice_set_question WHERE practice_set_id=10 AND question_id=1') \
        is None


@with_motivation
def test_grading_without_revision_still_works(calls):
    """不带 grading_revision（电脑旧弹窗）可以提交，版本号照样加 1。"""
    c, db = grading_fixture()
    assert submit(db, 10, [(1, True), (2, True), (3, False)])['grading_revision'] == 1
    assert submit(db, 10, [(3, True)])['grading_revision'] == 2
    assert counters(c, 3) == (1, 1, 0)


@with_motivation
def test_grading_partial_payload_keeps_others(calls):
    """已批改的卷子只提交一道题的修改，其他题结果不变；第一次批改时没提到的题算没批改。"""
    c, db = grading_fixture()
    first = submit(db, 10, [(1, True), (2, False)], revision=0)
    assert first['accuracy'] == 50.0
    assert db_value(c, 'SELECT is_correct FROM practice_set_question WHERE practice_set_id=10 AND question_id=3') \
        is None and counters(c, 3) == (0, 0, 0)
    body = submit(db, 10, [(2, True)], revision=1)
    results = dict(c.execute('SELECT question_id,is_correct FROM practice_set_question WHERE practice_set_id=10'))
    assert results == {1: 1, 2: 1, 3: None} and body['accuracy'] == 100.0
    assert counters(c, 1) == (1, 1, 0) and counters(c, 2) == (1, 1, 0)


@with_motivation
def test_grading_rejects_foreign_item(calls):
    """不属于这份卷子的题、is_correct 不是布尔值、skip_reason 不对、版本号不是整数：422，库里没有任何变化。"""
    import practices
    c, db = grading_fixture()
    starmap_test.add_question(c, 9, 1, '2026-09-09 08:00:00', [101])
    c.commit()
    before = snapshot_tables(c)
    bad_payloads = [
        {'question_results': [{'question_id': 1, 'is_correct': True}, {'question_id': 9, 'is_correct': True}]},
        {'question_results': [{'question_id': 1, 'is_correct': 1}]},
        {'question_results': [{'question_id': 1, 'is_correct': 'true'}]},
        {'question_results': [{'question_id': 1, 'skip_reason': 'x'}]},
        {'question_results': [{'question_id': '1', 'is_correct': True}]},
        {'question_results': [{'question_id': 1, 'is_correct': True}, {'question_id': 1, 'is_correct': False}]},
        {'question_results': [{'question_id': 1, 'is_correct': True}], 'grading_revision': 'x'},
        {'question_results': ['坏数据']},
    ]
    for payload in bad_payloads:
        starmap_test.expect_http_error(422, practices.reviewed(10, grade_request(db, payload)))
    assert snapshot_tables(c) == before and calls['trigger'] == 0


@with_motivation
def test_grading_motivation_only_first_time(calls):
    """两次提交，激励只触发一次。"""
    c, db = grading_fixture()
    submit(db, 10, [(1, True)], revision=0)
    submit(db, 10, [(1, False)], revision=1)
    assert calls['trigger'] == 1


@with_motivation
def test_grading_reports_changes(calls):
    """考点 102：错题 3、4；之前两份卷子把 4 做对两次、3 做对一次。这次 3 做对：3 毕业，102 点亮。"""
    c, db = grading_fixture()
    starmap_test.add_question(c, 4, 1, '2026-09-04 08:00:00', [102])
    c.execute('UPDATE question_knowledge_point SET knowledge_point_id=102 WHERE question_id=3')
    add_set(c, 1, '2026-09-10 08:00:00', '2026-09-10 20:00:00', [(3, 1, 'original'), (4, 1, 'original')])
    add_set(c, 2, '2026-09-12 08:00:00', '2026-09-12 20:00:00', [(4, 1, 'original')])
    c.execute('DELETE FROM practice_set_question WHERE practice_set_id=10')
    add_set(c, 11, '2026-11-01 08:00:00', None, [(1, None, 'original'), (3, None, 'original')])
    c.commit()
    body = submit(db, 11, [(1, True), (3, True)], revision=0)
    points = {point['id']: point for point in body['points']}
    assert set(points[102]) == {'id', 'name', 'before', 'after'} and points[102]['name'] == '有理数乘方'
    assert points[102]['before']['status'] != 'mastered' and points[102]['after'] == {'value': 1.0,
                                                                                      'status': 'mastered'}
    assert 101 in points and points[101]['before']['value'] < points[101]['after']['value']
    assert body['graduated'] == [2] and body['newly_mastered'] == 1
    # 原样再提交：没有变化
    again = submit(db, 11, [(1, True), (3, True)], revision=1)
    assert again['points'] == [] and again['graduated'] == [] and again['newly_mastered'] == 0


def test_grading_query_count_is_fixed():
    """3 道题和 30 道题的卷子，批改执行的 SQL 条数相同。"""
    import motivation

    def count(total):
        """建 total 道题的考点卷，批改一次，返回读库条数。"""
        c = build_db()
        for qid in range(1, total + 1):
            starmap_test.add_question(c, qid, 1, '2026-09-01 08:00:00', [(101, 102, 111)[qid % 3]])
        add_set(c, 10, '2026-11-01 08:00:00', None, [(qid, None, 'original') for qid in range(1, total + 1)])
        c.commit()
        counter = starmap_test.CountingDB(c)
        starmap_test.run(mark(counter, 10, [(qid, qid % 2 == 0) for qid in range(1, total + 1)], revision=0))
        return counter.calls

    saved = motivation.trigger

    async def fake_trigger(db, code, reason=None):
        pass
    motivation.trigger = fake_trigger
    try:
        small, big = count(3), count(30)
    finally:
        motivation.trigger = saved
    assert small == big, (small, big)


@with_motivation
def test_grading_reading_and_word_sets_unchanged(calls):
    """阅读练习的批改照旧按次数加一，返回里没有 points，版本号不动。"""
    import practices
    c, db = grading_fixture()
    c.execute("INSERT INTO reading_passage(id,title,content,topic,grade,difficulty,deleted) "
              "VALUES(1,'短文','内容','主题',6,2,0)")
    for number in (1, 2):
        c.execute("INSERT INTO reading_question(id,passage_id,question_number,question_text,option_a,option_b,"
                  "option_c,option_d,correct_answer,deleted) VALUES(?,1,?,'问','A','B','C','D','A',0)",
                  (number, number))
    c.execute("INSERT INTO practice_set(id,name,subject_id,source_type,question_type,passage_id,total_questions,"
              "reviewed,review_count,deleted,created_at) VALUES(20,'阅读',2,'reading','original',1,2,0,0,0,"
              "'2026-11-01 08:00:00')")
    c.commit()
    payload = {'question_results': [{'question_id': 1, 'is_correct': True}, {'question_id': 2, 'is_correct': False}]}
    for expected in (1, 2):
        body = starmap_test.run(practices.reviewed(20, grade_request(db, payload)))
        assert body['review_count'] == expected and body['accuracy'] == 50.0
        assert 'points' not in body and 'grading_revision' not in body
    assert db_value(c, 'SELECT review_count FROM practice_set WHERE id=20') == 2
    assert db_value(c, 'SELECT grading_revision FROM practice_set WHERE id=20') == 0
    assert calls['trigger'] == 2


# ---------------------------------------------------------------- 任务 7：考点卷的 PDF 版式


def paper_detail():
    """考点卷详情：两个模块共 3 道题，第 2 道是相似题；#7。"""
    def point(pid, parent_id, parent, name):
        return [{'id': pid, 'parent_id': parent_id, 'parent_name': parent, 'name': name, 'is_primary': 1}]
    base = {'difficulty': 2, 'error_type': None, 'option_a': None, 'option_b': None, 'option_c': None,
            'option_d': None, 'is_reading_question': False, 'topic': None}
    return {'id': 7, 'name': '考点卷7', 'kind': 'targeted', 'passage': None, 'questions': [
        {**base, 'id': 1, 'question_id': 1, 'number': 1, 'form': 'original', 'reason': 'new',
         'question_text': '原题一', 'answer': '答案一', 'analysis': '原题的解析', 'explanation': None,
         'knowledge_points': point(101, 100, '有理数', '加法')},
        {**base, 'id': 2, 'question_id': 2, 'number': 2, 'form': 'similar', 'reason': 'wrong',
         'question_text': '相似题干', 'answer': 'x' * 50, 'analysis': '被忽略的原题解析', 'explanation': '相似题的解析',
         'knowledge_points': point(102, 100, '有理数', '乘方')},
        {**base, 'id': 3, 'question_id': 3, 'number': 3, 'form': 'original', 'reason': 'spot',
         'question_text': '原题三', 'answer': '答案三', 'analysis': None, 'explanation': None,
         'option_a': '甲', 'option_b': '乙',
         'knowledge_points': point(201, 200, '线段与角', '线段')},
    ]}


def test_build_payload_targeted():
    """考点卷：按一级模块分组、题号连续，答案页带原因和题面；相似题用相似题的解析。"""
    import pdf
    payload = pdf.build_payload(paper_detail())
    assert payload['template_version'] == '4' and payload['layout'] == 'targeted' and payload['code'] == '#7'
    assert payload['title'] == '考点卷7'
    assert [g['title'] for g in payload['groups']] == ['一、有理数（2 题）', '二、线段与角（1 题）']
    assert [q['number'] for g in payload['groups'] for q in g['questions']] == [1, 2, 3]
    second = payload['answers'][1]
    assert second['form'] == '相似题' and second['analysis'] == '相似题的解析' and second['reason'] == '上次做错'
    assert payload['answers'][0]['analysis'] == '原题的解析' and payload['answers'][0]['form'] == '原题'
    assert payload['answers'][0]['point'] == '有理数 / 加法' and payload['answers'][0]['reason'] == '新错题'
    assert payload['answers'][2]['reason'] == '抽查'
    assert payload['footer'] == '手机上从首页的"专项练习"进待批改，找到 #7'
    assert payload['groups'][1]['questions'][0]['option_a'] == '甲'


def test_build_payload_groups_by_picked_point():
    """主考点在模块 A、出卷时挑的考点在模块 B：分组和答案页的考点都跟着挑的考点走。"""
    import pdf
    detail = paper_detail()
    other = {'id': 301, 'parent_id': 300, 'parent_name': '整式', 'name': '合并同类项', 'is_primary': 0}
    # 第 2 题主考点仍是有理数 / 乘方，但这次是为"整式 / 合并同类项"挑的
    detail['questions'][1]['knowledge_points'].append(other)
    detail['questions'][1]['knowledge_point_id'] = 301
    payload = pdf.build_payload(detail)
    assert [g['title'] for g in payload['groups']] == ['一、有理数（1 题）', '二、整式（1 题）', '三、线段与角（1 题）']
    assert payload['groups'][1]['questions'][0]['number'] == 2
    assert payload['answers'][1]['point'] == '整式 / 合并同类项'
    # 列为空或找不到时退回主考点
    for value in (None, 999):
        detail['questions'][1]['knowledge_point_id'] = value
        assert pdf.build_payload(detail)['answers'][1]['point'] == '有理数 / 乘方'


def test_build_payload_reason_labels():
    """六种入选原因的中文名。"""
    import pdf
    assert pdf.REASON_LABELS == {'new': '新错题', 'wrong': '上次做错', 'redo': '旧错题重做',
                                 'consolidate': '巩固', 'check': '验收', 'spot': '抽查'}


def test_build_payload_space_sizes():
    """留白：有选项 s；答案 10 字 s、50 字 m、200 字 l。"""
    import pdf
    detail = paper_detail()
    for question, text in zip(detail['questions'], ['y' * 10, 'y' * 50, 'y' * 200]):
        question['answer'] = text
        question['option_a'] = question['option_b'] = None
    spaces = [q['space'] for g in pdf.build_payload(detail)['groups'] for q in g['questions']]
    assert spaces == ['s', 'm', 'l']
    detail['questions'][2]['option_a'] = '甲'
    assert pdf.build_payload(detail)['groups'][1]['questions'][0]['space'] == 's'


OLD_DETAIL = {'id': 5, 'name': '旧练习', 'kind': 'manual', 'pdf_path': None, 'passage': None, 'questions': [
    {'id': 11, 'question_id': 21, 'question_text': r'算 \(1+1\)', 'difficulty': 2, 'error_type': '计算',
     'option_a': None, 'option_b': None, 'option_c': None, 'option_d': None, 'is_reading_question': False,
     'topic': None,
     'knowledge_points': [{'id': 102, 'parent_id': 100, 'parent_name': '有理数', 'name': '乘方', 'is_primary': 0},
                          {'id': 101, 'parent_id': 100, 'parent_name': '有理数', 'name': '加法', 'is_primary': 1}]},
    {'id': 12, 'question_id': 22, 'question_text': '选哪个', 'difficulty': 1, 'error_type': None,
     'option_a': '甲', 'option_b': '乙', 'option_c': '丙', 'option_d': '丁', 'is_reading_question': False,
     'topic': 't', 'knowledge_points': []}]}

# 改动前 generate_practice 对 OLD_DETAIL 发给渲染器的内容（逐字节捕获），指纹不能变
EXPECTED_OLD_PAYLOAD = json.loads(
    '{"passage": null, "questions": [{"difficulty": 2, "error_type": "\\u8ba1\\u7b97", "id": 21, '
    '"is_reading_question": false, "knowledge_path": [{"id": 101, "is_primary": true, "name": "\\u52a0\\u6cd5", '
    '"parent_id": 100, "parent_name": "\\u6709\\u7406\\u6570"}, {"id": 102, "is_primary": false, '
    '"name": "\\u4e58\\u65b9", "parent_id": 100, "parent_name": "\\u6709\\u7406\\u6570"}], '
    '"knowledge_point": "\\u6709\\u7406\\u6570/\\u52a0\\u6cd5\\uff08\\u4e3b\\u8003\\u70b9\\uff09", '
    '"option_a": null, "option_b": null, "option_c": null, "option_d": null, '
    '"question_text": "\\u7b97 \\\\(1+1\\\\)", "topic": null}, '
    '{"difficulty": 1, "error_type": null, "id": 22, "is_reading_question": false, "knowledge_path": [], '
    '"knowledge_point": null, "option_a": "\\u7532", "option_b": "\\u4e59", "option_c": "\\u4e19", '
    '"option_d": "\\u4e01", "question_text": "\\u9009\\u54ea\\u4e2a", "topic": "t"}], '
    '"template_version": "2", "title": "\\u65e7\\u7ec3\\u4e60"}')


def test_build_payload_manual_unchanged():
    """非考点卷：内容和改动前 generate_practice 发出的逐字段相同，指纹不变。"""
    import hashlib
    import pdf
    payload = pdf.build_payload(OLD_DETAIL)
    assert payload == EXPECTED_OLD_PAYLOAD
    digest = lambda value: hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
    assert digest(payload) == digest(EXPECTED_OLD_PAYLOAD)
    no_kind = {key: value for key, value in OLD_DETAIL.items() if key != 'kind'}
    assert pdf.build_payload(no_kind) == EXPECTED_OLD_PAYLOAD


def test_local_generate_practice_writes_layout_json():
    """本机替身：把版式数据写成 uploads/practice_sets/<编号>.json 并更新 pdf_path。"""
    import tempfile
    import local_dev_server
    c = build_db()
    starmap_test.add_question(c, 1, 1, '2026-09-01 08:00:00', [101])
    add_set(c, 7, '2026-11-01 08:00:00', None, [(1, None, 'original')])
    c.commit()
    uploads = pathlib.Path(tempfile.mkdtemp(prefix='easyfix_pdf_'))
    generate = local_dev_server.make_local_generate_practice(uploads)
    result = starmap_test.run(generate(7, request_for(starmap_test.adapter(c))))
    assert result == {'pdf_url': '/uploads/practice_sets/7.json'}
    saved = json.loads((uploads / 'practice_sets' / '7.json').read_text(encoding='utf-8'))
    assert saved['layout'] == 'targeted' and saved['code'] == '#7'
    assert c.execute('SELECT pdf_path FROM practice_set WHERE id=7').fetchone()[0] == 'practice_sets/7.json'


# ---------------------------------------------------------------- 整体评审后的修复


def unprepared_paper():
    """paper_fixture 上按 plan 建一份考点卷：错题 3 是相似题、还没准备。返回 (连接, db, 卷子, 相似题那一行的编号)。"""
    c, db = paper_fixture()
    paper = create_paper(db, create_items(plan_body(db, size=3, spot_count=0)))
    item_id = c.execute("SELECT id FROM practice_set_question WHERE practice_set_id=? AND form='similar'",
                        (paper['id'],)).fetchone()[0]
    return c, db, paper, item_id


@with_fakes
def test_pdf_refuses_unprepared_targeted(calls):
    """考点卷还有没准备好的相似题：生成 PDF 返回 409（线上和本机替身都一样）；准备完后可以生成。"""
    import tempfile
    from fastapi import HTTPException
    import local_dev_server
    import pdf
    import targeted
    c, db, paper, item_id = unprepared_paper()
    pdf.Database = lambda binding: binding
    request = request_for(db)
    try:
        starmap_test.run(pdf.generate_practice(paper['id'], request))
        raise AssertionError('没有抛出 409')
    except HTTPException as error:
        assert error.status_code == 409 and error.detail == '还有 1 道相似题没准备好，请先在出卷页准备完'
    generate = local_dev_server.make_local_generate_practice(pathlib.Path(tempfile.mkdtemp(prefix='easyfix_pdf_')))
    starmap_test.expect_http_error(409, generate(paper['id'], request))
    assert c.execute('SELECT pdf_path FROM practice_set WHERE id=?', (paper['id'],)).fetchone()[0] is None
    starmap_test.run(targeted.prepare(paper['id'], request_for(db, {})))
    assert starmap_test.run(generate(paper['id'], request))['pdf_url'].endswith('.json')


def test_pdf_check_is_one_query():
    """考点卷的"相似题是否准备完"检查只多一条 SQL，和题数无关；别的卷子不查。"""
    import pdf
    c, db, paper, item_id = unprepared_paper()
    counter = starmap_test.CountingDB(c)
    starmap_test.expect_http_error(409, pdf.ensure_printable(counter, {'id': paper['id'], 'kind': 'targeted'}))
    assert counter.calls == 1
    starmap_test.run(pdf.ensure_printable(counter, {'id': paper['id'], 'kind': 'manual'}))
    assert counter.calls == 1


class RaceDB(starmap_test.SQLiteDB):
    """在执行某条 UPDATE 之前先跑一段"另一个页面"的写入，模拟两个页面同时准备同一道题。"""

    def __init__(self, connection, marker, before):
        super().__init__(connection)
        self.marker, self.before = marker, before

    async def run(self, sql, parameters=()):
        """碰到含 marker 的 SQL 时，先执行一次 before。"""
        if self.marker in sql and self.before is not None:
            self.before()
            self.before = None
        return await super().run(sql, parameters)


def add_other_similar(c):
    """给错题 3 加一道"另一个页面生成的"相似题（编号 50）。"""
    c.execute("INSERT INTO similar_question(id,source_question_id,similar_text,similar_answer,explanation,deleted,"
              "generated_at) VALUES(50,3,'别处的相似题','答','解析',0,'2026-11-01')")
    c.commit()


@with_fakes
def test_prepare_does_not_overwrite_concurrent_prepare(calls):
    """另一个页面先把这道题准备好了：这边的写入不覆盖它，remaining 按库里重新算。"""
    import targeted
    c, db, paper, item_id = unprepared_paper()

    def other_tab():
        """另一个页面抢先生成并写入（在这边查过可复用的相似题之后）。"""
        add_other_similar(c)
        c.execute('UPDATE practice_set_question SET similar_question_id=50 WHERE id=?', (item_id,))
    race = RaceDB(c, 'SET similar_question_id=?', other_tab)
    body = starmap_test.run(targeted.prepare(paper['id'], request_for(race, {})))
    assert body['remaining'] == 0 and body['item_id'] == item_id
    assert c.execute('SELECT similar_question_id FROM practice_set_question WHERE id=?', (item_id,)).fetchone()[0] == 50


@with_fakes
def test_fallback_does_not_overwrite_concurrent_prepare(calls):
    """另一个页面已经给这道题配好了相似题：这边的"改成原题"不生效，题面仍是相似题。"""
    import targeted
    c, db, paper, item_id = unprepared_paper()
    add_other_similar(c)

    def other_tab():
        """另一个页面抢先写入。"""
        c.execute('UPDATE practice_set_question SET similar_question_id=50 WHERE id=?', (item_id,))
    race = RaceDB(c, "SET form='original'", other_tab)
    body = starmap_test.run(targeted.prepare(paper['id'], request_for(race, {'fallback': True})))
    assert body['remaining'] == 0
    row = c.execute('SELECT form,similar_question_id FROM practice_set_question WHERE id=?', (item_id,)).fetchone()
    assert (row[0], row[1]) == ('similar', 50)


def test_targeted_numbers_stable_after_question_deleted():
    """考点卷里一道错题被删除后，其余题的题号不变（按出卷顺序）；旧练习集仍按剩下的题连续编号。"""
    import practices
    c, db = grading_fixture()
    add_set(c, 12, '2026-11-01 08:00:00', None, [(1, None, 'original'), (2, None, 'original'),
                                                 (3, None, 'original')], kind='manual')
    c.execute('UPDATE question SET deleted=1 WHERE id=2')
    c.commit()
    detail = starmap_test.run(practices.get(db, 10))
    assert [(q['question_id'], q['number']) for q in detail['questions']] == [(1, 1), (3, 3)]
    legacy = starmap_test.run(practices.get(db, 12))
    assert [(q['question_id'], q['number']) for q in legacy['questions']] == [(1, 1), (3, 2)]


@with_motivation
def test_graduated_numbers_follow_paper_numbers(calls):
    """删掉第 1 题后批改：刚毕业的题报的仍是卷面上的题号。"""
    c, db = grading_fixture()
    add_set(c, 1, '2026-09-10 08:00:00', '2026-09-10 20:00:00', [(3, 1, 'original')])
    c.execute('UPDATE question SET deleted=1 WHERE id=1')
    c.commit()
    body = submit(db, 10, [(2, False), (3, True)], revision=0)
    assert body['graduated'] == [3]


@with_fakes
def test_bad_question_similar_never_reused(calls):
    """相似题被标"题目有误"：卷子删掉以后也不再复用；卷面仍显示这道相似题；没被标的相似题照常复用。"""
    import motivation
    import practices
    import similar
    import targeted
    c, db, paper, item_id = unprepared_paper()
    starmap_test.run(targeted.prepare(paper['id'], request_for(db, {})))
    similar_id = c.execute('SELECT similar_question_id FROM practice_set_question WHERE id=?', (item_id,)).fetchone()[0]
    payload = {'question_results': [{'question_id': 3, 'skip_reason': 'bad_question'}], 'grading_revision': 0}
    saved = motivation.trigger

    async def fake_trigger(db, code, reason=None):
        pass
    motivation.trigger = fake_trigger
    try:
        starmap_test.run(practices.reviewed(paper['id'], grade_request(db, payload)))
    finally:
        motivation.trigger = saved
    # 批改后卷子上仍显示这道相似题（以后改批改时不会变成原题）
    detail = starmap_test.run(practices.get(db, paper['id']))
    assert [q['question_text'] for q in detail['questions'] if q['form'] == 'similar'] == ['相似题目']
    c.execute('UPDATE practice_set SET deleted=1 WHERE id=?', (paper['id'],))
    c.commit()
    assert starmap_test.run(similar.reusable_similar(db, 3)) is None
    # 对照：同一道错题另一道没被标的相似题照常复用
    c.execute("INSERT INTO similar_question(id,source_question_id,similar_text,similar_answer,explanation,deleted,"
              "generated_at) VALUES(?,3,'另一道','答','解析',0,'2026-11-01')", (similar_id + 100,))
    assert starmap_test.run(similar.reusable_similar(db, 3))['id'] == similar_id + 100


def test_build_payload_groups_by_module_id():
    """两个同名但不同的一级模块：PDF 分成两组，组标题都用模块名。"""
    import pdf
    detail = paper_detail()
    detail['questions'][2]['knowledge_points'] = [
        {'id': 202, 'parent_id': 200, 'parent_name': '有理数', 'name': '其他', 'is_primary': 1}]
    payload = pdf.build_payload(detail)
    assert [g['title'] for g in payload['groups']] == ['一、有理数（2 题）', '二、有理数（1 题）']


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
    test_targeted_prompt_content,
    test_prepare_prompt_ignores_wrong_answer,
    test_create_similar_stores_explanation,
    test_create_similar_rejects_empty,
    test_reusable_similar_rules,
    test_plan_endpoint_shape_and_reasons,
    test_plan_validations,
    test_create_then_prepare_until_done,
    test_plan_excludes_blocked_and_old_open_papers,
    test_plan_lower_grades_switch,
    test_plan_without_default_grade,
    test_plan_and_create_with_nothing_to_pick,
    test_plan_query_count_is_fixed,
    test_create_validations,
    test_create_orders_by_module_and_point,
    test_prepare_reuses_unused_similar,
    test_prepare_failure_keeps_item_pending_then_fallback,
    test_reroll_replaces_similar,
    test_prepare_and_reroll_reject_closed_paper,
    test_status_endpoint,
    test_get_keeps_old_sets_working,
    test_grading_is_idempotent_and_counts_delta,
    test_grading_stale_revision_conflicts,
    test_grading_guard_blocks_concurrent_submit,
    test_grading_skip_reasons,
    test_grading_skip_then_correct,
    test_grading_without_revision_still_works,
    test_grading_partial_payload_keeps_others,
    test_grading_rejects_foreign_item,
    test_grading_motivation_only_first_time,
    test_grading_reports_changes,
    test_grading_query_count_is_fixed,
    test_grading_reading_and_word_sets_unchanged,
    test_build_payload_targeted,
    test_build_payload_groups_by_picked_point,
    test_build_payload_reason_labels,
    test_build_payload_space_sizes,
    test_build_payload_manual_unchanged,
    test_local_generate_practice_writes_layout_json,
    test_pdf_refuses_unprepared_targeted,
    test_pdf_check_is_one_query,
    test_prepare_does_not_overwrite_concurrent_prepare,
    test_fallback_does_not_overwrite_concurrent_prepare,
    test_targeted_numbers_stable_after_question_deleted,
    test_graduated_numbers_follow_paper_numbers,
    test_bad_question_similar_never_reused,
    test_build_payload_groups_by_module_id,
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
