# CANopen / EtherCAT 手册导入

来源为项目 `协议文档/YONIQ_AXIS_CANopen_EtherCAT用户手册.docx`，V1.1，2026-10-22；原 PDF 为同目录同名文件。按合订版完整导入，不拆分共用章节，不改技术参数。

- 阅读入口：`https://yoniqtech.com/guides.html?doc=canopen-ethercat`。
- 分类：协议手册；目录名称：CANopen / EtherCAT 用户手册。
- 正文包含 97 个章节标题、34 张表格、296 行；Word 无图片和公式。纸面目录页码由网站章节侧栏代替，原封面标题由网站标题展示。
- 原版 PDF 共 43 页，通过现有 PDF.js 阅读器查看，并提供下载。PDF 文件位于后台持久化素材目录，由 `guide_assets`、`guide_asset_refs` 授权公开读取。
- 此资料从 Word 导入，没有飞书来源绑定；可在现有后台“网站内编辑”修改，不会显示飞书同步按钮。

`convert.cjs` 使用临时工具目录的 mammoth 1.11.0 生成 `content.html` 并复制原 PDF，网站没有新增运行依赖。`verify_source.py` 使用标准库对照 Word 的全部正文、章节和每个表格单元格，结果记录在 `validation.json`。

`import_manual.py --data <数据目录>` 使用现有网站虚拟环境及 `PYTHONPATH=/opt/yoniq-docs` 执行，直接进行增量事务导入，不初始化应用，不干预同步任务。重复执行通过 `word-canopen-ethercat-20261110` 标记跳过；已存在同名 slug 时拒绝覆盖。先在隔离数据库验证，再备份正式数据库与全部资料文件后执行。

正式备份：`/var/backups/yoniq-docs/before-canopen-ethercat-20261110-145644/`。原有各表记录逐行核对不变，新增一个公开文档、一个 PDF 素材及其引用和迁移标记。公开资料由 9 份增加为 10 份；JC7651 仍保持原来的未发布状态。

验证：源文逐字和逐单元格一致；清理后的正文与转换结果一致；隔离导入及重复执行、SQLite 完整性和外键检查通过；正式浏览器检查 97 个章节、34 张表格、296 行、搜索和 390/320px 手机布局通过；PDF.js 加载 43 页成功，下载 SHA-256 与原文件一致，分段请求返回 206。

本目录为迁移记录，不应整目录上传到公开网站。后续网站编辑不会写回这里的初始快照，不能重新转换后强行覆盖数据库。
