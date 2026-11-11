"""整页识别回归脚本：在识别主机上，用真实的识别服务和真实的文本模型，把一批回归图完整走一遍。

【怎么跑】把整个仓库（或至少 cloudflare/src/scan_model.py 和本目录）带到那台主机上，在仓库根目录执行：

    python cloudflare/scripts/scan_regression.py --images <回归图目录> ^
        --ocr-key-file <识别口令文件> --llm-config <文本模型配置.json> ^
        [--ocr-url http://127.0.0.1:11436] [--out <结果目录>] ^
        [--subject 数学 --grade 6 --semester 1] [--no-rescan]

- 只依赖 Python 自带库和主机上已有的 httpx，不需要 fastapi，也不起本机测试服务。
- "读图、整理、需要时重扫一次、再整理"的先后顺序和判断用的是 scan_model.run_page，
  和线上后端逐步推进时是同一套函数；提示词、清洗规则、模型参数（SCAN_MAX_TOKENS、SCAN_TEMPERATURE）
  也都来自 scan_model，所以结果和线上一致。
- 先查一次识别服务的 /health，不可用就不跑。读图直接调 <ocr-url>/ocr?mode=normal|enhanced，
  请求体是图片原始字节，请求头带 X-EasyFix-OCR-Key；主机忙时按约定等 2 秒重试，最多 3 次。
- 文本模型的调用方式照抄后端 settings.generate_json（OpenAI 兼容接口或 Anthropic 接口），
  配置文件是一个 JSON 对象：{"provider": "...", "api_key": "...", "base_url": "https://...", "model": "..."}。
- 口令和模型密钥只从你给的文件里读，不会打印。
- 回归图和结果都带学生信息：--images 和 --out 都不允许放在仓库目录里。
  --out 不给时存到 %USERPROFILE%\\.easyfix\\scan-regression\\<日期时间>\\ 。
- 一张图出错（读不了、网络异常等）不影响其他图：汇总里记一行 error，继续往下跑。

【考点清单】线上用的是数据库里的考点；主机上没有数据库，这里读仓库里的
cloudflare/scripts/knowledge_grade6_catalog.json，只取 --subject 学科、符合年级学期的二级考点。
考点编号的规则：编号 = 这个考点在文件 points 数组里的位置（从 1 开始数，一级、二级都算位置）。
只要不改这个文件，同一个考点每次的编号都一样；对照结果里的考点编号时按这个规则回查文件。
这些编号和线上数据库的编号不同，只在本脚本里有意义。
错因清单用本文件里的 ERROR_TYPES（和本机测试服务的一样）。

【跑完得到什么】结果目录里有：
- 每张图一个 <图名>.json：状态、题目草稿、识别原文 ocr_text、重扫后的原文 ocr_text_enhanced、
  是否重扫、各步用时、失败提示、总用时；
- summary.csv：每页的状态、题数、做错数、拿不准数、带提示数、是否重扫、各步用时、总用时；
- 对照表.md：每页一段，列出模型判错的题、拿不准的题、判对的题，方便人工对着原图核对。
最后在屏幕上打印每页用时的中位数和最大值。

【跑完之后人工评分】（设计文档 12.2 第 1 条；不设及格线，数字交给用户决定能不能给妈妈用）
拿 对照表.md 对着原图和交接文档（ocr-ollama-handoff.md）里人工核对过的 61 道目标题，数出：
  1. 关键题干完全正确的道数、有关键错误的道数（和交接文档里的 41 / 6 比）；
  2. 模型判断做错、而且学生确实做错的道数；
  3. 做错了却被判成做对的道数（漏判）：61 道目标题都是真错题，被判成做对就算漏判；
  4. 做对了却被判成做错的道数（误判）：模型判错但不在 61 道里的题，要对着原图看一眼，
     可能是误判，也可能是当初没录的错题；
  5. 重扫触发了几页（summary.csv 的"是否重扫"列）、救回了几道关键读错的题
     （对比 JSON 里 ocr_text 和 ocr_text_enhanced 两份原文）；
  6. 每页用时的中位数和最大值（脚本最后会打印）。
"""

