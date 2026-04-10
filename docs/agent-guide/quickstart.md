# Agent Quickstart

## 目标

本仓库优先交付 Agent 优先的论文处理基础设施。只需要记住两条业务链路：

1. `conference`：顶会论文筛选
2. `arxiv`：arXiv 日更抓取与报告

## 先读什么

1. `.codex/skills/paper-analysis/SKILL.md`
2. `docs/agent-guide/command-surface.md`
3. `docs/engineering/testing-and-quality.md`

## 常用命令

```powershell
py -m paper_analysis.cli.main --help
py -m paper_analysis.cli.main conference report
py -m paper_analysis.cli.main conference report --venue iclr --year 2025
py -m paper_analysis.cli.main arxiv report
py -m paper_analysis.cli.main arxiv report --source-mode subscription-api --subscription-date 2026-04/04-10 --deliver-subscription
py -m paper_analysis.cli.main quality send-test-email
py -m paper_analysis.cli.main quality local-ci
py -m paper_analysis.api.evaluation_server --port 8765
```

## Doubao 私有配置

- 默认优先读取环境变量 `ARK_API_KEY`
- 如需本地配置文件，请放在用户私有目录 `~/.paper-analysis/doubao.yaml`
- 若要调用 embedding 路线，请额外配置 `doubao.embedding_model`，值应为当前账号下可直接调用的 embedding endpoint / model
- 若 `embedding_model` 使用的是 `doubao-embedding-vision-*`，客户端会自动改走 multimodal embedding API，并允许纯文本输入
- 仓库内只保留模板文件 `paper_analysis/config/doubao.template.yaml`，不要在 `paper_analysis/config/` 下保存真实密钥

## 自然语言如何落到命令

当人类直接对 Codex 说自然语言时，默认按下面的稳定入口分流：

- “帮我筛 ICLR 2025 论文” -> `conference filter` 或 `conference report`
- “帮我看今天的 arXiv AI 更新” -> `arxiv daily-filter` 或 `arxiv report`
- “把今天的 arXiv 订阅结果发邮件并更新本地页面” -> `arxiv report --source-mode subscription-api --subscription-date <YYYY-MM/MM-DD> --deliver-subscription`
- “帮我试一下 QQ SMTP 发信” -> `quality send-test-email`
- “跑一下本地检查” -> `quality local-ci`
- “看最近一次顶会报告” -> `report --source conference`

缺少关键参数时，只追问必要信息：

- `conference` 缺会议名或年份时追问
- `arxiv` 在 `subscription-api` 模式下缺订阅日期时追问
- `report` 缺来源时追问 `conference` 或 `arxiv`

不要新增 `recommend` 命名空间。

## QQ SMTP 测试邮件

先准备环境变量：

```powershell
$env:SMTP_HOST = "smtp.qq.com"
$env:SMTP_PORT = "587"
$env:SMTP_USERNAME = "your-account@qq.com"
$env:SMTP_PASSWORD = "你的 QQ 邮箱授权码"
$env:SMTP_FROM = "your-account@qq.com"
$env:SMTP_TO = "lijiawei14@huawei.com"
```

然后执行：

```powershell
py -m paper_analysis.cli.main quality send-test-email
```

结果会写到：

```text
artifacts/email/send-test-latest/
```

## arXiv 订阅最小投递闭环

先准备和测试邮件相同的 SMTP 环境变量，然后执行：

```powershell
py -m paper_analysis.cli.main arxiv report --source-mode subscription-api --subscription-date 2026-04/04-10 --deliver-subscription
```

首次闭环成功后，关键产物位于：

```text
artifacts/e2e/arxiv/latest/
artifacts/subscriptions/arxiv/runs/<run_id>/
artifacts/subscriptions/arxiv/site/latest.html
artifacts/subscriptions/arxiv/site/index.html
```

## paperlists 子模块

顶会真实数据源来自 `third_party/paperlists` 子模块。首次使用前先初始化：

```powershell
git submodule update --init --recursive
```

如果只想在测试夹具上验证，也可以显式覆盖根目录：

```powershell
py -m paper_analysis.cli.main conference report --venue iclr --year 2025 --paperlists-root tests/fixtures/paperlists_repo
```

## 数据集子仓

- `third_party/paper_analysis_dataset` 只在需要 benchmark、annotation、网页标注或评测数据时初始化
- 主仓 `quality local-ci` 不依赖这个子仓
- benchmark 正式规范文档统一位于 `third_party/paper_analysis_dataset/docs/benchmarks/`
- 跨仓评测时，由主仓启动 `paper_analysis.api.evaluation_server`，子仓通过 `POST /v1/evaluation/annotate` 调用

## 第一原则

- 中文优先
- UTF-8 优先
- CLI 优先
- “推荐”不是独立产品面
- arXiv 默认先抓取候选，再输出过滤后的推荐结果
- `--deliver-subscription` 只允许在 `subscription-api` 模式下执行真实投递
