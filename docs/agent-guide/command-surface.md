# Command Surface

## 主入口

```powershell
py -m paper_analysis.cli.main <namespace> <action> [options]
```

## conference

- `conference filter`
  - 样例模式：`conference filter --input <json>`
  - paperlists 模式：`conference filter --venue <venue> --year <year> [--paperlists-root <path>] [--seed <int>]`
- `conference report`
  - 样例模式：`conference report --input <json>`
  - paperlists 模式：`conference report --venue <venue> --year <year> [--paperlists-root <path>] [--seed <int>]`

## arxiv

- `arxiv daily-filter`
  - 样例模式：`arxiv daily-filter --input <json>`
  - 订阅 API 模式：`arxiv daily-filter --source-mode subscription-api --subscription-date <YYYY-MM/MM-DD> [--category <term>]... [--max-results <int>]`
- `arxiv report`
  - 样例模式：`arxiv report --input <json>`
  - 订阅 API 模式：`arxiv report --source-mode subscription-api --subscription-date <YYYY-MM/MM-DD> [--category <term>]... [--max-results <int>]`

## quality

- `quality local-ci`
- `quality lint`
- `quality typecheck`
- `quality unit`
- `quality integration`
- `quality e2e`

## report

- `report --source conference`
- `report --source arxiv`

## 约束

- 业务入口只允许 `conference` 和 `arxiv`
- “推荐 / 排序”不是独立命名空间
- arXiv CLI 当前默认展示抓取结果，不在命令入口执行偏好筛选
