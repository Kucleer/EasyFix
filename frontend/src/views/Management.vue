<template>
  <div class="management">
    <!-- 访问密码验证 -->
    <el-dialog v-model="showPasswordDialog" title="请输入访问密码" width="400px" :close-on-click-modal="false" :show-close="false">
      <el-form>
        <el-form-item label="访问密码">
          <el-input v-model="password" type="password" placeholder="请输入访问密码" @keyup.enter="verifyPassword" show-password />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button type="primary" @click="verifyPassword" :loading="verifying">验证</el-button>
      </template>
    </el-dialog>

    <el-card v-if="isVerified">
      <template #header>
        <div class="card-header">
          <span>管理中心</span>
        </div>
      </template>

      <el-tabs v-model="activeTab">
        <!-- 学科管理 -->
        <el-tab-pane label="学科管理" name="subjects">
          <div class="tab-content">
            <div class="action-bar">
              <el-button type="primary" @click="showSubjectDialog = true">
                <el-icon><Plus /></el-icon>
                新增学科
              </el-button>
            </div>
            <el-table :data="subjects" stripe style="width: 100%; margin-top: 15px">
              <el-table-column prop="id" label="ID" width="80" />
              <el-table-column prop="name" label="学科名称" />
              <el-table-column label="操作" width="120">
                <template #default="{ row }">
                  <el-button link type="danger" size="small" @click="deleteSubject(row)">删除</el-button>
                </template>
              </el-table-column>
            </el-table>
          </div>
        </el-tab-pane>

        <!-- 标签管理 -->
        <el-tab-pane label="标签管理" name="tags">
          <div class="tab-content">
            <div class="action-bar">
              <el-button type="primary" @click="showTagDialog = true">
                <el-icon><Plus /></el-icon>
                新增标签
              </el-button>
            </div>
            <el-table :data="tags" stripe style="width: 100%; margin-top: 15px">
              <el-table-column prop="id" label="ID" width="80" />
              <el-table-column prop="name" label="标签名称" />
              <el-table-column prop="color" label="颜色" width="120">
                <template #default="{ row }">
                  <el-tag :style="{ backgroundColor: row.color, color: '#fff' }">{{ row.color || '默认' }}</el-tag>
                </template>
              </el-table-column>
              <el-table-column label="操作" width="120">
                <template #default="{ row }">
                  <el-button link type="danger" size="small" @click="deleteTag(row)">删除</el-button>
                </template>
              </el-table-column>
            </el-table>
          </div>
        </el-tab-pane>

        <!-- 错误类型管理 -->
        <el-tab-pane label="错误类型管理" name="errorTypes">
          <div class="tab-content">
            <div class="action-bar">
              <el-button type="primary" @click="showErrorTypeDialog = true">
                <el-icon><Plus /></el-icon>
                新增错误类型
              </el-button>
            </div>
            <el-table :data="errorTypes" stripe style="width: 100%; margin-top: 15px">
              <el-table-column prop="id" label="ID" width="80" />
              <el-table-column prop="name" label="类型名称" />
              <el-table-column label="操作" width="120">
                <template #default="{ row }">
                  <el-button link type="danger" size="small" @click="deleteErrorType(row)">删除</el-button>
                </template>
              </el-table-column>
            </el-table>
          </div>
        </el-tab-pane>

        <!-- 知识点管理 -->
        <el-tab-pane label="知识点管理" name="knowledgePoints">
          <div class="tab-content">
            <div class="action-bar">
              <el-button type="primary" @click="showKnowledgeDialog = true">
                <el-icon><Plus /></el-icon>
                新增知识点
              </el-button>
            </div>
            <div class="filters">
              <el-select v-model="kpFilters.subject_id" placeholder="选择学科" clearable @change="fetchKnowledgePoints" style="width: 150px">
                <el-option v-for="s in subjects" :key="s.id" :label="s.name" :value="s.id" />
              </el-select>
              <el-select v-model="kpFilters.grade" placeholder="年级" clearable @change="fetchKnowledgePoints" style="width: 120px">
                <el-option v-for="g in gradeOptions" :key="g.value" :label="g.label" :value="g.value" />
              </el-select>
              <el-select v-model="kpFilters.semester" placeholder="学期" clearable @change="fetchKnowledgePoints" style="width: 100px">
                <el-option label="上学期" :value="1" />
                <el-option label="下学期" :value="2" />
              </el-select>
            </div>
            <el-table :data="knowledgePoints" stripe style="width: 100%; margin-top: 15px">
              <el-table-column prop="id" label="ID" width="80" />
              <el-table-column prop="name" label="知识点名称" />
              <el-table-column prop="subject_name" label="学科" width="100" />
              <el-table-column prop="grade" label="年级" width="80">
                <template #default="{ row }">
                  {{ getGradeLabel(row.grade) }}
                </template>
              </el-table-column>
              <el-table-column prop="semester" label="学期" width="80">
                <template #default="{ row }">
                  {{ row.semester === 1 ? '上学期' : '下学期' }}
                </template>
              </el-table-column>
              <el-table-column label="操作" width="120">
                <template #default="{ row }">
                  <el-button link type="danger" size="small" @click="deleteKnowledgePoint(row)">删除</el-button>
                </template>
              </el-table-column>
            </el-table>
          </div>
        </el-tab-pane>

        <!-- 错题本管理 -->
        <el-tab-pane label="错题本管理" name="errorBooks">
          <div class="tab-content">
            <div class="action-bar">
              <el-button type="primary" @click="showErrorBookDialog = true">
                <el-icon><Plus /></el-icon>
                新增错题本
              </el-button>
            </div>
            <el-table :data="errorBooks" stripe style="width: 100%; margin-top: 15px">
              <el-table-column prop="id" label="ID" width="80" />
              <el-table-column prop="name" label="错题本名称" />
              <el-table-column prop="subject_name" label="学科" width="100" />
              <el-table-column prop="description" label="描述" />
              <el-table-column label="操作" width="180">
                <template #default="{ row }">
                  <el-button link type="primary" size="small" @click="editErrorBook(row)">编辑</el-button>
                  <el-button link type="danger" size="small" @click="deleteErrorBook(row)">删除</el-button>
                </template>
              </el-table-column>
            </el-table>
          </div>
        </el-tab-pane>

        <!-- 行为配置 -->
        <el-tab-pane label="行为配置" name="starActions">
          <div class="tab-content">
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

            <div class="action-bar">
              <el-button type="primary" @click="showStarActionDialog = true">
                <el-icon><Plus /></el-icon>
                新增行为
              </el-button>
            </div>
            <el-table :data="starActions" stripe style="width: 100%; margin-top: 15px">
              <el-table-column prop="id" label="ID" width="80" />
              <el-table-column prop="code" label="行为代码" width="150" />
              <el-table-column prop="name" label="行为名称" width="120" />
              <el-table-column prop="star_value" label="积分值" width="100">
                <template #default="{ row }">
                  <span :class="row.star_value >= 0 ? 'text-success' : 'text-danger'">
                    {{ row.star_value >= 0 ? '+' : '' }}{{ row.star_value }}
                  </span>
                </template>
              </el-table-column>
              <el-table-column prop="enabled" label="启用" width="80">
                <template #default="{ row }">
                  <el-tag :type="row.enabled ? 'success' : 'info'">{{ row.enabled ? '是' : '否' }}</el-tag>
                </template>
              </el-table-column>
              <el-table-column prop="is_custom" label="类型" width="100">
                <template #default="{ row }">
                  <el-tag :type="row.is_custom ? 'warning' : 'primary'">{{ row.is_custom ? '自定义' : '预设' }}</el-tag>
                </template>
              </el-table-column>
              <el-table-column label="操作" width="180">
                <template #default="{ row }">
                  <el-button link type="primary" size="small" @click="editStarAction(row)">编辑</el-button>
                  <el-button link type="danger" size="small" @click="deleteStarAction(row)" :disabled="row.is_preset">删除</el-button>
                </template>
              </el-table-column>
            </el-table>
          </div>
        </el-tab-pane>

        <!-- 成就管理 -->
        <el-tab-pane label="成就管理" name="achievements">
          <div class="tab-content">
            <div class="action-bar">
              <el-button type="primary" @click="showAchievementDialog = true">
                <el-icon><Plus /></el-icon>
                新增成就
              </el-button>
            </div>
            <el-table :data="achievements" stripe style="width: 100%; margin-top: 15px">
              <el-table-column prop="id" label="ID" width="80" />
              <el-table-column prop="name" label="成就名称" width="120" />
              <el-table-column prop="level" label="等级" width="80" />
              <el-table-column prop="trigger_action" label="触发行为" width="150" />
              <el-table-column prop="trigger_count" label="触发次数" width="100" />
              <el-table-column prop="reward_stars" label="奖励积分" width="100" />
              <el-table-column prop="is_preset" label="类型" width="100">
                <template #default="{ row }">
                  <el-tag :type="row.is_preset ? 'primary' : 'warning'">{{ row.is_preset ? '预设' : '自定义' }}</el-tag>
                </template>
              </el-table-column>
              <el-table-column label="操作" width="180">
                <template #default="{ row }">
                  <el-button link type="primary" size="small" @click="editAchievement(row)" :disabled="row.is_preset">编辑</el-button>
                  <el-button link type="danger" size="small" @click="deleteAchievement(row)" :disabled="row.is_preset">删除</el-button>
                </template>
              </el-table-column>
            </el-table>
          </div>
        </el-tab-pane>

        <!-- 奖励管理 -->
        <el-tab-pane label="奖励管理" name="rewards">
          <div class="tab-content">
            <div class="action-bar">
              <el-button type="primary" @click="showRewardDialog = true">
                <el-icon><Plus /></el-icon>
                新增奖励
              </el-button>
            </div>
            <el-table :data="rewards" stripe style="width: 100%; margin-top: 15px">
              <el-table-column prop="id" label="ID" width="80" />
              <el-table-column prop="name" label="奖励名称" width="150" />
              <el-table-column prop="cost_stars" label="所需积分" width="100" />
              <el-table-column prop="total_stock" label="总库存" width="100">
                <template #default="{ row }">
                  {{ row.total_stock === -1 ? '无限' : row.total_stock }}
                </template>
              </el-table-column>
              <el-table-column prop="remaining_stock" label="剩余库存" width="100">
                <template #default="{ row }">
                  {{ row.remaining_stock === -1 ? '无限' : row.remaining_stock }}
                </template>
              </el-table-column>
              <el-table-column label="操作" width="180">
                <template #default="{ row }">
                  <el-button link type="primary" size="small" @click="editReward(row)">编辑</el-button>
                  <el-button link type="danger" size="small" @click="deleteReward(row)">删除</el-button>
                </template>
              </el-table-column>
            </el-table>
          </div>
        </el-tab-pane>
      </el-tabs>
    </el-card>

    <!-- 新增学科弹窗 -->
    <el-dialog v-model="showSubjectDialog" title="新增学科" width="400px">
      <el-form :model="subjectForm" label-width="80px">
        <el-form-item label="学科名称" required>
          <el-input v-model="subjectForm.name" placeholder="请输入学科名称" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showSubjectDialog = false">取消</el-button>
        <el-button type="primary" @click="createSubject">保存</el-button>
      </template>
    </el-dialog>

    <!-- 新增标签弹窗 -->
    <el-dialog v-model="showTagDialog" title="新增标签" width="400px">
      <el-form :model="tagForm" label-width="80px">
        <el-form-item label="标签名称" required>
          <el-input v-model="tagForm.name" placeholder="请输入标签名称" />
        </el-form-item>
        <el-form-item label="颜色">
          <el-color-picker v-model="tagForm.color" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showTagDialog = false">取消</el-button>
        <el-button type="primary" @click="createTag">保存</el-button>
      </template>
    </el-dialog>

    <!-- 新增错误类型弹窗 -->
    <el-dialog v-model="showErrorTypeDialog" title="新增错误类型" width="400px">
      <el-form :model="errorTypeForm" label-width="80px">
        <el-form-item label="类型名称" required>
          <el-input v-model="errorTypeForm.name" placeholder="请输入错误类型名称" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showErrorTypeDialog = false">取消</el-button>
        <el-button type="primary" @click="createErrorType">保存</el-button>
      </template>
    </el-dialog>

    <!-- 新增知识点弹窗 -->
    <el-dialog v-model="showKnowledgeDialog" title="新增知识点" width="500px">
      <el-form :model="knowledgeForm" label-width="100px">
        <el-form-item label="知识点名称" required>
          <el-input v-model="knowledgeForm.name" placeholder="请输入知识点名称" />
        </el-form-item>
        <el-form-item label="学科" required>
          <el-select v-model="knowledgeForm.subject_id" placeholder="选择学科" style="width: 100%">
            <el-option v-for="s in subjects" :key="s.id" :label="s.name" :value="s.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="年级">
          <el-select v-model="knowledgeForm.grade" placeholder="选择年级" clearable style="width: 100%">
            <el-option v-for="g in gradeOptions" :key="g.value" :label="g.label" :value="g.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="学期">
          <el-select v-model="knowledgeForm.semester" placeholder="选择学期" clearable style="width: 100%">
            <el-option label="上学期" :value="1" />
            <el-option label="下学期" :value="2" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showKnowledgeDialog = false">取消</el-button>
        <el-button type="primary" @click="createKnowledgePoint">保存</el-button>
      </template>
    </el-dialog>

    <!-- 新增/编辑错题本弹窗 -->
    <el-dialog v-model="showErrorBookDialog" :title="editErrorBookData ? '编辑错题本' : '新增错题本'" width="500px">
      <el-form :model="errorBookForm" label-width="100px">
        <el-form-item label="错题本名称" required>
          <el-input v-model="errorBookForm.name" placeholder="请输入错题本名称" />
        </el-form-item>
        <el-form-item label="学科" required>
          <el-select v-model="errorBookForm.subject_id" placeholder="选择学科" style="width: 100%">
            <el-option v-for="s in subjects" :key="s.id" :label="s.name" :value="s.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="errorBookForm.description" type="textarea" :rows="3" placeholder="请输入描述" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showErrorBookDialog = false">取消</el-button>
        <el-button type="primary" @click="createOrUpdateErrorBook">保存</el-button>
      </template>
    </el-dialog>

    <!-- 新增/编辑行为弹窗 -->
    <el-dialog v-model="showStarActionDialog" :title="editStarActionData ? '编辑行为' : '新增行为'" width="500px">
      <el-form :model="starActionForm" label-width="100px">
        <el-form-item label="行为代码" required>
          <el-input v-model="starActionForm.code" placeholder="如: upload_question" :disabled="!!editStarActionData" />
        </el-form-item>
        <el-form-item label="行为名称" required>
          <el-input v-model="starActionForm.name" placeholder="如: 上传错题" />
        </el-form-item>
        <el-form-item label="积分值" required>
          <el-input-number v-model="starActionForm.star_value" :min="-999" :max="999" />
        </el-form-item>
        <el-form-item label="启用">
          <el-switch v-model="starActionForm.enabled" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showStarActionDialog = false">取消</el-button>
        <el-button type="primary" @click="createOrUpdateStarAction">保存</el-button>
      </template>
    </el-dialog>

    <!-- 新增/编辑成就弹窗 -->
    <el-dialog v-model="showAchievementDialog" :title="editAchievementData ? '编辑成就' : '新增成就'" width="500px">
      <el-form :model="achievementForm" label-width="100px">
        <el-form-item label="成就名称" required>
          <el-input v-model="achievementForm.name" placeholder="如: 学习达人" />
        </el-form-item>
        <el-form-item label="等级" required>
          <el-input-number v-model="achievementForm.level" :min="1" :max="10" />
        </el-form-item>
        <el-form-item label="触发行为" required>
          <el-select v-model="achievementForm.trigger_action" placeholder="选择触发行为" style="width: 100%">
            <el-option v-for="a in starActions" :key="a.code" :label="a.name" :value="a.code" />
          </el-select>
        </el-form-item>
        <el-form-item label="触发次数" required>
          <el-input-number v-model="achievementForm.trigger_count" :min="1" :max="9999" />
        </el-form-item>
        <el-form-item label="奖励积分" required>
          <el-input-number v-model="achievementForm.reward_stars" :min="0" :max="9999" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showAchievementDialog = false">取消</el-button>
        <el-button type="primary" @click="createOrUpdateAchievement">保存</el-button>
      </template>
    </el-dialog>

    <!-- 新增/编辑奖励弹窗 -->
    <el-dialog v-model="showRewardDialog" :title="editRewardData ? '编辑奖励' : '新增奖励'" width="500px">
      <el-form :model="rewardForm" label-width="100px">
        <el-form-item label="奖励名称" required>
          <el-input v-model="rewardForm.name" placeholder="如: 免作业卡" />
        </el-form-item>
        <el-form-item label="奖励描述">
          <el-input v-model="rewardForm.description" type="textarea" :rows="2" placeholder="描述奖励的用途或详情" />
        </el-form-item>
        <el-form-item label="所需积分" required>
          <el-input-number v-model="rewardForm.cost_stars" :min="0" :max="99999" />
        </el-form-item>
        <el-form-item label="总库存">
          <el-input-number v-model="rewardForm.total_stock" :min="-1" :max="99999" placeholder="-1表示无限" />
        </el-form-item>
        <el-form-item label="剩余库存">
          <el-input-number v-model="rewardForm.remaining_stock" :min="-1" :max="99999" placeholder="-1表示无限" />
        </el-form-item>
        <el-form-item label="奖励图片">
          <div v-if="rewardForm.image_url" class="reward-image-preview">
            <img :src="rewardForm.image_url" style="width:100px;height:100px;object-fit:contain;border:1px solid #ddd;" />
            <el-button type="danger" size="small" @click="removeRewardImage" style="margin-top:8px;">删除图片</el-button>
          </div>
          <el-upload
            v-else
            ref="rewardImageRef"
            :auto-upload="false"
            :limit="1"
            accept="image/*"
            :on-change="uploadRewardImage"
          >
            <el-button size="small" type="primary">点击上传图片</el-button>
          </el-upload>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showRewardDialog = false">取消</el-button>
        <el-button type="primary" @click="createOrUpdateReward">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { questionApi, uploadApi } from '@/api/question'
