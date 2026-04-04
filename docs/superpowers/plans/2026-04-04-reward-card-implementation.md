# 奖励卡片样式改造实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将奖励商城从网格布局改为左侧列表+右侧详情布局

**Architecture:** 修改 Motivation.vue 的奖励商城部分，使用 flex 布局实现左侧120px卡片列表和右侧详情区域

**Tech Stack:** Vue 3 + Element Plus + CSS

---

## 文件修改

- Modify: `frontend/src/views/Motivation.vue` (奖励商城 Tab 的模板和样式)

---

## 实施步骤

### Task 1: 修改奖励商城模板结构

**Files:**
- Modify: `frontend/src/views/Motivation.vue:86-128`

- [ ] **Step 1: 将 rewards-grid 改为左右布局**

替换整个奖励商城 Tab 内容（约87-128行）：
```html
<!-- 奖励商城 Tab -->
<el-tab-pane label="奖励商城" name="rewards">
  <div class="rewards-section">
    <div class="rewards-layout">
      <!-- 左侧列表 -->
      <div class="reward-list">
        <div
          v-for="reward in rewards"
          :key="reward.id"
          class="reward-list-card"
          :class="{ 'selected': selectedReward?.id === reward.id }"
          @click="selectReward(reward)"
        >
          <img v-if="reward.image_url" :src="reward.image_url" class="reward-list-img" />
          <div v-else class="reward-list-icon">
            <el-icon :size="30" color="#fff">
              <component :is="reward.icon || 'Present'" />
            </el-icon>
          </div>
          <div class="reward-list-name">{{ reward.name }}</div>
        </div>
      </div>

      <!-- 右侧详情 -->
      <div class="reward-detail">
        <div v-if="selectedReward" class="reward-detail-inner">
          <img
            v-if="selectedReward.image_url"
            :src="selectedReward.image_url"
            class="reward-detail-image"
          />
          <div v-else class="reward-detail-placeholder">
            <el-icon :size="80" color="#ccc">
              <component :is="selectedReward.icon || 'Present'" />
            </el-icon>
          </div>
          <div class="reward-detail-content">
            <h2 class="reward-detail-name">{{ selectedReward.name }}</h2>
            <div class="reward-detail-meta">
              <span class="reward-points">
                <el-icon><Coin /></el-icon>
                {{ selectedReward.points_required }}
              </span>
              <span class="reward-stock" :class="{ 'out-of-stock': selectedReward.stock === 0 }">
                库存: {{ selectedReward.stock }}
              </span>
            </div>
            <p class="reward-detail-desc">{{ selectedReward.description || '暂无描述' }}</p>
            <el-button
              type="primary"
              size="large"
              :disabled="selectedReward.stock === 0 || selectedReward.redeemed || userPoints.balance < selectedReward.points_required"
              @click="redeemReward(selectedReward)"
              class="redeem-btn"
            >
              {{ selectedReward.redeemed ? '已兑换' : (selectedReward.stock === 0 ? '库存不足' : '立即兑换') }}
            </el-button>
          </div>
        </div>
        <div v-else class="reward-empty">
          <el-empty description="请选择一个奖励" />
        </div>
      </div>
    </div>
  </div>
</el-tab-pane>
```

### Task 2: 添加选中状态和选择方法

**Files:**
- Modify: `frontend/src/views/Motivation.vue:318-335` (fetchRewards 函数附近)

- [ ] **Step 1: 添加 selectedReward ref 和 selectReward 方法**

在 fetchRewards 函数附近添加：
```javascript
const selectedReward = ref(null)

const selectReward = (reward) => {
  selectedReward.value = reward
}
```

- [ ] **Step 2: 在 fetchRewards 后自动选中第一个**

修改 fetchRewards 函数，在赋值 rewards 后添加：
```javascript
rewards.value = res.data.map(...)
if (rewards.value.length > 0 && !selectedReward.value) {
  selectedReward.value = rewards.value[0]
}
```

### Task 3: 添加 CSS 样式

**Files:**
- Modify: `frontend/src/views/Motivation.vue:683-762` (rewards-grid 样式附近)

- [ ] **Step 1: 替换 rewards-grid 样式为左右布局**

找到 `.rewards-grid` 样式（约683行），替换为：
```css
.rewards-layout {
  display: flex;
  gap: 24px;
  min-height: 500px;
}

.reward-list {
  width: 120px;
  flex-shrink: 0;
  max-height: 600px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.reward-list-card {
  width: 120px;
  height: 120px;
  border: 2px solid #f0f0f0;
  border-radius: 8px;
  overflow: hidden;
  cursor: pointer;
  transition: all 0.2s ease;
  display: flex;
  flex-direction: column;
}

.reward-list-card:hover {
  border-color: #409eff;
  transform: scale(1.05);
}

.reward-list-card.selected {
  border-color: #409eff;
  background: #ecf5ff;
}

.reward-list-img {
  width: 100%;
  height: 90px;
  object-fit: cover;
}

.reward-list-icon {
  width: 100%;
  height: 90px;
  background: #409eff;
  display: flex;
  align-items: center;
  justify-content: center;
}

.reward-list-name {
  height: 30px;
  line-height: 30px;
  font-size: 12px;
  text-align: center;
  padding: 0 4px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  background: #fff;
}

.reward-detail {
  flex: 1;
  background: #fff;
  border-radius: 12px;
  border: 1px solid #f0f0f0;
  overflow: hidden;
}

.reward-detail-inner {
  display: flex;
  flex-direction: column;
}

.reward-detail-image {
  width: 100%;
  max-height: 400px;
  object-fit: contain;
  background: #f5f5f5;
}

.reward-detail-placeholder {
  width: 100%;
  height: 300px;
  background: #f5f5f5;
  display: flex;
  align-items: center;
  justify-content: center;
}

.reward-detail-content {
  padding: 24px;
}

.reward-detail-name {
  font-size: 20px;
  font-weight: bold;
  color: #303133;
  margin: 0 0 16px 0;
}

.reward-detail-meta {
  display: flex;
  gap: 24px;
  margin-bottom: 16px;
}

.reward-detail-meta .reward-points {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 18px;
  font-weight: bold;
  color: #e6a23c;
}

.reward-detail-meta .reward-stock {
  font-size: 14px;
  color: #67c23a;
}

.reward-detail-meta .reward-stock.out-of-stock {
  color: #f56c6c;
}

.reward-detail-desc {
  font-size: 14px;
  color: #606266;
  line-height: 1.6;
  margin-bottom: 24px;
}

.reward-empty {
  height: 100%;
  min-height: 400px;
  display: flex;
  align-items: center;
  justify-content: center;
}

/* 隐藏旧的网格样式相关类 */
.rewards-grid,
.reward-card,
.reward-icon,
.reward-content {
  display: none;
}
```

### Task 4: 验证实现

- [ ] **Step 1: 检查是否有语法错误**

运行前端开发服务器检查编译是否通过

- [ ] **Step 2: 验证交互**

1. 打开奖励商城 Tab
2. 确认左侧显示120px卡片列表
3. 确认右侧显示选中奖励的详情
4. 测试点击不同卡片切换详情
5. 测试 hover 效果
6. 测试滚动（奖励数量多时）

---

## 验收标准检查

- [ ] 左侧列表固定120px宽度，支持垂直滚动
- [ ] hover时卡片边框变色+缩放效果
- [ ] 点击卡片后右侧显示对应详情
- [ ] 选中卡片保持高亮状态
- [ ] 右侧大图自适应宽度
- [ ] 描述文字完整展示
- [ ] 兑换按钮根据库存/余额状态正确禁用
