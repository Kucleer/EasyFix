from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, func
from sqlalchemy.orm import relationship
from app.database import Base


class StarAction(Base):
    """行为配置"""
    __tablename__ = "star_action"

    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String(50), nullable=False, unique=True)
    name = Column(String(100), nullable=False)
    star_value = Column(Integer, nullable=False, default=0)
    icon = Column(String(500), nullable=True)
    enabled = Column(Boolean, default=True)
    is_custom = Column(Boolean, default=False)
    deleted = Column(Boolean, default=False)
    created_at = Column(DateTime, server_default=func.now())


class StarBalance(Base):
    """积分余额"""
    __tablename__ = "star_balance"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, default=1)
    balance = Column(Integer, default=0)
    updated_at = Column(DateTime, onupdate=func.now())


class StarRecord(Base):
    """积分明细"""
    __tablename__ = "star_record"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, default=1)
    action_code = Column(String(50), nullable=False)
    star_delta = Column(Integer, nullable=False)
    balance_after = Column(Integer, nullable=False)
    reason = Column(String(200), nullable=True)
    created_at = Column(DateTime, server_default=func.now())