# 错题列表打印更新实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 更新练习集PDF打印样式：删除答题区域、增加ID/知识点/错误类型标注、难度改用彩色星号显示

**Architecture:** 修改 `PracticeSetPDF.add_question()` 方法，重构题目头部布局，替换难度文字为彩色星号，移除答题虚线框

**Tech Stack:** Python fpdf2, 中文字体 simhei.ttf

---

### Task 1: 修改 `add_question` 方法头部标注

**Files:**
- Modify: `backend/app/services/pdf.py:97-130`

**Steps:**

- [ ] **Step 1: 替换 add_question 方法**

将 `backend/app/services/pdf.py` 第 97-130 行的 `add_question` 方法替换为以下完整代码：

```python
def add_question(self, index: int, question_text: str, difficulty: int, question_id: int = None,
                 knowledge_point: str = None, error_type: str = None):
    """添加一道题目"""
    # 难度星号配色
    star_colors = {
        1: (255, 102, 102),   # #ff6666 绿-难度低用绿色系
        2: (255, 153, 102),   # #ff9966
        3: (255, 204, 102),   # #ffcc66 橙
        4: (255, 102, 102),   # #ff6666 红
        5: (238, 102, 102),   # #ee6666 深红
    }
    empty_star_color = (220, 223, 230)  # #dcdfe6 灰色

    # 绘制星号
    def draw_stars(difficulty):
        filled = min(max(difficulty, 0), 5)
        empty = 5 - filled
        for i in range(filled):
            self.set_text_color(*star_colors.get(difficulty, (255, 102, 102)))
            self.set_font('chinese_b', size=10)
            self.cell(8, 6, '★', new_x=XPos.RIGHT, new_y=YPos.TOP, align='C')
        for i in range(empty):
            self.set_text_color(*empty_star_color)
            self.set_font('chinese', size=10)
            self.cell(8, 6, '★', new_x=XPos.RIGHT, new_y=YPos.TOP, align='C')
        self.set_text_color(51, 51, 51)

    # 题目头部：ID + 序号 + 星号 + 知识点 + 错误类型
    self.set_font('chinese_b', size=10)
    self.set_fill_color(78, 205, 196)  # #4ECDC4
    self.set_text_color(255, 255, 255)

    # ID标注
    if question_id:
        id_text = f'ID:{question_id}'
        self.cell(0, 7, id_text, new_x=XPos.RIGHT, new_y=YPos.TOP, align='L', fill=False)

    # 序号
    self.cell(0, 7, f'第{index}题', new_x=XPos.RIGHT, new_y=YPos.TOP, align='C', fill=True)

    # 星号（替代难度文字）
    self.set_fill_color(248, 249, 250)
    self.set_text_color(51, 51, 51)
    draw_stars(difficulty)
    self.ln(1)

    # 副行：知识点 + 错误类型
    self.set_font('chinese', size=9)
    self.set_text_color(128, 128, 128)
    parts = []
    if knowledge_point:
        parts.append(f'知识点: {knowledge_point}')
    if error_type:
        parts.append(f'错误类型: {error_type}')
    if parts:
        self.cell(0, 5, '  |  '.join(parts), new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='L')

    self.ln(2)

    # 分隔线
    self.set_draw_color(189, 195, 199)
    self.set_line_width(0.3)
    self.line(10, self.get_y(), 200, self.get_y())
    self.ln(4)

    # 题目内容
    self.set_font('chinese', size=11)
    self.set_text_color(51, 51, 51)
    safe_text = decode_html(question_text) if question_text else '暂无题目内容'
    self.multi_cell(0, 6, safe_text)
    self.ln(6)
```

- [ ] **Step 2: 提交**

```bash
git add backend/app/services/pdf.py
git commit -m "feat: update question print layout - remove answer area, add id/knowledge/error_type, use colored stars for difficulty"
```

---

**验证方式：**
生成一个练习集PDF，检查每道题的：
1. 无底部60px虚线答题框
2. 头部有 ID、序号、彩色星号、知识点、错误类型
3. 星号填充色根据难度变化

**Spec 核对：**
- [x] 删除答题区域
- [x] 增加 ID、知识点、错误类型标注
- [x] 难度使用彩色星号（1-5星填充色，☆灰色）
- [x] 星号配色：难度高红色，低绿色
