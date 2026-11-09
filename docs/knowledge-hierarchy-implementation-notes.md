# 两级知识点改造实现说明

日期：2026-11-10（北京时间）
分支：`codex/knowledge-hierarchy-20261110`
状态：代码已在独立分支实现并通过本地 SQLite 不变量测试与前端构建；**未执行生产 D1 迁移、未部署 Worker / Pages、未开启维护开关**。
规格来源：`docs/knowledge-hierarchy-final-plan.md`。

## 1. 已实现范围

### 1.1 数据层

新增追加迁移 `cloudflare/migrations/0009_knowledge_hierarchy.sql`，不修改历史迁移：

- `knowledge_point` 增加 `code`、`name_key`、`level`、`parent_id`、`sort_order`、`updated_at`。
- `question` 增加 `knowledge_revision`、`legacy_knowledge_point`，并回填旧文本原文。
- 新增 `question_knowledge_point`：题目与二级知识点多对多，`source` 为 `manual/migration/agent`，软删除。
- 新增 `knowledge_assert`：事务内版本守卫与主考点结构断言；与 `write_guard` 分开，避免不同失败都映射成版本冲突。
- 索引：
  - `ux_kp_code`：有效编码唯一；
  - `ux_kp_level1_name(subject_id,name_key) WHERE level=1`；
  - `ux_kp_level2_name(parent_id,name_key) WHERE level=2`；
  - `ux_qkp_pair(question_id,knowledge_point_id)`：重复添加可恢复；
  - `ux_qkp_primary(question_id) WHERE is_primary=1 AND deleted=0`：每题至多一个主考点；
  - 题目反查与关联装配索引。
- 触发器（错误消息前缀 `KP_<CODE>:`）：
  - `trg_kp_bi/trg_kp_bu`：拒绝三级、跨学科父级、一级带父级、空名称；有子级/引用时拒绝改层级、改学科、移动；有有效子级/引用时拒绝软删除。
  - `trg_qkp_bi/trg_qkp_bu`：只允许未删除、与题目同学科、`level=2` 的节点。
  - `trg_question_subject_kp`：题目改学科时不允许留下原学科有效关联。
  - `trg_kp_error_type_bi/bu`：错误类型只能配置在有效二级。
  - `trg_subject_bu`：学科下仍有有效知识点或错题时拒绝软删除。
  - `trg_knowledge_assert_guard/structure`：分别抛出 `KP_GUARD`（409）与 `KP_STRUCT`（422）。

### 1.2 后端

| 文件 | 内容 |
| --- | --- |
| `cloudflare/src/knowledge_model.py` | `name_key` 规范化（NFKC + 折叠空白 + casefold）、错误码映射、树组装、主考点投影 |
| `cloudflare/src/knowledge.py` | `/api/knowledge-points` 平铺与 `/tree`、CRUD、引用计数、错误类型、`taxonomy_version` 与 `data_revision` 同批次递增；题目关联读写与集合校验 `resolve_many` |
| `cloudflare/src/knowledge_stats.py` | 一级/二级聚合、未分类、复习覆盖、模块练习正确率、筛选组合校验 |
| `cloudflare/src/questions.py` | 单题保存/批量入库/列表/详情/filter-options；分类变化在同一 batch 内完成版本守卫、旧关联清理、新关联写入、结构断言 |
| `cloudflare/src/catalog.py` | 移出 `knowledge-points`；补学科删除引用保护 |
| `cloudflare/src/analytics.py` | `summary`、`analysis/full`、`/stats/knowledge-points` 统一使用一级模块；图谱返回父子边 |
| `cloudflare/src/reports.py` | `schema_version=2`、服务端 `content.metrics`、`taxonomy_version`、旧报告 `legacy_schema` |
| `cloudflare/src/practices.py` | 练习条目按 `question_id` 批量装配知识点；批改支持 `question_knowledge` 并按版本守卫写入 |
| `cloudflare/src/prompts.py` | 手写源；相似题传主考点与其他二级；报告提示词只输出叙述，不输出计数 |
| `cloudflare/src/similar.py` | 相似题读取全部关联二级 |
| `cloudflare/src/pdf.py` | 指纹加入模板版本、主考点路径与全部二级；打印显示“一级 / 二级（主考点）” |
| `cloudflare/src/auth.py` | D1 `write_maintenance` 维护写开关，覆盖 Bearer |
| `cloudflare/src/media.py` | 维护期间音频缓存未命中返回 503，不回源写 R2 |
| `cloudflare/src/cache.py` | 未改动；复用现有 `data_revision` 机制（目录写入在知识路由同批次递增，使统计缓存失效） |

