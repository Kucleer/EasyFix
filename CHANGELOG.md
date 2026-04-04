# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [1.0.9] - 2026-04-04

### Added
- 奖励管理新增图片上传功能
- 奖励管理新增奖励描述字段
- 奖励商城展示奖励图片和描述
- 简单文件上传接口 `/api/upload/file`（不进行OCR）

### Changed
- 奖励卡片布局改为左侧列表+右侧详情模式
  - 左侧：120px单列卡片列表，支持垂直滚动
  - 右侧：大图+名称+积分+库存+描述+兑换按钮
  - hover效果：边框变蓝+缩放1.05
  - 选中效果：蓝色边框+浅蓝背景
- 积分明细Tab展示所有积分变更记录（非仅兑换）
- 单词复习抽词排序：新词40% > 需加强40% > 薄弱20%
- 练习页查看详情按钮改为蓝色(primary)
- 练习页详情默认打开详情tab
- 单词正确率成就改为累计模式（满足条件7/14/30次后解锁对应等级）

### Fixed
- 单词正确率成就错误触发问题（需≥90%才触发）
- 单词复习完成后未触发单词达人成就计算
- 单词复习提交后光标未恢复问题
- reward表缺少image_url列（已添加）

### Database
- reward表新增image_url列

### API Endpoints
- POST /api/upload/file - 简单文件上传（无OCR）

## [1.0.8] - 2026-04-03

### Added
- 激励中心页面（前端）
  - 积分成就 Tab：显示积分余额、今日获取、成就徽章墙
  - 奖励商城 Tab：显示可用奖励列表
  - 积分明细弹窗：显示积分获取/消耗记录
- 激励系统后端 API
  - 积分余额查询 `/api/stars/balance`
  - 积分记录查询 `/api/stars/records`
  - 成就列表查询 `/api/achievements`
  - 成就进度查询 `/api/achievements/progress`
  - 奖励列表查询 `/api/rewards`
  - 奖励兑换 `/api/rewards/{id}/redeem`
  - 激励概览 `/api/motivation/overview`
- 激励数据初始化服务
  - 根据已有练习数据（错题、练习集、相似题、单词）初始化成就进度
  - 根据历史数据初始化积分余额和积分记录
- 激励触发动点（供内部调用）
  - 上传错题、复习练习集、生成相似题、背单词、创建练习集等行为触发积分

### Changed
- 激励成就数据来源：从练习集实际数据计算（非静态模拟数据）
- 前端 Motivation.vue：从后端 API 获取实时数据

### Fixed
- element-plus/icons-vue 图标名称错误（Book→Notebook, Gift→Present, Ribbon→Medal, Study→School, Target→Aim）
- el-tabs 组件 v-model:active-tab 语法错误

## [1.0.7] - 2026-04-02

### Added
- 练习集详情页新增"单词练习"标签页
  - 展示所有单词题目
  - 显示正确/错误状态和用户答案
  - 单词标签显示
  - 用时、正确数等统计数据
- 练习集列表页新增日期筛选功能
  - 按创建时间范围筛选

### Changed
- 练习集列表从卡片布局改为表格布局
- 练习集详情页默认显示详情标签页
- 移除详情页"最近复习"字段
- 名称列宽度调宽（1200px）
- 日期筛选器宽度调窄（400px）
- Element Plus 语言设置为中文

### Fixed
- 单词练习集 API 未返回 `is_correct`、`user_answer`、`tags` 等字段
- 历史单词复习练习集的学科错误（数学→英语）

## [1.0.6] - 2026-03-31

### Added
- 单词复习计时功能
- 练习集复习完成上传图片功能
  - 非单词练习集标记已复习时支持上传多张完成图片
  - 图片存储在练习集记录中
  - 复习过程实时显示用时（分:秒）
  - 复习结果页面显示总用时
  - 用时数据记录到练习集

### Changed
- 单词复习背景虚化效果
- 单词复习布局优化：提示框与输入框分行显示
- 单词复习学科设置为"英语"（单词复习归为英语学科）
- 单词表默认每页展示20条

### Fixed
- 历史单词复习练习集的学科错误（已批量修复为"英语"）
- 单词复习结果duration参数未传递问题

### Database
- practice_set 表新增 review_images 字段

## [1.0.5] - 2026-03-30

### Added
- 学习状态分析模块（LearningReports.vue）
  - LLM多维度学习报告生成：整体概况、错题分析、单词分析、学习建议、总结
  - 报告可按学科、年级、时间范围筛选
  - 每次分析报告均可保存查看
- 单词复习纳入练习集
  - 单词复习后自动创建练习集记录
  - 练习集列表可按来源类型筛选（source_type: question/word）
- 单词正确率等级快速筛选
  - 五个等级：新词、需加强、薄弱、一般、掌握
  - 前端显示各等级单词数量

### Changed
- 单词复习抽样算法优化：优先抽样未复习(20%)和低正确率(30%)单词
- 单词列表返回新增 accuracy_level 字段

### Database
- practice_set 表新增 source_type 字段
- 新增 word_review_session 表（单词复习场次关联练习集）

### API Endpoints
- POST /api/learning-reports/generate - 生成学习分析报告
- GET /api/learning-reports/list - 获取报告列表
- GET /api/learning-reports/{id} - 获取报告详情
- DELETE /api/learning-reports/{id} - 删除报告
- GET /api/practice-sets?source_type=word - 获取单词来源的练习集
- GET /api/words?accuracy_level=new - 按正确率等级筛选单词

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
