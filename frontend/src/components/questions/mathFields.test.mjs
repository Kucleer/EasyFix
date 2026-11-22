// 待核对和错题详情里会带公式的字段（说明、判错依据）必须用 MathText 显示，不能直接插值成原文。
// 运行：node --test frontend/src/components/questions/mathFields.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { join, dirname } from 'node:path'
import { fileURLToPath } from 'node:url'

const HERE = dirname(fileURLToPath(import.meta.url))

/** 读同目录下的组件源码 */
function read(name) {
  return readFileSync(join(HERE, name), 'utf8')
}

// [文件, 字段]：这些字段的内容来自录入，常写成 \(\pm 7\) 这样的公式
const FIELDS = [
  ['ReviewTab.vue', 'q.review_note'],
  ['ReviewTab.vue', 'q.wrong_evidence'],
  ['QuestionDetailDialog.vue', 'question.wrong_evidence'],
]

test('说明、判错依据不直接插值显示', () => {
  for (const [file, field] of FIELDS) {
    const plain = new RegExp('\\{\\{\\s*' + field.replace('.', '\\.') + '\\b')
    assert.ok(!plain.test(read(file)), file + ' 里 ' + field + ' 仍是直接插值')
  }
})

test('说明、判错依据交给 MathText 渲染', () => {
  for (const [file, field] of FIELDS) {
    const rendered = new RegExp('<MathText\\s+:text="' + field.replace('.', '\\.') + '\\b')
    assert.ok(rendered.test(read(file)), file + ' 里 ' + field + ' 没有用 MathText')
  }
})
