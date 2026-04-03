from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import os

from app.database import engine, Base, SessionLocal
from app.routers import question_router, upload_router, stats_router, similar_router, config_router, error_book_router, subject_router, tag_router, knowledge_point_router, practice_set_router, word_router, learning_report_router, motivation_router
from app.config import get_settings
from app.access_config import ACCESS_PASSWORD
from app.services.init_motivation_data import init_preset_data, init_achievement_progress, init_star_records_from_existing_data

settings = get_settings()

# 创建数据库表
Base.metadata.create_all(bind=engine)

# 初始化激励系统预设数据
with SessionLocal() as db:
    init_preset_data(db)
    init_achievement_progress(db)
    init_star_records_from_existing_data(db)

app = FastAPI(
    title="EasyFix API",
    description="错题整理系统后端API",
    version="1.0.0",
)

# CORS配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境应限制
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 挂载静态文件服务（上传的图片）
uploads_path = os.path.abspath(settings.UPLOAD_DIR)
os.makedirs(uploads_path, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=uploads_path), name="uploads")

# 注册路由
app.include_router(question_router)
app.include_router(upload_router)
app.include_router(stats_router)
app.include_router(similar_router)
app.include_router(config_router)
app.include_router(error_book_router)
app.include_router(subject_router)
app.include_router(tag_router)
app.include_router(knowledge_point_router)
app.include_router(practice_set_router)
app.include_router(word_router)
app.include_router(learning_report_router)
app.include_router(motivation_router)


@app.get("/")
def root():
    return {"message": "EasyFix API", "version": "1.0.0"}


@app.get("/health")
def health_check():
    return {"status": "ok"}


class PasswordVerifyRequest(BaseModel):
    password: str


@app.post("/api/auth/verify-password")
def verify_password(data: PasswordVerifyRequest):
    """验证访问密码"""
    if data.password == ACCESS_PASSWORD:
        return {"success": True}
    raise HTTPException(status_code=401, detail="密码错误")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=True,
    )
