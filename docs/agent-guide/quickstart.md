# Agent Quickstart

## 目标

本仓库当前先交付 Agent 优先的论文筛选工程基础设施。

你只需要记住两条业务链路：

1. `conference`：顶会论文筛选
2. `arxiv`：arXiv 日更筛选

## 先读什么

1. `.codex/skills/paper-analysis/SKILL.md`
2. `docs/agent-guide/command-surface.md`
3. `docs/engineering/testing-and-quality.md`

## 常用命令

```powershell
py -m paper_analysis.cli.main --help
py -m paper_analysis.cli.main conference report
py -m paper_analysis.cli.main arxiv report
py -m paper_analysis.cli.main quality local-ci
```

## 第一原则

- 中文优先
- UTF-8 优先
- CLI 优先
- “推荐”不是独立产品面
