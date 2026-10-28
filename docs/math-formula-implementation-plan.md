# 数学公式及 PDF 打印支持实施方案

## 目标与业务边界

当前业务为：图片交给 Agent 识别，Agent 直接写入数据库，系统展示题目并生成 PDF 下载打印。本次不改造旧多模态 OCR 或相似题生成服务。

重点保证新题型的次方、上下标、分数、嵌套分数和根号可以完整入库、展示、导出及打印。历史记录只保持可读，不批量转换，不依赖已缺失的原图。几何图形继续使用现有图片，第一版不重绘。

## 数据兼容与 Agent 入库约定

- 沿用 original_text、parsed_question、answer、analysis 等 Text 字段；无表结构变更、无数据库迁移、禁止删库。
- 新数据采用普通正文混合 LaTeX；行内用 `\(...\)`，独立公式用 `\[...\]`。
- 示例：`计算 \(\frac{3}{4}+2^{3}\)。`；多位、负数及复合指数使用花括号。
- 不保存排版 HTML，不把公式变成不可编辑截图。
- Agent 使用参数化 SQL 或结构化数据库工具入库；SQL 参数中的字符串应为实际文本，JSON 中的反斜杠按 JSON 规则转义。禁止通过多轮手动替换反斜杠处理转义。
- 入库后回读并核对原字符串，特别检查 `\frac`、`\sqrt`、反斜杠、花括号；禁止出现误转义的制表符或换页符。
- 建议 Agent 入库前对有边界的公式执行与产品相同的 KaTeX 校验；解析通过只代表语法可排版，不代表数学内容正确。
- Agent 直接写库会绕过 API 校验，因此规范必须写入实际入库流程的指令或脚本，不能仅放在前端。正式实施时定位实际 Agent 入口；若入口在仓库外，提供可复制指令和校验工具，并明确外部接入尚待完成。
- 新图应保留可访问路径；缺失原图时仍允许完整文本导出，但无法恢复已丢失的结构，不猜测补全。

历史兼容规则：普通文本、Unicode 上标和分数字符保持原样；裸 `x^2`、`1/2` 不自动转换；带规范边界的公式渲染。旧数据是否存在 `$...$`、HTML 或 HTML 实体先做只读抽样，再确定受控兼容规则。不能把正文中的比较符号当作 HTML，也不能直接执行旧内容中的 HTML。对旧 HTML 若确需保留换行或上标，采用白名单转换或净化，不直接使用原始 v-html。

## 前端改造

新增 `frontend/src/components/MathText.vue`，接入 KaTeX 和本地 CSS/字体。普通文本通过 textContent 等安全方式写入，再渲染公式；默认 trust=false，限制宏展开和尺寸。内容更新时从原始文本重建，避免重复渲染。错误公式显示安全的原文和提示。

覆盖 Questions.vue 的列表、详情、答案、解析，以及 PracticeSets.vue 的题目、答案、详情、批改弹窗。Upload.vue 及现有编辑框可增加实时预览和次方、分数、根号插入按钮，但不改变当前 Agent 入库主链路。列表限高；详情长公式可横向滚动，打印另行处理。

## PDF 架构

保留现有 API、按钮、下载返回结构和相对路径约定。`backend/app/services/pdf.py` 的 `generate_practice_set_pdf()` 内部改用打印 HTML → 本地 KaTeX → Playwright Chromium → PDF。`practice_set.py` 中创建练习集自动生成和手动重新生成两个入口均需覆盖。现有单词默写 fpdf2 路径第一版保留；阅读理解路径保持短文、选项顺序和内容。

新增后端打印模板、打印 CSS、本地 KaTeX 和中文字体。前后端锁定同一 KaTeX 版本和边界规则。建议提供资源同步脚本，确保 Python 部署不依赖 frontend/node_modules；字体选择可分发且许可明确的中文字体，保留许可证。依赖补充 Playwright，并在保留的 fpdf2 路径实际需要时补齐其依赖声明；当前 requirements.txt 未声明 fpdf2。

浏览器仅载入受控模板和本地资源，不访问用户提供 URL；题干按文本注入，不拼接成可执行脚本。等待公式渲染完成、document.fonts.ready 和图片加载状态，再导出。公式解析失败则阻止导出，并返回题目编号/ID及可读错误，避免把源码作为成功 PDF。缺失的历史图片可以显示缺图占位；若既无文本也无可用图片，提示具体缺失题目。

纸张 A4，统一页边距、页眉页码；黑白打印清楚。普通题块尽量整题分页；长于一页的题目允许分段。公式不从中间裁断；检测超宽公式，优先合理断行或有限缩放，仍超宽则提示修正。具体断页须用实际 PDF 验证，不能只靠 break-inside: avoid。

