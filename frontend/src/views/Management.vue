<template>
  <div class="management">
    <!-- 访问密码验证 -->
    <el-dialog v-model="showPasswordDialog" title="请输入访问密码" width="400px" :close-on-click-modal="false" :show-close="false">
      <el-form>
        <el-form-item label="访问密码">
          <el-input v-model="password" type="password" placeholder="请输入访问密码" @keyup.enter="verifyPassword" show-password />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button type="primary" @click="verifyPassword" :loading="verifying">验证</el-button>
      </template>
    </el-dialog>

    <el-card v-if="isVerified">
      <template #header>
        <div class="card-header">
          <span>管理中心</span>
        </div>
      </template>

      <el-tabs v-model="activeTab">
        <!-- 学科管理 -->
        <el-tab-pane label="学科管理" name="subjects">
          <div class="tab-content">
            <div class="action-bar">
              <el-button type="primary" @click="showSubjectDialog = true">
                <el-icon><Plus /></el-icon>
                新增学科
              </el-button>
            </div>
            <el-table :data="subjects" stripe style="width: 100%; margin-top: 15px">
              <el-table-column prop="id" label="ID" width="80" />
              <el-table-column prop="name" label="学科名称" />
              <el-table-column label="操作" width="120">
                <template #default="{ row }">
                  <el-button link type="danger" size="small" @click="deleteSubject(row)">删除</el-button>
                </template>
              </el-table-column>
            </el-table>
          </div>
        </el-tab-pane>

        <!-- 标签管理 -->
        <el-tab-pane label="标签管理" name="tags">
          <div class="tab-content">
            <div class="action-bar">
              <el-button type="primary" @click="showTagDialog = true">
                <el-icon><Plus /></el-icon>
                新增标签
              </el-button>
            </div>
            <el-table :data="tags" stripe style="width: 100%; margin-top: 15px">
              <el-table-column prop="id" label="ID" width="80" />
              <el-table-column prop="name" label="标签名称" />
              <el-table-column prop="color" label="颜色" width="120">
                <template #default="{ row }">
                  <el-tag :style="{ backgroundColor: row.color, color: '#fff' }">{{ row.color || '默认' }}</el-tag>
                </template>
              </el-table-column>
              <el-table-column label="操作" width="120">
                <template #default="{ row }">
                  <el-button link type="danger" size="small" @click="deleteTag(row)">删除</el-button>
                </template>
              </el-table-column>
            </el-table>
          </div>
        </el-tab-pane>

        <!-- 错误类型管理 -->
        <el-tab-pane label="错误类型管理" name="errorTypes">
          <div class="tab-content">
            <div class="action-bar">
              <el-button type="primary" @click="showErrorTypeDialog = true">
                <el-icon><Plus /></el-icon>
                新增错误类型
              </el-button>
            </div>
            <el-table :data="errorTypes" stripe style="width: 100%; margin-top: 15px">
              <el-table-column prop="id" label="ID" width="80" />
              <el-table-column prop="name" label="类型名称" />
              <el-table-column label="操作" width="120">
                <template #default="{ row }">
                  <el-button link type="danger" size="small" @click="deleteErrorType(row)">删除</el-button>
                </template>
              </el-table-column>
            </el-table>
          </div>
        </el-tab-pane>

        <!-- 知识点管理 -->
        <el-tab-pane label="知识点管理" name="knowledgePoints">
          <div class="tab-content">
            <div class="action-bar">
              <el-button type="primary" @click="showKnowledgeDialog = true">
                <el-icon><Plus /></el-icon>
                新增知识点
              </el-button>
            </div>
            <div class="filters">
              <el-select v-model="kpFilters.subject_id" placeholder="选择学科" clearable @change="fetchKnowledgePoints" style="width: 150px">
                <el-option v-for="s in subjects" :key="s.id" :label="s.name" :value="s.id" />
              </el-select>
              <el-select v-model="kpFilters.grade" placeholder="年级" clearable @change="fetchKnowledgePoints" style="width: 120px">
                <el-option v-for="g in gradeOptions" :key="g.value" :label="g.label" :value="g.value" />
              </el-select>
              <el-select v-model="kpFilters.semester" placeholder="学期" clearable @change="fetchKnowledgePoints" style="width: 100px">
                <el-option label="上学期" :value="1" />
                <el-option label="下学期" :value="2" />
              </el-select>
            </div>
            <el-table :data="knowledgePoints" stripe style="width: 100%; margin-top: 15px">
              <el-table-column prop="id" label="ID" width="80" />
              <el-table-column prop="name" label="知识点名称" />
              <el-table-column prop="subject_name" label="学科" width="100" />
              <el-table-column prop="grade" label="年级" width="80">
                <template #default="{ row }">
                  {{ getGradeLabel(row.grade) }}
                </template>
              </el-table-column>
              <el-table-column prop="semester" label="学期" width="80">
                <template #default="{ row }">
                  {{ row.semester === 1 ? '上学期' : '下学期' }}
                </template>
              </el-table-column>
              <el-table-column label="操作" width="120">
                <template #default="{ row }">
                  <el-button link type="danger" size="small" @click="deleteKnowledgePoint(row)">删除</el-button>
                </template>
              </el-table-column>
            </el-table>
          </div>
        </el-tab-pane>

        <!-- 错题本管理 -->
        <el-tab-pane label="错题本管理" name="errorBooks">
          <div class="tab-content">
            <div class="action-bar">
              <el-button type="primary" @click="showErrorBookDialog = true">
                <el-icon><Plus /></el-icon>
                新增错题本
              </el-button>
            </div>
            <el-table :data="errorBooks" stripe style="width: 100%; margin-top: 15px">
              <el-table-column prop="id" label="ID" width="80" />
              <el-table-column prop="name" label="错题本名称" />
              <el-table-column prop="subject_name" label="学科" width="100" />
              <el-table-column prop="description" label="描述" />
              <el-table-column label="操作" width="180">
                <template #default="{ row }">
                  <el-button link type="primary" size="small" @click="editErrorBook(row)">编辑</el-button>
                  <el-button link type="danger" size="small" @click="deleteErrorBook(row)">删除</el-button>
                </template>
              </el-table-column>
            </el-table>
          </div>
        </el-tab-pane>
      </el-tabs>
    </el-card>

    <!-- 新增学科弹窗 -->
    <el-dialog v-model="showSubjectDialog" title="新增学科" width="400px">
      <el-form :model="subjectForm" label-width="80px">
        <el-form-item label="学科名称" required>
          <el-input v-model="subjectForm.name" placeholder="请输入学科名称" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showSubjectDialog = false">取消</el-button>
        <el-button type="primary" @click="createSubject">保存</el-button>
      </template>
    </el-dialog>

    <!-- 新增标签弹窗 -->
    <el-dialog v-model="showTagDialog" title="新增标签" width="400px">
      <el-form :model="tagForm" label-width="80px">
        <el-form-item label="标签名称" required>
          <el-input v-model="tagForm.name" placeholder="请输入标签名称" />
        </el-form-item>
        <el-form-item label="颜色">
          <el-color-picker v-model="tagForm.color" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showTagDialog = false">取消</el-button>
        <el-button type="primary" @click="createTag">保存</el-button>
      </template>
    </el-dialog>

    <!-- 新增错误类型弹窗 -->
    <el-dialog v-model="showErrorTypeDialog" title="新增错误类型" width="400px">
      <el-form :model="errorTypeForm" label-width="80px">
        <el-form-item label="类型名称" required>
          <el-input v-model="errorTypeForm.name" placeholder="请输入错误类型名称" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showErrorTypeDialog = false">取消</el-button>
        <el-button type="primary" @click="createErrorType">保存</el-button>
      </template>
    </el-dialog>

    <!-- 新增知识点弹窗 -->
    <el-dialog v-model="showKnowledgeDialog" title="新增知识点" width="500px">
      <el-form :model="knowledgeForm" label-width="100px">
        <el-form-item label="知识点名称" required>
          <el-input v-model="knowledgeForm.name" placeholder="请输入知识点名称" />
        </el-form-item>
        <el-form-item label="学科" required>
          <el-select v-model="knowledgeForm.subject_id" placeholder="选择学科" style="width: 100%">
            <el-option v-for="s in subjects" :key="s.id" :label="s.name" :value="s.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="年级">
          <el-select v-model="knowledgeForm.grade" placeholder="选择年级" clearable style="width: 100%">
            <el-option v-for="g in gradeOptions" :key="g.value" :label="g.label" :value="g.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="学期">
          <el-select v-model="knowledgeForm.semester" placeholder="选择学期" clearable style="width: 100%">
            <el-option label="上学期" :value="1" />
            <el-option label="下学期" :value="2" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showKnowledgeDialog = false">取消</el-button>
        <el-button type="primary" @click="createKnowledgePoint">保存</el-button>
      </template>
    </el-dialog>

    <!-- 新增/编辑错题本弹窗 -->
    <el-dialog v-model="showErrorBookDialog" :title="editErrorBookData ? '编辑错题本' : '新增错题本'" width="500px">
      <el-form :model="errorBookForm" label-width="100px">
        <el-form-item label="错题本名称" required>
          <el-input v-model="errorBookForm.name" placeholder="请输入错题本名称" />
        </el-form-item>
        <el-form-item label="学科" required>
          <el-select v-model="errorBookForm.subject_id" placeholder="选择学科" style="width: 100%">
            <el-option v-for="s in subjects" :key="s.id" :label="s.name" :value="s.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="errorBookForm.description" type="textarea" :rows="3" placeholder="请输入描述" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showErrorBookDialog = false">取消</el-button>
        <el-button type="primary" @click="createOrUpdateErrorBook">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { questionApi } from '@/api/question'
