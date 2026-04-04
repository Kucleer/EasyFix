<template>
  <div class="motivation">
    <el-card v-loading="loading">
      <template #header>
        <div class="card-header">
          <span>激励中心</span>
          <el-button type="primary" @click="showPointsDetail">
            <el-icon><List /></el-icon>
            积分明细
          </el-button>
        </div>
      </template>

      <!-- Tab切换 -->
      <el-tabs v-model="activeTab">
        <!-- 积分成就 Tab -->
        <el-tab-pane label="积分成就" name="achievements">
          <!-- 积分概览 -->
          <div class="points-overview">
            <el-row :gutter="20">
              <el-col :span="12">
                <div class="points-card balance-card">
                  <div class="points-icon">
                    <el-icon :size="40"><Coin /></el-icon>
                  </div>
                  <div class="points-info">
                    <div class="points-label">积分余额</div>
                    <div class="points-value">{{ userPoints.balance }}</div>
                  </div>
                </div>
              </el-col>
              <el-col :span="12">
                <div class="points-card today-card">
                  <div class="points-icon">
                    <el-icon :size="40"><Calendar /></el-icon>
                  </div>
                  <div class="points-info">
                    <div class="points-label">今日获取</div>
                    <div class="points-value today-value">+{{ userPoints.today_earned }}</div>
                  </div>
                </div>
              </el-col>
            </el-row>
          </div>

          <!-- 成就徽章墙 -->
          <div class="achievements-section">
            <h3 class="section-title">成就徽章</h3>
            <div v-for="group in achievementGroups" :key="group.code" class="achievement-group">
              <div class="group-header">
                <span class="group-name">{{ group.name }}</span>
                <span class="group-progress">{{ group.unlocked_count }}/{{ group.total_count }}</span>
              </div>
              <div class="achievement-grid">
                <div
                  v-for="item in group.items"
                  :key="item.id"
                  class="achievement-item"
                  :class="{ 'is-locked': !item.unlocked, 'is-unlocked': item.unlocked }"
                  @click="showAchievementDetail(item)"
                >
                  <div class="achievement-icon" :style="{ backgroundColor: item.unlocked ? item.color : '#e0e0e0' }">
                    <el-icon :size="32" :color="item.unlocked ? '#fff' : '#999'">
                      <component :is="item.icon" />
                    </el-icon>
                  </div>
                  <div class="achievement-name">{{ item.name }}</div>
                  <div class="achievement-level">{{ item.level }}</div>
                  <div class="achievement-progress">
                    <el-progress
                      :percentage="item.progress"
                      :stroke-width="6"
                      :show-text="false"
                      :color="item.unlocked ? '#67c23a' : '#409eff'"
                    />
                  </div>
                  <div v-if="item.unlocked" class="achievement-badge">
                    <el-icon color="#fff"><Check /></el-icon>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </el-tab-pane>

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

        <!-- 积分明细 Tab -->
        <el-tab-pane label="积分明细" name="points">
          <el-table :data="pointsRecords" stripe style="width: 100%" max-height="400">
            <el-table-column prop="action_code" label="行为" width="150">
              <template #default="{ row }">
                {{ getActionName(row.action_code) }}
              </template>
            </el-table-column>
            <el-table-column prop="star_delta" label="积分变动" width="120">
              <template #default="{ row }">
                <span :class="row.star_delta > 0 ? 'text-success' : 'text-danger'">
                  {{ row.star_delta > 0 ? '+' : '' }}{{ row.star_delta }}
                </span>
              </template>
            </el-table-column>
            <el-table-column prop="balance_after" label="变动后余额" width="120" />
            <el-table-column prop="reason" label="备注" />
            <el-table-column prop="created_at" label="时间" width="180">
              <template #default="{ row }">
                {{ formatDate(row.created_at) }}
              </template>
            </el-table-column>
          </el-table>
          <el-pagination
            v-if="pointsRecordsTotal > 0"
            v-model:current-page="pointsQuery.page"
            :page-size="pointsQuery.limit"
            :total="pointsRecordsTotal"
            layout="prev, pager, next"
            @current-change="fetchRecords"
            style="margin-top: 16px; justify-content: center;"
          />
          <el-empty v-if="pointsRecords.length === 0" description="暂无积分记录" />
        </el-tab-pane>
      </el-tabs>
    </el-card>

    <!-- 成就详情弹窗 -->
    <el-dialog v-model="achievementDialogVisible" title="成就详情" width="500px">
      <div v-if="selectedAchievement" class="achievement-detail">
        <div class="detail-header">
          <div class="detail-icon" :style="{ backgroundColor: selectedAchievement.unlocked ? selectedAchievement.color : '#e0e0e0' }">
            <el-icon :size="48" :color="selectedAchievement.unlocked ? '#fff' : '#999'">
              <component :is="selectedAchievement.icon" />
            </el-icon>
          </div>
          <div class="detail-info">
            <h3>{{ selectedAchievement.name }}</h3>
            <el-tag :type="selectedAchievement.unlocked ? 'success' : 'info'" size="small">
              {{ selectedAchievement.unlocked ? '已解锁' : '未解锁' }}
            </el-tag>
          </div>
        </div>
        <el-descriptions :column="1" border class="detail-descriptions">
          <el-descriptions-item label="等级">{{ selectedAchievement.level }}</el-descriptions-item>
          <el-descriptions-item label="系列">{{ selectedAchievement.series_name }}</el-descriptions-item>
          <el-descriptions-item label="进度">
            <el-progress :percentage="selectedAchievement.progress" :color="selectedAchievement.unlocked ? '#67c23a' : '#409eff'" />
          </el-descriptions-item>
          <el-descriptions-item label="描述">{{ selectedAchievement.description }}</el-descriptions-item>
          <el-descriptions-item v-if="selectedAchievement.unlocked" label="解锁时间">
            {{ selectedAchievement.unlocked_at || '未知' }}
          </el-descriptions-item>
        </el-descriptions>
      </div>
      <template #footer>
        <el-button @click="achievementDialogVisible = false">关闭</el-button>
      </template>
    </el-dialog>

    <!-- 积分明细弹窗 -->
    <el-dialog v-model="pointsDetailVisible" title="积分明细" width="700px" destroy-on-close>
      <div class="points-detail">
        <el-table :data="pointsRecords" stripe style="width: 100%" max-height="400">
          <el-table-column prop="created_at" label="时间" width="160">
            <template #default="{ row }">
              {{ formatDate(row.created_at) }}
            </template>
          </el-table-column>
          <el-table-column prop="type" label="类型" width="120">
            <template #default="{ row }">
              <el-tag :type="row.type === 'earn' ? 'success' : row.type === 'spend' ? 'warning' : 'info'" size="small">
                {{ getTypeName(row.type) }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="points" label="积分" width="100">
            <template #default="{ row }">
              <span :class="row.type === 'earn' ? 'points-earn' : 'points-spend'">
                {{ row.type === 'earn' ? '+' : '-' }}{{ row.points }}
              </span>
            </template>
          </el-table-column>
          <el-table-column prop="reason" label="原因" min-width="200" />
        </el-table>
      </div>
      <template #footer>
        <el-button @click="pointsDetailVisible = false">关闭</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Coin, Calendar, Check, List, Star, Trophy, Medal, Present, Notebook, School, Timer, Aim } from '@element-plus/icons-vue'
