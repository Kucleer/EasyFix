import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  timeout: 60000,
})

// 错题相关API
export const questionApi = {
  list(params) {
    return api.get('/questions', { params })
  },
  get(id) {
    return api.get(`/questions/${id}`)
  },
  create(data) {
    return api.post('/questions', data)
  },
  createBatch(data) {
    return api.post('/questions/batch', data)
  },
  update(id, data) {
    return api.put(`/questions/${id}`, data)
  },
  delete(id) {
    return api.delete(`/questions/${id}`)
  },
  generateSimilar(id) {
    return api.post(`/questions/${id}/similar`)
  },
  listErrorBooks(params) {
    return api.get('/error-books', { params })
  },
  listSubjects() {
    return api.get('/subjects')
  },
  listTags() {
    return api.get('/tags')
  },
  createTag(name, color) {
    return api.post('/tags', { name, color })
  },
  deleteTag(id) {
    return api.delete(`/tags/${id}`)
  },
  createSubject(name) {
    return api.post('/subjects', { name })
  },
  deleteSubject(id) {
    return api.delete(`/subjects/${id}`)
  },
  createErrorBook(data) {
    return api.post('/error-books', data)
  },
  updateErrorBook(id, data) {
    return api.put(`/error-books/${id}`, data)
  },
  deleteErrorBook(id) {
    return api.delete(`/error-books/${id}`)
  },
  listKnowledgePoints(params) {
    return api.get('/knowledge-points', { params })
  },
  createKnowledgePoint(data) {
    return api.post('/knowledge-points', data)
  },
  updateKnowledgePoint(id, data) {
    return api.put(`/knowledge-points/${id}`, data)
  },
  deleteKnowledgePoint(id) {
    return api.delete(`/knowledge-points/${id}`)
  },
  listErrorTypes(params) {
    return api.get('/error-types', { params })
  },
  createErrorType(data) {
    return api.post('/error-types', data)
  },
  updateErrorType(id, data) {
    return api.put(`/error-types/${id}`, data)
  },
  deleteErrorType(id) {
    return api.delete(`/error-types/${id}`)
  },
  batchGenerateSimilar(data) {
    return api.post('/questions/batch-similar', data)
  },
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
  markPracticeSetReviewedWithGrading(id, questionResults) {
    const formData = new FormData()
    formData.append('question_results', JSON.stringify(questionResults))
    return api.post(`/practice-sets/${id}/mark-reviewed`, formData)
  },
  getPracticeSetDetail(id) {
    return api.get(`/practice-sets/${id}`)
  },
  updatePracticeSet(id, data) {
    return api.put(`/practice-sets/${id}`, data)
  },
  updatePracticeSetReviewImages(id, images) {
    return api.put(`/practice-sets/${id}/review-images`, { images })
  },
  deletePracticeSet(id) {
    return api.delete(`/practice-sets/${id}`)
  },
  batchDeletePracticeSets(ids) {
    return api.post('/practice-sets/batch-delete', { ids })
  },
  batchDownloadPracticeSetsPdf(ids) {
    return api.post('/practice-sets/batch-download-pdf', { ids })
  },
  getFilterOptions(subjectId) {
    return api.get(`/questions/filter-options/${subjectId}`)
  },
  generateFromQuestions(params) {
    return api.post('/practice-sets/generate-from-questions', params)
  },
}

// 学习概览API
export const statsOverviewApi = {
  getOverview(params) {
    return api.get('/stats/overview', { params })
  },
}

// 图片上传API
export const uploadApi = {
  uploadFile(file) {
    const formData = new FormData()
    formData.append('file', file)
    return api.post('/upload/file', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },
}

// 统计API
export const statsApi = {
  getSummary(params) {
    return api.get('/stats/summary', { params })
  },
  getTodayStats() {
    return api.get('/stats/today')
  },
  getKnowledgePoints() {
    return api.get('/stats/knowledge-points')
  },
}

// 配置API
export const configApi = {
  getLlmConfig() {
    return api.get('/config/llm')
  },
  saveLlmConfig(data) {
    return api.post('/config/llm', data)
  },
}

export default api