import axios from 'axios'

const activeTab = ref('subjects')
const showPasswordDialog = ref(true)
const isVerified = ref(false)
const password = ref('')
const verifying = ref(false)

// 年级选项
const gradeOptions = [
  { label: '一年级', value: 1 },
  { label: '二年级', value: 2 },
  { label: '三年级', value: 3 },
  { label: '四年级', value: 4 },
  { label: '五年级', value: 5 },
  { label: '六年级', value: 6 },
  { label: '初一', value: 7 },
  { label: '初二', value: 8 },
  { label: '初三', value: 9 },
  { label: '高一', value: 10 },
  { label: '高二', value: 11 },
  { label: '高三', value: 12 },
]

const getGradeLabel = (grade) => {
  if (!grade) return '未设置'
  const g = gradeOptions.find(o => o.value === grade)
  return g ? g.label : `${grade}年级`
}

// 学科
const subjects = ref([])
const showSubjectDialog = ref(false)
const subjectForm = reactive({ name: '' })

// 标签
const tags = ref([])
const showTagDialog = ref(false)
const tagForm = reactive({ name: '', color: '#409eff' })

// 错误类型
const errorTypes = ref([])
const showErrorTypeDialog = ref(false)
const errorTypeForm = reactive({ name: '' })

// 知识点
const knowledgePoints = ref([])
const kpFilters = reactive({ subject_id: null, grade: null, semester: null })
const showKnowledgeDialog = ref(false)
const knowledgeForm = reactive({ name: '', subject_id: null, grade: null, semester: null })

