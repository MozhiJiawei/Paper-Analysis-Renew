---
title: feat: Launch minimal arXiv subscription delivery loop
type: feat
status: completed
date: 2026-04-10
origin: docs/brainstorms/2026-04-10-arxiv-subscription-minimal-launch-requirements.md
---

# feat: Launch minimal arXiv subscription delivery loop

## Overview

本计划以 `docs/brainstorms/2026-04-10-arxiv-subscription-minimal-launch-requirements.md` 为唯一来源文档，目标是在不新增第三业务命名空间的前提下，把现有 arXiv 真实抓取、推荐结果写出、已经调好的邮件发送能力和本地 HTML 查看串成一个可被外部调度器每天触发的最小闭环 `(see origin: docs/brainstorms/2026-04-10-arxiv-subscription-minimal-launch-requirements.md)`。

本次交付继续坚持来源文档里的几个关键决策：

- 定时调度不内建在主仓代码里，主仓只负责单次被触发后的完整执行链路 `(see origin: docs/brainstorms/2026-04-10-arxiv-subscription-minimal-launch-requirements.md)`。
- 邮件是第一交付物，HTML 是镜像和后续交互扩展壳子 `(see origin: docs/brainstorms/2026-04-10-arxiv-subscription-minimal-launch-requirements.md)`。
- 用户只看推荐后的结果，不把原始订阅全集作为首版主要交付物 `(see origin: docs/brainstorms/2026-04-10-arxiv-subscription-minimal-launch-requirements.md)`。
- 当天无推荐结果也必须发送邮件，并且邮件与 HTML 保持同一份口径 `(see origin: docs/brainstorms/2026-04-10-arxiv-subscription-minimal-launch-requirements.md)`。

## Problem Statement / Motivation

仓库已经具备三段关键能力，但它们还没有组成真正可上线的单次运行链路：

- `arxiv report` 已能通过真实订阅 API 拉取论文，并把结果落到固定产物目录 [paper_analysis/cli/arxiv.py](D:/Git_Repo/Paper-Analysis-New/paper_analysis/cli/arxiv.py:88)。
- `write_report()` 已能稳定写出 `summary.md`、`result.json`、`result.csv`、`stdout.txt` 四类 UTF-8 产物 [paper_analysis/services/report_writer.py](D:/Git_Repo/Paper-Analysis-New/paper_analysis/services/report_writer.py:15)。
- 现有 HTML 写入链路已经证明“结构化 JSON -> Jinja2 -> 本地静态页面”这套模式可维护、可回归 [paper_analysis/services/ci_html_writer.py](D:/Git_Repo/Paper-Analysis-New/paper_analysis/services/ci_html_writer.py:82)。

当前缺口主要有四个：

1. 外部调度器缺少一个“单次运行即可完成抓取、推荐、报告、邮件、HTML 更新”的稳定入口。
2. 现有报告产物只有 `latest` 视图，没有面向订阅场景的历史归档与浏览索引。
3. 邮件发送能力虽然已单独调通，但还没有被接入订阅运行闭环，因此还没有真实用户可消费的每日交付物。
4. 无推荐结果、闭环接入失败、HTML 更新失败等非 happy path 还没有被定义成可诊断的产品行为。

## Proposed Solution

采用“复用现有 `arxiv report` 主链路，补一层最小交付编排”的方案，而不是新建独立产品面或第二套报告系统。

### 方案摘要

1. 继续以 `py -m paper_analysis.cli.main arxiv report --source-mode subscription-api ...` 作为真实抓取与推荐结果生成的基础入口，不新增顶层命名空间 `(see origin: docs/brainstorms/2026-04-10-arxiv-subscription-minimal-launch-requirements.md)`。
2. 在 `arxiv` 命名空间内为 `report` 增加最小“订阅投递模式”参数，让同一次命令在生成推荐报告后继续完成：
   - 归档本次运行产物
   - 调用已经调好的邮件发送能力发送完整邮件
   - 更新本地 HTML 最新页与历史列表
3. 引入单独的“交付编排 service”，把抓取/报告写出、邮件能力接入、HTML 镜像、历史索引更新解耦，避免把所有逻辑塞回 CLI。
4. 首版邮件和 HTML 共享同一份结构化运行快照，确保不出现“两套口径” `(see origin: docs/brainstorms/2026-04-10-arxiv-subscription-minimal-launch-requirements.md)`。

### 默认实现决策

以下问题在来源文档中被明确留给 planning，这里给出首版默认决策：

