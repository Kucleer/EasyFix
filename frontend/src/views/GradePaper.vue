<template>
  <div class="grade-paper" :class="{ 'is-wide': wideReview }" v-loading="loading">
    <div class="paper-head">
      <RouterLink to="/practice-sets" class="back-link"><el-icon><ArrowLeft /></el-icon>练习中心</RouterLink>
      <h2 v-if="paper" class="paper-title">{{ paperLabel(paper) }}</h2>
      <p v-if="reviewedText && step !== 'result'" class="reviewed-line">{{ reviewedText }}</p>
    </div>

    <p v-if="loadError" class="page-empty">{{ loadError }}</p>
    <p v-else-if="paper && isOtherKind" class="page-empty">这份练习不在这里批改，请到练习中心处理。</p>

    <template v-else-if="paper">
      <!-- 第一步：拍照（可跳过识别） -->
      <section v-if="step === 'photo'" class="step-block">
        <h3 class="step-title">第一步 拍下学生做完的卷子</h3>
        <p class="step-hint">请在用红笔批改前拍照：系统读出孩子写的答案，先替你批一轮，你再复核。可以拍多张，也可以从相册选。</p>
        <p v-if="numberingWarn" class="warn-line">{{ NUMBERING_TEXT }}</p>

        <!-- 两个隐藏的选择框：一个直接调相机，一个从相册（电脑上是文件）选 -->
        <input ref="cameraInput" class="hidden-input" type="file" accept="image/*" capture="environment" multiple @change="onPickFiles" />
        <input ref="albumInput" class="hidden-input" type="file" accept="image/*" multiple @change="onPickFiles" />

        <!-- 电脑上：点按钮选文件，也可以把图片拖进这一块 -->
        <div
          v-if="isWide"
          class="drop-zone"
          :class="{ 'is-over': dragOver }"
          @dragover.prevent="dragOver = true"
          @dragleave.prevent="dragOver = false"
          @drop.prevent="onDropFiles"
        >
          <el-icon class="drop-icon"><Upload /></el-icon>
          <p>把卷子照片拖到这里，或者</p>
          <el-button type="primary" :loading="uploading" @click="albumInput.click()">选择图片</el-button>
        </div>
        <div v-else class="photo-actions">
          <el-button type="primary" size="large" :loading="uploading" @click="cameraInput.click()">
            <el-icon><Camera /></el-icon>拍照
          </el-button>
          <el-button size="large" :disabled="uploading" @click="albumInput.click()">
            <el-icon><Picture /></el-icon>从相册选
          </el-button>
        </div>
        <p v-if="uploading" class="step-hint">{{ uploadText }}</p>

        <div v-if="images.length" class="photo-grid">
          <div v-for="(path, index) in images" :key="path" class="photo-cell">
            <el-image
              :src="'/uploads/' + path"
              :preview-src-list="imageUrls"
              :initial-index="index"
              fit="cover"
              class="photo-item"
              preview-teleported
            />
            <span class="photo-no">第 {{ index + 1 }} 页</span>
            <button class="photo-remove" type="button" aria-label="删掉这张" :disabled="uploading" @click="removeImage(index)">
              <el-icon><Close /></el-icon>
            </button>
          </div>
        </div>

        <div class="step-footer">
          <template v-if="images.length">
            <el-button size="large" :disabled="uploading" @click="skipRecognition">跳过识别</el-button>
            <el-button type="primary" size="large" :disabled="uploading || numberingWarn" @click="startRecognition(false)">开始识别</el-button>
          </template>
          <el-button v-else size="large" :disabled="uploading" @click="skipRecognition">不拍照，直接批改</el-button>
        </div>
      </section>

      <!-- 第二步：识别和预批（进度条） -->
      <section v-else-if="step === 'recognize'" class="step-block recognize-block">
        <h3 class="step-title">{{ recognizeAsReference ? '重新识别（结果只作参考）' : '第二步 识别和预批' }}</h3>
        <el-progress :percentage="progressPercent" :stroke-width="14" :show-text="false" class="recognize-bar" />
        <p class="recognize-text">{{ progressText }}</p>
        <p class="step-hint">一页大约十几秒，请留在这个页面上等。</p>
        <div class="step-footer">
          <el-button size="large" @click="cancelRecognition">取消，手动批改</el-button>
        </div>
      </section>

      <!-- 第三步：复核 -->
      <section v-else-if="step === 'review'" class="step-block">
        <div class="review-layout">
          <div class="review-main">
            <!-- 顶部固定的统计和筛选 -->
            <div class="mark-counter">
              <span>错 <b class="wrong-count">{{ wrongCount }}</b></span>
              <span v-if="unsureCount" class="unsure-text">拿不准 <b>{{ unsureCount }}</b></span>
              <span>共 {{ questions.length }}</span>
              <span v-if="skippedCount" class="skipped-note">（{{ skippedCount }} 道不计）</span>
              <span class="counter-actions">
                <el-switch v-if="focus.size" v-model="onlyFocus" size="small" active-text="只看错的和拿不准的" />
                <el-button v-if="images.length && !numberingWarn" link type="primary" @click="startRecognition(paper.reviewed)">
                  <el-icon><Refresh /></el-icon>{{ recognition || paper.reviewed ? '重新识别' : '识别' }}
                </el-button>
                <el-button link type="primary" @click="step = 'photo'">
                  <el-icon><Camera /></el-icon>{{ images.length ? `照片 ${images.length}` : '拍照' }}
                </el-button>
              </span>
            </div>
            <p v-if="numberingWarn" class="warn-line">{{ NUMBERING_TEXT }}</p>
            <p v-if="recognizeAsReference && recognition" class="step-hint">识别结果只作参考，不会改动已提交的对错；要改请点每道题后面的按钮。</p>
            <p v-else-if="recognition" class="step-hint">已按识别结果预批。请对照标准答案和识别出的答案复核，黄色的"拿不准"要点成对或错。</p>
            <p v-else class="step-hint">默认都算对，点"错"标出做错的题；没做的题和题目有误的题在"更多"里标。</p>

            <p v-if="onlyFocus && !visibleList.length" class="page-empty">没有错的和拿不准的题</p>

            <div class="review-list">
              <div
                v-for="q in visibleList"
                :key="q.id"
                class="review-row"
                :class="[rowClass(q), { 'is-active': activeId === q.id }]"
                @click="selectRow(q)"
              >
                <div class="row-head">
                  <span class="row-number">{{ q.number }}</span>
                  <el-tag size="small" :type="shownForm(q) === 'similar' ? 'warning' : 'info'" effect="light">{{ FORM_LABELS[shownForm(q)] }}</el-tag>
                  <span v-if="recognized(q) && recognizeAsReference" class="ref-tag" :class="'ref-' + recognized(q).verdict">识别：{{ MARK_LABELS[recognized(q).verdict] }}</span>
                  <button v-if="!isWide && images.length" class="row-photo" type="button" @click.stop="openPhotoSheet(q)">
                    <el-icon><Picture /></el-icon>看照片
                  </button>
                </div>

                <div class="row-body">
                  <div class="row-question" :class="{ 'is-open': expanded.has(q.id) }" @click.stop="toggleExpand(q)">
                    <MathText :text="q.question_text || '（无题面）'" />
                  </div>
                  <div class="row-answers">
                    <div class="answer-line">
                      <span class="answer-label">标准答案</span>
                      <MathText class="answer-text" :text="q.answer || '（无）'" />
                    </div>
                    <div v-if="recognition" class="answer-line">
                      <span class="answer-label">孩子写的</span>
                      <MathText v-if="recognized(q)?.student_answer" class="answer-text child-answer" :text="recognized(q).student_answer" />
                      <span v-else class="answer-missing">没读到</span>
                    </div>
                  </div>
                </div>

                <div class="row-marks" @click.stop>
                  <button type="button" class="mark-btn btn-right" :class="{ on: marks[q.id] === 'right' }" @click="setMark(q, 'right')">对</button>
                  <button type="button" class="mark-btn btn-wrong" :class="{ on: marks[q.id] === 'wrong' }" @click="setMark(q, 'wrong')">错</button>
                  <span v-if="marks[q.id] === 'unsure'" class="mark-state state-unsure">拿不准</span>
                  <span v-else-if="isSkipped(q)" class="mark-state state-skipped">{{ MARK_LABELS[marks[q.id]] }}</span>
                  <el-dropdown trigger="click" @command="command => onMore(q, command)">
                    <button type="button" class="mark-btn btn-more" aria-label="更多"><el-icon><MoreFilled /></el-icon></button>
                    <template #dropdown>
                      <el-dropdown-menu>
                        <el-dropdown-item command="not_done">没做（不计入）</el-dropdown-item>
                        <el-dropdown-item command="bad_question">题目有误（不计入）</el-dropdown-item>
                        <el-dropdown-item command="detail" divided>看解析</el-dropdown-item>
                      </el-dropdown-menu>
                    </template>
                  </el-dropdown>
                </div>
              </div>
            </div>

            <div class="step-footer submit-bar">
              <p v-if="unsureCount" class="submit-note">还有 {{ unsureCount }} 道拿不准，点成对或错后才能提交</p>
              <el-button type="primary" size="large" class="submit-button" :disabled="unsureCount > 0" :loading="submitting" @click="submit">提交</el-button>
            </div>
          </div>

          <!-- 电脑宽屏：右边固定显示卷面照片 -->
          <aside v-if="isWide && images.length" class="photo-panel">
            <div class="panel-tabs">
              <button
                v-for="(path, index) in images"
                :key="path"
                type="button"
                class="panel-tab"
                :class="{ on: photoIndex === index }"
                @click="photoIndex = index"
              >第 {{ index + 1 }} 页</button>
            </div>
            <el-image
              :src="imageUrls[photoIndex]"
              :preview-src-list="imageUrls"
              :initial-index="photoIndex"
              fit="contain"
              class="panel-image"
              preview-teleported
            />
            <p class="panel-hint">点照片可以放大</p>
          </aside>
        </div>
      </section>

      <!-- 第四步：结果 -->
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
        <p v-if="resultWrongNumbers.length" class="result-line">做错的题：第 {{ resultWrongNumbers.join('、') }} 题，请在纸上圈出来让孩子订正</p>
        <p v-if="resultWrongNumbers.length && paper.kind === 'targeted'" class="result-line result-note">做错的题会在下一份卷子里换成相似题再出现</p>

        <div class="step-footer">
          <el-button size="large" @click="step = 'review'">再改改</el-button>
          <el-button type="primary" size="large" @click="router.push('/practice-sets')">返回练习中心</el-button>
        </div>
      </section>
    </template>

    <!-- 手机：从底部弹出卷面照片 -->
    <el-drawer v-model="photoSheetOpen" direction="btt" size="85%" :title="images.length ? `第 ${photoIndex + 1} / ${images.length} 页` : ''">
      <div v-if="images.length" class="sheet-body">
        <el-image
          :src="imageUrls[photoIndex]"
          :preview-src-list="imageUrls"
          :initial-index="photoIndex"
          fit="contain"
          class="sheet-image"
          preview-teleported
        />
        <div class="sheet-nav">
          <el-button :disabled="photoIndex === 0" @click="photoIndex -= 1">上一页</el-button>
          <span class="panel-hint">点照片可以放大</span>
          <el-button :disabled="photoIndex >= images.length - 1" @click="photoIndex += 1">下一页</el-button>
        </div>
      </div>
    </el-drawer>

    <!-- 一道题的题面、答案、解析 -->
    <el-drawer v-model="drawerOpen" :direction="isWide ? 'rtl' : 'btt'" :size="isWide ? '480px' : '75%'" :title="drawerQuestion ? `第 ${drawerQuestion.number} 题` : ''">
      <template v-if="drawerQuestion">
        <div class="drawer-block">
          <MathText :text="drawerQuestion.question_text || '（无题面）'" />
          <div v-if="optionList(drawerQuestion).length" class="drawer-options">
            <div v-for="option in optionList(drawerQuestion)" :key="option.key"><b>{{ option.key }}.</b> <MathText :text="option.text" /></div>
          </div>
        </div>
        <div class="drawer-block"><span class="drawer-label">答案</span><MathText :text="drawerQuestion.answer || '（无）'" /></div>
        <div class="drawer-block"><span class="drawer-label">解析</span><MathText :text="explanationOf(drawerQuestion) || '（无）'" /></div>
        <p class="step-hint">答案录错了：先标"题目有误"，批改完再去错题页改。</p>
      </template>
    </el-drawer>
  </div>
