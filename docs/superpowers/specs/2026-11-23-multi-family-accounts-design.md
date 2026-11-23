# 多家庭账号设计

日期：2026-11-23
状态：待开发者审阅

## 1. 为什么要做

EasyFix 现在只有一个共享访问密码，所有数据默认属于"1 号学生"。开发者想让**少量熟人家庭**也用上 EasyFix：每个家庭用自己的账号密码登录，只看得到自己家孩子的错题、单词、练习、周报，看不到别家的。

账号由开发者（管理员）手动开，不开放自助注册。

## 2. 目标、非目标、反目标

**目标**

- 登录页从"访问密码"改为"账号 + 密码"。
- 一个家庭一个账号，账号下可以有一个或几个学生，登录后在侧栏切换学生。
- 所有学生数据（错题、卷子、单词、练习、阅读、周报、翻一翻、星星奖励、考点掌握度等）按学生隔离，读写都只碰当前学生的。
- 附件（照片、练习 PDF）按家庭隔离，别家拿到路径也读不到。
- 管理员在设置页开家庭、加学生、重置密码、停用家庭。
- 现有数据全部归开发者家（1 号家庭、1 号学生），行为不变。

**非目标（这次不做）**

- 自助注册、找回密码邮件、手机验证码。
- 每个家庭单独的模型密钥或用量上限；模型费用先由管理员的密钥统一承担。
- 老师账号、一个学生被多个家庭共享。
- 录入技能（easyfix-intake）给别的家庭用；别的家庭用网页上的"整页识别"和"手工添加"。

**反目标（就算功能能用，出现这些也算失败）**

- 任何一个家庭能看到或改到别家的数据，哪怕只是首页的一个数字或一张缓存的统计图。
- 开发者家现有数据丢失、错挂到别的学生名下。
- 为了做账号超出 Workers 免费计划（CPU、请求数、D1 读写）。
- 密码明文出现在数据库、日志、仓库或文档里。

## 3. 现状（调研结果）

- 登录：`cloudflare/src/auth.py` 提供 `/login` 页面和 `/api/auth/verify-password`，比对环境变量 `ACCESS_PASSWORD`，签发 `easyfix_session=过期时间.签名` 的 Cookie，里面不带用户信息。设置页进入时也调一次 `verify-password`。
- 网关 `cloudflare/pages/_worker.js` 对页面、`/uploads/`、图片上传自己验 Cookie 签名；其余 `/api/` 原样转给后端，由后端 `guard` 验证。后端没有公开路由，只能经网关的服务绑定访问。
- 录入工具用 `ACCESS_TOKEN`（Bearer）访问，网关和后端都认它。
- 数据库：迁移 0011 建了 `app_user`（只有 id、name）、`student`（id、user_id、name）和 `paper`，16 张主表有 `student_id`（默认 1）；之后的 `scan_page`、`weekly_report`、`flip_log`、`mastery_adjustment`、`textbook_section` 也有。
- 表级唯一约束（来自迁移前的旧结构，SQLite 删不掉，只能重建表）：`tag` 的 `UNIQUE(name)`、`star_action` 的 `UNIQUE(code)`、`achievement_progress` 的 `UNIQUE(user_id, achievement_id)`。另有唯一索引 `cloudflare_star_balance_user ON star_balance(user_id)`（迁移 0004，可以删）。
- 激励模块 `motivation.py` 不看 `student_id`，而是按旧列 `user_id=1` 读写余额、记录和成就进度。
- 知识星空每科"学到哪一节"和"已看过的考点"存在全局 `runtime_config('starmap')`，首页、周报、星空都读它。
- 代码：`question_scope.current_student_id()` 固定返回 1。只有 flip、home、weekly、intake、papers、scan、starmap 用了 `student_id`；questions、practices、words、motivation、targeted、media、readings、reports、review、similar、word_focus、analytics、catalog、knowledge 共 14 个模块查主表不带学生条件。flip 的 `load_question_rows` 读题时也没按学生过滤。
- 统计缓存 `cache.py` 用完整网址做键，不分学生。
- 默认年级、学期存在全局 `runtime_config('app')`。
- 周报定时任务 `weekly.run_scheduled` 只推进 1 号学生。
- R2 附件路径：上传图片 `年/月/8位随机_文件名`；练习 PDF `practice_sets/<uuid>.pdf`、`practice_sets/word_<uuid>.pdf`；单词音频 `audio/words/…`（与学生无关，大家共用）。
- 设置页七个标签：年级与学期、学科、标签、知识点、错题本、知识星空、模型。

