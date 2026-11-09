# EasyFix Cloudflare 迁移与运行记录

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