- 单次执行入口：
  外部调度器直接调用增强后的 `arxiv report`，而不是再造一个平行脚本。这样最贴近现有稳定命令面，也能继续复用现有 `artifacts/e2e/arxiv/latest/` 报告契约。
- 邮件发送方式：
  邮件发送能力已由独立计划 `2026-04-10-002-feat-email-delivery-capability-plan.md` 单独建设与调通；本计划只负责接入该能力，不再重复规划 SMTP 底层细节。
- 首版邮件统计字段：
  至少包含订阅日期、抓取总数、推荐命中数、邮件生成时间、前几篇推荐标题摘要；若无推荐，则显式展示“0 命中”与任务仍成功运行。
- HTML 复用策略：
  复用现有 Jinja2 静态渲染方式，但不复用 `CI 审核报告` 页面本身；新增面向订阅报告的专用模板与索引数据。
- 历史保留策略：
  首版按时间倒序保留最近 30 次运行索引；磁盘上的原始归档不主动清理，只限制 HTML 首页展示数量。
- 后续交互预留：
  在 HTML 渲染中为每条论文暴露稳定的 `run_id`、`paper_id`、`source` 和 `published_at` 数据槽位或 DOM 标识，后续点赞、纠错、确认、入库可以直接挂接，不必重做页面结构 `(see origin: docs/brainstorms/2026-04-10-arxiv-subscription-minimal-launch-requirements.md)`。

### Scope Boundaries

本计划明确不做以下内容：

- 点赞、纠错、确认和入库功能 `(see origin: docs/brainstorms/2026-04-10-arxiv-subscription-minimal-launch-requirements.md)`。
- 多用户订阅管理、账号体系和公网产品化部署 `(see origin: docs/brainstorms/2026-04-10-arxiv-subscription-minimal-launch-requirements.md)`。
- 趋势看板、复杂运营分析或交互式仪表盘 `(see origin: docs/brainstorms/2026-04-10-arxiv-subscription-minimal-launch-requirements.md)`。
- 新增独立 `recommend` 命名空间或新的业务域 `(see origin: docs/brainstorms/2026-04-10-arxiv-subscription-minimal-launch-requirements.md)`。

## Technical Considerations

- 架构影响
  - [paper_analysis/cli/arxiv.py](D:/Git_Repo/Paper-Analysis-New/paper_analysis/cli/arxiv.py:20) 继续作为稳定入口，但只负责参数编排与结构化失败输出。
  - 新增订阅交付编排 service，例如 `paper_analysis/services/arxiv_subscription_delivery.py`，负责单次运行上下文、归档、邮件能力接入与 HTML 更新。
  - [paper_analysis/services/report_writer.py](D:/Git_Repo/Paper-Analysis-New/paper_analysis/services/report_writer.py:15) 继续负责基础报告四件套，不直接承担邮件底层发送和 HTML 历史索引职责。
- 产物组织
  - 保留现有 `artifacts/e2e/arxiv/latest/`，避免破坏现有 e2e 与 `report --source arxiv` 的消费路径。
  - 新增订阅运行归档目录，例如 `artifacts/subscriptions/arxiv/runs/<run_id>/`，其中保存邮件快照、结构化索引输入和 HTML 页面。
  - 新增订阅站点目录，例如 `artifacts/subscriptions/arxiv/site/`，至少包含 `index.html`、`latest.html` 和历史索引数据文件。
- 邮件内容模型
  - 闭环层只负责向独立邮件能力传入统一结构化运行快照，不重复实现 SMTP、连接和认证逻辑。
  - “无推荐结果”也要渲染完整模板，只是论文列表为空，正文替换为明确说明。
- HTML 渲染模式
  - 参考现有 `ci_html_writer` 的做法，优先从结构化 JSON 渲染，而不是解析 Markdown 或终端文本 [paper_analysis/services/ci_html_writer.py](D:/Git_Repo/Paper-Analysis-New/paper_analysis/services/ci_html_writer.py:241)。
  - 页面首版至少包含最新报告视图、历史列表、运行统计摘要和可扩展的论文卡片容器。
- UTF-8 与失败语义
  - 所有新增文本产物、邮件模板输入、HTML 索引文件继续使用 UTF-8。
  - 邮件能力接入失败、HTML 更新失败等都需要延续现有 `CliInputError` / 结构化失败输出规则，不能向终端泄漏 traceback。相关约束遵循 `docs/solutions/integration-issues/cli-structured-failure-and-windows-utf8-compatibility.md`。

## System-Wide Impact

