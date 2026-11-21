import axios from '@/api/http'

const api = axios.create({
  baseURL: '/api',
  timeout: 180000, // 报告生成可能需要更长时间
})

export const learningReportApi = {
  /**
   * 获取报告列表
   * @param {Object} params - { skip, limit, subject_id, grade }
   */
  list(params) {
    return api.get('/learning-reports/list', { params })
  },

  /**
   * 获取报告详情
   * @param {number} id - 报告ID
   */
  get(id) {
    return api.get(`/learning-reports/${id}`)
  },

  /**
   * 删除报告
   * @param {number} id - 报告ID
   */
  delete(id) {
    return api.delete(`/learning-reports/${id}`)
  },
}

export default learningReportApi
