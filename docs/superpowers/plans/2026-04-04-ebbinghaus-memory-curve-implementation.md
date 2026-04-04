# 艾宾浩斯记忆曲线复习功能实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现基于艾宾浩斯遗忘曲线的单词复习功能，包括记忆阶段展示、复习历史时间轴、智能复习抽取、首页待复习卡片。

**Architecture:**
- 后端：Word 模型新增 `learning_phase` 字段，修改 `submit_review` 更新阶段和间隔，新增记忆曲线 API，修改首页统计 API
- 前端：单词详情页新增"记忆曲线" Tab，首页"复习次数"卡片改为"待复习"

**Tech Stack:** Python FastAPI + SQLAlchemy, Vue 3 + Element Plus

---

## 文件结构

### 后端变更
- `backend/app/models/word.py` — 新增 `learning_phase` 字段
- `backend/app/routers/word.py` — 修改复习抽取算法、submit_review 更新阶段、新增 memory-curve API
- `backend/app/routers/stats.py` — 首页统计新增待复习数量
- `backend/app/schemas/word.py` — 新增 MemoryCurveResponse schema

### 前端变更
- `frontend/src/views/Words.vue` — 单词详情页新增记忆曲线 Tab
- `frontend/src/views/Home.vue` — "复习次数"卡片改为"待复习"
- `frontend/src/api/word.js` — 新增 memory-curve API 调用

### 数据变更
- 数据库迁移：新增 `learning_phase` 列到 `word` 表
- 历史数据初始化：根据 review_count 和 correct_count 初始化所有单词的 learning_phase

---

## 任务清单

### Task 1: 数据库迁移 - 新增 learning_phase 字段

**文件:**
- Modify: `backend/app/models/word.py:38` — 新增 learning_phase 字段定义

- [ ] **Step 1: 修改 Word 模型**

在 `backend/app/models/word.py` 的 Word 类中，`interval` 字段后新增：

```python
learning_phase = Column(String(20), default="新学")  # 新学/在途/遗忘点/牢记
```

- [ ] **Step 2: 记录 SQL 迁移语句**

用户提供以下 SQL 执行：

```sql
ALTER TABLE word ADD COLUMN learning_phase VARCHAR(20) DEFAULT '新学';
```

- [ ] **Step 3: 提交**

```bash
git add backend/app/models/word.py
git commit -m "feat(word): add learning_phase field for ebbinghaus curve"
```

---

### Task 2: 修改 submit_review - 更新 learning_phase 和 interval

**文件:**
- Modify: `backend/app/routers/word.py:452-467`

- [ ] **Step 1: 读取当前 submit_review 代码**

确认现有逻辑位置。

- [ ] **Step 2: 修改 interval 更新逻辑**

找到 `word.interval = min((word.interval or 1) * 2, 30)` 附近代码，修改为：

```python
# 更新间隔和阶段
if result.is_correct:
    word.correct_count = (word.correct_count or 0) + 1
    correct_count += 1
    # 艾宾浩斯间隔：答对则加倍，最多30天
    word.interval = min((word.interval or 1) * 2, 30)
    # 更新阶段
    consecutive_correct = _get_consecutive_correct(word.id, db)
    if consecutive_correct >= 3 and word.interval >= 7:
        word.learning_phase = "牢记"
    elif word.next_review_at and word.next_review_at <= datetime.now():
        word.learning_phase = "遗忘点"
    else:
        word.learning_phase = "在途"
else:
    error_count += 1
    word.interval = 1  # 错误后重置为1天
    word.learning_phase = "在途"  # 退回在途
```

- [ ] **Step 3: 新增辅助函数**

在 `_get_accuracy_level` 函数后新增：

```python
def _get_consecutive_correct(word_id: int, db: Session) -> int:
    """获取连续正确次数"""
    logs = db.query(WordReviewLog).filter(
        WordReviewLog.word_id == word_id,
        WordReviewLog.deleted == False
    ).order_by(WordReviewLog.reviewed_at.desc()).limit(10).all()

    consecutive = 0
    for log in reversed(logs):
        if log.is_correct:
            consecutive += 1
        else:
            break
    return consecutive
```

- [ ] **Step 4: 提交**

```bash
git add backend/app/routers/word.py
git commit -m "feat(word): update learning_phase in submit_review"
```

---

### Task 3: 新增记忆曲线 API

**文件:**
- Modify: `backend/app/routers/word.py` — 新增 `/words/{word_id}/memory-curve` 端点
- Modify: `backend/app/schemas/word.py` — 新增 MemoryCurveResponse schema

- [ ] **Step 1: 添加 schema**

