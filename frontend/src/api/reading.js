import axios from '@/api/http'

const api = axios.create({
  baseURL: '/api',
  timeout: 120000, // 生成短文要调模型
})

// 阅读短文
export const readingApi = {
  topics() {
    return api.get('/readings/topics')
  },
  list(params) {
    return api.get('/readings', { params })
  },
  get(id) {
    return api.get(`/readings/${id}`)
  },
  // 按年级、话题生成一篇短文和配套题
  generate(payload) {
    return api.post('/readings/generate', payload)
  },
  remove(id) {
    return api.delete(`/readings/${id}`)
  },
}

export default readingApi