### 1.3 前端

| 文件 | 内容 |
| --- | --- |
| `components/KnowledgePointPicker.vue` | 新增共享两级选择器：一级分组、二级多选、显式主考点；单选自动设为主考点；学科切换清理跨学科选择 |
| `components/KnowledgeTag.vue` | 支持对象、一级/二级路径、主考点标记；保留旧 `name` 用法 |
| `composables/knowledgeColors.js` | 按 ID 取色；一级固定色系、二级同色系派生；`refreshKnowledgeColors` 在目录写入后重置 |
| `components/SubjectKnowledgeRanking.vue` | 模块级排行、`模块练习正确率`、点击下钻事件 |
| `views/Management.vue` | 两级树表、新增一级/二级、父级选择、编码/排序、错误类型只配二级、引用计数、待处理旧目录 |
| `views/Upload.vue` | 使用 Picker；错误类型按所选二级取并集 |
| `views/Questions.vue` | 一级/二级筛选、未分类筛选、列表多标签折叠、详情路径、编辑携带 `knowledge_revision` |
| `views/PracticeSets.vue` | 批改弹窗使用 Picker 与 `knowledge_revision`，保存后用响应刷新本地条目 |
| `views/LearningAnalysis.vue` | 默认一级、点击下钻二级、未分类跳转、两套正确率命名 |
| `views/LearningReports.vue` | 新版读取 `content.metrics` 与 `content.narrative`；旧报告标识旧口径 |
| `api/http.js` | 目录树缓存覆盖 `/knowledge-points/tree` |
| `api/question.js`、`api/learning_analysis.js` | 新参数、树接口、批改知识点参数 |

## 2. API 合约

### 2.1 知识点目录

```http
GET /api/knowledge-points/tree?subject_id=1&grade=6&semester=1
```

```json
{
  "taxonomy_version": "12",
  "total": 10,
  "items": [
    {
      "id": 10, "name": "有理数", "level": 1, "parent_id": null,
      "code": "MATH-M07", "sort_order": 70, "question_count": 42, "child_count": 6,
      "children": [
        {"id": 11, "name": "乘方", "level": 2, "parent_id": 10, "parent_name": "有理数",
         "code": "MATH-L2-001", "question_count": 12, "error_types": [{"id": 1, "name": "计算错误"}]}
      ]
    }
  ]
}
```

`/tree` 声明在 `/{item_id}` 之前；`grade/semester` 先匹配二级，再补齐父级。

### 2.2 题目写入

```json
POST /api/questions
{
  "subject_id": 1,
  "parsed_question": "...",
  "knowledge_point_ids": [101, 102],
  "primary_knowledge_point_id": 101,
  "knowledge_revision": 3
}
```

规则：

- 新建可省略 `knowledge_revision`；已有题目分类/学科实际变化时必须提供读取时的版本，过期返回 409。
- 非空列表必须显式主考点；空数组明确清空；未提供字段保留关联。
- 旧文本 `knowledge_point` 按 4.3 处理：等于当前投影或空字符串视为未修改；唯一匹配二级则设为主考点并保留其他关联；未知/歧义返回 422。
- 提供 `knowledge_point_ids` 时不再接受其他旧文本作为身份；新旧同传且矛盾返回 422。
- 改学科必须在同一请求提交新学科 `knowledge_point_ids`（可为空数组），否则 422。
- 响应统一包含 `knowledge_revision`、`knowledge_points`、`knowledge_point`（主考点名）、`legacy_knowledge_point`。

