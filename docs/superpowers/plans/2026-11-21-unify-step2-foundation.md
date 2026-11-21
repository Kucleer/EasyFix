# 项目 5 第 2 步：共用的地基 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 给第 3 步重写的页面打地基：学科、标签、知识点树集中存一份；同一个接口只留一个前端函数、页面不再直接写地址；共用组件、样式变量和图表主题；去掉 `echarts-gl`。界面基本看不出变化。

**Architecture:** 只动前端。新建 Pinia store `catalog`（纯逻辑放 `catalogModel.js`，用 `node --test` 测）；接口按资源归到 `api/practice.js`、`api/upload.js`、`api/reading.js`、`api/auth.js`、`api/config.js`，旧的重复函数删掉、调用处改过来，用一个读源码的测试钉住"页面不直接写地址、每个接口只定义一次"；共用组件放 `components/ui/`，图表主题放 `composables/chartTheme.js`。

**Tech Stack:** Vue 3 `<script setup>` + Pinia + Element Plus + ECharts；测试是 Node 自带的 `node --test`。

**Spec:** `docs/superpowers/specs/2026-11-21-workspace-and-unify-design.md` 第 9 节（地基）、第 11 节（分步）。

## Global Constraints

- 只改前端，后端和数据库不动；这一步只发布 Pages。
- 用户已授权第 2–4 步连续做完、每步自动发布（2026-11-21），不再逐步询问。
- 这次重写的四页（第 3 步）和新页面必须用 store；练习中心、单词页等没重写的页面，改动只有几行的顺手改，其余留着。
- 不引用外部字体，只用系统自带字体。
- 去掉 `echarts-gl` 前先确认全站没有别处用到三维图表。
- 代码规范：Composition API + `<script setup>`；函数前写中文注释；常量全大写。
- 提交信息沿用仓库写法：英文、`feat(ui): ...`、`refactor(api): ...` 这类前缀。
- `frontend/node_modules` 有一部分被 git 跟踪：不提交 `node_modules/.package-lock.json`；构建只用 `python backend/scripts/prepare_cloudflare_frontend.py`。

## Review Focus

1. 管理中心新增或删除学科、标签、知识点后，其他页面（录入、错题筛选、出卷）再打开时看到的是新列表，不是 store 里的旧值。（Task 1：管理中心写入后调用 `invalidate`）
2. 学科请求偶发 502 失败后，下一次调用要能重新请求，不能把空列表永久记住。（Task 1 测试 `loader 失败后下次重试`）
3. 练习中心里的旧批改弹窗和阅读测试的提交，改成统一的 JSON 写法后仍能保存（后端 `mark-reviewed` 同时接受表单和 JSON，`question_results` 可以是列表或字符串）。（Task 2）
4. 练习中心上传批改照片、单词本播放读音，从 `fetch` 改成封装函数后仍正常（多张照片的表单字段名仍是 `files`；读音按 blob 取、不走缓存）。（Task 2）
5. 知识星空、出卷页只显示数学、英语两科，顺序不变。（Task 1 测试 `pickStarmapSubjects`）

---

## 文件一览

| 文件 | 怎么动 |
| --- | --- |
| `frontend/src/stores/catalogModel.js`、`catalogModel.test.mjs` | 新建：纯函数 |
| `frontend/src/stores/catalog.js` | 新建：Pinia store |
| `frontend/src/api/practice.js`、`upload.js`、`reading.js`、`auth.js` | 新建 |
| `frontend/src/api/question.js`、`targeted.js`、`starmap.js`、`config.js`、`word.js` | 删重复函数、合并 |
| `frontend/src/api/apiLayer.test.mjs` | 新建：读源码的接口层测试 |
| `frontend/src/components/ui/icons.js`、`LineIcon.vue`、`StatCard.vue`、`ChartCard.vue`、`TabBar.vue`、`ui.test.mjs` | 新建 |
| `frontend/src/composables/chartTheme.js`、`chartTheme.test.mjs`、`useTabQuery.js` | 新建 |
| `frontend/src/composables/weeklyReport.js`、`views/WeeklyReport.vue` | 改用图表主题 |
| `frontend/src/styles/variables.css` | 补样稿的颜色、圆角、阴影 |
| 用到上面接口的页面和组件 | 改调用 |
| `frontend/package.json`、`package-lock.json`、`views/Home.vue` | 去掉 `echarts-gl` |

"跑全部前端测试"指（仓库根目录）：

