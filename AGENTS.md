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

## PDF 阅读器适配（2026-10-21）

- `document.html` 使用站内 PDF.js 阅读器，默认“适合页面”，阅读区占窗口剩余高度；手动缩放、翻页、搜索、目录、打印和下载由阅读器提供。
- 当前静态资源为 `网页/vendor/pdfjs-6.4.299-legacy/` 和 `网页/pdf-viewer.css`，部署时须一起同步到 `/var/www/yoniq/`。PDF.js 为 Mozilla 官方 `v6.4.299` 的兼容构建 `pdfjs-6.4.299-legacy-dist.zip`，来源 `https://github.com/mozilla/pdf.js/releases/tag/v6.4.299`；ZIP SHA-256 为 `c894bce53b2f4c3e13141e088c89cc051a1f7118ba4a2c02ec058798ae1303d1`，保留许可证。站点配置在 `document.js`，窄屏覆盖样式在 `pdf-viewer.css`，不修改上游阅读器源码。
- `/etc/nginx/default.d/yoniq-pdfjs.conf` 指定 `.mjs` 和 `.wasm` 的正确 MIME 类型；公网配置显式包含它，内部预览通过原有通配规则包含它。本地副本在 `website-admin/deploy/`，更新配置后需 `nginx -t` 再重载。
- 修改前备份：`/var/backups/yoniq-docs/before-pdfjs-20261021-131639/`，含阅读页三个文件和公网 Nginx 配置。本次没有修改文档数据库或 PDF 原文件。
- 已用浏览器模拟笔记本 125%／150%／200% 系统缩放、手机窄屏及大小屏尺寸往返，验证实际 PDF 纸张四边均在可视区域；翻页、手动缩放、恢复整页和下载通过。用户实际笔记本的最终显示效果仍需由用户确认。
- 同日已用夸克 7.4.0.1015（Chromium 144）复现普通构建的空白故障：`Map.prototype.getOrInsertComputed` 不存在，阅读器初始化中断，尚未发起 PDF 请求。已改用同版本官方 legacy 构建并在夸克验证 39 页文档、翻页、缩放、下载与跨屏适配；后续不能只以新版 Chrome 的结果判断兼容性。修复前页面和 MIME 配置备份：`/var/backups/yoniq-docs/before-pdfjs-compat-20261021-200755/`。服务器旧普通构建暂留供旧缓存入口和回滚使用，本地只保留当前兼容构建。

## 飞书资料站内迁移（2026-11-09）

- 新文档中心：`https://yoniqtech.com/guides.html?doc=selection`，支持文档目录、本页章节、正文关键词搜索和手机菜单。
- 已迁移原官网 8 个飞书入口及正文引用的串口协议手册，共 9 份文档、39 张图片、12 个附件。快速选型原有 3 张嵌入式电子表格另外提取了 91 行数据及合并单元格，不能只依赖飞书 Markdown 导出以免漏表。
- 本地资源：`网页/guides.html`、`网页/guides.css`、`网页/guides.js`、`网页/guides/`；服务器对应 `/var/www/yoniq/`。附件直接由本站提供，PDF 使用现有 legacy PDF.js 站内阅读器。
- 7 个已有产品记录的 `url` 已改为 `/guides.html?doc=<slug>`，`link_type` 仍为 `url`。首页快速选型链接也已改为站内路径；不要通过旧 `catalog.json` 将其覆盖回飞书。
- 原有产品名称、简介、排序、发布状态、两份已发布 PDF 与账号记录保持不变。文档中心最初为静态快照，同日已升级为下面的后台在线编辑；飞书后续修改不会自动同步。
- 原始 Markdown、表格快照、来源清单、生成及部署脚本保存在 `website-admin/migrations/20261109-feishu/`。详见该目录 `README.md`；该目录不上传到公开网站。生成器需要 Node.js 和 markdown-it 15.0.3，网站运行仍无前端构建依赖。
- 迁移前完整备份：`/var/backups/yoniq-docs/before-feishu-migration-20261109-095655/`，包含原站点、SQLite 与原有 PDF 文件。不要覆盖或直接恢复，以免丢失后续后台修改。
- 已校验 65 个部署文件 SHA-256；公网真实浏览器验证 9 份文档、59 个站内资源链接、搜索、章节定位、手机显示、PDF 查看及下载。Nginx 与后台服务持续正常，无需重启。
- 原文存在 I15/I10、48 V 文档正文写 36 V、JP57-40 额定 48 V 与过压保护描述 30 V 等不一致，本次按原资料保留，未擅自改技术参数。

## 在线文档可视化编辑（2026-11-09）

