---
title: fix: 修复 Codex 仓库 skill 加载并补齐自然语言操作入口
type: fix
status: completed
date: 2026-03-21
origin: docs/brainstorms/2026-03-19-agent-first-project-organization-requirements.md
---

# fix: 修复 Codex 仓库 skill 加载并补齐自然语言操作入口

## Overview

本计划聚焦修复一个直接阻断仓库可用性的问题：仓库内虽然存在 repo-local skill，但它目前还没有被明确建模成符合 Codex 原生发现与加载机制的 skill 资产，因此 Codex 不能稳定地在不依赖 [AGENTS.md](D:\Git_Repo\Paper-Analysis-New\AGENTS.md) 的前提下发现它、加载它，并把自然语言请求映射到正确 CLI，导致人类无法顺畅地通过自然语言驱动 Codex 使用该软件。

这项工作继承来源文档里已经确定的四个核心方向：工程能力优先、Agent 优先、标准门禁、CLI 文本报告 `(see origin: docs/brainstorms/2026-03-19-agent-first-project-organization-requirements.md)`。本次不会新增第三个业务命名空间，也不会把“推荐”抽成独立产品面；修复目标是让 Codex 更稳定地走到现有 `conference`、`arxiv`、`quality`、`report` 命令面。

## Problem Statement / Motivation

当前仓库已经具备基本的 Agent-first 工程骨架，但“仓库里有 `.codex/skills/paper-analysis/SKILL.md`”并不等于“它已经是一个 Codex 能原生发现和正确触发的 skill”。当前落差主要体现在：

- [.codex/skills/paper-analysis/SKILL.md](D:\Git_Repo\Paper-Analysis-New\.codex\skills\paper-analysis\SKILL.md) 虽然有基础 frontmatter，但当前内容更像命令速查表，缺少足够清晰的触发描述、意图映射、任务分流、失败回退和自然语言示例。
- skill 目录当前没有 `agents/openai.yaml`，这会削弱它在 Codex UI 与技能发现层的完整性。
- `quickstart`、`command-surface`、`extending-cli` 分别描述了文档入口、命令边界和扩展规则，但没有为“人类直接对 Codex 说一句自然语言”提供统一的操作协议。
- Windows / UTF-8 已经是仓库明确约束；如果 Codex 在加载 skill 或引用文档时出现编码、入口歧义或帮助文本不一致，用户体验会快速崩掉。

结果是：仓库对维护者来说是“有文档的”，但对第一次进入仓库的 Codex 来说并不一定是“能原生发现 skill 并立即正确执行的”。这个问题直接违背了来源文档里的成功标准：新加入的 Agent 应该在阅读少量核心文档后知道如何运行、如何测试、如何新增能力 `(see origin: docs/brainstorms/2026-03-19-agent-first-project-organization-requirements.md)`。

## Research Summary

### Origin Document Findings

已找到相关来源文档 [docs/brainstorms/2026-03-19-agent-first-project-organization-requirements.md](D:\Git_Repo\Paper-Analysis-New\docs\brainstorms\2026-03-19-agent-first-project-organization-requirements.md)，且仍在 14 天窗口内，主题与当前问题高度相关，因此作为本计划的主要输入。来源文档中与本计划直接相关的结论包括：

- 项目必须以 Agent 为默认操作者设计，所有关键能力都要有清晰稳定的 CLI 入口 `(see origin: docs/brainstorms/2026-03-19-agent-first-project-organization-requirements.md)`。
- 项目文档应优先服务 Agent 理解与执行，明确项目目标、目录职责、核心命令、任务边界、输入输出约定和质量门禁 `(see origin: docs/brainstorms/2026-03-19-agent-first-project-organization-requirements.md)`。
- 中文与 UTF-8 兼容性属于显式工程约束，不是附带优化 `(see origin: docs/brainstorms/2026-03-19-agent-first-project-organization-requirements.md)`。

来源文档中的 `Outstanding Questions` 没有 `Resolve Before Planning` 阻塞项，因此可以继续规划。

### Local Repository Findings

