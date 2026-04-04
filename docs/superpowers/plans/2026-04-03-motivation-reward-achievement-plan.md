# 激励系统增强实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现奖励商城图片上传和兑换明细Tab，以及成就系统连续学习和单词正确率成就

**Architecture:** 后端在 motivation 服务中添加连续学习检查和单词正确率检查逻辑，前端在激励中心页面新增兑换明细Tab，奖励卡片支持自定义图片展示

**Tech Stack:** Python FastAPI, SQLAlchemy, Vue 3, Element Plus

---

## 文件结构

```
backend/
├── app/models/
│   ├── reward.py          # Reward 表 + image_url 字段
│   └── achievement.py     # AchievementConfig 新模型
├── app/schemas/
│   ├── achievement.py     # AchievementConfigSchema
│   └── reward.py         # RewardResponse 增加 image_url
├── app/services/
│   ├── motivation.py      # check_continuous_learning(), check_word_accuracy()
│   └── init_motivation_data.py  # 新行为和成就初始化
├── app/routers/
│   └── motivation.py      # 图片上传、兑换明细、单词正确率触发接口

frontend/src/
├── views/Motivation.vue   # 兑换明细Tab + 奖励图片展示
└── api/motivation.js     # 新 API 方法
```

---

## Part 1: 奖励商城增强

### Task 1: Reward 模型增加 image_url 字段

**Files:**
- Modify: `backend/app/models/reward.py`

- [ ] **Step 1: 修改 Reward 模型**

```python
# 在 Reward 类的 created_at 字段前添加
image_url = Column(String(500), nullable=True)  # 自定义图片路径，与 icon 二选一
```

- [ ] **Step 2: 提交**

```bash
git add backend/app/models/reward.py
git commit -m "feat: reward model add image_url field"
```

---

### Task 2: Reward Response Schema 增加 image_url

**Files:**
- Modify: `backend/app/schemas/reward.py`

- [ ] **Step 1: 修改 RewardResponse**

```python
# 在 RewardResponse 类中添加 image_url 字段
image_url: Optional[str] = None
```

- [ ] **Step 2: 提交**

```bash
git add backend/app/schemas/reward.py
git commit -m "feat: reward schema add image_url field"
```

---

### Task 3: 新增奖励图片上传 API

**Files:**
- Modify: `backend/app/routers/motivation.py`

- [ ] **Step 1: 添加上传接口**

在 `motivation.py` 顶部添加 import:
```python
from fastapi import UploadFile, File
import os
import uuid
```

添加路由:
```python
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

    return {"image_url": reward.image_url}
```

- [ ] **Step 2: 确保静态文件服务已配置**

检查 `backend/app/main.py` 中是否有静态文件服务配置:
```python
app.mount("/uploads", StaticFiles(directory="backend/uploads"), name="uploads")
```

如果不存在，在 CORS 配置后添加。

- [ ] **Step 3: 提交**

```bash
git add backend/app/routers/motivation.py backend/app/main.py
git commit -m "feat: add reward image upload API"
```

---

### Task 4: 前端奖励卡片支持图片展示

**Files:**
- Modify: `frontend/src/views/Motivation.vue`

- [ ] **Step 1: 修改奖励卡片图标展示逻辑**

找到奖励卡片的图标展示部分（约在第97-100行）:
```html
<div class="reward-icon" :style="{ backgroundColor: reward.color }">
  <el-icon :size="40" color="#fff">
    <component :is="reward.icon" />
  </el-icon>
</div>
```

替换为:
```html
<div class="reward-icon" :style="{ backgroundColor: reward.color }">
  <img v-if="reward.image_url" :src="reward.image_url" style="width:40px;height:40px;object-fit:contain;" />
  <el-icon v-else :size="40" color="#fff">
    <component :is="reward.icon || 'Present'" />
  </el-icon>
</div>
```

- [ ] **Step 2: 提交**

```bash
git add frontend/src/views/Motivation.vue
git commit -m "feat: reward card support image display"
```

