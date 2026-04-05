from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel
from app.database import get_db
from app.models import ErrorType, Subject

router = APIRouter(prefix="/api/error-types", tags=["错误类型"])


class ErrorTypeResponse(BaseModel):
    id: int
    name: str
    subject_id: Optional[int] = None
    subject_name: Optional[str] = None
    created_at: Optional[str] = None

    class Config:
        from_attributes = True


class ErrorTypeCreate(BaseModel):
    name: str
    subject_id: Optional[int] = None


class ErrorTypeUpdate(BaseModel):
    name: Optional[str] = None
    subject_id: Optional[int] = None


@router.get("", response_model=List[ErrorTypeResponse])
def list_error_types(
    subject_id: Optional[int] = None,
    db: Session = Depends(get_db),
):
    """获取错误类型列表（排除已删除的）"""
    query = db.query(ErrorType).filter(ErrorType.deleted == False)

    if subject_id:
        # 同时返回该学科的和通用的（subject_id为空的）
        query = query.filter((ErrorType.subject_id == subject_id) | (ErrorType.subject_id.is_(None)))

    error_types = query.order_by(ErrorType.created_at.desc()).all()

    # 获取学科名称
    subjects = db.query(Subject).filter(Subject.deleted == False).all()
    subject_map = {s.id: s.name for s in subjects}

    result = []
    for et in error_types:
        result.append(ErrorTypeResponse(
            id=et.id,
            name=et.name,
            subject_id=et.subject_id,
            subject_name=subject_map.get(et.subject_id, "通用") if et.subject_id else "通用",
            created_at=et.created_at.isoformat() if et.created_at else None,
        ))

    return result


@router.post("", response_model=ErrorTypeResponse, status_code=201)
def create_error_type(data: ErrorTypeCreate, db: Session = Depends(get_db)):
    """创建错误类型"""
    # 如果有学科ID，检查学科是否存在
    if data.subject_id:
        subject = db.query(Subject).filter(Subject.id == data.subject_id, Subject.deleted == False).first()
        if not subject:
            raise HTTPException(status_code=400, detail="学科不存在")

    et = ErrorType(
        name=data.name,
        subject_id=data.subject_id,
    )
    db.add(et)
    db.commit()
    db.refresh(et)

    subject_name = "通用"
    if et.subject_id:
        subject = db.query(Subject).filter(Subject.id == et.subject_id, Subject.deleted == False).first()
        if subject:
            subject_name = subject.name

    return ErrorTypeResponse(
        id=et.id,
        name=et.name,
        subject_id=et.subject_id,
        subject_name=subject_name,
        created_at=et.created_at.isoformat() if et.created_at else None,
    )


@router.put("/{et_id}", response_model=ErrorTypeResponse)
def update_error_type(et_id: int, data: ErrorTypeUpdate, db: Session = Depends(get_db)):
    """更新错误类型"""
    et = db.query(ErrorType).filter(ErrorType.id == et_id, ErrorType.deleted == False).first()
    if not et:
        raise HTTPException(status_code=404, detail="错误类型不存在")

    if data.subject_id is not None:
        if data.subject_id:
            subject = db.query(Subject).filter(Subject.id == data.subject_id, Subject.deleted == False).first()
            if not subject:
                raise HTTPException(status_code=400, detail="学科不存在")
        et.subject_id = data.subject_id

    if data.name is not None:
        et.name = data.name

    db.commit()
    db.refresh(et)

    subject_name = "通用"
    if et.subject_id:
        subject = db.query(Subject).filter(Subject.id == et.subject_id, Subject.deleted == False).first()
        if subject:
            subject_name = subject.name

    return ErrorTypeResponse(
        id=et.id,
        name=et.name,
        subject_id=et.subject_id,
        subject_name=subject_name,
        created_at=et.created_at.isoformat() if et.created_at else None,
    )


@router.delete("/{et_id}", status_code=204)
def delete_error_type(et_id: int, db: Session = Depends(get_db)):
    """软删除错误类型"""
    et = db.query(ErrorType).filter(ErrorType.id == et_id, ErrorType.deleted == False).first()
    if not et:
        raise HTTPException(status_code=404, detail="错误类型不存在")

    et.deleted = True
    db.commit()