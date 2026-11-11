<template>
  <!--
    默写字母格：点击时把焦点交给下面的隐藏输入框，手机才会弹出软键盘。
    mousedown 阻止默认行为，避免点格子时输入框先失焦、键盘先收起再弹出（闪一下）。
  -->
  <div
    class="letter-input"
    :class="{ compact }"
    @mousedown="keepInputFocus"
    @click="focusInput"
  >
    <div class="letter-cells">
      <!-- 每个词一组，整组换行，避免一个词被拆到两行 -->
      <div
        v-for="(group, g) in wordGroups"
        :key="g"
        class="letter-word"
        :class="{ gap: group.gapBefore }"
      >
        <div
          v-for="{ cell, i } in group.items"
          :key="i"
          class="letter-cell"
          :class="{
            fixed: cell.fixed,
            given: cell.fixed && isLetterOrDigit(cell.char),
            filled: !!answers[i],
            active: i === activeLetterIdx && !result,
            correct: cellStatus(cell) === 'correct',
            wrong: cellStatus(cell) === 'wrong'
          }"
        >
          {{ cell.fixed ? cell.char : (answers[i] || '') }}
        </div>
      </div>
    </div>
    <!--
      隐藏输入框：真正接收键盘输入的元素（电脑键盘和手机软键盘都走这里）。
      手机软键盘（尤其安卓、微信）按键时 keydown 拿不到具体字母，
      所以字母和退格都从 input 事件里读输入框的值来判断，见 handleInput。
    -->
    <input
      ref="inputRef"
      class="letter-hidden-input"
      type="text"
      inputmode="text"
      enterkeyhint="done"
      autocomplete="off"
      autocorrect="off"
      autocapitalize="off"
      spellcheck="false"
      aria-label="默写输入"
      @input="handleInput"
      @compositionend="handleInput"
      @keydown="handleKeydown"
    />
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { buildCells } from '@/composables/dictation'

const props = defineProps({
  // 题目对象，含 english 与可选 tokens
  question: { type: Object, required: true },
  // 是否禁用输入（已提交作答后为 true）
  disabled: { type: Boolean, default: false },
  // 紧凑模式：内容很长时用小一号的格子
  compact: { type: Boolean, default: false },
  // 判对结果 {tokenResults, correct}，未提交时为 null
  result: { type: Object, default: null },
  // v-model：与格子等长的各格内容
  modelValue: { type: Array, default: () => [] },
})
const emit = defineEmits(['update:modelValue', 'submit'])

const inputRef = ref(null)
const answers = ref([])
const activeLetterIdx = ref(0)

// 当前题目的字母格子，来源于 buildCells
// 固定格里的字母或数字按「给出的字母」样式显示；空格和标点保持窄格
const isLetterOrDigit = (char) => /[a-zA-Z0-9]/.test(char || '')

const cells = computed(() => buildCells(props.question))

// 把格子按词分组：有 tokens 时按 gapBefore 断开；旧样式里空格本身是一个固定格，单独成组
const wordGroups = computed(() => {
  const groups = []
  let current = null
  cells.value.forEach((cell, i) => {
    const isSpace = cell.fixed && cell.char === ' '
    if (!current || cell.gapBefore || isSpace || current.space) {
      current = { gapBefore: !!cell.gapBefore, space: isSpace, items: [] }
      groups.push(current)
    }
    current.items.push({ cell, i })
  })
  return groups
})

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

// 隐藏输入框里常驻的占位字符：有它在，按退格时输入框才有东西可删，
// 才会触发 input 事件（手机软键盘的退格只能靠这个识别）
const SENTINEL = ' '

/**
 * 把隐藏输入框的值还原成占位字符，并把光标放到末尾。
 */
function reset_input_value() {
  const el = inputRef.value
  if (!el) return
  el.value = SENTINEL
  try {
    el.setSelectionRange(SENTINEL.length, SENTINEL.length)
  } catch (err) {
    // 个别浏览器在输入框未聚焦时不允许设置光标，忽略即可
  }
}

/**
 * 聚焦隐藏输入框，唤起键盘（禁用时不聚焦）。
 * 注意：iOS 和微信只在「用户点击的同一个事件」里调用 focus 才会弹键盘，
 * 所以点击处理函数里要直接调用它，不能放进 setTimeout。
 */
function focus() {
  if (props.disabled) return
  const el = inputRef.value
  if (!el) return
  reset_input_value()
  // preventScroll：聚焦时不要让页面跳到隐藏输入框的位置
  el.focus({ preventScroll: true })
}

// 点击格子区域：在点击事件里同步聚焦隐藏输入框（已提交后不聚焦）
function focusInput() {
  focus()
}

/**
 * 按下鼠标/手指时阻止默认行为：否则焦点会先离开输入框，
 * 手机键盘会先收起再弹出。输入框本身不在这里处理。
 * @param {MouseEvent} e 鼠标事件
 */
function keepInputFocus(e) {
  if (e.target !== inputRef.value) e.preventDefault()
}

/**
 * 填入一个字母，并把光标跳到下一个可填格。
 * @param {string} letter 单个英文字母
 */
function type_letter(letter) {
  const cs = cells.value
  let idx = activeLetterIdx.value
  while (idx < cs.length && cs[idx].fixed) idx++
  if (idx >= cs.length) return
  answers.value[idx] = letter.toLowerCase()
  // 跳到下一个可填格
  let next = idx + 1
  while (next < cs.length && cs[next].fixed) next++
  activeLetterIdx.value = Math.min(next, cs.length - 1)
}

/**
 * 退格：当前格有内容则清空；否则回退到上一个可填格并清空它。
 */
