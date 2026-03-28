<template>
  <div id="app">
    <el-container>
      <el-header>
        <div class="header-content">
          <h1>EasyFix 错题整理</h1>
          <el-menu mode="horizontal" :router="true" :default-active="$route.path">
            <el-menu-item index="/">首页</el-menu-item>
            <el-menu-item index="/questions">错题列表</el-menu-item>
            <el-menu-item index="/upload">上传错题</el-menu-item>
            <el-menu-item index="/stats">统计分析</el-menu-item>
            <el-menu-item index="/settings">配置</el-menu-item>
            <el-menu-item index="/management">管理中心</el-menu-item>
            <el-menu-item index="/practice-sets">练习集</el-menu-item>
          </el-menu>
        </div>
      </el-header>
      <el-main>
        <router-view />
      </el-main>
    </el-container>
  </div>
</template>

<script setup>
// App root component
</script>

<style>
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

#app {
  min-height: 100vh;
}

.el-header {
  background-color: #409eff;
  color: white;
  padding: 0;
}

.header-content {
  display: flex;
  align-items: center;
  height: 100%;
  padding: 0 20px;
}

.header-content h1 {
  margin-right: 40px;
  font-size: 20px;
}

.header-content .el-menu {
  background-color: transparent;
  border: none;
}

.header-content .el-menu-item {
  color: white !important;
}

.header-content .el-menu-item:hover,
.header-content .el-menu-item.is-active {
  background-color: rgba(255, 255, 255, 0.2) !important;
}

.el-main {
  padding: 20px;
  background-color: #f5f5f5;
  min-height: calc(100vh - 60px);
}
</style>
