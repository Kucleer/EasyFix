# backend/app/services/motivation.py
"""
激励系统核心服务
负责：积分触发、成就检查、奖励兑换
"""
from sqlalchemy.orm import Session
from app.models.star import StarAction, StarBalance, StarRecord
from app.models.achievement import Achievement, AchievementProgress
from app.models.reward import Reward, Redemption
from typing import Optional, List
from datetime import datetime


# 默认用户ID（单用户场景）
DEFAULT_USER_ID = 1


class MotivationService:
    def __init__(self, db: Session):
        self.db = db

    def get_or_create_balance(self, user_id: int = DEFAULT_USER_ID) -> StarBalance:
        """获取或创建用户积分余额"""
        balance = self.db.query(StarBalance).filter(StarBalance.user_id == user_id).first()
        if not balance:
            balance = StarBalance(user_id=user_id, balance=0)
            self.db.add(balance)
            self.db.commit()
            self.db.refresh(balance)
        return balance

    def trigger_action(self, action_code: str, user_id: int = DEFAULT_USER_ID, reason: str = None) -> Optional[dict]:
        """
        触发积分行为
        返回：积分变动信息和成就解锁信息
        """
        # 查找启用的行为
        action = self.db.query(StarAction).filter(
            StarAction.code == action_code,
            StarAction.enabled == True,
            StarAction.deleted == False
        ).first()

        if not action:
            return None

        # 获取余额
        balance = self.get_or_create_balance(user_id)

        # 记录积分明细
        new_balance = balance.balance + action.star_value
        record = StarRecord(
            user_id=user_id,
            action_code=action_code,
            star_delta=action.star_value,
            balance_after=new_balance,
            reason=reason or action.name
        )
        self.db.add(record)

        # 更新余额
        balance.balance = new_balance
        self.db.commit()

        # 检查成就
        unlocked_achievements = self._check_achievements(user_id, action_code)

        return {
            "star_delta": action.star_value,
            "new_balance": new_balance,
            "unlocked_achievements": unlocked_achievements
        }

    def _check_achievements(self, user_id: int, action_code: str) -> List[dict]:
        """检查并更新成就进度"""
        unlocked = []

        # 查找所有因该行为触发的成就
        achievements = self.db.query(Achievement).filter(
            Achievement.trigger_action == action_code,
            Achievement.is_active == True,
            Achievement.deleted == False
        ).all()

        for achievement in achievements:
            # 计算该用户在该成就系列上的总进度
            total_count = self._get_achievement_total_count(user_id, achievement.trigger_action)

            # 获取或创建进度记录
            progress = self.db.query(AchievementProgress).filter(
                AchievementProgress.user_id == user_id,
                AchievementProgress.achievement_id == achievement.id
            ).first()

            if not progress:
                progress = AchievementProgress(
                    user_id=user_id,
                    achievement_id=achievement.id,
                    current_count=0,
                    is_unlocked=False
                )
                self.db.add(progress)

            # 检查是否达成（需先达成上一级）
            if achievement.level == 1 or self._is_previous_level_unlocked(user_id, achievement.code, achievement.level):
                if total_count >= achievement.trigger_count and not progress.is_unlocked:
                    progress.is_unlocked = True
                    progress.unlocked_at = datetime.now()
                    progress.current_count = total_count

                    # 发放成就奖励积分
                    if achievement.reward_stars > 0:
                        self._add_stars(user_id, achievement.reward_stars, f"成就奖励：{achievement.name} Lv{achievement.level}")

                    unlocked.append({
                        "achievement_id": achievement.id,
                        "name": achievement.name,
                        "level": achievement.level,
                        "reward_stars": achievement.reward_stars
                    })

                    # 自动创建下一级进度记录
                    self._create_next_level_progress(user_id, achievement)
                else:
                    progress.current_count = total_count

        self.db.commit()
        return unlocked

    def _is_previous_level_unlocked(self, user_id: int, code: str, level: int) -> bool:
        """检查上一级是否已解锁"""
        if level <= 1:
            return True

        previous_achievement = self.db.query(Achievement).filter(
            Achievement.code == code,
            Achievement.level == level - 1
        ).first()

        if not previous_achievement:
            return True

        previous_progress = self.db.query(AchievementProgress).filter(
            AchievementProgress.user_id == user_id,
            AchievementProgress.achievement_id == previous_achievement.id,
            AchievementProgress.is_unlocked == True
        ).first()

        return previous_progress is not None

    def _create_next_level_progress(self, user_id: int, current_achievement: Achievement):
        """为当前成就的下一级创建进度记录"""
        next_achievement = self.db.query(Achievement).filter(
            Achievement.code == current_achievement.code,
            Achievement.level == current_achievement.level + 1
        ).first()

        if next_achievement:
            existing = self.db.query(AchievementProgress).filter(
                AchievementProgress.user_id == user_id,
                AchievementProgress.achievement_id == next_achievement.id
            ).first()

            if not existing:
                progress = AchievementProgress(
                    user_id=user_id,
                    achievement_id=next_achievement.id,
                    current_count=0,
                    is_unlocked=False
                )
                self.db.add(progress)

    def _get_achievement_total_count(self, user_id: int, trigger_action: str) -> int:
        """获取用户已完成该行为的总次数"""
        from sqlalchemy import func
        count = self.db.query(func.count(StarRecord.id)).filter(
            StarRecord.user_id == user_id,
            StarRecord.action_code == trigger_action
        ).scalar()
        return count or 0

    def _add_stars(self, user_id: int, stars: int, reason: str):
        """手动增加积分"""
        balance = self.get_or_create_balance(user_id)
        new_balance = balance.balance + stars

        record = StarRecord(
            user_id=user_id,
            action_code="reward",
            star_delta=stars,
            balance_after=new_balance,
            reason=reason
        )
        self.db.add(record)
        balance.balance = new_balance
        self.db.commit()

    def redeem_reward(self, reward_id: int, user_id: int = DEFAULT_USER_ID) -> dict:
        """兑换奖励"""
        reward = self.db.query(Reward).filter(
            Reward.id == reward_id,
            Reward.is_active == True,
            Reward.deleted == False
        ).first()

        if not reward:
            raise ValueError("奖励不存在或已下架")

        balance = self.get_or_create_balance(user_id)

        if balance.balance < reward.cost_stars:
            raise ValueError("积分不足")

        if reward.remaining_stock > 0 and reward.remaining_stock < 1:
            raise ValueError("库存不足")

        # 扣除积分
        new_balance = balance.balance - reward.cost_stars
        record = StarRecord(
            user_id=user_id,
            action_code="redeem",
            star_delta=-reward.cost_stars,
            balance_after=new_balance,
            reason=f"兑换：{reward.name}"
        )
        self.db.add(record)
        balance.balance = new_balance

        # 减少库存
        if reward.remaining_stock > 0:
            reward.remaining_stock -= 1

        # 创建兑换记录
        redemption = Redemption(
            user_id=user_id,
            reward_id=reward_id,
            star_cost=reward.cost_stars
        )
        self.db.add(redemption)
        self.db.commit()

        return {
            "success": True,
            "new_balance": new_balance,
            "reward_name": reward.name
        }