</template>

<script setup>
// 批改一份错题练习卷（考点卷和手动组的卷子都在这里批，设计 2026-11-12-grading-recognition-design.md）：
// 拍照 → 识别预批（进度条，可取消、失败自动改为手动）→ 复核 → 提交看结果。
// 宽度 ≥ 1024 按电脑排（左列表、右照片，可拖放照片），窄屏按手机排（卡片列表，点"看照片"弹出照片）。
// 识别出的孩子答案只在这次复核时显示，不保存；已批改的卷子直接进复核，不自动识别。
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { ArrowLeft, Camera, Picture, MoreFilled, Star, Upload, Close, Refresh } from '@element-plus/icons-vue'
import MathText from '@/components/MathText.vue'
import { targetedApi } from '@/api/targeted'
import { questionApi } from '@/api/question'
import { scanApi } from '@/api/scan'
import { statusText } from '@/components/starmap/starmapColors.js'
import { shrink_image } from '@/composables/scanPage'
import {
  FORM_LABELS, MARK_LABELS, initialMarks, gradePayload, countWrong, countUnsure, paperLabel,
  recognitionMap, marksFromRecognition, focusIds, visibleQuestions, shownForm, numberingChanged,
} from '@/composables/targetedPaper'

const PHOTO_MAX_SIDE = 1600    // 照片压缩后的长边像素
const PHOTO_QUALITY = 0.8      // 照片压缩的 JPEG 质量
const UPLOAD_BATCH = 10        // 上传接口一次最多收 10 张
const WIDE_QUERY = '(min-width: 1024px)'   // 按电脑排版的宽度
const STALE_TEXT = '这份卷子刚被批改过，已为你刷新'
const FALLBACK_TEXT = '识别没成功，已改为手动批改'
const NUMBERING_TEXT = '题号可能和纸上不一致（打印后删过题），这份卷子请对照纸上的题目手动批改'
// 考点状态的先后，用来判断变好还是变差
const STATUS_RANK = { unlearned: 0, weak: 1, fair: 2, good: 3, mastered: 4 }

