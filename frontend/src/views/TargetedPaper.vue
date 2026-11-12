<template>
  <div class="targeted-paper">
    <PageHeading title="出练习卷" description="按考点掌握情况挑题，打印出来给学生做。" />

    <!-- 1. 顶部小字：上一份考点卷、没批改的卷子数 -->
    <div class="paper-notes">
      <p v-if="lastPaperText" class="note-line">{{ lastPaperText }}</p>
      <p v-else-if="planData" class="note-line">这一科还没有出过考点卷。</p>
      <p v-if="openPaperCount > 0" class="note-line note-warn">还有 {{ openPaperCount }} 份没批改</p>
    </div>

    <!-- 2. 设置区：只在选题阶段显示 -->
    <el-card v-if="stage === 'setup'" class="settings-card" shadow="never">
      <div class="settings-grid">
        <label class="setting">
          <span class="setting-label">学科</span>
          <el-select v-model="subjectId" placeholder="选择学科" class="setting-subject" @change="onSubjectChange">
            <el-option v-for="s in subjects" :key="s.id" :label="s.name" :value="s.id" />
          </el-select>
        </label>
        <label class="setting">
          <span class="setting-label">题量</span>
          <el-input-number v-model="size" :min="SIZE_MIN" :max="SIZE_MAX" :step="1" step-strictly controls-position="right" />
        </label>
        <div class="setting">
          <span class="setting-label">分法</span>
          <el-radio-group v-model="mode">
            <el-radio-button v-for="(label, key) in MODE_LABELS" :key="key" :value="key">{{ label }}</el-radio-button>
          </el-radio-group>
        </div>
        <label class="setting">
          <span class="setting-label">其中抽查</span>
          <el-input-number v-model="spotCount" :min="0" :max="SIZE_MAX" :step="1" step-strictly controls-position="right" />
          <span class="setting-unit">道</span>
        </label>
        <div class="setting">
          <span class="setting-label">包含低年级的错题</span>
          <el-switch v-model="includeLower" />
        </div>
        <div class="setting setting-action">
          <el-button :loading="planLoading" @click="loadPlan">重新选题</el-button>
        </div>
      </div>
    </el-card>

    <!-- 3. 题目清单（选题阶段，可增删换） -->
    <el-card v-if="stage === 'setup'" v-loading="planLoading" class="list-card" shadow="never">
      <div v-if="planError" class="list-empty">{{ planError }}</div>
      <div v-else-if="planData && !planData.items.length" class="list-empty">这一科现在没有可以出的题</div>
      <template v-else-if="planData">
        <section v-for="group in planGroups" :key="group.module_id" class="module-group">
          <h3 class="module-title">{{ group.module_name || '未分模块' }}<span class="module-count">{{ group.items.length }} 道</span></h3>
          <div v-for="item in group.items" :key="item.question_id" class="item-row">
            <div class="item-main">
              <div class="item-stem"><MathText :text="item.stem" /></div>
              <div class="item-tags">
                <span class="point-name">{{ item.point_name }}</span>
                <el-tag size="small" :type="reasonTagType(item.reason)" effect="plain">{{ REASON_LABELS[item.reason] }}</el-tag>
                <el-tag size="small" :type="item.form === 'similar' ? 'primary' : 'info'">{{ FORM_LABELS[item.form] }}</el-tag>
                <el-tag v-if="item.has_figure" size="small" type="warning">有图</el-tag>
              </div>
            </div>
            <div class="item-actions">
              <el-button v-if="item.reason !== 'spot'" size="small" text :disabled="!canSwap(item)" @click="onSwap(item)">换一道</el-button>
              <el-button size="small" text type="danger" @click="onRemove(item)">删掉</el-button>
              <el-button size="small" text :disabled="!canToggleForm(item)" @click="onToggleForm(item)">
                {{ item.form === 'similar' ? '改成原题' : '改成相似题' }}
              </el-button>
            </div>
          </div>
        </section>
        <p v-if="planData.shortfall > 0" class="shortfall">能出的题不够，少出了 {{ planData.shortfall }} 道</p>
      </template>
    </el-card>

    <!-- 4. 底部：题数统计、卷子名称、生成并打印 -->
    <el-card v-if="stage === 'setup'" class="footer-card" shadow="never">
      <div class="footer-bar">
        <div class="summary">
          共 <b>{{ planSummary.total }}</b> 道题，涉及 <b>{{ planSummary.points }}</b> 个考点，其中 <b>{{ planSummary.similar }}</b> 道相似题要生成
        </div>
        <div class="footer-actions">
          <el-input v-model="paperName" placeholder="卷子名称（可不填，用默认名）" maxlength="60" clearable class="name-input" />
          <el-button type="primary" :disabled="!canCreate" :loading="creating" @click="onCreate">生成并打印</el-button>
        </div>
      </div>
    </el-card>

    <!-- 5. 准备相似题的进度 -->
    <el-card v-if="stage === 'preparing'" class="progress-card" shadow="never">
      <p class="progress-text">正在准备相似题 {{ prepareDone }} / {{ prepareTotal }}</p>
      <el-progress :percentage="preparePercent" :stroke-width="10" />
      <p class="progress-hint">每道相似题要等模型生成，请不要关闭页面。</p>
    </el-card>

    <!-- 6. 卷面预览（只读，只能换相似题） -->
    <template v-if="stage === 'preview'">
      <el-alert v-if="prepareError" type="error" :closable="false" show-icon class="prepare-alert">
        <template #title>{{ prepareError }}</template>
        <el-button size="small" type="primary" :loading="prepareRunning" @click="runPrepare">继续准备</el-button>
      </el-alert>
      <!-- 已经生成过 PDF 又换了相似题：提醒重新生成（后端按卷面内容的指纹判断，内容变了会重新渲染） -->
      <el-alert v-if="pdfStale" type="warning" :closable="false" show-icon class="prepare-alert"
        title="题目换过了，之前生成的 PDF 是旧题面。请点「生成 PDF」重新生成后再打印，否则纸上和手机批改页对不上。" />

      <el-card v-loading="previewLoading" class="list-card" shadow="never">
        <template #header>
          <div class="preview-header">
            <span class="preview-title">{{ paper?.name }}</span>
            <span class="preview-meta">共 {{ previewQuestions.length }} 道题</span>
          </div>
        </template>
        <section v-for="group in previewGroups" :key="group.module_id" class="module-group">
          <h3 class="module-title">{{ group.module_name || '未分模块' }}<span class="module-count">{{ group.items.length }} 道</span></h3>
          <div v-for="item in group.items" :key="item.id" class="item-row preview-row">
            <div class="item-main">
              <div class="preview-stem">
                <span class="item-number">{{ item.number }}.</span>
                <MathText :text="item.question_text" />
              </div>
              <div class="item-tags">
                <span class="point-name">{{ item.point_name }}</span>
                <el-tag size="small" :type="reasonTagType(item.reason)" effect="plain">{{ REASON_LABELS[item.reason] }}</el-tag>
                <el-tag size="small" :type="item.form === 'similar' ? 'primary' : 'info'">{{ FORM_LABELS[item.form] || '原题' }}</el-tag>
                <el-tag v-if="fallbackIds.has(item.id)" size="small" type="danger">相似题没生成成功，已改用原题</el-tag>
              </div>
              <!-- 相似题可展开看答案、解析和原题 -->
              <div v-if="isSimilarReady(item)" class="similar-box">
                <el-button size="small" text @click="toggleExpand(item.id)">
                  {{ expanded.has(item.id) ? '收起' : '看答案和解析' }}
                </el-button>
                <div v-if="expanded.has(item.id)" class="similar-detail">
                  <div class="detail-block"><span class="detail-label">答案</span><MathText :text="item.answer || '（无）'" /></div>
                  <div class="detail-block"><span class="detail-label">解析</span><MathText :text="item.explanation || '（无）'" /></div>
                  <div class="detail-block detail-original"><span class="detail-label">原题</span><MathText :text="item.original_question_text" /></div>
                </div>
              </div>
            </div>
            <div class="item-actions">
              <el-button
                v-if="isSimilarReady(item)"
                size="small"
                text
                :loading="rerollingId === item.id"
                :disabled="rerollingId !== null && rerollingId !== item.id"
                @click="onReroll(item)"
              >换一道相似题</el-button>
            </div>
          </div>
        </section>
      </el-card>

      <el-card class="footer-card" shadow="never">
        <div class="footer-bar">
          <div class="summary">卷子已经创建，题目不能再增删；想大改可以删掉重出。</div>
          <div class="footer-actions">
            <el-button type="danger" plain :loading="deleting" @click="onDeletePaper">删掉重出</el-button>
            <el-button type="primary" :loading="pdfLoading" :disabled="prepareRunning || !!prepareError" @click="onGeneratePdf">生成 PDF</el-button>
          </div>
        </div>
      </el-card>
    </template>
  </div>
