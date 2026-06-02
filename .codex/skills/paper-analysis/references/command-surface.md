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
- “审一下 arXiv 日更有没有误推荐或漏推荐” -> 查看 `arxiv report` 默认写出的审阅产物
- “把 arXiv 日更样本入评测数据集” -> `arxiv import-dataset --subscription-date YYYY-MM/MM-DD`
- “跑一下本地检查 / 回归” -> `quality local-ci`
- “帮我测一下 SMTP / 发一封测试邮件” -> `quality send-test-email`
- “查看最近的报告” -> `report --source <conference|arxiv>`

如果缺参数，只补问必要字段，不发明新入口。

## arXiv 数据集导入

- `arxiv report --subscription-date YYYY-MM/MM-DD` 默认只生成推荐报告和蓝军审阅，不写入数据集
- `arxiv report --subscription-date YYYY-MM/MM-DD --fetch-all` 默认按批次续跑，批大小默认 `--batch-size 100`，游标写入分日目录 `workflow-state.json`
- 全量模式只有推荐和蓝军审阅全部完成后才生成 `final-summary.md` / `final-result.json` 等 `final-*` 产物；GitHub Issue 发布只能消费这些最终报告
- 手动执行 `arxiv import-dataset --subscription-date YYYY-MM/MM-DD` 才会读取同一个分日目录下的推荐报告/蓝军审阅产物，写入 `artifacts/datasets/arxiv/latest/import-payload.json`，并调用子仓 `paper-analysis-dataset-import-samples`
- 分日目录为 `artifacts/e2e/arxiv/daily/YYYY-MM/MM-DD/`，同时包含 `summary.md` / `result.json` 和 `review-summary.md` / `review-result.json`
- 如果分日目录中的推荐报告或蓝军审阅文件不存在，直接失败并提示先重跑 `arxiv report --subscription-date YYYY-MM/MM-DD --fetch-all`
- 同一篇论文的导入 notes 同时保留推荐算法结论与蓝军审阅结论
- 入库必须是人工确认后的显式操作，避免推荐算法或蓝军算法噪音直接增加人工标注成本
