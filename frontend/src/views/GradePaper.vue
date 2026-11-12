<template>
  <div class="grade-paper" v-loading="loading">
    <div class="paper-head">
      <RouterLink to="/grade" class="back-link"><el-icon><ArrowLeft /></el-icon>待批改</RouterLink>
      <h2 v-if="paper" class="paper-title">{{ paperLabel(paper) }}</h2>
      <p v-if="reviewedText && step !== 'result'" class="reviewed-line">{{ reviewedText }}</p>
    </div>

    <p v-if="loadError" class="page-empty">{{ loadError }}</p>
    <p v-else-if="paper && paper.source_type !== 'question'" class="page-empty">这份练习不在这里批改，请到练习中心处理。</p>

    <template v-else-if="paper">
      <!-- 第一步：拍照（可跳过） -->
      <section v-if="step === 'photo'" class="step-block">
        <h3 class="step-title">第一步 拍下学生做完的卷子</h3>
        <p class="step-hint">可以拍多张，也可以从相册选；照片会存进这份练习，以后在练习中心能看到。</p>

        <!-- 两个隐藏的选择框：一个直接调相机，一个从相册选 -->
        <input ref="cameraInput" class="hidden-input" type="file" accept="image/*" capture="environment" multiple @change="onPickFiles" />
        <input ref="albumInput" class="hidden-input" type="file" accept="image/*" multiple @change="onPickFiles" />

        <div class="photo-actions">
          <el-button type="primary" size="large" :loading="uploading" @click="cameraInput.click()">
            <el-icon><Camera /></el-icon>拍照
          </el-button>
          <el-button size="large" :disabled="uploading" @click="albumInput.click()">
            <el-icon><Picture /></el-icon>从相册选
          </el-button>
        </div>
        <p v-if="uploading" class="step-hint">{{ uploadText }}</p>

        <div v-if="images.length" class="photo-grid">
          <el-image
            v-for="(path, index) in images"
            :key="path"
            :src="'/uploads/' + path"
            :preview-src-list="images.map(p => '/uploads/' + p)"
            :initial-index="index"
            fit="cover"
            class="photo-item"
            preview-teleported
          />
        </div>

        <div class="step-footer">
          <el-button v-if="images.length" type="primary" size="large" :disabled="uploading" @click="step = 'mark'">下一步：点对错</el-button>
          <el-button v-else size="large" :disabled="uploading" @click="step = 'mark'">跳过</el-button>
        </div>
      </section>

      <!-- 第二步：点对错 -->
      <section v-else-if="step === 'mark'" class="step-block">
        <!-- 顶部固定的统计 -->
        <div class="mark-counter">
          <span>做错 <b class="wrong-count">{{ wrongCount }}</b> 道 / 共 {{ questions.length }} 道</span>
          <span v-if="skippedCount" class="skipped-note">（{{ skippedCount }} 道不计）</span>
          <el-button link type="primary" class="photo-link" @click="step = 'photo'">
            <el-icon><Camera /></el-icon>{{ images.length ? `照片 ${images.length}` : '拍照' }}
          </el-button>
        </div>
        <p class="step-hint">默认都算对。点一下变成错，再点一下变回对；长按或点右上角的小圆点可以看题目、标"没做"。</p>

        <div v-for="section in sections" :key="section.key" class="mark-section">
          <h4 v-if="section.title" class="section-title">{{ section.title }}</h4>
          <div class="square-grid">
            <div
              v-for="q in section.items"
              :key="q.id"
              class="square"
              :class="squareClass(q)"
              role="button"
              :aria-label="`第 ${q.number} 题 ${MARK_TEXTS[marks[q.id]] || ''}`"
              @click="onSquareClick(q)"
              @pointerdown="startPress(q)"
              @pointerup="cancelPress"
              @pointerleave="cancelPress"
              @pointercancel="cancelPress"
              @contextmenu.prevent
            >
              <span class="square-number">{{ q.number }}</span>
              <span class="square-state">{{ MARK_TEXTS[marks[q.id]] }}</span>
              <button class="square-more" type="button" aria-label="看题目" @click.stop="openDrawer(q)" @pointerdown.stop>
                <el-icon><MoreFilled /></el-icon>
              </button>
            </div>
          </div>
        </div>

        <div class="step-footer submit-bar">
          <el-button type="primary" size="large" class="submit-button" :loading="submitting" @click="submit">提交</el-button>
        </div>
      </section>

      <!-- 第三步：结果 -->
      <section v-else-if="step === 'result' && result" class="step-block">
        <h3 class="step-title">批改好了</h3>
        <div class="result-accuracy">
          <span class="result-label">正确率</span>
          <b>{{ result.accuracy === null || result.accuracy === undefined ? '—' : `${result.accuracy}%` }}</b>
        </div>

        <div v-if="betterPoints.length" class="result-group">
          <h4 class="result-heading better">变好的考点</h4>
          <p v-for="point in betterPoints" :key="point.id" class="result-line">{{ pointLine(point) }}</p>
        </div>
        <div v-if="worsePoints.length" class="result-group">
          <h4 class="result-heading worse">变差的考点</h4>
          <p v-for="point in worsePoints" :key="point.id" class="result-line">{{ pointLine(point) }}</p>
        </div>

        <p v-if="result.newly_mastered > 0" class="result-line">
          <RouterLink to="/star-map" class="star-link"><el-icon><Star /></el-icon>点亮了 {{ result.newly_mastered }} 颗星</RouterLink>
        </p>
        <p v-if="result.graduated && result.graduated.length" class="result-line">第 {{ result.graduated.join('、') }} 题毕业了</p>
        <p v-if="resultWrongCount > 0" class="result-line result-note">做错的题会在下一份卷子里换成相似题再出现</p>

        <div class="step-footer">
          <el-button type="primary" size="large" @click="router.push('/grade')">返回待批改</el-button>
        </div>
      </section>
    </template>

    <!-- 底部抽屉：看一道题的题面、答案、解析，标"没做""题目有误"或恢复 -->
    <el-drawer v-model="drawerOpen" direction="btt" size="75%" :title="drawerQuestion ? `第 ${drawerQuestion.number} 题` : ''">
      <template v-if="drawerQuestion">
        <div class="drawer-block">
          <MathText :text="drawerQuestion.question_text || '（无题面）'" />
          <div v-if="optionList(drawerQuestion).length" class="drawer-options">
            <div v-for="option in optionList(drawerQuestion)" :key="option.key"><b>{{ option.key }}.</b> <MathText :text="option.text" /></div>
          </div>
        </div>
        <div class="drawer-block"><span class="drawer-label">答案</span><MathText :text="drawerQuestion.answer || '（无）'" /></div>
        <div class="drawer-block"><span class="drawer-label">解析</span><MathText :text="explanationOf(drawerQuestion) || '（无）'" /></div>
        <div class="drawer-actions">
          <el-button size="large" :type="marks[drawerQuestion.id] === 'not_done' ? 'info' : ''" @click="setMark(drawerQuestion, 'not_done')">没做</el-button>
          <el-button size="large" :type="marks[drawerQuestion.id] === 'bad_question' ? 'info' : ''" @click="setMark(drawerQuestion, 'bad_question')">题目有误</el-button>
          <el-button size="large" @click="setMark(drawerQuestion, 'right')">恢复</el-button>
        </div>
      </template>
    </el-drawer>
  </div>
