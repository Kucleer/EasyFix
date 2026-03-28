import json
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional
from app.database import get_db
from app.models import ErrorBook, Subject
from app.schemas import ErrorBookCreate, ErrorBookUpdate, ErrorBookResponse, ErrorBookListResponse
from app.services.logger import logger_service

router = APIRouter(prefix="/api/error-books", tags=["错题本"])


@router.get("", response_model=ErrorBookListResponse)
def list_error_books(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    subject_id: Optional[int] = None,
    db: Session = Depends(get_db),
):
    """获取错题本列表（排除已删除的）"""
    # 只返回未删除的错题本
    query = db.query(ErrorBook).filter(ErrorBook.deleted == False)

    if subject_id:
        query = query.filter(ErrorBook.subject_id == subject_id)

    total = query.count()
    items = query.order_by(ErrorBook.created_at.desc()).offset(skip).limit(limit).all()

    # 转换original_images
    result_items = []
    for item in items:
        item_dict = {
            "id": item.id,
            "name": item.name,
            "subject_id": item.subject_id,
            "description": item.description,
            "cover_image": item.cover_image,
            "original_images": json.loads(item.original_images or "[]") if item.original_images else [],
            "created_at": item.created_at,
            "updated_at": item.updated_at,
        }
        result_items.append(ErrorBookResponse(**item_dict))

    return {"total": total, "items": result_items}


@router.get("/{error_book_id}", response_model=ErrorBookResponse)
def get_error_book(error_book_id: int, db: Session = Depends(get_db)):
    """获取单个错题本"""
    # 只获取未删除的记录
    error_book = db.query(ErrorBook).filter(ErrorBook.id == error_book_id, ErrorBook.deleted == False).first()
    if not error_book:
        raise HTTPException(status_code=404, detail="错题本不存在")

    return {
        "id": error_book.id,
        "name": error_book.name,
        "subject_id": error_book.subject_id,
        "description": error_book.description,
        "cover_image": error_book.cover_image,
        "original_images": json.loads(error_book.original_images or "[]") if error_book.original_images else [],
        "created_at": error_book.created_at,
        "updated_at": error_book.updated_at,
    }


@router.post("", response_model=ErrorBookResponse, status_code=201)
def create_error_book(data: ErrorBookCreate, db: Session = Depends(get_db)):
    """创建错题本"""
    # 检查学科是否存在（且未删除）
    subject = db.query(Subject).filter(Subject.id == data.subject_id, Subject.deleted == False).first()
    if not subject:
        raise HTTPException(status_code=400, detail="学科不存在")

    error_book = ErrorBook(
        name=data.name,
        subject_id=data.subject_id,
        description=data.description,
        cover_image=data.cover_image,
        original_images=json.dumps(data.original_images or [], ensure_ascii=False) if data.original_images else None,
    )
    db.add(error_book)
    db.commit()
    db.refresh(error_book)

    # 记录日志
    logger_service.log_error_book(
        operation="create_error_book",
        error_book_id=error_book.id,
        data={"name": data.name, "subject_id": data.subject_id},
        success=True,
    )

    return {
        "id": error_book.id,
        "name": error_book.name,
        "subject_id": error_book.subject_id,
        "description": error_book.description,
        "cover_image": error_book.cover_image,
        "original_images": json.loads(error_book.original_images or "[]") if error_book.original_images else [],
        "created_at": error_book.created_at,
        "updated_at": error_book.updated_at,
    }


@router.put("/{error_book_id}", response_model=ErrorBookResponse)
def update_error_book(
    error_book_id: int,
    data: ErrorBookUpdate,
    db: Session = Depends(get_db),
):
    """更新错题本"""
    error_book = db.query(ErrorBook).filter(ErrorBook.id == error_book_id, ErrorBook.deleted == False).first()
    if not error_book:
        raise HTTPException(status_code=404, detail="错题本不存在")

    update_data = data.model_dump(exclude_unset=True)

    # 处理original_images
    if "original_images" in update_data:
        update_data["original_images"] = json.dumps(update_data["original_images"], ensure_ascii=False)

    for key, value in update_data.items():
        setattr(error_book, key, value)

    db.commit()
    db.refresh(error_book)

    # 记录日志
    logger_service.log_error_book(
        operation="update_error_book",
        error_book_id=error_book.id,
        data=update_data,
        success=True,
    )

    return {
        "id": error_book.id,
        "name": error_book.name,
        "subject_id": error_book.subject_id,
        "description": error_book.description,
        "cover_image": error_book.cover_image,
        "original_images": json.loads(error_book.original_images or "[]") if error_book.original_images else [],
        "created_at": error_book.created_at,
        "updated_at": error_book.updated_at,
    }


@router.delete("/{error_book_id}", status_code=204)
def delete_error_book(error_book_id: int, db: Session = Depends(get_db)):
    """
    软删除错题本（设置deleted=True），而非物理删除
    错题本下的错题不受影响（仍可通过error_book_id关联查询）
    """
    error_book = db.query(ErrorBook).filter(ErrorBook.id == error_book_id, ErrorBook.deleted == False).first()
    if not error_book:
        raise HTTPException(status_code=404, detail="错题本不存在")

    # 软删除：设置deleted标志为True
    error_book.deleted = True
    db.commit()

    # 记录日志
    logger_service.log_error_book(
        operation="delete_error_book",
        error_book_id=error_book_id,
        data={"soft_delete": True},
        success=True,
    )