- 管理入口：`https://yoniqtech.com/admin/guides`，原账号登录后点击“在线文档”。现有 9 份文档支持修改标题、目录名称、正文、图片、表格及附件，点击“保存并更新官网”立即生效，阅读 URL 不变。无需再在飞书修改和迁移。
- 编辑器为本地托管 Jodit 4.19.10，许可证在 `website-admin/static/vendor/jodit-4.19.10/LICENSE.txt`。仅编辑页允许内联样式，脚本仍限制为本站；服务端使用 nh3 清理 HTML，生成章节锚点和搜索正文。保存使用版本号防止并行编辑互相覆盖。
- 图片支持 PNG/JPG/GIF/WebP，最大 10 MB；附件支持 PDF/ZIP/STEP/STP/JSON/BIN/HEX，最大 150 MB。PDF 使用原有站内阅读器；未保存引用的新上传文件仅管理员可预览，保存后访客可访问。不自动删除旧文件，避免误伤尚未保存的编辑或其他文档引用。
- 新源码：`website-admin/guides.py`、`import_guides.py`、`test_guides.py`、`templates/guides.html`、`templates/guide_edit.html`、`static/guide-editor.css` 和 `static/guide-editor.js`。依赖新增 `nh3==0.3.7`、`Pillow==13.0.0`。
- 数据库新增 `guides`、`guide_assets`、`guide_asset_refs`、`guide_migrations`。正文及文件索引在 `/var/lib/yoniq-docs/documents.sqlite`，51 个原始图片和附件已复制到 `/var/lib/yoniq-docs/guide-files/`，新上传文件也存此处。备份必须同时包含 SQLite、原 `files/` 与新 `guide-files/`；代码或网站更新不能覆盖这些数据。
- Nginx 的 `/guides/` 已转发后台，保留旧资源 URL；`/admin/guides/` 单独允许 160 MB 请求体。后台列表兼容有无尾部斜杠，避免 Nginx 自动补斜杠造成 404。本地配置在 `website-admin/deploy/nginx-locations.conf`，正式配置仍是 `/etc/nginx/default.d/yoniq-docs.conf`。
- 一次性导入命令：`/opt/yoniq-docs/venv/bin/python /opt/yoniq-docs/import_guides.py --source /var/www/yoniq/guides --data /var/lib/yoniq-docs`。`feishu-20261109` 标记确保重复执行不覆盖后台编辑。静态生成器只保留为初始快照生成工具，不再用于更新线上正文。
- 上线前备份：`/var/backups/yoniq-docs/before-guide-editor-20261109-103650/`，包含原后台、Nginx 路由、静态文档和完整持久化数据。账号、产品、分类、原 PDF 及迁移标记均与备份逐行比较一致。
- 本地及服务器隔离环境通过 36 项后台测试，另验证尾部斜杠修复后的 10 项在线文档测试。真实浏览器检查全部 9 份正文经过编辑器保存后文字、图片、表格、合并单元格、链接及章节 ID 保留；图片/PDF 上传、表格修改、手机阅读通过。公网核对 9 份原文、51 个资源、PDF 阅读器、原账号登录、安全 Cookie 及编辑器加载通过。

## 阅读页章节侧栏（2026-11-09）

- “本页目录”已从正文顶部移到右侧独立侧栏。宽度超过 1100px 时随页面保持可见，长目录可独立滚动；1100px 及以下通过固定顶栏的“本页目录”按钮打开。原左侧文档导航保留，窄屏两个目录面板互斥。
- 阅读时高亮当前章节，支持原有章节 URL、点击跳转和键盘 Escape 关闭；窄屏选择章节后收起面板并将焦点交给标题。标题定位保留顶栏避让。新标题由后台保存后自动进入目录。
- 仅更新 `网页/guides.html`、`guides.css` 和 `guides.js`，缓存版本为 `20261109-outline`，未改文档正文、数据库或附件。部署备份为 `/var/backups/yoniq-docs/before-outline-sidebar-20261109-110027/`。
- 本地资源与线上正文组合预览已通过桌面、长目录、1100/1024/768/760/390/320px 窄屏、手机中英文、面板互斥、Escape 与章节定位验证；三个部署文件 SHA-256 一致。

## 飞书同步应用配置（2026-11-09）

- 用户已选择“继续在飞书编辑，网站一键同步”，并明确授权代为创建应用、配置权限和文档授权。企业自建应用 `YONIQ 官网文档同步` 已创建并发布 `1.0.0`，App ID：`cli_aa7b11412ff8dc0d`。所属组织为南京创凯航空科技有限公司，可用范围仅应用所有者，已开启机器人能力，未开启外部群/外部用户交互。
- 已开通应用身份（`tenant_access_token`）权限：`docx:document:readonly`、`docs:document.media:download`、`sheets:spreadsheet:readonly`、`wiki:wiki:readonly`。未申请消息、文档写入或删除权限。
- `migrations/20261109-feishu/sources.json` 中的 9 份原文档均已通过“添加文档应用”授予该应用“可阅读”权限。知识库原链接仍可通过 `wiki/v2/spaces/get_node` 解析，不要用浏览器重定向后的链接替换原始来源清单。
- App ID 与 App Secret 已直接写入服务器 `/etc/yoniq-feishu.env`，变量为 `YONIQ_FEISHU_APP_ID`、`YONIQ_FEISHU_APP_SECRET`，文件仅 root 可读（0600）。不得输出其内容、复制到静态目录、提交到仓库或写入日志。密钥没有保存在本地项目中。
- 已从正式服务器验证应用身份认证、9 份正文分页读取、全部 6 个嵌入电子表格块的实际单元格读取（其中快速选型 3 个）、图片与 PDF 附件分段下载。协议手册分页读取共 2862 个块。文档正文和官网数据未因本次授权而修改。
- 此节记录最初的飞书端应用配置；同日已完成下节的网站一键同步功能，服务现已加载凭证。

