"""考点卷上线前的只读核对。

对一份本机 SQLite 副本（正式 D1 导出后、已执行迁移 0015 的演练副本）打印四项结果：
  1. 旧规则是绿色、新规则不再是绿色的二级考点；
  2. 题干为空的错题数；
  3. 30 天以前创建、一直没批改的错题练习集数，和 30 天以内的数（另附 source_type 为空的卷子数）；
  4. 每科按题量 12、均布、抽查 1 时，第一份考点卷会选到的题。

只读：用 mode=ro 打开数据库，不连接正式环境。运行：

    python cloudflare/scripts/targeted_preflight.py --db <本机 SQLite 副本>
"""

import argparse
import asyncio
import datetime
import pathlib
import sqlite3
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
sys.path.insert(0, str(ROOT / 'scripts'))

import settings  # noqa: E402
import starmap  # noqa: E402
import targeted  # noqa: E402
from analytics import now  # noqa: E402
from knowledge_invariants_test import SQLiteDB  # noqa: E402  复用生产异步接口的 sqlite 适配器
from question_scope import counted, stem_ready  # noqa: E402
from targeted_model import OPEN_PAPER_DAYS, SIZE_DEFAULT, SPOT_DEFAULT  # noqa: E402

REASON_TEXT = {'new': '新错题', 'wrong': '上次做错', 'redo': '旧错题重做', 'consolidate': '巩固',
               'check': '验收', 'spot': '抽查'}

# 旧规则（上线前的 mastery_model）的常量：单独写在这里，不依赖已经改掉的代码
OLD_START, OLD_STEP, OLD_FLOOR, OLD_MAX, OLD_N = 0.5, 0.15, 0.15, 0.99, 3
OLD_ADJUST = {'up_small': 0.15, 'up_large': 0.35, 'down_small': -0.15, 'set_mastered': None}


def configure_output():
    """把标准输出改成 utf-8，避免 Windows GBK 控制台打印中文时报错。"""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding='utf-8', errors='replace')
        except (AttributeError, ValueError):
            pass


def old_leaf_value(events):
    """旧规则的底层考点掌握度：从 0.5 起按时间逐条加减；最近 3 次全对，或手动设为掌握，则为 1；之后再错往下扣。"""
    def clamp(value):
        """限制在 [0.15, 0.99]。"""
        return max(OLD_FLOOR, min(OLD_MAX, value))

    value, answers = OLD_START, []
    for event in sorted(events, key=lambda e: (str(e['at'] or ''), e['seq'])):
        if event['kind'] in ('wrong', 'right'):
            answers.append(event['kind'])
            value = clamp(value + (OLD_STEP if event['kind'] == 'right' else -OLD_STEP))
            if len(answers) >= OLD_N and all(kind == 'right' for kind in answers[-OLD_N:]):
                value = 1.0
        elif OLD_ADJUST.get(event['adjust'], 0) is None:
            value = 1.0
        else:
            value = clamp(value + OLD_ADJUST.get(event['adjust'], 0))
    return value


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


def open_readonly(path):
    """以只读方式打开 SQLite 副本。"""
    connection = sqlite3.connect('file:%s?mode=ro' % pathlib.Path(path).resolve().as_posix(), uri=True)
    connection.row_factory = sqlite3.Row
    return connection


async def turned_not_green(db, request, subjects, default_grade):
    """第 1 项：逐科找出旧规则绿色、新规则不再是绿色的二级考点。"""
    total = 0
    print('== 1. 旧规则是绿色、新规则不再是绿色的二级考点 ==')
    for subject in subjects:
        # 新规则：直接用分支上的 starmap.compute
        _, nodes, _, _, _ = await starmap.compute(db, request, subject['id'], default_grade)
        # 旧规则：用同一批事件，套上面单独写的旧公式
        events = await starmap.load_events(db, subject['id'], 1, default_grade)
        rows = []
        for node in nodes:
            if node['level'] != 2 or node['value'] is None:      # 没学的考点不算
                continue
            if old_leaf_value(events.get(node['id'], [])) == 1 and node['value'] < 1:
                rows.append(node)
        total += len(rows)
        print('[%s] %d 颗' % (subject['name'], len(rows)))
        for node in rows:
            print('  考点 %d %s：新掌握度 %.2f，待重做错题 %d 道'
                  % (node['id'], node['name'], node['value'], node['pending']))
    print('合计 %d 颗' % total)