```bash
node --test frontend/src/stores/catalogModel.test.mjs frontend/src/api/apiLayer.test.mjs frontend/src/components/ui/ui.test.mjs frontend/src/composables/chartTheme.test.mjs frontend/src/composables/dictation.test.mjs frontend/src/composables/weeklyReport.test.mjs
python backend/scripts/prepare_cloudflare_frontend.py
```

---

### Task 1：目录数据 store

**Files:**
- Create: `frontend/src/stores/catalogModel.js`、`frontend/src/stores/catalogModel.test.mjs`、`frontend/src/stores/catalog.js`
- Modify: `frontend/src/api/starmap.js`（删 `starmapApi.subjects`、`STARMAP_SUBJECTS`、`loadStarmapSubjects`）
- Modify（读学科改用 store）：`components/StarMapCard.vue`、`components/StarMapSettings.vue`、`views/StarMap.vue`、`views/TargetedPaper.vue`（这四处用 `starmapSubjects`）；`components/ManualQuestionForm.vue`、`views/LearningAnalysis.vue`、`views/LearningReports.vue`、`views/Management.vue`、`views/Papers.vue`、`views/PracticeSets.vue`、`views/Questions.vue`、`views/Upload.vue`（`loadSubjects`）
- Modify（读标签）：`components/ManualQuestionForm.vue`、`views/Management.vue`、`views/Questions.vue`、`views/Words.vue`
- Modify（读知识点树）：`components/KnowledgePointPicker.vue`、`composables/knowledgeColors.js`
- Modify（写入后失效）：`views/Management.vue` 的 `createSubject`、`deleteSubject`、`createTag`、`deleteTag`、知识点的保存和删除

**Interfaces:**
- Produces（`catalogModel.js`，不得 import 带 `@/` 的模块）：
  - `STARMAP_SUBJECTS = ['数学', '英语']`
  - `normalizeList(data) -> Array`：接口返回数组就原样，`{items}` 取 `items`，其余返回 `[]`
  - `pickStarmapSubjects(subjects) -> [{id, name}]`：按 `STARMAP_SUBJECTS` 的顺序挑出存在的科目
  - `treeKey(subjectId) -> string`：`null`/`undefined` 为 `'all'`，否则 `String(subjectId)`
  - `createLoader(fetcher) -> { load(force=false): Promise<any>, reset(): void }`：同一时刻只发一次请求；成功后记住结果，`force` 才重新请求；失败时不记住，下次调用重新请求，错误照常抛出
- Produces（`catalog.js`）：`useCatalogStore()`，state `subjects`、`tags`、`trees`（按 `treeKey` 存树接口的完整返回体）；getter `starmapSubjects`；actions `loadSubjects(force=false) -> Array`、`loadTags(force=false) -> Array`、`loadKnowledgeTree(subjectId=null, force=false) -> {items, taxonomy_version, ...}`、`invalidate(kind)`（`'subjects'`、`'tags'`、`'knowledge'`，不传就全部）。请求仍走 `questionApi.listSubjects`、`listTags`、`getKnowledgePointTree`。

- [ ] **Step 1：写 `catalogModel.test.mjs`**

用例：
- `normalizeList`：`[1]` → `[1]`；`{items:[2]}` → `[2]`；`null` → `[]`
- `pickStarmapSubjects([{id:2,name:'英语'},{id:1,name:'数学'},{id:3,name:'语文'}])` → `[{id:1,name:'数学'},{id:2,name:'英语'}]`；缺英语时只返回数学
- `treeKey(null) === 'all'`，`treeKey(3) === '3'`
- `createLoader`：并发两次 `load()` 只调用一次 fetcher；第二次 `load()` 不再调用；`load(true)` 再调用一次
- `loader 失败后下次重试`：fetcher 第一次 reject，`load()` 抛错；第二次 `load()` 再调用 fetcher 并拿到结果
- `reset()` 之后 `load()` 重新请求

- [ ] **Step 2：运行，确认失败**

Run: `node --test frontend/src/stores/catalogModel.test.mjs`
Expected: FAIL（模块不存在）

- [ ] **Step 3：实现 `catalogModel.js`，再实现 `catalog.js`**

- [ ] **Step 4：运行，确认通过**

- [ ] **Step 5：改调用处**

