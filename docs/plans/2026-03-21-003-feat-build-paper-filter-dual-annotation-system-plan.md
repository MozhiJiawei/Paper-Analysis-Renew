---
title: feat: 构建论文筛选双人标注系统与评测集
type: feat
status: completed
date: 2026-03-21
origin: docs/brainstorms/2026-03-21-paper-filter-evaluation-taxonomy-requirements.md
---

# feat: 构建论文筛选双人标注系统与评测集

## Overview

本计划面向论文筛选离线评测基础设施，目标是在现有 `conference` / `arxiv` 两条业务链路之外，不新增新的顶层产品命名空间，而是在仓库内部补齐一套可持续迭代的双人标注系统、双标签数据资产、负样本分层与评测报告协议。计划直接继承来源文档已经确定的“双轴标签体系”“第一版聚焦推理优化”“研究对象采用中粒度主类”“显式负样本分层”等核心决策 `(see origin: docs/brainstorms/2026-03-21-paper-filter-evaluation-taxonomy-requirements.md)`。

这项工作解决的不是“如何立刻做更强推荐模型”，而是“如何先稳定产生高质量真值并衡量筛选算法是否更好”。因此第一阶段优先交付一个可运行的双人标注软件系统，其中标注员 A 为 `Codex_CLI`，标注员 B 为人类网页标注员；同时交付可合入主干的数据资产目录、标注规范、样本抽样协议与评测切分结构，让后续无论是规则、prompt 还是模型策略迭代，都能在统一评测基线下比较。

## Problem Statement

当前仓库已经具备 `conference`、`arxiv`、`report`、`quality` 等稳定命令入口，也有真实 `paperlists` 顶会数据与 arXiv 联网链路，但还缺少一套专门服务“论文筛选效果验证”的离线 benchmark。缺口主要体现在：

- 还没有明确的评测集结构，无法稳定回答“某个偏好标签是否被召回”“哪些相邻论文被误召回”。
- 标签体系已在头脑风暴中形成方向，但尚未收敛成可执行的标注手册、数据 schema、抽样协议和正式入库的数据目录。
- 负样本难度目前没有分层，容易出现指标虚高，无法区分系统只是排除了明显无关论文，还是确实学会了边界。
- 还没有讨论清楚第一版数据集规模、数据来源覆盖策略、Codex_CLI 与人类如何协作标注、以及最终数据质量门禁，推进到实现阶段会反复返工。

如果继续在没有 benchmark 的情况下迭代筛选算法，后续任何“感觉更好了”的结论都缺少客观支撑，也无法知道改进究竟来自对真实偏好的捕捉，还是来自对样本分布的偶然适配。

## Research Summary

### Origin Document Findings

已找到相关来源文档 [docs/brainstorms/2026-03-21-paper-filter-evaluation-taxonomy-requirements.md](D:/Git_Repo/Paper-Analysis-New/docs/brainstorms/2026-03-21-paper-filter-evaluation-taxonomy-requirements.md)，文档时间与主题完全匹配，因此作为本计划的主要输入。需要完整继承的关键结论包括：

- 第一版 benchmark 以“论文 + 双标签标注”作为基础结构 `(see origin: docs/brainstorms/2026-03-21-paper-filter-evaluation-taxonomy-requirements.md)`。
- A 轴是偏好标签体系，B 轴是研究对象标签体系；A 轴第一版仅聚焦 `推理优化` 及其 6 个正式子类 `(see origin: docs/brainstorms/2026-03-21-paper-filter-evaluation-taxonomy-requirements.md)`。
- B 轴第一版采用中粒度主研究对象标签，每篇论文必须有且仅有一个主研究对象 `(see origin: docs/brainstorms/2026-03-21-paper-filter-evaluation-taxonomy-requirements.md)`。
- A 轴允许零个、一个或多个偏好标签命中，来源文档已明确第一版允许多标签，Outstanding Questions 中的同名项应视为在 planning 中正式收敛 `(see origin: docs/brainstorms/2026-03-21-paper-filter-evaluation-taxonomy-requirements.md)`。
- 评测协议必须显式定义 easy negatives、in-domain negatives、hard negatives 三层负样本，并在报告中分层统计 `(see origin: docs/brainstorms/2026-03-21-paper-filter-evaluation-taxonomy-requirements.md)`。
- 第一版数据参考范围优先来自本地 `paperlists` 可见的 `AAAI 2025`、`ICLR 2025`、`ICLR 2026`、`ICML 2025`、`NeurIPS 2025` `(see origin: docs/brainstorms/2026-03-21-paper-filter-evaluation-taxonomy-requirements.md)`。

来源文档没有 `Resolve Before Planning` 阻塞项，因此可以继续产出结构化实施计划。

### Local Repository Findings

