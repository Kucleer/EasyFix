<template>
  <div class="questions">
    <PageHeading title="我的错题本" description="留下问题，也留下解决问题的过程。" />
    <el-card>
      <template #header>
        <div class="card-header">
          <span>错题列表<small v-if="is_mobile" class="q-mobile-total">共 {{ questions.total }} 题</small></span>
          <!-- 手机：只留一个主按钮「录入」，其余收进「⋯」 -->
          <div v-if="is_mobile" class="header-actions q-mobile-header-actions">
            <el-button type="primary" @click="$router.push('/upload')">录入</el-button>
            <el-dropdown trigger="click">
              <el-button aria-label="更多操作">⋯</el-button>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item @click="goTargetedPaper">出练习卷</el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
          </div>
          <div v-else class="header-actions">
            <el-button type="success" size="large" @click="goTargetedPaper">
              <el-icon><Plus /></el-icon>
              出练习卷
            </el-button>
            <el-button type="primary" size="large" @click="$router.push('/upload')">
              <el-icon><Plus /></el-icon>
              新增错题
            </el-button>
          </div>
        </div>
      </template>

      <!-- 手机：只露搜索框 + 「筛选」按钮，其余筛选项放进底部抽屉 -->
      <div v-if="is_mobile" class="q-mobile-search">
        <el-input v-model="filters.keyword" placeholder="搜题目文字" clearable @change="fetchQuestions" />
        <el-button class="q-mobile-filter-btn" @click="filter_drawer_visible = true">
          筛选<span v-if="active_filter_count" class="q-mobile-filter-count">{{ active_filter_count }}</span>
        </el-button>
      </div>

      <!-- 筛选条件（电脑） -->
      <div v-if="!is_mobile" class="filters">
        <el-select v-model="filters.subject_id" placeholder="选择学科" clearable @change="fetchQuestions" style="width: 195px">
          <el-option v-for="s in subjects" :key="s.id" :label="s.name" :value="s.id" />
        </el-select>
        <el-select v-model="filters.difficulty" placeholder="难度" multiple clearable @change="fetchQuestions" style="width: 150px">
          <el-option v-for="i in 5" :key="i" :label="'★'.repeat(i)" :value="i" />
        </el-select>
        <el-select v-model="filters.tag_ids" placeholder="标签" multiple clearable @change="fetchQuestions" style="width: 300px">
          <el-option v-for="t in allTags" :key="t.id" :label="t.name" :value="t.id" />
        </el-select>
        <el-select v-model="filters.knowledge_parent_id" placeholder="知识模块（一级）" clearable filterable @change="onModuleChange" style="width: 180px">
          <el-option v-for="module in filterOptions.knowledge_modules" :key="module.id" :label="module.name" :value="module.id" />
        </el-select>
        <el-select v-model="filters.knowledge_point_id" placeholder="二级知识点" clearable filterable :disabled="!filters.knowledge_parent_id" @change="fetchQuestions" style="width: 180px">
          <el-option v-for="point in filterPointOptions" :key="point.id" :label="point.name" :value="point.id" />
        </el-select>
        <el-checkbox v-model="filters.unclassified" border @change="onUnclassifiedChange">只看未分类</el-checkbox>
        <el-select v-model="filters.grade" placeholder="年级" clearable @change="fetchQuestions" style="width: 150px">
          <el-option v-for="g in gradeOptions" :key="g.value" :label="g.label" :value="g.value" />
        </el-select>
        <el-select v-model="filters.semester" placeholder="学期" clearable @change="fetchQuestions" style="width: 135px">
          <el-option label="上学期" :value="1" />
          <el-option label="下学期" :value="2" />
        </el-select>
        <el-select v-model="filters.accuracy_range" placeholder="正确率筛选" clearable @change="fetchQuestions" style="width: 150px">
          <el-option v-for="opt in ACCURACY_RANGE_OPTIONS" :key="opt.value" :label="opt.label" :value="opt.value" />
        </el-select>
        <el-input
          v-model="filters.keyword"
          placeholder="搜索关键词"
          clearable
          @change="fetchQuestions"
          style="width: 225px"
        />
      </div>

      <!-- 已选筛选条件展示 -->
      <!-- 手机上同一块就是搜索框下面那排可点 × 去掉的小标签 -->
      <div v-if="hasActiveFilters" class="selected-filters" :class="{ 'q-mobile-chips': is_mobile }">
        <span class="filter-label">已选条件：</span>
        <el-tag v-if="filters.difficulty?.length" v-for="d in filters.difficulty" :key="d" size="small" closable @close="removeFilter('difficulty', d)" :class="'difficulty-filter-' + d">
          {{ getDifficultyStars(d) }}
        </el-tag>
        <el-tag v-if="filters.tag_ids?.length" v-for="tagId in filters.tag_ids" :key="tagId" size="small" closable @close="removeFilter('tag_ids', tagId)" :style="getTagStyle(tagId)">
          {{ getTagName(tagId) }}
        </el-tag>
        <KnowledgeTag v-if="filters.knowledge_parent_id" :point="selectedFilterModule" :subject-id="filters.subject_id" closable @close="removeFilter('knowledge_parent_id')" />
        <KnowledgeTag v-if="filters.knowledge_point_id" :point="selectedFilterPoint" :subject-id="filters.subject_id" show-path closable @close="removeFilter('knowledge_point_id')" />
        <el-tag v-if="filters.unclassified" size="small" type="info" closable @close="removeFilter('unclassified')">未分类</el-tag>
        <el-tag v-if="filters.subject_id" size="small" closable @close="removeFilter('subject_id')">
          {{ subjects.find(s => s.id === filters.subject_id)?.name }}
        </el-tag>
        <el-tag v-if="filters.grade" size="small" closable @close="removeFilter('grade')">
          {{ getGradeLabel(filters.grade) }}
        </el-tag>
        <el-tag v-if="filters.semester" size="small" closable @close="removeFilter('semester')">
          {{ filters.semester === 1 ? '上学期' : '下学期' }}
        </el-tag>
        <el-tag v-if="filters.accuracy_range" size="small" closable @close="removeFilter('accuracy_range')">
          {{ get_accuracy_range_label(filters.accuracy_range) }}
        </el-tag>
        <el-button link type="primary" size="small" @click="clearAllFilters">清空</el-button>
      </div>

      <!-- 错题列表 -->
      <!-- 手机：卡片列表（表格在窄屏上题目、知识点、正确率都被挤掉了） -->
      <template v-if="is_mobile">
        <div v-if="questions.items.length" class="q-mobile-list">
          <div
            v-for="row in questions.items"
            :key="row.id"
            class="q-mobile-card"
            :class="{ 'is-pending': row.review_status === 'pending', 'is-selected': is_question_selected(row) }"
          >
            <!-- 第一层：勾选 + 原图 + 题目文字（最多 3 行） -->
            <div class="q-mobile-top">
              <el-checkbox
                :model-value="is_question_selected(row)"
                :disabled="!isRowSelectable(row)"
                aria-label="选择这道错题"
                @change="toggle_question_select(row)"
              />
              <el-image
                v-if="row.original_image || row.original_images?.length"
                class="q-mobile-thumb"
                :src="'/uploads/' + (row.original_image || row.original_images[0])"
                fit="cover"
                @click="previewImage('/uploads/' + (row.original_image || row.original_images[0]))"
              />
              <div class="q-mobile-text" @click="viewDetail(row)">
                <el-tag v-if="row.review_status === 'pending'" type="warning" size="small" class="q-mobile-pending">待核对</el-tag>
                <MathText :text="row.parsed_question || row.original_text || '无文本'" />
              </div>
            </div>
            <!-- 第二层：学科、知识点（最多 2 个）、标签、日期靠右 -->
            <div class="q-mobile-tags">
              <span class="q-mobile-chip">{{ subjects.find(subject => subject.id === row.subject_id)?.name || '未指定学科' }}</span>
              <template v-if="row.knowledge_points?.length">
                <KnowledgeTag v-for="point in visibleKnowledgePoints(row).slice(0, 2)" :key="point.id" :point="point" :primary="point.is_primary" :subject-id="row.subject_id" />
                <span v-if="row.knowledge_points.length > 2" class="q-mobile-chip">+{{ row.knowledge_points.length - 2 }}</span>
              </template>
              <span v-else class="q-mobile-chip is-muted">未分类</span>
              <span v-for="tag in row.tags || []" :key="tag.id" class="q-mobile-chip">{{ tag.name }}</span>
              <em class="q-mobile-date">{{ format_short_date(row.created_at) }}</em>
            </div>
            <!-- 第三层：难度、正确率 + 操作 -->
            <div class="q-mobile-foot">
              <div class="q-mobile-meta">
                <span class="q-mobile-stars">{{ '★'.repeat(row.difficulty || 0) }}</span>
                <span v-if="getAccuracyValue(row) < 0">未练习</span>
                <span v-else>
                  正确率 <b>{{ getAccuracyDisplay(row) }}</b>
                  <i class="q-mobile-acc-bar" :class="{ 'is-low': getAccuracyValue(row) < 0.6 }"><i :style="{ width: getAccuracyDisplay(row) }" /></i>
                </span>
              </div>
              <ListActions :primary="question_primary_action(row)" :actions="question_more_actions(row)" />
            </div>
          </div>
        </div>
        <el-empty v-else description="暂无错题" />
      </template>

      <el-table v-else class="question-table" v-model:selection="selectedQuestions" :data="questions.items" stripe style="width: 100%; margin-top: 20px" @selection-change="handleSelectionChange">
        <el-table-column type="selection" width="42" :selectable="isRowSelectable" />

        <el-table-column label="题目" min-width="620">
          <template #default="{ row }">
            <div class="question-cell">
              <el-image
                v-if="row.original_image || row.original_images?.length"
                :src="'/uploads/' + (row.original_image || row.original_images[0])"
                fit="contain"
                style="width: 50px; height: 50px; margin-right: 8px; cursor: pointer"
                @click="previewImage('/uploads/' + (row.original_image || row.original_images[0]))"
              />
              <el-tag v-if="row.review_status === 'pending'" type="warning" size="small" style="margin-right: 6px; flex-shrink: 0">待核对</el-tag>
              <div class="text-preview"><MathText :text="row.parsed_question || row.original_text || '无文本'" /></div>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="分类与记录" width="260">
          <template #default="{ row }">
            <div class="question-meta">
              <span>{{ subjects.find(subject => subject.id === row.subject_id)?.name || '未指定学科' }}</span>
              <div v-if="row.knowledge_points?.length" class="question-kp">
                <KnowledgeTag v-for="point in visibleKnowledgePoints(row)" :key="point.id" :point="point" :primary="point.is_primary" :subject-id="row.subject_id" show-path />
                <el-tag v-if="row.knowledge_points.length > 3" size="small" type="info">+{{ row.knowledge_points.length - 3 }}</el-tag>
              </div>
              <span v-else-if="row.legacy_knowledge_point" class="legacy-knowledge">原标签：{{ row.legacy_knowledge_point }}</span>
              <span v-else class="text-muted">未分类</span>
              <div class="question-tags"><el-tag v-for="tag in row.tags || []" :key="tag.id" size="small">{{ tag.name }}</el-tag></div>
              <small>#{{ row.id }} · {{ formatDate(row.created_at) }}</small>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="复习情况" width="125" sortable :sort-method="(a, b) => getAccuracyValue(a) - getAccuracyValue(b)">
          <template #default="{ row }"><div class="question-meta"><span class="difficulty-stars" :class="'difficulty-' + row.difficulty">{{ getDifficultyStars(row.difficulty) }}</span><span>正确率 {{ getAccuracyDisplay(row) }}</span><small>答对 {{ row.correct_count || 0 }} / {{ (row.correct_count || 0) + (row.error_count || 0) }} 次</small></div></template>
        </el-table-column>
        <el-table-column label="操作" width="160" fixed="right"><template #default="{ row }"><ListActions :primary="question_primary_action(row)" :actions="question_more_actions(row)" /></template></el-table-column>
      </el-table>

      <!-- 分页 -->
      <div class="pagination">
        <el-pagination
          v-model:current-page="pagination.page"
          v-model:page-size="pagination.limit"
          :page-sizes="[10, 20, 50, 100]"
          :total="questions.total"
          :layout="is_mobile ? 'prev, pager, next' : 'total, sizes, prev, pager, next'"
          :small="is_mobile"
          @change="fetchQuestions"
        />
      </div>

      <!-- 批量操作栏：勾选后才出现；手机上浮在底部导航上方 -->
      <div v-if="selectedQuestions.length > 0" class="batch-actions" :class="{ 'is-floating': is_mobile }">
        <div class="batch-info">
          <span>已选择 <strong>{{ selectedQuestions.length }}</strong> {{ is_mobile ? '题' : '道错题' }}</span>
        </div>
        <div class="batch-buttons">
          <el-button type="primary" @click="showPrintDialog('original')">打印原题</el-button>
          <el-button type="success" @click="showPrintDialog('similar')">打印相似题</el-button>
          <el-button type="warning" @click="batchGenerateSimilar">{{ is_mobile ? '生成相似题' : '批量生成相似题' }}</el-button>
          <el-button @click="clearSelection">{{ is_mobile ? '取消' : '取消选择' }}</el-button>
        </div>
      </div>
    </el-card>

    <!-- 手机筛选抽屉：和电脑共用同一份 filters，改动先不查询，点「确定」才查 -->
    <el-drawer
      v-model="filter_drawer_visible"
      direction="btt"
      size="auto"
      title="筛选"
      class="q-filter-drawer"
    >
      <div class="q-drawer-body">
        <div class="q-drawer-label">学科 / 难度</div>
        <div class="q-drawer-grid">
          <el-select v-model="filters.subject_id" placeholder="学科" clearable>
            <el-option v-for="s in subjects" :key="s.id" :label="s.name" :value="s.id" />
          </el-select>
          <el-select v-model="filters.difficulty" placeholder="难度" multiple collapse-tags clearable>
            <el-option v-for="i in 5" :key="i" :label="'★'.repeat(i)" :value="i" />
          </el-select>
        </div>
        <div class="q-drawer-label">知识点</div>
        <div class="q-drawer-grid">
          <el-select v-model="filters.knowledge_parent_id" placeholder="一级模块" clearable filterable :disabled="!filters.subject_id" @change="filters.knowledge_point_id = null">
            <el-option v-for="module in filterOptions.knowledge_modules" :key="module.id" :label="module.name" :value="module.id" />
          </el-select>
          <el-select v-model="filters.knowledge_point_id" placeholder="二级知识点" clearable filterable :disabled="!filters.knowledge_parent_id">
            <el-option v-for="point in filterPointOptions" :key="point.id" :label="point.name" :value="point.id" />
          </el-select>
        </div>
        <el-checkbox v-model="filters.unclassified" class="q-drawer-check" @change="clear_knowledge_if_unclassified">只看未分类</el-checkbox>
        <div class="q-drawer-label">年级 / 学期 / 正确率</div>
        <div class="q-drawer-grid is-three">
          <el-select v-model="filters.grade" placeholder="年级" clearable>
            <el-option v-for="g in gradeOptions" :key="g.value" :label="g.label" :value="g.value" />
          </el-select>
          <el-select v-model="filters.semester" placeholder="学期" clearable>
            <el-option label="上学期" :value="1" />
            <el-option label="下学期" :value="2" />
          </el-select>
          <el-select v-model="filters.accuracy_range" placeholder="正确率" clearable>
            <el-option v-for="opt in ACCURACY_RANGE_OPTIONS" :key="opt.value" :label="opt.label" :value="opt.value" />
          </el-select>
        </div>
        <div class="q-drawer-label">标签</div>
        <el-select v-model="filters.tag_ids" placeholder="标签" multiple collapse-tags clearable style="width: 100%">
          <el-option v-for="t in allTags" :key="t.id" :label="t.name" :value="t.id" />
        </el-select>
      </div>
      <template #footer>
        <div class="q-drawer-footer">
          <el-button @click="reset_filter_fields">重置</el-button>
          <el-button type="primary" @click="apply_drawer_filters">确定</el-button>
        </div>
      </template>
    </el-drawer>

    <!-- 详情弹窗 -->
    <el-dialog v-model="detailVisible" title="错题详情" width="900px">
      <div v-if="currentQuestion" class="question-detail">
        <!-- 原图展示区 -->
        <div v-if="getImageList(currentQuestion).length" class="detail-images">
          <div class="detail-card">
            <div class="card-header-blue">原图</div>
            <div class="card-content">
              <div class="image-gallery">
                <el-image
                  v-for="(img, idx) in getImageList(currentQuestion)"
                  :key="idx"
                  :src="'/uploads/' + img"
                  fit="contain"
                  class="gallery-image"
                  style="cursor: pointer"
                  @click="previewImage('/uploads/' + img)"
                />
              </div>
            </div>
          </div>
        </div>

        <!-- 题目和答案并排 -->
        <div class="detail-row">
          <!-- 题目卡片 -->
          <div class="detail-card flex-1">
            <div class="card-header-blue">题目</div>
            <div class="card-content">
              <div class="question-text"><MathText :text="currentQuestion.parsed_question || currentQuestion.original_text || '暂无'" /></div>
            </div>
          </div>
          <!-- 答案卡片 -->
          <div class="detail-card flex-1">
            <div class="card-header-green">答案</div>
            <div class="card-content">
              <div class="question-text"><MathText :text="currentQuestion.answer || '暂无'" /></div>
            </div>
          </div>
        </div>

        <!-- 卷子、题号、学生的答案和判错依据 -->
        <div class="detail-card">
          <div class="card-header-gray">卷子与作答</div>
          <div class="card-content">
            <div class="meta-row">
              <div class="meta-item">
                <label>所属卷子：</label>
                <router-link v-if="currentQuestion.paper" :to="'/papers/' + currentQuestion.paper.id">{{ currentQuestion.paper.name }}</router-link>
                <span v-else>无</span>
              </div>
              <div class="meta-item">
                <label>题号：</label>
                <span>{{ currentQuestion.question_no || '未填' }}</span>
              </div>
            </div>
            <div class="meta-item">
              <label>学生的答案：</label>
              <div class="question-text"><MathText :text="currentQuestion.wrong_answer || '暂无'" /></div>
            </div>
            <div class="meta-item">
              <label>判错依据：</label>
              <span>{{ currentQuestion.wrong_evidence || '暂无' }}</span>
            </div>
          </div>
        </div>

        <!-- 解析卡片 -->
        <div class="detail-card">
          <div class="card-header-orange">解析</div>
          <div class="card-content">
            <div v-if="currentQuestion.analysis" class="question-text"><MathText :text="currentQuestion.analysis" /></div>
            <div v-if="currentQuestion.analysis_image" class="analysis-image">
              <el-image
                :src="'/uploads/' + currentQuestion.analysis_image"
                fit="contain"
                class="analysis-img"
                style="cursor: pointer"
                @click="previewImage('/uploads/' + currentQuestion.analysis_image)"
              />
            </div>
            <span v-if="!currentQuestion.analysis && !currentQuestion.analysis_image" class="text-muted">暂无</span>
          </div>
        </div>

        <!-- 元数据卡片 -->
        <div class="detail-card">
          <div class="card-header-gray">信息</div>
          <div class="card-content">
            <div class="meta-row">
              <div class="meta-item">
                <label>难度：</label>
                <span class="difficulty-stars-yellow">{{ getYellowStars(currentQuestion.difficulty) }}</span>
              </div>
              <div class="meta-item">
                <label>年级/学期：</label>
                <span>{{ getGradeLabel(currentQuestion.grade) }} / {{ currentQuestion.semester ? (currentQuestion.semester === 1 ? '上学期' : '下学期') : '未设置' }}</span>
              </div>
            </div>
            <div class="meta-row">
              <div class="meta-item knowledge-meta-item">
                <label>知识点：</label>
                <div v-if="currentQuestion.knowledge_points?.length" class="detail-knowledge">
                  <KnowledgeTag v-for="point in currentQuestion.knowledge_points" :key="point.id" :point="point" :primary="point.is_primary" :subject-id="currentQuestion.subject_id" show-path />
                </div>
                <span v-else-if="currentQuestion.legacy_knowledge_point" class="legacy-knowledge">原标签（未迁移）：{{ currentQuestion.legacy_knowledge_point }}</span>
                <span v-else class="text-muted">未分类</span>
              </div>
            </div>
          </div>
        </div>

        <!-- 标签区域 -->
        <div class="tags-area">
          <label class="tags-label">标签：</label>
          <el-tag
            v-for="tag in currentQuestion.tags"
            :key="tag.id"
            size="small"
            :style="{ marginRight: '8px', backgroundColor: tag.color || '#409eff', borderColor: tag.color || '#409eff', color: tag.color ? getContrastColor(tag.color) : '#ffffff' }"
          >{{ tag.name }}</el-tag>
          <span v-if="!currentQuestion.tags?.length" class="text-muted">暂无</span>
        </div>

        <!-- 练习历史卡片 -->
        <div v-if="practiceHistory.length" class="detail-card">
          <div class="card-header-purple">练习历史</div>
          <div class="card-content">
            <div v-for="(record, idx) in practiceHistory" :key="idx" class="history-item">
              <span class="history-date">{{ record.date }}</span>
              <span class="history-name">{{ record.practice_set_name }}</span>
              <el-tag :type="record.is_correct ? 'success' : 'danger'" size="small">
                {{ record.is_correct ? '✓ 正确' : '✗ 错误' }}
              </el-tag>
            </div>
            <div v-if="practiceHistory.length === 0" class="text-muted">暂无练习记录</div>
          </div>
        </div>

        <!-- 相似题卡片 -->
        <div v-if="currentQuestion.similar_questions?.length" class="detail-card">
          <div class="card-header-purple">相似题</div>
          <div class="card-content">
            <div v-for="sq in currentQuestion.similar_questions" :key="sq.id" class="similar-item">
              <p><strong>题目：</strong><MathText :text="sq.similar_text" /></p>
              <p><strong>答案：</strong><MathText :text="sq.similar_answer" /></p>
            </div>
          </div>
        </div>
      </div>
    </el-dialog>

    <!-- 编辑弹窗 -->
    <el-dialog v-model="editVisible" title="编辑错题" width="700px">
      <el-form :model="editForm" label-width="100px" style="max-width: 600px">
        <el-form-item label="学科" required>
          <el-select v-model="editForm.subject_id" placeholder="选择学科" style="width: 100%">
            <el-option v-for="s in subjects" :key="s.id" :label="s.name" :value="s.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="原图">
          <div v-if="editForm.original_image" class="original-image-preview">
            <el-image
              :src="'/uploads/' + editForm.original_image"
              fit="contain"
              style="width: 100px; height: 100px; margin-right: 10px; cursor: pointer"
              @click="previewImage('/uploads/' + editForm.original_image)"
            />
            <el-button size="small" @click="editForm.original_image = ''">移除</el-button>
          </div>
          <el-upload
            v-if="!editForm.original_image"
            :show-file-list="false"
            accept="image/*"
            :http-request="handleOriginalImageUpload"
          >
            <el-button size="small" type="primary">上传图片</el-button>
          </el-upload>
        </el-form-item>
        <el-form-item label="题目">
          <MathEditor v-model="editForm.parsed_question" :rows="6" />
        </el-form-item>
        <el-form-item label="题号">
          <el-input v-model="editForm.question_no" placeholder="如 二、5" />
        </el-form-item>
        <el-form-item label="学生的答案">
          <MathEditor v-model="editForm.wrong_answer" :rows="3" />
        </el-form-item>
        <el-form-item label="答案">
          <MathEditor v-model="editForm.answer" :rows="4" />
        </el-form-item>
        <el-form-item label="解析">
          <MathEditor v-model="editForm.analysis" :rows="4" />
        </el-form-item>
        <el-form-item label="解析图片">
          <div v-if="editForm.analysis_image" class="analysis-image-preview">
            <el-image
              :src="'/uploads/' + editForm.analysis_image"
              fit="contain"
              style="width: 100px; height: 100px; margin-right: 10px; cursor: pointer"
              @click="previewImage('/uploads/' + editForm.analysis_image)"
            />
            <el-button size="small" @click="editForm.analysis_image = ''">移除</el-button>
          </div>
          <el-upload
            v-if="!editForm.analysis_image"
            :show-file-list="false"
            accept="image/*"
            :http-request="handleAnalysisImageUpload"
          >
            <el-button size="small" type="primary">上传图片</el-button>
          </el-upload>
        </el-form-item>
        <el-form-item label="难度">
          <el-rate v-model="editForm.difficulty" :max="5" />
        </el-form-item>
        <el-form-item label="年级">
          <el-select v-model="editForm.grade" placeholder="选择年级" clearable>
            <el-option v-for="g in gradeOptions" :key="g.value" :label="g.label" :value="g.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="学期">
          <el-select v-model="editForm.semester" placeholder="选择学期" clearable>
            <el-option label="上学期" :value="1" />
            <el-option label="下学期" :value="2" />
          </el-select>
        </el-form-item>
        <el-form-item label="知识点">
          <KnowledgePointPicker
            v-model="editForm.knowledge_point_ids"
            v-model:primary-id="editForm.primary_knowledge_point_id"
            :subject-id="editForm.subject_id"
          />
        </el-form-item>
        <el-form-item label="标签">
          <el-select v-model="editForm.tag_ids" multiple placeholder="选择标签" style="width: 100%">
            <el-option v-for="tag in allTags" :key="tag.id" :label="tag.name" :value="tag.id" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editVisible = false">取消</el-button>
        <el-button type="primary" :loading="editLoading" @click="saveEdit">保存</el-button>
      </template>
    </el-dialog>

    <!-- 打印设置弹窗 -->
    <el-dialog v-model="printDialogVisible" title="创建练习集" width="500px">
      <el-form :model="printForm" label-width="100px">
        <el-form-item label="练习集名称">
          <el-input v-model="printForm.name" placeholder="请输入练习集名称" />
        </el-form-item>
        <el-form-item label="题目类型">
          <el-tag :type="printForm.questionType === 'original' ? 'primary' : 'success'">
            {{ printForm.questionType === 'original' ? '原题' : '相似题' }}
          </el-tag>
        </el-form-item>
        <el-form-item label="选择题目">
          <span>已选择 <strong>{{ selectedQuestions.length }}</strong> 道错题</span>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="printDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="printLoading" @click="createPracticeSet">创建并生成PDF</el-button>
      </template>
    </el-dialog>

    <!-- 图片预览弹层 -->
    <el-image-viewer
      v-if="imagePreviewVisible"
      :url-list="[imagePreviewUrl]"
      @close="imagePreviewVisible = false"
    />
  </div>