import { motivationApi } from '@/api/motivation'

const activeTab = ref('achievements')

// 用户积分数据
const userPoints = ref({
  balance: 0,
  today_earned: 0,
})

// 成就数据
const achievements = ref([])

// 奖励数据
const rewards = ref([])

// 积分明细记录
const pointsRecords = ref([])
const pointsRecordsTotal = ref(0)
const pointsQuery = reactive({
  page: 1,
  limit: 20
})

// 兑换记录数据
const redemptionList = ref([])

// 成就弹窗
const achievementDialogVisible = ref(false)
const selectedAchievement = ref(null)

// 积分明细弹窗
const pointsDetailVisible = ref(false)

// 加载状态
const loading = ref(false)

// 获取概览数据
const fetchOverview = async () => {
  try {
    const res = await motivationApi.getOverview()
    userPoints.value = {
      balance: res.data.balance || 0,
      today_earned: res.data.today_stars || 0,
    }
  } catch (error) {
    console.error('获取概览失败:', error)
  }
}

// 获取成就进度
const fetchAchievements = async () => {
  try {
    const res = await motivationApi.getAchievementProgress()
    // 转换后端数据为前端格式
    achievements.value = res.data.map((p, index) => {
      const progress = p.achievement.trigger_count > 0
        ? Math.min(100, Math.round((p.current_count / p.achievement.trigger_count) * 100))
        : 0
      const seriesMap = {
        'upload_question': 'study',
        'review_practice_set': 'review',
        'review_word': 'review',
        'generate_similar': 'study',
        'create_practice_set': 'study',
      }
      // 根据触发行为确定图标
      const iconMapAction = {
        'upload_question': 'Notebook',
        'review_practice_set': 'Timer',
        'review_word': 'School',
        'generate_similar': 'Aim',
        'create_practice_set': 'Trophy',
      }
      return {
        id: p.achievement_id,
        code: seriesMap[p.achievement.trigger_action] || 'study',
        name: p.achievement.name,
        series_name: '学习成就',
        level: p.achievement.level === 1 ? '初级' : p.achievement.level === 2 ? '中级' : '高级',
        icon: iconMapAction[p.achievement.trigger_action] || 'Notebook',
        color: '#409eff',
        progress,
        unlocked: p.is_unlocked,
        unlocked_at: p.unlocked_at,
        description: p.achievement.description,
        trigger_count: p.achievement.trigger_count,
        current_count: p.current_count,
      }
    })
  } catch (error) {
    console.error('获取成就失败:', error)
  }
}

