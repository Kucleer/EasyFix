// 共用组件里的纯逻辑测试：node --test frontend/src/components/ui/ui.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { ICON_PATHS } from './icons.js'
import { pickTab } from '../../composables/tabQuery.js'

test('图标表照抄样稿的 17 个，菜单要用的都在', () => {
  assert.equal(Object.keys(ICON_PATHS).length, 17)
  for (const name of ['home', 'words', 'flip', 'reading', 'questions', 'practice', 'weekly', 'insight', 'settings', 'more']) {
    assert.ok(ICON_PATHS[name], name)
  }
})

test('pickTab：地址里的标签有效就用它，否则用默认', () => {
  const keys = ['review', 'all']
  assert.equal(pickTab({ tab: 'all' }, keys, 'review'), 'all')
  assert.equal(pickTab({ tab: 'x' }, keys, 'review'), 'review')
  assert.equal(pickTab({}, keys, 'review'), 'review')
  assert.equal(pickTab(undefined, keys, 'review'), 'review')
})
