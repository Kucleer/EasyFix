# 每周周报（项目 4）交接说明

写于 2026-11-20。给接手实施的新对话看。讨论和设计是在另一个对话里完成的，那个对话的内容你看不到，需要知道的都写在这里和下面两份文档里。

## 1. 你要做什么

按实施计划把"每周周报"做出来：每周日 20:00 自动生成一期给孩子看的成长打卡式周报。

先按这个顺序读：

1. `CLAUDE.md`、`AGENTS.md`（项目规矩）
2. `docs/superpowers/specs/2026-11-20-weekly-report-design.md`（设计，已定稿）
3. `docs/superpowers/specs/2026-11-20-weekly-report-mockup.html`（样稿，用浏览器打开；它从 cdnjs 加载 ECharts，需要能上外网）
4. `docs/superpowers/plans/2026-11-20-weekly-report.md`（实施计划，10 个任务）
5. 本文

## 2. 现在的状态

- 设计、样稿、计划和本文都已提交在本地 `main`，**还没有推送到远程**。产品代码一行没动。
- 用户已经审过并通过了设计。计划写完后用户没有提修改意见，直接说要开新对话来跑。
- 正式环境当前版本：后端 Worker `de2e3208`，Pages `f9317fa8`（2026-11-19 上线，网关直接处理图片上传），PDF Worker `c2c5a68b`。
- 数据库最新迁移是 `0015`，本计划新增 `0016`。

## 3. 怎么执行

- 用户选的方式：**新对话、Opus 5.5 来跑**。计划的每个任务是否再配独立审阅，用户没有明确说；之前的建议是用 superpowers:subagent-driven-development（每个任务一个子代理实现、一个独立审阅者检查）。开工前用一句话向用户确认用哪种。
- 用 superpowers:using-git-worktrees 建工作树，分支名 `feature/weekly-report`，从本地 `main` 切出。**不要在 `main` 上直接改。**
- 主检出目录 `D:/code/easyfix` 可能同时有别的对话在用：不要 stash、reset、切换分支，只提交你自己改的文件。
- 任务 1–9 都在分支上做，不碰正式环境。任务 7 的第 5 步和任务 10 涉及正式环境，**每一步都要先得到用户同意**。

## 4. 已经定了的事，不要重新讨论

来源都在设计文档里标了【用户定】或【Claude 定】。最要紧的几条：

- 周报是"成长打卡"风格（样稿里的样子），图表用 ECharts。【用户定】
- 文字全部对孩子说（用"你"），鼓励为主，另附一句每期不重样的鼓励。【用户定】
- 文字里不出现爸爸、妈妈、父母、家长。【用户定】
- 周日晚上固定自动生成，不依赖手动。【用户定】
- 页面底部给父母的操作只是一个普通跳转链接，不做成按钮。【用户定】
- 要给后端打开历史日志（Workers Logs）。【用户定】
- 只夸真实做到的事：考点"变好"必须本周有做对的练习；父母手动调整掌握度不算变好，也不算错题毕业。【Claude 定，用户审过】
- 实现方式：后端自己带定时任务，每次只推进一步；打开页面时补做。【Claude 定，用户审过】

## 5. 这些情况要停下来问用户

- 想改兜底鼓励句（计划任务 4 里的 12 句）。这是孩子直接读到的话。
- 任务 7 第 5 步：本地验证不了后端入口，需要部署临时测试 Worker。
- 后端入口无法同时保留现有 HTTP 行为和定时入口（要换成设计第 4 节的方案二）。
- 上线前核对发现 Workers Logs 已经不在免费范围内。
- 任何需要偏离设计文档的地方，或者设计和计划互相矛盾的地方。
- 所有正式环境的操作：导出备份、执行迁移、部署 Worker、发布 Pages、推送远程。

## 6. 这台机器上的实际情况

这些是前几次发布踩出来的，文档里的命令有些在本机不能直接用。