</template>

<script setup>
// 出练习卷页（设计 11.1）：选题预览 → 创建 → 一道一道准备相似题 → 只读卷面预览 → 生成 PDF。
// 刷新页面不恢复没创建的清单。已创建、没批改的考点卷可以带 ?paper_id= 再打开（练习中心的"查看""生成 PDF"
// 会跳到这里）：没准备完的相似题接着准备，然后显示卷面预览。
import { ref, computed, watch, onMounted, onBeforeUnmount } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import PageHeading from '@/components/PageHeading.vue'
import MathText from '@/components/MathText.vue'
import { targetedApi } from '@/api/targeted'
import { questionApi } from '@/api/question'
import { loadStarmapSubjects } from '@/api/starmap'
import {
  REASON_LABELS, FORM_LABELS, MODE_LABELS, STATE_LABELS,
  groupByModule, swapItem, removeItem, toggleForm, createPayload, summary, canResume, pendingSimilarCount,
} from '@/composables/targetedPaper'

const SIZE_MIN = 1          // 题量下限
const SIZE_MAX = 90         // 题量上限
const SIZE_DEFAULT = 12     // 从没出过考点卷时预填的题量
const SPOT_DEFAULT = 1      // 抽查默认道数
const PLAN_DELAY = 400      // 设置停止变化多少毫秒后重新选题

