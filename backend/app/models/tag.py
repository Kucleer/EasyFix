from sqlalchemy import Column, Integer, String, ForeignKey, Table, Boolean
from sqlalchemy.orm import relationship
from app.database import Base


class Tag(Base):
    __tablename__ = "tag"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(50), nullable=False, unique=True)
    color = Column(String(20), nullable=True)
    deleted = Column(Boolean, default=False, nullable=False)  # 软删除标记

    # Relationships
    questions = relationship("Question", secondary="question_tag", back_populates="tags")


# 关联表
QuestionTag = Table(
    "question_tag",
    Base.metadata,
    Column("question_id", Integer, ForeignKey("question.id"), primary_key=True),
    Column("tag_id", Integer, ForeignKey("tag.id"), primary_key=True),
)
