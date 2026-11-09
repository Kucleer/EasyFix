import { reactive } from 'vue'
import { questionApi } from '@/api/question'

const state = reactive({
  taxonomyVersion: '',
  modules: [],
  points: new Map(),
  nameHue: new Map(),
})
let loading

function hueForIndex(index, offset = 210) {
  return (index * 137.508 + offset) % 360
}

function hashHue(text) {
  let hash = 0
  for (const char of String(text || '')) hash = (Math.imul(hash, 31) + char.codePointAt(0)) >>> 0
  return hash % 360
}

function remember(point, moduleHue, hue) {
  const record = { ...point, moduleHue, hue }
  state.points.set(String(point.id), record)
  const name = String(point.name || '').trim()
  if (name && !state.nameHue.has(name)) state.nameHue.set(name, hue)
  return record
}

function rebuild(modules) {
  state.modules = modules || []
  state.points.clear()
  state.nameHue.clear()
  let index = 0
  for (const module of state.modules) {
    const moduleHue = hueForIndex(index++)
    remember({ ...module, level: 1 }, moduleHue, moduleHue)
    const children = module.children || []
    children.forEach((child, childIndex) => {
      remember({ ...child, level: 2, parent_name: module.name },
        moduleHue, (moduleHue + 16 + childIndex * 11) % 360)
    })
  }
}

/** 加载两级目录与颜色；同一页面内只请求一次，目录写入后调用 refresh。 */
export function loadKnowledgeColors(force = false) {
  if (loading) return loading
  if (!force && state.taxonomyVersion) return Promise.resolve(state)
  loading = questionApi.getKnowledgePointTree()
    .then(({ data }) => {
      state.taxonomyVersion = String(data.taxonomy_version || '')
      rebuild(data.items || [])
      return state
    })
    .catch(() => undefined)
    .finally(() => { loading = undefined })
  return loading
}

/** 目录写入后强制重新加载，避免颜色与名称残留旧值。 */
export function refreshKnowledgeColors() {
  state.taxonomyVersion = ''
  return loadKnowledgeColors(true)
}

/** 退出或切换学科时清空缓存，下次进入重新获取。 */
export function resetKnowledgeColors() {
  state.taxonomyVersion = ''
  state.modules = []
  state.points.clear()
  state.nameHue.clear()
}

export function knowledgePointById(id) {
  return state.points.get(String(id))
}

export function knowledgePointByName(name, subjectId) {
  const target = String(name || '').trim()
  if (!target) return undefined
  for (const record of state.points.values()) {
    if (record.name === target && (subjectId == null || String(record.subject_id) === String(subjectId))) return record
  }
  return undefined
}

/** 统一按 ID 取色；旧文本名称回退到名称映射或稳定散列。 */
export function knowledgeColor(point, subjectId) {
  let hue
  if (point && typeof point === 'object') {
    hue = state.points.get(String(point.id))?.hue
    if (hue === undefined && point.name) {
      hue = knowledgePointByName(point.name, point.subject_id ?? subjectId)?.hue
        ?? state.nameHue.get(String(point.name).trim())
    }
  } else {
    hue = knowledgePointByName(point, subjectId)?.hue ?? state.nameHue.get(String(point || '').trim())
  }
  if (hue === undefined) hue = hashHue(typeof point === 'object' ? point?.name : point)
  return {
    background: 'linear-gradient(115deg, hsl(' + hue + ' 85% 91%), hsl(' + ((hue + 32) % 360) + ' 90% 85%))',
    borderColor: 'hsl(' + hue + ' 55% 75%)',
    color: '#263247',
  }
}

export function knowledgePath(point) {
  if (!point) return ''
  const parent = point.parent_name || point.parentName || ''
  return parent ? parent + ' / ' + point.name : String(point.name || '')
}

export function primaryKnowledgePoint(points) {
  return (points || []).find(point => point.is_primary) || null
}

export function sortKnowledgePoints(points) {
  return [...(points || [])].sort((left, right) => {
    if (Boolean(left.is_primary) !== Boolean(right.is_primary)) return left.is_primary ? -1 : 1
    return (left.id || 0) - (right.id || 0)
  })
}
