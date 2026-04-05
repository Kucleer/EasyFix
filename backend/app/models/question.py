from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, func, CheckConstraint, Boolean
from sqlalchemy.orm import relationship
from app.database import Base


class Question(Base):
    __tablename__ = "question"

    id = Column(Integer, primary_key=True, autoincrement=True)
    error_book_id = Column(Integer, ForeignKey("error_book.id"), nullable=True)
    subject_id = Column(Integer, ForeignKey("subject.id"), nullable=False)
    original_image = Column(String(500), nullable=True)  # 单个图片路径（兼容）
    original_images = Column(Text, nullable=True)  # JSON数组，多个图片路径
    original_text = Column(Text, nullable=True)
    grade = Column(Integer, nullable=True)  # 年级 1-12
    semester = Column(Integer, nullable=True)  # 学期 1-2
    parsed_question = Column(Text, nullable=True)
    answer = Column(Text, nullable=True)
    analysis = Column(Text, nullable=True)
    analysis_image = Column(String(500), nullable=True)  # 答案解析图片
    difficulty = Column(Integer, default=3)
    error_type = Column(String(50), nullable=True)  # 计算/概念/审题/其他
    knowledge_point = Column(String(200), nullable=True)
    review_count = Column(Integer, default=0, nullable=False)  # 复习次数
    correct_count = Column(Integer, default=0, nullable=False)  # 正确次数
    error_count = Column(Integer, default=0, nullable=False)  # 错误次数
    last_reviewed_at = Column(DateTime, nullable=True)  # 最后复习时间
    deleted = Column(Boolean, default=False, nullable=False)  # 软删除标记
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now(), nullable=True)

    __table_args__ = (
        CheckConstraint("difficulty >= 1 AND difficulty <= 5", name="check_difficulty"),
    )

    # Relationships
    error_book = relationship("ErrorBook", back_populates="questions")
    subject = relationship("Subject", back_populates="questions")
    tags = relationship("Tag", secondary="question_tag", back_populates="questions")
    similar_questions = relationship("SimilarQuestion", back_populates="source_question")
    practice_set_questions = relationship("PracticeSetQuestion", back_populates="question")
