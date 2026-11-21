<template>
  <!-- 设置 · 模型：相似题、周报文字等用的大模型接口 -->
  <div class="model-tab">
    <el-form v-loading="loading" :model="form" :label-width="is_mobile ? 'auto' : '100px'" :label-position="is_mobile ? 'top' : 'right'" class="model-form">
      <el-form-item label="接口类型">
        <el-select v-model="form.provider" style="width: 100%">
          <el-option v-for="p in PROVIDERS" :key="p.value" :label="p.label" :value="p.value" />
        </el-select>
      </el-form-item>
      <el-form-item label="API Key">
        <el-input v-model="form.api_key" type="password" placeholder="请输入 API Key" show-password autocomplete="off" />
      </el-form-item>
      <el-form-item label="Base URL">
        <el-input v-model="form.base_url" placeholder="接口地址，如 https://api.openai.com/v1" />
      </el-form-item>
      <el-form-item label="模型名称">
        <el-input v-model="form.model" placeholder="如 gpt-4o、claude-3-sonnet" />
      </el-form-item>
      <el-form-item>
        <el-button type="primary" :loading="saving" :disabled="loading" @click="save">保存模型配置</el-button>
      </el-form-item>
    </el-form>
  </div>
</template>

<script setup>
import { reactive, ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { configApi } from '@/api/config'
import { use_is_mobile } from '@/composables/useIsMobile'

const PROVIDERS = [
  { label: 'OpenAI', value: 'openai' },
  { label: 'Claude', value: 'claude' },
  { label: '自定义', value: 'custom' },
]

const is_mobile = use_is_mobile()
const loading = ref(true)
const saving = ref(false)
// 接口还没返回时的默认值
const form = reactive({
  provider: 'openai',
  api_key: '',
  base_url: 'https://api.openai.com/v1',
  model: 'gpt-4o',
})

/** 读当前的模型配置 */
async function load() {
  loading.value = true
  try {
    const { data } = await configApi.getLlm()
    Object.assign(form, data)
  } catch (e) {
    console.error('加载模型配置失败:', e)
  } finally {
    loading.value = false
  }
}

/** 保存模型配置 */
async function save() {
  saving.value = true
  try {
    await configApi.saveLlm(form)
    ElMessage.success('模型配置已保存')
  } catch (e) {
    ElMessage.error('保存失败：' + (e.message || '未知错误'))
  } finally {
    saving.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.model-form { max-width: 600px; }
</style>
