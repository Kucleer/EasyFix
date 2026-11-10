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

    def _build_phrase_focus_prompt(self, items: list, default_grade: Optional[int]) -> str:
        """构建词组默写标注提示词：模型只给每个已切好的 token 指定角色，不得改动词本身。"""
        import json
        from phrase_focus import split_tokens
        entries = []
        for item in items:
            # 条目没有年级时使用默认年级
            grade = item.get('grade') or default_grade
            grade_text = self._get_grade_name(grade) if grade else '未知年级'
            # 预先切好 token，避免模型自己切分
            tokens = split_tokens(item['english'])
            entries.append(
                f'- "id": {item["id"]}，词组：{item["english"]}，中文：{item.get("chinese") or ""}，'
                f'年级：{grade_text}\n'
                f'  tokens（已按空格切好）：{json.dumps(tokens, ensure_ascii=False)}')
        entries_text = '\n'.join(entries)
        return (
            '你是小学和初中英语老师。下面是学生要默写的英语词组，请判断每个词组里哪些词是默写时需要重点记忆的。\n'
            '每个词组都已经按空格切成 tokens，你只需要给每个 token 指定一个角色。\n\n'
            '## 角色（role）只能是以下四种\n'
            '1. collocation：搭配词。介词、副词小品词（如 up、out、off）、不定式 to，'
            '以及固定搭配中容易和近义词混淆的词（如 take part in 中的 in，look forward to 中的 forward 和 to）。\n'
            '2. content：实义词。该年级学生可能还不熟悉的名词、动词、形容词、副词等。'
            '这类词必须额外给出 lemma（原形，小写）和 gloss（中文释义）。\n'
            '3. plain：基础词。该年级学生早已熟悉的基础词，如 be、a、the、take、good、part 等。\n'
            "4. placeholder：占位符。sb.、sth.、sp.、doing、do、one's、oneself 及其变体"
            "（如 sb.'s、sth.'s、somebody、something、yourself、myself、themselves）。\n\n"
            '## 判断原则\n'
            '- 是否是基础词要结合词组所属年级来判断；拿不准时标 content，不要标 plain。\n'
            '- 每个 token 只能有一个角色，只有 content 才有 lemma 和 gloss。\n\n'
            '## 硬性要求\n'
            '- 不得增、删、改写 token，也不得重新切分或合并 token；返回的 tokens 必须与给出的 tokens '
            '数量相同、顺序相同、text 完全一致（包括标点和大小写）。\n'
            '- 每个词组都必须返回，id 必须与给出的 id 一致。\n'
            '- 只返回合法 JSON，不要 markdown 代码块，不要任何解释文字。\n\n'
            f'## 待标注的词组\n{entries_text}\n\n'
            '## 输出格式\n'
            '{"items": [{"id": 1, "tokens": ['
            '{"text": "be", "role": "plain"}, '
            '{"text": "proud", "role": "content", "lemma": "proud", "gloss": "自豪的"}, '
            '{"text": "of", "role": "collocation"}]}]}\n')

    def _get_grade_name(self, grade: int) -> str:
        """转换年级数字为名称"""
        grade_map = {1: '一年级', 2: '二年级', 3: '三年级', 4: '四年级', 5: '五年级', 6: '六年级',
                     7: '初一', 8: '初二', 9: '初三', 10: '高一', 11: '高二', 12: '高三'}
        return grade_map.get(grade, f'{grade}年级')
