<template>
  <div class="scan-workspace">
    <div class="ws-head">
      <span class="ws-title">{{ title_text }}</span>
      <span class="ws-summary">识别出 {{ summary.total }} 道题，模型判断 {{ summary.wrong }} 道做错</span>
    </div>

    <div class="ws-body">
      <ScanImagePane class="ws-image" :src="'/uploads/' + page.image" />

      <div class="ws-list">
        <el-alert
          v-if="!groups.main.length"
          type="success"
          title="模型没发现做错的题"
          :closable="false"
          show-icon
        />

        <ScanItemCard
          v-for="item in groups.main"
          :key="item.seq"
          :data-seq="item.seq"
          :item="item"
          :subject-id="page.subject_id"
          :error-types="error_type_names"
          :knowledge-names="knowledge_names"
          :server-error="server_errors[item.seq] || ''"
          :busy="accepting_all || Boolean(busy_seqs[item.seq])"
          @save="(fields, finish) => save_item(item, fields, finish)"
          @accept="accept_item(item)"
          @dismiss="dismiss_item(item)"
          @withdraw="withdraw_item(item)"
          @editing-change="(value) => set_editing(item.seq, value)"
        />

        <!-- 模型认为做对的题：默认收起；主列表为空时自动展开 -->
        <el-collapse v-if="groups.right.length" v-model="open_panels" class="right-group">
          <el-collapse-item name="right">
            <template #title>
              <span class="right-title">模型认为做对的 {{ groups.right.length }} 道</span>
            </template>
            <div v-for="item in groups.right" :key="item.seq" class="right-row">
              <span class="right-no">{{ itemLabel(item) }}</span>
              <span class="right-text"><MathText :text="item.parsed_question" /></span>
              <el-button
                size="small"
                :loading="Boolean(busy_seqs[item.seq])"
                :disabled="accepting_all"
                @click="promote_item(item)"
              >补成错题</el-button>
            </div>
          </el-collapse-item>
        </el-collapse>

        <el-button class="add-button" size="small" :loading="adding" :disabled="accepting_all" @click="add_item">
          ＋ 手工加一道
        </el-button>
      </div>
    </div>

    <!-- 底部：进度和两个按钮（手机端固定在屏幕底部） -->
    <div class="ws-footer">
      <span class="ws-progress">已录入 {{ progress.accepted }} 道，还剩 {{ progress.remaining }} 道</span>
      <span class="ws-footer-actions">
        <el-button
          type="primary"
          size="small"
          :loading="accepting_all"
          :disabled="!accept_all_count && !accepting_all"
          @click="accept_all"
        >{{ accepting_all ? accept_all_progress : `全部录入（${accept_all_count}）` }}</el-button>
        <el-button size="small" :disabled="accepting_all" @click="request_next">下一张</el-button>
      </span>
    </div>
  </div>
</template>

<script setup>
// 整理区：左边原图、右边题目卡片；逐道录入、修改、去掉、补成错题、手工加题、全部录入
import MathText from '@/components/MathText.vue'
import ScanImagePane from '@/components/scan/ScanImagePane.vue'
import ScanItemCard from '@/components/scan/ScanItemCard.vue'
import { ref, computed, watch, onMounted, onBeforeUnmount, nextTick, h } from 'vue'
import { ElMessage, ElMessageBox, ElNotification, ElButton } from 'element-plus'
import { questionApi } from '@/api/question'
import { scanApi } from '@/api/scan'
import {
  groupItems, progressCounts, acceptAllSeqs, pageSummary, itemLabel, gradeTermText,
  acceptFailureAction, acceptAllProgressText, runAcceptAll,
} from '@/composables/scanPage'

const props = defineProps({
  page: { type: Object, required: true },        // 当前这一页（后端 page_view，status 为 ready）
  subjectName: { type: String, default: '' },    // 学科名，标题用
})

// update(page)：接口返回了新的页；next：确认后要结束这一页、回到选图
const emit = defineEmits(['update', 'next'])

// "不是错题"后撤销提示停留的毫秒数
const UNDO_DURATION_MS = 5000
// 补成错题没补上时给的提示
const FILL_FAILED_TEXT = '没补上答案和解析，可以点修改自己填'
// 手机端宽度上限，以及手机端撤销提示离底部的距离（导航约 65px + 按钮条约 54px）
const MOBILE_MAX_WIDTH = 768
const MOBILE_NOTIFY_OFFSET = 130

