# 飞书一体账本 + iPhone 截图记账

[English](README.en.md) · [MIT](LICENSE)

付款后运行快捷指令：**截图 → 本机 OCR → 修改金额 → 选择收支和分类 → 写入自己的飞书表格**。

这是通用模板，适合日常开销、自由职业、副业和小生意。没有作者的应用凭证、账本地址或专用服务器依赖。使用者需要自己的飞书账号、自建应用和 iPhone；本版面向中国版飞书，默认人民币、北京时间。国际版 Lark 需要另行适配域名和授权。

## 先选需要的功能

| 功能 | 是否必须 | 运行位置 |
| --- | --- | --- |
| 截图识别、金额修改、分类、写入飞书 | 必须 | iPhone + 飞书 |
| 生意月净结余自动计入生活账本 | 可选 | 自己的 Google Apps Script，每天一次 |
| Google Sheets 单向备份 | **可选，默认关闭** | 单独安装备份模块后，使用同一个每日任务 |

不使用 Google 也能直接记账。飞书的收入、支出和月份由公式计算；**跨账本月结余行需要另外配置刷新任务，不是公式自动生成**。也可以只看原始交易，不启用联动。

## v2 的变化

- 一张“一体账本”，用 `账本=生意/生活` 区分，两边各有收入、支出入口。
- 识别到的金额先确认，可修改；没有候选时可手动输入，正负号由收支入口决定。
- 常用支出选一次分类即可保存；设备、其他支出和收入填写具体事件，不再重复选择分类。
- 使用原生 JSON 字典发送，备注里的引号、换行不再破坏请求；日期使用毫秒数字。
- 只有飞书返回 `code=0` 和 `record_id` 才显示成功。网络中断或结果不确定时先查表，不自动重发创建请求。
- 月结余任务独立于手机触发，按整数分计算；重复自动行、分页异常、读写期间数据变化会中止，不删除原始流水。
- Sheets 单独选装，默认脚本不申请 Google 表格权限。

## 从零开始

### 1. 创建自己的飞书应用和表格

按[应用授权指南](docs/02-feishu-open-app-setup.md)创建自建应用，并给它目标多维表格的编辑权限。

然后按[建表指南](docs/01-feishu-bitable-setup.md)创建一张含 9 个字段的一体账本。会运行 Node.js 的用户也可用初始化工具（Node.js 18+）：

```bash
node tools/init-bitable.mjs --dry-run
# 在自己的终端配置 FEISHU_APP_ID、FEISHU_APP_SECRET、FEISHU_APP_TOKEN 后：
node tools/init-bitable.mjs --apply
```

默认不联网、不写数据；`--apply` 才新建表。不修改已有同名表，也不默认插入示例流水。首次测试建议使用空白测试 Base。

### 2. 导入通用快捷指令

下载 [飞书一体账本-通用版.shortcut](shortcuts/飞书一体账本-通用版.shortcut)，发送到 iPhone 并用“快捷指令”打开。GitHub 文件预览页请点击下载原始文件。

导入时填写自己的三项配置：

1. 飞书应用 `App ID`
2. 飞书应用 `App Secret`
3. 一体账本记录 API 地址：`https://open.feishu.cn/open-apis/bitable/v1/apps/你的APP_TOKEN/tables/你的TABLE_ID/records`

第一次用小额测试记录检查四个入口、识别后改金额、失败提示。确认无误后，按[手机设置指南](docs/03-iphone-shortcut-guide.md)绑定“轻点背面”。

> 仓库同时提供[未签名 XML 源码](shortcuts/Feishu-Unified-Ledger-Unsigned.shortcut)和[签名回执](shortcuts/signing-receipt.json)。签名表示可供 Apple 快捷指令导入，不代表已经在你的 iOS 版本和飞书应用上测试。这个通用构建尚需使用者完成真机验收。

### 3. 可选：每天刷新一次月结余

需要把生意净收入计入生活账本时，按[云端任务指南](docs/05-cloud-daily-sync.md)配置 Apps Script。默认每天北京时间约 03:30（前后约 15 分钟浮动），无需个人电脑开机，也不用发布公开 Web App。

### 4. 可选：Google Sheets 备份

需要另存一份流水时，再按[Sheets 备份指南](docs/06-optional-google-sheets.md)添加模块。不配置这一项不会影响手机记账或月结余刷新。

## 统计口径

`收支`：收入为正，支出为负。自动月结余是内部流转，不是又赚了一笔钱。

- 看生意：筛选 `账本=生意`。
- 看生活可支配结余：筛选 `账本=生活`，包含自动月结余；它在下次成功刷新前可能滞后。
- 看全部真实流水、总收入/总支出或交易笔数：**排除 `来源=自动联动`**，避免同时计算生意明细和汇总行。
- 生意某月亏损时，自动行是负的“生活收入”，不当作一笔生活消费。

详见[字段与看板设置](docs/01-feishu-bitable-setup.md)。

## 自定义分类与源码构建

Python 3.10+，无需第三方依赖：

```bash
python3 tools/build-shortcut.py
python3 -m unittest discover -s tests -p 'test_*.py'
node tests/cloud.cjs
node tests/init.mjs
python3 tools/check-public.py
```

复制 `config/shortcut-config.example.json` 为 `config/shortcut-config.local.json`，修改分类和 `ask_note`。自定义输出放到忽略的私有目录：

```bash
python3 tools/build-shortcut.py --config config/shortcut-config.local.json --output shortcuts/private/MyLedger.shortcut
```

默认输出可复现的占位符模板。Mac 可用 `bash tools/sign-shortcut.sh` 签名公开模板，或对自定义构建加 `--sign` 在本机签名；构建器不把密钥发送到远程签名服务。

## 升级与排错

- 旧“两张表”用户先读[迁移指南](docs/07-migration-v1-to-v2.md)，不要把新快捷指令直接接到旧结构上。
- [常见问题](docs/04-troubleshooting-faq.md)：权限、日期、参数丢失、重复提交、授权弹窗和待核实创建。
- [变更记录](CHANGELOG.md)；旧版参考文档在 `legacy/v1/`，不是当前安装入口。
- 凭证只放自己的手机、私有环境变量或 Apps Script 脚本属性；项目编辑者可查看脚本属性，分享项目会扩大密钥访问范围。不要公开配置后的快捷指令或账本快照。

本仓库包含离线动作图测试、云端故障模拟和建表模拟；这些检查不替代 iPhone 真机运行和新建飞书应用的部署验收。不会因为运行测试而连接真实账本。

## 致谢

感谢 iOS 快捷指令与中文效率工具社区对本机 OCR 记账工作流的探索。
