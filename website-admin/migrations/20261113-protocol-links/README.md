# 设备协议 PDF 入口统一为在线手册

2026-11-13 将 JP57-08、JP57-40、JP76-48 三份设备资料中的 CANopen / EtherCAT PDF 查看和下载入口替换为 `/guides.html?doc=canopen-ethercat`。串口协议和其他内容保留。

`replace_links.py` 在事务中检查目标已发布、没有同步任务运行，按素材索引识别已核实的两种附件名称，只替换对应链接对，更新搜索文本、素材引用及版本号。重复执行不会再次修改。运行前必须备份 SQLite、`files/`、`guide-files/`；脚本参数为数据库路径，需使用后台虚拟环境。

`feishu.py` 对 `YONIQ_AXIS_CANopen_EtherCAT用户手册.pdf` 和 `YONIQ_AXIS_CANopen_EtherCAT_User_Manual_V2.pdf` 输出相同在线手册链接，不再下载设备中的这两类副本。仅匹配这两个已核实名称；其他附件正常处理，协议主页面自身的 PDF 保留。后续只需在网站后台修改协议主页面正文。

正式备份：`/var/backups/yoniq-docs/before-protocol-links-20261113-105422/`，含数据库、全部原文件和修改前源码；`changes.json` 记录版本变化。JP57-08／JP57-40 由 3 升至 4，JP76-48 由 4 升至 5。不要整库恢复覆盖后续编辑。

验证：76 项后台测试通过；正式数据库隔离快照验证迁移及重复执行；正式数据核对仅目标三份正文、搜索文本、版本及素材引用改变，其余记录和原文件哈希不变。两个域名公开内容检查及 1440／390px 真实浏览器点击跳转通过。运行中的后台仍为单 worker。