const route = useRoute()
const router = useRouter()

const paper = ref(null)          // 卷子详情
const loading = ref(false)
const loadError = ref('')
const step = ref('photo')        // photo 拍照 / recognize 识别 / review 复核 / result 结果
const marks = ref({})            // {题目行编号: right / wrong / unsure / not_done / bad_question}
const revision = ref(0)          // 进入时读到的批改版本号，提交时带上
const result = ref(null)         // 提交后的结果
const resultWrongNumbers = ref([])  // 提交时做错的题号
const submitting = ref(false)

const cameraInput = ref(null)
const albumInput = ref(null)
const uploading = ref(false)
const uploadText = ref('')
const dragOver = ref(false)

// 识别：结果只在内存里，不存库
const recognition = ref(null)            // {题目行编号: {student_answer, verdict, page}}，没识别时为 null
const recognizeAsReference = ref(false)  // 已批改卷子的"重新识别"：只显示参考，不改对错
const progressDone = ref(0)              // 已完成的步骤数（每页一步 + 比对一步）
const progressText = ref('')
let recognizeController = null           // 用来取消正在进行的识别请求
let recognizeRun = 0                     // 每次识别的编号，取消或重来后旧的结果作废

// 复核列表
const focus = ref(new Set())     // "只看错的和拿不准的"名单，预批时定下
const onlyFocus = ref(false)
const expanded = ref(new Set())  // 展开了题目的题
const activeId = ref(null)       // 电脑上选中的题（右边照片跟着翻页）
const photoIndex = ref(0)        // 当前显示第几张照片
const photoSheetOpen = ref(false)
const drawerOpen = ref(false)
const drawerQuestion = ref(null)

