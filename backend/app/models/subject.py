from sqlalchemy import Column, Integer, String, DateTime, func, Boolean
from sqlalchemy.orm import relationship
from app.database import Base


class Subject(Base):
    __tablename__ = "subject"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(50), nullable=False, unique=True)
    deleted = Column(Boolean, default=False, nullable=False)  # 软删除标记
    created_at = Column(DateTime, server_default=func.now())

    # Relationships
    error_books = relationship("ErrorBook", back_populates="subject")
    questions = relationship("Question", back_populates="subject")
    knowledge_points = relationship("KnowledgePoint", back_populates="subject")
    practice_sets = relationship("PracticeSet", back_populates="subject")
    learning_reports = relationship("LearningReport", back_populates="subject")
