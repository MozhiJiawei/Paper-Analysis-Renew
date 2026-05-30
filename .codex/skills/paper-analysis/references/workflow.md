# 工作流摘要

先做意图分流，再执行稳定 CLI：

1. 识别用户属于 `conference`、`arxiv`、`quality` 还是 `report`
2. 缺少关键参数时只追问必要信息
3. 参数齐全后执行现有命令
4. 输出终端摘要与报告产物

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

## arXiv 大模型审阅

`arxiv report` 在订阅邮件模式下默认执行：

1. 读取本次推荐结果中的已推荐论文
2. 复用本次已加载的 Gmail 订阅邮件候选集合；日更全量审阅使用 `--fetch-all`
3. 用 OpenRouter `deepseek/deepseek-v4-pro` 审阅已推荐论文是否误推荐
4. 分批审阅未推荐候选中是否存在明显漏推荐
5. 将蓝军结论写回 `artifacts/e2e/arxiv/latest/summary.md` 与 `result.json`
6. 输出详细审阅产物 `artifacts/reviews/arxiv/latest/summary.md`、`result.json`、`stdout.txt`

对应命令：

```powershell
py -m paper_analysis.cli.main arxiv report --subscription-date <YYYY-MM/MM-DD>
```

## arXiv 数据集手动导入

`arxiv report` 默认不写入评测数据集。确认推荐算法与蓝军审阅结果适合沉淀后，再手动执行：

```powershell
py -m paper_analysis.cli.main arxiv import-dataset --subscription-date <YYYY-MM/MM-DD>
```

执行步骤：

1. 检查 `artifacts/e2e/arxiv/daily/<YYYY-MM>/<MM-DD>/result.json` 是否存在
2. 检查同一目录下的 `review-result.json` 是否存在且日期匹配
3. 从分日报告读取推荐论文与候选全集
4. 抽样 ds-v4 边界负例
5. 写出 `artifacts/datasets/arxiv/latest/import-payload.json` 并调用数据集子仓导入 API

如果任一分日产物不存在，直接报错，提示先运行：

```powershell
py -m paper_analysis.cli.main arxiv report --subscription-date <YYYY-MM/MM-DD> --fetch-all
```

## 质量门禁

```powershell
py -m paper_analysis.cli.main quality local-ci
```

执行顺序：

1. `lint`
2. `unit`
3. `integration`
4. `e2e`

`quality lint` 内部固定执行：

1. 仓库规范检查
2. `ruff`
3. `mypy`
4. 代码质量治理报告（仅告警）

## 邮件通道调试

```powershell
py -m paper_analysis.cli.main quality send-test-email
```

执行步骤：

1. 从环境变量读取 SMTP 配置
2. 校验必填字段
3. 构造 UTF-8 测试邮件
4. 发送到固定收件人并写出 `.eml` 与结果 JSON 产物

## 最近报告

```powershell
py -m paper_analysis.cli.main report --source conference
py -m paper_analysis.cli.main report --source arxiv
```
