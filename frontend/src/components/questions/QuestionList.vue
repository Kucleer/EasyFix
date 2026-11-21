<template>
  <!-- 错题列表：电脑用表格，手机用卡片；操作都是"查看"+"更多（编辑、生成相似题、删除）" -->
  <div class="ql">
    <template v-if="isMobile">
      <div v-if="items.length" class="ql-cards">
        <article v-for="row in items" :key="row.id" class="ql-card" :class="{ 'is-pending': row.review_status === 'pending' }">
          <!-- 第一层：原图 + 题目文字（最多 3 行），点文字看详情 -->
          <div class="ql-card-top">
            <el-image
              v-if="thumb(row)"
              class="ql-thumb"
              :src="thumb(row)"
              :preview-src-list="[thumb(row)]"
              preview-teleported
              fit="cover"
            />
            <div class="ql-card-text" @click="emit('view', row)">
              <el-tag v-if="row.review_status === 'pending'" type="warning" size="small" class="ql-pending">待核对</el-tag>
              <MathText :text="row.parsed_question || row.original_text || '无文本'" />
            </div>
          </div>
          <!-- 第二层：学科、知识点（最多 2 个）、标签，日期靠右 -->
          <div class="ql-card-tags">
            <span class="ql-chip">{{ subject_name(row.subject_id) }}</span>
            <template v-if="row.knowledge_points?.length">
              <KnowledgeTag v-for="point in visible_knowledge_points(row, 2)" :key="point.id" :point="point" :primary="!!point.is_primary" :subject-id="row.subject_id" />
              <span v-if="row.knowledge_points.length > 2" class="ql-chip">+{{ row.knowledge_points.length - 2 }}</span>
            </template>
            <span v-else class="ql-chip is-muted">未分类</span>
            <span v-for="tag in row.tags || []" :key="tag.id" class="ql-chip">{{ tag.name }}</span>
            <em class="ql-date">{{ short_date(row.created_at) }}</em>
          </div>
          <!-- 第三层：难度、正确率 + 操作 -->
          <div class="ql-card-foot">
            <div class="ql-card-meta">
              <span class="ql-stars">{{ '★'.repeat(row.difficulty || 0) }}</span>
              <span v-if="accuracy_value(row) < 0">未练习</span>
              <span v-else>
                正确率 <b>{{ accuracy_text(row) }}</b>
                <i class="ql-bar" :class="{ 'is-low': accuracy_value(row) < 0.6 }"><i :style="{ width: accuracy_text(row) }" /></i>
              </span>
            </div>
            <ListActions :primary="primary_action(row)" :actions="more_actions(row)" />
          </div>
        </article>
      </div>
      <el-empty v-else description="没有符合条件的错题" />
    </template>

    <el-table v-else class="ql-table" :data="items" empty-text="没有符合条件的错题">
      <el-table-column label="题目" min-width="420">
        <template #default="{ row }">
          <div class="ql-cell">
            <el-image
              v-if="thumb(row)"
              class="ql-cell-thumb"
              :src="thumb(row)"
              :preview-src-list="[thumb(row)]"
              preview-teleported
              fit="contain"
            />
            <el-tag v-if="row.review_status === 'pending'" type="warning" size="small" class="ql-cell-pending">待核对</el-tag>
            <div class="ql-cell-text"><MathText :text="row.parsed_question || row.original_text || '无文本'" /></div>
          </div>
        </template>
      </el-table-column>
      <el-table-column label="分类与记录" width="260">
        <template #default="{ row }">
          <div class="ql-meta">
            <span>{{ subject_name(row.subject_id) }}</span>
            <div v-if="row.knowledge_points?.length" class="ql-kp">
              <KnowledgeTag v-for="point in visible_knowledge_points(row)" :key="point.id" :point="point" :primary="!!point.is_primary" :subject-id="row.subject_id" show-path />
              <el-tag v-if="row.knowledge_points.length > 3" size="small" type="info">+{{ row.knowledge_points.length - 3 }}</el-tag>
            </div>
            <span v-else-if="row.legacy_knowledge_point" class="ql-legacy">原标签：{{ row.legacy_knowledge_point }}</span>
            <span v-else class="ql-muted">未分类</span>
            <div v-if="row.tags?.length" class="ql-tags"><el-tag v-for="tag in row.tags" :key="tag.id" size="small">{{ tag.name }}</el-tag></div>
            <small>#{{ row.id }} · {{ full_date(row.created_at) }}</small>
          </div>
        </template>
      </el-table-column>
      <el-table-column label="复习情况" width="130" sortable :sort-method="(a, b) => accuracy_value(a) - accuracy_value(b)">
        <template #default="{ row }">
          <div class="ql-meta">
            <span class="ql-stars" :class="'is-d' + (row.difficulty || 0)">{{ '★'.repeat(row.difficulty || 0) }}</span>
            <span>正确率 {{ accuracy_text(row) }}</span>
            <small>答对 {{ row.correct_count || 0 }} / {{ (row.correct_count || 0) + (row.error_count || 0) }} 次</small>
          </div>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="150" fixed="right">
        <template #default="{ row }"><ListActions :primary="primary_action(row)" :actions="more_actions(row)" /></template>
      </el-table-column>
    </el-table>
  </div>
</template>

