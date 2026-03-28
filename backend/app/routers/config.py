from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
import json
import os
from app.config import get_settings

router = APIRouter(prefix="/api/config", tags=["配置"])
settings = get_settings()


class OCRConfig(BaseModel):
    provider: str
    baidu_api_key: Optional[str] = ""
    baidu_secret_key: Optional[str] = ""
    tencent_app_id: Optional[str] = ""
    tencent_secret_id: Optional[str] = ""
    tencent_secret_key: Optional[str] = ""
    tencent_bucket: Optional[str] = ""
    multimodal_provider: Optional[str] = "none"
    openai_vision_model: Optional[str] = "gpt-4o"
    anthropic_api_key: Optional[str] = ""
    claude_vision_model: Optional[str] = "claude-3-sonnet-20240229"
    qwen_api_key: Optional[str] = ""
    qwen_vision_model: Optional[str] = "qwen-vl-max"


class LLMConfig(BaseModel):
    provider: str
    api_key: str
    base_url: str
    model: str


class CustomOCRConfig(BaseModel):
    api_url: str
    method: str = "POST"
    headers: str = ""
    body_template: str = ""
    response_parser: str = ""


@router.get("/ocr")
def get_ocr_config():
    """获取OCR配置"""
    config_file = "config/ocr.json"
    if os.path.exists(config_file):
        with open(config_file) as f:
            return json.load(f)
    return {
        "provider": settings.OCR_PROVIDER,
        "baidu_api_key": settings.BAIDU_API_KEY,
        "baidu_secret_key": settings.BAIDU_SECRET_KEY,
        "tencent_app_id": settings.TENCENT_APP_ID,
        "tencent_secret_id": settings.TENCENT_SECRET_ID,
        "tencent_secret_key": settings.TENCENT_SECRET_KEY,
        "tencent_bucket": settings.TENCENT_BUCKET,
        "multimodal_provider": settings.MULTIMODAL_PROVIDER,
        "openai_vision_model": settings.OPENAI_VISION_MODEL,
        "anthropic_api_key": settings.ANTHROPIC_API_KEY,
        "claude_vision_model": settings.CLAUDE_VISION_MODEL,
        "qwen_api_key": settings.QWEN_API_KEY,
        "qwen_vision_model": settings.QWEN_VISION_MODEL,
    }


@router.post("/ocr")
def save_ocr_config(config: OCRConfig):
    """保存OCR配置"""
    os.makedirs("config", exist_ok=True)
    config_file = "config/ocr.json"
    with open(config_file, 'w') as f:
        json.dump(config.model_dump(), f, indent=2)
    return {"message": "OCR配置已保存"}


@router.get("/llm")
def get_llm_config():
    """获取LLM配置"""
    config_file = "config/llm.json"
    if os.path.exists(config_file):
        with open(config_file) as f:
            return json.load(f)
    return {
        "provider": "openai",
        "api_key": settings.OPENAI_API_KEY,
        "base_url": settings.OPENAI_BASE_URL,
        "model": settings.LLM_MODEL,
    }


@router.post("/llm")
def save_llm_config(config: LLMConfig):
    """保存LLM配置"""
    os.makedirs("config", exist_ok=True)
    config_file = "config/llm.json"
    with open(config_file, 'w') as f:
        json.dump(config.model_dump(), f, indent=2)
    return {"message": "LLM配置已保存"}


@router.get("/custom-ocr")
def get_custom_ocr_config():
    """获取自定义OCR配置"""
    config_file = "config/custom_ocr.json"
    if os.path.exists(config_file):
        with open(config_file) as f:
            return json.load(f)
    return {
        "api_url": "",
        "method": "POST",
        "headers": "{}",
        "body_template": '{"image": "${base64_image}"}',
        "response_parser": "response.text || response.data",
    }


@router.post("/custom-ocr")
def save_custom_ocr_config(config: CustomOCRConfig):
    """保存自定义OCR配置"""
    os.makedirs("config", exist_ok=True)
    config_file = "config/custom_ocr.json"
    with open(config_file, 'w') as f:
        json.dump(config.model_dump(), f, indent=2)
    return {"message": "自定义OCR配置已保存"}
