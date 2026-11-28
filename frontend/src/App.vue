<template>
  <div class="app-shell">
    <!-- 电脑侧栏：按"学生用 / 家长用 / 看成果"分组，样式照样稿 -->
    <aside class="app-sidebar">
      <RouterLink class="app-brand" to="/"><span class="brand-mark">E</span>EasyFix</RouterLink>
      <!-- 当前学生：家庭有几个学生时点开可以切换 -->
      <div v-if="accountStore.student" class="student-switch">
        <el-dropdown v-if="accountStore.students.length > 1" trigger="click" @command="switch_student">
          <button type="button" class="student-name">{{ accountStore.student.name }}<span class="caret">▾</span></button>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item
                v-for="item in accountStore.students"
                :key="item.id"
                :command="item.id"
                :disabled="item.id === accountStore.student.id"
              >{{ item.name }}</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
        <span v-else class="student-name">{{ accountStore.student.name }}</span>
      </div>
      <nav aria-label="主菜单">
        <template v-for="group in nav_groups" :key="group.key">
          <p v-if="group.label" class="nav-label">{{ group.label }}</p>
          <RouterLink
            v-for="item in group.items"
            :key="item.id"
            :to="link_of(item)"
            class="nav-link"
            :class="{ on: is_active(item) }"
          >
            <LineIcon :name="item.icon" />
            <span>{{ item.name }}</span>
            <b v-if="badge_of(item)" class="nav-badge">{{ badge_of(item) }}</b>
            <span v-else-if="item.is_new" class="nav-new">新</span>
          </RouterLink>
        </template>
      </nav>
      <p class="sidebar-note">每一次订正，都是新的进步。</p>
      <button type="button" class="logout" @click="accountStore.logout()">退出登录</button>
    </aside>

    <!-- 页面内容（不再有顶部栏） -->
    <main class="app-main">
      <RouterView v-slot="{ Component, route }">
        <component :is="Component" :key="route.meta.separateView ? route.name : undefined" />
      </RouterView>
    </main>

    <!-- 手机底部导航：固定 4 格 + "更多" -->
    <nav class="mobile-navigation" aria-label="手机导航">
      <RouterLink
        v-for="item in bottom_items"
        :key="item.id"
        :to="link_of(item)"
        :class="{ on: is_active(item) }"
      >
        <span class="pill"><LineIcon :name="item.icon" /></span>
        {{ item.name }}
        <b v-if="badge_of(item)" class="nav-badge">{{ badge_of(item) }}</b>
      </RouterLink>
      <button type="button" :class="{ on: in_more }" @click="more_open = true">
        <span class="pill"><LineIcon name="more" /></span>
        更多
      </button>
    </nav>

    <!-- 手机"更多"抽屉：底部 4 格以外的入口 -->
    <el-drawer
      v-model="more_open"
      direction="btt"
      size="auto"
      :with-header="false"
      class="more-sheet"
      modal-class="more-sheet-mask"
      aria-label="更多入口"
    >
      <!-- 手机"更多"顶部：当前学生、切换、退出 -->
      <div v-if="accountStore.student" class="more-account">
        <span class="student-name">{{ accountStore.student.name }}</span>
        <el-button
          v-for="item in other_students"
          :key="item.id"
          size="small"
          @click="switch_student(item.id)"
        >切换到{{ item.name }}</el-button>
        <el-button size="small" @click="accountStore.logout()">退出登录</el-button>
      </div>
      <nav class="mobile-more">
        <RouterLink
          v-for="item in more_items"
          :key="item.id"
          :to="link_of(item)"
          class="nav-link"
          :class="{ on: is_active(item) }"
          @click="more_open = false"
        >
          <LineIcon :name="item.icon" />
          <span>{{ item.name }}</span>
          <b v-if="badge_of(item)" class="nav-badge">{{ badge_of(item) }}</b>
          <span v-else-if="item.is_new" class="nav-new">新</span>
        </RouterLink>
      </nav>
    </el-drawer>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import LineIcon from '@/components/ui/LineIcon.vue'
import { ElMessage } from 'element-plus'
import { useAccountStore } from '@/stores/account'
import { useAppConfigStore } from '@/stores/appConfig'
import { useReviewCountStore } from '@/stores/reviewCount'
// "翻一翻"入口开关放在 config/features.js，首页和菜单共用
import { FLIP_READY } from '@/config/features'

