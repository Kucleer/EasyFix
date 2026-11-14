<template>
  <div class="papers-page">
    <PageHeading title="卷子和作业" description="每份卷子或作业一条记录，错题和考试分数都挂在它下面">
      <el-button type="primary" @click="createVisible = true">新增记录</el-button>
    </PageHeading>

    <el-card shadow="never">
      <div class="filters">
        <el-select v-model="filters.subject_id" placeholder="全部学科" clearable class="filter-item" @change="onFilterChange">
          <el-option v-for="s in subjects" :key="s.id" :label="s.name" :value="s.id" />
        </el-select>
        <el-select v-model="filters.paper_type" placeholder="全部类型" clearable class="filter-item" @change="onFilterChange">
          <el-option v-for="(label, value) in PAPER_TYPE_LABELS" :key="value" :label="label" :value="value" />
        </el-select>
      </div>

      <!-- 手机：卡片列表，整张卡片可点进详情（和电脑端名称链接去同一个页面） -->
      <div v-if="is_mobile" v-loading="loading" class="pp-mobile-list">
        <div v-if="!papers.length && !loading" class="pp-mobile-empty">还没有记录</div>
        <div
          v-for="row in papers"
          :key="row.id"
          class="pp-mobile-card"
          :class="{ 'is-pending': row.pending_count > 0 }"
          role="link"
          tabindex="0"
          @click="open_paper(row)"
          @keydown.enter="open_paper(row)"
        >
          <!-- 第一层：名称 + 右边大号分数 -->
          <div class="pp-mobile-top">
            <div class="pp-mobile-main">
              <div class="pp-mobile-title">{{ row.name }}</div>
              <!-- 第二层：学科、类型、年级学期，日期靠右 -->
              <div class="pp-mobile-tags">
                <span v-if="row.subject_name">{{ row.subject_name }}</span>
                <span v-if="paperTypeLabel(row)">{{ paperTypeLabel(row) }}</span>
                <span v-if="gradeSemesterText(row)">{{ gradeSemesterText(row) }}</span>
                <em v-if="row.paper_date" class="pp-mobile-date">{{ format_short_date(row.paper_date) }}</em>
              </div>
            </div>
            <div v-if="scoreText(row)" class="pp-mobile-score">{{ Number(row.score) }}<small>/{{ Number(row.full_score) }}</small></div>
            <div v-else class="pp-mobile-score is-empty">无分数</div>
          </div>
          <!-- 底部：错题数、待核对、备注，右边"查看" -->
          <div class="pp-mobile-foot">
            <div class="pp-mobile-meta">
              <span><b>{{ row.question_count ?? 0 }}</b> 道错题</span>
              <span v-if="row.pending_count > 0" class="is-warn">{{ row.pending_count }} 道待核对</span>
              <span v-if="row.notes" class="pp-mobile-notes">{{ row.notes }}</span>
            </div>
            <span class="pp-mobile-more">查看 ›</span>
          </div>
        </div>
      </div>

      <el-table v-else v-loading="loading" :data="papers" stripe style="width: 100%" empty-text="还没有记录">
        <el-table-column label="名称" min-width="200">
          <template #default="{ row }">
            <router-link :to="'/papers/' + row.id" class="paper-link">{{ row.name }}</router-link>
            <div class="sub-line">{{ row.subject_name }}</div>
          </template>
        </el-table-column>
        <el-table-column label="类型" width="130">
          <template #default="{ row }">{{ paperTypeLabel(row) }}</template>
        </el-table-column>
        <el-table-column prop="paper_date" label="日期" width="120" />
        <el-table-column label="年级学期" width="130">
          <template #default="{ row }">{{ gradeSemesterText(row) }}</template>
        </el-table-column>
        <el-table-column label="分数" width="110">
          <template #default="{ row }">{{ scoreText(row) }}</template>
        </el-table-column>
        <el-table-column label="题目数" width="90">
          <template #default="{ row }">{{ row.question_count }}</template>
        </el-table-column>
        <el-table-column label="待核对" width="90">
          <template #default="{ row }">
            <el-tag v-if="row.pending_count > 0" type="warning" size="small">{{ row.pending_count }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="备注" min-width="160">
          <template #default="{ row }"><span class="notes-text">{{ row.notes }}</span></template>
        </el-table-column>
      </el-table>

      <div class="pagination">
        <el-pagination
          v-model:current-page="pagination.page"
          v-model:page-size="pagination.limit"
          :page-sizes="[10, 20, 50]"
          :total="total"
          :layout="is_mobile ? 'prev, pager, next' : 'total, sizes, prev, pager, next'"
          :small="is_mobile"
          @current-change="fetchPapers"
          @size-change="onFilterChange"
        />
      </div>
    </el-card>

    <PaperFormDialog v-model="createVisible" :subjects="subjects" :default-subject-id="filters.subject_id" @saved="onCreated" />
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import PageHeading from '@/components/PageHeading.vue'
import PaperFormDialog from '@/components/PaperFormDialog.vue'
import { paperApi } from '@/api/paper'
import { questionApi } from '@/api/question'
import { PAPER_TYPE_LABELS, paperTypeLabel, scoreText } from '@/composables/intakeLabels'
import { use_is_mobile } from '@/composables/useIsMobile'

const router = useRouter()
// 是否手机宽度：手机用卡片列表，电脑用表格
const is_mobile = use_is_mobile()

const loading = ref(false)
const papers = ref([])
const total = ref(0)
const subjects = ref([])
const createVisible = ref(false)
const filters = reactive({ subject_id: null, paper_type: null })
const pagination = reactive({ page: 1, limit: 20 })

// 年级学期的显示文字，都没填返回空串
function gradeSemesterText(paper) {
  const grades = ['', '一年级', '二年级', '三年级', '四年级', '五年级', '六年级', '初一', '初二', '初三', '高一', '高二', '高三']
  const grade = paper.grade ? grades[paper.grade] || '' : ''
  const semester = paper.semester === 1 ? '上学期' : paper.semester === 2 ? '下学期' : ''
  return [grade, semester].filter(Boolean).join(' ')
}

/** 打开某份卷子的详情页（手机卡片整卡点击用，和电脑端名称链接去同一个地方）。 */
function open_paper(paper) {
  router.push('/papers/' + paper.id)
}

/** 手机卡片上的短日期：'2026-11-08' 显示成 '11/08'，格式不认识就原样返回。 */
function format_short_date(date_str) {
  const match = /^\d{4}-(\d{2})-(\d{2})/.exec(date_str || '')
  return match ? `${match[1]}/${match[2]}` : (date_str || '')
}

// 加载学科，供筛选和新增使用
async function fetchSubjects() {
  try {
    const { data } = await questionApi.listSubjects()
    subjects.value = data
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '加载学科失败')
  }
}

