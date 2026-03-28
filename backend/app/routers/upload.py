import os
import uuid
import json
from datetime import datetime
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional
from app.database import get_db
from app.services.ocr import ocr_service
from app.services.logger import logger_service
from app.config import get_settings

router = APIRouter(prefix="/api/upload", tags=["上传"])
settings = get_settings()


class UploadResponse(BaseModel):
    image_path: str
    ocr_result: dict


class BatchUploadResponse(BaseModel):
    images: List[dict]  # 每个图片的信息
    total_count: int
    success_count: int
    failed_count: int


async def _save_image(file: UploadFile) -> dict:
    """保存图片并返回信息"""
    # 验证文件类型
    allowed_types = ["image/jpeg", "image/png", "image/jpg", "image/webp"]
    if file.content_type not in allowed_types:
        return {"error": f"不支持的文件类型: {file.content_type}"}

    # 读取文件内容
    content = await file.read()

    # 验证文件大小
    if len(content) > settings.MAX_UPLOAD_SIZE:
        return {"error": f"文件大小超过限制: {settings.MAX_UPLOAD_SIZE // (1024*1024)}MB"}

    # 生成存储路径
    now = datetime.now()
    year = now.strftime("%Y")
    month = now.strftime("%m")
    file_uuid = str(uuid.uuid4())[:8]
    ext = os.path.splitext(file.filename)[1] or ".jpg"
    safe_filename = file.filename.replace("/", "_").replace("\\", "_")
    filename = f"{file_uuid}_{safe_filename}"
    # 存储在 UPLOAD_DIR/year/month/ 下
    relative_dir = os.path.join(year, month)
    relative_path = os.path.join(relative_dir, filename)
    absolute_dir = os.path.abspath(os.path.join(settings.UPLOAD_DIR, year, month))
    absolute_path = os.path.join(absolute_dir, filename)

    # 创建目录并保存文件
    os.makedirs(absolute_dir, exist_ok=True)
    with open(absolute_path, "wb") as f:
        f.write(content)

    # 返回相对路径（统一使用正斜杠）
    # 路径格式: year/month/filename.jpg
    url_path = relative_path.replace("\\", "/")
    return {
        "image_path": url_path,
        "absolute_path": absolute_path,
        "original_filename": file.filename,
        "size": len(content),
    }


@router.post("/image", response_model=UploadResponse)
async def upload_image(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """
    上传单张图片并进行OCR识别

    Returns:
        {
            "image_path": str,
            "ocr_result": {
                "full_text": str,
                "blocks": list,
                "provider": str,
            }
        }
    """
    # 保存图片
    result = await _save_image(file)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])

    image_path = result["image_path"]
    absolute_path = result["absolute_path"]

    # 记录上传日志
    logger_service.log_upload(
        image_path=image_path,
        ocr_result={"status": "processing"},
        success=True,
    )

    # 执行OCR识别
    try:
        ocr_result = ocr_service.recognize(absolute_path)
    except Exception as e:
        error_msg = str(e)
        logger_service.log_upload(
            image_path=image_path,
            ocr_result={},
            success=False,
            error=error_msg,
        )
        raise HTTPException(status_code=500, detail=f"OCR识别失败: {error_msg}")

    # 记录OCR日志
    logger_service.log_ocr(
        image_path=image_path,
        result=ocr_result,
        provider=ocr_result.get("provider", "unknown"),
        success=True,
    )

    return {
        "image_path": image_path,
        "ocr_result": ocr_result,
    }


@router.post("/batch", response_model=BatchUploadResponse)
async def upload_batch_images(
    files: List[UploadFile] = File(...),
    db: Session = Depends(get_db),
):
    """
    批量上传多张图片，每张图片单独进行OCR识别

    Returns:
        {
            "images": [
                {
                    "image_path": str,
                    "ocr_result": {...},
                    "original_filename": str,
                },
                ...
            ],
            "total_count": int,
            "success_count": int,
            "failed_count": int,
        }
    """
    results = []
    success_count = 0
    failed_count = 0

    for file in files:
        # 保存图片
        save_result = await _save_image(file)

        if "error" in save_result:
            results.append({
                "original_filename": file.filename,
                "success": False,
                "error": save_result["error"],
            })
            failed_count += 1
            logger_service.log_upload(
                image_path="",
                ocr_result={},
                success=False,
                error=save_result["error"],
            )
            continue

        image_path = save_result["image_path"]
        absolute_path = save_result["absolute_path"]

        # 执行OCR识别
        try:
            ocr_result = ocr_service.recognize(absolute_path)
            results.append({
                "image_path": image_path,
                "ocr_result": ocr_result,
                "original_filename": file.filename,
                "size": save_result["size"],
                "success": True,
            })
            success_count += 1

            logger_service.log_ocr(
                image_path=image_path,
                result=ocr_result,
                provider=ocr_result.get("provider", "unknown"),
                success=True,
            )
        except Exception as e:
            error_msg = str(e)
            results.append({
                "image_path": image_path,
                "ocr_result": {},
                "original_filename": file.filename,
                "success": False,
                "error": error_msg,
            })
            failed_count += 1

            logger_service.log_ocr(
                image_path=image_path,
                result={},
                provider="unknown",
                success=False,
                error=error_msg,
            )

    return {
        "images": results,
        "total_count": len(files),
        "success_count": success_count,
        "failed_count": failed_count,
    }


@router.post("/to-error-book/{error_book_id}")
async def upload_to_error_book(
    error_book_id: int,
    files: List[UploadFile] = File(...),
    db: Session = Depends(get_db),
):
    """
    上传图片到指定错题本，图片保留在错题本中用于对比

    Returns:
        {
            "error_book_id": int,
            "images": [...],
        }
    """
    from app.models import ErrorBook

    # 检查错题本是否存在
    error_book = db.query(ErrorBook).filter(ErrorBook.id == error_book_id).first()
    if not error_book:
        raise HTTPException(status_code=404, detail="错题本不存在")

    results = []
    for file in files:
        save_result = await _save_image(file)

        if "error" in save_result:
            continue

        results.append({
            "image_path": save_result["image_path"],
            "original_filename": file.filename,
            "size": save_result["size"],
        })

        # 记录上传日志
        logger_service.log_upload(
            image_path=save_result["image_path"],
            ocr_result={"stored": True},
            success=True,
        )

    # 更新错题本的original_images字段
    existing_images = json.loads(error_book.original_images or "[]")
    new_images = [r["image_path"] for r in results]
    all_images = existing_images + new_images
    error_book.original_images = json.dumps(all_images, ensure_ascii=False)

    # 如果没有封面图，设置第一张为封面
    if not error_book.cover_image and results:
        error_book.cover_image = results[0]["image_path"]

    db.commit()

    return {
        "error_book_id": error_book_id,
        "images": results,
        "total_images": len(all_images),
    }