## 飞书一键同步上线（2026-11-09）

- 正式入口：`https://yoniqtech.com/admin/guides`。每份资料提供“去飞书编辑”和“从飞书同步并发布”；在飞书编辑完成后点击同步，成功后立即更新官网。现有 9 份资料已逐份通过正式后台按钮同步成功。关闭浏览器页面不会中断任务，返回列表可查看结果。不是自动定时同步。
- 最初 9 份来源清单在 `website-admin/feishu_sources.json`，同日新增链接导入后，实际来源绑定迁移至下节的 `guide_sources` 表。保留原知识库链接并校验解析后的文档 ID。同步更新标题、正文、搜索文本和文件引用，保留目录名称、分类、排序和阅读 URL；原章节 ID 按标题匹配保留。网站内手工修改会在下次同步时被飞书内容替换，编辑页已有说明。
- 实现：`feishu.py` 负责分页读取、文档块/电子表格转换及素材下载；`feishu_sync.py` 负责任务、附件校验和事务发布；界面为 `templates/guides.html`、`static/guide-sync.js`、`static/guide-sync.css`。新增 `test_feishu.py`。依赖保持不变。
- 为读取 CF-1 的两张画板，另开通应用身份只读权限 `board:whiteboard:node:read`，已实测下载成功。应用仍无文档写入、删除及消息发送权限。系统服务通过 `/etc/systemd/system/yoniq-docs.service.d/feishu.conf` 加载 `/etc/yoniq-feishu.env`；本地 drop-in 副本在 `website-admin/deploy/feishu.conf`。凭证文件保持 root:root 0600，不得打印或上传公开目录。
- 飞书应用身份只能读取最新文档块，不指定正数 `document_revision_id`（否则 HTTP 403）。读取前后核对文档和嵌入表格版本；同步期间飞书被修改、网站被其他编辑保存、素材下载失败或遇到未支持块类型时，整份资料不发布，官网保留原内容。
- 新表 `guide_sync_jobs` 保存同步状态，`guide_sync_history` 保存发布前标题、正文、搜索文本及版本。原素材文件保留；内容相同的重复同步不增加网站版本或重复保存素材。历史恢复需由维护人员针对单份资料处理，同时重建 `guide_asset_refs`、递增网站版本；不要直接恢复整库覆盖后续业务数据。
- 同步线程运行于现有单 Gunicorn worker 内，数据库约束全站同时只运行一份资料。**继续保持 `--workers 1`**；服务重启会将未完成任务标记失败，需要重新点击同步。改为多 worker 前必须调整任务恢复机制，不能直接增加 worker 数。
- 同步前完整备份：`/var/backups/yoniq-docs/before-feishu-sync-20261109-200114/`，包含后台源码、SQLite、PDF、全部文档素材及受限配置。原账号、8 个产品、6 个分类、2 份 PDF、迁移标记逐行比对不变，51 个原素材校验值不变。新增两张画板后共 53 个素材（41 张图片、12 个附件）；补齐 3 份驱动器资料中的通信代码表。
- 本地和服务器均通过 49 项后台测试；服务器隔离副本完成全部 9 份真实同步并逐项比对原文文字无遗漏。正式浏览器通过 9 个同步按钮、关闭页面后继续运行、53 个资源分段下载、47 张表格、搜索、安全 Cookie、手机布局及章节侧栏/旧锚点验证。快速选型表格仍为 91 行，串口协议 41 张表格共 447 行。

## 粘贴飞书链接导入新资料（2026-11-09）

