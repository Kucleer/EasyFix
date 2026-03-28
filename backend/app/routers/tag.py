from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from pydantic import BaseModel
from app.database import get_db
from app.models import Tag

router = APIRouter(prefix="/api/tags", tags=["标签"])


class TagResponse(BaseModel):
    id: int
    name: str
    color: str = None

    class Config:
        from_attributes = True


class TagCreate(BaseModel):
    name: str
    color: str = None


@router.get("", response_model=List[TagResponse])
def list_tags(db: Session = Depends(get_db)):
    """获取所有标签（排除已删除的）"""
    # 只返回未删除的标签
    tags = db.query(Tag).filter(Tag.deleted == False).all()
    return tags


@router.post("", response_model=TagResponse, status_code=201)
def create_tag(data: TagCreate, db: Session = Depends(get_db)):
    """创建标签"""
    tag = Tag(name=data.name, color=data.color)
    db.add(tag)
    db.commit()
    db.refresh(tag)
    return tag


@router.delete("/{tag_id}", status_code=204)
def delete_tag(tag_id: int, db: Session = Depends(get_db)):
    """
    软删除标签（设置deleted=True），而非物理删除
    标签与错题的关联关系不受影响
    """
    tag = db.query(Tag).filter(Tag.id == tag_id, Tag.deleted == False).first()
    if not tag:
        raise HTTPException(status_code=404, detail="标签不存在")

    # 软删除：设置deleted标志为True
    tag.deleted = True
    db.commit()