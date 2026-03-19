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
- `arxiv report`

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
- 偏好筛选属于共享内部能力，不单独暴露为 `recommend`