const route = useRoute()

// ---------------- 设置区
const subjects = ref([])
const subjectId = ref(null)
const size = ref(SIZE_DEFAULT)
const mode = ref('spread')          // 每次打开默认均布
const spotCount = ref(SPOT_DEFAULT)
const includeLower = ref(false)

// ---------------- 选题结果
const stage = ref('setup')          // setup 选题、preparing 准备相似题、preview 卷面预览
const planData = ref(null)          // plan 接口的返回：items、reserve、shortfall、open_paper_count、last_paper
const planLoading = ref(false)
const planError = ref('')
const paperName = ref('')
const creating = ref(false)
let planSeq = 0                     // 选题请求的序号：只采用最后一次请求的结果
let planTimer = null                // 防抖计时器
let prefilling = false              // 正在按上一份卷子预填题量时，不触发防抖选题
let lastPlanKey = ''                // 最近一次选题用的设置，设置没变就不再重复选题

// ---------------- 已创建的卷子
const paper = ref(null)             // detail 接口返回的卷子
const prepareDone = ref(0)
const prepareTotal = ref(0)
const prepareRunning = ref(false)
const prepareError = ref('')
const fallbackIds = ref(new Set())  // 生成失败、已改用原题的题目行编号
const previewLoading = ref(false)
const expanded = ref(new Set())     // 展开了答案和解析的题目行编号
const rerollingId = ref(null)
const pdfLoading = ref(false)
const deleting = ref(false)
const pdfStale = ref(false)         // 已有 PDF 之后又换过相似题：PDF 是旧题面，要重新生成
let leaving = false                 // 离开页面后停止准备循环

const lastPaper = computed(() => planData.value?.last_paper || null)
const openPaperCount = computed(() => planData.value?.open_paper_count || 0)
const planGroups = computed(() => groupByModule(planData.value?.items || []))
const planSummary = computed(() => summary(planData.value || { items: [] }))
const canCreate = computed(() => !planLoading.value && !!planData.value?.items.length && !!subjectId.value)
const preparePercent = computed(() => (prepareTotal.value ? Math.round(prepareDone.value / prepareTotal.value * 100) : 100))

