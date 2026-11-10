import axios from '@/api/http'

const api = axios.create({
  baseURL: '/api',
  timeout: 60000,
})

// 卷子和作业相关API
export const paperApi = {
  list(params) {
    return api.get('/papers', { params })
  },
  get(id) {
    return api.get(`/papers/${id}`)
  },
  create(data) {
    return api.post('/papers', data)
  },
  update(id, data) {
    return api.put(`/papers/${id}`, data)
  },
  // withQuestions 为真时连同卷子下的题目一起删除
  remove(id, withQuestions = false) {
    return api.delete(`/papers/${id}`, { params: withQuestions ? { with_questions: 1 } : {} })
  },
}

// 待核对相关API
export const reviewApi = {
  count() {
    return api.get('/questions/review/count')
  },
  pending(params) {
    return api.get('/questions', { params: { ...params, review_status: 'pending' } })
  },
  approve(id) {
    return api.post(`/questions/${id}/review`, { action: 'approve' })
  },
  reject(id) {
    return api.post(`/questions/${id}/review`, { action: 'reject' })
  },
}
