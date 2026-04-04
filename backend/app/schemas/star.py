from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


class StarActionBase(BaseModel):
    code: str
    name: str
    star_value: int = 0
    icon: Optional[str] = None
    enabled: bool = True


class StarActionCreate(StarActionBase):
    pass


class StarActionUpdate(BaseModel):
    name: Optional[str] = None
    star_value: Optional[int] = None
    icon: Optional[str] = None
    enabled: Optional[bool] = None


class StarActionResponse(StarActionBase):
    id: int
    is_custom: bool
    created_at: datetime

    class Config:
        from_attributes = True


class StarBalanceResponse(BaseModel):
    balance: int

    class Config:
        from_attributes = True


class StarRecordResponse(BaseModel):
    id: int
    action_code: str
    star_delta: int
    balance_after: int
    reason: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class StarsAdjustRequest(BaseModel):
    """积分调整请求"""
    delta: int
    reason: str

    class Config:
        from_attributes = True


class StarsAdjustResponse(BaseModel):
    """积分调整响应"""
    success: bool
    new_balance: int
    delta: int
    record_id: int