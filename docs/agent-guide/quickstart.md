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

## paperlists 子模块

顶会真实数据源来自 `third_party/paperlists` 子模块。首次使用前先初始化：

```powershell
git submodule update --init --recursive
```

如果只想在测试夹具上验证，也可以显式覆盖根目录：

```powershell
py -m paper_analysis.cli.main conference report --venue iclr --year 2025 --paperlists-root tests/fixtures/paperlists_repo
```

## 第一原则

- 中文优先
- UTF-8 优先
- CLI 优先
- “推荐”不是独立产品面
- arXiv subscription-api 默认展示抓取到的前 10 条结果