import { motivationApi } from '@/api/motivation'
import axios from 'axios'

const activeTab = ref('subjects')
const showPasswordDialog = ref(true)
const isVerified = ref(false)
const password = ref('')
const verifying = ref(false)

// 年级选项
const gradeOptions = [
  { label: '一年级', value: 1 },
  { label: '二年级', value: 2 },
  { label: '三年级', value: 3 },
  { label: '四年级', value: 4 },
  { label: '五年级', value: 5 },
  { label: '六年级', value: 6 },
  { label: '初一', value: 7 },
  { label: '初二', value: 8 },
  { label: '初三', value: 9 },
  { label: '高一', value: 10 },
  { label: '高二', value: 11 },
  { label: '高三', value: 12 },
]

const getGradeLabel = (grade) => {
  if (!grade) return '未设置'
  const g = gradeOptions.find(o => o.value === grade)
  return g ? g.label : `${grade}年级`
}

// 学科
const subjects = ref([])
const showSubjectDialog = ref(false)
const subjectForm = reactive({ name: '' })

// 标签
const tags = ref([])
const showTagDialog = ref(false)
const tagForm = reactive({ name: '', color: '#409eff' })

// 错误类型
const errorTypes = ref([])
const showErrorTypeDialog = ref(false)
const errorTypeForm = reactive({ name: '' })

