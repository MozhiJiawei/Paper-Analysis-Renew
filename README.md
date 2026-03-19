# Paper-Analysis-New

一个面向 Agent 的论文筛选工程基础仓库。

当前阶段先建立稳定工程骨架，聚焦两条业务链路：

1. 从顶会论文集合中筛选符合用户偏好的论文
2. 从 arXiv 每日更新中筛选符合用户偏好的论文

“推荐”不是独立产品面，而是上述两条链路中的共享筛选与排序阶段。

## 当前能力

- 仓库内 repo-local skill：`.codex/skills/paper-analysis/SKILL.md`
- 单一主 CLI：`py -m paper_analysis.cli.main`
- 稳定业务命名空间：`conference`、`arxiv`
- 质量门禁入口：`quality local-ci`
- 双黄金路径样例：顶会筛选、arXiv 日更筛选

## 快速开始

查看主帮助：

```powershell
py -m paper_analysis.cli.main --help
```

运行顶会黄金路径报告：

```powershell
py -m paper_analysis.cli.main conference report
```

运行 arXiv 黄金路径报告：

```powershell
py -m paper_analysis.cli.main arxiv report
```

运行本地质量门禁：

```powershell
py -m paper_analysis.cli.main quality local-ci
```

## 文档入口

- `AGENTS.md`
- `docs/agent-guide/quickstart.md`
- `docs/agent-guide/command-surface.md`
- `docs/engineering/testing-and-quality.md`
- `docs/engineering/encoding-and-output.md`

## 说明

当前实现优先保证：

- 中文输出可读
- UTF-8 编码一致
- CLI 与文档对齐
- 在未安装第三方依赖的 Windows 环境也能跑通基础验证

后续如需切换到 `pytest`、`ruff`、`mypy`，请参考 `docs/engineering/testing-and-quality.md`。
