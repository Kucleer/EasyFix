"""
单词模型 - 存储单词信息及复习记录
"""
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey, Table
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base


# 单词-标签关联表
word_tag = Table(
    "word_tag",
    Base.metadata,
    Column("word_id", Integer, ForeignKey("word.id"), primary_key=True),
    Column("tag_id", Integer, ForeignKey("tag.id"), primary_key=True),
)


class Word(Base):
    """单词表"""
    __tablename__ = "word"

    id = Column(Integer, primary_key=True, autoincrement=True)
    english = Column(String(200), nullable=False, index=True)  # 英文单词
    chinese = Column(Text, nullable=False)  # 中文释义
    phonetic = Column(String(100), nullable=True)  # 音标
    grade = Column(Integer, nullable=True)  # 年级 1-12
    semester = Column(Integer, nullable=True)  # 学期 1=上学期, 2=下学期

    # 复习相关
    review_count = Column(Integer, default=0)  # 复习次数
    correct_count = Column(Integer, default=0)  # 正确次数
    last_reviewed_at = Column(DateTime, nullable=True)  # 上次复习时间
    next_review_at = Column(DateTime, nullable=True)  # 下次复习时间

    # 记忆曲线参数（艾宾浩斯）
    ease_factor = Column(Integer, default=250)  # 难度因子（单位：分钟）
    interval = Column(Integer, default=1)  # 当前间隔天数

    # 软删除
    deleted = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.now, nullable=False)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, nullable=False)

    # 关系
    tags = relationship("Tag", secondary=word_tag, back_populates="words")
    review_logs = relationship("WordReviewLog", back_populates="word")


class WordReviewLog(Base):
    """单词复习记录表"""
    __tablename__ = "word_review_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    word_id = Column(Integer, ForeignKey("word.id"), nullable=False)
    is_correct = Column(Boolean, nullable=False)  # 是否正确
    user_answer = Column(Text, nullable=True)  # 用户答案
    review_type = Column(Integer, nullable=False)  # 复习题型 1=默写, 2=选择
    reviewed_at = Column(DateTime, default=datetime.now, nullable=False)
    deleted = Column(Boolean, default=False, nullable=False)  # 软删除

    # 关系
    word = relationship("Word", back_populates="review_logs")


class WordReview(Base):
    """复习场次表"""
    __tablename__ = "word_review"

    id = Column(Integer, primary_key=True, autoincrement=True)
    total_count = Column(Integer, default=0)  # 总单词数
    correct_count = Column(Integer, default=0)  # 正确数
    error_count = Column(Integer, default=0)  # 错误数
    duration = Column(Integer, default=0)  # 用时（秒）
    reviewed_at = Column(DateTime, default=datetime.now, nullable=False)
