<template>
  <!-- 每日一句：上面一行小字是星期和日期，下面是全页最大的一行字；右侧（手机在下方）是连续天数 -->
  <header class="hello">
    <div class="hello-text">
      <p class="date">{{ date_text }}</p>
      <h1>{{ line }}</h1>
    </div>
    <span v-if="streakDays > 0" class="streak">
      <LineIcon name="flame" :size="18" />已经连续 {{ streakDays }} 天
    </span>
  </header>
</template>

<script setup>
import { computed } from 'vue'
import LineIcon from '@/components/ui/LineIcon.vue'
import { pickDailyLine } from '@/data/dailyLines'
import { greeting_text } from './homeText'

const props = defineProps({
  // 今天（北京时间）'YYYY-MM-DD'
  today: { type: String, required: true },
  // 连续有学习记录的天数；0 时不显示
  streakDays: { type: Number, default: 0 },
})

const date_text = computed(() => greeting_text(props.today))
const line = computed(() => pickDailyLine(props.today))
</script>

<style scoped>
.hello { display: flex; align-items: flex-end; gap: 14px; margin-bottom: 20px; }
.hello-text { min-width: 0; }
.date { margin: 0 0 6px; color: var(--muted); font-size: 14px; }
/* 左边一条紫色竖条，把这句话托起来 */
h1 { position: relative; margin: 0; padding-left: 20px; color: var(--ink); font-size: 26px; line-height: 1.4; letter-spacing: .3px; }
h1::before {
  content: ''; position: absolute; left: 0; top: .32em; bottom: .32em; width: 6px; border-radius: 3px;
  background: linear-gradient(180deg, #7b74f7, var(--brand));
}
.streak {
  margin-left: auto; display: flex; align-items: center; gap: 6px; padding: 7px 14px; border-radius: 999px;
  background: var(--surface); color: var(--sun); font-weight: 600; font-size: 13px; box-shadow: var(--shadow-1); white-space: nowrap;
}

@media (min-width: 1200px) {
  .hello { margin-bottom: 24px; }
  h1 { font-size: 32px; }
}

@media (max-width: 768px) {
  .hello { flex-direction: column; align-items: flex-start; gap: 10px; }
  h1 { font-size: 21px; padding-left: 16px; }
  .streak { margin-left: 0; }
}
</style>
