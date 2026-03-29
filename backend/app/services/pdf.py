"""
PDF生成服务 - 使用fpdf2生成练习集PDF（支持中文）
"""
import os
import uuid
from datetime import datetime
from typing import List, Dict, Any
from fpdf import FPDF
from fpdf.enums import XPos, YPos
from app.config import get_settings
from app.utils.html import decode_html

settings = get_settings()

# 字体路径
FONT_PATH = 'C:/Windows/Fonts/simhei.ttf'


def generate_practice_set_pdf(
    practice_set_name: str,
    questions: List[Dict[str, Any]],
    output_dir: str = None
) -> str:
    """
    生成练习集PDF

    Args:
        practice_set_name: 练习集名称
        questions: 题目列表，每题包含 question_text, answer, difficulty 等
        output_dir: 输出目录，默认为 uploads/practice_sets

    Returns:
        生成的PDF文件相对路径
    """
    if output_dir is None:
        # PDF输出到 uploads/images/practice_sets，与静态文件服务一致
        upload_dir_abs = os.path.abspath(settings.UPLOAD_DIR)
        output_dir = os.path.join(upload_dir_abs, "practice_sets")

    # 确保目录存在
    os.makedirs(output_dir, exist_ok=True)
    print(f"[PDF DEBUG] output_dir: {output_dir}")
    print(f"[PDF DEBUG] dir exists: {os.path.exists(output_dir)}")
    print(f"[PDF DEBUG] is dir: {os.path.isdir(output_dir)}")

    # 生成文件名
    filename = f"{uuid.uuid4().hex[:8]}_{datetime.now().strftime('%Y%m%d%H%M%S')}.pdf"
    output_path = os.path.join(output_dir, filename)
    print(f"[PDF DEBUG] output_path: {output_path}")

    # 创建PDF
    pdf = PracticeSetPDF(practice_set_name, questions)
    pdf.generate(output_path)

    # 验证文件是否生成
    if os.path.exists(output_path):
        print(f"[PDF DEBUG] PDF生成成功: {output_path}, 大小: {os.path.getsize(output_path)}")
    else:
        print(f"[PDF DEBUG] PDF生成失败，文件不存在: {output_path}")

    # 返回相对路径（始终使用正斜杠以兼容URL）
    return f"practice_sets/{filename}"


class PracticeSetPDF(FPDF):
    """练习集PDF生成器"""

    def __init__(self, title: str, questions: List[Dict[str, Any]]):
        super().__init__()
        self.title = title
        self.questions = questions
        self.set_auto_page_break(auto=True, margin=15)
        # 注册中文字体（使用下划线后缀_B表示粗体）
        self.add_font('chinese', '', FONT_PATH)
        self.add_font('chinese_b', '', FONT_PATH)

    def header(self):
        """页眉"""
        self.set_font('chinese_b', size=16)
        self.cell(0, 10, self.title, new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='C')
        self.set_font('chinese', size=10)
        date_str = datetime.now().strftime('%Y年%m月%d日')
        self.cell(0, 8, date_str, new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='C')
        self.ln(5)
        self.set_draw_color(78, 205, 196)  # #4ECDC4
        self.set_line_width(0.5)
        self.line(10, self.get_y(), 200, self.get_y())
        self.ln(5)

    def footer(self):
        """页脚"""
        self.set_y(-15)
        self.set_font('chinese', size=9)
        self.set_text_color(128, 128, 128)
        self.cell(0, 10, f'第 {self.page_no()} 页', align='C')

    def add_question(self, index: int, question_text: str, difficulty: int):
        """添加一道题目"""
        # 题目编号和难度
        difficulty_labels = {1: "简单", 2: "较简单", 3: "中等", 4: "较难", 5: "困难"}
        difficulty_text = difficulty_labels.get(difficulty, "中等")

        # 编号背景
        self.set_font('chinese_b', size=11)
        self.set_fill_color(78, 205, 196)  # #4ECDC4
        self.set_text_color(255, 255, 255)
        self.cell(20, 8, f'第{index}题', new_x=XPos.RIGHT, new_y=YPos.TOP, align='C', fill=True)
        self.set_text_color(128, 128, 128)
        self.set_font('chinese', size=10)
        self.cell(0, 8, f'难度: {difficulty_text}', new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='R')
        self.ln(3)

        # 题目内容
        self.set_font('chinese', size=11)
        self.set_text_color(51, 51, 51)
        self.set_fill_color(248, 249, 250)  # #F8F9FA
        # 多行题目文本（解码HTML实体）
        safe_text = decode_html(question_text) if question_text else '暂无题目内容'
        self.multi_cell(0, 6, safe_text, fill=True)
        self.ln(5)

        # 答题区域
        self.set_draw_color(189, 195, 199)  # #BDC3C7
        self.set_line_width(0.3)
        self.set_dash_pattern(3, 3)  # dash=3, gap=3
        self.rect(10, self.get_y(), 190, 60)
        self.ln(65)

        self.set_dash_pattern()  # 恢复实线

    def generate(self, output_path: str):
        """生成PDF文件"""
        self.add_page()

        for idx, q in enumerate(self.questions, 1):
            question_text = q.get('question_text', '')
            difficulty = q.get('difficulty', 3)

            # 检查是否需要新页面
            if self.get_y() > 220:
                self.add_page()

            self.add_question(idx, question_text, difficulty)

        # 输出到文件
        self.output(output_path)


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
