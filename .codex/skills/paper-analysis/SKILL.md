# Paper Analysis Repo Skill

进入本仓库后，默认先做三件事：

1. 阅读 `docs/agent-guide/quickstart.md`
2. 阅读 `docs/agent-guide/command-surface.md`
3. 根据任务选择 `conference`、`arxiv`、`quality` 或 `report` 命令

## 软件边界

- 业务能力只有两类：
  - 顶会论文筛选
  - arXiv 日更 / 订阅抓取
- “推荐 / 排序”是共享内部阶段，不是独立命名空间
- 扩展业务能力时，优先沿 `conference` 或 `arxiv` 链路扩展，不新增 `recommend` CLI
- arXiv 订阅链路当前以实时抓取和报告展示为主，CLI 默认展示抓取结果的前 10 条

## 推荐工作流

- 查看总入口：`py -m paper_analysis.cli.main --help`
- 查看顶会命令：`py -m paper_analysis.cli.main conference --help`
- 查看 arXiv 命令：`py -m paper_analysis.cli.main arxiv --help`
- 运行本地门禁：`py -m paper_analysis.cli.main quality local-ci`
- 查看最近报告：`py -m paper_analysis.cli.main report --source conference`

## 顶会真实数据源

- `conference filter` / `conference report` 支持通过 `paperlists` 子模块读取真实会议 JSON
- 默认子模块路径：`third_party/paperlists`
- 初始化子模块：
  - `git submodule update --init --recursive`
- 示例：
  - `py -m paper_analysis.cli.main conference report --venue iclr --year 2025`
  - `py -m paper_analysis.cli.main conference filter --venue cvpr --year 2024 --seed 7`

## arXiv 订阅输入

- `arxiv daily-filter` / `arxiv report` 支持两种输入模式：
  - fixture：读取本地样例 JSON
  - subscription-api：访问 arXiv 官方 API
- 订阅 API 最小参数：
  - `--source-mode subscription-api`
  - `--subscription-date YYYY-MM/MM-DD`
- 可选参数：
  - `--category <term>`，可重复传入
  - `--max-results <int>`
- CLI 当前默认输出抓取结果，不在入口做偏好过滤
- 示例：
  - `py -m paper_analysis.cli.main arxiv report --source-mode subscription-api --subscription-date 2025-09/09-01 --max-results 10`
  - `py -m paper_analysis.cli.main arxiv daily-filter --source-mode subscription-api --subscription-date 2025-09/09-01 --category cs.AI`

## 首读文档

- `docs/agent-guide/quickstart.md`
- `docs/agent-guide/command-surface.md`
- `docs/engineering/testing-and-quality.md`
- `docs/engineering/extending-cli.md`

## 任务路由

- 新增顶会相关能力时，优先看 `paper_analysis/cli/conference.py`、`ConferencePipeline` 和 `paper_analysis/sources/conference/`
- 新增 arXiv 日更 / 订阅能力时，优先看 `paper_analysis/cli/arxiv.py`、`ArxivPipeline` 和 `paper_analysis/sources/arxiv/`
- 修改偏好筛选逻辑时，优先看 `PreferenceProfile`、`PreferenceRanker`
- 更新质量门禁时，优先看 `paper_analysis/cli/quality.py` 和 `scripts/quality/`

## 维护要求

- 变更命令面时，必须同步更新：
  - 本 skill
  - `docs/agent-guide/command-surface.md`
  - CLI `--help`
- 新增来源、规则或测试层级时，更新 `docs/engineering/extending-cli.md`
