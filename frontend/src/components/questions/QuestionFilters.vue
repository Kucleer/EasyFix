<template>
  <!-- 全部错题的筛选：一个搜索框（电脑、手机共用）+ 电脑筛选栏 / 手机筛选抽屉 + 已选条件小标签 -->
  <div class="qf">
    <div class="qf-bar">
      <el-input
        v-model="filters.keyword"
        class="qf-keyword"
        placeholder="搜题目文字"
        clearable
        :prefix-icon="Search"
        @change="emit('change')"
      />
      <!-- 手机：只露搜索框 + "筛选"按钮，其余筛选项放进底部抽屉 -->
      <el-button v-if="isMobile" class="qf-filter-btn" @click="open_drawer">
        筛选<span v-if="active_count" class="qf-count">{{ active_count }}</span>
      </el-button>
      <!-- 电脑：每改一项马上查询 -->
      <template v-else>
        <el-select v-model="filters.subject_id" placeholder="学科" clearable class="qf-w-sm" @change="value => emit('subject-change', value)">
          <el-option v-for="s in subjects" :key="s.id" :label="s.name" :value="s.id" />
        </el-select>
        <el-select v-model="filters.knowledge_parent_id" placeholder="知识模块（一级）" clearable filterable :disabled="!filters.subject_id" class="qf-w-md" @change="on_module_change">
          <el-option v-for="m in modules_of(filters.subject_id)" :key="m.id" :label="m.name" :value="m.id" />
        </el-select>
        <el-select v-model="filters.knowledge_point_id" placeholder="二级考点" clearable filterable :disabled="!filters.knowledge_parent_id" class="qf-w-md" @change="emit('change')">
          <el-option v-for="p in points_of(filters.subject_id, filters.knowledge_parent_id)" :key="p.id" :label="p.name" :value="p.id" />
        </el-select>
        <el-checkbox v-model="filters.unclassified" border @change="on_unclassified_change(filters)">只看未分类</el-checkbox>
        <el-select v-model="filters.difficulty" placeholder="难度" multiple collapse-tags clearable class="qf-w-sm" @change="emit('change')">
          <el-option v-for="i in 5" :key="i" :label="'★'.repeat(i)" :value="i" />
        </el-select>
        <el-select v-model="filters.tag_ids" placeholder="标签" multiple collapse-tags clearable class="qf-w-md" @change="emit('change')">
          <el-option v-for="t in tags" :key="t.id" :label="t.name" :value="t.id" />
        </el-select>
        <el-select v-model="filters.grade" placeholder="年级" clearable class="qf-w-xs" @change="emit('change')">
          <el-option v-for="g in GRADE_OPTIONS" :key="g.value" :label="g.label" :value="g.value" />
        </el-select>
        <el-select v-model="filters.semester" placeholder="学期" clearable class="qf-w-xs" @change="emit('change')">
          <el-option label="上学期" :value="1" />
          <el-option label="下学期" :value="2" />
        </el-select>
        <el-select v-model="filters.accuracy_range" placeholder="正确率" clearable class="qf-w-sm" @change="emit('change')">
          <el-option v-for="opt in ACCURACY_RANGE_OPTIONS" :key="opt.value" :label="opt.label" :value="opt.value" />
        </el-select>
      </template>
    </div>

    <!-- 已选条件：点 × 去掉一项；手机上一行横向滑动 -->
    <div v-if="active_count" class="qf-chips" :class="{ 'is-mobile': isMobile }">
      <span class="qf-chips-label">已选：</span>
      <el-tag v-if="filters.subject_id" size="small" closable @close="remove('subject_id')">{{ subject_name(filters.subject_id) }}</el-tag>
      <KnowledgeTag v-if="filters.knowledge_parent_id" :point="selected_module || `知识模块 #${filters.knowledge_parent_id}`" :subject-id="filters.subject_id" closable @close="remove('knowledge_parent_id')" />
      <KnowledgeTag v-if="filters.knowledge_point_id" :point="selected_point || `考点 #${filters.knowledge_point_id}`" :subject-id="filters.subject_id" show-path closable @close="remove('knowledge_point_id')" />
      <el-tag v-if="filters.unclassified" size="small" type="info" closable @close="remove('unclassified')">未分类</el-tag>
      <el-tag v-for="d in filters.difficulty" :key="'d' + d" size="small" closable @close="remove('difficulty', d)">{{ '★'.repeat(d) }}</el-tag>
      <el-tag v-for="id in filters.tag_ids" :key="'t' + id" size="small" closable :style="tag_style(tag_color(id))" @close="remove('tag_ids', id)">{{ tag_name(id) }}</el-tag>
      <el-tag v-if="filters.grade" size="small" closable @close="remove('grade')">{{ grade_label(filters.grade) }}</el-tag>
      <el-tag v-if="filters.semester" size="small" closable @close="remove('semester')">{{ semester_label(filters.semester) }}</el-tag>
      <el-tag v-if="filters.accuracy_range" size="small" closable @close="remove('accuracy_range')">{{ accuracy_range_label(filters.accuracy_range) }}</el-tag>
      <el-button link type="primary" size="small" @click="clear_all">清空</el-button>
    </div>

    <!-- 手机筛选抽屉：改的是一份草稿，点"确定"才生效并查询 -->
    <el-drawer v-model="drawer_visible" direction="btt" size="auto" title="筛选" class="q-filter-drawer">
      <div class="qd-body">
        <div class="qd-label">学科 / 难度</div>
        <div class="qd-grid">
          <el-select v-model="draft.subject_id" placeholder="学科" clearable @change="on_draft_subject_change">
            <el-option v-for="s in subjects" :key="s.id" :label="s.name" :value="s.id" />
          </el-select>
          <el-select v-model="draft.difficulty" placeholder="难度" multiple collapse-tags clearable>
            <el-option v-for="i in 5" :key="i" :label="'★'.repeat(i)" :value="i" />
          </el-select>
        </div>
        <div class="qd-label">知识点</div>
        <div class="qd-grid">
          <el-select v-model="draft.knowledge_parent_id" placeholder="一级模块" clearable filterable :disabled="!draft.subject_id" @change="draft.knowledge_point_id = null">
            <el-option v-for="m in modules_of(draft.subject_id)" :key="m.id" :label="m.name" :value="m.id" />
          </el-select>
          <el-select v-model="draft.knowledge_point_id" placeholder="二级考点" clearable filterable :disabled="!draft.knowledge_parent_id">
            <el-option v-for="p in points_of(draft.subject_id, draft.knowledge_parent_id)" :key="p.id" :label="p.name" :value="p.id" />
          </el-select>
        </div>
        <el-checkbox v-model="draft.unclassified" class="qd-check" @change="on_unclassified_change(draft, false)">只看未分类</el-checkbox>
        <div class="qd-label">年级 / 学期 / 正确率</div>
        <div class="qd-grid is-three">
          <el-select v-model="draft.grade" placeholder="年级" clearable>
            <el-option v-for="g in GRADE_OPTIONS" :key="g.value" :label="g.label" :value="g.value" />
          </el-select>
          <el-select v-model="draft.semester" placeholder="学期" clearable>
            <el-option label="上学期" :value="1" />
            <el-option label="下学期" :value="2" />
          </el-select>
          <el-select v-model="draft.accuracy_range" placeholder="正确率" clearable>
            <el-option v-for="opt in ACCURACY_RANGE_OPTIONS" :key="opt.value" :label="opt.label" :value="opt.value" />
          </el-select>
        </div>
        <div class="qd-label">标签</div>
        <el-select v-model="draft.tag_ids" placeholder="标签" multiple collapse-tags clearable style="width: 100%">
          <el-option v-for="t in tags" :key="t.id" :label="t.name" :value="t.id" />
        </el-select>
      </div>
      <template #footer>
        <div class="qd-footer">
          <el-button @click="reset_filters(draft)">重置</el-button>
          <el-button type="primary" @click="apply_drawer">确定</el-button>
        </div>
      </template>
    </el-drawer>
  </div>
