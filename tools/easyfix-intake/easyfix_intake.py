"""EasyFix 录入小工具：给 Claude / Codex 等助手调用，只用 Python 标准库。

用法：python easyfix_intake.py <命令> ...
  guide --subject 名称 [--grade N] [--semester N]   取录入规范
  upload 图片路径...                                  上传照片，输出存储路径
  check 文件.json                                     只检查试卷内容，不保存
  submit 文件.json                                    检查通过后正式提交

退出码：0 成功；2 内容有问题需要修改；3 录入规范版本不一致；4 配置、文件或网络问题。

opener 约定（测试用它代替真实网络）：
    opener(method, url, headers, body) -> (状态码, 响应体字节)
  method 是 'GET' / 'POST'，url 是完整地址，headers 是字典，body 是字节或 None。
  遇到 HTTP 错误状态（如 409、422）也要正常返回状态码和响应体；
  只有连不上、超时等网络问题才抛 OSError。
"""
import argparse
import json
import os
import pathlib
import sys
import urllib.error
import urllib.parse
import urllib.request
import uuid

SPEC_VERSION = 1
UPLOAD_BATCH = 10
MAX_IMAGE_BYTES = 10 * 1024 * 1024
IMAGE_SUFFIXES = ('.jpg', '.jpeg', '.png', '.webp')
REQUEST_TIMEOUT = 120

EXIT_OK = 0
EXIT_CONTENT = 2
EXIT_VERSION = 3
EXIT_ENV = 4


class ToolError(Exception):
    """给人看的中文说明和退出码。"""

    def __init__(self, message, code):
        """记录说明和退出码。"""
        super().__init__(message)
        self.message = message
        self.code = code


def load_config(environ, config_path):
    """读取配置：环境变量优先，其次配置文件；缺任何一项都报错。"""
    base_url = environ.get('EASYFIX_URL') or ''
    token = environ.get('EASYFIX_TOKEN') or ''
    if not (base_url and token) and pathlib.Path(config_path).is_file():
        try:
            file_data = json.loads(pathlib.Path(config_path).read_text(encoding='utf-8'))
        except (OSError, ValueError):
            raise ToolError('配置文件读不出来，请检查 ~/.easyfix/intake.json 是否是正确的 JSON', EXIT_ENV)
        if isinstance(file_data, dict):
            base_url = base_url or str(file_data.get('base_url') or '')
            token = token or str(file_data.get('token') or '')
    if not (base_url and token):
        raise ToolError('还没有配置接口地址或访问口令，请先运行 install.py 并填写 ~/.easyfix/intake.json', EXIT_ENV)
    return {'base_url': base_url, 'token': token}


def chunk(items, size):
    """把列表按 size 切成多段，保持原有顺序。"""
    return [items[i:i + size] for i in range(0, len(items), size)]


def check_images(paths):
    """检查图片是否存在、格式和大小是否合格；不合格抛 ToolError(code=4)。"""
    for raw in paths:
        path = pathlib.Path(raw)
        if not path.is_file():
            raise ToolError('找不到图片文件：%s' % path.name, EXIT_ENV)
        if path.suffix.lower() not in IMAGE_SUFFIXES:
            raise ToolError('不支持的图片格式：%s（只支持 jpg、png、webp）' % path.name, EXIT_ENV)
        if path.stat().st_size > MAX_IMAGE_BYTES:
            raise ToolError('图片超过 10MB：%s，请压缩后再传' % path.name, EXIT_ENV)


def build_multipart(paths):
    """把多张图片打成 multipart 请求体，表单字段名是 files；返回 (请求体, Content-Type)。"""
    boundary = 'easyfix' + uuid.uuid4().hex
    parts = []
    for raw in paths:
        path = pathlib.Path(raw)
        # 文件名里的双引号会破坏头部格式，替换掉
        filename = path.name.replace('"', '_')
        content_type = 'image/png' if path.suffix.lower() == '.png' else (
            'image/webp' if path.suffix.lower() == '.webp' else 'image/jpeg')
        head = ('--%s\r\nContent-Disposition: form-data; name="files"; filename="%s"\r\n'
                'Content-Type: %s\r\n\r\n' % (boundary, filename, content_type))
        parts.append(head.encode('utf-8') + path.read_bytes() + b'\r\n')
    parts.append(('--%s--\r\n' % boundary).encode('utf-8'))
    return b''.join(parts), 'multipart/form-data; boundary=' + boundary