</template>

<script setup>
// 批改一份卷子（设计 8.2、8.3）：拍照（可跳过）→ 点对错 → 提交看结果。
// 按手机 390 宽设计，电脑上也能用。已批改的卷子直接从第二步开始，可以修改后再提交。
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { ArrowLeft, Camera, Picture, MoreFilled, Star } from '@element-plus/icons-vue'
import MathText from '@/components/MathText.vue'
import { targetedApi } from '@/api/targeted'
import { questionApi } from '@/api/question'
import { statusText } from '@/components/starmap/starmapColors.js'
import { shrink_image } from '@/composables/scanPage'
import {
  initialMarks, toggleMark, gradePayload, countWrong, paperLabel, groupByModule,
} from '@/composables/targetedPaper'

const PHOTO_MAX_SIDE = 1600    // 照片压缩后的长边像素
const PHOTO_QUALITY = 0.8      // 照片压缩的 JPEG 质量
const UPLOAD_BATCH = 10        // 上传接口一次最多收 10 张
const LONG_PRESS_MS = 500      // 按住多久算长按
const CLICK_GUARD_MS = 400     // 长按触发后这么久内到达的 click 算长按松手，不切换对错
const STALE_TEXT = '这份卷子刚被批改过，已为你刷新'
// 方格里显示的状态文字
const MARK_TEXTS = { right: '对', wrong: '错', not_done: '没做', bad_question: '有误' }
// 考点状态的先后，用来判断变好还是变差
const STATUS_RANK = { unlearned: 0, weak: 1, fair: 2, good: 3, mastered: 4 }