// 菜单项：id 同时是图标名；match 判断当前地址是否算这一项（用来高亮）
const ITEMS = {
  home: { id: 'home', name: '首页', to: '/', match: (path) => path === '/' },
  words: { id: 'words', name: '单词', to: '/words', match: (path) => path === '/words' },
  flip: { id: 'flip', name: '翻一翻', to: '/flip', is_new: true, match: (path) => path === '/flip' },
  englishFlip: { id: 'english-flip', name: '英语错题翻一翻', to: '/flip/english', match: (path) => path === '/flip/english' },
  reading: {
    id: 'reading', name: '阅读', to: '/reading',
    // 阅读练习页也算"阅读"
    match: (path) => path === '/reading' || path.startsWith('/reading-test/'),
  },
  questions: {
    id: 'questions', name: '错题', to: '/questions', badge: true,
    // 手工添加和卷子详情都算"错题"
    match: (path) => path === '/questions' || path === '/upload' || path.startsWith('/papers/'),
  },
  practice: {
    id: 'practice', name: '练习', to: '/practice-sets',
    // 出考点卷、批改都算"练习"
    match: (path) => path === '/practice-sets' || path === '/targeted-paper' || path === '/grade' || path.startsWith('/grade/'),
  },
  weekly: {
    id: 'weekly', name: '周报', to: '/learning-reports',
    // 旧报告也算"周报"
    match: (path) => path === '/learning-reports' || path === '/learning-reports/legacy',
  },
  insight: { id: 'insight', name: '学情', to: '/insight', match: (path) => path === '/insight' },
  settings: { id: 'settings', name: '设置', to: '/settings', match: (path) => path === '/settings' },
}
// 每一项的图标名就是它的 id
for (const item of Object.values(ITEMS)) item.icon = item.id

// 隐藏还没做好的入口
const ready = (item) => !['flip', 'english-flip'].includes(item.id) || FLIP_READY

// 电脑侧栏的分组（照样稿 NAV）；没有标题的组只显示菜单项
const nav_groups = [
  { key: 'top', label: '', items: [ITEMS.home] },
  { key: 'student', label: '学生用', items: [ITEMS.words, ITEMS.flip, ITEMS.englishFlip, ITEMS.reading] },
  { key: 'parent', label: '家长用', items: [ITEMS.questions, ITEMS.practice] },
  { key: 'result', label: '看成果', items: [ITEMS.weekly, ITEMS.insight] },
  { key: 'end', label: '', items: [ITEMS.settings] },
].map((group) => ({ ...group, items: group.items.filter(ready) }))

// 手机底部固定四格（照样稿 BOTTOM_IDS），第五格是"更多"
const BOTTOM_IDS = ['home', 'words', 'questions', 'practice']
const all_items = nav_groups.flatMap((group) => group.items)
const bottom_items = BOTTOM_IDS.map((id) => ITEMS[id])
const more_items = all_items.filter((item) => !BOTTOM_IDS.includes(item.id))

const route = useRoute()
const more_open = ref(false)
const appConfigStore = useAppConfigStore()
const accountStore = useAccountStore()

// 手机"更多"里列出的、可以切换过去的其他学生
const other_students = computed(() =>
  accountStore.students.filter((item) => !accountStore.student || item.id !== accountStore.student.id))

/** 切换学生；成功后整页刷新（失败时提示） */
async function switch_student(student_id) {
  try {
    await accountStore.switchTo(student_id)
  } catch {
    ElMessage.error('切换学生失败，请稍后重试')
  }
}
const reviewCountStore = useReviewCountStore()

// 当前地址是否属于某个菜单项
function is_active(item) {
  return item.match(route.path)
}

// 当前页面属于"更多"里的某一项时，底部"更多"格也高亮
const in_more = computed(() => more_items.some((item) => is_active(item)))

// 菜单项右侧的红色数字：只有"错题"显示待核对数量，0 不显示
function badge_of(item) {
  if (!item.badge) return ''
  const count = reviewCountStore.pending
  if (count <= 0) return ''
  return count > 99 ? '99+' : String(count)
}

// 菜单项的链接：有待核对时，"错题"直接落在"待核对"标签
function link_of(item) {
  if (item.badge && reviewCountStore.pending > 0) return { path: item.to, query: { tab: 'review' } }
  return item.to
}

// 换页面时收起"更多"抽屉（包括按返回键的情况）
watch(() => route.fullPath, () => { more_open.value = false })

// 进入应用时加载配置并刷新待核对数量
onMounted(() => { accountStore.load(); appConfigStore.load(); reviewCountStore.refresh() })
</script>

<style scoped>
/* 当前学生和退出：样式尽量简单，跟随侧栏原有的颜色变量 */
.student-switch { margin: 4px 12px 12px; }
.student-name { display: inline-flex; align-items: center; gap: 4px; padding: 4px 10px; border: 0; border-radius: 999px;
  background: var(--surface-2, #eef2fb); color: var(--ink, #243149); font: inherit; font-size: 14px; cursor: pointer; }
.caret { font-size: 11px; color: var(--muted, #6b7280); }
.logout { margin: 8px 12px; padding: 6px 0; border: 0; background: none; color: var(--muted, #6b7280); font: inherit;
  font-size: 13px; text-align: left; cursor: pointer; }
.logout:hover { color: var(--ink, #243149); }
.more-account { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; padding: 12px 16px 4px; }
</style>
