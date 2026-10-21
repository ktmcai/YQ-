# 项目说明

## 工作准则

- 编码前明确假设、成功标准和验证方式；存在影响实现的歧义时先澄清。
- 使用满足需求的最少代码，不添加未要求的功能、抽象或配置。
- 只修改任务需要的内容，保持现有风格，不顺带重构、格式化或删除已有死代码。
- 清理本次修改造成的无用导入、变量、函数或文件；每项修改都应能追溯到用户请求。
- 多步骤任务简述计划及验证方法，按实际风险进行验证，直到成功标准满足。
- 子代理仅允许使用 `gpt-5.6-sol` 或 `gpt-6-astra`，默认 `gpt-5.6-sol`；创建时显式指定允许的模型或确认继承模型符合限制。两者均不可用时报告原因，不回退到其他模型。

## 阿里云官网服务器

以下连接和部署状态于 2026-10-14 验证成功，后续操作前需重新检查实际状态。

- 域名：`yoniqtech.com`，计划同时支持 `www.yoniqtech.com`。
- 公网 IP：`120.79.178.50`。
- 地域：华南 1（深圳）。
- 系统：Alibaba Cloud Linux 3.2104 U12。
- SSH 用户：`root`；端口：`22`。
- 私钥路径：`F:\Desk\HPM_Motor\Motor_ctl_demo\yoniq-deploy.pem`。
- 私钥文件权限已限制为当前 Windows 用户 `DESKTOP-04V1QRO\Kimi`。
- 服务器 ED25519 主机指纹：`SHA256:PVMfkbibC38E2U23363ANV39+6CjBXPwRNWq4r67pmw`。
- 不将私钥内容写入文档、日志或聊天，不将 `.pem` 文件加入网站上传内容或提交到版本库。

### SSH 登录（本地 PowerShell）

```powershell
$project = 'F:\Desk\HPM_Motor\YQ官网'
$key = 'F:\Desk\HPM_Motor\Motor_ctl_demo\yoniq-deploy.pem'
$server = 'root@120.79.178.50'
$knownHosts = Join-Path $env:TEMP 'yoniq-deploy-known-hosts'
$sshOptions = @(
    '-i', $key,
    '-o', 'IdentitiesOnly=yes',
    '-o', 'BatchMode=yes',
    '-o', 'ConnectTimeout=15',
    '-o', 'StrictHostKeyChecking=yes',
    '-o', "UserKnownHostsFile=$knownHosts"
)
ssh @sshOptions $server
```

`$knownHosts` 是本次成功连接时建立的主机记录。若临时文件已清理，先用 `ssh-keyscan -t ed25519 120.79.178.50` 获取候选主机记录，并用 `ssh-keygen -l -f <候选记录文件>` 核对上述指纹；匹配后再保存到 `$knownHosts`。若指纹发生变化，先查明原因，不关闭主机身份校验。

执行单条远程命令，无需进入交互终端：

```powershell
ssh @sshOptions $server 'id; uptime; systemctl is-active nginx; nginx -t'
```

Windows 通过管道向 Linux 传入多行脚本时，需处理 CRLF 换行：

```powershell
$script | ssh @sshOptions $server "tr -d '\015' | bash -se"
```

本次本地工具的普通沙箱出现 `helper_unknown_error: setup refresh had errors`，使用经审批的沙箱外执行后成功连接。后续先按当前环境的正常权限运行，遇到相同错误再按工具流程处理。

## 网站部署与预览

- 本地首页：`F:\Desk\HPM_Motor\YQ官网\网页\index.html`。
- 首页主体为静态 HTML，原有样式、脚本和标志图片内嵌；产品目录通过 `/api/products`、PDF 卡片通过 `/api/documents` 读取内容管理后台，不需要前端构建。
- 服务器网站目录：`/var/www/yoniq`；首页：`/var/www/yoniq/index.html`。
- 已安装 Nginx 1.24.0，并设置开机启动。
- Nginx 配置：`/etc/nginx/nginx.conf`。
- 安装后的原始配置备份：`/etc/nginx/nginx.conf.before-yoniq`，后续不要覆盖。
- 2026-10-21 已启用公网 `80`（跳转 HTTPS）和 `443`（正式网站）；`127.0.0.1:8080` 内部预览仍保留，后台应用仍仅监听 `127.0.0.1:8001`。
- 已验证配置检查通过、首页返回 HTTP 200、本地文件与服务器文件及 HTTP 响应的 SHA-256 一致。
- 用户已于 2026-10-21 确认备案完成，备案号为 `苏ICP备2026079677号`，两个域名均已解析到服务器；官网已公开上线并在页脚展示备案查询链接。

