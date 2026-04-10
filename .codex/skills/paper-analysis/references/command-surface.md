# 命令面摘要

稳定对外入口：

```powershell
py -m paper_analysis.cli.main <namespace> <action> [options]
```

当前仅有四个顶层命名空间：

- `conference`
- `arxiv`
- `quality`
- `report`

业务命名空间只有两个：

- `conference`
- `arxiv`

禁止新增 `recommend` 作为独立业务命名空间。

## 意图路由摘要

- “帮我筛某个顶会的论文” -> `conference filter` 或 `conference report`
- “帮我看 arXiv 今日更新 / 订阅结果” -> `arxiv daily-filter` 或 `arxiv report`
- “跑一下本地检查 / 回归” -> `quality local-ci`
- “帮我测一下 SMTP / 发一封测试邮件” -> `quality send-test-email`
- “查看最近的报告” -> `report --source <conference|arxiv>`

如果缺参数，只补问必要字段，不发明新入口。
