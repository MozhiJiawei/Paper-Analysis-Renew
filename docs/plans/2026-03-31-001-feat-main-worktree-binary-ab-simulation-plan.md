---
title: feat: 用两个独立 worktree 模拟一次二分类 A/B 开发
type: feat
status: active
date: 2026-03-31
origin: docs/brainstorms/2026-03-30-decoding-strategy-ab-requirements.md
---

# feat: 用两个独立 worktree 模拟一次二分类 A/B 开发

## Overview

本计划聚焦一次“先不搞复杂、先做 `positive/negative`”的真实 A/B 开发演练：从同一共享底座提交点创建两个彼此独立的 Git worktree，分别承载 A 方案与 B 方案；双方都必须是彼此独立的真实算法方向，而不是“主线基线 + 空壳挑战者”或“同一路线的小参数微调”。两边围绕同一份二分类任务、同一份评测输入、同一套输出契约分别调优，完成后按统一标准择优录取。这个范围直接承接来源文档已经确认的结论：第一阶段只做大类二分类、先保 recall、多路径并行、默认使用 worktree 隔离 `(see origin: docs/brainstorms/2026-03-30-decoding-strategy-ab-requirements.md)`。

与已经完成的“主线 A/B scaffold 落地”不同，这份计划不再讨论如何补脚手架，而是定义如何基于现有脚手架做第一次最小真实对打：两个独立 worktree 各自承载一条真实算法路线；`main` 只负责冻结共享底座与承接最终胜方回收。两边都只输出 `positive/negative`，不把六个偏好子类作为本轮胜负依据。

## Problem Statement / Motivation

当前仓库已经具备运行一次最小 A/B 对打所需的大部分共享底座：

- 公开评测接口已经固定为 `POST /v1/evaluation/annotate`，并要求返回 `model_info.algorithm_version` [paper_analysis/api/evaluation_server.py](D:/Git_Repo/Paper-Analysis-New/paper_analysis/api/evaluation_server.py)。
- 二分类协议已经稳定约束 `negative_tier=positive|negative`，正例时只允许返回一个主偏好标签 [paper_analysis/api/evaluation_protocol.py](D:/Git_Repo/Paper-Analysis-New/paper_analysis/api/evaluation_protocol.py)。
- 主线已经存在 A/B runner、registry 和四类 stub 路线，可支持结构化结果落盘 [paper_analysis/evaluation/ab_runner.py](D:/Git_Repo/Paper-Analysis-New/paper_analysis/evaluation/ab_runner.py) [paper_analysis/evaluation/route_registry.py](D:/Git_Repo/Paper-Analysis-New/paper_analysis/evaluation/route_registry.py)。
- 主仓与子仓之间已经保留最小真实评测 e2e，且报告里能看到 `precision / recall / f1` 与 `algorithm_version` [tests/e2e/test_evaluation_api.py](D:/Git_Repo/Paper-Analysis-New/tests/e2e/test_evaluation_api.py)。

但“如何用两个独立 worktree 做第一次真实二分类 A/B 演练”还没有被写成一份清晰方案：

- 哪些文件属于共享底座，双方都不能随意改。
- A 路线和 B 路线各自允许在哪些目录调优，以及哪些改动必须留在各自 worktree 内。
- 同一轮对比的输入集、算法版本标识、结果目录和胜出规则是什么。
- 当第一次只做 `positive/negative` 时，如何避免过早把实验目标收缩到子类标签，从而偏离来源文档的阶段目标 `(see origin: docs/brainstorms/2026-03-30-decoding-strategy-ab-requirements.md)`。

如果没有这层计划，团队很容易出现两类问题：

1. 两边都在改共享 runner 或协议，结果不是比较算法，而是在比较谁改了更多底座。
2. 两边各自输出不同格式或不同评测口径，最后无法真正“择优录取”。

