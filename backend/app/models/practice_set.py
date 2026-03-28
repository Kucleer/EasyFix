from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, func, Boolean, Enum
from sqlalchemy.orm import relationship
from app.database import Base


class PracticeSet(Base):
    """练习集模型"""
    __tablename__ = "practice_set"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(200), nullable=False)  # 练习集名称
    subject_id = Column(Integer, ForeignKey("subject.id"), nullable=False)  # 所属学科
    question_type = Column(String(20), default="original")  # original=原题, similar=相似题
    pdf_path = Column(String(500), nullable=True)  # 生成的PDF路径
    total_questions = Column(Integer, default=0)  # 总题数
    reviewed = Column(Boolean, default=False)  # 是否已复习
    review_count = Column(Integer, default=0)  # 复习次数
    deleted = Column(Boolean, default=False, nullable=False)  # 软删除标记
    created_at = Column(DateTime, server_default=func.now())

    # Relationships
    subject = relationship("Subject", back_populates="practice_sets")
    practice_set_questions = relationship("PracticeSetQuestion", back_populates="practice_set", cascade="all, delete-orphan")


class PracticeSetQuestion(Base):
    """练习集-题目关联表"""
    __tablename__ = "practice_set_question"

    id = Column(Integer, primary_key=True, autoincrement=True)
    practice_set_id = Column(Integer, ForeignKey("practice_set.id"), nullable=False)
    question_id = Column(Integer, ForeignKey("question.id"), nullable=False)
    similar_question_id = Column(Integer, ForeignKey("similar_question.id"), nullable=True)  # 相似题ID，可为null
    display_order = Column(Integer, default=0)  # 显示顺序

    # Relationships
    practice_set = relationship("PracticeSet", back_populates="practice_set_questions")
    question = relationship("Question")
    similar_question = relationship("SimilarQuestion")
