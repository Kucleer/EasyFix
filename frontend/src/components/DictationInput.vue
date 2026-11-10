<template>
  <!-- 默写字母格：点击聚焦唤起键盘，键盘输入填格并判对 -->
  <div
    ref="boxRef"
    class="letter-input"
    tabindex="0"
    @click="focusInput"
    @keydown="handleKeydown"
  >
    <div class="letter-cells">
      <div
        v-for="(cell, i) in cells"
        :key="i"
        class="letter-cell"
        :class="{
          fixed: cell.fixed,
          gap: cell.gapBefore,
          filled: !!answers[i],
          active: i === activeLetterIdx && !result,
          correct: cellStatus(cell) === 'correct',
          wrong: cellStatus(cell) === 'wrong'
        }"
      >
        {{ cell.fixed ? cell.char : (answers[i] || '') }}
      </div>
    </div>
    <!-- 隐藏输入框：在手机上唤起软键盘，沿用旧实现 -->
    <input
      ref="inputRef"
      class="letter-hidden-input"
      autocomplete="off"
      autocapitalize="off"
      spellcheck="false"
    />
  </div>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { buildCells } from '@/composables/dictation'

const props = defineProps({
  // 题目对象，含 english 与可选 tokens
  question: { type: Object, required: true },
  // 是否禁用输入（已提交作答后为 true）
  disabled: { type: Boolean, default: false },
  // 判对结果 {tokenResults, correct}，未提交时为 null
  result: { type: Object, default: null },
  // v-model：与格子等长的各格内容
  modelValue: { type: Array, default: () => [] },
})
const emit = defineEmits(['update:modelValue', 'submit'])

const boxRef = ref(null)
const inputRef = ref(null)
const answers = ref([])
const activeLetterIdx = ref(0)

// 当前题目的字母格子，来源于 buildCells
const cells = computed(() => buildCells(props.question))

// 按词对错查表：{tokenIndex: ok}
const tokenOkMap = computed(() => {
  const map = {}
  const results = props.result?.tokenResults
  if (Array.isArray(results)) {
    for (const r of results) map[r.i] = r.ok
  }
  return map
})

/**
 * 返回某个格子的判对状态：correct / wrong / null。
 * 未提交或预填格返回 null；有 tokenResults 时按所属词对错，否则按整条对错。
 * @param {object} cell 格子对象
 * @returns {string|null}
 */
function cellStatus(cell) {
  if (!props.result || cell.fixed) return null
  // 无 tokenResults（无 tokens 题目）：整条对错
  if (!Array.isArray(props.result.tokenResults)) {
    return props.result.correct ? 'correct' : 'wrong'
  }
  // 有 tokenResults：按该格所属词对错，非空出词的格子不着色
  const ok = tokenOkMap.value[cell.token]
  if (ok === undefined) return null
  return ok ? 'correct' : 'wrong'
}

/**
 * 重新初始化作答数组：预填格填入自带字符，光标落到第一个可填格。
 */
function reset() {
  const cs = cells.value
  answers.value = cs.map(c => (c.fixed ? c.char : ''))
  const first = cs.findIndex(c => !c.fixed)
  activeLetterIdx.value = first >= 0 ? first : 0
  emit('update:modelValue', answers.value.slice())
}

/**
 * 聚焦输入区，唤起键盘（禁用时不聚焦）。
 */
function focus() {
  if (props.disabled) return
  boxRef.value?.focus()
}

// 点击聚焦（已提交后不聚焦）
function focusInput() {
  if (props.disabled) return
  boxRef.value?.focus()
}

/**
 * 键盘处理：字母键填入并跳到下一个可填格，退格清空或回退，回车触发 submit。
 * @param {KeyboardEvent} e 键盘事件
 */
function handleKeydown(e) {
  if (props.disabled) return

  if (e.key === 'Backspace') {
    e.preventDefault()
    const cs = cells.value
    const idx = activeLetterIdx.value
    // 当前格有内容则清空；否则回退到上一个可填格
    if (idx < cs.length && !cs[idx].fixed && answers.value[idx]) {
      answers.value[idx] = ''
      emit('update:modelValue', answers.value.slice())
      return
    }
    let i = idx - 1
    while (i >= 0 && cs[i].fixed) i--
    if (i >= 0) {
      answers.value[i] = ''
      activeLetterIdx.value = i
      emit('update:modelValue', answers.value.slice())
    }
    return
  }

  if (e.key === 'Enter') {
    e.preventDefault()
    emit('submit')
    return
  }

  if (/^[a-zA-Z]$/.test(e.key)) {
    e.preventDefault()
    const cs = cells.value
    let idx = activeLetterIdx.value
    while (idx < cs.length && cs[idx].fixed) idx++
    if (idx >= cs.length) return
    answers.value[idx] = e.key.toLowerCase()
    // 跳到下一个可填格
    let next = idx + 1
    while (next < cs.length && cs[next].fixed) next++
    activeLetterIdx.value = Math.min(next, cs.length - 1)
    emit('update:modelValue', answers.value.slice())
  }
}

// 题目变化时自动重置作答
watch(() => props.question, reset, { immediate: true })

defineExpose({ focus, reset })
</script>

<style scoped>
.letter-input {
  outline: none;
  cursor: text;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  position: relative;
  min-height: 80px;
  width: 100%;
}

.letter-cells {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 8px;
  max-width: 100%;
  padding: 8px 4px;
}

.letter-cell {
  width: 42px;
  height: 52px;
  border-bottom: 3px solid #c0c4cc;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 28px;
  font-weight: 600;
  color: var(--text-primary);
  text-transform: lowercase;
  box-sizing: border-box;
  background: #fafafa;
  border-radius: 6px 6px 0 0;
}

/* 词组档位下词间空格不占格，用 gap 格的左侧留白表示词间距 */
.letter-cell.gap {
  margin-left: 22px;
}

.letter-cell.fixed {
  border-bottom-color: transparent;
  background: transparent;
  color: var(--text-muted);
  font-size: 24px;
  min-width: 20px;
  width: auto;
  padding: 0 4px;
}

.letter-cell.active {
  border-bottom-color: var(--accent-blue);
  box-shadow: 0 2px 0 var(--accent-blue);
  background: #ecf5ff;
}

.letter-cell.filled {
  background: #fff;
}

.letter-cell.correct {
  border-bottom-color: #67c23a;
  color: #67c23a;
  background: #f0f9eb;
}

.letter-cell.wrong {
  border-bottom-color: #f56c6c;
  color: #f56c6c;
  background: #fef0f0;
}

.letter-hidden-input {
  position: absolute;
  opacity: 0;
  width: 1px;
  height: 1px;
  pointer-events: none;
}

@media (max-width: 768px) {
  .letter-cell {
    width: 31px;
    height: 44px;
    font-size: 23px;
  }
  .letter-cell.gap {
    margin-left: 14px;
  }
  .letter-cells {
    gap: 5px;
  }
}
</style>