/** 顶部小字：上一份考点卷的出卷日期和状态，如"上一份考点卷：11月10日出，已批改 83%"。 */
const lastPaperText = computed(() => {
  const last = lastPaper.value
  if (!last) return ''
  let state = STATE_LABELS[last.state] || ''
  if (last.state === 'graded' && last.accuracy !== null && last.accuracy !== undefined) state += ` ${Math.round(last.accuracy)}%`
  return `上一份考点卷：${format_date(last.created_at)}出，${state}`
})

/** 卷面预览的题目：补上考点名和模块，供按模块分组。 */
const previewQuestions = computed(() => (paper.value?.questions || []).map(q => {
  const links = q.knowledge_points || []
  const link = links.find(k => k.id === q.knowledge_point_id) || links[0] || {}
  return { ...q, point_name: link.name || '', module_id: link.parent_id ?? 0, module_name: link.parent_name || '' }
}))
const previewGroups = computed(() => groupByModule(previewQuestions.value))

/** 把 '2026-11-10 08:00:00' 变成 '11月10日'。 */
function format_date(text) {
  const m = /(\d{4})-(\d{2})-(\d{2})/.exec(text || '')
  return m ? `${Number(m[2])}月${Number(m[3])}日` : ''
}

/** 从接口错误里取出给人看的说明。 */
function error_text(error, fallback) {
  const detail = error?.response?.data?.detail
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail) && detail[0]?.msg) return detail[0].msg
  return fallback
}

/** 入选原因标签的颜色。 */
function reasonTagType(reason) {
  return { new: 'danger', wrong: 'danger', redo: 'warning', consolidate: 'success', check: 'success', spot: 'info' }[reason] || 'info'
}

// ---------------- 选题

/** 调 plan 接口重新选题；只采用最后一次请求的结果，防止慢请求覆盖新结果。 */
async function loadPlan() {
  clearTimeout(planTimer)
  if (!subjectId.value || !size.value) return
  const seq = ++planSeq
  lastPlanKey = plan_key()
  planLoading.value = true
  planError.value = ''
  try {
    const { data } = await targetedApi.plan({
      subject_id: subjectId.value,
      size: size.value,
      mode: mode.value,
      spot_count: spotCount.value ?? 0,
      include_lower_grades: includeLower.value,
    })
    if (seq !== planSeq) return
    planData.value = { ...data, reserve: data.reserve || {} }
  } catch (error) {
    if (seq !== planSeq) return
    planData.value = null
    planError.value = error_text(error, '选题失败，请稍后再试')
  } finally {
    if (seq === planSeq) planLoading.value = false
  }
}

/** 当前设置拼成的字符串，用来判断设置有没有变。 */
function plan_key() {
  return JSON.stringify([subjectId.value, size.value, mode.value, spotCount.value, includeLower.value])
}

/** 设置停下 400 毫秒后再选题；设置和上次选题时一样就不重复调用。 */
function schedulePlan() {
  clearTimeout(planTimer)
  planTimer = setTimeout(() => {
    if (plan_key() !== lastPlanKey) loadPlan()
  }, PLAN_DELAY)
}

/** 换学科：题量预填这一科上一份考点卷的题数（没有就 12），然后选题。 */
async function onSubjectChange() {
  if (!subjectId.value) return
  clearTimeout(planTimer)
  prefilling = true
  let count = SIZE_DEFAULT
  try {
    const { data } = await targetedApi.status()
    const last = (data.subjects || []).find(s => s.subject_id === subjectId.value)?.last_paper
    if (last) {
      const { data: detail } = await targetedApi.detail(last.id)
      const total = detail.total_questions || detail.questions?.length || 0
      if (total) count = Math.min(SIZE_MAX, Math.max(SIZE_MIN, total))
    }
  } catch {
    // 取不到上一份卷子时用默认题量，不影响出卷
  }
  size.value = count
  prefilling = false
  await loadPlan()
}

// 改题量、分法、抽查数、低年级开关：防抖后重新选题
watch([size, mode, spotCount, includeLower], () => {
  if (prefilling || stage.value !== 'setup') return
  schedulePlan()
})