原生同步路由可先配合受限的同步浏览器任务实现；设置生成超时、并发上限并可靠关闭页面/浏览器，避免无限堆积。第一版不强制引入任务队列。新 PDF 写入独立文件并验证成功后，再提交 pdf_path；失败保留旧路径和旧文件。批量下载读取已有 PDF，不隐式重生成。不得用旧引擎静默回退公式题。

## 备份脚本（已准备）

脚本位置：`backend/scripts/backup_data.py`。读取项目的 Settings，切换到 backend 目录加载 backend/.env；继承现有环境变量优先级，不输出密码。SQLite 相对 DB_PATH 按 backend 解析，与项目推荐启动方式一致；如历史服务从其他工作目录启动，需确认实际文件并传 --sqlite-path。

备份数据库、整个 backend/uploads（包括现存图片、音频及 PDF）、外置 UPLOAD_DIR、backend/config 和 backend/.env。输出目录默认根目录 backups，已加入 .gitignore；目录包含密钥及学生数据，应放在受控磁盘，不上传版本库或公开分享。

先暂停后端和 Agent 等所有写入，再执行：

```powershell
# 从仓库根目录执行；确认所有写入已经停止后再传确认参数
.\backend\.venv\Scripts\python.exe .\backend\scripts\backup_data.py --writers-paused

# 建议保存到独立磁盘，避免与项目同盘故障
.\backend\.venv\Scripts\python.exe .\backend\scripts\backup_data.py --writers-paused --output-dir E:\EasyFixBackups

# SQLite 真实文件与配置不一致时显式指定；仅 SQLite 可用
.\backend\.venv\Scripts\python.exe .\backend\scripts\backup_data.py --writers-paused --sqlite-path D:\data\easyfix.db

# 使用实际生成的备份目录校验；校验过程不连接数据库
.\backend\.venv\Scripts\python.exe .\backend\scripts\backup_data.py --verify E:\EasyFixBackups\easyfix_实际时间戳
```

每次生成唯一 UTC 时间戳目录，不覆盖旧备份。SQLite 使用只读连接和 backup API（包括 WAL 中已提交内容），并执行 integrity_check；MySQL 调用 PATH 中的 mysqldump，使用 single-transaction/quick；PostgreSQL 配置也支持，以 pg_dump custom 格式导出。外部客户端必须提前安装，密码通过子进程环境变量传递。MySQL 一致性仍要求暂停写入和 DDL，尤其非事务表；该参数不能自动检查其他程序是否已暂停。

成功目录包含 manifest.json，列明文件大小、SHA-256、数据库类型、原路径和缺失目录。生成后自动校验；失败返回非零退出码，不留下成功清单，保留不完整目录供排查，不自动删除。缺失目录会记录，但无法找回已丢失原图；清单也不保证每条数据库图片引用都存在。校验用于检测意外损坏，不是防篡改签名或数据库恢复演练。

## 恢复与回退

1. 停止后端及 Agent 写入，对当前状态再备份；验证拟恢复目录的 manifest 和哈希。
2. 优先恢复到隔离目录或临时数据库，验证题目数量、关联关系、中文和公式文本。数据库导出文件校验不能代替实际恢复演练。
3. SQLite 将 database.sqlite3 恢复到确认后的 DB_PATH。停止全部连接后，将现有主文件及同名 -wal/-shm 文件一起保留到独立目录，再放置快照，避免混用旧 WAL；不直接覆盖运行中数据库。MySQL 将 SQL 导入临时库验证，再切换配置；PostgreSQL 使用 pg_restore 导入临时库验证。默认不提供自动覆盖生产库的恢复命令。
4. uploads 恢复到 backend/uploads；若 custom_upload_copy=true，将 configured_uploads 恢复到对应外置路径。配置和 .env 单独检查后恢复，避免覆盖新的数据库连接配置。均先恢复到空目录核对，再切换实际路径。
5. 读取代表性历史题和新公式题，下载旧 PDF、生成新 PDF，确认后恢复服务和 Agent。

本次无数据迁移：仅代码回退时无需恢复数据库；新 LaTeX 数据仍在，但旧版本页面/PDF 不具备排版能力。不能把“回退代码”视为仍能正确打印新题。

## 实施阶段及验收