// 知识点
const knowledgePoints = ref([])
const kpFilters = reactive({ subject_id: null, grade: null, semester: null })
const showKnowledgeDialog = ref(false)
const knowledgeForm = reactive({ name: '', subject_id: null, grade: null, semester: null })

// 错题本
const errorBooks = ref([])
const showErrorBookDialog = ref(false)
const editErrorBookData = ref(null)
const errorBookForm = reactive({ name: '', subject_id: null, description: '' })

// 行为配置
const starActions = ref([])
const showStarActionDialog = ref(false)
const editStarActionData = ref(null)
const starActionForm = reactive({ code: '', name: '', star_value: 0, enabled: true })

// 积分调整相关
const starsAdjustForm = reactive({
  delta: 0,
  reason: ''
})
const starsAdjustLoading = ref(false)
const starsAdjustResult = ref(null)

const fetchBalance = async () => {
  try {
    const { data } = await motivationApi.getBalance()
    starsAdjustResult.value = data.balance
  } catch (e) {
    console.error('获取积分余额失败:', e)
  }
}

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

// 成就管理
const achievements = ref([])
const showAchievementDialog = ref(false)
const editAchievementData = ref(null)
const achievementForm = reactive({ name: '', level: 1, trigger_action: '', trigger_count: 1, reward_stars: 0 })