<script setup>
import MathText from '@/components/MathText.vue'
import { accuracy_value, accuracy_text, visible_knowledge_points } from './questionFilters'

const props = defineProps({
  items: { type: Array, default: () => [] },
  subjects: { type: Array, default: () => [] },
  isMobile: { type: Boolean, default: false },
})
// view 查看详情；edit 编辑；similar 生成相似题；remove 删除
const emit = defineEmits(['view', 'edit', 'similar', 'remove'])

/** 学科名称 */
function subject_name(id) {
  return props.subjects.find(s => s.id === id)?.name || '未指定学科'
}

/** 列表里的小图：第一张原图；没有图返回空串 */
function thumb(row) {
  const key = row.original_image || row.original_images?.[0]
  return key ? '/uploads/' + key : ''
}

/** 手机卡片上的短日期，例如 11/12 */
function short_date(value) {
  if (!value) return ''
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? '' : `${date.getMonth() + 1}/${date.getDate()}`
}

/** 表格里的完整日期时间 */
function full_date(value) {
  return value ? new Date(value).toLocaleString('zh-CN') : ''
}

/** 主按钮"查看" */
function primary_action(row) {
  return { label: '查看', run: () => emit('view', row) }
}

/** "更多"里的操作：编辑、生成相似题、删除 */
function more_actions(row) {
  return [
    { label: '编辑', run: () => emit('edit', row) },
    { label: '生成相似题', run: () => emit('similar', row) },
    { label: '删除', danger: true, run: () => emit('remove', row) },
  ]
}
</script>

<style scoped>
/* ---------- 电脑表格 ---------- */
.ql-table { width: 100%; margin-top: 14px; font-size: 14px; }
.ql-table :deep(td.el-table__cell) { padding: 12px 0; vertical-align: top; }
.ql-cell { display: flex; align-items: flex-start; gap: 10px; min-width: 0; }
.ql-cell-thumb { width: 52px; height: 52px; flex: none; border-radius: 8px; cursor: zoom-in; background: var(--bg); }
.ql-cell-pending { flex: none; }
.ql-cell-text { flex: 1; min-width: 0; line-height: 1.9; font-size: 15px; color: var(--ink); overflow-wrap: anywhere; }
.ql-cell-text :deep(.math-text) { display: block; width: 100%; }
.ql-meta { display: flex; flex-direction: column; align-items: flex-start; gap: 6px; font-size: 13px; color: var(--ink-2); }
.ql-meta small { color: var(--muted); font-size: 12px; }
.ql-meta :deep(.el-tag) { max-width: 100%; height: auto; white-space: normal; line-height: 1.6; padding: 3px 7px; }
.ql-kp, .ql-tags { display: flex; flex-wrap: wrap; gap: 4px; }
.ql-legacy { color: var(--muted); font-size: 12px; font-style: italic; }
.ql-muted { color: var(--muted); }
.ql-stars { color: var(--sun); letter-spacing: 1px; font-size: 13px; }
.ql-stars.is-d1, .ql-stars.is-d2 { color: var(--mint); }
.ql-stars.is-d4, .ql-stars.is-d5 { color: var(--coral); }

/* ---------- 手机卡片：题目 / 标签 / 数据+操作 三层 ---------- */
.ql-cards { display: flex; flex-direction: column; gap: 10px; margin-top: 12px; }
.ql-card {
  padding: 12px 14px; border-radius: var(--r-md); background: var(--surface);
  box-shadow: var(--shadow-1); border-left: 3px solid transparent;
}
.ql-card.is-pending { border-left-color: var(--sun); }
.ql-card-top { display: flex; align-items: flex-start; gap: 10px; }
.ql-thumb { width: 52px; height: 52px; flex: none; border-radius: 8px; background: var(--bg); }
.ql-card-text {
  flex: 1; min-width: 0; font-size: 14px; line-height: 22px; cursor: pointer; color: var(--ink); overflow-wrap: anywhere;
  display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical; overflow: hidden;
}
.ql-card-text :deep(.math-text) { display: inline; }
.ql-pending { margin-right: 4px; vertical-align: 1px; }
.ql-card-tags { display: flex; flex-wrap: wrap; align-items: center; gap: 6px; margin-top: 8px; }
.ql-card-tags :deep(.el-tag) { max-width: 100%; }
.ql-chip { font-size: 12px; line-height: 20px; padding: 0 8px; border-radius: 10px; color: var(--ink-2); background: var(--bg); }
.ql-chip.is-muted { color: var(--muted); }
.ql-date { margin-left: auto; font-style: normal; font-size: 12px; color: var(--muted); }
.ql-card-foot {
  display: flex; align-items: center; justify-content: space-between; gap: 8px;
  margin-top: 10px; padding-top: 10px; border-top: 1px dashed var(--line);
}
.ql-card-meta { display: flex; flex-wrap: wrap; align-items: center; gap: 2px 12px; min-width: 0; font-size: 13px; color: var(--ink-2); }
.ql-card-meta b { color: var(--ink); font-weight: 600; }
/* 正确率小条：低于 60% 变红 */
.ql-bar { display: inline-block; width: 48px; height: 5px; margin-left: 4px; vertical-align: middle; border-radius: 3px; overflow: hidden; background: var(--line); }
.ql-bar > i { display: block; height: 100%; background: var(--mint); }
.ql-bar.is-low > i { background: var(--coral); }
</style>
