from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


class ErrorBookBase(BaseModel):
    name: str
    subject_id: int
    description: Optional[str] = None


class ErrorBookCreate(ErrorBookBase):
    cover_image: Optional[str] = None
    original_images: Optional[List[str]] = None


class ErrorBookUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    cover_image: Optional[str] = None
    original_images: Optional[List[str]] = None


class ErrorBookResponse(ErrorBookBase):
    id: int
    cover_image: Optional[str] = None
    original_images: Optional[List[str]] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ErrorBookListResponse(BaseModel):
    total: int
    items: List[ErrorBookResponse]
