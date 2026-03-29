<template>
  <div id="app">
    <el-container>
      <el-header>
        <div class="header-content">
          <h1>EasyFix</h1>
          <el-menu mode="horizontal" :router="true" :default-active="$route.path">
            <el-menu-item index="/">首页</el-menu-item>
            <el-menu-item index="/questions">错题</el-menu-item>
            <el-menu-item index="/stats">统计</el-menu-item>
            <el-menu-item index="/practice-sets">练习</el-menu-item>
            <el-menu-item index="/words">单词</el-menu-item>
            <el-menu-item index="/settings">配置</el-menu-item>
            <el-menu-item index="/management">管理</el-menu-item>
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

/* H5移动端适配 */
@media screen and (max-width: 768px) {
  .el-header {
    height: auto !important;
    min-height: 50px;
    padding: 5px 0 !important;
    line-height: 1.5;
  }

  .header-content {
    flex-wrap: wrap;
    padding: 0 5px;
    gap: 5px;
  }

  .header-content h1 {
    font-size: 14px;
    margin-right: 10px;
    flex-shrink: 0;
  }

  .header-content .el-menu {
    flex-wrap: wrap;
    overflow-x: visible;
    width: 100%;
  }

  .header-content .el-menu-item {
    font-size: 11px;
    padding: 0 6px;
    height: 32px;
    line-height: 32px;
    flex-shrink: 0;
  }

  .el-main {
    padding: 10px;
  }
}

@media screen and (max-width: 480px) {
  .header-content h1 {
    font-size: 12px;
    margin-right: 5px;
  }

  .header-content .el-menu-item {
    font-size: 10px;
    padding: 0 4px;
    height: 28px;
    line-height: 28px;
  }
}

.el-header {
  background-color: #409eff;
  color: white;
  padding: 0;
  height: 60px !important;
  line-height: 60px;
}

.header-content {
  display: flex;
  align-items: center;
  height: 100%;
  padding: 0 20px;
  width: 100%;
  gap: 10px;
}

.header-content h1 {
  margin-right: 20px;
  font-size: 18px;
  white-space: nowrap;
  flex-shrink: 0;
}

.header-content .el-menu {
  background-color: transparent;
  border: none;
  flex: 1;
  display: flex;
  overflow-x: auto;
}

.header-content .el-menu::-webkit-scrollbar {
  display: none;
}

.header-content .el-menu-item {
  color: white !important;
  font-size: 14px;
  padding: 0 12px;
  height: 60px;
  line-height: 60px;
  min-width: auto;
  white-space: nowrap;
  flex-shrink: 0;
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

/* 全局H5适配 */
@media screen and (max-width: 768px) {
  .el-card {
    margin-bottom: 10px;
  }

  .el-card__header {
    padding: 12px 10px;
    font-size: 14px;
  }

  .el-card__body {
    padding: 10px;
  }

  .el-table {
    font-size: 12px;
  }

  .el-button {
    font-size: 12px;
    padding: 8px 10px;
  }

  .el-form-item {
    margin-bottom: 15px;
  }

  .el-form-item__label {
    font-size: 13px;
  }

  .el-pagination {
    font-size: 12px;
  }
}
</style>