### 2.3 统计

```http
GET /api/stats/knowledge-points?subject_id=1&level=1&days=30
GET /api/stats/knowledge-points?subject_id=1&level=2&parent_id=10
```

返回：

```json
{
  "taxonomy_version": "12",
  "counting_mode": "level1_primary_share+module_practice_accuracy",
  "level": 1,
  "parent_id": null,
  "total_questions": 120,
  "unclassified_count": 7,
  "items": [{
    "id": 10, "name": "有理数", "question_count": 42, "primary_question_count": 38,
    "share_percent": 31.7, "reviewed_question_count": 30, "review_coverage": 71.4,
    "answer_count": 55, "correct_count": 40, "accuracy": 72.7
  }]
}
```

- 题数按题目-模块去重；占比只按主考点归属，未分类单独计数。
- `accuracy` 来自 `practice_set_question` 最终批改状态，零作答为 `null`。
- 题数按 `question.created_at` 筛选；正确率按 `practice_set.last_reviewed_at` 筛选，二者不叠加。
- `review_coverage` 的分子分母使用同一收录筛选题目集合：分子是集合内“曾有过有效已批改练习”的去重题目，表示“曾复习”；不按练习批改时间放大，因此始终在 0–100%。模块正确率仍可包含旧题的本期作答。
- 一级 `share_percent` 按主考点归属，加未分类后为整体；二级额外返回 `parent_share_percent` = 该二级主考点题数 / 父模块收录筛选后的去重题数，不使用兄弟二级题数相加。
- 模块即使当前筛选下没有题目也会返回（题数 0、正确率 `null`），避免删除或时间窗口变化后静默丢模块。

### 2.4 学习报告

`POST /api/learning-reports/generate` 返回 `schema_version=2`；报告 `content`：

```json
{
  "schema_version": 2,
  "overview": {"total_questions": 0, "total_words": 0, "overall_accuracy": 0},
  "metrics": {
    "taxonomy_version": "12",
    "counting_mode": "level1_primary_share+module_practice_accuracy",
    "level": 1,
    "total_questions": 120,
    "unclassified_count": 7,
    "modules": [{"id": 10, "name": "有理数", "share_percent": 31.7, "accuracy": 72.7}],
    "time_window": {"question_created_days": 30, "practice_reviewed_days": 30}
  },
  "narrative": {
    "overall": "...",
    "knowledge_modules": [{"module_id": 10, "module_name": "有理数", "reason": "...", "suggestion": "..."}],
    "review_strategy": "...",
    "word_strategy": "..."
  },
  "suggestions": [{"type": "练习", "content": "...", "priority": 1}],
  "summary": {"key_findings": ["..."], "priority_improvements": ["..."]}
}
```

旧报告没有 `schema_version` 时 `legacy_schema=true`，前端显示“旧版分类口径；知识点排行未按新口径复核”，不重写、不重新调用模型。

## 3. 迁移运行手册

所有脚本默认只读或只生成 SQL，不直接写生产库。

### 3.1 预检

```text
python cloudflare/scripts/knowledge_preflight.py --snapshot backups/<新导出>/database.sqlite3
python cloudflare/scripts/knowledge_consistency_check.py --snapshot backups/<新导出>/database.sqlite3
```

预检输出 `tmp/knowledge-preflight-*.json`：目录与题目数量、按学科/年级/学期分布、旧文本清单、宽标签、同名候选、守卫行与 schema。发现 `write_guard` 缺失、同级重名等问题时以非零状态退出。

### 3.2 审核映射