/** 题目在 planData.items 里的位置（分组后显示，操作时要换回原下标）。 */
function indexOf(item) {
  return planData.value.items.indexOf(item)
}

/** 能不能换一道：抽查题没有备选；同考点备选为空也不能换。 */
function canSwap(item) {
  return item.reason !== 'spot' && !!(planData.value?.reserve?.[item.point_id] || []).length
}

/** 能不能切换题面：验收和抽查的题只能是相似题。 */
function canToggleForm(item) {
  return !(item.form === 'similar' && (item.reason === 'check' || item.reason === 'spot'))
}

function onSwap(item) {
  planData.value = swapItem(planData.value, indexOf(item))
}

function onRemove(item) {
  planData.value = removeItem(planData.value, indexOf(item))
}

function onToggleForm(item) {
  planData.value = toggleForm(planData.value, indexOf(item))
}

// ---------------- 创建与准备相似题

/** 生成并打印：创建卷子，然后一道一道准备相似题。 */
async function onCreate() {
  if (!canCreate.value) return
  clearTimeout(planTimer)
  creating.value = true
  try {
    const { data } = await targetedApi.create(createPayload(subjectId.value, paperName.value.trim() || null, planData.value))
    paper.value = data
    // 要准备的相似题数：题面是相似题、还没挂相似题的行
    prepareTotal.value = pendingSimilarCount(data.questions)
    prepareDone.value = 0
    fallbackIds.value = new Set()
    expanded.value = new Set()
    stage.value = 'preparing'
  } catch (error) {
    ElMessage.error(error_text(error, '创建卷子失败'))
    return
  } finally {
    creating.value = false
  }
  await runPrepare()
}

/** 调一次 prepare；返回接口数据。 */
async function prepareOnce(fallback) {
  const { data } = await targetedApi.prepare(paper.value.id, fallback)
  return data
}

/**
 * 循环调用 prepare 直到 remaining 为 0。
 * 某一道失败：先自动再试一次；还失败就带 fallback 改成原题，并在那道题上标出来。
 * 连 fallback 也失败（卷子被删、已批改等）：停下来显示错误，可以点"继续准备"。
 */
async function runPrepare() {
  if (!paper.value || prepareRunning.value) return
  prepareRunning.value = true
  prepareError.value = ''
  stage.value = 'preparing'
  try {
    while (!leaving) {
      let result
      try {
        result = await prepareOnce(false)
      } catch {
        try {
          result = await prepareOnce(false)        // 自动再试一次
        } catch {
          result = await prepareOnce(true)         // 还失败：改用原题
          if (result.item_id) fallbackIds.value = new Set([...fallbackIds.value, result.item_id])
        }
      }
      if (result.item_id) prepareDone.value = Math.min(prepareTotal.value, prepareDone.value + 1)
      if (!result.remaining) break
      // 总数以接口为准（例如别处已经准备了几道）
      prepareTotal.value = Math.max(prepareTotal.value, prepareDone.value + result.remaining)
    }
  } catch (error) {
    prepareError.value = error_text(error, '准备相似题时出错，请稍后继续')
  } finally {
    prepareRunning.value = false
  }
  if (leaving) return
  await loadDetail()
  stage.value = 'preview'
}

/** 重新取卷子详情，刷新卷面预览。 */
async function loadDetail() {
  previewLoading.value = true
  try {
    const { data } = await targetedApi.detail(paper.value.id)
    paper.value = data
  } catch (error) {
    ElMessage.error(error_text(error, '读取卷子失败'))
  } finally {
    previewLoading.value = false
  }
}

// ---------------- 卷面预览

/** 这一行是不是已经挂好的相似题。 */
function isSimilarReady(item) {
  return item.form === 'similar' && !!item.similar_question_id && item.similar_text != null
}

/** 展开 / 收起答案和解析。 */
function toggleExpand(id) {
  const next = new Set(expanded.value)
  if (next.has(id)) next.delete(id)
  else next.add(id)
  expanded.value = next
}

