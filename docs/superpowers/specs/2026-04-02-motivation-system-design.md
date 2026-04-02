# 激励系统设计方案

## 一、系统概述

激励系统包含：行为积分、成就徽章、奖励兑换三个模块，用于提升学生学习动力。

**设计模式**：方案二（标准型），功能完整但不过度设计。

---

## 二、数据库设计

### 2.1 ER图

```
┌─────────────────┐     ┌─────────────────┐
│   star_action   │     │  star_balance   │
│   (行为配置)     │     │   (积分余额)     │
└────────┬────────┘     └────────┬────────┘
         │                       │
         │ 触发                  │
         ▼                       │
┌─────────────────┐               │
│  star_record    │               │
│   (积分明细)     │               │
└────────┬────────┘               │
         │                       │
         ▼                       │
┌─────────────────┐     ┌─────────────────┐
│achievement_progress│   │   achievement   │
│   (成就进度)      │────│    (成就定义)    │
└─────────────────┘     └─────────────────┘

┌─────────────────┐     ┌─────────────────┐
│     reward      │     │   redemption    │
│   (奖励配置)     │────│   (兑换记录)     │
└─────────────────┘     └─────────────────┘
```

### 2.2 表结构详情

#### star_action（行为配置）

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | INTEGER | PK, AUTO | 主键 |
| code | VARCHAR(50) | NOT NULL, UNIQUE | 行为代码 |
| name | VARCHAR(100) | NOT NULL | 行为名称 |
| star_value | INTEGER | NOT NULL, DEFAULT 0 | 积分值（可为负） |
| icon | VARCHAR(500) | | 图标URL |
| enabled | BOOLEAN | DEFAULT TRUE | 是否启用 |
| is_custom | BOOLEAN | DEFAULT FALSE | 是否自定义行为 |
| deleted | BOOLEAN | DEFAULT FALSE | 软删除 |
| created_at | DATETIME | DEFAULT NOW | 创建时间 |

**预设行为：**

| code | name | star_value | 说明 |
|------|------|------------|------|
| upload_question | 上传错题 | +10 | 每上传一道错题 |
| review_practice_set | 复习练习集 | +5 | 每完成一次练习集复习 |
| generate_similar | 生成相似题 | +3 | 每生成一道相似题 |
| review_word | 背单词 | +2 | 每完成一次单词复习 |
| create_practice_set | 创建练习集 | +5 | 每创建一个练习集 |
| daily_login | 每日登录 | +1 | 每天首次访问 |
| continuous_7day | 连续7天学习 | +50 | 连续7天有学习行为 |

#### star_balance（积分余额）

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | INTEGER | PK, AUTO | 主键 |
| user_id | INTEGER | DEFAULT 1 | 用户ID（预留，默认1） |
| balance | INTEGER | DEFAULT 0 | 当前积分余额 |
| updated_at | DATETIME | | 更新时间 |

#### star_record（积分明细）

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | INTEGER | PK, AUTO | 主键 |
| user_id | INTEGER | DEFAULT 1 | 用户ID（预留） |
| action_code | VARCHAR(50) | NOT NULL | 行为代码 |
| star_delta | INTEGER | NOT NULL | 积分变动值 |
| balance_after | INTEGER | NOT NULL | 变动后余额 |
| reason | VARCHAR(200) | | 变动原因 |
| created_at | DATETIME | DEFAULT NOW | 时间 |

#### achievement（成就定义）

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | INTEGER | PK, AUTO | 主键 |
| code | VARCHAR(50) | NOT NULL | 成就代码（同成就多级共享） |
| name | VARCHAR(100) | NOT NULL | 成就名称 |
| level | INTEGER | DEFAULT 1 | 成就等级（1, 2, 3...） |
| description | VARCHAR(500) | | 成就描述 |
| icon | VARCHAR(500) | | 图标URL |
| trigger_action | VARCHAR(50) | NOT NULL | 触发行为代码 |
| trigger_count | INTEGER | NOT NULL | 触发次数阈值 |
| reward_stars | INTEGER | DEFAULT 0 | 达成奖励积分 |
| is_preset | BOOLEAN | DEFAULT FALSE | 是否预设 |
| is_active | BOOLEAN | DEFAULT TRUE | 是否启用 |
| deleted | BOOLEAN | DEFAULT FALSE | 软删除 |
| created_at | DATETIME | DEFAULT NOW | 创建时间 |