- **Interaction graph**: 外部调度器在北京时间 08:00 调用增强后的 `arxiv report` `(see origin: docs/brainstorms/2026-04-10-arxiv-subscription-minimal-launch-requirements.md)`；CLI 进入 [paper_analysis/cli/arxiv.py](D:/Git_Repo/Paper-Analysis-New/paper_analysis/cli/arxiv.py:88)；`ArxivPipeline` 拉取真实订阅结果并返回推荐后的 `Paper` 列表；[paper_analysis/services/report_writer.py](D:/Git_Repo/Paper-Analysis-New/paper_analysis/services/report_writer.py:15) 写出基础报告；新的 delivery service 基于该结果生成运行快照、调用已调好的邮件能力、更新 HTML 最新页和历史索引；`report --source arxiv` 与本地 HTML 都继续消费同源产物。
- **Error propagation**: 输入参数错误、订阅 API 错误、报告写出失败、邮件能力接入失败、HTML 写出失败都必须汇聚到 CLI 边界并输出结构化失败；邮件或 HTML 子步骤失败时要带上明确 `next:` 提示，而不是静默失败。
- **State lifecycle risks**: 单次运行是多步副作用链路。若报告已生成但邮件能力返回失败，系统不能让“latest 页面已更新但用户未收到邮件”变成不可诊断状态。建议使用“先生成运行快照 -> 再调用邮件能力 -> 发布 latest 页面 -> 更新历史索引”的顺序，并在运行元数据中记录每一步状态。
- **API surface parity**: `arxiv report` 的基础行为仍然是写报告；新增投递模式不能破坏现有只写 `summary.md/result.json/result.csv/stdout.txt` 的调用方式。`report --source arxiv`、现有 e2e、未来 HTML 页面必须继续围绕同一产物契约工作。
- **Integration test scenarios**:
  - 成功路径：真实 `subscription-api` 拉取后，完整生成运行快照、调用邮件能力并更新 HTML 页面。
  - 空结果路径：抓取成功但推荐命中为 0 时，邮件和 HTML 都出现“今日无推荐论文”。
  - 接入失败路径：邮件能力返回失败时，CLI 返回结构化失败，且不会误报运行成功。
  - 局部失败路径：HTML 索引更新失败时，运行元数据能明确记录失败步骤。
  - 回归路径：现有 [tests/e2e/test_golden_paths.py](D:/Git_Repo/Paper-Analysis-New/tests/e2e/test_golden_paths.py:71) 仍能证明 `arxiv report` 基础产物稳定可用。

## SpecFlow Analysis

### User Flow Overview

1. 外部调度器在每天北京时间 08:00 触发单次命令运行 `(see origin: docs/brainstorms/2026-04-10-arxiv-subscription-minimal-launch-requirements.md)`。
2. CLI 校验订阅日期、运行目标和运行目录等参数，并启动 delivery service。
3. delivery service 调用现有 arXiv 抓取与推荐链路，得到推荐后的论文列表。
4. 系统写出本次运行的结构化快照和基础报告四件套。
5. 系统根据同一份快照渲染邮件正文与 HTML 页面。
6. 系统调用已调好的邮件能力把邮件发送到 `lijiawei14@huawei.com`，本地站点更新“最新报告”与“历史列表”。
7. 终端输出本次运行结果、关键产物路径和失败时的诊断信息。

### Flow Permutations Matrix

| Flow | 结果集 | 邮件发送 | HTML 更新 | 预期行为 |
| --- | --- | --- | --- | --- |
| 正常推荐命中 | `count > 0` | 成功 | 成功 | 邮件含统计与推荐列表，HTML 展示同版内容 |
| 正常无命中 | `count = 0` | 成功 | 成功 | 邮件与 HTML 都明确写“今日无推荐论文”，并展示抓取统计 |
| 邮件能力接入失败 | 任意 | 失败 | 未开始 | CLI 结构化失败，提示检查邮件能力配置或返回结果 |
| 邮件发送失败 | 任意 | 失败 | 可选继续或停止 | 默认停止发布 latest，并把失败写进运行元数据 |
| HTML 发布失败 | 任意 | 成功 | 失败 | CLI 结构化失败，保留运行快照，提示检查站点目录 |

### Missing Elements & Gaps

- **运行入口语义**: 现有 `arxiv report` 只覆盖基础报告写出，没有“投递模式”。
  - 规划默认通过可选参数扩展 `report`，避免新增平行脚本。
