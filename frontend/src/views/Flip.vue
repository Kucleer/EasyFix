<template>
  <!-- 翻一翻：每天一组旧错题卡片，看题 → 想 → 看答案 → 点"我记得 / 我忘了"。手机优先，电脑上居中一张卡 -->
  <div class="flip-page">
    <!-- 读取中；手里的卡片翻完、服务器说还有没翻的时候也先显示这个，再重新取 -->
    <div v-if="(loading && !today) || state === 'reload'" class="flip-loading" aria-busy="true" aria-label="正在读取">
      <div class="bone top-bone"></div>
      <div class="bone card-bone"></div>
    </div>

    <!-- 读取失败：说一句，给一个"再试一次" -->
    <div v-else-if="!today" class="flip-error" role="alert">
      <span>今天的卡片没有读到，可能是网络不好。</span>
      <button type="button" class="btn primary small" @click="load_today">再试一次</button>
    </div>

    <!-- 今天没有要翻的 -->
    <div v-else-if="state === 'empty'" class="finish">
      <div class="medal calm"><LineIcon name="flip" :size="52" /></div>
      <h1>今天没有要翻的</h1>
      <p>错题都还没到再看的时候，过几天再来。</p>
      <RouterLink class="btn primary small" to="/">回首页</RouterLink>
    </div>

    <!-- 今天翻完了：不能继续刷 -->
    <div v-else-if="state === 'finished'" class="finish">
      <div class="medal"><LineIcon name="check" :size="52" /></div>
      <h1>今天翻完了</h1>
      <p>{{ finish_line }}</p>
      <RouterLink class="btn primary small" to="/">回首页</RouterLink>
    </div>

    <!-- 正在翻 -->
    <template v-else>
      <div class="flip-top">
        <b>翻一翻</b>
        <div class="seg" aria-hidden="true"><i v-for="(dot, i) in dots" :key="i" :class="dot"></i></div>
        <span class="progress num">{{ progress }}</span>
      </div>
      <div class="deck">
        <FlipCard
          :key="card.id"
          :card="card"
          :revealed="revealed"
          :submitting="submitting"
          @reveal="revealed = true"
          @answer="answer"
        />
      </div>
      <p class="flip-hint">不用打字，也不打分。点“我忘了”的题，过两天会再出现。</p>
    </template>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import FlipCard from '@/components/flip/FlipCard.vue'
import LineIcon from '@/components/ui/LineIcon.vue'
import { flipApi } from '@/api/flip'
import { after_record, card_view, finish_text, page_state, progress_dots, progress_text } from '@/components/flip/flipModel'

const today = ref(null)        // /api/flip/today 的返回：{ total, done, cards }；没读到之前是 null
const index = ref(0)           // 这次打开后翻到 cards 里的第几张
const revealed = ref(false)    // 当前卡片是否已经看了答案
const submitting = ref(false)  // 正在提交"我记得 / 我忘了"
const loading = ref(true)     // 一打开就在读取，避免先闪一下"没有读到"

// 页面状态：empty 没有要翻的、finished 翻完了、card 正在翻、reload 要重新取卡片
const state = computed(() => (today.value ? page_state(today.value, index.value) : ''))
// 当前这张卡要显示的内容
const card = computed(() => card_view(today.value.cards[index.value]))
// 顶部进度：文字和进度条都按服务器给的已翻张数算，刷新页面后也接得上
const progress = computed(() => progress_text(today.value.done, today.value.total))
const dots = computed(() => progress_dots(today.value.done, today.value.total))
const finish_line = computed(() => finish_text(today.value.total))

/** 读取今天这一组还没翻的卡片；同一天再打开时服务器按原来的顺序给剩下的 */
async function load_today() {
  loading.value = true
  try {
    const { data } = await flipApi.today()
    today.value = data
    index.value = 0
    revealed.value = false
  } catch (error) {
    console.error('读取翻一翻卡片失败:', error)
    today.value = null
  } finally {
    loading.value = false
  }
}

/**
 * 记下这张卡的结果并换下一张。
 * 提交中直接忽略再点（按钮也禁用），防止网络慢时连点翻过两张；失败时提示并停在这张卡上。
 */
