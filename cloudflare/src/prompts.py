"""从现有服务提取的纯提示词模板。"""
from typing import Optional

class PromptLibrary:

    def _build_prompt(self, question: str, answer: str, subject: str, knowledge_point: str) -> str:
        subject_info = f'学科：{subject}' if subject else '学科：未知'
        knowledge_info = f'知识点：{knowledge_point}' if knowledge_point else ''
        prompt = f'请根据以下题目生成一道相似的练习题，要求：\n1. 题型相似、难度相近\n2. 考察的知识点相同\n3. 但具体数值或情境不同\n\n{subject_info}\n{knowledge_info}\n\n原题目：\n{question}\n\n原答案：\n{answer}\n\n请以以下JSON格式返回结果：\n{{\n    "similar_question": "生成的相似题目",\n    "similar_answer": "相似题目的答案",\n    "explanation": "简要解析"\n}}\n'
        return prompt

    def _build_learning_report_prompt(self, subject_name: Optional[str], grade: Optional[int], time_range_days: Optional[int], data_summary: dict) -> str:
        """构建学习报告生成的Prompt"""
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
        prompt = f'你是一位专业的学习分析师。请根据以下学习数据，生成一份详细的多维度学习状态分析报告。\n\n## 分析范围\n{scope_text}\n\n## 数据摘要\n{json.dumps(data_summary, ensure_ascii=False, indent=2)}\n\n## 报告要求\n\n请生成一份结构化的多维度学习分析报告，包含以下维度：\n\n### 1. 整体概况\n- 学习数据总量（错题数量、单词数量）\n- 整体正确率/准确率\n\n### 2. 错题分析\n- **难度分布**：各难度级别（1-5）的错题数量和占比\n- **错误类型分析**：计算错误、概念错误、审题错误、其他错误的分布\n- **知识点分布**：高频出错知识点TOP10。输入中的“学科 · 知识点”是完整身份，输出 point 必须保留学科前缀，不得合并不同学科的同名知识点。\n- **复习效果**：错题的复习次数分布，未复习/复习1次/复习多次的比例\n\n### 3. 单词分析（如有数据）\n- 总体掌握率\n- 低准确率单词（正确率低于70%的单词）\n- 复习间隔建议\n\n### 4. 学习建议\n- 针对薄弱知识点推荐练习方向\n- 记忆类科目的复习策略建议\n- 下一阶段学习重点\n\n### 5. 总结\n- 简明扼要的核心发现（3-5条）\n- 优先改进项（最多3条）\n\n## 输出格式\n\n请以JSON格式返回报告内容：\n{{\n    "overview": {{\n        "total_questions": number,\n        "total_words": number,\n        "overall_accuracy": number\n    }},\n    "question_analysis": {{\n        "difficulty_distribution": {{"1": count, "2": count, ...}},\n        "error_type_distribution": {{"计算": count, "概念": count, ...}},\n        "top_error_knowledge_points": [{{"point": "知识点名", "count": number}}],\n        "review_effectiveness": {{"not_reviewed": count, "reviewed_1": count, "reviewed_multiple": count}}\n    }},\n    "word_analysis": {{\n        "mastery_rate": number,\n        "low_accuracy_words": [{{"word": "单词", "accuracy": number}}],\n        "recommended_review_interval": "建议"\n    }},\n    "suggestions": [\n        {{"type": "练习", "content": "建议内容"}}\n    ],\n    "summary": {{\n        "key_findings": ["发现1", "发现2", ...],\n        "priority_improvements": ["优先项1", "优先项2", ...]\n    }}\n}}\n\n请确保返回的是合法的JSON格式，不要包含markdown代码块标记。'
        return prompt

    def _get_grade_name(self, grade: int) -> str:
        """转换年级数字为名称"""
        grade_map = {1: '一年级', 2: '二年级', 3: '三年级', 4: '四年级', 5: '五年级', 6: '六年级', 7: '初一', 8: '初二', 9: '初三', 10: '高一', 11: '高二', 12: '高三'}
        return grade_map.get(grade, f'{grade}年级')
