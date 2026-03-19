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