此外，本轮还需要补上一条关键数据约束：现有人工标注数据只能作为最终测试验收与统一评测依据，不能回流为 A/B 路线的开发集、调参集或 prompt 反复打磨集。路线开发阶段应优先从仓内 `paper_analysis` 现有论文来源链路或 arXiv API 拉取无标记论文，作为算法开发、规则草拟、错误观察和候选分析的数据来源。

## Proposed Solution

采用“一份共享底座 + 两个隔离 worktree + 一轮统一离线评测”的最小演练方案。

### 1. 固定本轮只比较大类二分类

本轮 A/B 的唯一主任务是：

- 输入单篇论文
- 输出 `positive` 或 `negative`
- 若为 `positive`，允许附带一个主偏好标签用于协议兼容，但本轮胜负不按子类标签打分

这与来源文档的阶段边界一致：先把 `positive/negative` 做稳，再决定是否进入子类细分 `(see origin: docs/brainstorms/2026-03-30-decoding-strategy-ab-requirements.md)`。

### 2. 用两个独立 worktree 承载 A/B 方案，`main` 只承载共享底座

本轮默认角色如下：

- `main`：冻结共享底座，不直接承载参赛路线实现
- A 方案：从共享底座提交点拉出的独立 worktree 上的一条真实算法路线
- B 方案：从同一提交点拉出的另一独立 worktree 上的另一条真实算法路线

两边都必须复用同一套共享底座：

- `paper_analysis/api/evaluation_protocol.py`
- `paper_analysis/api/evaluation_server.py`
- `paper_analysis/evaluation/ab_protocol.py`
- `paper_analysis/evaluation/ab_runner.py`
- `paper_analysis/evaluation/ab_reporter.py`
- `paper_analysis/evaluation/route_registry.py`

两边允许独立修改的范围应尽量收缩到：

- 自己的 worktree 内 route 实现文件
- 与该 route 绑定的轻量配置
- 必要的 prompt / 阈值 / 特征参数

两边默认**不要**各自改共享协议、结果 schema、跨仓 e2e 断言和统一 runner；否则就不是同赛道 A/B。

额外约束是：

- A、B 必须是两个独立方向，不能只是同一路线换阈值、换 prompt 文案或换少量关键词。
- A、B 都必须进入 `ready` 状态并产出真实预测结果，不能让任一方以 stub、占位实现或纯概念方案参赛。
- 两边都应各自完成最小必要调优，再进入统一评测；不接受“一边是真算法，另一边只是陪跑壳层”。

### 3. 第一次演练采用“两条真实路线”的最小形态

来源文档要求长期至少覆盖本地学习式、embedding、LLM、两阶段等多类路线 `(see origin: docs/brainstorms/2026-03-30-decoding-strategy-ab-requirements.md)`，但这次第一次演练先不要铺太大。

建议首轮只安排：

- `worktree-a`：一条真实方向的 A 路线
  - 建议采用 `embedding / 相似度召回 + 阈值二分类`
- `worktree-b`：另一条明确不同范式的 B 路线
  - 建议采用 `规则预过滤 + LLM 二阶段裁决`

首轮的“不要太复杂”，指的是只比大类 `positive/negative`，而不是把 A、B 降级成不完整方案。也就是说，复杂度收缩的是任务口径，不是路线真实性。

这样能先验证工作流本身，同时也让第一次结果具备真实决策价值，而不是一次性把所有路线都卷进来。

建议把两条路线明确命名为：

- A：`embedding_similarity_binary`
- B：`rule_filtered_llm_binary`

### 4. 统一输入、统一命名、统一落盘

同一轮 A/B 必须共享：

- 同一份验收 benchmark 输入集
- 同一份评测切分或固定样本清单
- 同一套 metrics 计算方式
- 同一份结果目录结构

但需要明确区分两类数据：

- 开发数据：
  - 必须是无标记论文
  - 来源应优先是 `paper_analysis` 当前可访问的论文来源链路，或真实 arXiv API 抓取结果
  - 只用于规则观察、候选分析、prompt 迭代、阈值直觉建立和失败案例浏览
