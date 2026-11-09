<template>
  <el-tag
    v-if="label"
    class="knowledge-tag"
    :style="style"
    :closable="closable"
    :size="size"
    :title="title"
    @close="$emit('close', $event)"
  >
    <span v-if="showPath && context" class="knowledge-parent">{{ context }} / </span>{{ label }}<span v-if="primary" class="knowledge-primary">主</span>
  </el-tag>
  <span v-else class="knowledge-empty">—</span>
</template>
<script setup>
import { computed } from 'vue'
import { knowledgeColor, knowledgePath, loadKnowledgeColors } from '@/composables/knowledgeColors'

const props = defineProps({
  point: { type: [Object, String, Number], default: null },
  name: { type: [String, Number], default: '' },
  subjectId: { type: [String, Number], default: null },
  parentName: { type: String, default: '' },
  level: { type: Number, default: 0 },
  primary: { type: Boolean, default: false },
  showPath: { type: Boolean, default: false },
  closable: { type: Boolean, default: false },
  size: { type: String, default: 'small' },
})
defineEmits(['close'])

const label = computed(() => {
  if (props.point && typeof props.point === 'object') return props.point.name || ''
  return props.point ?? props.name
})
const context = computed(() => {
  if (props.parentName) return props.parentName
  if (props.point && typeof props.point === 'object') return props.point.parent_name || ''
  return ''
})
const style = computed(() => knowledgeColor(props.point ?? props.name, props.subjectId))
const title = computed(() => props.showPath ? knowledgePath(props.point) : label.value)

loadKnowledgeColors()
</script>
<style scoped>
.knowledge-tag{font-weight:550;max-width:100%;height:auto;white-space:normal;overflow-wrap:anywhere;line-height:1.6;padding:3px 9px;border-radius:6px;vertical-align:middle}
.knowledge-parent{opacity:.72;font-weight:450}
.knowledge-primary{margin-left:5px;padding:0 4px;border-radius:4px;background:rgba(52,104,223,.14);color:#2b55b4;font-size:10px}
.knowledge-empty{color:var(--text-muted)}
</style>
