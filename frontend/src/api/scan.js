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
    // 一步最慢约 120 秒（后端调主机、调模型的时限），页面多等一点；卡住判定是 180 秒
    return api.post(`/scan/pages/${id}/advance`, null, { timeout: 150000 })
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
  // "全部录入"没有单独的接口：页面按顺序逐道调 accept
  accept(id, seq) {
    return api.post(`/scan/pages/${id}/items/${seq}/accept`)
  },
  withdraw(id, seq) {
    return api.post(`/scan/pages/${id}/items/${seq}/withdraw`)
  },
}
