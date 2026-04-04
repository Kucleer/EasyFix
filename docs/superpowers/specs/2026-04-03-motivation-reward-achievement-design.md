# 激励系统增强设计

## 1. 概述

本次增强包含两个独立模块：
1. **奖励商城增强**：图片上传、兑换明细 Tab
2. **成就系统增强**：连续学习成就扩展、单词正确率成就

---

## 2. 奖励商城增强

### 2.1 数据模型变更

**Reward 表增加字段：**
```python
image_url = Column(String(500), nullable=True)  # 自定义图片路径，与 icon 二选一
```

**新增 API：**
- `POST /api/rewards/{id}/upload-image` - 上传奖励图片
- `GET /api/uploads/{filename}` - 访问上传的图片

**前端奖励卡片：**
- 优先显示 `image_url`（自定义图片）
- 无 `image_url` 时显示 Element Plus 图标（`icon` 字段）

### 2.2 兑换明细 Tab

**前端结构：**
- 激励中心页面新增 Tab：「兑换明细」
- 显示当前用户的兑换记录列表

**数据模型：** 沿用现有的 `Redemption` 表，已包含：
- `id`, `user_id`, `reward_id`, `star_cost`, `redeemed_at`
- 关联 `Reward` 表获取奖励名称

**展示字段：**
| 列名 | 说明 |
|-----|------|
| 奖励名称 | redemption.reward.name |
| 消耗积分 | redemption.star_cost |
| 兑换时间 | redemption.redeemed_at |

---

## 3. 成就系统增强

### 3.1 连续学习成就扩展

**新增行为配置（PRESET_ACTIONS）：**
| code | name | star_value |
|------|------|-----------|
| continuous_14day | 连续14天学习 | 100 |
| continuous_30day | 连续30天学习 | 200 |

**新增成就配置（PRESET_ACHIEVEMENTS）：**
| code | name | level | trigger_action | trigger_count | reward_stars |
|------|------|-------|----------------|----------------|--------------|
| continuous_learning | 连续学习 | 1 | continuous_7day | 7 | 50 |
| continuous_learning | 连续学习 | 2 | continuous_14day | 14 | 100 |
| continuous_learning | 连续学习 | 3 | continuous_30day | 30 | 200 |

**触发逻辑：**
- 在 `trigger_action` API 中，当任何学习行为触发时检查连续学习状态
- 调用 `check_continuous_learning(db, user_id)` 函数：
  1. 查询 `StarRecord` 中该用户最近的学习日期
  2. 判断是否构成连续 7/14/30 天
  3. 如有新成就解锁，插入 `StarRecord` 记录并更新进度

### 3.2 单词正确率成就

**新增数据模型：**
```python
class AchievementConfig(Base):
    """成就配置表"""
    __tablename__ = "achievement_config"

    id = Column(Integer, primary_key=True, autoincrement=True)
    achievement_id = Column(Integer, ForeignKey("achievement.id"), unique=True)
    min_words = Column(Integer, default=10)      # 每次最少单词数
    min_accuracy = Column(Integer, default=90)   # 最低正确率%
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())
```

**初始数据：**
```python
# 单词正确率成就
{"code": "word_accuracy", "name": "单词正确率", "level": 1,
 "trigger_action": "review_word_accuracy", "trigger_count": 1, "reward_stars": 30,
 "description": "单次复习10个单词以上且正确率90%以上"},
```

**触发逻辑：**
- 单词复习完成时，调用 `check_word_accuracy(db, user_id, review_result)`
- `review_result` 包含：`total_count`, `correct_count`
- 判断：`total_count >= min_words AND accuracy >= min_accuracy`
- 解锁后插入 `StarRecord(action_code="review_word_accuracy")`

### 3.3 行为触发端点扩展

**现有触发端点：**
- `POST /api/motivation/trigger/{action_code}`

**扩展行为触发时同时检查连续学习：**
```python
@router.post("/motivation/trigger/{action_code}")
def trigger_action(action_code: str, reason: str = None, db: Session = Depends(get_db)):
    service = MotivationService(db)
    result = service.trigger_action(action_code, reason=reason)

    # 新增：检查连续学习
    if result:
        service.check_continuous_learning()

    return result
```

**单词复习完成触发：**
- `POST /api/motivation/trigger/review_word_accuracy`
- 请求体：`{"total_count": 15, "correct_count": 14, "reason": "单词复习"}`

---

## 4. 前端页面变更

### 4.1 激励中心页面结构

```
激励中心
├── 积分成就 Tab（现有）
├── 兑换明细 Tab（新增）
└── 奖励商城 Tab（现有）
```

### 4.2 兑换明细 Tab

```html
<el-tab-pane label="兑换明细" name="redemptions">
  <el-table :data="redemptionList">
    <el-table-column prop="reward.name" label="奖励名称" />
    <el-table-column prop="star_cost" label="消耗积分" />
    <el-table-column prop="redeemed_at" label="兑换时间" formatter="formatDate" />
  </el-table>
</el-tab-pane>
```

### 4.3 奖励卡片图片展示

```html
<div class="reward-icon">
  <img v-if="reward.image_url" :src="reward.image_url" />
  <el-icon v-else :size="40"><component :is="reward.icon" /></el-icon>
</div>
```

---

## 5. API 汇总

### 5.1 新增 API

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | /api/rewards/{id}/upload-image | 上传奖励图片 |
| GET | /api/redemptions | 获取当前用户兑换明细（按用户筛选） |
| POST | /api/motivation/trigger/review_word_accuracy | 单词正确率触发 |

### 5.2 修改 API

| 方法 | 路径 | 变更 |
|------|------|------|
| GET | /api/rewards | 返回新增 `image_url` 字段 |
| GET | /api/achievements | 返回关联的 `config` 信息 |
| POST | /api/motivation/trigger/{action_code} | 触发后检查连续学习 |

---

## 6. 数据库变更

### 6.1 新增表

**achievement_config：**
| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER PK | 主键 |
| achievement_id | INTEGER FK | 关联成就ID |
| min_words | INTEGER | 最少单词数（默认10） |
| min_accuracy | INTEGER | 最低正确率%（默认90） |
| created_at | DATETIME | 创建时间 |
| updated_at | DATETIME | 更新时间 |

### 6.2 修改表

**reward 表新增：**
| 字段 | 类型 | 说明 |
|------|------|------|
| image_url | VARCHAR(500) | 自定义图片路径 |

---

## 7. 文件变更清单

### 后端
- `backend/app/models/reward.py` - 增加 image_url 字段
- `backend/app/models/achievement.py` - 新增 AchievementConfig 模型
- `backend/app/schemas/achievement.py` - 增加 AchievementConfigSchema
- `backend/app/services/motivation.py` - 增加连续学习检查、单词正确率检查逻辑
- `backend/app/services/init_motivation_data.py` - 增加新成就和行为初始化
- `backend/app/routers/motivation.py` - 增加图片上传、兑换明细接口
- `backend/app/routers/upload.py` - 复用现有图片上传或新建接口

### 前端
- `frontend/src/views/Motivation.vue` - 新增兑换明细 Tab，奖励卡片支持图片
- `frontend/src/api/motivation.js` - 新增 API 方法

---

## 8. 待讨论

无

---

## 9. 依赖项

- 单词复习完成时需调用激励触发接口（触发单词正确率成就检查）
- 图片上传复用现有的上传服务
