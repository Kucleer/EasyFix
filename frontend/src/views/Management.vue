<template>
  <div class="management">
    <PageHeading title="资料管理" description="整理学习资料，设置适合自己的学习偏好。" />
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
        <!-- 系统配置 -->
        <el-tab-pane label="系统配置" name="system">
          <div class="tab-content system-config">
            <el-form :model="appConfigForm" label-width="120px" style="max-width: 480px">
              <el-form-item label="默认年级">
                <el-select v-model="appConfigForm.defaultGrade" placeholder="选择默认年级" clearable style="width: 100%">
                  <el-option v-for="g in gradeOptions" :key="g.value" :label="g.label" :value="g.value" />
                </el-select>
                <div class="form-tip">各页面搜索/筛选将默认使用该年级；可单独清空后查看全部</div>
              </el-form-item>
              <el-form-item label="默认学期">
                <el-select v-model="appConfigForm.defaultSemester" placeholder="选择默认学期" clearable style="width: 100%">
                  <el-option label="上学期" :value="1" />
                  <el-option label="下学期" :value="2" />
                </el-select>
                <div class="form-tip">若页面提供学期筛选，将默认使用该值</div>
              </el-form-item>
              <el-form-item>
                <el-button type="primary" @click="saveAppConfig" :loading="savingAppConfig">保存配置</el-button>
              </el-form-item>
            </el-form>
            <el-alert type="info" :closable="false" style="margin-top: 8px">
              <template #title>
                保存后立即生效：单词、错题、阅读、学习报告、上传录入等页面的默认筛选与新建表单会自动带入默认年级。
              </template>
            </el-alert>
          </div>
        </el-tab-pane>

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
              <el-table-column label="操作" width="160" fixed="right"><template #default="{ row }"><ListActions :primary="{ label: '删除', run: () => deleteSubject(row), disabled: false, danger: true }" :actions="[]" /></template></el-table-column>
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
              <el-table-column label="操作" width="160" fixed="right"><template #default="{ row }"><ListActions :primary="{ label: '删除', run: () => deleteTag(row), disabled: false, danger: true }" :actions="[]" /></template></el-table-column>
            </el-table>
          </div>
        </el-tab-pane>

        <!-- 错误类型管理 -->
        <el-tab-pane label="错误类型管理" name="errorTypes">
          <div class="tab-content">
            <div class="action-bar">
              <el-button type="primary" @click="openErrorTypeDialog">
                <el-icon><Plus /></el-icon>
                新增错误类型
              </el-button>
            </div>
            <el-table :data="errorTypes" stripe style="width: 100%; margin-top: 15px">
              <el-table-column prop="id" label="ID" width="80" />
              <el-table-column prop="name" label="类型名称" />
              <el-table-column prop="subject_name" label="学科" width="120" />
              <el-table-column label="操作" width="160" fixed="right"><template #default="{ row }"><ListActions :primary="{ label: '编辑', run: () => editErrorType(row), disabled: false, danger: false }" :actions="[{ label: '删除', run: () => deleteErrorType(row), disabled: false, danger: true }]" /></template></el-table-column>
            </el-table>
          </div>
        </el-tab-pane>

        <!-- 知识点管理 -->
        <el-tab-pane label="知识点管理" name="knowledgePoints">
          <div class="tab-content">
            <el-alert
              type="info"
              :closable="false"
              show-icon
              class="kp-tip"
              title="两级目录：一级是知识模块，二级是具体考点。删除有子级或有题目引用的节点会被拒绝；有引用的节点也不能改学科或移动。"
            />
            <div class="action-bar">
              <el-button type="primary" @click="openKnowledgeDialog(1)">
                <el-icon><Plus /></el-icon>
                新增一级模块
              </el-button>
              <el-button @click="openKnowledgeDialog(2)">
                <el-icon><Plus /></el-icon>
                新增二级考点
              </el-button>
              <el-button v-if="legacyKnowledgePoints.length" plain type="warning" @click="showLegacy = !showLegacy">
                待处理旧目录 {{ legacyKnowledgePoints.length }}
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
              <el-input v-model="kpFilters.keyword" placeholder="搜索名称" clearable @change="fetchKnowledgePoints" style="width: 180px" />
            </div>
            <el-table :data="knowledgePoints" row-key="id" :tree-props="{ children: 'children' }" default-expand-all stripe style="width: 100%; margin-top: 15px" empty-text="暂无目录数据">
              <el-table-column label="知识点" min-width="230">
                <template #default="{ row }">
                  <KnowledgeTag :point="row" :subject-id="row.subject_id" :show-path="row.level === 2" />
                  <el-tag size="small" :type="row.level === 1 ? 'primary' : 'info'">{{ row.level === 1 ? '一级' : '二级' }}</el-tag>
                </template>
              </el-table-column>
              <el-table-column prop="code" label="编码" width="170" />
              <el-table-column prop="subject_name" label="学科" width="90" />
              <el-table-column label="题数" width="80" align="right">
                <template #default="{ row }">{{ row.question_count || 0 }}</template>
              </el-table-column>
              <el-table-column label="子级 / 错误类型" min-width="180">
                <template #default="{ row }">
                  <span v-if="row.level === 1">子级 {{ row.child_count || 0 }} 个</span>
                  <div v-else class="kp-errors">
                    <el-tag v-for="et in row.error_types || []" :key="et.id" size="small">{{ et.name }}</el-tag>
                    <span v-if="!row.error_types?.length" class="text-muted">未配置</span>
                  </div>
                </template>
              </el-table-column>
              <el-table-column prop="sort_order" label="排序" width="70" align="right" />
              <el-table-column label="操作" width="190" fixed="right">
                <template #default="{ row }">
                  <ListActions
                    :primary="{ label: '编辑', run: () => editKnowledgePoint(row) }"
                    :actions="[
                      ...(row.level === 1 ? [{ label: '新增二级', run: () => openKnowledgeDialog(2, row) }] : []),
                      { label: '删除', run: () => deleteKnowledgePoint(row), danger: true },
                    ]"
                  />
                </template>
              </el-table-column>
            </el-table>
            <div v-if="showLegacy" class="legacy-panel">
              <h4>待处理旧目录（level 为空，不参与新树与新统计）</h4>
              <el-table :data="legacyKnowledgePoints" size="small" empty-text="没有待处理旧目录">
                <el-table-column prop="id" label="ID" width="80" />
                <el-table-column prop="name" label="原名称" />
                <el-table-column prop="subject_name" label="学科" width="100" />
                <el-table-column label="题数" width="80" align="right">
                  <template #default="{ row }">{{ row.question_count || 0 }}</template>
                </el-table-column>
                <el-table-column label="操作" width="160">
                  <template #default="{ row }">
                    <el-button link type="primary" @click="promoteLegacy(row)">转为二级</el-button>
                    <el-button link type="danger" :disabled="row.question_count > 0" @click="deleteKnowledgePoint(row)">软删除</el-button>
                  </template>
                </el-table-column>
              </el-table>
            </div>
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
              <el-table-column label="操作" width="160" fixed="right"><template #default="{ row }"><ListActions :primary="{ label: '编辑', run: () => editErrorBook(row), disabled: false, danger: false }" :actions="[{ label: '删除', run: () => deleteErrorBook(row), disabled: false, danger: true }]" /></template></el-table-column>
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
              <el-table-column label="操作" width="160" fixed="right"><template #default="{ row }"><ListActions :primary="{ label: '编辑', run: () => editStarAction(row), disabled: false, danger: false }" :actions="[{ label: '删除', run: () => deleteStarAction(row), disabled: row.is_preset, danger: true }]" /></template></el-table-column>
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
              <el-table-column label="操作" width="160" fixed="right"><template #default="{ row }"><ListActions :primary="{ label: '编辑', run: () => editAchievement(row), disabled: row.is_preset, danger: false }" :actions="[{ label: '删除', run: () => deleteAchievement(row), disabled: row.is_preset, danger: true }]" /></template></el-table-column>
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
              <el-table-column label="操作" width="160" fixed="right"><template #default="{ row }"><ListActions :primary="{ label: '编辑', run: () => editReward(row), disabled: false, danger: false }" :actions="[{ label: '删除', run: () => deleteReward(row), disabled: false, danger: true }]" /></template></el-table-column>
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

    <!-- 新增/编辑错误类型弹窗 -->
    <el-dialog v-model="showErrorTypeDialog" :title="editErrorTypeData ? '编辑错误类型' : '新增错误类型'" width="400px">
      <el-form :model="errorTypeForm" label-width="80px">
        <el-form-item label="类型名称" required>
          <el-input v-model="errorTypeForm.name" placeholder="请输入错误类型名称" />
        </el-form-item>
        <el-form-item label="学科">
          <el-select v-model="errorTypeForm.subject_id" placeholder="选择学科（空表示通用）" clearable style="width: 100%">
            <el-option v-for="s in subjects" :key="s.id" :label="s.name" :value="s.id" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="closeErrorTypeDialog">取消</el-button>
        <el-button type="primary" @click="saveErrorType">保存</el-button>
      </template>
    </el-dialog>

    <!-- 新增/编辑知识点弹窗 -->
    <el-dialog v-model="showKnowledgeDialog" :title="editKnowledgeData ? '编辑知识点' : '新增知识点'" width="560px">
      <el-form :model="knowledgeForm" label-width="100px">
        <el-form-item label="层级" required>
          <el-radio-group v-model="knowledgeForm.level" :disabled="!!editKnowledgeData">
            <el-radio :value="1">一级模块</el-radio>
            <el-radio :value="2">二级考点</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item v-if="knowledgeForm.level === 2" label="所属一级" required>
          <el-select v-model="knowledgeForm.parent_id" placeholder="选择一级模块" style="width: 100%" :disabled="!!editKnowledgeData" @change="onKnowledgeParentChange">
            <el-option v-for="module in moduleOptions" :key="module.id" :label="module.name" :value="module.id" />
          </el-select>
        </el-form-item>
        <el-form-item :label="knowledgeForm.level === 1 ? '模块名称' : '考点名称'" required>
          <el-input v-model="knowledgeForm.name" placeholder="请输入名称" />
        </el-form-item>
        <el-form-item label="学科" required>
          <el-select v-model="knowledgeForm.subject_id" placeholder="选择学科" style="width: 100%" :disabled="!!editKnowledgeData" @change="onKnowledgeSubjectChange">
            <el-option v-for="s in subjects" :key="s.id" :label="s.name" :value="s.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="编码">
          <el-input v-model="knowledgeForm.code" placeholder="留空自动生成，改名不变" />
        </el-form-item>
        <el-form-item label="排序">
          <el-input-number v-model="knowledgeForm.sort_order" :min="0" :max="9999" controls-position="right" />
        </el-form-item>
        <el-form-item label="年级">
          <el-select v-model="knowledgeForm.grade" placeholder="仅作推荐筛选" clearable style="width: 100%">
            <el-option v-for="g in gradeOptions" :key="g.value" :label="g.label" :value="g.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="学期">
          <el-select v-model="knowledgeForm.semester" placeholder="仅作推荐筛选" clearable style="width: 100%">
            <el-option label="上学期" :value="1" />
            <el-option label="下学期" :value="2" />
          </el-select>
        </el-form-item>
        <el-form-item v-if="knowledgeForm.level === 2" label="错误类型">
          <el-select v-model="knowledgeForm.error_type_ids" multiple placeholder="选择该考点的错误类型" style="width: 100%">
            <el-option v-for="et in knowledgeErrorTypeOptions" :key="et.id" :label="et.name" :value="et.id" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="closeKnowledgeDialog">取消</el-button>
        <el-button type="primary" :loading="knowledgeSaving" @click="saveKnowledgePoint">保存</el-button>
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
import PageHeading from '@/components/PageHeading.vue'
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { questionApi, uploadApi } from '@/api/question'
import { motivationApi } from '@/api/motivation'
import { useAppConfigStore } from '@/stores/appConfig'
import { refreshKnowledgeColors } from '@/composables/knowledgeColors'
import axios from '@/api/http'