import argparse
import asyncio
import csv
import json
import pathlib
import statistics
import sys
import time
from datetime import datetime

ROOT = pathlib.Path(__file__).resolve().parents[1]
REPO_ROOT = ROOT.parent
sys.path.insert(0, str(ROOT / 'src'))

import scan_model  # noqa: E402  只用标准库的纯逻辑：识别顺序、提示词、清洗规则

IMAGE_TYPES = {'.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.png': 'image/png', '.webp': 'image/webp'}
STEP_KEYS = ('read_ms', 'analyze_ms', 'rescan_ms', 'analyze2_ms', 'host_read_ms', 'host_rescan_ms')
CSV_HEADER = (['图名', '状态', '题数', '做错数', '拿不准数', '带提示数', '是否重扫']
              + list(STEP_KEYS) + ['总用时_ms', '备注'])
DEFAULT_OUT_ROOT = pathlib.Path.home() / '.easyfix' / 'scan-regression'
DEFAULT_OCR_URL = 'http://127.0.0.1:11436'
HOST_KEY_HEADER = 'X-EasyFix-OCR-Key'
CATALOG_FILE = ROOT / 'scripts' / 'knowledge_grade6_catalog.json'
# 错因清单，照抄本机测试服务 local_dev_server.ERROR_TYPES：(名称, 学科编号)，学科编号见 SUBJECT_IDS
ERROR_TYPES = [('计算错误', 1), ('审题不清', 1), ('概念错误', 1), ('完全不会', 1), ('背诵拼写', 2), ('语法', 2)]
SUBJECT_IDS = {'数学': 1, '英语': 2}
# 文本模型的调用参数，和 settings.generate_json 一致
MODEL_TIMEOUT_SECONDS = 120
MODEL_SYSTEM_PROMPT = '你是严谨的学习辅导助手。仅返回有效JSON。数学公式使用带边界的LaTeX，保留反斜杠。'
DEFAULT_TEMPERATURE = 0.6  # settings.generate_json 的默认随机度：Anthropic 接口只在不同于它时才传
MODEL_HTTP_FAILED_TEXT = '文本模型请求失败，请检查模型配置和余额'
MODEL_INVALID_TEXT = '模型没有返回有效的结构化内容'


class RegressionError(Exception):
    """脚本自己能说清楚的错误：直接把消息打印给用户，不打印堆栈。"""


class ModelError(Exception):
    """文本模型调用失败；detail 是给人看的一句话（和线上后端的提示文字一致）。"""

    def __init__(self, detail):
        super().__init__(detail)
        self.detail = detail


# ---------------------------------------------------------------- 路径与配置


def configure_output():
    """把标准输出改成 utf-8，避免 Windows GBK 控制台打印中文时报错。"""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding='utf-8', errors='replace')
        except (AttributeError, ValueError):
            pass


def is_inside_repo(path):
    """路径解析后是否在仓库目录之内（含仓库目录本身）。"""
    resolved = pathlib.Path(path).resolve()
    return resolved == REPO_ROOT or REPO_ROOT in resolved.parents


def check_outside_repo(path, label):
    """路径在仓库里就拒绝运行：图片和结果带学生信息，不能进仓库。"""
    if is_inside_repo(path):
        raise RegressionError('%s 不能放在仓库目录里（%s）：图片和结果含学生信息。请换一个仓库外的目录。'
                              % (label, REPO_ROOT))


def list_images(images_dir):
    """目录里的图片，按文件名顺序；一张都没有就报错。"""
    images_dir = pathlib.Path(images_dir)
    if not images_dir.is_dir():
        raise RegressionError('--images 不是一个目录：%s' % images_dir)
    images = sorted((path for path in images_dir.iterdir() if path.suffix.lower() in IMAGE_TYPES),
                    key=lambda path: path.name)
    if not images:
        raise RegressionError('目录里没有 .jpg/.jpeg/.png/.webp 图片：%s' % images_dir)
    return images