- 星空四处：`const catalog = useCatalogStore(); await catalog.loadSubjects(); subjects.value = catalog.starmapSubjects`（或直接用 getter）。
- 其余读学科、标签的地方：`questionApi.listSubjects()` / `listTags()` 换成 `catalog.loadSubjects()` / `loadTags()`，注意原代码用的是 `{ data }`，store 直接返回数组。
- `KnowledgePointPicker.vue` 用 `catalog.loadKnowledgeTree(props.subjectId)`；`knowledgeColors.js` 的 `loadKnowledgeColors(force)` 改为 `useCatalogStore().loadKnowledgeTree(null, force)`，本文件自己的 `loading` 去重保留。
- `Management.vue`：学科、标签增删后调用 `catalog.invalidate('subjects')` / `invalidate('tags')` 再按原逻辑刷新列表（列表用 `loadSubjects(true)` / `loadTags(true)`）；知识点保存、删除后调用 `catalog.invalidate('knowledge')`。管理页列表用的带筛选的 `listKnowledgePoints` 不动。

- [ ] **Step 6：确认没有遗漏**

Run: `grep -rnE "listSubjects\(|listTags\(|getKnowledgePointTree\(|loadStarmapSubjects|starmapApi\.subjects" frontend/src --include=*.vue --include=*.js`
Expected: 只在 `api/question.js` 的定义和 `stores/catalog.js` 里出现。

- [ ] **Step 7：跑全部前端测试，提交**

```bash
git add frontend/src
git commit -m "feat(ui): keep subjects, tags and knowledge trees in one catalog store"
```

---

### Task 2：前端接口函数去重

**Files:**
- Create: `frontend/src/api/practice.js`、`upload.js`、`reading.js`、`auth.js`、`apiLayer.test.mjs`
- Modify: `frontend/src/api/question.js`、`targeted.js`、`config.js`、`word.js`
- Modify（调用处）：`views/PracticeSets.vue`、`views/GradePaper.vue`、`views/TargetedPaper.vue`、`views/Questions.vue`、`views/Reading.vue`、`views/ReadingTest.vue`、`views/Management.vue`、`views/Settings.vue`、`views/Upload.vue`、`views/Words.vue`、`components/ManualQuestionForm.vue`，以及 `grep` 找到的其他使用者

**Interfaces:**
- Produces `practiceApi`（`api/practice.js`，`timeout: 120000`）：`list(params)`、`detail(id)`（`cache: false`）、`create(data)`、`update(id, data)`、`remove(id)`、`batchRemove(ids)`、`batchDownloadPdf(ids)`、`generatePdf(id)`、`markReviewed(id, payload = {})`（JSON）、`updateReviewImages(id, images)`、`generateFromReading(payload)`
- Produces `uploadApi`（`api/upload.js`）：`uploadFile(file)`（字段 `file`）、`uploadImages(files)`（字段 `files`，可多张）
- Produces `readingApi`（`api/reading.js`）：`topics()`、`list(params)`、`get(id)`、`generate(payload)`、`remove(id)`
- Produces `authApi`（`api/auth.js`）：`verifyPassword(password)`
- Produces `configApi`（`api/config.js`，只此一份）：`getApp()`、`saveApp(data)`、`getLlm()`、`saveLlm(data)`
- 新增 `questionApi.practiceHistory(id)`、`wordApi.audio(id)`（`responseType: 'blob'`、`cache: false`）
- 删除：`questionApi` 里所有 practice-set 函数和 `uploadApi`、`configApi`；`targetedApi.detail`、`generatePdf`、`grade`、`uploadImages`（考点卷特有的 `status`、`plan`、`create`、`prepare`、`reroll`、`recognizePage`、`recognizeJudge` 保留）

- [ ] **Step 1：写 `apiLayer.test.mjs`（读源码文本）**

- `views`、`components`、`composables`、`stores` 下没有 `axios.get|post|put|delete(` 直接请求，也没有 `fetch(` 加 `/api/` 的写法
- `api/*.js` 里下面每个地址片段只出现在一个函数里：`` `/practice-sets/${id}` ``（GET 详情）、`/generate-pdf`、`/mark-reviewed`、`'/subjects'`（GET）、`'/config/app'`、`'/config/llm'`、`'/upload/batch-simple'`、`'/upload/file'`、`'/auth/verify-password'`
- 没有文件从 `@/api/question` 导入 `configApi` 或 `uploadApi`

- [ ] **Step 2：运行，确认失败**

Run: `node --test frontend/src/api/apiLayer.test.mjs`
Expected: FAIL（列出现有的直接请求和重复定义）

- [ ] **Step 3：建四个新文件、合并 `configApi`、删重复函数**

- [ ] **Step 4：改调用处**