const route = useRoute()
const router = useRouter()

const paper = ref(null)          // 卷子详情
const loading = ref(false)
const loadError = ref('')
const step = ref('photo')        // photo 拍照 / mark 点对错 / result 结果
const marks = ref({})            // {题目行编号: right / wrong / not_done / bad_question}
const revision = ref(0)          // 进入时读到的批改版本号，提交时带上
const result = ref(null)         // 提交后的结果
const resultWrongCount = ref(0)  // 提交时做错的题数
const submitting = ref(false)

const cameraInput = ref(null)
const albumInput = ref(null)
const uploading = ref(false)
const uploadText = ref('')

const drawerOpen = ref(false)
const drawerQuestion = ref(null)

let pressTimer = null     // 长按计时器
// 上一次长按触发的时间。只看时间、不留开关：松手如果落在抽屉遮罩上，方格收不到 click，
// 用开关的话会一直留着，把下一次正常点击吞掉；用时间窗口过了就自动失效。
let pressFiredAt = 0

const questions = computed(() => paper.value?.questions || [])
const images = computed(() => paper.value?.review_images || [])
const wrongCount = computed(() => countWrong(marks.value))
const skippedCount = computed(() => Object.values(marks.value).filter(m => m === 'not_done' || m === 'bad_question').length)

/** 顶部"已于 M 月 D 日 HH:mm 批改"；没批改过返回空串。 */
const reviewedText = computed(() => {
  if (!paper.value?.reviewed) return ''
  const m = /(\d{4})-(\d{2})-(\d{2})[ T](\d{2}):(\d{2})/.exec(paper.value.last_reviewed_at || '')
  return m ? `已于 ${Number(m[2])} 月 ${Number(m[3])} 日 ${m[4]}:${m[5]} 批改` : '已批改'
})

/**
 * 题号方格按模块分段：模块取这道题出卷时选中的考点（knowledge_point_id），
 * 找不到时用主考点；整份卷子都没有考点（旧卷子）就不分段。
 */
const sections = computed(() => {
  const list = questions.value
  if (!list.some(q => (q.knowledge_points || []).length)) {
    return [{ key: 'all', title: '', items: list }]
  }
  const rows = list.map(q => {
    const points = q.knowledge_points || []
    const picked = points.find(p => p.id === q.knowledge_point_id) || points.find(p => p.is_primary) || points[0]
    return {
      module_id: picked ? picked.parent_id : null,
      module_name: picked ? picked.parent_name : null,
      question: q,
    }
  })
  return groupByModule(rows).map(group => ({
    key: String(group.module_id),
    title: group.module_name || '其他',
    items: group.items.map(row => row.question),
  }))
})

/** 结果里变好的考点（状态升级，或状态不变但掌握度升高）。 */
const betterPoints = computed(() => (result.value?.points || []).filter(p => pointDelta(p) > 0))
/** 结果里变差的考点。 */
const worsePoints = computed(() => (result.value?.points || []).filter(p => pointDelta(p) < 0))

/** 把接口错误转成提示文字，取不到时用 fallback。 */
function error_text(error, fallback) {
  const detail = error?.response?.data?.detail
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail) && detail[0]?.msg) return detail[0].msg
  return fallback
}