def read_config_file(path, label, parse_json=False):
    """读口令或配置文件（去掉 BOM 和首尾空白）；找不到、读不了、JSON 不对都给中文提示，不打印文件内容。"""
    try:
        text = pathlib.Path(path).read_text(encoding='utf-8-sig')
    except (OSError, UnicodeDecodeError):
        raise RegressionError('读不了 %s 指定的文件：%s' % (label, path))
    if not parse_json:
        text = text.strip()
        if not text:
            raise RegressionError('%s 指定的文件是空的：%s' % (label, path))
        return text
    try:
        config = json.loads(text)
    except ValueError:
        raise RegressionError('%s 指定的文件不是有效的 JSON：%s' % (label, path))
    if not isinstance(config, dict):
        raise RegressionError('%s 指定的文件内容应是一个 JSON 对象：%s' % (label, path))
    for key in ('api_key', 'base_url'):
        if not isinstance(config.get(key), str) or not config[key].strip():
            raise RegressionError('%s 指定的文件里缺少 %s：%s' % (label, key, path))
    return config


def load_catalog(subject_name, grade, semester, catalog_file=CATALOG_FILE):
    """从考点目录文件拼出和后端 load_catalog 一样的结构：[{'id','name','points':[{'id','name'}]}]。

    编号 = 考点在文件 points 数组里的位置（从 1 开始），见文件开头的说明。
    只取这个学科的二级考点；年级、学期为空表示不限（和后端一致）。
    """
    points = json.loads(pathlib.Path(catalog_file).read_text(encoding='utf-8'))['points']
    # 编号按文件里的位置定；排列顺序和后端一样按 sort_order（相同时按编号）
    numbered = sorted(enumerate(points, start=1), key=lambda pair: (int(pair[1].get('sort_order') or 0), pair[0]))
    groups = {}
    for index, point in numbered:
        if point.get('subject') == subject_name and point.get('level') == 1:
            groups[point['code']] = {'id': index, 'name': point['name'], 'points': []}
    for index, point in numbered:
        if point.get('subject') != subject_name or point.get('level') != 2:
            continue
        if grade is not None and point.get('grade') not in (None, grade):
            continue
        if semester is not None and point.get('semester') not in (None, semester):
            continue
        group = groups.get(point.get('parent_code'))
        if group is not None:
            group['points'].append({'id': index, 'name': point['name']})
    return [group for group in groups.values() if group['points']]


def load_error_type_names(subject_name):
    """这个学科可用的错因名称。"""
    subject_id = SUBJECT_IDS.get(subject_name)
    return {name for name, owner in ERROR_TYPES if owner == subject_id}


# ---------------------------------------------------------------- 识别主机和文本模型（真实的，用 httpx）


def parse_json_body(response):
    """把响应体解析成 JSON 对象；不是 JSON 对象时返回 None。"""
    try:
        parsed = response.json()
    except ValueError:
        return None
    return parsed if isinstance(parsed, dict) else None


class HostClient:
    """真实的识别主机客户端：health() 和 ocr() 都返回 (状态码, JSON 对象或 None)，连不上、超时返回 (0, None)。"""

    def __init__(self, url, key, http):
        self.url = url.rstrip('/')
        self.key = key
        self.http = http  # httpx.Client

    def _send(self, method, path, timeout_seconds, content=None, content_type=None):
        """发一次请求；任何网络异常都收成 (0, None)，只打印异常类型名，不打印口令和内容。"""
        headers = {HOST_KEY_HEADER: self.key}
        if content_type:
            headers['Content-Type'] = content_type
        try:
            response = self.http.request(method, self.url + path, headers=headers, content=content,
                                         timeout=timeout_seconds)
        except Exception as error:
            print('  识别服务请求 %s 失败：%s' % (path.split('?')[0], type(error).__name__))
            return 0, None
        return response.status_code, parse_json_body(response)

    def health(self):
        """查识别服务的健康状态。"""
        return self._send('GET', '/health', scan_model.HEALTH_TIMEOUT_SECONDS)

    def ocr(self, content, content_type, mode):
        """把图片原始字节发给主机识别。"""
        return self._send('POST', '/ocr?mode=' + mode, scan_model.HOST_TIMEOUT_SECONDS[mode],
                          content=content, content_type=content_type)


