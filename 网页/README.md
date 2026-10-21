# YONIQ 官网前端

首页为 `index.html`；本目录包含官网静态资源和 PDF 阅读页，不需要前端构建。

在仓库根目录运行：

```powershell
python -m http.server 8080 --directory 网页
```

打开 http://127.0.0.1:8080/ 可预览静态布局。产品和资料分别通过 `/api/products`、`/api/documents` 获取，需要后台及相应反向代理；直接打开 HTML 或使用简单静态服务器不能加载完整实时内容。

部署时将本目录的网站资源同步到 `/var/www/yoniq/`。完整目录结构、测试与部署说明见仓库根目录的 `README.md` 和 `AGENTS.md`。
