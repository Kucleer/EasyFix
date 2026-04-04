# 全局 UI 风格升级实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 统一全局字体大小，优化配色系统，升级为简洁现代的视觉效果

**Architecture:** 创建全局CSS变量文件，覆盖Element Plus主题变量，统一字体层级，更新组件样式

**Tech Stack:** Vue 3 + Element Plus + CSS Variables

---

## 文件修改

- Create: `frontend/src/styles/variables.css` (全局CSS变量)
- Modify: `frontend/src/main.js` (引入全局样式)
- Modify: `frontend/src/App.vue` (添加全局字体样式)

---

## 实施步骤

### Task 1: 创建全局 CSS 变量文件

**Files:**
- Create: `frontend/src/styles/variables.css`

- [ ] **Step 1: 创建 styles 目录和变量文件**

```css
/* frontend/src/styles/variables.css */

/* ==================== 字体层级 ==================== */
:root {
  /* 字号 */
  --font-h1: 20px;
  --font-h2: 18px;
  --font-h3: 16px;
  --font-body: 14px;
  --font-small: 12px;

  /* 字重 */
  --font-weight-bold: bold;
  --font-weight-semibold: 600;
  --font-weight-normal: normal;

  /* ==================== 背景色 ==================== */
  --bg-primary: #ffffff;
  --bg-secondary: #f5f5f5;
  --bg-tertiary: #fafafa;
  --bg-dark: #1a1a1a;

  /* ==================== 文字色 ==================== */
  --text-primary: #303133;
  --text-secondary: #606266;
  --text-muted: #909399;
  --text-white: #ffffff;

  /* ==================== 强调色 ==================== */
  --accent-blue: #409eff;
  --accent-purple: #8250df;
  --accent-pink: #ec7cf3;
  --accent-gradient: linear-gradient(135deg, #667eea 0%, #764ba2 100%);

  /* ==================== 功能色 ==================== */
  --success: #67c23a;
  --warning: #e6a23c;
  --danger: #f56c6c;
  --info: #909399;

  /* ==================== 边框色 ==================== */
  --border-light: #f0f0f0;
  --border-default: #dcdfe6;
  --border-dark: #303133;

  /* ==================== 圆角系统 ==================== */
  --radius-sm: 6px;
  --radius-md: 10px;
  --radius-lg: 16px;
  --radius-full: 9999px;

  /* ==================== 阴影系统 ==================== */
  --shadow-sm: 0 1px 4px rgba(0, 0, 0, 0.06);
  --shadow-md: 0 2px 12px rgba(0, 0, 0, 0.08);
  --shadow-lg: 0 8px 24px rgba(0, 0, 0, 0.12);
}

/* ==================== Element Plus 主题覆盖 ==================== */
.el-button {
  border-radius: var(--radius-md) !important;
}

.el-button:hover {
  transform: translateY(-2px);
  box-shadow: var(--shadow-md);
}

.el-card {
  border-radius: var(--radius-md) !important;
  box-shadow: var(--shadow-md) !important;
  border: 1px solid var(--border-light);
}

.el-input__wrapper {
  border-radius: var(--radius-sm) !important;
}

.el-table {
  border-radius: var(--radius-md) !important;
  overflow: hidden;
}

.el-table th {
  background-color: var(--bg-tertiary) !important;
  font-weight: var(--font-weight-semibold) !important;
}

.el-table tr:hover > td {
  background-color: #f5f7fa !important;
}

.el-dialog {
  border-radius: var(--radius-lg) !important;
}

.el-tag {
  border-radius: var(--radius-sm) !important;
}
```

### Task 2: 在 main.js 中引入全局样式

**Files:**
- Modify: `frontend/src/main.js:1-10`

- [ ] **Step 1: 添加全局样式引入**

在 `import App from './App.vue'` 后添加：
```javascript
import './styles/variables.css'
```

### Task 3: 在 App.vue 添加全局字体样式

**Files:**
- Modify: `frontend/src/App.vue`

- [ ] **Step 1: 在 App.vue 的 `<style>` 或 `<style scoped>` 后添加全局样式**

在 App.vue 底部添加（非scoped的style）：
```html
<style>
/* 全局字体层级 */
h1, .h1 {
  font-size: var(--font-h1);
  font-weight: var(--font-weight-bold);
  color: var(--text-primary);
  margin: 0 0 16px 0;
}

h2, .h2 {
  font-size: var(--font-h2);
  font-weight: var(--font-weight-bold);
  color: var(--text-primary);
  margin: 0 0 12px 0;
}

h3, .h3 {
  font-size: var(--font-h3);
  font-weight: var(--font-weight-semibold);
  color: var(--text-primary);
  margin: 0 0 8px 0;
}

body, p {
  font-size: var(--font-body);
  color: var(--text-secondary);
  line-height: 1.6;
}

.text-secondary, .text-muted {
  font-size: var(--font-small);
  color: var(--text-muted);
}

/* 全局字体平滑 */
body {
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}

/* 统一卡片hover效果 */
.el-card:hover {
  transform: translateY(-4px);
  box-shadow: var(--shadow-lg) !important;
  transition: all 0.3s ease;
}

/* 统一按钮hover效果 */
.el-button:not(.is-text):not(.is-link):hover {
  transform: translateY(-2px);
  box-shadow: var(--shadow-md);
}

/* 统一输入框focus */
.el-input__wrapper:focus-within {
  box-shadow: 0 0 0 1px var(--accent-blue) inset;
}

/* 渐变按钮样式 */
.btn-gradient {
  background: var(--accent-gradient) !important;
  border: none !important;
  color: var(--text-white) !important;
}

.btn-gradient:hover {
  opacity: 0.9;
  transform: translateY(-2px);
}
</style>
```

### Task 4: 验证实现

- [ ] **Step 1: 检查编译是否通过**

运行前端开发服务器确认无编译错误

- [ ] **Step 2: 验证样式效果**

1. 打开各页面检查字体层级
2. 检查卡片hover效果
3. 检查按钮圆角和阴影
4. 检查输入框focus效果
5. 检查表格样式

---

## 验收标准检查

- [ ] 全局CSS变量文件创建成功
- [ ] main.js 正确引入全局样式
- [ ] Element Plus 组件主题被覆盖
- [ ] 字体层级：H1 20px / H2 18px / 正文 14px / 辅助 12px
- [ ] 圆角统一：按钮 10px / 卡片 10px / 输入框 6px
- [ ] 卡片hover效果：轻微上浮 + 阴影加深
