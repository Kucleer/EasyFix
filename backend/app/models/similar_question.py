from sqlalchemy import Column, Integer, String, Text, Float, DateTime, ForeignKey, func, Boolean
from sqlalchemy.orm import relationship
from app.database import Base


class SimilarQuestion(Base):
    __tablename__ = "similar_question"

    id = Column(Integer, primary_key=True, autoincrement=True)
    source_question_id = Column(Integer, ForeignKey("question.id"), nullable=False)
    similar_text = Column(Text, nullable=False)
    similar_answer = Column(Text, nullable=True)
    similarity_score = Column(Float, nullable=True)
    deleted = Column(Boolean, default=False, nullable=False)  # 软删除标记
    generated_at = Column(DateTime, server_default=func.now())

    # Relationships
    source_question = relationship("Question", back_populates="similar_questions")
    practice_set_questions = relationship("PracticeSetQuestion", back_populates="similar_question")