</template>

<script setup>
import PageHeading from '@/components/PageHeading.vue'
import MathText from '@/components/MathText.vue'
import MathEditor from '@/components/MathEditor.vue'
import KnowledgePointPicker from '@/components/KnowledgePointPicker.vue'
import { ref, reactive, computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { questionApi, uploadApi } from '@/api/question'
import { useAppConfigStore } from '@/stores/appConfig'
import axios from '@/api/http'
import { use_is_mobile } from '@/composables/useIsMobile'

const route = useRoute()
const router = useRouter()
const appConfigStore = useAppConfigStore()

// 年级选项：一年级到六年级，初一/初二/初三，高一/高二/高三
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

// 正确率筛选选项：电脑筛选栏、手机抽屉、已选条件标签共用
const ACCURACY_RANGE_OPTIONS = [
  { label: '0-30% 薄弱', value: '0-30' },
  { label: '30-60% 一般', value: '30-60' },
  { label: '60-80% 良好', value: '60-80' },
  { label: '80-100% 掌握', value: '80-100' },
  { label: '无统计', value: 'none' },
]

// 是否手机宽度：手机用卡片列表 + 筛选抽屉，电脑用表格 + 筛选栏
const is_mobile = use_is_mobile()
// 手机筛选抽屉是否打开
const filter_drawer_visible = ref(false)

const questions = ref({ total: 0, items: [] })
const subjects = ref([])
const allTags = ref([])


const filters = reactive({
  subject_id: null,
  difficulty: null,
  tag_ids: null,
  knowledge_parent_id: null,
  knowledge_point_id: null,
  unclassified: false,
  keyword: '',
  grade: null,
  semester: null,
  accuracy_range: null,
})

// 动态筛选选项
const filterOptions = reactive({
  knowledge_modules: [],
  knowledge_point_options: [],
})

const selectedFilterModule = computed(() => filterOptions.knowledge_modules.find(module => module.id === filters.knowledge_parent_id) || null)
const selectedFilterPoint = computed(() => filterOptions.knowledge_point_options.find(point => point.id === filters.knowledge_point_id) || null)
const filterPointOptions = computed(() => {
  const module = selectedFilterModule.value
  return module ? (module.children || []) : []
})

// 获取筛选选项（按学科）
const fetchFilterOptions = async (subjectId) => {
  if (!subjectId) {
    filterOptions.knowledge_modules = []
    filterOptions.knowledge_point_options = []
    return
  }
  try {
    const { data } = await questionApi.getFilterOptions(subjectId)
    filterOptions.knowledge_modules = data.knowledge_modules || []
    filterOptions.knowledge_point_options = data.knowledge_point_options || []
  } catch (error) {
    console.error('获取筛选选项失败:', error)
  }
}

const onModuleChange = () => {
  filters.knowledge_point_id = null
  fetchQuestions()
}

const onUnclassifiedChange = () => {
  if (filters.unclassified) {
    filters.knowledge_parent_id = null
    filters.knowledge_point_id = null
  }
  fetchQuestions()
}

// 监听学科变化，获取对应的知识点选项
watch(() => filters.subject_id, (newVal, oldVal) => {
  if (newVal !== oldVal) {
    filters.knowledge_parent_id = null
    filters.knowledge_point_id = null
    filters.unclassified = false
    fetchFilterOptions(newVal)
  }
})
const pagination = reactive({
  page: 1,
  limit: 20,
})
const detailVisible = ref(false)
const editVisible = ref(false)
const currentQuestion = ref(null)
const practiceHistory = ref([])
const imagePreviewVisible = ref(false)
const imagePreviewUrl = ref('')
const editLoading = ref(false)

// 多选相关
const selectedQuestions = ref([])
const printDialogVisible = ref(false)
const printLoading = ref(false)
const printForm = reactive({
  name: '',
  questionType: 'original',
})

// 出练习卷：跳到考点卷页，当前筛了学科就带上
const goTargetedPaper = () => {
  const query = filters.subject_id ? { subject_id: filters.subject_id } : {}
  router.push({ path: '/targeted-paper', query })
}

const editForm = reactive({
  subject_id: null,
  original_image: '',
  parsed_question: '',
  question_no: '',
  wrong_answer: '',
  answer: '',
  analysis: '',
  analysis_image: '',
  difficulty: 3,
  knowledge_point_ids: [],
  primary_knowledge_point_id: null,
  knowledge_revision: 0,
  grade: null,
  semester: null,
  tag_ids: [],
})

const fetchQuestions = async () => {
  try {
    // 构建查询参数，多选值用逗号分隔
    const params = {
      skip: (pagination.page - 1) * pagination.limit,
      limit: pagination.limit,
    }
    if (filters.subject_id) params.subject_id = filters.subject_id
    if (filters.difficulty && filters.difficulty.length) params.difficulty = filters.difficulty.join(',')
    if (filters.tag_ids && filters.tag_ids.length) params.tag_ids = filters.tag_ids.join(',')
    if (filters.knowledge_parent_id) params.knowledge_parent_id = filters.knowledge_parent_id
    if (filters.knowledge_point_id) params.knowledge_point_id = filters.knowledge_point_id
    if (filters.unclassified) params.unclassified = 1
    if (filters.keyword) params.keyword = filters.keyword
    if (filters.grade) params.grade = filters.grade
    if (filters.semester) params.semester = filters.semester
    if (filters.accuracy_range) params.accuracy_range = filters.accuracy_range

    const { data } = await questionApi.list(params)
    questions.value = data
    // 手机卡片：列表换了就清空勾选，避免批量删除时带上看不到的题（电脑端表格换数据时自己会清）
    if (is_mobile.value) selectedQuestions.value = []
  } catch (error) {
    ElMessage.error('获取错题列表失败')
  }
}

const fetchSubjects = async () => {
  try {
    const { data } = await questionApi.listSubjects()
    subjects.value = data
  } catch (error) {
    console.error('获取学科失败:', error)
  }
}

const fetchTags = async () => {
  try {
    const { data } = await questionApi.listTags()
    allTags.value = data
  } catch (error) {
    console.error('获取标签失败:', error)
  }
}

// 编辑弹窗中切换学科时清空已选考点（考点属于学科）
watch(() => editForm.subject_id, () => {
  editForm.knowledge_point_ids = []
  editForm.primary_knowledge_point_id = null
})

const getImageList = (row) => {
  if (!row) return []
  if (row.original_images && Array.isArray(row.original_images)) {
    return row.original_images
  }
  if (row.original_image) {
    return [row.original_image]
  }
  return []
}

const handleAnalysisImageUpload = async (options) => {
  const { file } = options
  try {
    const formData = new FormData()
    formData.append('file', file)
    const res = await uploadApi.uploadFile(file)
    if (res.data && res.data.path) {
      editForm.analysis_image = res.data.path
      ElMessage.success('上传成功')
    } else if (res.data && res.data.image_path) {
      editForm.analysis_image = res.data.image_path
      ElMessage.success('上传成功')
    } else if (res.data && res.data.file_path) {
      editForm.analysis_image = res.data.file_path
      ElMessage.success('上传成功')
    } else {
      ElMessage.error('上传失败')
    }
  } catch (error) {
    console.error('上传失败:', error)
    ElMessage.error('上传失败')
  }
}

const handleOriginalImageUpload = async (options) => {
  const { file } = options
  console.log('[DEBUG upload] file:', file.name)
  try {
    const formData = new FormData()
    formData.append('file', file)
    const res = await uploadApi.uploadFile(file)
    console.log('[DEBUG upload] res:', res)
    console.log('[DEBUG upload] res.data:', res.data)
    console.log('[DEBUG upload] res.data.path:', res.data?.path)
    if (res.data && res.data.path) {
      editForm.original_image = res.data.path
      ElMessage.success('上传成功')
    } else if (res.data && res.data.image_path) {
      editForm.original_image = res.data.image_path
      ElMessage.success('上传成功')
    } else if (res.data && res.data.file_path) {
      editForm.original_image = res.data.file_path
      ElMessage.success('上传成功')
    } else {
      ElMessage.error('上传失败')
    }
  } catch (error) {
    console.error('上传失败:', error)
    ElMessage.error('上传失败')
  }
}

const viewDetail = async (row) => {
  const { data } = await questionApi.get(row.id)
  currentQuestion.value = data
  detailVisible.value = true

  // 获取练习历史
  try {
    const historyRes = await axios.get(`/api/questions/${row.id}/practice-history`)
    practiceHistory.value = historyRes.data || []
  } catch {
    practiceHistory.value = []
  }
}

const previewImage = (url) => {
  imagePreviewUrl.value = url
  imagePreviewVisible.value = true
}

const editQuestion = (row) => {
  currentQuestion.value = row
  editForm.subject_id = row.subject_id || null
  editForm.original_image = row.original_image || ''
  editForm.parsed_question = row.parsed_question || ''
  editForm.question_no = row.question_no || ''
  editForm.wrong_answer = row.wrong_answer || ''
  editForm.answer = row.answer || ''
  editForm.analysis = row.analysis || ''
  editForm.analysis_image = row.analysis_image || ''
  editForm.difficulty = row.difficulty || 3
  const points = row.knowledge_points || []
  editForm.knowledge_point_ids = points.map(point => point.id)
  editForm.primary_knowledge_point_id = points.find(point => point.is_primary)?.id ?? null
  editForm.knowledge_revision = row.knowledge_revision || 0
  editForm.grade = row.grade || null
  editForm.semester = row.semester || null
  editForm.tag_ids = row.tags ? row.tags.map(t => t.id) : []
  editVisible.value = true
}

const saveEdit = async () => {
  if (editForm.knowledge_point_ids.length && !editForm.primary_knowledge_point_id) {
    ElMessage.warning('请为所选知识点指定主考点')
    return
  }
  editLoading.value = true
  try {
    const submitData = { ...editForm }
    await questionApi.update(currentQuestion.value.id, submitData)
    ElMessage.success('更新成功')
    editVisible.value = false
    fetchQuestions()
  } catch (error) {
    const detail = error.response?.data?.detail
    ElMessage.error(detail || '更新失败')
    if (error.response?.status === 409) fetchQuestions()
  } finally {
    editLoading.value = false
  }
}

const generateSimilar = async (row) => {
  try {
    await ElMessageBox.confirm('将为该错题生成一道相似题目，是否继续？', '生成相似题', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'info',
    })
    const { data } = await questionApi.generateSimilar(row.id)
    ElMessage.success('相似题已生成')
    fetchQuestions()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('生成失败')
    }
  }
}