映射 JSON（含学生题目 ID，不能提交）：

```json
{
  "points": [
    {"code": "MATH-L2-001", "subject": "数学", "level": 2, "parent_code": "MATH-M07", "name": "乘方", "sort_order": 10}
  ],
  "questions": [
    {"question_id": 123, "knowledge_revision": 0, "codes": ["MATH-L2-001"], "primary_code": "MATH-L2-001"}
  ]
}
```

一级模块种子 `cloudflare/scripts/knowledge_seed_modules.json` 只包含一级建议，二级必须逐条审核后写入私有映射。脚本会优先复用同名的旧目录行（保留原 ID），避免同级唯一索引冲突。

### 3.3 生成回填 SQL

```text
python cloudflare/scripts/knowledge_backfill.py \
  --seed cloudflare/scripts/knowledge_seed_modules.json \
  --mapping tmp/knowledge-reviewed-mapping.json \
  --snapshot backups/<新导出>/database.sqlite3
```

生成 `tmp/knowledge-backfill-<时间>/`：

- `00-catalog.sql`：目录与错误类型；已存在的同名旧目录行按 code 复用原 ID；
- `batch-001.sql`...：每批默认 25 题；首条守卫确认全部目标 code 存在、有效、二级，并校验题目版本；末尾断言实际关联集合等于审核 codes、没有额外关联、恰好一个主考点且编码等于审核主考点；
- `99-versions.sql`：全部批次通过一致性校验后再执行；
- `manifest.json`：数量、文件顺序、映射 SHA-256 与各文件 SHA-256。

注意：D1 要求导入文件移除 `BEGIN/COMMIT`，并由平台把一次文件导入作为事务执行（Wrangler 提示“D1 runs your SQL in a transaction for you”）；本地 D1 验证中，含失败语句的文件整体回滚。批次文件仍逐批执行。缺任何目标 code、目标被软删除、关联多出或主考点不符都会整批失败，题目版本与旧关联不变。

一致性校验应带映射逐题核对实际集合，不能只检查“结构合法”：

```text
python cloudflare/scripts/knowledge_consistency_check.py \
  --snapshot <新导出> --mapping tmp/knowledge-reviewed-mapping.json
```

幂等性说明：`00-catalog.sql` 可重复执行；已成功提交的 `batch-*.sql` 会因题目版本已递增而在首条守卫失败，这是防重复写入的安全策略，不应把“重放成功”当作幂等。重试未提交批次前，先用 manifest 的 `mapping_sha256` / 文件 SHA-256 与逐题回读确认该批未落库；已落库批次跳过，不重复执行。

### 3.4 生产执行顺序

1. 发布只含维护开关的 Worker 小版本（发布 A），验证开启时浏览器与 Bearer 写入均 503、只读与登录正常。
2. 开启 `write_maintenance=1`，排空在途写入与外部生成任务。
3. 记录 D1 Time Travel 书签并导出完整 SQL 备份。
4. 应用 `0009_knowledge_hierarchy.sql`（先 schema，后回填）。
5. 依次执行 `00-catalog.sql`、`batch-*.sql`；每批后重新导出快照，运行带 `--mapping` 的一致性校验，确认集合与主考点完整。
6. 全部通过后执行 `99-versions.sql`，再运行一次一致性校验。
7. 发布新 Worker 与已构建的 Pages 产物（发布 B），保持维护开启做正式只读验证。
8. 关闭维护，执行最小真实写入冒烟并清理临时记录；失败立即重新开启维护。

恢复策略见方案第 12.3 节；分类纠错使用软删除/恢复，不全库覆盖。

## 4. 验证记录（本地）

