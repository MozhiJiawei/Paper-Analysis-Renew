---
title: feat: 在 main 分支落地二分类 A/B 测试脚手架
type: feat
status: completed
date: 2026-03-30
origin: docs/brainstorms/2026-03-30-decoding-strategy-ab-requirements.md
---

# feat: 在 main 分支落地二分类 A/B 测试脚手架

## Overview

本计划聚焦一个更收敛的目标：不是在 `main` 分支上直接实现完整多路线算法，而是先把“论文筛选第一阶段大类二分类”的 A/B 测试脚手架补齐到主线，让后续各路线可以在独立 worktree 中只补算法实现、直接接入统一 runner 和统一报表。这个收敛方向直接承接来源文档已确认的约束：第一阶段只做 `positive/negative` 大类二分类、先保 recall、多路径并行、共享底座与路线实现显式分层 `(see origin: docs/brainstorms/2026-03-30-decoding-strategy-ab-requirements.md)`。

与今天稍早那份“完整多路径 A/B 框架”计划不同，本计划把范围进一步压缩为“主线先落脚手架，算法全部留空”。主线交付的是协议、注册、空路线占位、统一执行、结果落盘、门禁与文档；具体分类器、embedding 检索器、LLM 裁决器与两阶段编排逻辑后续再分别在路线 worktree 中实现。

## Problem Statement

当前仓库已经有稳定的评测 API 契约、跨仓 e2e 和一个可替换的默认预测器壳层：

- 公开评测接口固定为 `POST /v1/evaluation/annotate`，并要求响应包含 `model_info.algorithm_version` [paper_analysis/api/evaluation_server.py](D:/Git_Repo/Paper-Analysis-New/paper_analysis/api/evaluation_server.py) [tests/e2e/test_evaluation_api.py](D:/Git_Repo/Paper-Analysis-New/tests/e2e/test_evaluation_api.py)。
- 对外公开协议已经稳定约束 `negative_tier=positive|negative`，正例必须且只能返回一个主偏好标签 [paper_analysis/api/evaluation_protocol.py](D:/Git_Repo/Paper-Analysis-New/paper_analysis/api/evaluation_protocol.py)。
- 当前 `EvaluationPredictor` 仍是单一路线启发式实现，只适合作为现有默认壳层，不足以承载多路线 A/B 协作 [paper_analysis/api/evaluation_predictor.py](D:/Git_Repo/Paper-Analysis-New/paper_analysis/api/evaluation_predictor.py)。

但“多路径 A/B 测试所需的公共底座”尚未进入主线：

- 没有统一的路线协议和注册中心。
- 没有“算法可缺席、脚手架仍可跑通”的空实现约定。
- 没有结构化的离线 A/B 结果目录、manifest 和排行榜格式。
- 没有把“共享底座留在 main、算法各自在 worktree 演进”的协作边界写成仓库约束。

如果直接在主线开发完整算法，会马上遇到两个问题：

1. `main` 分支变成实验战场，路线间高频冲突，违背来源文档要求的 worktree 并行原则 `(see origin: docs/brainstorms/2026-03-30-decoding-strategy-ab-requirements.md)`。
2. 公共接口、测试和产物格式还没冻结，后续每条路线都要重复返工接线。

## Research Summary

### Origin Document Findings

已找到并完整继承来源文档 [docs/brainstorms/2026-03-30-decoding-strategy-ab-requirements.md](D:/Git_Repo/Paper-Analysis-New/docs/brainstorms/2026-03-30-decoding-strategy-ab-requirements.md)。本计划明确延续以下结论：

- 第一阶段只聚焦大类二分类，不同时推进六个偏好子类 `(see origin: docs/brainstorms/2026-03-30-decoding-strategy-ab-requirements.md)`。
- 目标指标仍是 `recall > 90%` 且 `precision > 50%`，但本计划主线只先交付能支撑该对比的基础设施，不承诺在脚手架阶段达标 `(see origin: docs/brainstorms/2026-03-30-decoding-strategy-ab-requirements.md)`。
- 第一阶段必须至少支撑本地学习式、embedding、LLM、两阶段路线四类候选能力 `(see origin: docs/brainstorms/2026-03-30-decoding-strategy-ab-requirements.md)`。
- 候选路线需要在独立 worktree 中并行推进，统一 runner 拉起，统一报表比较 `(see origin: docs/brainstorms/2026-03-30-decoding-strategy-ab-requirements.md)`。

