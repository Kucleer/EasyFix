# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [1.0.4] - 2026-03-29

### Added
- 单词本模块（Words.vue）
  - 单词CRUD管理
  - 多种导入方式：文本粘贴、文件上传、图片OCR识别
  - 在线复习：默写英文、选择题两种题型
  - 多选复习：支持勾选单词后进行专项复习
  - PDF打印默写功能
  - 复习统计：正确率、复习次数、错词记录
  - 导入预览表格：显示英文、中文、音标，可编辑
  - 智能分隔单词：自动识别序号、英文、中文、音标
- 复习弹窗整体放大100%，提升UI体验
- 练习集批量操作功能
  - 批量下载PDF：勾选练习集后可一次性下载多个PDF
  - 批量删除：勾选后可一次性删除多个练习集

### Changed
- 复习弹窗缩小至70%
- 答题成功/失败增加动画效果（正确放大发光，错误抖动）
- 复习答题框文本放大至48px
- 复习增加终止按钮，可提前结算已答题结果
- 练习集页面默认展示所有练习集（默认1000条）
- 前端配置支持内网IP访问（vite server.host: 0.0.0.0）
- 配置/管理中心增加访问密码保护（密码：32167）
- 导航菜单排序调整（配置/管理中心移至最后）
- 前端添加H5移动端适配样式
- 修复练习集API返回数据为None报错问题
- 单词复习数据记录优化（session_id传递正确）
- 单词列表增加正确率字段，支持区间筛选和排序
- 正确率颜色显示：100%绿色，0%红色，渐变色
- 复习次数为0时正确率显示"--"
- 错题上传增加"跳过图片，直接手动录入"功能
- 手动录入模式显示缺省图片（无交互）
  - 批量下载PDF：勾选练习集后可一次性下载多个PDF
  - 批量删除：勾选后可一次性删除多个练习集

### Changed
- 复习API支持指定word_ids参数（多选复习）
- 单词表格增加多选列
- 导入弹窗增加预览表格，弹窗宽度扩大至1100px
- 智能分隔算法优化：支持序号分割、音标提取、多空格分隔

### Database
- 新增 word 表（单词表）
- 新增 word_tag 表（单词-标签关联表）
- 新增 word_review_log 表（单词复习记录表）
- 新增 word_review 表（单词复习场次表）

### API Endpoints
- POST /api/words - 创建单词
- GET /api/words - 获取单词列表
- GET /api/words/{id} - 获取单词详情
- PUT /api/words/{id} - 更新单词
- DELETE /api/words/{id} - 删除单词
- POST /api/words/batch - 批量创建单词
- GET /api/words/stats/summary - 单词统计
- POST /api/words/review/start - 开始复习
- POST /api/words/review/submit - 提交复习结果
- GET /api/words/errors - 获取错词列表
- POST /api/words/print-pdf - 生成打印PDF

## [1.0.3] - 2026-03-28

### Added
- Multi-select questions in question list
- Practice set management (create, view, delete)
- Batch generate similar questions
- Print practice set as PDF (original or similar questions)
- Review count tracking for questions
- Practice sets page

### Changed
- Similar question now works in batch mode (removed single-question interaction)
- Questions table now has selection column

## [1.0.2] - 2026-03-28

### Fixed
- LLM similar question returns empty content (MiniMax thinking block issue)
- Added `thinking={"type": "disabled"}` to disable MiniMax thinking blocks
- Similar question generation now works correctly for math problems

## [1.0.1] - 2026-03-28

### Added
- Grade and semester support for questions (一年级至高三年级, 上学期/下学期)
- Tag management and selection for questions
- Statistics by grade and semester
- Management center for error books, subjects, tags, error types, knowledge points
- Upload preview after question creation
- Original image display in question detail view
- Edit functionality for questions with tag support

### Changed
- Grade dropdown now shows Chinese labels (一年级, 二年级, etc.)
- Search box width adjusted to be narrower
- Question text areas have increased height

### Fixed
- Subject dropdown not loading data
- Missing database columns for grade/semester
- Image upload directory path issue

## [1.0.0] - 2026-03-28

### Added
- Initial release
- Image upload with OCR recognition (multiple providers)
- Question management (CRUD)
- Error book organization
- Subject categorization
- Similar question generation via LLM
- Statistics dashboard
