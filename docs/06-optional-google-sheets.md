# 可选：Google Sheets 单向备份

**这不是记账的前提。** 不需要独立备份时，仅保留飞书和核心刷新脚本即可。

## 在已运行的每日任务上选装

1. 在自己的 Google 账号新建一个**专用空白备份表**。备份模块会管理同名工作表，不要指向包含重要自建报表的文件。
2. 在已有 Apps Script 项目新增 `SheetsBackup.gs`，粘贴 `apps-script/optional-sheets/SheetsBackup.gs`。
3. 用 `apps-script/optional-sheets/appsscript.json` 替换项目清单。它额外启用 **Sheets v4 高级服务**并申请 Google 表格读写权限；只在同意这项额外访问时安装。默认 GCP 项目通常自动开通对应 API，自定义 GCP 项目按 Google 文档启用。
4. 新增脚本属性 `SPREADSHEET_ID=自己的备份表ID`（地址 `/spreadsheets/d/ID/edit` 中的 ID），再设 `BACKUP_ENABLED=true`。
5. 手动运行 `runDailySync`，完成新增 Google 权限授权。成功后在备份表“说明”查看时间、记录数与快照摘要。之后沿用已有每日任务，**不用另建备份触发器**。

不需要公开分享备份表，也不需要 Web App、Webhook URL 或常开电脑。飞书凭证只放自己的项目，不用把财务数据发给仓库维护者。

## 备份内容

管理的工作表：`明细`、`生意`、`生活`、`自动联动`、`说明`，以及已有明细时保留的 `云端备份_上一份明细`。这几个页签属于镜像区：手动改动会被后续备份覆盖；同名已有页签也会被接管，所以应使用专用文件。

- 流向始终是 **飞书 → Google Sheets**，不把 Sheets 编辑写回飞书。
- 以整数分校验金额；写入采用类型化单元格值，`=...` 开头的备注保持文本。
- 批量写完后读取“明细”并核验摘要，一致才更新 `LAST_BACKUP_SUCCESS_AT`、记录数和摘要。
- 记录数量比上次减少超过 20% 时拒绝覆盖，防止不完整快照冲掉正常备份。预期大幅删除需人工核对后设一次性 `ALLOW_LARGE_SHRINK=true`。
- 仅保留一份上一轮明细，**不是长期历史归档**；长期留存应另行导出。首次备份之前没有旧版本可保留。
- 不合计重复收入：跨账本分析排除 `来源=自动联动`。亏损月的自动结余是负的生活收入，不计为生活消费。

月结余刷新先执行、备份后执行。备份失败时月结余可能已刷新，查看 `LAST_ERROR` 和 `LAST_BACKUP_SUCCESS_AT` 分别判断，不把部分成功当作全部成功。

关闭备份：`BACKUP_ENABLED=false`。如要撤掉 Google 表格权限，再移除 SheetsBackup.gs、恢复核心清单，并在 Google 账号中检查/撤销旧授权；仅关闭开关不等于撤销已授予的权限。

官方参考：[高级服务启用](https://developers.google.com/apps-script/guides/services/advanced)、[Sheets 批量请求](https://developers.google.com/workspace/sheets/api/guides/batch)。
