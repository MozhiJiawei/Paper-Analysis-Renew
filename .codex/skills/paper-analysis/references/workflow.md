# 工作流摘要

## 顶会筛选

1. 载入顶会样例或指定输入
2. 载入用户偏好
3. 通过共享偏好模型筛选与排序
4. 输出终端摘要与报告产物

对应命令：

```powershell
py -m paper_analysis.cli.main conference filter
py -m paper_analysis.cli.main conference report
```

## arXiv 日更筛选

1. 载入 arXiv 日更样例或指定输入
2. 载入用户偏好
3. 通过共享偏好模型筛选与排序
4. 输出终端摘要与报告产物

对应命令：

```powershell
py -m paper_analysis.cli.main arxiv daily-filter
py -m paper_analysis.cli.main arxiv report
```

## 质量门禁

```powershell
py -m paper_analysis.cli.main quality local-ci
```

执行顺序：

1. `lint`
2. `typecheck`
3. `unit`
4. `integration`
5. `e2e`
