<template>
  <span class="math-text" :class="{ 'math-text-invalid': errors.length }">
    <span ref="content" class="math-text-content"></span>
    <span v-if="errors.length" class="math-text-error" role="alert">{{ errors.join('；') }}</span>
  </span>
</template>

<script setup>
import { ref, watch, onMounted } from 'vue'
import autoRender from 'katex/contrib/auto-render'
import 'katex/dist/katex.min.css'
import { renderMathText } from '../../../shared/math-text.mjs'

const props = defineProps({ text: { type: [String, Number], default: '' } })
const content = ref(null)
const errors = ref([])
const render = () => {
  if (content.value) errors.value = renderMathText(content.value, props.text, autoRender)
}
onMounted(render)
watch(() => props.text, render, { flush: 'post' })
</script>

<style>
.math-text { display: inline-block; vertical-align: middle; max-width: 100%; overflow-x: auto; white-space: pre-wrap; overflow-wrap: anywhere; line-height: 1.9; }
.math-text-content { white-space: pre-wrap; }
.math-text .katex { white-space: nowrap; }
.math-text .katex-display { overflow-x: auto; overflow-y: hidden; padding: .3em 0; }
.math-text-error { display: block; color: #c45656; font-size: 12px; }
</style>
