import axios from '@/api/http'

const api = axios.create({
  baseURL: '/api',
  timeout: 60000,
})

// 周报相关接口
export const weeklyReportApi = {
  /**
   * 各期简表（新的在前）
   * 返回 { items: [{ id, number, monday, sunday, status }], due }；due 为真表示最近一期还没做完
   */
  list() {
    return api.get('/weekly-reports')
  },

  /**
   * 一期的完整内容
   * @param {number} id - 周报编号
   */
  get(id) {
    return api.get(`/weekly-reports/${id}`)
  },

  /**
   * 把最近一期推进一步，返回 { id, status, busy }
   */
  advance() {
    // 一步里可能要调模型写文字，最慢约 120 秒，页面多等一点（和 scanApi.advance 一样）
    return api.post('/weekly-reports/advance', null, { timeout: 150000 })
  },
}

export default weeklyReportApi