const deleteQuestion = async (row) => {
  try {
    await ElMessageBox.confirm('确定要删除这道错题吗？', '删除确认', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning',
    })
    await questionApi.delete(row.id)
    ElMessage.success('删除成功')
    fetchQuestions()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('删除失败')
    }
  }
}

const getDifficultyType = (difficulty) => {
  const types = ['', 'success', 'success', 'warning', 'warning', 'danger']
  return types[difficulty] || 'info'
}

const getDifficultyStars = (difficulty) => {
  return '★'.repeat(difficulty)
}

// 获取黄色星星（统一黄色）
const getYellowStars = (difficulty) => {
  if (!difficulty) return '☆☆☆☆☆'
  const d = Math.max(0, Math.min(5, difficulty)) // clamp to [0, 5]
  return '★'.repeat(d) + '☆'.repeat(5 - d)
}

const getAccuracyDisplay = (row) => {
  const correct = row.correct_count || 0
  const error = row.error_count || 0
  if (correct + error === 0) return '-'
  return Math.round(correct / (correct + error) * 100) + '%'
}

const getAccuracyValue = (row) => {
  const correct = row.correct_count || 0
  const error = row.error_count || 0
  if (correct + error === 0) return -1
  return correct / (correct + error)
}

const visibleKnowledgePoints = (row) => {
  const points = [...(row.knowledge_points || [])]
  points.sort((left, right) => {
    if (Boolean(left.is_primary) !== Boolean(right.is_primary)) return left.is_primary ? -1 : 1
    return (left.id || 0) - (right.id || 0)
  })
  return points.slice(0, 3)
}