---

## Part 2: 兑换明细 Tab

### Task 5: 新增兑换明细 API

**Files:**
- Modify: `backend/app/routers/motivation.py`

- [ ] **Step 1: 修改兑换记录查询接口**

将现有 `/api/rewards/redemptions` 改为按 user_id 筛选:

```python
@router.get("/redemptions", response_model=List[RedemptionResponse])
def get_redemptions(db: Session = Depends(get_db)):
    """获取当前用户的兑换记录"""
    from app.models.reward import Redemption
    from app.models.star import StarBalance

    DEFAULT_USER_ID = 1

    redemptions = db.query(Redemption).filter(
        Redemption.user_id == DEFAULT_USER_ID
    ).order_by(Redemption.redeemed_at.desc()).limit(50).all()

    return redemptions
```

- [ ] **Step 2: 提交**

```bash
git add backend/app/routers/motivation.py
git commit -m "feat: filter redemptions by user_id"
```

---

### Task 6: 前端新增兑换明细 Tab

**Files:**
- Modify: `frontend/src/views/Motivation.vue`
- Modify: `frontend/src/api/motivation.js`

- [ ] **Step 1: api/motivation.js 添加方法**

```javascript
getRedemptions() {
  return api.get('/redemptions')
},
```

- [ ] **Step 2: Motivation.vue 添加数据和方法**

在 script setup 中添加:
```javascript
const activeTab = ref('achievements')

// 新增兑换记录数据
const redemptionList = ref([])

// 新增获取兑换记录方法
const fetchRedemptions = async () => {
  try {
    const res = await motivationApi.getRedemptions()
    redemptionList.value = res.data.map(r => ({
      ...r,
      reward: r.reward || { name: '未知奖励' }
    }))
  } catch (error) {
    console.error('获取兑换记录失败:', error)
  }
}
```

- [ ] **Step 3: 在 initData 中调用 fetchRedemptions**

```javascript
const initData = async () => {
  loading.value = true
  try {
    await Promise.all([
      fetchOverview(),
      fetchAchievements(),
      fetchRewards(),
      fetchRecords(),
      fetchRedemptions(),  // 新增
    ])
  } finally {
    loading.value = false
  }
}
```

- [ ] **Step 4: 添加兑换明细 Tab**

在 el-tabs 中添加新的 tab-pane（在奖励商城 Tab 之后）:
```html
<el-tab-pane label="兑换明细" name="redemptions">
  <el-table :data="redemptionList" stripe>
    <el-table-column prop="reward.name" label="奖励名称" />
    <el-table-column prop="star_cost" label="消耗积分" width="120" />
    <el-table-column prop="redeemed_at" label="兑换时间" width="180">
      <template #default="{ row }">
        {{ formatDate(row.redeemed_at) }}
      </template>
    </el-table-column>
  </el-table>
  <el-empty v-if="redemptionList.length === 0" description="暂无兑换记录" />
</el-tab-pane>
```

- [ ] **Step 5: 提交**

```bash
git add frontend/src/views/Motivation.vue frontend/src/api/motivation.js
git commit -m "feat: add redemptions tab to motivation page"
```

---

## Part 3: 成就系统增强

### Task 7: 创建 AchievementConfig 模型

**Files:**
- Modify: `backend/app/models/achievement.py`

- [ ] **Step 1: 添加 AchievementConfig 模型**

在 `AchievementProgress` 类之后添加:
```python
class AchievementConfig(Base):
    """成就配置表"""
    __tablename__ = "achievement_config"

    id = Column(Integer, primary_key=True, autoincrement=True)
    achievement_id = Column(Integer, ForeignKey("achievement.id"), unique=True)
    min_words = Column(Integer, default=10)      # 每次最少单词数
    min_accuracy = Column(Integer, default=90)    # 最低正确率%
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())

    achievement = relationship("Achievement")
```

- [ ] **Step 2: 提交**

```bash
git add backend/app/models/achievement.py
git commit -m "feat: add achievement_config model"
```

