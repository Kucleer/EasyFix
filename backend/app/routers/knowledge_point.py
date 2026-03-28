from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel
from app.database import get_db
from app.models import KnowledgePoint, Subject

router = APIRouter(prefix="/api/knowledge-points", tags=["知识点"])


class KnowledgePointResponse(BaseModel):
    id: int
    name: str
    subject_id: int
    subject_name: Optional[str] = None
    grade: Optional[int] = None
    semester: Optional[int] = None
    created_at: Optional[str] = None

    class Config:
        from_attributes = True


class KnowledgePointCreate(BaseModel):
    name: str
    subject_id: int
    grade: Optional[int] = None
    semester: Optional[int] = None


@router.get("", response_model=List[KnowledgePointResponse])
def list_knowledge_points(
    subject_id: Optional[int] = None,
    grade: Optional[int] = None,
    semester: Optional[int] = None,
    db: Session = Depends(get_db),
):
    """获取知识点列表（排除已删除的）"""
    # 只返回未删除的知识点
    query = db.query(KnowledgePoint).filter(KnowledgePoint.deleted == False)

    if subject_id:
        query = query.filter(KnowledgePoint.subject_id == subject_id)
    if grade:
        query = query.filter(KnowledgePoint.grade == grade)
    if semester:
        query = query.filter(KnowledgePoint.semester == semester)

    knowledge_points = query.order_by(KnowledgePoint.created_at.desc()).all()

    # 获取学科名称（只取未删除的学科）
    subjects = db.query(Subject).filter(Subject.deleted == False).all()
    subject_map = {s.id: s.name for s in subjects}

    result = []
    for kp in knowledge_points:
        result.append(KnowledgePointResponse(
            id=kp.id,
            name=kp.name,
            subject_id=kp.subject_id,
            subject_name=subject_map.get(kp.subject_id, ""),
            grade=kp.grade,
            semester=kp.semester,
            created_at=kp.created_at.isoformat() if kp.created_at else None,
        ))

    return result


@router.post("", response_model=KnowledgePointResponse, status_code=201)
def create_knowledge_point(data: KnowledgePointCreate, db: Session = Depends(get_db)):
    """创建知识点"""
    # 检查学科是否存在（且未删除）
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
    db.commit()
    db.refresh(kp)

    return KnowledgePointResponse(
        id=kp.id,
        name=kp.name,
        subject_id=kp.subject_id,
        subject_name=subject.name,
        grade=kp.grade,
        semester=kp.semester,
        created_at=kp.created_at.isoformat() if kp.created_at else None,
    )


@router.delete("/{kp_id}", status_code=204)
def delete_knowledge_point(kp_id: int, db: Session = Depends(get_db)):
    """
    软删除知识点（设置deleted=True），而非物理删除
    """
    kp = db.query(KnowledgePoint).filter(KnowledgePoint.id == kp_id, KnowledgePoint.deleted == False).first()
    if not kp:
        raise HTTPException(status_code=404, detail="知识点不存在")

    # 软删除：设置deleted标志为True
    kp.deleted = True
    db.commit()