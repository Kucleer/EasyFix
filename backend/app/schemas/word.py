"""
单词相关 Pydantic Schemas
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class WordBase(BaseModel):
    """单词基础字段"""
    english: str = Field(..., min_length=1, max_length=200)
    chinese: str = Field(..., min_length=1)
    phonetic: Optional[str] = Field(None, max_length=100)
    grade: Optional[int] = Field(None, ge=1, le=12)
    semester: Optional[int] = Field(None, ge=1, le=2)


class WordCreate(WordBase):
    """创建单词"""
    tag_ids: Optional[List[int]] = []


class WordUpdate(BaseModel):
    """更新单词"""
    english: Optional[str] = Field(None, min_length=1, max_length=200)
    chinese: Optional[str] = None
    phonetic: Optional[str] = Field(None, max_length=100)
    grade: Optional[int] = Field(None, ge=1, le=12)
    semester: Optional[int] = Field(None, ge=1, le=2)
    tag_ids: Optional[List[int]] = None


class TagResponse(BaseModel):
    """标签响应"""
    id: int
    name: str
    color: Optional[str] = None

    class Config:
        from_attributes = True


class WordResponse(WordBase):
    """单词响应"""
    id: int
    review_count: int = 0
    correct_count: int = 0
    last_reviewed_at: Optional[datetime] = None
    next_review_at: Optional[datetime] = None
    tags: List[TagResponse] = []
    created_at: datetime

    class Config:
        from_attributes = True


class WordListResponse(BaseModel):
    """单词列表响应"""
    total: int
    items: List[WordResponse]


class ReviewLogResponse(BaseModel):
    """复习记录响应"""
    id: int
    word_id: int
    is_correct: bool
    user_answer: Optional[str] = None
    review_type: int
    reviewed_at: datetime

    class Config:
        from_attributes = True


class WordReviewSubmit(BaseModel):
    """提交复习结果"""
    word_id: int
    is_correct: bool
    user_answer: Optional[str] = None
    review_type: int = Field(..., description="复习题型 1=默写, 2=选择")


class ReviewSessionSubmit(BaseModel):
    """提交复习场次"""
    session_id: int
    results: List[WordReviewSubmit]
    duration: int = Field(0, description="用时秒数")


class WordStatsResponse(BaseModel):
    """单词统计响应"""
    total_words: int = 0
    total_reviews: int = 0
    total_correct: int = 0
    accuracy: float = 0.0
    mastered_words: int = 0  # 完全掌握的单词
    learning_words: int = 0  # 学习中
    new_words: int = 0  # 新单词
    grade_distribution: dict = {}  # 各年级分布
    review_today: int = 0  # 今日复习数
    due_words: int = 0  # 待复习数


class ReviewQuestion(BaseModel):
    """复习题目"""
    word_id: int
    english: str
    chinese: str
    word_length: int  # 单词长度
    options: Optional[List[str]] = None  # 选择题选项


class ReviewStartResponse(BaseModel):
    """开始复习响应"""
    session_id: int
    questions: List[ReviewQuestion]
    total: int
