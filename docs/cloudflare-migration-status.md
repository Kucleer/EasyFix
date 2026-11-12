# EasyFix Cloudflare 迁移与运行记录

## 六年级目录与逐题回填完成（2026-11-10，北京时间）

- 根据用户后续明确授权，已完成六年级 366 道有效题（数学 220、英语 146）的逐题审核与正式回填；18 个一级模块、75 个二级考点、574 条关联，六年级未分类 0。
- 五年级 206 道题及其原标签、所有作答记录未改；既有共享目录原行保留。一级统计与二级下钻、全部 366 道题正式 API 回读通过，taxonomy_version=6，write_maintenance=0。
- 已备份并完成逐字段核验，详情、数量口径、备份校验与限制见 `docs/grade6-knowledge-backfill-status.md`；公开目录见 `cloudflare/scripts/knowledge_grade6_catalog.json`。私有逐题映射和执行 SQL 未提交。
- 这是上一次“功能与结构上线、分类待回填”之后的实际数据完成记录；应用代码未改，不重复部署 Worker / Pages。

## 两级知识点正式发布记录（2026-11-10，北京时间）

- 用户授权合并、推送和部署，并明确接受单用户维护期间在途写入风险；事务内门禁未实现，不以本次成功验证宣称该风险消失。
- 用户限定数据处理范围为六年级。0009 追加 schema 已在远端执行，仅对 grade=6 复制原标签到 legacy_knowledge_point；没有执行任何未经审核的逐题分类映射。非六年级题目未回填分类。
- 功能分支 `codex/knowledge-hierarchy-20261110` 已推送，分支提交 `c9d4e280`；合并并推送 main 的部署提交为 `4ad3e03d`。
- 发布 A（仅维护保护）：Worker `84d9b752-1b28-4696-b819-f928518ef293`，由合并前 main 的源码加本次 auth/media 构建；维护开启后 Bearer POST 返回 503，GET 返回 200。
- 发布 B：Worker `c8639a41-e616-4b63-93db-ca3e1d25b7b8`；Pages 生产部署 `6bd68197-d6b7-49c4-a6c2-4fd31209bbe8`，来源 commit `4ad3e03`。正式入口仍为 https://easyfix-bl2.pages.dev 。PDF 模板未改变，内部 PDF Worker 未重发。
- 维护期间备份：`backups/knowledge_hierarchy_20261109T193932Z/remote.sql`，UTC 文件名对应北京时间 2026-11-10；SHA-256 为 `a1bb553420d2f5ff61ff41ea0cace45dc46a17ce909b24cb07c72aee2f9111bb`。Time Travel 信息保存在同目录私有文件中，未执行恢复。
- 同目录 `after/database.sqlite3`、`integrity-verification.json`、`consistency.json` 记录迁移回读：question 595、knowledge_point 84、subject 4、practice_set 216、practice_set_question 1101、word 1280、reading_passage 109、reading_question 436，全部原有行与原有列逐字段一致；新分类关联为 0。
- 有效题：五年级 206、六年级 366。六年级 361 道非空原标签保存快照，5 道原为空；非六年级 legacy 列无回填。新接口可用只读兼容回退展示其他年级原标签，不改库。
- 一致性检查无阻断错误；27 条旧错误类型配置及 206 条非六年级 legacy 未复制为已知过渡警告，均保留原数据。
- 本地 19 项不变量、7 项 HTTP 测试通过，六年级回填范围额外校验通过，`prepare_cloudflare_frontend.py` 构建通过。正式 health、题目列表、知识点树、知识点统计、完整分析和学科汇总返回 200。
- 关闭维护后完成实际两级目录、六年级临时题关联、清空与版本递增冒烟，临时题与目录均软删除，记录为 `tmp/knowledge-release-smoke.json`；清理后有效题数仍为五年级 206、六年级 366。write_maintenance 已恢复 0。
- **本次交付为功能与结构上线，非教材分类整理完成。** 正式两级目录暂未填充，历史题仍待审核分类，模块统计当前为空；原标签保留。后续只能对六年级执行经审核的目录与逐题映射，不使用旧关键词候选结果直接入库。
- 本次未提交工作区其他修改、生成目录、备份或密钥；没有写旧 PostgreSQL/MySQL，没有升级 Workers Paid。

更新时间：2026-11-09（北京时间）。**已完成业务入口切换，云端 D1 / R2 为正式数据源。**

## 入口与资源

