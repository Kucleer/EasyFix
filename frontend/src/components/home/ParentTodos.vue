<template>
  <!-- 家长待办三格：待核对、待批改、出一份考点卷。前两格为 0 时变浅色、写"都处理完了"，仍可点 -->
  <section class="todo" aria-label="家长待办">
    <RouterLink class="todo-item" :class="review.count > 0 ? 'hot' : 'clear'" :to="{ path: '/questions', query: { tab: 'review' } }">
      <span v-if="review.count > 0" class="dot num">{{ review.count }}</span>
      <span v-else class="dot"><LineIcon name="check" :size="22" /></span>
      <span class="text">
        <b>{{ review.count > 0 ? '道题待核对' : '待核对' }}</b>
        <small v-if="review.count === 0">都处理完了</small>
        <small v-else-if="review.latest_paper">{{ review.latest_paper.name }}</small>
      </span>
      <span class="go"><LineIcon name="arrow" /></span>
    </RouterLink>

    <RouterLink class="todo-item" :class="grading.count > 0 ? 'hot' : 'clear'" :to="{ path: '/practice-sets', query: { pending: '1' } }">
      <span v-if="grading.count > 0" class="dot num">{{ grading.count }}</span>
      <span v-else class="dot"><LineIcon name="check" :size="22" /></span>
      <span class="text">
        <b>{{ grading.count > 0 ? '份卷子待批改' : '待批改' }}</b>
        <small v-if="grading.count === 0">都处理完了</small>
        <small v-else-if="grading_hint">{{ grading_hint }}</small>
      </span>
      <span class="go"><LineIcon name="arrow" /></span>
    </RouterLink>

    <RouterLink class="todo-item calm" to="/targeted-paper">
      <span class="dot"><LineIcon name="plus" :size="22" /></span>
      <span class="text">
        <b>出一份考点卷</b>
        <small>{{ targeted_text }}</small>
      </span>
      <span class="go"><LineIcon name="arrow" /></span>
    </RouterLink>
  </section>
</template>

<script setup>
import { computed } from 'vue'
import LineIcon from '@/components/ui/LineIcon.vue'
import { short_date_text, targeted_hint } from './homeText'

const props = defineProps({
  // /api/home 的 review：{ count, latest_paper: { id, name } | null }
  review: { type: Object, required: true },
  // /api/home 的 grading：{ count, oldest: { id, name, created_at } | null }
  grading: { type: Object, required: true },
  // /api/home 的 targeted：{ last_created_at }
  targeted: { type: Object, required: true },
  // 今天（北京时间）'YYYY-MM-DD'
  today: { type: String, required: true },
})

// 待批改的副标题：最早一份的名称和出卷日期，例如"数学考点卷 · 11 月 18 日"
const grading_hint = computed(() => {
  const oldest = props.grading.oldest
  if (!oldest) return ''
  const date = short_date_text(oldest.created_at)
  return date ? `${oldest.name} · ${date}` : oldest.name
})

// 考点卷的副标题："上次出卷是 N 天前"
const targeted_text = computed(() => targeted_hint(props.targeted.last_created_at, props.today))
</script>

<style scoped>
.todo { display: grid; grid-template-columns: repeat(3, 1fr); gap: 14px; }
.num { font-family: var(--font-num); font-variant-numeric: tabular-nums; font-weight: 700; }
.todo-item {
  min-width: 0; min-height: 76px; display: flex; align-items: center; gap: 14px; padding: 14px 16px;
  border-radius: var(--r-md); background: var(--surface); color: var(--ink); text-decoration: none;
  box-shadow: var(--shadow-1); border: 1px solid transparent; transition: border-color .18s, box-shadow .18s;
}
.todo-item:hover { border-color: #cfcbf7; box-shadow: var(--shadow-2); }
.todo-item:focus-visible { outline: 3px solid #a5a0f5; outline-offset: 2px; }
.dot { width: 46px; height: 46px; border-radius: 14px; display: grid; place-items: center; font-size: 22px; flex-shrink: 0; }
.hot .dot { background: var(--coral-soft); color: var(--coral); }
.calm .dot { background: var(--brand-soft); color: var(--brand); }
/* 没有待办：浅色，不抢眼，但仍然可以点进去 */
.clear { background: rgba(255,255,255,.55); box-shadow: none; border-color: var(--line); color: var(--ink-2); }
.clear .dot { background: var(--mint-soft); color: var(--mint); }
.text { min-width: 0; }
.text b { display: block; font-size: 15px; }
/* 卷子名可能很长，只显示一行 */
.text small { display: block; color: var(--muted); font-size: 13px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.go { margin-left: auto; color: #a3a7bd; display: flex; }

@media (max-width: 768px) {
  .todo { grid-template-columns: 1fr; gap: 10px; }
}
@media (prefers-reduced-motion: reduce) {
  .todo-item { transition: none; }
}
</style>