// 奖励管理
const rewards = ref([])
const showRewardDialog = ref(false)
const editRewardData = ref(null)
const rewardForm = reactive({ name: '', description: '', cost_stars: 0, total_stock: -1, remaining_stock: -1, image_url: '' })

// 获取学科列表
const fetchSubjects = async () => {
  try {
    const { data } = await questionApi.listSubjects()
    subjects.value = Array.isArray(data) ? data : (data.items || [])
  } catch (e) {
    console.error('获取学科失败:', e)
  }
}

// 创建学科
const createSubject = async () => {
  if (!subjectForm.name.trim()) {
    ElMessage.warning('请输入学科名称')
    return
  }
  try {
    await questionApi.createSubject(subjectForm.name)
    ElMessage.success('创建成功')
    showSubjectDialog.value = false
    subjectForm.name = ''
    fetchSubjects()
  } catch (e) {
    ElMessage.error('创建失败')
  }
}

// 删除学科
const deleteSubject = async (row) => {
  try {
    await ElMessageBox.confirm('确定要删除该学科吗？', '删除确认', { type: 'warning' })
    await questionApi.deleteSubject(row.id)
    ElMessage.success('删除成功')
    fetchSubjects()
  } catch (e) {
    if (e !== 'cancel') ElMessage.error('删除失败')
  }
}