const hasActiveFilters = computed(() => {
  return filters.difficulty?.length ||
    filters.tag_ids?.length ||
    filters.knowledge_parent_id ||
    filters.knowledge_point_id ||
    filters.unclassified ||
    filters.subject_id ||
    filters.grade ||
    filters.semester ||
    filters.accuracy_range
})

const removeFilter = (key, val) => {
  if (key === 'difficulty') {
    filters.difficulty = (filters.difficulty || []).filter(d => d !== val)
  } else if (key === 'tag_ids') {
    filters.tag_ids = (filters.tag_ids || []).filter(id => id !== val)
  } else if (key === 'unclassified') {
    filters.unclassified = false
  } else if (key === 'knowledge_parent_id') {
    filters.knowledge_parent_id = null
    filters.knowledge_point_id = null
  } else if (key === 'knowledge_point_id') {
    filters.knowledge_point_id = null
  } else {
    filters[key] = typeof filters[key] === 'number' ? null : (Array.isArray(filters[key]) ? [] : '')
  }
  fetchQuestions()
}

/** 把筛选项（不含搜索关键词）全部清空，只改条件不查询。手机抽屉的「重置」也用它。 */
const reset_filter_fields = () => {
  filters.difficulty = null
  filters.tag_ids = null
  filters.knowledge_parent_id = null
  filters.knowledge_point_id = null
  filters.unclassified = false
  filters.subject_id = null
  filters.grade = null
  filters.semester = null
  filters.accuracy_range = null
}

