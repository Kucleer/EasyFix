import os
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # Database
    DB_TYPE: str = "sqlite"  # "mysql" or "sqlite"
    DB_HOST: str = "localhost"
    DB_PORT: int = 3306
    DB_USER: str = "root"
    DB_PASSWORD: str = "123456"
    DB_NAME: str = "easyfix"
    DB_PATH: str = "easyfix.db"  # SQLite database file path

    # Upload
    UPLOAD_DIR: str = "uploads/images"
    MAX_UPLOAD_SIZE: int = 10 * 1024 * 1024  # 10MB

    # LLM
    OPENAI_API_KEY: str = ""
    OPENAI_BASE_URL: str = "https://api.openai.com/v1"
    LLM_MODEL: str = "gpt-4o"

    # Multimodal OCR Provider: openai / claude / qwen / none
    MULTIMODAL_PROVIDER: str = "none"
    OPENAI_VISION_MODEL: str = "gpt-4o"  # gpt-4o, gpt-4-turbo, gpt-4-vision-preview
    ANTHROPIC_API_KEY: str = ""
    CLAUDE_VISION_MODEL: str = "claude-3-sonnet-20240229"  # claude-3-haiku, claude-3-sonnet, claude-3-opus
    QWEN_API_KEY: str = ""
    QWEN_VISION_MODEL: str = "qwen-vl-max"  # qwen-vl-plus, qwen-vl-max

    # OCR Provider: paddleocr / tesseract / baidu / tencent / multimodal
    OCR_PROVIDER: str = "multimodal"

    # Baidu OCR (按量计费: ¥1/1000次)
    BAIDU_API_KEY: str = ""
    BAIDU_SECRET_KEY: str = ""

    # Tencent OCR (按量计费: ¥0.0015/次)
    TENCENT_APP_ID: str = ""
    TENCENT_SECRET_ID: str = ""
    TENCENT_SECRET_KEY: str = ""
    TENCENT_BUCKET: str = ""

    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    @property
    def DATABASE_URL(self) -> str:
        if self.DB_TYPE == "sqlite":
            return f"sqlite:///{self.DB_PATH}"
        return f"mysql+pymysql://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}?charset=utf8mb4"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
