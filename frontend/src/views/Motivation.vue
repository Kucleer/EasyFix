<template>
  <div class="motivation">
    <el-card>
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
      <el-tabs v-model:active-tab="activeTab">
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
            <h3 class="section-title">可用奖励</h3>
            <div class="rewards-grid">
              <div
                v-for="reward in rewards"
                :key="reward.id"
                class="reward-card"
                :class="{ 'is-redeemed': reward.redeemed }"
              >
                <div class="reward-icon" :style="{ backgroundColor: reward.color }">
                  <el-icon :size="40" color="#fff">
                    <component :is="reward.icon" />
                  </el-icon>
                </div>
                <div class="reward-content">
                  <div class="reward-name">{{ reward.name }}</div>
                  <div class="reward-desc">{{ reward.description }}</div>
                  <div class="reward-meta">
                    <span class="reward-points">
                      <el-icon><Coin /></el-icon>
                      {{ reward.points_required }}
                    </span>
                    <span class="reward-stock" :class="{ 'out-of-stock': reward.stock === 0 }">
                      库存: {{ reward.stock }}
                    </span>
                  </div>
                  <el-button
                    type="primary"
                    size="small"
                    :disabled="reward.stock === 0 || reward.redeemed || userPoints.balance < reward.points_required"
                    @click="redeemReward(reward)"
                    class="redeem-btn"
                  >
                    {{ reward.redeemed ? '已兑换' : (reward.stock === 0 ? '库存不足' : '立即兑换') }}
                  </el-button>
                </div>
              </div>
            </div>
          </div>
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
import { Coin, Calendar, Check, List, Star, Trophy, Medal, Ribbon, Gift, Book, Study, Timer, Target } from '@element-plus/icons-vue'

const activeTab = ref('achievements')

// 用户积分数据
const userPoints = ref({
  balance: 1250,
  today_earned: 50,
})

// 成就数据
const achievements = ref([
  // 学习系列
  { id: 1, code: 'study', name: '初次学习', series_name: '学习成就', level: '初级', icon: 'Book', color: '#409eff', progress: 100, unlocked: true, unlocked_at: '2024-01-15', description: '完成第一次学习' },
  { id: 2, code: 'study', name: '学习达人', series_name: '学习成就', level: '中级', icon: 'Study', color: '#67c23a', progress: 70, unlocked: false, unlocked_at: null, description: '累计学习100道题目' },
  { id: 3, code: 'study', name: '学习大师', series_name: '学习成就', level: '高级', icon: 'Trophy', color: '#e6a23c', progress: 30, unlocked: false, unlocked_at: null, description: '累计学习500道题目' },
  { id: 4, code: 'study', name: '知识渊博', series_name: '学习成就', level: '终极', icon: 'Star', color: '#f56c6c', progress: 10, unlocked: false, unlocked_at: null, description: '累计学习1000道题目' },
  // 复习系列
  { id: 5, code: 'review', name: '复习新手', series_name: '复习成就', level: '初级', icon: 'Timer', color: '#909399', progress: 100, unlocked: true, unlocked_at: '2024-01-20', description: '完成第一次复习' },
  { id: 6, code: 'review', name: '复习坚持', series_name: '复习成就', level: '中级', icon: 'Medal', color: '#b37feb', progress: 60, unlocked: false, unlocked_at: null, description: '连续复习7天' },
  { id: 7, code: 'review', name: '复习达人', series_name: '复习成就', level: '高级', icon: 'Ribbon', color: '#ffd666', progress: 25, unlocked: false, unlocked_at: null, description: '连续复习30天' },
  // 正确率系列
  { id: 8, code: 'accuracy', name: '初露锋芒', series_name: '正确率成就', level: '初级', icon: 'Target', color: '#ff9f43', progress: 100, unlocked: true, unlocked_at: '2024-02-01', description: '单次练习正确率达到80%' },
  { id: 9, code: 'accuracy', name: '精准打击', series_name: '正确率成就', level: '中级', icon: 'Target', color: '#ff6b6b', progress: 50, unlocked: false, unlocked_at: null, description: '单次练习正确率达到90%' },
  { id: 10, code: 'accuracy', name: '完美答案', series_name: '正确率成就', level: '高级', icon: 'Trophy', color: '#f56c6c', progress: 20, unlocked: false, unlocked_at: null, description: '单次练习正确率达到100%' },
])

