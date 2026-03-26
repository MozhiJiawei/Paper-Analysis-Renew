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
py -m paper_analysis.cli.main quality local-ci
```

## Doubao 私有配置

- 默认优先读取环境变量 `ARK_API_KEY`
- 如需本地配置文件，请放在用户私有目录 `~/.paper-analysis/doubao.yaml`
- 仓库内只保留模板文件 `paper_analysis/config/doubao.template.yaml`，不要在 `paper_analysis/config/` 下保存真实密钥

## 自然语言如何落到命令

当人类直接对 Codex 说自然语言时，默认按下面的稳定入口分流：

- “帮我筛 ICLR 2025 论文” -> `conference filter` 或 `conference report`
- “帮我看今天的 arXiv AI 更新” -> `arxiv daily-filter` 或 `arxiv report`
- “跑一下本地检查” -> `quality local-ci`
- “看最近一次顶会报告” -> `report --source conference`

缺少关键参数时，只追问必要信息：

- `conference` 缺会议名或年份时追问
- `arxiv` 在 `subscription-api` 模式下缺订阅日期时追问
- `report` 缺来源时追问 `conference` 或 `arxiv`

不要新增 `recommend` 命名空间。

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

## 第一原则

- 中文优先
- UTF-8 优先
- CLI 优先
- “推荐”不是独立产品面
- arXiv subscription-api 默认展示抓取到的前 10 条结果
