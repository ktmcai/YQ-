# YONIQ 官网

官网前端、产品及资料管理后台、部署配置的独立源码仓库。

## 目录

- `网页/`：官网静态文件，首页为 `网页/index.html`，包含产品目录、资料卡片和 PDF 阅读页。
- `website-admin/`：Flask 管理后台、API、模板、静态资源和测试。
- `website-admin/deploy/`：Nginx、systemd 服务及证书续期配置。
- `品牌素材/`：公司标志原图；官网实际使用的图片仍随前端文件保留。
- `AGENTS.md`：项目约定、部署操作和服务器状态记录。

## 本地预览和验证

在仓库根目录执行：

```powershell
python -m http.server 8080 --directory 网页
```

打开 http://127.0.0.1:8080/ 可预览静态页面。这个简单静态服务器不提供 `/api/products`、`/api/documents`，因此不能展示完整实时产品和资料；完整预览可按 `AGENTS.md` 使用服务器 SSH 转发。

后台使用 Python 3.11+。安装依赖后运行已有测试：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r website-admin/requirements.txt
.\.venv\Scripts\python.exe -B -m unittest discover -s website-admin -p test_app.py -v
```

生产环境通过 Linux 上的 Gunicorn/systemd 运行后台，参见 `website-admin/deploy/`。后台启动需配置 `YONIQ_SECRET_KEY`、`YONIQ_DATA_DIR`；正式 HTTPS 环境保持 `YONIQ_COOKIE_SECURE=1`。

## 部署与数据

正式网站：https://yoniqtech.com/ 。前端部署到 `/var/www/yoniq/`，后台部署到 `/opt/yoniq-docs/`。详细命令见 `AGENTS.md`；本仓库整理不会自动更新线上网站。

线上 SQLite 数据库和已上传 PDF 位于 `/var/lib/yoniq-docs/`，不包含在本仓库中，需要单独同时备份数据库与文件。`website-admin/catalog.json` 只用于首次迁移，不代表后台当前的产品数据。

SSH 私钥和初始登录信息保留在原来的 `F:\Desk\HPM_Motor\Motor_ctl_demo` 目录，不复制或提交到此仓库。服务器环境密钥、TLS 私钥、运行数据同样不进入 Git。

## Git 管理

已初始化本地 `main` 分支；尚未提交或关联远程仓库。检查内容后可创建首次提交：

```powershell
git add .
git commit -m "Initial YONIQ website source"
```

2026-10-21 从 `F:\Desk\HPM_Motor\Motor_ctl_demo` 复制整理，原文件保留。后续建议统一在本目录修改和管理官网源码。
