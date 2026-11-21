import axios from '@/api/http'

const api = axios.create({
  baseURL: '/api',
  timeout: 120000, // 生成 PDF 可能较慢
})

// 练习集（错题练习卷、考点卷、单词、阅读练习）的通用接口；考点卷特有的出卷、预批在 targeted.js
export const practiceApi = {
  // 列表（筛选参数原样传给后端）
  list(params) {
    return api.get('/practice-sets', { params })
  },
  // 详情：不走前端短时缓存，保证批改、换题后看到的是最新内容
  detail(id) {
    return api.get(`/practice-sets/${id}`, { cache: false })
  },
  // 改名称、备注
  update(id, data) {
    return api.put(`/practice-sets/${id}`, data)
  },
  remove(id) {
    return api.delete(`/practice-sets/${id}`)
  },
  batchRemove(ids) {
    return api.post('/practice-sets/batch-delete', { ids })
  },
  batchDownloadPdf(ids) {
    return api.post('/practice-sets/batch-download-pdf', { ids })
  },
  generatePdf(id) {
    return api.post(`/practice-sets/${id}/generate-pdf`)
  },
  // 提交批改：统一用 JSON，payload 里可带 question_results、question_knowledge、images 等
  markReviewed(id, payload = {}) {
    return api.post(`/practice-sets/${id}/mark-reviewed`, payload)
  },
  // 换批改照片（不重复计批改次数）
  updateReviewImages(id, images) {
    return api.put(`/practice-sets/${id}/review-images`, { images })
  },
  // 用一篇阅读短文建一份阅读练习
  generateFromReading(payload) {
    return api.post('/practice-sets/generate-from-reading', payload)
  },
}

export default practiceApi
