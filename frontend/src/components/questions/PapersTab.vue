<template>
  <!-- 卷子和作业：每份一条记录，错题和考试分数都挂在它下面；详情仍去 /papers/:id -->
  <section class="papers-tab">
    <div class="pp-head">
      <div class="pp-filters">
        <el-select v-model="filters.subject_id" placeholder="全部学科" clearable class="pp-filter" @change="refetch_from_first">
          <el-option v-for="s in subjects" :key="s.id" :label="s.name" :value="s.id" />
        </el-select>
        <el-select v-model="filters.paper_type" placeholder="全部类型" clearable class="pp-filter" @change="refetch_from_first">
          <el-option v-for="(label, value) in PAPER_TYPE_LABELS" :key="value" :label="label" :value="value" />
        </el-select>
      </div>
      <el-button type="primary" @click="create_visible = true">
        <LineIcon name="plus" :size="16" class="pp-plus" />新增记录
      </el-button>
    </div>

    <div class="pp-panel">
      <!-- 手机：卡片列表，整张卡片点进详情 -->
      <div v-if="is_mobile" v-loading="loading" class="pp-cards">
        <div v-if="!papers.length && !loading" class="pp-empty">还没有记录</div>
        <div
          v-for="row in papers"
          :key="row.id"
          class="pp-card"
          :class="{ 'is-pending': row.pending_count > 0 }"
          role="link"
          tabindex="0"
          @click="open_paper(row)"
          @keydown.enter="open_paper(row)"
        >
          <div class="pp-card-top">
            <div class="pp-card-main">
              <div class="pp-card-title">{{ row.name }}</div>
              <div class="pp-card-tags">
                <span v-if="row.subject_name">{{ row.subject_name }}</span>
                <span v-if="paperTypeLabel(row)">{{ paperTypeLabel(row) }}</span>
                <span v-if="grade_semester(row)">{{ grade_semester(row) }}</span>
                <em v-if="row.paper_date" class="pp-card-date">{{ short_date(row.paper_date) }}</em>
              </div>
            </div>
            <div v-if="scoreText(row)" class="pp-score">{{ Number(row.score) }}<small>/{{ Number(row.full_score) }}</small></div>
            <div v-else class="pp-score is-empty">无分数</div>
          </div>
          <div class="pp-card-foot">
            <div class="pp-card-meta">
              <span><b>{{ row.question_count ?? 0 }}</b> 道错题</span>
              <span v-if="row.pending_count > 0" class="is-warn">{{ row.pending_count }} 道待核对</span>
              <span v-if="row.notes" class="pp-notes">{{ row.notes }}</span>
            </div>
            <span class="pp-more">查看 ›</span>
          </div>
        </div>
      </div>

      <el-table v-else v-loading="loading" :data="papers" empty-text="还没有记录">
        <el-table-column label="名称" min-width="200">
          <template #default="{ row }">
            <router-link :to="'/papers/' + row.id" class="pp-link">{{ row.name }}</router-link>
            <div class="pp-sub">{{ row.subject_name }}</div>
          </template>
        </el-table-column>
        <el-table-column label="类型" width="130"><template #default="{ row }">{{ paperTypeLabel(row) }}</template></el-table-column>
        <el-table-column prop="paper_date" label="日期" width="120" />
        <el-table-column label="年级学期" width="130"><template #default="{ row }">{{ grade_semester(row) }}</template></el-table-column>
        <el-table-column label="分数" width="110"><template #default="{ row }">{{ scoreText(row) }}</template></el-table-column>
        <el-table-column label="题目数" width="90"><template #default="{ row }">{{ row.question_count }}</template></el-table-column>
        <el-table-column label="待核对" width="90">
          <template #default="{ row }"><el-tag v-if="row.pending_count > 0" type="warning" size="small">{{ row.pending_count }}</el-tag></template>
        </el-table-column>
        <el-table-column label="备注" min-width="160"><template #default="{ row }"><span class="pp-notes-text">{{ row.notes }}</span></template></el-table-column>
      </el-table>

      <div class="pp-pagination">
        <el-pagination
          v-model:current-page="pagination.page"
          v-model:page-size="pagination.limit"
          :page-sizes="[10, 20, 50]"
          :total="total"
          :layout="is_mobile ? 'prev, pager, next' : 'total, sizes, prev, pager, next'"
          :small="is_mobile"
          @current-change="fetch_papers"
          @size-change="refetch_from_first"
        />
      </div>
    </div>

    <PaperFormDialog v-model="create_visible" :subjects="subjects" :default-subject-id="filters.subject_id || null" @saved="refetch_from_first" />
  </section>
</template>

