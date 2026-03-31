from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime


class ReportGenerateRequest(BaseModel):
    """报告生成请求"""
    subject_id: Optional[int] = None  # 学科筛选，可为空
    grade: Optional[int] = None  # 年级筛选，可为空
    time_range_days: Optional[int] = None  # 时间范围天数，如30表示最近30天
    title: Optional[str] = None  # 报告标题，不提供则自动生成


class ReportListItem(BaseModel):
    """报告列表项"""
    id: int
    title: str
    subject_id: Optional[int] = None
    subject_name: Optional[str] = None
    grade: Optional[int] = None
    time_range_days: Optional[int] = None
    total_questions: int
    total_words: int
    overall_accuracy: float
    created_at: datetime


class ReportDetail(BaseModel):
    """报告详情"""
    id: int
    title: str
    subject_id: Optional[int] = None
    subject_name: Optional[str] = None
    grade: Optional[int] = None
    time_range_days: Optional[int] = None
    content: Dict[str, Any]  # 多维度分析内容
    total_questions: int
    total_words: int
    overall_accuracy: float
    created_at: datetime


class ReportGenerateResponse(BaseModel):
    """报告生成响应"""
    id: int  # 报告ID
    title: str
    message: str = "报告生成成功"


class ReportListResponse(BaseModel):
    """报告列表响应"""
    total: int
    items: List[ReportListItem]
