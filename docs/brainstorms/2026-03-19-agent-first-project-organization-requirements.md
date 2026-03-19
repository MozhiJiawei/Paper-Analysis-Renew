---
date: 2026-03-19
topic: agent-first-project-organization
---

# Agent-First Project Organization

## Problem Frame

这个项目的目标不是单纯实现若干 Python 功能，而是构建一个可被 Agent 稳定理解、调用、验证和扩展的工程系统。
如果项目结构、文档、测试入口和质量门禁缺乏统一约束，后续即使功能可用，也会出现以下问题：

- Agent 难以判断应该从哪个入口执行任务
- 人类难以快速验证一次完整分析链路是否真实可用
- 合入前缺乏稳定的本地质量看护，容易把低质量改动带入主线

本次需求聚焦于定义项目的组织原则与质量基线，使后续实现论文推荐、顶会分析、arXiv 每日分析时，都落在一致的工程框架内。

## Requirements

- R1. 项目应采用“工程能力优先”的组织方式，优先围绕 CLI、pipeline、testing、docs、quality gates 等工程能力分层，而不是先按业务主题堆叠目录。
- R2. 项目应以 Agent 为默认操作者进行设计，所有关键能力都需要有清晰、稳定、可脚本调用的 CLI 入口。
- R3. 项目文档应优先服务 Agent 理解与执行，明确项目目标、目录职责、核心命令、任务边界、输入输出约定和质量门禁。
- R4. 测试体系应覆盖 lint、类型检查、单元测试、集成测试和关键 CLI 的 e2e 验证，并能在本地一次性执行。
- R5. e2e 结果应以 CLI 文本报告为主要展示形式，允许人类直接查看终端输出或生成的 Markdown/JSON 报告。
- R6. 合入前应提供本地质量看护能力，至少能够在提交或合并前统一执行标准门禁，并对失败原因给出明确反馈。
- R7. 项目中的明确子任务应尽可能封装为独立 Python CLI 工具或子命令，减少运行时由大模型自由发挥带来的不确定性。
- R8. 文档与测试产物应尽可能使用中文，并明确编码约束，避免中文乱码影响 Agent 与人类协作。

## Success Criteria

- 新加入的 Agent 能在阅读少量核心文档后，知道项目如何运行、如何测试、如何新增一个能力。
- 人类开发者可以通过一个统一命令执行标准质量门禁，并看到明确的失败定位。
- 至少一个关键业务链路可以通过 CLI e2e 命令展示完整输入、处理过程摘要和最终结果。
- 后续新增业务能力时，不需要重新发明文档格式、测试入口或质量检查方式。

## Scope Boundaries

- 本次不决定具体使用哪些 Python 库、测试框架、lint 工具或 CI 平台。
- 本次不定义论文推荐、顶会分析、arXiv 分析的详细产品行为。
- 本次不展开具体目录树、文件命名和模块实现细节。
- 本次不要求引入图形界面或 HTML 报告体系。

## Key Decisions

- 工程能力优先: 先建立统一工程框架，再承载具体业务能力，避免项目过早被业务目录主导。
- Agent 优先: 将 CLI、文档和任务边界设计成 Agent 默认可执行形态，减少额外解释成本。
- 标准门禁: 合入前门禁至少覆盖 lint、类型检查、单元测试、集成测试和关键 e2e，而不是只做基础静态检查。
- CLI 文本报告: e2e 展示以终端和文本产物为主，优先保证可自动化、可读性和低维护成本。

## Dependencies / Assumptions

- 后续实现阶段会补充一套统一命令入口，用于运行开发命令、质量检查和 e2e 验证。
- 至少会定义一个“黄金路径”业务场景，作为首个 e2e 展示链路。
- 项目会持续以 Python 为主语言，并接受通过 CLI 暴露核心能力的设计约束。

## Outstanding Questions

### Deferred to Planning

- [Affects R1,R2,R6][Technical] 统一命令入口采用何种形式组织，例如单一总 CLI、任务运行器还是两者结合。
- [Affects R3][Technical] Agent 首读文档集合应包含哪些核心文档，以及它们之间如何分层。
- [Affects R4,R6][Technical] 本地质量门禁的执行顺序、耗时分层和失败反馈格式应如何设计。
- [Affects R5][Needs research] e2e CLI 文本报告应输出到终端、Markdown、JSON 还是多格式并存。
- [Affects R7][Technical] CLI 子命令边界如何划分，既保持稳定又避免过度切碎。
- [Affects R8][Technical] 中文文档与输出的编码、终端兼容性和快照验证策略如何统一。

## Next Steps

→ /prompts:ce-plan for structured implementation planning