/** 读取卷子详情并按库里的结果重置标记；first 为 true 时按批改与否决定从哪一步开始。 */
async function load_detail(first = false) {
  loading.value = true
  loadError.value = ''
  try {
    const { data } = await targetedApi.detail(route.params.id)
    paper.value = data
    marks.value = initialMarks(data.questions)
    revision.value = data.grading_revision || 0
    if (first) step.value = data.reviewed ? 'mark' : 'photo'
  } catch (error) {
    loadError.value = error?.response?.status === 404 ? '这份卷子不存在或已删除' : error_text(error, '读取卷子失败')
  } finally {
    loading.value = false
  }
}

// ---------------------------------------------------------------- 拍照

/** 选好照片：逐张压缩（长边 1600、质量 0.8），分批上传，再把路径存进这份练习。 */
async function onPickFiles(event) {
  const files = Array.from(event.target.files || [])
  event.target.value = ''  // 清空，下次选同一张也能触发
  if (!files.length || uploading.value) return
  uploading.value = true
  try {
    const shrunk = []
    for (let i = 0; i < files.length; i += 1) {
      uploadText.value = `正在压缩第 ${i + 1}/${files.length} 张`
      try {
        shrunk.push(await shrink_image(files[i], PHOTO_MAX_SIDE, PHOTO_QUALITY))
      } catch (error) {
        // 浏览器解不开这种图片（比如部分 HEIC）就传原图，交给后端判断
        console.error('压缩照片失败，改传原图:', error)
        shrunk.push(files[i])
      }
    }
    const paths = []
    let failed = 0
    for (let i = 0; i < shrunk.length; i += UPLOAD_BATCH) {
      uploadText.value = `正在上传 ${Math.min(i + UPLOAD_BATCH, shrunk.length)}/${shrunk.length} 张`
      const { data } = await targetedApi.uploadImages(shrunk.slice(i, i + UPLOAD_BATCH))
      for (const item of data.images || []) {
        if (item.success) paths.push(item.image_path)
        else failed += 1
      }
    }
    if (paths.length) {
      const all = [...images.value, ...paths]
      const { data } = await questionApi.updatePracticeSetReviewImages(paper.value.id, all)
      paper.value = { ...paper.value, review_images: data.review_images || all }
    }
    if (failed) ElMessage.warning(`有 ${failed} 张照片没传上去，可以再试一次`)
    else ElMessage.success(`已保存 ${paths.length} 张照片`)
  } catch (error) {
    ElMessage.error(error_text(error, '上传照片失败，请再试一次'))
  } finally {
    uploading.value = false
    uploadText.value = ''
  }
}

// ---------------------------------------------------------------- 点对错

/** 方格的颜色：对绿、错红、没做和题目有误灰。 */
function squareClass(q) {
  const mark = marks.value[q.id] || 'right'
  return mark === 'right' ? 'is-right' : mark === 'wrong' ? 'is-wrong' : 'is-skipped'
}

/** 点一下方格：对 <-> 错（灰色的回到对）；刚长按过就不切换。 */
function onSquareClick(q) {
  if (Date.now() - pressFiredAt < CLICK_GUARD_MS) return
  marks.value = { ...marks.value, [q.id]: toggleMark(marks.value[q.id] || 'right') }
}

/** 按下方格开始计时，按满 LONG_PRESS_MS 打开抽屉。 */
function startPress(q) {
  cancelPress()
  pressFiredAt = 0  // 新的一次按下，之前的长按不再影响
  pressTimer = setTimeout(() => {
    pressTimer = null
    pressFiredAt = Date.now()
    openDrawer(q)
  }, LONG_PRESS_MS)
}

/** 松手或移开时取消长按计时。 */
function cancelPress() {
  if (pressTimer) clearTimeout(pressTimer)
  pressTimer = null
}

/** 打开一道题的抽屉。 */
function openDrawer(q) {
  drawerQuestion.value = q
  drawerOpen.value = true
}