- [paper_analysis/cli/main.py](D:/Git_Repo/Paper-Analysis-New/paper_analysis/cli/main.py) 已将稳定顶层入口固定为 `conference`、`arxiv`、`quality`、`report`，因此本计划应作为仓库内部评测能力建设，不应新增新的顶层 CLI 命名空间。
- [docs/agent-guide/command-surface.md](D:/Git_Repo/Paper-Analysis-New/docs/agent-guide/command-surface.md) 与 [.codex/skills/paper-analysis/SKILL.md](D:/Git_Repo/Paper-Analysis-New/.codex/skills/paper-analysis/SKILL.md) 明确要求自然语言能力最终都落到现有命令面，但本次标注工具的主要使用方是人类，不要求对 Agent 额外暴露产品接口。
- [docs/engineering/extending-cli.md](D:/Git_Repo/Paper-Analysis-New/docs/engineering/extending-cli.md) 已定义：新增来源、规则或测试层级时，需要同步更新 skill、命令文档、CLI `--help` 和质量文档。这意味着 benchmark 一旦形成稳定命令，也必须纳入同一同步契约。
- 代码层已经有可复用模式：`paper_analysis/sources/conference/` 负责真实来源读取，`paper_analysis/services/*pipeline.py` 负责编排，`tests/unit` 适合承载数据资产与 schema 质量校验。benchmark 实现应尽量沿用这条结构，而不是另起一套脚本型体系。
- [tests/fixtures/paperlists_repo](D:/Git_Repo/Paper-Analysis-New/tests/fixtures/paperlists_repo) 已展示本仓库对顶会真实来源的 fixture 化思路；这为 benchmark 数据 schema、fixture、协议测试提供了可直接复用的组织方式。

### Institutional Learnings

本地 `docs/solutions/` 中没有直接针对“评测集构建 / 标注规范”的经验文档，但有一条相关的流程型经验：[docs/solutions/integration-issues/skill-usage-contract-without-development-guidance.md](D:/Git_Repo/Paper-Analysis-New/docs/solutions/integration-issues/skill-usage-contract-without-development-guidance.md)。

关键启发是：边界契约必须显式写下来并可验证，不能靠隐性共识维持。这个经验可直接迁移到 benchmark 建设：

- 标签定义必须有显式边界，否则不同标注员会各自理解。
- 数据集协议、负样本协议、报表协议必须文档化并测试化，否则随着样本扩充会不断漂移。
- “如何使用 benchmark”与“如何维护 benchmark”要分层表述，避免一个文档同时承担过多职责。

### External Research Decision

本次不做外部研究。原因是你当前要解决的是仓库内 benchmark 方案落地，而不是陌生技术接入；已有来源文档已经定义了业务目标、标签骨架、评测方向和负样本原则，本地仓库也有清晰的数据源与测试分层模式。当前最需要的是把这些决定收敛为可执行计划，而不是再引入新的外部 taxonomy 讨论。

## Proposed Solution

采用“数据协议先行 + 双人标注系统落地 + 小规模高质量起步 + 分层负样本补强 + 数据资产主干化”的方案。

### 1. 先定义 benchmark 数据协议，而不是先大量收集样本

第一步先冻结数据模型、标签边界、切分协议与正式数据目录，确保后续任何样本扩展都落在同一 schema 下。第一版 benchmark 推荐的最小记录结构为：

- 论文原始信息
  - `paper_id`
  - `title`
  - `abstract`
  - `authors`
  - `venue`
  - `year`
  - `source`
  - `source_path`
- B 轴主研究对象
  - `primary_research_object`
- A 轴偏好标签集合
  - `preference_labels`
- 评测辅助字段
  - `split`
  - `negative_tier`
  - `labeler_ids`
  - `review_status`
  - `evidence_spans`
  - `notes`

同时冻结正式目录结构，避免开发中继续把数据写到 `artifacts/` 或零散脚本目录。建议结构如下：

- `data/benchmarks/paper-filter/candidates/`
  - 候选论文池与来源快照
- `data/benchmarks/paper-filter/calibration/`
  - 校准集标注文件、合并结果、统计摘要
- `data/benchmarks/paper-filter/v1/`
  - 正式 benchmark、split、报告与版本说明
- `data/benchmarks/paper-filter/shared/`
  - 标签 schema、枚举、判例库、关键词召回规则

其中 `calibration/` 与 `v1/` 下建议统一包含：

- `records.jsonl`
  - 合并后的最终真值
- `annotations-codex.jsonl`
  - 标注员 A 原始预标
- `annotations-human.jsonl`
  - 标注员 B 原始复标
- `conflicts.jsonl`
  - 待仲裁与已仲裁冲突记录
- `splits.json`
  - train/validation/test 或等价切分
- `stats.json`
  - 标签、来源、负样本层分布统计
- `README.md`
  - 本版本数据说明、范围和已知限制

### 2. 第一版数据集规模采用“小而准”的分层目标

为了避免 benchmark 规模过大导致规范迟迟落不下来，第一版建议按“两阶段规模目标”推进：

- Phase 1 校准集
  - 目标总量：180 到 240 篇论文
  - 用途：验证标签定义、标注手册、负样本协议与报告格式
  - 结构目标：
    - 每个 A 轴子类至少 20 篇正样本
    - 每个 A 轴子类至少 15 篇 in-domain negatives
    - 每个 A 轴子类至少 8 篇 hard negatives