// 按筛选和分页加载卷子列表
async function fetchPapers() {
  loading.value = true
  try {
    const params = { skip: (pagination.page - 1) * pagination.limit, limit: pagination.limit }
    if (filters.subject_id) params.subject_id = filters.subject_id
    if (filters.paper_type) params.paper_type = filters.paper_type
    const { data } = await paperApi.list(params)
    papers.value = data.items || []
    total.value = data.total || 0
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '加载卷子列表失败')
  } finally {
    loading.value = false
  }
}

// 筛选或每页条数变了，回到第一页重新加载
function onFilterChange() {
  pagination.page = 1
  fetchPapers()
}

// 新增成功后回到第一页看最新的记录
function onCreated() {
  pagination.page = 1
  fetchPapers()
}

onMounted(() => {
  fetchSubjects()
  fetchPapers()
})
</script>

<style scoped>
.filters { display: flex; gap: 12px; flex-wrap: wrap; margin-bottom: 14px; }
.filter-item { width: 160px; }
.paper-link { color: var(--accent-blue); font-weight: 600; text-decoration: none; }
.paper-link:hover { text-decoration: underline; }
.sub-line { font-size: 12px; color: var(--text-muted); margin-top: 2px; }
.notes-text { color: var(--text-secondary); font-size: 13px; }
.pagination { display: flex; justify-content: flex-end; margin-top: 16px; }

/* ---------- 手机端：两个筛选各占一半、卡片列表、分页居中 ---------- */
@media (max-width: 768px) {
  .papers-page :deep(.el-card__body) { padding: 12px; }
  .filters { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; margin-bottom: 12px; }
  .filter-item { width: 100%; }
  .pagination { justify-content: center; }
}

/* 手机卡片：名称+分数 / 标签 / 错题数等 三层 */
.pp-mobile-list { display: flex; flex-direction: column; gap: 10px; min-height: 80px; }
.pp-mobile-empty { padding: 32px 0; text-align: center; font-size: 13px; color: var(--el-text-color-secondary); }
.pp-mobile-card {
  padding: 12px 14px; border-radius: 12px; cursor: pointer;
  background: var(--el-bg-color, #fff);
  border: 1px solid var(--el-border-color-lighter, #ebeef5);
  border-left: 3px solid transparent;
}
.pp-mobile-card:active { background: var(--el-fill-color-light, #f5f7fa); }
/* 有待核对的题，左边一道橙色竖线提醒 */
.pp-mobile-card.is-pending { border-left-color: var(--el-color-warning); }
.pp-mobile-top { display: flex; align-items: flex-start; gap: 10px; }
.pp-mobile-main { flex: 1; min-width: 0; }
.pp-mobile-title {
  font-size: 15px; font-weight: 600; line-height: 22px;
  color: var(--el-text-color-primary); overflow-wrap: anywhere;
  display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden;
}
.pp-mobile-score { flex: none; font-size: 22px; font-weight: 700; line-height: 1.1; color: var(--el-color-primary); }
.pp-mobile-score small { font-size: 12px; font-weight: 400; color: var(--el-text-color-placeholder); }
.pp-mobile-score.is-empty { font-size: 13px; font-weight: 400; line-height: 22px; color: var(--el-text-color-placeholder); }
.pp-mobile-tags { display: flex; flex-wrap: wrap; align-items: center; gap: 6px; margin-top: 8px; }
.pp-mobile-tags span {
  font-size: 12px; line-height: 20px; padding: 0 8px; border-radius: 10px;
  color: var(--el-text-color-regular); background: var(--el-fill-color-light, #f5f7fa);
}
.pp-mobile-date { margin-left: auto; font-style: normal; font-size: 12px; color: var(--el-text-color-placeholder); }
.pp-mobile-foot {
  display: flex; align-items: center; justify-content: space-between; gap: 8px;
  margin-top: 10px; padding-top: 10px;
  border-top: 1px dashed var(--el-border-color-lighter, #ebeef5);
}
.pp-mobile-meta { display: flex; gap: 12px; min-width: 0; font-size: 13px; color: var(--el-text-color-secondary); }
.pp-mobile-meta > span { flex: none; }
.pp-mobile-meta b { color: var(--el-text-color-primary); font-weight: 600; }
.pp-mobile-meta .is-warn { color: var(--el-color-warning-dark-2); }
/* 备注只占剩下的位置，太长显示省略号 */
.pp-mobile-meta .pp-mobile-notes { flex: 1 1 auto; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.pp-mobile-more { flex: none; font-size: 13px; color: var(--el-color-primary); }
</style>
