---
name: "paper-analysis"
description: "Use when working in this repository on conference paper filtering, arXiv daily updates or subscription fetching, local quality checks, or latest report lookup. Route natural-language requests onto the stable `conference`, `arxiv`, `quality`, and `report` CLI commands, and never invent a separate `recommend` namespace."
---

# Paper Analysis Repo Skill

这个仓库是一个面向 Codex 的论文分析 CLI。进入仓库后，优先围绕两条业务链路工作：

1. `conference`：从顶会论文集合中筛选符合用户偏好的论文
2. `arxiv`：从 arXiv 每日更新或订阅抓取中筛选符合用户偏好的论文

“推荐 / 排序”是共享内部阶段能力，不是独立的第三个业务命名空间。任何自然语言请求，都只能映射到现有稳定入口：

- `conference`
- `arxiv`
- `quality`
- `report`

## Quick Start

进入仓库后默认先做三件事：

1. 阅读 `docs/agent-guide/quickstart.md`
2. 阅读 `docs/agent-guide/command-surface.md`
3. 按用户意图选择 `conference`、`arxiv`、`quality` 或 `report`

常用稳定命令：

- `py -m paper_analysis.cli.main --help`
- `py -m paper_analysis.cli.main conference --help`
- `py -m paper_analysis.cli.main arxiv --help`
- `py -m paper_analysis.cli.main arxiv report --subscription-date 2026-04/04-10 --deliver-subscription`
- `py -m paper_analysis.cli.main arxiv report --subscription-date 2026-04/04-10 --fetch-all --batch-size 100`
- `py -m paper_analysis.cli.main arxiv import-dataset --subscription-date 2026-04/04-10`
- `py -m paper_analysis.cli.main quality send-test-email`
- `py -m paper_analysis.cli.main quality lint`
- `py -m paper_analysis.cli.main quality local-ci`
- `py -m paper_analysis.cli.main report --source conference`

## 自然语言路由

优先把自然语言请求翻译成已有 CLI，而不是发明新入口：

- 顶会筛选请求 -> `conference filter` 或 `conference report`
- arXiv 日更 / 订阅请求 -> `arxiv daily-filter` 或 `arxiv report`
- arXiv 推荐质量审阅 / 误推荐 / 漏推荐请求 -> 查看 `arxiv report` 每日推荐报告中的“蓝军审阅”段落；详细产物在 `artifacts/reviews/arxiv/latest/`
- arXiv 日更样本入评测数据集请求 -> `arxiv import-dataset --subscription-date YYYY-MM/MM-DD`
- arXiv 订阅最小投递闭环请求 -> `arxiv report --subscription-date YYYY-MM/MM-DD --deliver-subscription`
- 本地检查 / 回归请求 -> `quality local-ci`
- 邮件通道调试 / 测试邮件请求 -> `quality send-test-email`
- 查看最近产物 -> `report --source <conference|arxiv>`

缺少关键参数时，只追问必要信息：

- `conference` 缺会议或年份时追问 `venue` / `year`
- `arxiv` 在 `subscription-api` 或 `subscription-email` 模式下缺日期时追问 `subscription-date`
- `report` 缺来源时追问 `conference` 或 `arxiv`

默认假设：

- 顶会链路优先复用 `conference` 命名空间，不新增 `recommend`
- arXiv 链路优先复用 `arxiv` 命名空间，不在入口层做新的偏好产品面
- arXiv 默认先抓取候选，再输出过滤后的推荐结果
- arXiv 大模型审阅在 `arxiv report` 订阅邮件模式下默认执行，复用本次已加载候选集合和 OpenRouter `deepseek/deepseek-v4-pro`，检查误推荐、边界推荐与漏推荐，并把蓝军结论写回每日推荐报告；日更全量审阅使用 `--fetch-all`
- arXiv 订阅邮件 `--fetch-all` 默认按批次推进，批大小默认 `--batch-size 100`；同一条命令可重复运行续跑，游标在分日目录 `workflow-state.json`
- arXiv 全量推荐与蓝军审阅全部完成前不得把中间报告当成最终交付；只有分日目录下 `final-summary.md` / `final-result.json` 等 `final-*` 产物存在时，才允许发布到 GitHub Issue
- arXiv 数据集导入默认不随 `arxiv report` 自动执行；只有显式执行 `arxiv import-dataset` 时才写入子仓数据集
- arXiv 订阅默认使用 Gmail 订阅邮件；自然语言路由不要主动补 `--source-mode subscription-api`
- 质量检查默认运行 `quality local-ci`
- 邮件通道调试默认复用 `quality send-test-email`，不新增 `email` 顶层命名空间
- 文本产物与文档统一使用 UTF-8

