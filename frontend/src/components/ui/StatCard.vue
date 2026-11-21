<template>
  <!-- 统计数字卡：上面一行说明，中间一个大数字，下面一行补充说明 -->
  <div class="stat-card" :class="'tone-' + tone">
    <div class="stat-label">{{ label }}</div>
    <div class="stat-value">
      <span class="num">{{ value == null ? '—' : value }}</span>
      <span v-if="unit && value != null" class="stat-unit">{{ unit }}</span>
    </div>
    <div v-if="hint" class="stat-hint">{{ hint }}</div>
  </div>
</template>

<script setup>
defineProps({
  label: { type: String, required: true },
  // 数字；为 null 时显示 —
  value: { type: [Number, String], default: null },
  unit: { type: String, default: '' },
  hint: { type: String, default: '' },
  // 颜色：brand 主色、mint 进步、sun 留意、coral 待办、plain 普通
  tone: {
    type: String,
    default: 'plain',
    validator: value => ['brand', 'mint', 'sun', 'coral', 'plain'].includes(value),
  },
})
</script>

<style scoped>
.stat-card {
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: var(--r-md);
  padding: 14px 16px;
  min-width: 0;
}
.stat-label { color: var(--muted); font-size: 13px; }
.stat-value { margin-top: 4px; display: flex; align-items: baseline; gap: 4px; color: var(--ink); }
.stat-value .num { font-family: var(--font-num); font-variant-numeric: tabular-nums; font-weight: 700; font-size: 28px; line-height: 1.1; }
.stat-unit { color: var(--ink-2); font-size: 13px; }
.stat-hint { margin-top: 4px; color: var(--muted); font-size: 12px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.tone-brand .stat-value { color: var(--brand); }
.tone-mint .stat-value { color: var(--mint); }
.tone-sun .stat-value { color: var(--sun); }
.tone-coral .stat-value { color: var(--coral); }
</style>
