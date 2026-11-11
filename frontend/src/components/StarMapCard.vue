<template>
  <section class="starmap-card" @click="router.push('/star-map')">
    <div class="head"><h2>我的知识星空</h2><span>点开看看 →</span></div>
    <div class="sky">
      <StarCanvas v-if="data" :data="data" mini />
      <div v-if="data" class="count"><b>{{ total }}</b> 颗星已掌握</div>
      <div v-else-if="failed" class="failed">星空暂时打不开</div>
    </div>
  </section>
</template>

<script setup>
// 首页的知识星空缩略图：会动的数学星空，左下角是两科已掌握的考点数，点击进入星空页
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import StarCanvas from '@/components/starmap/StarCanvas.vue'
import { starmapApi, loadStarmapSubjects } from '@/api/starmap'

const router = useRouter()
const data = ref(null)
const total = ref(0)
const failed = ref(false)

onMounted(async () => {
  try {
    const subjects = await loadStarmapSubjects()
    const results = await Promise.all(subjects.map(s => starmapApi.get(s.id)))
    total.value = results.reduce((sum, r) => sum + (r.data.mastered_count || 0), 0)
    data.value = results[0]?.data || null
    failed.value = !data.value
  } catch {
    failed.value = true   // 加载失败只显示一行灰字，不影响首页其他部分
  }
})
</script>

<style scoped>
.starmap-card {
  margin-bottom: 18px;
  padding: 16px 18px;
  background: #fff;
  border: 1px solid var(--border-light);
  border-radius: 12px;
  cursor: pointer;
}
.head { display: flex; align-items: baseline; justify-content: space-between; margin-bottom: 10px; }
.head h2 { margin: 0; font-size: 16px; }
.head span { font-size: 13px; color: var(--text-muted); }
.sky { position: relative; height: 260px; border-radius: 10px; overflow: hidden; background: #030306; }
.count {
  position: absolute;
  left: 16px;
  bottom: 12px;
  color: #e6e9f2;
  font-size: 13px;
  letter-spacing: 1px;
  text-shadow: 0 0 8px rgba(0, 0, 0, 0.8);
  pointer-events: none;
}
.count b { font-size: 24px; margin-right: 4px; color: rgb(88, 214, 141); }
.failed { position: absolute; inset: 0; display: grid; place-items: center; color: #8d93a5; font-size: 13px; }
</style>