async def scalar(db, sql, parameters=()):
    """取单个计数。"""
    return (await db.first(sql, parameters))['total']


async def count_data_issues(db):
    """第 2、3 项：题干为空的错题，以及没批改的错题练习集。"""
    print('\n== 2. 题干为空的错题（没删除、已核对） ==')
    print('%d 道' % await scalar(
        db, 'SELECT COUNT(*) AS total FROM question q WHERE %s AND NOT (%s)' % (counted('q'), stem_ready('q'))))

    cutoff = (now() - datetime.timedelta(days=OPEN_PAPER_DAYS)).isoformat(' ')[:19]
    base = "FROM practice_set WHERE deleted=0 AND source_type='question' AND COALESCE(reviewed,0)=0 "
    old = await scalar(db, 'SELECT COUNT(*) AS total ' + base + 'AND created_at<?', (cutoff,))
    recent = await scalar(db, 'SELECT COUNT(*) AS total ' + base + 'AND created_at>=?', (cutoff,))
    print('\n== 3. 一直没批改的错题练习集（分界 %s） ==' % cutoff)
    print('%d 天以前创建：%d 份（不再占题）' % (OPEN_PAPER_DAYS, old))
    print('%d 天以内创建：%d 份（仍占题）' % (OPEN_PAPER_DAYS, recent))
    null_type = await scalar(db, 'SELECT COUNT(*) AS total FROM practice_set WHERE deleted=0 AND source_type IS NULL')
    print('附：source_type 为空的卷子 %d 份（现在按错题练习集批改）' % null_type)


async def first_papers(request, subjects):
    """第 4 项：每科第一份考点卷（题量 12、均布、抽查 1）会选到的题，直接调用分支上的选题接口。"""
    print('\n== 4. 第一份考点卷会选到的题（题量 %d、均布、抽查 %d） ==' % (SIZE_DEFAULT, SPOT_DEFAULT))
    for subject in subjects:
        request.payload = {'subject_id': subject['id'], 'size': SIZE_DEFAULT, 'mode': 'spread',
                           'spot_count': SPOT_DEFAULT}
        result = await targeted.plan(request)
        print('[%s] 选中 %d 道，少出 %d 道' % (subject['name'], len(result['items']), result['shortfall']))
        for item in result['items']:
            print('  题 %d｜考点 %s｜%s｜%s' % (item['question_id'], item['point_name'],
                                          REASON_TEXT.get(item['reason'], item['reason']),
                                          '原题' if item['form'] == 'original' else '相似题'))


async def main(db_path):
    """核对主流程。"""
    connection = open_readonly(db_path)
    columns = {row[1] for row in connection.execute('PRAGMA table_info(practice_set)')}
    if 'kind' not in columns:
        sys.exit('这份副本还没有执行迁移 0015（practice_set 缺 kind 列），请先在演练副本上执行迁移再核对。')
    db = SQLiteDB(connection)
    # 让读取配置、算掌握度、选题的模块直接用这个本机连接
    for module in (settings, starmap, targeted):
        module.Database = lambda binding: binding
    request = FakeRequest({}, db)
    subjects = await db.all('SELECT id,name FROM subject WHERE deleted=0 ORDER BY id')
    default_grade = await starmap.load_default_grade(request)
    print('数据库：%s（只读）；默认年级：%s\n' % (db_path, default_grade if default_grade is not None else '未设置'))
    await turned_not_green(db, request, subjects, default_grade)
    await count_data_issues(db)
    await first_papers(request, subjects)


if __name__ == '__main__':
    configure_output()
    parser = argparse.ArgumentParser(description='考点卷上线前只读核对')
    parser.add_argument('--db', required=True, help='本机 SQLite 副本路径')
    asyncio.run(main(parser.parse_args().db))
