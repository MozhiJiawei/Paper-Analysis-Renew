---
title: feat: Add conference paperlists ingestion flow
type: feat
status: completed
date: 2026-03-19
---

# feat: Add conference paperlists ingestion flow

## Overview

为 `conference` 命名空间接入 `papercopilot/paperlists` 作为真实数据源，替换当前仅依赖本地样例 JSON 的验证模式。第一阶段不实现偏好筛选算法，仅完成：

- 通过 git submodule 引入 `paperlists`
- 解析其顶会 JSON 文件并归一化到本仓库 `Paper` 领域模型
- 仅保留“已录用”论文
- 以随机 10 篇作为功能验证输出
- 复用现有 `conference filter` / `conference report` 链路生成 stdout、Markdown、JSON、CSV 报告

该方案保持仓库现有边界：业务仍归属 `conference`，不新增 `recommend` 命名空间。

## Problem Statement / Motivation

当前 `conference` 流程只能读取 `tests/fixtures/conference/sample_papers.json`，更像工程脚手架验证，无法证明系统具备处理真实顶会数据的能力。用户当前最需要的是跑通一条“真实数据 -> 归一化 -> 报告输出”的最小闭环，而不是提前设计完整的推荐算法。

因此本次工作应优先解决三个问题：

1. 如何以稳定方式把 `paperlists` 纳入仓库，并让 CLI 能访问它。
2. 如何为 `paperlists` 不完全统一的会议 JSON 设计一个可扩展解析层。
3. 如何在暂不实现真实排序时，仍用随机 10 篇验证 `conference` 全链路可用。

## Proposed Solution

### 1. 数据源接入

将 `https://github.com/papercopilot/paperlists` 作为只读 git submodule 接入，例如放在 `third_party/paperlists/`。这样可以：

- 保持数据源版本可追踪
- 避免把大批原始 JSON 直接复制进主仓
- 允许后续通过固定 submodule commit 重现实验结果

同时在仓库文档中补充 submodule 初始化与更新命令，确保本地和 CI 行为一致。

### 2. 文件格式分析与解析设计

根据 `paperlists` README，可确认其数据按“会议目录 / 年份 JSON 文件”组织，例如：

- `iclr/iclr2025.json`
- `nips/nips2024.json`
- `cvpr/cvpr2024.json`

README 中 `tools/extract.py` 的默认搜索字段包含 `keywords`、`title`、`primary_area`、`topic`，说明记录至少常见地包含主题类字段。结合仓库定位“Processed / Cleaned Data for Paper Copilot”，可以合理推断不同会议年份文件整体为 JSON 数组，但字段集合可能并不完全一致。

解析层不应把 `paperlists` JSON 直接强绑到当前 `Paper(**item)`。应增加两层模型：

1. `PaperlistsRawRecord`
   - 保存原始字典、来源会议、年份、文件路径
   - 负责抽取常见字段并保留未知字段，便于兼容不同会议格式
2. `NormalizedConferencePaper`
   - 统一映射为本仓库报告与后续排序可消费的字段
   - 必填目标字段应覆盖：
     - `paper_id`
     - `title`
     - `abstract`
     - `source`
     - `venue`
     - `authors`
     - `tags`
     - `organization`
     - `published_at`
   - 另建议补充保留字段：
     - `acceptance_status`
     - `primary_area`
     - `topic`
     - `keywords`
     - `pdf_url`
     - `project_url`
     - `code_url`
     - `openreview_url`
     - `raw_payload`

建议实现为“目录级公共适配器 + 会议特定回退规则”：

- 公共规则负责识别常见同义字段，如 `author`/`authors`、`aff`/`organization`、`keywords`/`topic`
- 会议特定规则负责处理少数目录中的异构字段与特殊状态命名
- 若关键字段缺失，不直接崩溃；应落入结构化 `CliInputError` 或解析告警统计

### 3. 仅关注已录用论文

本阶段只分析被录用论文。由于不同会议状态字段可能不同，建议把“已录用”判断抽象为独立策略：

- 优先读取显式状态字段，如 `status`、`acceptance_status`、`decision`
- 若无统一状态字段，则根据目录语义处理：
  - 对官方“paperlist/accepted list”目录视为默认已录用
  - 若单文件混有 withdrawn/rejected/poster/oral 等标签，仅保留明确 accepted 的记录
- `oral`、`spotlight`、`poster` 只要属于 accepted 子集，应视为保留，而不是误删

需要把判定逻辑单独放在 `conference` 源适配层，避免污染未来真实偏好排序逻辑。

### 4. 随机 10 篇功能验证

在排序算法留空的前提下，`conference filter` 第一阶段不走 `PreferenceRanker.rank()` 的真实偏好逻辑，而是：

