from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, func, Boolean, Enum, Float
from sqlalchemy.orm import relationship
from app.database import Base


class PracticeSet(Base):
    """练习集模型"""
    __tablename__ = "practice_set"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(200), nullable=False)  # 练习集名称
    notes = Column(Text, nullable=True)  # 备注
    subject_id = Column(Integer, ForeignKey("subject.id"), nullable=False)  # 所属学科
    source_type = Column(String(20), default="question")  # question=来自错题, word=来自单词复习
    question_type = Column(String(20), default="original")  # original=原题, similar=相似题
    pdf_path = Column(String(500), nullable=True)  # 生成的PDF路径
    total_questions = Column(Integer, default=0)  # 总题数
    reviewed = Column(Boolean, default=False)  # 是否已复习
    review_count = Column(Integer, default=0)  # 复习次数
    accuracy = Column(Float, nullable=True)  # 整体正确率百分比
    last_reviewed_at = Column(DateTime, nullable=True)  # 最近复习时间
    review_images = Column(Text, nullable=True)  # JSON数组，复习完成上传的图片
    deleted = Column(Boolean, default=False, nullable=False)  # 软删除标记
    created_at = Column(DateTime, server_default=func.now())

    # Relationships
    subject = relationship("Subject", back_populates="practice_sets")
    practice_set_questions = relationship("PracticeSetQuestion", back_populates="practice_set", cascade="all, delete-orphan")
    word_review_sessions = relationship("WordReviewSession", back_populates="practice_set")


class PracticeSetQuestion(Base):
    """练习集-题目关联表"""
    __tablename__ = "practice_set_question"

    id = Column(Integer, primary_key=True, autoincrement=True)
    practice_set_id = Column(Integer, ForeignKey("practice_set.id"), nullable=False)
    question_id = Column(Integer, ForeignKey("question.id"), nullable=False)
    similar_question_id = Column(Integer, ForeignKey("similar_question.id"), nullable=True)  # 相似题ID，可为null
    is_correct = Column(Boolean, nullable=True)  # 批改是否正确
    display_order = Column(Integer, default=0)  # 显示顺序

    # Relationships
    practice_set = relationship("PracticeSet", back_populates="practice_set_questions")
    question = relationship("Question")
    similar_question = relationship("SimilarQuestion")


class WordReviewSession(Base):
    """单词复习场次（关联练习集）"""
    __tablename__ = "word_review_session"

    id = Column(Integer, primary_key=True, autoincrement=True)
    practice_set_id = Column(Integer, ForeignKey("practice_set.id"), nullable=True)  # 关联练习集
    session_id = Column(Integer, nullable=False)  # WordReview的session_id
    total_count = Column(Integer, default=0)  # 总单词数
    correct_count = Column(Integer, default=0)  # 正确数
    accuracy = Column(Integer, default=0)  # 正确率(%)
    duration = Column(Integer, default=0)  # 用时（秒）
    reviewed_at = Column(DateTime, server_default=func.now())  # 复习时间

    # Relationships
    practice_set = relationship("PracticeSet", back_populates="word_review_sessions")
