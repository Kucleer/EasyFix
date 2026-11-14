<template>
  <div class="learning-analysis">
    <PageHeading title="每一点进步，都看得见" description="根据真实错题、单词和练习记录，找到下一步巩固的方向。"><el-button :loading="loading" @click="loadStats">刷新数据</el-button></PageHeading>
    <div class="filters"><el-select v-model="selectedSubject" placeholder="全部学科" clearable @change="changeSubject" style="width:180px"><el-option v-for="subject in subjects" :key="subject.id" :label="subject.name" :value="subject.id" /></el-select></div>
    <el-alert v-if="error" :title="error" type="error" show-icon :closable="false" class="load-error" />
    <div v-loading="loading">
      <div class="analysis-metrics"><article v-for="metric in metrics" :key="metric.label" class="metric"><span>{{ metric.label }}</span><strong>{{ loaded ? metric.value : '—' }}</strong><small>{{ metric.note }}</small></article></div>
      <el-alert v-if="unclassifiedCount" class="load-error" type="warning" :closable="false" show-icon>
        <template #title>
          未分类错题 {{ unclassifiedCount }} 道，未计入任何知识模块占比。
          <el-button link type="primary" @click="goUnclassified">去错题列表处理</el-button>
        </template>
      </el-alert>
      <el-tabs v-model="activeTab">
        <el-tab-pane label="错题与知识点" name="questions">
          <div class="analysis-grid"><el-card class="full"><template #header>一级知识模块</template><p class="chart-note">默认按一级模块聚合，点击模块可下钻二级。题数按任一关联去重；占比只按主考点归属，未分类单独计数。“模块练习正确率”来自练习最终批改状态，与题目累计批改次数不同。</p><SubjectKnowledgeRanking :items="knowledgePoints" :subjects="subjects" :subject-id="selectedSubject || null" @select="drillDown" /></el-card><el-card><template #header>错题复习覆盖</template><VChart v-if="reviewTotal" :option="reviewOption" autoresize class="chart" /><el-empty v-else description="暂无错题复习数据" /></el-card>
          <el-card v-if="drillParent" class="full"><template #header><div class="card-header"><span>{{ drillParent.name }} · 二级考点下钻</span><el-button size="small" @click="clearDrill">返回一级</el-button></div></template><p class="chart-note">占比为模块内主考点占比；正确率相同时按题数排序。</p><el-table v-loading="drillLoading" :data="drillItems" empty-text="该模块暂无有效二级记录"><el-table-column prop="name" label="二级考点" min-width="180" /><el-table-column prop="question_count" label="收录题数" width="100" align="right" /><el-table-column label="模块内占比" width="110" align="right"><template #default="{row}">{{ row.parent_share_percent == null ? '—' : row.parent_share_percent + '%' }}</template></el-table-column><el-table-column label="复习覆盖" width="110" align="right"><template #default="{row}">{{ row.review_coverage == null ? '—' : row.review_coverage + '%' }}</template></el-table-column><el-table-column label="模块练习正确率" width="140" align="right"><template #default="{row}"><span v-if="row.accuracy == null" class="text-muted">暂无练习记录</span><span v-else>{{ row.accuracy }}%</span></template></el-table-column><el-table-column label="操作" width="100"><template #default="{row}"><el-button link type="primary" @click="viewPointQuestions(row)">查看错题</el-button></template></el-table-column></el-table></el-card>
          <el-card><template #header>错题累计正确率趋势</template><p class="chart-note">按已批阅错题练习的创建日期统计累计正确率。</p><VChart v-if="questionStats.accuracy_trend?.length" :option="questionTrend" autoresize class="chart" /><el-empty v-else description="完成并批阅练习后显示" /></el-card></div>
        </el-tab-pane>
        <el-tab-pane label="单词温习" name="words"><div class="analysis-grid"><el-card><template #header>单词复习次数分布</template><p class="chart-note">未复习 / 1–3 次 / 4 次及以上；仅表示复习次数。</p><VChart v-if="wordStats.total" :option="wordOption" autoresize class="chart" /><el-empty v-else description="暂无单词" /></el-card><el-card><template #header>单词复习频率</template><VChart v-if="wordStats.frequency_trend?.length" :option="frequencyOption" autoresize class="chart" /><el-empty v-else description="暂无复习记录" /></el-card><el-card class="full"><template #header>需要关注的单词</template><p class="chart-note">已复习且正确率低于 70% 的单词，最多显示 20 个。</p><el-table :data="wordStats.low_accuracy_words || []" empty-text="暂无低正确率单词"><el-table-column prop="word" label="单词" min-width="160" /><el-table-column label="正确率" width="120"><template #default="{row}">{{ row.accuracy }}%</template></el-table-column></el-table></el-card></div></el-tab-pane>
        <el-tab-pane label="练习记录" name="practice"><div class="analysis-grid"><el-card><template #header>每周练习分布</template><p class="chart-note">全部历史练习，按创建日期的星期汇总。</p><VChart v-if="Object.keys(practiceStats.frequency_heatmap || {}).length" :option="practiceOption" autoresize class="chart" /><el-empty v-else description="暂无练习记录" /></el-card><el-card><template #header>错题难度分布</template><VChart v-if="questionStats.total" :option="difficultyOption" autoresize class="chart" /><el-empty v-else description="暂无错题" /></el-card></div></el-tab-pane>
        <el-tab-pane label="学习建议" name="suggestions"><el-card><template #header><div class="card-header"><span>结合记录生成学习建议</span><el-button type="primary" :loading="suggesting" :disabled="!loaded" @click="generateSuggestions">生成建议</el-button></div></template><p class="chart-note">点击后调用已配置的模型。建议基于学习记录生成，供安排复习时参考。</p><el-alert v-if="suggestionError" :title="suggestionError" type="error" :closable="false" /><el-empty v-if="!suggestions.length && !suggesting && !suggestionError" description="点击生成建议，获取针对性的复习方向" /><article v-for="(item,index) in suggestions" :key="index" class="suggestion"><el-tag>{{ item.type || '学习建议' }}</el-tag><p>{{ item.content }}</p></article></el-card></el-tab-pane>
      </el-tabs>
    </div>
  </div>
