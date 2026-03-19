---
title: feat: 建立 Agent 优先的论文筛选工程基础设施
type: feat
status: completed
date: 2026-03-19
origin: docs/brainstorms/2026-03-19-agent-first-project-organization-requirements.md
---

# feat: 建立 Agent 优先的论文筛选工程基础设施

## Overview

本计划定义 `Paper-Analysis-New` 的第一阶段工程基础设施，使仓库在实现具体业务前，先具备稳定的 Agent 入口、仓库内 skill 暴露层、清晰文档、分层测试和本地质量门禁能力。产品能力被明确收敛为两个功能：

1. 从某个顶会论文集合中筛选出符合用户偏好的论文
2. 从 arXiv 每日更新中筛选出符合用户偏好的论文

这里的“推荐”不再是独立产品模块，而是上述两类论文分析/筛选流程中的一个输出步骤，即：先获取候选论文，再结合用户偏好进行筛选、排序和理由生成。核心方向直接承接来源文档中的四个已定决策：工程能力优先、Agent 优先、标准门禁、CLI 文本报告 `(see origin: docs/brainstorms/2026-03-19-agent-first-project-organization-requirements.md)`。

## Problem Statement

当前仓库几乎是空白状态，仅有 [AGENTS.md](D:\Git_Repo\Paper-Analysis-New\AGENTS.md)、[README.md](D:\Git_Repo\Paper-Analysis-New\README.md) 和一份 brainstorm 文档，没有既有代码结构、质量脚本、计划模板、测试约定或历史 learnings 可复用。这个现状意味着：

- Agent 虽然能读取需求，但没有稳定命令面，也没有仓库内 skill 作为首个操作说明层，无法可靠执行“顶会论文筛选”“arXiv 日更筛选”“跑测试”“展示 e2e”这类动作。
- 人类虽然能理解需求，但不能用单一命令验证仓库状态，也无法看到可展示的黄金路径输出。
- 如果不先冻结工程边界，后续功能很容易形成脚本散落、文档失真、测试层级混乱的问题。
- 如果错误地把“推荐”建成独立功能面，后续会出现与顶会/arXiv 两条输入链路重复建模、重复命令和重复测试的问题。

来源文档已经明确要求：项目需要优先围绕 CLI、pipeline、testing、docs、quality gates 组织，而不是围绕业务主题先堆目录 `(see origin: docs/brainstorms/2026-03-19-agent-first-project-organization-requirements.md)`。因此本计划的目标是先搭建稳定工程骨架，再承载两条稳定业务链路：顶会筛选与 arXiv 日更筛选。

## Research Summary

### Local Repository Findings

- 仓库现状极简：当前仅有根目录文档和 [docs/brainstorms/2026-03-19-agent-first-project-organization-requirements.md](D:\Git_Repo\Paper-Analysis-New\docs\brainstorms\2026-03-19-agent-first-project-organization-requirements.md)。
- 项目约束由 [AGENTS.md](D:\Git_Repo\Paper-Analysis-New\AGENTS.md) 明确：尽可能使用中文、避免乱码、使用 Python、明确子任务封装为 Python CLI 工具。
- 当前不存在 `.github/` 模板、`docs/solutions/` institutional learnings、现成测试目录、现成 CLI 入口或质量脚本。
- [README.md](D:\Git_Repo\Paper-Analysis-New\README.md) 还未承载有效工程说明，因此计划必须同时覆盖“首批文档体系”和“首个 repo skill”的建立。

### Institutional Learnings Findings

- `docs/solutions/` 当前不存在，因此没有历史经验文档可复用。
- 这意味着计划中需要显式加入“后续问题沉淀为 learnings 文档”的扩展位，否则后续仍会重复踩坑。

### External Research Decision

本次不做外部研究。原因是该计划要解决的是仓库本地组织、命令面、skill 入口和质量边界，而不是外部依赖选型；来源文档已经给出了足够明确的产品和工程方向，且 scope boundary 明确排除了“本次决定具体使用哪些 Python 库、测试框架、lint 工具或 CI 平台” `(see origin: docs/brainstorms/2026-03-19-agent-first-project-organization-requirements.md)`。

## Proposed Solution

建立一套“仓库内 skill + 单一主 CLI + 明确文档层级 + 分层测试目录 + 本地质量聚合入口 + 两条黄金路径 e2e”的工程骨架。

