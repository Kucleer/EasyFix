from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


class AchievementBase(BaseModel):
    code: str
    name: str
    level: int = 1
    description: Optional[str] = None
    icon: Optional[str] = None
    trigger_action: str
    trigger_count: int
    reward_stars: int = 0
    is_active: bool = True


class AchievementCreate(AchievementBase):
    pass


class AchievementUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    icon: Optional[str] = None
    trigger_action: Optional[str] = None
    trigger_count: Optional[int] = None
    reward_stars: Optional[int] = None
    is_active: Optional[bool] = None


class AchievementResponse(AchievementBase):
    id: int
    is_preset: bool
    created_at: datetime

    class Config:
        from_attributes = True


class AchievementConfigSchema(BaseModel):
    id: int
    achievement_id: int
    min_words: int = 10
    min_accuracy: int = 90
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class AchievementProgressResponse(BaseModel):
    id: int
    achievement_id: int
    current_count: int
    is_unlocked: bool
    unlocked_at: Optional[datetime]
    achievement: AchievementResponse
    config: Optional[AchievementConfigSchema] = None

    class Config:
        from_attributes = True