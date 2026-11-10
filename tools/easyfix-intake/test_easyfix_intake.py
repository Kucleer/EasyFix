"""录入小工具的测试：全部用可替换的 opener 代替真实网络。"""
import importlib.util
import io
import json
import os
import pathlib
import re
import tempfile
import unittest
from unittest import mock

# 目录名带连字符，不能当包导入，按路径加载
_MODULE_PATH = pathlib.Path(__file__).with_name('easyfix_intake.py')
_spec = importlib.util.spec_from_file_location('easyfix_intake', _MODULE_PATH)
tool = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(tool)

TOKEN = 'secret-token-XYZ-987'
BASE_URL = 'http://example.test'
ENV = {'EASYFIX_URL': BASE_URL, 'EASYFIX_TOKEN': TOKEN}


class FakeOpener:
    """记录每次请求，并按路径调用处理函数返回 (状态码, 响应字典)。"""

    def __init__(self, handler):
        self.handler = handler
        self.requests = []

    def __call__(self, method, url, headers, body):
        self.requests.append({'method': method, 'url': url, 'headers': headers, 'body': body})
        result = self.handler(method, url, headers, body)
        if isinstance(result, Exception):
            raise result
        status, data = result
        return status, json.dumps(data, ensure_ascii=False).encode('utf-8')

    def paths(self):
        """返回所有请求的路径（不含地址和查询串）。"""
        return [r['url'][len(BASE_URL):].split('?')[0] for r in self.requests]


def upload_handler(fail_name=None):
    """生成上传接口的假处理函数；fail_name 指定要失败的文件名。"""
    def handler(method, url, headers, body):
        names = re.findall(rb'filename="([^"]+)"', body)
        images = []
        for raw in names:
            name = raw.decode('utf-8')
            if name == fail_name:
                images.append({'original_filename': name, 'success': False, 'error': '格式不支持'})
            else:
                images.append({'path': '2026/11/' + name, 'original_filename': name, 'success': True})
        return 200, {'images': images}
    return handler


class IntakeToolTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = pathlib.Path(self.tmp.name)
        patcher = mock.patch.dict(os.environ, ENV)
        patcher.start()
        self.addCleanup(patcher.stop)

    def run_main(self, argv, opener):
        """运行 main，返回 (退出码, 标准输出文本)。"""
        out = io.StringIO()
        code = tool.main(argv, opener=opener, stdout=out)
        return code, out.getvalue()

    def make_images(self, count):
        """在临时目录生成 count 张小图，返回路径列表。"""
        paths = []
        for i in range(count):
            p = self.dir / ('img_%02d.jpg' % i)
            p.write_bytes(b'\xff\xd8fake')
            paths.append(str(p))
        return paths

    def make_paper(self, data=None):
        """写一份试卷 JSON，返回路径。"""
        p = self.dir / 'paper.json'
        p.write_text(json.dumps(data or {'paper': {}, 'questions': []}, ensure_ascii=False), encoding='utf-8')
        return p

    def test_config_prefers_environment(self):
        cfg_file = self.dir / 'intake.json'
        cfg_file.write_text(json.dumps({'base_url': 'http://file.test', 'token': 'file-token'}), encoding='utf-8')
        # 环境变量和文件都有：用环境变量
        cfg = tool.load_config({'EASYFIX_URL': 'http://env.test', 'EASYFIX_TOKEN': 'env-token'}, cfg_file)
        self.assertEqual(cfg, {'base_url': 'http://env.test', 'token': 'env-token'})
        # 只有文件：用文件
        cfg = tool.load_config({}, cfg_file)
        self.assertEqual(cfg, {'base_url': 'http://file.test', 'token': 'file-token'})
        # 都没有：退出码 4，且说明里不含口令
        with self.assertRaises(tool.ToolError) as ctx:
            tool.load_config({'EASYFIX_TOKEN': TOKEN}, self.dir / 'missing.json')
        self.assertEqual(ctx.exception.code, 4)
        self.assertNotIn(TOKEN, str(ctx.exception))
        self.assertIn('install.py', str(ctx.exception))

    def test_chunk_keeps_order(self):
        self.assertEqual(tool.chunk(list(range(23)), 10), [list(range(10)), list(range(10, 20)), [20, 21, 22]])

    def test_check_images_rejects_big_and_non_image(self):
        big = self.dir / 'big.jpg'
        with open(big, 'wb') as f:
            f.truncate(11 * 1024 * 1024)
        pdf = self.dir / 'doc.pdf'
        pdf.write_bytes(b'%PDF')
        missing = self.dir / 'nothing.png'
        for path in (big, pdf, missing):
            with self.assertRaises(tool.ToolError) as ctx:
                tool.check_images([str(path)])
            self.assertEqual(ctx.exception.code, 4)
            self.assertIn(path.name, str(ctx.exception))
        # 合格的图片不抛错
        tool.check_images(self.make_images(2))

    def test_upload_batches_and_keeps_page_order(self):
        paths = self.make_images(23)
        opener = FakeOpener(upload_handler())
        code, out = self.run_main(['upload'] + paths, opener)
        self.assertEqual(code, 0)
        # 23 张分 3 次请求，路径与路径参数
        self.assertEqual(opener.paths(), ['/api/upload/batch-simple'] * 3)
        counts = [len(re.findall(rb'name="files"', r['body'])) for r in opener.requests]
        self.assertEqual(counts, [10, 10, 3])
        # 输出的 23 个路径与输入顺序一一对应
        expected = ['2026/11/img_%02d.jpg' % i for i in range(23)]
        self.assertEqual(json.loads(out), {'images': expected})

    def test_upload_fails_as_a_whole_when_one_image_fails(self):
        paths = self.make_images(23)
        opener = FakeOpener(upload_handler(fail_name='img_11.jpg'))
        code, out = self.run_main(['upload'] + paths, opener)
        self.assertEqual(code, 4)
        self.assertNotIn('images', out)
        # 说明里有第几张、文件名和原因
        self.assertIn('第12张', out)
        self.assertIn('img_11.jpg', out)
        self.assertIn('格式不支持', out)

    def test_prepare_payload_fills_and_keeps_request_id(self):
        payload, added = tool.prepare_payload({'paper': {}, 'questions': []}, lambda: 'abc-12345')
        self.assertEqual((payload['spec_version'], payload['request_id'], added), (1, 'abc-12345', True))
        again, added = tool.prepare_payload(payload, lambda: 'other-id')
        self.assertEqual((again['request_id'], added), ('abc-12345', False))

    def test_submit_writes_request_id_before_sending(self):
        paper = self.make_paper()
        state = {'fail_submit': True}

        def handler(method, url, headers, body):
            if url.endswith('/api/intake/papers/check'):
                return 200, {'ok': True}
            if state['fail_submit']:
                return OSError('连接中断')
            return 200, {'ok': True, 'paper_id': 7}

        opener = FakeOpener(handler)
        code, _ = self.run_main(['submit', str(paper)], opener)
        self.assertEqual(code, 4)
        # 提交请求失败后，文件里已经有 request_id
        saved = json.loads(paper.read_text(encoding='utf-8'))
        self.assertTrue(saved['request_id'])
        first_sent = json.loads(opener.requests[-1]['body'])
        self.assertEqual(first_sent['request_id'], saved['request_id'])
        # 再次 submit 沿用同一个 request_id
        state['fail_submit'] = False
        code, _ = self.run_main(['submit', str(paper)], opener)
        self.assertEqual(code, 0)
        second_sent = json.loads(opener.requests[-1]['body'])
        self.assertEqual(second_sent['request_id'], saved['request_id'])
        self.assertEqual(json.loads(paper.read_text(encoding='utf-8'))['request_id'], saved['request_id'])

    def test_submit_stops_when_check_fails(self):
        paper = self.make_paper()
        errors = [{'path': 'questions[0].stem', 'message': '题干不能为空'}]
        opener = FakeOpener(lambda m, u, h, b: (200, {'ok': False, 'errors': errors}))
        code, out = self.run_main(['submit', str(paper)], opener)
        self.assertEqual(code, 2)
        # 只调了 check，没有发正式提交
        self.assertEqual(opener.paths(), ['/api/intake/papers/check'])
        self.assertEqual(json.loads(out)['errors'], errors)

    def test_check_command_exit_codes(self):
        paper = self.make_paper()
        code, _ = self.run_main(['check', str(paper)], FakeOpener(lambda m, u, h, b: (200, {'ok': True})))
        self.assertEqual(code, 0)
        code, _ = self.run_main(['check', str(paper)], FakeOpener(lambda m, u, h, b: (200, {'ok': False, 'errors': []})))
        self.assertEqual(code, 2)

    def test_version_mismatch_exit_code(self):
        paper = self.make_paper()
        opener = FakeOpener(lambda m, u, h, b: (409, {'detail': '版本不一致', 'spec_version': 2}))
        code, out = self.run_main(['submit', str(paper)], opener)
        self.assertEqual(code, 3)
        self.assertIn('安装脚本', out)

    def test_guide_sends_query_and_bearer_header(self):
        opener = FakeOpener(lambda m, u, h, b: (200, {'guide': '规则'}))
        code, out = self.run_main(['guide', '--subject', '数学', '--grade', '3', '--semester', '1'], opener)
        self.assertEqual(code, 0)
        req = opener.requests[0]
        self.assertEqual(req['method'], 'GET')
        self.assertTrue(req['url'].startswith(BASE_URL + '/api/intake/guide?'))
        self.assertIn('grade=3', req['url'])
        self.assertIn('semester=1', req['url'])
        self.assertIn('subject=%E6%95%B0%E5%AD%A6', req['url'])
        self.assertEqual(req['headers']['Authorization'], 'Bearer ' + TOKEN)
        self.assertEqual(json.loads(out), {'guide': '规则'})

    def test_token_never_printed(self):
        paper = self.make_paper()
        images = self.make_images(2)
        # 网络错误的异常文字里故意带上口令，输出也不能出现
        leaky = OSError('连接失败 ' + TOKEN)
        scenarios = [
            (['guide', '--subject', '数学'], FakeOpener(lambda m, u, h, b: (200, {'guide': 'x'}))),
            (['guide', '--subject', '数学'], FakeOpener(lambda m, u, h, b: leaky)),
            (['guide', '--subject', '数学'], FakeOpener(lambda m, u, h, b: (401, {'detail': '口令不对'}))),
            (['upload'] + images, FakeOpener(upload_handler(fail_name='img_01.jpg'))),
            (['upload'] + images, FakeOpener(lambda m, u, h, b: leaky)),
            (['upload', str(self.dir / 'none.jpg')], FakeOpener(upload_handler())),
            (['check', str(paper)], FakeOpener(lambda m, u, h, b: (422, {'detail': '格式错', 'errors': []}))),
            (['check', str(paper)], FakeOpener(lambda m, u, h, b: leaky)),
            (['submit', str(paper)], FakeOpener(lambda m, u, h, b: (409, {'spec_version': 2}))),
            (['submit', str(paper)], FakeOpener(lambda m, u, h, b: leaky)),
            (['check', str(self.dir / 'none.json')], FakeOpener(lambda m, u, h, b: (200, {'ok': True}))),
        ]
        for argv, opener in scenarios:
            code, out = self.run_main(argv, opener)
            self.assertNotIn(TOKEN, out, argv)
        # 即使文件里的 request_id 等内容不含口令，错误说明也不能带出口令
        with self.assertRaises(tool.ToolError) as ctx:
            tool.call({'base_url': BASE_URL, 'token': TOKEN}, 'GET', '/x', opener=FakeOpener(lambda m, u, h, b: leaky))
        self.assertNotIn(TOKEN, str(ctx.exception))
        self.assertEqual(ctx.exception.code, 4)


if __name__ == '__main__':
    unittest.main()