const appConfigStore = useAppConfigStore()
const activeTab = ref('system')
const appConfigForm = reactive({
  defaultGrade: null,
  defaultSemester: null,
})
const savingAppConfig = ref(false)

const loadAppConfig = async () => {
  await appConfigStore.load(true)
  appConfigForm.defaultGrade = appConfigStore.defaultGrade
  appConfigForm.defaultSemester = appConfigStore.defaultSemester
}

const saveAppConfig = async () => {
  savingAppConfig.value = true
  try {
    await appConfigStore.save({
      defaultGrade: appConfigForm.defaultGrade,
      defaultSemester: appConfigForm.defaultSemester,
    })
    ElMessage.success('默认年级配置已保存')
  } catch (e) {
    ElMessage.error('保存失败')
  } finally {
    savingAppConfig.value = false
  }
}
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
const etFilters = reactive({ subject_id: null })
const showErrorTypeDialog = ref(false)
const editErrorTypeData = ref(null)
const errorTypeForm = reactive({
  name: '',
  subject_id: localStorage.getItem('lastEtSubject') ? parseInt(localStorage.getItem('lastEtSubject')) : null
})

// 知识点
const knowledgePoints = ref([])
const legacyKnowledgePoints = ref([])
const showLegacy = ref(false)
const knowledgeSaving = ref(false)
const kpFilters = reactive({
  subject_id: null,
  grade: appConfigStore.defaultGrade,
  semester: appConfigStore.defaultSemester,
  keyword: '',
})
const showKnowledgeDialog = ref(false)
const editKnowledgeData = ref(null)
const knowledgeForm = reactive({
  name: '',
  subject_id: localStorage.getItem('lastKpSubject') ? parseInt(localStorage.getItem('lastKpSubject')) : null,
  level: 2,
  parent_id: null,
  code: '',
  sort_order: 0,
  grade: localStorage.getItem('lastKpGrade') ? parseInt(localStorage.getItem('lastKpGrade')) : null,
  semester: localStorage.getItem('lastKpSemester') ? parseInt(localStorage.getItem('lastKpSemester')) : null,
  error_type_ids: [],
})
const moduleOptions = computed(() => (knowledgePoints.value || [])
  .filter(item => item.level === 1)
  .filter(item => !knowledgeForm.subject_id || item.subject_id === knowledgeForm.subject_id))