在 `backend/app/schemas/word.py` 末尾添加：

```python
class MemoryCurveResponse(BaseModel):
    """记忆曲线响应"""
    word_id: int
    learning_phase: str
    interval: int
    next_review_at: Optional[datetime] = None
    review_history: List[dict] = []

    class Config:
        from_attributes = True
```

- [ ] **Step 2: 添加 API 端点**

在 `backend/app/routers/word.py` 末尾添加：

```python
@router.get("/{word_id}/memory-curve", response_model=MemoryCurveResponse)
def get_memory_curve(word_id: int, db: Session = Depends(get_db)):
    """获取单词记忆曲线"""
    word = db.query(Word).filter(Word.id == word_id, Word.deleted == False).first()
    if not word:
        raise HTTPException(status_code=404, detail="单词不存在")

    # 获取复习历史
    logs = db.query(WordReviewLog).filter(
        WordReviewLog.word_id == word_id,
        WordReviewLog.deleted == False
    ).order_by(WordReviewLog.reviewed_at.desc()).all()

    review_history = []
    for log in logs:
        review_history.append({
            "reviewed_at": log.reviewed_at,
            "is_correct": log.is_correct,
            "user_answer": log.user_answer or " - "
        })

    return {
        "word_id": word.id,
        "learning_phase": word.learning_phase or "新学",
        "interval": word.interval or 1,
        "next_review_at": word.next_review_at,
        "review_history": review_history
    }
```

- [ ] **Step 3: 提交**

```bash
git add backend/app/routers/word.py backend/app/schemas/word.py
git commit -m "feat(word): add memory-curve API endpoint"
```

---

### Task 4: 修改复习抽取算法

**文件:**
- Modify: `backend/app/routers/word.py:340-391`

- [ ] **Step 1: 读取当前 start_review 代码**

确认智能抽样算法位置。

- [ ] **Step 2: 替换为新算法**

找到 pool_a/pool_b/pool_c 分组代码，替换为：

```python
# 新算法：按优先级抽取
pool_unreviewed = []  # 未复习
pool_due = []         # 曲线到期
pool_low_acc = []     # 低正确率(<60%)
pool_other = []       # 其他

now = datetime.now()
for w in all_words:
    accuracy = (w.correct_count / w.review_count * 100) if w.review_count and w.review_count > 0 else 0
    if w.review_count == 0:
        pool_unreviewed.append(w)
    elif w.next_review_at and w.next_review_at <= now:
        pool_due.append(w)
    elif accuracy < 60:
        pool_low_acc.append(w)
    else:
        pool_other.append(w)

selected_words = []
remaining_count = min(count, len(all_words))

# 1. 优先从未复习抽取
a_count = min(len(pool_unreviewed), remaining_count)
if a_count > 0:
    selected_words.extend(random.sample(pool_unreviewed, a_count))
    remaining_count -= a_count

# 2. 曲线到期单词
if remaining_count > 0:
    d_count = min(len(pool_due), remaining_count)
    if d_count > 0:
        selected_words.extend(random.sample(pool_due, d_count))
        remaining_count -= d_count

# 3. 低正确率
if remaining_count > 0:
    b_count = min(len(pool_low_acc), remaining_count)
    if b_count > 0:
        selected_words.extend(random.sample(pool_low_acc, b_count))
        remaining_count -= b_count

# 4. 随机其他
if remaining_count > 0:
    o_count = min(len(pool_other), remaining_count)
    if o_count > 0:
        selected_words.extend(random.sample(pool_other, o_count))
```

- [ ] **Step 3: 提交**

```bash
git add backend/app/routers/word.py
git commit -m "feat(word): update review selection to ebbinghaus priority"
```

---

### Task 5: 修改首页统计 API

**文件:**
- Modify: `backend/app/routers/question.py` — 找到 stats home API
- Modify: `backend/app/schemas/question.py` — WordStatsResponse 新增 to_review_count

- [ ] **Step 1: 修改 WordStatsResponse schema**

在 `backend/app/schemas/question.py` 的 `WordStatsResponse` 类中，新增字段：

```python
to_review_count: int = 0  # 待复习单词数（未复习+曲线到期）
```

- [ ] **Step 2: 找到 stats home API**

在 `backend/app/routers/question.py` 中找到返回 `word_stats` 的 API。

- [ ] **Step 3: 修改统计查询**

在返回 word_stats 的地方，添加待复习数量计算：

