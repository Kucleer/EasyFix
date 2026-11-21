import { defineStore } from 'pinia'
import { questionApi } from '@/api/question'
import { createLoader, normalizeList, pickStarmapSubjects, treeKey } from './catalogModel'

// 加载器放在 store 外面：它们只管"请求一次、失败重试"，数据本身放在 state 里供页面响应式使用
const subject_loader = createLoader(async () => normalizeList((await questionApi.listSubjects()).data))
const tag_loader = createLoader(async () => normalizeList((await questionApi.listTags()).data))
const tree_loaders = new Map()

/** 取某个学科（或全部学科）的知识点树加载器 */
function tree_loader(subject_id) {
  const key = treeKey(subject_id)
  if (!tree_loaders.has(key)) {
    const params = subject_id == null ? undefined : { subject_id }
    tree_loaders.set(key, createLoader(async () => (await questionApi.getKnowledgePointTree(params)).data))
  }
  return tree_loaders.get(key)
}

/**
 * 学科、标签、知识点树的集中存放处，各页面共用。
 * 管理这些数据的页面在增删改之后调用 invalidate，其他页面下次读取时就会重新请求。
 */
export const useCatalogStore = defineStore('catalog', {
  state: () => ({
    subjects: [],
    tags: [],
    trees: {},   // 按学科存知识点树接口的完整返回体：{ all: {...}, '1': {...} }
  }),

  getters: {
    /** 知识星空和出卷页用的两科：[{ id, name }] */
    starmapSubjects: state => pickStarmapSubjects(state.subjects),
  },

  actions: {
    /** 读全部学科；force 为真时重新请求 */
    async loadSubjects(force = false) {
      this.subjects = await subject_loader.load(force)
      return this.subjects
    },

    /** 读知识星空和出卷页用的两科：[{ id, name }] */
    async loadStarmapSubjects(force = false) {
      await this.loadSubjects(force)
      return this.starmapSubjects
    },

    /** 读全部标签；force 为真时重新请求 */
    async loadTags(force = false) {
      this.tags = await tag_loader.load(force)
      return this.tags
    },

    /** 读某个学科的两级知识点树，不传学科就是全部学科 */
    async loadKnowledgeTree(subject_id = null, force = false) {
      const data = await tree_loader(subject_id).load(force)
      this.trees = { ...this.trees, [treeKey(subject_id)]: data }
      return data
    },

    /** 让某一类数据失效：'subjects'、'tags'、'knowledge'，不传就是全部 */
    invalidate(kind) {
      if (!kind || kind === 'subjects') {
        subject_loader.reset()
        this.subjects = []
      }
      if (!kind || kind === 'tags') {
        tag_loader.reset()
        this.tags = []
      }
      if (!kind || kind === 'knowledge') {
        for (const loader of tree_loaders.values()) loader.reset()
        this.trees = {}
      }
    },
  },
})