def prepare_payload(payload, new_id):
    """补上 spec_version 和 request_id；返回 (新内容, 是否新补了 request_id)。"""
    result = dict(payload)
    result['spec_version'] = SPEC_VERSION
    added = not result.get('request_id')
    if added:
        result['request_id'] = new_id()
    return result, added


def default_opener(method, url, headers, body):
    """真实网络请求：HTTP 错误状态也正常返回；连不上则抛 OSError。"""
    request = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read()


def call(config, method, path, *, params=None, json_body=None, body=None, content_type=None, opener=None):
    """调用服务端接口，返回 (状态码, 响应字典)；网络问题抛 ToolError(code=4)。"""
    opener = opener or default_opener
    url = config['base_url'].rstrip('/') + path
    if params:
        url += '?' + urllib.parse.urlencode(params)
    headers = {'Authorization': 'Bearer ' + config['token'], 'Accept': 'application/json'}
    if json_body is not None:
        body = json.dumps(json_body, ensure_ascii=False).encode('utf-8')
        content_type = 'application/json; charset=utf-8'
    if content_type:
        headers['Content-Type'] = content_type
    try:
        status, raw = opener(method, url, headers, body)
    except OSError as exc:
        # 异常文字里万一带了口令，先抹掉再给人看
        reason = str(exc).replace(config['token'], '***')
        raise ToolError('连不上服务器，请检查网络和接口地址后重试（%s）' % reason, EXIT_ENV)
    except ValueError:
        # 地址缺少 http:// 或口令含无法编码的字符时，请求发出前就会失败；
        # 异常文字可能带出口令里的字符，所以不展示原因
        raise ToolError('接口地址格式不对（需要以 http:// 或 https:// 开头），或访问口令含有无法识别的字符，'
                        '请检查 ~/.easyfix/intake.json', EXIT_ENV)
    try:
        data = json.loads(raw.decode('utf-8')) if raw else {}
    except ValueError:
        data = {}
    if not isinstance(data, dict):
        data = {'data': data}
    return status, data


def _failure_text(status, data):
    """把服务端的失败响应整理成一句话（不含口令）。"""
    detail = data.get('detail')
    if isinstance(detail, (dict, list)):
        detail = json.dumps(detail, ensure_ascii=False)
    return '服务器返回 %s：%s' % (status, detail or '没有更多说明')


def _version_error():
    """录入规范版本不一致时的提示。"""
    return ToolError('录入规范版本和服务器不一致，请重新运行安装脚本 install.py 更新后再试', EXIT_VERSION)


def _read_json_file(path):
    """读取 JSON 文件，失败抛 ToolError(code=4)。"""
    try:
        data = json.loads(pathlib.Path(path).read_text(encoding='utf-8'))
    except OSError:
        raise ToolError('读不到文件：%s' % pathlib.Path(path).name, EXIT_ENV)
    except ValueError:
        raise ToolError('文件不是正确的 JSON：%s' % pathlib.Path(path).name, EXIT_ENV)
    if not isinstance(data, dict):
        raise ToolError('文件内容必须是一个 JSON 对象：%s' % pathlib.Path(path).name, EXIT_ENV)
    return data


def _run_check(config, payload, opener):
    """调用检查接口；返回 (退出码, 要输出的字典)。"""
    status, data = call(config, 'POST', '/api/intake/papers/check', json_body=payload, opener=opener)
    if status == 409 and 'spec_version' in data:
        raise _version_error()
    if status == 422:
        return EXIT_CONTENT, data
    if status != 200:
        raise ToolError(_failure_text(status, data), EXIT_ENV)
    return (EXIT_OK if data.get('ok') else EXIT_CONTENT), data


def command_guide(config, args, opener):
    """guide 命令：取录入规范。"""
    params = {'subject': args.subject}
    if args.grade is not None:
        params['grade'] = args.grade
    if args.semester is not None:
        params['semester'] = args.semester
    status, data = call(config, 'GET', '/api/intake/guide', params=params, opener=opener)
    if status != 200:
        raise ToolError(_failure_text(status, data), EXIT_ENV)
    return EXIT_OK, data


