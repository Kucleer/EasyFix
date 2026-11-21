<template>
  <!-- 图表卡：标题、副标题、右上角操作，下面放图表；没有数据时显示"暂无数据" -->
  <section class="chart-card">
    <header class="chart-head">
      <div class="chart-titles">
        <h3 class="chart-title">{{ title }}</h3>
        <p v-if="subtitle" class="chart-subtitle">{{ subtitle }}</p>
      </div>
      <div class="chart-extra"><slot name="extra" /></div>
    </header>
    <div class="chart-body" :style="{ height }">
      <div v-if="empty" class="chart-empty">暂无数据</div>
      <slot v-else />
    </div>
  </section>
</template>

<script setup>
defineProps({
  title: { type: String, required: true },
  subtitle: { type: String, default: '' },
  // 图表区域高度
  height: { type: String, default: '260px' },
  // 为真时不放图表，显示"暂无数据"
  empty: { type: Boolean, default: false },
})
</script>

<style scoped>
.chart-card {
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: var(--r-lg);
  box-shadow: var(--shadow-1);
  padding: 16px 18px;
  min-width: 0;
}
.chart-head { display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; margin-bottom: 8px; }
.chart-titles { min-width: 0; }
.chart-title { margin: 0; font-size: 16px; color: var(--ink); }
.chart-subtitle { margin: 2px 0 0; color: var(--muted); font-size: 12px; }
.chart-extra { flex-shrink: 0; }
.chart-body { position: relative; width: 100%; }
.chart-empty { height: 100%; display: flex; align-items: center; justify-content: center; color: var(--muted); font-size: 13px; }
</style>