/** 换一道相似题：成功后只更新这一行。 */
async function onReroll(item) {
  rerollingId.value = item.id
  try {
    const { data } = await targetedApi.reroll(paper.value.id, item.id)
    paper.value = {
      ...paper.value,
      questions: paper.value.questions.map(q => (q.id === item.id
        ? { ...q, similar_text: data.similar_text, question_text: data.similar_text, answer: data.similar_answer,
            similar_answer: data.similar_answer, explanation: data.explanation }
        : q)),
    }
    // 这份卷子已经生成过 PDF：提醒重新生成
    if (paper.value.pdf_path) pdfStale.value = true
    ElMessage.success('已换成新的相似题')
  } catch (error) {
    ElMessage.error(error_text(error, '换相似题失败，请再试一次'))
  } finally {
    rerollingId.value = null
  }
}

/** 生成 PDF 并在新窗口打开；先开空白窗口，避免等待后被浏览器拦截弹窗。 */
async function onGeneratePdf() {
  const win = window.open('', '_blank')
  pdfLoading.value = true
  try {
    const { data } = await targetedApi.generatePdf(paper.value.id)
    paper.value = { ...paper.value, pdf_path: data.pdf_url.replace('/uploads/', '') }
    pdfStale.value = false
    if (win) win.location.href = data.pdf_url
    else window.open(data.pdf_url, '_blank')
  } catch (error) {
    if (win) win.close()
    ElMessage.error(error_text(error, '生成 PDF 失败'))
  } finally {
    pdfLoading.value = false
  }
}

/** 删掉重出：确认后软删除这份卷子，回到选题。 */
async function onDeletePaper() {
  try {
    await ElMessageBox.confirm('删掉这份卷子后，里面的题会重新变成可选，可以重新出一份。确定删掉吗？', '删掉重出', {
      confirmButtonText: '删掉', cancelButtonText: '取消', type: 'warning',
    })
  } catch {
    return
  }
  deleting.value = true
  try {
    await questionApi.deletePracticeSet(paper.value.id)
    paper.value = null
    prepareError.value = ''
    pdfStale.value = false
    paperName.value = ''
    stage.value = 'setup'
    ElMessage.success('已删掉，可以重新出卷')
    await loadPlan()
  } catch (error) {
    ElMessage.error(error_text(error, '删除失败'))
  } finally {
    deleting.value = false
  }
}

// ---------------- 进入页面

/**
 * 带 ?paper_id= 打开：读这份卷子；是没批改的考点卷就进入准备阶段，
 * 准备循环在没有要准备的题时（remaining 为 0）直接显示卷面预览。返回是否成功接上。
 */
async function resumePaper(id) {
  try {
    const { data } = await targetedApi.detail(id)
    if (!canResume(data)) {
      ElMessage.warning(data.reviewed ? '这份卷子已经批改过，不能再改题面' : '这份卷子不是考点卷')
      return false
    }
    paper.value = data
    subjectId.value = data.subject_id
    prepareTotal.value = pendingSimilarCount(data.questions)
    prepareDone.value = 0
    fallbackIds.value = new Set()
    expanded.value = new Set()
    stage.value = 'preparing'
  } catch (error) {
    ElMessage.error(error_text(error, '读取卷子失败'))
    return false
  }
  await runPrepare()
  return true
}

onMounted(async () => {
  try {
    subjects.value = await loadStarmapSubjects()
  } catch {
    subjects.value = []
  }
  // 查询参数 paper_id：接着准备一份已创建的卷子，接上了就不用选题
  const paperId = Number(route.query.paper_id)
  if (paperId > 0 && await resumePaper(paperId)) return
  // 查询参数 subject_id 预选学科，没有或不在列表里就选第一科
  const wanted = Number(route.query.subject_id)
  subjectId.value = subjects.value.find(s => s.id === wanted)?.id ?? subjects.value[0]?.id ?? null
  if (subjectId.value) await onSubjectChange()
  else planError.value = '没有找到可以出卷的学科'
})

onBeforeUnmount(() => {
  leaving = true
  clearTimeout(planTimer)
})
</script>