- 练习中心旧批改：`markPracticeSetReviewed(id)` → `practiceApi.markReviewed(id)`；`markPracticeSetReviewedWithGrading(id, results)` → `practiceApi.markReviewed(id, { question_results: results })`。
- 考点卷批改页：`targetedApi.grade(id, payload)` → `practiceApi.markReviewed(id, payload)`。
- 阅读测试：`axios.post(... mark-reviewed, { question_results: JSON.stringify(results) })` → `practiceApi.markReviewed(id, { question_results: results })`。
- 练习中心两处 `fetch('/api/upload/batch-simple')` → `const { data: uploadData } = await uploadApi.uploadImages(files)`，后面读 `uploadData.images` 的逻辑不变。
- 单词读音：`fetch(...)` + `response.blob()` → `const { data: blob } = await wordApi.audio(wordId)`；失败走原来的 catch。
- 管理中心、配置页验密码：`authApi.verifyPassword(password.value)`；配置页的模型配置：`configApi.getLlm()` / `saveLlm()`。
- 错题页的练习历史：`questionApi.practiceHistory(row.id)`。
- 阅读页：全部换成 `readingApi` 和 `practiceApi.generateFromReading`。

- [ ] **Step 5：运行 `apiLayer.test.mjs`，确认通过；跑全部前端测试**

- [ ] **Step 6：提交**

```bash
git add frontend/src
git commit -m "refactor(api): one front-end function per endpoint, no direct URLs in pages"
```

---

### Task 3：样式变量、图表主题、共用组件

**Files:**
- Modify: `frontend/src/styles/variables.css`
- Create: `frontend/src/composables/chartTheme.js`、`chartTheme.test.mjs`、`useTabQuery.js`
- Create: `frontend/src/components/ui/icons.js`、`LineIcon.vue`、`StatCard.vue`、`ChartCard.vue`、`TabBar.vue`、`ui.test.mjs`
- Modify: `frontend/src/composables/weeklyReport.js`、`frontend/src/views/WeeklyReport.vue`

**Interfaces:**
- `variables.css` 的 `:root` 追加样稿第 14–37 行的变量，名字和值原样照抄：`--bg`、`--surface`、`--ink`、`--ink-2`、`--muted`、`--line`、`--brand`、`--brand-deep`、`--brand-soft`、`--mint`、`--mint-deep`、`--mint-soft`、`--sun`、`--sun-soft`、`--coral`、`--coral-soft`、`--night`、`--r-lg`、`--r-md`、`--r-sm`、`--shadow-1`、`--shadow-2`、`--font`、`--font-num`。已有变量不改（2026-11-21 搜过，这些名字在代码里都没有被用过）。
- `chartTheme.js`（不 import `@/`）：
  - `CHART_THEME = { text: '#686e89', strong: '#1f2340', line: '#e6e5f2', main: '#4f46e5', soft: '#c7c4f7', green: '#17895a', orange: '#b4641a', grey: '#b4b4bb' }`
  - `readChartTheme(getVar)`：`getVar(name)` 读 CSS 变量，`text` ← `--muted`、`strong` ← `--ink`、`line` ← `--line`、`main` ← `--brand`、`green` ← `--mint`、`orange` ← `--sun`；读不到（空字符串）的用 `CHART_THEME` 的值；返回完整对象
  - `useChartTheme()`：在组件里调用，返回 `readChartTheme(name => getComputedStyle(document.documentElement).getPropertyValue(name).trim())`
- `weeklyReport.js`：`MAIN`、`SOFT`、`GREEN`、`LINE_GREY`、`DEFAULT_THEME` 改成取自 `CHART_THEME`；各 `xxxOption(…, theme)` 的参数含义不变（只换颜色，不改图表内容）。`WeeklyReport.vue` 的 `read_theme` 删掉，改用 `useChartTheme()`；页面里写死的 `#5b5bd6` 换成 `var(--brand)`，图例色块与日历的颜色保持一致。
- `icons.js`：`ICON_PATHS`，照抄样稿第 272–290 行的 18 个名字和路径。
- `LineIcon.vue`：props `name`（必填）、`size`（默认 20）；渲染 `<svg viewBox="0 0 24 24" aria-hidden="true">`，`fill: none; stroke: currentColor; stroke-width: 1.9; stroke-linecap/linejoin: round`；名字不存在时不渲染。
- `StatCard.vue`：props `label`、`value`、`unit`、`hint`、`tone`（`'brand'|'mint'|'sun'|'coral'|'plain'`，默认 `'plain'`）；数字用 `var(--font-num)`；`value` 为 `null` 时显示 `—`。
- `ChartCard.vue`：props `title`、`subtitle`、`height`（默认 `'260px'`）、`empty`（布尔，真时显示"暂无数据"）；默认插槽放图表；右上角具名插槽 `extra`。
- `TabBar.vue`：`v-model`（当前 key）、props `tabs: [{ key, label, badge? }]`；`badge > 0` 时显示红色数字；手机宽度下可横向滚动。
- `useTabQuery.js`：`pickTab(query, keys, fallback) -> string`（`query.tab` 在 `keys` 里就用它，否则 `fallback`），以及 `useTabQuery(keys, fallback)` 返回一个和地址 `?tab=` 双向同步的 `ref`（用 `router.replace` 改地址，不新增历史记录）。

