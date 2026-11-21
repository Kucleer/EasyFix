<template>
  <!-- 这一周：日期范围、七天打卡条、几个数字、考点变好 / 变差的标签、"看周报"链接 -->
  <div class="card">
    <div class="card-head">
      <b>{{ range_text }}</b>
      <RouterLink class="link" to="/learning-reports">看周报<LineIcon name="arrow" :size="16" /></RouterLink>
    </div>

    <!-- 七天打卡条：有学习记录的一天打勾，今天加一圈，还没到的日子画虚线 -->
    <div class="days">
      <div v-for="(day, index) in week.days" :key="day.date" class="day" :class="day_state(day.date, day.active, today)">
        <i><LineIcon name="check" :size="18" /></i>{{ WEEKDAY_NAMES[index] }}
      </div>
    </div>

    <div class="nums" :class="{ three: numbers.length === 3 }">
      <div v-for="item in numbers" :key="item.label">
        <span class="num">{{ item.value }}<small>{{ item.unit }}</small></span>
        <span class="label">{{ item.label }}</span>
      </div>
    </div>

    <div v-if="week.improved.length || week.dropped.length" class="chips">
      <span v-for="name in week.improved" :key="'up-' + name" class="chip up"><LineIcon name="up" :size="14" />{{ name }}</span>
      <span v-for="name in week.dropped" :key="'down-' + name" class="chip down"><LineIcon name="down" :size="14" />{{ name }}</span>
    </div>
    <p v-else class="quiet">这周考点还没有明显变化</p>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import LineIcon from '@/components/ui/LineIcon.vue'
import { FLIP_READY } from '@/config/features'
import { WEEKDAY_NAMES, day_state, week_range_text } from './homeText'

const props = defineProps({
  // /api/home 的 week：monday、sunday、days（7 天）、entries、papers、dictation_days、flip_days、improved、dropped
  week: { type: Object, required: true },
  // 今天（北京时间）'YYYY-MM-DD'
  today: { type: String, required: true },
})

const range_text = computed(() => week_range_text(props.week.monday, props.week.sunday))

// 四个数字；翻一翻没上线时先不显示"翻了错题"
const numbers = computed(() => {
  const list = [
    { label: '新录错题', value: props.week.entries, unit: '道' },
    { label: '练习卷', value: props.week.papers, unit: '份' },
    { label: '背了单词', value: props.week.dictation_days, unit: '天' },
  ]
  if (FLIP_READY) list.push({ label: '翻了错题', value: props.week.flip_days, unit: '天' })
  return list
})
</script>

<style scoped>
.card { min-width: 0; padding: 20px 22px; border-radius: var(--r-lg); background: var(--surface); box-shadow: var(--shadow-1); }
.card-head { display: flex; align-items: center; gap: 10px; margin-bottom: 14px; }
.card-head b { font-size: 16px; color: var(--ink); }
.link {
  margin-left: auto; display: flex; align-items: center; gap: 4px; min-height: 44px; padding: 0 4px;
  color: var(--brand); font-weight: 600; font-size: 14px; text-decoration: none;
}
.link:focus-visible { outline: 3px solid #a5a0f5; outline-offset: 2px; border-radius: 6px; }

.days { display: grid; grid-template-columns: repeat(7, 1fr); gap: 8px; margin-bottom: 16px; }
.day { text-align: center; font-size: 12px; color: var(--muted); }
.day i { display: grid; place-items: center; height: 38px; margin-bottom: 4px; border-radius: 12px; background: var(--bg); color: transparent; font-style: normal; }
.day i :deep(.line-icon) { stroke-width: 2.6; }
.day.done i { background: var(--mint-soft); color: var(--mint); }
.day.today i { box-shadow: 0 0 0 2px var(--brand); }
.day.future i { background: none; border: 1.5px dashed var(--line); }

.nums { display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; margin-bottom: 14px; }
.nums.three { grid-template-columns: repeat(3, 1fr); }
.nums > div { min-width: 0; padding: 10px 12px; border-radius: var(--r-sm); background: var(--bg); }
.num { display: block; font-family: var(--font-num); font-variant-numeric: tabular-nums; font-weight: 700; font-size: 22px; line-height: 1.2; color: var(--ink); }
.num small { font: 600 13px var(--el-font-family); margin-left: 2px; }
.label { display: block; font-size: 12.5px; color: var(--muted); }

.chips { display: flex; flex-wrap: wrap; gap: 8px; }
.chip { display: inline-flex; align-items: center; gap: 4px; padding: 4px 12px; border-radius: 999px; font-size: 13px; font-weight: 600; }
.chip :deep(.line-icon) { stroke-width: 2.6; }
.chip.up { background: var(--mint-soft); color: var(--mint-deep); }
.chip.down { background: var(--sun-soft); color: var(--sun); }
.quiet { margin: 0; font-size: 13px; color: var(--muted); }

@media (max-width: 768px) {
  .card { padding: 16px; }
  .days { gap: 5px; }
  .nums { grid-template-columns: repeat(2, 1fr); }
  .nums > div { padding: 10px; }
}
</style>