- Phase 2 稳定评测集
  - 目标总量：360 到 480 篇论文
  - 用途：作为后续算法迭代的正式离线 benchmark
  - 结构目标：
    - 每个 A 轴子类累计 35 到 50 篇正样本
    - 每个 A 轴子类累计 25 到 40 篇 in-domain negatives
    - 每个 A 轴子类累计 12 到 20 篇 hard negatives

这样设计的原因是：

- 对第一版最重要的是边界质量，不是样本总量。
- 6 个 A 子类同时起步，如果一开始就追求千级样本，会把精力耗在收集和协调上，而不是把标签定义做准。
- 180 到 240 篇已经足够暴露大部分标签歧义和 hard negative 不足问题，同时仍可通过人工复核完成。

### 3. 数据来源按“核心顶会真实数据 + 控制性补样”组织

第一版正式数据来源建议按优先级分层：

1. 主来源：本地 `paperlists` 顶会真实数据
   - `AAAI 2025`
   - `ICLR 2025`
   - `ICLR 2026`
   - `ICML 2025`
   - `NeurIPS 2025`
2. 候选补样来源：同一来源内的边界论文
   - 用于补充 in-domain negatives 与 hard negatives
3. 预留辅助来源：arXiv 或外部元数据
   - 第一版不作为正式 benchmark 主来源
   - 仅在 Phase 2 之后评估是否用于预标注、召回候选或质检

不把 arXiv 直接纳入第一版正式 benchmark 主池的原因：

- 来源文档已明确第一版要先以本地 `paperlists` 可见顶会数据为参考 `(see origin: docs/brainstorms/2026-03-21-paper-filter-evaluation-taxonomy-requirements.md)`。
- 顶会论文元数据更稳定，噪声更低，更适合建立第一版标注协议。
- 如果一开始混入 arXiv，年份漂移、版本差异和论文成熟度差异会加重标注噪音。

### 4. 标注工作流采用“Codex_CLI 初标 + 人类网页复标 + 轻量仲裁 + 证据记录”

为了保证第一版 benchmark 的高质量标注，建议采用如下流程：

1. 预筛候选池
   - 从 `paperlists` 论文池按关键词、摘要片段、B 轴主类进行初筛
2. 初标
   - 标注员 A 固定为 `Codex_CLI`，由仓库内受控流程生成首轮 B 轴主类与 A 轴标签集合
   - 标注员 B 固定为人类，通过网页界面独立复标，不看 A 的最终裁决结果
3. 差异比对
   - 自动输出冲突项：
     - B 轴主类不同
     - A 轴标签数量不同
     - 是否属于 hard negative 判断不同
4. 仲裁
   - 第三方或主标注负责人只处理冲突项
5. 证据沉淀
   - 对每篇最终样本记录 1 到 3 条证据句或关键词依据
   - 对 hard negative 记录“为什么看起来像、但不属于”的边界说明

其中软件系统的重点交付不是给 Agent 提供新入口，而是给人类提供一个可交互网页，用于：

- 浏览候选论文标题、摘要、来源与上下文
- 查看 `Codex_CLI` 的预标结果与证据
- 填写或修改 B 轴主类与 A 轴标签
- 标记 hard negative / in-domain negative
- 提交复标结果并进入冲突比对
- 查看待仲裁列表与最终状态

为避免“网页标注工具”继续停留在抽象层，第一版建议把人类界面收敛为 4 个页面：

1. 候选池列表页
   - 展示待标注 / 已完成 / 有冲突 / 已仲裁四类状态
   - 支持按会议、年份、B 轴主类、A 轴标签、负样本层筛选
2. 单论文标注页
   - 左侧展示论文标题、摘要、来源、关键词
   - 右侧展示 `Codex_CLI` 预标结果与证据
   - 底部表单录入人类复标结果与备注
3. 冲突审阅页
   - 仅显示 A/B 不一致项
   - 高亮冲突字段和双方证据
   - 支持仲裁结果写回
4. 数据概览页
   - 展示当前进度、标签分布、会议覆盖、hard negative 缺口
   - 用于决定下一轮补样重点

第一版不追求复杂协作能力，不做账号系统、不做多人同时编辑、不做实时同步；默认单机本地运行，目标是让一个人可以稳定完成“看预标、复标、仲裁、导出”的完整闭环。

### 5. 负样本协议正式写入 benchmark 结构

第一版要求每个 A 子类都有三层负样本，而且要在样本条目里显式标记 `negative_tier`：

- `easy`
  - 从全局未命中目标标签的论文中随机抽样
- `in_domain`
  - 从相同 B 轴主类、但未命中目标 A 子类的论文中抽样
- `hard`
  - 从语义相近候选池中半自动召回，再由人工确认

第一版 hard negative 候选池建议采用“两段式构造”：

- 规则召回
  - 标题/摘要含 `efficient`、`fast`、`scaling`、`cache`、`kernel`、`compression`、`routing` 等近邻术语
