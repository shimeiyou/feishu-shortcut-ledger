# 第二步：创建并授权自己的飞书应用

1. 在[飞书开放平台](https://open.feishu.cn/app)创建企业自建应用。每个人使用自己的应用，不共用作者的服务。
2. 在“凭证与基础信息”取得 App ID 和 App Secret，私下保存，不发到 Issues、配置示例或公开截图。
3. 开通目标多维表格所需的读写权限（例如 `bitable:app`），发布应用版本，使新增权限生效。界面名称可能随飞书更新，按实际权限说明操作。
4. 回到自己的多维表格，在“更多 / 添加文档应用”中添加该应用并赋予编辑权限。API 权限与文档资源授权都要完成。
5. 取得 Base 的 app_token 与一体账本的 table_id，组装唯一的记录 API 地址：

```text
https://open.feishu.cn/open-apis/bitable/v1/apps/YOUR_BITABLE_APP_TOKEN/tables/YOUR_TABLE_ID/records
```

权限以飞书[多维表格接入指南](https://open.feishu.cn/document/server-docs/docs/bitable-v1/bitable-overview)为准。如果组织管理员限制自建应用或资源授权，需要管理员协助；模板不能绕过组织权限。

先用测试表检查能读取字段和写入小额测试记录，再接到正式账本。不要把多维表格公开为“任何人可编辑”来解决应用权限问题。