</template>

<script setup>
import { computed, reactive, ref } from 'vue'
import { Search } from '@element-plus/icons-vue'
import {
  GRADE_OPTIONS, ACCURACY_RANGE_OPTIONS, grade_label, semester_label, accuracy_range_label,
  empty_filters, active_filter_count, clear_knowledge, reset_filters, remove_filter, tag_style,
} from './questionFilters'

const props = defineProps({
  // 当前生效的筛选条件（AllTab 里的 reactive 对象，这里直接改它的字段，改完发 change）
  filters: { type: Object, required: true },
  subjects: { type: Array, default: () => [] },
  tags: { type: Array, default: () => [] },
  // 各学科的知识模块：{ [学科编号]: [{ id, name, children: [...] }] }
  modulesBySubject: { type: Object, default: () => ({}) },
  // 取某个学科的筛选项（有缓存，同一学科只请求一次）
  loadOptions: { type: Function, required: true },
  isMobile: { type: Boolean, default: false },
})
// change：其余筛选变了（父组件回到第 1 页再查）；subject-change：电脑上换学科；apply：手机抽屉点了确定
const emit = defineEmits(['change', 'subject-change', 'apply'])

const drawer_visible = ref(false)
const draft = reactive(empty_filters())

const active_count = computed(() => active_filter_count(props.filters))

/** 某个学科的一级模块列表 */
function modules_of(subject_id) {
  return (subject_id && props.modulesBySubject[subject_id]) || []
}

