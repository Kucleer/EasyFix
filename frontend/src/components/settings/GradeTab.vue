<template>
  <!-- 设置 · 年级与学期：各页面筛选和新建表单默认带入的年级、学期 -->
  <div class="grade-tab">
    <el-form :model="form" :label-width="is_mobile ? 'auto' : '100px'" :label-position="is_mobile ? 'top' : 'right'" class="grade-form">
      <el-form-item label="默认年级">
        <el-select v-model="form.defaultGrade" placeholder="选择默认年级" clearable style="width: 100%">
          <el-option v-for="g in GRADE_OPTIONS" :key="g.value" :label="g.label" :value="g.value" />
        </el-select>
        <div class="form-tip">各页面搜索、筛选默认用这个年级；清空后看全部</div>
      </el-form-item>
      <el-form-item label="默认学期">
        <el-select v-model="form.defaultSemester" placeholder="选择默认学期" clearable style="width: 100%">
          <el-option v-for="s in SEMESTER_OPTIONS" :key="s.value" :label="s.label" :value="s.value" />
        </el-select>
        <div class="form-tip">页面有学期筛选时，默认用这个学期</div>
      </el-form-item>
      <el-form-item>
        <el-button type="primary" :loading="saving" :disabled="loading" @click="save">保存</el-button>
      </el-form-item>
    </el-form>
    <el-alert type="info" :closable="false" class="grade-alert">
      <template #title>
        保存后立即生效：单词、错题、阅读、周报、录入等页面的默认筛选和新建表单会自动带入默认年级。
      </template>
    </el-alert>
  </div>
</template>

<script setup>
import { reactive, ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { useAppConfigStore } from '@/stores/appConfig'
import { use_is_mobile } from '@/composables/useIsMobile'
import { GRADE_OPTIONS, SEMESTER_OPTIONS } from './settingsModel'

const appConfigStore = useAppConfigStore()
const is_mobile = use_is_mobile()
const form = reactive({ defaultGrade: null, defaultSemester: null })
const loading = ref(true)
const saving = ref(false)

/** 读最新的默认年级、学期（强制重新请求，避免看到别处改过之前的旧值） */
async function load_config() {
  loading.value = true
  await appConfigStore.load(true)
  form.defaultGrade = appConfigStore.defaultGrade
  form.defaultSemester = appConfigStore.defaultSemester
  loading.value = false
}

/** 保存默认年级、学期；store 里的值同步更新，其他页面马上用上 */
async function save() {
  saving.value = true
  try {
    await appConfigStore.save({ defaultGrade: form.defaultGrade, defaultSemester: form.defaultSemester })
    ElMessage.success('默认年级和学期已保存')
  } catch {
    ElMessage.error('保存失败')
  } finally {
    saving.value = false
  }
}

onMounted(load_config)
</script>

<style scoped>
.grade-form { max-width: 480px; }
.form-tip { width: 100%; margin-top: 4px; font-size: 12px; line-height: 1.5; color: var(--muted); }
.grade-alert { margin-top: 8px; }
</style>