- 正式入口：https://easyfix-bl2.pages.dev ，沿用原访问密码；登录后才能读取业务数据与附件。
- 没有购买域名或升级 Workers Paid。账号内暂无自有域名，使用免费 Pages 域名。
- 账号：52ff92165ba654aa8260a45ded30e1ef。
- Pages 项目 easyfix：Vue 静态资源、会话验证、R2 附件直读、后端服务绑定。
- Python Worker easyfix：FastAPI 与异步 D1；不开放 workers.dev / preview_urls。
- D1 easyfix：2de427ad-42be-412f-8afe-dfedd94f1c6a。
- 私有 R2 easyfix：原图、历史 PDF、音频、历史上传目录。
- 内部 Worker easyfix-pdf：KaTeX 校验、Browser Run PDF，无公开路由。

## 最终数据与完整性证据

2026-11-09 02:33 UTC 冻结旧 PostgreSQL 写入，关闭该库现有客户端连接。最终同步保留原主键、关联、软删除标志、时间、公式反斜杠与原文换行。

| 项目 | 结果 / 本地证据 |
| --- | --- |
| 最终原生备份 | `backups/easyfix_20261109T023323_672586Z`，897 个备份文件大小与 SHA-256 核对通过 |
| 一致性数据快照 | `backups/cloudflare_d1_20261109T023329946287Z/database.sqlite3` |
| 远端回读核对 | 同目录 `remote.sql`、`final-verification.json`：28 张表、8,292 条源记录逐主键逐字段一致，有效数量一致，完整性 / 外键检查通过 |
| 附件清单 | `backups/cloudflare_files_20261109T023331268951Z.json`：900 文件，共 169,864,242 字节 |
| 附件远端核对 | `backups/cloudflare-file-verification.json`：900 / 900 下载后大小与 SHA-256 一致，失败 0 |
| 切换状态 | `backups/cloudflare-cutover-state.json`、`backend/config/cloudflare-cutover.json` |

表中错题 575、单词 1264、练习 212、阅读短文 109 为包含历史软删除的源记录数；页面只显示有效记录。知识点最终为 84 条，已包含迁移期间新增的 50 条。

900 个文件包括 107 张图片、684 个音频、104 个其他应用文件（主要 PDF）、5 个文本文件；不是 900 张图片。历史根目录与嵌套上传目录保留归档映射；含特殊标点的音频名用哈希键保存，原文件名和映射仍在清单中。

验证期间创建的额外业务记录全部软删除，源激励余额、复习进度与源记录内容在最终同步时恢复。正式开放后的登录写入验证只创建并软删除临时标签，另外保留了一张 1 像素上传验证图及正常审计日志。

备份和导出含学生数据、配置及密钥，均不作为公共静态资源部署。原生备份已检查文件完整性，尚未做独立 PostgreSQL 恢复演练。

## 已完成任务与验证范围

- [x] 原生备份、源数据盘点、D1 结构转换、附加软删除字段及索引。
- [x] 102 个旧业务路由完成适配，逐项表见 `cloudflare-api-checklist.md`；兼容不等于每个边界输入都已穷举测试。
- [x] 登录 Cookie、匿名访问拦截、来源校验、私有附件、配置密钥脱敏。
- [x] 错题与单词增改删、标签关联、批量单词导入、公式入库回读。
- [x] 单词复习提交和重复提交幂等验证，删除验证练习后计数回滚。
- [x] PDF 实际生成、下载、重复使用；页面图像检查中文、分数和次方渲染。
- [x] 已配置的 LLM 实际生成学习报告，随后软删除验证报告。
- [x] 缓存音频播放、图片实际上传并下载逐字节核对。
- [x] 浏览器检查首页、错题、单词、阅读、练习、报告、成就、知识点分析真实数据。
- [x] 最终停写同步、远端逐字段核对、900 个附件哈希校验。
- [x] `MIGRATION_READY=true`，浏览器 Cookie 写入及软删除验证通过，健康检查报告切换完成。
- [x] 旧本地 Vue 入口 GET 跳转至云端，旧 API 返回迁移地址；旧库新连接默认只读。
- [x] Python 编译检查、Vue 生产构建；构建仅有体积分包提示。

## 免费额度与减少调用的实现

