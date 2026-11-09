import os
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # Database: sqlite / mysql / postgres
    DB_TYPE: str = "sqlite"  # "sqlite" | "mysql" | "postgres"
    DB_HOST: str = "localhost"
    DB_PORT: int = 3306
    DB_USER: str = "root"
    DB_PASSWORD: str = "123456"
    DB_NAME: str = "easyfix"
    DB_PATH: str = "easyfix.db"  # SQLite database file path

    # Upload - 图片存储在 backend/uploads/images
    UPLOAD_DIR: str = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "uploads", "images")
    MAX_UPLOAD_SIZE: int = 10 * 1024 * 1024  # 10MB
    PDF_BROWSER_CHANNEL: str = ""  # 默认使用 Playwright Chromium；本机可配置 msedge
    PDF_FONT_PATH: str = ""  # 可选：部署环境中的可分发中文字体绝对路径
    PDF_TIMEOUT_MS: int = 30000

    # LLM
    OPENAI_API_KEY: str = ""
    OPENAI_BASE_URL: str = "https://api.openai.com/v1"
    LLM_MODEL: str = "gpt-4o"

    ANTHROPIC_API_KEY: str = ""  # Claude 文本模型共享配置

    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8000  # 后端API端口

    @property
    def DATABASE_URL(self) -> str:
        if self.DB_TYPE == "sqlite":
            return f"sqlite:///{self.DB_PATH}"
        if self.DB_TYPE in ("postgres", "postgresql"):
            return (
                f"postgresql+psycopg2://{self.DB_USER}:{self.DB_PASSWORD}"
                f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
            )
        return f"mysql+pymysql://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}?charset=utf8mb4"

    class Config:
        extra = "ignore"  # 兼容旧环境文件中的已退役配置
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