// 屏幕宽度：≥ 1024 按电脑排
const isWide = ref(false)
let wideMedia = null
function updateWide() { isWide.value = !!wideMedia?.matches }

const questions = computed(() => paper.value?.questions || [])
const images = computed(() => paper.value?.review_images || [])
const imageUrls = computed(() => images.value.map(path => '/uploads/' + path))
const isOtherKind = computed(() => ['word', 'reading'].includes(paper.value?.source_type))
const numberingWarn = computed(() => numberingChanged(paper.value))
const wideReview = computed(() => isWide.value && step.value === 'review' && images.value.length > 0)
const wrongCount = computed(() => countWrong(marks.value))
const unsureCount = computed(() => countUnsure(marks.value))
const skippedCount = computed(() => Object.values(marks.value).filter(m => m === 'not_done' || m === 'bad_question').length)
const visibleList = computed(() => visibleQuestions(questions.value, focus.value, onlyFocus.value))
const progressTotal = computed(() => images.value.length + 1)
const progressPercent = computed(() => Math.round(progressDone.value / progressTotal.value * 100))

/** 顶部"已于 M 月 D 日 HH:mm 批改"；没批改过返回空串。 */
const reviewedText = computed(() => {
  if (!paper.value?.reviewed) return ''
  const m = /(\d{4})-(\d{2})-(\d{2})[ T](\d{2}):(\d{2})/.exec(paper.value.last_reviewed_at || '')
  return m ? `已于 ${Number(m[2])} 月 ${Number(m[3])} 日 ${m[4]}:${m[5]} 批改` : '已批改'
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
    clear_recognition()
    if (first) step.value = data.reviewed ? 'review' : 'photo'
  } catch (error) {
    loadError.value = error?.response?.status === 404 ? '这份卷子不存在或已删除' : error_text(error, '读取卷子失败')
  } finally {
    loading.value = false
  }
}

