import axios from '@/api/http'

const api = axios.create({
  baseURL: '/api',
  timeout: 30000,
})

export const configApi = {
  /** 获取应用配置（默认年级/学期） */
  getApp() {
    return api.get('/config/app')
  },

  /** 保存应用配置 */
  saveApp(data) {
    return api.post('/config/app', data)
  },
}

export default configApi
