"""使用离线 KaTeX 和无头 Chromium 生成可直接打印的练习集 PDF。"""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
import html
from pathlib import Path
import re
import threading
import uuid

from app.config import get_settings

ROOT = Path(__file__).resolve().parents[3]
ASSETS = ROOT / 'backend/app/static/katex'
RENDERER = ROOT / 'shared/math-text.mjs'
# 限制单个服务进程的并发；同步 Playwright 放在线程中，也兼容异步调用方。
PDF_SLOTS = threading.BoundedSemaphore(2)


def get_answer_space_mm(question):
    """仅为数学题分配答题留白；不明确时留四厘米，多小问额外加高。"""
    if question.get('is_reading_question') or str(question.get('subject_name') or '').strip() != '数学':
        return 0

    # 去掉公式边界内的括号，避免把 (1)、(2) 等公式内容误当小问。
    text = re.sub(r'\\\(.*?\\\)|\\\[.*?\\\]', '', str(question.get('question_text') or ''), flags=re.S)
    numbers = {int(value) for value in re.findall(r'[（(]\s*([1-9]\d*)\s*[）)]', text)}
    subquestions = 0
    while subquestions + 1 in numbers:
        subquestions += 1

    has_options = all(question.get('option_' + letter) for letter in 'abc') or bool(
        re.search(r'A\s*[.．、)）].*?B\s*[.．、)）].*?C\s*[.．、)）]', text, re.S)
    )
    # 复杂任务优先，避免“定义题中提到分解质因数”被当成普通计算。
    if subquestions > 1:
        space = 60
    elif re.search(r'规定|定义|称为|证明', text):
        space = 60
    elif has_options or re.search(r'填空|判断[对正错误]|判断题', text):
        space = 20
    elif re.search(r'在数轴上表示|画出|作图|计算|化简|解方程|分解质因数', text):
        space = 40
    elif re.search(r'出租车|大桥|参赛作品|阅卷|观看区|工程|路程|速度|售价|利润|面积|体积|至少需要|共[有需]|多少[米元吨人件盏]', text):
        space = 60
    else:
        space = 40
    return space + max(0, subquestions - 1) * 20


def build_document(title, questions):
    """生成不含用户 HTML 的打印模板及待渲染文本数据。"""
    texts = []

    def field(value, label):
        """注册待通过 textContent 注入的字段，不拼接题干 HTML。"""
        index = len(texts)
        texts.append({'text': str(value or ''), 'label': label})
        return f'<div class="math-field" data-field="{index}"></div>'

    blocks = []
    if questions and questions[0].get('is_reading_question'):
        blocks.append('<section class="passage">' + field(questions[0].get('_passage_title'), '短文标题')
                      + field(questions[0].get('_passage_content'), '短文') + '</section>')
    for index, question in enumerate(questions, 1):
        identity = question.get('id', index)
        if not str(question.get('question_text') or '').strip():
            raise ValueError(f'题目 {identity} 没有可导出的文本，请补充题干')
        metadata = [f'第 {index} 题', f'ID: {identity}']
        if not question.get('is_reading_question'):
            difficulty = max(1, min(5, int(question.get('difficulty') or 3)))
            metadata.append('难度：' + '★' * difficulty + '☆' * (5 - difficulty))
            if question.get('knowledge_point'):
                metadata.append('知识点：' + str(question['knowledge_point']))
        header = html.escape('　 |　 '.join(metadata))
        body = field(question.get('question_text'), f'题目 {identity}')
        for letter in 'abcd':
            option = question.get('option_' + letter)
            if option:
                # 与旧导出器一致：已有 A. / A、/ (A) / A) 前缀时不重复添加。
                option = re.sub(r'^(?:[A-Da-d]\s*[.、．)]|\([A-Da-d]\))\s*', '', str(option).strip())
                body += field(f'{letter.upper()}. {option}', f'题目 {identity} 选项 {letter.upper()}')
        # 默认不打印答案，沿用现有练习集行为；专项验证可显式带答案解析。
        if question.get('include_solution'):
            body += '<div class="solution-label">答案与解析</div>'
            body += field(question.get('answer'), f'题目 {identity} 答案')
            body += field(question.get('analysis'), f'题目 {identity} 解析')
        space = get_answer_space_mm(question)
        question_class = 'question'
        if space:
            question_class += ' math-question'
            body += f'<div class="answer-space" style="height:{space}mm" aria-hidden="true"></div>'
        blocks.append(f'<section class="{question_class}"><div class="question-header">{header}</div>{body}</section>')
    css_url = (ASSETS / 'katex.min.css').as_uri()
    settings = get_settings()
    font_css = ''
    if settings.PDF_FONT_PATH:
        font_path = Path(settings.PDF_FONT_PATH).resolve()
        if not font_path.is_file():
            raise RuntimeError('PDF_FONT_PATH 指定的中文字体不存在')
        font_css = "@font-face{font-family:EasyFixChinese;src:url('" + font_path.as_uri() + "')}"
    source = f'''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
<link rel="stylesheet" href="{css_url}"><style>
{font_css}
@page {{ size: A4; margin: 18mm 16mm 20mm; }}
* {{ box-sizing: border-box; }}
body {{ margin: 0; color: #111; font-family: EasyFixChinese,"Noto Sans CJK SC","Microsoft YaHei",sans-serif; font-size: 11pt; line-height: 1.9; }}
h1 {{ font-size: 18pt; text-align: center; margin: 0 0 5mm; }}
.date {{ text-align: center; font-size: 9pt; margin-bottom: 7mm; }}
.question {{ border-top: 1px solid #888; padding-top: 3mm; margin-bottom: 10mm; break-inside: avoid; }}
.question.long {{ break-inside: auto; }}
.question.math-question {{ margin-bottom: 0; }}
.question-header {{ font-size: 9pt; color: #333; margin-bottom: 3mm; }}
.math-field {{ white-space: pre-wrap; overflow-wrap: anywhere; }}
.katex {{ white-space: nowrap; }}
.katex-display {{ margin: 3mm 0; break-inside: avoid; }}
.solution-label {{ margin-top: 4mm; font-weight: bold; }}
.passage {{ margin-bottom: 8mm; }}
</style></head><body><h1>{html.escape(str(title))}</h1>
<div class="date">{datetime.now().strftime('%Y-%m-%d')}</div>{''.join(blocks)}</body></html>'''
    return source, texts