## 4. 做法比较（已选做法一）

| 做法 | 说明 | 取舍 |
|------|------|------|
| **一、自建账号密码，共用一个库（已选）** | 网关做登录，Cookie 带家庭和学生编号，后端按学生过滤，附件按路径前缀归属 | 改动面最大，但过滤和附件归属本来就绕不开；同一个入口，加家庭只是加一行数据 |
| 二、Cloudflare Access 邮箱验证码登录 | 不自己存密码 | 不是"账号密码"；pages.dev 能否接入待验证；过滤和附件工作量不变 |
| 三、每个家庭单独部署一套 | 隔离最彻底，不用改过滤 | 每家一个网址，发布和迁移跑 N 遍，D1 免费最多 10 个库，不符合"同一入口账号密码" |

开发者选了做法一。

## 5. 设计

### 5.1 数据结构（新迁移 `0018_accounts.sql`，只追加）

`app_user` 加列：

| 列 | 说明 |
|----|------|
| `username` | 登录名，唯一（软删除的不占用），只允许小写字母、数字、下划线 |
| `password_hash` | 形如 `pbkdf2-sha256$迭代次数$盐$哈希`，盐和哈希用 base64；迭代次数写在串里，以后能调高 |
| `is_admin` | 1 为管理员；迁移时 1 号用户设为 1 |
| `session_version` | 整数，默认 1；改密码、重置密码、停用时加 1，旧会话随之失效 |
| `disabled` | 1 为停用，不能登录，已有会话立即失效 |
| `updated_at` | 修改时间 |

`app_user` 另加 `last_login_at`（最近登录时间，管理员页面显示）。

`student` 加列：`sort_order`。

每个学生的默认年级、学期仍放在 `runtime_config`，配置名从 `app` 改为 `app:<学生编号>`（和星空进度 `starmap:<学生编号>` 同一种做法，`settings.load/store` 一处换名，调用方不用改）。迁移时把现有 `app` 的值复制到 `app:1`。（写计划时的调整：原先打算给 `student` 加 `grade`、`semester` 列，改成配置名按学生区分，改动点更少。）

迁移不设置 1 号用户的用户名和密码，由第 5.9 节的初始化步骤设置。

### 5.2 登录与会话（网关负责密码，后端负责身份）

**为什么密码放在网关算：**Python Worker 在免费计划下每个请求只有 10 毫秒 CPU，算 PBKDF2 会被中止（和当年图片上传 502 是同一个原因）。网关是 JS，用 WebCrypto 原生计算。

**网关新增的接口**（凡是要接触密码的都在网关）：

| 接口 | 用途 |
|------|------|
| `GET /login` | 登录页（账号、密码两个框），从后端搬到网关 |
| `POST /api/auth/login` | `{username, password}` → 验证通过签发 Cookie，当前学生取该家庭第一个学生 |
| `POST /api/auth/logout` | 清 Cookie |
| `POST /api/auth/verify-password` | 设置页进入时验当前账号的密码（保留现有交互） |
| `POST /api/auth/change-password` | 家长改自己的密码：旧密码 + 新密码（至少 10 位），`session_version` 加 1 并给当前浏览器重新签发 Cookie |
| `POST /api/auth/admin/set-password` | 管理员给某个家庭设新密码；网关生成 12 位随机密码，只在返回里出现一次 |

**Cookie 格式**：`easyfix_session=v2.过期时间.用户编号.学生编号.会话版本.签名`，签名是 HMAC-SHA256（`SESSION_SECRET`）覆盖前面所有字段。有效期 30 天（**我的决定**：手机上孩子每天输账号密码太麻烦；停用和改密码能让会话立刻失效，弥补了期限长的风险）。旧格式 Cookie 一律视为未登录。

**每个请求怎么认人**：

1. 验签名和过期时间（纯计算，很便宜）。
2. 查一次 D1：`app_user` 没删除、没停用、`session_version` 一致，并且 `student` 属于这个用户、没删除。一条 JOIN 查询。
3. 通过后，后端把 `user_id`、`student_id`、`is_admin` 放进 `request.state`；`current_student_id(request)` 从这里读。

