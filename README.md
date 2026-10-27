# 从飞书多维表格到 iPhone 快捷指令自动记账 (feishu-shortcut-ledger)

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Platform: iOS Shortcuts + Feishu Bitable](https://img.shields.io/badge/Platform-iOS%20Shortcuts%20%2B%20Feishu%20Bitable-00D6B9)](docs/03-iphone-shortcut-guide.md)

**[English Documentation (README.en.md)](README.en.md)**

一套**零第三方中转、零服务器成本、支持「日常消费 + 副业/项目」双账本**的飞书多维表格（Bitable）+ iPhone 快捷指令（Shortcuts）自动记账开源方案与零基础保姆级教程。

付款完成后，**轻轻敲击两下 iPhone 背面** → 自动截屏并调用 iOS 本地 OCR 提取金额 → 点选账本与分类 → 直连飞书开放平台官方 `bitable/v1` REST API 秒级入表 → 飞书多维表格通过 **3 个自动公式列** 与 **8 大可视化仪表盘组件** 实时汇总总收入、总支出、净结余与月度趋势。

---

## 核心特性

1. **零第三方中转，100% 隐私安全**：
   - iOS 原生离线图文识别（OCR）在手机本地提取金额，截图用完即焚、不存相册、不上传外部图床。
   - 快捷指令直连你自己的飞书开放平台企业自建应用接口（`open.feishu.cn/open-apis/bitable/v1`），不经过任何第三方闭源 Webhook 转发服务。
2. **「单列有符号收支 + 3 公式列派生 + 8 看板组件」极简架构**：
   - 快捷指令端只需写入带正负号的 **`收支`** 数字列（**正数表示收入**如 `500`，**负数表示支出**如 `-35.5`）及 `事件`、`标签`、`分类`。
   - 多维表格内部由 **3 个公式列**（`收入`、`支出`、`月份`）自动完成正负拆分与月份归档，天然支撑 8 大仪表盘图表。
3. **支持「日常消费账本 + 副业/项目账本」双账本独立核算与按月净结余自动联动（方案 A）**：
   - 顶层四选一极速菜单：**副业项目收入 / 副业项目支出 / 日常消费支出 / 日常其他收入**，个人生活开销与副业项目收支清晰隔离。
   - **按月净结余自动联动**：每次往副业/生意账本记账后，快捷指令（或同步脚本 `tools/sync-business-to-life.mjs`）会自动汇总当月副业账本全部记录的 `SUM(收支)`，并以 `"YYYY/MM 生意净结余（自动联动）"`（`标签="生意结余"`）幂等更新（`PUT`/`POST`）到日常消费账本，配合升级公式让日常账本既能独立看日常开销，又能直接算出「副业净收入 - 日常支出 = 真实可支配净结余」。
4. **提供一键初始化脚本与可编程 `.shortcut` 编译器**：
   - 提供 `init-feishu-ledger.sh`（及 `tools/init-lark-cli.sh`）与零依赖 Node.js 脚本 `tools/init-bitable.mjs`，30 秒自动建好数据表与公式列。
   - 提供 `tools/build-shortcut.py`，修改 JSON 配置文件即可一键编译生成你专属分类的 `.shortcut` 快捷指令文件。

---

## 仓库目录结构

```text
feishu-shortcut-ledger/
├── README.md                            # 零基础保姆级中文主教程（本文档）
├── README.en.md                         # English step-by-step tutorial
├── LICENSE                              # MIT 开源许可证
├── init-feishu-ledger.sh                # 飞书官方 CLI (lark-cli base) 一键初始化表结构、公式列与 8 大看板脚本
├── config/
│   ├── shortcut-config.example.json     # 快捷指令通用分类与 API 占位符配置文件
│   └── sample-records.json              # 通用测试流水数据（用于一键体验仪表盘图表效果）
├── docs/
│   ├── 01-feishu-bitable-setup.md       # 第一步：创建多维表格、3 个公式列与 8 大仪表盘组件详解
│   ├── 02-feishu-open-app-setup.md      # 第二步：飞书开放平台自建应用、权限开通与「添加文档应用」授权
│   ├── 03-iphone-shortcut-guide.md      # 第三步：iPhone 快捷指令导入、手动搭建拆解与「轻点背面」绑定
│   └── 04-troubleshooting-faq.md        # 第四步：常见错误码（91403 / 99991663 / 1254045）排查手册
├── shortcuts/
│   ├── 飞书双账本自动记账-通用模板.shortcut      # 已签名（AEA1）可直接导入 iPhone 的通用脱敏模板
│   └── Feishu-Dual-Ledger-Unsigned.shortcut   # 未签名 XML Plist 快捷指令源码（透明可审计）
└── tools/
    ├── init-bitable.mjs                 # 纯 Node.js (18+ 零依赖) 飞书 REST API 一键建表与公式初始化脚本
    ├── init-lark-cli.sh                 # lark-cli base 初始化脚本（与根目录 init-feishu-ledger.sh 同步）
    ├── init-feishu-ledger.sh            # 同上，方便在 tools/ 目录下直接调用
    ├── sync-business-to-life.mjs        # 双账本按月净结余幂等联动同步脚本（支持 CLI / 定时任务 / --dry-run）
    └── build-shortcut.py                # 从 JSON 配置生成未签名/已签名 .shortcut 文件的 Python 编译器
```

---

## 10 分钟零基础从 0 到 1 完整上手教程

### 第一步：搭建飞书多维表格（6 个基础字段 + 3 个自动公式列）

你可以选择 **脚本一键自动建表**（完成第二步拿到凭证后运行 `node tools/init-bitable.mjs` 或 `bash init-feishu-ledger.sh`），也可以直接在飞书网页端花 3 分钟手动建表。

#### 1.1 基础写入字段（由 iPhone 快捷指令或 API 写入）

在飞书云文档中新建多维表格，创建两张数据表（**`日常消费账本`** 与 **`副业项目账本`**，若只需单账本则建一张表即可），每张表包含以下基础列：

| 字段名称 | 字段类型 | 格式 / 属性设置 | 说明与示例 |
| :--- | :--- | :--- | :--- |
| **`事件`** | **文本**（主列） | 默认文本 | 消费或收入摘要（如：`工作日午餐`、`地铁通勤`、`项目回款`） |
| **`收支`** | **数字** | 保留 **2 位小数** (`0.00`) | **正数表示收入（如 `500`），负数表示支出（如 `-35.5`）** |
| **`标签`** | **文本** | 默认文本 | 通用分类文本（如：`餐饮`、`交通`、`购物`、`主业收入`、`副业收入`） |
| **`分类`** | **多选 / 单选** | 预设通用分类选项 | 彩色分类标签（日常：`餐饮`/`交通`/`购物`/`居住水电`/`娱乐休闲`/`医疗健康`；副业：`主业收入`/`副业收入`/`项目回款`/`采购成本`/`运营支出`/`设备工具`） |
| **`时间`** | **日期** | 格式 `yyyy/MM/dd`，**勾选「新记录自动填入创建时间」** | 记账日期（也支持 API 传入毫秒时间戳） |
| **`渠道`** | **文本**（可选） | 默认文本 | `微信支付` / `支付宝` / `银行卡` / `现金` |

#### 1.2 三个自动计算公式列（供仪表盘图表聚合统计）

在同一数据表中，新增以下 **3 个「公式（Formula）」类型列**：

| 公式列名 | 精确公式表达式（直接复制粘贴） | 格式设置 | 自动计算逻辑说明 |
| :--- | :--- | :--- | :--- |
| **`收入`** | 日常账本（联动版）：`IF([标签]="生意结余",[收支],IF([收支]>0,[收支],0))`<br>副业账本：`IF([收支]>0,[收支],0)` | 数字 `0.00` | 日常账本中，当 `标签="生意结余"` 时直接计入收入列（兼容某月净结余为负冲减总收入），其余按 `收支 > 0` 提取收入 |
| **`支出`** | 日常账本（联动版）：`IF([标签]="生意结余",0,IF([收支]<0,ABS([收支]),0))`<br>副业账本：`IF([收支]<0,ABS([收支]),0)` | 数字 `0.00` | 日常账本中，`标签="生意结余"` 永远不计入日常支出（记为 `0`），其余按 `收支 < 0` 提取支出绝对值 `ABS([收支])` |
| **`月份`** | `TODATE([时间],"YYYY/MM")`（或 `TEXT([时间],"YYYY/MM")`） | 默认文本 | 将 `时间` 列自动格式化为 `"2026/10"` 年月字符串，用于按月统计 |

#### 1.2.1 双账本按月净结余自动联动行规范（方案 A）

当采用「副业/生意账本 + 日常生活消费账本」双账本模式时，每月副业账本的净结余会自动汇总并幂等同步为日常消费账本中的一行：

- **`事件`**：`"YYYY/MM 生意净结余（自动联动）"`（例如 `"2026/10 生意净结余（自动联动）"`）
- **`收支`**：当月副业/生意账本全部记录的 `SUM(收支)`（保留 2 位小数）
- **`标签`**：`"生意结余"`
- **`分类`**：`["生意结余"]`（绿色选项）
- **`渠道`**：`"生意账本自动同步"`
- **`时间`**：当月 1 日 `12:00:00`（UTC+8）毫秒时间戳
- **幂等更新规则**：按 `标签 == "生意结余"` 且 `事件` 前缀为 `"YYYY/MM"` 匹配 `record_id`，已存在则 `PUT` 更新，不存在则 `POST` 创建。

#### 1.3 配置 8 大仪表盘看板组件（Dashboard Widgets）

点击多维表格左侧栏 **「+ 新建仪表盘」**，按以下清单添加 **8 个可视化图表组件**：

1. **总收入**（统计数字卡）：汇总字段 **`收入`** → **求和 (SUM)**
2. **总支出**（统计数字卡）：汇总字段 **`支出`** → **求和 (SUM)**
3. **净结余**（统计数字卡）：汇总字段 **`收支`** → **求和 (SUM)**（正负自动抵消即为净结余）
4. **记账笔数**（统计数字卡）：统计方式 → **记录总数 (COUNT)**
5. **月度收支三柱对比**（柱状图）：横轴 `X` = **`月份`**，纵轴 `Y` = **`收入`**（求和）/ **`支出`**（求和）/ **`收支`**（求和）
6. **月度横向条形图**（条形图）：维度 = **`月份`**，数值 = **`收入`** / **`支出`**
7. **各分类支出占比**（饼图 / 环形图）：分类维度 = **`标签`**（或 **`分类`**），数值 = **`支出`**（求和）
8. **每月净结余趋势**（折线图）：横轴 `X` = **`月份`**，纵轴 `Y` = **`收支`**（求和）

> 详细图文级说明请阅读：**[docs/01-feishu-bitable-setup.md](docs/01-feishu-bitable-setup.md)**

---

### 第二步：创建飞书自建应用并授权多维表格（3 分钟）

1. 打开 **[飞书开放平台开发者后台](https://open.feishu.cn/app)** → 点击 **「创建企业自建应用」**（名称如：`自动记账助手`）。
2. 在左侧 **「凭证与基础信息」** 复制保存你的 **`App ID`**（`cli_xxxx`）和 **`App Secret`**。
3. 在左侧 **「开发配置 → 权限管理」** 搜索 `bitable:app`，勾选开通 **「查看、评论、编辑和管理多维表格」** 权限。
4. 在左侧 **「添加应用能力」** 添加 **「机器人（Bot）」**，然后进入 **「应用发布 → 版本管理与发布」** 创建版本 `1.0.0` 并确认发布。
5. **【必做关键步】授权文档应用**：
   - 回到你的飞书多维表格页面，点击右上角 **`...`（更多）** → **「添加文档应用」**。
   - 搜索你刚创建的 **`自动记账助手`**，将权限设为 **「可编辑」** 并确定。

#### 使用脚本一键建表（可选，省去手动配字段与公式）

拿到 `App ID`、`App Secret` 以及多维表格地址栏中的 `APP_TOKEN`（形如 `https://xxx.feishu.cn/base/bascnXXXXXX` 中的 `bascnXXXXXX`）后，可直接运行：

```bash
# 方式 1：使用纯 Node.js 18+ REST API 脚本（零外部依赖，支持一键写入示例数据）
FEISHU_APP_ID="YOUR_FEISHU_APP_ID" \
FEISHU_APP_SECRET="YOUR_FEISHU_APP_SECRET" \
FEISHU_APP_TOKEN="YOUR_BITABLE_APP_TOKEN" \
node tools/init-bitable.mjs --insert-sample

# 方式 2：使用飞书官方 lark-cli 脚本
FEISHU_APP_TOKEN="YOUR_BITABLE_APP_TOKEN" bash init-feishu-ledger.sh

# 方式 3：全量/增量按月同步副业账本净结余至日常消费账本（幂等，0 重复写入）
FEISHU_APP_ID="YOUR_FEISHU_APP_ID" \
FEISHU_APP_SECRET="YOUR_FEISHU_APP_SECRET" \
FEISHU_BIZ_APP_TOKEN="YOUR_BITABLE_APP_TOKEN_BIZ" \
FEISHU_BIZ_TABLE_ID="YOUR_TABLE_ID_BIZ" \
FEISHU_LIFE_APP_TOKEN="YOUR_BITABLE_APP_TOKEN_LIFE" \
FEISHU_LIFE_TABLE_ID="YOUR_TABLE_ID_LIFE" \
node tools/sync-business-to-life.mjs
```

> 详细图文级步骤请阅读：**[docs/02-feishu-open-app-setup.md](docs/02-feishu-open-app-setup.md)**

---

### 第三步：导入 iPhone 快捷指令并绑定「轻点背面」

1. 将本仓库中的 **`shortcuts/飞书双账本自动记账-通用模板.shortcut`** 发送到你的 iPhone（隔空投送 AirDrop / iCloud 云盘 / 飞书文件）。
2. 点击打开该文件，在弹出的 4 个导入配置框中填入：
   - **1/4 `App ID`**：你的 `cli_xxxxxxxxxxxxxxxx`
   - **2/4 `App Secret`**：你的 32 位 `App Secret`
   - **3/4 `副业项目账本 API 地址`**：
     `https://open.feishu.cn/open-apis/bitable/v1/apps/你的APP_TOKEN/tables/你的副业表TABLE_ID/records`
   - **4/4 `日常消费账本 API 地址`**：
     `https://open.feishu.cn/open-apis/bitable/v1/apps/你的APP_TOKEN/tables/你的日常表TABLE_ID/records`
3. **绑定轻点背面触发**：
   - 打开 iPhone **「设置」 → 「辅助功能」 → 「触控」 → 「轻点背面」 → 「轻点两下」** → 选择 **`飞书双账本自动记账-通用模板`**。
4. **自定义分类编译（可选）**：
   - 编辑 `config/shortcut-config.example.json` 中的菜单与分类名称，运行：
     ```bash
     python3 tools/build-shortcut.py --config config/shortcut-config.example.json --sign
     ```

> 详细快捷指令动作拆解与排错指南请阅读：
> - **[docs/03-iphone-shortcut-guide.md](docs/03-iphone-shortcut-guide.md)**
> - **[docs/04-troubleshooting-faq.md](docs/04-troubleshooting-faq.md)**

---

## 致谢 (Acknowledgments)

利用 iOS 快捷指令本地截屏 OCR 结合飞书多维表格实现移动端快速记账的自动化思路，受到中文效率工具社区（如少数派 SSPai 及 iOS 快捷指令创作者群体）相关探索与分享的启发，特此向社区创作者致谢。

---

## 开源许可 (License)

本项目基于 **[MIT License](LICENSE)** 开源，欢迎自由使用、修改与二次分发。
