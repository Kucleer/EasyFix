from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, func
from sqlalchemy.orm import relationship
from app.database import Base


class Reward(Base):
    """奖励配置"""
    __tablename__ = "reward"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    description = Column(String(500), nullable=True)
    icon = Column(String(500), nullable=True)
    cost_stars = Column(Integer, nullable=False)
    total_stock = Column(Integer, default=-1)  # -1 表示无限
    remaining_stock = Column(Integer, default=-1)
    is_active = Column(Boolean, default=True)
    deleted = Column(Boolean, default=False)
    created_at = Column(DateTime, server_default=func.now())


class Redemption(Base):
    """兑换记录"""
    __tablename__ = "redemption"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, default=1)
    reward_id = Column(Integer, ForeignKey("reward.id"), nullable=False)
    star_cost = Column(Integer, nullable=False)
    redeemed_at = Column(DateTime, server_default=func.now())

    reward = relationship("Reward")