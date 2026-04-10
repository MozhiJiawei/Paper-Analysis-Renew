---
title: feat: 收敛推荐算法研究对象四分类
type: feat
status: active
date: 2026-04-11
---

# feat: 收敛推荐算法研究对象四分类

## Overview

本计划聚焦两件绑定在一起的事情：

1. 把当前推荐算法中的 `primary_research_object` 判定，收敛为一个更稳定的四分类能力：`LLM`、`VLM`、`Diffusion`、`其他`
2. 同步修改评测逻辑，使“研究对象”和“研究子类 / preference_labels”指标都只在 `negative_tier=positive` 的样本子集上统计；负样本因为没有经过这两个维度的人工标注，不作为对应维度 precision / recall / accuracy 的依据

这里的“其他”不是新增一个独立产品命名空间，而是指将截图中除 `LLM`、`多模态 / VLM`、`Diffusion / 生成模型` 之外的研究对象统一并桶处理。

约束重点有三个：

1. 数据 schema、数据协议、现有 `RESEARCH_OBJECT_LABELS` 枚举都不能改。
2. 保持当前评测 API / 推荐链路的稳定边界，不新开 `recommend` 顶层命名空间。
3. 在当前代码基础上，把启发式分类、评测口径、测试夹具与跨仓评测契约一起收敛，而不是只改一处关键词表。

## Problem Statement / Motivation

当前仓库已经具备“研究对象”字段，并且数据已经按当前 schema 完成标注；因此这次改造不能动数据协议，只能在算法与评测口径层做收敛：

- 公共协议当前允许 10 个 `primary_research_object` 标签，包括 `强化学习 / 序列决策`、`检索 / 推荐 / 搜索`、`计算机视觉`、`语音 / 音频`、`AI 系统 / 基础设施`、`评测 / Benchmark / 数据集` 等 [paper_analysis/api/evaluation_protocol.py](D:/Git_Repo/Paper-Analysis-New/paper_analysis/api/evaluation_protocol.py)。
- 子仓 benchmark 域模型也把同一组 `RESEARCH_OBJECT_LABELS` 当作数据协议常量使用 [third_party/paper_analysis_dataset/paper_analysis_dataset/domain/benchmark.py](D:/Git_Repo/Paper-Analysis-New/third_party/paper_analysis_dataset/paper_analysis_dataset/domain/benchmark.py)。
- 启发式预测器当前也是按这些细标签顺序匹配关键词 [paper_analysis/api/evaluation_predictor.py](D:/Git_Repo/Paper-Analysis-New/paper_analysis/api/evaluation_predictor.py)。
- 真实 e2e 会校验评测服务返回合法 schema，因此如果只改分类逻辑、不同时更新协议与回归，容易造成跨仓契约漂移 [tests/e2e/test_evaluation_api.py](D:/Git_Repo/Paper-Analysis-New/tests/e2e/test_evaluation_api.py)。

这带来四个问题：

- 当前字段语义和用户需要的“研究对象四分类视角”不一致。
- 现有细粒度标签会让规则维护复杂化，且不利于后续围绕 LLM/VLM/Diffusion 做专项偏好分析。
- 如果直接把输出改成 `其他`，会立刻与当前 schema 枚举冲突，因此“其他”只能作为算法与评测内部聚合概念，不能直接改写数据协议标签。
- 当前子仓评测报告会把全部样本都纳入研究对象和研究子类指标统计，但负样本没有经过这两个维度的人工标注，不适合作为对应分类准确率、召回率的真值依据 [third_party/paper_analysis_dataset/paper_analysis_dataset/services/evaluation_reporter.py](D:/Git_Repo/Paper-Analysis-New/third_party/paper_analysis_dataset/paper_analysis_dataset/services/evaluation_reporter.py)。

## Proposed Solution

采用“内部四分类聚合 + 外部协议完全保持不变”的方案，在不修改任何数据 schema / 数据协议的前提下完成一次可测试、可演进的算法改造。

### 1. 先定义新的目标语义

新的研究对象识别逻辑在算法内部只保留四个目标桶：

- `LLM`
- `VLM`
- `Diffusion`
- `其他`

分类原则：