来源文档没有 `Resolve Before Planning` 阻塞项，因此允许继续规划。

### Local Repository Findings

- 仓库业务入口仍固定为 `conference`、`arxiv`、`quality`、`report`，不能为 A/B 基础设施新增新的顶层产品命名空间 [docs/agent-guide/command-surface.md](D:/Git_Repo/Paper-Analysis-New/docs/agent-guide/command-surface.md) [.codex/skills/paper-analysis/SKILL.md](D:/Git_Repo/Paper-Analysis-New/.codex/skills/paper-analysis/SKILL.md)。
- 评测 API 属于正式支持的跨仓契约，因此任何主线脚手架设计都必须避免破坏当前公开 schema 与真实 e2e [docs/engineering/testing-and-quality.md](D:/Git_Repo/Paper-Analysis-New/docs/engineering/testing-and-quality.md)。
- 现有计划 [docs/plans/2026-03-30-001-feat-paper-filter-binary-ab-framework-plan.md](D:/Git_Repo/Paper-Analysis-New/docs/plans/2026-03-30-001-feat-paper-filter-binary-ab-framework-plan.md) 已经把“完整框架”方向铺开；本计划在它的基础上进一步收缩为“主线脚手架先行，算法留空”的实施切片。

### Institutional Learnings

- [docs/solutions/integration-issues/skill-usage-contract-without-development-guidance.md](D:/Git_Repo/Paper-Analysis-New/docs/solutions/integration-issues/skill-usage-contract-without-development-guidance.md)
  - 启发：职责边界需要写成显式契约。迁移到本计划，就是“主线只放共享脚手架，路线实现不混进底座”。
- [docs/solutions/integration-issues/cli-structured-failure-and-windows-utf8-compatibility.md](D:/Git_Repo/Paper-Analysis-New/docs/solutions/integration-issues/cli-structured-failure-and-windows-utf8-compatibility.md)
  - 启发：边界层要有稳定失败语义与 UTF-8 契约。迁移到本计划，就是 A/B runner 和报表即便遇到未实现路线，也要给出结构化 `skipped/not_implemented` 结果，而不是直接崩溃。

`docs/solutions/patterns/critical-patterns.md` 在本仓库不存在，因此没有额外全局强制模式文件需要纳入。

### External Research Decision

不做外部研究。当前问题核心不是算法选择，而是如何把现有仓库和评测契约收敛成一个稳定的主线脚手架；本地上下文已经足够。

## Proposed Solution

采用“主线冻结共享脚手架，路线实现延后补齐”的方案。

### 1. 在 main 只引入共享底座，不引入真实算法逻辑

主线新增的能力应只包含：

- 二分类路线公共协议
- 路线注册中心
- 空路线占位实现
- 统一 A/B runner
- 统一结果落盘与报表
- 统一 not-implemented / skipped 语义
- 统一测试夹具与质量门禁
- worktree 协作文档

主线**不包含**：

- 真正训练好的本地分类器
- 真正可用的 embedding 索引和近邻检索实现
- 真正调用外部 API 的生产判别逻辑
- 真正完成召回与裁决的两阶段编排细节

这能保证 `main` 先稳定出“接线板”，而不是先卷入算法细节。

### 2. 用占位路线固定四类参赛接口

为满足来源文档 R8、R9，主线直接预留四条路线名，但全部先做空壳：

1. `local_classifier_stub`
2. `embedding_retriever_stub`
3. `llm_judge_stub`
4. `two_stage_stub`

这些 stub 的职责不是给出真实预测，而是稳定暴露：

