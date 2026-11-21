// 前端接口层的读源码测试：页面不直接写接口地址，每个接口只定义一个前端函数。
// 运行：node --test frontend/src/api/apiLayer.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync, readdirSync, statSync } from 'node:fs'
import { join, dirname, relative } from 'node:path'
import { fileURLToPath } from 'node:url'

const SRC = join(dirname(fileURLToPath(import.meta.url)), '..')

/** 递归列出某个目录下的 .vue / .js 文件（不含测试文件） */
function list_files(dir) {
  const result = []
  for (const name of readdirSync(dir)) {
    const path = join(dir, name)
    if (statSync(path).isDirectory()) result.push(...list_files(path))
    else if (/\.(vue|js)$/.test(name) && !/\.test\./.test(name)) result.push(path)
  }
  return result
}

/** 读文件全文 */
function read(path) {
  return readFileSync(path, 'utf8')
}

const PAGE_DIRS = ['views', 'components', 'composables', 'stores']
const API_FILES = list_files(join(SRC, 'api'))

test('页面、组件、composable、store 里不直接请求接口地址', () => {
  const offenders = []
  for (const dir of PAGE_DIRS) {
    for (const path of list_files(join(SRC, dir))) {
      const text = read(path)
      if (/axios\.(get|post|put|delete|patch)\(/.test(text) || /fetch\(\s*[`'"]\/api\//.test(text)) {
        offenders.push(relative(SRC, path))
      }
    }
  }
  assert.deepEqual(offenders, [])
})

// 每个片段在 api/*.js 里只能出现一次（同一个接口只留一个前端函数）
const UNIQUE_ENDPOINTS = [
  ["api.get(`/practice-sets/${", '练习集详情'],
  ['/generate-pdf`', '生成 PDF'],
  ['/mark-reviewed`', '提交批改'],
  ["api.get('/subjects'", '学科列表'],
  ["'/config/app'", '应用配置（读、写各一次，按函数计）'],
  ["'/upload/batch-simple'", '多张上传'],
  ["'/upload/file'", '单张上传'],
  ["'/auth/verify-password'", '验密码'],
]

test('每个接口只定义一个前端函数', () => {
  for (const [fragment, label] of UNIQUE_ENDPOINTS) {
    const hits = API_FILES.flatMap(path => read(path).split('\n')
      .filter(line => line.includes(fragment))
      .map(() => relative(SRC, path)))
    // 应用配置有读、写两个函数，各出现一次，合计 2；其余都只能有 1 处
    const expected = fragment === "'/config/app'" ? 2 : 1
    assert.equal(hits.length, expected, label + '：' + hits.join(', '))
  }
})

test('没有文件从 question.js 导入 configApi 或 uploadApi', () => {
  const offenders = []
  for (const dir of [...PAGE_DIRS, 'api']) {
    for (const path of list_files(join(SRC, dir))) {
      if (/import\s*\{[^}]*\b(configApi|uploadApi)\b[^}]*\}\s*from\s*'@\/api\/question'/.test(read(path))) {
        offenders.push(relative(SRC, path))
      }
    }
  }
  assert.deepEqual(offenders, [])
})
