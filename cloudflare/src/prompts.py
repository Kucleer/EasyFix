"""手写提示词模板；本文件是云端提示词的唯一来源。

不再由 backend/scripts/prepare_cloudflare_prompts.py 生成，避免覆盖两级知识点改造。
学习报告提示词只要求叙述与建议，数值由服务端写入 content.metrics。
"""

from typing import Optional


class PromptLibrary:

    def _build_prompt(self, question: str, answer: str, subject: str, knowledge_points=None) -> str:
        """生成相似题提示词，主考点必考，其他关联考点作为背景。"""
        subject_info = f'学科：{subject}' if subject else '学科：未知'
        points = []
        if isinstance(knowledge_points, str):
            knowledge_points = [{'name': knowledge_points, 'is_primary': True}] if knowledge_points else []
        for point in knowledge_points or []:
            path = (point.get('parent_name') + ' / ' if point.get('parent_name') else '') + str(point.get('name') or '')
            points.append(('主考点：' if point.get('is_primary') else '关联考点：') + path)
        knowledge_info = '\n'.join(points) if points else '知识点：未分类'
        return (
            '请根据以下题目生成一道相似的练习题，要求：\n'
            '1. 题型相似、难度相近\n'
            '2. 必须考察主考点；其他关联考点作为背景，不保证全部覆盖\n'
            '3. 但具体数值或情境不同\n\n'
            f'{subject_info}\n{knowledge_info}\n\n原题目：\n{question}\n\n原答案：\n{answer}\n\n'
            '请以以下JSON格式返回结果：\n'
            '{\n    "similar_question": "生成的相似题目",\n'
            '    "similar_answer": "相似题目的答案",\n'
            '    "explanation": "简要解析"\n}\n')

    def _build_learning_report_prompt(self, subject_name: Optional[str], grade: Optional[int],
                                      time_range_days: Optional[int], data_summary: dict) -> str:
        """构建学习报告提示词：模型只写叙述，不输出任何计数或正确率数字。"""
        import json
        scope_info = []
        if subject_name:
            scope_info.append(f'学科：{subject_name}')
        if grade:
            scope_info.append(f'年级：{self._get_grade_name(grade)}')
        if time_range_days:
            scope_info.append(f'时间范围：最近{time_range_days}天')
        if not scope_info:
            scope_info.append('范围：全学科、全年级、所有时间')
        scope_text = '，'.join(scope_info)
        return (
            '你是一位专业的学习分析师。请根据以下学习数据，生成多维度学习状态分析。\n\n'
            f'## 分析范围\n{scope_text}\n\n'
            f'## 数据摘要\n{json.dumps(data_summary, ensure_ascii=False, indent=2)}\n\n'
            '## 硬性要求\n'
            '1. 不要输出任何计数、占比、正确率或排名数字；这些数值由服务端写入，模型只负责解释。\n'
            '2. 分析知识点时必须引用数据摘要中 knowledge_modules 的 module_id 与 name，不得自造分类，'
            '不得合并不同学科的同名模块。\n'
            '3. 未分类题目单独说明，不要为它们虚构模块。\n'
            '4. “模块练习正确率”来自练习最终批改状态；不得把它解释为题目累计复习次数。\n'
            '5. 结论要可执行，避免空泛鼓励。\n\n'
            '## 输出格式（仅返回合法 JSON，不要 markdown 代码块）\n'
            '{\n'
            '    "narrative": {\n'
            '        "overall": "整体学习状态叙述",\n'
            '        "knowledge_modules": [\n'
            '            {"module_id": number, "module_name": "一级模块名", '
            '"reason": "薄弱原因", "suggestion": "练习建议"}\n'
            '        ],\n'
            '        "review_strategy": "复习策略",\n'
            '        "word_strategy": "单词或记忆类策略，没有数据时留空字符串"\n'
            '    },\n'
            '    "suggestions": [\n'
            '        {"type": "练习", "content": "建议内容", "priority": 1}\n'
            '    ],\n'
            '    "summary": {\n'
            '        "key_findings": ["发现1", "发现2"],\n'
            '        "priority_improvements": ["优先项1", "优先项2"]\n'
            '    }\n'
            '}\n')

    def _get_grade_name(self, grade: int) -> str:
        """转换年级数字为名称"""
        grade_map = {1: '一年级', 2: '二年级', 3: '三年级', 4: '四年级', 5: '五年级', 6: '六年级',
                     7: '初一', 8: '初二', 9: '初三', 10: '高一', 11: '高二', 12: '高三'}
        return grade_map.get(grade, f'{grade}年级')