高层设计如下：

1. 在仓库内维护一个项目专属 skill，作为 Codex 进入仓库后的首个工作流入口，说明软件用途、核心命令、推荐工作流程和边界。
2. 用单一主 CLI 作为 Agent 默认可执行入口，但业务能力只暴露两个主命名空间：`conference` 和 `arxiv`。
3. 将“用户偏好筛选/推荐”定义为两条业务链路中的共享阶段能力，而不是独立子产品。
4. 用统一任务运行器脚本聚合开发、检查、测试和 e2e 命令，但不把它作为对外 API。
5. 把文档按“Agent 首读 skill / Agent 首读文档 / 开发规则 / 计划与沉淀”分层，缩短 Agent onboarding 路径。
6. 把测试分为单元、集成、e2e 三层，并定义质量门禁命令的执行顺序和失败反馈格式。
7. 为“顶会筛选”和“arXiv 日更筛选”分别建立黄金路径 e2e，满足人类演示与回归验证。

这个方案分别响应来源文档中的未决点：

- 统一命令入口：采用“仓库内 skill 负责说明，单一主 CLI 负责执行，辅助任务运行器负责开发便利”的三层结构，而不是多个对外 CLI 并列。
- Agent 首读入口：建立“AGENTS.md 指向 repo skill，repo skill 再指向核心文档与 CLI”的固定入口链。
- 质量门禁执行顺序：先快后慢，先静态后动态，失败即停并输出下一步建议。
- e2e 报告格式：终端为即时输出，Markdown/JSON 为落盘格式，三者并存但以 CLI 文本为主。
- CLI 子命令边界：按稳定输入来源划分为 `conference` 与 `arxiv`，而不是把“推荐”单独切成第三个业务域。
- 编码与终端兼容：统一 UTF-8、固定文本快照策略、明确 Windows 终端假设。

## Technical Approach

### Architecture

建议的工程骨架如下：

```text
repo/
  AGENTS.md
  README.md
  .codex/
    skills/
      paper-analysis/
        SKILL.md
        references/
          workflow.md
          command-surface.md
  pyproject.toml
  paper_analysis/
    cli/
      __init__.py
      main.py
      conference.py
      arxiv.py
      quality.py
      report.py
    domain/
      paper.py
      preference.py
      filtering.py
    services/
      conference_pipeline.py
      arxiv_pipeline.py
      preference_ranker.py
      report_writer.py
    pipelines/
    shared/
  tests/
    unit/
    integration/
    e2e/
    fixtures/
    snapshots/
  scripts/
    quality/
    e2e/
  docs/
    agent-guide/
    engineering/
    plans/
    brainstorms/
    solutions/
```

关键结构说明：

- `.codex/skills/paper-analysis/SKILL.md`：仓库内维护的项目 skill，Codex 进入仓库后应优先读取；它负责把项目目标、推荐命令、执行顺序和常见工作流压缩成稳定入口。
- `paper_analysis/cli/conference.py`：顶会论文筛选命令入口。
- `paper_analysis/cli/arxiv.py`：arXiv 日更筛选命令入口。
- 不设置单独的 `recommend.py` 业务入口；偏好筛选和排序由共享服务层承担。
- `domain/preference.py` 与 `domain/filtering.py`：承载用户偏好和筛选规则的共享建模。
- `services/preference_ranker.py`：承载“符合用户偏好”的共用逻辑，服务于 conference/arxiv 两条链路。
- `tests/unit/`、`tests/integration/`、`tests/e2e/`：对应 R4 的测试分层 `(see origin: docs/brainstorms/2026-03-19-agent-first-project-organization-requirements.md)`。

### Agent Exposure Design

对 Agent 的暴露方式采用三层：

- 第一层是 [AGENTS.md](D:\Git_Repo\Paper-Analysis-New\AGENTS.md)，负责告诉 Codex 进入仓库后需要优先读取 repo skill。
- 第二层是 repo skill，负责“告诉 Agent 应该做什么、先读什么、常用命令是什么、不同任务走哪条流程”。
- 第三层是主 CLI，负责“真正执行稳定动作”。

skill 中应明确说明：

- 业务功能只有两类：顶会筛选、arXiv 日更筛选。
- “推荐”是筛选链路的一个内部阶段，不是独立的 CLI 产品面。
- Agent 不应主动创造第三个业务命名空间。

