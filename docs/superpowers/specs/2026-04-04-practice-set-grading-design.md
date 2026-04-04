# 练习集批改与正确率统计 设计方案

## 概述

这是一个练习集批改与正确率统计的功能增强，涉及练习集列表、详情页、批改流程、错题表字段等多个模块。

## 核心数据结构

### 练习集（PracticeSet）
- 新增 `accuracy` 字段：整体正确率（百分比，0-100）
- 列表展示正确率，为空显示 "-"

### 练习集-题目关联表（PracticeSetQuestion）
- 新增 `is_correct` 字段：记录每题批改是否正确（null=未批改，true=正确，false=错误）

### 错题（Question）
- 现有 `review_count`：复习次数
- 新增 `error_count`：错误次数（批改错误+1）
- 新增 `correct_count`：正确次数（批改正确+1）
- 正确率 = correct_count / (correct_count + error_count)，若两者都为0则正确率为null

## 功能模块

### 1. 练习集列表正确率列

**列表新增列：**
- 列名：正确率
- 位置：题目数列之后
- 显示规则：
  - 有值显示百分比（如 "85%"）
  - 无值（null或0）显示 "-"
  - 单词复习集显示 "-"

### 2. 练习集详情展示原题

**错题练习集详情Tab：**
- 题目列表增加"原题"列
- 显示原始错题的题目内容（前50字符截断）
- 若有原图则显示缩略图

### 3. 批改流程（标记已复习时）

**前置条件：**
- 练习集来源为错题（source_type='question'）时才需要批改
- 单词复习集直接标记已复习

**整体批改：**
1. 弹窗标题："批改练习集"
2. 显示题目数量
3. 两个选项按钮：
   - "全部正确" - 正确率100%
   - "有错误" - 进入逐题批改

**逐题批改：**
1. 逐题显示：
   - 题目序号和内容
   - 若有原题图片则显示
   - 原题答案
2. 每题两个按钮："正确" / "错误"
3. 底部显示已批改数量和当前正确率
4. 全部完成后显示汇总，确认提交

**数据更新：**
- 练习集 accuracy = 正确题数 / 总题数 * 100
- 每道题目 is_correct 记录批改结果
- 关联错题的 review_count + 1
- 关联错题的 correct_count 或 error_count +1

### 4. 批改时上传图片

**上传弹窗：**
- 标题："上传复习完成图片（选填）"
- 可上传多张图片（非必填）
- 上传后存储在练习集的 review_images 字段

**流程调整：**
1. 先完成批改流程
2. 批改完成后弹出图片上传
3. 图片上传非必填，可跳过

### 5. 错题表字段

**新增字段：**
- `error_count`：错误次数，默认0
- `correct_count`：正确次数，默认0

**计数逻辑：**
- 每次批改时：
  - 批改正确：correct_count + 1
  - 批改错误：error_count + 1
- 每次复习标记：review_count + 1

**正确率计算：**
- 正确率 = correct_count / (correct_count + error_count) * 100%
- 若 correct_count + error_count = 0，正确率为 null

### 6. 错题列表正确率筛选

**筛选条件：**
- 按准确率区间筛选：
  - 0-30%（薄弱）
  - 30-60%（一般）
  - 60-80%（良好）
  - 80-100%（掌握）
  - 未筛选（无统计）

**排序支持：**
- 支持按正确率升序/降序排序

## API 变更

### POST /api/practice-sets/{id}/mark-reviewed

**请求参数调整：**
- 新增 `is_all_correct` 参数（bool）：整体批改时是否全对
- 新增 `question_results` 参数（array）：逐题批改结果
  ```json
  {
    "question_results": [
      {"question_id": 1, "is_correct": true},
      {"question_id": 2, "is_correct": false}
    ]
  }
  ```
- 图片上传保持原逻辑

**响应调整：**
```json
{
  "message": "已标记为复习",
  "review_count": 1,
  "accuracy": 85.7
}
```

## 数据库变更

### question 表
```sql
ALTER TABLE question ADD COLUMN error_count INTEGER DEFAULT 0;
ALTER TABLE question ADD COLUMN correct_count INTEGER DEFAULT 0;
```

### practice_set_question 表
```sql
ALTER TABLE practice_set_question ADD COLUMN is_correct BOOLEAN;
```

### practice_set 表
```sql
ALTER TABLE practice_set ADD COLUMN accuracy FLOAT;
```

## 前端页面变更

### 练习集列表页
- 表格增加"正确率"列
- 筛选条件不变

### 练习集详情弹窗
- 详情Tab：题目列表增加"原题"列
- 单词练习Tab保持不变

### 批改流程
- 整体批改弹窗
- 逐题批改弹窗
- 图片上传弹窗

### 错题列表页
- 筛选条件增加"准确率区间"
- 列表增加正确率列
- 支持按正确率排序