- `route_name`
- `algorithm_version`
- `capability_type`
- `implementation_status`
- `prepare()`
- `predict_many()`

其中 `predict_many()` 在未实现时返回统一的 `not_implemented` 结果或抛出受控异常，由 runner 负责转成结构化汇总。

### 3. 统一 runner 先支持“空算法跑通”

脚手架阶段 runner 的成功标准不是“有路线跑出高分”，而是：

- 能发现并加载所有已注册路线
- 能区分 `ready`、`stub`、`failed`
- 能在部分路线未实现时继续输出整体报告
- 能对 ready/stub/failed 三类状态分别计数
- 能写出后续 worktree 实现所需的固定产物结构

建议结果目录固定为：

- `artifacts/evaluation-ab/<run_id>/manifest.json`
- `artifacts/evaluation-ab/<run_id>/summary.md`
- `artifacts/evaluation-ab/<run_id>/leaderboard.json`
- `artifacts/evaluation-ab/<run_id>/routes/<route_name>/status.json`
- `artifacts/evaluation-ab/<run_id>/routes/<route_name>/predictions.jsonl`
- `artifacts/evaluation-ab/<run_id>/routes/<route_name>/metrics.json`

即使 stub 路线没有真实预测，也要写出 `status.json` 和空的 `metrics.json`，保证后续实现不需要再改产物协议。

### 4. 让公开 API 保持壳层稳定，不在本阶段切换默认算法

本阶段不把任一 stub 路线接到公开 `evaluation_predictor.py`。公开 API 继续使用当前默认预测器，只做两件事：

- 为未来切换默认路线预留适配层位置
- 保证离线脚手架和公开 API 在 `algorithm_version` 命名与二分类输出语义上兼容

这样可以避免把“离线框架建设”与“线上默认算法替换”耦合在同一阶段。

### 5. 把 worktree 分工写入主线文档和测试

脚手架进入 `main` 后，应同步固化协作边界：

- `main` 只接收共享底座和通用文档。
- 每条候选路线在自己的 worktree 中补真实实现。
- 路线 worktree 只允许改自己的 `routes/<route>.py`、配置文件和少量注册点。
- runner、协议、报表、结果格式默认由主线统一维护。

这部分约束应被写入工程文档，而不是停留在口头约定。

### 6. 主线脚手架必须保留一条最小跨仓真实 e2e

为了验证脚手架没有把主仓和 data 子仓评测契约割裂开，主线必须设计并保留一条“最小真实交互集” e2e：

- 主仓真实启动 `paper_analysis.api.evaluation_server`
- 子仓真实执行 `paper_analysis_dataset.tools.evaluate_paper_filter_benchmark`
- 用最小样本数 `--limit 3` 跑通一次完整评测
- 在子仓输出目录真实生成 `report.json`、`summary.md`、`stdout.txt`
- 在 e2e 用例 artifact 中同时保留：
  - 子仓生成的算法指标报告
  - 主仓服务启动所使用的 `algorithm_version`

这条用例的目标不是验证某条路线已经达标，而是验证：

- 跨仓正式评测契约仍然成立
- A/B 脚手架可以通过主仓公开接口向 data 子仓暴露一个可比较的算法快照
- e2e 审核页中能直接看到 `precision / recall / f1` 指标报告，而不是只看到“子进程成功退出”

## Technical Approach

### Architecture

建议主线新增如下文件边界：

- `paper_analysis/evaluation/ab_protocol.py`
  - 定义 `BinaryRouteInput`、`BinaryRoutePrediction`、`RouteExecutionStatus`、`RouteRunResult`
- `paper_analysis/evaluation/route_registry.py`
  - 统一注册与发现路线
- `paper_analysis/evaluation/ab_runner.py`
  - 负责执行、错误归一化、状态统计、结果落盘
- `paper_analysis/evaluation/ab_reporter.py`
  - 负责生成 `summary.md` 与 `leaderboard.json`
- `paper_analysis/evaluation/routes/base.py`
  - 路线基类 / Protocol
