---
title: "Skill 使用说明不混入开发与维护约束"
category: "integration-issues"
date: 2026-03-21
tags:
  - codex
  - skill
  - documentation
  - agent-entry
  - repository-boundary
  - spec
---

# Skill 使用说明不混入开发与维护约束

## 问题

`paper-analysis` 的 repo-local skill 最初同时承载了两类内容：

1. AI 如何使用仓库现有能力
2. 开发者如何编辑、扩展、维护仓库

这让 skill 从“能力使用说明”漂移成了“仓库内部维护手册”，不利于后续独立发布，也会让 AI 把与运行能力无关的开发细节误当成 skill 的默认职责。

## 现象

可见症状包括：

- `SKILL.md` 同时包含自然语言路由、稳定 CLI 命令和开发路径说明。
- skill 中出现了源码目录、维护同步要求和扩展流程之类的 contributor 内容。
- 当要把该 skill 独立发布时，正文无法脱离当前仓库的工程上下文单独成立。

## 根因

根因是 skill 的职责边界没有被写成显式契约。

- 使用型 skill 应回答“AI 应该如何调用现有能力”
- 开发型文档应回答“人如何修改、扩展、维护这个仓库”

这两类内容属于不同层级。它们一旦混写，skill 就会在 Agent 入口层发生语义漂移，降低可移植性，也增加后续维护噪音。

## 解决方案

这次修复采用“收缩 skill 职责边界”的方式：

### 1. 把 skill 限定为使用者视角

`SKILL.md` 只保留这些内容：

- 业务边界
- 稳定命令面
- 自然语言到 CLI 的映射
- 必要参数追问规则
- 默认假设
- 用户可直接执行的命令

例如，这类内容应保留：

```md
- 顶会筛选请求 -> `conference filter` 或 `conference report`
- arXiv 日更 / 订阅请求 -> `arxiv daily-filter` 或 `arxiv report`
- 本地检查 / 回归请求 -> `quality local-ci`
- 查看最近产物 -> `report --source <conference|arxiv>`
```

### 2. 移除开发与维护导向内容

从 `SKILL.md` 中移除了这类 contributor 信息：

- 应查看哪些源码路径
- 如何扩展命令面
- 文档同步维护要求
- 仓库维护流程

这类内容不应出现在 skill 正文中：

```md
- 新增顶会相关能力时，优先看 `paper_analysis/cli/conference.py` ...
- 变更命令面时，必须同步更新：
  - 本 skill
  - `docs/agent-guide/command-surface.md`
  - CLI `--help`
```

### 3. 把边界写入 spec 约束

这次经验应该上升为显式 spec / requirements 约束，而不是只停留在一次性编辑：

- repo-local skill 面向“使用现有能力”，不面向“开发仓库”
- 开发、扩展、维护信息不得写入 skill 正文
- 如果 skill 计划独立发布，正文必须能脱离当前仓库工程上下文单独理解

## 验证

这次调整通过以下方式验证：

- 人工审查 `SKILL.md`，确认只保留使用导向内容
- 移除开发路径与维护要求后，skill 仍保留稳定命令面与自然语言路由
- 运行 `py -m unittest tests.integration.test_skill_contract`，确认当前 skill 契约测试通过

## 预防策略

后续要避免这类漂移，建议把下面三条固定下来：

1. `SKILL.md` 的单一职责是“教 AI 用能力”，不是“教 AI 改仓库”
2. 开发与维护规则统一放到 `docs/engineering/`、spec 或 plan 文档
3. 每次修改 skill 都从“独立发布是否仍然成立”这个角度复查一遍

## 建议测试清单

如果后续把这条规则正式写入 spec，建议再补一层自动化校验：

- 断言 `SKILL.md` 不包含开发导向关键词或源码路径
- 断言 `SKILL.md` 仍包含 `conference`、`arxiv`、`quality`、`report` 等使用导向核心元素
- 断言 spec 中存在“skill 不含开发信息”的显式约束
- 断言 skill 内容与该 spec 约束保持一致

## 相关文档

- `docs/brainstorms/2026-03-19-agent-first-project-organization-requirements.md`
- `docs/agent-guide/quickstart.md`
- `docs/agent-guide/command-surface.md`
- `docs/engineering/extending-cli.md`
- `docs/solutions/integration-issues/cli-structured-failure-and-windows-utf8-compatibility.md`
- `.codex/skills/paper-analysis/SKILL.md`

## 结论

repo-local skill 是 Agent 的能力入口，不是仓库开发手册。

只要把“如何使用能力”和“如何维护仓库”分层清楚，skill 就更容易复用、发布和长期保持稳定。把这条规则写进 spec，再配上一层正反向回归检查，后续就不容易再漂移回去。
