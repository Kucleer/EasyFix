from pydantic import BaseModel, Field, computed_field
from typing import Optional, List
from datetime import datetime


class ReadingQuestionBase(BaseModel):
    question_number: int = Field(..., ge=1, le=4)
    question_text: str
    option_a: str
    option_b: str
    option_c: str
    option_d: str
    correct_answer: str = Field(..., pattern=r"^[A-D]$")
    explanation: Optional[str] = None


class ReadingQuestionCreate(ReadingQuestionBase):
    pass


class ReadingQuestionResponse(ReadingQuestionBase):
    id: int
    passage_id: int
    created_at: datetime

    class Config:
        from_attributes = True


class ReadingPassageBase(BaseModel):
    title: str
    content: str
    topic: str
    grade: int = Field(..., ge=1, le=12)
    difficulty: int = Field(default=3, ge=1, le=5)
    word_count: Optional[int] = None
    source: str = "generated"


class ReadingPassageCreate(ReadingPassageBase):
    questions: List[ReadingQuestionCreate]


class ReadingPassageUpdate(BaseModel):
    title: Optional[str] = None
    topic: Optional[str] = None
    grade: Optional[int] = Field(default=None, ge=1, le=12)
    difficulty: Optional[int] = Field(default=None, ge=1, le=5)


class ReadingPassageResponse(ReadingPassageBase):
    @computed_field
    @property
    def provenance(self) -> Optional[dict]:
        """读取本地阅读包来源，不改变数据库结构。"""
        return get_reading_provenance().get(self.source)

    id: int
    word_count: Optional[int] = None
    source: str
    deleted: bool = False
    created_at: datetime
    updated_at: Optional[datetime] = None
    questions: List[ReadingQuestionResponse] = []

    class Config:
        from_attributes = True


class ReadingPassageListResponse(BaseModel):
    total: int
    items: List[ReadingPassageResponse]


class GenerateReadingRequest(BaseModel):
    grade: int = Field(..., ge=1, le=12)
    topic: str
    difficulty: int = Field(default=3, ge=1, le=5)


from functools import lru_cache
from pathlib import Path
import json


@lru_cache(maxsize=1)
def get_reading_provenance():
    """加载随应用分发的阅读包来源索引。"""
    result = {}
    for path in (Path(__file__).resolve().parents[2] / 'data' / 'reading').glob('grade6-*.json'):
        pack = json.loads(path.read_text(encoding='utf-8'))
        for item in pack.get('passages', []):
            result[pack['pack_id'] + ':' + item['id']] = item['provenance']
    return result
