import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  timeout: 180000, // 报告生成可能需要更长时间
})

export const learningReportApi = {
  /**
   * 生成学习分析报告
   * @param {Object} data - { subject_id, grade, time_range_days, title }
   */
  generate(data) {
    return api.post('/learning-reports/generate', data)
  },

  /**
   * 获取报告列表
   * @param {Object} params - { skip, limit, subject_id }
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