后端 `guard` 和网关（页面、`/uploads/`、图片上传）各做一遍，判断规则写成相同的步骤。网关的页面请求（HTML）只验签名不查库也可以，因为页面本身不带数据。

**切换学生**：后端 `POST /api/auth/switch-student {student_id}`，确认学生属于当前用户后重新签发 Cookie（签名只要 HMAC，Python 也能算）。前端收到成功后整页刷新，清掉 `http.js` 的请求缓存和 Pinia 里的数据。

**防暴力猜密码**：同一个用户名 15 分钟内错 5 次就暂时拒绝登录，计数存在 `request_record`（已有的表，键如 `login_fail:<用户名>`）。

**录入口令**：`ACCESS_TOKEN` 只代表管理员家庭。请求可以带 `X-Easyfix-Student: <编号>` 指定学生，后端确认它属于管理员家庭；不带就用管理员家庭的第一个学生。`~/.easyfix/intake.json` 增加可选的 `student_id`，录入工具带上这个头。

**去掉的东西**：环境变量 `ACCESS_PASSWORD` 在发布后删除；后端的 `/login` 页面和旧 `verify-password` 删除。

### 5.3 数据隔离

**规则**：凡是表里有 `student_id` 的，读写都要带当前学生；附属表（如 `question_knowledge_point`、阅读题目、练习题目）不加列，通过 JOIN 主表过滤，或先确认主表那一行属于当前学生再操作。

**按编号访问时**（如 `GET /api/questions/{id}`、`PUT /api/practice-sets/{id}`），查询条件里同时带 `id` 和 `student_id`；不属于当前学生的一律返回 404，不返回 403（不透露"这个编号存在"）。

**要改的模块**：questions、practices、words、motivation、targeted、media、readings、reports、review、similar、word_focus、analytics、catalog（标签、错题本部分）、knowledge（掌握度统计部分），外加 flip 的 `load_question_rows` 和已接入模块里漏掉的查询。新增行时写入当前 `student_id`，不能依赖默认值 1。

**共用的目录（不分学生）**：学科、两级知识点、知识星空的教材章节（`textbook_section` 及其关联；现有行的 `student_id` 都是 1，读的时候不按学生过滤）、加星规则 `star_action`、成就定义 `achievement`、单词音频、提示词和模型设置。这些只有管理员能改，其他家庭只读。`star_action`、`achievement` 虽然有 `student_id` 列，但按共用目录处理，进防漏测试白名单（**我的决定**：加星规则和成就是游戏规则，各家一样；`star_action.code` 的表级唯一约束也决定了它只能有一份）。

**激励数据**：
- 奖品 `reward` 按学生分，家长在设置里维护自己孩子的奖品（**我的决定**：奖品是各家自己定的）。迁移时现有奖品留给 1 号学生。
- 余额、加星记录、兑换、成就进度一律以 `student_id` 为准；`motivation.py` 里所有 `user_id=1` 改成当前学生。
- `star_balance`：迁移 0018 删掉旧唯一索引 `cloudflare_star_balance_user`，改建 `star_balance(student_id)` 唯一索引（未删除的行）。
- `achievement_progress`：重建表，改为同一学生内唯一，见第 6 节。标签表同样重建。

**知识星空进度**：每科学到哪一节、已看过的考点改为按学生存，配置名从 `starmap` 改为 `starmap:<学生编号>`；迁移把现有 `starmap` 的值复制到 `starmap:1`。读写星空进度的地方（`starmap.py`、首页、周报）都改为读当前学生的配置；周报定时任务读被推进的那个学生的。

**统计缓存**：`cache.py` 的键加上 `student_id`。

**每个学生的设置**：默认年级、学期改为读写当前学生的 `app:<学生编号>` 配置；前端 `appConfig` 接口不变。

**周报定时任务**：每次触发按顺序找第一个"本周周报还没做完"的学生推进一步，一次只推进一个学生一步，保持每次触发的 CPU 和现在一样。家庭不多，每周日 20:00–20:50 的 6 次触发（每 10 分钟）可能不够；如果不够，把 cron 改成覆盖周日 20:00–23:50，打开周报页面时的补做逻辑不变。

