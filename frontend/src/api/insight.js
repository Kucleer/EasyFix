import axios from '@/api/http'

const api = axios.create({
  baseURL: '/api',
  timeout: 60000,
})

// 学情页接口（考点那一半用 starmap.js 里的 starmapApi）
export const insightApi = {
  /**
   * 单词学情：正确率偏低的单词（最多 20 个）和每天的复习次数
   * 返回 { low_accuracy_words: [{ word, accuracy }], frequency: [{ date, count }] }
   * 前端沿用统计接口的 30 秒短时缓存，来回切换标签时不重复请求
   */
  words() {
    return api.get('/stats/words')
  },
}

export default insightApi
