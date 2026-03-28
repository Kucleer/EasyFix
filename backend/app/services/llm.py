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


# 全局单例
llm_service = LLMService()