- 验收数据：
  - 可以使用现有人工标注 benchmark
  - 只用于最终统一打分、回归比较和录取决策

也就是说，A/B 两边都不能把人工标注 benchmark 当作开发集反复试错；否则最终分数会失去验收意义。

建议每次运行使用统一 `run_id`，但分路线保留独立 `algorithm_version`：

- `embedding-sim-binary-<date>-v1`
- `rule-llm-binary-<date>-v1`

离线产物继续复用现有 runner 目录结构：

- `artifacts/evaluation-ab/<run_id>/manifest.json`
- `artifacts/evaluation-ab/<run_id>/summary.md`
- `artifacts/evaluation-ab/<run_id>/leaderboard.json`
- `artifacts/evaluation-ab/<run_id>/routes/<route_name>/status.json`
- `artifacts/evaluation-ab/<run_id>/routes/<route_name>/predictions.jsonl`
- `artifacts/evaluation-ab/<run_id>/routes/<route_name>/metrics.json`

若需要通过主仓评测服务给子仓跑最小真实对比，则继续保留：

- `third_party/paper_analysis_dataset/artifacts/test-output/evaluation-ab-e2e-minimal/`
- `service-launch.json`

### 5. 择优标准按“先 recall，再 precision，再稳定性”执行

本轮择优必须与来源文档的优化优先级一致 `(see origin: docs/brainstorms/2026-03-30-decoding-strategy-ab-requirements.md)`：

1. 先比较 recall，低于门槛的路线不进入主推荐。
2. recall 接近时再比较 precision。
3. precision / recall 接近时再比较：
   - 结果稳定性
   - 失败率
   - 调试成本
   - 是否更适合作为后续子类细分底座

第一次演练不要求直接定最终长期赢家，但要明确输出：

- 谁是当前推荐默认路线
- 谁保留为备选继续深挖
- 谁暂时淘汰

## Technical Considerations

- 公开评测 API 本轮不改外部 schema，只允许通过 `--algorithm-version` 标记不同路线版本 [paper_analysis/api/evaluation_server.py](D:/Git_Repo/Paper-Analysis-New/paper_analysis/api/evaluation_server.py)。
- 现有 AB runner 已能处理 `ready/stub/failed/skipped`，因此第一次演练可以只让两条 ready 路线参赛，其余 stub 保留不动 [paper_analysis/evaluation/ab_runner.py](D:/Git_Repo/Paper-Analysis-New/paper_analysis/evaluation/ab_runner.py)。
- 集成测试已经证明 ready 与 stub 可在同一轮共存，这使得“只挑两条路线先打”成为低风险做法 [tests/integration/test_ab_scaffold.py](D:/Git_Repo/Paper-Analysis-New/tests/integration/test_ab_scaffold.py)。
- 二分类对打过程中仍要保持 UTF-8 产物和结构化失败语义，避免不同工作区在失败场景下生成不可比较的 artifact [docs/solutions/integration-issues/cli-structured-failure-and-windows-utf8-compatibility.md](D:/Git_Repo/Paper-Analysis-New/docs/solutions/integration-issues/cli-structured-failure-and-windows-utf8-compatibility.md)。
- B 路线不应直接把全量数据逐条送入 LLM；首轮推荐先用轻量规则做高召回预过滤，再把候选集交给 LLM 做裁决，以控制成本和迭代时延。
- 人工标注数据只允许作为测试验收依据，不允许作为开发数据回流；开发阶段应使用无标记论文，来源优先为仓内 `paper_analysis` 链路或 arXiv API。

## System-Wide Impact

- **Interaction graph**:
  `fixed benchmark -> worktree-a route / worktree-b route -> ab_runner -> metrics -> leaderboard -> winner decision`
- **Error propagation**:
  单条路线失败应落为 `failed`，不能阻断另一条路线出结果。
- **State lifecycle risks**:
  如果两边都改共享 runner 或 metrics 逻辑，将直接污染实验公平性。