// 错题本
const errorBooks = ref([])
const showErrorBookDialog = ref(false)
const editErrorBookData = ref(null)
const errorBookForm = reactive({ name: '', subject_id: null, description: '' })

// 获取学科列表
const fetchSubjects = async () => {
  try {
    const { data } = await questionApi.listSubjects()
    subjects.value = Array.isArray(data) ? data : (data.items || [])
  } catch (e) {
    console.error('获取学科失败:', e)
  }
}

// 创建学科
const createSubject = async () => {
  if (!subjectForm.name.trim()) {
    ElMessage.warning('请输入学科名称')
    return
  }
  try {
    await questionApi.createSubject(subjectForm.name)
    ElMessage.success('创建成功')
    showSubjectDialog.value = false
    subjectForm.name = ''
    fetchSubjects()
  } catch (e) {
    ElMessage.error('创建失败')
  }
}

// 删除学科
const deleteSubject = async (row) => {
  try {
    await ElMessageBox.confirm('确定要删除该学科吗？', '删除确认', { type: 'warning' })
    await questionApi.deleteSubject(row.id)
    ElMessage.success('删除成功')
    fetchSubjects()
  } catch (e) {
    if (e !== 'cancel') ElMessage.error('删除失败')
  }
}

// 获取标签列表
const fetchTags = async () => {
  try {
    const { data } = await questionApi.listTags()
    tags.value = Array.isArray(data) ? data : (data.items || [])
  } catch (e) {
    console.error('获取标签失败:', e)
  }
}

// 创建标签
const createTag = async () => {
  if (!tagForm.name.trim()) {
    ElMessage.warning('请输入标签名称')
    return
  }
  try {
    await questionApi.createTag(tagForm.name, tagForm.color)
    ElMessage.success('创建成功')
    showTagDialog.value = false
    tagForm.name = ''
    tagForm.color = '#409eff'
    fetchTags()
  } catch (e) {
    ElMessage.error('创建失败')
  }
}

// 删除标签
const deleteTag = async (row) => {
  try {
    await ElMessageBox.confirm('确定要删除该标签吗？', '删除确认', { type: 'warning' })
    await questionApi.deleteTag(row.id)
    ElMessage.success('删除成功')
    fetchTags()
  } catch (e) {
    if (e !== 'cancel') ElMessage.error('删除失败')
  }
}

// 获取错误类型列表
const errorTypeList = ref([
  { id: 1, name: '计算' },
  { id: 2, name: '概念' },
  { id: 3, name: '审题' },
  { id: 4, name: '其他' },
])

const fetchErrorTypes = async () => {
  errorTypes.value = errorTypeList.value
}

// 创建错误类型（预定义，不允许自定义）
const createErrorType = async () => {
  ElMessage.info('错误类型为系统预定义，不可添加')
}

// 删除错误类型（预定义，不允许删除）
const deleteErrorType = async (row) => {
  ElMessage.info('错误类型为系统预定义，不可删除')
}

