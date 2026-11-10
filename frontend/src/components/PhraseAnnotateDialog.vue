<template>
  <!-- 词组重点批量标注：进度 + 结果（失败条目、可加入单词本的生词） -->
  <el-dialog
    v-model="visible"
    title="标注词组重点"
    width="720px"
    class="annotate-dialog"
    :close-on-click-modal="false"
    :before-close="handleBeforeClose"
  >
    <div v-if="running" class="progress-box">
      <el-progress :percentage="percent" :stroke-width="14" />
      <div class="progress-text">已处理 {{ processed }} / 共 {{ total }}</div>
      <div class="progress-tip">每批 {{ BATCH_SIZE }} 个，需要调用大模型，请耐心等待。</div>
      <div v-if="cancelRequested" class="progress-tip">将在当前批次完成后停止……</div>
    </div>

    <div v-else>
      <div class="summary">
        已处理 {{ processed }} / 共 {{ total }}，成功标注 <b>{{ annotated }}</b> 个，
        <span :class="{ 'fail-count': failures.length > 0 }">失败 {{ failures.length }} 个</span>
        <span v-if="cancelled">（已中途停止）</span>。
        标注结果为"待确认"，可在词组详情中核对修改。
      </div>

      <div v-if="failures.length > 0" class="section">
        <div class="section-title">失败条目</div>
        <ul class="failure-list">
          <li v-for="(f, i) in failures" :key="`${f.id}-${i}`">
            <span class="failure-english">{{ f.english || `#${f.id}` }}</span>
            <span class="failure-reason">{{ f.reason }}</span>
          </li>
        </ul>
      </div>

      <div v-if="missingRows.length > 0" class="section">
        <div class="section-title">发现的生词（可加入单词本）</div>
        <div class="table-scroll">
          <el-table
            ref="missingTableRef"
            :data="missingRows"
            size="small"
            row-key="key"
            @selection-change="(rows) => (selectedRows = rows)"
          >
            <el-table-column type="selection" width="45" />
            <el-table-column label="原形" min-width="130">
              <template #default="{ row }">
                <el-input v-model="row.lemma" size="small" />
              </template>
            </el-table-column>
            <el-table-column label="释义" min-width="160">
              <template #default="{ row }">
                <el-input v-model="row.gloss" size="small" placeholder="必填" />
              </template>
            </el-table-column>
            <el-table-column label="年级" width="70">
              <template #default="{ row }">{{ row.grade ? row.grade + '年级' : '-' }}</template>
            </el-table-column>
          </el-table>
        </div>
        <el-button type="primary" size="small" class="add-btn" :loading="adding" @click="addSelected">
          加入单词本
        </el-button>
      </div>
    </div>

    <template #footer>
      <el-button v-if="running" :disabled="cancelRequested" @click="cancelRequested = true">停止</el-button>
      <el-button v-else type="primary" @click="visible = false">关闭</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref, computed, nextTick } from 'vue'
import { ElMessage } from 'element-plus'
import { wordApi } from '@/api/word'

const emit = defineEmits(['finished'])

const BATCH_SIZE = 20

const visible = ref(false)
const running = ref(false)
const cancelRequested = ref(false)
const cancelled = ref(false)
const total = ref(0)
const processed = ref(0)
const annotated = ref(0)
const failures = ref([])
const missingRows = ref([])
const selectedRows = ref([])
const adding = ref(false)
const missingTableRef = ref(null)

const percent = computed(() => (total.value ? Math.round((processed.value / total.value) * 100) : 0))

// 从错误对象中取出可读原因
const errorReason = (error) => {
  const detail = error?.response?.data?.detail
  return typeof detail === 'string' ? detail : (error?.message || '请求失败')
}