- 命中 `LLM` 相关关键词时，识别为 `LLM`
- 命中多模态 / vision-language 相关关键词时，识别为 `VLM`
- 命中 diffusion / denoising / DiT 等关键词时，识别为 `Diffusion`
- 当前 schema 中其余枚举分类，包括但不限于 `通用机器学习`、`强化学习 / 序列决策`、`检索 / 推荐 / 搜索`、`计算机视觉`、`语音 / 音频`、`AI 系统 / 基础设施`、`评测 / Benchmark / 数据集`，在算法分析与评测聚合时统一归为 `其他`

### 2. 明确“当前 schema 下”的承载方式

这次规划明确采用“协议层完全不动、算法层内部聚合”的解释，也就是：

- `paper_analysis/api/evaluation_protocol.py` 里的 `RESEARCH_OBJECT_LABELS` 不改
- `third_party/paper_analysis_dataset/paper_analysis_dataset/domain/benchmark.py` 里的 `RESEARCH_OBJECT_LABELS` 不改
- 已有数据文件中的 `primary_research_object` 取值不改

四分类只作为内部识别与评测聚合视角存在：

- `LLM` 对应当前协议标签 `LLM`
- `VLM` 对应当前协议标签 `多模态 / VLM`
- `Diffusion` 对应当前协议标签 `Diffusion / 生成模型`
- `其他` 对应当前协议中的其余全部合法枚举

也就是说，推荐算法对外仍只能输出当前 schema 合法值，但在内部逻辑与评测报表中，只把它们分成四个桶来处理。

### 3. 把规则实现从“细粒度枚举表”改成“四分类优先级表”

当前 `PRIMARY_RESEARCH_OBJECT_RULES` 需要重写为“只主动识别三类、其余统一回退到现有 schema 下的其他类”的版本，并显式管理优先级冲突：

- `多模态 / VLM` 需要优先于 `LLM`
  - 原因：很多多模态论文会同时提到 language model / transformer，如果先匹配 `LLM`，会把 VLM 误归为 LLM
- `Diffusion / 生成模型` 与 `多模态 / VLM` 需要都优先于其他类
- 对外返回时，fallback 不能直接写 `其他`，而应统一回退到一个现有 schema 合法值

建议默认回退到：

- `通用机器学习`

同时在评测聚合层把下面这些现有标签都映射进内部 `其他` 桶：

- `通用机器学习`
- `强化学习 / 序列决策`
- `检索 / 推荐 / 搜索`
- `计算机视觉`
- `语音 / 音频`
- `AI 系统 / 基础设施`
- `评测 / Benchmark / 数据集`

建议规则表按以下顺序组织：

1. `VLM`
2. `Diffusion`
3. `LLM`
4. `通用机器学习`（对外 fallback；内部聚合视为 `其他`）

### 4. 同步更新公共协议与 fixture

由于这次不允许改 schema / 数据协议，这一阶段不修改协议枚举，而是同步更新实现与测试：

- `paper_analysis/api/evaluation_predictor.py`
  - 收敛规则表，只主动识别 `LLM`、`多模态 / VLM`、`Diffusion / 生成模型`
  - 默认回退到现有 schema 合法值 `通用机器学习`
- 评测聚合层
  - 引入“研究对象四桶映射”，把现有 10 类协议标签映射为 `LLM` / `VLM` / `Diffusion` / `其他`
- `tests/fixtures/evaluation/annotate_request.json`
  - 如有必要，补充能命中 VLM / Diffusion / 其他的样例
- 相关 unit / integration / e2e 测试
  - 断言协议本身不变
  - 断言新的三类识别 + 其他聚合映射

### 5. 让“其他”成为评测中的正式聚合桶

不要把“其他”写进数据 schema，也不要把现有数据重写成 `其他`。正确做法是：

- 数据层继续保存当前 schema 合法值
- 算法层默认把未命中三类的论文输出为现有合法值 `通用机器学习`
- 评测层新增一个稳定映射函数，把所有非 `LLM` / `多模态 / VLM` / `Diffusion / 生成模型` 的 truth / prediction 统一映射到内部聚合桶 `其他`
- 报告层明确展示“研究对象四分类聚合结果”，而不是宣称数据协议已经变成四类

### 6. 同步收敛研究对象评测口径