完整路由示例见：

- `references/natural-language-routing.md`
- `references/command-surface.md`
- `references/workflow.md`

## 数据源与边界

顶会真实数据源：

- `conference filter` / `conference report` 支持通过 `paperlists` 子模块读取真实会议 JSON
- 默认子模块路径：`third_party/paperlists`
- 初始化命令：`git submodule update --init --recursive`

数据集与标注边界：

- benchmark / annotation / 网页标注 / 评测数据不再属于主仓稳定命令面
- 这些能力位于子模块 `third_party/paper_analysis_dataset`
- 主仓 `quality local-ci` 只检查主仓能力，不联跑子仓测试
- 只有在需要评测数据集或标注流程时，才初始化 `third_party/paper_analysis_dataset`
- 如需让子仓通过 API 调主仓推荐算法，使用 `py -m paper_analysis.api.evaluation_server`
- 评测复核默认走 OpenRouter，OpenRouter 失败时自动降级到 Doubao；如需强制 Doubao，可追加 `--ai-provider doubao`
- 当前评测 API 采用批量协议：请求体为 `requests` 数组，响应体为 `responses` 数组；子仓评测 CLI 默认每批发送 50 条

arXiv 输入模式：

- `fixture`：读取本地样例 JSON
- `subscription-email`：读取 Gmail 中的 arXiv 订阅邮件，按邮件内每篇论文的 `Date:` 映射到 `--subscription-date`
- `subscription-api`：访问 arXiv 官方 API，仅用于用户明确要求 API 或排障兼容场景
- 订阅邮件最小参数：`--subscription-date YYYY-MM/MM-DD`
- 订阅 API 显式参数：`--source-mode subscription-api --subscription-date YYYY-MM/MM-DD`
- arXiv 输出默认是过滤后的推荐结果，而不是原始抓取全集
- 提供 `--subscription-date` 且未显式设置 `--source-mode` 时默认使用 `subscription-email`
- 默认使用邮件而不是 API，是因为 arXiv API 在真实联网环境中容易出现 429、长时间无响应或大分页不稳定；订阅邮件是每日订阅报告的主事实来源
- 订阅投递闭环最小参数：`arxiv report --subscription-date YYYY-MM/MM-DD --deliver-subscription`
- 数据集导入手动参数：`arxiv import-dataset --subscription-date YYYY-MM/MM-DD`
- 手动导入只读取同一个分日目录下的推荐报告和蓝军审阅产物，不重新抓取 Gmail、不重跑推荐、不重跑蓝军审阅；缺少分日产物时直接报错，提示先重跑 `arxiv report --subscription-date YYYY-MM/MM-DD --fetch-all`
- 手动导入会把推荐结果、蓝军校验结果、ds-v4 边界负例抽样导入 `third_party/paper_analysis_dataset` 的现有 dataset-native import API
- 导入产物位于 `artifacts/datasets/arxiv/latest/import-payload.json`；同一篇论文的 notes 必须同时保留推荐算法结论和蓝军结论
- 不要把数据集导入挂到 `arxiv report` 默认流程上；入库必须是人工确认后的显式操作，避免算法噪音增加人工审阅成本

## 首读文档

- `docs/agent-guide/quickstart.md`
- `docs/agent-guide/command-surface.md`
- `docs/engineering/testing-and-quality.md`