</template>
<script setup>
import SubjectKnowledgeRanking from '@/components/SubjectKnowledgeRanking.vue'
import PageHeading from '@/components/PageHeading.vue'
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { questionApi } from '@/api/question'
import { learningAnalysisApi } from '@/api/learning_analysis'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { PieChart, BarChart, LineChart } from 'echarts/charts'
import { TooltipComponent, LegendComponent, GridComponent } from 'echarts/components'
use([CanvasRenderer, PieChart, BarChart, LineChart, TooltipComponent, LegendComponent, GridComponent])
const activeTab = ref('questions')
const selectedSubject = ref(null)
const subjects = ref([])
const router = useRouter()
questionApi.listSubjects().then(({data}) => { subjects.value = data }).catch(() => {})
function changeSubject() { suggestions.value = []; suggestionError.value = ''; clearDrill(); loadStats() }
const loading = ref(false)
const loaded = ref(false)
const error = ref('')
const data = ref({})
const suggestions = ref([])
const suggesting = ref(false)
const suggestionError = ref('')
const questionStats = computed(() => data.value.question_stats || {})
const wordStats = computed(() => data.value.word_stats || {})
const practiceStats = computed(() => data.value.practice_stats || {})
const review = computed(() => questionStats.value.review_effectiveness || {})
const reviewTotal = computed(() => Object.values(review.value).reduce((a,b) => a + b, 0))
const knowledge = computed(() => data.value.knowledge || {})
const knowledgeModules = computed(() => knowledge.value.modules || [])
const unclassifiedCount = computed(() => knowledge.value.unclassified_count || 0)
const knowledgePoints = computed(() => {
  if (knowledgeModules.value.length) {
    return knowledgeModules.value.map(module => ({
      module_id: module.id,
      id: module.id,
      point: module.name,
      subject_id: module.subject_id,
      subject_name: module.subject_name,
      count: module.question_count,
      accuracy: module.accuracy,
      review_coverage: module.review_coverage,
      share_percent: module.share_percent,
    }))
  }
  return (questionStats.value.top_error_knowledge_points || []).map(item => ({
    ...item,
    point: item.point?.trim() || '未标注知识点',
  }))
})
const drillParent = ref(null)
const drillItems = ref([])
const drillLoading = ref(false)