def build_host_client(url, key):
    """建真实的识别主机客户端（httpx 只在这里导入，测试时不需要装）。"""
    import httpx
    return HostClient(url, key, httpx.Client())


def build_model_request(config, prompt):
    """按 settings.generate_json 的格式拼模型请求，返回 (地址, 请求头, 请求体, 是否 Anthropic 接口)。

    用整页识别的参数：max_tokens = SCAN_MAX_TOKENS，temperature = SCAN_TEMPERATURE。
    """
    anthropic = config.get('provider') == 'anthropic' or '/anthropic' in config['base_url']
    base = config['base_url'].rstrip('/')
    if anthropic:
        url = base + ('/messages' if base.endswith('/v1') else '/v1/messages')
        headers = {'x-api-key': config['api_key'], 'anthropic-version': '2023-06-01'}
    else:
        url = base + '/chat/completions'
        headers = {'Authorization': 'Bearer ' + config['api_key']}
    headers['Content-Type'] = 'application/json'
    body = {'model': config.get('model'), 'max_tokens': scan_model.SCAN_MAX_TOKENS,
            'messages': [{'role': 'user', 'content': prompt}]}
    if anthropic:
        body['system'] = MODEL_SYSTEM_PROMPT
        body['thinking'] = {'type': 'disabled'}
        if scan_model.SCAN_TEMPERATURE != DEFAULT_TEMPERATURE:
            body['temperature'] = scan_model.SCAN_TEMPERATURE
    else:
        body['messages'].insert(0, {'role': 'system', 'content': MODEL_SYSTEM_PROMPT})
        body['temperature'] = scan_model.SCAN_TEMPERATURE
    return url, headers, body, anthropic


def parse_model_reply(text, anthropic):
    """从模型响应里取出 JSON 内容（去掉 ``` 围栏）；不是有效内容时抛 ModelError，和线上一样。"""
    try:
        result = json.loads(text)
        if anthropic:
            content = ''.join(block.get('text', '') for block in result.get('content', [])
                              if block.get('type') == 'text').strip()
        else:
            content = result['choices'][0]['message']['content'].strip()
        # 和线上一样：去掉围栏、补好 LaTeX 反斜杠再解析；解析不出时异常链里带出错位置附近的原文
        return scan_model.parse_model_json(content)
    except (KeyError, IndexError, ValueError, TypeError, AttributeError) as error:
        raise ModelError(MODEL_INVALID_TEXT) from error


class ModelClient:
    """真实的文本模型客户端：model(提示词) 返回解析后的 JSON，失败抛 ModelError（网络异常原样抛出）。"""

    def __init__(self, config, http):
        self.config = config
        self.http = http  # httpx.Client

    def __call__(self, prompt):
        """调一次模型。"""
        url, headers, body, anthropic = build_model_request(self.config, prompt)
        response = self.http.post(url, headers=headers, content=json.dumps(body, ensure_ascii=False).encode('utf-8'),
                                  timeout=MODEL_TIMEOUT_SECONDS)
        if response.status_code >= 400:
            raise ModelError(MODEL_HTTP_FAILED_TEXT)
        return parse_model_reply(response.text, anthropic)


def build_model_client(config):
    """建真实的文本模型客户端（httpx 只在这里导入）。"""
    import httpx
    return ModelClient(config, httpx.Client())


# ---------------------------------------------------------------- 跑一张图


async def recognize_image(image_path, host, model, context, rescan_enabled):
    """把一张图交给 scan_model.run_page 走完整流程，返回它的结果。

    context 是 (学科名, 年级, 学期, 考点清单, 错因名称集合)。
    """
    subject_name, grade, semester, catalog, error_type_names = context
    content = image_path.read_bytes()
    content_type = IMAGE_TYPES[image_path.suffix.lower()]
    catalog_ids = {point['id'] for group in catalog for point in group['points']}

    async def read_text(mode):
        """读一次图；主机忙时按约定等待重试。"""

        async def fetch():
            """调一次主机的 /ocr。"""
            return host.ocr(content, content_type, mode)

        return await scan_model.read_with_retries(fetch, asyncio.sleep)

    async def analyze(ocr_text, enhanced_text):
        """拼提示词、调模型、清洗结果；模型失败时抛异常，由 run_page 处理。"""
        prompt = scan_model.build_page_prompt(subject_name, grade, semester, ocr_text, enhanced_text,
                                              catalog, sorted(error_type_names))
        return scan_model.clean_items(model(prompt), catalog_ids, error_type_names)

    return await scan_model.run_page(read_text, analyze, rescan_enabled)