// 获取奖励列表
const fetchRewards = async () => {
  try {
    const res = await motivationApi.getRewards()
    rewards.value = res.data.map(r => ({
      id: r.id,
      name: r.name,
      description: r.description || '',
      image_url: r.image_url || '',
      points_required: r.cost_stars,
      stock: r.remaining_stock,
      color: r.color || '#409eff',
      icon: 'Present',
      redeemed: false,
    }))
    if (rewards.value.length > 0 && !selectedReward.value) {
      selectedReward.value = rewards.value[0]
    }
  } catch (error) {
    console.error('获取奖励失败:', error)
  }
}

// 选中奖励
const selectedReward = ref(null)

const selectReward = (reward) => {
  selectedReward.value = reward
}

// 获取积分记录
const fetchRecords = async () => {
  try {
    const skip = (pointsQuery.page - 1) * pointsQuery.limit
    const res = await motivationApi.getRecords({ skip, limit: pointsQuery.limit })
    pointsRecords.value = res.data.items
    pointsRecordsTotal.value = res.data.total
  } catch (error) {
    console.error('获取积分记录失败:', error)
  }
}

// 获取兑换记录
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

// 初始化数据
const initData = async () => {
  loading.value = true
  try {
    await Promise.all([
      fetchOverview(),
      fetchAchievements(),
      fetchRewards(),
      fetchRecords(),
      fetchRedemptions(),
    ])
  } finally {
    loading.value = false
  }
}

// 按系列分组成就
const achievementGroups = computed(() => {
  const groups = {}
  const seriesNames = {
    'study': '学习成就',
    'review': '复习成就',
    'accuracy': '正确率成就',
  }

  for (const item of achievements.value) {
    const code = item.code
    if (!groups[code]) {
      groups[code] = {
        code,
        name: seriesNames[code] || code,
        items: [],
        unlocked_count: 0,
        total_count: 0,
      }
    }
    groups[code].items.push(item)
    groups[code].total_count++
    if (item.unlocked) {
      groups[code].unlocked_count++
    }
  }

  return Object.values(groups)
})

// 显示成就详情
const showAchievementDetail = (item) => {
  selectedAchievement.value = item
  achievementDialogVisible.value = true
}

// 显示积分明细
const showPointsDetail = () => {
  pointsDetailVisible.value = true
}

// 格式化日期
const formatDate = (dateStr) => {
  if (!dateStr) return ''
  return new Date(dateStr).toLocaleString('zh-CN')
}

// 获取行为名称
const actionNameMap = {
  'upload_question': '上传错题',
  'review_practice_set': '复习练习集',
  'generate_similar': '生成相似题',
  'review_word': '背单词',
  'create_practice_set': '创建练习集',
  'daily_login': '每日登录',
  'continuous_7day': '连续7天学习',
  'continuous_14day': '连续14天学习',
  'continuous_30day': '连续30天学习',
  'review_word_accuracy': '单词正确率',
  'reward': '成就奖励',
  'redeem': '兑换奖励',
}
const getActionName = (actionCode) => {
  return actionNameMap[actionCode] || actionCode
}

// 获取类型名称
const getTypeName = (type) => {
  const map = {
    'earn': '获得',
    'spend': '消耗',
    'expire': '过期',
  }
  return map[type] || type
}