---

### Task 8: 创建 AchievementConfig Schema

**Files:**
- Modify: `backend/app/schemas/achievement.py`

- [ ] **Step 1: 添加 Schema**

```python
class AchievementConfigSchema(BaseModel):
    id: int
    achievement_id: int
    min_words: int = 10
    min_accuracy: int = 90
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True
```

在 `AchievementProgressResponse` 中添加:
```python
config: Optional[AchievementConfigSchema] = None
```

- [ ] **Step 2: 提交**

```bash
git add backend/app/schemas/achievement.py
git commit -m "feat: add achievement config schema"
```

---

### Task 9: 初始化新行为和成就数据

**Files:**
- Modify: `backend/app/services/init_motivation_data.py`

- [ ] **Step 1: 添加新的行为配置**

在 `PRESET_ACTIONS` 中添加:
```python
{"code": "continuous_14day", "name": "连续14天学习", "star_value": 100},
{"code": "continuous_30day", "name": "连续30天学习", "star_value": 200},
{"code": "review_word_accuracy", "name": "单词正确率成就", "star_value": 30},
```

- [ ] **Step 2: 添加新的成就配置**

在 `PRESET_ACHIEVEMENTS` 中添加（注意放在其他成就之后）:
```python
# 连续学习成就
{"code": "continuous_learning", "name": "连续学习", "level": 1, "trigger_action": "continuous_7day", "trigger_count": 7, "reward_stars": 50, "description": "连续学习7天"},
{"code": "continuous_learning", "name": "连续学习", "level": 2, "trigger_action": "continuous_14day", "trigger_count": 14, "reward_stars": 100, "description": "连续学习14天"},
{"code": "continuous_learning", "name": "连续学习", "level": 3, "trigger_action": "continuous_30day", "trigger_count": 30, "reward_stars": 200, "description": "连续学习30天"},
# 单词正确率成就
{"code": "word_accuracy", "name": "单词正确率", "level": 1, "trigger_action": "review_word_accuracy", "trigger_count": 1, "reward_stars": 30, "description": "单次复习10个单词以上且正确率90%以上"},
```

- [ ] **Step 3: 添加初始化 AchievementConfig 的逻辑**

在 `init_preset_data` 函数结束后添加:
```python
def init_achievement_configs(db: Session):
    """初始化成就配置"""
    from app.models.achievement import Achievement, AchievementConfig

    # 单词正确率成就配置
    word_accuracy = db.query(Achievement).filter(
        Achievement.code == "word_accuracy"
    ).first()

    if word_accuracy:
        existing = db.query(AchievementConfig).filter(
            AchievementConfig.achievement_id == word_accuracy.id
        ).first()

        if not existing:
            config = AchievementConfig(
                achievement_id=word_accuracy.id,
                min_words=10,
                min_accuracy=90
            )
            db.add(config)
            db.commit()
```

在 `backend/app/main.py` 中调用:
```python
from app.services.init_motivation_data import init_preset_data, init_achievement_progress, init_star_records_from_existing_data, init_achievement_configs

# 初始化激励系统预设数据
with SessionLocal() as db:
    init_preset_data(db)
    init_achievement_progress(db)
    init_star_records_from_existing_data(db)
    init_achievement_configs(db)
```

- [ ] **Step 4: 提交**

```bash
git add backend/app/services/init_motivation_data.py backend/app/main.py
git commit -m "feat: add continuous learning and word accuracy achievements"
```

---

### Task 10: 实现连续学习检查逻辑

**Files:**
- Modify: `backend/app/services/motivation.py`

- [ ] **Step 1: 添加 check_continuous_learning 方法**