// ---------------------------------------------------------------- 拍照

/** 选好照片后上传（拍照、相册、电脑选文件共用）。 */
async function onPickFiles(event) {
  const files = Array.from(event.target.files || [])
  event.target.value = ''  // 清空，下次选同一张也能触发
  await upload_files(files)
}

/** 电脑上把图片拖进页面。只收图片文件。 */
async function onDropFiles(event) {
  dragOver.value = false
  const files = Array.from(event.dataTransfer?.files || []).filter(file => file.type.startsWith('image/'))
  if (!files.length) {
    ElMessage.warning('请拖入图片文件')
    return
  }
  await upload_files(files)
}

/** 逐张压缩（长边 1600、质量 0.8），分批上传，再把路径存进这份练习。 */
async function upload_files(files) {
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
    if (paths.length) await save_images([...images.value, ...paths])
    if (failed) ElMessage.warning(`有 ${failed} 张照片没传上去，可以再试一次`)
    else ElMessage.success(`已保存 ${paths.length} 张照片`)
  } catch (error) {
    ElMessage.error(error_text(error, '上传照片失败，请再试一次'))
  } finally {
    uploading.value = false
    uploadText.value = ''
  }
}

/** 把照片列表存进这份练习；照片变了，之前的识别结果就作废。 */
async function save_images(list) {
  const { data } = await questionApi.updatePracticeSetReviewImages(paper.value.id, list)
  paper.value = { ...paper.value, review_images: data.review_images || list }
  photoIndex.value = 0
  clear_recognition()
}

/** 删掉一张拍错的照片（只是不再关联到这份练习，文件本身保留）。 */
async function removeImage(index) {
  if (uploading.value) return
  uploading.value = true
  try {
    await save_images(images.value.filter((_, i) => i !== index))
  } catch (error) {
    ElMessage.error(error_text(error, '删除照片失败，请再试一次'))
  } finally {
    uploading.value = false
  }
}

/** 跳过识别：直接进复核，按库里的结果（没批改过就是默认全对）。 */
function skipRecognition() {
  clear_recognition()
  step.value = 'review'
}

// ---------------------------------------------------------------- 识别和预批

/** 清掉识别结果和筛选。 */
function clear_recognition() {
  recognition.value = null
  recognizeAsReference.value = false
  focus.value = new Set()
  onlyFocus.value = false
}

/**
 * 识别一遍：先查识别主机能不能用，再一页一页读图，全部读完后比对一次。
 * 每完成一步才发下一步的请求，进度条是真实的。
 * asReference 为真时（已批改的卷子"重新识别"）只显示参考结果，不改已提交的对错。
 * 任何一步失败都不卡住：提示后进复核，按手动批改处理。
 */
async function startRecognition(asReference) {
  const run = ++recognizeRun
  recognizeController = new AbortController()
  const signal = recognizeController.signal
  recognizeAsReference.value = !!asReference
  progressDone.value = 0
  progressText.value = '正在连接识别服务'
  step.value = 'recognize'
  const alive = () => run === recognizeRun   // 取消或重来后，这一轮的结果全部作废

  try {
    const { data } = await scanApi.health()
    if (!alive()) return
    if (!data?.available) return fall_back('识别服务现在不可用，已改为手动批改')
  } catch (error) {
    if (!alive()) return
    return fall_back('识别服务现在不可用，已改为手动批改')
  }

  const pages = []
  let failedPages = 0
  for (let index = 0; index < images.value.length; index += 1) {
    progressText.value = `正在识别第 ${index + 1} / ${images.value.length} 页`
    try {
      const { data } = await targetedApi.recognizePage(paper.value.id, index, signal)
      if (!alive()) return
      pages.push({ index, text: data.text })
    } catch (error) {
      if (!alive()) return
      failedPages += 1   // 这一页没读出来，接着读下一页
    }
    progressDone.value = index + 1
  }
  if (!pages.length) return fall_back(FALLBACK_TEXT)

  progressText.value = '正在比对答案'
  try {
    const { data } = await targetedApi.recognizeJudge(paper.value.id, pages, signal)
    if (!alive()) return
    progressDone.value = progressTotal.value
    apply_recognition(data.items || [], failedPages)
  } catch (error) {
    if (!alive()) return
    fall_back(error?.response?.status === 409 ? error_text(error, FALLBACK_TEXT) : FALLBACK_TEXT)
  }
}