- `python -m compileall -q cloudflare/src`：通过。
- `python cloudflare/scripts/knowledge_invariants_test.py`：19 项全部通过，覆盖：
  - 名称规范化（全半角、大小写、空白）；
  - 三级/跨学科/缺父级/一级带父级/同级重名拒绝；
  - 关联只允许有效同学科二级；主考点唯一；
  - 题目改学科、二级移动、有引用删除、学科删除保护；
  - 错误类型只挂二级；
  - 版本守卫与结构断言错误码；
  - 目录版本与 `data_revision` 同批递增；
  - 旧文本兼容：当前投影/空字符串保留、精确匹配保留次要考点、歧义与未知拒绝、新旧字段矛盾拒绝、非空列表必须主考点；
  - 一级/二级聚合、多考点去重、跨模块覆盖、未分类、零作答 `accuracy=null`；
  - 时间窗口：题数按收录时间、正确率按批改时间；
  - 软删除后的指标；
  - 目录 CRUD：创建一级/二级、同级重名、三级、跨学科父级、一级挂错误类型、改名保持 ID、有引用禁止移动；
  - 回填集合完整性断言：缺次考点、缺全部考点、额外多出关联、主考点不一致均整批失败；
  - 单题保存原子路径（创建、内容更新、过期版本 409、分类更新、清空、改学科需新关联、同批迁移）。
- `python cloudflare/scripts/knowledge_api_test.py`：7 项 HTTP 集成测试全部通过（本地 SQLite 适配 D1 接口）：
  - `/api/knowledge-points/tree` 路由顺序与树结构；
  - 目录创建/更新/删除、同级重名 409、三级 422、一级挂错误类型 422、有子级删除 409；
  - 题目创建、一级/二级筛选、详情、过期版本 409、旧文本回传当前投影保留关联、filter-options；
  - 批量入库单题知识点错误隔离；
  - `/api/stats/knowledge-points` 一级/二级口径、零作答 `accuracy=null`、二级缺 `parent_id` 返回 422；
  - 练习批改提交过期分类版本返回 409，且题目分类、版本、练习批改状态与计数器均未部分写入；
  - 学习报告 `schema_version=2`、`content.metrics`、服务端分布数值、提示词要求“不要输出任何计数”、不含 `top_error_knowledge_points` 输出字段。
- 预检脚本在 2026-11-09 的迁移前快照上只读运行成功（557 道有效题、83 个目录行、137 条旧文本），并正确提示缺少 `runtime_config/write_guard`。
- 本地 D1（`wrangler d1 execute --local`，Miniflare）应用 `0009_knowledge_hierarchy.sql` 成功：`CREATE TRIGGER`、部分唯一索引与 `ALTER TABLE` 均可执行；回读确认 10 个触发器与 4 个 `question_knowledge_point` 索引存在。插入三级节点实际返回 `KP_LEVEL:...: SQLITE_CONSTRAINT (extended: SQLITE_CONSTRAINT_TRIGGER)`，应用层 `map_error` 会剥离 SQLite 后缀并映射 422。另验证含失败语句的导入文件整体回滚，成功文件用 `json_each` 横向展开批量关联并回读主/次考点正确。此项为本地验证，不等于生产 D1 已迁移。
- 回填脚本在本地 SQLite 快照上生成并执行 `00-catalog/batch-001/99-versions`，回读主考点与关联正确，一致性校验零阻断性违规。
- `knowledge_consistency_check.py --mapping` 逐题核对通过；人为删除一个次考点关联后返回 `mapping_mismatch: 1` 并以非零状态退出，证明集合完整性可被独立复核。
- 同一套回填文件在本地 D1（`wrangler d1 execute --local`）执行成功：题目 900 回读 `knowledge_point=测试考点`、`knowledge_revision=1`、主考点关联 1 条、父级路径正确，`taxonomy_version` 从 0 递增为 1。验证了 D1 对 JSON 集合、`ON CONFLICT`、守卫与结构断言的实际支持。
- `npm run build`（frontend）：通过；仅有既有的大 chunk 体积提示。

## 5. 已知边界与待办