// 获取标签列表
const fetchTags = async () => {
  try {
    const { data } = await questionApi.listTags()
    tags.value = Array.isArray(data) ? data : (data.items || [])
  } catch (e) {
    console.error('获取标签失败:', e)
  }
}

// 创建标签
const createTag = async () => {
  if (!tagForm.name.trim()) {
    ElMessage.warning('请输入标签名称')
    return
  }
  try {
    await questionApi.createTag(tagForm.name, tagForm.color)
    ElMessage.success('创建成功')
    showTagDialog.value = false
    tagForm.name = ''
    tagForm.color = '#409eff'
    fetchTags()
  } catch (e) {
    ElMessage.error('创建失败')
  }
}

// 删除标签
const deleteTag = async (row) => {
  try {
    await ElMessageBox.confirm('确定要删除该标签吗？', '删除确认', { type: 'warning' })
    await questionApi.deleteTag(row.id)
    ElMessage.success('删除成功')
    fetchTags()
  } catch (e) {
    if (e !== 'cancel') ElMessage.error('删除失败')
  }
}

// 获取错误类型列表
const errorTypeList = ref([
  { id: 1, name: '计算' },
  { id: 2, name: '概念' },
  { id: 3, name: '审题' },
  { id: 4, name: '其他' },
])

const fetchErrorTypes = async () => {
  errorTypes.value = errorTypeList.value
}

