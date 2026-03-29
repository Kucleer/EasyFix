<template>
  <div class="settings">
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
        <!-- OCR配置 -->
        <el-tab-pane label="OCR配置" name="ocr">
          <el-form :model="ocrForm" label-width="120px" style="max-width: 600px">
            <el-form-item label="OCR服务商">
              <el-select v-model="ocrForm.provider" placeholder="选择OCR服务商">
                <el-option label="多模态模型 (推荐)" value="multimodal" />
                <el-option label="百度OCR" value="baidu" />
                <el-option label="腾讯OCR" value="tencent" />
                <el-option label="PaddleOCR (本地)" value="paddleocr" />
                <el-option label="Tesseract (本地)" value="tesseract" />
              </el-select>
            </el-form-item>

            <!-- 多模态模型配置 -->
            <el-divider v-if="ocrForm.provider === 'multimodal'">多模态模型OCR配置</el-divider>
            <el-form-item v-if="ocrForm.provider === 'multimodal'" label="模型提供商">
              <el-select v-model="ocrForm.multimodal_provider" placeholder="选择多模态模型">
                <el-option label="OpenAI (GPT-4V/4o)" value="openai" />
                <el-option label="Claude (Vision)" value="claude" />
                <el-option label="阿里 (Qwen-VL)" value="qwen" />
              </el-select>
            </el-form-item>

            <!-- OpenAI配置 -->
            <el-form-item v-if="ocrForm.provider === 'multimodal' && ocrForm.multimodal_provider === 'openai'" label="API Key">
              <el-input v-model="ocrForm.openai_api_key" placeholder="请输入OpenAI API Key" show-password />
            </el-form-item>
            <el-form-item v-if="ocrForm.provider === 'multimodal' && ocrForm.multimodal_provider === 'openai'" label="模型">
              <el-select v-model="ocrForm.openai_vision_model" placeholder="选择模型">
                <el-option label="GPT-4o (最新)" value="gpt-4o" />
                <el-option label="GPT-4 Turbo" value="gpt-4-turbo" />
                <el-option label="GPT-4 Vision" value="gpt-4-vision-preview" />
              </el-select>
            </el-form-item>
            <el-form-item v-if="ocrForm.provider === 'multimodal' && ocrForm.multimodal_provider === 'openai'">
              <el-alert type="info" :closable="false">
                <template #title>
                  OpenAI计费：约¥0.01-0.1/张图片 | <a href="https://platform.openai.com/docs/vision" target="_blank">查看详情</a>
                </template>
              </el-alert>
            </el-form-item>

            <!-- Claude配置 -->
            <el-form-item v-if="ocrForm.provider === 'multimodal' && ocrForm.multimodal_provider === 'claude'" label="API Key">
              <el-input v-model="ocrForm.anthropic_api_key" placeholder="请输入Anthropic API Key" show-password />
            </el-form-item>
            <el-form-item v-if="ocrForm.provider === 'multimodal' && ocrForm.multimodal_provider === 'claude'" label="模型">
              <el-select v-model="ocrForm.claude_vision_model" placeholder="选择模型">
                <el-option label="Claude 3 Opus (最强)" value="claude-3-opus-20240229" />
                <el-option label="Claude 3 Sonnet (平衡)" value="claude-3-sonnet-20240229" />
                <el-option label="Claude 3 Haiku (快速)" value="claude-3-haiku-20240307" />
              </el-select>
            </el-form-item>
            <el-form-item v-if="ocrForm.provider === 'multimodal' && ocrForm.multimodal_provider === 'claude'">
              <el-alert type="info" :closable="false">
                <template #title>
                  Claude计费：约¥0.01-0.15/张图片 | <a href="https://docs.anthropic.com/claude/docs/vision" target="_blank">查看详情</a>
                </template>
              </el-alert>
            </el-form-item>

            <!-- Qwen配置 -->
            <el-form-item v-if="ocrForm.provider === 'multimodal' && ocrForm.multimodal_provider === 'qwen'" label="API Key">
              <el-input v-model="ocrForm.qwen_api_key" placeholder="请输入阿里云API Key" show-password />
            </el-form-item>
            <el-form-item v-if="ocrForm.provider === 'multimodal' && ocrForm.multimodal_provider === 'qwen'" label="模型">
              <el-select v-model="ocrForm.qwen_vision_model" placeholder="选择模型">
                <el-option label="Qwen-VL-Max (最强)" value="qwen-vl-max" />
                <el-option label="Qwen-VL-Plus" value="qwen-vl-plus" />
              </el-select>
            </el-form-item>
            <el-form-item v-if="ocrForm.provider === 'multimodal' && ocrForm.multimodal_provider === 'qwen'">
              <el-alert type="info" :closable="false">
                <template #title>
                  阿里云百炼计费：约¥0.002-0.02/张图片 | <a href="https://help.aliyun.com/zh/dashscope" target="_blank">查看详情</a>
                </template>
              </el-alert>
            </el-form-item>

            <!-- 传统OCR配置 -->
            <el-divider v-if="ocrForm.provider === 'baidu'">百度OCR配置</el-divider>
            <el-form-item v-if="ocrForm.provider === 'baidu'" label="API Key">
              <el-input v-model="ocrForm.baidu_api_key" placeholder="请输入百度OCR API Key" show-password />
            </el-form-item>
            <el-form-item v-if="ocrForm.provider === 'baidu'" label="Secret Key">
              <el-input v-model="ocrForm.baidu_secret_key" placeholder="请输入百度OCR Secret Key" show-password />
            </el-form-item>
            <el-form-item v-if="ocrForm.provider === 'baidu'">
              <el-alert type="info" :closable="false">
                <template #title>
                  百度OCR计费：¥1/1000次 | <a href="https://cloud.baidu.com/product/ocr" target="_blank">前往申请</a>
                </template>
              </el-alert>
            </el-form-item>

            <el-divider v-if="ocrForm.provider === 'tencent'">腾讯OCR配置</el-divider>
            <el-form-item v-if="ocrForm.provider === 'tencent'" label="App ID">
              <el-input v-model="ocrForm.tencent_app_id" placeholder="请输入腾讯App ID" />
            </el-form-item>
            <el-form-item v-if="ocrForm.provider === 'tencent'" label="Secret ID">
              <el-input v-model="ocrForm.tencent_secret_id" placeholder="请输入Secret ID" show-password />
            </el-form-item>
            <el-form-item v-if="ocrForm.provider === 'tencent'" label="Secret Key">
              <el-input v-model="ocrForm.tencent_secret_key" placeholder="请输入Secret Key" show-password />
            </el-form-item>
            <el-form-item v-if="ocrForm.provider === 'tencent'" label="Bucket">
              <el-input v-model="ocrForm.tencent_bucket" placeholder="请输入Bucket名称" />
            </el-form-item>
            <el-form-item v-if="ocrForm.provider === 'tencent'">
              <el-alert type="info" :closable="false">
                <template #title>
                  腾讯OCR计费：¥0.0015/次 | <a href="https://cloud.tencent.com/product/ocr" target="_blank">前往申请</a>
                </template>
              </el-alert>
            </el-form-item>

            <el-divider v-if="ocrForm.provider === 'paddleocr'">PaddleOCR配置 (本地)</el-divider>
            <el-form-item v-if="ocrForm.provider === 'paddleocr'">
              <el-alert type="success" :closable="false">
                <template #title>
                  PaddleOCR为本地OCR引擎，无需API密钥，但需要安装paddlepaddle。<br>
                  安装命令：pip install paddlepaddle paddleocr<br>
                  注意：需要Python 3.10以下环境
                </template>
              </el-alert>
            </el-form-item>

            <el-divider v-if="ocrForm.provider === 'tesseract'">Tesseract配置 (本地)</el-divider>
            <el-form-item v-if="ocrForm.provider === 'tesseract'" label="Tesseract路径">
              <el-input v-model="ocrForm.tesseract_path" placeholder="如：C:\Program Files\Tesseract-OCR\tesseract.exe" />
            </el-form-item>
            <el-form-item v-if="ocrForm.provider === 'tesseract'">
              <el-alert type="success" :closable="false">
                <template #title>
                  Tesseract为开源本地OCR引擎，需要单独安装。<br>
                  下载地址：https://github.com/UB-Mannheim/tesseract/wiki<br>
                  中文语言包：chi_sim (简体中文)
                </template>
              </el-alert>
            </el-form-item>

            <el-form-item>
              <el-button type="primary" @click="saveOcrConfig" :loading="saving">
                保存OCR配置
              </el-button>
            </el-form-item>
          </el-form>
        </el-tab-pane>

        <!-- 自定义OCR -->
        <el-tab-pane label="自定义OCR" name="custom">
          <el-form :model="customForm" label-width="120px" style="max-width: 800px">
            <el-form-item label="接口地址">
              <el-input v-model="customForm.api_url" placeholder="自定义OCR API接口地址" />
            </el-form-item>
            <el-form-item label="请求方法">
              <el-select v-model="customForm.method">
                <el-option label="POST" value="POST" />
                <el-option label="GET" value="GET" />
              </el-select>
            </el-form-item>
            <el-form-item label="请求头">
              <el-input
                v-model="customForm.headers"
                type="textarea"
                :rows="3"
                placeholder='{"Content-Type": "application/json", "Authorization": "Bearer xxx"}'
              />
            </el-form-item>
            <el-form-item label="请求体模板">
              <el-input
                v-model="customForm.body_template"
                type="textarea"
                :rows="4"
                placeholder='{"image": "${base64_image}"}'
              />
              <div class="form-tip">
                支持变量：${base64_image} (图片Base64), ${image_path} (图片路径)
              </div>
            </el-form-item>
            <el-form-item label="结果提取">
              <el-input
                v-model="customForm.response_parser"
                type="textarea"
                :rows="2"
                placeholder='response.words_result.map(w => w.words).join("\n")'
              />
              <div class="form-tip">
                JavaScript表达式，从API响应中提取文字
              </div>
            </el-form-item>
            <el-form-item>
              <el-button type="primary" @click="saveCustomConfig" :loading="saving">
                保存自定义配置
              </el-button>
            </el-form-item>
          </el-form>
        </el-tab-pane>

        <!-- LLM配置 -->
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
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { configApi } from '@/api/question'
import axios from 'axios'

