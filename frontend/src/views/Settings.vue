<template>
  <!-- 设置页：进来先验一次访问密码；标签和地址 ?tab= 同步，点到哪个标签才加载哪个标签的数据 -->
  <div class="settings-page">
    <header class="page-head">
      <h1>设置</h1>
      <p>不常改的东西都在这里，进来只验一次密码。</p>
    </header>

    <!-- 访问密码：关不掉，验过之前下面什么都不显示；回车直接验证 -->
    <el-dialog
      :model-value="!verified"
      title="请输入访问密码"
      :width="is_mobile ? '92%' : '400px'"
      :close-on-click-modal="false"
      :close-on-press-escape="false"
      :show-close="false"
      append-to-body
    >
      <el-form @submit.prevent>
        <el-form-item label="访问密码">
          <el-input v-model="password" type="password" placeholder="请输入访问密码" show-password autofocus @keyup.enter="verify" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="router.push('/')">返回首页</el-button>
        <el-button type="primary" :loading="verifying" @click="verify">验证</el-button>
      </template>
    </el-dialog>

    <template v-if="verified">
      <TabBar v-model="tab" :tabs="SETTINGS_TABS" class="page-tabs" />
      <section class="panel">
        <!-- 标签组件缓存着：第一次点到时才挂载、才请求数据，切回来时保留筛选和弹窗里记住的内容 -->
        <KeepAlive>
          <component :is="TAB_COMPONENTS[tab]" :key="tab" />
        </KeepAlive>
      </section>
    </template>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { authApi } from '@/api/auth'
import TabBar from '@/components/ui/TabBar.vue'
import StarMapSettings from '@/components/StarMapSettings.vue'
import GradeTab from '@/components/settings/GradeTab.vue'
import SubjectsTab from '@/components/settings/SubjectsTab.vue'
import TagsTab from '@/components/settings/TagsTab.vue'
import KnowledgeTab from '@/components/settings/KnowledgeTab.vue'
import ErrorBooksTab from '@/components/settings/ErrorBooksTab.vue'
import ModelTab from '@/components/settings/ModelTab.vue'
import { SETTINGS_TABS } from '@/components/settings/settingsModel'
import { useTabQuery } from '@/composables/useTabQuery'
import { use_is_mobile } from '@/composables/useIsMobile'

// 每个标签对应的组件；成就相关的三块（StarActionsPanel、AchievementsPanel、RewardsPanel）
// 暂不放进标签栏，等成就项目再加回来
const TAB_COMPONENTS = {
  grade: GradeTab,
  subjects: SubjectsTab,
  tags: TagsTab,
  knowledge: KnowledgeTab,
  books: ErrorBooksTab,
  starmap: StarMapSettings,
  model: ModelTab,
}

const router = useRouter()
const is_mobile = use_is_mobile()
const tab = useTabQuery(SETTINGS_TABS.map(t => t.key), 'grade')

// 这次打开页面是否已经验过密码；验过以后切换标签不再问
const verified = ref(false)
const password = ref('')
const verifying = ref(false)

/** 验证访问密码（会话本身已经登录，这里是改设置前再确认一次） */
async function verify() {
  if (verifying.value) return
  if (!password.value) {
    ElMessage.warning('请输入密码')
    return
  }
  verifying.value = true
  try {
    await authApi.verifyPassword(password.value)
    verified.value = true
  } catch {
    ElMessage.error('密码错误')
  } finally {
    password.value = ''
    verifying.value = false
  }
}
</script>

<style scoped>
.settings-page { max-width: 1280px; }
.page-head h1 { margin: 0; font-size: 24px; color: var(--ink); }
.page-head p { margin: 4px 0 16px; color: var(--muted); }
.page-tabs { width: fit-content; max-width: 100%; margin-bottom: 16px; }
.panel { padding: 20px 22px; border-radius: var(--r-lg); background: var(--surface); box-shadow: var(--shadow-1); }

@media (max-width: 768px) {
  .page-head h1 { font-size: 22px; }
  .page-head p { margin-bottom: 12px; font-size: 13px; }
  .panel { padding: 14px 12px; }
}
</style>
