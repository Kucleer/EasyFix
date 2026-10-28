"""供 Agent 入库前校验任意题目 JSON；只生成临时 PDF，不写数据库。"""

import argparse
import json
import os
from pathlib import Path
import re
import sys
import tempfile

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))


def main():
    """把题干、答案和解析交给产品渲染器校验，并拒绝没有边界的公式命令。"""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('json_file', type=Path, help='UTF-8 JSON：题目对象、题目数组或含 questions 数组的对象')
    args = parser.parse_args()
    data = json.loads(args.json_file.read_text(encoding='utf-8-sig'))
    rows = data if isinstance(data, list) else data.get('questions', [data])
    questions = []
    for index, row in enumerate(rows, 1):
        text = row.get('parsed_question') or row.get('question_text') or row.get('original_text')
        if not text:
            raise ValueError(f'第 {index} 题缺少题干')
        for key, value in [('题干', text), ('答案', row.get('answer')), ('解析', row.get('analysis'))]:
            # 去掉已包裹区域后，正文不应残留常见数学命令。
            outside = re.sub(r'\\\([\s\S]*?\\\)|\\\[[\s\S]*?\\\]|\$\$[\s\S]*?\$\$', '', value or '')
            if re.search(r'\\(?:frac|sqrt|left|right|times|cdot|sum)\b', outside):
                raise ValueError(f'第 {index} 题{key}存在未包裹的公式命令')
        questions.append(dict(row, question_text=text, include_solution=True))
    if not questions:
        raise ValueError('没有待校验题目')
    os.chdir(BACKEND)
    from app.services.math_pdf import generate_math_practice_pdf
    with tempfile.TemporaryDirectory() as directory:
        generate_math_practice_pdf('Agent 入库前公式校验', questions, directory)
    print(f'校验通过：{len(questions)} 道题，数据库未写入')


if __name__ == '__main__':
    main()
