# 可选 GitHub Actions

离线检查已经可以在本地运行，无需仓库密钥或真实账本。

`github-actions.yml.example` 是相同检查的 GitHub Actions 配置。当前发布凭证缺少 `workflow` 权限，未能自动创建工作流；这不影响快捷指令或云端 Apps Script 运行。

仓库管理员如果需要自动运行测试，可在 GitHub 界面将其保存为 `.github/workflows/checks.yml`，或使用具备相应权限的凭证提交。配置只需要 `contents: read`，不使用飞书或 Google 密钥。
