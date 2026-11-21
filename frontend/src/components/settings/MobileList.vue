<template>
  <!-- 手机端紧凑列表：每行名称 + 一行说明，右侧「⋯」展开操作；各设置标签共用 -->
  <div class="mg-list">
    <div
      v-for="item in rows"
      :key="item.key"
      class="mg-row"
      :class="{ 'is-child': item.is_child, 'is-parent': item.is_parent }"
    >
      <div class="mg-main">
        <div class="mg-name"><i v-if="item.color" class="mg-dot" :style="{ background: item.color }"></i>{{ item.name }}</div>
        <div v-if="item.desc" class="mg-desc">{{ item.desc }}</div>
      </div>
      <el-dropdown trigger="click" placement="bottom-end">
        <el-button class="mg-more" aria-label="更多操作"><el-icon><MoreFilled /></el-icon></el-button>
        <template #dropdown>
          <el-dropdown-menu>
            <el-dropdown-item
              v-for="act in item.actions"
              :key="act.label"
              :disabled="act.disabled"
              :class="{ 'list-action-danger': act.danger }"
              @click="act.run()"
            >{{ act.label }}</el-dropdown-item>
          </el-dropdown-menu>
        </template>
      </el-dropdown>
    </div>
    <div v-if="!rows.length" class="mg-empty">{{ emptyText }}</div>
  </div>
</template>

<script setup>
defineProps({
  // [{ key, name, desc, color?, is_parent?, is_child?, actions: [{ label, run, disabled?, danger? }] }]
  rows: { type: Array, required: true },
  emptyText: { type: String, default: '暂无数据' },
})
</script>

<style scoped>
.mg-list {
  overflow: hidden;
  border-radius: var(--r-sm);
  background: var(--surface);
  border: 1px solid var(--line);
}
/* 一行：左边名称+说明，右边操作 */
.mg-row {
  display: flex;
  align-items: center;
  gap: 10px;
  min-height: 56px;
  padding: 9px 10px 9px 14px;
  border-bottom: 1px solid var(--line);
}
.mg-row:last-of-type { border-bottom: none; }
/* 知识点二级缩进；一级加粗 */
.mg-row.is-child { padding-left: 32px; background: #faf9ff; }
.mg-row.is-parent .mg-name { font-weight: 600; }
.mg-main { flex: 1; min-width: 0; }
.mg-name {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 14px;
  line-height: 21px;
  color: var(--ink);
  overflow-wrap: anywhere;
}
.mg-desc {
  margin-top: 2px;
  font-size: 12px;
  line-height: 18px;
  color: var(--muted);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.mg-dot { flex: none; width: 10px; height: 10px; border-radius: 50%; }
.mg-more { flex: none; width: 34px; height: 34px; padding: 0; border-radius: 8px; }
.mg-empty { padding: 24px 0; text-align: center; font-size: 13px; color: var(--muted); }
</style>
