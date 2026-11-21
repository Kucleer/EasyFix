<template>
  <!-- 考点明细：按模块分组，每个考点一行；电脑上是表格，手机上每个考点是一张小卡片。点一行去看这个考点的错题 -->
  <section class="point-table">
    <header class="pt-head">
      <h2>考点明细</h2>
      <p>点一个考点，看它的错题</p>
    </header>

    <div v-if="!groups.length" class="pt-empty">这一科还没有考点</div>

    <template v-else>
      <div class="pt-columns" aria-hidden="true">
        <span>考点</span><span>掌握情况</span><span>最近几次</span><span>待重做</span><span></span>
      </div>

      <div v-for="group in groups" :key="group.id" class="pt-group">
        <div class="pt-module">
          <b>{{ group.name }}</b>
          <span class="pt-module-sum">
            已掌握 {{ group.summary.mastered }} / {{ group.summary.total }}
            <template v-if="group.summary.weak"> · 薄弱 {{ group.summary.weak }}</template>
            <template v-if="group.summary.pending"> · 待重做 {{ group.summary.pending }} 道</template>
          </span>
        </div>

        <RouterLink
          v-for="row in group.rows"
          :key="row.id"
          class="pt-row"
          :to="{ path: '/questions', query: point_query(subjectId, row) }"
        >
          <span class="pt-name">{{ row.name }}</span>
          <span class="pt-status"><em class="pt-chip" :class="'tone-' + row.tone">{{ row.status_text }}</em></span>
          <span class="pt-recent" :aria-label="recent_label(row)">
            <span class="pt-label">最近</span>
            <template v-if="row.recent.length">
              <i v-for="mark in row.recent" :key="mark.key" :class="mark.right ? 'right' : 'wrong'" :title="mark.label">
                {{ mark.right ? '✓' : '✗' }}
              </i>
            </template>
            <span v-else class="pt-muted">还没做过</span>
          </span>
          <span class="pt-pending">
            <span class="pt-label">待重做</span>
            <template v-if="row.pending"><b class="num">{{ row.pending }}</b> 道</template>
            <span v-else class="pt-muted">—</span>
          </span>
          <LineIcon name="arrow" :size="16" class="pt-arrow" />
        </RouterLink>
      </div>
    </template>
  </section>
</template>

<script setup>
import LineIcon from '@/components/ui/LineIcon.vue'
import { point_query } from './insightModel.js'

defineProps({
  // group_points() 的结果：[{ id, name, rows, summary }]
  groups: { type: Array, required: true },
  // 当前学科，拼去错题页的地址用
  subjectId: { type: Number, required: true },
})

/** 读屏用的"最近几次"说明，比如"最近：对、错、错" */
function recent_label(row) {
  return row.recent.length ? '最近：' + row.recent.map(mark => mark.label).join('、') : '还没做过'
}
</script>

<style scoped>
.point-table {
  margin-top: 18px;
  padding: 18px 20px 8px;
  border-radius: var(--r-lg);
  background: var(--surface);
  border: 1px solid var(--line);
  box-shadow: var(--shadow-1);
}
.pt-head { display: flex; align-items: baseline; gap: 12px; margin-bottom: 8px; }
.pt-head h2 { margin: 0; font-size: 16px; color: var(--ink); }
.pt-head p { margin: 0; color: var(--muted); font-size: 12px; }
.pt-empty { padding: 32px 0; text-align: center; color: var(--muted); font-size: 13px; }

/* 电脑：五列表格 */
.pt-columns,
.pt-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 100px 120px 90px 20px;
  align-items: center;
  gap: 12px;
  padding: 0 12px;
}
.pt-columns { padding-top: 6px; padding-bottom: 6px; color: var(--muted); font-size: 12px; }
.pt-group { border-top: 1px solid var(--line); padding: 4px 0 8px; }
.pt-module { display: flex; align-items: baseline; flex-wrap: wrap; gap: 4px 12px; padding: 10px 12px 6px; }
.pt-module b { font-size: 15px; color: var(--ink); }
.pt-module-sum { color: var(--muted); font-size: 12px; }
.pt-row {
  min-height: 44px;
  border-radius: var(--r-sm);
  color: var(--ink-2);
  text-decoration: none;
  font-size: 14px;
}
.pt-row:hover { background: var(--brand-soft); }
.pt-row:focus-visible { outline: 3px solid #a5a0f5; outline-offset: -2px; }
.pt-name { color: var(--ink); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.pt-chip {
  display: inline-block;
  padding: 1px 10px;
  border-radius: 999px;
  font-style: normal;
  font-size: 12px;
  font-weight: 600;
}
.tone-coral { background: var(--coral-soft); color: var(--coral); }
.tone-sun { background: var(--sun-soft); color: var(--sun); }
.tone-mint { background: var(--mint-soft); color: var(--mint-deep, var(--mint)); }
.tone-grey { background: #f0f0f4; color: var(--muted); }
.pt-recent { display: flex; align-items: center; gap: 4px; }
.pt-recent i {
  width: 20px; height: 20px; border-radius: 50%;
  display: inline-flex; align-items: center; justify-content: center;
  font-style: normal; font-size: 12px; font-weight: 700;
}
.pt-recent i.right { background: var(--mint-soft); color: var(--mint); }
.pt-recent i.wrong { background: var(--coral-soft); color: var(--coral); }
.pt-pending b { color: var(--coral); }
.pt-muted { color: var(--muted); font-size: 13px; }
.pt-label { display: none; }
.pt-arrow { color: var(--muted); }
.num { font-family: var(--font-num); font-variant-numeric: tabular-nums; font-weight: 700; }

/* 手机：表头收起，每个考点一张小卡片：第一行名称和箭头，第二行状态、最近几次、待重做 */
@media (max-width: 768px) {
  .point-table { padding: 14px 12px 6px; border-radius: var(--r-md); }
  .pt-head { flex-direction: column; gap: 2px; }
  .pt-columns { display: none; }
  .pt-module { padding: 10px 4px 6px; }
  .pt-row {
    grid-template-columns: auto auto minmax(0, 1fr) 16px;
    grid-template-areas: 'name name name arrow' 'status recent pending arrow';
    gap: 6px 12px;
    margin: 0 0 8px;
    padding: 10px 12px;
    border: 1px solid var(--line);
    border-radius: var(--r-sm);
  }
  .pt-name { grid-area: name; white-space: normal; }
  .pt-status { grid-area: status; }
  .pt-recent { grid-area: recent; }
  .pt-pending { grid-area: pending; justify-self: end; }
  .pt-arrow { grid-area: arrow; }
  .pt-label { display: inline; margin-right: 2px; color: var(--muted); font-size: 12px; }
}
</style>