- 误判回流
  - 把后续筛选模型误召回的论文回流到 hard negative 池中，复核后纳入 benchmark

这也回答了来源文档里关于 hard negatives 候选池的 Outstanding Question：第一版优先使用“关键词规则 + 误判回流”的组合方案，embedding 近邻作为 Phase 2 增强项，而不是第一天就引入。

### 6. 报告协议优先围绕“边界可解释”设计

第一版 benchmark 报告不只输出总体 precision / recall，还要至少支持：

- 按 A 子类统计的 precision / recall
- 按负样本层统计的 precision / recall
- 按 B 轴主类统计的 precision / recall
- `B × A` 交叉统计
- Top 误召回样本清单
- hard negative 误判样本清单

这样才能明确回答：

- 系统是否只是会排除 easy negatives
- 它是否在相同研究对象内部也能识别目标偏好
- 哪些边界定义最不稳定，应该先修标签还是先修算法

## Technical Approach

### Architecture

本计划建议沿用仓库现有分层模式，把 benchmark 能力拆成四层：

- `paper_analysis/domain/`
  - 增加标签、评测样本与指标结果的领域模型
- `paper_analysis/sources/conference/`
  - 继续复用真实 `paperlists` 数据加载
- `paper_analysis/services/`
  - 新增 benchmark 构筑、Codex 预标、标注合并、负样本采样、报告计算服务
- `paper_analysis/web/` 或同类前端/服务目录
  - 提供给人类标注员使用的交互式网页
- `tests/`
  - 用单元测试验证数据资产 schema、字段和分布质量约束

推荐新增或扩展的文件边界：

- `paper_analysis/domain/benchmark.py`
  - benchmark record、label schema、negative tier、split 定义
- `paper_analysis/services/benchmark_builder.py`
  - 从 `paperlists` 生成候选集、样本集与 split
- `paper_analysis/services/codex_annotator.py`
  - 负责驱动 `Codex_CLI` 生成标注员 A 的预标结果
- `paper_analysis/services/annotation_merge.py`
  - `Codex_CLI` 与人类复标结果合并与冲突检测
- `paper_analysis/services/benchmark_reporter.py`
  - 生成按层分桶的指标与错误分析
- `paper_analysis/services/annotation_repository.py`
  - 负责读写 `data/benchmarks/paper-filter/...` 下的标注与冲突文件
- `paper_analysis/web/annotation_app.py`
  - 人类标注网页入口
- `paper_analysis/web/view_models.py`
  - 页面所需聚合视图模型，避免模板直接拼业务逻辑
- `paper_analysis/web/templates/annotation_*.html`
  - 人类标注交互页面模板
- `paper_analysis/web/static/annotation.css`
  - 标注页面样式
- `tests/unit/test_benchmark_builder.py`
- `tests/unit/test_benchmark_dataset_contract.py`
- `tests/unit/test_annotation_merge.py`
- `tests/unit/test_codex_annotator_contract.py`
- `tests/unit/test_annotation_repository.py`

这次不把标注工具定义为 Agent 产品面，不要求新增自然语言入口，也不要求把网页标注工具暴露给 Agent 使用。

### Delivery Breakdown

为了让实现更可控，建议把代码交付拆成 4 个明确子系统：

1. 候选池与数据资产子系统
   - 负责从 `paperlists` 生成候选池，维护 `data/benchmarks/` 正式目录
2. Codex 预标子系统
   - 负责把候选论文转成 `Codex_CLI` 的结构化预标结果
3. 人类网页标注子系统
   - 负责人机交互、复标录入、冲突查看与仲裁写回
4. benchmark 评测子系统
   - 负责 merge、split、分层统计与报告生成

四者之间只通过正式数据文件和领域模型交互，不通过隐式临时文件串联。

### Implementation Phases

#### Phase 1: 标签协议与标注手册冻结

- 输出 `双标签标注规范` 文档
- 冻结 `data/benchmarks/paper-filter/` 目录结构与文件命名
- 为 6 个 A 子类分别写：
  - 定义
  - 正例边界
  - 常见误判边界
  - hard negative 判定规则
- 为 10 个 B 轴主类写主类判定规则与冲突裁决规则
- 明确 A 轴允许多标签命中，并在规范中要求记录主证据
- 明确人类网页每个表单字段与存盘格式
- 明确 `Codex_CLI` 预标结果的结构化输出 contract

交付物建议：

- `third_party/paper_analysis_dataset/docs/benchmarks/paper-filter-label-spec.md`
- `third_party/paper_analysis_dataset/docs/benchmarks/paper-filter-annotation-guidelines.md`
- `third_party/paper_analysis_dataset/docs/benchmarks/paper-filter-ui-workflow.md`
- `data/benchmarks/paper-filter/shared/schema.json`

#### Phase 2: 双人标注系统与校准集构筑

