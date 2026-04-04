# 奖励卡片样式改造设计方案

## 概述
将奖励商城的卡片展示从当前网格布局改为左侧列表+右侧详情的交互模式，提供更沉浸式的奖励浏览体验。

## 布局结构

```
+------------------+----------------------------------------+
|  奖励列表 (120px)  |           奖励详情区域                  |
|  +--------+      |  +------------------------------------+ |
|  | 小图   |      |  |                                    | |
|  +--------+      |  |            大图                    | |
|  | 名称   |  ---> |  |                                    | |
|  +--------+  选中 |  +------------------------------------+ |
|  | 小图   |      |  奖励名称                              |
|  +--------+      |  所需积分: ⭐ 100   库存: 5          |
|  | 小图   |      |  奖励描述: 这是一个xxx奖励...          |
|  +--------+      |  [立即兑换]                            |
|  |  ...   |      |                                        |
+------------------+----------------------------------------+
```

## 交互规格

### 左侧列表
- 单列竖排，固定宽度120px
- 每行一个卡片：图片(120x90) + 名称(单行截断)
- 支持垂直滚动（当奖励数量超过可视区域）
- hover效果：边框变蓝色(#409eff) + 缩放1.05
- 选中效果：边框高亮(#409eff) + 背景浅蓝(#ecf5ff)

### 右侧详情区
- 左侧大图撑满容器宽度，高度自适应
- 下方信息区：名称、积分+库存、描述、兑换按钮
- 无选中时显示空状态提示

## 样式规格

### 左侧卡片
```css
.reward-list-card {
  width: 120px;
  height: 120px;
  border: 2px solid #f0f0f0;
  border-radius: 8px;
  overflow: hidden;
  cursor: pointer;
  transition: all 0.2s ease;
}
.reward-list-card:hover {
  border-color: #409eff;
  transform: scale(1.05);
}
.reward-list-card.selected {
  border-color: #409eff;
  background: #ecf5ff;
}
.reward-list-card img {
  width: 100%;
  height: 90px;
  object-fit: cover;
}
```

### 右侧详情
```css
.reward-detail-image {
  width: 100%;
  max-height: 400px;
  object-fit: contain;
  background: #f5f5f5;
}
.reward-detail-content {
  padding: 20px;
}
.reward-detail-name {
  font-size: 20px;
  font-weight: bold;
  color: #303133;
  margin-bottom: 12px;
}
.reward-detail-meta {
  display: flex;
  gap: 20px;
  margin-bottom: 16px;
}
.reward-detail-desc {
  font-size: 14px;
  color: #606266;
  margin-bottom: 20px;
  line-height: 1.6;
}
```

## 数据映射

从API获取的奖励数据映射：
```javascript
{
  id: r.id,
  name: r.name,
  description: r.description || '',
  image_url: r.image_url || '',
  points_required: r.cost_stars,
  stock: r.remaining_stock,
}
```

## 组件状态

| 状态 | 左侧卡片 | 右侧详情 |
|-----|---------|---------|
| 无选中 | 默认灰色边框 | 显示空状态"请选择一个奖励" |
| 选中 | 蓝色边框+浅蓝背景 | 显示选中奖励的完整信息 |
| 无图片 | 显示默认图标 | 显示默认占位图 |

## 验收标准

1. 左侧列表固定120px宽度，支持垂直滚动
2. hover时卡片边框变色+缩放效果
3. 点击卡片后右侧显示对应详情
4. 选中卡片保持高亮状态
5. 右侧大图自适应宽度
6. 描述文字完整展示
7. 兑换按钮根据库存/余额状态正确禁用
