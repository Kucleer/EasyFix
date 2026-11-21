<template>
  <!-- 全部错题：搜索和筛选、列表、分页、详情、编辑、单题生成相似题、删除 -->
  <section class="all-tab">
    <div class="all-head">
      <span class="all-total">共 <b>{{ questions.total }}</b> 道错题</span>
      <div class="all-actions">
        <el-button @click="go_targeted">出练习卷</el-button>
        <el-button type="primary" @click="router.push('/upload')">
          <LineIcon name="plus" :size="16" class="all-plus" />手工添加
        </el-button>
      </div>
    </div>

    <div class="all-panel">
      <QuestionFilters
        :filters="state.filters"
        :subjects="subjects"
        :tags="tags"
        :modules-by-subject="modules_by_subject"
        :load-options="load_options"
        :is-mobile="is_mobile"
        @change="refetch_from_first"
        @subject-change="on_subject_change"
        @apply="on_drawer_apply"
      />

      <QuestionList
        v-loading="loading"
        :items="questions.items"
        :subjects="subjects"
        :is-mobile="is_mobile"
        @view="view_detail"
        @edit="open_edit"
        @similar="generate_similar"
        @remove="remove_question"
      />

      <div class="all-pagination">
        <el-pagination
          v-model:current-page="state.page"
          v-model:page-size="state.limit"
          :page-sizes="[10, 20, 50, 100]"
          :total="questions.total"
          :layout="is_mobile ? 'prev, pager, next' : 'total, sizes, prev, pager, next'"
          :small="is_mobile"
          @current-change="fetch_list"
          @size-change="refetch_from_first"
        />
      </div>
    </div>

    <QuestionDetailDialog v-model="detail_visible" :question-id="detail_id" />
    <QuestionEditDialog v-model="edit_visible" :question="editing" :subjects="subjects" :tags="tags" @saved="fetch_list" @conflict="fetch_list" />
  </section>
</template>