1. **准备**：定位实际 Agent 写入入口；确认 DB_TYPE、真实数据库路径、上传路径；暂停写入后运行备份与校验。先在隔离环境演练恢复。
2. **PDF 样例验证**：打通中文、次方、嵌套分数、根号生成 PDF；确认离线资源、字体和跨页。通过后再批量接入。
3. **页面和数据规范**：统一组件、编辑预览、Agent 指令及入库回读校验；不批量改历史数据。
4. **接口接入**：替换两个练习集 PDF 入口，保留现有返回值；验证生成失败保留旧 PDF，设置超时与并发限制。
5. **验收**：前端 npm run build；后端有针对性的检查与实际导出，不虚构项目现有测试套件。按下列样例执行“Agent 写入 → 回读 → 展示 → PDF → 打印预览”。

验收样例：x 的 12 次方、负指数、复合指数、上下标、普通与嵌套分数、根号、中文混排、比较符号和 &、普通旧题与新题混合练习集、历史缺图、错误 LaTeX、超宽公式、超过一页的题目。核对原题/阅读/单词 PDF 回归；不创建新的相似题功能。检查 PDF 内无公式源码泄漏、无裁切、页码正确、黑白可读，并至少做一次纸质打印确认。

## 当前交付状态

现已实现页面公式展示、编辑预览、离线 PDF 排版、备份及隔离恢复验证、Agent 入库规范与校验工具。两张授权图片已导入并完成实际接口和页面验收。详细结果见 [验收记录](math-formula-validation-20261028.md)。下节保留实施前的只读可行性检查记录；当前结果以验收记录为准。

## 2026-10-28 实际环境可行性验证

- 只读连接确认实际使用 PostgreSQL 18.6，public 下有 28 张表。question 的题干、答案、解析均为 text，结构支持方案，不需要改表。
- 共有 310 条题目记录，其中 deleted=false 为 293 条；有效题目均可取到题干文本。226 条未填写单图字段 original_image，但这不等同于全部缺图（还可能有 original_images），本次未据此判定文件丢失。
- 293 条有效题目中，题干/答案/解析未检出约定公式边界或 frac/sqrt/times 命令，未检出异常控制字符。宽泛尖括号规则曾命中两条，标准标签规则复核未检出 HTML 标签；不得直接将尖括号表达式视为 HTML。
- 使用 PostgreSQL 参数化 SELECT 回传公式文本完全一致；该检查只验证传输转义，没有插入数据，也没有验证仓库外 Agent 的实际入库行为。
- 在 tmp/math-feasibility 隔离安装 Node Playwright、KaTeX 和 PDF 检查工具，未修改业务依赖文件。使用本机 Edge 的无头 Chromium，禁用 HTTP/HTTPS 请求，本地资源生成 output/pdf/math-feasibility.pdf。共 3 页 A4，4 个公式区域渲染成功（首题含两个区域），无渲染错误，错误公式样例被拒绝，PDF 文本未检出 frac 源码且能提取中文。已逐页渲染检查。
- 样例确认数学排版及长题干跨页技术路径可行，尚不代表完整业务模板验收；页码、超宽公式、业务并发和纸质打印仍需正式实现后验证。字体使用本机微软雅黑，正式部署仍需打包可分发字体。
- 后端 Python 环境目前未安装 Playwright；样例验证使用 Node 实现，正式后端仍需安装 Python Playwright 并验证 Windows 服务运行账号可启动浏览器。已安装 Edge 可用于本机验证，生产建议使用锁定的浏览器和字体版本。
- PATH 中没有 pg_dump / pg_restore，常见 Program Files 目录也未发现 PostgreSQL 安装目录。因此当前 PostgreSQL 备份脚本尚不能实际运行成功，不能宣称已完成业务备份。建议安装 PostgreSQL 18 客户端，设置 PATH 后运行备份并在隔离库恢复演练。官方说明：pg_dump 不能备份主版本比自己更新的服务端，不能使用 17 或更旧的客户端备份此 18.6 服务端。参考 https://www.postgresql.org/docs/18/app-pgdump.html 。
- 现有 PDF 接口查询 Question 和部分关联记录时未统一过滤 deleted=false；正式接入时需核对关联模型是否含 deleted 并补齐过滤，避免已软删除题目进入新 PDF。保持历史 PDF，不修改历史题目。

结论：存储与 PDF 排版技术可行；正式上线前需要补齐 PostgreSQL 18 备份/恢复工具、Python 浏览器运行依赖、Agent 入库入口，以及打印模板的边界验收。没有对业务数据库执行 INSERT/UPDATE/DELETE，也未触发业务 PDF 接口更新 pdf_path。


## 实施与部署补充（2026-10-28）

