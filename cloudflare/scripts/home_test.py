"""首页接口（/api/home）和单词学情接口（/api/stats/words）的本地测试。

建库、造数据的助手都复用 weekly_report_test。运行：

    python cloudflare/scripts/home_test.py
"""

import pathlib
import sys
from datetime import datetime

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
sys.path.insert(0, str(ROOT / 'scripts'))

import starmap_test  # noqa: E402  复用输出与检查助手
import targeted_test  # noqa: E402
import weekly_report_test as weekly_test  # noqa: E402
from home_model import current_week_end, sky_counts, streak_days, top_names, week_days  # noqa: E402

run = starmap_test.run
MOMENT = datetime(2026, 11, 21, 10, 0)      # 周六上午：本周是 11-16 到 11-22（周日 20:00 结束）


def home_of(db, moment=MOMENT):
    """用 db 算首页数据；让 home、targeted 直接使用传入的 db。"""
    import home
    request = targeted_test.request_for(db)
    return run(home.build_home(db, request, moment))


# ---------------------------------------------------------------- 纯函数


def test_current_week_end_rolls_at_sunday_20():
    """周日 19:59 仍是当天 20:00 结束的这一周；周日 20:00 起算下周日 20:00。"""
    assert current_week_end(datetime(2026, 11, 22, 19, 59)) == datetime(2026, 11, 22, 20, 0)
    assert current_week_end(datetime(2026, 11, 22, 20, 0)) == datetime(2026, 11, 29, 20, 0)
    assert current_week_end(datetime(2026, 11, 21, 10, 0)) == datetime(2026, 11, 22, 20, 0)


def test_streak_days():
    """今天、昨天有、前天没有是 2；今天没有从昨天数；都没有是 0。"""
    assert streak_days({'2026-11-21', '2026-11-20', '2026-11-18'}, '2026-11-21') == 2
    assert streak_days({'2026-11-20', '2026-11-19', '2026-11-18'}, '2026-11-21') == 3
    assert streak_days({'2026-11-19'}, '2026-11-21') == 0
    assert streak_days(set(), '2026-11-21') == 0


def test_week_days():
    """7 项，周一在前，active 按集合。"""
    days = week_days('2026-11-16', {'2026-11-16', '2026-11-22'})
    assert len(days) == 7 and days[0] == {'date': '2026-11-16', 'active': True}
    assert days[6] == {'date': '2026-11-22', 'active': True}
    assert [d['active'] for d in days] == [True, False, False, False, False, False, True]


def test_sky_counts_and_top_names():
    """合并两科，fair+good 算中间，unlearned 不计；top_names 取前三个名字。"""
    one = {'unlearned': 5, 'weak': 1, 'fair': 2, 'good': 1, 'mastered': 3}
    two = {'unlearned': 9, 'weak': 2, 'fair': 0, 'good': 4, 'mastered': 0}
    assert sky_counts([one, two]) == {'weak': 3, 'middle': 7, 'lit': 3}
    assert sky_counts([]) == {'weak': 0, 'middle': 0, 'lit': 0}
    items = [{'id': i, 'name': 'n%d' % i} for i in range(5)]
    assert top_names(items) == ['n0', 'n1', 'n2'] and top_names(items[:1], 3) == ['n0']


# ---------------------------------------------------------------- 接口


def test_home_week_matches_weekly_facts():
    """同一个 week_end 下，首页本周的录入、批改、默写天数和周报 facts 相等。"""
    c = weekly_test.build_db()
    starmap_test.add_question(c, 1, 1, '2026-11-17 10:00:00.000000', [101])
    starmap_test.add_question(c, 2, 1, '2026-11-18 10:00:00.000000', [101])
    starmap_test.add_question(c, 3, 1, '2026-11-10 10:00:00.000000', [102])         # 上周：不算
    weekly_test.add_set(c, 1, '2026-11-17 10:00:00', '2026-11-18 10:00:00',
                        [(1, True, 'original'), (2, False, 'original')])
    for day in ('2026-11-17', '2026-11-19', '2026-11-20'):
        weekly_test.add_dictation(c, 1, day + ' 19:00:00', 1)
    weekly_test.add_dictation(c, 1, '2026-11-18 19:00:00', 1, review_type=2)        # 不是默写：不算
    c.commit()
    db = starmap_test.adapter(c)
    home = home_of(db)
    facts = weekly_test.facts_of(db)
    assert home['week']['entries'] == facts['entries']['count'] == 2
    assert home['week']['papers'] == facts['practice']['papers'] == 1
    assert home['week']['dictation_days'] == facts['dictation']['days'] == 3
    assert home['week']['monday'] == '2026-11-16' and home['week']['sunday'] == '2026-11-22'
    assert [d['active'] for d in home['week']['days']] == [False, True, False, True, True, False, False]
    assert home['streak_days'] == 2     # 今天（11-21）没默写，从昨天数：11-20、11-19 连续，11-18 断
    assert set(home) == {'review', 'grading', 'targeted', 'words', 'flip', 'streak_days', 'week', 'sky'}