研究对象与研究子类维度的评测都不再基于“全部样本”统计，而是切换为“仅正样本子集”统计：

- `negative_tier=positive` 的样本：
  - 其 `primary_research_object` 先映射到内部四桶之一，作为研究对象真值
  - 其唯一 `preference_label` 作为研究子类真值
  - 参与研究对象分类的 support、precision、recall、f1 或 accuracy 统计
  - 参与研究子类分类的 support、precision、recall、f1 或 accuracy 统计
- `negative_tier=negative` 的样本：
  - 仅参与正负样本识别维度的评测
  - 不参与研究对象维度的准确率、召回率、F1 统计
  - 不参与研究子类维度的准确率、召回率、F1 统计

建议把评测语义写得非常显式：

- overall 中单独保留“正负样本识别”全量口径
- 研究子类指标改成“正样本条件下”的分类指标，而不是继续混入负样本
- 新增或重写 `by_primary_research_object` 为“正样本条件下的四分类聚合指标”
- 如需保留说明文字，报告中应直接写明“负样本未标注研究对象和研究子类，不纳入这两个维度统计；数据协议标签已按四桶聚合后再评测”

## Technical Considerations

- **协议兼容性**: `primary_research_object` 是公开评测响应字段，这次不能改其字段结构和允许枚举，只能改算法返回策略与评测聚合逻辑。
- **关键词优先级**: `multimodal` / `vision-language` 论文常同时携带 `language model` 词汇，规则顺序不对会放大误分类。
- **回退语义**: “其他”是内部聚合桶，不是新的协议值；对外 fallback 应继续使用现有合法标签 `通用机器学习`。
- **中英文混合文本**: 当前实现同时读 `title`、`abstract`、`abstract_zh`、`keywords`，四分类规则应继续覆盖中英文字段，避免中文摘要命中率下降。
- **迁移边界**: 任何仍依赖“研究对象指标按原 10 类逐类评测”的断言、报表或测试，都需要被定位并改成四桶聚合。
- **评测真值边界**: 研究对象和研究子类两个维度都不能把负样本当成有标注样本使用，否则会把“未标注”误当作“分类错误”或“分类正确”。
- **报告语义**: 子仓 `report.json` / `summary.md` 需要明确哪些指标是全量样本统计，哪些指标只在正样本子集统计。

## System-Wide Impact

- **Interaction graph**: `POST /v1/evaluation/annotate` -> `EvaluationPredictor.predict()` -> `_predict_primary_research_object()` 返回当前 schema 合法值 -> `EvaluationPrediction` schema 校验 -> 子仓 `evaluation_reporter` 把 truth / prediction 映射成四个聚合桶，并把研究对象/研究子类指标限制在正样本子集上汇总 -> 主仓 e2e / 子仓评测消费结果。
- **Error propagation**: 如果预测器直接返回 `其他`，`EvaluationPrediction` 会因 `primary_research_object` 非法而直接报错；如果评测层没做四桶映射，研究对象指标会继续按旧 10 类统计并混入负样本噪声。
- **State lifecycle risks**: 历史 artifact 或 fixture 继续保留旧标签是允许的，但报告层若不说明“四桶聚合”和“仅正样本”，容易被误读。
- **API surface parity**: 公开 API、测试夹具、跨仓 benchmark 的字段与枚举保持不变；只有评测聚合和推荐算法识别范围发生变化。
- **Integration test scenarios**:
  - LLM 论文继续返回 `LLM`
  - 多模态论文返回 `多模态 / VLM`，而不是 `LLM`
  - diffusion 论文返回 `Diffusion / 生成模型`
  - 计算机视觉 / 检索 / RL / benchmark 论文对外继续返回当前 schema 合法值，但在评测聚合中统一落到 `其他`
  - 负样本即使带有候选 `primary_research_object`，也不会被计入研究对象 precision / recall
  - 负样本不会被计入研究子类 precision / recall
  - 报告能够区分“全量正负样本指标”和“正样本研究对象 / 研究子类指标”
  - 子仓真实评测流程在新标签集合下仍可跑通

## Research Summary

### Local Repository Findings

