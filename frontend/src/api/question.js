import axios from '@/api/http'

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
  getKnowledgePointTree(params) {
    return api.get('/knowledge-points/tree', { params })
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
  batchGenerateSimilar(data) {
    return api.post('/questions/batch-similar', data)
  },
  // 这道题出现在哪些练习里、每次对错
  practiceHistory(id) {
    return api.get(`/questions/${id}/practice-history`)
  },
  getFilterOptions(subjectId) {
    return api.get(`/questions/filter-options/${subjectId}`)
  },
}

// 学习概览API
export const statsOverviewApi = {
  getOverview(params) {
    return api.get('/stats/overview', { params })
  },
}

// 统计API
export const statsApi = {
  getSummary(params) {
    return api.get('/stats/summary', { params })
  },
}

export default api