- `/admin/guides` 顶部新增“从飞书导入新资料”：粘贴链接、选择分类（默认“通用资料”）、点击“一键导入并发布”。自动读取标题、正文、图片和附件，完成后出现在文档中心，并提供后续同步按钮。新增资料不会自动创建首页产品卡片；需要时在现有“产品管理”中填写其本站阅读链接。
- 只接受 HTTPS 的 `*.feishu.cn/docx/<token>` 或 `/wiki/<token>` 文档链接，去掉复制链接带的查询参数和章节片段。拒绝其他域名、用户名密码、端口和不支持的页面类型；服务只请求固定飞书 API，不直接抓取用户输入的地址。
- 每份新文档需在飞书“…”→“添加文档应用”中允许“YONIQ 官网文档同步”应用“可阅读”。不新增应用写入权限。无权限时明确提示授权步骤；知识库中的表格、文件夹等非文档页面不能直接作为文档导入。
- 新表 `guide_sources(slug,url,document_id)` 保存绑定，文档 ID 和来源 URL 均唯一；启动时只补入现有 9 份初始来源，不覆盖已有绑定。以后新增来源使用后台，不能仅修改 `feishu_sources.json`。普通链接和知识库别名解析为相同文档 ID 时会拦截重复，并提供已有条目的链接。
- `guides` 新增 `published`，旧资料默认 1，导入中为 0。新记录使用 `feishu-<随机标识>` 的稳定阅读地址；内容和文件校验完成后才在事务中改为 1。未完成资料不进入公开目录，正文及编辑/上传入口返回 404；后台保留状态和“重新导入并发布”按钮。导入与同步共用原单任务锁和重启处理。
- 来源映射及内部文档链接转换改为从数据库读取，支持新导入文档后续同步；新分类条目插入到现有同分类末尾，保持公开目录分组。原有编辑页、阅读器、章节侧栏继续复用。
- 部署前完整备份：`/var/backups/yoniq-docs/before-feishu-import-20261109-201933/`。原有 9 份正文及版本、53 个素材索引、引用关系、历史备份、PDF、产品和账号逐行核对不变，未向官网添加测试资料。服务凭证及 systemd 配置未改动。
- 本地与服务器均通过 56 项测试，覆盖新资料导入、失败隐藏及重试、重复链接/知识库别名、权限、URL 校验、并发任务、重启及动态来源链接。服务器隔离数据通过真实 docx 和 wiki 首次导入及素材下载；浏览器通过粘贴导入到阅读页、分类选择、错误提示和 1440/900/390/320px 布局。正式后台通过重复知识库链接拦截及既有资料重复同步无变更验证。

## AXIS 三系列与文档树（2026-11-09）

- 用户指定 AXIS 下设 JP（行星关节执行器）、JS（应变波关节执行器）、JC（摆线关节执行器）。一级产品分类仍为原 6 类。固定系列定义在 `website-admin/taxonomy.py`；公开 `/api/axis-series` 提供中英文名称。没有新增虚构产品、参数或资料。
- `products` 和 `guides` 各新增 `series TEXT NOT NULL DEFAULT ''`。首次增加字段时按 AXIS 下已有型号前缀归类，之后重启不覆盖后台选择。当前 3 款 JP 产品及 2 份 JP 在线文档已归入 JP，原产品 ID、名称、链接、排序、发布状态及文档正文、标签、阅读 URL 保留。
- 首页 AXIS 使用 JP/JS/JC 三个系列标签切换，支持方向键、Home/End、中英文和手机。产品按所选系列过滤；空系列展示真实空状态。有已发布文档时显示对应系列文档直达入口，未完成导入的资料不会生成公开入口。其他五个产品分组保留。
- `/api/products` 保持原分类和扁平 `products` 列表，新增产品 `series` 字段及分类的系列定义数组（含 `guide_href`）；新页面使用这些字段，不要改为不兼容的嵌套产品列表。
- 文档中心左侧为可展开的分类树，AXIS 下固定显示 JP/JS/JC，自动展开当前资料所在系列。搜索同时匹配系列名称、型号和正文；右侧“本页目录”、原章节锚点与手机菜单仍保留。正文上方显示分类/系列路径。
- 产品后台编辑页新增“AXIS 产品系列”，AXIS 产品保存时必须选择有效系列；移到其他一级分类时清空系列。飞书导入下拉框新增 `YONIQ AXIS / JP`、`/ JS`、`/ JC`；在线文档编辑页可调整“文档分类 / 系列”。保存保留阅读 URL，飞书同步保留分类和系列。AXIS 通用文档仍允许放在父级。
- 本次过程中用户新建了 `JC7651`，slug 为 `feishu-ca7ddcfe90f64d2d`。已从“通用资料”移到 `YONIQ AXIS / JC` 并递增版本以防旧编辑页覆盖。其原导入任务提示“飞书文档正文为空”，`published=0`，因此只在后台显示，公开文档仍为 9 份。用户补齐飞书正文后可重新导入；不得把空文档或仅有标题的记录公开，也不要宣称 JC7651 已发布。
- 本次修改：`taxonomy.py`、`products.py`、`guides.py`、`feishu_sync.py`、相关后台模板/`admin.js`，以及 `网页/index.html`、`products.js/css`、`guides.html/js/css`。首页产品资源版本 `20261109-axis2`，文档资源版本 `20261109-axis`；后台脚本版本 `axis-20261109`。更新需要同时同步后台与这 6 个站点文件。
- 部署备份：`/var/backups/yoniq-docs/before-axis-series-20261109-204522/`，含更新前后台、6 个站点资源、SQLite、PDF 和全部文档素材。原产品、链接、账号、PDF、来源绑定、素材、历史正文均逐项比对保留；JC7651 仅调整归类及版本，未修改正文。
- 本地及服务器隔离环境通过 59 项测试。真实资料副本验证新 JS 产品显示、新 JS 文档导入、JC 归类调整及自动展开；正式浏览器验证 3 个系列、8 个原产品、9 份公开资料、空文档隐藏、系列文档直达、搜索、中英文、桌面/手机及后台选项。原章节侧栏与旧锚点回归验证通过。