- **latest 与历史的发布顺序**: 如果先改 latest 再发邮件，会出现页面领先于邮件的状态。
  - 规划默认采用“运行快照 -> 邮件 -> latest -> 历史索引”的顺序。
- **无推荐结果的产品表达**: 如果沿用现有空列表报告，用户可能误判失败。
  - 规划默认在邮件和 HTML 模板里单独渲染“任务成功但无推荐”的状态文案。
- **后续反馈扩展位**: 首版不做交互，但需要稳定挂点。
  - 规划默认在论文卡片和运行元数据里预留 `run_id/paper_id/source/published_at`。

### Critical Questions Requiring Clarification

1. **Important**: 邮件能力返回发送失败后，是否仍然允许更新 HTML latest？
   - Why it matters: 决定“latest 页面是否代表用户已收到最新报告”的产品语义。
   - Default assumption: 不允许。首版把邮件视为第一交付物，邮件失败时 latest 不推进，只保留本次运行快照待人工排查。
2. **Important**: 历史列表首版展示最近多少次运行最合适？
   - Why it matters: 直接影响页面可读性和实现复杂度。
   - Default assumption: 首页展示最近 30 次，归档目录完整保留。
3. **Nice-to-have**: 是否需要把原始抓取总数与推荐命中数同时写进 `result.json`？
   - Why it matters: 这会让邮件和 HTML 渲染更容易共享统计字段。
   - Default assumption: 需要，建议在运行快照中增加 `fetched_count`、`recommended_count`，而不是修改现有基础 `result.json` 太多。

### Recommended Next Steps

- 先设计单次运行快照 schema，再落邮件模板和 HTML 模板，避免两套模板各自长出统计字段。
- 先保住现有 `arxiv report` 基础契约，再逐步叠加“投递模式”，降低回归风险。
- 把“无推荐结果”和“邮件能力接入失败”作为首批集成测试覆盖对象，而不是等功能完成后再补。

## Acceptance Criteria

- [ ] `arxiv` 业务命名空间保持不变，首版最小上线不新增独立 `recommend` 或其他第三业务入口。
- [ ] 外部调度器可以通过单条 `py -m paper_analysis.cli.main arxiv report ...` 命令触发完整的“抓取 -> 推荐 -> 报告 -> 已调好的邮件能力 -> HTML”单次链路。
- [ ] 现有基础报告四件套 `summary.md`、`result.json`、`result.csv`、`stdout.txt` 继续稳定生成到 `artifacts/e2e/arxiv/latest/`，不破坏当前回归。
- [ ] 新增运行归档目录，单次运行至少保存结构化运行快照、邮件正文快照和 HTML 页面快照。
- [ ] 闭环始终调用已调好的邮件能力向 `lijiawei14@huawei.com` 发送邮件；有推荐时发送推荐列表，无推荐时发送“今日无推荐论文”说明 `(see origin: docs/brainstorms/2026-04-10-arxiv-subscription-minimal-launch-requirements.md)`。
- [ ] 每封邮件至少包含订阅日期、抓取总数、推荐命中数和结果摘要。
- [ ] 本地 HTML 站点首版同时支持“最新报告展示”和“历史报告列表” `(see origin: docs/brainstorms/2026-04-10-arxiv-subscription-minimal-launch-requirements.md)`。
- [ ] HTML 内容与邮件来自同一份运行快照，不出现字段口径漂移。
- [ ] HTML 页面为后续点赞、纠错、确认和入库预留稳定标识，但本次不实现这些交互 `(see origin: docs/brainstorms/2026-04-10-arxiv-subscription-minimal-launch-requirements.md)`。
- [ ] 邮件能力接入失败、发送失败、HTML 更新失败等异常场景都有结构化失败输出，无 traceback 泄漏。
- [ ] 至少补齐以下测试：
  - `tests/integration/` 覆盖投递模式成功、无推荐、配置失败路径
  - `tests/e2e/` 保留真实 arXiv 订阅黄金路径
  - HTML 渲染测试覆盖 latest 与 history 同时可读

## Success Metrics

- 外部调度器每天能稳定触发一次完整运行，且人工无需登录仓库即可从邮箱收到结果 `(see origin: docs/brainstorms/2026-04-10-arxiv-subscription-minimal-launch-requirements.md)`。
- 邮件和 HTML 对同一次运行展示相同的统计数字与论文列表。
- 无推荐结果日不会再被误判为“任务失败”。
- 本地最新页和历史页都可直接用于人工回看，而不需要再打开原始 JSON 或 stdout。
- 交付后若要加入反馈能力，只需在现有 HTML 结构上增量扩展，而不是重做页面入口 `(see origin: docs/brainstorms/2026-04-10-arxiv-subscription-minimal-launch-requirements.md)`。