**操作日志**：`operation_log.operator` 从固定的 `'cloudflare'` 改为登录名，方便管理员看谁在用、用了多少模型。

**防漏测试**：新增 `cloudflare/scripts/student_scope_test.py`，扫描 `cloudflare/src/*.py` 里的 SQL 字符串：只要出现带 `student_id` 列的表名，同一条 SQL 里就必须出现 `student_id`。共用目录表在白名单里；确实不需要过滤的个别语句加注释标记豁免，豁免数量写死在测试里，新增豁免要改测试。

### 5.4 附件

- 新上传的图片存到 `u<用户编号>/年/月/8位随机_文件名`；新生成的练习 PDF 存到 `u<用户编号>/practice_sets/…`。
- 网关读 `/uploads/` 时：
  - `audio/` 开头的大家都能读；
  - `u<编号>/` 开头的只有那个用户能读；
  - 其他路径（迁移前的旧附件）只有 1 号用户能读。
- 后端接收图片路径的接口（录入、整页识别、批改拍照、复核图片）要检查路径属于当前用户，防止把别家路径挂到自己的题上再读出来。
- 练习 PDF 的"复用已生成 PDF"逻辑本来就按练习集查，练习集已按学生过滤，不用再改。

### 5.5 管理员功能

设置页加第八个标签"账号"，只有管理员看得到。

- 家庭列表：登录名、显示名、学生、状态（正常/停用）、最近登录时间。
- 新建家庭：填登录名和显示名，自动建一个学生（填学生名字、年级、学期），然后调网关生成初始密码，页面显示一次，让管理员发给对方。
- 加学生、改学生名字和年级、删除学生（软删除）。
- 重置密码（生成新密码并显示一次）、停用和启用。
- 管理员不能停用或删除自己。

后端接口放在 `/api/admin/…`（新模块 `cloudflare/src/accounts.py`），`guard` 里统一检查 `is_admin`；涉及密码的转给网关接口（见 5.2）。

**我的决定**：管理员切换学生时只能看到自己家的学生，不提供"以某个家庭身份查看"。需要帮别家排查时，先让对方截图描述。

### 5.6 非管理员能看到的设置

- 年级与学期：改当前学生的。
- 标签、错题本：只管当前学生的。
- 学科、知识点：只读。
- 知识星空：教材章节目录只读；"学到哪一节"和"手动调整掌握度"可以改，只影响当前学生。
- 激励（奖品、加星规则、成就所在的面板）：奖品可以改；加星规则和成就只读。
- 模型：隐藏。
- 新增"账号"区：显示自己的登录名、学生列表（只读），可以改自己的密码。

### 5.7 前端

- 登录页：账号、密码、登录按钮，错误提示统一为"账号或密码不正确"。
- 侧栏顶部（手机在"更多"顶部）显示当前学生名字；家庭有多个学生时点开可以切换。
- 侧栏底部加"退出登录"。
- `stores/` 新增 `account.js`：当前用户名、是否管理员、学生列表、当前学生，来自新接口 `GET /api/auth/me`（后端）。
- 所有页面不需要传学生编号，学生只由 Cookie 决定。

### 5.8 免费计划影响

- 每个 API 请求多一次 D1 读（一条带 JOIN 的查询，读几行），在 D1 免费额度（每天 500 万行读）里很小。
- PBKDF2 只在登录、验密码、改密码时算。迭代次数在实施时实测：选在网关免费计划 CPU 下稳定不超限的最大值（目标 10 万次，测不过就往下降）。初始密码由管理员随机生成，12 位；家长自己改密码时至少 10 位，迭代次数低一点也难以离线破解。**我的决定**：实测连 1 万次都会超限时，停下来向开发者报告，不自行降到 1 万次以下或换方案。

### 5.9 发布与初始化

1. 导出 D1 备份。
2. 执行迁移 0018 之前的预检（都应没有结果；有结果先停下来处理）：
   - 远程 `PRAGMA table_info(tag)`、`PRAGMA table_info(achievement_progress)` 的列和 0018 里新表的列一致；
   - `SELECT student_id, COUNT(*) FROM star_balance WHERE deleted=0 GROUP BY 1 HAVING COUNT(*)>1;`
   - `SELECT student_id, achievement_id, COUNT(*) FROM achievement_progress WHERE deleted=0 GROUP BY 1,2 HAVING COUNT(*)>1;`
   - 先用备份恢复出的本地 D1 演练一次 0018（`wrangler d1 execute --local`），核对行数、最大编号、`PRAGMA foreign_key_check` 为空。
   然后在远程执行 0018。
