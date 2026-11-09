from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
import json
import os
from app.config import get_settings

router = APIRouter(prefix="/api/config", tags=["配置"])
settings = get_settings()




class LLMConfig(BaseModel):
    provider: str
    api_key: str
    base_url: str
    model: str




class AppConfig(BaseModel):
    """应用级默认配置（如默认年级）"""
    default_grade: Optional[int] = None
    default_semester: Optional[int] = None






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






@router.get("/app")
def get_app_config():
    """获取应用配置（默认年级/学期）"""
    config_file = "config/app.json"
    if os.path.exists(config_file):
        with open(config_file) as f:
            return json.load(f)
    return {"default_grade": None, "default_semester": None}


@router.post("/app")
def save_app_config(config: AppConfig):
    """保存应用配置（默认年级/学期）"""
    os.makedirs("config", exist_ok=True)
    config_file = "config/app.json"
    with open(config_file, 'w') as f:
        json.dump(config.model_dump(), f, indent=2)
    return {"message": "应用配置已保存", "data": config.model_dump()}
