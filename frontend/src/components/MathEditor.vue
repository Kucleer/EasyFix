<template>
  <div class="math-editor">
    <el-input ref="input" :model-value="modelValue" type="textarea" :rows="rows" :placeholder="placeholder" @update:model-value="$emit('update:modelValue', $event)" />
    <div class="math-editor-tools">
      <el-button v-for="item in templates" :key="item.label" size="small" @click="insert(item.value)">{{ item.label }}</el-button>
      <span>公式用 \(…\) 包裹，独立公式用 \[…\]</span>
    </div>
    <div v-if="modelValue" class="math-editor-preview"><MathText :text="modelValue" /></div>
  </div>
</template>

<script setup>
import { ref, nextTick } from 'vue'
import MathText from './MathText.vue'
const props = defineProps({ modelValue: { type: String, default: '' }, rows: { type: Number, default: 4 }, placeholder: String })
const emit = defineEmits(['update:modelValue'])
const input = ref(null)
const templates = [
  { label: '次方', value: '\\(x^{2}\\)' },
  { label: '分数', value: '\\(\\frac{a}{b}\\)' },
  { label: '根号', value: '\\(\\sqrt{x}\\)' },
]
const insert = async (value) => {
  const textarea = input.value?.textarea
  const start = textarea?.selectionStart ?? props.modelValue.length
  const end = textarea?.selectionEnd ?? start
  emit('update:modelValue', props.modelValue.slice(0, start) + value + props.modelValue.slice(end))
  await nextTick()
  textarea?.focus()
  textarea?.setSelectionRange(start + value.length, start + value.length)
}
</script>

<style scoped>
.math-editor { width: 100%; }
.math-editor-tools { display: flex; flex-wrap: wrap; align-items: center; gap: 6px; margin: 8px 0; }
.math-editor-tools span { color: #777; font-size: 12px; }
.math-editor-preview { padding: 10px; border: 1px dashed #ccc; border-radius: 4px; overflow-x: auto; }
</style>