- 统计采用 D1 SQL 聚合和代码计算，不用 LLM 计算事实数字，也不启动原 SQLAlchemy 全表对象算法。
- 浏览器 GET 请求去重与短时内存缓存；分类缓存 5 分钟，统计 30 秒，一般查询 10 秒，成功写入即失效。
- 后端统计缓存 60 秒，读取共享版本号避免跨实例写入后沿用旧统计。
- 批量导入、批改和计数回滚用 JSON SQL 批处理；标签与分类关联合并查询，避免逐记录调用。
- 静态资源、登录会话校验及附件读取由 Pages 处理，附件直接访问 R2；不会每张图都经过 Python Worker。
- 音频保留已有缓存，缺少时首次播放生成，不再批量生成未播放的单词。
- PDF 按打印内容指纹复用，内容未变不重新启动浏览器；公式校验用 KaTeX 代码，不启动浏览器。
- LLM 仅在主动请求分析、报告、类似题或生成短文时调用，沿用原模型配置；模型服务自身费用取决于已有提供商。

当前数据约 1.84 MB，附件约 170 MB，未开通 Workers Paid。免费方案有请求、CPU、D1 和 Browser Run 上限，不能承诺任意流量下无限免费；PDF 所用 Browser Run 免费额度目前为每天 10 分钟，额度耗尽后需等待重置，已缓存 PDF 仍可下载。

官方额度资料：https://developers.cloudflare.com/workers/platform/pricing/ 、https://developers.cloudflare.com/browser-run/pricing/ 。

## 日常部署

生产逻辑在 `cloudflare/src/`，旧 `backend/app/` 是保留的本地版本。修改旧后端不会自动修改云端。不要再向旧 PostgreSQL / 本地 MySQL MCP 写生产数据。

Wrangler 固定 4.158.0。可先执行 `npm install --prefix cloudflare`；`node cloudflare/tools/cli.cjs <命令>` 自动选用固定版本并把授权、日志放在被忽略的 `tmp/cloudflare-config`。授权失效时用该包装器运行 `login`。

```text
# 仓库根目录：后端代码更新，现有 Python 依赖已打包时
python -m compileall -q cloudflare/src
node cloudflare/tools/cli.cjs deploy --config cloudflare/wrangler.jsonc

# 前端构建（只清理隔离生成目录，不改写其他资源）
python backend/scripts/prepare_cloudflare_frontend.py

# 转入 cloudflare/pages 执行，Pages CLI 不接收自定义 --config
node ../tools/cli.cjs pages deploy ../../tmp/cloudflare-pages-build --project-name easyfix --branch main --commit-dirty=true

# 数据库只追加审核过的迁移，不再次导入旧源快照
node cloudflare/tools/cli.cjs d1 execute easyfix --config cloudflare/wrangler.jsonc --remote --file cloudflare/migrations/新增迁移.sql --yes
```

变更 Python 依赖时先从 `cloudflare/` 运行 `uv run pywrangler deploy`，将 `UV_PYTHON_INSTALL_DIR`、`UV_CACHE_DIR` 指向本仓库 `tmp/uv-python`、`tmp/uv-cache`，并保持同一盘符，避免 Windows Pyodide 虚拟环境跨盘失败。授权路径需保持上述 XDG_CONFIG_HOME。仅修改源码不必重复安装依赖。

密钥准备脚本 `prepare_cloudflare_secrets.py` 会保留本机现有随机会话 / Agent 密钥，仅生成忽略文件；`secret bulk` 上传文件路径，不打印内容。不要随意重建会话密钥；Pages 与后端 SESSION_SECRET 必须一致。正式写入开关 MIGRATION_READY 已配置为 true，不要在正常部署时关闭。

`sync_cloudflare_d1.py` 是本次停写切换使用的覆盖同步工具，**切换后禁止重新运行旧快照同步**，否则会覆盖后续云端修改。`prepare_cloudflare_analytics.py` 是早期适配探索脚本，不属于正式部署流程。

## 备份与恢复

云端正式备份先在 Cloudflare 关闭业务写入并暂停 Agent 写入，再导出 D1 与 R2 清单 / 对象；D1 可用 `export_remote_cloudflare.py <新建备份目录>` 下载完整 SQL，临时签名链接不输出。R2 对象应按新清单逐项下载并比对 SHA-256。旧 PostgreSQL 备份只覆盖切换前数据。

代码故障可回滚 Worker / Pages 部署，D1 与 R2 数据不随代码回滚。数据恢复必须先保存当前云端快照并审核差异，禁止直接导入旧数据库。

`python backend/scripts/cloudflare_cutover.py status` 查看旧入口状态。`rollback` 只恢复旧 PostgreSQL 原只读设置并撤销旧入口标记，**不会把云端新增数据复制回旧库**。云端已有新写入时，必须先停写并迁回新增数据，核对后才能使用此命令，避免数据分叉。还需重启旧后端 / 前端。当前不执行回滚。

