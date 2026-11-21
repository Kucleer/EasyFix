<template>
  <!-- 学情 · 单词：需要关注的单词、单词复习频率 -->
  <div class="words-tab">
    <p v-if="load_error" class="words-error">{{ load_error }}</p>

    <div class="words-grid">
      <ChartCard title="需要关注的单词" subtitle="复习过、正确率低于 70% 的单词，最多 20 个" height="auto">
        <ul v-if="low_words.length" class="word-list">
          <li v-for="item in low_words" :key="item.word">
            <span class="word">{{ item.word }}</span>
            <span class="accuracy">
              <i class="bar"><i :style="{ width: item.accuracy + '%' }"></i></i>
              <b class="num">{{ item.accuracy }}%</b>
            </span>
          </li>
        </ul>
        <p v-else class="words-empty">{{ loading ? '正在读取…' : '没有正确率偏低的单词' }}</p>
      </ChartCard>

      <ChartCard title="单词复习频率" subtitle="最近 60 天，每天复习单词的次数" :empty="!loading && !has_reviews">
        <VChart v-if="has_reviews" :option="chart_option" autoresize class="words-chart" />
      </ChartCard>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent } from 'echarts/components'
import ChartCard from '@/components/ui/ChartCard.vue'
import { CHART_THEME, useChartTheme } from '@/composables/chartTheme'
import { insightApi } from '@/api/insight'
import { daily_counts, frequency_option } from './insightModel.js'

use([CanvasRenderer, LineChart, GridComponent, TooltipComponent])

const loading = ref(true)
const load_error = ref('')
const low_words = ref([])
const frequency = ref([])
const theme = ref(CHART_THEME)   // 挂载后换成从 CSS 变量读到的颜色

/** 今天的日期 'YYYY-MM-DD'（本机时间） */
function today_text() {
  const now = new Date()
  const pad = value => String(value).padStart(2, '0')
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`
}

// 最近 60 天每天一个点，没复习的日子是 0
const points = computed(() => daily_counts(frequency.value, today_text(), 60))
const has_reviews = computed(() => points.value.some(point => point.count > 0))
const chart_option = computed(() => frequency_option(points.value, theme.value))

/** 读取单词学情 */
async function load() {
  loading.value = true
  load_error.value = ''
  try {
    const { data } = await insightApi.words()
    low_words.value = data.low_accuracy_words || []
    frequency.value = data.frequency || []
  } catch (error) {
    load_error.value = error.response?.data?.detail || '单词学情暂时读不到，请稍后再试'
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  theme.value = useChartTheme()   // 图表颜色读 CSS 变量，读不到用默认主题
  load()
})
</script>

<style scoped>
.words-grid { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1.4fr); gap: 16px; align-items: start; }
.words-error { margin: 0 0 12px; padding: 10px 14px; border-radius: var(--r-sm); background: var(--coral-soft); color: var(--coral); font-size: 13px; }
.words-chart { width: 100%; height: 100%; }
.word-list { list-style: none; margin: 4px 0 0; padding: 0; }
.word-list li {
  display: flex; align-items: center; justify-content: space-between; gap: 12px;
  min-height: 40px; border-top: 1px solid var(--line);
}
.word-list li:first-child { border-top: 0; }
.word { color: var(--ink); font-size: 15px; overflow-wrap: anywhere; }
.accuracy { display: inline-flex; align-items: center; gap: 8px; flex-shrink: 0; }
.bar { display: block; width: 72px; height: 6px; border-radius: 3px; background: var(--coral-soft); overflow: hidden; }
.bar i { display: block; height: 100%; background: var(--coral); }
.num { width: 48px; text-align: right; font-family: var(--font-num); font-variant-numeric: tabular-nums; font-weight: 700; color: var(--coral); }
.words-empty { margin: 16px 0; color: var(--muted); font-size: 13px; text-align: center; }

@media (max-width: 900px) {
  .words-grid { grid-template-columns: minmax(0, 1fr); }
}
</style>
