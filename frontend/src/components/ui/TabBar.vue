<template>
  <!-- 页内标签栏：v-model 绑定当前标签的 key；badge 大于 0 时显示红色数字 -->
  <nav class="tab-bar" role="tablist">
    <button
      v-for="tab in tabs"
      :key="tab.key"
      type="button"
      role="tab"
      class="tab-item"
      :class="{ active: tab.key === modelValue }"
      :aria-selected="tab.key === modelValue"
      @click="emit('update:modelValue', tab.key)"
    >
      {{ tab.label }}
      <b v-if="tab.badge > 0" class="tab-badge">{{ tab.badge }}</b>
    </button>
  </nav>
</template>

<script setup>
defineProps({
  // 当前标签的 key
  modelValue: { type: String, required: true },
  // [{ key, label, badge? }]
  tabs: { type: Array, required: true },
})
const emit = defineEmits(['update:modelValue'])
</script>

<style scoped>
.tab-bar {
  display: flex;
  gap: 4px;
  padding: 4px;
  background: var(--brand-soft);
  border-radius: var(--r-md);
  overflow-x: auto;           /* 手机宽度下标签多时可以横向滑动 */
  scrollbar-width: none;
}
.tab-bar::-webkit-scrollbar { display: none; }
.tab-item {
  flex-shrink: 0;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 7px 16px;
  border: 0;
  border-radius: var(--r-sm);
  background: none;
  color: var(--ink-2);
  font: inherit;
  font-size: 14px;
  cursor: pointer;
}
.tab-item.active { background: var(--surface); color: var(--brand); font-weight: 600; box-shadow: var(--shadow-1); }
.tab-item:focus-visible { outline: 3px solid #a5a0f5; outline-offset: 2px; }
.tab-badge {
  min-width: 18px;
  padding: 0 5px;
  border-radius: 999px;
  background: var(--coral);
  color: #fff;
  font-size: 11px;
  line-height: 18px;
  text-align: center;
}
</style>
