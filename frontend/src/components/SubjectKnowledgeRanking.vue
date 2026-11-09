<template>
  <div class="subject-rankings">
    <section v-for="group in groups" :key="group.name" class="subject-ranking">
      <header><strong>{{ group.name }}</strong><span>一级模块 TOP {{ limit }}</span></header>
      <el-table :data="group.items" empty-text="暂无该学科错题模块记录" class="ranking-table" @row-click="row => $emit('select', row)">
        <el-table-column label="知识模块" min-width="160">
          <template #default="{ row }">
            <span class="module-link">
              <KnowledgeTag
                :point="row.pointObject"
                :name="row.point"
                :subject-id="row.subject_id || group.subjectId"
                show-path
              />
            </span>
            <el-tag v-if="row.unclassified" size="small" type="info">未分类</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="count" :label="countLabel" width="90" align="right" />
        <el-table-column v-if="showAccuracy" label="模块练习正确率" width="130" align="right">
          <template #default="{ row }">
            <span v-if="row.accuracy == null" class="muted">暂无练习记录</span>
            <span v-else>{{ row.accuracy }}%</span>
          </template>
        </el-table-column>
      </el-table>
    </section>
  </div>
</template>
<script setup>
import { computed } from 'vue'
import KnowledgeTag from '@/components/KnowledgeTag.vue'

const props = defineProps({
  items: { type: Array, default: () => [] },
  subjects: { type: Array, default: () => [] },
  subjectId: { type: Number, default: null },
  limit: { type: Number, default: 10 },
  countLabel: { type: String, default: '收录题数' },
  showAccuracy: { type: Boolean, default: true },
})
defineEmits(['select'])

const groups = computed(() => {
  const map = new Map()
  const available = props.subjectId
    ? props.subjects.filter(subject => subject.id === props.subjectId)
    : props.subjects
  available.forEach(subject => map.set(subject.name, { name: subject.name, subjectId: subject.id, items: [] }))
  for (const item of props.items) {
    let point = (item.point ?? item.name ?? '').trim() || '未标注知识点'
    let subjectName = item.subject_name || props.subjects.find(subject => subject.id === item.subject_id)?.name
    if (!subjectName) {
      const matched = props.subjects.find(subject => point.startsWith(subject.name + ' · ') || point.startsWith(subject.name + '·'))
      if (matched) {
        subjectName = matched.name
        point = point.slice(matched.name.length).replace(/^\s*·\s*/, '')
      }
    }
    if (!subjectName && props.subjectId) subjectName = props.subjects.find(subject => subject.id === props.subjectId)?.name
    subjectName = subjectName || '未标注学科'
    if (!map.has(subjectName)) map.set(subjectName, { name: subjectName, items: [] })
    const count = item.count ?? item.question_count ?? 0
    map.get(subjectName).items.push({
      ...item,
      point,
      count,
      pointObject: {
        id: item.module_id ?? item.id ?? point,
        name: point,
        subject_id: item.subject_id,
        parent_name: item.parent_name || '',
      },
    })
  }
  return [...map.values()].map(group => ({
    ...group,
    items: group.items.sort((left, right) => right.count - left.count).slice(0, props.limit),
  }))
})
</script>
<style scoped>
.subject-rankings{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px}
.subject-ranking{min-width:0;border:1px solid var(--border-light);border-radius:9px;overflow:hidden}
.subject-ranking header{display:flex;justify-content:space-between;align-items:center;padding:12px 14px;background:#f6f5ff}
.subject-ranking header span{font-size:12px;color:var(--text-muted)}
.muted{color:var(--text-muted)}
.ranking-table :deep(tbody tr){cursor:pointer}
.ranking-table :deep(tbody tr:hover) .module-link{text-decoration:underline}
.subject-rankings:has(>section:only-child){grid-template-columns:minmax(0,1fr)}
@media(max-width:700px){.subject-rankings{grid-template-columns:minmax(0,1fr)}}
</style>
