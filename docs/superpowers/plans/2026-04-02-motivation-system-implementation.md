# 激励系统实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现完整的激励系统，包含行为积分、成就徽章（多级）、奖励兑换三大模块

**Architecture:** 后端采用 FastAPI + SQLAlchemy，前端采用 Vue 3 + Element Plus。新增独立激励模块，复用现有密码验证机制。

**Tech Stack:** Python FastAPI, SQLAlchemy, Vue 3, Element Plus, ECharts

---

## 文件结构

```
backend/app/
├── models/
│   ├── star.py              # 新增：star_action, star_balance, star_record
│   ├── achievement.py      # 新增：achievement, achievement_progress
│   └── reward.py           # 新增：reward, redemption
├── schemas/
│   ├── star.py              # 新增：积分相关 Pydantic 模型
│   ├── achievement.py       # 新增：成就相关 Pydantic 模型
│   └── reward.py            # 新增：奖励相关 Pydantic 模型
├── routers/
│   ├── motivation.py        # 新增：激励相关所有 API
│   ├── __init__.py          # 修改：注册 motivation_router
├── services/
│   └── motivation.py        # 新增：激励业务逻辑（触发积分、检查成就等）
├── main.py                  # 修改：注册 motivation_router
models/__init__.py           # 修改：导出新增模型

frontend/src/
├── api/
│   └── motivation.js        # 新增：激励 API
├── views/
│   └── Motivation.vue       # 新增：激励中心页面
├── router/index.js          # 修改：添加 /motivation 路由
├── views/Home.vue           # 修改：添加激励入口
└── views/Management.vue     # 修改：添加行为/成就/奖励管理 Tab
```

---

## 后端实现

### Task 1: 创建积分相关模型

**Files:**
- Create: `backend/app/models/star.py`
- Modify: `backend/app/models/__init__.py`

```python
# backend/app/models/star.py
from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, UniqueConstraint, func
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
```

- [ ] **Step 1: 创建 `backend/app/models/star.py`**
- [ ] **Step 2: 更新 `backend/app/models/__init__.py` 导出 StarAction, StarBalance, StarRecord**
- [ ] **Step 3: Commit**

---

### Task 2: 创建成就相关模型

**Files:**
- Create: `backend/app/models/achievement.py`
- Modify: `backend/app/models/__init__.py`

```python
# backend/app/models/achievement.py
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
```

- [ ] **Step 1: 创建 `backend/app/models/achievement.py`**
- [ ] **Step 2: 更新 `backend/app/models/__init__.py` 导出 Achievement, AchievementProgress**
- [ ] **Step 3: Commit**

---

### Task 3: 创建奖励相关模型

**Files:**
- Create: `backend/app/models/reward.py`
- Modify: `backend/app/models/__init__.py`

```python
# backend/app/models/reward.py
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
```

- [ ] **Step 1: 创建 `backend/app/models/reward.py`**
- [ ] **Step 2: 更新 `backend/app/models/__init__.py` 导出 Reward, Redemption**
- [ ] **Step 3: Commit**

---

### Task 4: 创建 Pydantic Schema

**Files:**
- Create: `backend/app/schemas/star.py`
- Create: `backend/app/schemas/achievement.py`
- Create: `backend/app/schemas/reward.py`
- Modify: `backend/app/schemas/__init__.py`

```python
# backend/app/schemas/star.py
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
```

```python
# backend/app/schemas/achievement.py
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


class AchievementProgressResponse(BaseModel):
    id: int
    achievement_id: int
    current_count: int
    is_unlocked: bool
    unlocked_at: Optional[datetime]
    achievement: AchievementResponse

    class Config:
        from_attributes = True
```

```python
# backend/app/schemas/reward.py
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
```

- [ ] **Step 1: 创建 `backend/app/schemas/star.py`**
- [ ] **Step 2: 创建 `backend/app/schemas/achievement.py`**
- [ ] **Step 3: 创建 `backend/app/schemas/reward.py`**
- [ ] **Step 4: 更新 `backend/app/schemas/__init__.py` 导出所有新 Schema**
- [ ] **Step 5: Commit**

