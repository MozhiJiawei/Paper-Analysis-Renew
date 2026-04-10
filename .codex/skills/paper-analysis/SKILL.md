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
- `py -m paper_analysis.cli.main quality send-test-email`
- `py -m paper_analysis.cli.main quality lint`
- `py -m paper_analysis.cli.main quality local-ci`
- `py -m paper_analysis.cli.main report --source conference`

## 自然语言路由

优先把自然语言请求翻译成已有 CLI，而不是发明新入口：

- 顶会筛选请求 -> `conference filter` 或 `conference report`
- arXiv 日更 / 订阅请求 -> `arxiv daily-filter` 或 `arxiv report`
- 本地检查 / 回归请求 -> `quality local-ci`
- 邮件通道调试 / 测试邮件请求 -> `quality send-test-email`
- 查看最近产物 -> `report --source <conference|arxiv>`

缺少关键参数时，只追问必要信息：

- `conference` 缺会议或年份时追问 `venue` / `year`
- `arxiv` 在 `subscription-api` 模式下缺日期时追问 `subscription-date`
- `report` 缺来源时追问 `conference` 或 `arxiv`

默认假设：

- 顶会链路优先复用 `conference` 命名空间，不新增 `recommend`
- arXiv 链路优先复用 `arxiv` 命名空间，不在入口层做新的偏好产品面
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
- 当前评测 API 采用批量协议：请求体为 `requests` 数组，响应体为 `responses` 数组；子仓评测 CLI 默认每批发送 50 条

arXiv 输入模式：

- `fixture`：读取本地样例 JSON
- `subscription-api`：访问 arXiv 官方 API
- 订阅 API 最小参数：`--source-mode subscription-api --subscription-date YYYY-MM/MM-DD`

## 首读文档

- `docs/agent-guide/quickstart.md`
- `docs/agent-guide/command-surface.md`
- `docs/engineering/testing-and-quality.md`
