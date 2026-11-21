// 目录数据 store 的纯函数测试：node --test frontend/src/stores/catalogModel.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { normalizeList, pickStarmapSubjects, treeKey, createLoader } from './catalogModel.js'

test('normalizeList：数组原样、{items} 取 items、其余为空', () => {
  assert.deepEqual(normalizeList([1]), [1])
  assert.deepEqual(normalizeList({ items: [2] }), [2])
  assert.deepEqual(normalizeList(null), [])
  assert.deepEqual(normalizeList({}), [])
})

test('pickStarmapSubjects：按数学、英语的顺序挑出存在的科目', () => {
  const list = [{ id: 2, name: '英语', extra: 1 }, { id: 1, name: '数学' }, { id: 3, name: '语文' }]
  assert.deepEqual(pickStarmapSubjects(list), [{ id: 1, name: '数学' }, { id: 2, name: '英语' }])
  assert.deepEqual(pickStarmapSubjects([{ id: 1, name: '数学' }]), [{ id: 1, name: '数学' }])
  assert.deepEqual(pickStarmapSubjects(null), [])
})

test('treeKey：不指定学科为 all', () => {
  assert.equal(treeKey(null), 'all')
  assert.equal(treeKey(undefined), 'all')
  assert.equal(treeKey(3), '3')
})

test('createLoader：并发只请求一次，成功后记住，force 才重新请求', async () => {
  let calls = 0
  const loader = createLoader(async () => { calls += 1; return calls })
  const [a, b] = await Promise.all([loader.load(), loader.load()])
  assert.equal(calls, 1)
  assert.equal(a, 1)
  assert.equal(b, 1)
  assert.equal(await loader.load(), 1)
  assert.equal(calls, 1)
  assert.equal(await loader.load(true), 2)
  assert.equal(calls, 2)
})

test('loader 失败后下次重试', async () => {
  let calls = 0
  const loader = createLoader(async () => {
    calls += 1
    if (calls === 1) throw new Error('502')
    return 'ok'
  })
  await assert.rejects(loader.load(), /502/)
  assert.equal(await loader.load(), 'ok')
  assert.equal(calls, 2)
})

test('reset 之后重新请求', async () => {
  let calls = 0
  const loader = createLoader(async () => { calls += 1; return calls })
  await loader.load()
  loader.reset()
  assert.equal(await loader.load(), 2)
})
