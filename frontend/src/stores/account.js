import { defineStore } from 'pinia'
import { authApi } from '@/api/auth'

/**
 * 当前登录的账号和学生。
 * 学生只由登录 Cookie 决定，页面请求不用带学生编号；切换学生后整页刷新，
 * 这样请求缓存（http.js）和各个 store 里存着的上一个学生的数据都会清掉。
 */
export const useAccountStore = defineStore('account', {
  state: () => ({
    username: '',
    name: '',
    isAdmin: false,
    student: null,      // { id, name }
    students: [],       // 本家庭全部学生 [{ id, name }]
    loaded: false,
  }),

  actions: {
    /** 读当前账号；已经读过就不再请求（force 为真时重读） */
    async load(force = false) {
      if (this.loaded && !force) return
      try {
        const { data } = await authApi.me()
        this.username = data.username || ''
        this.name = data.name || ''
        this.isAdmin = data.is_admin === true
        this.student = data.student || null
        this.students = data.students || []
        this.loaded = true
      } catch (e) {
        console.error('读取当前账号失败:', e)
      }
    },

    /** 切换学生：成功后整页刷新 */
    async switchTo(student_id) {
      if (this.student && this.student.id === student_id) return
      await authApi.switchStudent(student_id)
      window.location.reload()
    },

    /** 退出登录：回到登录页 */
    async logout() {
      try {
        await authApi.logout()
      } finally {
        window.location.replace('/login')
      }
    },
  },
})