# ---------------------------------------------------------------- 输出


def summarize_page(name, page, total_ms, note=''):
    """把一页整理成 summary.csv 的一行。"""
    items = page['items']
    timings = page['timings']
    return ([name, page['status'], len(items),
             sum(1 for item in items if item.get('verdict') == 'wrong'),
             sum(1 for item in items if item.get('verdict') == 'unsure'),
             sum(1 for item in items if item.get('flags')),
             '是' if page['rescan_used'] == 1 else '否']
            + [timings.get(key, '') for key in STEP_KEYS] + [total_ms, note])


def describe_item(item):
    """对照表里一道题的一行：题号、题干开头、学生的答案、原因、提示。"""
    text = (item.get('parsed_question') or '').replace('\n', ' ')[:40]
    line = '- 第 %s 题：%s' % (item.get('question_no') or '?', text)
    if item.get('wrong_answer'):
        line += '；学生写：%s' % item['wrong_answer']
    if item.get('reason'):
        line += '；原因：%s' % item['reason']
    if item.get('flags'):
        line += '；提示：%s' % '、'.join(item['flags'])
    return line


def make_comparison_section(name, page):
    """对照表里一页的一段：模型判错的、拿不准的、判对的题。"""
    lines = ['## %s（%s%s）' % (name, page['status'], '，重扫过' if page['rescan_used'] == 1 else '')]
    if page.get('error'):
        lines.append('失败提示：%s' % page['error'])
    for title, verdict in (('模型判错', 'wrong'), ('拿不准', 'unsure'), ('模型判对', 'right')):
        group = [item for item in page['items'] if item.get('verdict') == verdict]
        lines.append('')
        lines.append('### %s（%d 道）' % (title, len(group)))
        lines.extend(describe_item(item) for item in group)
    return '\n'.join(lines) + '\n'


def make_error_section(name, message):
    """对照表里一张出错图的一段。"""
    return '## %s（error）\n备注：%s\n' % (name, message)


def print_timing_summary(totals_ms):
    """打印每页总用时的中位数和最大值。"""
    if not totals_ms:
        return
    print('每页总用时：中位数 %.1f 秒，最大 %.1f 秒（共 %d 页）'
          % (statistics.median(totals_ms) / 1000, max(totals_ms) / 1000, len(totals_ms)))


def write_outputs(out_dir, rows, sections):
    """写 summary.csv（utf-8-sig，Excel 直接打开不乱码）和 对照表.md。"""
    with open(out_dir / 'summary.csv', 'w', encoding='utf-8-sig', newline='') as file:
        writer = csv.writer(file)
        writer.writerow(CSV_HEADER)
        writer.writerows(rows)
    (out_dir / '对照表.md').write_text('# 整页识别对照表\n\n' + '\n'.join(sections), encoding='utf-8')


# ---------------------------------------------------------------- 主流程


def parse_arguments(argv):
    """解析命令行参数。"""
    parser = argparse.ArgumentParser(description='整页识别回归脚本（用真实识别服务和文本模型跑一批图）')
    parser.add_argument('--images', required=True, help='回归图目录（不能在仓库里）')
    parser.add_argument('--ocr-url', default=DEFAULT_OCR_URL, help='识别服务地址，默认 %s' % DEFAULT_OCR_URL)
    parser.add_argument('--ocr-key-file', required=True, help='存放识别服务口令的文件')
    parser.add_argument('--llm-config', required=True, help='文本模型配置 JSON（provider、api_key、base_url、model）')
    parser.add_argument('--out', default=None, help='结果目录（不能在仓库里）；默认放在用户目录的 .easyfix 下')
    parser.add_argument('--subject', default='数学')
    parser.add_argument('--grade', type=int, default=6)
    parser.add_argument('--semester', type=int, default=1)
    parser.add_argument('--no-rescan', action='store_true', help='关掉兜底重扫（和后端的 SCAN_RESCAN=off 一样）')
    return parser.parse_args(argv)