- [README.md](D:\Git_Repo\Paper-Analysis-New\README.md) 已经把仓库定位为“面向 Codex / Agent 的论文筛选基础仓库”，并明确两条业务链路：顶会筛选与 arXiv 日更筛选。
- [docs/agent-guide/quickstart.md](D:\Git_Repo\Paper-Analysis-New\docs\agent-guide\quickstart.md) 与 [docs/agent-guide/command-surface.md](D:\Git_Repo\Paper-Analysis-New\docs\agent-guide\command-surface.md) 已经定义稳定命令面，但更偏“给知道命令的人查阅”，而不是“把自然语言任务翻译成命令”的指导。
- [paper_analysis/cli/main.py](D:\Git_Repo\Paper-Analysis-New\paper_analysis\cli\main.py) 的主入口清晰，顶层命名空间固定为 `conference`、`arxiv`、`quality`、`report`。这说明命令执行层是稳定的，问题主要集中在 Codex 入口层和任务解释层，而不是核心 CLI 架构。
- 从 Codex skill 规范看，`SKILL.md` 的 `name` 与 `description` 是技能被发现和触发的主入口；body 只有在技能被触发后才会加载。这意味着当前 skill 的核心问题不是“有没有说明”，而是 `description` 是否足够支撑自动发现，以及整体目录是否符合 Codex 推荐结构。
- Codex skill 推荐结构除 `SKILL.md` 外，还建议补 `agents/openai.yaml` 作为 UI 元数据层。当前仓库的 `paper-analysis` skill 目录缺少这部分资产。
- [.codex/skills/paper-analysis/SKILL.md](D:\Git_Repo\Paper-Analysis-New\.codex\skills\paper-analysis\SKILL.md) 已说明软件边界、推荐工作流与任务路由，但对“什么自然语言会触发该 skill”“自然语言例句 -> 应走哪个命令 -> 是否需要进一步追问 -> 默认假设是什么”尚未形成明确模板。
- [docs/engineering/testing-and-quality.md](D:\Git_Repo\Paper-Analysis-New\docs\engineering\testing-and-quality.md) 与 [docs/engineering/encoding-and-output.md](D:\Git_Repo\Paper-Analysis-New\docs\engineering\encoding-and-output.md) 已将联网 e2e、UTF-8、质量产物路径固定下来，可作为本计划的验证与回归基线。

### Institutional Learnings

找到一份高度相关的经验文档：[docs/solutions/integration-issues/cli-structured-failure-and-windows-utf8-compatibility.md](D:\Git_Repo\Paper-Analysis-New\docs\solutions\integration-issues\cli-structured-failure-and-windows-utf8-compatibility.md)。

关键启发：

- 问题往往不在 happy path，而在“边界层有没有稳定语义”。
- Windows 下 UTF-8 兼容要被当成显式契约处理，而不是寄希望于环境默认值。
- CLI 的失败路径也属于公共接口，必须被文档化和测试化。

这些 learnings 可以直接迁移到当前问题：repo skill 与 AGENTS 也是边界层，它们同样需要稳定语义、默认假设和失败回退。

### External Research Decision

本次不做外部研究。原因是问题主要发生在仓库本地的 Agent 暴露层、文档契约和任务路由层，仓库已有足够清晰的本地约束与既有实现模式；当前最需要的是统一入口与一致性，而不是引入新的外部方案。

## Proposed Solution

修复方案采用“skill 原生格式修复 + 自然语言触发描述补齐 + CLI 一致性校验 + 真实回归验证”四段式设计。

### 1. 修复 skill 原生格式与发现元数据

把 [.codex/skills/paper-analysis/SKILL.md](D:\Git_Repo\Paper-Analysis-New\.codex\skills\paper-analysis\SKILL.md) 与 skill 目录结构从“仓库自定义说明文件”提升为“符合 Codex 原生 skill 发现机制的技能资产”：

- 校验并收紧 frontmatter，只保留 Codex 识别真正依赖的字段，并确保 `description` 直接包含“做什么”和“何时使用”的触发信息。
- 为 skill 增加 `agents/openai.yaml`，补齐技能列表与 UI 发现所需的人类可读元数据。
- repo skill 要在前部明确三件事：
  - 这个软件支持哪两条业务链路
  - 人类常见自然语言请求会被如何分流
  - 默认先尝试哪些稳定命令，不应发明哪些新命名空间

### 2. 增加自然语言触发与任务路由层

在 repo skill 或其 reference 文档中新增一个面向 Codex 的“自然语言到命令”的稳定映射层，覆盖至少四类意图：

- 顶会筛选类请求
- arXiv 日更 / 订阅类请求
- 质量检查 / 回归验证类请求
- 最近报告查看类请求

映射层需要明确：

- 常见中文自然语言表达示例
- 对应的稳定 CLI 命令
- 缺少参数时的默认处理方式
- 哪些情况下必须向用户追问
- 哪些情况下只能在现有 `conference` / `arxiv` 命名空间内扩展，不能新增 `recommend`