<script setup>
import { onActivated, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import LineIcon from '@/components/ui/LineIcon.vue'
import QuestionFilters from './QuestionFilters.vue'
import QuestionList from './QuestionList.vue'
import QuestionDetailDialog from './QuestionDetailDialog.vue'
import QuestionEditDialog from './QuestionEditDialog.vue'
import { questionApi } from '@/api/question'
import { useCatalogStore } from '@/stores/catalog'
import { useAppConfigStore } from '@/stores/appConfig'
import { useReviewCountStore } from '@/stores/reviewCount'
import { use_is_mobile } from '@/composables/useIsMobile'
import { change_subject, empty_filters, enter_with_route, list_params, route_filter_key } from './questionFilters'

const route = useRoute()
const router = useRouter()
const catalogStore = useCatalogStore()
const appConfigStore = useAppConfigStore()
const reviewCountStore = useReviewCountStore()
// 手机宽度用卡片和筛选抽屉，电脑用表格和筛选栏
const is_mobile = use_is_mobile()

// 筛选条件和页码放在一起，规则函数（questionFilters.js）直接改它
const state = reactive({ filters: empty_filters(), page: 1, limit: 20 })
const questions = ref({ total: 0, items: [] })
const loading = ref(false)
const subjects = ref([])
const tags = ref([])

// 各学科的知识模块（筛选项），同一学科只请求一次
const modules_by_subject = reactive({})
const option_requests = new Map()

/** 取某个学科的筛选项；已经取过（或正在取）就直接用那一次的结果；失败了下次再试 */
async function load_options(subject_id) {
  if (!subject_id) return
  if (!option_requests.has(subject_id)) {
    const request = questionApi.getFilterOptions(subject_id)
      .then(({ data }) => { modules_by_subject[subject_id] = data?.knowledge_modules || [] })
      .catch(error => {
        option_requests.delete(subject_id)
        console.error('获取筛选项失败:', error)
      })
    option_requests.set(subject_id, request)
  }
  await option_requests.get(subject_id)
}

// 每次查询编个号：筛选连着改时，只用最后一次查询的结果，避免旧结果盖掉新结果
let fetch_serial = 0

/** 按当前筛选和页码查列表 */
async function fetch_list() {
  const serial = ++fetch_serial
  loading.value = true
  try {
    const { data } = await questionApi.list(list_params(state.filters, state.page, state.limit))
    if (serial === fetch_serial) questions.value = { total: data?.total || 0, items: data?.items || [] }
  } catch (error) {
    if (serial === fetch_serial) ElMessage.error(error.response?.data?.detail || '获取错题列表失败')
  } finally {
    if (serial === fetch_serial) loading.value = false
  }
}

const deps = { load_options, fetch_list }

/** 任何筛选变了：回到第 1 页再查 */
function refetch_from_first() {
  state.page = 1
  fetch_list()
}

/** 电脑上换学科：先清知识点再查（规则见 change_subject） */
function on_subject_change(subject_id) {
  change_subject(state, subject_id, deps)
}

/** 手机抽屉点了确定：整份草稿生效，回到第 1 页查询 */
function on_drawer_apply(next) {
  Object.assign(state.filters, next)
  refetch_from_first()
}

/** 按地址里的筛选进入：先取默认年级学期，再按规则取筛选项、套知识点、查列表 */
async function apply_route() {
  await appConfigStore.load()
  const defaults = { grade: appConfigStore.defaultGrade, semester: appConfigStore.defaultSemester }
  await enter_with_route(state, route.query, defaults, deps)
}

// 停在本页时地址里的筛选变了（比如从学情页又点了另一个考点进来）：重新套用。只切换标签不算。
let last_route_key = route_filter_key(route.query)
watch(() => route.query, query => {
  if (route.path !== '/questions') return
  const key = route_filter_key(query)
  if (key === last_route_key) return
  last_route_key = key
  apply_route()
})

/** 学科、标签从共用的目录 store 取 */
async function load_catalog() {
  try {
    subjects.value = [...await catalogStore.loadSubjects()]
  } catch (error) {
    console.error('获取学科失败:', error)
  }
  try {
    tags.value = [...await catalogStore.loadTags()]
  } catch (error) {
    console.error('获取标签失败:', error)
  }
}

// 详情和编辑弹窗
const detail_visible = ref(false)
const detail_id = ref(null)
const edit_visible = ref(false)
const editing = ref(null)

/** 打开详情 */
function view_detail(row) {
  detail_id.value = row.id
  detail_visible.value = true
}

/** 打开编辑 */
function open_edit(row) {
  editing.value = row
  edit_visible.value = true
}

/** 给一道题生成一道相似题（会调一次模型） */
async function generate_similar(row) {
  try {
    await ElMessageBox.confirm('将为这道错题生成一道相似题，是否继续？', '生成相似题', {
      confirmButtonText: '生成', cancelButtonText: '取消', type: 'info',
    })
  } catch {
    return
  }
  try {
    await questionApi.generateSimilar(row.id)
    ElMessage.success('相似题已生成，在详情里可以看到')
    fetch_list()
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '生成失败')
  }
}

/** 删除一道题；删的是待核对的题时，刷新菜单和首页上的待核对数 */
async function remove_question(row) {
  try {
    await ElMessageBox.confirm('确定要删除这道错题吗？', '删除确认', {
      confirmButtonText: '删除', cancelButtonText: '取消', type: 'warning',
    })
  } catch {
    return
  }
  try {
    await questionApi.delete(row.id)
    ElMessage.success('已删除')
    if (row.review_status === 'pending') reviewCountStore.refresh()
    fetch_list()
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '删除失败')
  }
}

/** 出练习卷：去考点卷页，筛了学科就带上 */
function go_targeted() {
  const query = state.filters.subject_id ? { subject_id: state.filters.subject_id } : {}
  router.push({ path: '/targeted-paper', query })
}

onMounted(() => {
  load_catalog()
  apply_route()
})

// 从别的标签切回来时（标签页被缓存着）重新查一次，看到核对、删除后的最新结果
let activated_before = false
onActivated(() => {
  if (activated_before) fetch_list()
  activated_before = true
})
</script>

<style scoped>
.all-head { display: flex; align-items: center; justify-content: space-between; gap: 12px; margin-bottom: 12px; }
.all-total { color: var(--muted); font-size: 13px; }
.all-total b { color: var(--ink); font-size: 15px; }
.all-actions { display: flex; gap: 8px; }
.all-actions :deep(.el-button) { margin: 0; }
.all-plus { margin-right: 4px; }
.all-panel { padding: 18px 20px; border-radius: var(--r-lg); background: var(--surface); box-shadow: var(--shadow-1); }
.all-pagination { display: flex; justify-content: flex-end; margin-top: 16px; }

@media (max-width: 768px) {
  /* 手机：卡片本身是白底，外面不再套一层白板 */
  .all-panel { padding: 0; background: none; box-shadow: none; }
  .all-pagination { justify-content: center; }
}
</style>
