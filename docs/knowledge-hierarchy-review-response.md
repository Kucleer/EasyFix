# 两级知识点 Review 修复记录

日期：2026-11-10（北京时间）
分支：`codex/knowledge-hierarchy-20261110`
审查来源：`docs/knowledge-hierarchy-implementation-review.md`
用户指示：**在途问题暂时不用考虑**，因此 R1 中“事务内写门禁 / 在途排空”本轮不实现；其余问题修复。

## 1. 处理状态

| 编号 | 级别 | 状态 | 说明 |
| --- | --- | --- | --- |
| R1 | P1 | 暂缓（按用户指示） | 未实现数据库事务内维护门禁与在途排空。发布 A 前仍必须补齐，当前不具备生产迁移条件。 |
| R2 | P1 | 已修复 | 回填批次首条校验全部目标 code 存在/有效/二级；末尾双向比对实际关联集合与主考点；一致性脚本支持 `--mapping` 逐题核对。 |
| R3 | P2 | 已修复 | 复习覆盖率分子改为“收录筛选集合内曾复习过的题”，分母同集合题数；模块正确率仍按批改时间。 |
| R4 | P2 | 已修复 | 练习批改 batch 统一映射 `KP_*` 触发器错误；auth 中间件也做兜底映射，不再一律 500。 |
| R5 | P2 | 已修复 | 多选时移除主考点不再静默选第一个；保持 `null` 并提示，Upload 增加提交前校验。 |

## 2. R2：回填集合完整性

改动：
- `knowledge_backfill.py` 的 `assertion_sql`：
  - 批次首条 guard 新增“全部审核 code 在库中且为未删除二级”的数量断言；缺任何目标整批失败。
  - 末尾 structure 断言要求每题的：
    - 有效关联数量等于审核 `codes` 数量；
    - 不存在审核集合之外的关联；
    - 恰好一个主考点；
    - 主考点 code 等于审核 `primary_code`。
  - 不再只检查“主考点数量”。
- `knowledge_consistency_check.py` 新增 `--mapping`：
  - 逐题比较实际有效关联 code 集合与审核 `codes`；
  - 比较实际主考点与 `primary_code`；
  - 不一致写入 `mapping_mismatches` 并以非零状态退出。
- manifest 增加 `mapping_sha256`，并说明已提交批次重放会因版本 guard 失败，不能把“重放成功”当作幂等。

回归：
- `knowledge_invariants_test.py` 新增“回填集合完整性断言”：缺次考点、缺全部考点（guard）、额外关联、主考点不一致均失败；完整集合通过。
- 本地 SQLite 回填后运行 `knowledge_consistency_check.py --mapping` 零 mismatch；人为删除次考点后返回 `mapping_mismatch: 1` 且退出码 1。

## 3. R3：覆盖率口径

改动 `knowledge_stats.py`：
- 新增独立的 coverage 查询：使用题目收录筛选集合（含 `q.created_at` 时间窗口）作为分子分母，只统计“曾有过有效已批改练习”的去重题目。
- 模块练习正确率仍使用 `practice_set.last_reviewed_at` 的练习时间窗口，可包含旧题本期作答。
- 覆盖率定义明确为“曾复习”，因此始终 0–100%；文档已记录。

回归：
- `test_stats_time_window`：窗口内 1 题、窗口外 1 题且两题都在练习窗口内被批改，覆盖率仍为 100%（1/1），不再出现 200%；正确率仍计 2 次作答。
- 既有模块正确率/覆盖率测试继续通过。

## 4. R4：批改版本冲突错误映射

改动：
- `practices.py` 新增 `batch_or_http`，创建练习、批改、删除练习的 D1 batch 都通过它执行；捕获 `KP_GUARD`/`KP_STRUCT`/`KP_STATE` 并映射 409/422/503，未知异常继续抛出。
- `auth.py` 的通用异常处理兜底调用 `map_error`，其他路径的触发器错误也不再统一变成 500。

回归：
- 新增 HTTP 测试：批改提交过期 `knowledge_revision` 返回 409；回读确认题目分类、`knowledge_revision`、练习 `reviewed`/`review_count`、逐题 `is_correct` 均未部分写入。
- 练习批改、目录、题目、报告测试继续通过。

## 5. R5：主考点选择

改动：
- `KnowledgePointPicker.vue`：
  - 剩余单项自动设为主考点；
  - 保留原主考点时不变；
  - 多选且原主考点失效时设为 `null`，不静默选择第一个；
  - 目录刷新 prune 选择时同样只有“剩一项”才自动指定。
- `Upload.vue` 提交前检查“已选知识点必须有主考点”，与 Questions/PracticeSets 一致。

验证：
- `npm run build` 通过。未做浏览器交互测试，Picker 三个入口的实际视觉/交互仍需发布前人工检查。

## 6. 其他对齐

- `knowledge.py` 头部注释 `0081` 改为 `0009`。
- 实施说明中 `cache.py` 的描述改为“未改动，复用现有 `data_revision` 机制”。
- `parent_share_percent` 改为“该二级主考点题数 / 父模块收录筛选后的去重题数”，不再把兄弟二级题数相加；测试改为 100%/0%。
- 回填幂等说明区分“目录可重复执行”和“已提交批次不可重放”，并给出 manifest/回读判断步骤。
- 实施说明补充“已实现 / 已本地验证 / 待隔离验证 / 待生产验证”的边界，并注明 R1 暂缓。

## 7. 最新验证

```text
python -m compileall -q cloudflare/src                      通过
python cloudflare/scripts/knowledge_invariants_test.py      19/19 通过
python cloudflare/scripts/knowledge_api_test.py             7/7 通过
python cloudflare/scripts/knowledge_consistency_check.py --snapshot ... --mapping ...   0 mismatch
cd frontend && npm run build                                通过
```

本地 D1 验证仍限于 `wrangler d1 execute --local`：0009 触发器/索引、JSON 批量关联、回填文件、失败文件整体回滚。未执行远端 D1、Time Travel、维护开关切换、Worker/Pages 部署或浏览器验收。

## 8. 发布前仍需完成

1. R1：事务内维护写门禁与在途排空/副作用排空（按用户指示暂缓）。
2. 发布 A 维护小版本单独构建、验证、固定产物。
3. 二级种子、逐题映射、外部 Agent 提示词审核。
4. 隔离 D1 演练触发器错误映射、批次回滚、Time Travel 恢复。
5. 浏览器检查 Picker 的 Upload、Questions、PracticeSets 三个入口。
