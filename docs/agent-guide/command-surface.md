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
  - 默认订阅邮件模式：`arxiv daily-filter --subscription-date <YYYY-MM/MM-DD> [--category <term>]... [--max-results <int>]`
  - 订阅 API 模式：`arxiv daily-filter --source-mode subscription-api --subscription-date <YYYY-MM/MM-DD> [--category <term>]... [--max-results <int>]`
  - 订阅邮件模式：`arxiv daily-filter --source-mode subscription-email --subscription-date <YYYY-MM/MM-DD> [--category <term>]... [--max-results <int>]`
  - 默认行为：先抓取候选，再输出过滤后的推荐结果
- `arxiv report`
  - 样例模式：`arxiv report --input <json>`
  - 默认订阅邮件模式：`arxiv report --subscription-date <YYYY-MM/MM-DD> [--category <term>]... [--max-results <int>]`
  - 订阅 API 模式：`arxiv report --source-mode subscription-api --subscription-date <YYYY-MM/MM-DD> [--category <term>]... [--max-results <int>]`
  - 订阅邮件模式：`arxiv report --source-mode subscription-email --subscription-date <YYYY-MM/MM-DD> [--category <term>]... [--max-results <int>]`
  - 默认行为：先抓取候选，再把过滤后的推荐结果写入基础四件套
  - 订阅邮件全量模式：`arxiv report --subscription-date <YYYY-MM/MM-DD> --fetch-all [--batch-size 100]`
  - 订阅邮件全量模式会按批次推进推荐与蓝军审阅进度；同一命令可重复运行续跑，游标写入分日目录 `workflow-state.json`
  - 全量模式只有推荐批次和蓝军审阅全部完成后，才生成 `final-summary.md` / `final-result.json` / `final-result.csv` / `final-stdout.txt`，并同步到 `artifacts/e2e/arxiv/latest/`
  - 若 `final-*` 产物不存在，视为未完成中间态；GitHub Issue 发布脚本只能提醒继续运行同一条 CLI，不能发布半成品
  - 订阅投递模式：`arxiv report --subscription-date <YYYY-MM/MM-DD> [--category <term>]... [--max-results <int>] --deliver-subscription`
  - 订阅邮件模式下默认执行大模型蓝军审阅，结论会写回 `artifacts/e2e/arxiv/latest/summary.md` 与 `result.json`
  - 详细审阅产物保留在：`artifacts/reviews/arxiv/latest/summary.md`、`result.json`、`stdout.txt`
  - 大模型审阅默认使用 OpenRouter `deepseek/deepseek-v4-pro`，复用本次已加载候选集合，检查误推荐、边界推荐与漏推荐；日更全量审阅使用 `--fetch-all`
- `arxiv import-dataset`
  - 手动入库：`arxiv import-dataset --subscription-date <YYYY-MM/MM-DD>`
  - 默认行为：只读取 `artifacts/e2e/arxiv/daily/<YYYY-MM>/<MM-DD>/` 下的推荐报告与蓝军审阅文件，不会重新抓取 Gmail、重跑推荐或重跑蓝军审阅
  - 同一日期目录同时包含 `summary.md` / `result.json` / `result.csv` / `stdout.txt` 和 `review-summary.md` / `review-result.json` / `review-stdout.txt`
  - 如果分日目录中的推荐报告或蓝军审阅文件不存在，直接结构化失败，并提示先重跑 `arxiv report --subscription-date <YYYY-MM/MM-DD> --fetch-all`
  - 数据集导入产物保留在 `artifacts/datasets/arxiv/latest/import-payload.json`
  - 数据集导入会包含推荐算法结论、蓝军校验结论，以及 ds-v4 从未覆盖候选中抽样的边界负例；同一篇论文的 `notes` 同时保留推荐算法结论与蓝军结论

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
- arXiv 推荐质量审阅、误推荐或漏推荐分析 -> `arxiv report` 生成的每日推荐报告中的“蓝军审阅”段落，详细信息见 `artifacts/reviews/arxiv/latest/`
- arXiv 日更样本入评测数据集 -> `arxiv import-dataset --subscription-date <YYYY-MM/MM-DD>`
- arXiv 每日订阅邮件与本地 HTML 闭环 -> `arxiv report --deliver-subscription`
- 质量检查或回归请求 -> `quality local-ci`
- 邮件通道调试或测试邮件请求 -> `quality send-test-email`
- 最近报告查看请求 -> `report --source <conference|arxiv>`

默认只映射到现有四个顶层命名空间；缺少关键参数时只做最小追问。

## 约束

- 业务入口只允许 `conference` 和 `arxiv`
- “推荐 / 排序”不是独立命名空间
- arXiv CLI 当前默认先过滤，再输出或写出推荐结果；“推荐 / 排序”仍是共享内部阶段能力，不是独立命名空间
- arXiv 大模型审阅是 `arxiv report` 的默认蓝军复核层，结论写回每日推荐报告，不新增 `recommend` 顶层命名空间
- arXiv 订阅邮件日更默认不入库；只有显式执行 `arxiv import-dataset` 时，才调用数据集子仓现有 `paper-analysis-dataset-import-samples` API
- 数据集导入样本必须保留推荐算法和蓝军的双侧结论，避免同一篇论文被蓝军覆盖后失去原始推荐上下文
- 数据集导入是人工确认后的手动操作，避免推荐算法或蓝军算法噪音直接转成人工标注成本
- `arxiv report --deliver-subscription` 只支持 `--source-mode subscription-api` 或 `--source-mode subscription-email`，并在保留基础四件套的同时继续归档运行快照、发送邮件并发布本地订阅站点
- `subscription-email` 模式使用 Gmail 中的 arXiv 订阅邮件作为主数据源，`--subscription-date` 仍表示论文日期；系统按邮件内每篇论文的 `Date:` 字段做本地日期映射
- 提供 `--subscription-date` 且未显式设置 `--source-mode` 时，默认使用 `subscription-email`
- 自然语言路由、E2E 与 CI 默认不要主动补 `--source-mode subscription-api`；官方 API 模式仅用于用户明确要求 API 或排障兼容场景，必须显式传入 `--source-mode subscription-api`
- 默认使用邮件模式是因为 arXiv 官方 API 在真实联网环境中容易出现 429、长时间无响应或大分页不稳定，而订阅邮件更贴近日常报告的日期语义
- benchmark / annotation / 网页标注能力已迁到 `third_party/paper_analysis_dataset` 子模块，不属于主仓 CLI 命令面
- benchmark 正式规范文档位于 `third_party/paper_analysis_dataset/docs/benchmarks/`

## 评测 API

以下能力不属于稳定 CLI 命令面，但属于跨仓评测契约的一部分：

- 启动方式：`py -m paper_analysis.api.evaluation_server --port <port>`
- 默认 AI provider 为 OpenRouter，失败时自动降级到 Doubao
- 如需强制只用 Doubao：`py -m paper_analysis.api.evaluation_server --port <port> --ai-provider doubao`
- 健康检查：`GET /healthz`
- 评测接口：`POST /v1/evaluation/annotate`

接口说明：

- 请求体包含 `requests` 数组；数组元素包含 `request_id` 与单篇论文 `paper`
- 响应体包含 `responses` 数组；数组元素包含 `request_id`、`prediction` 与 `model_info.algorithm_version`
- 主仓会在一个批次请求内并行处理全部论文，等整批完成后再一次性返回
- 返回标签必须遵循数据集子仓的单标签协议
- 响应中不得包含 `expected_label`、`ground_truth`、`split` 等评测泄露字段