### Command Surface Design

对外执行面只暴露一个主 CLI，例如：

```text
python -m paper_analysis.cli.main <namespace> <action> [options]
```

首批稳定子命令建议如下：

- `conference filter`：从指定顶会论文集合中筛选符合用户偏好的论文
- `conference report`：输出顶会筛选结果报告
- `arxiv daily-filter`：从 arXiv 每日更新中筛选符合用户偏好的论文
- `arxiv report`：输出 arXiv 日更筛选结果报告
- `quality local-ci`：聚合质量门禁入口
- `report show`：查看最近一次文本报告或产物索引

设计原则：

- 子命令按稳定输入来源和任务动作划分，不按“推荐/排序”这类内部阶段划分。
- 每个子命令都支持结构化输入参数和结构化文本输出。
- 每个子命令都支持 `--help`，并在帮助文本里说明输入、输出和失败语义。
- repo skill 中给出的命令示例必须与 CLI 帮助文本保持一致，避免两套真相。

### Shared Filtering Model

“符合用户偏好”的逻辑应该被设计为共享能力，而不是第三条业务链路。建议统一抽象为：

```text
input source -> candidate papers -> preference filtering/ranking -> report output
```

两条具体链路分别是：

- `conference source -> conference candidate papers -> preference filtering/ranking -> conference report`
- `arxiv daily source -> arxiv candidate papers -> preference filtering/ranking -> arxiv report`

这样做的收益：

- 避免 conference/arxiv 各自实现一套偏好筛选逻辑。
- 避免将来出现“recommend CLI”与上游来源 CLI 责任重叠。
- 更符合你现在定义的产品边界：只有两个业务功能，推荐只是内部计算步骤。

### Documentation Layering

Agent 首读入口建议分两步：

1. 先读 `.codex/skills/paper-analysis/SKILL.md`
2. 再按 skill 指引读取以下核心文档

Agent 首读文档集合建议最少包含：

1. [AGENTS.md](D:\Git_Repo\Paper-Analysis-New\AGENTS.md)
2. `docs/agent-guide/quickstart.md`
3. `docs/agent-guide/command-surface.md`
4. `docs/engineering/testing-and-quality.md`
5. `docs/engineering/encoding-and-output.md`

skill 与文档职责：

- `SKILL.md`：定义软件用途、两类业务功能、推荐工作流、命令选择规则、遇到不同任务时该先做什么。
- `references/workflow.md`：补充“顶会筛选”和“arXiv 日更筛选”的工作流说明。
- `references/command-surface.md`：给 skill 引用的命令面摘要，明确只有 `conference` 和 `arxiv` 两个业务命名空间。
- `quickstart.md`：3 分钟内说明项目目标、最关键命令、执行顺序，供人类和 skill 共同引用。
- `command-surface.md`：定义所有稳定 CLI 的输入输出约定和边界。

### Quality Gate Design

本地质量门禁采用统一入口：

```text
python -m paper_analysis.cli.main quality local-ci
```

执行顺序建议如下：

1. `lint`
2. `typecheck`
3. `unit`
4. `integration`
5. `e2e`

其中 `integration` 和 `e2e` 至少覆盖两条业务路径：

- 顶会筛选
- arXiv 日更筛选

失败反馈格式建议统一为：

```text
[FAIL] stage=integration
summary: conference filter pipeline returned unstable schema
next: run `python -m paper_analysis.cli.main quality integration --verbose`
artifact: reports/quality/integration-latest.txt
```

### E2E Reporting Strategy

两条 e2e 报告都采用三层输出：

- 终端：简短过程摘要与最终筛选结果
- Markdown：人类可读的演示产物
- JSON：结构化结果，便于脚本比较和自动化回归

落盘建议：

```text
artifacts/
  e2e/
    conference/
      latest/
        summary.md
        result.json
        stdout.txt
    arxiv/
      latest/
        summary.md
        result.json
        stdout.txt
```

### Encoding and Snapshot Strategy

为满足中文优先且避免乱码：

