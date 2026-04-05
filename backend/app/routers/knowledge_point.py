from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel
from app.database import get_db
from app.models import KnowledgePoint, Subject, ErrorType

router = APIRouter(prefix="/api/knowledge-points", tags=["知识点"])


class ErrorTypeSimple(BaseModel):
    id: int
    name: str

    class Config:
        from_attributes = True


class KnowledgePointResponse(BaseModel):
    id: int
    name: str
    subject_id: int
    subject_name: Optional[str] = None
    grade: Optional[int] = None
    semester: Optional[int] = None
    created_at: Optional[str] = None
    error_types: List[ErrorTypeSimple] = []

    class Config:
        from_attributes = True


class KnowledgePointCreate(BaseModel):
    name: str
    subject_id: int
    grade: Optional[int] = None
    semester: Optional[int] = None
    error_type_ids: Optional[List[int]] = []


class KnowledgePointUpdate(BaseModel):
    name: Optional[str] = None
    subject_id: Optional[int] = None
    grade: Optional[int] = None
    semester: Optional[int] = None
    error_type_ids: Optional[List[int]] = None


@router.get("", response_model=List[KnowledgePointResponse])
def list_knowledge_points(
    subject_id: Optional[int] = None,
    grade: Optional[int] = None,
    semester: Optional[int] = None,
    db: Session = Depends(get_db),
):
    """获取知识点列表（排除已删除的）"""
    query = db.query(KnowledgePoint).filter(KnowledgePoint.deleted == False)

    if subject_id:
        query = query.filter(KnowledgePoint.subject_id == subject_id)
    if grade:
        query = query.filter(KnowledgePoint.grade == grade)
    if semester:
        query = query.filter(KnowledgePoint.semester == semester)

    knowledge_points = query.order_by(KnowledgePoint.created_at.desc()).all()

    # 获取学科名称
    subjects = db.query(Subject).filter(Subject.deleted == False).all()
    subject_map = {s.id: s.name for s in subjects}

    result = []
    for kp in knowledge_points:
        error_types = []
        for et in kp.error_types:
            if not et.deleted:
                error_types.append(ErrorTypeSimple(id=et.id, name=et.name))
        result.append(KnowledgePointResponse(
            id=kp.id,
            name=kp.name,
            subject_id=kp.subject_id,
            subject_name=subject_map.get(kp.subject_id, ""),
            grade=kp.grade,
            semester=kp.semester,
            created_at=kp.created_at.isoformat() if kp.created_at else None,
            error_types=error_types,
        ))

    return result


@router.post("", response_model=KnowledgePointResponse, status_code=201)
def create_knowledge_point(data: KnowledgePointCreate, db: Session = Depends(get_db)):
    """创建知识点"""
    subject = db.query(Subject).filter(Subject.id == data.subject_id, Subject.deleted == False).first()
    if not subject:
        raise HTTPException(status_code=400, detail="学科不存在")

    kp = KnowledgePoint(
        name=data.name,
        subject_id=data.subject_id,
        grade=data.grade,
        semester=data.semester,
    )
    db.add(kp)
    db.flush()

    # 关联错误类型
    if data.error_type_ids:
        for et_id in data.error_type_ids:
            et = db.query(ErrorType).filter(ErrorType.id == et_id, ErrorType.deleted == False).first()
            if et:
                kp.error_types.append(et)

    db.commit()
    db.refresh(kp)

    error_types = []
    for et in kp.error_types:
        if not et.deleted:
            error_types.append(ErrorTypeSimple(id=et.id, name=et.name))

    return KnowledgePointResponse(
        id=kp.id,
        name=kp.name,
        subject_id=kp.subject_id,
        subject_name=subject.name,
        grade=kp.grade,
        semester=kp.semester,
        created_at=kp.created_at.isoformat() if kp.created_at else None,
        error_types=error_types,
    )


@router.put("/{kp_id}", response_model=KnowledgePointResponse)
def update_knowledge_point(kp_id: int, data: KnowledgePointUpdate, db: Session = Depends(get_db)):
    """更新知识点"""
    kp = db.query(KnowledgePoint).filter(KnowledgePoint.id == kp_id, KnowledgePoint.deleted == False).first()
    if not kp:
        raise HTTPException(status_code=404, detail="知识点不存在")

    if data.subject_id is not None:
        subject = db.query(Subject).filter(Subject.id == data.subject_id, Subject.deleted == False).first()
        if not subject:
            raise HTTPException(status_code=400, detail="学科不存在")
        kp.subject_id = data.subject_id

    if data.name is not None:
        kp.name = data.name
    if data.grade is not None:
        kp.grade = data.grade
    if data.semester is not None:
        kp.semester = data.semester

    # 更新错误类型关联
    if data.error_type_ids is not None:
        kp.error_types = []
        for et_id in data.error_type_ids:
            et = db.query(ErrorType).filter(ErrorType.id == et_id, ErrorType.deleted == False).first()
            if et:
                kp.error_types.append(et)

    db.commit()
    db.refresh(kp)

    subject = db.query(Subject).filter(Subject.id == kp.subject_id, Subject.deleted == False).first()
    subject_name = subject.name if subject else ""

    error_types = []
    for et in kp.error_types:
        if not et.deleted:
            error_types.append(ErrorTypeSimple(id=et.id, name=et.name))

    return KnowledgePointResponse(
        id=kp.id,
        name=kp.name,
        subject_id=kp.subject_id,
        subject_name=subject_name,
        grade=kp.grade,
        semester=kp.semester,
        created_at=kp.created_at.isoformat() if kp.created_at else None,
        error_types=error_types,
    )


@router.delete("/{kp_id}", status_code=204)
def delete_knowledge_point(kp_id: int, db: Session = Depends(get_db)):
    """软删除知识点"""
    kp = db.query(KnowledgePoint).filter(KnowledgePoint.id == kp_id, KnowledgePoint.deleted == False).first()
    if not kp:
        raise HTTPException(status_code=404, detail="知识点不存在")

    kp.deleted = True
    db.commit()