- [ ] **Step 1：写 `chartTheme.test.mjs` 和 `ui.test.mjs`**

- `readChartTheme(() => '')` 等于 `CHART_THEME`；`readChartTheme(n => n === '--brand' ? '#000' : '')` 的 `main` 为 `'#000'`，其余不变
- `ICON_PATHS` 正好有 18 个键，包含 `home`、`words`、`flip`、`reading`、`questions`、`practice`、`weekly`、`insight`、`settings`、`more`（菜单要用的 10 个）
- `pickTab({tab:'all'}, ['review','all'], 'review') === 'all'`；`pickTab({tab:'x'}, …) === 'review'`；`pickTab({}, …) === 'review'`

- [ ] **Step 2：运行，确认失败**

- [ ] **Step 3：实现上面的文件，改 `weeklyReport.js` 和 `WeeklyReport.vue`**

- [ ] **Step 4：跑全部前端测试（`weeklyReport.test.mjs` 必须照常通过）**

- [ ] **Step 5：提交**

```bash
git add frontend/src
git commit -m "feat(ui): shared tokens, chart theme, icon, stat/chart cards and tab bar"
```

---

### Task 4：去掉 `echarts-gl`

**Files:**
- Modify: `frontend/src/views/Home.vue`（删 `import 'echarts-gl'`）、`frontend/package.json`、`frontend/package-lock.json`
- Delete（被跟踪的依赖目录）：`frontend/node_modules/echarts-gl`、`frontend/node_modules/claygl`

- [ ] **Step 1：确认没有三维图表**

Run: `grep -rnE "echarts-gl|grid3D|bar3D|scatter3D|line3D|surface|globe|geo3D" frontend/src`
Expected: 只有 `Home.vue` 的 import。`claygl` 只被 `echarts-gl` 依赖（看 `package-lock.json`）。

- [ ] **Step 2：在 `frontend` 目录 `npm uninstall echarts-gl --legacy-peer-deps`，删掉 `Home.vue` 的 import**

- [ ] **Step 3：构建**

Run: `python backend/scripts/prepare_cloudflare_frontend.py`
Expected: 成功；产物里搜不到 `claygl`。

- [ ] **Step 4：提交（不带 `node_modules/.package-lock.json`）**

```bash
git add frontend/package.json frontend/package-lock.json frontend/src/views/Home.vue
git add -A frontend/node_modules/echarts-gl frontend/node_modules/claygl
git commit -m "chore(ui): drop unused echarts-gl"
```

---

### Task 5：发布与记录

- [ ] **Step 1：跑全部前端测试和后端现有测试**（后端没改，确认基线）
- [ ] **Step 2：独立审阅整个分支，修掉严重和重要的问题**
- [ ] **Step 3：快进合并进本地 `main`**
- [ ] **Step 4：发布 Pages**（只发前端；照 `docs/cloudflare-migration-status.md` 的"日常部署"，在 `cloudflare/pages` 目录执行，记下发布前后的部署号）
- [ ] **Step 5：核对**：`/health` 200、首页跳登录 303、新构建的主脚本能从正式域名取到
- [ ] **Step 6：在 `docs/cloudflare-migration-status.md` 追加变更记录，更新 `CLAUDE.md`（`stores/`、`components/ui/` 的说明）和路线图状态行；提交、合并、推送远端**
- [ ] **Step 7：把需要登录核对的项目记下来，留到第 4 步完成后一起交给用户**：学科下拉、出卷页科目、知识星空两科、管理中心增删学科标签后录入页能看到、练习中心上传批改照片、单词读音、配置页验密码和模型配置、阅读页生成和做题提交、周报图表颜色