- 所有文档、代码和测试快照统一使用 UTF-8。
- repo skill 与其 references 也必须使用 UTF-8，避免 Agent 首入口就出现乱码。
- 快照测试只比较稳定文本字段，动态时间戳、随机数、网络元数据需要先规范化。
- e2e 文本产物中固定标题、阶段名、字段顺序，避免中文输出因环境差异导致快照漂移。

### Implementation Phases

#### Phase 1: Foundation Skeleton

目标：建立最小可运行骨架。

交付物：

- `.codex/skills/paper-analysis/` skill 结构
- `AGENTS.md -> repo skill -> docs/CLI` 的入口链
- 主 CLI 入口与 `conference` / `arxiv` 命名空间骨架
- 偏好筛选共享域模型骨架
- `docs/agent-guide/` 与 `docs/engineering/` 首批核心文档
- `tests/` 分层目录和最小样例测试
- `docs/solutions/` 占位结构

完成标准：

- Agent 进入仓库后能先通过 repo skill 找到正确工作流，再跳转到 CLI 或文档。
- CLI 帮助文本中明确只有两条业务入口：`conference` 与 `arxiv`。
- `AGENTS.md` 中明确告知 Codex 需要优先加载 repo skill。

#### Phase 2: Quality Gate Backbone

目标：让“本地 CI”从概念变成真实命令。

交付物：

- `quality local-ci` 聚合命令
- `lint`、`typecheck`、`unit`、`integration`、`e2e` 子阶段入口
- 顶会筛选与 arXiv 日更筛选的基础集成验证
- 标准失败输出模板
- `artifacts/quality/` 产物目录约定

#### Phase 3: Dual Golden Path E2E

目标：打通两个可展示的业务黄金路径。

交付物：

- 一个固定输入的顶会筛选 e2e 场景
- 一个固定输入的 arXiv 日更筛选 e2e 场景
- 两条路径各自的终端摘要输出
- 两条路径各自的 Markdown/JSON 产物
- `tests/e2e/` 回归验证

#### Phase 4: Extension Rules

目标：把骨架固定成团队规则。

交付物：

- “新增顶会来源接入”的扩展指南
- “新增 arXiv 筛选规则”的扩展指南
- “新增测试层级”的模板或约定
- repo skill 的维护规范，明确何时更新 `SKILL.md` 与 references
- 计划到执行的工作流说明

## Alternative Approaches Considered

### 方案 A：把推荐做成独立业务命名空间

做法：单独提供 `recommend` CLI，与 `conference` 和 `arxiv` 并列。

不采纳原因：

- 与你当前明确的产品定义冲突。你已经把产品能力收敛为两个功能，而不是三个。
- 会把“偏好筛选”这个内部共享步骤误暴露为第三个业务面。
- 容易造成 conference/arxiv 与 recommend 的职责重叠，命令和测试都变得模糊。

### 方案 B：按业务域直接建目录，但每条链路各自实现偏好逻辑

做法：`conference` 和 `arxiv` 各自维护自己的筛选逻辑。

不采纳原因：

- 会导致偏好模型、排序规则和输出格式重复实现。
- 后续用户偏好变化时，需要双份修改和双份验证。

### 方案 C：只有 AGENTS.md，没有 repo skill

做法：把所有 Agent 使用说明都堆在 `AGENTS.md` 中，不维护仓库内 skill。

不采纳原因：

- `AGENTS.md` 更适合短规则和仓库约束，不适合承载持续增长的工作流说明。
- 缺少专门的 skill 结构后，无法为 Codex 提供分层引用和可扩展的工作流文档。

## System-Wide Impact

### Interaction Graph

核心链路应收敛为：

`Agent/人类 -> AGENTS.md -> repo skill -> conference/arxiv CLI -> source pipeline -> preference filtering/ranking -> report writer -> artifacts/tests`

### Integration Test Scenarios

必须覆盖的跨层场景：

1. Agent 按 `AGENTS.md` 指引能定位 repo skill，并从 skill 中找到正确 CLI 命令。
2. 顶会筛选链路能从固定论文集合中输出符合偏好的结果。
3. arXiv 日更筛选链路能从固定日更样例中输出符合偏好的结果。
4. 两条链路共享同一偏好筛选模型，但输出上下文正确区分。
5. 中文输入、中文输出、中文文档与 skill 快照在 Windows 环境下不乱码。

## Acceptance Criteria

### Functional Requirements