```python
# 待复习 = 未复习 + 曲线到期
from app.models import Word
from datetime import datetime
now = datetime.now()
unreviewed_count = db.query(Word).filter(Word.deleted == False, Word.review_count == 0).count()
due_count = db.query(Word).filter(Word.deleted == False, Word.next_review_at != None, Word.next_review_at <= now).count()
word_stats["to_review_count"] = unreviewed_count + due_count
```

- [ ] **Step 4: 提交**

```bash
git add backend/app/routers/question.py backend/app/schemas/question.py
git commit -m "feat(stats): add to_review_count to home stats"
```

---

### Task 6: 前端 - 首页卡片改造

**文件:**
- Modify: `frontend/src/views/Home.vue:81-92`

- [ ] **Step 1: 修改"复习次数"卡片**

将"复习次数"卡片改为"待复习"：

```vue
<el-col :span="6">
  <div class="stat-card stat-card-teal" @click="$router.push('/words')">
    <div class="stat-glow"></div>
    <div class="stat-icon-wrapper">
      <el-icon class="stat-icon"><Timer /></el-icon>
    </div>
    <div class="stat-info">
      <div class="stat-value">{{ stats.word_stats?.to_review_count || 0 }}</div>
      <div class="stat-label">待复习</div>
    </div>
  </div>
</el-col>
```

- [ ] **Step 2: 提交**

```bash
git add frontend/src/views/Home.vue
git commit -m "feat(home): replace review count with to-review card"
```

---

### Task 7: 前端 - 单词详情页记忆曲线 Tab

**文件:**
- Modify: `frontend/src/views/Words.vue` — 新增记忆曲线 Tab
- Create: `frontend/src/api/word.js` — 新增 memory-curve API（若不存在）

- [ ] **Step 1: 在 Words.vue 中添加 API 调用**

在 `<script setup>` 中新增：

```javascript
const memoryCurve = ref(null)
const memoryCurveLoading = ref(false)

const fetchMemoryCurve = async (wordId) => {
  memoryCurveLoading.value = true
  try {
    const { data } = await wordApi.getMemoryCurve(wordId)
    memoryCurve.value = data
  } finally {
    memoryCurveLoading.value = false
  }
}

// 阶段对应的颜色
const phaseColors = {
  '新学': '#909399',
  '在途': '#409eff',
  '遗忘点': '#e6a23c',
  '牢记': '#67c23a'
}

// 阶段对应的进度位置
const phasePosition = {
  '新学': 12.5,
  '在途': 37.5,
  '遗忘点': 62.5,
  '牢记': 87.5
}
```

- [ ] **Step 2: 在详情弹窗中添加 Tab**

找到编辑/查看弹窗，在现有 Tab 基础上新增"记忆曲线"：

```vue
<el-tabs v-if="dialogVisible" v-model="activeTab">
  <el-tab-pane label="基本信息" name="info">...</el-tab-pane>
  <el-tab-pane label="记忆曲线" name="curve">
    <div v-if="memoryCurve" class="memory-curve">
      <!-- 阶段进度条 -->
      <div class="phase-bar">
        <div class="phase-track">
          <div class="phase-dot" v-for="(phase, idx) in ['新学', '在途', '遗忘点', '牢记']"
               :key="phase"
               :class="{ active: memoryCurve.learning_phase === phase }"
               :style="{ left: phasePosition[phase] + '%' }">
            {{ phase }}
          </div>
        </div>
      </div>

      <!-- 下次复习时间 -->
      <div class="next-review">
        <span v-if="memoryCurve.learning_phase === '遗忘点'">即将到期</span>
        <span v-else-if="memoryCurve.next_review_at">下次复习：{{ formatDate(memoryCurve.next_review_at) }}</span>
        <span v-else>暂未安排复习</span>
      </div>

      <!-- 复习历史 -->
      <div class="review-history">
        <div class="history-title">复习历史：</div>
        <div v-if="memoryCurve.review_history.length === 0" class="history-empty">暂无复习记录</div>
        <div v-else class="history-item">
          <span class="history-date">今天（待复习）</span>
        </div>
        <div v-for="(log, idx) in memoryCurve.review_history" :key="idx" class="history-item">
          <span class="history-date">{{ formatDate(log.reviewed_at) }}</span>
          <span v-if="log.is_correct" class="history-correct">✓</span>
          <span v-else class="history-wrong">✗ 【{{ log.user_answer }}】</span>
        </div>
      </div>
    </div>
    <div v-else class="no-curve">加载中...</div>
  </el-tab-pane>
</el-tabs>
```

- [ ] **Step 3: 添加查看详情时获取记忆曲线**

在 `viewDetail` 函数中调用 `fetchMemoryCurve(row.id)`。

- [ ] **Step 4: 添加 CSS 样式**

