import api from './question.js'

export const motivationApi = {
  // 积分
  getBalance() {
    return api.get('/stars/balance')
  },
  getRecords(params) {
    return api.get('/stars/records', { params })
  },
  getActions() {
    return api.get('/stars/actions')
  },
  createAction(data) {
    return api.post('/stars/actions', data)
  },
  updateAction(id, data) {
    return api.put(`/stars/actions/${id}`, data)
  },
  deleteAction(id) {
    return api.delete(`/stars/actions/${id}`)
  },

  // 成就
  getAchievements() {
    return api.get('/achievements')
  },
  getAchievementProgress() {
    return api.get('/achievements/progress')
  },
  createAchievement(data) {
    return api.post('/achievements', data)
  },
  updateAchievement(id, data) {
    return api.put(`/achievements/${id}`, data)
  },
  deleteAchievement(id) {
    return api.delete(`/achievements/${id}`)
  },

  // 奖励
  getRewards() {
    return api.get('/rewards')
  },
  createReward(data) {
    return api.post('/rewards', data)
  },
  updateReward(id, data) {
    return api.put(`/rewards/${id}`, data)
  },
  deleteReward(id) {
    return api.delete(`/rewards/${id}`)
  },
  redeemReward(id) {
    return api.post(`/rewards/${id}/redeem`)
  },
  getRedemptions() {
    return api.get('/rewards/redemptions')
  },

  // 概览
  getOverview() {
    return api.get('/motivation/overview')
  },

  // 积分调整
  adjustStars(data) {
    return api.post('/stars/adjust', data)
  },

  // 单词复习正确率触发
  triggerWordAccuracy(data) {
    return api.post('/motivation/trigger/review_word_accuracy', data)
  }
}