- **API surface parity**:
  离线 A/B 与跨仓评测都要继续遵守现有 `positive/negative + algorithm_version` 契约。
- **Integration test scenarios**:
  需要同时覆盖“本地 runner 对比成功”和“子仓真实请求主仓评测服务成功”两层验证。

## Implementation Phases

### Phase 1: 冻结本轮实验契约

- 明确首轮只比较 `positive/negative`
- 明确 A 方案与 B 方案的 route 名称、`algorithm_version` 命名规则和输入集
- 明确开发数据与验收数据分离：
  - 开发阶段只用无标记论文
  - 人工标注数据只用于最终验收
- 明确共享底座文件白名单与路线独占文件边界
- 为本轮输出单独的实验记录文档，说明如何复现

交付物：

- `docs/engineering/ab-worktree-workflow.md` 更新本轮规则
- `docs/plans/2026-03-31-001-feat-main-worktree-binary-ab-simulation-plan.md`

### Phase 2: 创建 `worktree-a` 并实现 A 方案真实路线

- 从共享底座提交点创建 `worktree-a`
- 在 `worktree-a` 中实现 `embedding_similarity_binary`
- 从 `paper_analysis` 现有来源链路或 arXiv API 拉取无标记论文，作为 A 路线开发观察数据
- 保证该路线在自己的 worktree 中可以稳定跑完，并产出真实预测与 metrics
- 为 A 路线写清算法思路、输入、阈值、已知短板和 `algorithm_version`

交付物：

- 一个隔离的 `worktree-a`
- 一个可运行的 A 路线实现
- 对应的最小 unit / integration 验证

### Phase 3: 创建 `worktree-b` 并实现 B 方案真实路线

- 从与 `worktree-a` 相同的共享底座提交点创建 `worktree-b`
- 在 `worktree-b` 中实现 `rule_filtered_llm_binary`
- 从 `paper_analysis` 现有来源链路或 arXiv API 拉取无标记论文，作为 B 路线规则观察与 prompt 调优数据
- 先定义规则预过滤层，再定义 LLM 裁决层
- 只在 B 路线独占目录或 route 文件中调优
- 不回写共享 runner、协议和统一报表格式
- 让 B 路线也能在同一 benchmark 上输出同构产物
- 确保 B 路线与 A 路线在方法上有明确区分，而不是同类方法的微变体

交付物：

- 一个隔离的 `worktree-b`
- 一个 ready 状态的 B 路线实现
- B 路线自有调优记录

### Phase 4: 统一跑分并择优录取

- 在同一输入集上分别跑 `worktree-a` 与 `worktree-b` 路线
- 汇总 precision / recall / f1 与失败情况
- 生成对比结论
- 选出本轮推荐默认路线
- 决定败方是淘汰、冻结还是继续保留观察
- 若需要回收胜方，只把胜方路线实现、必要配置与最小测试有选择地合回 `main`

交付物：

- 一份离线 A/B 对比报告
- 一次最小跨仓真实评测记录
- 一条明确的录取结论

## SpecFlow Analysis

### User Flow Overview

1. 开发者先在 `main` 冻结共享底座与实验契约。
2. 开发者从同一提交点创建 `worktree-a` 与 `worktree-b`。
3. 两个 worktree 各自只在允许范围内完成独立方向调优。
4. 双方使用同一 benchmark 输入集运行 A/B。
5. runner 生成统一产物与 leaderboard。
6. 团队按 recall-first 规则做录取决定。
7. 若需要推广胜方，再把胜方实现有选择地回收进主线。

其中第 4 步之前，应先完成一轮开发数据阶段：

- A、B 各自用无标记论文做开发
- 人工标注 benchmark 在录取前不参与反复调参

### Missing Elements & Gaps