## 用户需要操作

现在打开正式入口，使用原密码登录即可，不需要再开通付费服务或填写额外迁移配置。以后如需自有域名，可将自己持有的域名接入 Cloudflare 再绑定 Pages；这是可选工作，不影响当前使用。

## 变更记录：两级知识点改造（2026-11-10，发布前的实施记录；正式发布与回填结果见文首两节）

- 分支：`codex/knowledge-hierarchy-20261110`；实施规格见 `docs/knowledge-hierarchy-final-plan.md`，实现说明见 `docs/knowledge-hierarchy-implementation-notes.md`。
- 追加迁移 `cloudflare/migrations/0009_knowledge_hierarchy.sql`：`knowledge_point` 增加 `code/name_key/level/parent_id/sort_order/updated_at`；`question` 增加 `knowledge_revision/legacy_knowledge_point`；新增 `question_knowledge_point`、`knowledge_assert`；部分唯一索引与 `KP_*` 触发器。
- 新增正式接口 `/api/knowledge-points/tree`；知识点 CRUD 移入 `cloudflare/src/knowledge.py`，不再由通用 `catalog.py` 注册。
- 单题保存、批量入库与练习批改统一通过 `write_guard` / `knowledge_assert` 与 `question_knowledge_point` 在同一 D1 batch 内写入。
- 统计改为一级模块口径：`knowledge_stats.py` 复用 D1 SQL 聚合，正确率取 `practice_set_question` 最终批改状态；学习报告模块指标由服务端写入。
- 维护开关：D1 `runtime_config` 表 `write_maintenance`（`1/true/on/yes` 为开启）。开启后所有非 GET/HEAD/OPTIONS 请求（含 `Bearer ACCESS_TOKEN`）返回 503；`/health`、`/login`、`/api/auth/verify-password` 不受影响。音频缓存未命中时返回 503，不写 R2。`MIGRATION_READY` 语义不变，不用于维护停写。
- 维护开关切换示例（不修改 `MIGRATION_READY`）：
  ```text
  node cloudflare/tools/cli.cjs d1 execute easyfix --config cloudflare/wrangler.jsonc --remote --yes \
    --command "INSERT INTO runtime_config(name,value,deleted,updated_at) VALUES('write_maintenance','1',0,CURRENT_TIMESTAMP) ON CONFLICT(name) DO UPDATE SET value='1',deleted=0,updated_at=excluded.updated_at"
  ```
  关闭时将 `'1'` 改为 `'0'`。开关状态可用只读命令核对。
- 迁移工具（均默认只读或只生成 SQL，不直接写生产）：
  - `python cloudflare/scripts/knowledge_preflight.py --snapshot <sqlite快照>`
  - `python cloudflare/scripts/knowledge_backfill.py --seed cloudflare/scripts/knowledge_seed_modules.json --mapping <审核映射> --snapshot <sqlite快照>`
  - `python cloudflare/scripts/knowledge_consistency_check.py --snapshot <sqlite快照>`
  - `python cloudflare/scripts/knowledge_invariants_test.py`
- 发布顺序仍按方案第 12 节：先维护开关小版本（发布 A），停写排空并记录 Time Travel 书签，应用 0009 与回填，运行一致性校验，再发布新 Worker 与 Pages（发布 B）。本次未执行生产迁移、未开启维护开关、未修改 `MIGRATION_READY`。
- 已停用会覆盖云端源码的生成脚本：`prepare_cloudflare_prompts.py`、`refine_cloudflare_queries.py`、`prepare_cloudflare_analytics.py`。`annotate_english_knowledge.py`、`import_math_formula_photos.py` 已增加只读提示，不能作为生产写入通道。

## 变更记录：词组默写优化（2026-11-10，已发布）

