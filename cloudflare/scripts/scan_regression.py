"""整页识别回归脚本：在识别主机上，用真实的识别服务和真实的文本模型，把一批回归图完整走一遍。

【怎么跑】在那台主机上，仓库根目录执行（只依赖 Python 自带库和已装的 fastapi、httpx，不用装别的）：

    python cloudflare/scripts/scan_regression.py --images <回归图目录> ^
        --ocr-url http://127.0.0.1:11436 --ocr-key-file <识别口令文件> ^
        --llm-config <文本模型配置.json> [--out <结果目录>] [--subject 数学 --grade 6 --semester 1]

- 图片目录里每张 .jpg/.jpeg/.png/.webp，按文件名顺序：上传 -> 新建一页 -> 读图 -> 整理 -> 需要时重扫。
  流程和线上完全一样（用的就是后端的同一套代码），数据只放在内存里，不会碰正式库。
- 口令和模型密钥只从你给的文件里读，不会打印。
- 回归图和结果都带学生信息：--images 和 --out 都不允许放在仓库目录里。
  --out 不给时存到 %USERPROFILE%\\.easyfix\\scan-regression\\<日期时间>\\ 。
- 不给 --ocr-url 或 --llm-config 时用假的识别和假的模型（只用来自测，没有评分意义）。

【跑完得到什么】结果目录里有：
- 每张图一个 <图名>.json：完整的草稿，加上识别原文 ocr_text 和重扫后的原文 ocr_text_enhanced；
- summary.csv：每页的状态、题数、做错数、拿不准数、带提示数、是否重扫、各步用时、总用时；
- 对照表.md：每页一段，列出模型判错的题、拿不准的题、判对的题，方便人工对着原图核对。
最后在屏幕上打印每页用时的中位数和最大值。

【跑完之后人工评分】（设计文档 12.2 第 1 条；不设及格线，数字交给用户决定能不能给妈妈用）
拿 对照表.md 对着原图和交接文档（ocr-ollama-handoff.md）里人工核对过的 61 道目标题，数出：
  1. 关键题干完全正确的道数、有关键错误的道数（和交接文档里的 41 / 6 比）；
  2. 模型判断做错、而且孩子确实做错的道数；
  3. 做错了却被判成做对的道数（漏判）：61 道目标题都是真错题，被判成做对就算漏判；
  4. 做对了却被判成做错的道数（误判）：模型判错但不在 61 道里的题，要对着原图看一眼，
     可能是误判，也可能是当初没录的错题；
  5. 重扫触发了几页（summary.csv 的"是否重扫"列）、救回了几道关键读错的题
     （对比 JSON 里 ocr_text 和 ocr_text_enhanced 两份原文）；
  6. 每页用时的中位数和最大值（脚本最后会打印）。
"""

import argparse
import csv
import json
import pathlib
import statistics
import sys
import tempfile
import time
from datetime import datetime

ROOT = pathlib.Path(__file__).resolve().parents[1]
REPO_ROOT = ROOT.parent
sys.path.insert(0, str(ROOT / 'src'))
sys.path.insert(0, str(ROOT / 'scripts'))

from fastapi.testclient import TestClient  # noqa: E402
import local_dev_server  # noqa: E402  复用本机测试环境：应用、真实识别客户端、真实模型调用、读口令文件

IMAGE_TYPES = {'.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.png': 'image/png', '.webp': 'image/webp'}
STEP_KEYS = ('read_ms', 'analyze_ms', 'rescan_ms', 'analyze2_ms', 'host_read_ms', 'host_rescan_ms')
CSV_HEADER = (['图名', '状态', '题数', '做错数', '拿不准数', '带提示数', '是否重扫']
              + list(STEP_KEYS) + ['总用时_ms'])
MAX_ADVANCE_ROUNDS = 40  # 一页最多推进的次数，防止卡住的页面无限循环
BUSY_WAIT_SECONDS = 0.5
DEFAULT_OUT_ROOT = pathlib.Path.home() / '.easyfix' / 'scan-regression'


class RegressionError(Exception):
    """脚本自己能说清楚的错误：直接把消息打印给用户，不打印堆栈。"""


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


def find_subject_id(client, name):
    """按学科名字查学科编号；系统里没有这个学科就报错。"""
    for subject in client.get('/api/subjects').json():
        if subject['name'] == name:
            return subject['id']
    raise RegressionError('系统里没有学科：%s' % name)


def run_one_image(client, connection, image_path, subject_id, grade, semester):
    """把一张图走完整流程，返回 (页面视图, 识别原文, 重扫后原文, 总用时毫秒)。"""
    started = time.monotonic()
    upload = client.post('/api/upload/file', files={
        'file': (image_path.name, image_path.read_bytes(), IMAGE_TYPES[image_path.suffix.lower()])})
    if upload.status_code != 200:
        raise RegressionError('上传 %s 失败（%s）' % (image_path.name, upload.status_code))
    created = client.post('/api/scan/pages', json={
        'image': upload.json()['path'], 'subject_id': subject_id, 'grade': grade, 'semester': semester})
    if created.status_code != 201:
        raise RegressionError('新建页面失败（%s）：%s' % (created.status_code, created.text[:200]))
    page = created.json()
    page_id = page['id']
    for _ in range(MAX_ADVANCE_ROUNDS):
        if page['status'] in ('ready', 'failed'):
            break
        result = client.post('/api/scan/pages/%d/advance' % page_id).json()
        page = result['page']
        if result['busy']:
            # 别的请求正在做这一步：稍等再查一次状态
            time.sleep(BUSY_WAIT_SECONDS)
            page = client.get('/api/scan/pages/%d' % page_id).json()
    total_ms = int((time.monotonic() - started) * 1000)
    # OCR 原文不在接口的页面视图里，直接从库里读
    row = connection.execute('SELECT ocr_text, ocr_text_enhanced FROM scan_page WHERE id=?', (page_id,)).fetchone()
    return page, row['ocr_text'], row['ocr_text_enhanced'], total_ms