---

### Task 5: 创建激励服务

**Files:**
- Create: `backend/app/services/motivation.py`

```python
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
```

- [ ] **Step 1: 创建 `backend/app/services/motivation.py`**
- [ ] **Step 2: Commit**

---

### Task 6: 创建激励路由

**Files:**
- Create: `backend/app/routers/motivation.py`
- Modify: `backend/app/routers/__init__.py`
- Modify: `backend/app/main.py`

```python
# backend/app/routers/motivation.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
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
    from app.models.achievement import AchievementProgress
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
        p.achievement = db.query(Achievement).filter(Achievement.id == p.achievement_id).first()

        # 计算真实进度：统计该行为代码的记录数
        count = db.query(func.count(StarRecord.id)).filter(
            StarRecord.user_id == DEFAULT_USER_ID,
            StarRecord.action_code == p.achievement.trigger_action
        ).scalar() or 0

        p.current_count = count
        result.append(p)

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
```

- [ ] **Step 1: 创建 `backend/app/routers/motivation.py`**
- [ ] **Step 2: 更新 `backend/app/routers/__init__.py` 导出 `motivation_router`**
- [ ] **Step 3: 更新 `backend/app/main.py` 注册 `motivation_router`**
- [ ] **Step 4: Commit**

---

### Task 7: 集成触发点到现有路由

**Files:**
- Modify: `backend/app/routers/question.py` - 上传错题触发
- Modify: `backend/app/routers/practice_set.py` - 复习练习集触发
- Modify: `backend/app/routers/similar.py` - 生成相似题触发
- Modify: `backend/app/routers/word.py` - 背单词触发

```python
# 在 question.py 的创建错题接口中添加：
from app.services.motivation import MotivationService

# 在创建错题成功后：
service = MotivationService(db)
service.trigger_action("upload_question", reason="上传错题")
```

```python
# 在 practice_set.py 的标记已复习接口中添加：
service = MotivationService(db)
service.trigger_action("review_practice_set", reason="复习练习集")
```

```python
# 在 similar.py 的生成相似题成功后添加：
service = MotivationService(db)
service.trigger_action("generate_similar", reason="生成相似题")
```

```python
# 在 word.py 的提交复习结果接口中添加：
service = MotivationService(db)
service.trigger_action("review_word", reason="背单词复习")
```

- [ ] **Step 1: 修改 `backend/app/routers/question.py` 添加上传错题触发**
- [ ] **Step 2: 修改 `backend/app/routers/practice_set.py` 添加复习触发**
- [ ] **Step 3: 修改 `backend/app/routers/similar.py` 添加相似题触发**
- [ ] **Step 4: 修改 `backend/app/routers/word.py` 添加背单词触发**
- [ ] **Step 5: Commit**

---

### Task 8: 初始化预设数据

**Files:**
- Create: `backend/app/services/init_motivation_data.py`

