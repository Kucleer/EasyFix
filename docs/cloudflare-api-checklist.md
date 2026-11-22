# Cloudflare API 迁移清单

以下复选框代表已有对应代码；不等同于全部运行场景均已验收。运行验证见迁移记录。

- [x] `DELETE /api/achievements/{achievement_id}`
- [x] `DELETE /api/error-books/{error_book_id}`
- [x] `DELETE /api/knowledge-points/{kp_id}`
- [x] `DELETE /api/learning-reports/{report_id}`
- [x] `DELETE /api/practice-sets/{practice_set_id}`
- [x] `DELETE /api/questions/{question_id}`
- [x] `DELETE /api/readings/{reading_id}`
- [x] `DELETE /api/rewards/{reward_id}`
- [x] `DELETE /api/stars/actions/{action_id}`
- [x] `DELETE /api/subjects/{subject_id}`
- [x] `DELETE /api/tags/{tag_id}`
- [x] `DELETE /api/words/{word_id}`
- [x] `GET /api/achievements`
- [x] `GET /api/achievements/progress`
- [x] `GET /api/config/app`
- [x] `GET /api/config/llm`
- [x] `GET /api/error-books`
- [x] `GET /api/knowledge-points`
- [x] `GET /api/learning-reports/list`
- [x] `GET /api/learning-reports/{report_id}`
- [x] `GET /api/motivation/overview`
- [x] `GET /api/practice-sets`
- [x] `GET /api/practice-sets/{practice_set_id}`
- [x] `GET /api/questions`
- [x] `GET /api/questions/filter-options/{subject_id}`
- [x] `GET /api/questions/{question_id}`
- [x] `GET /api/questions/{question_id}/practice-history`
- [x] `GET /api/readings`
- [x] `GET /api/readings/topics`
- [x] `GET /api/readings/{reading_id}`
- [x] `GET /api/rewards`
- [x] `GET /api/rewards/redemptions`
- [x] `GET /api/stars/actions`
- [x] `GET /api/stars/balance`
- [x] `GET /api/stars/records`
- [x] `GET /api/subjects`
- [x] `GET /api/tags`
- [x] `GET /api/words`
- [x] `GET /api/words/stats/summary`
- [x] `GET /api/words/{word_id}`
- [x] `GET /api/words/{word_id}/audio`
- [x] `GET /api/words/{word_id}/memory-curve`
- [x] `POST /api/achievements`
- [x] `POST /api/config/app`
- [x] `POST /api/config/llm`
- [x] `POST /api/error-books`
- [x] `POST /api/knowledge-points`
- [x] `POST /api/motivation/trigger/review_word_accuracy`
- [x] `POST /api/practice-sets`
- [x] `POST /api/practice-sets/batch-delete`
- [x] `POST /api/practice-sets/batch-download-pdf`
- [x] `POST /api/practice-sets/generate-from-reading`
- [x] `POST /api/practice-sets/{practice_set_id}/generate-pdf`
- [x] `POST /api/practice-sets/{practice_set_id}/mark-reviewed`
- [x] `POST /api/questions`
- [x] `POST /api/questions/{question_id}/similar`
- [x] `POST /api/readings/generate`
- [x] `POST /api/rewards`
- [x] `POST /api/rewards/{reward_id}/redeem`
- [x] `POST /api/stars/actions`
- [x] `POST /api/stars/adjust`
- [x] `POST /api/subjects`
- [x] `POST /api/tags`
- [x] `POST /api/upload/batch-simple` （由 Pages 网关直接写入 R2，不转给后端）
- [x] `POST /api/upload/file` （由 Pages 网关直接写入 R2，不转给后端）
- [x] `POST /api/words`
- [x] `POST /api/words/batch`
- [x] `POST /api/words/print-pdf`
- [x] `POST /api/words/review/start`
- [x] `POST /api/words/review/submit`
- [x] `PUT /api/achievements/{achievement_id}`
- [x] `PUT /api/error-books/{error_book_id}`
- [x] `PUT /api/knowledge-points/{kp_id}`
- [x] `PUT /api/practice-sets/{practice_set_id}`
- [x] `PUT /api/practice-sets/{practice_set_id}/review-images`
- [x] `PUT /api/questions/{question_id}`
- [x] `PUT /api/rewards/{reward_id}`
- [x] `PUT /api/stars/actions/{action_id}`
- [x] `PUT /api/words/{word_id}`