// 获取知识点列表
const fetchKnowledgePoints = async () => {
  try {
    const params = {}
    if (kpFilters.subject_id) params.subject_id = kpFilters.subject_id
    if (kpFilters.grade) params.grade = kpFilters.grade
    if (kpFilters.semester) params.semester = kpFilters.semester
    const { data } = await questionApi.listKnowledgePoints(params)
    knowledgePoints.value = Array.isArray(data) ? data : []
  } catch (e) {
    console.error('获取知识点失败:', e)
  }
}

// 创建知识点
const createKnowledgePoint = async () => {
  if (!knowledgeForm.name.trim()) {
    ElMessage.warning('请输入知识点名称')
    return
  }
  if (!knowledgeForm.subject_id) {
    ElMessage.warning('请选择学科')
    return
  }
  try {
    await questionApi.createKnowledgePoint({
      name: knowledgeForm.name,
      subject_id: knowledgeForm.subject_id,
      grade: knowledgeForm.grade,
      semester: knowledgeForm.semester,
    })
    ElMessage.success('创建成功')
    showKnowledgeDialog.value = false
    knowledgeForm.name = ''
    knowledgeForm.subject_id = null
    knowledgeForm.grade = null
    knowledgeForm.semester = null
    fetchKnowledgePoints()
  } catch (e) {
    ElMessage.error('创建失败')
  }
}

// 删除知识点
const deleteKnowledgePoint = async (row) => {
  try {
    await ElMessageBox.confirm('确定要删除该知识点吗？', '删除确认', { type: 'warning' })
    await questionApi.deleteKnowledgePoint(row.id)
    ElMessage.success('删除成功')
    fetchKnowledgePoints()
  } catch (e) {
    if (e !== 'cancel') ElMessage.error('删除失败')
  }
}

// 获取错题本列表
const fetchErrorBooks = async () => {
  try {
    const { data } = await questionApi.listErrorBooks()
    errorBooks.value = data.items || []
    // 如果有subject_id，获取学科名称
    if (errorBooks.value.length > 0) {
      await fetchSubjects()
      errorBooks.value = errorBooks.value.map(eb => ({
        ...eb,
        subject_name: subjects.value.find(s => s.id === eb.subject_id)?.name || ''
      }))
    }
  } catch (e) {
    console.error('获取错题本失败:', e)
  }
}

// 创建或更新错题本
const createOrUpdateErrorBook = async () => {
  if (!errorBookForm.name.trim()) {
    ElMessage.warning('请输入错题本名称')
    return
  }
  if (!errorBookForm.subject_id) {
    ElMessage.warning('请选择学科')
    return
  }
  try {
    if (editErrorBookData.value) {
      await questionApi.updateErrorBook(editErrorBookData.value.id, errorBookForm)
      ElMessage.success('更新成功')
    } else {
      await questionApi.createErrorBook(errorBookForm)
      ElMessage.success('创建成功')
    }
    showErrorBookDialog.value = false
    editErrorBookData.value = null
    errorBookForm.name = ''
    errorBookForm.subject_id = null
    errorBookForm.description = ''
    fetchErrorBooks()
  } catch (e) {
    ElMessage.error('保存失败')
  }
}

// 编辑错题本
const editErrorBook = (row) => {
  editErrorBookData.value = row
  errorBookForm.name = row.name
  errorBookForm.subject_id = row.subject_id
  errorBookForm.description = row.description || ''
  showErrorBookDialog.value = true
}

// 删除错题本
const deleteErrorBook = async (row) => {
  try {
    await ElMessageBox.confirm('确定要删除该错题本吗？', '删除确认', { type: 'warning' })
    await questionApi.deleteErrorBook(row.id)
    ElMessage.success('删除成功')
    fetchErrorBooks()
  } catch (e) {
    if (e !== 'cancel') ElMessage.error('删除失败')
  }
}

const verifyPassword = async () => {
  if (!password.value) {
    ElMessage.warning('请输入密码')
    return
  }
  verifying.value = true
  try {
    await axios.post('/api/auth/verify-password', { password: password.value })
    isVerified.value = true
    showPasswordDialog.value = false
    fetchAll()
  } catch (error) {
    ElMessage.error('密码错误')
    password.value = ''
  } finally {
    verifying.value = false
  }
}

const fetchAll = () => {
  fetchSubjects()
  fetchTags()
  fetchErrorTypes()
  fetchKnowledgePoints()
  fetchErrorBooks()
}

onMounted(() => {
  // 先显示密码对话框
})
</script>

<style scoped>
.management {
  max-width: 1200px;
  margin: 0 auto;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.tab-content {
  padding: 10px 0;
}

.action-bar {
  margin-bottom: 10px;
}

.filters {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  margin-bottom: 15px;
}
</style>
