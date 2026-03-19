# Paper Analysis Repo Skill

进入本仓库后，默认先做三件事：

1. 读取 `docs/agent-guide/quickstart.md`
2. 读取 `docs/agent-guide/command-surface.md`
3. 根据任务选择 `conference`、`arxiv`、`quality` 或 `report` 命令

## 软件边界

- 业务功能只有两类：
  - 顶会论文筛选
  - arXiv 日更筛选
- “推荐/排序”是共享内部阶段，不是独立命名空间。
- 如果要扩展业务能力，优先沿 `conference` 或 `arxiv` 链路扩展，而不是新增 `recommend` CLI。

## 推荐工作流

- 查看项目总览：`py -m paper_analysis.cli.main --help`
- 查看顶会命令：`py -m paper_analysis.cli.main conference --help`
- 查看 arXiv 命令：`py -m paper_analysis.cli.main arxiv --help`
- 跑本地门禁：`py -m paper_analysis.cli.main quality local-ci`
- 查看最近报告：`py -m paper_analysis.cli.main report --source conference`

## 首读文档

- `references/workflow.md`
- `references/command-surface.md`
- `docs/engineering/testing-and-quality.md`
- `docs/engineering/extending-cli.md`

## 任务路由

- 当任务是“新增顶会相关能力”时，先看 `conference` 命令和 `ConferencePipeline`
- 当任务是“新增 arXiv 日更相关能力”时，先看 `arxiv` 命令和 `ArxivPipeline`
- 当任务是“修改偏好筛选逻辑”时，先看 `PreferenceProfile`、`rank_papers` 和 `PreferenceRanker`
- 当任务是“更新质量门禁”时，先看 `paper_analysis/cli/quality.py` 和 `scripts/quality/`

## 维护要求

- 变更命令面时，必须同步更新：
  - 本 skill
  - `references/command-surface.md`
  - `docs/agent-guide/command-surface.md`
  - CLI `--help`
