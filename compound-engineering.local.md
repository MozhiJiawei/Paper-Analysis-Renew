---
review_agents: [kieran-python-reviewer, code-simplicity-reviewer, security-sentinel, performance-oracle]
plan_review_agents: [kieran-python-reviewer, code-simplicity-reviewer]
---

# Review Context

- 这是一个以 Python CLI 为主的 Agent-first 工程基础设施仓库。
- 重点关注命令面一致性、UTF-8 中文输出稳定性、Windows 环境兼容性、共享筛选逻辑是否被两条链路正确复用。
- 当前 review 目标是本地未提交改动，不依赖 GitHub PR 元数据。
- `tests/e2e/` 中的 arXiv 联网校验是默认质量门禁要求，评审时不要建议把它降级为可选或跳过。
- `.gitignore` 中忽略 `todos` 是本仓库的既定约定；不要再把 `todos/` 被忽略视为代码评审问题。