- **Category**: Route Selection
  - **Gap Description**: 需要明确 A、B 首轮分别采用哪两类独立方法。
  - **Impact**: 若两边方法过于相似，就失去 A/B 的意义；若任一方不够真实，就失去比较价值。
  - **Default**: A 采用 `embedding / 相似度召回 + 阈值二分类`，B 采用 `规则预过滤 + LLM 裁决`。

- **Category**: Challenger Scope
  - **Gap Description**: 每个 worktree 首轮都只能落一条真实路线，不能把多个方向混成一团。
  - **Impact**: 若同时混入 LLM、embedding、两阶段多个思路，就失去路线独立性与可解释性。
  - **Default**: B 路线固定为“两阶段但单主思路”：规则负责高召回候选过滤，LLM 只负责候选裁决。

- **Category**: LLM Throughput
  - **Gap Description**: 若 B 路线直接全量调用 LLM，首轮实验成本与迭代速度都可能不可接受。
  - **Impact**: 会拖慢 prompt 调优、错误分析和回归节奏。
  - **Default**: 先用规则把明显负样本挡在外面，只把候选子集送给 LLM。

- **Category**: Data Boundary
  - **Gap Description**: 如果把人工标注 benchmark 当开发集反复使用，A/B 结果会产生明显泄漏。
  - **Impact**: 最终验收分数失真，无法反映真实泛化效果。
  - **Default**: 开发阶段只使用无标记论文；人工标注数据只用于最终验收。

- **Category**: Promotion Rule
  - **Gap Description**: 胜方回收进主线时，哪些文件允许合并、哪些实验垃圾必须留在 worktree。
  - **Impact**: 关系到是否污染主线。
  - **Default**: 只回收胜方 route 实现、必要配置和最小测试，不回收临时实验脚本与中间产物。

### Critical Questions Requiring Clarification

本计划先按以下默认假设继续，不阻塞规划：

1. **Critical**: A、B 都必须是独立方向的真实算法方案，不能出现 stub 对真算法、或同一路线小改参数的伪 A/B。
2. **Critical**: `worktree-a` 与 `worktree-b` 都必须复用同一 runner 和同一 metrics 口径。
3. **Important**: B 路线必须通过规则层缩小 LLM 处理范围，不直接对全量数据逐条调用 LLM。
4. **Critical**: 人工标注数据只允许作为测试验收依据，不能作为开发集、调参集或 prompt 迭代集使用。
5. **Important**: 录取标准严格遵循 recall-first，不因某条路线 precision 更高就忽略召回损失。

## Acceptance Criteria

- [ ] 首轮 A/B 只比较 `positive/negative`，不把子类标签作为胜负主指标。
- [ ] `worktree-a` 与 `worktree-b` 都有各自可运行的 ready 路线。
- [ ] A、B 两条路线在方法上属于彼此独立的真实方向，而不是同一方法的轻微改写。
- [ ] A 路线明确为 `embedding_similarity_binary`，B 路线明确为 `rule_filtered_llm_binary`。
- [ ] B 路线先经过规则预过滤，再把候选集交给 LLM 裁决，而不是全量数据直送 LLM。
- [ ] 开发阶段只使用无标记论文，来源为仓内 `paper_analysis` 论文链路或 arXiv API。
- [ ] 人工标注数据只在最终统一验收时使用，不回流到开发调优环节。
- [ ] 双方使用同一输入集、同一 runner、同一 metrics 口径、同一结果目录协议。
- [ ] 双方的 `algorithm_version` 可被明确区分并写入产物。
- [ ] 同一轮对比后能清晰给出 recall、precision、f1 与失败情况。
- [ ] 最终能得出“录取 / 保留观察 / 淘汰”之一的明确结论。
- [ ] 主仓现有评测 API schema 与最小跨仓 e2e 不回归。

## Success Metrics

- 团队可以在不改共享底座的前提下，完成一次 `worktree-a` 的 `embedding_similarity_binary` vs `worktree-b` 的 `rule_filtered_llm_binary` 真实二分类对打。
- 首轮就能用统一报告回答“哪条真实路线 recall 更稳、谁综合更优、谁更适合作为下一阶段底座”。
- 最终验收结果不依赖人工标注数据泄漏到开发阶段，仍具备独立比较价值。
- 胜方被回收进主线时，不需要重写 runner、协议和 artifact schema。