def test_home_streak_counts_from_yesterday():
    """今天没默写、昨天和前天有：连续 2 天。"""
    c = weekly_test.build_db()
    for day in ('2026-11-19', '2026-11-20'):
        weekly_test.add_dictation(c, 1, day + ' 19:00:00', 1)
    c.commit()
    assert home_of(starmap_test.adapter(c))['streak_days'] == 2


def test_home_review_targeted_words_and_sky():
    """待核对数和最新卷子、考点卷创建时间、到期单词数、星空三档。"""
    c = weekly_test.build_db()
    starmap_test.add_paper(c, 7, 1, '2026-11-10')
    starmap_test.add_paper(c, 8, 1, '2026-11-15')
    starmap_test.add_question(c, 1, 1, '2026-11-17 10:00:00.000000', [101], status='pending', paper_id=7)
    starmap_test.add_question(c, 2, 1, '2026-11-17 10:00:00.000000', [101], status='pending', paper_id=8)
    starmap_test.add_question(c, 3, 1, '2026-11-17 10:00:00.000000', [101], status='pending', deleted=1)
    weekly_test.add_set(c, 1, '2026-11-19 19:00:00', None, [(1, None, 'original')])
    weekly_test.add_set(c, 2, '2026-11-20 19:00:00', None, [(2, None, 'original')])
    weekly_test.add_set(c, 3, '2026-11-21 19:00:00', None, [(2, None, 'original')], deleted=1)
    for word_id, due in ((1, '2026-11-21 09:59:59'), (2, '2026-11-21 10:00:01'), (3, None)):
        weekly_test.add_dictation(c, word_id, '2026-10-01 10:00:00', 1)
        c.execute('UPDATE word SET next_review_at=? WHERE id=?', (due, word_id))
    c.commit()
    home = home_of(starmap_test.adapter(c))
    assert home['review'] == {'count': 2, 'latest_paper': {'id': 8, 'name': '卷子8'}}
    assert home['targeted'] == {'last_created_at': '2026-11-20 19:00:00'}
    assert home['words'] == {'due': 1}
    assert set(home['sky']) == {'weak', 'middle', 'lit'}
    assert home['review']['count'] == 2 and home['grading']['count'] == 2


def test_home_empty_database():
    """什么数据都没有：各项为 0 或 null，不报错。"""
    home = home_of(starmap_test.adapter(weekly_test.build_db()))
    assert home['review'] == {'count': 0, 'latest_paper': None}
    assert home['grading'] == {'count': 0, 'oldest': None}
    assert home['targeted'] == {'last_created_at': None}
    assert home['words'] == {'due': 0} and home['streak_days'] == 0
    assert home['week']['improved'] == [] and home['week']['dropped'] == []


def test_grading_pending_not_limited_to_30_days():
    """40 天前的未批改错题练习卷也计入待批改，oldest 是它；targeted/status 的 pending_count 一致。"""
    import targeted
    from analytics import now
    c = weekly_test.build_db()
    starmap_test.add_question(c, 1, 1, '2026-09-01 08:00:00', [101])
    old = targeted_test.days_ago(40)
    targeted_test.add_set(c, 80, old, None, [(1, None, 'original')])
    targeted_test.add_set(c, 81, targeted_test.days_ago(2), None, [(1, None, 'original')])
    targeted_test.add_set(c, 82, targeted_test.days_ago(50), targeted_test.days_ago(49), [(1, True, 'original')])
    c.commit()
    db = starmap_test.adapter(c)
    home = home_of(db, now())
    assert home['grading'] == {'count': 2, 'oldest': {'id': 80, 'name': '考点卷80', 'created_at': old}}
    status = run(targeted.status(targeted_test.request_for(db)))
    assert status['pending_count'] == 2


