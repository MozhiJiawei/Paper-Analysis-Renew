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
- `quality send-test-email`
- `quality lint`
- `quality unit`
- `quality integration`
- `quality e2e`

## report

- `report --source conference`
- `report --source arxiv`

## 意图到命令

- 顶会筛选类请求 -> `conference filter` / `conference report`
- arXiv 日更或订阅类请求 -> `arxiv daily-filter` / `arxiv report`
- 质量检查或回归请求 -> `quality local-ci`
- 邮件通道调试或测试邮件请求 -> `quality send-test-email`
- 最近报告查看请求 -> `report --source <conference|arxiv>`

默认只映射到现有四个顶层命名空间；缺少关键参数时只做最小追问。

## 约束

- 业务入口只允许 `conference` 和 `arxiv`
- “推荐 / 排序”不是独立命名空间
- arXiv CLI 当前默认展示抓取结果，不在命令入口执行偏好筛选
- benchmark / annotation / 网页标注能力已迁到 `third_party/paper_analysis_dataset` 子模块，不属于主仓 CLI 命令面
- benchmark 正式规范文档位于 `third_party/paper_analysis_dataset/docs/benchmarks/`

## 评测 API

以下能力不属于稳定 CLI 命令面，但属于跨仓评测契约的一部分：

- 启动方式：`py -m paper_analysis.api.evaluation_server --port <port>`
- 健康检查：`GET /healthz`
- 评测接口：`POST /v1/evaluation/annotate`

接口说明：

- 请求体包含 `requests` 数组；数组元素包含 `request_id` 与单篇论文 `paper`
- 响应体包含 `responses` 数组；数组元素包含 `request_id`、`prediction` 与 `model_info.algorithm_version`
- 主仓会在一个批次请求内并行处理全部论文，等整批完成后再一次性返回
- 返回标签必须遵循数据集子仓的单标签协议
- 响应中不得包含 `expected_label`、`ground_truth`、`split` 等评测泄露字段