- 从 5 个会议抽取基础候选池
- 打通 `Codex_CLI` 预标流程，产出标注员 A 结果
- 实现人类标注网页，支持浏览、复标、保存与冲突查看
- 让网页能直接读取 `annotations-codex.jsonl` 并保存 `annotations-human.jsonl`
- 先完成 180 到 240 篇校准集
- 跑 `Codex_CLI + 人类` 双人标注与冲突仲裁
- 产出第一版 split 文件与统计摘要

交付物建议：

- `data/benchmarks/paper-filter/candidates/paperlists-2025-2026.jsonl`
- `data/benchmarks/paper-filter/calibration/records.jsonl`
- `data/benchmarks/paper-filter/calibration/stats.json`
- `data/benchmarks/paper-filter/calibration/annotations-codex.jsonl`
- `data/benchmarks/paper-filter/calibration/annotations-human.jsonl`
- `data/benchmarks/paper-filter/calibration/conflicts.jsonl`

#### Phase 3: 分层负样本补齐与正式评测集扩容

- 按 A 子类检查：
  - 正样本是否足够
  - in-domain negatives 是否足够
  - hard negatives 是否足够
- 从近邻术语候选池和误判回流池补足 hard negatives
- 为每个 A 子类沉淀至少一批“边界判例”
- 将总量扩展到 360 到 480 篇正式评测集

交付物建议：

- `data/benchmarks/paper-filter/v1/records.jsonl`
- `data/benchmarks/paper-filter/v1/splits.json`
- `data/benchmarks/paper-filter/v1/stats.json`
- `data/benchmarks/paper-filter/shared/hard-negative-rules.yaml`
- `data/benchmarks/paper-filter/shared/boundary-cases.jsonl`

#### Phase 4: 报告与数据质量门禁

- 把 benchmark 报告与数据资产放入独立目录并合入主干
- 让单元测试覆盖 benchmark schema、标注协议与分布门禁
- 明确标注工具只面向人类，不为 Agent 增加产品接口
- 输出一份版本化说明，解释 calibration 与 v1 的差异

交付物建议：

- `data/benchmarks/paper-filter/v1/report.md`
- `tests/unit/test_benchmark_dataset_contract.py`
- `data/benchmarks/paper-filter/v1/README.md`

## System-Wide Impact

### Interaction Graph

预期链路应为：

`paperlists 真实论文 -> benchmark candidate builder -> Codex_CLI 预标 -> 人类网页复标 -> annotation merge / arbitration -> split builder -> evaluator -> data/benchmarks/...`

### Error & Failure Propagation

- 如果标签 schema 缺字段，应在 domain/schema 校验层失败，而不是等到报告阶段才暴露。
- 如果标注结果出现非法标签名或同一论文缺少 B 轴主类，应在 annotation merge 阶段返回结构化错误。
- 如果某个 A 子类 hard negatives 数量不足，应在 benchmark report 中显式标红并阻断“正式 v1”发布。
- 如果 split 构造导致同一论文跨 split 泄漏，应在单元测试的数据门禁中直接失败。
- 如果网页保存的人类复标记录与 schema 不一致，应在 repository 层拒绝写入，而不是容忍脏数据进入主干文件。
- 如果 `Codex_CLI` 预标没有返回结构化字段，应在 `codex_annotator` contract 校验中失败。

### State Lifecycle Risks

- 半成品标注与正式 benchmark 记录混放，会导致统计口径漂移。
  - 缓解：校准集与正式集必须分目录，并带 `review_status`。
- hard negatives 如果只靠一次性人工挑选，后续会逐渐失真。
  - 缓解：把误判回流作为固定补样渠道。
- 如果多标签协议没有写清楚，后续 precision / recall 计算会不一致。
  - 缓解：第一版统一按“每个 A 子类独立计算 binary relevance”，同时可选输出组合统计。

### API Surface Parity

本次需要维护的对外表面应收敛为三类：

- 人类使用表面
  - 网页标注界面
  - 标注手册
  - 数据版本说明
- 数据资产表面
  - `data/benchmarks/paper-filter/...` 下的正式 JSONL/JSON/Markdown 文件
- 仓库内代码表面
  - domain / services / web 三层模块 contract

不把它扩展成 Agent 技能表面、自然语言路由表面或新的公共 CLI 表面。

### Validation Scenarios

至少需要覆盖以下数据与服务场景：

1. 从 `paperlists` 指定会议读取候选论文并生成 benchmark 候选池。
2. `Codex_CLI` 与人类网页复标结果合并后，冲突项会被正确识别并输出待仲裁清单。
3. 每条正式 benchmark record 都有且仅有一个 B 轴主类。
4. 每个 A 子类都能独立输出 overall / easy / in-domain / hard 四组指标。
5. hard negatives 为 0 时，正式 v1 数据门禁失败并给出缺口说明。
6. `B × A` 交叉统计可定位主要误召回来源。
7. 网页保存出的 `annotations-human.jsonl` 与最终 `records.jsonl` 均满足 schema 校验。

## SpecFlow Analysis

### User Flow Overview