在 `<style>` 中添加：

```css
.memory-curve {
  padding: 20px;
}
.phase-bar {
  margin-bottom: 20px;
}
.phase-track {
  position: relative;
  height: 40px;
  background: #f0f0f0;
  border-radius: 20px;
}
.phase-dot {
  position: absolute;
  top: 50%;
  transform: translate(-50%, -50%);
  padding: 4px 8px;
  background: #fff;
  border-radius: 4px;
  font-size: 12px;
  border: 2px solid #ddd;
}
.phase-dot.active {
  background: #409eff;
  color: #fff;
  border-color: #409eff;
}
.next-review {
  margin-bottom: 20px;
  font-size: 16px;
  color: #666;
}
.review-history {
  border-top: 1px solid #eee;
  padding-top: 15px;
}
.history-title {
  font-weight: bold;
  margin-bottom: 10px;
}
.history-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 0;
  font-size: 14px;
}
.history-date {
  min-width: 100px;
}
.history-correct {
  color: #67c23a;
}
.history-wrong {
  color: #f56c6c;
}
```

- [ ] **Step 5: 提交**

```bash
git add frontend/src/views/Words.vue
git commit -m "feat(words): add memory curve tab in word detail"
```

---

### Task 8: 历史数据初始化

**文件:**
- Create: `backend/app/services/init_word_learning_phase.py` — 初始化脚本

- [ ] **Step 1: 创建初始化脚本**

创建 `backend/app/services/init_word_learning_phase.py`：

```python
"""
初始化历史单词的 learning_phase
"""
from datetime import datetime, timedelta
from app.database import get_db
from app.models import Word, WordReviewLog


def init_learning_phase():
    """根据历史复习记录初始化 learning_phase"""
    db = next(get_db())

    words = db.query(Word).filter(Word.deleted == False).all()
    updated = 0

    for word in words:
        if word.review_count == 0:
            word.learning_phase = "新学"
        else:
            # 获取最近复习日志判断连续正确次数
            logs = db.query(WordReviewLog).filter(
                WordReviewLog.word_id == word.id,
                WordReviewLog.deleted == False
            ).order_by(WordReviewLog.reviewed_at.desc()).limit(10).all()

            consecutive_correct = 0
            for log in reversed(logs):
                if log.is_correct:
                    consecutive_correct += 1
                else:
                    break

            # 判断阶段
            if consecutive_correct >= 3 and (word.interval or 1) >= 7:
                word.learning_phase = "牢记"
            elif word.next_review_at and word.next_review_at <= datetime.now():
                word.learning_phase = "遗忘点"
            else:
                word.learning_phase = "在途"

            # 初始化 next_review_at（如果为空）
            if not word.next_review_at:
                word.next_review_at = datetime.now() + timedelta(days=word.interval or 1)

        updated += 1

    db.commit()
    print(f"已初始化 {updated} 个单词的 learning_phase")


if __name__ == "__main__":
    init_learning_phase()
```

- [ ] **Step 2: 执行初始化脚本**

```bash
cd backend && python -m app.services.init_word_learning_phase
```

- [ ] **Step 3: 提交**

```bash
git add backend/app/services/init_word_learning_phase.py
git commit -m "feat(word): add learning phase init script"
```

---

## Task 9: 更新 Changelog

**文件:**
- Modify: `CHANGELOG.md` — 添加版本记录

- [ ] **Step 1: 在 CHANGELOG.md 头部添加新版本**

```markdown
## [Unreleased] - 2026-04-04

### Added
- 艾宾浩斯记忆曲线复习功能
  - 新增 learning_phase 字段追踪学习阶段（新学/在途/遗忘点/牢记）
  - 新增 /api/words/{word_id}/memory-curve API
  - 复习抽取优先未复习 → 曲线到期 → 低正确率 → 随机
  - 首页新增待复习数量卡片
  - 单词详情页新增记忆曲线 Tab，展示阶段进度和复习历史

### Changed
- submit_review 更新 learning_phase 和 interval
- 首页"复习次数"卡片改为"待复习"
```

- [ ] **Step 2: 提交**

```bash
git add CHANGELOG.md
git commit -m "docs: update changelog for ebbinghaus feature"
```

---

## 实施顺序

1. Task 1: 数据库迁移
2. Task 2: 修改 submit_review
3. Task 3: 新增记忆曲线 API
4. Task 4: 修改复习抽取算法
5. Task 5: 修改首页统计 API
6. Task 6: 前端首页卡片
7. Task 7: 前端记忆曲线 Tab
8. Task 8: 历史数据初始化
9. Task 9: 更新 Changelog
