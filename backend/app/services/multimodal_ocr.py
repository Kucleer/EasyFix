import os
import base64
import json
from typing import Optional
from app.config import get_settings

settings = get_settings()


def load_config() -> dict:
    """从config/ocr.json加载配置"""
    config_file = "config/ocr.json"
    if os.path.exists(config_file):
        with open(config_file) as f:
            return json.load(f)
    return {}


class MultimodalOCRService:
    """多模态模型OCR服务 - 支持GPT-4V、Claude Vision、Qwen-VL等"""

    def __init__(self):
        self._config = load_config()
        # 优先使用config文件中的配置，否则用环境变量
        self.provider = self._config.get("multimodal_provider", "none")
        self._available = self._check_available()

    def _get_config(self, key: str, default: str = "") -> str:
        """获取配置，优先从config文件，否则从环境变量"""
        return self._config.get(key, getattr(settings, key, default))

    def _check_available(self) -> bool:
        if self.provider == "openai":
            api_key = self._get_config("openai_api_key", settings.OPENAI_API_KEY)
            return bool(api_key)
        if self.provider == "claude":
            api_key = self._get_config("anthropic_api_key", settings.ANTHROPIC_API_KEY)
            return bool(api_key)
        if self.provider == "qwen":
            api_key = self._get_config("qwen_api_key", settings.QWEN_API_KEY)
            return bool(api_key)
        return False

    @property
    def is_available(self) -> bool:
        # 每次检查时重新加载配置
        self._config = load_config()
        self.provider = self._config.get("multimodal_provider", "none")
        return self._check_available()

    def recognize(self, image_path: str) -> dict:
        """
        使用多模态模型识别图片文字

        Returns:
            dict: {
                "full_text": str,
                "blocks": list,
                "provider": str,
                "model": str,
            }
        """
        # 重新加载配置
        self._config = load_config()
        self.provider = self._config.get("multimodal_provider", "none")
        self._check_available()

        if not self._available:
            return {
                "full_text": "",
                "blocks": [],
                "warning": f"Multimodal OCR provider '{self.provider}' not configured. Please set API key in settings.",
                "provider": self.provider,
            }

        try:
            if self.provider == "openai":
                return self._recognize_openai(image_path)
            elif self.provider == "claude":
                return self._recognize_claude(image_path)
            elif self.provider == "qwen":
                return self._recognize_qwen(image_path)
            else:
                return {"full_text": "", "blocks": [], "error": "Unknown provider"}
        except Exception as e:
            return {"full_text": "", "blocks": [], "error": str(e), "provider": self.provider}

    def _read_image_base64(self, image_path: str) -> str:
        with open(image_path, 'rb') as f:
            return base64.b64encode(f.read()).decode()

    def _recognize_openai(self, image_path: str) -> dict:
        """使用OpenAI GPT-4V/4o进行OCR"""
        from openai import OpenAI

        api_key = self._get_config("openai_api_key", settings.OPENAI_API_KEY)
        base_url = self._get_config("base_url", settings.OPENAI_BASE_URL)
        model = self._get_config("openai_vision_model", settings.OPENAI_VISION_MODEL)

        client = OpenAI(
            api_key=api_key,
            base_url=base_url,
        )

        base64_image = self._read_image_base64(image_path)

        response = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "请识别图片中的所有文字，保持原有格式和排版。如果图片中有数学公式、符号等，请准确识别并用标准格式表示。直接输出识别结果，不需要其他说明。"
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{base64_image}"
                            }
                        }
                    ]
                }
            ],
            max_tokens=4096,
        )

        full_text = response.choices[0].message.content
        return {
            "full_text": full_text,
            "blocks": [{"text": line.strip()} for line in full_text.split('\n') if line.strip()],
            "provider": "openai",
            "model": model,
        }

    def _recognize_claude(self, image_path: str) -> dict:
        """使用Anthropic Claude Vision进行OCR"""
        import anthropic

        api_key = self._get_config("anthropic_api_key", settings.ANTHROPIC_API_KEY)
        model = self._get_config("claude_vision_model", settings.CLAUDE_VISION_MODEL)

        client = anthropic.Anthropic(
            api_key=api_key,
        )

        with open(image_path, 'rb') as f:
            image_data = base64.b64encode(f.read()).decode()

        response = client.messages.create(
            model=model,
            max_tokens=4096,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/jpeg",
                                "data": image_data,
                            }
                        },
                        {
                            "type": "text",
                            "text": "请识别图片中的所有文字，保持原有格式和排版。如果图片中有数学公式、符号等，请准确识别并用标准格式表示。直接输出识别结果，不需要其他说明。"
                        }
                    ]
                }
            ]
        )

        full_text = response.content[0].text
        return {
            "full_text": full_text,
            "blocks": [{"text": line.strip()} for line in full_text.split('\n') if line.strip()],
            "provider": "claude",
            "model": model,
        }

    def _recognize_qwen(self, image_path: str) -> dict:
        """使用阿里Qwen-VL进行OCR"""
        from openai import OpenAI

        api_key = self._get_config("qwen_api_key", settings.QWEN_API_KEY)
        model = self._get_config("qwen_vision_model", settings.QWEN_VISION_MODEL)

        client = OpenAI(
            api_key=api_key,
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        )

        base64_image = self._read_image_base64(image_path)

        response = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{base64_image}"
                            }
                        },
                        {
                            "type": "text",
                            "text": "请识别图片中的所有文字，保持原有格式和排版。如果图片中有数学公式、符号等，请准确识别并用标准格式表示。直接输出识别结果，不需要其他说明。"
                        }
                    ]
                }
            ],
            max_tokens=4096,
        )

        full_text = response.choices[0].message.content
        return {
            "full_text": full_text,
            "blocks": [{"text": line.strip()} for line in full_text.split('\n') if line.strip()],
            "provider": "qwen",
            "model": model,
        }


# 全局单例
multimodal_ocr_service = MultimodalOCRService()
