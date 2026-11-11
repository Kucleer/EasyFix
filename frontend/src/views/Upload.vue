<template>
  <div class="upload">
    <PageHeading title="录入错题" description="记录题目、解题过程，并保留原图方便回顾。" />

    <!-- 选图：选学科年级学期，传一张图开始识别 -->
    <el-card v-if="mode === 'pick'">
      <el-alert
        v-if="health_state === 'down'"
        class="top-alert"
        type="warning"
        title="识别暂时用不了，可以先手工录"
        :closable="false"
        show-icon
      />
      <el-alert
        v-if="unfinished_pages.length"
        class="top-alert"
        type="info"
        title="上次有一张图没整理完"
        :closable="false"
        show-icon
      >
        <div class="alert-actions">
          <el-button size="small" :loading="unfinished_closing" @click="drop_unfinished">不要了</el-button>
          <el-button type="primary" size="small" @click="resume_unfinished">继续</el-button>
        </div>
      </el-alert>

      <el-form :model="pick_form" label-width="60px" class="pick-form">
        <el-form-item label="学科" required>
          <el-select v-model="pick_form.subject_id" placeholder="选择学科" style="width: 100%">
            <el-option v-for="s in subjects" :key="s.id" :label="s.name" :value="s.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="年级">
          <el-select v-model="pick_form.grade" placeholder="选择年级" clearable style="width: 100%">
            <el-option v-for="g in GRADE_OPTIONS" :key="g.value" :label="g.label" :value="g.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="学期">
          <el-select v-model="pick_form.semester" placeholder="选择学期" clearable style="width: 100%">
            <el-option label="上学期" :value="1" />
            <el-option label="下学期" :value="2" />
          </el-select>
        </el-form-item>
      </el-form>

      <el-upload
        ref="pick_upload_ref"
        drag
        :auto-upload="false"
        :show-file-list="false"
        :disabled="uploading"
        :on-change="handle_pick_file"
        accept="image/*"
      >
        <div v-loading="uploading" element-loading-text="正在上传…">
          <el-icon class="el-icon--upload"><upload-filled /></el-icon>
          <div class="el-upload__text">选一张作业或卷子的照片，或者拍一张</div>
        </div>
      </el-upload>

      <div class="manual-entry-link">
        <el-button link type="primary" @click="enter_manual([])">不识别，直接手工录一道</el-button>
      </div>
    </el-card>

    <!-- 识别中：原图先显示，旁边显示进行到哪一步 -->
    <el-card v-else-if="mode === 'scanning' && page">
      <div class="scan-layout">
        <div class="scan-image">
          <el-image :src="'/uploads/' + page.image" :preview-src-list="['/uploads/' + page.image]" fit="contain" />
        </div>
        <div class="scan-status">
          <template v-if="scan_error">
            <el-alert type="error" :title="scan_error" :closable="false" show-icon />
            <div class="scan-actions">
              <el-button size="small" @click="cancel_to_manual">改为手工录</el-button>
              <el-button type="primary" size="small" @click="retry_scan">再试一次</el-button>
            </div>
          </template>
          <template v-else>
            <div class="step-label">
              <el-icon class="is-loading"><loading /></el-icon>
              <span>{{ stepLabel(page.status) || '正在处理' }}</span>
            </div>
            <div class="scan-actions">
              <el-button size="small" @click="cancel_to_manual">取消，改为手工录</el-button>
            </div>
          </template>
        </div>
      </div>
    </el-card>

    <!-- 整理：一道题都没识别出来 -->
    <el-card v-else-if="mode === 'sorting' && page && !page.items.length">
      <el-empty description="没有识别出题目">
        <div class="scan-actions">
          <el-button size="small" :loading="sorting_busy" @click="next_page">换一张</el-button>
          <el-button type="primary" size="small" :loading="sorting_busy" @click="add_blank_item">手工加一道</el-button>
        </div>
      </el-empty>
    </el-card>

    <!-- 整理：Task 8 用 ScanWorkspace 替换这个占位（props page、subjectName；事件 update、next） -->
    <el-card v-else-if="mode === 'sorting' && page">
      <div class="sorting-placeholder">
        <div>{{ subject_name }} · 识别出 {{ page.items.length }} 道题（整理区还没接上）</div>
        <div class="scan-actions">
          <el-button type="primary" size="small" :loading="sorting_busy" @click="next_page">下一张</el-button>
        </div>
      </div>
    </el-card>

    <!-- 手工录：现有的手工表单，可带上照片和学科年级学期 -->
    <template v-else-if="mode === 'manual'">
      <div class="back-link">
        <el-button link type="primary" @click="back_to_pick">← 返回选图</el-button>
      </div>
      <div :class="{ 'manual-layout': manual_preset.images.length }">
        <!-- 带着照片改为手工录时，照片留在旁边对照（电脑端左栏，手机端在上方可收起） -->
        <div
          v-if="manual_preset.images.length"
          class="photo-panel"
          :class="{ collapsed: photo_collapsed }"
        >
          <div class="photo-header">
            <span>原图</span>
            <el-button class="photo-toggle" link type="primary" size="small" @click="photo_collapsed = !photo_collapsed">
              {{ photo_collapsed ? '展开' : '收起' }}
            </el-button>
          </div>
          <div class="photo-body">
            <el-image
              v-for="img in manual_preset.images"
              :key="img"
              :src="'/uploads/' + img"
              :preview-src-list="manual_preset.images.map(i => '/uploads/' + i)"
              fit="contain"
            />
          </div>
        </div>
        <div class="manual-form">
          <ManualQuestionForm
            :key="manual_key"
            :preset-images="manual_preset.images"
            :subject-id="manual_preset.subject_id"
            :grade="manual_preset.grade"
            :semester="manual_preset.semester"
          />
        </div>
      </div>
    </template>
  </div>