1. 维护者选择顶会范围并生成候选池。
2. `Codex_CLI` 先对每篇论文生成预标结果。
3. 人类标注员通过网页读取候选论文和预标信息，填写或修改 B 轴主类与 A 轴标签集合。
4. 系统自动比对双人标注结果，输出一致项和冲突项。
5. 仲裁者处理冲突项并写回最终结果。
6. benchmark builder 根据最终标注结果构造 split 和分层负样本。
7. evaluator 对筛选算法结果计算分层指标并输出报告。
8. 维护者根据 hard negative 缺口、误召回分布继续补样或修规范。

### Flow Permutations Matrix

| Flow | 场景 | 关键差异 |
| --- | --- | --- |
| 候选池构造 | 单会议 / 多会议 | 多会议时需防止某一 venue 占比过高 |
| 标注 | Codex 预标 / 人类复标 | 人类界面需能查看论文上下文与预标结果，但最终人类输入独立保存 |
| 标注 | 单标签 / 多标签 | 多标签时需记录每个标签的证据，不允许只给集合不写依据 |
| 负样本构造 | easy / in-domain / hard | hard negatives 需要人工确认，不能全自动通过 |
| 评测 | 单 A 子类 / `B × A` 交叉 | 交叉统计更容易暴露标签稀疏与 sample size 不足 |
| 质检 | 初标一致 / 初标冲突 | 冲突样本要进入仲裁池，不能静默覆盖 |

### Missing Elements & Gaps

- **Category**: Dataset Scale
  - **Gap Description**: 来源文档没有给出第一版样本总量与每层负样本的最低门槛。
  - **Impact**: 不设门槛会让“v1 完成”失去客观标准。
  - **Current Ambiguity**: 校准集与正式评测集规模边界不清。

- **Category**: Annotation Quality
  - **Gap Description**: 还没有固定 `Codex_CLI + 人类网页` 双人标注、冲突仲裁、证据记录和一致性指标。
  - **Impact**: 标签质量无法稳定复现。
  - **Current Ambiguity**: 哪些字段必须双人独立标，哪些字段允许单人补录尚未明确。

- **Category**: Human Tooling
  - **Gap Description**: 还没有为人类标注员定义交互页面、保存模型和审阅体验。
  - **Impact**: 人类复标会退化成手工编辑 JSON，效率和一致性都很差。
  - **Current Ambiguity**: 是否支持查看预标证据、过滤待处理项、进入仲裁队列尚未明确。

- **Category**: Hard Negative Mining
  - **Gap Description**: 来源文档提出了 hard negatives，但尚未落地为稳定工作流。
  - **Impact**: 很容易在实施时把 hard negatives 简化成“人工随便挑几个相似样本”。
  - **Current Ambiguity**: 第一版候选池是用规则、误判回流还是 embedding。

- **Category**: Release Gate
  - **Gap Description**: 缺少“什么时候可以把 calibration 升级为 v1 benchmark”的定义。
  - **Impact**: 数据会在没有完成质检时被过早拿来做正式比较。
  - **Current Ambiguity**: 样本规模、hard negative 覆盖、一致性阈值尚未写成门禁。

### Critical Questions Requiring Clarification

本计划先做如下默认决策，避免 planning 继续悬空：

1. **Critical**: 第一版正式 benchmark 仅以 `paperlists` 顶会数据为主来源，不混入 arXiv 主池。
   - Why it matters: 直接决定数据稳定性与标注成本。
   - Default assumption: `AAAI 2025`、`ICLR 2025`、`ICLR 2026`、`ICML 2025`、`NeurIPS 2025` 组成首批主样本池。

2. **Critical**: 双人标注流程固定为“标注员 A = `Codex_CLI`，标注员 B = 人类网页标注员”。
   - Why it matters: 这决定系统交互、数据流和软件交付重点。
   - Default assumption: 人类网页是正式交付件，Agent 不直接使用这套界面。

3. **Critical**: A 轴允许多标签命中，但指标计算按“每个 A 子类独立二分类”执行。
   - Why it matters: 这决定 schema、标注表单与 evaluator 逻辑。
   - Default assumption: 组合标签统计作为附加报表，不作为第一版主指标。

4. **Important**: hard negatives 第一版采用“关键词规则 + 误判回流”的组合候选池，不强依赖 embedding。
   - Why it matters: 影响实现复杂度和第一版落地速度。
   - Default assumption: embedding 近邻作为 Phase 2 之后的增强项。

5. **Important**: 第一版发布门槛至少包括样本量、三层负样本覆盖和双人标注冲突已仲裁完成。
   - Why it matters: 没有发布门槛，benchmark 会持续处于未完成但被使用的状态。
   - Default assumption: 未满足门槛时仅命名为 calibration，不命名为 v1。

### Recommended Next Steps

- 先把标签手册与标注模板写出来，再开始大规模抽样。
- 先做一个 20 篇论文的网页交互试玩版，验证单论文标注页信息密度是否合适。
- 用 30 到 50 篇论文做微型试标，专门找标签冲突最大的边界。
- 把试标中出现频率最高的冲突模式，直接沉淀进 hard negative 判例库。
- 在进入正式 Phase 2 前，先实现 schema 校验与冲突对比脚本，减少人工整理成本。