### 从本机浏览服务器页面

先运行上面的 PowerShell 变量定义，再启动 SSH 转发：

```powershell
ssh @sshOptions -o ExitOnForwardFailure=yes -o ServerAliveInterval=30 -o ServerAliveCountMax=3 -N -L '127.0.0.1:18080:127.0.0.1:8080' $server
```

浏览器打开 `http://127.0.0.1:18080/`。该链接仅在本机、SSH 通道运行时有效；上述命令会保持运行，用 Ctrl+C 结束。若端口已被已有预览通道占用，先验证现有通道，不重复启动或终止无关进程。通过工具启动后台通道时使用 `Start-Process -WindowStyle Hidden`。

### 更新首页

```powershell
scp @sshOptions (Join-Path $project '网页\index.html') 'root@120.79.178.50:/var/www/yoniq/index.html'
```

确认上传成功后验证；仅更新静态首页无需重启 Nginx：

```powershell
Get-FileHash -LiteralPath (Join-Path $project '网页\index.html') -Algorithm SHA256
ssh @sshOptions $server 'nginx -t && sha256sum /var/www/yoniq/index.html && curl -fsSI http://127.0.0.1:8080/'
```

已知上线前待补齐事项：`manuals/YONIQ_AXIS_JP62-48-G1.pdf` 被首页引用但文件不存在；中文联系方式为空。不要擅自编造文档、联系方式或备案号。

## PDF 文档管理后台（2026-10-15 新增）

- 本地后台源码：`F:\Desk\HPM_Motor\YQ官网\website-admin`；依赖在 `requirements.txt`。
- 正式管理入口：`https://yoniqtech.com/admin/`，上线后优先使用该 HTTPS 地址；旧本机预览通道保留用于排查。
- 管理账号：`admin`；初始登录信息保存在 `F:\Desk\HPM_Motor\Motor_ctl_demo\文档管理登录信息.txt`，仅当前 Windows 用户可读。不要输出密码或把这个文件上传到网站、加入版本库。
- 管理页支持修改密码。修改后初始密码失效，原有管理会话全部退出；该本地文件不会自动更新。
- 支持上传、编辑名称、替换 PDF、草稿、发布、下架和删除。单份文件最大 30 MB，拒绝加密或无法解析的 PDF。
- 首页自动读取已发布文档，卡片提供独立的“在线查看”和“下载 PDF”；更改发布状态后刷新官网查看。
- 原有快速选型飞书卡片保留。不要未经用户指定便将项目中的业务 PDF 批量发布。
- 新增首页资源：`网页\documents.css`、`网页\documents.js`；站内阅读页：`网页\document.html`、`网页\document.css`、`网页\document.js`。这些资源需要与首页一起同步至 `/var/www/yoniq/`。
- 服务器后台源码及独立 Python 3.11 环境：`/opt/yoniq-docs`、`/opt/yoniq-docs/venv`。
- systemd 服务：`yoniq-docs`；运行用户为 `yoniq-docs`，仅监听 `127.0.0.1:8001`。
- 配置：`/etc/yoniq-docs.env`，包含会话密钥，不要输出其内容。2026-10-21 正式开放 HTTPS 后已设置 `YONIQ_COOKIE_SECURE=1` 并重启后台；管理会话 Cookie 必须保留 Secure、HttpOnly、SameSite=Strict。
- Nginx 转发配置：`/etc/nginx/default.d/yoniq-docs.conf`；转发 `/admin`、`/api/`、`/documents/` 到后台，仍通过原来的 `127.0.0.1:8080` 提供内部预览。
- **持久化数据**：`/var/lib/yoniq-docs/documents.sqlite`（SQLite）及 `/var/lib/yoniq-docs/files/`（PDF）。两者位于网站及程序目录之外，更新、重部署时必须保留；备份时需同时备份数据库与 PDF 文件。
- 本次接入前的首页备份：`/var/backups/yoniq-docs/index.before-admin.html`。该文件不包含后续上传的文档数据。
- 后台测试：使用安装了 Flask、pypdf 的 Python 3.11+ 执行 `python -B -m unittest discover -s website-admin -p test_app.py -v`。
- 已完成本地及服务器 12 项后台测试、浏览器登录/上传/发布/查看/下载/改名/下架/删除验证；验证用 PDF 已删除。