def run_regression(arguments, make_host=build_host_client, make_model=build_model_client):
    """检查路径和配置、确认识别服务可用、逐张跑图并写出结果；返回 0。

    make_host(地址, 口令)、make_model(配置) 建客户端，测试时换成假的。
    """
    check_outside_repo(arguments.images, '--images')
    out_dir = (pathlib.Path(arguments.out) if arguments.out
               else DEFAULT_OUT_ROOT / datetime.now().strftime('%Y%m%d-%H%M%S'))
    check_outside_repo(out_dir, '--out')
    images = list_images(arguments.images)
    ocr_key = read_config_file(arguments.ocr_key_file, '--ocr-key-file')
    llm_config = read_config_file(arguments.llm_config, '--llm-config', parse_json=True)
    if arguments.subject not in SUBJECT_IDS:
        raise RegressionError('不认识的学科：%s（可选：%s）' % (arguments.subject, '、'.join(SUBJECT_IDS)))
    catalog = load_catalog(arguments.subject, arguments.grade, arguments.semester)
    context = (arguments.subject, arguments.grade, arguments.semester, catalog,
               load_error_type_names(arguments.subject))

    try:
        host = make_host(arguments.ocr_url, ocr_key)
        model = make_model(llm_config)
    except ImportError:
        raise RegressionError('这台机器上没有装 httpx（pip install httpx）。')
    status, body = host.health()
    if not scan_model.interpret_health(status, body):
        raise RegressionError('识别服务不可用（%s/health 没有返回可用、或约定版本不是 %d）。请先确认服务在运行。'
                              % (arguments.ocr_url.rstrip('/'), scan_model.CONTRACT_VERSION))
    out_dir.mkdir(parents=True, exist_ok=True)
    print('识别服务可用，共 %d 张图，重扫%s' % (len(images), '关闭' if arguments.no_rescan else '开启'))

    rows, sections, totals_ms = [], [], []
    for index, image_path in enumerate(images, start=1):
        started = time.monotonic()
        try:
            page = asyncio.run(recognize_image(image_path, host, model, context, not arguments.no_rescan))
        except Exception as error:
            # 一张图出错不影响其他图：记一行 error，继续往下跑（只记异常类型和说明，不含口令）
            message = '%s：%s' % (type(error).__name__, error)
            rows.append([image_path.name, 'error'] + [''] * (len(CSV_HEADER) - 3) + [message])
            sections.append(make_error_section(image_path.name, message))
            print('[%d/%d] %s：出错，%s' % (index, len(images), image_path.name, message))
            continue
        total_ms = int((time.monotonic() - started) * 1000)
        (out_dir / (image_path.name + '.json')).write_text(
            json.dumps(dict(page, total_ms=total_ms), ensure_ascii=False, indent=2), encoding='utf-8')
        rows.append(summarize_page(image_path.name, page, total_ms))
        sections.append(make_comparison_section(image_path.name, page))
        totals_ms.append(total_ms)
        print('[%d/%d] %s：%s，%.1f 秒' % (index, len(images), image_path.name, page['status'], total_ms / 1000))
    write_outputs(out_dir, rows, sections)
    print_timing_summary(totals_ms)
    print('结果已存到：%s' % out_dir)
    return 0


def main(argv, make_host=build_host_client, make_model=build_model_client):
    """入口：参数不对、路径不合规、配置有问题、识别服务不可用时打印中文说明并返回 2。"""
    configure_output()
    arguments = parse_arguments(argv)
    try:
        return run_regression(arguments, make_host, make_model)
    except RegressionError as error:
        print('无法运行：%s' % error)
        return 2


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
