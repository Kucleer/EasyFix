import axios from '@/api/http'

const api = axios.create({
  baseURL: '/api',
  timeout: 60000,
})

// 整页识别录入相关API
export const scanApi = {
  health() {
    return api.get('/scan/health', { timeout: 5000 })
  },
  create(data) {
    return api.post('/scan/pages', data)
  },
  get(id) {
    // 一页的状态随时在变（别的窗口也可能改），不走 GET 短时缓存
    return api.get(`/scan/pages/${id}`, { cache: false })
  },
  unfinished() {
    return api.get('/scan/pages/unfinished')
  },
  advance(id) {
    return api.post(`/scan/pages/${id}/advance`, null, { timeout: 180000 })
  },
  close(id) {
    return api.post(`/scan/pages/${id}/close`)
  },
  addItem(id) {
    return api.post(`/scan/pages/${id}/items`)
  },
  saveItem(id, seq, data) {
    return api.put(`/scan/pages/${id}/items/${seq}`, data)
  },
  dismiss(id, seq) {
    return api.post(`/scan/pages/${id}/items/${seq}/dismiss`)
  },
  restore(id, seq) {
    return api.post(`/scan/pages/${id}/items/${seq}/restore`)
  },
  promote(id, seq) {
    return api.post(`/scan/pages/${id}/items/${seq}/promote`, null, { timeout: 150000 })
  },
  accept(id, seq) {
    return api.post(`/scan/pages/${id}/items/${seq}/accept`)
  },
  acceptAll(id) {
    return api.post(`/scan/pages/${id}/accept-all`, null, { timeout: 120000 })
  },
  withdraw(id, seq) {
    return api.post(`/scan/pages/${id}/items/${seq}/withdraw`)
  },
}