// 开始标注：取出全部未标注词组，按 20 个一批顺序调用接口
const start = async () => {
  let items = []
  try {
    const { data } = await wordApi.list({ entry_type: 'phrase', focus_status: 'none', limit: 1000 })
    items = data.items || []
  } catch (error) {
    ElMessage.error('获取未标注词组失败')
    return
  }
  if (items.length === 0) {
    ElMessage.info('没有需要标注的词组')
    return
  }

  // 重置状态
  total.value = items.length
  processed.value = 0
  annotated.value = 0
  failures.value = []
  missingRows.value = []
  selectedRows.value = []
  cancelRequested.value = false
  cancelled.value = false
  running.value = true
  visible.value = true

  const lemmaSeen = new Set()
  for (let i = 0; i < items.length; i += BATCH_SIZE) {
    if (cancelRequested.value) {
      cancelled.value = true
      break
    }
    const batch = items.slice(i, i + BATCH_SIZE)
    try {
      const { data } = await wordApi.annotateFocus(batch.map((w) => w.id))
      annotated.value += data.annotated || 0
      failures.value.push(...(data.failures || []))
      // 跳过的条目也当作失败展示，便于家长知道原因
      for (const s of data.skipped || []) {
        const w = batch.find((x) => x.id === s.id)
        failures.value.push({ id: s.id, english: w?.english, reason: s.reason })
      }
      for (const m of data.missing_lemmas || []) {
        const key = (m.lemma || '').toLowerCase()
        if (!key || lemmaSeen.has(key)) continue
        lemmaSeen.add(key)
        missingRows.value.push({ ...m, key: `${key}-${missingRows.value.length}` })
      }
    } catch (error) {
      // 整批失败：记录这些条目后继续下一批
      const reason = errorReason(error)
      for (const w of batch) failures.value.push({ id: w.id, english: w.english, reason })
    }
    processed.value += batch.length
  }

  running.value = false
  await nextTick()
  // 默认全选有释义的生词
  missingRows.value.forEach((row) => {
    if (row.gloss) missingTableRef.value?.toggleRowSelection(row, true)
  })
  emit('finished')
}

// 运行中关闭窗口视为停止
const handleBeforeClose = (done) => {
  if (running.value) {
    cancelRequested.value = true
    return
  }
  done()
}

// 把勾选的生词加入单词本，释义为空的不能加入
const addSelected = async () => {
  if (selectedRows.value.length === 0) {
    ElMessage.warning('请先勾选要加入的生词')
    return
  }
  const invalid = selectedRows.value.filter((r) => !(r.lemma || '').trim() || !(r.gloss || '').trim())
  if (invalid.length > 0) {
    ElMessage.warning('请先补全勾选项的原形和释义')
    return
  }
  const rows = [...selectedRows.value]
  adding.value = true
  try {
    const payload = rows.map((r) => {
      const item = { english: r.lemma.trim(), chinese: r.gloss.trim() }
      if (r.grade) item.grade = r.grade
      if (r.semester) item.semester = r.semester
      return item
    })
    const { data } = await wordApi.createBatch(payload)
    const ok = data?.success_count ?? rows.length
    ElMessage.success(`已加入 ${ok} 个生词`)
    // 成功后从表格中移除
    const done = new Set(rows.map((r) => r.key))
    missingRows.value = missingRows.value.filter((r) => !done.has(r.key))
    selectedRows.value = []
    emit('finished')
  } catch (error) {
    ElMessage.error('加入单词本失败：' + errorReason(error))
  } finally {
    adding.value = false
  }
}

defineExpose({ start })
</script>

<style scoped>
.progress-box { padding: 10px 0; }
.progress-text { margin-top: 12px; font-size: var(--font-h3); color: var(--text-primary); text-align: center; }
.progress-tip { margin-top: 6px; font-size: var(--font-small); color: var(--text-muted); text-align: center; }
.summary { color: var(--text-secondary); line-height: 1.8; }
.fail-count { color: var(--danger); font-weight: var(--font-weight-semibold); }
.section { margin-top: 16px; }
.section-title { font-weight: var(--font-weight-semibold); margin-bottom: 8px; color: var(--text-primary); }
.failure-list { margin: 0; padding-left: 18px; max-height: 160px; overflow-y: auto; }
.failure-list li { margin-bottom: 4px; word-break: break-word; }
.failure-english { font-weight: var(--font-weight-semibold); margin-right: 8px; }
.failure-reason { color: var(--danger); font-size: var(--font-small); }
.table-scroll { max-width: 100%; overflow-x: auto; max-height: 320px; overflow-y: auto; }
.add-btn { margin-top: 10px; }
</style>

<style>
/* 手机上限制弹窗宽度，避免横向溢出 */
.annotate-dialog { max-width: 94vw; }
</style>