- 分支：`claude/project-optimization-plan-b28c5c`，发布提交 `310f70d9`。设计见 `docs/superpowers/specs/2026-11-10-phrase-dictation-design.md`，计划见 `docs/superpowers/plans/2026-11-10-phrase-dictation.md`。
- 迁移 `cloudflare/migrations/0010_phrase_focus.sql` 已在正式 D1 执行：`word` 增加 `entry_type/focus_spec/focus_status/focus_updated_at/dictation_level`，`word_review_log` 增加 `token_results/dictation_level`，并回填词条类型与档位初值。只加列，不改已有计数、间隔、阶段和日志。
- 执行前备份：`D:/code/easyfix/backups/phrase_focus_release_20261110T083549Z/`（D1 完整导出 `remote.sql`，SHA-256 `b7d10e0b6732b6251e259cfb501359ba909480a1ab2cf23e8a89d8858579450c`；同目录有 Time Travel 信息、迁移输出、迁移前后核对结果、部署输出）。未开启维护开关；迁移先在备份副本上演练通过。
- 核对：迁移前后词条 1280 条、复习次数合计 2188、正确次数合计 1657、复习日志 2225 条均一致；抽查 5 条词条的计数、间隔与备份相同。有效词条中词组 222 条、单词 580 条；`focus_status` 全部为 `none`，即上线后在父母点击"标注词组重点"之前行为不变。
- Worker：新版本 `d0df1517-fad2-4ff7-b4ff-89eda4204a29`，上一版本 `c8639a41-e616-4b63-93db-ca3e1d25b7b8`（回滚用）。Pages：新部署 `d061cbde`，上一部署 `6bd68197`。
- 发布后只做了无需登录的核对：`/health` 200、未登录访问接口 401、登录页 200、新前端资源可访问。登录后的功能（默写各档位、标注、重点编辑、打印）和手机真机输入尚未在正式环境验证。
- 本机情况：`tmp/cloudflare-config`、`cloudflare/python_modules`、`cloudflare/node_modules` 在本次使用的工作树里都不存在。本次用系统默认位置的 Wrangler 登录（未经 `cloudflare/tools/cli.cjs` 包装器），Wrangler 4.158.0 取自 `D:/code/easyfix-cloudflare-inspect/cloudflare/node_modules`；Python 依赖用 `uv run pywrangler sync` 按 `pylock.toml` 重新打包（依赖版本未变）。`pywrangler` 1.17.9 要求 uv ≥ 0.13.4，本次在 `tmp/uv-new` 单独安装了 uv 0.13.7，未改动系统 uv。本机代理访问 Cloudflare API 不稳定，命令需去掉代理环境变量直连。
- 该分支截至提交 `7cc0c5b9` 的内容已合并到 `main` 并推送远端。
- 追加发布（同日，提交 `5671d5ed`）：未标注的词组手动选"提示"档也给每个词首字母（占位符照常显示，打印同理），以提示档答对不授予"牢记"；不限类型的混合抽题按 60% 单词 + 40% 词组，一方不足时由另一方补足。无数据库变更。Worker 版本 `9e1b49c8-5da7-4f30-a071-cebc84fc41fc`（上一版本 `d0df1517`），Pages 部署 `82bc4e43`（上一部署 `d061cbde`）。已用当日正式数据副本实际抽题验证；登录后的页面未实测。
- 追加发布（同日，提交 `7da9f971`）：自动模式下未标注的词组走 提示 → 完整 两级（先带首字母，默写答对升为完整默写，完整默写答错退回提示）；"牢记"仍只在完整默写答对时授予。无数据库变更。Worker 版本 `47608c9c-f681-4d66-8ea4-3d4e045fa4df`（上一版本 `9e1b49c8`），Pages 部署 `68875cb9`（上一部署 `82bc4e43`）。已用当日正式数据副本跑完整一轮验证；登录后的页面未实测。
- 追加发布（同日，提交 `db6b82ed`，仅前端）：默写格子样式统一——给出的字母与填写格同宽同字号并改用主题色，配色改用主题变量，词整体换行，手机窄屏格子收窄。Pages 部署 `6a65e573`（上一部署 `68875cb9`）。本地用真实组件在桌面与 375px 宽度下核对过布局；正式环境登录后的页面未实测。
- 追加发布（同日，提交 `f310ab35`）：默写（含听力）答错后显示订正卡——正确答案标红错处、显示孩子所写内容、照抄一遍再继续（不计分，可跳过）；"完成"按钮只在最后一题答完后显示。单词练习详情页改为错词优先的紧凑列表（逐行标红、累计错误次数、对的词压缩为标签），新增"重练错词"和"打印错词"。后端：练习详情返回 `token_results`、`dictation_level`、`error_count`（一次批量查询），`/api/words/print-pdf` 支持 `word_ids`。无数据库变更。Worker 版本 `18902ab4-19a3-4c57-8564-c42a4b47cc37`（上一版本 `47608c9c`），Pages 部署 `1b33ec9b`（上一部署 `6a65e573`）。完整答题流程与"重练错词"跳转未在浏览器实测。
- 追加发布（同日，提交 `320297c7`，仅前端）：复习弹窗重新设计（"安静专注"方向）——答题时去掉标题栏，顶部一行为题号、进度条、用时；字母格改为带边框的圆角方格；答错订正改为"正确写法 / 你写的"左右并排；底部左侧"终止答题"、右侧主操作；弹窗高度随屏幕、单屏显示。Pages 部署 `cead4a63`（上一部署 `1b33ec9b`）。本地用模拟接口在 1280×720 与 390×760 下走过答题与订正流程；正式环境登录后的页面未实测。
- 追加发布（同日，提交 `84282fc4`，仅前端）：长答案（超过 22 个字符）的订正卡改为"正确写法 / 你写的"上下各占一行，抄写与答题的字母格用小一号的紧凑尺寸，弹窗高度上限提到 640，内容超高时从顶部开始显示而不再裁掉释义。Pages 部署 `9f7e20c9`（上一部署 `cead4a63`）。本地用 44 和 50 字符的两条长内容在 1280×720 实测无滚动条，44 字符那条另在 390×760 实测；正式环境登录后的页面未实测。
- 追加发布（同日，提交 `7cc0c5b9`，仅前端）：单词练习答题中按 Esc 不再直接关闭，改为二次确认；确认后放弃本次练习、不提交任何结果，取消则回到答题并保留已填内容。设置页与结果页按 Esc 照旧直接关闭。Pages 部署 `c35b9e7d`（上一部署 `9f7e20c9`）。本地用模拟接口实测取消与确认两条路径，确认退出后提交接口调用 0 次；正式环境登录后的页面未实测。放弃时后端在开始练习时登记的空场次记录仍保留，不参与统计。