async function drillDown(row) {
  const moduleId = row?.module_id ?? row?.id
  if (!moduleId) return
  drillParent.value = { id: moduleId, name: row.point }
  drillLoading.value = true
  try {
    const { data: response } = await learningAnalysisApi.getKnowledgeStats({
      subject_id: selectedSubject.value || row.subject_id || undefined,
      level: 2,
      parent_id: moduleId,
    })
    drillItems.value = response.items || []
  } catch (error) {
    drillItems.value = []
    error.value = error.response?.data?.detail || '二级下钻加载失败'
  } finally {
    drillLoading.value = false
  }
}
function clearDrill() {
  drillParent.value = null
  drillItems.value = []
  drillLoading.value = false
}
function goUnclassified() {
  router.push({ path: '/questions', query: { unclassified: '1', ...(selectedSubject.value ? { subject_id: selectedSubject.value } : {}) } })
}
function viewPointQuestions(row) {
  router.push({
    path: '/questions',
    query: {
      ...(selectedSubject.value ? { subject_id: selectedSubject.value } : {}),
      knowledge_parent_id: drillParent.value?.id,
      knowledge_point_id: row.id,
    },
  })
}
const metrics = computed(() => [
  { label: '累计错题', value: questionStats.value.total || 0, note: '全部未删除错题' },
  { label: '尚未复习错题', value: review.value.not_reviewed || 0, note: '复习次数为 0' },
  { label: '单词待复习', value: wordStats.value.memory_curve_status?.due_review || 0, note: '已到计划复习时间' },
  { label: '累计练习', value: practiceStats.value.total_practices || 0, note: '全部未删除练习集' },
])
const palette = ['#655bea','#83b8a0','#e1b56f','#d88491','#8aa5cf']
const base = { color: palette, tooltip: { trigger: 'item' }, legend: { bottom: 0, type: 'scroll', textStyle: { color: '#697187' } } }
function pie(values) { return { ...base, series: [{ type: 'pie', radius: ['40%','65%'], center: ['50%','43%'], label: { show: false }, data: Object.entries(values).map(([name,value]) => ({name,value})) }] } }
function bars(values) {return {color:palette, tooltip:{trigger:'axis'}, grid:{left:45,right:20,top:20,bottom:45,containLabel:true},xAxis:{type:'category',data:Object.keys(values),axisLabel:{interval:0,rotate:20}},yAxis:{type:'value',minInterval:1},series:[{type:'bar',data:Object.values(values),barMaxWidth:35,itemStyle:{borderRadius:[4,4,0,0]}}]}}
function trend(rows,key,percent=false) {return {color:palette,tooltip:{trigger:'axis'},grid:{left:15,right:20,top:20,bottom:20,containLabel:true},xAxis:{type:'category',data:rows.map(x=>x.date)},yAxis:{type:'value',...(percent?{min:0,max:100,axisLabel:{formatter:'{value}%'}}:{minInterval:1})},series:[{type:'line',data:rows.map(x=>x[key]),symbolSize:5,areaStyle:{opacity:.07}}]}}
const reviewOption = computed(() => pie({'未复习':review.value.not_reviewed || 0,'复习 1 次':review.value.reviewed_once || 0,'复习 2 次及以上':review.value.reviewed_multiple || 0}))
const questionTrend = computed(() => trend(questionStats.value.accuracy_trend || [],'accuracy',true))
const wordOption = computed(() => {const d=wordStats.value.mastery_distribution || {};return pie({'未复习':d.unmastered || 0,'复习 1–3 次':d.learning || 0,'复习 4 次及以上':d.mastered || 0})})
const frequencyOption = computed(() => trend(wordStats.value.frequency_trend || [],'count'))
const practiceOption = computed(() => bars(Object.fromEntries(['周一','周二','周三','周四','周五','周六','周日'].map(day=>[day,practiceStats.value.frequency_heatmap?.[day] || 0]))))
const difficultyOption = computed(() => bars(Object.fromEntries(Object.entries(questionStats.value.by_difficulty || {}).map(([k,v])=>['难度 '+k,v]))))
async function loadStats() {
  loading.value = true
  error.value = ''
  try {
    const response = await learningAnalysisApi.getFullStats({ subject_id: selectedSubject.value || undefined })
    if (!response.data?.question_stats || !response.data?.word_stats || !response.data?.practice_stats) throw new Error('分析接口返回结构不完整')
    data.value = response.data
    loaded.value = true
  } catch (e) { error.value = e.response?.data?.detail || e.message || '分析加载失败，请重试' }
  finally { loading.value = false }
}
async function generateSuggestions() {
  suggesting.value = true
  suggestionError.value = ''
  try {
    const response = await learningAnalysisApi.getLlmAnalysis({ subject_id: selectedSubject.value || undefined })
    if (response.data?.error) throw new Error(response.data.error)
    suggestions.value = response.data?.suggestions || []
    if (!suggestions.value.length) suggestionError.value = '模型未返回有效建议，请检查配置后重试。'
  } catch(e) {suggestionError.value = e.response?.data?.detail || e.message || '建议生成失败'}
  finally { suggesting.value = false }
}
loadStats()
</script>
<style scoped>
.analysis-metrics {display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px;margin-bottom:18px}
.metric {background:#fff;border:1px solid var(--border-light);border-radius:10px;padding:14px 18px}
.metric span,.metric small {display:block;color:var(--text-muted);font-size:12px}
.metric strong {display:block;font-size:28px;line-height:1.5}
.metric small {font-size:11px}
.analysis-grid {display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px}
.full {grid-column:1/-1}
.chart {height:290px}
.chart-note {font-size:12px;color:var(--text-muted);margin:0 0 12px;line-height:1.7}
.load-error {margin-bottom:16px}
.suggestion {border-top:1px solid var(--border-light);padding:16px 0}
.suggestion p {margin:10px 0 0;line-height:1.8}
@media(max-width:768px){.analysis-metrics{grid-template-columns:1fr 1fr;gap:8px}.metric{padding:12px}.metric strong{font-size:25px}.analysis-grid{grid-template-columns:minmax(0,1fr)}.chart{height:260px}}
</style>