```python
# backend/app/services/init_motivation_data.py
"""初始化激励系统预设数据"""
from sqlalchemy.orm import Session
from app.models.star import StarAction
from app.models.achievement import Achievement


PRESET_ACTIONS = [
    {"code": "upload_question", "name": "上传错题", "star_value": 10},
    {"code": "review_practice_set", "name": "复习练习集", "star_value": 5},
    {"code": "generate_similar", "name": "生成相似题", "star_value": 3},
    {"code": "review_word", "name": "背单词", "star_value": 2},
    {"code": "create_practice_set", "name": "创建练习集", "star_value": 5},
    {"code": "daily_login", "name": "每日登录", "star_value": 1},
    {"code": "continuous_7day", "name": "连续7天学习", "star_value": 50},
]


PRESET_ACHIEVEMENTS = [
    # 首次上传
    {"code": "first_upload", "name": "首次上传", "level": 1, "trigger_action": "upload_question", "trigger_count": 1, "reward_stars": 20, "description": "完成第一次错题上传"},
    # 上传达人
    {"code": "upload_master", "name": "上传达人", "level": 1, "trigger_action": "upload_question", "trigger_count": 10, "reward_stars": 50, "description": "上传10道错题"},
    {"code": "upload_master", "name": "上传达人", "level": 2, "trigger_action": "upload_question", "trigger_count": 50, "reward_stars": 100, "description": "上传50道错题"},
    {"code": "upload_master", "name": "上传达人", "level": 3, "trigger_action": "upload_question", "trigger_count": 200, "reward_stars": 200, "description": "上传200道错题"},
    # 练习高手
    {"code": "review_master", "name": "练习高手", "level": 1, "trigger_action": "review_practice_set", "trigger_count": 10, "reward_stars": 30, "description": "复习10次练习集"},
    {"code": "review_master", "name": "练习高手", "level": 2, "trigger_action": "review_practice_set", "trigger_count": 50, "reward_stars": 80, "description": "复习50次练习集"},
    {"code": "review_master", "name": "练习高手", "level": 3, "trigger_action": "review_practice_set", "trigger_count": 200, "reward_stars": 150, "description": "复习200次练习集"},
    # 单词达人
    {"code": "word_master", "name": "单词达人", "level": 1, "trigger_action": "review_word", "trigger_count": 50, "reward_stars": 50, "description": "背50个单词"},
    {"code": "word_master", "name": "单词达人", "level": 2, "trigger_action": "review_word", "trigger_count": 200, "reward_stars": 100, "description": "背200个单词"},
    {"code": "word_master", "name": "单词达人", "level": 3, "trigger_action": "review_word", "trigger_count": 500, "reward_stars": 200, "description": "背500个单词"},
    # 相似题专家
    {"code": "similar_master", "name": "相似题专家", "level": 1, "trigger_action": "generate_similar", "trigger_count": 20, "reward_stars": 60, "description": "生成20道相似题"},
    {"code": "similar_master", "name": "相似题专家", "level": 2, "trigger_action": "generate_similar", "trigger_count": 100, "reward_stars": 120, "description": "生成100道相似题"},
    {"code": "similar_master", "name": "相似题专家", "level": 3, "trigger_action": "generate_similar", "trigger_count": 300, "reward_stars": 250, "description": "生成300道相似题"},
]


def init_preset_data(db: Session):
    """初始化预设数据"""
    # 初始化行为
    for action_data in PRESET_ACTIONS:
        existing = db.query(StarAction).filter(StarAction.code == action_data["code"]).first()
        if not existing:
            action = StarAction(**action_data, is_preset=True, enabled=True)
            db.add(action)

    # 初始化成就
    for ach_data in PRESET_ACHIEVEMENTS:
        existing = db.query(Achievement).filter(
            Achievement.code == ach_data["code"],
            Achievement.level == ach_data["level"]
        ).first()
        if not existing:
            achievement = Achievement(**ach_data, is_preset=True, is_active=True)
            db.add(achievement)

    db.commit()
```

在 `main.py` 的 `Base.metadata.create_all(bind=engine)` 之后调用：

```python
from app.services.init_motivation_data import init_preset_data

# 初始化激励系统预设数据
with SessionLocal() as db:
    init_preset_data(db)
```

- [ ] **Step 1: 创建 `backend/app/services/init_motivation_data.py`**
- [ ] **Step 2: 修改 `backend/app/main.py` 在启动时初始化预设数据**
- [ ] **Step 3: Commit**

---

## 前端实现

### Task 9: 创建激励 API

**Files:**
- Create: `frontend/src/api/motivation.js`

