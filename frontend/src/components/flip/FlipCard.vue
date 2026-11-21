<template>
  <!-- 一张错题卡：正面是标签、题目、你上次写的；点"想好了，看答案"后在同一张卡上展开答案和解析 -->
  <article class="qcard">
    <span class="qtag">{{ card.tag }}</span>

    <!-- 题目：有题干显示题干（公式用 MathText）；只有原图时直接显示原图 -->
    <div v-if="card.stem" class="qstem"><MathText :text="card.stem" /></div>
    <div v-if="card.image_only || show_images" class="qimages">
      <el-image
        v-for="(src, i) in card.images"
        :key="src"
        :src="src"
        :preview-src-list="card.images"
        :initial-index="i"
        preview-teleported
        fit="contain"
        class="qimage"
        :alt="'原题图片 ' + (i + 1)"
      />
    </div>
    <!-- 有题干也有原图时，原图收起来，想看再点 -->
    <button v-if="card.stem && card.images.length" type="button" class="see-image" @click="show_images = !show_images">
      {{ show_images ? '收起原图' : '看原图' }}
    </button>

    <!-- 你上次写的：没记录错误答案时整块不显示 -->
    <div v-if="card.wrong_answer" class="mine">
      <small>你上次写的</small>
      <b><MathText :text="card.wrong_answer" /></b>
    </div>

    <!-- 正确答案和解析：看答案之后才出现 -->
    <div v-if="revealed" class="right">
      <small>正确答案</small>
      <b><MathText :text="card.answer || '没有记录答案'" /></b>
      <p v-if="card.analysis"><MathText :text="card.analysis" /></p>
      <el-image
        v-if="card.analysis_image"
        :src="card.analysis_image"
        :preview-src-list="[card.analysis_image]"
        preview-teleported
        fit="contain"
        class="qimage"
        alt="解析图片"
      />
    </div>

    <div class="grow"></div>

    <!-- 按钮：先"想好了，看答案"，看过之后换成"我忘了 / 我记得"；提交中两个按钮都不能点 -->
    <div v-if="revealed" class="pair">
      <button type="button" class="btn no" :disabled="submitting" @click="emit('answer', 'forget')">
        <LineIcon name="again" />我忘了
      </button>
      <button type="button" class="btn yes" :disabled="submitting" @click="emit('answer', 'remember')">
        <LineIcon name="check" />我记得
      </button>
    </div>
    <button v-else type="button" class="btn primary" @click="emit('reveal')">想好了，看答案</button>
  </article>
</template>

<script setup>
import { ref } from 'vue'
import MathText from '@/components/MathText.vue'
import LineIcon from '@/components/ui/LineIcon.vue'

defineProps({
  // flipModel.card_view 的结果：tag、stem、images、image_only、wrong_answer、answer、analysis、analysis_image
  card: { type: Object, required: true },
  // 是否已经点了"想好了，看答案"
  revealed: { type: Boolean, default: false },
  // 正在提交"我记得 / 我忘了"，按钮先禁用，防止连点翻过两张
  submitting: { type: Boolean, default: false },
})
const emit = defineEmits(['reveal', 'answer'])

// 有题干时原图默认收起；换卡片时父组件用 :key 重新创建本组件，这里自然回到收起
const show_images = ref(false)
</script>

<style scoped>
/* 卡片样子照样稿：白底大圆角，进来时从右边滑入 */
.qcard {
  position: relative; z-index: 1; min-height: 372px; display: flex; flex-direction: column; padding: 22px;
  border-radius: var(--r-lg); background: var(--surface); box-shadow: var(--shadow-2); color: var(--ink);
  animation: card-in .28s ease-out;
}
@keyframes card-in { from { opacity: 0; transform: translateX(26px) rotate(1.5deg); } to { opacity: 1; transform: none; } }
.qtag {
  align-self: flex-start; padding: 3px 11px; border-radius: 999px; background: var(--brand-soft); color: var(--brand-deep);
  font-size: 13px; font-weight: 600;
}
.qstem { margin: 14px 0 16px; font-size: 19px; line-height: 1.65; overflow-wrap: anywhere; }
.qimages { display: grid; gap: 8px; margin: 14px 0 12px; }
.qimage { width: 100%; max-height: 320px; border-radius: 12px; background: var(--bg); }
.see-image {
  align-self: flex-start; margin: -6px 0 12px; padding: 6px 2px; border: 0; background: none; cursor: pointer;
  color: var(--brand); font: inherit; font-size: 14px; font-weight: 600;
}
.see-image:focus-visible { outline: 3px solid #a5a0f5; outline-offset: 2px; border-radius: 6px; }

.mine, .right { padding: 11px 14px; border-radius: 14px; }
.mine { background: var(--coral-soft); color: #a8303f; }
.mine small, .right small { display: block; font-size: 12.5px; opacity: .85; }
.mine b, .right b { font-size: 17px; }
.right { margin-top: 10px; background: var(--mint-soft); color: var(--mint-deep); animation: reveal .26s ease-out; }
.right p { margin: 6px 0 0; color: var(--ink-2); font-size: 14.5px; }
.right .qimage { margin-top: 8px; }
@keyframes reveal { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: none; } }
.grow { flex: 1; min-height: 16px; }

/* 大按钮：底边一道深色，按下去往下沉 */
.btn {
  width: 100%; min-height: 54px; display: flex; align-items: center; justify-content: center; gap: 8px;
  border: 0; border-radius: 16px; font: inherit; font-size: 17px; font-weight: 700; cursor: pointer;
  transition: transform .14s ease-out, box-shadow .14s ease-out, opacity .14s;
}
.btn:active:not(:disabled) { transform: translateY(2px); }
.btn:focus-visible { outline: 3px solid #a5a0f5; outline-offset: 2px; }
.btn:disabled { opacity: .55; cursor: wait; }
.btn.primary { background: var(--brand); color: #fff; box-shadow: inset 0 -4px 0 var(--brand-deep), 0 6px 14px rgba(79,70,229,.3); }
.btn.yes { background: var(--mint); color: #fff; box-shadow: inset 0 -4px 0 var(--mint-deep), 0 6px 14px rgba(23,137,90,.28); }
.btn.no { background: #fff; color: var(--sun); box-shadow: inset 0 0 0 2px #edcf9f, inset 0 -4px 0 #f3e2c4; }
.pair { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }

@media (prefers-reduced-motion: reduce) {
  .qcard, .right { animation: none; }
  .btn { transition: none; }
}
</style>
