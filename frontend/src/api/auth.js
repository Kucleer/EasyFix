import axios from '@/api/http'

const api = axios.create({
  baseURL: '/api',
  timeout: 30000,
})

// 登录与账号：跟密码有关的接口由网关处理，其余（我是谁、切换学生、管理员接口）由后端处理
export const authApi = {
  // 进入设置页前再验一次当前账号的密码
  verifyPassword(password) {
    return api.post('/auth/verify-password', { password })
  },

  /** 当前账号：登录名、名字、是否管理员、当前学生、本家庭全部学生 */
  me() {
    return api.get('/auth/me')
  },

  /** 切换到本家庭的另一个学生（重新签发登录 Cookie） */
  switchStudent(student_id) {
    return api.post('/auth/switch-student', { student_id })
  },

  /** 退出登录 */
  logout() {
    return api.post('/auth/logout', {})
  },

  /** 改自己的密码（新密码至少 10 位） */
  changePassword(old_password, new_password) {
    return api.post('/auth/change-password', { old_password, new_password })
  },

  // ---------------- 管理员 ----------------

  /** 全部家庭和学生 */
  adminUsers() {
    return api.get('/admin/users')
  },

  /** 开一个家庭：{ username, name, student_name, grade, semester } → { user_id, student_id } */
  adminCreateUser(data) {
    return api.post('/admin/users', data)
  },

  /** 改家庭名字、停用或启用：{ name?, disabled? } */
  adminUpdateUser(user_id, data) {
    return api.put(`/admin/users/${user_id}`, data)
  },

  /** 给家庭加学生：{ name, grade, semester } */
  adminAddStudent(user_id, data) {
    return api.post(`/admin/users/${user_id}/students`, data)
  },

  /** 改学生：{ name?, grade?, semester?, sort_order? } */
  adminUpdateStudent(student_id, data) {
    return api.put(`/admin/students/${student_id}`, data)
  },

  /** 删除学生（软删除；家庭至少留一个） */
  adminDeleteStudent(student_id) {
    return api.delete(`/admin/students/${student_id}`)
  },

  /** 给某个家庭生成新的随机密码，返回 { password }，只显示这一次 */
  adminSetPassword(user_id) {
    return api.post('/auth/admin/set-password', { user_id })
  },
}

export default authApi