const error_type_names = ref([])   // 这一学科的错因名称
const knowledge_names = ref({})    // 考点编号 -> 名称
const busy_seqs = ref({})          // 有请求在进行的题
const server_errors = ref({})      // 录入被拒等提示：seq -> 文字
const adding = ref(false)
const accepting_all = ref(false)
const accept_all_progress = ref('')  // "全部录入"进行中按钮上的进度，如"正在录入 2/5"
const open_panels = ref([])        // 展开的折叠区
const editing_seqs = ref({})       // 正在修改（表单打开着）的题
let undo_notifications = []        // 还开着的"撤销"提示，结束这一页或离开时关掉

const groups = computed(() => groupItems(props.page.items))
const progress = computed(() => progressCounts(props.page.items))
const summary = computed(() => pageSummary(props.page.items))
const accept_all_count = computed(() => acceptAllSeqs(props.page.items).length)
const title_text = computed(() =>
  [props.subjectName, gradeTermText(props.page.grade, props.page.semester)].filter(Boolean).join(' · '))

// 主列表空了（全都判对）时自动展开折叠区
watch(() => groups.value.main.length, (count) => {
  if (count === 0 && !open_panels.value.includes('right')) open_panels.value = [...open_panels.value, 'right']
}, { immediate: true })

// ---------------------------------------------------------------- 通用

/** 从接口错误里取出后端给的提示文字。 */
const read_error_text = (error) => {
  const detail = error?.response?.data?.detail
  if (typeof detail === 'string' && detail) return detail
  return error?.message || '未知错误'
}

/** 重新读这一页的最新状态（别处改过时用），返回新的页；读失败返回 null。 */
const refresh_page = async () => {
  try {
    const { data } = await scanApi.get(props.page.id)
    emit('update', data)
    return data
  } catch (error) {
    ElMessage.error('刷新失败：' + read_error_text(error))
    return null
  }
}

/** 接口失败：显示后端的提示；409 说明这一页或这道题已经变了，提示后刷新。 */
const report_error = async (error) => {
  const text = read_error_text(error)
  if (error?.response?.status === 409) {
    const fresh = await refresh_page()
    // 这一页已经被结束：上层会提示"这一页已经结束了"并回选图，这里不再重复提示
    if (fresh && fresh.status !== 'ready') return
    // 后端的提示可能自带"请刷新"，这里已经替她刷新了，换成"已刷新这一页"
    ElMessage.error(text.replace(/，?请刷新$/, '') + '，已刷新这一页')
    return
  }
  ElMessage.error(text)
}

/** 标记/取消某道题正在请求中。 */
const set_busy = (seq, value) => {
  const next = { ...busy_seqs.value }
  if (value) next[seq] = true
  else delete next[seq]
  busy_seqs.value = next
}

/** 设置或清除某道题的提示文字。 */
const set_server_error = (seq, text) => {
  const next = { ...server_errors.value }
  if (text) next[seq] = text
  else delete next[seq]
  server_errors.value = next
}

/** 记录某道题的修改表单是否打开着。 */
const set_editing = (seq, value) => {
  const next = { ...editing_seqs.value }
  if (value) next[seq] = true
  else delete next[seq]
  editing_seqs.value = next
}

/** 关掉所有还开着的"撤销"提示，免得这一页结束后再点撤销。 */
const close_undo_notifications = () => {
  undo_notifications.forEach(notification => notification.close())
  undo_notifications = []
}

/** 对一道题调接口：期间标记忙，成功时把新页交给上层并返回响应数据，失败时报错并返回 null。 */
const run_item_request = async (seq, request) => {
  set_busy(seq, true)
  try {
    const { data } = await request()
    return data
  } catch (error) {
    await report_error(error)
    return null
  } finally {
    set_busy(seq, false)
  }
}

// ---------------------------------------------------------------- 逐道操作

/** 保存修改：存回草稿后回到只读，不自动录入。 */
const save_item = async (item, fields, finish) => {
  const data = await run_item_request(item.seq, () => scanApi.saveItem(props.page.id, item.seq, fields))
  if (data) {
    emit('update', data)
    set_server_error(item.seq, '')
  }
  finish(Boolean(data))
}

/** 录入失败后的处理：后端拒绝（422 等）时卡片切到修改状态、顶部显示原因；409 刷新；其余只提示。 */
const handle_accept_failure = async (seq, error) => {
  if (acceptFailureAction(error?.response?.status) === 'edit') {
    const text = read_error_text(error)
    set_server_error(seq, text)
    ElMessage.error(text)
    return
  }
  await report_error(error)  // 409 会刷新这一页
}