// 创建错误类型（预定义，不允许自定义）
const createErrorType = async () => {
  ElMessage.info('错误类型为系统预定义，不可添加')
}

// 删除错误类型（预定义，不允许删除）
const deleteErrorType = async (row) => {
  ElMessage.info('错误类型为系统预定义，不可删除')
}

// 获取知识点列表
const fetchKnowledgePoints = async () => {
  try {
    const params = {}
    if (kpFilters.subject_id) params.subject_id = kpFilters.subject_id
    if (kpFilters.grade) params.grade = kpFilters.grade
    if (kpFilters.semester) params.semester = kpFilters.semester
    const { data } = await questionApi.listKnowledgePoints(params)
    knowledgePoints.value = Array.isArray(data) ? data : []
  } catch (e) {
    console.error('获取知识点失败:', e)
  }
}

// 创建知识点
const createKnowledgePoint = async () => {
  if (!knowledgeForm.name.trim()) {
    ElMessage.warning('请输入知识点名称')
    return
  }
  if (!knowledgeForm.subject_id) {
    ElMessage.warning('请选择学科')
    return
  }
  try {
    await questionApi.createKnowledgePoint({
      name: knowledgeForm.name,
      subject_id: knowledgeForm.subject_id,
      grade: knowledgeForm.grade,
      semester: knowledgeForm.semester,
    })
    ElMessage.success('创建成功')
    showKnowledgeDialog.value = false
    knowledgeForm.name = ''
    knowledgeForm.subject_id = null
    knowledgeForm.grade = null
    knowledgeForm.semester = null
    fetchKnowledgePoints()
  } catch (e) {
    ElMessage.error('创建失败')
  }
}

// 删除知识点
const deleteKnowledgePoint = async (row) => {
  try {
    await ElMessageBox.confirm('确定要删除该知识点吗？', '删除确认', { type: 'warning' })
    await questionApi.deleteKnowledgePoint(row.id)
    ElMessage.success('删除成功')
    fetchKnowledgePoints()
  } catch (e) {
    if (e !== 'cancel') ElMessage.error('删除失败')
  }
}

// 获取错题本列表
const fetchErrorBooks = async () => {
  try {
    const { data } = await questionApi.listErrorBooks()
    errorBooks.value = data.items || []
    // 如果有subject_id，获取学科名称
    if (errorBooks.value.length > 0) {
      await fetchSubjects()
      errorBooks.value = errorBooks.value.map(eb => ({
        ...eb,
        subject_name: subjects.value.find(s => s.id === eb.subject_id)?.name || ''
      }))
    }
  } catch (e) {
    console.error('获取错题本失败:', e)
  }
}