/** 某个一级模块下的二级考点 */
function points_of(subject_id, parent_id) {
  return modules_of(subject_id).find(m => m.id === parent_id)?.children || []
}

// 已选的一级模块、二级考点（小标签显示名称用；筛选项还没取到时为 null）
const selected_module = computed(() => modules_of(props.filters.subject_id).find(m => m.id === props.filters.knowledge_parent_id) || null)
const selected_point = computed(() => {
  for (const m of modules_of(props.filters.subject_id)) {
    const point = (m.children || []).find(p => p.id === props.filters.knowledge_point_id)
    if (point) return point
  }
  return null
})

/** 学科、标签的名称 */
function subject_name(id) {
  return props.subjects.find(s => s.id === id)?.name || '学科'
}
function tag_name(id) {
  return props.tags.find(t => t.id === id)?.name || '标签'
}
function tag_color(id) {
  return props.tags.find(t => t.id === id)?.color || ''
}

/** 电脑上换一级模块：二级考点跟着清掉 */
function on_module_change() {
  props.filters.knowledge_point_id = null
  emit('change')
}

/** 勾"只看未分类"时清掉知识点；notify 为假时只改条件不查询（手机抽屉） */
function on_unclassified_change(target, notify = true) {
  if (target.unclassified) clear_knowledge(target)
  if (notify) emit('change')
}

/** 去掉一项已选条件，马上查询 */
function remove(key, value) {
  remove_filter(props.filters, key, value)
  emit('change')
}

/** 清空全部筛选（搜索词保留），马上查询 */
function clear_all() {
  reset_filters(props.filters)
  emit('change')
}

/** 打开手机抽屉：草稿从当前条件复制一份 */
function open_drawer() {
  Object.assign(draft, JSON.parse(JSON.stringify(props.filters)))
  drawer_visible.value = true
}

/** 抽屉里换学科：清掉草稿里的知识点，并取新学科的知识点选项 */
function on_draft_subject_change(value) {
  clear_knowledge(draft)
  props.loadOptions(value)
}

/** 抽屉点"确定"：把草稿交给父组件生效（回到第 1 页查询），关上抽屉 */
function apply_drawer() {
  emit('apply', { ...draft, difficulty: [...draft.difficulty], tag_ids: [...draft.tag_ids] })
  drawer_visible.value = false
}
</script>

<style scoped>
.qf-bar { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; }
.qf-keyword { width: 240px; }
.qf-w-xs { width: 104px; }
.qf-w-sm { width: 132px; }
.qf-w-md { width: 168px; }
.qf-bar :deep(.el-checkbox.is-bordered) { margin: 0; height: 32px; }
.qf-filter-btn { flex: none; margin: 0; }
.qf-count {
  margin-left: 4px; padding: 0 6px; border-radius: 8px; font-size: 11px; line-height: 16px;
  color: #fff; background: var(--brand);
}
.qf-chips { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; padding: 12px 0 2px; font-size: 13px; }
.qf-chips-label { color: var(--muted); }

@media (max-width: 768px) {
  .qf-bar { flex-wrap: nowrap; }
  .qf-keyword { flex: 1; min-width: 0; width: auto; }
  /* 已选条件：一行横向滑动，不换行 */
  .qf-chips.is-mobile { flex-wrap: nowrap; overflow-x: auto; gap: 6px; padding: 10px 0 2px; }
  .qf-chips.is-mobile .qf-chips-label { display: none; }
  .qf-chips.is-mobile > * { flex: none; }
}

/* 抽屉内容 */
.qd-body { display: flex; flex-direction: column; }
.qd-label { margin: 10px 0 6px; font-size: 12px; color: var(--muted); }
.qd-label:first-child { margin-top: 0; }
.qd-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; }
.qd-grid.is-three { grid-template-columns: repeat(3, minmax(0, 1fr)); }
.qd-check { margin-top: 8px; }
.qd-footer { display: flex; gap: 8px; }
.qd-footer :deep(.el-button) { flex: 1; height: 40px; margin: 0; }
.qd-footer :deep(.el-button--primary) { flex: 2; }
</style>

<style>
/* 手机筛选抽屉外框（抽屉挂在 body 下，scoped 样式管不到） */
.el-drawer.q-filter-drawer { max-height: 85vh; border-radius: 16px 16px 0 0; }
.el-drawer.q-filter-drawer .el-drawer__header { margin-bottom: 8px; padding: 14px 16px 0; }
.el-drawer.q-filter-drawer .el-drawer__body { padding: 8px 16px; }
.el-drawer.q-filter-drawer .el-drawer__footer { padding: 10px 16px calc(12px + env(safe-area-inset-bottom)); }
</style>
