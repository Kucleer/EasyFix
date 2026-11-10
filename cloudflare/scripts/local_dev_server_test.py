"""本机测试环境 local_dev_server.py 的测试：用 TestClient 直接调用，不启动真正的服务。运行：

    python cloudflare/scripts/local_dev_server_test.py
"""

import pathlib
import re
import sys
import tempfile
import traceback
import uuid

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
sys.path.insert(0, str(ROOT / 'scripts'))

from fastapi.testclient import TestClient  # noqa: E402
import local_dev_server  # noqa: E402
from local_dev_server import build_app, build_connection  # noqa: E402

KEY_PATTERN = r'^\d{4}/\d{2}/[0-9a-f]{8}_[^/\\]+$'


def configure_output():
    """把标准输出改成 utf-8，避免 Windows GBK 控制台打印中文时报错。"""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding='utf-8', errors='replace')
        except (AttributeError, ValueError):
            pass


def make_client(frontend_dir=None):
    """建一个带临时上传目录的测试客户端，返回 (客户端, 上传目录)。"""
    uploads_dir = pathlib.Path(tempfile.mkdtemp(prefix='easyfix_uploads_'))
    return TestClient(build_app(build_connection(), uploads_dir, frontend_dir)), uploads_dir


def count_points(guide):
    """统计 guide 里所有模块的考点总数。"""
    return sum(len(module['points']) for module in guide['knowledge_modules'])


def upload_two_photos(client):
    """上传 p1.jpg、p2.jpg 两个假图片，返回响应内容。"""
    response = client.post('/api/upload/batch-simple', files=[
        ('files', ('p1.jpg', b'fake-one', 'image/jpeg')), ('files', ('p2.jpg', b'fake-two', 'image/jpeg'))])
    assert response.status_code == 200, response.text
    return response.json()


def build_payload(client, evidence='老师打叉'):
    """用 guide 的第一个考点和第一个错因拼一份带两张照片、两道题的卷子。"""
    guide = client.get('/api/intake/guide', params={'subject': '数学'}).json()
    point_id = guide['knowledge_modules'][0]['points'][0]['id']
    images = [item['path'] for item in upload_two_photos(client)['images']]
    questions = [{'page': page, 'question_no': str(page), 'parsed_question': '题目%d' % page, 'answer': '答案',
                  'analysis': '解析', 'wrong_answer': '错解', 'wrong_evidence': evidence, 'difficulty': 3,
                  'error_type': guide['error_types'][0], 'knowledge_point_ids': [point_id],
                  'primary_knowledge_point_id': point_id} for page in (1, 2)]
    return {'spec_version': guide['spec_version'], 'request_id': uuid.uuid4().hex[:20],
            'paper': {'subject_id': 1, 'grade': 6, 'semester': 1, 'name': '', 'paper_type': 'homework',
                      'images': images}, 'questions': questions}


def question_items(client, paper_id):
    """读取某份卷子下的题目列表（兼容分页对象和纯列表两种返回）。"""
    body = client.get('/api/questions', params={'paper_id': paper_id}).json()
    return body['items'] if isinstance(body, dict) else body


def test_guide_math():
    """数学 guide：9 个模块 38 个考点，四个数学错因，六年级。"""
    client, _ = make_client()
    response = client.get('/api/intake/guide', params={'subject': '数学'})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body['catalog_available'] is True
    assert len(body['knowledge_modules']) == 9, len(body['knowledge_modules'])
    assert count_points(body) == 38, count_points(body)
    assert sorted(body['error_types']) == sorted(['计算错误', '审题不清', '概念错误', '完全不会']), body['error_types']
    assert body['grade'] == 6


def test_guide_english():
    """英语 guide：9 个模块 37 个考点。"""
    client, _ = make_client()
    body = client.get('/api/intake/guide', params={'subject': '英语'}).json()
    assert len(body['knowledge_modules']) == 9, len(body['knowledge_modules'])
    assert count_points(body) == 37, count_points(body)


def test_upload_and_fetch():
    """上传两张图：路径合格、文件落盘、能从 /uploads 取回。"""
    client, uploads_dir = make_client()
    body = upload_two_photos(client)
    assert body['total_count'] == 2 and body['success_count'] == 2 and body['failed_count'] == 0
    for item, content in zip(body['images'], (b'fake-one', b'fake-two')):
        assert item['success'] is True
        assert re.match(KEY_PATTERN, item['path']), item['path']
        assert item['image_path'] == item['path']
        assert (uploads_dir / item['path']).read_bytes() == content
        fetched = client.get('/uploads/' + item['path'])
        assert fetched.status_code == 200 and fetched.content == content


def test_upload_rejects_pdf():
    """pdf 文件被拒绝，且不影响同批其他图片。"""
    client, _ = make_client()
    response = client.post('/api/upload/batch-simple', files=[
        ('files', ('a.pdf', b'%PDF', 'application/pdf')), ('files', ('p1.jpg', b'x', 'image/jpeg'))])
    body = response.json()
    assert body['images'][0]['success'] is False and body['images'][0]['error']
    assert body['images'][1]['success'] is True
    assert body['failed_count'] == 1


