<template><el-tag v-if="name" class="knowledge-tag" :style="knowledgeColor(name, subjectId)" :closable="closable" :size="size" @close="$emit('close', $event)">{{ name }}</el-tag><span v-else class="knowledge-empty">—</span></template>
<script setup>
import { knowledgeColor, loadKnowledgeColors } from '@/composables/knowledgeColors'
defineProps({ name: [String, Number], subjectId: [String, Number], closable: Boolean, size: { type: String, default: 'small' } })
defineEmits(['close'])
loadKnowledgeColors()
</script>
<style scoped>.knowledge-tag{font-weight:550;max-width:100%;height:auto;white-space:normal;overflow-wrap:anywhere;line-height:1.6;padding:3px 9px;border-radius:6px;vertical-align:middle}.knowledge-empty{color:var(--text-muted)}</style>