## 两级知识点改造新增/调整（2026-11-10）

- [x] `GET /api/knowledge-points/tree`：返回两级树与 `taxonomy_version`，必须注册在 `/{kp_id}` 之前。
- [x] `GET /api/knowledge-points`：平铺响应增加 `level`、`parent_id`、`parent_name`、`code`、`sort_order`、引用计数；支持 `level`、`parent_id`、`keyword`、`include_legacy`。
- [x] `POST/PUT/DELETE /api/knowledge-points`：改由 `cloudflare/src/knowledge.py` 实现；触发器兜底层级、学科、移动与删除引用约束，错误码 `KP_*` 映射 409/422。
- [x] `GET /api/questions`：新增 `knowledge_parent_id`、`knowledge_point_id`、`unclassified`；旧 `knowledge_point` 改为精确 `name_key` 匹配，不再子串匹配。
- [x] `POST/PUT /api/questions`：新增 `knowledge_point_ids`、`primary_knowledge_point_id`、`knowledge_revision`；响应增加 `knowledge_points`、`knowledge_revision`、`legacy_knowledge_point`。
- [x] `POST/PUT /api/questions`（2026-11-22）：保存后题干 `parsed_question` 和原题文字 `original_text` 都为空时返回 422"题干不能为空"；修改时没带的字段按库里旧值算。
- [x] `GET /api/questions/filter-options/{subject_id}`：增加 `knowledge_point_options`、`knowledge_modules`，旧 `knowledge_points` 保留供过渡。
- [x] `GET /api/practice-sets/{id}`：条目增加 `knowledge_points`、`knowledge_revision`、`legacy_knowledge_point`；阅读条目改用 `topic`。
- [x] `POST /api/practice-sets/{id}/mark-reviewed`：支持 `question_knowledge` 并在同一批次写入分类；响应返回更新后的题目知识点。
- [x] `POST /api/words/{word_id}/audio` 与所有写请求：维护开关开启时 Bearer 写入同样返回 503；音频缓存未命中不写 R2。

## 考点卷（项目 3，2026-11-12）

- [x] `GET /api/practice-sets/targeted/status`：待批改卷子数量，以及每个科目最近一份考点卷的题量、分法和抽查数（出卷页预填用）。
- [x] `POST /api/practice-sets/targeted/plan`：按科目、题量（1–90）、分法（`spread` 均布 / `focus` 集中）、抽查数、是否包含低年级，算出入选清单（每题带入选原因、考点、模块、`has_figure`）和每个考点的备选题；没有可出的题时返回空清单与 `shortfall`，不写库。
- [x] `POST /api/practice-sets/targeted`：按预览清单创建考点卷（`kind='targeted'`，`question_type='mixed'`），空清单返回 422。
- [x] `POST /api/practice-sets/targeted/{id}/prepare`：为下一道要用相似题的行生成相似题（每次最多一次模型调用和一次公式校验）；失败返回 502 且该行保持未准备，带 `fallback` 改用原题；卷子已删除返回 404，已批改返回 409。
- [x] `POST /api/practice-sets/targeted/{id}/reroll`：给某一行换一道题或重新生成相似题，规则同 `prepare`。
- [x] `POST /api/practice-sets/{id}/mark-reviewed`（改动）：错题练习的批改支持逐题 `skip_reason`（`not_done` / `bad_question`）、`grading_revision` 乐观锁（过期返回 409）和重复提交不重复计数；响应增加 `grading_revision`、`points`（考点变化）、`newly_mastered`、`graduated`（本次毕业的题号）。不再记录错因。
- [x] `GET /api/practice-sets/{id}`（改动）：条目增加 `number`（卷面题号）、`form`、`reason`、`analysis`、`explanation`。
- [x] `POST /api/practice-sets/{id}/generate-pdf`（改动）：考点卷按模块分组、题号连续，答案页标注"原题 / 相似题"和入选原因，仍沿用指纹缓存。