## 变更记录：六年级数学目录追加四个考点（2026-11-11，已写入正式库）

- 起因：项目 1 的录入规范实测时，第二章"简单的代数式"的作业题在目录里找不到对应考点。只读核对确认正式库目录与种子文件 `cloudflare/scripts/knowledge_grade6_catalog.json` 逐条一致（93 条），缺口来自目录是按已有错题整理的。
- 用户同意后追加：`M6-ALG-03 用字母表示数与列代数式`、`M6-ALG-04 代数式的书写规范`、`M6-ALG-05 代数式的意义`、`M6-PAT-05 图形与数字排列规律`。按一页真实作业（2.1 用字母表示数）出现的题型起草，不是凭记忆编的整章目录。
- 做法：种子文件先加四条并提交（`dcf3e413`），用 `knowledge_backfill.point_sql` 生成按 code 幂等的插入语句，先在本机内存库演练（含重复执行），再用 Wrangler 执行；同时把 `taxonomy_version` 和 `data_revision` 各加 1。
- 核对：执行前 179 行、二级考点 75 个、最大 id 179、`taxonomy_version=6`、`data_revision=135`；执行后 183 行、二级考点 79 个、新行 id 180–183、`taxonomy_version=7`、`data_revision=136`。题目数 572 不变，没有改动任何题目和关联。
- 仍然存在的情况（未处理）：83 条旧的自由文本考点（层级为空）未清理；42 道六年级数学题学期为空；五年级 206 道题未归类。

## 变更记录：录入规范与卷子记录（项目 1，2026-11-11 已上线）

- 分支 `claude/project-optimization-plan-b28c5c`；设计 `docs/superpowers/specs/2026-11-10-intake-and-papers-design.md`，计划 `docs/superpowers/plans/2026-11-10-intake-and-papers.md`。
- 迁移 `0011_intake_papers.sql`：新增 `app_user`、`student`、`paper`；16 张表加 `student_id`；`question` 加卷子关联、题号、孩子的答案、核对状态等列；旧题按学科+年级+学期回填"历史作业"卷子（全是已删除题的组对应的卷子同样软删除）。执行前把 42 道六年级数学学期为空的题补成上学期。
- 备份 `backups/intake_release_20261110T192803Z/remote.sql`（SHA-256 `076fae1c30a187c34e2248918c0ca171f04df96e3d771576131bea7832eb7842`），同目录有演练结果、Time Travel 书签和每一步输出。维护开关开启期间执行，核对与演练一致：596 题（572 未删除）全部 approved、8 条历史卷子（3 条软删除）、题目与卷子的学科年级学期全部一致、其余表行数不变。
- 部署：Worker `518f7ca0-9df0-46dd-86b8-c599c30c65fa`（上一版本 `18902ab4`），Pages `3e13883a`；录入小工具的 User-Agent 修复后，重设 Agent 访问口令（Worker 与 Pages 的 `ACCESS_TOKEN` 同时更新，Pages 重新部署 `f63cd022`）。
- 录入技能安装在 `~/.claude/skills/easyfix-intake/` 与 `~/.agents/skills/easyfix-intake/`，配置在 `~/.easyfix/intake.json`。
- 验收：登录后首页、错题、统计、待核对、卷子页、"加载更多"均正常；Codex 实际录入一份 8 页作业（41 题、2 题待核对、每题照片对应正确页）。未验收：Claude 的一次录入没有留下记录；待核对页三个按钮和手机端未由用户实测。