<style scoped>
.targeted-paper {
  max-width: 1100px;
  margin: 0 auto;
}
.paper-notes {
  margin: -6px 0 12px;
}
.note-line {
  margin: 0 0 2px;
  font-size: 13px;
  color: var(--text-muted);
}
.note-warn {
  color: #b7791f;
}
.settings-card,
.list-card,
.footer-card,
.progress-card {
  margin-bottom: 14px;
}
.settings-grid {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 14px 24px;
}
.setting {
  display: flex;
  align-items: center;
  gap: 8px;
}
.setting-label {
  font-size: 13px;
  color: var(--text-secondary);
  white-space: nowrap;
}
.setting-unit {
  font-size: 13px;
  color: var(--text-secondary);
}
.setting-subject {
  width: 120px;
}
.setting-action {
  margin-left: auto;
}
.list-empty {
  padding: 36px 0;
  text-align: center;
  color: var(--text-muted);
}
.module-group + .module-group {
  margin-top: 18px;
}
.module-title {
  margin: 0 0 6px;
  font-size: 15px;
  color: var(--text-primary);
}
.module-count {
  margin-left: 8px;
  font-size: 12px;
  font-weight: normal;
  color: var(--text-muted);
}
.item-row {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
  padding: 10px 0;
  border-top: 1px solid var(--border-light);
}
.item-main {
  flex: 1;
  min-width: 0;
}
/* 题干最多两行（MathText 的行高是 1.9） */
.item-stem {
  max-height: 3.9em;
  overflow: hidden;
  font-size: 14px;
  line-height: 1.9;
  color: var(--text-primary);
}
.item-tags {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
  margin-top: 4px;
}
.point-name {
  font-size: 12px;
  color: var(--text-secondary);
}
.item-actions {
  display: flex;
  flex-shrink: 0;
  align-items: center;
}
.item-actions .el-button + .el-button {
  margin-left: 4px;
}
.shortfall {
  margin: 14px 0 0;
  font-size: 13px;
  color: #b7791f;
}
.footer-bar {
  display: flex;
  flex-wrap: wrap;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
}
.summary {
  font-size: 14px;
  color: var(--text-secondary);
}
.summary b {
  color: var(--text-primary);
}
.footer-actions {
  display: flex;
  align-items: center;
  gap: 10px;
}
.name-input {
  width: 260px;
}
.progress-text {
  margin: 0 0 12px;
  font-size: 15px;
  color: var(--text-primary);
}
.progress-hint {
  margin: 10px 0 0;
  font-size: 12px;
  color: var(--text-muted);
}
.prepare-alert {
  margin-bottom: 14px;
}
.preview-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 10px;
}
.preview-title {
  font-weight: 600;
}
.preview-meta {
  font-size: 13px;
  color: var(--text-muted);
}
.preview-stem {
  display: flex;
  gap: 6px;
  font-size: 14px;
  line-height: 1.9;
}
.item-number {
  flex-shrink: 0;
  font-weight: 600;
}
.similar-box {
  margin-top: 2px;
}
.similar-detail {
  margin-top: 4px;
  padding: 8px 12px;
  border-radius: 8px;
  background: #f6f7fb;
  font-size: 13px;
}
.detail-block {
  display: flex;
  gap: 8px;
  align-items: baseline;
}
.detail-block + .detail-block {
  margin-top: 4px;
}
.detail-label {
  flex-shrink: 0;
  font-weight: 600;
  color: var(--text-secondary);
}
.detail-original {
  color: var(--text-muted);
}

/* 手机宽度：设置项、题目操作、底部按钮各自占满一行 */
@media (max-width: 768px) {
  .settings-grid {
    gap: 12px;
  }
  .setting {
    width: 100%;
    justify-content: space-between;
  }
  .setting-action {
    margin-left: 0;
  }
  .setting-action .el-button {
    width: 100%;
  }
  .item-row {
    flex-direction: column;
    gap: 4px;
  }
  .item-actions {
    flex-wrap: wrap;
    margin-left: -8px;
  }
  .footer-actions {
    width: 100%;
    flex-wrap: wrap;
  }
  .footer-actions .el-button {
    flex: 1;
  }
  .name-input {
    width: 100%;
  }
  .detail-block {
    flex-direction: column;
    gap: 0;
  }
}
</style>
