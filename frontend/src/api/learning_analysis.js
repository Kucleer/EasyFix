import api from './question.js'

// 学习分析API
export const learningAnalysisApi = {
  // 获取完整分析数据
  getFullStats(params) {
    return api.get('/stats/analysis/full', { params })
  },

  // 获取知识点聚合，level=1 默认，二级需带 parent_id
  getKnowledgeStats(params) {
    return api.get('/stats/knowledge-points', { params })
  },

  // 获取LLM分析
  getLlmAnalysis(params) {
    return api.post('/stats/analysis/llm', {}, { params })
  },
}

export default learningAnalysisApi