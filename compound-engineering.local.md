---
review_agents: [kieran-python-reviewer, code-simplicity-reviewer, security-sentinel, performance-oracle]
plan_review_agents: [kieran-python-reviewer, code-simplicity-reviewer]
---

# Review Context

- 这是一个以 Python CLI 为主的 Agent-first 工程基础设施仓库。
- 重点关注命令面一致性、UTF-8 中文输出稳定性、Windows 环境兼容性、共享筛选逻辑是否被两条链路正确复用。
- 当前 review 目标是本地未提交改动，不依赖 GitHub PR 元数据。