## Acceptance Criteria

### Functional Requirements

- [ ] 输出一份正式的双标签标注规范，覆盖 6 个 A 子类和 B 轴主类判定规则。
- [ ] benchmark 数据 schema 明确定义论文字段、标签字段、负样本层、split 与质检字段。
- [ ] 交付一套双人标注软件系统，其中标注员 A 固定为 `Codex_CLI`，标注员 B 固定为人类网页标注员。
- [ ] 人类标注网页支持浏览候选论文、查看 `Codex_CLI` 预标、录入复标结果、查看冲突项与提交仲裁结果。
- [ ] 正式数据资产统一存放于 `data/benchmarks/paper-filter/`，并以版本目录形式合入主干。
- [ ] 第一版校准集成功构建，总量达到 180 到 240 篇。
- [ ] 每个 A 子类在校准集中至少拥有 20 篇正样本、15 篇 in-domain negatives、8 篇 hard negatives。
- [ ] 第一版正式 benchmark 扩展到 360 到 480 篇时，每个 A 子类都具备三层负样本，且 hard negatives 比例不为 0。
- [ ] 每条正式样本都具备且仅具备一个 B 轴主研究对象。
- [ ] A 轴支持多标签命中，并为每个命中标签保留证据说明。
- [ ] evaluator 能输出 overall / easy / in-domain / hard 四类指标，以及 `B × A` 交叉统计。

### Non-Functional Requirements

- [ ] 标注手册和样本文件统一使用 UTF-8。
- [ ] benchmark 构筑过程优先复用现有 `paperlists` 与仓库分层结构，不依赖一次性临时脚本。
- [ ] 正式 benchmark 发布前，所有冲突样本都已完成仲裁。
- [ ] 数据规模、标签规模和文档复杂度保持在单人可理解、可维护的范围，不追求全学科完备性。
- [ ] 网页标注工具默认支持单机本地运行，不引入账号系统、权限系统或在线协作依赖。
- [ ] `Codex_CLI` 预标与人类复标的文件格式保持稳定、可审计、可回放。

### Quality Gates

- [ ] `tests/unit/test_benchmark_builder.py` 覆盖 schema、负样本分层与 split 约束。
- [ ] `tests/unit/test_annotation_merge.py` 覆盖 `Codex_CLI + 人类` 双人标注冲突识别与非法标签失败路径。
- [ ] `tests/unit/test_benchmark_dataset_contract.py` 验证最终合入主干的数据文件格式、字段完整性与分布质量门槛。
- [ ] `tests/unit/test_codex_annotator_contract.py` 验证 `Codex_CLI` 预标结果包含必需字段且标签值合法。
- [ ] `tests/unit/test_annotation_repository.py` 验证网页保存与文件落盘不会写入非法结构。
- [ ] 不要求新增 integration / e2e 测试。
- [ ] benchmark 数据资产放在独立目录并合入主干，不写入 `artifacts/`。

建议把 `test_benchmark_dataset_contract.py` 的门禁显式写成以下几类断言：

- 结构门禁
  - 必需字段全部存在
  - 枚举值只来自允许集合
  - 每条记录恰好一个 `primary_research_object`
- 分布门禁
  - 每个 A 子类的正样本数量达到下限
  - 每个 A 子类的 `hard` 负样本数量大于 0
  - 主来源会议分布不被单个 venue 完全垄断
- 质量门禁
  - `annotations-codex.jsonl`、`annotations-human.jsonl`、`records.jsonl` 的 `paper_id` 可对齐
  - 所有 `review_status=final` 的记录都已去除 unresolved conflict
  - `v1` 数据中不存在跨 split 重复

## Success Metrics

- 第一版 benchmark 能稳定回答“推理优化论文是否被召回”“同一研究对象中的相邻论文是否被误召回”“哪类 hard negatives 最容易误判”。
- 标注员对校准集的 B 轴主类冲突率明显下降，并在第二轮规范修订后趋于稳定。
- 后续任一筛选策略改动都能在统一 benchmark 上比较，而不是依赖主观观感。
- benchmark 扩容时，不需要重写标签协议、负样本协议和报表协议。

## Dependencies & Risks

### Dependencies

- 依赖 `paperlists` 真实来源持续可用，并覆盖来源文档指定的 2025 到 2026 会议范围。
- 依赖现有 `conference` 链路与 `paper_analysis/sources/conference/` 的数据读取能力。
- 依赖仓库现有 unit 测试体系，承接 benchmark 数据资产回归。
- 依赖文档同步规则：任何稳定命令面变化，都要同步 skill、agent-guide 与 `--help`。

### Risks

- **风险**: 样本规模定得过大，导致标注规范迟迟无法冻结。
  - **缓解**: 先做 180 到 240 篇校准集，只有通过门禁后才扩容。

- **风险**: hard negatives 被弱化成“随机相似样本”，丧失评测价值。
  - **缓解**: 强制记录 hard negative 的边界说明，并把误判回流纳入正式补样流程。