### 3. 让文档、skill、CLI `--help` 形成单一真相

当前命令面本身较稳定，但帮助文档与自然语言路由没有形成完整闭环。本计划要求：

- 若 skill 中出现稳定命令示例，必须能在 CLI `--help` 中找到同名入口和一致语义。
- `quickstart` 应增加“自然语言与 Codex 对话时，Codex 预期会怎么选命令”的解释。
- `command-surface` 应补足面向 Agent 的“意图 -> 命名空间/动作”摘要。
- `extending-cli` 应增加一条规则：任何新增命令或修改命令语义时，都要同步更新自然语言路由示例与入口文档。

### 4. 为 skill 发现与自然语言入口增加回归验证

当前测试已覆盖 CLI 成功与失败路径，但尚未显式覆盖“skill 是否符合 Codex 原生发现格式”和“仓库入口是否足以让 Codex 正确路由任务”。需要新增一组轻量、可自动化的回归：

- skill 结构校验：`SKILL.md` frontmatter 合法，`description` 非空且包含足够的触发语义，`agents/openai.yaml` 存在且与 `SKILL.md` 一致。
- 文档一致性校验：skill、agent-guide、CLI `--help` 中的稳定命令面一致。
- 引用校验：skill references 路径存在、内容编码为 UTF-8、引用关系不悬空。
- 自然语言样例校验：至少维护一组自然语言示例与预期命令映射，避免后续文档漂移。

## Technical Considerations

- 不新增业务命名空间。自然语言入口只负责把任务映射到现有命令面，不负责引入新的产品边界。
- `SKILL.md` 的 frontmatter 必须被视为产品级接口，而不是普通文档元信息，因为它决定 skill 能否被 Codex 发现。
- 优先复用现有文档树。除非现有结构放不下，否则不新增过多文档层级；更好的方式是在 skill references 或 `docs/agent-guide/` 中增加一份专门的路由说明。
- 编码必须继续遵守 UTF-8 契约，避免 Windows 下再出现“文件内容正确但显示链路失真”的协作问题。
- 自然语言映射要尽量规则化，而不是写成大量不稳定 prose，否则之后难以验证一致性。

## System-Wide Impact

### Interaction Graph

目标链路应收敛为：

`人类自然语言 -> Codex 原生发现 repo skill -> 加载 SKILL.md / references -> 根据自然语言路由规则选择 conference/arxiv/quality/report -> CLI 执行 -> 结构化输出 / 报告产物`

需要至少向下追踪两层：

- “帮我看看今天 arXiv 有什么 AI 论文” -> `arxiv report` 或 `arxiv daily-filter` -> `ArxivPipeline` -> `subscription_loader/api_client` -> 报告产物
- “帮我筛一下 ICLR 2025 里符合我偏好的论文” -> `conference filter/report` -> `ConferencePipeline` -> `paperlists_loader/parser` -> 报告产物

### Error & Failure Propagation

- 如果 skill 没有被原生发现，整个自然语言工作流会在入口前就失效，因此 skill 元数据缺陷必须被视为高优先级故障。
- 如果 Codex 无法从自然语言判断命令，应在入口层给出有限追问，而不是直接猜出新的命名空间。
- 如果文档引用断裂或帮助文本不一致，应由质量检查或一致性测试尽早失败。
- 如果 CLI 缺少某个 skill 中承诺的参数或行为，应视为命令面回归，而不是文档小问题。

### State Lifecycle Risks

- skill 发现层漂移的风险高于代码层漂移：一旦 `SKILL.md` frontmatter、`agents/openai.yaml`、skill references、`quickstart`、`--help` 不一致，Codex 就会出现“仓库里有 skill，但实际不会触发”的状态。
- 自然语言示例如果没有自动校验，很容易在后续命令面迭代中失效。

### API Surface Parity

需要保持一致的接口包括：

- [AGENTS.md](D:\Git_Repo\Paper-Analysis-New\AGENTS.md)
- [.codex/skills/paper-analysis/SKILL.md](D:\Git_Repo\Paper-Analysis-New\.codex\skills\paper-analysis\SKILL.md)
- `.codex/skills/paper-analysis/agents/openai.yaml`
- [.codex/skills/paper-analysis/references/command-surface.md](D:\Git_Repo\Paper-Analysis-New\.codex\skills\paper-analysis\references\command-surface.md)
- [.codex/skills/paper-analysis/references/workflow.md](D:\Git_Repo\Paper-Analysis-New\.codex\skills\paper-analysis\references\workflow.md)
- [docs/agent-guide/quickstart.md](D:\Git_Repo\Paper-Analysis-New\docs\agent-guide\quickstart.md)
- [docs/agent-guide/command-surface.md](D:\Git_Repo\Paper-Analysis-New\docs\agent-guide\command-surface.md)
- CLI `--help`