const clearAllFilters = () => {
  reset_filter_fields()
  fetchQuestions()
}

/** 已选了几项筛选（手机「筛选」按钮上的数字），多选项算一项。 */
const active_filter_count = computed(() => [
  filters.subject_id,
  filters.difficulty?.length,
  filters.tag_ids?.length,
  filters.knowledge_parent_id,
  filters.knowledge_point_id,
  filters.unclassified,
  filters.grade,
  filters.semester,
  filters.accuracy_range,
].filter(Boolean).length)

/** 手机抽屉里勾「只看未分类」时，清掉知识点选择（和电脑一致，但先不查询）。 */
const clear_knowledge_if_unclassified = () => {
  if (filters.unclassified) {
    filters.knowledge_parent_id = null
    filters.knowledge_point_id = null
  }
}

/** 手机抽屉点「确定」：回到第一页、按当前条件查询，并关上抽屉。 */
const apply_drawer_filters = () => {
  pagination.page = 1
  fetchQuestions()
  filter_drawer_visible.value = false
}

/** 正确率筛选值对应的文字，例如 '0-30' → '0-30% 薄弱'。 */
const get_accuracy_range_label = (value) => {
  return ACCURACY_RANGE_OPTIONS.find(opt => opt.value === value)?.label || value
}

const removeDifficulty = (d) => {
  filters.difficulty = filters.difficulty.filter(i => i !== d)
  fetchQuestions()
}

