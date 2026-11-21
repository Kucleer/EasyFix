import axios from '@/api/http'

const api = axios.create({
  baseURL: '/api',
  timeout: 30000,
})

// 登录相关
export const authApi = {
  // 进入管理、配置页面前再验一次访问密码
  verifyPassword(password) {
    return api.post('/auth/verify-password', { password })
  },
}

export default authApi