- 从“已录用且成功归一化”的候选集中采样 10 篇
- 若不足 10 篇，则返回全部
- 为保证集成测试稳定，CLI 应支持注入随机种子，例如内部默认使用固定 seed，或显式提供 `--seed`

这样既能满足“先随机抽样验证链路”，又不会让 e2e 测试因非确定性而抖动。

### 5. 报告输出设计

复用 `paper_analysis/services/report_writer.py` 的报告写出模式，但需要从当前 Markdown / JSON / stdout 三产物扩展到 Markdown / JSON / stdout / CSV 四产物，使报告既适合程序消费，也适合后续人工筛查。

建议输出：

- stdout
  - 会议、年份、已录用候选总数、最终输出数量
  - 每篇显示 `title | venue | sampled`
- `summary.md`
  - 标题、命令、数据源路径、采样 seed、候选总量、输出总量
  - 每篇至少展示：
    - 标题
    - 作者
    - 机构
    - 会议/年份
    - 主题标签
    - 接收状态
    - 链接字段（PDF/OpenReview/Project/Code，有则展示）
- `result.json`
  - 除现有字段外，补充原始来源元数据，便于后续推荐算法接入
- `result.csv`
  - 面向人工分析与二次筛选
  - 一行一篇论文，列尽量扁平化，避免嵌套 JSON
  - 建议至少包含：
    - `paper_id`
    - `title`
    - `venue`
    - `year`
    - `acceptance_status`
    - `authors`
    - `organization`
    - `primary_area`
    - `topic`
    - `keywords`
    - `pdf_url`
    - `project_url`
    - `code_url`
    - `openreview_url`
    - `sampled_reason`
  - 多值字段如 `authors`、`keywords` 建议用稳定分隔符拼接，优先使用 ` | `，降低人工在 Excel/表格工具中查看时的歧义

## Technical Considerations

- 子仓路径应固定，避免未来数据源切换时散落硬编码。
- `ConferencePipeline` 当前默认从 `tests/fixtures/conference/sample_papers.json` 加载；接入真实源后，应改为“样例模式”和“paperlists 模式”并存，避免破坏现有最小测试。
- 当前 `Paper` 模型中的 `organization` 为单值字符串，但真实会议论文常有多作者多机构；第一阶段可降级为主机构或拼接字符串，后续再演进为列表字段。
- 当前 `published_at` 在顶会场景不一定总能可靠取得；需要允许缺省值或回退到会议年份。
- 报告层应继续坚持 UTF-8 输出与结构化失败语义，沿用现有 CLI 边界规范。

## System-Wide Impact

- **Interaction graph**: `conference` CLI 将从“读取样例 JSON”切换为“解析子仓目录 -> 归一化 -> accepted 过滤 -> 随机抽样 -> 报告输出”。
- **Error propagation**: 子仓缺失、文件不存在、JSON 非法、记录字段缺失、accepted 判定失败都需要在 CLI 边界转成稳定失败输出，而不是 traceback。
- **State lifecycle risks**: 本功能主要读取静态文件，状态风险较低；但 submodule 未初始化会造成用户体验上的硬失败，需要明确错误提示和 next step。
- **API surface parity**: `conference filter` 与 `conference report` 都应共享同一解析和抽样逻辑，避免一边走真实源一边仍走样例。
- **Integration test scenarios**:
  - submodule 缺失时 `conference report` 返回结构化错误
  - 指定会议/年份文件缺失时返回结构化错误
  - accepted 过滤后少于 10 篇时返回全部
  - 固定 seed 下输出顺序稳定
  - 报告产物包含真实源元数据
  - CSV 产物列头稳定且可被表格工具直接打开

## SpecFlow Analysis

### Core flow

1. 用户初始化仓库并拉取 submodule。
2. 用户执行 `py -m paper_analysis.cli.main conference filter|report ...`。
3. CLI 根据会议和年份定位 `paperlists` JSON 文件。
4. 解析器将原始记录归一化并过滤出 accepted 论文。
5. 抽样器基于固定 seed 选出 10 篇。
6. `conference filter` 输出 stdout，`conference report` 额外写入 Markdown、JSON、CSV 报告产物。

### Edge cases

- submodule 未初始化
- 目标会议目录不存在
- 目标年份文件不存在
- 不同会议字段命名不一致
- accepted 状态字段为空或取值多样
- 记录缺摘要、机构、链接等非必填字段
- 候选数量小于 10

这些边界都应进入计划中的解析与测试范围。

## Acceptance Criteria