def command_upload(config, args, opener):
    """upload 命令：先检查全部图片，再按批上传，任何一张失败就整体失败。"""
    check_images(args.paths)
    stored = []
    for batch in chunk(args.paths, UPLOAD_BATCH):
        body, content_type = build_multipart(batch)
        status, data = call(config, 'POST', '/api/upload/batch-simple', body=body,
                            content_type=content_type, opener=opener)
        if status != 200:
            raise ToolError(_failure_text(status, data), EXIT_ENV)
        results = data.get('images') or []
        for offset, raw in enumerate(batch):
            number = len(stored) + 1  # 第几张（从 1 开始，按给出顺序）
            name = pathlib.Path(raw).name
            item = results[offset] if offset < len(results) else {}
            if not item.get('success') or not item.get('path'):
                reason = item.get('error') or '服务器没有返回这张图片的存储路径'
                raise ToolError('第%d张图片上传失败（%s）：%s，本次没有保存任何结果' % (number, name, reason), EXIT_ENV)
            stored.append(item['path'])
    return EXIT_OK, {'images': stored}


def command_check(config, args, opener):
    """check 命令：只检查，不保存，也不改文件。"""
    payload, _ = prepare_payload(_read_json_file(args.file), lambda: str(uuid.uuid4()))
    return _run_check(config, payload, opener)


def command_submit(config, args, opener):
    """submit 命令：先把 request_id 写回文件，再检查，通过后正式提交。"""
    original = _read_json_file(args.file)
    payload, added = prepare_payload(original, lambda: str(uuid.uuid4()))
    if added:
        # 先落盘再发请求：网络中断后重试能沿用同一个 request_id，不会重复入库
        try:
            pathlib.Path(args.file).write_text(
                json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
        except OSError:
            raise ToolError('无法把 request_id 写回文件：%s' % pathlib.Path(args.file).name, EXIT_ENV)
    code, data = _run_check(config, payload, opener)
    if code != EXIT_OK:
        return code, data
    status, data = call(config, 'POST', '/api/intake/papers', json_body=payload, opener=opener)
    if status == 409 and 'spec_version' in data:
        raise _version_error()
    if status == 422:
        return EXIT_CONTENT, data
    if status not in (200, 201):
        raise ToolError(_failure_text(status, data), EXIT_ENV)
    return EXIT_OK, data


def build_parser():
    """构造命令行参数解析器。"""
    parser = argparse.ArgumentParser(prog='easyfix_intake.py', description='EasyFix 录入小工具')
    sub = parser.add_subparsers(dest='command', required=True)
    guide = sub.add_parser('guide', help='取录入规范')
    guide.add_argument('--subject', required=True, help='学科名称')
    guide.add_argument('--grade', type=int)
    guide.add_argument('--semester', type=int)
    upload = sub.add_parser('upload', help='上传照片')
    upload.add_argument('paths', nargs='+', help='图片路径，按页面顺序给出')
    check = sub.add_parser('check', help='检查试卷 JSON')
    check.add_argument('file')
    submit = sub.add_parser('submit', help='检查并提交试卷 JSON')
    submit.add_argument('file')
    return parser


def _emit(stdout, data):
    """把结果以 UTF-8 JSON 写到标准输出。"""
    stdout.write(json.dumps(data, ensure_ascii=False) + '\n')


def main(argv, *, opener=None, stdout=None):
    """命令行入口：返回退出码，所有输出都是 JSON。"""
    stdout = stdout or sys.stdout
    try:
        args = build_parser().parse_args(argv)
    except SystemExit as exc:
        # argparse 自己会把用法说明写到 stderr；参数不对归为 4
        return EXIT_OK if exc.code == 0 else EXIT_ENV
    handlers = {'guide': command_guide, 'upload': command_upload,
                'check': command_check, 'submit': command_submit}
    try:
        config_path = pathlib.Path.home() / '.easyfix' / 'intake.json'
        config = load_config(os.environ, config_path)
        code, data = handlers[args.command](config, args, opener)
    except ToolError as exc:
        _emit(stdout, {'ok': False, 'message': exc.message})
        return exc.code
    _emit(stdout, data)
    return code


if __name__ == '__main__':
    # Windows 上显式按 UTF-8 输出，避免中文乱码
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    sys.exit(main(sys.argv[1:]))