## 批改识别预批（2026-11-12）

- [x] `POST /api/practice-sets/{id}/recognize/page`：请求 `{index}`（`review_images` 里的照片序号，服务端按序号取路径，不接受前端传路径），普通模式读一张照片，返回 `{index, text}`。照片找不到 404；识别主机不可用、忙、读不出来 503（前端改为手动批改）；单词、阅读练习 422。不写库。
- [x] `POST /api/practice-sets/{id}/recognize/judge`：请求 `{pages: [{index, text}]}`；题号、题目、标准答案由服务端从库里取，调一次模型，返回 `{items: [{id, number, student_answer, verdict, page}]}`（`verdict` 为 `right` / `wrong` / `unsure`，每题一项，漏掉的补成 `unsure`）。手动组的卷子打印后删过题（题号可能和纸上不一致）409；模型出错 502；单词、阅读练习 422。识别文字和结果都不写库。
- [x] `GET /api/practice-sets/{id}`（改动）：错题练习的条目增加 `shown_form`（卷面上印的是 `original` 原题还是 `similar` 相似题）。

## 每周周报（项目 4，2026-11-20）

- [x] `GET /api/weekly-reports`：各期简表（只列已算出数字的期，新的在前），每项 `id`、`number`、`monday`、`sunday`、`status`；`due` 为真表示最近一期还没做完，页面据此补做。
- [x] `GET /api/weekly-reports/{id}`：一期的完整内容（`facts` 数字、`text` 文字）；不存在 404。
- [x] `POST /api/weekly-reports/advance`：把最近一期推进一步（算数字 → 写文字），返回 `{id, status, busy}`；`busy` 为真表示这一步正被别人做着。这是写请求，维护开关开启时返回 503；它不清统计缓存（`auth.py` 已豁免）。定时任务（`*/10 12 * * sun`，UTC，即北京时间周日 20:00–20:50）走同一套推进逻辑，不经过这个接口。

## 界面整合（项目 5 第 3 步，2026-11-21）

- [x] `GET /api/home`：首页一次取齐，字段 `review`（待核对数和最新待核对卷子）、`grading`（待批改）、`targeted`（最近一份考点卷时间）、`words`（到期单词数）、`streak_days`（连续天数）、`week`（这一周：直接用周报的计算函数，含录题、卷子、默写天数、进步与退步考点）、`sky`（星空三个数）。
- [x] `GET /api/stats/words`：单词学情（原 `analytics.py` 里单词部分，学情页的"单词"标签使用）。
- [x] `GET /api/practice-sets/targeted/status`（改动）：`pending_count` 不再限 30 天，和练习中心列表里的待批改一致。
- [x] 已删除：`POST /api/questions/batch-similar`；`GET /api/stats/summary`、`/api/stats/overview`、`/api/stats/knowledge-points`、`/api/stats/analysis/full`；`POST /api/stats/analysis/llm`。

## 翻一翻（项目 5 第 4 步，2026-11-21）

- [x] `GET /api/flip/today`：今天这一组还没翻的卡片，返回 `{total, done, cards}`；`total` 是今天总张数，`done` 是已翻张数，`cards` 每项 `id`、`subject_name`、`point_name`、`parsed_question`、`images`、`wrong_answer`、`answer`、`analysis`、`analysis_image`。每天最多 8 张，候选是已核对、未删除、未毕业且有题干或原图的错题（所有学科、年级），选题规则见 `cloudflare/src/flip_model.py`。
- [x] `POST /api/flip/{question_id}`：请求 `{result}`，`result` 为 `remember`（我记得）或 `forget`（我忘了）；同一题同一天只记一次，重复提交不再写入；题目不在候选范围（不存在、未核对、已删除、已毕业、无题干也无原图）返回 404，`result` 非法返回 422；返回今天的 `{done, total}`。只写 `flip_log`，不影响考点掌握度和错题毕业。
- [x] `GET /api/home`（改动）：增加 `flip: {total, done}`（今天的进度），`week` 增加 `flip_days`（本周翻过卡片的天数）。
- [x] 每周周报（改动）：`facts` 增加 `flip: {days, cards}`（翻了几天、几张）；改动前生成的旧周报没有这个字段。