// 创建或更新错题本
const createOrUpdateErrorBook = async () => {
  if (!errorBookForm.name.trim()) {
    ElMessage.warning('请输入错题本名称')
    return
  }
  if (!errorBookForm.subject_id) {
    ElMessage.warning('请选择学科')
    return
  }
  try {
    if (editErrorBookData.value) {
      await questionApi.updateErrorBook(editErrorBookData.value.id, errorBookForm)
      ElMessage.success('更新成功')
    } else {
      await questionApi.createErrorBook(errorBookForm)
      ElMessage.success('创建成功')
    }
    showErrorBookDialog.value = false
    editErrorBookData.value = null
    errorBookForm.name = ''
    errorBookForm.subject_id = null
    errorBookForm.description = ''
    fetchErrorBooks()
  } catch (e) {
    ElMessage.error('保存失败')
  }
}

// 编辑错题本
const editErrorBook = (row) => {
  editErrorBookData.value = row
  errorBookForm.name = row.name
  errorBookForm.subject_id = row.subject_id
  errorBookForm.description = row.description || ''
  showErrorBookDialog.value = true
}

// 删除错题本
const deleteErrorBook = async (row) => {
  try {
    await ElMessageBox.confirm('确定要删除该错题本吗？', '删除确认', { type: 'warning' })
    await questionApi.deleteErrorBook(row.id)
    ElMessage.success('删除成功')
    fetchErrorBooks()
  } catch (e) {
    if (e !== 'cancel') ElMessage.error('删除失败')
  }
}

// 获取行为列表
const fetchStarActions = async () => {
  try {
    const { data } = await motivationApi.getActions()
    starActions.value = Array.isArray(data) ? data : (data.items || [])
  } catch (e) {
    console.error('获取行为列表失败:', e)
  }
}

// 创建或更新行为
const createOrUpdateStarAction = async () => {
  if (!starActionForm.code.trim()) {
    ElMessage.warning('请输入行为代码')
    return
  }
  if (!starActionForm.name.trim()) {
    ElMessage.warning('请输入行为名称')
    return
  }
  try {
    if (editStarActionData.value) {
      await motivationApi.updateAction(editStarActionData.value.id, starActionForm)
      ElMessage.success('更新成功')
    } else {
      await motivationApi.createAction(starActionForm)
      ElMessage.success('创建成功')
    }
    showStarActionDialog.value = false
    editStarActionData.value = null
    starActionForm.code = ''
    starActionForm.name = ''
    starActionForm.star_value = 0
    starActionForm.enabled = true
    fetchStarActions()
  } catch (e) {
    ElMessage.error('保存失败')
  }
}

// 编辑行为
const editStarAction = (row) => {
  editStarActionData.value = row
  starActionForm.code = row.code
  starActionForm.name = row.name
  starActionForm.star_value = row.star_value
  starActionForm.enabled = row.enabled
  showStarActionDialog.value = true
}

// 删除行为
const deleteStarAction = async (row) => {
  try {
    await ElMessageBox.confirm('确定要删除该行为吗？', '删除确认', { type: 'warning' })
    await motivationApi.deleteAction(row.id)
    ElMessage.success('删除成功')
    fetchStarActions()
  } catch (e) {
    if (e !== 'cancel') ElMessage.error('删除失败')
  }
}

// 获取成就列表
const fetchAchievements = async () => {
  try {
    const { data } = await motivationApi.getAchievements()
    achievements.value = Array.isArray(data) ? data : (data.items || [])
  } catch (e) {
    console.error('获取成就列表失败:', e)
  }
}

// 创建或更新成就
const createOrUpdateAchievement = async () => {
  if (!achievementForm.name.trim()) {
    ElMessage.warning('请输入成就名称')
    return
  }
  if (!achievementForm.trigger_action) {
    ElMessage.warning('请选择触发行为')
    return
  }
  try {
    if (editAchievementData.value) {
      await motivationApi.updateAchievement(editAchievementData.value.id, achievementForm)
      ElMessage.success('更新成功')
    } else {
      await motivationApi.createAchievement(achievementForm)
      ElMessage.success('创建成功')
    }
    showAchievementDialog.value = false
    editAchievementData.value = null
    achievementForm.name = ''
    achievementForm.level = 1
    achievementForm.trigger_action = ''
    achievementForm.trigger_count = 1
    achievementForm.reward_stars = 0
    fetchAchievements()
  } catch (e) {
    ElMessage.error('保存失败')
  }
}