// 兑换奖励
const redeemReward = async (reward) => {
  try {
    await ElMessageBox.confirm(
      `确定要兑换「${reward.name}」吗？需要消耗 ${reward.points_required} 积分。`,
      '确认兑换',
      {
        confirmButtonText: '确认兑换',
        cancelButtonText: '取消',
        type: 'info',
      }
    )

    // 模拟兑换
    if (userPoints.value.balance >= reward.points_required) {
      userPoints.value.balance -= reward.points_required
      reward.redeemed = true
      ElMessage.success(`恭喜！成功兑换「${reward.name}」`)
    } else {
      ElMessage.warning('积分不足，无法兑换')
    }
  } catch (error) {
    // 用户取消
  }
}

// 图标名称到组件的映射
const iconMap = {
  Notebook, School, Trophy, Star, Medal, Present, Timer, Aim
}

onMounted(() => {
  initData()
})
</script>

<style scoped>
.motivation {
  max-width: 1200px;
  margin: 0 auto;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

/* 积分概览 */
.points-overview {
  margin-bottom: 30px;
}

.points-card {
  display: flex;
  align-items: center;
  padding: 25px 30px;
  border-radius: 12px;
  background: linear-gradient(135deg, #409eff 0%, #66b1ff 100%);
  color: white;
  box-shadow: 0 4px 12px rgba(64, 158, 255, 0.3);
}

.points-card.balance-card {
  background: linear-gradient(135deg, #409eff 0%, #66b1ff 100%);
}

.points-card.today-card {
  background: linear-gradient(135deg, #67c23a 0%, #95d475 100%);
  box-shadow: 0 4px 12px rgba(103, 194, 58, 0.3);
}

.points-icon {
  width: 60px;
  height: 60px;
  border-radius: 50%;
  background-color: rgba(255, 255, 255, 0.2);
  display: flex;
  align-items: center;
  justify-content: center;
  margin-right: 20px;
}

.points-info {
  flex: 1;
}

.points-label {
  font-size: 14px;
  opacity: 0.9;
  margin-bottom: 5px;
}

.points-value {
  font-size: 32px;
  font-weight: bold;
}

.today-value {
  color: #ffff00;
}

/* 成就徽章墙 */
.achievements-section {
  margin-top: 20px;
}

.section-title {
  font-size: 18px;
  color: #303133;
  margin-bottom: 20px;
  padding-left: 10px;
  border-left: 4px solid #409eff;
}

.achievement-group {
  margin-bottom: 30px;
}

.group-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 15px;
}

.group-name {
  font-size: 16px;
  font-weight: bold;
  color: #606266;
}

.group-progress {
  font-size: 14px;
  color: #909399;
}

.achievement-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
  gap: 20px;
}

.achievement-item {
  position: relative;
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 20px 15px;
  background-color: #fff;
  border-radius: 12px;
  border: 2px solid #f0f0f0;
  cursor: pointer;
  transition: all 0.3s ease;
}

.achievement-item:hover {
  transform: translateY(-5px);
  box-shadow: 0 8px 20px rgba(0, 0, 0, 0.1);
}

.achievement-item.is-locked {
  background-color: #f5f5f5;
}

.achievement-item.is-locked .achievement-icon {
  opacity: 0.5;
}

.achievement-item.is-unlocked {
  border-color: #67c23a;
}

.achievement-item.is-unlocked:hover {
  border-color: #85ce61;
}

.achievement-icon {
  width: 64px;
  height: 64px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 12px;
  transition: all 0.3s ease;
}

.achievement-name {
  font-size: 14px;
  font-weight: bold;
  color: #303133;
  text-align: center;
  margin-bottom: 4px;
}

.achievement-level {
  font-size: 12px;
  color: #909399;
  margin-bottom: 10px;
}

.achievement-progress {
  width: 100%;
}

.achievement-badge {
  position: absolute;
  top: 8px;
  right: 8px;
  width: 22px;
  height: 22px;
  border-radius: 50%;
  background-color: #67c23a;
  display: flex;
  align-items: center;
  justify-content: center;
}

/* 奖励商城 */
.rewards-section {
  margin-top: 20px;
}

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

.redeem-btn {
  width: 100%;
}

/* 成就详情弹窗 */
.achievement-detail {
  padding: 10px 0;
}

.detail-header {
  display: flex;
  align-items: center;
  margin-bottom: 20px;
}

.detail-icon {
  width: 80px;
  height: 80px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-right: 20px;
}

.detail-info h3 {
  margin: 0 0 10px;
  font-size: 20px;
  color: #303133;
}

.detail-descriptions {
  margin-top: 10px;
}

/* 积分明细 */
.points-detail {
  padding: 10px 0;
}

.points-earn {
  color: #67c23a;
  font-weight: bold;
}

.points-spend {
  color: #f56c6c;
  font-weight: bold;
}
</style>
