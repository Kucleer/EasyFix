<template><header class="page-heading"><div><p class="page-eyebrow">{{ eyebrow }}</p><h1>{{ title }}</h1><p class="page-description">{{ description }}</p></div><slot /></header></template>
<script setup>
defineProps({ title: String, description: String, eyebrow: { type: String, default: 'EASYFIX · LEARNING SPACE' } })
</script>
<style scoped>.page-heading {
  display:flex;
  justify-content:space-between;
  align-items:center;
  gap:15px;
  margin-bottom:18px}
.page-eyebrow {
  font-size:10px;
  letter-spacing:1.6px;
  color:var(--accent-blue);
  font-weight:700;
  margin:0 0 4px}
.page-heading h1 {
  font-size:26px;
  line-height:1.4;
  letter-spacing:-.7px;
  margin:0 0 4px}
.page-description {
  font-size:13px;
  color:var(--text-muted);
  margin:0}
@media(max-width:768px) {
  .page-heading h1 {
  font-size:23px}
.page-heading {
  margin-bottom:15px}
}</style>