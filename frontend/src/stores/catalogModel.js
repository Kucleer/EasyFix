/**
 * 目录数据（学科、标签、知识点树）的纯函数。
 * 不依赖 Vue 和接口层，方便用 node --test 直接测试；store 在 catalog.js。
 */

// 知识星空和出卷页只用这两科，按这个顺序显示
export const STARMAP_SUBJECTS = ['数学', '英语']

/** 把接口返回统一成数组：数组原样返回，{ items } 取 items，其余返回空数组 */
export function normalizeList(data) {
  if (Array.isArray(data)) return data
  if (data && Array.isArray(data.items)) return data.items
  return []
}

/** 从全部学科里按 STARMAP_SUBJECTS 的顺序挑出存在的科目，只留 id 和 name */
export function pickStarmapSubjects(subjects) {
  const list = normalizeList(subjects)
  return STARMAP_SUBJECTS
    .map(name => list.find(subject => subject.name === name))
    .filter(Boolean)
    .map(subject => ({ id: subject.id, name: subject.name }))
}

/** 知识点树按学科分开存：不指定学科时用 'all' */
export function treeKey(subjectId) {
  return subjectId == null ? 'all' : String(subjectId)
}

/**
 * 包一层只请求一次的加载器：
 * - 同一时刻多次调用只发一次请求；
 * - 成功后记住结果，force 为真才重新请求；
 * - 失败时不记住，下次调用重新请求，错误照常抛给调用方。
 */
export function createLoader(fetcher) {
  let has_value = false
  let value
  let pending = null
  let version = 0

  async function load(force = false) {
    if (!force && has_value) return value
    if (pending) return pending
    const started = version
    pending = Promise.resolve()
      .then(fetcher)
      .then(result => {
        // reset 之后才回来的结果不记住，避免把旧数据写回去
        if (started === version) {
          value = result
          has_value = true
        }
        return result
      })
      .finally(() => { pending = null })
    return pending
  }

  /** 忘掉记住的结果；下次 load 重新请求 */
  function reset() {
    version += 1
    has_value = false
    value = undefined
    pending = null
  }

  return { load, reset }
}