const knowledgeErrorTypeOptions = computed(() => (errorTypes.value || []).filter(
  item => item.subject_id == null || item.subject_id === knowledgeForm.subject_id,
))

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
    fetchKnowledgePoints()
  } catch (e) {
    if (e !== 'cancel') ElMessage.error(e.response?.data?.detail || '删除失败')
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
const fetchErrorTypes = async () => {
  try {
    const params = {}
    if (etFilters.subject_id) params.subject_id = etFilters.subject_id
    const { data } = await questionApi.listErrorTypes(params)
    errorTypes.value = Array.isArray(data) ? data : []
  } catch (e) {
    console.error('获取错误类型失败:', e)
  }
}

// 打开新增错误类型弹窗
const openErrorTypeDialog = () => {
  editErrorTypeData.value = null
  errorTypeForm.name = ''
  errorTypeForm.subject_id = localStorage.getItem('lastEtSubject') ? parseInt(localStorage.getItem('lastEtSubject')) : null
  showErrorTypeDialog.value = true
}

// 关闭错误类型弹窗
const closeErrorTypeDialog = () => {
  showErrorTypeDialog.value = false
  editErrorTypeData.value = null
  errorTypeForm.name = ''
  errorTypeForm.subject_id = localStorage.getItem('lastEtSubject') ? parseInt(localStorage.getItem('lastEtSubject')) : null
}

// 编辑错误类型
const editErrorType = (row) => {
  editErrorTypeData.value = row
  errorTypeForm.name = row.name
  errorTypeForm.subject_id = row.subject_id
  showErrorTypeDialog.value = true
}

// 保存错误类型（新增或编辑）
const saveErrorType = async () => {
  if (!errorTypeForm.name.trim()) {
    ElMessage.warning('请输入类型名称')
    return
  }
  try {
    if (editErrorTypeData.value) {
      await questionApi.updateErrorType(editErrorTypeData.value.id, {
        name: errorTypeForm.name,
        subject_id: errorTypeForm.subject_id,
      })
      ElMessage.success('更新成功')
    } else {
      await questionApi.createErrorType({
        name: errorTypeForm.name,
        subject_id: errorTypeForm.subject_id,
      })
      ElMessage.success('创建成功')
      localStorage.setItem('lastEtSubject', errorTypeForm.subject_id || '')
    }
    closeErrorTypeDialog()
    fetchErrorTypes()
  } catch (e) {
    ElMessage.error(editErrorTypeData.value ? '更新失败' : '创建失败')
  }
}

// 删除错误类型
const deleteErrorType = async (row) => {
  try {
    await ElMessageBox.confirm('确定要删除该错误类型吗？', '删除确认', { type: 'warning' })
    await questionApi.deleteErrorType(row.id)
    ElMessage.success('删除成功')
    fetchErrorTypes()
  } catch (e) {
    if (e !== 'cancel') ElMessage.error('删除失败')
  }
}

// 获取两级目录与待处理旧目录
const fetchKnowledgePoints = async () => {
  try {
    const params = {}
    if (kpFilters.subject_id) params.subject_id = kpFilters.subject_id
    if (kpFilters.grade) params.grade = kpFilters.grade
    if (kpFilters.semester) params.semester = kpFilters.semester
    if (kpFilters.keyword) params.keyword = kpFilters.keyword
    const [treeResponse, legacyResponse] = await Promise.all([
      questionApi.getKnowledgePointTree(params),
      questionApi.listKnowledgePoints({
        include_legacy: 1,
        ...(kpFilters.subject_id ? { subject_id: kpFilters.subject_id } : {}),
      }),
    ])
    knowledgePoints.value = treeResponse.data.items || []
    const flat = Array.isArray(legacyResponse.data) ? legacyResponse.data : (legacyResponse.data.items || [])
    legacyKnowledgePoints.value = flat.filter(item => item.legacy)
  } catch (e) {
    console.error('获取知识点失败:', e)
  }
}

const onKnowledgeSubjectChange = () => {
  knowledgeForm.parent_id = null
  knowledgeForm.error_type_ids = []
}

const onKnowledgeParentChange = (parentId) => {
  const module = knowledgePoints.value.find(item => item.id === parentId)
  if (module) knowledgeForm.subject_id = module.subject_id
}

// 打开新增弹窗；可传入一级模块作为父级
const openKnowledgeDialog = (level = 2, parent = null) => {
  editKnowledgeData.value = null
  knowledgeForm.name = ''
  knowledgeForm.level = level
  knowledgeForm.parent_id = parent?.id ?? null
  knowledgeForm.subject_id = parent?.subject_id
    ?? (localStorage.getItem('lastKpSubject') ? parseInt(localStorage.getItem('lastKpSubject')) : kpFilters.subject_id)
  knowledgeForm.code = ''
  knowledgeForm.sort_order = 0
  knowledgeForm.grade = localStorage.getItem('lastKpGrade')
    ? parseInt(localStorage.getItem('lastKpGrade'))
    : appConfigStore.defaultGrade
  knowledgeForm.semester = localStorage.getItem('lastKpSemester')
    ? parseInt(localStorage.getItem('lastKpSemester'))
    : appConfigStore.defaultSemester
  knowledgeForm.error_type_ids = []
  showKnowledgeDialog.value = true
}

const closeKnowledgeDialog = () => {
  showKnowledgeDialog.value = false
  editKnowledgeData.value = null
}

const editKnowledgePoint = (row) => {
  editKnowledgeData.value = row
  knowledgeForm.name = row.name
  knowledgeForm.subject_id = row.subject_id
  knowledgeForm.level = row.level || 2
  knowledgeForm.parent_id = row.parent_id || null
  knowledgeForm.code = row.code || ''
  knowledgeForm.sort_order = row.sort_order || 0
  knowledgeForm.grade = row.grade
  knowledgeForm.semester = row.semester
  knowledgeForm.error_type_ids = (row.error_types || []).map(item => item.id)
  showKnowledgeDialog.value = true
}

// 把待处理旧目录提升为二级考点，由用户明确选择父级
const promoteLegacy = (row) => {
  openKnowledgeDialog(2)
  knowledgeForm.name = row.name
  knowledgeForm.subject_id = row.subject_id
  knowledgeForm.grade = row.grade
  knowledgeForm.semester = row.semester
}

const saveKnowledgePoint = async () => {
  if (!knowledgeForm.name.trim()) {
    ElMessage.warning('请输入知识点名称')
    return
  }
  if (!knowledgeForm.subject_id) {
    ElMessage.warning('请选择学科')
    return
  }
  if (knowledgeForm.level === 2 && !knowledgeForm.parent_id) {
    ElMessage.warning('请选择所属一级模块')
    return
  }
  knowledgeSaving.value = true
  try {
    const payload = {
      name: knowledgeForm.name.trim(),
      subject_id: knowledgeForm.subject_id,
      level: knowledgeForm.level,
      parent_id: knowledgeForm.level === 2 ? knowledgeForm.parent_id : null,
      sort_order: knowledgeForm.sort_order || 0,
      grade: knowledgeForm.grade,
      semester: knowledgeForm.semester,
      error_type_ids: knowledgeForm.level === 2 ? knowledgeForm.error_type_ids : [],
    }
    if (knowledgeForm.code.trim()) payload.code = knowledgeForm.code.trim()
    if (editKnowledgeData.value) {
      await questionApi.updateKnowledgePoint(editKnowledgeData.value.id, payload)
      ElMessage.success('更新成功')
    } else {
      await questionApi.createKnowledgePoint(payload)
      ElMessage.success('创建成功')
      localStorage.setItem('lastKpSubject', knowledgeForm.subject_id)
      localStorage.setItem('lastKpGrade', knowledgeForm.grade || '')
      localStorage.setItem('lastKpSemester', knowledgeForm.semester || '')
    }
    closeKnowledgeDialog()
    await refreshKnowledgeColors()
    fetchKnowledgePoints()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || (editKnowledgeData.value ? '更新失败' : '创建失败'))
  } finally {
    knowledgeSaving.value = false
  }
}

