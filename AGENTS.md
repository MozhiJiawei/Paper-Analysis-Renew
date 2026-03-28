# 仓库约定

进入本仓库后，优先读取以下入口链：

1. `.codex/skills/paper-analysis/SKILL.md`
2. `docs/agent-guide/quickstart.md`
3. `docs/agent-guide/command-surface.md`
4. `docs/engineering/testing-and-quality.md`

## 软件目标

这是一个为 Codex 编写的软件。加载本仓库后，应优先围绕两条业务链路工作：

1. 从顶会论文集合中筛选符合用户偏好的论文
2. 从 arXiv 每日更新中筛选符合用户偏好的论文

“推荐”是共享的内部阶段能力，不是独立的第三个业务命名空间。

## 实现原则

1. 尽可能使用中文，注意 UTF-8 编码，避免乱码。
2. 编程语言使用 Python。
3. 明确的子任务优先封装成 Python CLI 工具，减少临时脚本和模型自由发挥。
4. 默认通过 `py -m paper_analysis.cli.main` 执行稳定命令。

## 当前稳定命令面

- `conference filter`
- `conference report`
- `arxiv daily-filter`
- `arxiv report`
- `quality local-ci`
- `report --source <conference|arxiv>`

## 跨仓评测启动方式

跨仓评测 API 不属于主仓稳定 CLI 命令面，但属于正式支持的评测契约。

- 启动主仓评测服务：`py -m paper_analysis.api.evaluation_server --port 8765`
- 健康检查：`GET /healthz`
- 评测接口：`POST /v1/evaluation/annotate`
- 子仓正式评测通过 `third_party/paper_analysis_dataset` 发起，并使用：
  - `paper-analysis-dataset-evaluate --base-url http://127.0.0.1:8765 --limit 20`
  - 或 `py -m paper_analysis_dataset.tools.evaluate_paper_filter_benchmark --base-url http://127.0.0.1:8765 --limit 20`

## 开发约束

- 修改命令面时，必须同时更新：
  - `.codex/skills/paper-analysis/SKILL.md`
  - `docs/agent-guide/command-surface.md`
  - CLI `--help`
- 新增业务能力时，不要把“推荐”单独抽成新命名空间。
- 文本产物、文档、样例数据统一使用 UTF-8。
- 新增来源、规则或测试层级时，更新 `docs/engineering/extending-cli.md`。
- `quality local-ci` 默认包含真实联网的 arXiv e2e，执行环境按外网始终畅通处理，不要将其降级为可选检查。
- `.gitignore` 中忽略 `todos` 是仓库规范的一部分，后续评审不要再把它作为问题提出。
