# YONIQ 官网前端

首页为 `index.html`；在线文档入口为 `guides.html`，PDF 阅读页为 `document.html`。本目录包含站点静态资源、本地托管的 PDF.js 阅读器及历史资料快照，无需前端构建。

在仓库根目录运行：

```powershell
python -m http.server 8080 --directory 网页
```

打开 http://127.0.0.1:8080/ 可预览静态布局。产品、资料列表和在线文档依赖后台的 `/api/products`、`/api/documents`、`/guides/` 路由；直接打开 HTML 或使用简单静态服务器不能加载完整实时内容。`guides/` 是初次迁移的静态快照，不能代表或覆盖线上最新正文。

部署时同步站点资源至 `/var/www/yoniq/`，同时保留后台路由和独立持久化数据。完整目录结构、测试与部署说明见仓库根目录的 `README.md` 和 `AGENTS.md`。