/** 用识别结果预批（或作为参考显示），进入复核。 */
function apply_recognition(items, failedPages) {
  recognition.value = recognitionMap(items)
  if (!recognizeAsReference.value) {
    marks.value = marksFromRecognition(questions.value, items)
    focus.value = focusIds(marks.value)
    onlyFocus.value = focus.value.size > 0
  }
  if (failedPages) ElMessage.warning(`有 ${failedPages} 页没读出来，这些页上的题按"拿不准"处理`)
  step.value = 'review'
}

/** 识别没成功：提示，进入复核，按原来的方式（默认全对，或已提交的结果）手动批。 */
function fall_back(text) {
  ElMessage.warning(text)
  recognizeRun += 1
  clear_recognition()
  step.value = 'review'
}

/** 取消识别：中止正在等的请求，进入复核，按手动批改处理。 */
function cancelRecognition() {
  recognizeRun += 1
  recognizeController?.abort()
  clear_recognition()
  step.value = 'review'
}

// ---------------------------------------------------------------- 复核

/** 这道题的识别结果（没识别时为 undefined）。 */
function recognized(q) {
  return recognition.value?.[q.id]
}

/** 是不是"没做""题目有误"。 */
function isSkipped(q) {
  const mark = marks.value[q.id]
  return mark === 'not_done' || mark === 'bad_question'
}

/** 行的颜色：对绿、错红、拿不准黄、不计入灰。 */
function rowClass(q) {
  const mark = marks.value[q.id] || 'right'
  if (mark === 'right') return 'is-right'
  if (mark === 'wrong') return 'is-wrong'
  if (mark === 'unsure') return 'is-unsure'
  return 'is-skipped'
}

/** 改一道题的结果。 */
function setMark(q, mark) {
  marks.value = { ...marks.value, [q.id]: mark }
}

/** "更多"菜单：标没做、题目有误，或看解析。 */
function onMore(q, command) {
  if (command === 'detail') {
    drawerQuestion.value = q
    drawerOpen.value = true
  } else {
    setMark(q, command)
  }
}

/** 展开或收起题目全文。 */
function toggleExpand(q) {
  const next = new Set(expanded.value)
  if (next.has(q.id)) next.delete(q.id)
  else next.add(q.id)
  expanded.value = next
}

/** 照片跟着题目翻页：识别给出了这道题在第几页就翻过去。 */
function follow_page(q) {
  const page = recognized(q)?.page
  if (page && page <= images.value.length) photoIndex.value = page - 1
}

/** 电脑上点一行：选中它，右边照片翻到这道题所在的页。 */
function selectRow(q) {
  activeId.value = q.id
  follow_page(q)
}

/** 手机上点"看照片"：从底部弹出照片，翻到这道题所在的页。 */
function openPhotoSheet(q) {
  activeId.value = q.id
  follow_page(q)
  photoSheetOpen.value = true
}

/** 选择题的选项列表（没有选项返回空数组）。 */
function optionList(q) {
  return ['a', 'b', 'c', 'd']
    .filter(key => q[`option_${key}`])
    .map(key => ({ key: key.toUpperCase(), text: q[`option_${key}`] }))
}

/** 解析：相似题用它自己的解析，原题用错题的分析。 */
function explanationOf(q) {
  return shownForm(q) === 'similar' ? (q.explanation || q.analysis) : (q.analysis || q.explanation)
}

