<template>
  <div class="upload">
    <PageHeading title="录入错题" description="记录题目、解题过程，并保留原图方便回顾。" />
    <ManualQuestionForm />
  </div>
</template>

<script setup>
import PageHeading from '@/components/PageHeading.vue'
import ManualQuestionForm from '@/components/ManualQuestionForm.vue'
</script>

<style scoped>
.upload {
  max-width: 1100px;
  margin: 0 auto;
}

/* 禁用上传页面卡片的hover效果 */
.upload :deep(.el-card) {
  transition: none;
}

.upload :deep(.el-card:hover) {
  transform: none;
  box-shadow: var(--shadow-sm) !important;
}
</style>