在 `MotivationService` 类中添加:
```python
def check_continuous_learning(self, user_id: int = None) -> List[dict]:
    """检查并更新连续学习成就"""
    from app.models.achievement import Achievement, AchievementProgress

    if user_id is None:
        user_id = DEFAULT_USER_ID
    from datetime import datetime, timedelta

    unlocked = []

    # 获取连续学习相关的行为
    continuous_actions = ['continuous_7day', 'continuous_14day', 'continuous_30day']

    # 查询用户的学习日期记录
    records = self.db.query(StarRecord).filter(
        StarRecord.user_id == user_id,
        StarRecord.action_code.in_(['upload_question', 'review_practice_set', 'review_word', 'generate_similar', 'create_practice_set'])
    ).order_by(StarRecord.created_at.desc()).all()

    if not records:
        return unlocked

    # 提取唯一的学习日期
    study_dates = set()
    for r in records:
        date_str = r.created_at.strftime('%Y-%m-%d') if isinstance(r.created_at, datetime) else datetime.strptime(str(r.created_at), '%Y-%m-%d %H:%M:%S').strftime('%Y-%m-%d')
        study_dates.add(date_str)

    study_dates = sorted(study_dates, reverse=True)

    # 检查每个连续学习成就
    for action_code in continuous_actions:
        achievement = self.db.query(Achievement).filter(
            Achievement.code == 'continuous_learning',
            Achievement.trigger_action == action_code,
            Achievement.deleted == False
        ).first()

        if not achievement:
            continue

        days = achievement.trigger_count

        # 计算连续天数
        consecutive_days = 0
        today = datetime.now().strftime('%Y-%m-%d')

        for i in range(days):
            check_date = (datetime.now() - timedelta(days=i)).strftime('%Y-%m-%d')
            if check_date in study_dates:
                consecutive_days += 1
            else:
                break

        # 检查是否解锁
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

        if consecutive_days >= days and not progress.is_unlocked:
            progress.is_unlocked = True
            progress.unlocked_at = datetime.now()
            progress.current_count = consecutive_days

            # 发放奖励积分
            if achievement.reward_stars > 0:
                self._add_stars(user_id, achievement.reward_stars, f"成就奖励：{achievement.name} Lv{achievement.level}")

            # 触发该行为记录
            self._add_star_record(user_id, action_code, achievement.reward_stars, f"连续学习成就解锁：{achievement.name}")

            unlocked.append({
                "achievement_id": achievement.id,
                "name": achievement.name,
                "level": achievement.level,
                "reward_stars": achievement.reward_stars
            })

    self.db.commit()
    return unlocked

def _add_star_record(self, user_id: int, action_code: str, star_delta: int, reason: str):
    """内部方法：添加积分记录"""
    balance = self.get_or_create_balance(user_id)
    new_balance = balance.balance + star_delta

    record = StarRecord(
        user_id=user_id,
        action_code=action_code,
        star_delta=star_delta,
        balance_after=new_balance,
        reason=reason
    )
    self.db.add(record)
    balance.balance = new_balance
    self.db.commit()
```

- [ ] **Step 2: 修改 trigger_action 方法**

在 `trigger_action` 方法返回前添加:
```python
# 检查连续学习
if result:
    self.check_continuous_learning(user_id)

return result
```

- [ ] **Step 3: 提交**

```bash
git add backend/app/services/motivation.py
git commit -m "feat: implement continuous learning achievement check"
```

---

### Task 11: 实现单词正确率检查逻辑

**Files:**
- Modify: `backend/app/services/motivation.py`

- [ ] **Step 1: 添加 check_word_accuracy 方法**