/** 调接口录入一道，成功后把新页交给上层；失败时抛出，由调用方处理。 */
const accept_request = async (seq) => {
  // 先清掉旧提示，这样同样的原因再次出现时卡片也会重新进入修改状态
  set_server_error(seq, '')
  const { data } = await scanApi.accept(props.page.id, seq)
  emit('update', data)
}

/** 录入一道；被后端拒绝时卡片切到修改状态，顶部显示原因。 */
const accept_item = async (item) => {
  set_busy(item.seq, true)
  try {
    await accept_request(item.seq)
  } catch (error) {
    await handle_accept_failure(item.seq, error)
  } finally {
    set_busy(item.seq, false)
  }
}

/** 撤回录入：错题删掉，这道题回到未处理。 */
const withdraw_item = async (item) => {
  const data = await run_item_request(item.seq, () => scanApi.withdraw(props.page.id, item.seq))
  if (data) {
    emit('update', data)
    ElMessage.success(itemLabel(item) + ' 已撤回')
  }
}

/** 撤销"不是错题"：把这道题恢复回来。 */
const restore_item = async (item) => {
  const data = await run_item_request(item.seq, () => scanApi.restore(props.page.id, item.seq))
  if (data) emit('update', data)
}

/** 不是错题：直接去掉，不二次确认；给一个约 5 秒的"撤销"提示。 */
const dismiss_item = async (item) => {
  const data = await run_item_request(item.seq, () => scanApi.dismiss(props.page.id, item.seq))
  if (!data) return
  emit('update', data)
  set_server_error(item.seq, '')
  const notification = ElNotification({
    onClose: () => {
      undo_notifications = undo_notifications.filter(one => one !== notification)
    },
    title: itemLabel(item) + ' 已去掉',
    duration: UNDO_DURATION_MS,
    position: 'bottom-right',
    // 手机端底部有导航和固定的按钮条，提示往上挪，免得挡住
    offset: window.innerWidth <= MOBILE_MAX_WIDTH ? MOBILE_NOTIFY_OFFSET : 16,
    message: h('div', { class: 'scan-undo' }, [
      h('span', '不会录入。'),
      h(ElButton, {
        link: true,
        type: 'primary',
        size: 'small',
        onClick: () => {
          notification.close()
          restore_item(item)
        },
      }, () => '撤销'),
    ]),
  })
  undo_notifications.push(notification)
}

/** 补成错题：移到主列表并请模型补全；没补上时卡片进修改状态让她自己填。 */
const promote_item = async (item) => {
  const data = await run_item_request(item.seq, () => scanApi.promote(props.page.id, item.seq))
  if (!data) return
  emit('update', data.page)
  if (data.fill_error) {
    set_server_error(item.seq, FILL_FAILED_TEXT)
    ElMessage.warning(FILL_FAILED_TEXT)
  }
}

/** 手工加一道：在主列表末尾加一张空白卡片（卡片自己会进修改状态），并滚到它。 */
const add_item = async () => {
  adding.value = true
  try {
    const { data } = await scanApi.addItem(props.page.id)
    emit('update', data)
    await nextTick()
    const cards = document.querySelectorAll('.scan-workspace [data-seq]')
    cards[cards.length - 1]?.scrollIntoView({ behavior: 'smooth', block: 'center' })
  } catch (error) {
    await report_error(error)
  } finally {
    adding.value = false
  }
}

// ---------------------------------------------------------------- 底部按钮

/**
 * 全部录入：按卷面顺序逐道调"录入一道"（没有一次录多道的接口，免费计划限制单次请求的数据库操作次数），
 * 按钮上显示"正在录入 2/5"；某一道失败就停在那道：被拒绝的卡片切到修改状态并显示原因，
 * 409 刷新这一页；已经录入的不受影响。
 */
const accept_all = async () => {
  // 正在修改的题也在"全部录入"里时，录入的是草稿里存着的内容，表单里没保存的修改会丢，先问一句
  const candidates = acceptAllSeqs(props.page.items)
  const editing_count = candidates.filter(seq => editing_seqs.value[seq]).length
  if (editing_count > 0) {
    try {
      await ElMessageBox.confirm(`有 ${editing_count} 道正在修改，先保存吗？`, '全部录入', {
        confirmButtonText: '先去保存',
        cancelButtonText: '不保存，照原样录入',
        distinguishCancelAndClose: true,
        type: 'warning',
      })
      return  // 选了"先去保存"：不录入，回去保存
    } catch (action) {
      if (action !== 'cancel') return  // 关掉对话框也当作不录入
    }
  }
  accepting_all.value = true
  try {
    const result = await runAcceptAll(candidates, accept_request, (index, total) => {
      accept_all_progress.value = acceptAllProgressText(index, total)
    })
    if (result.failedSeq === null) {
      ElMessage.success(`已录入 ${result.accepted} 道`)
      return
    }
    // 停在失败的那道：先给出已录入几道，再按失败原因处理（卡片进修改状态 / 刷新 / 提示）
    if (result.accepted > 0) ElMessage.success(`已录入 ${result.accepted} 道，后面的先停下`)
    await handle_accept_failure(result.failedSeq, result.error)
  } finally {
    accepting_all.value = false
    accept_all_progress.value = ''
  }
}

