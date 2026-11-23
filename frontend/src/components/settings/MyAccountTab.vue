<template>
  <!-- 设置 · 我的账号：看登录名和本家庭的学生，改自己的密码 -->
  <div class="me-tab">
    <el-descriptions :column="1" border class="me-info">
      <el-descriptions-item label="登录名">{{ accountStore.username }}</el-descriptions-item>
      <el-descriptions-item label="家庭">{{ accountStore.name }}</el-descriptions-item>
      <el-descriptions-item label="学生">
        {{ accountStore.students.map(s => s.name).join('、') || '—' }}
      </el-descriptions-item>
    </el-descriptions>

    <h3>修改密码</h3>
    <el-form :model="form" :label-width="is_mobile ? 'auto' : '100px'" :label-position="is_mobile ? 'top' : 'right'" class="me-form">
      <el-form-item label="原密码">
        <el-input v-model="form.old_password" type="password" show-password autocomplete="current-password" />
      </el-form-item>
      <el-form-item label="新密码">
        <el-input v-model="form.new_password" type="password" show-password autocomplete="new-password" />
        <div class="form-tip">至少 {{ MIN_LENGTH }} 位；改完以后，其他设备上的登录需要重新登录</div>
      </el-form-item>
      <el-form-item label="再输一遍">
        <el-input v-model="form.confirm" type="password" show-password autocomplete="new-password" @keyup.enter="change" />
      </el-form-item>
      <el-form-item>
        <el-button type="primary" :loading="saving" @click="change">修改密码</el-button>
      </el-form-item>
    </el-form>
  </div>
</template>

<script setup>
import { reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { authApi } from '@/api/auth'
import { useAccountStore } from '@/stores/account'
import { use_is_mobile } from '@/composables/useIsMobile'

const MIN_LENGTH = 10   // 和网关 auth_routes.js 的 MIN_PASSWORD_LENGTH 一致
const accountStore = useAccountStore()
const is_mobile = use_is_mobile()
const form = reactive({ old_password: '', new_password: '', confirm: '' })
const saving = ref(false)

/** 改密码：先在页面上检查长度和两次输入，再交给网关；成功后清空表单 */
async function change() {
  if (saving.value) return
  if (form.new_password.length < MIN_LENGTH) {
    ElMessage.warning(`新密码至少 ${MIN_LENGTH} 位`)
    return
  }
  if (form.new_password !== form.confirm) {
    ElMessage.warning('两次输入的新密码不一样')
    return
  }
  saving.value = true
  try {
    await authApi.changePassword(form.old_password, form.new_password)
    ElMessage.success('密码已修改')
    form.old_password = form.new_password = form.confirm = ''
  } catch (error) {
    ElMessage.error(error?.response?.data?.detail || '修改失败，请稍后重试')
  } finally {
    saving.value = false
  }
}
</script>

<style scoped>
.me-info { max-width: 480px; margin-bottom: 20px; }
.me-tab h3 { margin: 0 0 12px; font-size: 16px; color: var(--ink); }
.me-form { max-width: 480px; }
.form-tip { width: 100%; margin-top: 4px; font-size: 12px; line-height: 1.5; color: var(--muted); }
</style>
