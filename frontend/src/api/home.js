import axios from '@/api/http'

const api = axios.create({
  baseURL: '/api',
  timeout: 60000,
})

// 首页接口
export const homeApi = {
  /**
   * 首页需要的全部数字：待核对、待批改、上次出卷、到期单词、连续天数、这一周、知识星空
   * 后端已有 60 秒缓存，前端不再用短时缓存，每次打开首页都拿最新的
   */
  get() {
    return api.get('/home', { cache: false })
  },
}

export default homeApi
