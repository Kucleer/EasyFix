# 提交文件的格式

这是提交给 EasyFix 的 JSON 文件的完整格式。`SKILL.md` 讲怎么判题、什么时候停，
这里讲每个字段怎么填、以及怎么把文件写对。用到时再读。

整份文件要么全部入库、要么整份退回：只要有一处不合格，`check` / `submit` 会返回
退出码 2 和一份问题清单（`errors`）。清单里卷子级的问题（家长回答、公式、分数等）
`index` 为 null，题目的问题 `index` 是第几道题（从 0 数）。全部改好后再提交。

`spec_version` 和 `request_id` 由小工具自动补，**你不用写**。

## 顶层结构

```json
{
  "parent_reply": "家长怎么回答的（必填）",
  "paper": { "...一份卷子的信息..." : "" },
  "questions": [ "...每道错题一个对象，1 到 100 道..." ]
}
```

## 顶层 `parent_reply`（必填）

家长对"这是哪份作业或卷子？如果是考试，多少分？"这一问的回答，1 到 200 个字：

- 家长说了是哪份 → 写家长的原话（如"第三章数学单元测试，考了 85 分"）。
- 家长回"跳过" → 写 `跳过`。
- 家长说过不用问 → 写 `家长说不用问`。

不写、为空、或只有空白，整份都会被退回。它不会存进数据库，只用来确认你确实问过。

## `paper`（卷子）

| 字段 | 必填 | 说明 |
| --- | --- | --- |
| `subject_id` | **是** | 学科编号，取自 `guide` 返回的学科列表（不是学科名字）。学科必须存在。 |
| `name` |  | 卷子名称。不填时系统默认"学科名 + 习题 + 日期"，如"数学习题 2026-11-10"。家长回"跳过"就不要填。 |
| `paper_type` |  | `homework` 作业（默认）／`chapter_practice` 章节练习／`exam` 考试。 |
| `exam_kind` |  | 只有考试才有意义：`unit` 单元测／`midterm` 期中／`final` 期末／`other` 其他（考试时不填默认 `other`）。 |
| `paper_date` |  | `YYYY-MM-DD`。只有家长说了、或卷面印着才填；否则不填（系统按今天当录入日）。不能是未来的日期。 |
| `grade` |  | 年级 1–12。家长说了或卷面印着才填，否则留空，**系统会自动补默认年级**，不用你去抄 `guide` 的默认值。 |
| `semester` |  | 学期 1 或 2。同上，否则留空，系统会自动补默认学期。 |
| `score` / `full_score` |  | 得分、满分。**要么都填要么都不填**；都不小于 0；得分不大于满分。一般只有考试才填。 |
| `images` |  | 照片存储路径的数组，按页顺序。**必须是 `upload` 命令返回的那种路径**（形如 `2026/11/ab12cd34_p1.jpg`），不能自己编路径。家长说不用上传图片时留空数组 `[]`。 |
| `notes` |  | 备注，可空。 |

## `questions`（每道错题一个对象）

| 字段 | 必填 | 说明 |
| --- | --- | --- |
| `parsed_question` | **是** | 题干。空着会被退回。 |
| `page` | 看情况 | 这道题在第几张照片，从 1 开始。**卷子有照片时必填**，范围 1 到照片张数；**卷子没有照片时必须留空**（设为 null 或不写）。 |
| `question_no` |  | 卷面上的题号，**照卷面印刷的样子写**（卷面印 I、II 就写 I、II，印 一、二 就写 一、二），如"二、5"。核对时靠它在整页照片上找到这道题，尽量填。 |
| `answer` |  | 正确答案。 |
| `analysis` |  | 解析。 |
| `wrong_answer` |  | 孩子写的答案，**逐字照抄能认清的字；哪怕一个字拿不准，整条留空**，绝不编造、不写近似或音译的读法。留空不会让这道题变成待核对。近似读法只有在这题已因别的原因待核对时，才能写进 `review_note`（"看起来像…，不确定"），不进 `wrong_answer`、也不进 `wrong_evidence`。 |
| `wrong_evidence` |  | 判错依据，如"老师打叉""有红笔订正""老师没有批改这一题，验算得数不对"。老师判错但孩子字迹看不清时，写"老师判错，孩子字迹看不清"——这类直接入库、不标待核对。**不填的话系统会自动把这道题标成待核对（`wrong_unclear`）**，所以凡是确定做错的题都要写清依据。 |
| `difficulty` |  | 难度 1–5，默认 3。 |
| `error_type` |  | 错因，逗号分隔。每一项**必须在 `guide` 返回的 `error_types` 清单里**（清单为空时可不填，也不校验）。不要因为题型复杂就随手标"计算"。 |
| `knowledge_point_ids` |  | 考点编号数组，**只能用 `guide` 清单里的二级考点编号，不能用文字名称**。 |
| `primary_knowledge_point_id` |  | 主考点编号，取自上面的数组。**没有主考点、且这个年级有考点目录时，系统会自动标成待核对（`kp_unsure`）。** 清单为空（`catalog_available` 为 false）时留空即可，不算待核对。 |
| `needs_review` |  | 是否待核对，`true` / `false`（默认 `false`）。标 `true` 时 `review_reasons` 不能为空。 |
| `review_reasons` |  | 待核对原因代码数组，见下。 |
| `review_note` |  | 一句话说清疑问在哪，给家长看。标了待核对就写上。**老师没有批改的题，这一句必须以"老师没有批改这一题"开头。** |

