# EasyFix Cloudflare 迁移记录

更新时间：2026-11-08（北京时间）。迁移尚未完成，现有服务仍为业务入口。

## 已完成

- Wrangler 4.158.0 已安装，通过设备授权完成登录，whoami 已验证目标账号。
- 账号 ID：52ff92165ba654aa8260a45ded30e1ef。
- D1 数据库 easyfix 已创建，ID：2de427ad-42be-412f-8afe-dfedd94f1c6a。
- 数据快照 backups/cloudflare_d1_20261108T134631252119Z 已导入 D1，28 张表的远程记录数核对和外键检查均通过；本地转换逐行回读一致。远程尚未逐字段比较。
- R2 已开通，私有桶 easyfix 已创建；202 张图片全部上传成功，失败 0 张。每张上传前已核对本地 SHA-256，尚未执行远程逐张下载校验。进度记录在 backups/cloudflare-r2-image-progress.json。
- 授权和 npm 缓存目录加入 .gitignore，禁止提交授权文件。
- 已使用现有备份脚本生成 PostgreSQL 在线快照、上传文件和配置备份：backups/easyfix_20261108T134238_555639Z。
- 备份清单中 896 个文件通过大小与 SHA-256 校验。尚未执行恢复演练。

## 当前状态

R2 开通阻塞已解除。应用尚未部署和切换，后端仍需适配 D1 的异步绑定及 R2；现有 SQLAlchemy 同步 Session 无法仅替换数据库 URL。

数据盘点：28 张表，575 道错题、1264 个单词、212 套练习、202 张图片（150229747 字节）。清单 backups/cloudflare_inventory_20261108T134446652452Z.json。

## 后续顺序

### 后端适配进展

- 新增 cloudflare/ 独立 Python Worker，不修改现有 FastAPI 服务入口。
- 配置绑定 DB 与 IMAGES；关闭 workers.dev 和 preview_urls，尚未配置公共访问域名。
- 新增异步 D1 数据层，以及学科查询、错题详情、错题分页筛选、R2 单图上传与附件读取的初版接口。尚未完成运行验证，不能标为完成。
- 共盘点 102 个业务接口，逐项待办见 cloudflare-api-checklist.md。
- 官方 Python 依赖打包工具安装完成；uv 从 0.12.3 更新为 0.13.7。
- 修复 Windows 下跨盘 Pyodide 解释器路径问题：UV_PYTHON_INSTALL_DIR 与 UV_CACHE_DIR 均放到项目 tmp 下，并重新生成失败的环境（旧环境已保留）。
- Python Worker 成功上传，版本 fa91add1-743e-4401-aa45-ffdaf6bd2fe1，启动校验 1731ms。
- 远程预览可启动，但本地代理健康请求超时，尚未取得实际 HTTP 响应。因此仅能确认上传及启动校验成功，不能确认业务可用。
- 无 ACCESS_TOKEN 时业务请求返回 503；已配置密钥后需要 Bearer 认证。前端登录会话尚未适配，不能直接开放给用户。

Python 部署：`node tmp/cloudflare-python.cjs deploy`。原生 Wrangler 不会自行安装 Python 依赖；需要先成功执行 pywrangler 同步。

1. 核对生产数据库各表及附件清单；备份为在线数据库快照，附件仅尽力复制，正式切换还需最终一致性备份。
2. 验证 Python Workers、FastAPI、D1 访问和 PDF 依赖兼容性，再确定 API 适配方案。
3. 编写并验证数据库 schema、数据转换与导入脚本，保留主键、关系、软删除、公式字符串。
4. 适配数据库访问、R2 上传与鉴权、配置持久化、AI 与 PDF。
5. 部署 Vue 和 API 至测试环境，核对功能、数据与附件。
6. 暂停写入，完成最终备份、迁移与核对后切换业务入口。

## 本机命令

通过 `node tmp/cloudflare-cli.cjs <命令>` 调用 Wrangler；包装脚本将配置与日志放在被忽略的 tmp/cloudflare-config 下。凭证不得打印或提交。

备份命令：

```text
python backend/scripts/backup_data.py --online-snapshot --pg-bin C:/Progra~1/PostgreSQL/18/bin
```

备份含密钥，禁止将整个备份目录上传为公共网站资源。