**唯一索引**: (code, level) — 同一成就的每个等级唯一
| is_preset | BOOLEAN | DEFAULT FALSE | 是否预设 |
| is_active | BOOLEAN | DEFAULT TRUE | 是否启用 |
| deleted | BOOLEAN | DEFAULT FALSE | 软删除 |
| created_at | DATETIME | DEFAULT NOW | 创建时间 |

**预设成就模板（多级示例）：**

| code | name | level | trigger_action | trigger_count | reward_stars |
|------|------|-------|----------------|---------------|--------------|
| first_upload | 首次上传 | 1 | upload_question | 1 | 20 |
| upload_master | 上传达人 | 1 | upload_question | 10 | 50 |
| upload_master | 上传达人 | 2 | upload_question | 50 | 100 |
| upload_master | 上传达人 | 3 | upload_question | 200 | 200 |
| review_master | 练习高手 | 1 | review_practice_set | 10 | 30 |
| review_master | 练习高手 | 2 | review_practice_set | 50 | 80 |
| review_master | 练习高手 | 3 | review_practice_set | 200 | 150 |
| word_master | 单词达人 | 1 | review_word | 50 | 50 |
| word_master | 单词达人 | 2 | review_word | 200 | 100 |
| word_master | 单词达人 | 3 | review_word | 500 | 200 |
| similar_master | 相似题专家 | 1 | generate_similar | 20 | 60 |
| similar_master | 相似题专家 | 2 | generate_similar | 100 | 120 |
| similar_master | 相似题专家 | 3 | generate_similar | 300 | 250 |

**说明**：
- 同一 `code` 表示同一成就系列的不同等级
- 用户需先达成 Lv1 才能解锁 Lv2，以此类推
- 成就进度共享计数，跨等级累加

#### achievement_progress（成就进度）

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | INTEGER | PK, AUTO | 主键 |
| user_id | INTEGER | DEFAULT 1 | 用户ID |
| achievement_id | INTEGER | FK → achievement.id | 成就ID（关联到具体等级） |
| current_count | INTEGER | DEFAULT 0 | 当前进度 |
| is_unlocked | BOOLEAN | DEFAULT FALSE | 是否已解锁 |
| unlocked_at | DATETIME | | 解锁时间 |

**唯一索引**: (user_id, achievement_id)

**进度追踪说明**：
- 同一成就多级共享进度（通过 achievement.code 关联）
- 用户解锁 Lv1 后，系统自动创建 Lv2 的进度记录
- 成就进度查询按 code 分组，展示所有等级状态

#### reward（奖励配置）

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | INTEGER | PK, AUTO | 主键 |
| name | VARCHAR(100) | NOT NULL | 奖励名称 |
| description | VARCHAR(500) | | 奖励描述 |
| icon | VARCHAR(500) | | 奖励图标 |
| cost_stars | INTEGER | NOT NULL | 消耗积分 |
| total_stock | INTEGER | DEFAULT -1 | 总库存（-1=无限） |
| remaining_stock | INTEGER | DEFAULT -1 | 剩余库存 |
| is_active | BOOLEAN | DEFAULT TRUE | 是否上架 |
| deleted | BOOLEAN | DEFAULT FALSE | 软删除 |
| created_at | DATETIME | DEFAULT NOW | 创建时间 |

#### redemption（兑换记录）

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | INTEGER | PK, AUTO | 主键 |
| user_id | INTEGER | DEFAULT 1 | 用户ID |
| reward_id | INTEGER | FK → reward.id | 奖励ID |
| star_cost | INTEGER | NOT NULL | 消耗积分 |
| redeemed_at | DATETIME | DEFAULT NOW | 兑换时间 |

---

## 三、API设计