</template>

<script setup>
// 录入错题页：选图 → 识别中 → 整理，任何时候都可以改为手工录
import PageHeading from '@/components/PageHeading.vue'
import ManualQuestionForm from '@/components/ManualQuestionForm.vue'
import { ref, reactive, computed, onMounted, onBeforeUnmount } from 'vue'
import { ElMessage } from 'element-plus'
import { UploadFilled, Loading } from '@element-plus/icons-vue'
import { useAppConfigStore } from '@/stores/appConfig'
import { uploadApi, questionApi } from '@/api/question'
import { scanApi } from '@/api/scan'
import { stepLabel, needsCompression, scaledSize } from '@/composables/scanPage'

// 年级选项
const GRADE_OPTIONS = [
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

// 处理中（"推进一步"返回 busy）时，等多久再查一次
const BUSY_WAIT_MS = 3000

const appConfigStore = useAppConfigStore()

// 页面状态：pick 选图 / scanning 识别中 / sorting 整理 / manual 手工录
const mode = ref('pick')
const page = ref(null)              // 当前这一页（后端 page_view）
const scan_error = ref('')          // 识别中出错时给用户看的一句话
const subjects = ref([])
const health_state = ref('checking') // checking / ok / down
let health_promise = null
const unfinished_pages = ref([])    // 没整理完的页，最近的在前
const unfinished_closing = ref(false)
const uploading = ref(false)
const sorting_busy = ref(false)
const pick_upload_ref = ref(null)

// 手工表单的初值；每次进入手工录都换一个 key，让表单重新按初值建立
const manual_key = ref(0)
const manual_preset = reactive({ images: [], subject_id: null, grade: null, semester: null })
const photo_collapsed = ref(false)  // 手机端原图是否收起

/** 读 localStorage 里保存的上次选择（整数），没有时返回 null。 */
const read_last_choice = (key) => {
  const value = localStorage.getItem(key)
  return value ? parseInt(value) : null
}

// 选图时的学科年级学期，沿用上次的选择
const pick_form = reactive({
  subject_id: read_last_choice('lastSubjectId'),
  grade: read_last_choice('lastGrade'),
  semester: read_last_choice('lastSemester'),
})

// 当前页的学科名，给整理区标题用
const subject_name = computed(() => {
  const subject_id = page.value ? page.value.subject_id : pick_form.subject_id
  const found = subjects.value.find(s => s.id === subject_id)
  return found ? found.name : ''
})

/** 从接口错误里取出后端给的提示文字。 */
const read_error_text = (error) => {
  const detail = error?.response?.data?.detail
  if (typeof detail === 'string' && detail) return detail
  return error?.message || '未知错误'
}

/** 把选图时的学科年级学期存进 localStorage，下次沿用。 */
const remember_pick_choice = () => {
  if (pick_form.subject_id) localStorage.setItem('lastSubjectId', pick_form.subject_id)
  if (pick_form.grade) localStorage.setItem('lastGrade', pick_form.grade)
  if (pick_form.semester) localStorage.setItem('lastSemester', pick_form.semester)
}

// ---------------------------------------------------------------- 识别循环

// 每次开始或停止循环都加一；旧循环发现编号变了就自己退出，保证同一时刻只有一个循环在干活
let loop_token = 0

/** 停止正在跑的识别循环（已经发出的请求不撤回，但它返回后不再处理）。 */
const stop_scan_loop = () => {
  loop_token += 1
}

/** 等待指定毫秒数。 */
const wait_ms = (ms) => new Promise(resolve => setTimeout(resolve, ms))

/** 根据页的新状态决定下一步：ready 进整理，failed 显示原因；返回 true 表示循环该结束了。 */
const apply_page_status = (new_page) => {
  page.value = new_page
  if (new_page.status === 'ready') {
    mode.value = 'sorting'
    return true
  }
  if (new_page.status === 'failed') {
    scan_error.value = new_page.error || '识别没成功'
    return true
  }
  if (new_page.status === 'closed') {
    // 别的窗口把这一页结束了，回到选图
    ElMessage.warning('这一页已经结束了')
    back_to_pick()
    return true
  }
  return false
}

/** 识别循环：反复"推进一步"，直到 ready 或 failed；别人正在做时等 3 秒再查。 */
const run_scan_loop = async () => {
  stop_scan_loop()
  const token = loop_token
  const page_id = page.value.id
  scan_error.value = ''
  while (token === loop_token) {
    try {
      const { data } = await scanApi.advance(page_id)
      if (token !== loop_token) return
      if (apply_page_status(data.page)) return
      if (data.busy) {
        // 这一步别的请求正在做：等一会儿再查这一页的最新状态
        await wait_ms(BUSY_WAIT_MS)
        if (token !== loop_token) return
        const fresh = await scanApi.get(page_id)
        if (token !== loop_token) return
        if (apply_page_status(fresh.data)) return
      }
    } catch (error) {
      if (token !== loop_token) return
      scan_error.value = '识别请求出错：' + read_error_text(error)
      return
    }
  }
}

/** "再试一次"：重新开始循环（失败的页再推进一步就会重做）。 */
const retry_scan = () => {
  run_scan_loop()
}

/** 进入识别中状态并开始循环。 */
const start_scanning = (new_page) => {
  page.value = new_page
  scan_error.value = ''
  mode.value = 'scanning'
  run_scan_loop()
}

/** "取消，改为手工录"/"改为手工录"：停止循环、结束这一页，带上照片进手工表单。 */
const cancel_to_manual = async () => {
  stop_scan_loop()
  const current = page.value
  try {
    await scanApi.close(current.id)
  } catch (error) {
    // 结束失败不影响手工录，只是这一页下次还会出现在"没整理完"里
    console.error('结束这一页失败:', error)
  }
  enter_manual([current.image], current)
}

// ---------------------------------------------------------------- 选图

/** 把图片画到 canvas 上按长边缩小，导出为 JPEG。 */
const shrink_image = async (file, max_side, quality) => {
  const bitmap = await createImageBitmap(file)
  const size = scaledSize(bitmap.width, bitmap.height, max_side)
  const canvas = document.createElement('canvas')
  canvas.width = size.width
  canvas.height = size.height
  canvas.getContext('2d').drawImage(bitmap, 0, 0, size.width, size.height)
  bitmap.close()
  const blob = await new Promise(resolve => canvas.toBlob(resolve, 'image/jpeg', quality))
  // 浏览器导不出图片时 toBlob 给 null，不能把它当文件上传
  if (!blob) throw new Error('图片压缩失败，请换一张')
  const name = file.name.replace(/\.[^.]*$/, '') + '.jpg'
  return new File([blob], name, { type: 'image/jpeg' })
}

/** 超过上传上限时压缩：先长边 3000、质量 0.85，还超就长边 2400、质量 0.7；不超限原样返回。 */
const compress_if_needed = async (file) => {
  if (!needsCompression(file.size)) return file
  let result = await shrink_image(file, 3000, 0.85)
  if (needsCompression(result.size)) result = await shrink_image(file, 2400, 0.7)
  return result
}

/** 选了一张图：必要时压缩、上传；识别可用就新建一页开始识别，不可用就直接进手工表单。 */
const handle_pick_file = async (upload_file) => {
  pick_upload_ref.value?.clearFiles()
  if (uploading.value) return
  if (!pick_form.subject_id) {
    ElMessage.warning('请先选择学科')
    return
  }
  uploading.value = true
  try {
    const file = await compress_if_needed(upload_file.raw)
    if (needsCompression(file.size)) {
      ElMessage.error('图片太大，压缩后还是超过 10MB，请换一张')
      return
    }
    const { data: uploaded } = await uploadApi.uploadFile(file)
    remember_pick_choice()
    // 进入页面时的可用性检查可能还没结束，等它出结果
    await health_promise
    if (health_state.value === 'down') {
      enter_manual([uploaded.path], pick_form)
      return
    }
    let new_page
    try {
      const response = await scanApi.create({
        image: uploaded.path,
        subject_id: pick_form.subject_id,
        grade: pick_form.grade,
        semester: pick_form.semester,
      })
      new_page = response.data
    } catch (error) {
      // 照片已经传上去了，只是识别没开始：带着照片改为手工录
      ElMessage.error('识别没开始：' + read_error_text(error))
      enter_manual([uploaded.path], pick_form)
      return
    }
    start_scanning(new_page)
  } catch (error) {
    ElMessage.error('上传失败：' + read_error_text(error))
  } finally {
    uploading.value = false
  }
}

/** 进入手工录，带上照片和学科年级学期（source 为选图表单或一页）。 */
const enter_manual = (images, source = pick_form) => {
  manual_preset.images = images
  manual_preset.subject_id = source.subject_id ?? null
  manual_preset.grade = source.grade ?? null
  manual_preset.semester = source.semester ?? null
  manual_key.value += 1
  photo_collapsed.value = false
  page.value = null
  mode.value = 'manual'
}

/** 回到选图状态，学科年级学期保留。 */
const back_to_pick = () => {
  stop_scan_loop()
  page.value = null
  scan_error.value = ''
  mode.value = 'pick'
}

/** "继续"：接着处理上次没整理完的那一页。 */
const resume_unfinished = () => {
  const target = unfinished_pages.value.shift()
  if (target.status === 'ready') {
    page.value = target
    mode.value = 'sorting'
  } else {
    start_scanning(target)
  }
}

/** "不要了"：结束上次没整理完的那一页。 */
const drop_unfinished = async () => {
  unfinished_closing.value = true
  try {
    await scanApi.close(unfinished_pages.value[0].id)
    unfinished_pages.value.shift()
  } catch (error) {
    ElMessage.error('操作失败：' + read_error_text(error))
  } finally {
    unfinished_closing.value = false
  }
}

// ---------------------------------------------------------------- 整理

/** "手工加一道"：一道题都没识别出来时，在这一页加一道空白题。 */
const add_blank_item = async () => {
  sorting_busy.value = true
  try {
    const { data } = await scanApi.addItem(page.value.id)
    page.value = data
  } catch (error) {
    ElMessage.error('添加失败：' + read_error_text(error))
  } finally {
    sorting_busy.value = false
  }
}

/** "下一张"/"换一张"：结束这一页，回到选图。 */
const next_page = async () => {
  sorting_busy.value = true
  try {
    await scanApi.close(page.value.id)
    back_to_pick()
  } catch (error) {
    ElMessage.error('操作失败：' + read_error_text(error))
  } finally {
    sorting_busy.value = false
  }
}

// ---------------------------------------------------------------- 进入页面

/** 查识别服务是否可用；出错或不可用都算用不了。 */
const check_health = async () => {
  try {
    const { data } = await scanApi.health()
    health_state.value = data && data.available ? 'ok' : 'down'
  } catch (error) {
    health_state.value = 'down'
  }
}

/** 查有没有上次没整理完的页。 */
const load_unfinished = async () => {
  try {
    const { data } = await scanApi.unfinished()
    unfinished_pages.value = data.items || []
  } catch (error) {
    console.error('查没整理完的页失败:', error)
  }
}

/** 加载学科列表。 */
const load_subjects = async () => {
  try {
    const { data } = await questionApi.listSubjects()
    subjects.value = Array.isArray(data) ? data : (data.items || [])
  } catch (error) {
    console.error('加载学科失败:', error)
  }
}

onMounted(async () => {
  health_promise = check_health()
  load_unfinished()
  load_subjects()
  // 没有上次的选择时，用默认学段
  await appConfigStore.load()
  if (pick_form.grade == null) pick_form.grade = appConfigStore.defaultGrade
  if (pick_form.semester == null) pick_form.semester = appConfigStore.defaultSemester
})

// 离开页面时停止识别循环（后端记录还在，下次可以"继续"）
onBeforeUnmount(stop_scan_loop)
</script>

<style scoped>
.upload {
  max-width: 1100px;
  margin: 0 auto;
}

/* 禁用上传页面卡片的hover效果 */
.upload :deep(.el-card) {
  transition: none;
}

.upload :deep(.el-card:hover) {
  transform: none;
  box-shadow: var(--shadow-sm) !important;
}

.top-alert {
  margin-bottom: 12px;
}

.alert-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 6px;
}