### 什么时候会变成"待核对"

一道题满足下面任一条就是待核对（其余直接入库）：

- 你把 `needs_review` 标成了 `true`（此时必须给 `review_reasons`）；
- `wrong_evidence` 留空了 → 系统自动加原因 `wrong_unclear`；
- 没有主考点、且这个年级有考点目录 → 系统自动加原因 `kp_unsure`。

### 四个待核对原因代码

| 代码 | 什么时候用 |
| --- | --- |
| `wrong_unclear` | **只用于"不确定孩子到底做错了没有"**：符号和你的验算对不上；或老师没有批改、但你验算发现写错了；或你自己也做不出、老师的符号也看不清。**孩子的答案看不清不属于这里**——老师判错就直接入库、`wrong_answer` 留空、`wrong_evidence` 写明字迹看不清，不用这个代码。 |
| `text_unclear` | **题干或正确答案**拿不准：照片模糊、缺字或被裁切。孩子的答案看不清不属于这里（按上面 `wrong_answer` 留空处理，不标 `text_unclear`）。 |
| `kp_unsure` | 看遍所有模块后，`guide` 清单里仍找不到合适的考点。 |
| `other` | 其他说不清的疑问，具体写在 `review_note` 里。 |

## 多小问的大题怎么拆（`SKILL.md` 指到这里）

- 各小问能独立成立（如并列的计算 (1)…(8)）→ 每道做错的小问各录一条，`question_no` 写成"4(3)"。
- 共用一个题干、图、表，或只共用一段"定义新运算 / 给定条件"的说明、各小问本身能独立做的
  → 都算共用题干，整题只录一条：题干写全，`question_no` 写印刷的大题号，做错的小问连同孩子的
  答案写进 `wrong_answer`，哪几小问错写进 `wrong_evidence`；只要有一小问要待核对，这一条就按那个
  原因标待核对。

## 数值对但写法被判错（`SKILL.md` 指到这里）

孩子的得数对、但写法不合规范被老师判错（如把字母写在数字前、漏写乘号、式子格式不对）：
这不是"符号和验算对不上"，是实实在在的书写错误，**正常录入、不标 `wrong_unclear`**，
考点选"书写规范"那一类。

## 怎么把文件写对（公式的反斜杠最容易写坏）

JSON 里一个反斜杠要写成**两个**。`\frac` 直接写进文件会被当成 `\f`（换页控制字符），
公式就坏了；服务器会退回并提示"公式里的反斜杠没有写对：JSON 里每个反斜杠要写成两个……"。
两种稳妥的写法，任选其一：

- **用小脚本生成（推荐）：** 在 Python 里把内容拼成数据，用
  `json.dump(data, f, ensure_ascii=False)` 写文件，普通反斜杠用原始字符串即可，如
  `r"\(\frac{1}{2}\)"`，`json.dump` 会替你把每个反斜杠转成两个。**但 LaTeX 自己的换行 `\\`
  本身就是两个反斜杠，原始字符串里也要照打两个**，即写成 `r"...\\..."`。