def test_home_flip_empty_database():
    """没有错题、没有翻牌：flip 是 {total: 0, done: 0}，week.flip_days 为 0。"""
    home = home_of(starmap_test.adapter(weekly_test.build_db()))
    assert home['flip'] == {'total': 0, 'done': 0} and home['week']['flip_days'] == 0


def test_home_flip_progress_and_days():
    """flip 是今天的进度（和 /api/flip/today 同一套选题）；week.flip_days 和周报 facts 的翻牌天数相同。"""
    import flip
    c = weekly_test.build_db()
    for qid in range(1, 6):
        starmap_test.add_question(c, qid, 1, '2026-11-01 10:00:00.000000', [101])
    weekly_test.add_flip(c, 1, '2026-11-15 19:00:00.000000')        # 上一期：不算
    weekly_test.add_flip(c, 2, '2026-11-15 21:00:00.000000')        # 上周日 20:00 之后：算本期（和周报同一个窗口）
    weekly_test.add_flip(c, 3, '2026-11-18 19:00:00.000000', result='forget')
    weekly_test.add_flip(c, 4, '2026-11-21 08:00:00.000000')        # 今天已经翻了 1 张
    c.commit()
    db = starmap_test.adapter(c)
    home = home_of(db)
    progress = run(flip.today_progress(db, 1, '2026-11-21'))
    assert home['flip'] == progress, (home['flip'], progress)
    assert home['flip'] == {'total': 5, 'done': 1}      # 今天翻过的题 4 + 还没翻的 1、2、3（都到期了）、5
    facts = weekly_test.facts_of(db)
    assert home['week']['flip_days'] == facts['flip']['days'] == 3
    assert [d['active'] for d in home['week']['days']] == [False, False, True, False, False, True, False]


def test_home_streak_counts_flip_days():
    """连续天数和七天打卡条：默写或翻一翻都算有学习记录；只录入错题不算。"""
    c = weekly_test.build_db()
    weekly_test.add_dictation(c, 1, '2026-11-18 19:00:00', 1)
    weekly_test.add_flip(c, 1, '2026-11-19 19:00:00.000000')
    weekly_test.add_dictation(c, 1, '2026-11-20 19:00:00', 1)
    weekly_test.add_flip(c, 2, '2026-11-20 19:30:00.000000')
    weekly_test.add_flip(c, 3, '2026-11-21 09:00:00.000000')
    weekly_test.add_flip(c, 4, '2026-11-16 09:00:00.000000', deleted=1)     # 删除的不算
    starmap_test.add_question(c, 9, 1, '2026-11-17 10:00:00.000000', [101])  # 录入不算打卡
    c.commit()
    home = home_of(starmap_test.adapter(c))
    assert home['streak_days'] == 4                                     # 11-18 默写、11-19 翻、11-20、11-21 翻
    assert [d['active'] for d in home['week']['days']] == [False, False, True, True, True, True, False]
    assert home['week']['flip_days'] == 3 and home['week']['dictation_days'] == 2


def test_stats_words_returns_low_accuracy_and_frequency():
    """正确率低于 70% 的词和每天复习次数。"""
    import analytics
    c = weekly_test.build_db()
    weekly_test.add_dictation(c, 1, '2026-11-19 10:00:00', 0)
    weekly_test.add_dictation(c, 1, '2026-11-19 11:00:00', 1)
    weekly_test.add_dictation(c, 2, '2026-11-20 10:00:00', 1)
    c.execute('UPDATE word SET review_count=2, correct_count=1 WHERE id=1')
    c.execute('UPDATE word SET review_count=1, correct_count=1 WHERE id=2')
    c.commit()
    analytics.Database = lambda binding: binding
    body = run(analytics.words(targeted_test.request_for(starmap_test.adapter(c))))
    assert body == {'low_accuracy_words': [{'word': 'word1', 'accuracy': 50.0}],
                    'frequency': [{'date': '2026-11-19', 'count': 2}, {'date': '2026-11-20', 'count': 1}]}, body


TESTS = [
    test_current_week_end_rolls_at_sunday_20,
    test_streak_days,
    test_week_days,
    test_sky_counts_and_top_names,
    test_home_week_matches_weekly_facts,
    test_home_streak_counts_from_yesterday,
    test_home_review_targeted_words_and_sky,
    test_home_empty_database,
    test_grading_pending_not_limited_to_30_days,
    test_home_flip_empty_database,
    test_home_flip_progress_and_days,
    test_home_streak_counts_flip_days,
    test_stats_words_returns_low_accuracy_and_frequency,
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
