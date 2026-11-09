<template>
  <div class="settings">
    <PageHeading title="模型配置" description="配置内容辅助生成与学习报告使用的模型。" />
    <!-- 访问密码验证 -->
    <el-dialog v-model="showPasswordDialog" title="请输入访问密码" width="400px" :close-on-click-modal="false" :show-close="false">
      <el-form>
        <el-form-item label="访问密码">
          <el-input v-model="password" type="password" placeholder="请输入访问密码" @keyup.enter="verifyPassword" show-password />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button type="primary" @click="verifyPassword" :loading="verifying">验证</el-button>
      </template>
    </el-dialog>

    <el-card v-if="isVerified">
      <template #header>
        <span>系统配置</span>
      </template>

      <el-tabs v-model="activeTab">
        <!-- 模型配置 -->
        <el-tab-pane label="LLM配置" name="llm">
          <el-form :model="llmForm" label-width="120px" style="max-width: 600px">
            <el-form-item label="API类型">
              <el-select v-model="llmForm.provider">
                <el-option label="OpenAI" value="openai" />
                <el-option label="Claude" value="claude" />
                <el-option label="自定义" value="custom" />
              </el-select>
            </el-form-item>
            <el-form-item label="API Key">
              <el-input v-model="llmForm.api_key" placeholder="请输入API Key" show-password />
            </el-form-item>
            <el-form-item label="Base URL">
              <el-input v-model="llmForm.base_url" placeholder="API地址，如 https://api.openai.com/v1" />
            </el-form-item>
            <el-form-item label="模型名称">
              <el-input v-model="llmForm.model" placeholder="如 gpt-4o, claude-3-sonnet" />
            </el-form-item>
            <el-form-item>
              <el-button type="primary" @click="saveLlmConfig" :loading="saving">
                保存LLM配置
              </el-button>
            </el-form-item>
          </el-form>
        </el-tab-pane>
      </el-tabs>
      </el-card>
  </div>
</template>

<script setup>
import PageHeading from '@/components/PageHeading.vue'
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { configApi } from '@/api/question'
import axios from '@/api/http'

const activeTab = ref('llm')
const saving = ref(false)
const loading = ref(false)
const showPasswordDialog = ref(true)
const isVerified = ref(false)
const password = ref('')
const verifying = ref(false)

const llmForm = reactive({
  provider: 'openai',
  api_key: '',
  base_url: 'https://api.openai.com/v1',
  model: 'gpt-4o',
})

const saveLlmConfig = async () => {
  saving.value = true
  try {
    await configApi.saveLlmConfig(llmForm)
    ElMessage.success('LLM配置已保存')
  } catch (error) {
    ElMessage.error('保存失败: ' + (error.message || '未知错误'))
  } finally {
    saving.value = false
  }
}

const verifyPassword = async () => {
  if (!password.value) {
    ElMessage.warning('请输入密码')
    return
  }
  verifying.value = true
  try {
    await axios.post('/api/auth/verify-password', { password: password.value })
    isVerified.value = true
    showPasswordDialog.value = false
    loadConfigs()
  } catch (error) {
    ElMessage.error('密码错误')
    password.value = ''
  } finally {
    verifying.value = false
  }
}

const loadConfigs = async () => {
  loading.value = true
  try {
    const { data: llmData } = await configApi.getLlmConfig()
    Object.assign(llmForm, llmData)
  } catch (error) {
    console.error('加载配置失败:', error)
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.settings  {

  max-width: 900px;
  margin: 0 auto;
}

.form-tip  {

  font-size: 12px;
  color: #999;
  margin-top: 5px;
}

.el-divider  {

  margin: 20px 0 10px;
}
.settings {
  max-width:1000px;
  margin:0}
.form-tip {
  color:var(--text-muted)}
</style>