- `paper_analysis/evaluation/routes/local_classifier_stub.py`
- `paper_analysis/evaluation/routes/embedding_retriever_stub.py`
- `paper_analysis/evaluation/routes/llm_judge_stub.py`
- `paper_analysis/evaluation/routes/two_stage_stub.py`
- `paper_analysis/evaluation/errors.py`
  - `RouteNotImplementedError`、`RouteContractError`
- `tests/unit/test_ab_protocol.py`
- `tests/unit/test_route_registry.py`
- `tests/unit/test_ab_runner.py`
- `tests/integration/test_ab_scaffold.py`
- `docs/engineering/ab-worktree-workflow.md`

如需 CLI 入口，优先作为内部工程命令挂在现有 `quality` 命名空间下，而不是新增新的顶层业务命名空间。例如后续可以考虑：

```text
py -m paper_analysis.cli.main quality evaluation-ab-scaffold
```

但如果当前仓库更适合先以内部模块调用 runner，也可以先不暴露 CLI，只在文档与测试中固定模块接口。

### Implementation Phases

#### Phase 1: 冻结共享协议与占位语义

- 定义路线输入输出协议
- 定义 `stub`、`ready`、`failed`、`skipped` 状态
- 定义 `RouteNotImplementedError` 与 runner 的归一化逻辑
- 冻结结果目录结构与 manifest schema

交付物：

- `paper_analysis/evaluation/ab_protocol.py`
- `paper_analysis/evaluation/errors.py`
- `tests/unit/test_ab_protocol.py`

#### Phase 2: 落地注册中心与四条 stub 路线

- 建立统一 route registry
- 注册四条占位路线
- 为每条路线提供固定元信息和空实现
- runner 能在统一数据集上发现并执行它们

交付物：

- `paper_analysis/evaluation/route_registry.py`
- `paper_analysis/evaluation/routes/*.py`
- `tests/unit/test_route_registry.py`
- `tests/integration/test_ab_scaffold.py`

#### Phase 3: 打通 runner、manifest 和报表

- runner 支持逐路线执行与状态归一化
- 生成 `manifest.json`、`summary.md`、`leaderboard.json`
- 为 stub 路线输出结构化“未实现”状态，而不是 traceback
- 文档明确后续路线 worktree 只需要把 stub 替换成真实实现

交付物：

- `paper_analysis/evaluation/ab_runner.py`
- `paper_analysis/evaluation/ab_reporter.py`
- `artifacts/evaluation-ab/<run_id>/...`

#### Phase 4: 固化文档、质量门禁与 API 兼容约束

- 把 worktree 协作方式写入文档
- 若增加内部 CLI 或质量入口，同步更新命令面和 `--help`
- 增加对结果目录、stub 状态与 UTF-8 产物的回归测试
- 明确本阶段不切换公开 API 默认算法

交付物：

- `docs/engineering/ab-worktree-workflow.md`
- `docs/engineering/testing-and-quality.md`
- `docs/agent-guide/command-surface.md` 或 CLI `--help`（仅在命令面变化时）

## Alternative Approaches Considered

### 方案 A：直接在 main 实现 3 到 4 条真实路线

不采纳。这样会让主线在共享协议未冻结前就承载大量实验逻辑，和来源文档要求的 worktree 并行开发相冲突 `(see origin: docs/brainstorms/2026-03-30-decoding-strategy-ab-requirements.md)`。

### 方案 B：只写文档，不写 stub 与 runner

不采纳。只有文档没有可运行脚手架，后续每条路线仍会各自发明状态语义、产物格式和注册方式，无法真正降低并行开发摩擦。

### 方案 C：先把默认公开预测器抽成“当前唯一路线”

部分保留，但不作为本阶段主线。当前默认预测器可以作为未来适配样本，但本阶段不应让公开 API 改成多路线调度中心。

## System-Wide Impact

### Interaction Graph

脚手架阶段的主链路应为：

`benchmark dataset -> route registry -> stub/ready routes -> ab_runner -> ab_reporter -> artifacts/evaluation-ab/*`

本阶段**不**把该链路接入：

