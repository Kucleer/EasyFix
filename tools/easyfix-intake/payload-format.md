# 提交文件的格式

这是提交给 EasyFix 的 JSON 文件的完整格式。`SKILL.md` 讲怎么判题、什么时候停，
这里讲每个字段怎么填。用到时再读。

整份文件要么全部入库、要么整份退回：只要有一道题不合格，`check` / `submit` 会返回
退出码 2 和一份问题清单（`errors`，每条带 `index` 指第几道题），全部改好后再提交。

`spec_version` 和 `request_id` 由小工具自动补，**你不用写**。

## 顶层结构

```json
{
  "paper": { ...一份卷子的信息... },
  "questions": [ ...每道错题一个对象，1 到 100 道... ]
}
```

## `paper`（卷子）

| 字段 | 必填 | 说明 |
| --- | --- | --- |
| `subject_id` | **是** | 学科编号，取自 `guide` 返回的学科列表（不是学科名字）。学科必须存在。 |
| `name` |  | 卷子名称。不填时系统默认"学科名 + 习题 + 日期"，如"数学习题 2026-11-10"。家长回"跳过"就不要填。 |
| `paper_type` |  | `homework` 作业（默认）／`chapter_practice` 章节练习／`exam` 考试。 |
| `exam_kind` |  | 只有考试才有意义：`unit` 单元测／`midterm` 期中／`final` 期末／`other` 其他（考试时不填默认 `other`）。 |
| `paper_date` |  | `YYYY-MM-DD`。只有家长说了、或卷面印着才填；否则不填（系统按今天当录入日）。不能是未来的日期。 |
| `grade` |  | 年级 1–12。家长说了或卷面印着才填，否则用 `guide` 的默认年级。 |
| `semester` |  | 学期 1 或 2。同上，否则用 `guide` 的默认学期。 |
| `score` / `full_score` |  | 得分、满分。**要么都填要么都不填**；都不小于 0；得分不大于满分。一般只有考试才填。 |
| `images` |  | 照片存储路径的数组，按页顺序。**必须是 `upload` 命令返回的那种路径**（形如 `2026/11/ab12cd34_p1.jpg`），不能自己编路径。家长说不用上传图片时留空数组 `[]`。 |
| `notes` |  | 备注，可空。 |

## `questions`（每道错题一个对象）

| 字段 | 必填 | 说明 |
| --- | --- | --- |
| `parsed_question` | **是** | 题干。空着会被退回。 |
| `page` | 看情况 | 这道题在第几张照片，从 1 开始。**卷子有照片时必填**，范围 1 到照片张数；**卷子没有照片时必须留空**（设为 null 或不写）。 |
| `question_no` |  | 卷面上的题号，文字，如"二、5"。核对时靠它在整页照片上找到这道题，尽量填。 |
| `answer` |  | 正确答案。 |
| `analysis` |  | 解析。 |
| `wrong_answer` |  | 孩子写的答案，从卷面照抄。**看不清就留空，绝不编造。** 留空不会让这道题变成待核对。 |
| `wrong_evidence` |  | 判错依据，如"老师打叉""有红笔订正""老师没有批改这一题，验算得数不对"。**不填的话系统会自动把这道题标成待核对（`wrong_unclear`）**，所以凡是确定做错的题都要写清依据。 |
| `difficulty` |  | 难度 1–5，默认 3。 |
| `error_type` |  | 错因，逗号分隔。每一项**必须在 `guide` 返回的 `error_types` 清单里**（清单为空时可不填，也不校验）。不要因为题型复杂就随手标"计算"。 |
| `knowledge_point_ids` |  | 考点编号数组，**只能用 `guide` 清单里的二级考点编号，不能用文字名称**。 |
| `primary_knowledge_point_id` |  | 主考点编号，取自上面的数组。**没有主考点、且这个年级有考点目录时，系统会自动标成待核对（`kp_unsure`）。** 清单为空（`catalog_available` 为 false）时留空即可，不算待核对。 |
| `needs_review` |  | 是否待核对，`true` / `false`（默认 `false`）。标 `true` 时 `review_reasons` 不能为空。 |
| `review_reasons` |  | 待核对原因代码数组，见下。 |
| `review_note` |  | 一句话说清疑问在哪，给家长看。标了待核对就写上。 |

### 什么时候会变成"待核对"

一道题满足下面任一条就是待核对（其余直接入库）：

- 你把 `needs_review` 标成了 `true`（此时必须给 `review_reasons`）；
- `wrong_evidence` 留空了 → 系统自动加原因 `wrong_unclear`；
- 没有主考点、且这个年级有考点目录 → 系统自动加原因 `kp_unsure`。

### 四个待核对原因代码

| 代码 | 什么时候用 |
| --- | --- |
| `wrong_unclear` | 不确定这题是否做错了：符号和你的验算对不上；或老师没有批改、但你验算发现写错了（`review_note` 写"老师没有批改这一题"）。 |
| `text_unclear` | 照片模糊、缺字或被裁切，题干或孩子的答案拿不准。 |
| `kp_unsure` | `guide` 清单里找不到合适的考点。 |
| `other` | 其他说不清的疑问，具体写在 `review_note` 里。 |

## 数学公式写法

数学题的题干、答案、解析里的公式沿用现有规范（整份卷子一次送检）：

- 行内公式 `\(...\)`，独立公式 `\[...\]`。
- 次方带花括号，如 `x^{2026}`。
- 分数用 `\frac{a}{b}`。

## 完整示例

两道题：第一道确定做错、直接入库；第二道老师没批改但验算是错的，标为待核对。

```json
{
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
      "error_type": "概念不清",
      "knowledge_point_ids": [15],
      "primary_knowledge_point_id": 15,
      "needs_review": true,
      "review_reasons": ["wrong_unclear"],
      "review_note": "老师没有批改这一题，按验算结果判为错"
    }
  ]
}
```