const removeTag = (tagId) => {
  filters.tag_ids = filters.tag_ids.filter(id => id !== tagId)
  fetchQuestions()
}

const getTagColor = (tagId) => {
  const tag = allTags.value.find(t => t.id === tagId)
  return tag?.color || '#409eff'
}

// 获取标签的样式（背景色和文字色）
const getTagStyle = (tagId) => {
  const bgColor = getTagColor(tagId)
  // 根据背景色亮度计算文字颜色
  const textColor = getContrastColor(bgColor)
  return { backgroundColor: bgColor, borderColor: bgColor, color: textColor }
}

// 根据背景色返回对比色文字
const getContrastColor = (hexColor) => {
  if (!hexColor) return '#ffffff'
  // 移除 # 号
  const color = hexColor.replace('#', '')
  // 解析RGB
  const r = parseInt(color.substr(0, 2), 16)
  const g = parseInt(color.substr(2, 2), 16)
  const b = parseInt(color.substr(4, 2), 16)
  // 计算亮度
  const brightness = (r * 299 + g * 587 + b * 114) / 1000
  return brightness > 128 ? '#000000' : '#ffffff'
}

const getTagName = (tagId) => {
  const tag = allTags.value.find(t => t.id === tagId)
  return tag?.name || ''
}

const getGradeLabel = (grade) => {
  if (!grade) return '未设置'
  const g = gradeOptions.find(o => o.value === grade)
  return g ? g.label : `${grade}年级`
}

const formatDate = (dateStr) => {
  if (!dateStr) return ''
  return new Date(dateStr).toLocaleString('zh-CN')
}

// 多选相关方法
// 待核对的题不能勾选（不能拿去建练习卷）
const isRowSelectable = (row) => row.review_status !== 'pending'

const handleSelectionChange = (selection) => {
  selectedQuestions.value = selection
}

const clearSelection = () => {
  selectedQuestions.value = []
}

/** 手机卡片：这道题当前是否已勾选（按 id 比较）。 */
const is_question_selected = (row) => selectedQuestions.value.some(q => q.id === row.id)

/** 手机卡片上的勾选：没选中就选上，选中了就取消；和表格共用 selectedQuestions，批量操作照常可用。 */
const toggle_question_select = (row) => {
  if (!isRowSelectable(row)) return
  handleSelectionChange(is_question_selected(row)
    ? selectedQuestions.value.filter(q => q.id !== row.id)
    : [...selectedQuestions.value, row])
}

/** 列表里的主按钮「查看」。表格和手机卡片共用。 */
const question_primary_action = (row) => ({ label: '查看', run: () => viewDetail(row) })

/** 「更多」下拉里的操作：编辑、生成相似题、删除。表格和手机卡片共用。 */
const question_more_actions = (row) => [
  { label: '编辑', run: () => editQuestion(row) },
  { label: '生成相似题', run: () => generateSimilar(row) },
  { label: '删除', danger: true, run: () => deleteQuestion(row) },
]

/** 手机卡片上的短日期，例如 11/12。 */
const format_short_date = (dateStr) => {
  if (!dateStr) return ''
  const d = new Date(dateStr)
  return `${d.getMonth() + 1}/${d.getDate()}`
}

const showPrintDialog = (type) => {
  printForm.questionType = type
  // 自动生成默认名称
  const now = new Date()
  const dateStr = `${now.getFullYear()}${String(now.getMonth() + 1).padStart(2, '0')}${String(now.getDate()).padStart(2, '0')}`
  printForm.name = `练习集_${dateStr}`
  printDialogVisible.value = true
}

const createPracticeSet = async () => {
  if (!printForm.name.trim()) {
    ElMessage.warning('请输入练习集名称')
    return
  }
  if (selectedQuestions.value.length === 0) {
    ElMessage.warning('请先选择题目')
    return
  }

  printLoading.value = true
  try {
    const questionIds = selectedQuestions.value.map(q => q.id)
    const { data } = await questionApi.createPracticeSet({
      name: printForm.name,
      question_ids: questionIds,
      question_type: printForm.questionType,
    })

    // 练习集已经保存，PDF失败时关闭创建窗口，避免重复创建。
    printDialogVisible.value = false
    clearSelection()
    let pdfRes
    try {
      pdfRes = await questionApi.generatePracticeSetPdf(data.id)
    } catch (error) {
      ElMessage.warning(`练习集已创建，PDF生成失败：${error.response?.data?.detail || error.message}。请在练习列表重试`)
      return
    }

    ElMessage.success('练习集已创建，PDF已生成')
    printDialogVisible.value = false
    clearSelection()

    // 打开PDF下载
    window.open(pdfRes.data.pdf_url, '_blank')
  } catch (error) {
    ElMessage.error('创建练习集失败')
  } finally {
    printLoading.value = false
  }
}

const batchGenerateSimilar = async () => {
  if (selectedQuestions.value.length === 0) {
    ElMessage.warning('请先选择题目')
    return
  }

  try {
    await ElMessageBox.confirm(`将为 ${selectedQuestions.value.length} 道错题生成相似题，是否继续？`, '批量生成相似题', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'info',
    })

    const questionIds = selectedQuestions.value.map(q => q.id)
    const { data } = await questionApi.batchGenerateSimilar({ question_ids: questionIds })

    if (data.failed_count > 0) {
      ElMessage.warning(`成功 ${data.success_count} 道，失败 ${data.failed_count} 道`)
    } else {
      ElMessage.success(`成功生成 ${data.success_count} 道相似题`)
    }
    fetchQuestions()
    clearSelection()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('批量生成失败')
    }
  }
}

onMounted(async () => {
  await appConfigStore.load()
  // 首页年级维度跳转：/questions?grade=6
  const routeGrade = Number(route.query.grade)
  const routeSubject = Number(route.query.subject_id)
  const routeParent = Number(route.query.knowledge_parent_id)
  const routePoint = Number(route.query.knowledge_point_id)
  if (routeSubject) filters.subject_id = routeSubject
  if (routeGrade) {
    filters.grade = routeGrade
  } else if (filters.grade == null) {
    filters.grade = appConfigStore.defaultGrade
  }
  if (filters.semester == null) filters.semester = appConfigStore.defaultSemester
  if (routeParent) filters.knowledge_parent_id = routeParent
  if (routePoint) filters.knowledge_point_id = routePoint
  if (route.query.unclassified === '1' || route.query.unclassified === 'true') filters.unclassified = true
  fetchQuestions()
  fetchSubjects()
  fetchTags()
  if (filters.subject_id) fetchFilterOptions(filters.subject_id)
})
</script>

<style scoped>
.card-header  {

  display: flex;

  justify-content: space-between;

  align-items: center;

}


.header-actions  {

  display: flex;

  gap: 12px;

}


.header-actions :deep(.el-button)  {

  padding: 12px 20px;

  font-size: 15px;

}


.filters  {

  display: flex;

  gap: 15px;

  flex-wrap: wrap;

  font-size: 16px;

}