`POST /v1/evaluation/annotate -> EvaluationPredictor`

公开 API 仅保持兼容参照。

### Error & Failure Propagation

- 路线未实现：
  - 路线抛 `RouteNotImplementedError`
  - runner 记录为 `stub`
  - reporter 产出结构化占位结果
- 路线输出字段缺失：
  - 协议层判定 `RouteContractError`
  - runner 记录为 `failed`
  - 不影响其他路线继续执行
- 结果目录创建失败：
  - runner 整体失败并输出结构化错误
- 某条路线尚无真实 metrics：
  - `metrics.json` 为空结构，但 schema 稳定存在

### State Lifecycle Risks

- 如果 stub 结果格式不稳定，后续真实实现接入仍会返工。
  - 缓解：脚手架阶段就冻结结果目录和 JSON schema。
- 如果 runner 遇到未实现路线直接中断，主线脚手架价值会大幅下降。
  - 缓解：把 `not_implemented` 作为一等状态处理。
- 如果主线开始容纳真实路线逻辑，后续 worktree 边界会再次模糊。
  - 缓解：文档和测试都显式强调“主线只保留共享底座”。

### API Surface Parity

需要维护的接口面包括：

- 离线 A/B 接口面
  - route protocol
  - route registry
  - runner output schema
- 公开评测接口面
  - `/v1/evaluation/annotate`
  - `algorithm_version`
  - `positive/negative` 协议

本阶段要求二者语义兼容，但不要求主线脚手架直接接管公开 API。

### Integration Test Scenarios

1. 四条 stub 路线都能被注册中心发现。
2. runner 在四条路线全部未实现时，仍能生成完整 manifest 与 summary。
3. 其中一条路线替换为测试用假实现时，runner 能同时处理 `ready + stub` 混合状态。
4. 产物目录中的 Markdown/JSON 全部使用 UTF-8 写出。
5. 公开 API 现有 e2e 在脚手架接入后保持不回归。
6. 至少一条最小跨仓 e2e 能真实运行子仓 CLI，并在 artifact 中展示 `report.json` / `summary.md` 里的算法指标。

## SpecFlow Analysis

### User Flow Overview

1. 开发者在 `main` 上运行 A/B scaffold runner。
2. runner 读取固定 benchmark 输入。
3. registry 发现四条已注册路线。
4. 每条路线进入 `prepare()`：
   - stub 路线返回“未实现”或无操作
5. runner 调用 `predict_many()`：
   - stub 路线返回结构化占位状态
   - 假实现路线可返回测试预测
6. reporter 汇总并写出产物。
7. 后续某条路线在独立 worktree 中替换 stub，实现无需改 runner 或报表协议。

### Missing Elements & Gaps

- **Category**: CLI Exposure
  - **Gap Description**: 当前还未决定脚手架是否立刻提供 CLI 入口。
  - **Impact**: 影响是否需要同步命令面文档与 `--help`。
  - **Default**: 先允许内部模块调用；若新增 CLI，再同步更新文档。

- **Category**: Dataset Fixture
  - **Gap Description**: 需要一个稳定的小型 benchmark fixture 供 scaffold 回归测试使用。
  - **Impact**: 没有稳定夹具就难以持续验证产物结构。
  - **Default**: 复用现有 evaluation fixture 或新增最小 JSON fixture。

- **Category**: Cross-Repo Evidence
  - **Gap Description**: 需要明确算法指标和 `algorithm_version` 分别出现在什么 artifact 中。
  - **Impact**: 如果只记录其一，e2e 报告就无法同时回答“跑的是哪条路线”和“指标是多少”。
  - **Default**: `report.json` / `summary.md` 负责展示算法指标；主仓服务启动日志或独立 artifact 负责保留 `algorithm_version`。

- **Category**: Status Semantics
  - **Gap Description**: `stub` 与 `skipped` 的边界需在协议里写清。
  - **Impact**: 否则不同路线会各自解释“未实现”。
  - **Default**: `stub` 表示路线设计存在但尚无算法；`skipped` 表示本次运行被显式跳过。