def render_pdf(title, questions, output_path):
    """在独立浏览器上下文渲染公式，验证完成后写入新文件。"""
    from playwright.sync_api import sync_playwright
    settings = get_settings()
    for resource in [ASSETS / 'katex.min.js', ASSETS / 'auto-render.min.js', ASSETS / 'katex.min.css', RENDERER]:
        if not resource.is_file():
            raise RuntimeError('缺少公式离线资源，请运行 backend/scripts/sync_math_assets.py')
    document, texts = build_document(title, questions)
    with sync_playwright() as playwright:
        launch = {'headless': True, 'timeout': settings.PDF_TIMEOUT_MS}
        if settings.PDF_BROWSER_CHANNEL:
            launch['channel'] = settings.PDF_BROWSER_CHANNEL
        browser = playwright.chromium.launch(**launch)
        try:
            # 与 A4 扣除左右页边距后的 178mm 内容宽度一致，用于超宽公式检测。
            page = browser.new_page(viewport={'width': 673, 'height': 978})
            page.set_default_timeout(settings.PDF_TIMEOUT_MS)
            page.route('http://**/*', lambda route: route.abort())
            page.route('https://**/*', lambda route: route.abort())
            # 本地临时 HTML 使 file:// 字体可加载；题目文本通过 evaluate 参数传递。
            html_path = output_path.with_suffix('.html')
            try:
                html_path.write_text(document, encoding='utf-8')
                page.goto(html_path.as_uri(), wait_until='load')
                page.add_script_tag(path=str(ASSETS / 'katex.min.js'))
                page.add_script_tag(path=str(ASSETS / 'auto-render.min.js'))
                page.add_script_tag(path=str(RENDERER), type='module')
                page.wait_for_function('Boolean(window.EasyFixMath)')
                errors = page.evaluate('''items => items.flatMap((item, index) => {
                  const element = document.querySelector(`[data-field="${index}"]`);
                  return window.EasyFixMath.renderMathText(element, item.text, renderMathInElement)
                    .map(error => `${item.label}：${error}`);
                })''', texts)
                if errors:
                    raise ValueError('；'.join(errors[:5]))
                page.evaluate('async () => { await document.fonts.ready; }')
                page.emulate_media(media='print')
                layout_errors = page.evaluate('''() => {
                  const issues = [];
                  document.querySelectorAll('.katex').forEach(el => {
                    const available = el.closest('.math-field').clientWidth;
                    if (el.getBoundingClientRect().width > available + 1) issues.push('公式过宽，请拆成多行');
                  });
                  document.querySelectorAll('.question').forEach(el => {
                    if (el.getBoundingClientRect().height > 900) el.classList.add('long');
                  });
                  return issues;
                }''')
                if layout_errors:
                    raise ValueError(layout_errors[0])
                page.pdf(path=str(output_path), format='A4', prefer_css_page_size=True,
                         print_background=True, display_header_footer=True,
                         header_template='<span></span>',
                         footer_template='<div style="font-size:9px;width:100%;text-align:center">第 <span class="pageNumber"></span> / <span class="totalPages"></span> 页</div>')
                if not output_path.is_file() or output_path.stat().st_size < 100:
                    raise RuntimeError('PDF 文件生成失败')
            finally:
                html_path.unlink(missing_ok=True)
        finally:
            browser.close()


def generate_math_practice_pdf(title, questions, output_dir=None):
    """受限并发地生成 PDF，失败不覆盖旧文件或旧数据库路径。"""
    settings = get_settings()
    directory = Path(output_dir or Path(settings.UPLOAD_DIR) / 'practice_sets').resolve()
    directory.mkdir(parents=True, exist_ok=True)
    output = directory / f'{uuid.uuid4().hex}_{datetime.now():%Y%m%d%H%M%S}.pdf'
    if not PDF_SLOTS.acquire(timeout=5):
        raise RuntimeError('PDF 生成繁忙，请稍后重试')
    try:
        with ThreadPoolExecutor(max_workers=1) as executor:
            executor.submit(render_pdf, title, questions, output).result()
        return f'practice_sets/{output.name}'
    except Exception:
        output.unlink(missing_ok=True)
        raise
    finally:
        PDF_SLOTS.release()