- 当前主实现已经有研究对象规则表，但它是细分类规则，不是四分类规则 [paper_analysis/api/evaluation_predictor.py](D:/Git_Repo/Paper-Analysis-New/paper_analysis/api/evaluation_predictor.py)。
- 当前公开协议会严格校验 `primary_research_object` 是否属于允许枚举 [paper_analysis/api/evaluation_protocol.py](D:/Git_Repo/Paper-Analysis-New/paper_analysis/api/evaluation_protocol.py)。
- 子仓 benchmark 域模型同样会校验 `primary_research_object` 必须属于现有 `RESEARCH_OBJECT_LABELS`，说明数据协议不能动 [third_party/paper_analysis_dataset/paper_analysis_dataset/domain/benchmark.py](D:/Git_Repo/Paper-Analysis-New/third_party/paper_analysis_dataset/paper_analysis_dataset/domain/benchmark.py)。
- 子仓当前 `evaluation_reporter` 会对研究子类和研究对象沿用全量样本口径，还没有把“仅正样本”做成显式统计口径 [third_party/paper_analysis_dataset/paper_analysis_dataset/services/evaluation_reporter.py](D:/Git_Repo/Paper-Analysis-New/third_party/paper_analysis_dataset/paper_analysis_dataset/services/evaluation_reporter.py)。
- 现有 e2e 会真实拉起评测服务并校验返回 schema，因此这次改造不能只改单测 [tests/e2e/test_evaluation_api.py](D:/Git_Repo/Paper-Analysis-New/tests/e2e/test_evaluation_api.py)。
- 仓库约束要求“推荐”是共享内部阶段能力，不单独扩成新命名空间；本需求应落在现有评测 / 推荐内部能力里，而不是新增 CLI 面 [docs/agent-guide/command-surface.md](D:/Git_Repo/Paper-Analysis-New/docs/agent-guide/command-surface.md) [.codex/skills/paper-analysis/SKILL.md](D:/Git_Repo/Paper-Analysis-New/.codex/skills/paper-analysis/SKILL.md)。

### Institutional Learnings

- [docs/solutions/integration-issues/skill-usage-contract-without-development-guidance.md](D:/Git_Repo/Paper-Analysis-New/docs/solutions/integration-issues/skill-usage-contract-without-development-guidance.md)
  - 启发：职责边界要写成显式契约。迁移到本需求，就是“四分类语义”不能只藏在实现细节里，必须反映到 schema / 测试 / 文档契约。
- [docs/solutions/integration-issues/cli-structured-failure-and-windows-utf8-compatibility.md](D:/Git_Repo/Paper-Analysis-New/docs/solutions/integration-issues/cli-structured-failure-and-windows-utf8-compatibility.md)
  - 启发：边界层契约变化要一次性打通输入、输出和回归检查。迁移到本需求，就是不能只改规则表，还要同步 fixture、协议和 e2e。

### External Research Decision

不做外部研究。当前问题的关键约束来自仓库内现有协议与评测链路，本地上下文已经足够支撑规划。

## SpecFlow Analysis

### User Flow Overview

1. 开发者或评测子仓向主仓 `POST /v1/evaluation/annotate` 发送论文请求。
2. 主仓读取论文标题、英文摘要、中文摘要和关键词。
3. 研究对象分类器按四分类优先级表判断：
   - 优先判断 `多模态 / VLM`
   - 再判断 `Diffusion / 生成模型`
   - 再判断 `LLM`
   - 若都未命中，则回退到当前 schema 合法值 `通用机器学习`
4. 协议层校验返回标签仍属于现有 schema 枚举。
5. 子仓评测器按两套口径汇总：
   - 全量样本：只统计正负样本识别
   - 正样本子集：先把现有 schema 标签映射到四个聚合桶，再统计研究对象分类和研究子类分类
6. e2e、跨仓 benchmark 和报告生成消费“不改协议的输出”与“新的正样本限定评测口径”。

### Missing Elements & Gaps

- **Category**: Schema migration
  - **Gap Description**: 当前已经确认 schema 不能改，因此不再做协议迁移；需要改成检查“哪些地方需要新增四桶聚合映射”。
  - **Impact**: 如果漏掉任一评测入口，最终会出现“输出还是 10 类、评测却没有聚合”的不一致。
  - **Default**: 规划中按“新增聚合映射函数并统一复用”处理。

