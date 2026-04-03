from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi import Path
from sqlalchemy.orm import Session
from app.database import get_db
import os
import uuid
from app.services.motivation import MotivationService
from app.schemas.star import (
    StarBalanceResponse, StarRecordResponse, StarActionResponse,
    StarActionCreate, StarActionUpdate
)
from app.schemas.achievement import (
    AchievementResponse, AchievementProgressResponse,
    AchievementCreate, AchievementUpdate
)
from app.schemas.reward import (
    RewardResponse, RewardCreate, RewardUpdate, RedemptionResponse
)
from typing import List

router = APIRouter(prefix="/api", tags=["激励系统"])

# ============ 积分模块 ============

@router.get("/stars/balance", response_model=StarBalanceResponse)
def get_balance(db: Session = Depends(get_db)):
    service = MotivationService(db)
    balance = service.get_or_create_balance()
    return StarBalanceResponse(balance=balance.balance)


@router.get("/stars/records", response_model=List[StarRecordResponse])
def get_records(skip: int = 0, limit: int = 50, db: Session = Depends(get_db)):
    from app.models.star import StarRecord
    records = db.query(StarRecord).order_by(StarRecord.created_at.desc()).offset(skip).limit(limit).all()
    return records


@router.get("/stars/actions", response_model=List[StarActionResponse])
def get_actions(db: Session = Depends(get_db)):
    from app.models.star import StarAction
    actions = db.query(StarAction).filter(StarAction.deleted == False).all()
    return actions


@router.post("/stars/actions", response_model=StarActionResponse)
def create_action(data: StarActionCreate, db: Session = Depends(get_db)):
    from app.models.star import StarAction
    action = StarAction(**data.model_dump(), is_custom=True)
    db.add(action)
    db.commit()
    db.refresh(action)
    return action


@router.put("/stars/actions/{action_id}", response_model=StarActionResponse)
def update_action(action_id: int, data: StarActionUpdate, db: Session = Depends(get_db)):
    from app.models.star import StarAction
    action = db.query(StarAction).filter(StarAction.id == action_id).first()
    if not action:
        raise HTTPException(status_code=404, detail="行为不存在")
    if action.is_preset:
        raise HTTPException(status_code=400, detail="预设行为不可修改")
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(action, key, value)
    db.commit()
    db.refresh(action)
    return action


@router.delete("/stars/actions/{action_id}")
def delete_action(action_id: int, db: Session = Depends(get_db)):
    from app.models.star import StarAction
    action = db.query(StarAction).filter(StarAction.id == action_id).first()
    if not action:
        raise HTTPException(status_code=404, detail="行为不存在")
    if action.is_preset:
        raise HTTPException(status_code=400, detail="预设行为不可删除")
    action.deleted = True
    db.commit()
    return {"success": True}


# ============ 成就模块 ============

@router.get("/achievements", response_model=List[AchievementResponse])
def get_achievements(db: Session = Depends(get_db)):
    from app.models.achievement import Achievement
    achievements = db.query(Achievement).filter(Achievement.deleted == False).all()
    return achievements


@router.get("/achievements/progress", response_model=List[AchievementProgressResponse])
def get_progress(db: Session = Depends(get_db)):
    from app.models.achievement import Achievement, AchievementProgress
    from app.models.star import StarRecord
    from sqlalchemy import func

    DEFAULT_USER_ID = 1

    # 获取所有成就进度
    progresses = db.query(AchievementProgress).filter(
        AchievementProgress.user_id == DEFAULT_USER_ID
    ).all()

    # 对于每个成就，计算当前进度（基于积分记录）
    result = []
    for p in progresses:
        achievement = db.query(Achievement).filter(Achievement.id == p.achievement_id).first()

        # 计算真实进度：统计该行为代码的记录数
        count = db.query(func.count(StarRecord.id)).filter(
            StarRecord.user_id == DEFAULT_USER_ID,
            StarRecord.action_code == achievement.trigger_action
        ).scalar() or 0

        result.append({
            "id": p.id,
            "achievement_id": p.achievement_id,
            "current_count": p.current_count,
            "is_unlocked": p.is_unlocked,
            "unlocked_at": p.unlocked_at,
            "achievement": achievement
        })

    return result


@router.post("/achievements", response_model=AchievementResponse)
def create_achievement(data: AchievementCreate, db: Session = Depends(get_db)):
    from app.models.achievement import Achievement
    achievement = Achievement(**data.model_dump(), is_preset=False)
    db.add(achievement)
    db.commit()
    db.refresh(achievement)
    return achievement


@router.put("/achievements/{achievement_id}", response_model=AchievementResponse)
def update_achievement(achievement_id: int, data: AchievementUpdate, db: Session = Depends(get_db)):
    from app.models.achievement import Achievement
    achievement = db.query(Achievement).filter(Achievement.id == achievement_id).first()
    if not achievement:
        raise HTTPException(status_code=404, detail="成就不存在")
    if achievement.is_preset:
        raise HTTPException(status_code=400, detail="预设成就不可修改")
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(achievement, key, value)
    db.commit()
    db.refresh(achievement)
    return achievement


