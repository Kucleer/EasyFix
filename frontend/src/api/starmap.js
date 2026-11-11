import axios from '@/api/http'

const api = axios.create({
  baseURL: '/api',
  timeout: 60000,
})

// 知识星空相关接口
export const starmapApi = {
  // 一科的星空：节点、连线、词汇星团、要播放的点亮考点（不走前端短时缓存，保证点亮时刻准确）
  get(subjectId) {
    return api.get('/starmap', { params: { subject_id: subjectId }, cache: false })
  },
  // 点亮时刻播放完后记下已经看过
  markSeen(subjectId, pointIds) {
    return api.post('/starmap/seen', { subject_id: subjectId, point_ids: pointIds })
  },
  adjustments(subjectId) {
    return api.get('/starmap/adjustments', { params: { subject_id: subjectId }, cache: false })
  },
  addAdjustment(pointId, kind) {
    return api.post('/starmap/adjustments', { knowledge_point_id: pointId, kind })
  },
  removeAdjustment(id) {
    return api.delete(`/starmap/adjustments/${id}`)
  },
  progress(subjectId) {
    return api.get('/starmap/progress', { params: { subject_id: subjectId }, cache: false })
  },
  saveProgress(subjectId, sectionNo) {
    return api.put('/starmap/progress', { section_no: sectionNo }, { params: { subject_id: subjectId } })
  },
  subjects() {
    return api.get('/subjects')
  },
}

// 星空里出现的两科
export const STARMAP_SUBJECTS = ['数学', '英语']

// 按名称找到两科的编号：[{ id, name }]
export async function loadStarmapSubjects() {
  const { data } = await starmapApi.subjects()
  const list = Array.isArray(data) ? data : (data.items || [])
  return STARMAP_SUBJECTS.map(name => list.find(s => s.name === name)).filter(Boolean).map(s => ({ id: s.id, name: s.name }))
}