// 奖励数据
const rewards = ref([
  { id: 1, name: 'VIP会员一天', description: '解锁所有高级功能一天', points_required: 100, stock: 10, color: '#409eff', icon: 'Gift', redeemed: false },
  { id: 2, name: '自定义头像框', description: '使用自定义头像框7天', points_required: 200, stock: 5, color: '#67c23a', icon: 'Medal', redeemed: false },
  { id: 3, name: '主题皮肤', description: '解锁专属主题皮肤', points_required: 300, stock: 3, color: '#e6a23c', icon: 'Star', redeemed: true },
  { id: 4, name: 'VIP会员一周', description: '解锁所有高级功能一周', points_required: 500, stock: 5, color: '#f56c6c', icon: 'Gift', redeemed: false },
  { id: 5, name: '专属徽章', description: '获得专属成就徽码', points_required: 800, stock: 2, color: '#b37feb', icon: 'Ribbon', redeemed: false },
  { id: 6, name: 'VIP会员一月', description: '解锁所有高级功能一个月', points_required: 1500, stock: 3, color: '#ffd666', icon: 'Gift', redeemed: false },
])

// 积分明细记录
const pointsRecords = ref([
  { id: 1, type: 'earn', points: 20, reason: '完成单词复习', created_at: '2024-03-01 10:30:00' },
  { id: 2, type: 'earn', points: 30, reason: '完成错题练习', created_at: '2024-03-01 14:20:00' },
  { id: 3, type: 'spend', points: 100, reason: '兑换VIP会员一天', created_at: '2024-03-01 16:00:00' },
  { id: 4, type: 'earn', points: 15, reason: '每日签到奖励', created_at: '2024-02-28 09:00:00' },
  { id: 5, type: 'earn', points: 25, reason: '分享练习成果', created_at: '2024-02-27 15:30:00' },
])

// 成就弹窗
const achievementDialogVisible = ref(false)
const selectedAchievement = ref(null)

// 积分明细弹窗
const pointsDetailVisible = ref(false)

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
  Book, Study, Trophy, Star, Medal, Ribbon, Gift, Timer, Target
}

onMounted(() => {
  // 可以在这里获取实际数据
  // fetchUserPoints()
  // fetchAchievements()
  // fetchRewards()
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

.rewards-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 20px;
}

.reward-card {
  display: flex;
  flex-direction: column;
  background-color: #fff;
  border-radius: 12px;
  border: 2px solid #f0f0f0;
  overflow: hidden;
  transition: all 0.3s ease;
}

.reward-card:hover {
  transform: translateY(-5px);
  box-shadow: 0 8px 20px rgba(0, 0, 0, 0.1);
}

.reward-card.is-redeemed {
  opacity: 0.6;
}

.reward-icon {
  height: 100px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.reward-content {
  padding: 15px;
  flex: 1;
  display: flex;
  flex-direction: column;
}

.reward-name {
  font-size: 16px;
  font-weight: bold;
  color: #303133;
  margin-bottom: 8px;
}

.reward-desc {
  font-size: 13px;
  color: #909399;
  margin-bottom: 12px;
  flex: 1;
}

.reward-meta {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.reward-points {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 16px;
  font-weight: bold;
  color: #e6a23c;
}

.reward-stock {
  font-size: 13px;
  color: #67c23a;
}

.reward-stock.out-of-stock {
  color: #f56c6c;
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