## 变更记录：考点掌握度与知识星空（项目 2，2026-11-11 已上线）

- 设计 `docs/superpowers/specs/2026-11-11-knowledge-starmap-design.md`，计划 `docs/superpowers/plans/2026-11-11-knowledge-starmap.md`，种子审阅清单 `docs/superpowers/specs/2026-11-11-knowledge-starmap-seed-review.md`。
- 迁移 `0012_starmap.sql`（教材节、节与考点对应、先学后学连线、手动调整表，考点加 `learn_grade`）、`0013_starmap_seed.sql`（英语新语法体系 12 个模块 56 个考点、沪教版六上数学 13 节 22 条对应、73 条连线，由 `build_starmap_seed.py` 生成）；英语错题重新打标由 `starmap_retag.py` 从被忽略的映射文件生成（238 道：222 道挂语法考点、16 道词汇题不挂；旧 `E6-` 考点全部软删除）。运行配置 `starmap` 设数学进度 4.2。
- 备份 `backups/starmap_release_20261111T072641Z/remote.sql`（SHA-256 `0be5f6b674fe824e7ffaae4f2a43aa5ee5de241ab038ecf460f67acd14a5da9d`），同目录有演练结果、映射和打标 SQL、Time Travel 书签与每一步输出。维护开关开启期间执行，核对与演练一致：613 道未删除题不变、数学关联 396 条不变、旧英语考点 0、新英语考点 56/12、节 13、对应 22、连线 73。
- 部署：Worker `25235f69-5147-4ee1-ac00-c18d3dfcd582`（上一版本 `020fdb21`），Pages `6bee1586`。上线时按用户决定"照实显示"：数学 39 颗薄弱、3 颗一般；英语 3 颗已掌握。第一次读取已把当时已掌握的考点记为已看。
- 未验证：管理设置"知识星空"栏未在浏览器实测（本机环境没有访问密码那一步）；平板和手机布局不在本期范围。

## 变更记录：整页识别录入（2026-11-11 上线试用）

- 设计 `docs/superpowers/specs/2026-11-11-page-scan-intake-design.md`，主机端 `docs/superpowers/specs/2026-11-11-ocr-host-service-design.md`，计划 `docs/superpowers/plans/2026-11-11-page-scan-intake.md`，联调与调优记录 `docs/scan-intake-tuning-2026-11-11.md`。
- 迁移 `0014_scan_page.sql`（只新建 `scan_page` 表和索引）。执行前备份 `backups/scan_trial_20261111T111154Z/remote.sql`，在备份副本上演练：原有 40 张表结构和行数不变。
- Worker 绑定 `OCR_HOST`（Workers VPC 服务），密钥 `OCR_SHARED_KEY` 由用户填写；重扫开关 `SCAN_RESCAN` 未设置，即开启。
- 部署：Worker `50db82b1`（上线前一版 `54589127`），Pages `dd159130`（上线前一版 `a54a1ab2`）。分支 `feature/page-scan-intake` 尚未合并进 main。
- 联调与调优期间没有录入任何错题，题库前后 637 道（未删除 613 道）；联调和评测用的识别页 5–13 都已结束。
- 2026-11-11 晚：修公式显示（清洗时给裸公式加边界）、"不是错题"改为红色描边按钮并直接滑出、界面"孩子"改为"学生"。部署 Worker `fa75dcfe`、Pages `e2f6e886`。此前 Worker 部署连续 4 次被 Cloudflare 以错误 10021（"binding DB of type d1 failed to generate"）拒绝，配置未变、D1 正常，约 10 分钟后重试成功。
- 2026-11-11 晚：合并手机默写修复（分支 `fix/mobile-dictation-keyboard`，提交 `51b19f8f`：点方格时让隐藏输入框真正获得焦点以弹出软键盘，并兼容安卓键盘读不到按键字母的情况）到 `feature/page-scan-intake`，一起构建前端发布 Pages `ce0740e3`。后端未变（Worker `fa75dcfe`）。尚未在真手机（微信 / iPhone）上验证。
- 2026-11-11 晚：公式组件 `MathText` 竖直方向不再滚动（去掉分数旁边带上下箭头的小滚动条），发布 Pages `856f1f9a`。
- 2026-11-11 晚：按调优记录第 5 节的测量结果关掉重扫：Worker 密钥 `SCAN_RESCAN=off`（用密钥而不是配置文件里的变量，避免部署时覆盖控制台里的普通变量）。实测一页读图 12.8 秒 + 整理 7.6 秒，不再重扫。要恢复重扫，删掉这个密钥即可。