// 编辑成就
const editAchievement = (row) => {
  editAchievementData.value = row
  achievementForm.name = row.name
  achievementForm.level = row.level
  achievementForm.trigger_action = row.trigger_action
  achievementForm.trigger_count = row.trigger_count
  achievementForm.reward_stars = row.reward_stars
  showAchievementDialog.value = true
}

// 删除成就
const deleteAchievement = async (row) => {
  try {
    await ElMessageBox.confirm('确定要删除该成就吗？', '删除确认', { type: 'warning' })
    await motivationApi.deleteAchievement(row.id)
    ElMessage.success('删除成功')
    fetchAchievements()
  } catch (e) {
    if (e !== 'cancel') ElMessage.error('删除失败')
  }
}

// 获取奖励列表
const fetchRewards = async () => {
  try {
    const { data } = await motivationApi.getRewards()
    rewards.value = Array.isArray(data) ? data : (data.items || [])
  } catch (e) {
    console.error('获取奖励列表失败:', e)
  }
}

// 创建或更新奖励
const createOrUpdateReward = async () => {
  if (!rewardForm.name.trim()) {
    ElMessage.warning('请输入奖励名称')
    return
  }
  try {
    if (editRewardData.value) {
      await motivationApi.updateReward(editRewardData.value.id, rewardForm)
      ElMessage.success('更新成功')
    } else {
      await motivationApi.createReward(rewardForm)
      ElMessage.success('创建成功')
    }
    showRewardDialog.value = false
    editRewardData.value = null
    rewardForm.name = ''
    rewardForm.description = ''
    rewardForm.cost_stars = 0
    rewardForm.total_stock = -1
    rewardForm.remaining_stock = -1
    rewardForm.image_url = ''
    fetchRewards()
  } catch (e) {
    ElMessage.error('保存失败')
  }
}

// 上传奖励图片
const rewardImageRef = ref(null)
const uploadRewardImage = async (file) => {
  try {
    const { data } = await uploadApi.uploadFile(file.raw)
    rewardForm.image_url = '/uploads/' + data.path
    ElMessage.success('图片上传成功')
  } catch (e) {
    console.error('上传失败:', e)
    ElMessage.error('图片上传失败')
  }
  return false
}

const removeRewardImage = () => {
  rewardForm.image_url = ''
}

// 编辑奖励
const editReward = (row) => {
  editRewardData.value = row
  rewardForm.name = row.name
  rewardForm.description = row.description || ''
  rewardForm.cost_stars = row.cost_stars
  rewardForm.total_stock = row.total_stock
  rewardForm.remaining_stock = row.remaining_stock
  rewardForm.image_url = row.image_url || ''
  showRewardDialog.value = true
}

// 删除奖励
const deleteReward = async (row) => {
  try {
    await ElMessageBox.confirm('确定要删除该奖励吗？', '删除确认', { type: 'warning' })
    await motivationApi.deleteReward(row.id)
    ElMessage.success('删除成功')
    fetchRewards()
  } catch (e) {
    if (e !== 'cancel') ElMessage.error('删除失败')
  }
}

const verifyPassword = async () => {
  if (!password.value) {
    ElMessage.warning('请输入密码')
    return
  }
  verifying.value = true
  try {
    await axios.post('/api/auth/verify-password', { password: password.value })
    isVerified.value = true
    showPasswordDialog.value = false
    fetchAll()
  } catch (error) {
    ElMessage.error('密码错误')
    password.value = ''
  } finally {
    verifying.value = false
  }
}

const fetchAll = () => {
  fetchSubjects()
  fetchTags()
  fetchErrorTypes()
  fetchKnowledgePoints()
  fetchErrorBooks()
  fetchStarActions()
  fetchAchievements()
  fetchRewards()
}

onMounted(() => {
  // 先显示密码对话框
})
</script>

<style scoped>
.management {
  max-width: 1200px;
  margin: 0 auto;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.tab-content {
  padding: 10px 0;
}

.action-bar {
  margin-bottom: 10px;
}

.filters {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  margin-bottom: 15px;
}

.text-success {
  color: #67c23a;
  font-weight: bold;
}

.text-danger {
  color: #f56c6c;
  font-weight: bold;
}

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
</style>