function delete_letter() {
  const cs = cells.value
  const idx = activeLetterIdx.value
  if (idx < cs.length && !cs[idx].fixed && answers.value[idx]) {
    answers.value[idx] = ''
    return
  }
  let i = idx - 1
  while (i >= 0 && cs[i].fixed) i--
  if (i >= 0) {
    answers.value[i] = ''
    activeLetterIdx.value = i
  }
}

/**
 * 处理隐藏输入框的内容变化（电脑和手机统一走这里）。
 * - 值比占位字符短：说明按了退格，删一个字母。
 * - 值里出现英文字母：逐个填进格子；中文、数字、标点直接丢掉。
 * 处理完把输入框还原成占位字符，等下一次输入。
 */
function handleInput() {
  const el = inputRef.value
  if (!el) return
  const value = el.value
  if (props.disabled) {
    reset_input_value()
    return
  }
  let changed = false
  if (value.length < SENTINEL.length) {
    delete_letter()
    changed = true
  } else {
    // 拼音输入法下孩子直接敲字母，也按英文字母收下
    const letters = value.match(/[a-zA-Z]/g) || []
    for (const letter of letters) type_letter(letter)
    changed = letters.length > 0
  }
  reset_input_value()
  if (changed) emit('update:modelValue', answers.value.slice())
}

/**
 * 键盘处理：只管回车提交。字母和退格交给 handleInput，
 * 因为手机软键盘的 keydown 往往拿不到具体按键（key 为 Unidentified）。
 * @param {KeyboardEvent} e 键盘事件
 */
function handleKeydown(e) {
  if (e.key === 'Enter') {
    e.preventDefault()
    if (props.disabled) return
    emit('submit')
  }
}

// 题目变化时自动重置作答
watch(() => props.question, reset, { immediate: true })

// 挂载后先放好占位字符，保证第一次按退格也能被识别
onMounted(reset_input_value)

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
  min-height: 0;
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
  height: 50px;
  border: 1.5px solid #c9cde0;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 26px;
  font-weight: 600;
  color: var(--text-primary);
  text-transform: lowercase;
  box-sizing: border-box;
  background: var(--bg-primary);
  border-radius: var(--radius-md);
  transition: background-color .15s ease, border-color .15s ease;
}

/* 一个词的格子：整组不拆行；单个词比整行还宽时才允许在词内换行 */
.letter-word {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 8px;
  max-width: 100%;
}

/* 词组档位下词间空格不占格，用词组左侧留白表示词间距 */
.letter-word.gap {
  margin-left: 14px;
}

.letter-cell.fixed {
  border-color: transparent;
  background: transparent;
  color: var(--text-muted);
  font-size: 24px;
  min-width: 20px;
  width: auto;
  padding: 0 4px;
}


.letter-cell.active {
  border-color: var(--accent-blue);
  background: var(--el-color-primary-light-9);
}

/* 已填的格子：白底加淡主题色底线；固定格（标点、空格、给出的字母）不套用 */
.letter-cell.filled:not(.fixed) {
  background: var(--bg-primary);
  border-color: var(--el-color-primary-light-5);
}

.letter-cell.correct {
  border-color: var(--success);
  color: var(--success);
  background: #eaf5f0;
}

.letter-cell.wrong {
  border-color: var(--danger);
  color: var(--danger);
  background: #fbecee;
}

/* 直接给出的字母（显示的词、首字母提示）：与填写格同宽同字号，只去掉底色，保持整行对齐 */
.letter-cell.fixed.given {
  width: 42px;
  min-width: 0;
  padding: 0;
  font-size: 26px;
  /* 给出的字母用主题色、不带框，和孩子自己填的方格区分开 */
  color: var(--accent-blue);
  background: transparent;
  border-color: transparent;
}

/* 紧凑模式：长句、长词组用小一号的格子，减少行数 */
.letter-input.compact .letter-cell,
.letter-input.compact .letter-cell.fixed.given {
  width: 30px;
  height: 38px;
  font-size: 18px;
  border-radius: var(--radius-sm);
}

.letter-input.compact .letter-cell.fixed:not(.given) {
  width: auto;
  min-width: 10px;
  font-size: 18px;
  padding: 0 2px;
}

.letter-input.compact .letter-word,
.letter-input.compact .letter-cells {
  gap: 4px;
}

.letter-input.compact .letter-word.gap {
  margin-left: 8px;
}

/*
  隐藏输入框：看不见但必须「可聚焦」。
  不能用 display:none / visibility:hidden，否则手机不弹键盘；
  字号至少 16px，否则 iOS 聚焦时会自动放大页面。
*/
.letter-hidden-input {
  position: absolute;
  top: 0;
  left: 50%;
  width: 1px;
  height: 1px;
  padding: 0;
  border: 0;
  opacity: 0;
  font-size: 16px;
  color: transparent;
  caret-color: transparent;
  background: transparent;
  pointer-events: none;
}

@media (max-width: 768px) {
  .letter-cell {
    width: 31px;
    height: 42px;
    font-size: 21px;
    border-radius: var(--radius-sm);
  }
  .letter-word {
    gap: 5px;
  }
  .letter-word.gap {
    margin-left: 9px;
  }
  .letter-cell.fixed.given {
    width: 31px;
    font-size: 21px;
  }
  .letter-cells {
    gap: 5px;
  }
}

/* 手机窄屏：格子再收窄一些，让 10 个字母左右的长词能放在一行 */
@media (max-width: 480px) {
  .letter-cell,
  .letter-cell.fixed.given {
    width: 27px;
    height: 38px;
    font-size: 19px;
  }
  .letter-word,
  .letter-cells {
    gap: 3px;
  }
  .letter-cells {
    padding: 8px 0;
  }
}
</style>