def test_upload_single_file():
    """单文件上传返回 path、original_filename、size，文件名里的斜杠被去掉。"""
    client, uploads_dir = make_client()
    body = client.post('/api/upload/file', files={'file': ('a/b.png', b'12345', 'image/png')}).json()
    assert body['size'] == 5 and body['original_filename'] == 'a/b.png'
    assert re.match(KEY_PATTERN, body['path']), body['path']
    assert (uploads_dir / body['path']).exists()


def test_uploads_cannot_escape():
    """路径穿越和反斜杠都不能读到上传目录之外的内容。"""
    client, uploads_dir = make_client()
    (uploads_dir.parent / 'secret_x.txt').write_text('secret', encoding='utf-8')
    for path in ('/uploads/../secret_x.txt', '/uploads/%2e%2e/secret_x.txt', '/uploads/..%5csecret_x.txt',
                 '/uploads/a/../../secret_x.txt', '/uploads/missing.jpg'):
        response = client.get(path)
        assert response.status_code in (400, 404), (path, response.status_code)
        assert b'secret' not in response.content


def test_submit_paper_end_to_end():
    """试提交、正式提交后，题目带各自页的照片，待核对为 0，卷子列表有 2 题。"""
    client, _ = make_client()
    payload = build_payload(client)
    checked = client.post('/api/intake/papers/check', json=payload)
    assert checked.status_code == 200 and checked.json()['ok'] is True, checked.text
    submitted = client.post('/api/intake/papers', json=payload)
    assert submitted.status_code == 201, submitted.text
    paper_id = submitted.json()['paper']['id']
    items = question_items(client, paper_id)
    assert len(items) == 2, items
    for item in items:
        assert item['original_image'] == payload['paper']['images'][item['paper_page'] - 1]
    assert client.get('/api/questions/review/count').json() == {'pending': 0}
    papers = client.get('/api/papers').json()['items']
    mine = [paper for paper in papers if paper['id'] == paper_id]
    assert mine and mine[0]['question_count'] == 2, papers


def test_review_flow():
    """证据为空的题进入待核对，通过后数字回到原值。"""
    client, _ = make_client()
    before = client.get('/api/questions/review/count').json()['pending']
    submitted = client.post('/api/intake/papers', json=build_payload(client, evidence=''))
    assert submitted.status_code == 201, submitted.text
    assert client.get('/api/questions/review/count').json()['pending'] > before
    pending = [item for item in question_items(client, submitted.json()['paper']['id'])
               if item['review_status'] == 'pending']
    assert pending, '应当有待核对的题'
    after_submit = client.get('/api/questions/review/count').json()['pending']
    response = client.post('/api/questions/%d/review' % pending[0]['id'], json={'action': 'approve'})
    assert response.status_code == 200, response.text
    assert client.get('/api/questions/review/count').json()['pending'] == after_submit - 1


def test_subjects():
    """学科列表有数学和英语。"""
    client, _ = make_client()
    body = client.get('/api/subjects').json()
    # 线上同名路由被 catalog 的通用列表抢先匹配，顺序不保证，所以只比较集合
    assert sorted(row['name'] for row in body) == sorted(['数学', '英语']), body


def test_frontend_fallback():
    """带前端目录时：根路径和前端路由返回 index.html，静态文件原样返回，接口不受影响。"""
    frontend_dir = pathlib.Path(tempfile.mkdtemp(prefix='easyfix_frontend_'))
    (frontend_dir / 'index.html').write_text('<html>INDEX</html>', encoding='utf-8')
    (frontend_dir / 'assets').mkdir()
    (frontend_dir / 'assets' / 'a.js').write_text('console.log(1)', encoding='utf-8')
    client, _ = make_client(frontend_dir)
    assert client.get('/').text == '<html>INDEX</html>'
    assert client.get('/review').text == '<html>INDEX</html>'
    assert client.get('/assets/a.js').text == 'console.log(1)'
    assert client.get('/api/subjects').headers['content-type'].startswith('application/json')
    assert client.get('/api/nope').status_code == 404
    assert client.get('/uploads/nope.jpg').status_code == 404
    # 目录之外的文件不能经静态路径读到
    (frontend_dir.parent / 'secret_y.txt').write_text('secret', encoding='utf-8')
    assert b'secret' not in client.get('/..%2fsecret_y.txt').content
    assert b'secret' not in client.get('/assets/..%2f..%2fsecret_y.txt').content


def test_no_auth_needed():
    """带不带 Authorization 都放行。"""
    client, _ = make_client()
    assert client.get('/api/subjects', headers={'Authorization': 'Bearer whatever'}).status_code == 200
    assert client.get('/api/subjects').status_code == 200


def test_main_rejects_non_local_host():
    """命令行不接受 127.0.0.1 之外的监听地址参数。"""
    try:
        local_dev_server.main(['--host', '0.0.0.0'])
    except SystemExit as error:
        assert error.code != 0
        return
    raise AssertionError('应当拒绝 --host')


def main():
    """依次运行所有以 test_ 开头的测试并汇总。"""
    configure_output()
    tests = [(name, function) for name, function in sorted(globals().items())
             if name.startswith('test_') and callable(function)]
    failures = 0
    for name, function in tests:
        try:
            function()
            print('通过', name)
        except Exception:
            failures += 1
            print('失败', name)
            traceback.print_exc()
    print('%d 个测试，%d 个失败' % (len(tests), failures))
    return 1 if failures else 0


if __name__ == '__main__':
    sys.exit(main())