/** 抽屉里的按钮：标"没做""题目有误"，或恢复成对，然后关掉抽屉。 */
function setMark(q, mark) {
  marks.value = { ...marks.value, [q.id]: mark }
  drawerOpen.value = false
}

/** 选择题的选项列表（没有选项返回空数组）。 */
function optionList(q) {
  return ['a', 'b', 'c', 'd']
    .filter(key => q[`option_${key}`])
    .map(key => ({ key: key.toUpperCase(), text: q[`option_${key}`] }))
}

/** 解析：相似题用它自己的解析，原题用错题的分析。 */
function explanationOf(q) {
  return q.form === 'similar' ? (q.explanation || q.analysis) : (q.analysis || q.explanation)
}

/** 提交批改；409 说明别人刚改过，提示后刷新成最新结果。 */
async function submit() {
  if (submitting.value) return
  submitting.value = true
  try {
    const payload = gradePayload(questions.value, marks.value, revision.value)
    const { data } = await targetedApi.grade(paper.value.id, payload)
    resultWrongCount.value = wrongCount.value
    result.value = data
    revision.value = data.grading_revision ?? revision.value + 1
    step.value = 'result'
    window.scrollTo(0, 0)
  } catch (error) {
    if (error?.response?.status === 409) {
      // 不管后端给的是哪种 409 文字，都按"别人刚批改过"处理：刷新详情、重置标记
      ElMessage.warning(STALE_TEXT)
      await load_detail()
      step.value = 'mark'
    } else {
      ElMessage.error(error_text(error, '提交失败，请再试一次'))
    }
  } finally {
    submitting.value = false
  }
}

// ---------------------------------------------------------------- 结果

/** 一个考点前后的变化方向：先比状态，状态相同再比掌握度；正数变好，负数变差。 */
function pointDelta(point) {
  const before = STATUS_RANK[point.before?.status] ?? 0
  const after = STATUS_RANK[point.after?.status] ?? 0
  if (before !== after) return after - before
  return (point.after?.value ?? -1) - (point.before?.value ?? -1)
}

/** 考点变化的一行文字，如"有理数加减：一般 → 较好"；状态没变时补上掌握度。 */
function pointLine(point) {
  const before = statusText(point.before?.status) || '—'
  const after = statusText(point.after?.status) || '—'
  if (before !== after) return `${point.name}：${before} → ${after}`
  const percent = value => (value === null || value === undefined ? '—' : `${Math.round(value * 100)}%`)
  return `${point.name}：仍是${after}（${percent(point.before?.value)} → ${percent(point.after?.value)}）`
}

onMounted(() => load_detail(true))
onBeforeUnmount(cancelPress)
</script>

<style scoped>
.grade-paper {
  max-width: 640px;
  margin: 0 auto;
  min-height: 200px;
}

.paper-head {
  margin-bottom: 12px;
}

.back-link {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 14px;
  color: var(--el-color-primary);
  text-decoration: none;
}

.paper-title {
  margin: 8px 0 2px;
  font-size: 18px;
  font-weight: 600;
}

.reviewed-line {
  margin: 0;
  font-size: 13px;
  color: var(--el-text-color-secondary);
}

.page-empty {
  padding: 30px 0;
  text-align: center;
  color: var(--el-text-color-secondary);
}

.step-title {
  margin: 4px 0 6px;
  font-size: 16px;
  font-weight: 600;
}

.step-hint {
  margin: 0 0 12px;
  font-size: 13px;
  line-height: 1.6;
  color: var(--el-text-color-secondary);
}

.step-footer {
  display: flex;
  justify-content: center;
  gap: 12px;
  margin-top: 24px;
}

/* ---------- 拍照 ---------- */
.hidden-input {
  display: none;
}

.photo-actions {
  display: flex;
  gap: 12px;
  margin-bottom: 12px;
}

.photo-actions .el-button {
  flex: 1;
  height: 52px;
  font-size: 16px;
}

.photo-actions .el-icon {
  margin-right: 6px;
}

.photo-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 8px;
}