## 阅读页侧栏左右互换（2026-11-10）

- 按用户要求，“本页目录”位于左侧，“搜索文档”及文档分类树位于右侧。桌面列宽为左 240px／正文自适应／右 280px；DOM 顺序同步调整，显式网格区域避免无章节标题时正文错位。
- 1100px 及以下，本页目录从左侧打开；760px 及以下，文档搜索和分类菜单从右侧打开。手机顶栏按钮顺序为“本页目录／文档目录”，互斥、Escape、焦点与章节跳转逻辑保持不变。
- 仅修改并部署 `网页/guides.html`、`网页/guides.css`，样式版本为 `20261110-sides`，未修改正文、数据库或后台服务。备份：`/var/backups/yoniq-docs/before-sidebar-swap-20261110-143528/`。
- 真实浏览器在本地资源预览及正式站点通过桌面位置、固定侧栏、章节跳转、搜索、长目录、1100/1024/768/760/390/320px 布局、手机菜单及无标题正文验证。两个部署文件 SHA-256 与本地一致。
- 用户反馈仍看到旧版后，核对两个正式域名均返回新版；原 HTML 未设置缓存校验。已在共享 Nginx 路由为 `/guides.html` 增加 `Cache-Control: no-cache`，新访问会重新校验入口；既有打开页面仍需刷新。配置备份 `/var/backups/yoniq-docs/before-guide-cache-20261110-144132/`，本地对应 `website-admin/deploy/nginx-locations.conf`。两个正式域名均经真实浏览器核对响应头与左目录／中正文／右搜索位置；用户此前所见旧版的具体原因仍待其实际地址确认。

## CANopen / EtherCAT 协议手册（2026-11-10）

- 按用户指定，从 `协议文档/YONIQ_AXIS_CANopen_EtherCAT用户手册.docx`（V1.1，2026-10-22）完整导入合订版，阅读入口 `/guides.html?doc=canopen-ethercat`，分类“协议手册”，目录名称“CANopen / EtherCAT 用户手册”。正文 97 个章节、34 张表格、296 行逐字和逐单元格核对一致；原 Word 无图片和公式。
- 提供同目录原版 43 页 PDF 的在线查看和下载，文件进入 `/var/lib/yoniq-docs/guide-files/`，公开地址 `/guides/canopen-ethercat/assets/YONIQ_AXIS_CANopen_EtherCAT.pdf`。此文档没有飞书来源绑定，现有后台可“网站内编辑”。
- 一次性转换、校验和增量导入脚本及快照位于 `website-admin/migrations/20261110-canopen-ethercat/`，详见其 README；迁移标记 `word-canopen-ethercat-20261110` 防止重复覆盖。未修改前端或后台运行代码、依赖，无需重启。
- 导入前备份 `/var/backups/yoniq-docs/before-canopen-ethercat-20261110-145644/` 包含数据库、PDF 与文档素材。原有各表记录逐行核对不变，公开文档由 9 增为 10；未发布的 JC7651 保留原状。真实浏览器已验证正式网页、章节跳转、搜索、390/320px 布局、43 页 PDF 加载、原文件下载哈希和 206 分段读取。

## 阅读页侧栏收起与展开（2026-11-10）

- 顶部固定显示两侧控制按钮，桌面文字为“收起／展开本页目录”和“收起／展开文档目录”。左右可独立隐藏，也可同时隐藏；收起对应网格列后正文利用空出的宽度。隐藏侧栏不再参与键盘焦点顺序，按钮保留正确的 `aria-expanded` 和操作标签。
- 1100px 及以下左侧仍为抽屉，760px 及以下右侧也为抽屉；手机菜单互斥、Escape、点击正文或章节关闭等行为保留。当前页的桌面收起状态在调整窗口大小后保留，重新加载页面默认展开，无新增持久化设置。
- 仅修改 `网页/guides.html`、`guides.css`、`guides.js`，两个资源版本为 `20261110-collapse`。未修改后台和资料数据。部署前备份 `/var/backups/yoniq-docs/before-sidebar-collapse-20261110-150334/`，三个文件线上 SHA-256 与本地一致。
- 本地预览及正式浏览器均通过独立收起、同时隐藏后正文扩展、键盘 Enter/Space、搜索、章节跳转、无章节文档、窗口尺寸往返、中英文和 1680/1440/1101/1100/1024/768/761/760/390/320px 布局检查。

## 飞书式侧栏边缘图标（2026-11-12）