在 `MotivationService` 类中添加:
```python
def check_word_accuracy(self, user_id: int, total_count: int, correct_count: int, reason: str = None) -> Optional[dict]:
    """检查单词正确率成就"""
    from app.models.achievement import Achievement, AchievementProgress, AchievementConfig
    from datetime import datetime

    # 获取单词正确率成就
    achievement = self.db.query(Achievement).filter(
        Achievement.code == "word_accuracy",
        Achievement.deleted == False
    ).first()

    if not achievement:
        return None

    # 获取成就配置
    config = self.db.query(AchievementConfig).filter(
        AchievementConfig.achievement_id == achievement.id
    ).first()

    min_words = config.min_words if config else 10
    min_accuracy = config.min_accuracy if config else 90

    # 计算正确率
    accuracy = (correct_count / total_count * 100) if total_count > 0 else 0

    # 检查是否满足条件
    if total_count < min_words or accuracy < min_accuracy:
        return None

    # 检查是否已解锁
    progress = self.db.query(AchievementProgress).filter(
        AchievementProgress.user_id == user_id,
        AchievementProgress.achievement_id == achievement.id
    ).first()

    if progress and progress.is_unlocked:
        return None  # 已解锁

    # 解锁成就
    if not progress:
        progress = AchievementProgress(
            user_id=user_id,
            achievement_id=achievement.id,
            current_count=0,
            is_unlocked=False
        )
        self.db.add(progress)

    progress.is_unlocked = True
    progress.unlocked_at = datetime.now()
    progress.current_count = 1

    # 发放奖励积分
    if achievement.reward_stars > 0:
        self._add_stars(user_id, achievement.reward_stars, f"成就奖励：{achievement.name}")

        # 触发行为记录
        self._add_star_record(user_id, "review_word_accuracy", achievement.reward_stars, reason or "单词正确率成就解锁")

    self.db.commit()

    return {
        "achievement_id": achievement.id,
        "name": achievement.name,
        "level": achievement.level,
        "reward_stars": achievement.reward_stars,
        "accuracy": accuracy,
        "total_count": total_count,
        "correct_count": correct_count
    }
```

- [ ] **Step 2: 添加单词正确率触发接口**

在 `motivation.py` 路由文件顶部确保有:
```python
DEFAULT_USER_ID = 1
```

添加路由:
```python
@router.post("/motivation/trigger/review_word_accuracy")
def trigger_word_accuracy(
    total_count: int,
    correct_count: int,
    reason: str = None,
    db: Session = Depends(get_db)
):
    """触发单词正确率成就"""
    service = MotivationService(db)
    result = service.check_word_accuracy(
        user_id=DEFAULT_USER_ID,
        total_count=total_count,
        correct_count=correct_count,
        reason=reason
    )
    if result is None:
        return {"unlocked": False, "message": "未达成条件"}
    return {"unlocked": True, **result}
```

- [ ] **Step 3: 提交**

```bash
git add backend/app/services/motivation.py backend/app/routers/motivation.py
git commit -m "feat: implement word accuracy achievement check"
```

---

### Task 12: 前端单词复习调用激励接口

**Files:**
- 需要确定单词复习完成的调用位置

- [ ] **Step 1: 查找单词复习相关代码**

```bash
grep -r "word_review" frontend/src --include="*.vue" --include="*.js" -l
```

- [ ] **Step 2: 在单词复习完成处调用激励接口**

在单词复习完成逻辑中添加:
```javascript
// 调用单词正确率成就检查
try {
  await motivationApi.triggerWordAccuracy({
    total_count: reviewResult.totalCount,
    correct_count: reviewResult.correctCount,
    reason: '单词复习'
  })
} catch (error) {
  console.error('激励触发失败:', error)
}
```

在 `api/motivation.js` 中添加:
```javascript
triggerWordAccuracy(data) {
  return api.post('/motivation/trigger/review_word_accuracy', data)
},
```

- [ ] **Step 3: 提交**

```bash
git add frontend/src/api/motivation.js
# 前端复习页面的修改（路径待确定）
git commit -m "feat: call word accuracy achievement trigger after review"
```

---

## 实施检查清单

完成所有任务后验证:

- [ ] Reward 表有 image_url 字段
- [ ] 奖励卡片可显示自定义图片
- [ ] 兑换明细 Tab 正常显示
- [ ] AchievementConfig 表已创建
- [ ] 连续学习成就已初始化
- [ ] 单词正确率成就已初始化
- [ ] 单词复习完成时触发成就检查

---

## 依赖说明

1. Task 12 需要先完成 Task 7-11 才能测试
2. 图片上传依赖静态文件服务配置
3. 单词复习触发需要确认复习完成的位置
