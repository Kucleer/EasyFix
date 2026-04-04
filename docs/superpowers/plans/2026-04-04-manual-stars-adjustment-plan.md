# 积分手动调整功能实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在管理后台允许管理员手动调整用户积分（增加或减少），调整记录通过激励中心可查看。

**Architecture:** 后端新增积分调整 API，前端在管理后台新增调整表单，激励中心积分明细展示调整记录。

**Tech Stack:** FastAPI (后端), Vue 3 + Element Plus (前端), SQLAlchemy (数据库)

---

## Task 1: 添加积分调整 Schema

**Files:**
- Modify: `backend/app/schemas/star.py`

- [ ] **Step 1: 添加请求和响应 Schema**

在 `backend/app/schemas/star.py` 文件末尾添加：

```python
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
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/schemas/star.py
git commit -m "feat: add stars adjust request/response schemas"
```

---

## Task 2: 添加积分调整 API

**Files:**
- Modify: `backend/app/routers/motivation.py`

- [ ] **Step 1: 添加 POST /api/stars/adjust 接口**

在 `backend/app/routers/motivation.py` 的"积分模块"部分（`get_balance` 之后），添加：

```python
@router.post("/stars/adjust")
def adjust_stars(data: StarsAdjustRequest, db: Session = Depends(get_db)):
    """手动调整积分（增加或减少）"""
    from app.models.star import StarAction, StarRecord, StarBalance

    # 校验
    if data.delta == 0:
        raise HTTPException(status_code=400, detail="积分变动不能为0")
    if not data.reason or len(data.reason.strip()) == 0:
        raise HTTPException(status_code=400, detail="请输入调整原因")
    if len(data.reason) > 200:
        raise HTTPException(status_code=400, detail="调整原因不能超过200字符")

    # 获取或创建余额
    balance = db.query(StarBalance).filter(StarBalance.user_id == DEFAULT_USER_ID).first()
    if not balance:
        balance = StarBalance(user_id=DEFAULT_USER_ID, balance=0)
        db.add(balance)
        db.commit()
        db.refresh(balance)

    # 检查余额是否足够（减少时）
    if data.delta < 0 and balance.balance + data.delta < 0:
        raise HTTPException(status_code=400, detail="积分不足，无法减少")

    # 计算新余额
    new_balance = balance.balance + data.delta

    # 创建积分记录
    record = StarRecord(
        user_id=DEFAULT_USER_ID,
        action_code="manual_adjustment",
        star_delta=data.delta,
        balance_after=new_balance,
        reason=data.reason.strip()
    )
    db.add(record)
    db.commit()
    db.refresh(record)

    # 更新余额
    balance.balance = new_balance
    db.commit()

    return {
        "success": True,
        "new_balance": new_balance,
        "delta": data.delta,
        "record_id": record.id
    }
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/routers/motivation.py
git commit -m "feat: add POST /api/stars/adjust endpoint"
```

---

## Task 3: 添加预设行为数据

**Files:**
- Modify: `backend/app/services/init_motivation_data.py`

- [ ] **Step 1: 在 PRESET_ACTIONS 列表中添加 manual_adjustment**

在 `backend/app/services/init_motivation_data.py` 文件的 `PRESET_ACTIONS` 列表中，添加：

```python
{"code": "manual_adjustment", "name": "手动调整", "star_value": 0},
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/services/init_motivation_data.py
git commit -m "feat: add manual_adjustment preset action"
```

---

## Task 4: 添加前端 API 调用

**Files:**
- Modify: `frontend/src/api/motivation.js`

- [ ] **Step 1: 添加 adjustStars 方法**

在 `frontend/src/api/motivation.js` 的 motivationApi 对象中添加：

```javascript
// 积分调整
adjustStars(data) {
  return api.post('/stars/adjust', data)
},
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/api/motivation.js
git commit -m "feat: add adjustStars API call"
```

---

## Task 5: 添加管理后台积分调整表单

**Files:**
- Modify: `frontend/src/views/Management.vue`

- [ ] **Step 1: 在激励 Tab 中添加积分调整区块**

在 Management.vue 的激励 Tab 部分，找到行为配置区域上方，添加：

```html
<!-- 积分调整区块 -->
<div class="stars-adjust-section">
  <h4>积分调整</h4>
  <el-form :model="starsAdjustForm" :inline="true" size="default">
    <el-form-item label="积分变动">
      <el-input-number
        v-model="starsAdjustForm.delta"
        :min="-9999"
        :max="9999"
        controls-position="right"
        style="width: 120px"
      />
      <span style="margin-left: 8px; color: #909399;">（正数增加，负数减少）</span>
    </el-form-item>
    <el-form-item label="调整原因" required>
      <el-input
        v-model="starsAdjustForm.reason"
        placeholder="请输入调整原因"
        maxlength="200"
        show-word-limit
        style="width: 300px"
      />
    </el-form-item>
    <el-form-item>
      <el-button type="primary" @click="handleStarsAdjust" :loading="starsAdjustLoading">
        确认调整
      </el-button>
    </el-form-item>
  </el-form>
  <div v-if="starsAdjustResult !== null" class="adjust-result">
    调整后积分余额：<span class="balance-value">{{ starsAdjustResult }}</span>
  </div>
</div>
```

- [ ] **Step 2: 添加数据和方法**

在 `<script setup>` 部分添加：

```javascript
// 积分调整相关
const starsAdjustForm = reactive({
  delta: 0,
  reason: ''
})
const starsAdjustLoading = ref(false)
const starsAdjustResult = ref(null)

const handleStarsAdjust = async () => {
  if (!starsAdjustForm.reason.trim()) {
    ElMessage.warning('请输入调整原因')
    return
  }
  try {
    starsAdjustLoading.value = true
    const { data } = await motivationApi.adjustStars({
      delta: starsAdjustForm.delta,
      reason: starsAdjustForm.reason
    })
    starsAdjustResult.value = data.new_balance
    starsAdjustForm.delta = 0
    starsAdjustForm.reason = ''
    ElMessage.success('积分调整成功')
    // 刷新积分数据
    fetchBalance()
  } catch (error) {
    ElMessage.error(error.detail || '调整失败')
  } finally {
    starsAdjustLoading.value = false
  }
}
```

- [ ] **Step 3: 添加样式**

在 `<style scoped>` 中添加：

```css
.stars-adjust-section {
  background: #f5f7fa;
  border-radius: 8px;
  padding: 16px;
  margin-bottom: 20px;
}

.stars-adjust-section h4 {
  margin: 0 0 12px 0;
  color: #303133;
}

.adjust-result {
  margin-top: 12px;
  color: #606266;
}

.balance-value {
  font-size: 18px;
  font-weight: bold;
  color: #409eff;
}
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/views/Management.vue
git commit -m "feat: add stars adjustment form in Management page"
```

---

## 实施检查清单

- [ ] 后端 Schema 已添加
- [ ] POST /api/stars/adjust 接口可访问
- [ ] manual_adjustment 预设行为已添加到数据库
- [ ] 前端 API 调用可用
- [ ] 管理后台表单可提交
- [ ] 积分余额正确更新
- [ ] 积分明细可查看调整记录
