from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, UniqueConstraint, func
from sqlalchemy.orm import relationship
from app.database import Base


class Achievement(Base):
    """成就定义"""
    __tablename__ = "achievement"

    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String(50), nullable=False)
    name = Column(String(100), nullable=False)
    level = Column(Integer, default=1)
    description = Column(String(500), nullable=True)
    icon = Column(String(500), nullable=True)
    trigger_action = Column(String(50), nullable=False)
    trigger_count = Column(Integer, nullable=False)
    reward_stars = Column(Integer, default=0)
    is_preset = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    deleted = Column(Boolean, default=False)
    created_at = Column(DateTime, server_default=func.now())

    __table_args__ = (
        UniqueConstraint('code', 'level', name='uix_achievement_code_level'),
    )


class AchievementProgress(Base):
    """成就进度"""
    __tablename__ = "achievement_progress"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, default=1)
    achievement_id = Column(Integer, ForeignKey("achievement.id"), nullable=False)
    current_count = Column(Integer, default=0)
    is_unlocked = Column(Boolean, default=False)
    unlocked_at = Column(DateTime, nullable=True)

    __table_args__ = (
        UniqueConstraint('user_id', 'achievement_id', name='uix_user_achievement'),
    )

    achievement = relationship("Achievement")