async function answer(result) {
  if (submitting.value) return
  submitting.value = true
  const question_id = card.value.id
  try {
    const { data } = await flipApi.record(question_id, result)
    // 用服务器算的进度（和首页、周报一致），换下一张
    const next = after_record(today.value, index.value, data)
    today.value = next.today
    index.value = next.index
    revealed.value = false
    // 手里的卡片翻完了、今天这组却变多了（翻的过程中录了新题）：重新取剩下的卡片，不显示"翻完了"
    if (page_state(today.value, index.value) === 'reload') await load_today()
  } catch (error) {
    if (error.response?.status === 404) {
      // 这道题已经不在今天这组里（比如刚被删掉或毕业了）：重新取一次剩下的卡片
      ElMessage.warning('这张卡已经不用翻了，换下一张')
      await load_today()
    } else {
      ElMessage.error('没有记上，请再点一次')
    }
  } finally {
    submitting.value = false
  }
}

onMounted(load_today)
</script>

<style scoped>
.flip-page { max-width: 480px; margin: 0 auto; color: var(--ink); }
.num { font-family: var(--font-num); font-variant-numeric: tabular-nums; font-weight: 700; }

/* 顶部：标题 + 分段进度条 + 第几张 / 共几张 */
.flip-top { display: flex; align-items: center; gap: 12px; margin-bottom: 18px; }
.flip-top b { font-size: 17px; white-space: nowrap; }
.seg { flex: 1; display: flex; gap: 5px; min-width: 0; }
.seg i { flex: 1; height: 8px; border-radius: 4px; background: #dddbee; transition: background .25s; }
.seg i.done { background: var(--mint); }
.seg i.now { background: #9be0c0; }
.progress { color: var(--muted); font-size: 14px; white-space: nowrap; }

/* 卡片后面垫两层，像一叠卡 */
.deck { position: relative; padding-bottom: 14px; }
.deck::before, .deck::after {
  content: ''; position: absolute; left: 12px; right: 12px; bottom: 6px; height: 40px;
  border-radius: var(--r-lg); background: #fff; box-shadow: var(--shadow-1); opacity: .7;
}
.deck::after { left: 24px; right: 24px; bottom: 0; opacity: .45; }
.flip-hint { margin-top: 16px; text-align: center; font-size: 13px; color: var(--muted); }

/* 翻完了 / 没有要翻的 */
.finish { text-align: center; padding: 56px 12px 20px; }
.medal {
  width: 108px; height: 108px; margin: 0 auto 18px; border-radius: 50%; display: grid; place-items: center; color: #fff;
  background: linear-gradient(145deg, #2fb37f, #0f6e47);
  box-shadow: inset 0 -6px 0 rgba(0,0,0,.16), 0 0 0 10px var(--mint-soft), var(--shadow-2);
  animation: pop .4s cubic-bezier(.2,1.4,.4,1);
}
.medal :deep(.line-icon) { stroke-width: 3; }
.medal.calm { background: linear-gradient(145deg, #6d65f5, #3b33b8); box-shadow: inset 0 -6px 0 rgba(0,0,0,.16), 0 0 0 10px var(--brand-soft), var(--shadow-2); }
.medal.calm :deep(.line-icon) { stroke-width: 2.2; }
@keyframes pop { from { transform: scale(.6); opacity: 0; } to { transform: none; opacity: 1; } }
.finish h1 { margin: 0 0 6px; font-size: 26px; }
.finish p { margin: 0 0 24px; color: var(--muted); }

.btn {
  display: flex; align-items: center; justify-content: center; gap: 8px; min-height: 54px; border: 0; border-radius: 16px;
  font: inherit; font-size: 17px; font-weight: 700; text-decoration: none; cursor: pointer;
}
.btn.primary { background: var(--brand); color: #fff; box-shadow: inset 0 -4px 0 var(--brand-deep), 0 6px 14px rgba(79,70,229,.3); }
.btn.small { width: 100%; max-width: 220px; margin: 0 auto; }
.btn:active { transform: translateY(2px); }
.btn:focus-visible { outline: 3px solid #a5a0f5; outline-offset: 2px; }

.flip-error {
  display: flex; flex-direction: column; align-items: center; gap: 16px; padding: 28px 22px; text-align: center;
  border-radius: var(--r-lg); background: var(--surface); box-shadow: var(--shadow-1); color: var(--ink-2);
}

/* 读取中的占位块 */
.bone { border-radius: var(--r-lg); background: #e9e8f4; animation: breathe 1.4s ease-in-out infinite; }
.top-bone { height: 26px; margin-bottom: 18px; border-radius: 10px; }
.card-bone { height: 372px; }
@keyframes breathe { 50% { opacity: .55; } }

@media (prefers-reduced-motion: reduce) {
  .medal, .bone { animation: none; }
  .seg i { transition: none; }
}
</style>
