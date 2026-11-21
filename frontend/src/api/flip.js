import axios from '@/api/http'

const api = axios.create({
  baseURL: '/api',
  timeout: 60000,
})

// 翻一翻接口
export const flipApi = {
  /**
   * 今天这一组还没翻的卡片和进度：{ total, done, cards }
   * 每翻一张进度都会变，不用短时缓存
   */
  today() {
    return api.get('/flip/today', { cache: false })
  },

  /**
   * 记一张卡片的结果，返回今天的进度 { done, total }
   * @param {number} question_id - 题目编号
   * @param {'remember'|'forget'} result - 我记得 / 我忘了
   */
  record(question_id, result) {
    return api.post(`/flip/${question_id}`, { result })
  },
}

export default flipApi
