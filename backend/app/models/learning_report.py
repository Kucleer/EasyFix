from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, func, Boolean, Float
from sqlalchemy.orm import relationship
from app.database import Base


class LearningReport(Base):
    """学习状态分析报告表"""
    __tablename__ = "learning_report"

    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(200), nullable=False)  # 报告标题
    # 筛选条件
    subject_id = Column(Integer, ForeignKey("subject.id"), nullable=True)  # 学科筛选，可为空表示全科
    grade = Column(Integer, nullable=True)  # 年级筛选，可为空表示全部
    time_range_days = Column(Integer, nullable=True)  # 时间范围（天数），可为空表示全部时间
    # 报告内容（JSON格式存储多维度分析结果）
    content = Column(Text, nullable=False)
    # 统计摘要
    total_questions = Column(Integer, default=0)  # 分析的错题总数
    total_words = Column(Integer, default=0)  # 分析的单词总数
    overall_accuracy = Column(Float, default=0.0)  # 整体准确率
    # 元数据
    deleted = Column(Boolean, default=False, nullable=False)  # 软删除标记
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now(), nullable=True)

    # Relationships
    subject = relationship("Subject", back_populates="learning_reports")