@router.delete("/achievements/{achievement_id}")
def delete_achievement(achievement_id: int, db: Session = Depends(get_db)):
    from app.models.achievement import Achievement
    achievement = db.query(Achievement).filter(Achievement.id == achievement_id).first()
    if not achievement:
        raise HTTPException(status_code=404, detail="成就不存在")
    if achievement.is_preset:
        raise HTTPException(status_code=400, detail="预设成就不可删除")
    achievement.deleted = True
    db.commit()
    return {"success": True}


# ============ 奖励模块 ============

@router.get("/rewards", response_model=List[RewardResponse])
def get_rewards(db: Session = Depends(get_db)):
    from app.models.reward import Reward
    rewards = db.query(Reward).filter(Reward.deleted == False, Reward.is_active == True).all()
    return rewards


@router.post("/rewards", response_model=RewardResponse)
def create_reward(data: RewardCreate, db: Session = Depends(get_db)):
    from app.models.reward import Reward
    reward = Reward(**data.model_dump())
    db.add(reward)
    db.commit()
    db.refresh(reward)
    return reward


@router.put("/rewards/{reward_id}", response_model=RewardResponse)
def update_reward(reward_id: int, data: RewardUpdate, db: Session = Depends(get_db)):
    from app.models.reward import Reward
    reward = db.query(Reward).filter(Reward.id == reward_id).first()
    if not reward:
        raise HTTPException(status_code=404, detail="奖励不存在")
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(reward, key, value)
    db.commit()
    db.refresh(reward)
    return reward


@router.delete("/rewards/{reward_id}")
def delete_reward(reward_id: int, db: Session = Depends(get_db)):
    from app.models.reward import Reward
    reward = db.query(Reward).filter(Reward.id == reward_id).first()
    if not reward:
        raise HTTPException(status_code=404, detail="奖励不存在")
    reward.deleted = True
    db.commit()
    return {"success": True}


@router.post("/rewards/{reward_id}/redeem")
def redeem_reward(reward_id: int, db: Session = Depends(get_db)):
    service = MotivationService(db)
    try:
        result = service.redeem_reward(reward_id)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/rewards/redemptions", response_model=List[RedemptionResponse])
def get_redemptions(db: Session = Depends(get_db)):
    from app.models.reward import Redemption
    redemptions = db.query(Redemption).order_by(Redemption.redeemed_at.desc()).limit(50).all()
    return redemptions


# ============ 激励概览 ============

@router.get("/motivation/overview")
def get_overview(db: Session = Depends(get_db)):
    """获取激励系统概览"""
    from app.models.star import StarAction, StarBalance, StarRecord
    from app.models.achievement import Achievement, AchievementProgress
    from app.models.reward import Reward, Redemption
    from sqlalchemy import func

    DEFAULT_USER_ID = 1

    # 积分余额
    balance = db.query(StarBalance).filter(StarBalance.user_id == DEFAULT_USER_ID).first()
    balance_value = balance.balance if balance else 0

    # 成就统计
    all_achievements = db.query(Achievement).filter(Achievement.deleted == False).all()
    unlocked_count = db.query(AchievementProgress).filter(
        AchievementProgress.user_id == DEFAULT_USER_ID,
        AchievementProgress.is_unlocked == True
    ).count()

    # 奖励统计
    active_rewards = db.query(Reward).filter(Reward.deleted == False, Reward.is_active == True).count()

    # 今日积分
    from datetime import datetime, timedelta
    today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    today_stars = db.query(func.coalesce(func.sum(StarRecord.star_delta), 0)).filter(
        StarRecord.user_id == DEFAULT_USER_ID,
        StarRecord.created_at >= today_start
    ).scalar()

    return {
        "balance": balance_value,
        "achievement_total": len(all_achievements),
        "achievement_unlocked": unlocked_count,
        "rewards_available": active_rewards,
        "today_stars": today_stars
    }


# ============ 内部触发接口（供其他模块调用） ============

@router.post("/motivation/trigger/{action_code}")
def trigger_action(action_code: str, reason: str = None, db: Session = Depends(get_db)):
    """触发积分行为（供内部服务调用）"""
    service = MotivationService(db)
    result = service.trigger_action(action_code, reason=reason)
    if result is None:
        raise HTTPException(status_code=404, detail="行为不存在或已禁用")
    return result


# ============ 奖励图片上传 ============

@router.post("/rewards/{reward_id}/upload-image")
async def upload_reward_image(reward_id: int, file: UploadFile = File(...), db: Session = Depends(get_db)):
    """上传奖励图片"""
    from app.models.reward import Reward

    reward = db.query(Reward).filter(Reward.id == reward_id).first()
    if not reward:
        raise HTTPException(status_code=404, detail="奖励不存在")

    # 保存文件
    upload_dir = os.path.join("backend", "uploads", "rewards")
    os.makedirs(upload_dir, exist_ok=True)

    ext = os.path.splitext(file.filename)[1] if file.filename else ".png"
    filename = f"{uuid.uuid4().hex}{ext}"
    file_path = os.path.join(upload_dir, filename)

    with open(file_path, "wb") as f:
        content = await file.read()
        f.write(content)

    # 更新数据库
    reward.image_url = f"/uploads/rewards/{filename}"
    db.commit()

    return {"Image_url": reward.image_url}