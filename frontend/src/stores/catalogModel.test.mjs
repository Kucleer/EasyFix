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

test('请求途中 reset：调用方拿到 reset 之后的新数据，旧结果不记住', async () => {
  let calls = 0
  const releases = []
  const loader = createLoader(() => {
    calls += 1
    const n = calls
    return new Promise(resolve => releases.push(() => resolve(n)))
  })
  const first = loader.load()
  await Promise.resolve()
  loader.reset()                  // 管理页刚改了目录
  releases[0]()                   // 旧请求这时才回来
  await new Promise(resolve => setTimeout(resolve, 0))
  releases[1]()                   // reset 之后重新发的请求
  assert.equal(await first, 2)
  assert.equal(await loader.load(), 2)
  assert.equal(calls, 2)
})

test('旧请求结束不会清掉新请求的去重', async () => {
  let calls = 0
  const releases = []
  const loader = createLoader(() => {
    calls += 1
    const n = calls
    return new Promise(resolve => releases.push(() => resolve(n)))
  })
  loader.load()
  await Promise.resolve()
  loader.reset()
  const second = loader.load()    // reset 后新发一个请求
  await Promise.resolve()
  releases[0]()                   // 旧请求结束
  await new Promise(resolve => setTimeout(resolve, 0))
  const third = loader.load()     // 新请求还没回来，应该复用它
  releases[1]()
  assert.equal(await second, 2)
  assert.equal(await third, 2)
  assert.equal(calls, 2)
})

test('reset 之后重新请求', async () => {
  let calls = 0
  const loader = createLoader(async () => { calls += 1; return calls })
  await loader.load()
  loader.reset()
  assert.equal(await loader.load(), 2)
})
