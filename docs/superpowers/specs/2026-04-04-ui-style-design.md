# 全局 UI 风格升级设计方案

## 概述
统一全局字体大小，优化配色系统，升级为简洁现代的视觉效果。

## 设计风格
- **主色调**：黑白灰为主色，彩色点缀
- **风格**：活泼学生风 - 简洁清爽、层次分明
- **圆角**：中等圆角 (8-12px)

## 字体层级

| 元素 | 字号 | 字重 | 颜色 |
|-----|------|------|-----|
| 页面标题 H1 | 20px | bold | #303133 |
| 区块标题 H2 | 18px | bold | #303133 |
| 卡片标题 H3 | 16px | 600 | #303133 |
| 正文内容 | 14px | normal | #606266 |
| 辅助文字 | 12px | normal | #909399 |

## 配色系统

### 背景色
```css
--bg-primary: #ffffff;      /* 主背景 */
--bg-secondary: #f5f5f5;    /* 次级背景 */
--bg-tertiary: #fafafa;      /* 卡片背景 */
--bg-dark: #1a1a1a;         /* 深色背景 */
```

### 文字色
```css
--text-primary: #303133;     /* 主要文字 */
--text-secondary: #606266;   /* 次要文字 */
--text-muted: #909399;       /* 辅助/禁用文字 */
--text-white: #ffffff;       /* 深色背景上的文字 */
```

### 强调色（彩色点缀）
```css
--accent-blue: #409eff;      /* 主按钮/链接 */
--accent-purple: #8250df;    /* 渐变起点 */
--accent-pink: #ec7cf3;      /* 渐变终点 */
--accent-gradient: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
```

### 功能色
```css
--success: #67c23a;         /* 成功 */
--warning: #e6a23c;         /* 警告 */
--danger: #f56c6c;          /* 错误 */
--info: #909399;            /* 信息 */
```

### 边框色
```css
--border-light: #f0f0f0;    /* 浅边框 */
--border-default: #dcdfe6;   /* 默认边框 */
--border-dark: #303133;      /* 深色边框 */
```

## 圆角系统

```css
--radius-sm: 6px;           /* 小圆角：输入框、标签 */
--radius-md: 10px;          /* 中圆角：按钮、卡片 */
--radius-lg: 16px;           /* 大圆角：弹窗、大卡片 */
--radius-full: 9999px;      /* 全圆角：头像、开关 */
```

## 阴影系统

```css
--shadow-sm: 0 1px 4px rgba(0, 0, 0, 0.06);
--shadow-md: 0 2px 12px rgba(0, 0, 0, 0.08);
--shadow-lg: 0 8px 24px rgba(0, 0, 0, 0.12);
```

## 实现方案

### 1. 创建全局样式文件
创建 `frontend/src/styles/variables.css` 存放 CSS 变量

### 2. 在 main.js 中引入全局样式
```javascript
import './styles/variables.css'
```

### 3. Element Plus 主题覆盖
在 variables.css 中覆盖 Element Plus CSS 变量

### 4. 统一字体层级
在 App.vue 或全局样式中添加基础排版样式

## 组件样式规范

### 卡片
- 背景：白色
- 圆角：10px
- 阴影：--shadow-md
- 内边距：16-20px

### 按钮
- 圆角：8px
- hover：轻微上浮 + 阴影加深
- 主按钮：蓝色渐变背景

### 输入框
- 圆角：6px
- 边框：1px solid --border-default
- focus：边框色变为 --accent-blue

### 表格
- 表头：背景 #fafafa，字重 600
- 行hover：背景 #f5f7fa
- 圆角：10px（外框）

## 验收标准

1. 全局字体层级清晰：标题 > 正文 > 辅助
2. 配色协调：黑白灰为主，彩色用于强调
3. 圆角统一：按钮/卡片/输入框各有固定圆角值
4. hover效果：卡片轻微上浮 + 阴影加深
5. 整体风格：简洁清爽、活泼友好
