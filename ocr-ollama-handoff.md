# EasyFix 本地 OCR 交接

记录日期：2026-11-11（北京时间）。远程接口核查基于 origin/main 的 79e9faeb。当前成果是本地原型和实测记录，EasyFix 正式版尚未接入 OCR。

## 本机运行

Windows PC 配备 RTX 4070 Ti 12GB。保留 Ollama 0.40.16 便携版和 longwayxu/xiaomi-ocr-0:bf16，监听 127.0.0.1:11435。Transformers 原版权重及其 PyTorch 等专用依赖已从实验目录清理。Pillow 和 httpx 仍供 Ollama 脚本使用。

从仓库根目录执行。若服务已经在运行，跳过启动，在另一个 PowerShell 窗口执行验证。

```powershell
& ./tmp/xiaomi-ocr/ollama/start.ps1
& ./tmp/xiaomi-ocr/.venv/Scripts/python.exe ./tmp/xiaomi-ocr/sign-test/run.py
```

换机器时使用 Ollama 官方发行包，拉取上述 BF16 模型。复用本地实验目录的官方适配代码 official_backend.py，其中包含图片预处理和非思考提示词。实验目录由 Git 忽略，接手人仅克隆仓库时需要另行获取这些脚本；图片、数据库快照和配置按授权交接。不要复制 API 密钥到文档或提交。

## 实测

同一批 20 张图片、同样输入尺寸和提示词、无提示缓存。Transformers BF16 总计 638.6 秒，单张中位 32.1 秒；Ollama BF16 总计 102.5 秒，单张中位 5.2 秒，约快 6.2 倍。人工核对 61 道目标题，关键题干完整正确分别为 40 和 41 道，均有 6 道关键错误。这个口径只衡量关键题干，整页转写、手写、批改痕迹和端到端入库另需评估。

指定题“比某数的立方还少 3 的数”实测中，Ollama 从整页和单题均读出学生式子 x²+3。现有 deepseek-flash 仅接收 OCR 文本，独立得出 x³−3 并指出两处错误。单题 OCR 约 0.19 秒（模型已加载，人工裁剪不计时），两份转写合并调用 LLM 约 3.24 秒。红色批改勾没有被 OCR 提取，教师判定须查原图。

常见失败包括分母 13 被读成 131、负号丢失、手写演算串题、图形条件遗漏。LLM 在正确题干下也曾算错，历史数据库也有录入错误。审核以原图为准。

## 对接边界

- 原图上传用 POST /api/upload/file 或 POST /api/upload/batch-simple。
- 正式知识点目录用 GET /api/knowledge-points/tree。按学科筛选现有节点，校验 knowledge_point_ids 和 primary_knowledge_point_id，未匹配的标签留待审核。
- POST /api/questions/batch 直接写入正式错题库，可关联原图并在数学题入库前校验 LaTeX。额外传 needs_review 不会变成待核对。该版本未发现截图中的错题待核对接口，review.py 是单词复习。
- 最小接法是本地脚本串联 Ollama、现有 LLM 和草稿审核。草稿分别保留原图、OCR 原文、题干、学生作答、模型参考答案、批改证据和候选标签。审核通过后上传原图并批量保存。正式写入前备份，检查逐题 errors 与成功数，回读核对图片关联、公式和标签。批量接口允许部分成功，重试前先核对已写入项。
- 手机自动识别可做成由本机领取云端任务并回传草稿，需新增任务状态、领取和回传接口。Worker 主动调用也可用 Cloudflare Tunnel 配合 Access 鉴权，固定公网隧道地址需接入域名。本机离线时无法即时识别。

## 本机证据

路径以仓库根目录为基准。以下文件都在 Git 忽略目录。

- tmp/xiaomi-ocr/regression/report.md：20 图回归、逐题评分和对照证据。
- tmp/xiaomi-ocr/expanded/report.md：与正式 D1 只读基线的逐题比对。
- tmp/xiaomi-ocr/sign-test/report.md：指定题判错验证及原始输出索引。
- tmp/xiaomi-ocr/ollama/README.md：便携运行环境和启动说明。
- tmp/xiaomi-ocr/review.html：本地审核原型，可编辑并导出草稿。