- 用户明确纠正收起展开的呈现方式：已移除顶栏两个文字按钮，将原控制改为左右侧栏外侧上方的小图标。展开时显示朝各自外侧的双箭头，收起时原位置保留目录图标；鼠标悬停及键盘聚焦显示操作提示，保留动态 `aria-label`、`aria-expanded` 与键盘操作。
- 桌面收起后每侧保留 52px 图标空间，正文扩展到剩余区域；长文滚动时图标固定可用。右侧分类树改为独立滚动，避免内容与固定图标或搜索框重叠。手机在原顶栏下方保留 48px 图标行，左右抽屉及章节滚动偏移同步避让。
- 仅更新 `网页/guides.html`、`guides.css`、`guides.js`，资源版本 `20261112-edge`；未修改正文、数据库或后台。备份 `/var/backups/yoniq-docs/before-edge-controls-20261112-173636/`，三个部署文件 SHA-256 与本地一致。
- 本地预览及正式浏览器通过无顶栏文字按钮、图标／提示、独立收起／展开、键盘、搜索、长文滚动、左右侧栏内容滚动、中英文、无标题正文和 1680/1440/1101/1100/1024/768/761/760/390/320px 布局验证。

## 产品卡片扭矩悬停显示（2026-11-12）

- 官网产品卡片默认显示简介；鼠标悬停或键盘聚焦时替换为额定／峰值扭矩，移开后恢复，卡片尺寸不变。无触摸悬停能力的设备保持简介及原链接行为，中英文标签随站点语言切换。
- `products` 新增可选 `rated_torque`、`peak_torque` 文本字段，单位 N·m；`/api/products` 返回这两个字段，后台产品编辑页可填写非负小数或留空。不填写的参数不显示，两项均为空时保留原卡片。
- 按当天官网快速选型资料核对：JP57-08 G1 为 2.5／6，JP57-40 G1 为 7.5／27，JP76-48 G1 为 30／97 N·m（额定／峰值）。一次性初始化脚本位于 `website-admin/migrations/20261112-product-torque/seed_torque.py`，标记 `product-torque-20261112` 防止重复执行覆盖后台修改；后续参数更新使用后台，不修改旧 catalog.json。
- 修改 `website-admin/products.py`、`templates/product_edit.html`、`test_app.py` 及 `网页/index.html`、`products.js`、`products.css`；首页产品资源版本为 `20261112-torque`。后台保持单 worker，数据库其余原字段及各业务表记录逐行核对不变。
- 部署前备份：`/var/backups/yoniq-docs/before-product-torque-20261112-173746/`，包含后台源码、三个网页文件、SQLite 快照、PDF 与文档素材。
- 本地及服务器隔离环境均通过 62 项后台测试；正式浏览器验证三款参数、悬停／移开、卡片尺寸、键盘、中英文、系列切换、1440/1024/800/390/320px 布局及手机点按原链接。五个运行文件的本地与服务器 SHA-256 一致。

## JP76-48 文档与飞书颜色同步（2026-11-12）

- 用户指定的飞书文档 `IYjydbKLZo2EOExugsScgC2AnIf` 已导入为 `feishu-1b80d522b2294be5`，归入 `YONIQ AXIS / JP`，产品 ID 3（JP76-48 G1）已绑定 `/guides.html?doc=feishu-1b80d522b2294be5`，替换原缺失 PDF 入口。13 个章节、1 张图片、31 行表格及 2 个 PDF 附件已验证。导入前备份 `/var/backups/yoniq-docs/before-jp7648-import-20261112-094854/`。
- `feishu.py` 新增电子表格样式读取：调用官方 `sheet_ai/v2/spreadsheets/<token>/tools/invoke_read` 的 `get_cell_ranges`，保留文字色、背景色（包括条件格式结果）、加粗、斜体、下划线／删除线、水平及垂直对齐；原合并关系和格式化显示值保留。按 100 行分批读取并验证实际坐标、完整性和原有版本号；读取失败不发布部分结果。正文的文字颜色与高亮也已接入转换。
- 飞书应用已开通并验证 **应用身份**只读权限 `sheets:spreadsheet:read`，旧 `sheets:spreadsheet:readonly` 继续保留；没有新增文档写入或消息权限。表格字号、字体、列宽、边框以及页面布局仍沿用官网，不是飞书像素级复刻。
- 本次仅重新同步正式站的 JP76-48，版本由 1 升为 2；69 个可见单元格的颜色与对齐逐格核对一致。原文首标题 `JP62-48 G1` 及额定 48V／过压保护 30V 的不一致按来源保留，未修改技术参数。
- 其余 9 份已发布飞书文档在隔离副本完成真实同步检查：快速选型与三份驱动器资料存在电子表格颜色遗漏；CF-1、STUDIO、串口协议手册存在文字颜色／高亮遗漏；JP57-08、JP57-40 无本次颜色差异。以上文档正式正文和版本均未变，后续从后台同步会使用新转换逻辑。空白未发布 JC7651 和无飞书来源的 CANopen / EtherCAT 合订手册未同步。
- 仅部署 `website-admin/feishu.py`、`test_feishu.py`，后台仍为单 worker。部署前完整备份 `/var/backups/yoniq-docs/before-feishu-colors-20261112-113830/` 包含后台源码、SQLite、PDF 和文档素材。其余业务表、原文档、原素材哈希逐项核对不变。
- 本地及服务器均通过 69 项测试；隔离副本全部 10 份已发布飞书来源同步成功、搜索正文一致；正式浏览器通过 31 行／69 个可见单元格配色、产品链接、无脚本错误及 1440/1024/390/320px 布局验证。两个部署文件 SHA-256 与本地一致。

