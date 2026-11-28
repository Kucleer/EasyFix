<template>
  <!-- 学生的两张大卡：背单词、翻一翻错题。翻一翻没上线时只有背单词一张，占满一行 -->
  <section class="kid" :class="{ single: !show_flip }" aria-label="学生的入口">
    <RouterLink class="kid-card words" to="/words">
      <span class="deco" aria-hidden="true"><span class="tile">a</span><span class="tile">b</span><span class="tile">c</span></span>
      <span class="eyebrow">今天</span>
      <span class="title">背单词</span>
      <span v-if="words.due > 0" class="count"><span class="num">{{ words.due }}</span>个要温习</span>
      <span v-else class="count">今天的都温习完了</span>
      <span class="start">开始<LineIcon name="arrow" :size="18" /></span>
    </RouterLink>

    <!-- 翻一翻：第 4 步上线后 flip 形如 { total: 今天这组几张, done: 已翻几张 } -->
    <RouterLink v-if="show_flip" class="kid-card flip" to="/flip">
      <span class="deco" aria-hidden="true">
        <span class="mini"></span><span class="mini"></span><span class="mini"><LineIcon name="check" :size="28" /></span>
      </span>
      <span class="eyebrow">今天</span>
      <span class="title">翻一翻错题</span>
      <span v-if="flip_left > 0" class="count"><span class="num">{{ flip_left }}</span>张</span>
      <span v-else class="count">{{ flip.total > 0 ? '今天翻完了' : '今天没有要翻的' }}</span>
      <span class="start">开始<LineIcon name="arrow" :size="18" /></span>
    </RouterLink>
  </section>
</template>

<script setup>
import { computed } from 'vue'
import LineIcon from '@/components/ui/LineIcon.vue'
import { FLIP_READY } from '@/config/features'

const props = defineProps({
  // /api/home 的 words：{ due: 今天到期要温习的单词数 }
  words: { type: Object, required: true },
  // /api/home 的 flip；第 4 步之前是 null
  flip: { type: Object, default: null },
})

// 开关打开、并且后端给了翻一翻的数据，才显示翻一翻卡
const show_flip = computed(() => FLIP_READY && !!props.flip)
// 今天这组还剩几张没翻
const flip_left = computed(() => Math.max(0, (props.flip?.total || 0) - (props.flip?.done || 0)))
</script>

<style scoped>
.kid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: var(--home-gap, 18px); }
.kid.single { grid-template-columns: 1fr; }
.num { font-family: var(--font-num); font-variant-numeric: tabular-nums; font-weight: 700; }

/* 大卡：整块可点，底边一道深色像按钮，按下去会往下沉 */
.kid-card {
  position: relative; overflow: hidden; min-height: var(--home-entry-height, 168px); padding: 22px 24px; border-radius: var(--r-lg);
  color: #fff; text-decoration: none; display: flex; flex-direction: column;
  box-shadow: inset 0 -5px 0 rgba(0,0,0,.14), inset 0 1px 0 rgba(255,255,255,.25), var(--shadow-2);
  transition: transform .16s ease-out, box-shadow .16s ease-out;
}
.kid-card:hover { transform: translateY(-2px); }
.kid-card:active { transform: translateY(2px); box-shadow: inset 0 -2px 0 rgba(0,0,0,.14), var(--shadow-1); }
.kid-card:focus-visible { outline: 3px solid #a5a0f5; outline-offset: 2px; }
.kid-card.words { background: linear-gradient(145deg, #6d65f5 0%, #4f46e5 55%, #3b33b8 100%); }
.kid-card.flip { background: linear-gradient(145deg, #2fb37f 0%, #17895a 55%, #0f6e47 100%); }
.eyebrow { font-size: 13px; opacity: .85; letter-spacing: 1px; }
.title { font-size: 26px; font-weight: 700; line-height: 1.3; margin-top: 2px; }
.count { margin-top: auto; display: flex; align-items: baseline; gap: 6px; padding-right: 110px; font-size: 15px; }
.count .num { font-size: 40px; line-height: 1; }
.start {
  position: absolute; right: 20px; bottom: 20px; display: flex; align-items: center; gap: 6px; padding: 9px 16px;
  border-radius: 999px; background: #fff; font-weight: 700; font-size: 15px; box-shadow: 0 4px 12px rgba(0,0,0,.15);
}
.words .start { color: var(--brand-deep); }
.flip .start { color: var(--mint-deep); }

/* 右上角的装饰：字母块 / 叠起来的卡片 */
.deco { position: absolute; right: 18px; top: 16px; width: 120px; height: 84px; pointer-events: none; }
.tile {
  position: absolute; width: 46px; height: 46px; border-radius: 12px; display: grid; place-items: center;
  font: 700 24px var(--font-num); background: rgba(255,255,255,.18);
  box-shadow: inset 0 -3px 0 rgba(0,0,0,.12), inset 0 1px 0 rgba(255,255,255,.3);
}
.tile:nth-child(1) { left: 0; top: 22px; transform: rotate(-10deg); }
.tile:nth-child(2) { left: 38px; top: 2px; transform: rotate(6deg); background: rgba(255,255,255,.28); }
.tile:nth-child(3) { left: 76px; top: 26px; transform: rotate(-4deg); }
.mini { position: absolute; width: 62px; height: 78px; border-radius: 12px; background: rgba(255,255,255,.2); box-shadow: inset 0 1px 0 rgba(255,255,255,.3); }
.mini:nth-child(1) { right: 44px; top: 6px; transform: rotate(-12deg); }
.mini:nth-child(2) { right: 22px; top: 2px; transform: rotate(-2deg); background: rgba(255,255,255,.28); }
.mini:nth-child(3) { right: 0; top: 6px; transform: rotate(9deg); background: rgba(255,255,255,.92); display: grid; place-items: center; color: var(--mint); }
.mini :deep(.line-icon) { stroke-width: 2.6; }

@media (min-width: 1200px) {
  .kid-card { padding: 26px 28px; }
  .title { font-size: 30px; }
  .count .num { font-size: 48px; }
  .deco { top: 22px; right: 26px; }
  .start { right: 26px; bottom: 24px; }
}

@media (max-width: 768px) {
  .kid { grid-template-columns: 1fr; gap: 12px; }
  .kid-card { min-height: 138px; padding: 18px 20px; }
  .title { font-size: 23px; }
  .count .num { font-size: 34px; }
  /* 手机上卡片矮一些，装饰缩小，免得压在"开始"按钮上 */
  .deco { transform: scale(.7); transform-origin: top right; }
}
@media (prefers-reduced-motion: reduce) {
  .kid-card { transition: none; }
}
</style>
