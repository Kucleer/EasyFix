<template>
  <!-- 知识星空卡：夜色背景，三个数（还薄弱 / 一般 / 已点亮），整块点进学情 -->
  <RouterLink class="sky" to="/insight">
    <b>知识星空</b>
    <p>每个考点是一颗星</p>
    <div class="sky-nums">
      <div><span class="num weak">{{ sky.weak }}</span><span class="label">还薄弱</span></div>
      <div><span class="num mid">{{ sky.middle }}</span><span class="label">一般</span></div>
      <div><span class="num good">{{ sky.lit }}</span><span class="label">已点亮</span></div>
    </div>
    <span class="link">看学情<LineIcon name="arrow" :size="16" /></span>
  </RouterLink>
</template>

<script setup>
import LineIcon from '@/components/ui/LineIcon.vue'

defineProps({
  // /api/home 的 sky：{ weak: 薄弱, middle: 一般 + 较好, lit: 掌握 }，所有学科相加
  sky: { type: Object, required: true },
})
</script>

<style scoped>
.sky {
  position: relative; overflow: hidden; min-width: 0; min-height: 220px; padding: 20px 22px; border-radius: var(--r-lg);
  display: flex; flex-direction: column; color: #fff; text-decoration: none;
  background: radial-gradient(120% 90% at 80% 0%, #2c2f63 0%, var(--night) 60%); box-shadow: var(--shadow-2);
}
.sky:focus-visible { outline: 3px solid #a5a0f5; outline-offset: 2px; }
/* 背景上的几颗小星星，纯 CSS 画的 */
.sky::before {
  content: ''; position: absolute; inset: 0; opacity: .9; background-image:
    radial-gradient(1.4px 1.4px at 12% 22%, #fff 50%, transparent 51%), radial-gradient(1.2px 1.2px at 28% 64%, #cfd3ff 50%, transparent 51%),
    radial-gradient(1.8px 1.8px at 46% 14%, #ffe9a8 50%, transparent 51%), radial-gradient(1.2px 1.2px at 63% 48%, #fff 50%, transparent 51%),
    radial-gradient(2.2px 2.2px at 82% 30%, #9ff0c8 50%, transparent 51%), radial-gradient(1.2px 1.2px at 90% 72%, #cfd3ff 50%, transparent 51%),
    radial-gradient(1.6px 1.6px at 37% 86%, #ffb3bd 50%, transparent 51%), radial-gradient(1.2px 1.2px at 72% 88%, #fff 50%, transparent 51%);
}
.sky > * { position: relative; }
b { font-size: 16px; }
p { margin: 2px 0 0; font-size: 13px; color: #b9bdd6; }
.sky-nums { display: flex; gap: 10px; margin-top: auto; padding-top: 16px; }
.sky-nums > div { flex: 1; padding: 10px 8px; border-radius: 14px; text-align: center; background: rgba(255,255,255,.08); }
.num { display: block; font-family: var(--font-num); font-variant-numeric: tabular-nums; font-weight: 700; font-size: 24px; line-height: 1.2; }
.label { font-size: 12px; color: #c9cce2; }
.weak { color: #ffb3bd; }
.mid { color: #ffe9a8; }
.good { color: #9ff0c8; }
.link { display: flex; align-items: center; gap: 4px; min-height: 44px; margin: 10px 0 -8px auto; padding: 0 4px; color: #d7d4ff; font-weight: 600; font-size: 14px; }

@media (min-width: 1200px) {
  .sky { padding: 22px 26px; }
  b { font-size: 18px; }
  .sky-nums > div { padding: 12px 8px; }
  .num { font-size: 28px; }
  .label { font-size: 14px; }
}

@media (max-width: 768px) {
  .sky { min-height: 0; padding: 16px; }
}
</style>
