from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


class RewardBase(BaseModel):
    name: str
    description: Optional[str] = None
    icon: Optional[str] = None
    cost_stars: int
    total_stock: int = -1
    remaining_stock: int = -1
    is_active: bool = True


class RewardCreate(RewardBase):
    pass


class RewardUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    icon: Optional[str] = None
    cost_stars: Optional[int] = None
    total_stock: Optional[int] = None
    remaining_stock: Optional[int] = None
    is_active: Optional[bool] = None


class RewardResponse(RewardBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True


class RedemptionResponse(BaseModel):
    id: int
    reward_id: int
    star_cost: int
    redeemed_at: datetime
    reward: Optional[RewardResponse] = None

    class Config:
        from_attributes = True