- [ ] `paperlists` 作为 git submodule 接入主仓，仓库文档说明初始化和更新方式。
- [ ] `conference` 流程可从子仓指定会议/年份 JSON 读取真实数据，而不再只依赖样例 fixtures。
- [ ] 新增解析层，能将 `paperlists` 原始记录归一化为本仓库内部论文模型。
- [ ] 仅保留被录用的论文；`oral`、`spotlight`、`poster` 等 accepted 子状态被正确纳入。
- [ ] 在未实现偏好筛选算法前，CLI 默认输出固定 seed 的随机 10 篇。
- [ ] `conference filter` 与 `conference report` 共用同一数据加载、accepted 过滤和抽样逻辑。
- [ ] Markdown / JSON / stdout / CSV 报告包含真实数据源的关键字段和元数据。
- [ ] CSV 报告字段扁平、列头稳定，适合人工在 Excel 或其他表格工具中继续分析。
- [ ] submodule 缺失、目标文件缺失、JSON 非法等失败路径均输出结构化错误。
- [ ] 补齐 `tests/unit/`、`tests/integration/`、`tests/e2e/` 覆盖真实源解析与随机抽样链路。
- [ ] 若命令面发生变化，同步更新 `.codex/skills/paper-analysis/SKILL.md`、`docs/agent-guide/command-surface.md`、CLI `--help`，并在新增来源后更新 `docs/engineering/extending-cli.md`。

## Success Metrics

- 用户可基于至少一个真实顶会年份文件成功执行 `conference report`
- `artifacts/e2e/conference/latest/` 中生成稳定的 `summary.md`、`result.json`、`result.csv`、`stdout.txt`
- 固定 seed 下 e2e 测试结果可重复
- 新增解析逻辑不破坏现有 `arxiv` 与 `quality local-ci` 链路

## Dependencies & Risks

### Dependencies

- `papercopilot/paperlists` 仓库可作为 submodule 稳定访问
- 本地与 CI 环境支持初始化 submodule
- 需要选定首批支持的会议/年份，用于 MVP 验证

### Risks

- `paperlists` 不同会议字段异构度可能高于预期
- 部分文件可能不含统一的 accepted 状态字段
- 随机抽样若未固定 seed，会导致测试和报告不稳定
- `Paper` 当前单机构模型可能丢失真实多机构信息

### Mitigation

- 先以 1 到 2 个会议目录完成 MVP 适配，再推广为通用解析器
- 在归一化层保留 `raw_payload`
- 将 accepted 判定与字段映射拆成独立可测模块
- 在 CLI 或 pipeline 层固定随机种子

## Implementation Sketch

### Phase 1: 数据源与归一化骨架

- `third_party/paperlists/`：接入 git submodule
- `paper_analysis/sources/conference/paperlists_loader.py`：定位目录与年份文件
- `paper_analysis/sources/conference/paperlists_parser.py`：原始记录读取与字段抽取
- `tests/fixtures/conference/paperlists_*.json`：补充最小异构样例

### Phase 2: accepted 过滤与随机抽样

- `paper_analysis/services/conference_pipeline.py`：增加 paperlists 模式
- `paper_analysis/services/conference_sampler.py`：固定 seed 的随机抽样逻辑
- `paper_analysis/domain/`：必要时补充中间领域模型

### Phase 3: 报告与回归测试

- `paper_analysis/services/report_writer.py`：扩展真实会议字段输出，并新增 CSV 导出
- `tests/unit/test_paperlists_parser.py`：字段映射、accepted 判定、抽样稳定性
- `tests/unit/test_report_writer.py`：CSV 列头、字段展平与 UTF-8 写出
- `tests/integration/test_pipelines.py`：真实源路径与失败路径
- `tests/e2e/test_golden_paths.py`：真实会议 Markdown / JSON / CSV 报告产物

## Sources & References

- Internal references:
  - `paper_analysis/cli/conference.py`
  - `paper_analysis/services/conference_pipeline.py`
  - `paper_analysis/services/report_writer.py`
  - `paper_analysis/shared/sample_loader.py`
  - `tests/integration/test_pipelines.py`
  - `tests/e2e/test_golden_paths.py`
  - `docs/engineering/extending-cli.md`
- External references:
  - `papercopilot/paperlists` repository: https://github.com/papercopilot/paperlists
  - `paperlists` README overview and conference/year JSON layout: https://github.com/papercopilot/paperlists
  - Example raw dataset links exposed in README, such as `iclr/iclr2025.json`, `nips/nips2024.json`, `cvpr/cvpr2024.json`
- Institutional learnings:
  - `docs/solutions/integration-issues/cli-structured-failure-and-windows-utf8-compatibility.md` 提醒新增 CLI 能力必须同时覆盖 happy path 与 failure path，并保持 UTF-8 与结构化错误输出
