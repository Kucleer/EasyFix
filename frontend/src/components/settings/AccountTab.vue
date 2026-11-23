<template>
  <!-- 设置 · 账号（只有管理员看得到）：开家庭、加学生、改学生、重置密码、停用 -->
  <div class="account-tab">
    <div class="toolbar">
      <el-button type="primary" @click="open_create">新建家庭</el-button>
    </div>

    <el-table v-loading="loading" :data="users" border class="account-table" empty-text="还没有家庭">
      <el-table-column prop="username" label="登录名" min-width="110" />
      <el-table-column prop="name" label="家庭" min-width="100" />
      <el-table-column label="学生" min-width="220">
        <template #default="{ row }">
          <div class="students">
            <el-tag v-for="s in row.students" :key="s.id" class="student-tag" closable :disable-transitions="true"
                    @click="open_student(row, s)" @close="remove_student(s)">
              {{ s.name }}<span v-if="s.grade" class="grade">（{{ grade_label(s.grade) }}）</span>
            </el-tag>
            <el-button link type="primary" @click="open_student(row, null)">加学生</el-button>
          </div>
        </template>
      </el-table-column>
      <el-table-column label="状态" width="80">
        <template #default="{ row }">
          <el-tag :type="row.disabled ? 'info' : 'success'">{{ row.disabled ? '停用' : '正常' }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="last_login_at" label="最近登录" min-width="150">
        <template #default="{ row }">{{ row.last_login_at || '—' }}</template>
      </el-table-column>
      <el-table-column label="操作" min-width="170">
        <template #default="{ row }">
          <template v-if="!row.is_admin">
            <el-button link type="primary" @click="reset_password(row)">重置密码</el-button>
            <el-button link :type="row.disabled ? 'primary' : 'danger'" @click="toggle_disabled(row)">
              {{ row.disabled ? '启用' : '停用' }}
            </el-button>
          </template>
          <span v-else class="muted">管理员（自己的密码在"我的账号"里改）</span>
        </template>
      </el-table-column>
    </el-table>

    <!-- 新建家庭 -->
    <el-dialog v-model="create_visible" title="新建家庭" :width="is_mobile ? '92%' : '440px'" append-to-body>
      <el-form :model="create_form" label-width="90px">
        <el-form-item label="登录名"><el-input v-model="create_form.username" placeholder="小写字母、数字、下划线，3–20 位" /></el-form-item>
        <el-form-item label="家庭名字"><el-input v-model="create_form.name" placeholder="例如：王家" /></el-form-item>
        <el-form-item label="学生名字"><el-input v-model="create_form.student_name" /></el-form-item>
        <el-form-item label="年级">
          <el-select v-model="create_form.grade" clearable style="width: 100%">
            <el-option v-for="g in GRADE_OPTIONS" :key="g.value" :label="g.label" :value="g.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="学期">
          <el-select v-model="create_form.semester" clearable style="width: 100%">
            <el-option v-for="s in SEMESTER_OPTIONS" :key="s.value" :label="s.label" :value="s.value" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="create_visible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="create_family">建好并生成密码</el-button>
      </template>
    </el-dialog>

    <!-- 加学生 / 改学生 -->
    <el-dialog v-model="student_visible" :title="student_form.id ? '修改学生' : '加学生'" :width="is_mobile ? '92%' : '400px'" append-to-body>
      <el-form :model="student_form" label-width="70px">
        <el-form-item label="名字"><el-input v-model="student_form.name" /></el-form-item>
        <el-form-item label="年级">
          <el-select v-model="student_form.grade" clearable style="width: 100%">
            <el-option v-for="g in GRADE_OPTIONS" :key="g.value" :label="g.label" :value="g.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="学期">
          <el-select v-model="student_form.semester" clearable style="width: 100%">
            <el-option v-for="s in SEMESTER_OPTIONS" :key="s.value" :label="s.label" :value="s.value" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="student_visible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="save_student">保存</el-button>
      </template>
    </el-dialog>

    <!-- 新密码只显示这一次 -->
    <el-dialog v-model="password_visible" title="新密码" :width="is_mobile ? '92%' : '400px'" append-to-body
               :close-on-click-modal="false">
      <p>登录名：<b>{{ password_info.username }}</b></p>
      <p>密码：<b class="password">{{ password_info.password }}</b></p>
      <el-alert type="warning" :closable="false" title="请复制发给对方，关掉后不再显示。" />
      <template #footer>
        <el-button type="primary" @click="password_visible = false">我已记下</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { authApi } from '@/api/auth'
import { use_is_mobile } from '@/composables/useIsMobile'
import { GRADE_OPTIONS, SEMESTER_OPTIONS } from './settingsModel'

const is_mobile = use_is_mobile()
const users = ref([])
const loading = ref(false)
const saving = ref(false)
const create_visible = ref(false)
const create_form = reactive({ username: '', name: '', student_name: '', grade: null, semester: null })
const student_visible = ref(false)
const student_form = reactive({ id: null, user_id: null, name: '', grade: null, semester: null })
const password_visible = ref(false)
const password_info = reactive({ username: '', password: '' })

/** 接口返回的错误文字；没有就用默认说法 */
function error_text(error, fallback) {
  return error?.response?.data?.detail || fallback
}

/** 年级数字转成"六年级""初一"这样的文字 */
function grade_label(grade) {
  return GRADE_OPTIONS.find(g => g.value === grade)?.label || ''
}

/** 读全部家庭 */
async function load() {
  loading.value = true
  try {
    users.value = (await authApi.adminUsers()).data
  } catch (error) {
    ElMessage.error(error_text(error, '读取账号列表失败'))
  } finally {
    loading.value = false
  }
}

/** 打开"新建家庭"弹窗，表单清空 */
function open_create() {
  Object.assign(create_form, { username: '', name: '', student_name: '', grade: null, semester: null })
  create_visible.value = true
}

/** 显示一次新密码 */
function show_password(username, password) {
  Object.assign(password_info, { username, password })
  password_visible.value = true
}

/** 新建家庭：先建账号和学生，再让网关生成初始密码，显示一次 */
async function create_family() {
  saving.value = true
  try {
    const { data } = await authApi.adminCreateUser({ ...create_form, username: create_form.username.trim() })
    const { data: secret } = await authApi.adminSetPassword(data.user_id)
    create_visible.value = false
    show_password(create_form.username.trim(), secret.password)
    await load()
  } catch (error) {
    ElMessage.error(error_text(error, '新建失败'))
  } finally {
    saving.value = false
  }
}

/** 打开"加学生 / 改学生"弹窗；student 为空表示加学生 */
function open_student(user, student) {
  Object.assign(student_form, student
    ? { id: student.id, user_id: user.id, name: student.name, grade: student.grade, semester: student.semester }
    : { id: null, user_id: user.id, name: '', grade: null, semester: null })
  student_visible.value = true
}

/** 保存学生 */
async function save_student() {
  saving.value = true
  const data = { name: student_form.name, grade: student_form.grade, semester: student_form.semester }
  try {
    if (student_form.id) await authApi.adminUpdateStudent(student_form.id, data)
    else await authApi.adminAddStudent(student_form.user_id, data)
    student_visible.value = false
    await load()
  } catch (error) {
    ElMessage.error(error_text(error, '保存失败'))
  } finally {
    saving.value = false
  }
}

/** 删除学生（确认后软删除；家庭至少留一个，后端会拦） */
async function remove_student(student) {
  try {
    await ElMessageBox.confirm(`删除学生"${student.name}"？这个学生的错题等记录会保留在库里，但这个家庭看不到了。`, '删除学生',
      { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' })
  } catch {
    return
  }
  try {
    await authApi.adminDeleteStudent(student.id)
    await load()
  } catch (error) {
    ElMessage.error(error_text(error, '删除失败'))
  }
}

/** 重置密码：生成新的随机密码并显示一次，对方的旧登录全部失效 */
async function reset_password(user) {
  try {
    await ElMessageBox.confirm(`给"${user.name}"生成新密码？对方正在用的登录会失效。`, '重置密码',
      { type: 'warning', confirmButtonText: '重置', cancelButtonText: '取消' })
  } catch {
    return
  }
  try {
    const { data } = await authApi.adminSetPassword(user.id)
    show_password(user.username, data.password)
  } catch (error) {
    ElMessage.error(error_text(error, '重置失败'))
  }
}

/** 停用或启用家庭；停用后对方马上退出登录 */
async function toggle_disabled(user) {
  try {
    await authApi.adminUpdateUser(user.id, { disabled: !user.disabled })
    await load()
  } catch (error) {
    ElMessage.error(error_text(error, '操作失败'))
  }
}

onMounted(load)
</script>

<style scoped>
.toolbar { margin-bottom: 12px; }
.students { display: flex; flex-wrap: wrap; align-items: center; gap: 6px; }
.student-tag { cursor: pointer; }
.grade { color: var(--muted); }
.muted { color: var(--muted); font-size: 12px; }
.password { font-family: ui-monospace, Consolas, monospace; font-size: 18px; letter-spacing: 1px; }
</style>