const activeTab = ref('ocr')
const saving = ref(false)
const loading = ref(false)
const showPasswordDialog = ref(true)
const isVerified = ref(false)
const password = ref('')
const verifying = ref(false)

const ocrForm = reactive({
  provider: 'multimodal',
  // 多模态模型
  multimodal_provider: 'openai',
  openai_api_key: '',
  openai_vision_model: 'gpt-4o',
  anthropic_api_key: '',
  claude_vision_model: 'claude-3-sonnet-20240229',
  qwen_api_key: '',
  qwen_vision_model: 'qwen-vl-max',
  // 百度
  baidu_api_key: '',
  baidu_secret_key: '',
  // 腾讯
  tencent_app_id: '',
  tencent_secret_id: '',
  tencent_secret_key: '',
  tencent_bucket: '',
  // 本地
  tesseract_path: '',
})

const customForm = reactive({
  api_url: '',
  method: 'POST',
  headers: '{}',
  body_template: '{"image": "${base64_image}"}',
  response_parser: 'response.words_result?.map(w => w.words).join("\\n") || ""',
})

const llmForm = reactive({
  provider: 'openai',
  api_key: '',
  base_url: 'https://api.openai.com/v1',
  model: 'gpt-4o',
})

const saveOcrConfig = async () => {
  saving.value = true
  try {
    await configApi.saveOcrConfig(ocrForm)
    ElMessage.success('OCR配置已保存')
  } catch (error) {
    ElMessage.error('保存失败: ' + (error.message || '未知错误'))
  } finally {
    saving.value = false
  }
}

const saveCustomConfig = async () => {
  saving.value = true
  try {
    await configApi.saveCustomOcrConfig(customForm)
    ElMessage.success('自定义OCR配置已保存')
  } catch (error) {
    ElMessage.error('保存失败: ' + (error.message || '未知错误'))
  } finally {
    saving.value = false
  }
}

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
    const { data: ocrData } = await configApi.getOcrConfig()
    Object.assign(ocrForm, ocrData)

    const { data: customData } = await configApi.getCustomOcrConfig()
    Object.assign(customForm, customData)

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
.settings {
  max-width: 900px;
  margin: 0 auto;
}

.form-tip {
  font-size: 12px;
  color: #999;
  margin-top: 5px;
}

.el-divider {
  margin: 20px 0 10px;
}
</style>
