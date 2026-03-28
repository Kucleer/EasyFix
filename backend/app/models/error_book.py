from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, func, Boolean
from sqlalchemy.orm import relationship
from app.database import Base


class ErrorBook(Base):
    __tablename__ = "error_book"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    subject_id = Column(Integer, ForeignKey("subject.id"), nullable=False)
    description = Column(Text, nullable=True)
    cover_image = Column(String(500), nullable=True)  # 封面图片路径（用于对比）
    original_images = Column(Text, nullable=True)   # JSON数组，存储多张原图路径
    deleted = Column(Boolean, default=False, nullable=False)  # 软删除标记
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now(), nullable=True)

    # Relationships
    subject = relationship("Subject", back_populates="error_books")
    questions = relationship("Question", back_populates="error_book")
