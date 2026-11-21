"""接口清单测试：钉住"哪些接口必须已经删掉、哪些必须还在"。

项目 5 第 1 步清理没人用的接口时，用它判断"删对了、没多删"。
大多数路由模块依赖只在 Cloudflare 上才有的包，本机导不进来，
所以这里主要读源码文本判断；只有 catalog 能导入，单独检查它注册的路由。
运行：

    python cloudflare/scripts/dead_routes_test.py
"""

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC = ROOT / 'src'
sys.path.insert(0, str(SRC))

RESULTS = []

# 必须已经不存在：(文件, 源码里不应再出现的片段)
REMOVED = [
    ('analytics.py', "@router.get('/today')"),
    ('reports.py', "@router.post('/generate')"),
    ('auth.py', "'/api/auth/session'"),
    ('motivation.py', "'/motivation/trigger/{action_code}'"),
    ('practices.py', "'/generate-from-questions'"),
    ('questions.py', "'/api/questions/batch'"),
    ('questions.py', "'/api/questions/debug/{question_id}'"),
    ('readings.py', "@router.post('', status_code=201)"),
    ('readings.py', "@router.put('/{reading_id}')"),
    ('scan.py', "/items/{seq}/restore'"),
    ('words.py', "@router.get('/errors')"),
    ('knowledge.py', "@router.get('/api/knowledge-points/{item_id}')"),
    ('media.py', "'/api/upload/batch-simple'"),
    ('media.py', "'/api/upload/to-error-book/{error_book_id}'"),
    ('media.py', "'/api/rewards/{reward_id}/upload-image'"),
    ('media.py', "'/api/words/generate-audio'"),
    ('main.py', "@app.get('/api/subjects')"),
    ('main.py', "@app.post('/api/upload/file')"),
    ('main.py', "@app.get('/uploads/{key:path}')"),
    ('catalog.py', "'error-types'"),
    ('cache.py', "'/api/stats/today'"),
]

# 必须还在：(文件, 源码里必须出现的片段)
KEPT = [
    ('home.py', "@router.get('/api/home')"),
    ('analytics.py', "@router.get('/words')"),
    ('media.py', "@router.get('/api/words/{word_id}/audio')"),
    ('media.py', "@router.post('/api/words/print-pdf')"),
    ('reports.py', "@router.get('/list')"),
    ('reports.py', "@router.get('/{report_id}')"),
    ('reports.py', "@router.delete('/{report_id}')"),
    ('motivation.py', "/redeem'"),
    ('words.py', "@router.get('/{word_id}')"),
    ('scan.py', "/items/{seq}/dismiss'"),
    ('questions.py', "'/api/questions/filter-options/{subject_id}'"),
    ('main.py', "@app.get('/health')"),
    ('intake.py', "/guide'"),
    ('intake.py', "/papers/check'"),
]


def read_source(name):
    """返回 cloudflare/src/<name> 的全文。"""
    return (SRC / name).read_text(encoding='utf-8')


def check(name, function):
    """执行单个用例并记录结果。"""
    try:
        function()
        RESULTS.append((name, True, ''))
        print('PASS  ' + name)
    except Exception as error:  # noqa: BLE001
        RESULTS.append((name, False, str(error)))
        print('FAIL  ' + name + ': ' + str(error))


def make_removed_check(file_name, fragment):
    """生成一个断言"片段已从源码中消失"的用例函数。"""
    def run():
        assert fragment not in read_source(file_name), '仍然存在'
    return run


def make_kept_check(file_name, fragment):
    """生成一个断言"片段仍在源码中"的用例函数。"""
    def run():
        assert fragment in read_source(file_name), '找不到了'
    return run


def test_catalog_routes():
    """目录接口只剩该有的：没有错因、没有单条读取、学科和标签不能修改。"""
    import catalog
    routes = {(method, route.path) for route in catalog.router.routes for method in route.methods}
    kinds = ['subjects', 'tags', 'error-books', 'stars/actions', 'achievements', 'rewards']
    for kind in kinds:
        assert ('GET', '/api/' + kind) in routes, kind + ' 缺少列表'
        assert ('POST', '/api/' + kind) in routes, kind + ' 缺少新增'
        assert ('DELETE', '/api/' + kind + '/{item_id}') in routes, kind + ' 缺少删除'
        assert ('GET', '/api/' + kind + '/{item_id}') not in routes, kind + ' 仍有单条读取'
    for kind in ['error-books', 'stars/actions', 'achievements', 'rewards']:
        assert ('PUT', '/api/' + kind + '/{item_id}') in routes, kind + ' 缺少修改'
    for kind in ['subjects', 'tags']:
        assert ('PUT', '/api/' + kind + '/{item_id}') not in routes, kind + ' 仍可修改'
    assert not any('error-types' in path for _, path in routes), '仍有 error-types 路由'


def main():
    """逐条运行两张表和目录路由检查，有失败则以退出码 1 结束。"""
    for file_name, fragment in REMOVED:
        check('已删除 ' + file_name + ' ' + fragment, make_removed_check(file_name, fragment))
    for file_name, fragment in KEPT:
        check('仍保留 ' + file_name + ' ' + fragment, make_kept_check(file_name, fragment))
    check('目录路由只剩该有的', test_catalog_routes)
    failed = [item for item in RESULTS if not item[1]]
    print('\n合计 {} 项，通过 {} 项，失败 {} 项'.format(
        len(RESULTS), len(RESULTS) - len(failed), len(failed)))
    if failed:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