- **手写 JSON 文本：** 每个反斜杠都写成两个，如 `\\(`、`\\frac`、`\\times`；**换行 `\\`
  要写成四个反斜杠 `\\\\`**。

矩阵、行列式、多行公式（`\begin{vmatrix}…\end{vmatrix}`、`\begin{cases}…`、`\begin{aligned}…` 等）
里行与行之间用 `\\` 换行。只写了一个反斜杠时服务器会退回并提示"矩阵或多行公式里的换行没有
写对：换行要写成两个反斜杠 `\\`（手写 JSON 时是四个）"。

另外，普通文字里用空格代替制表符（TAB），换行只用 `\n`（不要 Windows 的 `\r\n`）——
这些控制字符也会被退回。

## 完整示例

四道题：第一道确定做错、直接入库；第二道老师没批改但验算是错的，标为待核对；
第三道是共用一个表格的多小问题，整题只录一条；第四道是行列式（看换行 `\\` 的正确写法），
孩子字迹看不清但老师判错，照样直接入库、`wrong_answer` 留空。

```json
{
  "parent_reply": "第三章数学单元测试，考了 85 分",
  "paper": {
    "subject_id": 1,
    "name": "第三章单元测试",
    "paper_type": "exam",
    "exam_kind": "unit",
    "paper_date": "2026-11-08",
    "grade": 6,
    "semester": 1,
    "score": 85,
    "full_score": 100,
    "images": ["2026/11/ab12cd34_p1.jpg", "2026/11/ef56ab78_p2.jpg"],
    "notes": ""
  },
  "questions": [
    {
      "page": 1,
      "question_no": "二、5",
      "parsed_question": "计算 \\(\\frac{2}{3}+\\frac{1}{6}\\)。",
      "answer": "\\(\\frac{5}{6}\\)",
      "analysis": "先通分再相加。",
      "wrong_answer": "\\(\\frac{3}{9}\\)",
      "wrong_evidence": "老师打叉",
      "difficulty": 3,
      "error_type": "计算错误",
      "knowledge_point_ids": [12, 15],
      "primary_knowledge_point_id": 12,
      "needs_review": false,
      "review_reasons": [],
      "review_note": ""
    },
    {
      "page": 2,
      "question_no": "三、2",
      "parsed_question": "一个长方形长 8 厘米、宽 3 厘米，求周长。",
      "answer": "22 厘米",
      "analysis": "周长 =（长 + 宽）× 2。",
      "wrong_answer": "",
      "wrong_evidence": "老师没有批改这一题，验算得数不对",
      "difficulty": 4,
      "error_type": "概念错误",
      "knowledge_point_ids": [15],
      "primary_knowledge_point_id": 15,
      "needs_review": true,
      "review_reasons": ["wrong_unclear"],
      "review_note": "老师没有批改这一题，按验算结果判为错"
    },
    {
      "page": 2,
      "question_no": "四、3",
      "parsed_question": "下表是用火柴棒拼三角形的根数规律，回答 (1)(2)：拼 n 个三角形用多少根？拼第 10 个图形用多少根？",
      "answer": "(1) 2n+1；(2) 21 根",
      "analysis": "每多拼一个三角形增加 2 根。",
      "wrong_answer": "(2) 写成 20",
      "wrong_evidence": "老师在 (2) 上打叉，(1) 正确",
      "difficulty": 4,
      "error_type": "概念错误",
      "knowledge_point_ids": [15],
      "primary_knowledge_point_id": 15,
      "needs_review": false,
      "review_reasons": [],
      "review_note": ""
    },
    {
      "page": 2,
      "question_no": "五、1",
      "parsed_question": "计算行列式 \\[\\begin{vmatrix} 1 & 2 \\\\ 3 & 4 \\end{vmatrix}\\]。",
      "answer": "-2",
      "analysis": "主对角线乘积减副对角线乘积：\\(1\\times 4-2\\times 3\\)。",
      "wrong_answer": "",
      "wrong_evidence": "老师打叉，孩子的字迹看不清",
      "difficulty": 3,
      "error_type": "计算错误",
      "knowledge_point_ids": [15],
      "primary_knowledge_point_id": 15,
      "needs_review": false,
      "review_reasons": [],
      "review_note": ""
    }
  ]
}
```