<script setup>
import { onActivated, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import LineIcon from '@/components/ui/LineIcon.vue'
import PaperFormDialog from '@/components/PaperFormDialog.vue'
import { paperApi } from '@/api/paper'
import { useCatalogStore } from '@/stores/catalog'
import { PAPER_TYPE_LABELS, paperTypeLabel, scoreText } from '@/composables/intakeLabels'
import { use_is_mobile } from '@/composables/useIsMobile'
import { grade_label, semester_label } from './questionFilters'

const router = useRouter()
const catalogStore = useCatalogStore()
// 手机宽度用卡片，电脑用表格
const is_mobile = use_is_mobile()

const loading = ref(false)
const papers = ref([])
const total = ref(0)
const subjects = ref([])
const create_visible = ref(false)
const filters = reactive({ subject_id: null, paper_type: null })
const pagination = reactive({ page: 1, limit: 20 })

/** 年级学期的显示文字，都没填返回空串 */
function grade_semester(paper) {
  const grade = paper.grade ? grade_label(paper.grade) : ''
  return [grade, semester_label(paper.semester)].filter(Boolean).join(' ')
}

/** 手机卡片上的短日期：'2026-11-08' 显示成 '11/08'，格式不认识就原样返回 */
function short_date(value) {
  const match = /^\d{4}-(\d{2})-(\d{2})/.exec(value || '')
  return match ? `${match[1]}/${match[2]}` : (value || '')
}

/** 打开某份卷子的详情页 */
function open_paper(paper) {
  router.push('/papers/' + paper.id)
}

/** 按筛选和分页读卷子列表 */
async function fetch_papers() {
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

/** 筛选、每页条数变了或新增了一条：回到第 1 页重新读 */
function refetch_from_first() {
  pagination.page = 1
  fetch_papers()
}

onMounted(async () => {
  fetch_papers()
  try {
    subjects.value = [...await catalogStore.loadSubjects()]
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '加载学科失败')
  }
})

// 从别的标签切回来时重新读一次（待核对数可能变了）
let activated_before = false
onActivated(() => {
  if (activated_before) fetch_papers()
  activated_before = true
})
</script>

<style scoped>
.pp-head { display: flex; align-items: center; justify-content: space-between; gap: 12px; margin-bottom: 12px; }
.pp-filters { display: flex; flex-wrap: wrap; gap: 8px; }
.pp-filter { width: 160px; }
.pp-plus { margin-right: 4px; }
.pp-panel { padding: 18px 20px; border-radius: var(--r-lg); background: var(--surface); box-shadow: var(--shadow-1); }
.pp-link { color: var(--brand); font-weight: 600; }
.pp-link:hover { text-decoration: underline; }
.pp-sub { margin-top: 2px; font-size: 12px; color: var(--muted); }
.pp-notes-text { color: var(--ink-2); font-size: 13px; }
.pp-pagination { display: flex; justify-content: flex-end; margin-top: 16px; }

@media (max-width: 768px) {
  .pp-head { flex-direction: column-reverse; align-items: stretch; }
  .pp-head > .el-button { align-self: flex-end; }
  .pp-filters { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .pp-filter { width: 100%; }
  .pp-panel { padding: 0; background: none; box-shadow: none; }
  .pp-pagination { justify-content: center; }
}

/* 手机卡片：名称+分数 / 标签 / 错题数等 */
.pp-cards { display: flex; flex-direction: column; gap: 10px; min-height: 80px; }
.pp-empty { padding: 32px 0; text-align: center; font-size: 13px; color: var(--muted); }
.pp-card {
  padding: 12px 14px; border-radius: var(--r-md); cursor: pointer;
  background: var(--surface); box-shadow: var(--shadow-1); border-left: 3px solid transparent;
}
.pp-card:active { background: var(--bg); }
/* 有待核对的题，左边一道橙色竖线提醒 */
.pp-card.is-pending { border-left-color: var(--sun); }
.pp-card-top { display: flex; align-items: flex-start; gap: 10px; }
.pp-card-main { flex: 1; min-width: 0; }
.pp-card-title {
  font-size: 15px; font-weight: 600; line-height: 22px; color: var(--ink); overflow-wrap: anywhere;
  display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden;
}
.pp-score { flex: none; font-size: 22px; font-weight: 700; line-height: 1.1; color: var(--brand); font-family: var(--font-num); }
.pp-score small { font-size: 12px; font-weight: 400; color: var(--muted); }
.pp-score.is-empty { font-size: 13px; font-weight: 400; line-height: 22px; color: var(--muted); font-family: inherit; }
.pp-card-tags { display: flex; flex-wrap: wrap; align-items: center; gap: 6px; margin-top: 8px; }
.pp-card-tags span { font-size: 12px; line-height: 20px; padding: 0 8px; border-radius: 10px; color: var(--ink-2); background: var(--bg); }
.pp-card-date { margin-left: auto; font-style: normal; font-size: 12px; color: var(--muted); }
.pp-card-foot {
  display: flex; align-items: center; justify-content: space-between; gap: 8px;
  margin-top: 10px; padding-top: 10px; border-top: 1px dashed var(--line);
}
.pp-card-meta { display: flex; gap: 12px; min-width: 0; font-size: 13px; color: var(--ink-2); }
.pp-card-meta > span { flex: none; }
.pp-card-meta b { color: var(--ink); font-weight: 600; }
.pp-card-meta .is-warn { color: var(--sun); }
/* 备注只占剩下的位置，太长显示省略号 */
.pp-card-meta .pp-notes { flex: 1 1 auto; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.pp-more { flex: none; font-size: 13px; color: var(--brand); }
</style>