/** 提交批改；409 说明刚被批改过（比如另一个窗口），提示后刷新成最新结果。 */
async function submit() {
  if (submitting.value || unsureCount.value > 0) return
  submitting.value = true
  try {
    const payload = gradePayload(questions.value, marks.value, revision.value)
    const { data } = await targetedApi.grade(paper.value.id, payload)
    resultWrongNumbers.value = questions.value.filter(q => marks.value[q.id] === 'wrong').map(q => q.number)
    result.value = data
    revision.value = data.grading_revision ?? revision.value + 1
    paper.value = { ...paper.value, reviewed: true }
    recognizeAsReference.value = true   // 提交后再"再改改"，识别结果只作参考
    step.value = 'result'
    window.scrollTo(0, 0)
  } catch (error) {
    if (error?.response?.status === 409) {
      // 不管后端给的是哪种 409 文字，都按"刚被批改过"处理：刷新详情、重置标记
      ElMessage.warning(STALE_TEXT)
      await load_detail()
      step.value = 'review'
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

onMounted(() => {
  wideMedia = window.matchMedia(WIDE_QUERY)
  updateWide()
  wideMedia.addEventListener('change', updateWide)
  load_detail(true)
})

onBeforeUnmount(() => {
  wideMedia?.removeEventListener('change', updateWide)
  recognizeRun += 1
  recognizeController?.abort()   // 离开页面时不再继续识别
})
</script>

<style scoped>
.grade-paper {
  max-width: 640px;
  margin: 0 auto;
  min-height: 200px;
}

/* 电脑上复核时左列表右照片，放宽页面 */
.grade-paper.is-wide {
  max-width: 1320px;
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

.warn-line {
  margin: 0 0 12px;
  padding: 8px 12px;
  border-radius: 8px;
  font-size: 13px;
  line-height: 1.6;
  color: var(--el-color-warning-dark-2);
  background: var(--el-color-warning-light-9);
}

.step-footer {
  display: flex;
  flex-wrap: wrap;
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

.drop-zone {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  padding: 28px 16px;
  margin-bottom: 12px;
  border: 2px dashed var(--el-border-color);
  border-radius: 12px;
  color: var(--el-text-color-secondary);
  transition: border-color 0.15s, background-color 0.15s;
}

.drop-zone p {
  margin: 0;
}

.drop-zone.is-over {
  border-color: var(--el-color-primary);
  background: var(--el-color-primary-light-9);
}

.drop-icon {
  font-size: 32px;
}

.photo-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(110px, 1fr));
  gap: 8px;
}

.photo-cell {
  position: relative;
}

.photo-item {
  display: block;
  width: 100%;
  aspect-ratio: 3 / 4;
  border-radius: 8px;
  background: var(--el-fill-color-light);
}

.photo-no {
  position: absolute;
  left: 6px;
  bottom: 6px;
  padding: 1px 6px;
  border-radius: 6px;
  font-size: 12px;
  color: #fff;
  background: rgba(0, 0, 0, 0.5);
}

.photo-remove {
  position: absolute;
  top: 4px;
  right: 4px;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 26px;
  height: 26px;
  padding: 0;
  border: none;
  border-radius: 50%;
  color: #fff;
  background: rgba(0, 0, 0, 0.5);
  cursor: pointer;
}

/* ---------- 识别 ---------- */
.recognize-block {
  padding: 24px 0;
}

.recognize-bar {
  margin: 16px 0 10px;
}

.recognize-text {
  margin: 0 0 6px;
  font-size: 16px;
  font-weight: 600;
  text-align: center;
}

.recognize-block .step-hint {
  text-align: center;
}

/* ---------- 复核 ---------- */
.review-layout {
  display: block;
}

.is-wide .review-layout {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(360px, 46%);
  gap: 20px;
  align-items: start;
}

.mark-counter {
  position: sticky;
  top: 0;
  z-index: 5;
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 4px 12px;
  padding: 10px 12px;
  margin-bottom: 8px;
  border-radius: 10px;
  background: var(--el-bg-color);
  border: 1px solid var(--el-border-color-lighter);
  font-size: 15px;
}

.wrong-count {
  font-size: 20px;
  color: var(--el-color-danger);
}

.unsure-text b {
  font-size: 20px;
  color: var(--el-color-warning);
}

.skipped-note {
  font-size: 13px;
  color: var(--el-text-color-secondary);
}

.counter-actions {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 4px 12px;
  margin-left: auto;
}

.counter-actions .el-button {
  margin-left: 0;
}

.counter-actions .el-icon {
  margin-right: 2px;
}

.review-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

/* 每道题一张卡片（电脑上也是一行一张，左边一条颜色表示结果） */
.review-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  gap: 6px;
  padding: 10px 12px;
  border: 1px solid var(--el-border-color-lighter);
  border-left: 5px solid var(--el-color-success);
  border-radius: 10px;
  background: var(--el-bg-color);
}

.is-wide .review-row {
  grid-template-columns: minmax(0, 1fr) auto;
  grid-template-areas: 'head marks' 'body marks';
  align-items: center;
  cursor: pointer;
}

.is-wide .row-head { grid-area: head; }
.is-wide .row-body { grid-area: body; }
.is-wide .row-marks { grid-area: marks; }

.review-row.is-wrong {
  border-left-color: var(--el-color-danger);
  background: var(--el-color-danger-light-9);
}

.review-row.is-unsure {
  border-left-color: var(--el-color-warning);
  background: var(--el-color-warning-light-9);
}

.review-row.is-skipped {
  border-left-color: var(--el-color-info-light-5);
  opacity: 0.75;
}

.review-row.is-active {
  box-shadow: 0 0 0 2px var(--el-color-primary-light-5);
}

.row-head {
  display: flex;
  align-items: center;
  gap: 8px;
}

.row-number {
  min-width: 28px;
  font-size: 20px;
  font-weight: 700;
}

.ref-tag {
  font-size: 12px;
  padding: 1px 6px;
  border-radius: 6px;
  background: var(--el-fill-color);
}

.ref-tag.ref-wrong { color: var(--el-color-danger); }
.ref-tag.ref-right { color: var(--el-color-success); }
.ref-tag.ref-unsure { color: var(--el-color-warning-dark-2); }

.row-photo {
  display: inline-flex;
  align-items: center;
  gap: 2px;
  margin-left: auto;
  padding: 4px 8px;
  border: none;
  border-radius: 6px;
  font-size: 13px;
  color: var(--el-color-primary);
  background: transparent;
  cursor: pointer;
}

.row-body {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
}

/* 题目默认只露两行，点一下展开 */
.row-question {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  font-size: 14px;
  line-height: 1.6;
  color: var(--el-text-color-regular);
  cursor: pointer;
}

.row-question.is-open {
  display: block;
}

.row-answers {
  display: flex;
  flex-wrap: wrap;
  gap: 2px 18px;
}

.answer-line {
  display: flex;
  align-items: baseline;
  gap: 6px;
  min-width: 0;
  font-size: 15px;
}

.answer-label {
  flex: none;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.answer-text {
  min-width: 0;
  font-weight: 600;
  overflow-wrap: anywhere;
}

.child-answer {
  color: var(--el-color-primary-dark-2);
}

.answer-missing {
  font-size: 13px;
  color: var(--el-color-warning-dark-2);
}

.row-marks {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}

.mark-btn {
  min-width: 52px;
  height: 38px;
  padding: 0 12px;
  border: 1px solid var(--el-border-color);
  border-radius: 8px;
  font-size: 15px;
  color: var(--el-text-color-regular);
  background: var(--el-bg-color);
  cursor: pointer;
  touch-action: manipulation;
}

.mark-btn.btn-more {
  min-width: 38px;
  padding: 0;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

.mark-btn.btn-right.on {
  border-color: var(--el-color-success);
  color: #fff;
  background: var(--el-color-success);
}

.mark-btn.btn-wrong.on {
  border-color: var(--el-color-danger);
  color: #fff;
  background: var(--el-color-danger);
}

.mark-state {
  padding: 2px 8px;
  border-radius: 6px;
  font-size: 13px;
}

.state-unsure {
  color: var(--el-color-warning-dark-2);
  background: var(--el-color-warning-light-8);
}

.state-skipped {
  color: var(--el-text-color-secondary);
  background: var(--el-fill-color);
}

/* 提交按钮贴在屏幕底部，长卷子不用滑到底；
   手机上底部导航是 fixed（约 61px 加安全区），要留出这段高度才不会被盖住 */
.submit-bar {
  position: sticky;
  bottom: 0;
  z-index: 5;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  padding: 10px 0;
  background: var(--bg-secondary, var(--el-bg-color-page));
}

@media (max-width: 768px) {
  .submit-bar {
    bottom: calc(62px + env(safe-area-inset-bottom));
  }
}

.submit-note {
  margin: 0;
  font-size: 13px;
  color: var(--el-color-warning-dark-2);
}

.submit-button {
  width: 100%;
  max-width: 360px;
  height: 52px;
  font-size: 17px;
}

/* ---------- 照片区（电脑右边、手机底部弹出） ---------- */
.photo-panel {
  position: sticky;
  top: 12px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  height: calc(100vh - 120px);
  min-height: 420px;
}

.panel-tabs {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.panel-tab {
  padding: 4px 12px;
  border: 1px solid var(--el-border-color);
  border-radius: 16px;
  font-size: 13px;
  background: var(--el-bg-color);
  color: var(--el-text-color-regular);
  cursor: pointer;
}

.panel-tab.on {
  border-color: var(--el-color-primary);
  color: #fff;
  background: var(--el-color-primary);
}

.panel-image {
  flex: 1;
  min-height: 0;
  width: 100%;
  border-radius: 10px;
  background: var(--el-fill-color-light);
}

.panel-hint {
  margin: 0;
  font-size: 12px;
  color: var(--el-text-color-secondary);
  text-align: center;
}

.sheet-body {
  display: flex;
  flex-direction: column;
  gap: 10px;
  height: 100%;
}

.sheet-image {
  flex: 1;
  min-height: 0;
  width: 100%;
  background: var(--el-fill-color-light);
  border-radius: 8px;
}

.sheet-nav {
  display: flex;
  align-items: center;
  justify-content: space-between;
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