- 页面新增 MathText/MathEditor，公式边界和安全文本处理位于 shared/math-text.mjs，前后端共用。保留 $$ 独立公式兼容，不开启单美元边界，避免货币文本误识别。
- 后端 math_pdf.py 实现离线 Chromium PDF；不依赖 Jinja2。现有 generate_practice_set_pdf 入口保持，单词默写保留 fpdf2；阅读短文、选项按现有顺序传入。
- KaTeX 固定为 0.19.0；后端离线资源已包含脚本、字体和许可证。更新版本后执行 sync_math_assets.py。部署需同时包含 backend、shared 两个目录；前端构建也需要 shared。
- PDF_BROWSER_CHANNEL 留空使用 Playwright Chromium；本机 backend/.env 配置 msedge。PDF_FONT_PATH 支持指定中文字体；Windows 可用系统微软雅黑，Linux 应安装具有中文字符的字体（例如 Noto CJK）或配置可分发字体文件，不能依赖远程字体 CDN。PDF_TIMEOUT_MS 用于浏览器启动、导航和页面就绪等待，不作为整个业务请求的绝对时限。

```powershell
# 前端；现有 vue-echarts 与 echarts 的 peer dependency 冲突与本次无关，暂保持版本并使用已有兼容安装方式
cd frontend
npm install --legacy-peer-deps
npm run build

# 后端（从 backend 目录执行）
python -m pip install -r requirements.txt
python -m playwright install chromium
python scripts/sync_math_assets.py
python scripts/verify_math_support.py
```

备份脚本增加 --pg-bin 指定客户端目录，不需修改系统 PATH。PostgreSQL 可使用 --online-snapshot：数据库由 pg_dump 生成一致性快照，上传文件为尽力复制，清单明确记录非跨资源原子快照，不谎称写入已暂停。需要严格跨资源一致性时仍应暂停后端及所有 Agent，再使用 --writers-paused。

```powershell
# 仓库根目录：在实际客户端路径下运行
.\backend\.venv\Scripts\python.exe backend/scripts/backup_data.py --online-snapshot --pg-bin C:\tools\pgsql18\bin

# 正式图片导入前检查；备份目录应为本次实际成功目录
.\backend\.venv\Scripts\python.exe backend/scripts/import_math_formula_photos.py --image-one 原图1.jpg --image-two 原图2.png --backup-dir backups/成功备份目录
# 在同一命令后加 --apply 才会写库。按题干去重，单事务写入并回读校验，不覆盖已有不同答案。
```

图片导入共三条题目：第14页C层（1）的三个小问合为一条、C层（2）裂项求和一条、第二图绝对值条件与2026次方一条。第一图顶部被裁切的数轴题不录入；年级学期不在图中，不推断。三小问正确答案为1/2、2/15、1/6；裂项和为2025/2026；乘方题为1。原图中已做对的三个小问保留为同组练习，不伪造错误记录；截图未展示第二题作答，不推断学生错误。脚本保留原图，创建独立整理本和练习集。


### 通用 Agent 入库预检

将题目对象或数组保存为 UTF-8 JSON，支持 parsed_question/question_text/original_text、answer、analysis：

```powershell
.\backend\.venv\Scripts\python.exe backend/scripts/validate_math_json.py 待入库题目.json
```

该工具检查题干、答案、解析，拒绝裸公式命令，使用生产渲染器生成临时 PDF 验证后自动清理，不写数据库。通过后仍须使用参数化写入并回读核对。

### 本次 PostgreSQL 备份及隔离恢复的实际命令

本机官方客户端已准备在 tmp/pg18。当前私有 PostgreSQL 服务的客户端连接协商需要指定以下会话环境变量；这仅用于本次现有非TLS私网连接，不修改应用默认连接或系统配置。对开启 TLS 的部署环境保留其实际 SSL 配置。

```powershell
$env:PGSSLMODE='disable'
$env:PGGSSENCMODE='disable'
.\backend\.venv\Scripts\python.exe backend/scripts/backup_data.py --online-snapshot --pg-bin tmp/pg18
.\backend\.venv\Scripts\python.exe backend/scripts/verify_postgres_backup.py --backup-dir backups/easyfix_20261028T104949_135313Z --pg-bin tmp/pg18
```

verify_postgres_backup.py 仅创建随机名称的 easyfix_restore_check_ 临时库；需要建库权限，不覆盖业务库。恢复、读取和索引检查成功后移除该临时库，结果保存在备份目录。备份脚本支持 PostgreSQL / MySQL / SQLite，当前正式环境验证覆盖 PostgreSQL，SQLite 为临时样例验证，MySQL 未做实际恢复验证。

部署前端需要 Node.js 22.12 或更高版本（KaTeX 0.19 的 CLI 依赖要求）。本次最终构建使用 Node.js 24.22.1，Vite build 退出码为0；系统 Node.js 24.14.1 曾在构建结束时出现 libuv 退出异常，未作为最终通过依据。