## Dependencies & Risks

### Dependencies

- 依赖现有 A/B scaffold 代码继续作为共享底座可用 [paper_analysis/evaluation/ab_runner.py](D:/Git_Repo/Paper-Analysis-New/paper_analysis/evaluation/ab_runner.py)。
- 依赖现有跨仓评测链路继续可运行 [tests/e2e/test_evaluation_api.py](D:/Git_Repo/Paper-Analysis-New/tests/e2e/test_evaluation_api.py)。
- 依赖团队遵守 worktree 边界，不把实验改动直接混入主线共享文件，并确保两个 worktree 都从同一共享底座提交点拉出 `(see origin: docs/brainstorms/2026-03-30-decoding-strategy-ab-requirements.md)`。

### Risks

- **风险**: A、B 两边方法本质过于接近，最后比出来的只是局部调参差异。
  - **缓解**: 在进入实现前先明确两边的方法学边界，要求一边一类主思路。

- **风险**: B 路线把全量数据都交给 LLM，导致成本和迭代耗时失控。
  - **缓解**: 先实现高召回规则预过滤，把 LLM 调用收缩到候选子集。

- **风险**: 人工标注数据在开发阶段被反复查看和调参使用，导致验收污染。
  - **缓解**: 明确开发数据与验收数据隔离；开发只用无标记论文，人工标注 benchmark 只在最终录取时启用。

- **风险**: worktree 过度调优，顺手改了共享 runner 或报表逻辑。
  - **缓解**: 先冻结共享底座白名单，评审时重点看越界修改。

- **风险**: 首轮把实验目标做复杂，混入子类、多阶段和多挑战者，导致无法收敛。
  - **缓解**: 只允许两条真实路线参赛，只比较 `positive/negative`。

## Sources & References

- **Origin document:** [docs/brainstorms/2026-03-30-decoding-strategy-ab-requirements.md](D:/Git_Repo/Paper-Analysis-New/docs/brainstorms/2026-03-30-decoding-strategy-ab-requirements.md)
- Similar implementation:
  [docs/plans/2026-03-30-002-feat-main-branch-ab-scaffold-plan.md](D:/Git_Repo/Paper-Analysis-New/docs/plans/2026-03-30-002-feat-main-branch-ab-scaffold-plan.md)
- Shared scaffold:
  [paper_analysis/evaluation/ab_runner.py](D:/Git_Repo/Paper-Analysis-New/paper_analysis/evaluation/ab_runner.py)
- Route registry:
  [paper_analysis/evaluation/route_registry.py](D:/Git_Repo/Paper-Analysis-New/paper_analysis/evaluation/route_registry.py)
- Public evaluation API:
  [paper_analysis/api/evaluation_server.py](D:/Git_Repo/Paper-Analysis-New/paper_analysis/api/evaluation_server.py)
- Public schema:
  [paper_analysis/api/evaluation_protocol.py](D:/Git_Repo/Paper-Analysis-New/paper_analysis/api/evaluation_protocol.py)
- Cross-repo minimal e2e:
  [tests/e2e/test_evaluation_api.py](D:/Git_Repo/Paper-Analysis-New/tests/e2e/test_evaluation_api.py)
- Institutional learning:
  [docs/solutions/integration-issues/cli-structured-failure-and-windows-utf8-compatibility.md](D:/Git_Repo/Paper-Analysis-New/docs/solutions/integration-issues/cli-structured-failure-and-windows-utf8-compatibility.md)
- Institutional learning:
  [docs/solutions/integration-issues/skill-usage-contract-without-development-guidance.md](D:/Git_Repo/Paper-Analysis-New/docs/solutions/integration-issues/skill-usage-contract-without-development-guidance.md)
