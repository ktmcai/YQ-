# YONIQ 官网

官网前端、产品及资料管理后台、在线文档、飞书同步和部署配置的独立源码仓库。

## 目录

- `网页/`：官网静态文件、在线文档阅读页及本地托管的 PDF.js 阅读器；无需前端构建。
- `website-admin/`：Flask 管理后台、API、飞书导入与同步、模板、静态资源和测试。
- `website-admin/deploy/`：Nginx、systemd 服务、飞书凭证加载和证书续期配置；不含实际凭证。
- `website-admin/migrations/`：历史迁移脚本及初始资料快照，按各目录说明使用，不能用于覆盖最新业务数据。
- `品牌素材/`：公司标志原图。
- `AGENTS.md`：项目约定、部署操作和功能变更记录。

## 当前功能

支持产品及 AXIS JP／JS／JC 系列管理、PDF 和网页资料管理、在线文档编辑、飞书链接导入及手动同步、文档搜索和章节目录。飞书格式同步保留接口提供的表格颜色、字体、字号、列宽及行高。

设备协议入口统一到 CANopen／EtherCAT 和串口在线手册。飞书采用“协议手册”父标题，在下级“CANOPEN协议”“EtherCAT协议”或“串口协议”标题下留空，导入或同步时自动补充对应链接；已有内容不覆盖。具体匹配规则见 `AGENTS.md`。

## 本地预览和验证

在仓库根目录执行：

```powershell
python -m http.server 8080 --directory 网页
```

打开 http://127.0.0.1:8080/ 可预览静态布局。此服务器不提供 `/api/products`、`/api/documents` 或动态 `/guides/` 路由，不能代替完整后台。`网页/guides/` 是初次迁移的静态快照，不代表官网最新正文；线上文档由后台数据库提供。完整预览按 `AGENTS.md` 使用服务器 SSH 转发。

后台使用 Python 3.11+。安装依赖后运行全部测试：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r website-admin/requirements.txt
.\.venv\Scripts\python.exe -B -m unittest discover -s website-admin -p "test_*.py" -v
```

生产环境通过 Linux 上的 Gunicorn/systemd 运行后台，继续保持单 worker；飞书同步任务机制不支持直接改为多 worker。后台需配置 `YONIQ_SECRET_KEY`、`YONIQ_DATA_DIR`；正式 HTTPS 环境保持 `YONIQ_COOKIE_SECURE=1`。飞书凭证仅在服务器的受限环境文件中配置。

## 部署与数据备份

正式网站：https://yoniqtech.com/ 。前端部署到 `/var/www/yoniq/`，后台部署到 `/opt/yoniq-docs/`。详细步骤见 `AGENTS.md`；本次源码同步没有部署或修改线上数据。

此仓库备份源码和随源码保存的历史资料，**不包含线上最新业务数据**。完整恢复需另外同时备份 `/var/lib/yoniq-docs/documents.sqlite`、`files/` 和 `guide-files/`。后台编辑的产品、在线文档正文和后续上传文件均在这些运行数据中。

`catalog.json`、`feishu_sources.json` 及历史静态快照用于初始迁移，不能代替当前数据库或覆盖后台修改。服务器密钥配置另行安全保存，不进入 Git。

SSH 私钥和初始登录信息保留在 `F:\Desk\HPM_Motor\Motor_ctl_demo`，未复制到此仓库。Git 历史、品牌素材和原有忽略规则保留。

## 本次同步

2026-11-17 从 `F:\Desk\HPM_Motor\Motor_ctl_demo` 同步最新官网源码，包含 2026-11-13 的统一协议入口及空白协议标题自动补链接功能。部署和迁移记录已同步到 `AGENTS.md`，其中本地代码路径适配为本仓库。

本次未执行 Git 提交或推送。上传前可检查：

```powershell
git status --short
git diff --stat
```