## Dependencies & Risks

- **邮件能力前置依赖**: 发信通道与 SMTP 调试已经由独立计划 `2026-04-10-002-feat-email-delivery-capability-plan.md` 单独处理；若该能力未完成，当前闭环计划无法验收。
- **外部调度器依赖**: 主仓不负责实现 08:00 定时调度 `(see origin: docs/brainstorms/2026-04-10-arxiv-subscription-minimal-launch-requirements.md)`，因此至少需要明确调度器传入日期与配置的方式。
- **真实 arXiv 网络依赖**: 现有 e2e 已要求真实联网访问 arXiv，新的投递链路会进一步放大对外网稳定性的依赖。
- **状态一致性风险**: 邮件、HTML latest、历史索引属于多步副作用；若没有运行快照与步骤状态记录，后续很难定位“哪一步失败了”。
- **命令面膨胀风险**: 如果把太多投递细节暴露成 CLI 参数，`arxiv report --help` 会迅速变复杂；首版应优先使用最小必要参数 + 配置文件/环境变量。

## Implementation Suggestions

### Phase 1: Delivery Model

- 新增 `paper_analysis/services/arxiv_subscription_delivery.py`
  - 定义 `run_id`
  - 组织基础报告产物与运行快照
  - 维护步骤状态记录
- 新增 `paper_analysis/domain/delivery_run.py` 或同类轻量数据模型
  - 描述 `subscription_date`
  - `fetched_count`
  - `recommended_count`
  - `papers`
  - `email_status`
  - `site_status`

### Phase 2: Email Integration & HTML

- 新增 `paper_analysis/services/arxiv_subscription_site_writer.py`
  - 渲染 `latest.html`
  - 渲染 `index.html`
  - 写历史索引 JSON
- 新增 `paper_analysis/templates/arxiv_subscription_report.html.j2`
- 接入独立邮件能力提供的发送器与模板

### Phase 3: CLI & Tests

- 更新 [paper_analysis/cli/arxiv.py](D:/Git_Repo/Paper-Analysis-New/paper_analysis/cli/arxiv.py:40)
  - 增加投递模式相关可选参数
  - 维持基础 `report` 行为向后兼容
- 更新 [tests/e2e/test_golden_paths.py](D:/Git_Repo/Paper-Analysis-New/tests/e2e/test_golden_paths.py:71)
  - 保留现有真实联网基础产物回归
  - 增加最小投递链路断言或新增独立 e2e 用例
- 新增 `tests/integration/test_arxiv_subscription_delivery.py`
  - 覆盖成功、0 命中、邮件能力接入失败、HTML 更新失败
- 更新文档与 skill：
  - `.codex/skills/paper-analysis/SKILL.md`
  - `docs/agent-guide/command-surface.md`
  - CLI `--help`
  - 如涉及来源/规则扩展，同步更新 `docs/engineering/extending-cli.md`

## Sources & References

- **Origin document:** `docs/brainstorms/2026-04-10-arxiv-subscription-minimal-launch-requirements.md`
  - 继承的关键决策：外部调度、邮件优先、推荐结果优先、无推荐也发、HTML 采用“最新 + 历史”
- **Internal references**
  - [paper_analysis/cli/arxiv.py](D:/Git_Repo/Paper-Analysis-New/paper_analysis/cli/arxiv.py:88)
  - [paper_analysis/services/report_writer.py](D:/Git_Repo/Paper-Analysis-New/paper_analysis/services/report_writer.py:15)
  - [paper_analysis/services/ci_html_writer.py](D:/Git_Repo/Paper-Analysis-New/paper_analysis/services/ci_html_writer.py:82)
  - [tests/e2e/test_golden_paths.py](D:/Git_Repo/Paper-Analysis-New/tests/e2e/test_golden_paths.py:71)
- **Institutional learnings**
  - `docs/solutions/integration-issues/ci-html-review-report-scalability-and-case-awareness.md`
  - `docs/solutions/integration-issues/cli-structured-failure-and-windows-utf8-compatibility.md`
  - `docs/solutions/integration-issues/skill-usage-contract-without-development-guidance.md`
- **Related work**
  - `docs/plans/2026-03-20-002-feat-add-arxiv-subscription-ingestion-plan.md`
  - `docs/plans/2026-04-10-002-feat-email-delivery-capability-plan.md`
