"""录入小工具的测试：全部用可替换的 opener 代替真实网络。"""
import contextlib
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

# 技能文件（SKILL.md、payload-format.md、easyfix_intake.py）所在的目录
SOURCE_DIR = pathlib.Path(__file__).parent
# UTF-8 的 BOM 头，Windows 记事本和 PowerShell 存文件时会带上
BOM_BYTES = bytes([0xEF, 0xBB, 0xBF])


def load_install():
    """按路径加载 install.py（目录名带连字符，不能当包导入）。"""
    path = SOURCE_DIR / 'install.py'
    spec = importlib.util.spec_from_file_location('easyfix_install', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def read_frontmatter(text):
    """取出 SKILL.md 开头两条 --- 之间的元信息，解析成 {键: 值}。"""
    lines = text.splitlines()
    end = lines.index('---', 1)  # 第二条 --- 的行号
    meta = {}
    for line in lines[1:end]:
        if ':' in line:
            key, _, value = line.partition(':')
            meta[key.strip()] = value.strip()
    return meta


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

    def test_submit_conflict_without_spec_version_is_exit_2_with_message(self):
        """正式提交返回 409（不是版本不一致）：退出码 2，输出 ok 为假并带服务器的说明。"""
        paper = self.make_paper()
        detail = '这个提交文件的内容和第一次提交时不一样，这次没有写入任何内容。'

        def handler(method, url, headers, body):
            if url.endswith('/api/intake/papers/check'):
                return 200, {'ok': True}
            return 409, {'detail': detail}

        code, out = self.run_main(['submit', str(paper)], FakeOpener(handler))
        data = json.loads(out)
        self.assertEqual(code, 2)
        self.assertEqual((data['ok'], data['message']), (False, detail))

    def test_submit_replayed_adds_message_first_and_exits_0(self):
        """正式提交返回 200 且 replayed 为真：退出码 0，message 在输出最前面。"""
        paper = self.make_paper()

        def handler(method, url, headers, body):
            if url.endswith('/api/intake/papers/check'):
                return 200, {'ok': True}
            return 200, {'paper': {'id': 7}, 'replayed': True}

        code, out = self.run_main(['submit', str(paper)], FakeOpener(handler))
        data = json.loads(out)
        self.assertEqual(code, 0)
        self.assertEqual(list(data)[0], 'message')
        self.assertIn('之前已经提交成功过', data['message'])
        self.assertEqual(data['paper'], {'id': 7})

    def test_submit_first_time_has_no_replay_message(self):
        """第一次提交成功（201）输出里没有 message。"""
        paper = self.make_paper()

        def handler(method, url, headers, body):
            if url.endswith('/api/intake/papers/check'):
                return 200, {'ok': True}
            return 201, {'paper': {'id': 7}, 'replayed': False}

        code, out = self.run_main(['submit', str(paper)], FakeOpener(handler))
        self.assertEqual(code, 0)
        self.assertNotIn('message', json.loads(out))

    def test_config_file_with_bom_is_readable(self):
        """Windows 记事本、PowerShell 存出来的带 BOM 配置文件也能读出地址和口令。"""
        cfg_file = self.dir / 'intake.json'
        cfg_file.write_bytes(BOM_BYTES + json.dumps({'base_url': 'http://bom.test', 'token': 'bom-token'}).encode('utf-8'))
        self.assertEqual(tool.load_config({}, cfg_file), {'base_url': 'http://bom.test', 'token': 'bom-token'})

    def test_help_lists_exit_codes(self):
        """--help 里列出退出码。"""
        self.assertIn('退出码：0 成功；2 内容没通过检查', tool.build_parser().format_help())

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
        # Cloudflare 会拦截 Python 默认的客户端名称，必须带自己的
        self.assertEqual(req['headers']['User-Agent'], 'easyfix-intake/1')
        self.assertEqual(json.loads(out), {'guide': '规则'})

    def test_malformed_base_url_or_token_is_exit_4_not_traceback(self):
        # 地址缺少 http://：用真实 default_opener，请求在连接前就失败，不会联网
        with mock.patch.dict(os.environ, {'EASYFIX_URL': 'example.test', 'EASYFIX_TOKEN': TOKEN}):
            code, out = self.run_main(['guide', '--subject', '数学'], tool.default_opener)
        self.assertEqual(code, 4)
        self.assertIn('接口地址格式不对', out)
        self.assertNotIn(TOKEN, out)
        # 口令含非 latin-1 字符：请求头编码失败，同样退出码 4，且不泄露口令
        bad_token = '口令-' + TOKEN
        with mock.patch.dict(os.environ, {'EASYFIX_URL': BASE_URL, 'EASYFIX_TOKEN': bad_token}):
            def encoding_opener(method, url, headers, body):
                """模拟 http 库发送请求头时按 latin-1 编码（不联网）。"""
                headers['Authorization'].encode('latin-1')
                return 200, b'{}'
            code, out = self.run_main(['guide', '--subject', '数学'], encoding_opener)
        self.assertEqual(code, 4)
        self.assertNotIn(bad_token, out)
        self.assertNotIn(TOKEN, out)

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


class InstallTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = pathlib.Path(self.tmp.name)

    def test_install_copies_files_and_creates_config(self):
        installer = load_install()
        installer.install(self.home, SOURCE_DIR)
        # 两个用户级技能目录里都要有三个技能文件
        for base in ('.claude/skills', '.agents/skills'):
            target = self.home / base / 'easyfix-intake'
            for name in installer.SKILL_FILES:
                self.assertTrue((target / name).is_file(), '%s/%s 没有复制过去' % (base, name))
        # intake.json：base_url 正确、token 为空
        config = json.loads((self.home / '.easyfix' / 'intake.json').read_text(encoding='utf-8'))
        self.assertEqual(config['base_url'], 'https://easyfix-bl2.pages.dev')
        self.assertEqual(config['token'], '')
        # 没有 --codex-pointer 时不创建 .codex/AGENTS.md
        self.assertFalse((self.home / '.codex' / 'AGENTS.md').exists())

    def test_install_is_repeatable_and_keeps_token(self):
        installer = load_install()
        installer.install(self.home, SOURCE_DIR)
        config_path = self.home / '.easyfix' / 'intake.json'
        # 先把 token 改成真实值，再运行一次
        data = json.loads(config_path.read_text(encoding='utf-8'))
        data['token'] = 'secret-value'
        config_path.write_text(json.dumps(data), encoding='utf-8')
        installer.install(self.home, SOURCE_DIR)
        again = json.loads(config_path.read_text(encoding='utf-8'))
        self.assertEqual(again['token'], 'secret-value')  # token 不被覆盖
        # 重复运行后技能文件仍然齐全（覆盖，不报错）
        for name in installer.SKILL_FILES:
            self.assertTrue((self.home / '.claude/skills/easyfix-intake' / name).is_file())

    def test_codex_pointer_is_added_once_and_keeps_other_content(self):
        installer = load_install()
        codex = self.home / '.codex'
        codex.mkdir(parents=True)
        original = '# 我的 Codex 说明\n这一行要保留。\n'
        (codex / 'AGENTS.md').write_text(original, encoding='utf-8')
        # codex_pointer=True 运行两次
        installer.install(self.home, SOURCE_DIR, codex_pointer=True)
        installer.install(self.home, SOURCE_DIR, codex_pointer=True)
        text = (codex / 'AGENTS.md').read_text(encoding='utf-8')
        self.assertEqual(text.count(installer.POINTER_MARK), 1)  # 标记只出现一次
        self.assertIn('这一行要保留。', text)                     # 原有内容还在

    def run_install_main(self, argv):
        """经由 main 运行安装（home 指到临时目录，不碰真实主目录），返回打印的文字。"""
        installer = load_install()
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(installer.main(argv, home=self.home, source=SOURCE_DIR), 0)
        return installer, out.getvalue()

    def test_main_with_codex_pointer_flag_writes_pointer(self):
        installer, _ = self.run_install_main(['--codex-pointer'])
        text = (self.home / '.codex' / 'AGENTS.md').read_text(encoding='utf-8')
        self.assertIn(installer.POINTER_MARK, text)

    def test_main_without_flag_does_not_write_pointer(self):
        self.run_install_main([])
        self.assertFalse((self.home / '.codex' / 'AGENTS.md').exists())
        self.assertTrue((self.home / '.easyfix' / 'intake.json').is_file())

    def test_install_reads_bom_config_token(self):
        """带 BOM 的配置文件里已有口令时，安装不再提醒填口令。"""
        installer = load_install()
        config_dir = self.home / '.easyfix'
        config_dir.mkdir(parents=True)
        (config_dir / 'intake.json').write_bytes(
            BOM_BYTES + json.dumps({'base_url': 'http://x.test', 'token': 'filled'}).encode('utf-8'))
        _, token_empty = installer.ensure_config(self.home)
        self.assertFalse(token_empty)

    def test_install_never_reports_token(self):
        installer = load_install()
        installer.install(self.home, SOURCE_DIR)
        config_path = self.home / '.easyfix' / 'intake.json'
        data = json.loads(config_path.read_text(encoding='utf-8'))
        data['token'] = 'secret-value'
        config_path.write_text(json.dumps(data), encoding='utf-8')
        notes = installer.install(self.home, SOURCE_DIR)
        for line in notes:
            self.assertNotIn('secret-value', line)  # 返回的说明里不含口令

    def test_skill_description_only_says_when_to_use(self):
        meta = read_frontmatter((SOURCE_DIR / 'SKILL.md').read_text(encoding='utf-8'))
        self.assertEqual(meta['name'], 'easyfix-intake')
        self.assertTrue(meta['description'].startswith('Use when'))
        self.assertIn('录入错题', meta['description'])
        # description 只写什么时候用，不出现任何命令名
        for command in ('guide', 'upload', 'check', 'submit'):
            self.assertNotIn(command, meta['description'])

    def test_skill_and_format_files_cover_required_content(self):
        skill = (SOURCE_DIR / 'SKILL.md').read_text(encoding='utf-8')
        # 那句提问的原文和待核对页地址
        self.assertIn("这是哪份作业或卷子？如果是考试，多少分？可以回'跳过'。", skill)
        self.assertIn('https://easyfix-bl2.pages.dev/review', skill)
        fmt = (SOURCE_DIR / 'payload-format.md').read_text(encoding='utf-8')
        # 必填的顶层字段：家长的回答
        self.assertIn('parent_reply', fmt)
        # 四个待核对原因代码
        for code in ('wrong_unclear', 'text_unclear', 'kp_unsure', 'other'):
            self.assertIn(code, fmt)
        # paper 部分的字段
        for field in ('subject_id', 'images'):
            self.assertIn(field, fmt)
        # questions 部分的字段
        for field in ('parsed_question', 'wrong_evidence', 'knowledge_point_ids'):
            self.assertIn(field, fmt)


if __name__ == '__main__':
    unittest.main()
