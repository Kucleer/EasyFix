from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class QuestionBase(BaseModel):
    error_book_id: Optional[int] = None
    subject_id: int
    grade: Optional[int] = Field(default=None, ge=1, le=12)  # 年级 1-12
    semester: Optional[int] = Field(default=None, ge=1, le=2)  # 学期 1-2
    answer: Optional[str] = None
    analysis: Optional[str] = None
    difficulty: int = Field(default=3, ge=1, le=5)
    error_type: Optional[str] = None
    knowledge_point: Optional[str] = None
    tag_ids: Optional[List[int]] = []


class QuestionCreate(QuestionBase):
    original_text: Optional[str] = None
    parsed_question: Optional[str] = None
    original_image: Optional[str] = None  # 单个图片
    original_images: Optional[List[str]] = None  # 多个图片


class QuestionUpdate(BaseModel):
    subject_id: Optional[int] = None
    original_image: Optional[str] = None
    grade: Optional[int] = Field(default=None, ge=1, le=12)
    semester: Optional[int] = Field(default=None, ge=1, le=2)
    answer: Optional[str] = None
    analysis: Optional[str] = None
    analysis_image: Optional[str] = None
    difficulty: Optional[int] = Field(default=None, ge=1, le=5)
    error_type: Optional[str] = None
    knowledge_point: Optional[str] = None
    tag_ids: Optional[List[int]] = None


# 批量创建错题
class QuestionBatchCreate(BaseModel):
    """批量创建错题（用于OCR后一道图生成多题）"""
    error_book_id: Optional[int] = None
    subject_id: int
    grade: Optional[int] = Field(default=None, ge=1, le=12)
    semester: Optional[int] = Field(default=None, ge=1, le=2)
    images: List[str]  # 关联的图片路径列表
    questions: List[QuestionCreate]  # 多个题目


class TagResponse(BaseModel):
    id: int
    name: str
    color: Optional[str] = None

    class Config:
        from_attributes = True


class SimilarQuestionResponse(BaseModel):
    id: int
    similar_text: str
    similar_answer: Optional[str] = None
    similarity_score: Optional[float] = None
    generated_at: datetime

    class Config:
        from_attributes = True


class QuestionResponse(BaseModel):
    id: int
    error_book_id: Optional[int] = None
    subject_id: int
    original_image: Optional[str] = None  # 单个图片
    original_images: Optional[List[str]] = None  # 多个图片
    original_text: Optional[str] = None
    parsed_question: Optional[str] = None
    grade: Optional[int] = None  # 年级 1-12
    semester: Optional[int] = None  # 学期 1-2
    answer: Optional[str] = None
    analysis: Optional[str] = None
    analysis_image: Optional[str] = None
    difficulty: int
    error_type: Optional[str] = None
    knowledge_point: Optional[str] = None
    correct_count: Optional[int] = 0
    error_count: Optional[int] = 0
    created_at: datetime
    updated_at: Optional[datetime] = None
    tags: List[TagResponse] = []
    similar_questions: List[SimilarQuestionResponse] = []

    class Config:
        from_attributes = True


class QuestionListResponse(BaseModel):
    total: int
    items: List[QuestionResponse]


class BatchCreateResponse(BaseModel):
    """批量创建响应"""
    questions: List[QuestionResponse]
    total_count: int
    success_count: int