## 其余飞书文档颜色补齐（2026-11-12）

- 用户随后明确授权重新同步其余有颜色遗漏的文档。已通过正式后台同步接口逐份发布 `selection`、`db1-v24`、`db1-v36`、`db1-v48`、`cf-1`、`studio`、`serial-protocol`，共 7 份；除 STUDIO 版本由 3 升为 4，其余由 2 升为 3。每份发布前正文均保存至原同步历史表。
- 同步前完整备份 `/var/backups/yoniq-docs/before-other-guide-colors-20261112-120301/` 包含 SQLite、原 PDF 与全部文档素材；同目录 `sync-results.json`、`verification.json` 保存任务结果和校验摘要。
- 逐份核对仅增加颜色及相应表格格式，搜索正文、章节锚点、链接、图片、表格结构与合并关系保持一致；其他文档（包括已恢复配色的 JP76-48）、产品、账号等业务记录保持不变，59 个原文件 SHA-256 一致。未改代码、配置或重启服务。
- 正式浏览器验证 7 份文档的配色、加粗、对齐及 1440/390/320px 布局，无脚本错误；快速选型仍为 3 表／91 行、203 个带样式单元格，三份驱动器各 7 行／14 个带样式单元格；串口协议仍为 41 表／447 行。7 份公开正文与数据库一致，37 个关联图片和附件的公开分段读取通过。字体、字号、列宽、边框和页面布局仍沿用官网样式。

## 首页导航随滚动高亮（2026-11-12）

- 首页导航根据实际滚动位置切换 `active` 和 `aria-current`，保留原生锚点跳转；滚动本身不修改 URL 或新增历史记录。使用固定导航高度与原滚动留白判断区域，滚动事件通过 `requestAnimationFrame` 合并；窗口变化、历史恢复及动态产品／资料加载改变高度时重新计算。
- 页尾短区域的定位点限制在实际可滚动范围内。“技术支持”和“商务联系”现处同一行，手动滚到页底默认高亮商务联系；点击技术支持则在两者共享的页底位置保留该项高亮，离开该区域后恢复按实际位置切换。
- 仅部署 `网页/index.html`，未修改后台、业务数据或 Nginx 配置，无需重启服务。部署前首页备份：`/var/backups/yoniq-docs/before-scroll-navigation-20261112-201700/index.html`。
- 真实浏览器在本地资源预览及正式网站通过 1440/1024/800/390/320px、中英文、上下滚动、鼠标滚轮、导航点击、前进后退及页尾定位检查，无脚本错误。浏览器历史在页面 CSS zoom 下可能恢复至与锚点不同的位置，高亮以实际视区为准。两个正式域名的首页响应、服务器文件及本地文件 SHA-256 一致，Nginx 与后台服务正常。

## 飞书字体、字号与版式同步（2026-11-12）

- 用户要求继续同步字体、字号、列宽并尽量保留原排版。`feishu.py` 通过 `get_sheet_structure` 读取嵌入电子表格的列宽及行高，完整校验范围和版本；`get_cell_ranges` 的字体和字号一起转换。当前真实来源的 11／12 号字经飞书 Canvas 核对对应 14／16 CSS px，宋体映射到 SimSun 并提供宋体系统回退，不下载或公开字体文件。
- 原生文档表格保留 `table.property.column_width`，输出 `colgroup` 与固定列宽；电子表格保留行高、合并关系、配色及对齐。行高作为最低高度，长文字可增高避免截断；宽表在桌面及手机都通过表格区域横向滚动，不压缩原列宽。
- 新增 `.feishu-document` 范围内的飞书正文与标题字号、行距、段距；保留 `grid_column.width_ratio` 分栏，手机改为纵向排列。空分栏仍不能使空文档通过发布校验。`guides.py` 允许清理后的字体、字号、列组及指定样式类；非飞书 Word 手册不应用这些版式覆盖。
- 修改并部署 `website-admin/feishu.py`、`guides.py`、`test_feishu.py` 及 `网页/guides.css`、`guides.html`；CSS 缓存版本为 `20261112-typography`。后台继续单 worker，没有新增权限、依赖或数据库字段。
- 通过正式后台接口重新发布全部 10 份已发布飞书文档：快速选型、三份驱动器、CF-1、串口协议版本为 4，STUDIO 为 5，JP57-08、JP57-40、JP76-48 为 3。保留分类、系列、目录名、顺序、阅读 URL、章节锚点、附件、正文和原技术参数。快速选型搜索正文仅在下载链接与表格间新增空格，其余文字一致。空白 JC7651 仍未发布，CANopen / EtherCAT Word 合订手册未修改。
- 发布前完整备份 `/var/backups/yoniq-docs/before-feishu-typography-20261112-122435/` 包含后台、相关静态文件、SQLite、PDF 和文档素材；同目录保存 `sync-results.json`、`verification.json`、`public-assets.json` 及浏览器检查结果。原账号、产品、文档来源、素材等业务记录一致，59 个原文件哈希一致。
- 本地和服务器隔离环境均通过 74 项测试。正式浏览器在 1440／390／320px 下验证全部 10 份文档、48 张表格的列宽、314 个电子表格可见单元格字号和字体、两处分栏，无页面横向溢出及脚本错误；56 个关联图片和附件公开分段读取均返回 206。部署文件 SHA-256 与本地一致。
- 还原边界：终端未安装的字体使用系统回退；部分飞书原生表格底色和边框未由当前 Docx API 返回（例如串口协议表格单元格对象为空），本功能不声称像素级复制这些样式。电子表格配色以及接口返回的正文文字颜色／高亮已保留。

