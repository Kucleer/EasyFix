"""
PDF生成服务：公式练习集使用 Chromium，单词默写保留 fpdf2。
"""
import os
import uuid
from datetime import datetime
from typing import List, Dict, Any
from fpdf import FPDF
from fpdf.enums import XPos, YPos
from app.config import get_settings

settings = get_settings()

# 字体路径
FONT_PATH = 'C:/Windows/Fonts/simhei.ttf'


def generate_practice_set_pdf(
    practice_set_name: str,
    questions: List[Dict[str, Any]],
    output_dir: str = None,
) -> str:
    """使用统一公式排版生成练习集 PDF，保留原有调用和返回路径。"""
    from app.services.math_pdf import generate_math_practice_pdf
    return generate_math_practice_pdf(practice_set_name, questions, output_dir)


# ==================== 单词默写PDF ====================

def generate_word_print_pdf(
    title: str,
    words: List[Dict[str, Any]],
    output_dir: str = None
) -> str:
    """
    生成单词默写PDF

    Args:
        title: 标题
        words: 单词列表，每项包含 chinese, english, length
        output_dir: 输出目录

    Returns:
        生成的PDF文件相对路径
    """
    if output_dir is None:
        upload_dir_abs = os.path.abspath(settings.UPLOAD_DIR)
        output_dir = os.path.join(upload_dir_abs, "practice_sets")

    os.makedirs(output_dir, exist_ok=True)

    filename = f"word_{uuid.uuid4().hex[:8]}_{datetime.now().strftime('%Y%m%d%H%M%S')}.pdf"
    output_path = os.path.join(output_dir, filename)

    pdf = WordPrintPDF(title, words)
    pdf.generate(output_path)

    return f"practice_sets/{filename}"


class WordPrintPDF(FPDF):
    """单词默写PDF生成器"""

    def __init__(self, title: str, words: List[Dict[str, Any]]):
        super().__init__()
        self.title = title
        self.words = words
        self.set_auto_page_break(auto=True, margin=15)
        self.add_font('chinese', '', FONT_PATH)
        self.add_font('chinese_b', '', FONT_PATH)

    def header(self):
        """页眉"""
        self.set_font('chinese_b', size=18)
        self.cell(0, 12, self.title, new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='C')
        self.set_font('chinese', size=10)
        date_str = datetime.now().strftime('%Y年%m月%d日')
        self.cell(0, 8, date_str, new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='C')
        self.ln(3)
        self.set_draw_color(64, 158, 255)
        self.set_line_width(0.5)
        self.line(10, self.get_y(), 200, self.get_y())
        self.ln(8)

    def footer(self):
        """页脚"""
        self.set_y(-15)
        self.set_font('chinese', size=9)
        self.set_text_color(128, 128, 128)
        self.cell(0, 10, f'第 {self.page_no()} 页', align='C')

    def add_word_item(self, index: int, chinese: str, word_length: int):
        """添加一个单词条目"""
        # 序号
        self.set_font('chinese_b', size=12)
        self.set_fill_color(64, 158, 255)
        self.set_text_color(255, 255, 255)
        self.cell(12, 10, f'{index}.', new_x=XPos.RIGHT, new_y=YPos.TOP, align='C', fill=True)

        # 中文
        self.set_text_color(51, 51, 51)
        self.set_font('chinese', size=14)
        self.cell(80, 10, chinese, new_x=XPos.RIGHT, new_y=YPos.TOP, align='L')

        # 长度提示
        self.set_font('chinese', size=10)
        self.set_text_color(128, 128, 128)
        self.cell(0, 10, f'({word_length}个字母)', new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='R')

        # 答题线
        self.set_draw_color(189, 195, 199)
        self.set_line_width(0.3)
        self.line(10, self.get_y() + 2, 200, self.get_y() + 2)
        self.ln(10)

    def generate(self, output_path: str):
        """生成PDF文件"""
        self.add_page()

        for idx, w in enumerate(self.words, 1):
            if self.get_y() > 250:
                self.add_page()

            chinese = w.get('chinese', '')
            word_length = w.get('length', len(w.get('english', '')))
            self.add_word_item(idx, chinese, word_length)

        # 输出到文件
        self.output(output_path)
