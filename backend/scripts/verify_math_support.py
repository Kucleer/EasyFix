"""验证数学文本安全、错误检测、图片题目排版和旧文本 PDF；不连接数据库。"""

import json
import os
from pathlib import Path
import sys
import tempfile

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(BACKEND / 'scripts'))


def main():
    """运行有针对性的公式与 PDF 回归检查。"""
    os.chdir(BACKEND)
    from playwright.sync_api import sync_playwright
    from app.config import get_settings
    from app.services.math_pdf import ASSETS, RENDERER, build_document, generate_math_practice_pdf, get_answer_space_mm
    from import_math_formula_photos import QUESTIONS
    settings = get_settings()
    results = {}
    spacing_cases = [
        ('默认留白', '已知两个数满足某个条件，求结果。', 40),
        ('选择题', r'选出正确答案：A. \(1\)；B. \(2\)；C. \(3\)。', 20),
        ('计算题', r'计算：\(1+2\)。', 40),
        ('应用题', '大桥两侧安装路灯，至少需要多少盏？', 60),
        ('定义优先', '一个数分解质因数后满足条件，称为特殊数。判断哪些数符合定义。', 60),
        ('多小问优先', '计算：（1）同时完成需要多久？（2）轮流完成需要多久？（3）怎样调整？', 100),
        ('公式括号不算小问', r'计算：\(f(1)+f(2)+f(3)\)。', 40),
    ]
    for name, text, expected in spacing_cases:
        question = {'subject_name': '数学', 'question_text': text}
        assert get_answer_space_mm(question) == expected, name
        document, _ = build_document(name, [question])
        assert f'height:{expected}mm' in document, name
        question['subject_name'] = '英语'
        assert get_answer_space_mm(question) == 0, name
        document, _ = build_document(name, [question])
        assert 'class="answer-space"' not in document, name
    assert get_answer_space_mm({'subject_name': '数学', 'is_reading_question': True}) == 0
    results['math_answer_spacing'] = 'passed'
    _, reading_fields = build_document('阅读选项兼容', [{'question_text': 'Choose one.', 'option_a': 'A. Reading', 'option_b': '(B) Music', 'option_c': 'C、Sports', 'option_d': 'D) Travel'}])
    assert [item['text'] for item in reading_fields[1:]] == ['A. Reading', 'B. Music', 'C. Sports', 'D. Travel']
    results['reading_option_prefixes'] = 'passed'
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True, **({'channel': settings.PDF_BROWSER_CHANNEL} if settings.PDF_BROWSER_CHANNEL else {}))
        try:
            page = browser.new_page()
            page.set_content('<!doctype html><html><body><div id="text"></div></body></html>')
            page.add_script_tag(path=str(ASSETS / 'katex.min.js'))
            page.add_script_tag(path=str(ASSETS / 'auto-render.min.js'))
            page.add_script_tag(path=str(RENDERER), type='module')
            page.wait_for_function('Boolean(window.EasyFixMath)')
            cases = [
                ('image_questions', '\n'.join(q['question_text'] for q in QUESTIONS), False),
                ('unclosed', r'计算 \(\frac{1}{2}', True),
                ('bad_command', r'\(\notARealCommand{x}\)', True),
                ('bad_braces', r'\(\frac{1}{\)', True),
                ('control_character', '\\(\x0crac{1}{2}\\)', True),
                ('legacy_comparison', '2 < 3，5 > 4，x²，1/2，A &amp; B', False),
                ('text_safety', '<img src=x onerror="window.mathXss=true"><script>window.mathXss=true</script>', False),
            ]
            for name, text, expected_error in cases:
                result = page.evaluate('''text => {
                  const el = document.querySelector('#text');
                  const errors = EasyFixMath.renderMathText(el, text, renderMathInElement);
                  return {errors, formulas: el.querySelectorAll('.katex').length, htmlNodes: el.querySelectorAll('img,script').length, xss: Boolean(window.mathXss), text: el.textContent};
                }''', text)
                assert bool(result['errors']) == expected_error, (name, result)
                assert not result['xss'] and result['htmlNodes'] == 0
                if name == 'image_questions':
                    assert result['formulas'] == 6, result
                if name == 'legacy_comparison':
                    assert result['text'] == '2 < 3，5 > 4，x²，1/2，A & B'
                results[name] = 'passed'
        finally:
            browser.close()
    output = BACKEND.parent / 'output/pdf'
    output.mkdir(parents=True, exist_ok=True)
    question_pdf = generate_math_practice_pdf('数学·分数与乘方（图片题目）', QUESTIONS, output)
    solution_pdf = generate_math_practice_pdf('数学·分数与乘方（答案与解析）', [dict(q, include_solution=True) for q in QUESTIONS], output)
    results['question_pdf'] = str(output / Path(question_pdf).name)
    results['solution_pdf'] = str(output / Path(solution_pdf).name)
    with tempfile.TemporaryDirectory() as directory:
        generate_math_practice_pdf('历史普通文本', [{'question_text': '旧题：2 < 3，5 > 4，x²，1/2；中文与英文 mixed。'}], directory)
        results['legacy_pdf'] = 'passed'
        try:
            generate_math_practice_pdf('错误公式', [{'id': 99, 'question_text': r'\(\frac{1}{\)'}], directory)
        except ValueError as exc:
            assert '99' in str(exc)
            results['invalid_pdf_rejected'] = 'passed'
        else:
            raise AssertionError('错误公式被静默导出')
        try:
            generate_math_practice_pdf('超宽公式', [{'question_text': '\\(' + '+'.join(['x^{2026}'] * 70) + '\\)'}], directory)
        except ValueError:
            results['wide_pdf_rejected'] = 'passed'
        else:
            raise AssertionError('超宽公式被静默裁切')
    (output / 'math-verification.json').write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