- **风险**: 多标签规则不清，导致不同 evaluator 计算口径不一致。
  - **缓解**: 在 plan 中明确第一版按“每个 A 子类独立二分类”计算主指标。

- **风险**: B 轴主类粒度漂移，导致 in-domain negative 定义失稳。
  - **缓解**: 先冻结中粒度 B 轴主类，不在 v1 内频繁加类或拆类。

- **风险**: benchmark 资产继续落到 `artifacts/` 或临时文件里，后续无法合入主干和稳定复现。
  - **缓解**: 把 schema、标注文件、split、报告与测试都放入 `data/benchmarks/` 固定目录和服务层。

- **风险**: 人类复标没有专用界面，最后退化成手工编辑 JSON，冲突率和误操作都很高。
  - **缓解**: 把网页标注工具作为核心交付件，而不是附属脚本。

## Alternative Approaches Considered

### 方案 A：直接做大而全 taxonomy，再回头构造 benchmark

不采纳原因：

- 与来源文档“先服务真实筛选需求，不追求全 AI ontology”冲突 `(see origin: docs/brainstorms/2026-03-21-paper-filter-evaluation-taxonomy-requirements.md)`。
- 会显著拉高标注成本，推迟 benchmark 落地。

### 方案 B：先不做双轴，只有一个偏好标签树

不采纳原因：

- 无法稳定构造 in-domain negatives。
- 难以支持 `B × A` 交叉统计，也不利于解释误召回来源。

### 方案 C：先全自动打标签，再把结果当 benchmark

不采纳原因：

- benchmark 的目标是评估算法，不应把未经人工校验的自动标签直接当真值。
- hard negative 与边界样本最需要人工定义，自动标签最容易在这里失真。

## Documentation Plan

建议至少新增或更新以下文档：

- `third_party/paper_analysis_dataset/docs/benchmarks/paper-filter-label-spec.md`
- `third_party/paper_analysis_dataset/docs/benchmarks/paper-filter-annotation-guidelines.md`
- `third_party/paper_analysis_dataset/docs/benchmarks/paper-filter-dataset-protocol.md`
- [docs/engineering/testing-and-quality.md](D:/Git_Repo/Paper-Analysis-New/docs/engineering/testing-and-quality.md)

本次不要求把标注工具同步到 Agent 命令面，因此默认不更新 skill、自然语言路由或 CLI `--help`，除非后续又决定开放内部构建命令。

## Sources & References

### Origin

- **Origin document:** [docs/brainstorms/2026-03-21-paper-filter-evaluation-taxonomy-requirements.md](D:/Git_Repo/Paper-Analysis-New/docs/brainstorms/2026-03-21-paper-filter-evaluation-taxonomy-requirements.md)
  - Carried-forward decisions: 双轴标签体系、A 轴第一版仅做推理优化、B 轴中粒度主类、显式三层负样本、优先使用 `paperlists` 2025-2026 顶会数据。

### Internal References

- [.codex/skills/paper-analysis/SKILL.md](D:/Git_Repo/Paper-Analysis-New/.codex/skills/paper-analysis/SKILL.md)
- [docs/agent-guide/quickstart.md](D:/Git_Repo/Paper-Analysis-New/docs/agent-guide/quickstart.md)
- [docs/agent-guide/command-surface.md](D:/Git_Repo/Paper-Analysis-New/docs/agent-guide/command-surface.md)
- [docs/engineering/extending-cli.md](D:/Git_Repo/Paper-Analysis-New/docs/engineering/extending-cli.md)
- [docs/engineering/testing-and-quality.md](D:/Git_Repo/Paper-Analysis-New/docs/engineering/testing-and-quality.md)
- [paper_analysis/cli/main.py](D:/Git_Repo/Paper-Analysis-New/paper_analysis/cli/main.py)
- [paper_analysis/services/conference_pipeline.py](D:/Git_Repo/Paper-Analysis-New/paper_analysis/services/conference_pipeline.py)
- [paper_analysis/sources/conference/paperlists_loader.py](D:/Git_Repo/Paper-Analysis-New/paper_analysis/sources/conference/paperlists_loader.py)
- [paper_analysis/sources/conference/paperlists_parser.py](D:/Git_Repo/Paper-Analysis-New/paper_analysis/sources/conference/paperlists_parser.py)

### Institutional Learnings

- [docs/solutions/integration-issues/skill-usage-contract-without-development-guidance.md](D:/Git_Repo/Paper-Analysis-New/docs/solutions/integration-issues/skill-usage-contract-without-development-guidance.md)

### Related Work

- [docs/plans/2026-03-20-002-feat-add-arxiv-subscription-ingestion-plan.md](D:/Git_Repo/Paper-Analysis-New/docs/plans/2026-03-20-002-feat-add-arxiv-subscription-ingestion-plan.md)
- [docs/plans/2026-03-21-001-fix-codex-skill-loading-and-natural-language-entry-plan.md](D:/Git_Repo/Paper-Analysis-New/docs/plans/2026-03-21-001-fix-codex-skill-loading-and-natural-language-entry-plan.md)
