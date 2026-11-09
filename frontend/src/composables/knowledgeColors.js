import { reactive } from 'vue'
import { questionApi } from '@/api/question'

const colors = reactive(new Map())
const subjectsByName = reactive(new Map())
let loading
export function loadKnowledgeColors() {
  if (loading) return loading
  loading = questionApi.listKnowledgePoints().then(({ data }) => {
    const bySubject = new Map()
    for (const point of [...data].sort((a, b) => a.id - b.id)) {
      const subject = String(point.subject_id)
      if (!bySubject.has(subject)) bySubject.set(subject, new Map())
      bySubject.get(subject).set(point.name.trim(), true)
      if (!subjectsByName.has(point.name.trim())) subjectsByName.set(point.name.trim(), new Set())
      subjectsByName.get(point.name.trim()).add(subject)
    }
    bySubject.forEach((names, subject) => {
      let index = 0
      names.forEach((_, name) => colors.set(subject + ':' + name, (index++ * 137.508 + 215) % 360))
    })
  }).catch(() => { loading = undefined })
  return loading
}
export function knowledgeColor(name, subjectId) {
  const normalized = String(name || '').trim()
  const known = subjectsByName.get(normalized)
  const subject = subjectId == null && known?.size === 1 ? [...known][0] : String(subjectId ?? 'unknown')
  let hash = 0
  for (const char of normalized) hash = (Math.imul(hash, 31) + char.codePointAt(0)) >>> 0
  const hue = colors.get(subject + ':' + normalized) ?? hash % 360
  return { background: 'linear-gradient(115deg, hsl(' + hue + ' 85% 91%), hsl(' + ((hue + 32) % 360) + ' 90% 85%))', borderColor: 'hsl(' + hue + ' 55% 75%)', color: '#263247' }
}