// 删除知识点；有子级或题目引用时后端返回 409 和数量
const deleteKnowledgePoint = async (row) => {
  try {
    await ElMessageBox.confirm(
      '确定要删除“' + row.name + '”吗？有子级或题目引用时会被拒绝。',
      '删除确认',
      { type: 'warning' },
    )
    await questionApi.deleteKnowledgePoint(row.id)
    ElMessage.success('删除成功')
    await refreshKnowledgeColors()
    fetchKnowledgePoints()
  } catch (e) {
    if (e !== 'cancel') ElMessage.error(e.response?.data?.detail || '删除失败')
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

const fetchAll = async () => {
  await loadAppConfig()
  // 知识点筛选套用默认年级/学期
  if (kpFilters.grade == null) kpFilters.grade = appConfigStore.defaultGrade
  if (kpFilters.semester == null) kpFilters.semester = appConfigStore.defaultSemester
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
.management  {

  max-width: 1200px;
  margin: 0 auto;
}

.card-header  {

  display: flex;
  justify-content: space-between;
  align-items: center;
}

.tab-content  {

  padding: 10px 0;
}

.system-config .form-tip  {

  font-size: 12px;
  color: var(--text-muted);
  line-height: 1.5;
  margin-top: 4px;
}

.action-bar  {

  margin-bottom: 10px;
}

.filters  {

  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  margin-bottom: 15px;
}

.text-success  {

  color: #67c23a;
  font-weight: bold;
}

.text-danger  {

  color: #f56c6c;
  font-weight: bold;
}

.stars-adjust-section  {

  background: #f5f7fa;
  border-radius: 8px;
  padding: 16px;
  margin-bottom: 20px;
}

.stars-adjust-section h4  {

  margin: 0 0 12px 0;
  color: var(--text-primary);
}

.adjust-result  {

  margin-top: 12px;
  color: var(--text-secondary);
}

.balance-value  {

  font-size: 18px;
  font-weight: bold;
  color: var(--accent-blue);
}

/* 禁用卡片的hover效果 */
.management :deep(.el-card)  {

  transition: none;
}
.management :deep(.el-card:hover)  {

  transform: none;
  box-shadow: var(--shadow-sm) !important;
}
.management {
  max-width:none}
.tab-content {
  padding:8px 0}
.stars-adjust-section {
  background:#f6f7fb;
  border:1px solid var(--border-light)}
.balance-value {
  color:var(--accent-blue)}
.kp-tip {
  margin-bottom:12px}
.kp-errors {
  display:flex;
  flex-wrap:wrap;
  gap:4px}
.legacy-panel {
  margin-top:20px;
  padding-top:14px;
  border-top:1px dashed var(--border-light)}
.legacy-panel h4 {
  margin:0 0 10px;
  color:var(--text-secondary)}
</style>