常用只读检查及后台重启（本地先定义上面的 `$sshOptions` 和 `$server`）：

```powershell
ssh @sshOptions $server 'systemctl is-active yoniq-docs; curl -fsS http://127.0.0.1:8080/api/documents'
ssh @sshOptions $server 'journalctl -u yoniq-docs -n 30 --no-pager'
ssh @sshOptions $server 'systemctl restart yoniq-docs'
```

修改后台 Python 代码后重启 `yoniq-docs`；修改 Nginx 转发规则后先 `nginx -t` 再重载 Nginx。仅上传 PDF 或更新静态网页无需重启服务。不要使用 `chmod 777`；后台虚拟环境、模板和静态资源需要对运行用户可读，配置和持久化数据保持受限权限。

## 产品管理（2026-10-15 新增）

- 正式管理入口：`https://yoniqtech.com/admin/products`，与资料管理共用账号和密码。后台提供“产品管理／资料管理”切换。
- 本次先管理产品条目，分类沿用原有的六类：AXIS、GEAR、MOTOR、DRIVE、LINK、STUDIO；未增加分类编辑功能。
- 支持新增、编辑名称和中英文简介、调整所属分类及显示顺序、草稿、发布、下架和删除。
- 链接方式支持网页链接、已上传 PDF、暂不添加资料。PDF 必须先发布才能随产品发布；PDF 后续下架或删除时，产品保留展示但暂停资料链接。
- 产品默认按分类、排序数字、创建顺序展示；数字越小越靠前。分类原有卡片布局和暂无产品状态保留。
- 后台模块：`website-admin/products.py`，由 `app.py` 注册；模板：`templates/products.html`、`templates/product_edit.html`。
- 官网资源：`网页/products.js`、`网页/products.css`，需要与 `网页/index.html` 一起同步到 `/var/www/yoniq/`。产品目录依赖运行中的后台 API，直接用 `file://` 打开首页不能读取实时目录。
- 数据仍在 `/var/lib/yoniq-docs/documents.sqlite`，新增 `product_categories`、`products`、`catalog_migrations` 三张表。
- `website-admin/catalog.json` 保存本次从原官网提取的六类、八个产品，**仅用于首次迁移**；迁移标记确保重启不覆盖后台修改、不重新添加已删除产品。后续产品变更使用后台或针对实际数据库执行明确的数据迁移，不靠修改此 JSON 更新线上内容。
- SQLite 连接已启用外键；删除产品不会删除关联 PDF，删除 PDF 会清除产品的文档关联。
- 迁移前备份：`/var/backups/yoniq-docs/before-products-20261015-113113/`，含原数据库、后台源码和首页；不要覆盖。恢复数据库前需确认不会丢失备份之后上传的内容。
- 本地及服务器已通过 19 项测试，另已通过浏览器产品新增/发布/排序/分类移动/PDF 关联/下架/删除与手机中英文验证。测试产品已删除，原有产品和已上传 PDF 保留。

## 资料类型扩展（2026-10-15）

