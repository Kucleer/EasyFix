from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from pydantic import BaseModel
from app.database import get_db
from app.models import Subject

router = APIRouter(prefix="/api/subjects", tags=["学科"])


class SubjectResponse(BaseModel):
    id: int
    name: str

    class Config:
        from_attributes = True


class SubjectCreate(BaseModel):
    name: str


@router.get("", response_model=List[SubjectResponse])
def list_subjects(db: Session = Depends(get_db)):
    """获取所有学科（排除已删除的）"""
    # 只返回未删除的学科
    subjects = db.query(Subject).filter(Subject.deleted == False).all()
    return subjects


@router.post("", response_model=SubjectResponse, status_code=201)
def create_subject(data: SubjectCreate, db: Session = Depends(get_db)):
    """创建学科"""
    subject = Subject(name=data.name)
    db.add(subject)
    db.commit()
    db.refresh(subject)
    return subject


@router.delete("/{subject_id}", status_code=204)
def delete_subject(subject_id: int, db: Session = Depends(get_db)):
    """
    软删除学科（设置deleted=True），而非物理删除
    学科下的错题本、知识点等不受影响
    """
    subject = db.query(Subject).filter(Subject.id == subject_id, Subject.deleted == False).first()
    if not subject:
        raise HTTPException(status_code=404, detail="学科不存在")

    # 软删除：设置deleted标志为True
    subject.deleted = True
    db.commit()