- [ ] 仓库存在一个 repo-local skill，能让 Codex 进入仓库后理解软件用途、命令面与推荐工作流。
- [ ] 仓库存在一个稳定主 CLI，业务命名空间只包含 `conference` 与 `arxiv`。
- [ ] 偏好筛选逻辑作为共享能力被两条业务链路复用，而不是作为独立产品入口暴露。
- [ ] `quality local-ci` 可统一触发 lint、typecheck、unit、integration、e2e。
- [ ] 至少存在一条顶会筛选 e2e 和一条 arXiv 日更筛选 e2e。
- [ ] 新增来源或筛选规则时有明确模板，要求同步更新 skill 或其 references。

### Non-Functional Requirements

- [ ] 所有文档、skill 与文本产物默认使用 UTF-8。
- [ ] CLI 失败输出具有统一字段与可读性。
- [ ] 测试分层结构清晰，执行时间可按阶段拆分。
- [ ] 终端输出对中文用户和 Agent 都可直接消费。

### Quality Gates

- [ ] 本地标准门禁命令存在且可单次执行。
- [ ] 单元、集成、e2e 分层至少各有一个样例验证。
- [ ] skill、文档与 CLI 帮助文本保持一致。
- [ ] 两条业务黄金路径的报告产物路径和文件名固定、可预测。

## Success Metrics

- 新 Agent 在 10 分钟内可以通过 repo skill 与核心文档区分两条业务功能，并运行对应帮助命令。
- 人类开发者在一次命令执行后可准确知道失败阶段与下一步排查命令。
- 顶会筛选与 arXiv 日更筛选各自都有可展示的文本报告与回归基线。
- 新业务演进不会把“推荐”再次误建成独立产品面。

## Dependencies & Prerequisites

- 需要在执行阶段确定 Codex 读取 repo skill 的触发方式，并在 [AGENTS.md](D:\Git_Repo\Paper-Analysis-New\AGENTS.md) 中固定引用约定。
- 需要至少一份稳定顶会样例数据和一份稳定 arXiv 日更样例数据。
- 需要在执行阶段选定具体 Python 打包、CLI、测试、lint、typecheck 工具。
- 需要在 Windows 环境验证 UTF-8 输出与终端兼容性。

## Risk Analysis & Mitigation

- **风险**: 未来又把“推荐”单独抽成第三个业务入口。
  - **缓解**: 在 skill、命令面文档和扩展指南中明确推荐只是内部共享阶段。
- **风险**: conference/arxiv 各自复制一份偏好逻辑。
  - **缓解**: 共享偏好域模型和 ranking 服务，测试中验证两条链路复用同一核心逻辑。
- **风险**: skill 存在，但 `AGENTS.md` 未强制指向，导致实际不会被读取。
  - **缓解**: 在第一阶段就把 skill 引用写入 `AGENTS.md`，并纳入 review checklist。

## Documentation Plan

执行本计划时至少要新增或更新以下文档：

- [AGENTS.md](D:\Git_Repo\Paper-Analysis-New\AGENTS.md)
- `.codex/skills/paper-analysis/SKILL.md`
- `.codex/skills/paper-analysis/references/workflow.md`
- `.codex/skills/paper-analysis/references/command-surface.md`
- [README.md](D:\Git_Repo\Paper-Analysis-New\README.md)
- `docs/agent-guide/quickstart.md`
- `docs/agent-guide/command-surface.md`
- `docs/engineering/testing-and-quality.md`
- `docs/engineering/encoding-and-output.md`
- `docs/engineering/extending-cli.md`
- `docs/solutions/README.md`

## Sources & References

### Origin

- **Origin document:** [docs/brainstorms/2026-03-19-agent-first-project-organization-requirements.md](D:\Git_Repo\Paper-Analysis-New\docs\brainstorms\2026-03-19-agent-first-project-organization-requirements.md)
  - Carried-forward decisions: 工程能力优先、Agent 优先、标准门禁、CLI 文本报告。

### Internal References

- [AGENTS.md](D:\Git_Repo\Paper-Analysis-New\AGENTS.md)
- [README.md](D:\Git_Repo\Paper-Analysis-New\README.md)

### External References

- 本计划未引入外部资料；后续执行阶段如涉及具体工具选型，再按需要补充官方文档。

### Related Work

- 当前无既有计划、issue、PR 或历史解决方案可引用。