### 3.1 积分模块

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /api/stars/balance | 获取积分余额 |
| GET | /api/stars/records | 获取积分明细（分页） |
| GET | /api/stars/actions | 获取行为列表（管理员） |
| PUT | /api/stars/actions/{id} | 更新行为配置（管理员） |
| POST | /api/stars/actions | 新增自定义行为（管理员） |
| DELETE | /api/stars/actions/{id} | 删除自定义行为（管理员） |

### 3.2 成就模块

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /api/achievements | 获取成就列表 |
| GET | /api/achievements/progress | 获取用户成就进度 |
| POST | /api/achievements | 新建成就（管理员） |
| PUT | /api/achievements/{id} | 更新成就（管理员） |
| DELETE | /api/achievements/{id} | 删除成就（管理员） |

### 3.3 奖励模块

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /api/rewards | 获取奖励列表（商城） |
| POST | /api/rewards | 新增奖励（管理员） |
| PUT | /api/rewards/{id} | 更新奖励（管理员） |
| DELETE | /api/rewards/{id} | 删除奖励（管理员） |
| POST | /api/rewards/{id}/redeem | 兑换奖励 |
| GET | /api/rewards/redemptions | 获取兑换记录 |

### 3.4 激励中心API

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /api/motivation/overview | 获取激励概览（积分+成就+奖励） |

---

## 四、业务流程

### 4.1 积分变动触发流程

```
用户操作 → 查找启用的star_action
         → 记录积分明细 (star_record)
         → 更新余额 (star_balance)
         → 检查成就进度 (achievement_progress)
         → 如达成，更新成就状态 + 发放奖励积分
```

### 4.2 兑换流程

```
用户兑换 → 校验余额是否足够
         → 校验库存是否足够（库存>-1时）
         → 扣除积分（创建积分明细，更新余额）
         → 减少库存（库存>-1时）
         → 创建兑换记录 (redemption)
```

---

## 五、前端页面

### 5.1 页面列表

| 路径 | 页面 | 功能 |
|------|------|------|
| /motivation | Motivation.vue | 激励中心：积分、成就、奖励三个模块 |
| /management | Management.vue | 新增Tab：行为配置、成就管理、奖励管理 |

### 5.2 激励中心（Motivation.vue）

**功能模块：**

1. **积分展示**
   - 当前积分余额（大数字展示）
   - 积分明细按钮 → 弹窗展示历史记录

2. **成就徽章墙**
   - 网格展示所有成就（按成就系列分组）
   - 同一成就显示多个等级（如：单词达人 Lv1/Lv2/Lv3）
   - 已解锁：彩色 + 解锁时间
   - 未解锁：灰色 + 当前进度/目标
   - 下一级未解锁时显示锁定状态
   - 点击成就 → 详情弹窗（描述、各等级进度、奖励）

3. **奖励商城**
   - 卡片列表展示可兑换奖励
   - 显示名称、图标、所需积分、库存
   - 库存紧张时提示
   - 点击兑换 → 确认弹窗

### 5.3 管理配置（Management.vue）

新增Tab：

1. **行为配置**
   - 列表展示所有行为
   - 可调整积分值、启用/禁用
   - 支持新增自定义行为

2. **成就管理**
   - 列表展示所有成就
   - 支持编辑、新增自定义成就
   - 预设成就不可删除

3. **奖励管理**
   - 列表展示所有奖励
   - 支持新增、编辑、删除
   - 显示库存情况

---

## 六、触发点集成

现有功能需在以下位置调用积分触发：

| 功能 | 触发点 | action_code |
|------|--------|-------------|
| 上传错题 | 错题创建成功 | upload_question |
| 复习练习集 | 练习集标记已复习 | review_practice_set |
| 生成相似题 | 相似题创建成功 | generate_similar |
| 背单词 | 单词复习提交 | review_word |
| 创建练习集 | 练习集创建成功 | create_practice_set |

---

## 七、访问控制

- 管理配置页面需要密码验证（复用现有32167）
- 积分、成就、奖励兑换面向所有用户（本地单用户应用）