import os
import json
from typing import Optional
import anthropic
from app.config import get_settings

settings = get_settings()


def load_llm_config() -> dict:
    """从config/llm.json加载配置"""
    config_file = "config/llm.json"
    if os.path.exists(config_file):
        with open(config_file) as f:
            return json.load(f)
    return {}


class LLMService:
    _instance: Optional["LLMService"] = None
    _client: Optional[anthropic.Anthropic] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        self._config = load_llm_config()
        self._init_client()

    def _init_client(self):
        if self._client is None:
            api_key = self._config.get("api_key") or settings.ANTHROPIC_API_KEY
            base_url = self._config.get("base_url")
            if base_url:
                self._client = anthropic.Anthropic(
                    api_key=api_key,
                    base_url=base_url,
                )
            else:
                self._client = anthropic.Anthropic(api_key=api_key)

    def _get_config(self, key: str, default: str = "") -> str:
        """获取配置，优先从config文件"""
        return self._config.get(key, getattr(settings, key, default))

    def generate_similar_question(
        self,
        question: str,
        answer: str,
        subject: str = "",
        knowledge_point: str = "",
    ) -> dict:
        """
        生成相似题目

        Args:
            question: 原题目
            answer: 原答案
            subject: 学科
            knowledge_point: 知识点

        Returns:
            dict: {
                "similar_question": str,
                "similar_answer": str,
                "explanation": str,
            }
        """
        # 重新加载配置
        self._config = load_llm_config()
        self._init_client()

        api_key = self._get_config("api_key", settings.ANTHROPIC_API_KEY)
        if not api_key:
            return {
                "error": "LLM API Key not configured. Please set it in Settings.",
                "similar_question": "",
                "similar_answer": "",
                "explanation": "",
            }

        model = self._get_config("model", "claude-sonnet-4-20250514")
        prompt = self._build_prompt(question, answer, subject, knowledge_point)

        try:
            response = self._client.messages.create(
                model=model,
                max_tokens=1000,
                messages=[
                    {
                        "role": "user",
                        "content": prompt,
                    }
                ],
                timeout=60,
                # 禁用思考块，避免MiniMax返回纯思考内容
                thinking={
                    "type": "disabled",
                },
            )

            # 获取文本内容（跳过ThinkingBlock，只取TextBlock）
            content = ""
            for block in response.content:
                if hasattr(block, 'type') and block.type == 'text' and hasattr(block, 'text'):
                    content = block.text
                    break

            if not content:
                return {
                    "error": "LLM返回内容为空或仅包含思考过程",
                    "similar_question": "",
                    "similar_answer": "",
                    "explanation": "",
                }

            return self._parse_response(content)
        except Exception as e:
            return {
                "error": str(e),
                "similar_question": "",
                "similar_answer": "",
                "explanation": f"LLM调用失败: {str(e)}",
            }

    def _build_prompt(
        self,
        question: str,
        answer: str,
        subject: str,
        knowledge_point: str,
    ) -> str:
        subject_info = f"学科：{subject}" if subject else "学科：未知"
        knowledge_info = f"知识点：{knowledge_point}" if knowledge_point else ""

        prompt = f"""请根据以下题目生成一道相似的练习题，要求：
1. 题型相似、难度相近
2. 考察的知识点相同
3. 但具体数值或情境不同

{subject_info}
{knowledge_info}

原题目：
{question}

原答案：
{answer}

请以以下JSON格式返回结果：
{{
    "similar_question": "生成的相似题目",
    "similar_answer": "相似题目的答案",
    "explanation": "简要解析"
}}
"""
        return prompt

    def _parse_response(self, content: str) -> dict:
        """解析LLM返回的内容"""
        import json
        import re

        # 尝试从markdown代码块中提取JSON
        json_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", content, re.DOTALL)
        if json_match:
            content = json_match.group(1)

        # 尝试直接解析JSON
        try:
            data = json.loads(content)
            # 兼容不同的字段名
            return {
                "similar_question": data.get("similar_question") or data.get("question") or data.get("similar_text") or "",
                "similar_answer": data.get("similar_answer") or data.get("answer") or "",
                "explanation": data.get("explanation") or data.get("解析") or "",
            }
        except json.JSONDecodeError:
            # 尝试提取JSON对象
            start = content.find("{")
            end = content.rfind("}") + 1
            if start != -1 and end != 0:
                try:
                    data = json.loads(content[start:end])
                    return {
                        "similar_question": data.get("similar_question") or data.get("question") or data.get("similar_text") or "",
                        "similar_answer": data.get("similar_answer") or data.get("answer") or "",
                        "explanation": data.get("explanation") or data.get("解析") or "",
                    }
                except json.JSONDecodeError:
                    pass

        return {
            "similar_question": content,
            "similar_answer": "",
            "explanation": "解析失败",
        }

    def generate_learning_report(
        self,
        subject_name: Optional[str],
        grade: Optional[int],
        time_range_days: Optional[int],
        data_summary: dict,
    ) -> dict:
        """
        生成学习状态分析报告

        Args:
            subject_name: 学科名称
            grade: 年级
            time_range_days: 时间范围天数
            data_summary: 数据摘要，包含错题和单词的统计数据

        Returns:
            dict: 多维度分析报告内容
        """
        # 重新加载配置
        self._config = load_llm_config()
        self._init_client()

        api_key = self._get_config("api_key", settings.ANTHROPIC_API_KEY)
        if not api_key:
            raise Exception("LLM API Key not configured. Please set it in Settings.")

        model = self._get_config("model", "claude-sonnet-4-20250514")
        prompt = self._build_learning_report_prompt(
            subject_name, grade, time_range_days, data_summary
        )

        try:
            response = self._client.messages.create(
                model=model,
                max_tokens=4000,  # 报告较长，需要更多token
                messages=[
                    {
                        "role": "user",
                        "content": prompt,
                    }
                ],
                timeout=120,  # 报告生成可能需要更长时间
                thinking={
                    "type": "disabled",
                },
            )

            # 获取文本内容
            content = ""
            for block in response.content:
                if hasattr(block, 'type') and block.type == 'text' and hasattr(block, 'text'):
                    content = block.text
                    break

            if not content:
                raise Exception("LLM返回内容为空")

            return self._parse_learning_report_response(content)
        except Exception as e:
            raise Exception(f"LLM调用失败: {str(e)}")

    def _build_learning_report_prompt(
        self,
        subject_name: Optional[str],
        grade: Optional[int],
        time_range_days: Optional[int],
        data_summary: dict,
    ) -> str:
        """构建学习报告生成的Prompt"""
        import json

        scope_info = []
        if subject_name:
            scope_info.append(f"学科：{subject_name}")
        if grade:
            scope_info.append(f"年级：{self._get_grade_name(grade)}")
        if time_range_days:
            scope_info.append(f"时间范围：最近{time_range_days}天")
        if not scope_info:
            scope_info.append("范围：全学科、全年级、所有时间")

        scope_text = "，".join(scope_info)

        prompt = f"""你是一位专业的学习分析师。请根据以下学习数据，生成一份详细的多维度学习状态分析报告。

## 分析范围
{scope_text}

## 数据摘要
{json.dumps(data_summary, ensure_ascii=False, indent=2)}

## 报告要求

请生成一份结构化的多维度学习分析报告，包含以下维度：

### 1. 整体概况
- 学习数据总量（错题数量、单词数量）
- 整体正确率/准确率

### 2. 错题分析
- **难度分布**：各难度级别（1-5）的错题数量和占比
- **错误类型分析**：计算错误、概念错误、审题错误、其他错误的分布
- **知识点分布**：高频出错知识点TOP10
- **复习效果**：错题的复习次数分布，未复习/复习1次/复习多次的比例

### 3. 单词分析（如有数据）
- 总体掌握率
- 低准确率单词（正确率低于70%的单词）
- 复习间隔建议

### 4. 学习建议
- 针对薄弱知识点推荐练习方向
- 记忆类科目的复习策略建议
- 下一阶段学习重点

### 5. 总结
- 简明扼要的核心发现（3-5条）
- 优先改进项（最多3条）

## 输出格式

请以JSON格式返回报告内容：
{{
    "overview": {{
        "total_questions": number,
        "total_words": number,
        "overall_accuracy": number
    }},
    "question_analysis": {{
        "difficulty_distribution": {{"1": count, "2": count, ...}},
        "error_type_distribution": {{"计算": count, "概念": count, ...}},
        "top_error_knowledge_points": [{{"point": "知识点名", "count": number}}],
        "review_effectiveness": {{"not_reviewed": count, "reviewed_1": count, "reviewed_multiple": count}}
    }},
    "word_analysis": {{
        "mastery_rate": number,
        "low_accuracy_words": [{{"word": "单词", "accuracy": number}}],
        "recommended_review_interval": "建议"
    }},
    "suggestions": [
        {{"type": "练习", "content": "建议内容"}}
    ],
    "summary": {{
        "key_findings": ["发现1", "发现2", ...],
        "priority_improvements": ["优先项1", "优先项2", ...]
    }}
}}

请确保返回的是合法的JSON格式，不要包含markdown代码块标记。"""
        return prompt

    def _get_grade_name(self, grade: int) -> str:
        """转换年级数字为名称"""
        grade_map = {
            1: "一年级", 2: "二年级", 3: "三年级", 4: "四年级",
            5: "五年级", 6: "六年级", 7: "初一", 8: "初二",
            9: "初三", 10: "高一", 11: "高二", 12: "高三"
        }
        return grade_map.get(grade, f"{grade}年级")

    def _parse_learning_report_response(self, content: str) -> dict:
        """解析LLM返回的报告内容"""
        import json
        import re

        # 尝试提取JSON
        json_match = re.search(r'\{.*\}', content, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(0))
            except json.JSONDecodeError:
                pass

        # 如果解析失败，返回一个错误结构
        raise Exception("无法解析LLM返回的报告内容，请重试")


# 全局单例
llm_service = LLMService()