```javascript
import api from './question.js'

export const motivationApi = {
  // 积分
  getBalance() {
    return api.get('/stars/balance')
  },
  getRecords(params) {
    return api.get('/stars/records', { params })
  },
  getActions() {
    return api.get('/stars/actions')
  },
  createAction(data) {
    return api.post('/stars/actions', data)
  },
  updateAction(id, data) {
    return api.put(`/stars/actions/${id}`, data)
  },
  deleteAction(id) {
    return api.delete(`/stars/actions/${id}`)
  },

  // 成就
  getAchievements() {
    return api.get('/achievements')
  },
  getAchievementProgress() {
    return api.get('/achievements/progress')
  },
  createAchievement(data) {
    return api.post('/achievements', data)
  },
  updateAchievement(id, data) {
    return api.put(`/achievements/${id}`, data)
  },
  deleteAchievement(id) {
    return api.delete(`/achievements/${id}`)
  },

  // 奖励
  getRewards() {
    return api.get('/rewards')
  },
  createReward(data) {
    return api.post('/rewards', data)
  },
  updateReward(id, data) {
    return api.put(`/rewards/${id}`, data)
  },
  deleteReward(id) {
    return api.delete(`/rewards/${id}`)
  },
  redeemReward(id) {
    return api.post(`/rewards/${id}/redeem`)
  },
  getRedemptions() {
    return api.get('/rewards/redemptions')
  },

  // 概览
  getOverview() {
    return api.get('/motivation/overview')
  }
}
```

- [ ] **Step 1: 创建 `frontend/src/api/motivation.js`**
- [ ] **Step 2: Commit**

---

### Task 10: 创建激励中心页面

**Files:**
- Create: `frontend/src/views/Motivation.vue`

页面结构：
- Tabs: 积分成就 | 奖励商城
- 积分成就 Tab：
  - 顶部：积分余额卡片 + 今日获取积分
  - 成就徽章墙（网格布局，按成就系列分组）
  - 每个成就显示：图标、名称、等级、进度条、解锁状态
- 奖励商城 Tab：
  - 奖励卡片列表
  - 每个奖励显示：图标、名称、所需积分、库存
  - 兑换按钮

- [ ] **Step 1: 创建 `frontend/src/views/Motivation.vue`**
- [ ] **Step 2: Commit**

---

### Task 11: 添加路由和导航

**Files:**
- Modify: `frontend/src/router/index.js`
- Modify: `frontend/src/views/Home.vue` - 添加激励入口卡片
- Modify: `frontend/src/App.vue` - 添加导航菜单

```javascript
// router/index.js 添加
{
  path: '/motivation',
  name: 'Motivation',
  component: () => import('@/views/Motivation.vue'),
}
```

- [ ] **Step 1: 添加路由**
- [ ] **Step 2: 在首页添加激励入口卡片**
- [ ] **Step 3: 在导航菜单添加入口**
- [ ] **Step 4: Commit**

---

### Task 12: 管理页面添加激励配置 Tab

**Files:**
- Modify: `frontend/src/views/Management.vue`

新增三个 Tab：
1. 行为配置 - 列表、编辑、新增自定义行为
2. 成就管理 - 列表、编辑、新增自定义成就
3. 奖励管理 - 列表、新增、编辑、删除奖励

- [ ] **Step 1: 修改 `Management.vue` 添加激励配置 Tab**
- [ ] **Step 2: Commit**

---

## 总结

**后端任务 (8个):**
1. 创建积分模型 (star_action, star_balance, star_record)
2. 创建成就模型 (achievement, achievement_progress)
3. 创建奖励模型 (reward, redemption)
4. 创建 Pydantic Schema
5. 创建激励服务 (motivation.py)
6. 创建激励路由 (motivation.py router)
7. 集成触发点到现有路由
8. 初始化预设数据

**前端任务 (4个):**
9. 创建激励 API
10. 创建激励中心页面
11. 添加路由和导航
12. 管理页面添加激励配置

**总任务数: 12个**

---

Plan saved to `docs/superpowers/plans/2026-04-02-motivation-system-implementation.md`