## 变更记录：考点卷与手机批改（项目 3，2026-11-12 已上线）

- 分支 `claude/targeted-paper-2026-11-12-dcd75f`，发布时代码提交 `560d41a4`；设计 `docs/superpowers/specs/2026-11-12-weekly-paper-design.md`，计划 `docs/superpowers/plans/2026-11-12-targeted-paper.md`。
- 迁移 `0015_targeted_paper.sql`（只加列）：`practice_set.kind`（默认 `manual`）、`practice_set.grading_revision`（默认 0）；`practice_set_question.form/reason/knowledge_point_id/skip_reason`；`similar_question.explanation`。
- 执行前备份 `backups/targeted_release_20261112T144006Z/remote.sql`（SHA-256 `62e6c6d49626ee188ed34e858ab0a3ebe2a5afeb90f1cde58702092524e508da`），Time Travel 书签 `0000008e-00000000-00005121-e21d6d9db51582ae1b50fdf7a0883858`；同目录有演练、核对脚本输出和每一步输出。未开启维护开关（只加列）。
- 演练与正式执行后核对一致：41 张表行数不变；错题 638、练习集 221、练习集题目 1116、相似题 7；221 份练习集全部为 `manual`、版本号 0；新列全部为空。
- 上线前核对（`targeted_preflight.py`，在演练副本上）：按新规则英语有 2 颗原来的绿星不再是绿色（分词作定语 0.55、待重做 3 道；特殊疑问句 0.15、待重做 24 道），数学无变化，用户同意照此上线；题干为空的错题 0；没批改的错题练习集 0；正式环境没有设置默认年级，选题不按年级筛。
- 部署：Worker `335a7e17-42f9-4c93-9261-4957d1a8a10d`（上一版本 `2af82122`）；PDF Worker `4405b7d6-9f71-44d5-9702-f789d43d13c3`（上一版本 `8afa5ed5`）；Pages `a58dd21c`（上一部署 `856f1f9a`）。
- 发布后只做了无需登录的核对：`/health` 200、未登录访问新接口 401、`/grade` 与 `/targeted-paper` 跳转登录、新页面资源可访问。
- 未验证（需登录）：真实 PDF 的分页、留白、公式和答案页；手机上批改一份卷子；拍照上传；星空页颜色。本机走查用的是假模型和 JSON 版 PDF 替身。
- 注意：错题练习的批改现在每次都经过 `write_guard`，维护开关开启时会返回 503（与其他写入一致）。
- 2026-11-12 晚：考点卷 PDF 的答题留白放大 1.5 倍（22.5/45/75mm），考点卷版式版本升到 4，已生成的考点卷 PDF 再次生成时按新间距重排。部署 PDF Worker `c2c5a68b`（上一版本 `4405b7d6`）、Worker `563c8d50`（上一版本 `335a7e17`）。
- 2026-11-12 深夜：批改识别预批与电脑手机共用批改页上线（设计 `docs/superpowers/specs/2026-11-12-grading-recognition-design.md`）。考点卷相似题提示词不再带孩子的错误答案；新增 `POST /api/practice-sets/{id}/recognize/page`、`/recognize/judge`（不写库、无迁移）；所有错题练习卷都在 `/grade/:id` 批改。从分支 `claude/grading-recognition-design-97c8d7`（`7984eaa`）部署 Worker `0f2d30dd`（上一版本 `563c8d50`）、Pages `5e3d1920`（上一版本 `a58dd21c`）。
- 发布后只做了无需登录的核对：`/health` 200、未登录调用两个识别接口 401、`/grade/1` 跳转登录。未验证（需登录）：用真实卷子在手机和电脑上各批一次；关掉识别主机走一遍兜底。本机走查用的是假识别主机和假比对模型。
