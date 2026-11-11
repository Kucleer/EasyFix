"""本机测试环境：用真实的后端路由加一份临时内存库在本机跑起来，不连接正式环境。

只做测试工具，永远不会部署。数据在内存里，关掉就没了。运行：

    python cloudflare/scripts/local_dev_server.py [--port 8765] [--frontend-dir 路径] [--uploads-dir 路径]
        [--ocr-url 地址 --ocr-key-file 口令文件] [--llm-config 模型配置.json]

整页识别默认用假的识别主机和假的文本模型；给了 --ocr-url、--llm-config 才改用真实的。
"""

import argparse
import asyncio
import importlib
import json
import mimetypes
import pathlib
import re
import sqlite3
import sys
import tempfile
import urllib.error
import urllib.request
from datetime import datetime
from types import SimpleNamespace
from uuid import uuid4

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
sys.path.insert(0, str(ROOT / 'scripts'))

from fastapi import FastAPI, File, HTTPException, Request, UploadFile  # noqa: E402
from fastapi.responses import FileResponse, Response  # noqa: E402
from knowledge_invariants_test import SQLiteDB  # noqa: E402  复用生产异步接口的 sqlite 适配器
from knowledge_model import normalize_name_key  # noqa: E402

DEFAULT_PORT = 8765
HOST = '127.0.0.1'
SCHEMA_FILE = ROOT / 'scripts' / 'd1_schema_before_0011.sql'
MIGRATION_FILE = ROOT / 'migrations' / '0011_intake_papers.sql'
STARMAP_MIGRATION = ROOT / 'migrations' / '0012_starmap.sql'
STARMAP_SEED = ROOT / 'migrations' / '0013_starmap_seed.sql'
SCAN_MIGRATION = ROOT / 'migrations' / '0014_scan_page.sql'
CATALOG_FILE = ROOT / 'scripts' / 'knowledge_grade6_catalog.json'
# 挂载顺序与 main.py 一致：intake、scan 的固定路径要排在 questions 的 {question_id} 之前
ROUTER_MODULES = ('intake', 'papers', 'similar', 'catalog', 'knowledge', 'scan', 'questions', 'settings', 'analytics',
                  'practices', 'reports', 'starmap')
IMAGE_TYPES = ('image/jpeg', 'image/jpg', 'image/png', 'image/webp')
MAX_IMAGE_BYTES = 10 * 1024 * 1024
MAX_BATCH_FILES = 10
SUBJECTS = [(1, '数学'), (2, '英语')]
ERROR_TYPES = [('计算错误', 1), ('审题不清', 1), ('概念错误', 1), ('完全不会', 1), ('背诵拼写', 2), ('语法', 2)]


def configure_output():
    """把标准输出改成 utf-8，避免 Windows GBK 控制台打印中文时报错。"""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding='utf-8', errors='replace')
        except (AttributeError, ValueError):
            pass


# ---------------------------------------------------------------- 数据库


def seed_catalog(connection, subject_ids):
    """把考点目录写入库里：先一级后二级，二级的 parent_id 按 parent_code 对应。"""
    points = json.loads(CATALOG_FILE.read_text(encoding='utf-8'))['points']
    id_by_code = {}
    # 触发器要求父级先存在，所以按层级排序；同层保持目录文件里的顺序
    for item in sorted(points, key=lambda point: point['level']):
        parent_id = id_by_code[item['parent_code']] if item['level'] == 2 else None
        cursor = connection.execute(
            'INSERT INTO knowledge_point(code,name,name_key,subject_id,level,parent_id,sort_order,grade,deleted,'
            'created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,0,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)',
            (item['code'], item['name'], normalize_name_key(item['name']), subject_ids[item['subject']],
             item['level'], parent_id, int(item.get('sort_order') or 0), item.get('grade')))
        id_by_code[item['code']] = cursor.lastrowid


