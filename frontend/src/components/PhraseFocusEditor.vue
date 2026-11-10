<template>
  <!-- 词组重点编辑：点击词在 基础词/搭配词/生词/占位符 之间循环，保存后词组变为"已确认" -->
  <div class="focus-editor">
    <div class="legend">
      <span v-for="r in ROLE_ORDER" :key="r" class="legend-item">
        <span class="legend-dot" :class="`role-${r}`"></span>{{ ROLE_LABELS[r] }}
      </span>
    </div>
    <div class="hint">点击词语切换类型；默写时"搭配词"和"生词"会被挖空。</div>

    <div class="token-list">
      <button
        v-for="(t, i) in tokens"
        :key="i"
        type="button"
        class="token-chip"
        :class="`role-${t.role}`"
        @click="cycleRole(i)"
      >
        <span class="chip-text">{{ t.text }}</span>
        <span class="chip-role">{{ ROLE_LABELS[t.role] }}</span>
      </button>
    </div>

    <!-- 生词需要填写原形与释义，方便加入单词本 -->
    <div v-for="(t, i) in tokens" :key="`lemma-${i}`">
      <div v-if="t.role === 'content'" class="lemma-row">
        <span class="lemma-word">{{ t.text }}</span>
        <el-input v-model="t.lemma" size="small" placeholder="原形" class="lemma-input" />
        <el-input v-model="t.gloss" size="small" placeholder="释义" class="gloss-input" />
      </div>
    </div>

    <div class="preview">
      <span class="preview-label">默写预览（重点档）：</span>
      <span class="preview-text">{{ previewText }}</span>
    </div>

    <div v-if="errorMessage" class="error-text">{{ errorMessage }}</div>

    <el-button type="primary" size="small" :loading="saving" @click="save">保存重点</el-button>
  </div>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { wordApi } from '@/api/word'

const props = defineProps({
  word: { type: Object, required: true },
})
const emit = defineEmits(['saved'])

// 角色循环顺序与中文名
const ROLE_ORDER = ['plain', 'collocation', 'content', 'placeholder']
const ROLE_LABELS = {
  plain: '基础词',
  collocation: '搭配词',
  content: '生词',
  placeholder: '占位符',
}

const tokens = ref([])
const saving = ref(false)
const errorMessage = ref('')

// 去掉首尾标点并转小写，作为生词原形的默认值
const guessLemma = (text) =>
  text.toLowerCase().replace(/^[^a-z0-9]+|[^a-z0-9]+$/gi, '')

// 按当前英文和已保存的重点构造编辑起点
// 规范化英文：去首尾空白、内部连续空白合并为一个空格（与后端 source_english 一致）
const normalizeEnglish = (s) => (s || '').trim().replace(/\s+/g, ' ')
// 规范化后的词列表；空字符串得到空列表而不是 ['']
const splitTokens = (english) => {
  const normalized = normalizeEnglish(english)
  return normalized ? normalized.split(' ') : []
}

const buildTokens = () => {
  const english = props.word.english || ''
  const parts = splitTokens(english)
  const spec = props.word.focus_spec
  // 已保存的重点必须与规范化后的英文一致才沿用，否则全部按基础词起步
  const usable =
    spec && Array.isArray(spec.tokens) &&
    spec.source_english === normalizeEnglish(english) &&
    spec.tokens.length === parts.length &&
    spec.tokens.every((t, i) => t.text === parts[i])
  return parts.map((text, i) => {
    const saved = usable ? spec.tokens[i] : null
    const role = saved && ROLE_LABELS[saved.role] ? saved.role : 'plain'
    return {
      text,
      role,
      lemma: saved?.lemma || (role === 'content' ? guessLemma(text) : ''),
      gloss: saved?.gloss || '',
    }
  })
}

const reset = () => {
  tokens.value = buildTokens()
  errorMessage.value = ''
}
watch(() => [props.word.id, props.word.english, props.word.focus_spec], reset, { immediate: true })

// 点击词语：切换到下一种角色
const cycleRole = (index) => {
  const t = tokens.value[index]
  const next = ROLE_ORDER[(ROLE_ORDER.indexOf(t.role) + 1) % ROLE_ORDER.length]
  t.role = next
  // 切到生词时补上默认原形
  if (next === 'content' && !t.lemma) t.lemma = guessLemma(t.text)
}

// 重点档默写预览：搭配词和生词显示为下划线
const previewText = computed(() =>
  tokens.value
    .map((t) =>
      t.role === 'collocation' || t.role === 'content'
        ? '_'.repeat(Math.max(t.text.replace(/[^A-Za-z0-9]/g, '').length, 2))
        : t.text
    )
    .join(' ')
)

// 保存：只发送 focus_spec.tokens，非生词不带原形，空释义不带
const save = async () => {
  const payload = tokens.value.map((t) => {
    const item = { text: t.text, role: t.role }
    if (t.role === 'content') {
      item.lemma = (t.lemma || '').trim()
      if ((t.gloss || '').trim()) item.gloss = t.gloss.trim()
    }
    return item
  })
  if (payload.some((t) => t.role === 'content' && !t.lemma)) {
    errorMessage.value = '生词需要填写原形'
    return
  }
  saving.value = true
  errorMessage.value = ''
  try {
    const { data } = await wordApi.update(props.word.id, { focus_spec: { tokens: payload } })
    ElMessage.success('重点已保存')
    emit('saved', data)
  } catch (error) {
    // 服务端 422 会返回中文原因
    const detail = error?.response?.data?.detail
    errorMessage.value = typeof detail === 'string' ? detail : '保存失败，请稍后重试'
  } finally {
    saving.value = false
  }
}
</script>

<style scoped>
.focus-editor { display: flex; flex-direction: column; gap: 10px; max-width: 100%; }
.legend { display: flex; flex-wrap: wrap; gap: 12px; font-size: var(--font-small); color: var(--text-secondary); }
.legend-item { display: inline-flex; align-items: center; gap: 4px; }
.legend-dot { width: 10px; height: 10px; border-radius: var(--radius-full); border: 1px solid var(--border-default); }
.hint { font-size: var(--font-small); color: var(--text-muted); }
.token-list { display: flex; flex-wrap: wrap; gap: 8px; }
.token-chip {
  display: inline-flex; flex-direction: column; align-items: center;
  padding: 4px 10px; border-radius: var(--radius-sm); cursor: pointer;
  border: 1px solid var(--border-default); background: var(--bg-primary);
  color: var(--text-primary); font: inherit; max-width: 100%;
}
.chip-text { font-size: var(--font-body); word-break: break-all; }
.chip-role { font-size: 11px; color: var(--text-muted); }
.role-plain { background: var(--bg-tertiary); }
.role-collocation { background: #e2e0fb; border-color: var(--accent-blue); }
.role-content { background: #fbeed8; border-color: var(--warning); }
.role-placeholder { background: #e6e8ef; border-style: dashed; border-color: var(--info); }
.lemma-row { display: flex; flex-wrap: wrap; align-items: center; gap: 6px; }
.lemma-word { font-weight: var(--font-weight-semibold); min-width: 60px; word-break: break-all; }
.lemma-input { flex: 1 1 100px; min-width: 0; }
.gloss-input { flex: 2 1 140px; min-width: 0; }
.preview { font-size: var(--font-body); color: var(--text-secondary); word-break: break-all; }
.preview-text { font-family: monospace; color: var(--text-primary); }
.error-text { color: var(--danger); font-size: var(--font-small); }
.focus-editor > .el-button { align-self: flex-start; }
</style>
