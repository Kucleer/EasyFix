<template>
  <!-- 首页：每日一句 → 学生入口 → 家长待办 → 这一周。数据只来自 /api/home 一个请求 -->
  <div class="home-page">
    <DailyLine :today="today" :streak-days="home?.streak_days || 0" />

    <!-- 读取失败：说一句，给一个"再试一次" -->
    <div v-if="failed && !home" class="home-error" role="alert">
      <span>首页数据没有读到，可能是网络不好。</span>
      <el-button type="primary" round :loading="loading" @click="load_home">再试一次</el-button>
    </div>

    <!-- 读取中：灰色占位块，和真正的版式一样大，读完不跳动 -->
    <div v-else-if="!home" class="home-skeleton" aria-busy="true" aria-label="正在读取">
      <div class="bone kid-bone"></div>
      <div class="zone">家长待办</div>
      <div class="bone-row"><div class="bone todo-bone"></div><div class="bone todo-bone"></div><div class="bone todo-bone"></div></div>
      <div class="zone">这一周</div>
      <div class="week"><div class="bone week-bone"></div><div class="bone week-bone"></div></div>
    </div>

    <template v-else>
      <StudentEntries :words="home.words" :flip="home.flip" />

      <div class="zone">家长待办</div>
      <ParentTodos :review="home.review" :grading="home.grading" :targeted="home.targeted" :today="today" />

      <div class="zone">这一周</div>
      <section class="week">
        <WeekSummary :week="home.week" :today="today" />
        <SkyCard :sky="home.sky" />
      </section>
    </template>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import DailyLine from '@/components/home/DailyLine.vue'
import StudentEntries from '@/components/home/StudentEntries.vue'
import ParentTodos from '@/components/home/ParentTodos.vue'
import WeekSummary from '@/components/home/WeekSummary.vue'
import SkyCard from '@/components/home/SkyCard.vue'
import { homeApi } from '@/api/home'
import { beijingDate } from '@/data/dailyLines'
import { useReviewCountStore } from '@/stores/reviewCount'

const reviewCountStore = useReviewCountStore()

// 今天（北京时间），每日一句、几天前、打卡条都按它算
const today = beijingDate(new Date())
// /api/home 的返回；没读到之前是 null
const home = ref(null)
const loading = ref(false)
const failed = ref(false)

/**
 * 读取首页数据；成功后把待核对数写回 store，让菜单上的红点和首页一致
 */
async function load_home() {
  loading.value = true
  failed.value = false
  try {
    const { data } = await homeApi.get()
    home.value = data
    reviewCountStore.pending = Number(data?.review?.count) || 0
  } catch (error) {
    console.error('读取首页数据失败:', error)
    failed.value = true
  } finally {
    loading.value = false
  }
}

onMounted(load_home)
</script>

<style scoped>
.home-page { max-width: 1100px; }

/* 分区小标题：文字后面拖一条细线 */
.zone { display: flex; align-items: center; gap: 12px; margin: 30px 0 12px; font-size: 13px; color: var(--muted); letter-spacing: 1.5px; }
.zone::after { content: ''; flex: 1; height: 1px; background: var(--line); }

/* 这一周：左边周概况，右边星空卡 */
.week { display: grid; grid-template-columns: 1.7fr 1fr; gap: 16px; }

.home-error {
  display: flex; flex-wrap: wrap; align-items: center; gap: 12px 16px; padding: 20px 22px;
  border-radius: var(--r-lg); background: var(--surface); box-shadow: var(--shadow-1); color: var(--ink-2);
}

/* 占位块：浅灰底，轻轻地一明一暗 */
.bone { border-radius: var(--r-lg); background: #e9e8f4; animation: breathe 1.4s ease-in-out infinite; }
.kid-bone { height: 168px; }
.bone-row { display: grid; grid-template-columns: repeat(3, 1fr); gap: 14px; }
.todo-bone { height: 76px; border-radius: var(--r-md); }
.week-bone { height: 260px; }
@keyframes breathe { 50% { opacity: .55; } }

@media (max-width: 768px) {
  .zone { margin: 22px 0 10px; }
  .week { grid-template-columns: 1fr; gap: 12px; }
  .kid-bone { height: 138px; }
  .bone-row { grid-template-columns: 1fr; gap: 10px; }
  .week-bone { height: 220px; }
}
@media (prefers-reduced-motion: reduce) {
  .bone { animation: none; }
}
</style>