def build_connection():
    """建一份内存库：结构基线 + 0011、0012 迁移 + 种子数据 + 0013 星空种子，并模拟英语重新打标后的状态。"""
    # 测试客户端和 uvicorn 都会在别的线程里使用连接，单用户本机工具可以放开线程检查
    connection = sqlite3.connect(':memory:', check_same_thread=False)
    connection.row_factory = sqlite3.Row
    connection.executescript(SCHEMA_FILE.read_text(encoding='utf-8'))
    connection.executescript(MIGRATION_FILE.read_text(encoding='utf-8'))
    connection.executescript(STARMAP_MIGRATION.read_text(encoding='utf-8'))
    connection.executescript(SCAN_MIGRATION.read_text(encoding='utf-8'))
    connection.execute('INSERT INTO write_guard(id,revision,deleted) VALUES(1,0,0)')
    connection.execute('INSERT INTO knowledge_assert(id,guard,structure) VALUES(1,1,1)')
    config = {'data_revision': '0', 'taxonomy_version': '1', 'app': '{"default_grade":6,"default_semester":1}'}
    for name, value in config.items():
        connection.execute(
            'INSERT INTO runtime_config(name,value,deleted,updated_at) VALUES(?,?,0,CURRENT_TIMESTAMP)',
            (name, value))
    for subject_id, name in SUBJECTS:
        connection.execute('INSERT INTO subject(id,name,deleted) VALUES(?,?,0)', (subject_id, name))
    seed_catalog(connection, {name: subject_id for subject_id, name in SUBJECTS})
    # 星空种子（英语新语法体系、数学章节、连线），再用空映射执行重新打标，去掉旧英语考点，和发布后一致
    from starmap_retag import build_retag_sql
    connection.executescript(STARMAP_SEED.read_text(encoding='utf-8'))
    connection.executescript(build_retag_sql([]))
    for name, subject_id in ERROR_TYPES:
        connection.execute('INSERT INTO error_type(name,subject_id,deleted) VALUES(?,?,0)', (name, subject_id))
    connection.commit()
    return connection


# ---------------------------------------------------------------- 依赖云端存储的路由（本机改用上传目录）


def make_storage_key(filename):
    """生成 YYYY/MM/<8 位十六进制>_<文件名>，文件名里的路径分隔符换成下划线。"""
    name = (filename or 'image').replace('/', '_').replace('\\', '_')
    return datetime.now().strftime('%Y/%m/') + uuid4().hex[:8] + '_' + name


async def store_image(uploads_dir, file):
    """校验并把图片写入上传目录，返回与线上一致的字段；不合格时抛 400。"""
    if file.content_type not in IMAGE_TYPES:
        raise HTTPException(400, '不支持的图片类型')
    content = await file.read(MAX_IMAGE_BYTES + 1)
    if not content or len(content) > MAX_IMAGE_BYTES:
        raise HTTPException(400, '图片为空或超过10MB')
    key = make_storage_key(file.filename)
    target = uploads_dir / key
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(content)
    return {'path': key, 'image_path': key, 'original_filename': file.filename, 'size': len(content)}


def safe_child(base_dir, relative):
    """把相对路径解析到 base_dir 之内；越界、含反斜杠或不是文件时返回 None。"""
    if '\\' in relative or any(part in ('', '.', '..') for part in relative.split('/')):
        return None
    base = base_dir.resolve()
    target = (base / relative).resolve()
    # 解析符号链接后仍必须在目录之内
    if base not in target.parents or not target.is_file():
        return None
    return target


def add_storage_routes(app, uploads_dir):
    """加上学科列表和三条依赖云端存储的路由。"""

    @app.get('/api/subjects')
    async def subjects(request: Request):
        """读取未删除的学科。"""
        return await request.scope['env'].DB.all('SELECT * FROM subject WHERE deleted=0 ORDER BY id')

    @app.post('/api/upload/batch-simple')
    async def upload_batch(files: list[UploadFile] = File(...)):
        """保存一批原图，逐项返回失败原因。"""
        if len(files) > MAX_BATCH_FILES:
            raise HTTPException(422, '每批最多10张图片')
        items = []
        for file in files:
            try:
                items.append({**await store_image(uploads_dir, file), 'success': True})
            except HTTPException as error:
                items.append({'original_filename': file.filename, 'success': False, 'error': error.detail})
        success = sum(item['success'] for item in items)
        return {'images': items, 'total_count': len(items), 'success_count': success,
                'failed_count': len(items) - success}

    @app.post('/api/upload/file')
    async def upload_file(file: UploadFile = File(...)):
        """保存单个原图。"""
        item = await store_image(uploads_dir, file)
        return {'path': item['path'], 'original_filename': item['original_filename'], 'size': item['size']}

    @app.get('/uploads/{key:path}')
    async def read_upload(key: str):
        """读取上传目录里的文件，拒绝路径穿越。"""
        target = safe_child(uploads_dir, key)
        if target is None:
            raise HTTPException(404, '附件不存在')
        content_type = mimetypes.guess_type(target.name)[0] or 'application/octet-stream'
        return Response(target.read_bytes(), media_type=content_type, headers={'X-Content-Type-Options': 'nosniff'})