- 资料管理的“新增资料／编辑资料”支持“上传 PDF”和“网页链接”两种类型，共用草稿、发布、下架、删除流程。
- PDF 卡片继续提供“在线查看”和“下载 PDF”；链接卡片显示“打开链接”，在新标签页打开。两者沿用蓝色资料卡片样式。
- 网页链接需为有效的 `https://` 或 `http://` 地址，不能包含账号密码。飞书等外部文档的访问权限仍需在原平台设置。
- `documents` 表新增 `source_type`（默认 `pdf`）和 `external_url`（默认空字符串）；启动时增量迁移，旧 PDF 的 ID、文件及发布状态保持不变。链接资料的文件字段为空、页数和大小为零，不能通过 PDF 查看或下载路由访问。
- 类型可以在编辑时切换：链接改为 PDF 必须选择文件；PDF 改为链接会在保存成功后移除原文件。已关联产品的 PDF 需先在产品管理中修改关联，才能改为网页链接；产品的 PDF 下拉列表仅显示真正的 PDF 资料。
- 更新前完整备份：`/var/backups/yoniq-docs/before-document-links-20261015-115807/`，含数据库、PDF、后台源码与本次修改的官网资源。不要覆盖或直接恢复以免丢失后续内容。
- 本地和服务器均通过 26 项测试，并完成浏览器链接/PDF 新增、草稿、发布、编辑、类型切换、查看、下载、删除及手机中英文显示验证。验证资料已清理，原有 PDF、产品与管理账号保留。

## 正式域名与 HTTPS（2026-10-21）

- 本次访问失败原因为 Nginx 仍只监听内部预览地址，未启用公网网站端口；域名解析已正确生效。已添加公网服务配置，不覆盖原内部预览配置。
- 正式网站：`https://yoniqtech.com/`，`https://www.yoniqtech.com/` 同样可用；两个域名的 HTTP 请求跳转到 `https://yoniqtech.com` 并保留路径和查询参数。
- 公网配置：`/etc/nginx/conf.d/yoniq-public.conf`；本地副本：`website-admin/deploy/yoniq-public.conf`。仅公开网站的 80、443 端口，不开放 8001、8080；现有 `/admin`、`/api/`、`/documents/` 转发规则继续复用。
- Let's Encrypt 证书同时覆盖两个域名，路径为 `/etc/letsencrypt/live/yoniqtech.com/fullchain.pem` 和 `privkey.pem`；首次签发的到期日期为 2027-01-19，后续以实际证书为准。不要输出或复制私钥到网站目录。
- 独立证书工具：`/opt/yoniq-certbot/bin/certbot`（初始安装版本 5.8.0）；HTTP 验证目录：`/var/lib/letsencrypt/.well-known/acme-challenge/`，80 端口此路径不能跳转或关闭，以供自动续期。
- 自动续期：`yoniq-certbot-renew.timer` 每日两次检查、随机延迟；调用 `yoniq-certbot-renew.service`，成功续期后检查并重载 Nginx。本地副本位于 `website-admin/deploy/`，服务器文件位于 `/etc/systemd/system/`。已启用开机启动，并通过模拟续期及重载演练。
- 续期检查：`systemctl list-timers yoniq-certbot-renew.timer --no-pager`、`journalctl -u yoniq-certbot-renew.service --no-pager`。手动演练：`/opt/yoniq-certbot/bin/certbot renew --dry-run --no-random-sleep-on-renew --run-deploy-hooks --deploy-hook '/usr/sbin/nginx -t && /usr/bin/systemctl reload nginx'`。
- 上线前备份：`/var/backups/yoniq-docs/before-public-20261021-103942/`，含原 Nginx 配置、受限环境配置、首页与数据库快照；环境配置包含密钥，不要输出内容。
- 已用真实浏览器验证 HTTP 跳转、两个域名的可信 HTTPS、8 个产品、1 份 PDF 的站内查看和下载、原账号登录、安全 Cookie、手机布局和备案链接；原产品、文档和账号数据库记录与上线前一致。
- 2026-10-21 已修复首页导航固定高亮“产品”的问题：根据当前 URL 锚点切换 `active` 和 `aria-current`，支持点击、刷新及浏览器前进后退；根元素增加桌面 126px／手机 91px 的滚动顶部留白，避免固定导航遮挡锚点标题。修改前首页备份：`/var/backups/yoniq-docs/before-navigation-20261021-110302/index.html`。已通过真实浏览器桌面、手机及中英文验证。