### Integration Test Scenarios

至少需要以下跨层场景：

1. Codex 无需依赖 `AGENTS.md`，也能原生发现并加载 `paper-analysis` skill。
2. 用户说“帮我筛 ICLR 2025 论文”，路由说明能把任务导向 `conference` 相关命令，而不是发明新入口。
3. 用户说“帮我看今天的 arXiv AI 更新”，路由说明能把任务导向 `arxiv` 相关命令，并保留对缺失参数的追问策略。
4. 用户说“跑一下本地检查”，路由说明能稳定导向 `quality local-ci`。
5. `SKILL.md`、`agents/openai.yaml` 与参考文档在 Windows 环境读取时不乱码，且路径引用有效。
6. `codex exec` 在 prompt 不直接点名 skill 的情况下，也能自然发现 repo-local skill，并完成最简单的 `arxiv report` 联网任务。

## SpecFlow Analysis

### User Flow Overview

1. 首次进入仓库的 Codex 原生发现 repo-local skill。
2. Codex 读取 `SKILL.md`，理解两条业务链路、命令边界与禁止事项。
3. 人类用自然语言提出任务。
4. Codex 根据路由规则判断应走 `conference`、`arxiv`、`quality` 还是 `report`。
5. 若参数充分，Codex 直接运行稳定命令；若参数不足，仅追问必要信息。
6. 命令执行后输出结构化结果，必要时产出报告或质量工件。

### Missing Elements & Gaps

- **Category**: Natural Language Routing
  - **Gap Description**: 当前缺少自然语言示例到稳定命令的显式映射。
  - **Impact**: Codex 容易知道“仓库里有什么”，却不知道“该怎么从人话落到命令”。
  - **Current Ambiguity**: 缺少默认假设、最小追问原则和路由边界。

- **Category**: Documentation Contract
  - **Gap Description**: skill 已存在，但其原生发现所依赖的 frontmatter 与元数据层尚未被测试化和一致性校验化。
  - **Impact**: 文档很容易逐步漂移，最终再次导致 skill 名存实亡。
  - **Current Ambiguity**: 目前没有自动化机制证明 `SKILL.md`、`agents/openai.yaml`、skill references、CLI `--help` 一致。

- **Category**: Failure Handling
  - **Gap Description**: 缺少“无法判断意图时怎么办”的入口层回退策略。
  - **Impact**: Codex 可能过度猜测，或反复问不必要的问题。
  - **Current Ambiguity**: 没有规定哪些问题必须追问，哪些可以带默认值执行。

### Critical Questions Requiring Clarification

本计划基于以下默认假设继续推进，执行前如需变更可再调整：

1. **Critical**: 这次修复不新增新的业务 CLI 命名空间。
   - Why it matters: 这关系到整个自然语言路由的稳定边界。
   - Default assumption: 所有人类自然语言请求都应被映射到现有 `conference`、`arxiv`、`quality`、`report`。

2. **Critical**: 这次修复以“让 skill 符合 Codex 原生 skill 格式并能被发现”为优先目标，而不是继续依赖 `AGENTS.md` 作为必经入口。
   - Why it matters: 如果 skill 不能被原生发现，再多入口文档也只是补丁。
   - Default assumption: `AGENTS.md` 可以保留为仓库约束文档，但不能成为 skill 加载成立的前提。

3. **Important**: 自然语言路由优先落在 skill/reference 文档层，而不是引入新的“聊天解析器”代码。
   - Why it matters: 当前问题更像入口契约问题，不是产品逻辑缺失。
   - Default assumption: 先修 skill 格式、文档契约和一致性校验，再评估是否需要代码层辅助。

4. **Important**: 需要新增一组文档或文本级回归，证明 skill 发现层与入口契约不会再次漂移。
   - Why it matters: 如果没有自动化保护，修复会很快失效。
   - Default assumption: 通过质量阶段纳入轻量校验，而不是人工约定。

## Acceptance Criteria

### Functional Requirements