def add_frontend_routes(app, frontend_dir):
    """提供前端静态文件；其余非接口的 GET 请求返回 index.html，让单页应用自己处理路由。"""

    @app.get('/{path:path}')
    async def frontend(path: str):
        """先找同名静态文件，找不到再回退到 index.html。"""
        if path.startswith(('api/', 'uploads/')) or path in ('api', 'uploads'):
            raise HTTPException(404, '接口不存在')
        target = safe_child(frontend_dir, path) if path else None
        return FileResponse(target or frontend_dir / 'index.html')


# ---------------------------------------------------------------- 整页识别：识别主机与文本模型（假的和真的）

FAKE_OCR_TEXT = (
    '一、计算题\n'
    '1. 计算 3/4 × 2/3 = ?  孩子写：1/3\n'
    '2. 计算 1/2 ÷ 1/4 = ?  孩子写：1/8\n'
    '3. 计算 1+1 = ?  孩子写：2\n'
    '4. 一块地的 5/131 种了玉米，种玉米的面积占全部的几分之几？  孩子写：5/13')
HOST_KEY_HEADER = 'X-EasyFix-OCR-Key'


class LocalOcrBase:
    """本机识别客户端的公共部分：照片从上传目录读（线上是从 R2 读）。"""

    uploads_dir = None

    async def read_image(self, env, key):
        """从上传目录读照片，返回 (字节, 类型)；找不到返回 None。"""
        target = safe_child(self.uploads_dir, key) if self.uploads_dir is not None else None
        if target is None:
            return None
        content_type = mimetypes.guess_type(target.name)[0] or 'application/octet-stream'
        return target.read_bytes(), ('image/jpeg' if content_type == 'image/jpg' else content_type)


class FakeOcr(LocalOcrBase):
    """假的识别主机：/health 永远可用，/ocr 永远返回固定的一页数学题文字（含一处 5/131）。"""

    async def fetch_health(self, env, timeout_seconds):
        """返回和真实主机一致的健康检查结果。"""
        return 200, {'ok': True, 'contract': 1, 'ollama': True, 'model': 'fake'}

    async def fetch_ocr(self, env, content, content_type, mode, timeout_seconds):
        """返回固定文字，忽略图片内容。"""
        return 200, {'ok': True, 'contract': 1, 'mode': mode, 'text': FAKE_OCR_TEXT,
                     'segments': FAKE_OCR_TEXT.split('\n'), 'elapsed_ms': 1}