- **Wrangler**：`cloudflare/tools/cli.cjs` 包装器需要 `tmp/cloudflare-config`，本机没有。实际用的是 `D:/code/easyfix-cloudflare-inspect/cloudflare/node_modules/.bin/wrangler`（4.158.0，已登录）。
- **代理**：本机设置了 `HTTP_PROXY` / `HTTPS_PROXY`。运行 Wrangler 的普通命令（部署、D1、R2）前要先 `unset HTTP_PROXY HTTPS_PROXY http_proxy https_proxy`，否则超时；只有 `wrangler tail` 相反，必须保留代理。
- **只读查正式库**（需要时）：`wrangler d1 execute easyfix --remote --config cloudflare/wrangler.jsonc --json --command "SELECT ..."`。只读查询可以做，写入必须走迁移并经用户同意。
- **Python 后端依赖**：新工作树里没有 `cloudflare/python_modules`，部署前要从 `pylock.toml` 相同的检出里复制过来。
- **前端依赖**：`frontend/node_modules` 有一部分被 git 跟踪，直接 `npm run build` 会弄脏它和 `frontend/dist`。在工作树里先 `npm install --legacy-peer-deps`（缺 `d3-force`、`katex` 时），构建只用 `python backend/scripts/prepare_cloudflare_frontend.py`。
- **Pages 发布是整站替换**：必须从包含线上全部前端功能的 `main` 构建，发布命令在 `cloudflare/pages` 目录下执行。
- **Worker 部署错误 10021**（"binding DB of type d1 failed to generate"）是临时的，隔几分钟重试即可。
- **后端每个请求都超过免费计划 10 毫秒的 CPU 限额**，偶尔会返回 502"云端请求失败"，隔几秒重试即可。这也是本计划要求"每一步都能重来"的原因。
- **本地开发服务器** `cloudflare/scripts/local_dev_server.py` 自己搭应用，不加载 `main.py`，所以验证不了后端入口的改动。
- **换行**：仓库开了 autocrlf，工作区文件是 CRLF。改已有文件时保持原来的换行，不要整文件改成 LF。
- **用户在北京时间（UTC+8）**；数据库里的时间都是北京时间，定时表达式要写 UTC。
- 录入小工具的接口地址和口令在 `~/.easyfix/intake.json`，**任何时候都不要把口令打印出来或写进文件**。

## 7. 实施时容易踩的地方

- `starmap_test.set_config` 会把值转成 JSON 再存；维护写开关存的是不带引号的原文，测试里要直接写 SQL（计划任务 7 已写明）。
- 状态颜色在 `frontend/src/components/starmap/starmapColors.js`，不是 `composables/knowledgeColors.js`。
- 错题事件的 `at` 可能是卷子日期（只有日期、比录入早）。判断"那个时刻系统知不知道这件事"要用录入时间，见设计 5.1。
- `word_review_log` 里混着三种题型，周报只算 `review_type = 1`。
- 测试脚本的写法、假请求、建库助手都在 `cloudflare/scripts/starmap_test.py` 和 `targeted_test.py` 里，新测试照着写。
- Cloudflare Python Workers 的入口和定时入口写法更新得快。改 `main.py` 入口之前先读官方文档当时的页面（Python Workers、FastAPI、Cron Triggers），不要凭记忆写。

## 8. 做完的标准

- 计划里 10 个任务的方框全部勾上，已有测试和新测试全部通过。
- 正式环境里能打开周报页，看到上线前刚结束的那一期。
- 发布记录写进 `docs/cloudflare-migration-status.md`，其中"未验证"写明：真实的定时任务要到上线后的第一个周日 20:20 之后才能验证。
- 那个周日之后回来核对一次，把结果补进发布记录。

## 9. 新对话的开场白（可以直接粘贴）

```text
请按 docs/superpowers/plans/2026-11-20-weekly-report-handoff.md 接手"每周周报"的实施。
先读这份交接说明和它列出的文档，然后告诉我你打算怎么执行（每个任务是否配独立审阅），我确认后再开工。
任务 1–9 在功能分支上做；任何涉及正式环境的操作都要先问我。
```