- [ ] Codex 无需依赖 [AGENTS.md](D:\Git_Repo\Paper-Analysis-New\AGENTS.md)，也能原生发现并加载 [.codex/skills/paper-analysis/SKILL.md](D:\Git_Repo\Paper-Analysis-New\.codex\skills\paper-analysis\SKILL.md)。
- [ ] repo skill 符合 Codex skill 目录规范，至少包括合法 `SKILL.md` frontmatter，必要时补齐 `agents/openai.yaml`。
- [ ] repo skill 明确说明两条业务链路、稳定命令面、禁止新增 `recommend` 命名空间，以及自然语言任务分流规则。
- [ ] 至少覆盖四类自然语言意图：`conference`、`arxiv`、`quality`、`report`。
- [ ] 人类可以通过自然语言让 Codex 选择并执行现有软件能力，而不是必须手动提供完整 CLI。
- [ ] 修改命令面时，skill、agent-guide 文档与 CLI `--help` 能同步更新，形成单一真相。

### Non-Functional Requirements

- [ ] `SKILL.md`、`agents/openai.yaml`、references 与入口文档继续统一使用 UTF-8，Windows 下读取不乱码。
- [ ] 路由规则足够简洁，首读成本低，不要求 Codex 先通读大量工程文档才能工作。
- [ ] 当自然语言信息不足时，Codex 只做必要追问，避免过度交互。

### Quality Gates

- [ ] 新增 skill 结构 / skill 元数据 / 文档一致性校验，并纳入 `quality local-ci` 或其子阶段。
- [ ] 至少维护一组自然语言样例与预期命令映射的回归样本。
- [ ] 至少维护一条 Codex 黑盒自然语言 e2e：prompt 不显式指定 skill，验证 agent 读取 repo-local skill 并成功完成最简单的 arXiv 联网报告任务。
- [ ] 与本次修复相关的文档更新、帮助文本更新和测试更新同时提交。

## Success Metrics

- 新进入仓库的 Codex 能原生发现 repo skill，并用自然语言完成至少一条 `conference` 任务和一条 `arxiv` 任务的正确命令选择。
- 人类不需要记忆完整 CLI，只需描述目标，Codex 就能以稳定命令执行或提出最小必要追问。
- 后续命令面变更时，一致性校验能及时指出 skill 元数据 / 文档 / `--help` 漂移。

## Dependencies & Risks

### Dependencies

- 依赖现有稳定命令面继续保持在 `conference`、`arxiv`、`quality`、`report` 四个顶层命名空间内。
- 依赖 [docs/engineering/testing-and-quality.md](D:\Git_Repo\Paper-Analysis-New\docs\engineering\testing-and-quality.md) 中的质量门禁作为回归承载点。
- 依赖 UTF-8 规范继续作为首读文档的默认编码契约。
- 依赖 Codex skill 规范中对 `SKILL.md` frontmatter 和 `agents/openai.yaml` 的约束。

### Risks

- **风险**: 只更新 `SKILL.md`，不补 skill 元数据层或一致性校验，修复会变成局部补丁。
  - **缓解**: 把 `SKILL.md`、`agents/openai.yaml`、references、`quickstart`、`command-surface`、`--help` 全部纳入验收条件与一致性测试。

- **风险**: 继续把 `AGENTS.md` 当成 skill 加载前提，导致实际问题被掩盖。
  - **缓解**: 把这些文件全部纳入验收条件与一致性测试。

- **风险**: 自然语言映射写得过于宽泛，后续无法验证。
  - **缓解**: 用有限意图集、固定例句和预期命令输出做回归基线。

- **风险**: 误把当前问题理解成“需要新增自然语言产品层”。
  - **缓解**: 计划中明确此次只修 Agent 入口与路由契约，不新增第三条业务链路。

## Implementation Outline

### Phase 1: skill 格式诊断与契约收敛

- 盘点 `SKILL.md` frontmatter、skill 目录结构、`agents/openai.yaml`、references、agent-guide、CLI `--help` 的职责边界。
- 明确“skill 原生发现条件”“自然语言路由规则”“必须追问的参数缺口”三类契约。
- 冻结哪些信息放在 `SKILL.md` body，哪些放在 references，哪些放在 agent-guide，避免重复且不一致。

### Phase 2: 自然语言路由文档化

- 在 skill 或 reference 中新增自然语言任务路由说明。
- 用中文示例覆盖常见任务表达。
- 明确默认动作、禁止动作、必要追问与推荐命令。

### Phase 3: 文档与 CLI 一致性补齐

