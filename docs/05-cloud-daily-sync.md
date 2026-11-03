# 可选：每天刷新月结余

只需要手机记账时可跳过本页。这个任务读取完整飞书一体账本，把每个月生意的 `SUM(收支)` 写成生活中的一条自动月结余。**不依赖 Google Sheets，也不需要电脑常开。**

## 安装

1. 在自己的 [Google Apps Script](https://script.google.com/) 新建项目，例如“一体账本·每日刷新”。只给自己或可信编辑者访问。
2. 把 `apps-script/Code.gs` 复制到 Code.gs。项目设置中开启显示 `appsscript.json`，用 `apps-script/appsscript.json` 替换清单（时区 Asia/Shanghai、V8）。不要安装 Sheets 模块或更大的权限清单，除非需要备份。
3. 在“项目设置 → 脚本属性”填写：

| 属性 | 值 |
| --- | --- |
| FEISHU_APP_ID | 自己的飞书 App ID |
| FEISHU_APP_SECRET | 自己的飞书 App Secret |
| FEISHU_APP_TOKEN | 自己的 Base 标识 |
| FEISHU_TABLE_ID | v2 一体账本的表标识 |

不需要部署成 Web App，不需要公开 `/exec` 地址。脚本属性不是独立的密钥保险箱：项目编辑者可以读取它，不要公开共享项目或配置截图。

## 先预演，再启用

1. 选 `previewDailySync` → Run，完成 Google 授权。它检查字段、分页和自动汇总标识，日志列出 proposed changes；不修改飞书/Sheets。首次运行会在脚本属性记住目标表，防止后续把旧同步状态用于另一张表。
2. 核对记录数和各月计划金额。零条记录的新表可以预演；非空旧表请先导出备份。任务不修改原始生意或生活流水。
3. 暂停此表已有的月结余同步脚本/定时器，避免多个写入器竞争。手机仍可记账；读写期间发生变化时任务可能中止，稍后重新预演。
4. 新增脚本属性 `CLOUD_WRITES_ENABLED=true`。**默认不写入，只有这一开关明确为 true 才执行。**
5. 手动运行一次 `runDailySync`。日志 `ok:true` 后，去飞书核对派生行，检查 `LAST_RUN_SUCCESS_AT`。
6. 最后运行 `installDailyTrigger`。触发器列表应只有一个本项目的 `runDailySync`：每天北京时间约 03:30，可能前后浮动约 15 分钟。安装器只替换同名处理函数，不删除其他任务。

选择定时任务失败通知并检查执行历史。新交易对应的汇总可能滞后到下一次成功任务；需要立即检查时手动运行一次 `runDailySync`，不要同时开第二个同步器。

## 写入范围与异常

- 只新增或更新“生活 / 生意结余 / 自动联动”的规范月结余行；更新已存在行时只修改 `收支`。
- 精确到分，校验月份与时间，分页读全，检测重复/同名手工行以及执行期间变化。没有金额变化时不写飞书。
- 创建请求结果不确定时留 `PENDING_CREATES` 标记，后续不会盲目再次创建。按[排错说明](04-troubleshooting-faq.md)核实。
- 不自动删除记录、不迁移旧表、不改字段/公式/看板，也不处理其他储蓄项目。
- 任务是按月逐行写入，不是飞书事务；中途失败时已成功的派生行可能已更新，未完成部分留待下次核对。错误不会回滚原始交易。
- 脚本锁只限同一个 Google 项目，不代替其他客户端的锁，也不能承诺绝对无并发窗口。

更换 Base/表/应用时请新建 Apps Script 项目重新预演。不要直接清掉 `PINNED_TARGET` 来混用 `PENDING_CREATES`、备份计数等状态。

不使用时，删掉本项目的 `runDailySync` 触发器并将写入开关设为 false；手机新增交易仍可继续。

官方说明：[定时触发器](https://developers.google.com/apps-script/guides/triggers/installable)、[nearMinute 的时间浮动](https://developers.google.com/apps-script/reference/script/clock-trigger-builder#nearMinute(Integer))、[脚本属性](https://developers.google.com/apps-script/guides/properties)。