### Critical Questions Requiring Clarification

本计划先按以下默认假设继续，不阻塞脚手架规划：

1. **Critical**: 本阶段的“完成”指脚手架可运行，不指任一路线已达标。
2. **Critical**: `main` 上允许放四条路线 stub，但不允许放真实实验逻辑。
3. **Important**: 若后续新增内部 CLI，则归入现有稳定命名空间，不新增 `recommend`。
4. **Important**: `algorithm_version` 在 stub 阶段也必须稳定存在，用于后续真实实现平滑替换。

### Recommended Next Steps

- 先在主线冻结协议、registry、runner、reporter 和 stub 状态。
- 用测试假实现替代其中一条 stub，确保脚手架能处理真实/空实现混合场景。
- 文档明确每条候选路线后续应该在哪个 worktree 中替换哪个 stub 文件。
- 设计并保留一条跨仓最小 e2e：主仓真实起服务、子仓真实评测、报告中可见算法指标。
- 等脚手架稳定后，再分别创建路线 worktree 补算法。

## Acceptance Criteria

### Functional Requirements

- [ ] `main` 分支具备统一的 A/B 路线协议、注册中心、runner 和 reporter。
- [ ] 主线预留四条候选路线 stub，对应本地学习式、embedding、LLM、两阶段四类能力。
- [ ] runner 能在路线未实现时输出结构化 `stub/not_implemented` 结果，而不是崩溃。
- [ ] 结果目录、manifest、summary、leaderboard 的文件结构被固定下来。
- [ ] 后续 worktree 中替换任一路线 stub 时，不需要修改共享产物协议。
- [ ] 至少存在一条最小跨仓 e2e：调用子仓真实评测 CLI，并输出包含 `precision / recall / f1` 的报告产物。

### Non-Functional Requirements

- [ ] 本阶段不新增新的顶层业务命名空间，不引入独立 `recommend` 面。
- [ ] 文本产物、报表和测试夹具统一使用 UTF-8。
- [ ] 公开评测 API 现有 schema 与跨仓 e2e 不回归。
- [ ] 主线不承载真实算法实验代码，只承载共享脚手架。
- [ ] 未实现路线的失败语义可机器消费、可测试、可报告。
- [ ] e2e 报告中能直接查看子仓 `report.json` / `summary.md` 的聚合算法指标，同时保留本次服务的 `algorithm_version` 证据。

### Quality Gates

- [ ] `tests/unit/test_ab_protocol.py` 覆盖协议与状态枚举。
- [ ] `tests/unit/test_route_registry.py` 覆盖四条 stub 注册与发现。
- [ ] `tests/unit/test_ab_runner.py` 覆盖 `ready/stub/failed/skipped` 归一化。
- [ ] `tests/integration/test_ab_scaffold.py` 覆盖完整产物目录与 UTF-8 写出。
- [ ] [tests/e2e/test_evaluation_api.py](D:/Git_Repo/Paper-Analysis-New/tests/e2e/test_evaluation_api.py) 继续通过。
- [ ] 跨仓最小 e2e 断言子仓 `report.json["overall"]` 含 macro/micro precision、recall、f1，且 `summary.md` 出现指标摘要行。

## Success Metrics

- 主线脚手架一旦合入，团队可以立刻在不同 worktree 中并行补路线实现，而不需要先争论 runner、报表和结果格式。
- 至少一条假实现路线能无缝替换 stub，证明协议设计对后续真实算法接入可用。
- 后续路线开发的改动主要落在各自 `routes/*.py`，而不是反复改 shared runner。
- 团队在 `quality` HTML 审核页或 e2e artifact 中，能直接看到一次最小跨仓运行产出的算法指标 report。

## Dependencies & Risks

### Dependencies

- 依赖现有评测 API 协议继续稳定 [paper_analysis/api/evaluation_protocol.py](D:/Git_Repo/Paper-Analysis-New/paper_analysis/api/evaluation_protocol.py)。
- 依赖现有 benchmark / evaluation fixture 能支持 scaffold 测试。
- 依赖团队接受“主线只合脚手架，算法在 worktree 落地”的协作方式 `(see origin: docs/brainstorms/2026-03-30-decoding-strategy-ab-requirements.md)`。

