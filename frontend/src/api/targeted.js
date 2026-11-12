import axios from '@/api/http'

const api = axios.create({
  baseURL: '/api',
  timeout: 120000,
})

// 考点卷相关接口（都不走前端短时缓存）
export const targetedApi = {
  status() {
    return api.get('/practice-sets/targeted/status', { cache: false })
  },
  plan(params) {
    return api.post('/practice-sets/targeted/plan', params)
  },
  create(payload) {
    return api.post('/practice-sets/targeted', payload)
  },
  prepare(id, fallback = false) {
    return api.post(`/practice-sets/targeted/${id}/prepare`, { fallback })
  },
  reroll(id, itemId) {
    return api.post(`/practice-sets/targeted/${id}/reroll`, { item_id: itemId })
  },
  detail(id) {
    return api.get(`/practice-sets/${id}`, { cache: false })
  },
  generatePdf(id) {
    return api.post(`/practice-sets/${id}/generate-pdf`)
  },
  grade(id, payload) {
    return api.post(`/practice-sets/${id}/mark-reviewed`, payload)
  },
  // 待批改的卷子：最近 30 天、未批改
  pending() {
    const start = new Date(Date.now() - 30 * 86400000)
    const pad = n => String(n).padStart(2, '0')
    const start_date = `${start.getFullYear()}-${pad(start.getMonth() + 1)}-${pad(start.getDate())}`
    return api.get('/practice-sets', {
      params: { source_type: 'question', reviewed: false, limit: 50, start_date },
      cache: false,
    })
  },
  uploadImages(files) {
    const form = new FormData()
    for (const file of files) form.append('files', file)
    return api.post('/upload/batch-simple', form)
  },
}
