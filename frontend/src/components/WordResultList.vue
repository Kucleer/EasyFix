<template>
  <!-- 单词练习结果：错题优先，一行一词，写对的折成紧凑标签 -->
  <div class="word-result-list">
    <!-- 顶部摘要由父组件通过 header 插槽提供（正确率、按钮、比例条等） -->
    <slot name="header" />

    <!-- 写错的词 -->
    <section v-if="wrongItems.length" class="result-section">
      <div class="section-title">
        <span class="section-name">写错的 {{ wrongItems.length }} 个</span>
        <span class="section-note">红色是写错或漏掉的部分</span>
      </div>
      <div class="wrong-list">
        <div v-for="(item, index) in wrongItems" :key="'w' + index" class="wrong-row">
          <!-- 正确答案：写错或漏掉的部分标红 -->
          <div class="col col-answer">
            <span
              v-for="(seg, si) in item.expectedSegs"
              :key="si"
              :class="{ wrong: seg.wrong }"
            >{{ seg.text }}</span>
          </div>
          <!-- 中文释义 -->
          <div class="col col-cn">{{ item.chinese }}</div>
          <!-- 孩子写的内容：多写或写错的部分标红；为空时显示没有作答 -->
          <div class="col col-user">
            <template v-if="item.userAnswer">
              <span
                v-for="(seg, si) in item.actualSegs"
                :key="si"
                :class="{ wrong: seg.wrong }"
              >{{ seg.text }}</span>
            </template>
            <span v-else class="empty-answer">没有作答</span>
          </div>
          <!-- 累计错误次数：错 2 次及以上用警示色，错 1 次用弱化色 -->
          <div
            v-if="item.errorCount != null"
            class="col col-count"
            :class="{ repeat: item.errorCount >= 2 }"
          >第 {{ item.errorCount }} 次错</div>
        </div>
      </div>
    </section>

    <!-- 写对的词：只展示英文，紧凑标签换行排列 -->
    <section v-if="correctItems.length" class="result-section">
      <div class="section-title">
        <span class="section-name">写对的 {{ correctItems.length }} 个</span>
      </div>
      <div class="correct-chips">
        <span v-for="(item, index) in correctItems" :key="'c' + index" class="chip">
          {{ item.english }}
        </span>
      </div>
    </section>

    <!-- 没有任何记录时的占位 -->
    <div v-if="!wrongItems.length && !correctItems.length" class="empty-tip">
      暂无练习记录
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { answerSegments } from '@/composables/dictation'

const props = defineProps({
  // 练习结果列表，每项含 english、chinese、userAnswer、isCorrect 等
  items: { type: Array, default: () => [] },
})

/**
 * 把一条原始记录归一化，并预先算好高亮片段，兼容后端(snake_case)与前端(camelCase)字段。
 * @param {object} raw 原始记录
 * @returns {object}
 */
function normalize(raw) {
  const english = raw.english ?? raw.question_text ?? ''
  const chinese = raw.chinese ?? raw.answer ?? ''
  const userAnswer = raw.userAnswer ?? raw.user_answer ?? ''
  const isCorrect = raw.isCorrect ?? raw.is_correct ?? raw.correct
  const tokenResults = raw.tokenResults ?? raw.token_results
  const errorCount = raw.errorCount ?? raw.error_count
  const segs = answerSegments({ english, userAnswer, tokenResults })
  return {
    english,
    chinese,
    userAnswer,
    isCorrect: !!isCorrect,
    errorCount: errorCount == null ? null : errorCount,
    expectedSegs: segs.expected,
    actualSegs: segs.actual,
  }
}

// 归一化后的全部条目
const normalized = computed(() => props.items.map(normalize))
// 写错的条目（错题优先展示）
const wrongItems = computed(() => normalized.value.filter(item => !item.isCorrect))
// 写对的条目
const correctItems = computed(() => normalized.value.filter(item => item.isCorrect))
</script>

<style scoped>
.word-result-list {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.result-section {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.section-title {
  display: flex;
  align-items: baseline;
  gap: 10px;
  flex-wrap: wrap;
}

.section-name {
  font-weight: var(--font-weight-semibold);
  color: var(--text-primary);
  font-size: var(--font-h3);
}

.section-note {
  font-size: var(--font-small);
  color: var(--text-muted);
}

/* 错题列表：发丝分隔线，不用卡片 */
.wrong-list {
  display: flex;
  flex-direction: column;
}

.wrong-row {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 4px 16px;
  padding: 9px 2px;
  border-bottom: 1px solid var(--border-light);
}

.wrong-row:last-child {
  border-bottom: none;
}

.col {
  min-width: 0;
  word-break: break-word;
  overflow-wrap: anywhere;
}

.col-answer {
  flex: 1 1 38%;
  font-weight: var(--font-weight-semibold);
  color: var(--text-primary);
  font-size: var(--font-h3);
  letter-spacing: 0.3px;
}

.col-cn {
  flex: 1 1 20%;
  color: var(--text-secondary);
}

.col-user {
  flex: 2 1 28%;
  color: var(--text-secondary);
}

.col-count {
  flex: 0 0 auto;
  margin-left: auto;
  font-size: var(--font-small);
  color: var(--text-muted);
  white-space: nowrap;
}

.col-count.repeat {
  color: var(--danger);
  font-weight: var(--font-weight-semibold);
}

/* 写错或漏掉的字符：统一用警示色标红 */
.wrong {
  color: var(--danger);
  font-weight: var(--font-weight-bold);
}

.empty-answer {
  color: var(--text-muted);
  font-style: italic;
}

/* 写对的词：紧凑标签换行 */
.correct-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.chip {
  padding: 3px 10px;
  border-radius: var(--radius-full);
  background: var(--bg-secondary);
  border: 1px solid var(--border-light);
  color: var(--text-secondary);
  font-size: var(--font-body);
}

.empty-tip {
  color: var(--text-muted);
  text-align: center;
  padding: 24px 0;
}

/* 窄屏：每行折成两行，第一行答案+次数，第二行中文+所写，不出现横向滚动 */
@media (max-width: 768px) {
  .wrong-row {
    gap: 4px 12px;
  }
  .col-answer {
    flex: 1 1 auto;
    order: 1;
  }
  .col-count {
    order: 2;
  }
  .col-cn {
    flex: 1 1 38%;
    order: 3;
  }
  .col-user {
    flex: 1 1 50%;
    order: 4;
  }
}
</style>