def http_call(url, method, headers, body, timeout_seconds):
    """同步发一次 HTTP 请求，返回 (状态码, JSON 对象或 None)；连不上、超时返回 (0, None)，永不抛异常。"""
    request = urllib.request.Request(url, data=body, method=method, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            status, raw = response.status, response.read()
    except urllib.error.HTTPError as error:
        # 4xx、5xx 也要读响应体：主机的 busy 等信息放在里面
        status = error.code
        try:
            raw = error.read()
        except Exception:
            raw = b''
    except Exception:
        return 0, None
    try:
        parsed = json.loads(raw.decode('utf-8'))
    except ValueError:
        return status, None
    return status, parsed if isinstance(parsed, dict) else None


class HttpOcr(LocalOcrBase):
    """真实的识别主机客户端：直接用 urllib 访问主机的 /health 和 /ocr（本机开发用，线上走 Workers VPC）。"""

    def __init__(self, url, key):
        self.url = url.rstrip('/')
        self.key = key

    async def fetch_health(self, env, timeout_seconds):
        """查询主机健康状态，返回 (状态码, JSON)。"""
        return await asyncio.to_thread(http_call, self.url + '/health', 'GET',
                                       {HOST_KEY_HEADER: self.key}, None, timeout_seconds)

    async def fetch_ocr(self, env, content, content_type, mode, timeout_seconds):
        """把图片字节发给主机识别，返回 (状态码, JSON)。"""
        headers = {HOST_KEY_HEADER: self.key, 'Content-Type': content_type}
        return await asyncio.to_thread(http_call, self.url + '/ocr?mode=' + str(mode), 'POST',
                                       headers, content, timeout_seconds)


def read_text_file(path):
    """读文本文件，去掉 UTF-8 BOM。"""
    return pathlib.Path(path).read_text(encoding='utf-8-sig')


def catalog_point_ids(prompt):
    """从提示词的考点清单里取编号：清单行的格式是"  编号 名称"。"""
    return [int(number) for number in re.findall(r'^ {2}(\d+) ', prompt, flags=re.M)]


async def fake_generate_json(request, prompt):
    """假的文本模型：整页提示词返回 3 道题，补题提示词返回补充字段。

    3 道题是：1 道做错、1 道做错且读图有问题（broken_formula）、1 道做对。
    考点编号从提示词的清单里取；清单为空时留空。
    """
    ids = catalog_point_ids(prompt)
    knowledge = {'knowledge_point_ids': ids[:1], 'primary_knowledge_point_id': ids[0] if ids else None}
    if '<<<OCR' not in prompt:
        # 单题补全提示词
        return {'answer': '1/2', 'analysis': '先约分再相乘。', 'error_types': ['计算错误'], 'difficulty': 2,
                **knowledge}
    return {'questions': [
        {'question_no': '1', 'parsed_question': '计算 \\(\\frac{3}{4}\\times\\frac{2}{3}\\)', 'wrong_answer': '1/3',
         'verdict': 'wrong', 'reason': '应为 1/2', 'flags': [], 'answer': '1/2', 'analysis': '先约分再相乘。',
         'error_types': ['计算错误'], 'difficulty': 2, **knowledge},
        {'question_no': '4', 'parsed_question': '一块地的 \\(\\frac{5}{131}\\) 种了玉米', 'wrong_answer': '5/13',
         'verdict': 'wrong', 'reason': '分母像是读错了', 'flags': ['broken_formula'], 'answer': '5/13',
         'analysis': '按原图核对分数。', 'error_types': ['审题不清'], 'difficulty': 3, **knowledge},
        {'question_no': '3', 'parsed_question': '计算 1+1', 'wrong_answer': '2', 'verdict': 'right',
         'reason': '孩子写 2，和计算结果一致', 'flags': []},
    ]}


def make_http_generate_json(config):
    """按 settings.generate_json 的请求格式，用 urllib 调真实的文本模型；config 来自 --llm-config。"""

    def call_model(prompt):
        """同步调一次模型，返回解析后的 JSON；失败抛和线上一样的 HTTPException。"""
        if not config.get('api_key') or not config.get('base_url'):
            raise HTTPException(503, '请先配置文本模型')
        anthropic = config.get('provider') == 'anthropic' or '/anthropic' in config['base_url']
        base = config['base_url'].rstrip('/')
        if anthropic:
            url = base + ('/messages' if base.endswith('/v1') else '/v1/messages')
        else:
            url = base + '/chat/completions'
        system = '你是严谨的学习辅导助手。仅返回有效JSON。数学公式使用带边界的LaTeX，保留反斜杠。'
        body = {'model': config.get('model'), 'max_tokens': 6000, 'messages': [{'role': 'user', 'content': prompt}]}
        headers = ({'x-api-key': config['api_key'], 'anthropic-version': '2023-06-01'} if anthropic
                   else {'Authorization': 'Bearer ' + config['api_key']})
        headers['Content-Type'] = 'application/json'
        if anthropic:
            body['system'] = system
            body['thinking'] = {'type': 'disabled'}
        else:
            body['messages'].insert(0, {'role': 'system', 'content': system})
            body['temperature'] = 0.6
        request = urllib.request.Request(url, data=json.dumps(body, ensure_ascii=False).encode('utf-8'),
                                         method='POST', headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                status, text = response.status, response.read().decode('utf-8')
        except urllib.error.HTTPError as error:
            status, text = error.code, ''
        except Exception:
            status, text = 599, ''  # 连不上、超时都按请求失败处理
        if status >= 400:
            raise HTTPException(502, '文本模型请求失败，请检查模型配置和余额')
        try:
            result = json.loads(text)
            if anthropic:
                content = ''.join(block.get('text', '') for block in result.get('content', [])
                                  if block.get('type') == 'text').strip()
            else:
                content = result['choices'][0]['message']['content'].strip()
            if content.startswith('```'):
                content = content.split('\n', 1)[1].rsplit('```', 1)[0]
            return json.loads(content)
        except (KeyError, IndexError, ValueError, AttributeError):
            raise HTTPException(502, '模型没有返回有效的结构化内容')

    async def generate_json(request, prompt):
        """异步包装：把阻塞的 HTTP 调用放到线程里。"""
        return await asyncio.to_thread(call_model, prompt)

    return generate_json


def install_scan_dependencies(uploads_dir, ocr_url, ocr_key, llm_config):
    """给 scan 模块装上识别主机和文本模型：没给地址或配置就用假的。"""
    ocr = HttpOcr(ocr_url, ocr_key or '') if ocr_url else FakeOcr()
    ocr.uploads_dir = uploads_dir
    scan = importlib.import_module('scan')
    scan.ocr_client = ocr
    scan.generate_json = make_http_generate_json(llm_config) if llm_config else fake_generate_json


# ---------------------------------------------------------------- 应用


async def skip_validation(request, texts):
    """本机不校验公式：什么都不做。"""
    return None


def mount_routers(app):
    """把真实路由模块逐个装进应用；导入失败的跳过并打印说明，返回已挂载的模块名。"""
    mounted = []
    for name in ROUTER_MODULES:
        try:
            module = importlib.import_module(name)
        except Exception as error:  # 依赖只在 Cloudflare 上才有的包等
            print('跳过路由模块 %s：%s' % (name, error))
            continue
        # 和 intake_test.py 的 fake_request 同一个办法：数据库对象由中间件放进 env，这里原样返回
        if hasattr(module, 'Database'):
            module.Database = lambda binding: binding
        if hasattr(module, 'validate_math'):
            module.validate_math = skip_validation
        app.include_router(module.router)
        mounted.append(name)
    try:
        importlib.import_module('pdf').validate_math = skip_validation  # questions、similar 在函数里按需导入
    except Exception as error:
        print('跳过公式校验替换 pdf：%s' % error)
    return mounted


def build_app(connection, uploads_dir, frontend_dir, ocr_url=None, ocr_key=None, llm_config=None):
    """把真实的路由装进一个本机应用；整页识别的主机和模型默认用假的。"""
    uploads_dir = pathlib.Path(uploads_dir)
    uploads_dir.mkdir(parents=True, exist_ok=True)
    database = SQLiteDB(connection)
    app = FastAPI(title='EasyFix 本机测试环境')

    @app.middleware('http')
    async def inject_env(request: Request, call_next):
        """给每个请求放上 env（只有 DB），不做任何登录校验。"""
        request.scope['env'] = SimpleNamespace(DB=database)
        return await call_next(request)

    mounted = mount_routers(app)
    if 'scan' in mounted:
        install_scan_dependencies(uploads_dir, ocr_url, ocr_key, llm_config)
    add_storage_routes(app, uploads_dir)
    if frontend_dir is not None:
        add_frontend_routes(app, pathlib.Path(frontend_dir))
    return app


# ---------------------------------------------------------------- 命令行


def parse_arguments(argv):
    """解析命令行参数；不提供 --host，只监听 127.0.0.1。"""
    parser = argparse.ArgumentParser(description='EasyFix 本机测试环境（临时内存库，不连接正式库）')
    parser.add_argument('--port', type=int, default=DEFAULT_PORT)
    parser.add_argument('--frontend-dir', default=None)
    parser.add_argument('--uploads-dir', default=None)
    parser.add_argument('--ocr-url', default=None, help='真实识别主机的地址；不给就用假的')
    parser.add_argument('--ocr-key-file', default=None, help='存放识别主机口令的文件')
    parser.add_argument('--llm-config', default=None,
                        help='文本模型配置 JSON（provider、api_key、base_url、model）；不给就用假的')
    return parser.parse_args(argv)


def main(argv):
    """解析参数并用 uvicorn 在 127.0.0.1 上启动。"""
    configure_output()
    arguments = parse_arguments(argv)
    frontend_dir = pathlib.Path(arguments.frontend_dir) if arguments.frontend_dir else None
    if frontend_dir is None and (ROOT.parent / 'frontend' / 'dist' / 'index.html').exists():
        frontend_dir = ROOT.parent / 'frontend' / 'dist'
    uploads_dir = (pathlib.Path(arguments.uploads_dir) if arguments.uploads_dir
                   else pathlib.Path(tempfile.mkdtemp(prefix='easyfix_uploads_')))
    ocr_key = read_text_file(arguments.ocr_key_file).strip() if arguments.ocr_key_file else None
    llm_config = json.loads(read_text_file(arguments.llm_config)) if arguments.llm_config else None
    app = build_app(build_connection(), uploads_dir, frontend_dir, arguments.ocr_url, ocr_key, llm_config)
    if arguments.ocr_url and not arguments.ocr_key_file:
        print('警告：给了 --ocr-url 但没有 --ocr-key-file，访问识别主机时不会带口令，可能被拒绝。')
    print('整页识别：识别主机%s，文本模型%s' % ('真实' if arguments.ocr_url else '假的', '真实' if llm_config else '假的'))
    print('本机测试环境：数据在内存里，关掉就没了；不连接正式库。')
    print('访问地址：http://%s:%d' % (HOST, arguments.port))
    print('上传目录：%s；前端目录：%s' % (uploads_dir, frontend_dir or '（无，只提供接口）'))
    import uvicorn
    uvicorn.run(app, host=HOST, port=arguments.port, log_level='warning')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