- **Category**: Fixture coverage
  - **Gap Description**: 当前主仓 e2e fixture 主要覆盖 LLM 场景，缺少 VLM、Diffusion、其他三类样例。
  - **Impact**: 仅靠单一 LLM fixture 无法证明四分类真正生效。
  - **Default**: 新增或扩展 unit / integration fixture，使四个桶都有最小样例。

- **Category**: Historical artifact semantics
  - **Gap Description**: 旧 artifact 或既有人工审核页若引用旧标签文案，可能需要清理或适配。
  - **Impact**: 可能造成同一页面上同时出现旧标签与新标签。
  - **Default**: 新运行产物以新标签为准，不追求历史 artifact 回写迁移。

- **Category**: Research-object metrics shape
  - **Gap Description**: 需要明确 `by_primary_research_object` 是继续只保留 accuracy，还是升级为 precision / recall / f1 + support。
  - **Impact**: 你已经明确提到了“准确率、召回率”，这意味着报告结构很可能需要扩展，而不是只改过滤逻辑。
  - **Default**: 规划中按“正样本子集上的四桶聚合结果提供至少 precision / recall / f1 / support，必要时保留 accuracy 作为补充”处理。

- **Category**: Preference metrics scope
  - **Gap Description**: 当前偏好标签评测默认混合了负样本，需要收敛为“仅正样本研究子类评测”。
  - **Impact**: 如果不改，研究子类指标会继续受未标注负样本干扰。
  - **Default**: 规划中按“正样本子集上统计唯一 preference_label 的 precision / recall / f1 / support”处理。

### Critical Questions Requiring Clarification

本计划默认按以下假设继续，不阻塞规划：

1. **Critical**: schema、数据协议、已有数据枚举都不改。
2. **Critical**: `其他` 只是算法与评测内部的聚合桶，不是新的输出标签。
3. **Important**: 截图中除 `LLM`、`多模态 / VLM`、`Diffusion / 生成模型` 外的所有研究对象，全部在评测聚合时合并入 `其他`。
4. **Important**: 本次需求不新增新的 CLI 命令或顶层命名空间，只更新内部算法、评测、测试与必要文档。
5. **Critical**: 研究对象维度和研究子类维度的 precision / recall / f1 都只在 `negative_tier=positive` 的样本子集上统计；负样本不构成这两个维度的真值。

### Recommended Next Steps

- 先实现统一的“四桶聚合映射函数”，避免不同模块各自理解 `其他`。
- 再改预测器规则，只主动识别 `LLM`、`多模态 / VLM`、`Diffusion / 生成模型`，其余回退为 `通用机器学习`。
- 为四个聚合桶各补一组最小正例 fixture，优先覆盖最容易误判的 `VLM vs LLM`。
- 跑主仓 e2e 与跨仓最小评测，确认协议不变但四桶聚合评测口径生效。
- 若报告或文档展示研究对象指标，同步更新文案，明确这是“四桶聚合结果”，不是 schema 变更。

## Acceptance Criteria

- [ ] schema、数据协议与现有 `RESEARCH_OBJECT_LABELS` 常量保持不变
- [ ] `EvaluationPredictor` 的研究对象判定规则只主动识别 `LLM`、`多模态 / VLM`、`Diffusion / 生成模型`
- [ ] 未命中三类的论文对外回退到当前 schema 合法值 `通用机器学习`
- [ ] 截图中其余研究对象在评测聚合时统一映射为内部桶 `其他`
- [ ] 至少补充覆盖 `LLM`、`VLM`、`Diffusion`、`其他` 四个聚合桶的测试样例
- [ ] 多模态论文不会因含有 `language model` 词汇而误判为 `LLM`
- [ ] 研究对象维度的评测仅基于 `negative_tier=positive` 的样本子集
- [ ] `negative_tier=negative` 的样本不会计入研究对象 accuracy / precision / recall / f1
- [ ] 研究子类维度的评测仅基于 `negative_tier=positive` 的样本子集
- [ ] `negative_tier=negative` 的样本不会计入研究子类 accuracy / precision / recall / f1
- [ ] 子仓评测报告明确展示“全量正负样本识别 + 正样本子集上的研究对象/研究子类指标”口径，并在文案中说明负样本未标注这两个维度
- [ ] 主仓真实评测 API e2e 继续通过
- [ ] 子仓真实评测 CLI 调主仓接口的最小 e2e 在新标签集合下继续通过
- [ ] 若报告或文档涉及研究对象评测展示，相关文案同步更新并保持 UTF-8

