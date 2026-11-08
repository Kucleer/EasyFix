<template><div class="subject-rankings"><section v-for="group in groups" :key="group.name" class="subject-ranking"><header><strong>{{ group.name }}</strong><span>知识点 TOP {{ limit }}</span></header><el-table :data="group.items" empty-text="暂无该学科知识点记录"><el-table-column prop="point" label="知识点" min-width="150"><template #default="{ row }"><KnowledgeTag :name="row.point" :subject-id="row.subject_id || group.subjectId" /></template></el-table-column><el-table-column prop="count" :label="countLabel" width="85" align="right" /></el-table></section></div></template>
<script setup>
import { computed } from 'vue'
const props = defineProps({items:{type:Array,default:()=>[]},subjects:{type:Array,default:()=>[]},subjectId:{type:Number,default:null},limit:{type:Number,default:10},countLabel:{type:String,default:'错题数'}})
const groups = computed(() => {
 const map = new Map()
 const available = props.subjectId ? props.subjects.filter(s=>s.id===props.subjectId) : props.subjects
 available.forEach(s=>map.set(s.name,{name:s.name,subjectId:s.id,items:[]}))
 props.items.forEach(item=>{
  let point = item.point?.trim() || '未标注知识点'
  let name = item.subject_name || props.subjects.find(s=>s.id===item.subject_id)?.name
  if(!name){const matched=props.subjects.find(s=>point.startsWith(s.name+' · ')||point.startsWith(s.name+'·'));if(matched){name=matched.name;point=point.slice(name.length).replace(/^\s*·\s*/,'')}}
  if(!name && props.subjectId)name=props.subjects.find(s=>s.id===props.subjectId)?.name
  name=name||'未标注学科'
  if(!map.has(name))map.set(name,{name,items:[]})
  map.get(name).items.push({...item,point})
 })
 return [...map.values()].map(g=>({...g,items:g.items.sort((a,b)=>b.count-a.count).slice(0,props.limit)}))
})
</script>
<style scoped>
.subject-rankings{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px}.subject-ranking{min-width:0;border:1px solid var(--border-light);border-radius:9px;overflow:hidden}.subject-ranking header{display:flex;justify-content:space-between;align-items:center;padding:12px 14px;background:#f6f5ff}.subject-ranking header span{font-size:12px;color:var(--text-muted)}.subject-rankings:has(>section:only-child){grid-template-columns:minmax(0,1fr)}@media(max-width:700px){.subject-rankings{grid-template-columns:minmax(0,1fr)}}
</style>