.filters :deep(.el-input__wrapper),
.filters :deep(.el-select__wrapper)  {

  min-height: 40px !important;

  font-size: 16px !important;

}


.filters :deep(.el-input__inner)  {

  font-size: 16px !important;

  height: 40px !important;

}


.filters :deep(.el-select__tags)  {

  font-size: 16px !important;

}


.selected-filters  {

  display: flex;

  gap: 12px;

  flex-wrap: wrap;

  align-items: center;

  padding: 12px 0;

  font-size: 16px;

}


.filter-label  {

  font-size: 16px;

  color: var(--text-muted);

}


.question-cell  {

  display: flex;

  align-items: center;

}


.text-preview  {

  overflow: hidden;

  text-overflow: ellipsis;

  white-space: normal;

  word-break: break-word;

  line-height: 1.4;

}


.pagination  {

  margin-top: 20px;

  display: flex;

  justify-content: flex-end;

}


.batch-actions  {

  position: fixed;

  bottom: 0;

  left: 0;

  right: 0;

  background: white;

  padding: 15px 20px;

  box-shadow: 0 -2px 10px rgba(0, 0, 0, 0.1);

  z-index: 100;

  display: flex;

  justify-content: space-between;

  align-items: center;

}


.batch-info  {

  font-size: 14px;

  color: var(--text-secondary);

}


.batch-info strong  {

  color: var(--accent-blue);

  font-size: 16px;

}


.batch-buttons  {

  display: flex;

  gap: 10px;

}


.analysis-image-preview  {

  display: flex;

  align-items: center;

  gap: 10px;

}


.original-image-preview  {

  display: flex;

  align-items: center;

  gap: 10px;

}


/* 难度星级样式 */
.difficulty-stars  {

  font-size: 14px;

  letter-spacing: 2px;

}


.difficulty-stars.difficulty-1,
.difficulty-stars.difficulty-2  {

  color: #67c23a;

}


.difficulty-stars.difficulty-3  {

  color: #e6a23c;

}


.difficulty-stars.difficulty-4,
.difficulty-stars.difficulty-5  {

  color: #f56c6c;

}


/* 难度筛选标签样式 */
.difficulty-filter-1,
.difficulty-filter-2  {

  color: #67c23a;

  border-color: #67c23a;

}


.difficulty-filter-3  {

  color: #e6a23c;

  border-color: #e6a23c;

}


.difficulty-filter-4,
.difficulty-filter-5  {

  color: #f56c6c;

  border-color: #f56c6c;

}


/* 表格字体加大 */
:deep(.el-table)  {

  font-size: 15px;

}


:deep(.el-table th)  {

  font-size: 15px;

}


:deep(.el-table td)  {

  font-size: 15px;

}


/* 禁用卡片的hover效果 */
.questions :deep(.el-card)  {

  transition: none;

}

.questions :deep(.el-card:hover)  {

  transform: none;

  box-shadow: var(--shadow-sm) !important;

}


/* ========== 详情页卡片式布局 ========== */
.question-detail  {

  padding: 8px;

}


/* 原图展示区 */
.detail-images  {

  margin-bottom: 16px;

}


.image-gallery  {

  display: flex;

  gap: 12px;

  overflow-x: auto;

  padding: 4px 0;

}


.gallery-image  {

  width: 180px;

  height: 180px;

  border-radius: 8px;

  cursor: pointer;

  transition: transform 0.2s;

  flex-shrink: 0;

}


.gallery-image:hover  {

  transform: scale(1.05);

}


/* 卡片通用样式 */
.detail-card  {

  background: #fff;

  border-radius: 12px;

  box-shadow: 0 4px 16px rgba(0,0,0,0.08);

  margin-bottom: 16px;

  overflow: hidden;

}


.detail-row  {

  display: flex;

  gap: 16px;

  margin-bottom: 16px;

}


.flex-1  {

  flex: 1;

}