.pick-form {
  max-width: 600px;
}

.manual-entry-link {
  text-align: center;
  margin-top: 12px;
}

.scan-layout {
  display: flex;
  gap: 16px;
}

.scan-image {
  flex: 1;
  min-width: 0;
}

.scan-image .el-image {
  width: 100%;
  max-height: 70vh;
}

.scan-status {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.step-label {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 16px;
  color: var(--text-primary);
}

.scan-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}

.sorting-placeholder {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.back-link {
  margin-bottom: 8px;
}

/* 手工录带照片：左边原图固定，右边表单 */
.manual-layout {
  display: flex;
  gap: 16px;
  align-items: flex-start;
}

.photo-panel {
  flex: 0 0 40%;
  position: sticky;
  top: 12px;
  border: 1px solid var(--border-light);
  border-radius: 10px;
  background: #fff;
  padding: 10px;
}

.photo-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
  font-weight: bold;
  color: var(--text-primary);
}

/* 电脑端不需要收起按钮 */
.photo-toggle {
  display: none;
}

.photo-body .el-image {
  width: 100%;
  max-height: 80vh;
}

.manual-form {
  flex: 1;
  min-width: 0;
}

/* 手机端：原图在上，状态在下；手工录的原图在上方，可以收起 */
@media (max-width: 768px) {
  .scan-layout {
    flex-direction: column;
  }

  .manual-layout {
    flex-direction: column;
    align-items: stretch;
  }

  .photo-panel {
    position: static;
    flex: none;
  }

  .photo-toggle {
    display: inline-flex;
  }

  .photo-panel.collapsed .photo-body {
    display: none;
  }

  .photo-panel.collapsed .photo-header {
    margin-bottom: 0;
  }
}
</style>