### Risks

- **风险**: 主线脚手架过度抽象，导致后续真实路线难以接入。
  - **缓解**: 用一条测试假实现尽早验证协议可用，而不是只靠接口想象。

- **风险**: stub 设计过弱，后续仍需重写结果协议。
  - **缓解**: 在脚手架阶段就冻结 `manifest.json`、`status.json`、`metrics.json` schema。

- **风险**: 团队把 stub 当成“功能已完成”。
  - **缓解**: 文档和报表明确区分 `stub` 与 `ready`，并把未实现路线显示为未就绪。

## Documentation Plan

- `docs/engineering/ab-worktree-workflow.md`
  - 新增，明确主线脚手架范围、worktree 边界和 stub 替换流程。
- `docs/engineering/testing-and-quality.md`
  - 若新增 scaffold runner 的测试入口或质量门禁，需同步更新。
- `docs/agent-guide/command-surface.md`
  - 仅在本阶段新增内部 CLI 时更新。
- `.codex/skills/paper-analysis/SKILL.md`
  - 仅在命令面真的变化时更新；若只是内部脚手架模块，不应扩展用户路由说明。

## Sources & References

### Origin

- **Origin document:** [docs/brainstorms/2026-03-30-decoding-strategy-ab-requirements.md](D:/Git_Repo/Paper-Analysis-New/docs/brainstorms/2026-03-30-decoding-strategy-ab-requirements.md)
  - Carried-forward decisions: 第一阶段只做大类二分类、先保 recall、多路线并行、两阶段路线必须参赛、规则仅作最小护栏、默认 worktree 隔离、共享底座与路线实现分层。

### Internal References

- [docs/plans/2026-03-30-001-feat-paper-filter-binary-ab-framework-plan.md](D:/Git_Repo/Paper-Analysis-New/docs/plans/2026-03-30-001-feat-paper-filter-binary-ab-framework-plan.md)
- [paper_analysis/api/evaluation_predictor.py](D:/Git_Repo/Paper-Analysis-New/paper_analysis/api/evaluation_predictor.py)
- [paper_analysis/api/evaluation_protocol.py](D:/Git_Repo/Paper-Analysis-New/paper_analysis/api/evaluation_protocol.py)
- [paper_analysis/api/evaluation_server.py](D:/Git_Repo/Paper-Analysis-New/paper_analysis/api/evaluation_server.py)
- [tests/e2e/test_evaluation_api.py](D:/Git_Repo/Paper-Analysis-New/tests/e2e/test_evaluation_api.py)
- [docs/agent-guide/command-surface.md](D:/Git_Repo/Paper-Analysis-New/docs/agent-guide/command-surface.md)
- [docs/engineering/testing-and-quality.md](D:/Git_Repo/Paper-Analysis-New/docs/engineering/testing-and-quality.md)
- [third_party/paper_analysis_dataset/paper_analysis_dataset/services/evaluation_reporter.py](D:/Git_Repo/Paper-Analysis-New/third_party/paper_analysis_dataset/paper_analysis_dataset/services/evaluation_reporter.py)
- [third_party/paper_analysis_dataset/tests/e2e/test_evaluate_cli.py](D:/Git_Repo/Paper-Analysis-New/third_party/paper_analysis_dataset/tests/e2e/test_evaluate_cli.py)

### Institutional Learnings

- [docs/solutions/integration-issues/skill-usage-contract-without-development-guidance.md](D:/Git_Repo/Paper-Analysis-New/docs/solutions/integration-issues/skill-usage-contract-without-development-guidance.md)
- [docs/solutions/integration-issues/cli-structured-failure-and-windows-utf8-compatibility.md](D:/Git_Repo/Paper-Analysis-New/docs/solutions/integration-issues/cli-structured-failure-and-windows-utf8-compatibility.md)