/* 卡片标题栏 */
.card-header-blue  {

  background: linear-gradient(135deg, var(--accent-blue) 0%, #3a8ee6 100%);

  color: #fff;

  padding: 14px 20px;

  font-weight: bold;

  font-size: 18px;

}


.card-header-green  {

  background: linear-gradient(135deg, #67c23a 0%, #5daf34 100%);

  color: #fff;

  padding: 14px 20px;

  font-weight: bold;

  font-size: 18px;

}


.card-header-orange  {

  background: linear-gradient(135deg, #e6a23c 0%, #db8b2e 100%);

  color: #fff;

  padding: 14px 20px;

  font-weight: bold;

  font-size: 18px;

}


.card-header-gray  {

  background: linear-gradient(135deg, var(--text-secondary) 0%, #555558 100%);

  color: #fff;

  padding: 14px 20px;

  font-weight: bold;

  font-size: 18px;

}


.card-header-purple  {

  background: linear-gradient(135deg, #9c27b0 0%, #862491 100%);

  color: #fff;

  padding: 14px 20px;

  font-weight: bold;

  font-size: 18px;

}


/* 卡片内容区 */
.card-content  {

  padding: 20px;

}


/* 题目/答案/解析文字 */
.question-text  {

  white-space: pre-wrap;

  word-break: break-word;

  line-height: 1.8;

  font-size: 17px;

  color: var(--text-primary);

}


/* 解析图片 */
.analysis-image  {

  margin-top: 12px;

}


.analysis-img  {

  width: 200px;

  height: 200px;

  border-radius: 8px;

  cursor: pointer;

}


/* 元数据行 */
.meta-row  {

  display: flex;

  gap: 32px;

  margin-bottom: 12px;

}


.meta-row:last-child  {

  margin-bottom: 0;

}


.meta-item  {

  display: flex;

  align-items: center;

  gap: 8px;

}


.meta-item label  {

  color: var(--text-muted);

  font-size: 14px;

}


.meta-item span  {

  color: var(--text-primary);

  font-size: 14px;

}


/* 黄色星星难度 */
.difficulty-stars-yellow  {

  font-size: 18px;

  letter-spacing: 3px;

  color: #f5c518;

}


/* 标签区域 */
.tags-area  {

  display: flex;

  align-items: center;

  flex-wrap: wrap;

  gap: 8px;

  margin-bottom: 16px;

}


.tags-label  {

  color: var(--text-muted);

  font-size: 14px;

}


/* 相似题 */
.similar-item  {

  padding: 12px;

  background: #f5f7fa;

  border-radius: 8px;

  margin-bottom: 12px;

}


.similar-item:last-child  {

  margin-bottom: 0;

}


.similar-item p  {

  margin: 0 0 8px 0;

  line-height: 1.6;

}


.similar-item p:last-child  {

  margin-bottom: 0;

}


/* 文字辅助 */
.text-muted  {

  color: #c0c4cc;

  font-size: 14px;

}


/* 练习历史 */
.history-item  {

  display: flex;

  align-items: center;

  gap: 12px;

  padding: 8px 0;

  border-bottom: 1px solid #ebeef5;

}


.history-item:last-child  {

  border-bottom: none;

}


.history-date  {

  color: var(--text-muted);

  font-size: 13px;

  min-width: 140px;

}


.history-name  {

  flex: 1;

  font-size: 14px;

  color: var(--text-primary);

}

.filters {
  gap:8px;
  font-size:14px}
.filters :deep(.el-input__wrapper),.filters :deep(.el-select__wrapper) {
  min-height:34px!important;
  font-size:14px!important}
.filters :deep(.el-input__inner) {
  font-size:14px!important;
  height:32px!important}
.filters :deep(.el-select__tags) {
  font-size:13px!important}
.selected-filters {
  gap:8px;
  padding:9px 0;
  font-size:13px}
.filter-label {
  font-size:13px}
.header-actions :deep(.el-button) {
  padding:9px 14px;
  font-size:14px}
.text-preview {
  line-height:1.7}
.batch-actions {
  left:220px;
  bottom:14px;
  right:20px;
  border:1px solid var(--border-light);
  border-radius:10px;
  padding:12px 16px;
  z-index:90}
.detail-card {
  box-shadow:none;
  border:1px solid var(--border-light);
  border-radius:10px}
.card-header-blue,.card-header-green,.card-header-orange,.card-header-purple {
  background:#f5f4ff;
  color:var(--text-primary);
  padding:11px 15px;
  font-size:15px}
.gallery-image:hover {
  transform:none}
@media(max-width:768px) {
  .batch-actions {
  left:10px;
  right:10px;
  bottom:76px;
  flex-wrap:wrap;
  gap:8px}
.batch-buttons {
  flex-wrap:wrap}
.detail-row {
  flex-direction:column}
.question-detail {
  padding:0}
}

.question-cell { align-items: flex-start; gap: 10px; min-width: 0; }
.question-cell :deep(.el-image) { flex-shrink: 0; }
.text-preview { flex: 1; min-width: 0; line-height: 1.9; font-size: 16px; }
.text-preview :deep(.math-text) { display: block; width: 100%; overflow-y: visible; }
.question-meta { display: flex; flex-direction: column; align-items: flex-start; gap: 6px; font-size: 13px; color: var(--text-secondary); }
.question-meta small { color: var(--text-muted); font-size: 12px; }
.question-meta :deep(.el-tag) { max-width: 100%; height: auto; white-space: normal; line-height: 1.6; padding: 3px 7px; }
.question-tags { display: flex; flex-wrap: wrap; gap: 4px; }
.question-tags:empty { display: none; }
.question-actions { display: flex; align-items: center; gap: 6px; }
.question-actions :deep(.el-button) { padding: 7px 9px; }
.question-table :deep(td.el-table__cell) { padding: 13px 0; vertical-align: top; }
.question-kp { display: flex; flex-wrap: wrap; gap: 4px; }
.legacy-knowledge { color: var(--text-muted); font-size: 12px; font-style: italic; }
.detail-knowledge { display: flex; flex-wrap: wrap; gap: 6px; min-width: 0; }
.knowledge-meta-item { align-items: flex-start; }

/* ---------- 手机端：头部、搜索+筛选、卡片列表、浮动批量栏 ---------- */
@media (max-width: 768px) {
  .questions :deep(.el-card__header) { padding: 14px 16px; }
  .questions :deep(.el-card__body) { padding: 12px; }
  .card-header > span { font-size: 16px; font-weight: 600; }
  .q-mobile-total { margin-left: 6px; font-size: 12px; font-weight: 400; color: var(--el-text-color-placeholder); }
  .q-mobile-header-actions { gap: 8px; }
  .q-mobile-header-actions :deep(.el-button) { margin: 0; padding: 8px 14px; font-size: 14px; }
  /* 已选条件：一行横向滑动，不换行 */
  .selected-filters.q-mobile-chips {
    flex-wrap: nowrap; overflow-x: auto; gap: 6px; margin: 0 0 10px; padding: 0 0 2px;
    background: transparent; border: 0;
  }
  .selected-filters.q-mobile-chips .filter-label { display: none; }
  .selected-filters.q-mobile-chips > * { flex: none; }
  /* 勾选后批量栏贴在底部导航上方 */
  .batch-actions.is-floating {
    position: fixed; left: 12px; right: 12px; z-index: 20;
    bottom: calc(76px + env(safe-area-inset-bottom));
    margin: 0; padding: 10px 12px; gap: 8px;
    background: var(--el-bg-color, #fff); border-radius: 12px;
    box-shadow: 0 6px 24px rgba(15, 23, 42, .16);
  }
  .batch-actions.is-floating .batch-buttons { gap: 6px; }
  .batch-actions.is-floating :deep(.el-button) { margin: 0; padding: 7px 10px; font-size: 13px; }
  .pagination { justify-content: center; }
}

/* 搜索框 + 筛选按钮 */
.q-mobile-search { display: flex; gap: 8px; margin-bottom: 8px; }
.q-mobile-search :deep(.el-input) { flex: 1; min-width: 0; }
.q-mobile-filter-btn { flex: none; margin: 0; }
.q-mobile-filter-count {
  margin-left: 4px; padding: 0 6px; border-radius: 8px; font-size: 11px; line-height: 16px;
  color: #fff; background: var(--el-color-primary);
}

/* 手机卡片：题目 / 标签 / 数据+操作 三层 */
.q-mobile-list { display: flex; flex-direction: column; gap: 10px; }
.q-mobile-card {
  padding: 12px 14px; border-radius: 12px;
  background: var(--el-bg-color, #fff);
  border: 1px solid var(--el-border-color-lighter, #ebeef5);
  border-left: 3px solid transparent;
}
.q-mobile-card.is-pending { border-left-color: var(--el-color-warning); }
.q-mobile-card.is-selected { border-color: var(--el-color-primary-light-5); background: var(--el-color-primary-light-9); }
.q-mobile-top { display: flex; align-items: flex-start; gap: 10px; }
.q-mobile-top :deep(.el-checkbox) { height: 22px; flex: none; }
.q-mobile-thumb {
  width: 52px; height: 52px; flex: none; border-radius: 8px; cursor: pointer;
  background: var(--el-fill-color-light, #f5f7fa);
}
.q-mobile-text {
  flex: 1; min-width: 0; font-size: 14px; line-height: 22px; cursor: pointer;
  color: var(--el-text-color-primary); overflow-wrap: anywhere;
  display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical; overflow: hidden;
}
.q-mobile-text :deep(.math-text) { display: inline; }
.q-mobile-pending { margin-right: 4px; vertical-align: 1px; }
.q-mobile-tags { display: flex; flex-wrap: wrap; align-items: center; gap: 6px; margin-top: 8px; padding-left: 24px; }
.q-mobile-tags :deep(.el-tag) { max-width: 100%; }
.q-mobile-chip {
  font-size: 12px; line-height: 20px; padding: 0 8px; border-radius: 10px;
  color: var(--el-text-color-regular); background: var(--el-fill-color-light, #f5f7fa);
}
.q-mobile-chip.is-muted { color: var(--el-text-color-placeholder); }
.q-mobile-date { margin-left: auto; font-style: normal; font-size: 12px; color: var(--el-text-color-placeholder); }
.q-mobile-foot {
  display: flex; align-items: center; justify-content: space-between; gap: 8px;
  margin-top: 10px; padding-top: 10px; padding-left: 24px;
  border-top: 1px dashed var(--el-border-color-lighter, #ebeef5);
}
.q-mobile-meta { display: flex; flex-wrap: wrap; align-items: center; gap: 2px 12px; min-width: 0; font-size: 13px; color: var(--el-text-color-secondary); }
.q-mobile-meta b { color: var(--el-text-color-primary); font-weight: 600; }
.q-mobile-stars { color: var(--el-color-warning); font-size: 12px; letter-spacing: 1px; }
/* 正确率小条：低于 60% 变红 */
.q-mobile-acc-bar {
  display: inline-block; width: 48px; height: 5px; margin-left: 4px; vertical-align: middle;
  border-radius: 3px; overflow: hidden; background: var(--el-fill-color, #f0f2f5);
}
.q-mobile-acc-bar > i { display: block; height: 100%; background: var(--el-color-success); }
.q-mobile-acc-bar.is-low > i { background: var(--el-color-danger); }

/* 筛选抽屉内容 */
.q-drawer-body { display: flex; flex-direction: column; }
.q-drawer-label { margin: 10px 0 6px; font-size: 12px; color: var(--el-text-color-secondary); }
.q-drawer-label:first-child { margin-top: 0; }
.q-drawer-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; }
.q-drawer-grid.is-three { grid-template-columns: repeat(3, minmax(0, 1fr)); }
.q-drawer-check { margin-top: 8px; }
.q-drawer-footer { display: flex; gap: 8px; }
.q-drawer-footer :deep(.el-button) { flex: 1; height: 40px; margin: 0; }
.q-drawer-footer :deep(.el-button--primary) { flex: 2; }
</style>
<style>
/* 手机筛选抽屉外框（抽屉挂在 body 下，scoped 样式管不到） */
.el-drawer.q-filter-drawer { max-height: 85vh; border-radius: 16px 16px 0 0; }
.el-drawer.q-filter-drawer .el-drawer__header { margin-bottom: 8px; padding: 14px 16px 0; }
.el-drawer.q-filter-drawer .el-drawer__body { padding: 8px 16px; }
.el-drawer.q-filter-drawer .el-drawer__footer { padding: 10px 16px calc(12px + env(safe-area-inset-bottom)); }
</style>
