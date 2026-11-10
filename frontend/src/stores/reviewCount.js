import { defineStore } from 'pinia'
import { reviewApi } from '@/api/paper'

/** 待核对题目数量，导航和首页共用 */
export const useReviewCountStore = defineStore('reviewCount', {
  state: () => ({
    pending: 0,
  }),

  actions: {
    // 刷新数量；失败时保持原值，不提示错误
    async refresh() {
      try {
        const { data } = await reviewApi.count()
        this.pending = Number(data?.pending) || 0
      } catch (e) {
        console.error('刷新待核对数量失败:', e)
      }
    },
  },
})
