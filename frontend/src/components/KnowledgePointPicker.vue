<template>
  <div class="knowledge-picker" :class="{ compact }">
    <div class="picker-row">
      <el-tree-select
        v-model="selected"
        class="picker-tree"
        :data="treeData"
        multiple
        show-checkbox
        check-strictly
        clearable
        filterable
        :render-after-expand="false"
        :disabled="disabled"
        :placeholder="treeLoading ? '加载知识点…' : '选择二级知识点'"
        :props="treeProps"
        @change="onSelectionChange"
      />
      <el-select
        v-model="primary"
        class="picker-primary"
        :disabled="disabled || !selected.length"
        :placeholder="selected.length ? '选择主考点' : '先选二级知识点'"
        @change="onPrimaryChange"
      >
        <el-option v-for="item in selectedPoints" :key="item.id" :label="item.name" :value="item.id" />
      </el-select>
    </div>
    <p v-if="selected.length && !primary" class="picker-hint warn">请指定主考点：模块占比统计只按主考点归属。</p>
    <p v-else-if="!selected.length" class="picker-hint">未选择知识点时按“未分类”处理，不会自动猜测。</p>
    <div v-if="selectedPoints.length" class="picker-tags">
      <KnowledgeTag
        v-for="item in selectedPoints"
        :key="item.id"
        :point="item"
        :primary="item.id === primary"
        size="small"
      />
    </div>
  </div>
</template>
<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { questionApi } from '@/api/question'
import KnowledgeTag from '@/components/KnowledgeTag.vue'

const props = defineProps({
  modelValue: { type: Array, default: () => [] },
  primaryId: { type: [Number, String], default: null },
  subjectId: { type: [Number, String], default: null },
  disabled: { type: Boolean, default: false },
  compact: { type: Boolean, default: true },
})
const emit = defineEmits(['update:modelValue', 'update:primaryId', 'change'])

const treeProps = { value: 'id', label: 'name', children: 'children', disabled: 'disabled' }
const treeData = ref([])
const treeLoading = ref(false)
const selected = ref([])
const primary = ref(null)
const points = ref(new Map())

function flatten(items, parentName = '') {
  const result = []
  for (const item of items || []) {
    const record = { ...item, parent_name: parentName || item.parent_name || '' }
    result.push(record)
    if (item.children?.length) result.push(...flatten(item.children, item.name))
  }
  return result
}

const selectedPoints = computed(() => selected.value
  .map(id => points.value.get(String(id)))
  .filter(point => point && point.level !== 1))

function syncFromProps() {
  const ids = (props.modelValue || []).map(value => Number(value)).filter(Boolean)
  selected.value = [...new Set(ids)]
  const current = props.primaryId == null ? null : Number(props.primaryId)
  primary.value = selected.value.includes(current) ? current : null
}

function emitChange() {
  emit('update:modelValue', [...selected.value])
  emit('update:primaryId', primary.value)
  emit('change', { ids: [...selected.value], primary: primary.value })
}

function onSelectionChange() {
  selected.value = [...new Set((selected.value || [])
    .map(value => Number(value))
    .filter(value => points.value.get(String(value))?.level !== 1)
    .filter(Boolean))]
  if (!selected.value.length) {
    primary.value = null
  } else if (selected.value.length === 1) {
    primary.value = selected.value[0]
  } else if (!selected.value.includes(primary.value)) {
    // 多选时不能静默改主考点：由用户明确选择，未选前阻止保存。
    primary.value = null
  }
  emitChange()
}

function onPrimaryChange() {
  emitChange()
}

async function loadTree() {
  if (props.subjectId == null) {
    treeData.value = []
    points.value = new Map()
    if (selected.value.length || primary.value != null) {
      selected.value = []
      primary.value = null
      emitChange()
    }
    return
  }
  treeLoading.value = true
  try {
    const { data } = await questionApi.getKnowledgePointTree({ subject_id: props.subjectId })
    const items = (data.items || []).map(module => ({
      ...module,
      disabled: true,
      children: (module.children || []).map(child => ({ ...child, disabled: false })),
    }))
    treeData.value = items
    points.value = new Map(flatten(items).map(item => [String(item.id), item]))
    const available = new Set([...points.value.values()]
      .filter(item => item.level !== 1)
      .map(item => String(item.id)))
    const kept = selected.value.filter(id => available.has(String(id)))
    if (kept.length !== selected.value.length) {
      selected.value = kept
      if (!kept.includes(primary.value)) primary.value = kept.length === 1 ? kept[0] : null
      emitChange()
    }
  } finally {
    treeLoading.value = false
  }
}

onMounted(() => {
  syncFromProps()
  loadTree()
})

watch(() => props.modelValue, (value) => {
  const next = (value || []).map(item => Number(item)).filter(Boolean)
  if (next.join(',') !== selected.value.join(',')) syncFromProps()
}, { deep: true })

watch(() => props.primaryId, (value) => {
  const next = value == null ? null : Number(value)
  if (next !== primary.value) primary.value = selected.value.includes(next) ? next : primary.value
})

watch(() => props.subjectId, () => {
  syncFromProps()
  loadTree()
})

defineExpose({ loadTree })
</script>
<style scoped>
.knowledge-picker{display:flex;flex-direction:column;gap:8px;width:100%}
.picker-row{display:flex;gap:10px;flex-wrap:wrap}
.picker-tree{flex:1 1 240px;min-width:0}
.picker-primary{flex:0 1 180px;min-width:140px}
.picker-hint{margin:0;font-size:12px;color:var(--text-muted)}
.picker-hint.warn{color:#b45309}
.picker-tags{display:flex;flex-wrap:wrap;gap:6px}
@media(max-width:640px){.picker-row{flex-direction:column}.picker-primary{flex:1 1 auto;width:100%}}
</style>