## Success Metrics

- 主仓 API 输出继续完全符合当前 schema，没有因为本次需求引入任何新协议值。
- 规则实现维护成本下降，新增论文样例时只需要判断三类显式识别目标和一个聚合桶，而不是在多个细分类之间摇摆。
- 主仓与子仓评测链路都能稳定消费内部 `其他` 聚合概念，不再把截图中的长尾研究对象拆成多个评测桶。
- 研究对象维度和研究子类维度指标都不再被未标注负样本稀释，正样本子集上的 precision / recall / f1 能真实反映分类效果。

## Dependencies & Risks

- **Dependency**: 依赖主仓与子仓都允许在不改 schema 的前提下新增统一的研究对象聚合映射。
- **Dependency**: 依赖现有测试体系可以方便补充多类别 fixture。
- **Risk**: 不同模块各自实现“其他”的聚合规则，导致统计口径不一致。
  - **Mitigation**: 提供单一聚合映射函数，由主仓与子仓统一复用。
- **Risk**: `VLM` 与 `LLM` 关键词重叠导致误判。
  - **Mitigation**: 用优先级规则和专门测试用例锁定。
- **Risk**: 把所有长尾类别直接并入 `其他` 后，细分类评测视角丢失。
  - **Mitigation**: 明确这是评测层的聚合口径收敛，不影响原始数据中保留旧细分类值。
- **Risk**: 研究对象或研究子类评测只改过滤条件、不改报表 schema，导致使用者误以为仍然是全量统计。
  - **Mitigation**: 在 `report.json` 与 `summary.md` 中显式增加“正样本研究对象指标 / 正样本研究子类指标”说明字段或标题。
- **Risk**: 子仓测试和注释工具仍把负样本的候选研究对象当成真值使用。
  - **Mitigation**: 把评测器、相关 unit tests、报告文案与 benchmark 说明一起调整。

## Sources & References

- [paper_analysis/api/evaluation_predictor.py](D:/Git_Repo/Paper-Analysis-New/paper_analysis/api/evaluation_predictor.py)
- [paper_analysis/api/evaluation_protocol.py](D:/Git_Repo/Paper-Analysis-New/paper_analysis/api/evaluation_protocol.py)
- [paper_analysis/evaluation/route_registry.py](D:/Git_Repo/Paper-Analysis-New/paper_analysis/evaluation/route_registry.py)
- [tests/e2e/test_evaluation_api.py](D:/Git_Repo/Paper-Analysis-New/tests/e2e/test_evaluation_api.py)
- [tests/fixtures/evaluation/annotate_request.json](D:/Git_Repo/Paper-Analysis-New/tests/fixtures/evaluation/annotate_request.json)
- [third_party/paper_analysis_dataset/paper_analysis_dataset/domain/benchmark.py](D:/Git_Repo/Paper-Analysis-New/third_party/paper_analysis_dataset/paper_analysis_dataset/domain/benchmark.py)
- [third_party/paper_analysis_dataset/paper_analysis_dataset/services/evaluation_reporter.py](D:/Git_Repo/Paper-Analysis-New/third_party/paper_analysis_dataset/paper_analysis_dataset/services/evaluation_reporter.py)
- [docs/agent-guide/command-surface.md](D:/Git_Repo/Paper-Analysis-New/docs/agent-guide/command-surface.md)
- [docs/engineering/testing-and-quality.md](D:/Git_Repo/Paper-Analysis-New/docs/engineering/testing-and-quality.md)
- [docs/solutions/integration-issues/skill-usage-contract-without-development-guidance.md](D:/Git_Repo/Paper-Analysis-New/docs/solutions/integration-issues/skill-usage-contract-without-development-guidance.md)
- [docs/solutions/integration-issues/cli-structured-failure-and-windows-utf8-compatibility.md](D:/Git_Repo/Paper-Analysis-New/docs/solutions/integration-issues/cli-structured-failure-and-windows-utf8-compatibility.md)
