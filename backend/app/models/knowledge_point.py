from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, func, Boolean, Table
from sqlalchemy.orm import relationship
from app.database import Base


# 知识点-错误类型关联表
kp_error_type = Table(
    "kp_error_type",
    Base.metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("knowledge_point_id", Integer, ForeignKey("knowledge_point.id", ondelete="CASCADE"), nullable=False),
    Column("error_type_id", Integer, ForeignKey("error_type.id", ondelete="CASCADE"), nullable=False),
)


class KnowledgePoint(Base):
    __tablename__ = "knowledge_point"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(200), nullable=False)
    subject_id = Column(Integer, ForeignKey("subject.id"), nullable=False)
    grade = Column(Integer, nullable=True)  # 年级 1-12
    semester = Column(Integer, nullable=True)  # 学期 1-2
    deleted = Column(Boolean, default=False, nullable=False)  # 软删除标记
    created_at = Column(DateTime, server_default=func.now())

    # Relationships
    subject = relationship("Subject", back_populates="knowledge_points")
    error_types = relationship("ErrorType", secondary=kp_error_type, back_populates="knowledge_points")