def summarize_page(name, page, total_ms):
    """把一页整理成 summary.csv 的一行。"""
    items = page['items']
    timings = page['timings']
    return ([name, page['status'], len(items),
             sum(1 for item in items if item.get('verdict') == 'wrong'),
             sum(1 for item in items if item.get('verdict') == 'unsure'),
             sum(1 for item in items if item.get('flags')),
             '是' if page['rescan_used'] == 1 else '否']
            + [timings.get(key, '') for key in STEP_KEYS] + [total_ms])


def describe_item(item):
    """对照表里一道题的一行：题号、题干开头、孩子的答案、原因、提示。"""
    text = (item.get('parsed_question') or '').replace('\n', ' ')[:40]
    line = '- 第 %s 题：%s' % (item.get('question_no', '?'), text)
    if item.get('wrong_answer'):
        line += '；孩子写：%s' % item['wrong_answer']
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


def print_timing_summary(totals_ms):
    """打印每页总用时的中位数和最大值。"""
    if not totals_ms:
        return
    print('每页总用时：中位数 %.1f 秒，最大 %.1f 秒（共 %d 页）'
          % (statistics.median(totals_ms) / 1000, max(totals_ms) / 1000, len(totals_ms)))


def parse_arguments(argv):
    """解析命令行参数。"""
    parser = argparse.ArgumentParser(description='整页识别回归脚本（用真实识别服务和文本模型跑一批图）')
    parser.add_argument('--images', required=True, help='回归图目录（不能在仓库里）')
    parser.add_argument('--ocr-url', default=None, help='识别服务地址；不给就用假的')
    parser.add_argument('--ocr-key-file', default=None, help='存放识别服务口令的文件')
    parser.add_argument('--llm-config', default=None, help='文本模型配置 JSON；不给就用假的')
    parser.add_argument('--out', default=None, help='结果目录（不能在仓库里）；默认放在用户目录的 .easyfix 下')
    parser.add_argument('--subject', default='数学')
    parser.add_argument('--grade', type=int, default=6)
    parser.add_argument('--semester', type=int, default=1)
    return parser.parse_args(argv)


def run_regression(arguments):
    """检查路径、起本机服务、逐张跑图并写出结果；返回 0。"""
    check_outside_repo(arguments.images, '--images')
    out_dir = (pathlib.Path(arguments.out) if arguments.out
               else DEFAULT_OUT_ROOT / datetime.now().strftime('%Y%m%d-%H%M%S'))
    check_outside_repo(out_dir, '--out')
    images = list_images(arguments.images)
    # 口令和模型配置只从文件读（去掉 BOM 和首尾空白），不打印
    ocr_key = (local_dev_server.read_text_file(arguments.ocr_key_file).strip()
               if arguments.ocr_key_file else None)
    llm_config = (json.loads(local_dev_server.read_text_file(arguments.llm_config))
                  if arguments.llm_config else None)
    if arguments.ocr_url and not ocr_key:
        print('警告：给了 --ocr-url 但没有 --ocr-key-file，访问识别服务时不会带口令，可能被拒绝。')
    out_dir.mkdir(parents=True, exist_ok=True)

    connection = local_dev_server.build_connection()
    with tempfile.TemporaryDirectory(prefix='easyfix_regression_') as uploads_dir:
        app = local_dev_server.build_app(connection, uploads_dir, None, arguments.ocr_url, ocr_key, llm_config)
        client = TestClient(app)
        subject_id = find_subject_id(client, arguments.subject)
        print('识别服务%s，文本模型%s，共 %d 张图'
              % ('真实' if arguments.ocr_url else '假的', '真实' if llm_config else '假的', len(images)))
        rows, sections, totals_ms = [], [], []
        for index, image_path in enumerate(images, start=1):
            page, ocr_text, ocr_text_enhanced, total_ms = run_one_image(
                client, connection, image_path, subject_id, arguments.grade, arguments.semester)
            (out_dir / (image_path.name + '.json')).write_text(json.dumps(
                {**page, 'ocr_text': ocr_text, 'ocr_text_enhanced': ocr_text_enhanced},
                ensure_ascii=False, indent=2), encoding='utf-8')
            rows.append(summarize_page(image_path.name, page, total_ms))
            sections.append(make_comparison_section(image_path.name, page))
            totals_ms.append(total_ms)
            print('[%d/%d] %s：%s，%.1f 秒' % (index, len(images), image_path.name, page['status'], total_ms / 1000))
    # utf-8-sig 让 Excel 直接打开不乱码
    with open(out_dir / 'summary.csv', 'w', encoding='utf-8-sig', newline='') as file:
        writer = csv.writer(file)
        writer.writerow(CSV_HEADER)
        writer.writerows(rows)
    (out_dir / '对照表.md').write_text('# 整页识别对照表\n\n' + '\n'.join(sections), encoding='utf-8')
    print_timing_summary(totals_ms)
    print('结果已存到：%s' % out_dir)
    return 0


def main(argv):
    """入口：参数不对或路径不合规时打印中文说明并返回 2。"""
    configure_output()
    arguments = parse_arguments(argv)
    try:
        return run_regression(arguments)
    except RegressionError as error:
        print('无法运行：%s' % error)
        return 2


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
