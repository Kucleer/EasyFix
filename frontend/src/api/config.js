import axios from '@/api/http'

const api = axios.create({
  baseURL: '/api',
  timeout: 30000,
})

// 应用配置（默认年级、学期）和模型配置，只此一份
export const configApi = {
  /** 获取应用配置（默认年级/学期） */
  getApp() {
    return api.get('/config/app')
  },

  /** 保存应用配置 */
  saveApp(data) {
    return api.post('/config/app', data)
  },

  /** 获取模型配置（不走前端缓存，见 http.js） */
  getLlm() {
    return api.get('/config/llm')
  },

  /** 保存模型配置 */
  saveLlm(data) {
    return api.post('/config/llm', data)
  },
}

export default configApi
