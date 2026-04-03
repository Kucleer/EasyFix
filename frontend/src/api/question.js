import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  timeout: 60000, // 60秒超时，用于OCR识别
})

// 错题相关API
export const questionApi = {
  // 获取错题列表
  list(params) {
    return api.get('/questions', { params })
  },

  // 获取单个错题
  get(id) {
    return api.get(`/questions/${id}`)
  },

  // 创建错题
  create(data) {
    return api.post('/questions', data)
  },

  // 批量创建错题
  createBatch(data) {
    return api.post('/questions/batch', data)
  },

  // 更新错题
  update(id, data) {
    return api.put(`/questions/${id}`, data)
  },

  // 删除错题
  delete(id) {
    return api.delete(`/questions/${id}`)
  },

  // 生成相似题
  generateSimilar(id) {
    return api.post(`/questions/${id}/similar`)
  },

  // 获取错题本列表
  listErrorBooks(params) {
    return api.get('/error-books', { params })
  },

  // 获取学科列表
  listSubjects() {
    return api.get('/subjects')
  },

  // 获取标签列表
  listTags() {
    return api.get('/tags')
  },

  // 创建标签
  createTag(name, color) {
    return api.post('/tags', { name, color })
  },

  // 删除标签
  deleteTag(id) {
    return api.delete(`/tags/${id}`)
  },

  // 创建学科
  createSubject(name) {
    return api.post('/subjects', { name })
  },

  // 删除学科
  deleteSubject(id) {
    return api.delete(`/subjects/${id}`)
  },

  // 创建错题本
  createErrorBook(data) {
    return api.post('/error-books', data)
  },

  // 更新错题本
  updateErrorBook(id, data) {
    return api.put(`/error-books/${id}`, data)
  },

  // 删除错题本
  deleteErrorBook(id) {
    return api.delete(`/error-books/${id}`)
  },

  // 知识点相关
  listKnowledgePoints(params) {
    return api.get('/knowledge-points', { params })
  },
  createKnowledgePoint(data) {
    return api.post('/knowledge-points', data)
  },
  deleteKnowledgePoint(id) {
    return api.delete(`/knowledge-points/${id}`)
  },

  // 批量生成相似题
  batchGenerateSimilar(data) {
    return api.post('/questions/batch-similar', data)
  },

  // 练习集相关
  createPracticeSet(data) {
    return api.post('/practice-sets', data)
  },
  listPracticeSets(params) {
    return api.get('/practice-sets', { params })
  },
  getPracticeSet(id) {
    return api.get(`/practice-sets/${id}`)
  },
  generatePracticeSetPdf(id) {
    return api.post(`/practice-sets/${id}/generate-pdf`)
  },
  markPracticeSetReviewed(id, images = null) {
    if (images) {
      const formData = new FormData()
      formData.append('images', images)
      return api.post(`/practice-sets/${id}/mark-reviewed`, formData)
    }
    return api.post(`/practice-sets/${id}/mark-reviewed`)
  },
  // 获取练习集详情
  getPracticeSetDetail(id) {
    return api.get(`/practice-sets/${id}`)
  },
  // 更新练习集名称和备注
  updatePracticeSet(id, data) {
    return api.put(`/practice-sets/${id}`, data)
  },
  deletePracticeSet(id) {
    return api.delete(`/practice-sets/${id}`)
  },
  // 批量删除练习集
  batchDeletePracticeSets(ids) {
    return api.post('/practice-sets/batch-delete', { ids })
  },
  // 批量下载练习集PDF
  batchDownloadPracticeSetsPdf(ids) {
    return api.post('/practice-sets/batch-download-pdf', { ids })
  },
}

// 图片上传API
export const uploadApi = {
  uploadImage(file) {
    const formData = new FormData()
    formData.append('file', file)
    return api.post('/upload/image', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      timeout: 120000, // 2分钟超时
    })
  },
}

// 统计API
export const statsApi = {
  getSummary() {
    return api.get('/stats/summary')
  },
}

// 配置API
export const configApi = {
  getOcrConfig() {
    return api.get('/config/ocr')
  },
  saveOcrConfig(data) {
    return api.post('/config/ocr', data)
  },
  getLlmConfig() {
    return api.get('/config/llm')
  },
  saveLlmConfig(data) {
    return api.post('/config/llm', data)
  },
  getCustomOcrConfig() {
    return api.get('/config/custom-ocr')
  },
  saveCustomOcrConfig(data) {
    return api.post('/config/custom-ocr', data)
  },
}

export default api
