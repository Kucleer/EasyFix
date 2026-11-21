import axios from '@/api/http'

const api = axios.create({
  baseURL: '/api',
  timeout: 120000,
})

// 考点卷特有的接口（都不走前端短时缓存）；详情、生成 PDF、提交批改用 practice.js，上传用 upload.js
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
  // 批改识别预批：读一张照片（传照片序号），返回这页的识别文字；一页最慢约 120 秒
  recognizePage(id, index, signal) {
    return api.post(`/practice-sets/${id}/recognize/page`, { index }, { timeout: 150000, signal })
  },
  // 批改识别预批：传各页识别文字，服务端取题目和答案、调一次模型，返回每题的预批结果
  recognizeJudge(id, pages, signal) {
    return api.post(`/practice-sets/${id}/recognize/judge`, { pages }, { timeout: 150000, signal })
  },
}