/** 下一张：还有没处理的题时先问一句，确认后交给上层结束这一页。 */
const request_next = async () => {
  const remaining = progress.value.remaining
  if (remaining > 0) {
    try {
      await ElMessageBox.confirm(`还有 ${remaining} 道没处理，不要了吗？`, '下一张', {
        confirmButtonText: '不要了',
        cancelButtonText: '再看看',
        type: 'warning',
      })
    } catch {
      return  // 点了"再看看"
    }
  }
  close_undo_notifications()
  emit('next')
}

// ---------------------------------------------------------------- 加载目录

/** 读这一学科的错因名称和考点名称（接口有短时缓存，不会重复请求）。 */
const load_catalog = async () => {
  const subject_id = props.page.subject_id
  try {
    const { data } = await questionApi.listErrorTypes({ subject_id })
    const list = Array.isArray(data) ? data : (data.items || [])
    error_type_names.value = list.map(one => one.name)
  } catch (error) {
    console.error('加载错因失败:', error)
  }
  try {
    const { data } = await questionApi.listKnowledgePoints({ subject_id })
    const list = Array.isArray(data) ? data : (data.items || [])
    knowledge_names.value = Object.fromEntries(list.map(point => [point.id, point.name]))
  } catch (error) {
    console.error('加载考点失败:', error)
  }
}

onMounted(load_catalog)
// 离开整理区（下一张、页被结束、离开页面）时关掉撤销提示
onBeforeUnmount(close_undo_notifications)
</script>

<style scoped>
.scan-workspace {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.ws-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 4px 12px;
}

.ws-title {
  font-weight: bold;
  color: var(--text-primary);
}

.ws-summary {
  color: var(--text-secondary, #606266);
}

/* 电脑端：左边原图固定不动，右边列表 */
.ws-body {
  display: flex;
  gap: 16px;
  align-items: flex-start;
}

.ws-image {
  flex: 0 0 42%;
  position: sticky;
  top: 12px;
}

.ws-list {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.right-group {
  border: 1px solid var(--border-light);
  border-radius: 10px;
  background: #fff;
  padding: 0 14px;
}

.right-group :deep(.el-collapse-item__wrap),
.right-group :deep(.el-collapse-item__header) {
  border-bottom: none;
}

.right-title {
  font-weight: bold;
  color: var(--text-primary);
}

.right-row {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 6px 0;
  border-top: 1px dashed var(--border-light);
}

.right-no {
  flex: none;
  color: var(--text-muted);
}

/* 题干只显示开头一行 */
.right-text {
  flex: 1;
  min-width: 0;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.add-button {
  width: 100%;
  border-style: dashed;
}

.ws-footer {
  position: sticky;
  bottom: 0;
  z-index: 10;
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
  padding: 10px 14px;
  background: #fff;
  border: 1px solid var(--border-light);
  border-radius: 10px;
}

.ws-progress {
  color: var(--text-primary);
}

.ws-footer-actions {
  display: inline-flex;
  gap: 8px;
}

.ws-footer-actions .el-button + .el-button {
  margin-left: 0;
}

/* 手机端：原图在上，列表在下，底部条固定在手机导航上方 */
@media (max-width: 768px) {
  .ws-body {
    flex-direction: column;
    align-items: stretch;
  }

  .ws-image {
    position: static;
    flex: none;
  }

  /* 给固定的底部条留出位置 */
  .scan-workspace {
    padding-bottom: 64px;
  }

  .ws-footer {
    position: fixed;
    left: 0;
    right: 0;
    bottom: calc(65px + env(safe-area-inset-bottom));  /* 手机导航高约 65px */
    border-radius: 0;
    border-left: none;
    border-right: none;
    padding: 8px 12px;
    box-shadow: 0 -2px 8px rgba(0, 0, 0, 0.06);
  }

  .ws-progress {
    font-size: 13px;
  }
}
</style>