- 未执行生产迁移、部署或维护开关切换；生产数据未改动。
- 维护开关目前只做请求入口检查；**数据库事务内写门禁与在途请求排空本轮按用户要求暂不实现**。发布 A 前必须补齐，否则无法证明最终备份后没有在途写入，不能进入生产迁移。
- 二级考点种子清单、逐题映射与外部 Agent 提示词不在本仓库；Agent 调用方需改为先取 `/api/knowledge-points/tree`，再提交 `knowledge_point_ids`/`primary_knowledge_point_id`。在 Agent 更新前，无法唯一匹配的旧文本会进入单题 `errors`。
- 教材章节与知识点的多对多映射不在本期范围。
- 旧 `kp_error_type` 行仍挂在 `level IS NULL` 的旧目录上，只读保留；新二级的错误类型必须在审核映射的 `error_type_ids` 中逐条指定，本期不做自动合并或清空。已有错误类型不会因分类变化被判定为错误。
- D1 文件导入不支持显式 `BEGIN/COMMIT`；平台按文件事务执行，本地验证失败文件会整体回滚。迁移仍按批次拆分，便于定位与逐批校验。
- `GET /api/stats/knowledge-points` 返回结构由数组改为对象（含 `items`），旧调用方需同步；本项目前端已迁移。
- 题目累计计数器 `review_count/correct_count/error_count` 未改动，仍用于题目级展示与 `accuracy_range` 筛选；“模块练习正确率”是另一套口径，界面已分开命名。
- 阅读练习的 topic 不再冒充知识点；阅读/单词练习不计入错题模块正确率。
- `cloudflare/pdf/index.js` 未改动：打印模板已经读取并转义 `knowledge_point`，本次只把该字段改为“一级 / 二级（主考点）”并在指纹中加入结构；`cloudflare/src/cache.py` 未改动：目录写入在同批次递增 `data_revision`，现有统计缓存键因此失效。

## 6. Review 指引

建议按以下顺序检查：

1. `cloudflare/migrations/0009_knowledge_hierarchy.sql`：唯一索引、触发器与 `write_guard`/`knowledge_assert` 断言是否覆盖方案 4.1/4.2 的不变量。
2. `cloudflare/src/questions.py` 的 `save()`/`batch()`：分类变化的 guard、旧关联清理、改学科顺序、末尾结构断言是否在同一 batch；旧的 `knowledge_point` 文本只作为兼容输入，不再作为写入事实。
3. `cloudflare/src/knowledge.py` 的 `resolve_many`/`link_statements`/`plan_knowledge`：4.3 兼容规则与主考点唯一性。
4. `cloudflare/src/knowledge_stats.py`：一级题数/主考点占比/复习覆盖/模块练习正确率的去重与时间窗口。
5. `cloudflare/src/reports.py` 与 `prompts.py`：模型是否仍可能输出计数，服务端是否覆盖 `metrics`/`overview`/分布数值。
6. 前端 `KnowledgePointPicker` 与 `Questions/Upload/PracticeSets/Management/Analysis/Reports`：是否所有写入都改为 ID + 主考点 + 版本，是否仍有自由文本知识点入口。
7. 运行：
   ```text
   python -m compileall -q cloudflare/src
   python cloudflare/scripts/knowledge_invariants_test.py
   python cloudflare/scripts/knowledge_api_test.py
   cd frontend && npm run build
   ```
   本地 D1 验证（不改生产）：
   ```text
   node cloudflare/tools/cli.cjs d1 execute easyfix --config cloudflare/wrangler.jsonc --local --file cloudflare/migrations/0009_knowledge_hierarchy.sql --yes
   ```

已知风险：生产迁移、维护开关切换、Time Travel 恢复与外部 Agent 提示词均未执行；二级种子与逐题映射仍需人工审核。`cloudflare/pages/_worker.js` 对所有 `/api/*` 透传，无需为新路由添加白名单。
