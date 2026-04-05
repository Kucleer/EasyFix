from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, func
from sqlalchemy.orm import relationship
from app.database import Base


class ErrorType(Base):
    """错误类型表"""
    __tablename__ = "error_type"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(50), nullable=False)  # 错误类型名称
    subject_id = Column(Integer, ForeignKey("subject.id"), nullable=True)  # 学科ID，可为空表示通用
    deleted = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, server_default=func.now())

    # Relationships
    knowledge_points = relationship("KnowledgePoint", secondary="kp_error_type", back_populates="error_types")