3. 本地运行一个小工具（`backend/scripts/set_admin_password.py`，用 Python `hashlib.pbkdf2_hmac` 生成和网关相同格式的哈希），通过 wrangler 给 1 号用户写入登录名和密码。密码只在终端输入，不写进文件和命令历史。
4. 同时发布 Worker 和 Pages（Cookie 格式一起变）。发布后所有人要重新登录。发布前先确认（实施时留下的待办）：
   - Pages 构建现在是 `_worker.js/` 目录形式（`index.js` 加 `session.js`、`password.js`、`auth_routes.js`），先用预览分支部署一次，确认能跑；
   - PBKDF2 迭代次数暂定 5 万次（本机约 7 毫秒）：在预览部署上登录几次，看 Cloudflare 日志里的 CPU 时间没有超限，超限就调低 `password.js` 和 `set_admin_password.py` 里的数字；
   - 重新运行 `tools/easyfix-intake/install.py`，让本机安装的录入技能和小工具带上 `student_id` 的支持；
   - 在浏览器里把"设置 → 账号"和"我的账号"点一遍（本机测试环境没有网关，开发时没点通）。
5. 核对：管理员能登录，数据和发布前一致；新建一个测试家庭和学生，确认首页、错题、单词、练习中心、周报、翻一翻、学情都是空的，读开发者家的附件路径返回 404；测试完把测试家庭停用。
6. 删除 `ACCESS_PASSWORD` 密钥。
7. 在 `docs/cloudflare-migration-status.md` 记录发布。

## 6. 重建两张表（开发者已同意破例）

`tag` 的表级 `UNIQUE(name)` 和 `achievement_progress` 的表级 `UNIQUE(user_id, achievement_id)` 会让不同学生之间撞名、撞进度。SQLite 去掉表级约束只能重建表。开发者同意在迁移 0018 里**破例**重建这两张表，这是"迁移只追加"规矩的唯一例外，其他表照旧只追加。

做法：

1. 执行前导出 D1 备份，记下两张表的行数和最大编号。
2. 迁移开头 `PRAGMA defer_foreign_keys = on;`（`question_tag`、`word_tag` 有外键指向 `tag(id)`，`achievement_progress` 有外键指向 `achievement(id)`；D1 默认检查外键，推迟到提交时检查才能删旧表）。
3. 建新表 `tag_new`、`achievement_progress_new`：列和旧表完全相同（包括 0011 加的 `student_id`），去掉旧的表级唯一约束，保留旧的外键约束。
4. `achievement_progress`（只是子表）：`INSERT INTO 新表 SELECT … FROM 旧表`，删旧表，新表改名。
5. `tag`（被 `question_tag`、`word_tag` 引用的父表）：先把数据复制到 `tag_copy`，删旧表，`tag_new` 改名为 `tag`，再从 `tag_copy` 插回（编号原样保留），最后删 `tag_copy`。D1 默认检查外键，删父表会把子行记成违约，只有往改名后的 `tag` 里插回同样的编号才能抵消；先插进 `tag_new` 再改名的做法在提交时会失败（评审时复现过）。
6. 建新的唯一索引：`tag(student_id, name) WHERE deleted=0`；`achievement_progress(student_id, achievement_id) WHERE deleted=0`。旧表上的其他索引按原样重建。
7. 迁移后核对：行数、最大编号与第 1 步一致；`question_tag`、`word_tag` 没有指向不存在标签的行；`PRAGMA foreign_key_check` 无结果。

重建后 `achievement_progress` 以 `student_id` 为准，旧列 `user_id` 保留但不再读写。

## 7. 留给实施者决定的

- 14 个模块的改动顺序和拆分方式（建议先接防漏测试，按测试报的位置逐个改）。
- PBKDF2 的具体迭代次数（按 5.8 实测）。
- 登录页和账号标签的具体样式（沿用 Element Plus 和现有设置页的样式）。
- 网关和后端身份校验代码怎么组织，只要两边规则一致、各有测试。