- 更新 `quickstart`、`command-surface`、`extending-cli` 与相关 `--help` 文案。
- 确保仓库中所有公开入口对命令面描述一致。

### Phase 4: 回归验证接入

- 增加 skill 结构合法性 / UTF-8 / 引用完整性检查。
- 增加自然语言样例到预期命令面的轻量回归。
- 纳入 `quality local-ci`，确保之后不会再次失真。

## Alternative Approaches Considered

### 方案 A：新增一个“自然语言”CLI 或 `recommend` 命名空间

不采纳原因：

- 与仓库边界冲突；当前产品面已经明确只有顶会与 arXiv 两条业务链路。
- 会把当前本质上的入口问题误建成新的产品表面。

### 方案 B：继续依赖 AGENTS.md 作为 skill 加载主入口

不采纳原因：

- 这不能解决“skill 是否符合 Codex 原生发现格式”的根问题。
- 会把产品级入口问题变成仓库局部约定，迁移性和稳定性都偏弱。

### 方案 C：完全依赖模型自由理解，不建立示例或路由规则

不采纳原因：

- 与来源文档的“减少模型自由发挥不确定性”原则冲突 `(see origin: docs/brainstorms/2026-03-19-agent-first-project-organization-requirements.md)`。
- 后续无法做自动化回归。

## Documentation Plan

本计划预计至少更新以下文件：

- [.codex/skills/paper-analysis/SKILL.md](D:\Git_Repo\Paper-Analysis-New\.codex\skills\paper-analysis\SKILL.md)
- `.codex/skills/paper-analysis/agents/openai.yaml`
- [.codex/skills/paper-analysis/references/workflow.md](D:\Git_Repo\Paper-Analysis-New\.codex\skills\paper-analysis\references\workflow.md)
- [.codex/skills/paper-analysis/references/command-surface.md](D:\Git_Repo\Paper-Analysis-New\.codex\skills\paper-analysis\references\command-surface.md)
- [docs/agent-guide/quickstart.md](D:\Git_Repo\Paper-Analysis-New\docs\agent-guide\quickstart.md)
- [docs/agent-guide/command-surface.md](D:\Git_Repo\Paper-Analysis-New\docs\agent-guide\command-surface.md)
- [docs/engineering/extending-cli.md](D:\Git_Repo\Paper-Analysis-New\docs\engineering\extending-cli.md)
- 如需补充专门的自然语言路由说明，则放在 skill `references/` 或 `docs/agent-guide/` 下，并由 `SKILL.md` 直接指向

## Sources & References

### Origin

- **Origin document:** [docs/brainstorms/2026-03-19-agent-first-project-organization-requirements.md](D:\Git_Repo\Paper-Analysis-New\docs\brainstorms\2026-03-19-agent-first-project-organization-requirements.md)
  - Carried-forward decisions: 工程能力优先、Agent 优先、标准门禁、CLI 文本报告。

### Internal References

- [.codex/skills/paper-analysis/SKILL.md](D:\Git_Repo\Paper-Analysis-New\.codex\skills\paper-analysis\SKILL.md)
- [docs/agent-guide/quickstart.md](D:\Git_Repo\Paper-Analysis-New\docs\agent-guide\quickstart.md)
- [docs/agent-guide/command-surface.md](D:\Git_Repo\Paper-Analysis-New\docs\agent-guide\command-surface.md)
- [docs/engineering/testing-and-quality.md](D:\Git_Repo\Paper-Analysis-New\docs\engineering\testing-and-quality.md)
- [docs/engineering/encoding-and-output.md](D:\Git_Repo\Paper-Analysis-New\docs\engineering\encoding-and-output.md)
- [docs/engineering/extending-cli.md](D:\Git_Repo\Paper-Analysis-New\docs\engineering\extending-cli.md)
- [paper_analysis/cli/main.py](D:\Git_Repo\Paper-Analysis-New\paper_analysis\cli\main.py)

### Institutional Learnings

- [docs/solutions/integration-issues/cli-structured-failure-and-windows-utf8-compatibility.md](D:\Git_Repo\Paper-Analysis-New\docs\solutions\integration-issues\cli-structured-failure-and-windows-utf8-compatibility.md)

### Related Work

- [docs/plans/2026-03-19-001-feat-agent-first-engineering-foundation-plan.md](D:\Git_Repo\Paper-Analysis-New\docs\plans\2026-03-19-001-feat-agent-first-engineering-foundation-plan.md)