.photo-item {
  width: 100%;
  aspect-ratio: 3 / 4;
  border-radius: 8px;
  background: var(--el-fill-color-light);
}

/* ---------- 点对错 ---------- */
.mark-counter {
  position: sticky;
  top: 0;
  z-index: 5;
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 4px 8px;
  padding: 10px 12px;
  margin-bottom: 8px;
  border-radius: 10px;
  background: var(--el-bg-color);
  border: 1px solid var(--el-border-color-lighter);
  font-size: 16px;
}

.wrong-count {
  font-size: 20px;
  color: var(--el-color-danger);
}

.skipped-note {
  font-size: 13px;
  color: var(--el-text-color-secondary);
}

.photo-link {
  margin-left: auto;
}

.mark-section {
  margin-bottom: 14px;
}

.section-title {
  margin: 0 0 8px;
  font-size: 14px;
  font-weight: 600;
  color: var(--el-text-color-regular);
}

/* 390 宽的手机一行放 5 个大方格 */
.square-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(62px, 1fr));
  gap: 8px;
}

.square {
  position: relative;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  aspect-ratio: 1;
  border-radius: 10px;
  color: #fff;
  cursor: pointer;
  user-select: none;
  -webkit-user-select: none;
  -webkit-touch-callout: none;
  touch-action: manipulation;
  transition: background-color 0.12s;
}

.square.is-right {
  background: var(--el-color-success);
}

.square.is-wrong {
  background: var(--el-color-danger);
}

.square.is-skipped {
  background: var(--el-color-info-light-5);
  color: var(--el-text-color-primary);
}

.square-number {
  font-size: 22px;
  font-weight: 700;
  line-height: 1.1;
}

.square-state {
  font-size: 12px;
  opacity: 0.9;
}

/* 方格右上角的小按钮：点了打开抽屉 */
.square-more {
  position: absolute;
  top: 2px;
  right: 2px;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 22px;
  height: 22px;
  padding: 0;
  border: none;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.3);
  color: inherit;
  font-size: 12px;
  cursor: pointer;
}

/* 提交按钮贴在屏幕底部，长卷子不用滑到底；
   手机上底部导航是 fixed（约 61px 加安全区），要留出这段高度才不会被盖住 */
.submit-bar {
  position: sticky;
  bottom: 0;
  z-index: 5;
  padding: 10px 0;
  background: var(--bg-secondary, var(--el-bg-color-page));
}

@media (max-width: 768px) {
  .submit-bar {
    bottom: calc(62px + env(safe-area-inset-bottom));
  }
}

.submit-button {
  width: 100%;
  max-width: 360px;
  height: 52px;
  font-size: 17px;
}

/* ---------- 抽屉 ---------- */
.drawer-block {
  margin-bottom: 14px;
  line-height: 1.7;
}

.drawer-label {
  display: block;
  margin-bottom: 2px;
  font-size: 13px;
  color: var(--el-text-color-secondary);
}

.drawer-options {
  margin-top: 6px;
}

.drawer-actions {
  display: flex;
  gap: 10px;
  margin-top: 18px;
}

.drawer-actions .el-button {
  flex: 1;
  margin: 0;
}

/* ---------- 结果 ---------- */
.result-accuracy {
  display: flex;
  align-items: baseline;
  gap: 10px;
  margin: 8px 0 16px;
}

.result-accuracy b {
  font-size: 36px;
  color: var(--el-color-primary);
}

.result-label {
  font-size: 14px;
  color: var(--el-text-color-secondary);
}

.result-group {
  margin-bottom: 12px;
}

.result-heading {
  margin: 0 0 6px;
  font-size: 14px;
  font-weight: 600;
}

.result-heading.better {
  color: var(--el-color-success);
}

.result-heading.worse {
  color: var(--el-color-danger);
}

.result-line {
  margin: 0 0 6px;
  font-size: 15px;
  line-height: 1.6;
}

.result-note {
  color: var(--el-text-color-secondary);
  font-size: 14px;
}

.star-link {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  color: var(--el-color-warning);
  font-weight: 600;
  text-decoration: none;
}
</style>