## 设备协议手册统一入口（2026-11-13）

- JP57-08、JP57-40、JP76-48 三份资料中的 CANopen / EtherCAT PDF 查看和下载入口已替换为 `/guides.html?doc=canopen-ethercat`，以后在后台修改该在线手册正文即可。串口协议、统一手册自身的原版 PDF 和其他内容保持不变。
- `website-admin/feishu.py` 对两种已核实名称 `YONIQ_AXIS_CANopen_EtherCAT用户手册.pdf`、`YONIQ_AXIS_CANopen_EtherCAT_User_Manual_V2.pdf` 转为统一页面链接，后续飞书同步不再恢复这些设备 PDF 入口；不匹配其他名称或附件。新增测试在 `test_feishu.py`。
- 一次性事务迁移及说明：`website-admin/migrations/20261113-protocol-links/`。三份设备资料版本分别变为 4、4、5；重建引用但保留原附件文件，不修改协议正文、技术参数或飞书源文档。
- 部署前备份：`/var/backups/yoniq-docs/before-protocol-links-20261113-105422/`，含 SQLite、PDF、文档素材及修改前源码。76 项后台测试、隔离迁移重复执行、正式数据及文件哈希比对、两域名入口和 1440／390px 浏览器点击验证通过。后台仍为单 worker。

## 串口协议统一在线入口（2026-11-13）

- 按用户后续要求，JP57-08、JP57-40、JP76-48 各自仅保留已有的 `/guides.html?doc=serial-protocol` 在线链接，移除串口协议 PDF 查看和下载入口。CANopen 链接及两个协议主页面正文保持不变。
- `feishu.py` 对 `串口协议手册.pdf` 附件改用在线链接；若源文档已有对应普通链接或文档引用则省略附件入口，避免重复，与链接顺序无关。其他附件正常处理。原文件保留，后续只需维护统一串口页面。
- 迁移及说明位于 `website-admin/migrations/20261113-serial-links/`；三份设备资料版本分别变为 5、5、6。备份：`/var/backups/yoniq-docs/before-serial-links-20261113-110005/`，含 SQLite、原 PDF、文档素材、修改前源码及变更记录。
- 77 项后台测试、隔离迁移重复执行、正式数据与原文件哈希比对、两域名内容和 1440／390px 浏览器跳转通过；部署源码与本地一致，服务仍为单 worker。

## 飞书空白协议小节自动补链接（2026-11-13）

- 按用户提供的模板，飞书使用“协议手册”父标题，下设“CANOPEN协议”“串口协议”等子标题并留空，首次导入及后续同步会自动在对应子标题下补上统一在线手册链接，无需放 PDF 或手动填写网址。
- `feishu.py` 的 `fill_protocol_placeholders` 识别“CANopen协议”“EtherCAT协议”“CANopen / EtherCAT协议”（大小写、空格和全角斜杠兼容）及“串口协议”；父标题允许原有数字编号。必须使用飞书标题样式并保持父子层级。只有空白或空行段落才补充，已有正文、链接、图片、表格或下级内容不覆盖；“协议手册”之外及两个协议主页面不应用本规则。
- 链接在 HTML 清理、搜索文本和发布事务之前生成；重复同步不增加链接或无意义版本。原附件名称转换规则继续有效。只部署 `feishu.py`、`test_feishu.py`，未同步或修改任何现有资料正文、版本、业务记录和原文件。
- 备份：`/var/backups/yoniq-docs/before-protocol-placeholders-20261113-110901/`，含原源码、SQLite 和全部文档文件。81 项后台测试覆盖导入、重复同步、标题变体、非空内容及范围；截图同结构预览在 1440／390px 浏览器通过链接位置和真实跳转。上线后两域名 10 个页面检查、全库记录与文件哈希比对、部署源码哈希核对通过，后台仍为单 worker。
