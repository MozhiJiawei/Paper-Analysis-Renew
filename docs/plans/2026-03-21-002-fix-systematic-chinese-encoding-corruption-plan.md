---
title: fix: 系统性治理中文乱码与编码污染
type: fix
status: active
date: 2026-03-21
---

# fix: 系统性治理中文乱码与编码污染

## Overview

仓库当前存在明显的中文乱码与编码污染问题，且不是单点故障，而是同时出现在以下几层：

- 仓库文档与 skill 文本存在大量已损坏中文，表现为 UTF-8 内容被错误按其他编码解释后的“二次污染”文本。
- CLI 帮助文本、错误提示、测试描述、报告模板等用户可见文案已有大量乱码，说明源码中的字符串字面量本身已经受损。
- `artifacts/test-output/codex-arxiv-e2e/events.jsonl` 中的 agent message 与 command output 也出现乱码，说明问题不仅在查看工具，也在上游生成链路和存量文本素材。
- 仓库虽已广泛显式使用 `encoding="utf-8"`、`ensure_ascii=False`、`PYTHONUTF8=1` 与 `PYTHONIOENCODING=utf-8`，但这些措施只能保证“按 UTF-8 读写”，无法自动修复“内容本身已经坏掉”的中文文本。

本计划目标是把“编码设置正确”和“中文内容正确”分开治理，建立一次性修复与长期防回归的完整闭环。

## Problem Statement / Motivation

当前乱码问题已经影响：

- 开发体验：核心文档如 `.codex/skills/paper-analysis/SKILL.md`、`docs/agent-guide/quickstart.md`、`docs/engineering/testing-and-quality.md` 在 UTF-8 读取下仍显示乱码，直接破坏 agent 发现链路与人工阅读体验。
- CLI 可用性：如 [paper_analysis/cli/arxiv.py](D:/Git_Repo/Paper-Analysis-New/paper_analysis/cli/arxiv.py) 与 [paper_analysis/cli/quality.py](D:/Git_Repo/Paper-Analysis-New/paper_analysis/cli/quality.py) 中大量中文 help/summary 文本已损坏，导致 `--help`、失败提示、阶段摘要无法作为可信接口文案。
- 测试可信度：如 [tests/e2e/test_codex_agent_flow.py](D:/Git_Repo/Paper-Analysis-New/tests/e2e/test_codex_agent_flow.py) 与 [tests/integration/test_skill_contract.py](D:/Git_Repo/Paper-Analysis-New/tests/integration/test_skill_contract.py) 的中文描述、断言字符串部分失真，既降低可读性，也削弱“UTF-8 契约验证”本身的意义。
- 产物消费链路：`events.jsonl`、`summary.md`、`stdout.txt` 等报告需要同时被人、测试和 HTML 审核页消费。如果其中任一环节输出乱码，就会让 e2e 回归价值大幅下降。

## Research Summary

### Repository Research

- 仓库规范要求中文优先、UTF-8 优先、CLI 优先，见 [AGENTS.md](D:/Git_Repo/Paper-Analysis-New/AGENTS.md)。
- 仓库入口链要求优先阅读 `.codex/skills/paper-analysis/SKILL.md`、`docs/agent-guide/quickstart.md`、`docs/agent-guide/command-surface.md`、`docs/engineering/testing-and-quality.md`；但这些入口文件本身已有显著乱码。
- 编码与输出规范已在 [docs/engineering/encoding-and-output.md](D:/Git_Repo/Paper-Analysis-New/docs/engineering/encoding-and-output.md) 中声明“统一使用 UTF-8”，说明当前问题更像“内容污染”而非“规范缺失”。
- 报告落盘代码 [paper_analysis/services/report_writer.py](D:/Git_Repo/Paper-Analysis-New/paper_analysis/services/report_writer.py) 已使用 UTF-8 写入 `summary.md`、`result.json`、`result.csv`、`stdout.txt`，但源码内中文模板字符串已损坏。
- 质量链路 [paper_analysis/cli/quality.py](D:/Git_Repo/Paper-Analysis-New/paper_analysis/cli/quality.py) 已强制子进程环境使用 UTF-8，但阶段提示文案自身同样存在乱码。

### Institutional Learnings

- [docs/solutions/integration-issues/cli-structured-failure-and-windows-utf8-compatibility.md](D:/Git_Repo/Paper-Analysis-New/docs/solutions/integration-issues/cli-structured-failure-and-windows-utf8-compatibility.md) 已记录 Windows 下 UTF-8 兼容性和结构化失败输出问题，核心启示是“环境显式 UTF-8 只是底座，不等于文本内容一定正确”。
- 当前 `docs/solutions/` 下未发现专门针对“存量中文字符串已被错误转码后提交”的治理方案，因此本计划需要补上“内容修复策略”和“乱码检测回归”。
- `docs/solutions/patterns/critical-patterns.md` 不存在。该缺口本身不是阻塞项，但说明 institutional learnings 还未把“编码污染”提升到通用关键模式。

### External Research Decision

本议题主要是仓库内部文本资产治理与 Python/Windows 编码边界修复，仓库已有清晰本地规范和现成实现样例，因此不做外部研究，优先依赖本地证据推进。

## Proposed Solution

采用“五层治理”方案：

1. 建立乱码问题的分类与盘点基线。
2. 批量修复已损坏的中文源码、文档与测试文本。
3. 明确运行时输入输出边界，补齐剩余链路缺口。
4. 把中文乱码检测纳入本地 CI，防止新的乱码再次进入主干。
5. 更新文档与测试基线，使 UTF-8 约束成为仓库的可验证契约。

## Technical Considerations

- 优先把“查看工具显示异常”与“文件内容已损坏”区分开。当前多份文件在 `read_text(encoding="utf-8")` 下仍乱码，可判定至少一部分内容是存量损坏，而不是终端展示问题。
- 修复策略不能简单依赖“统一另存为 UTF-8”，因为坏内容若已写入文件，重新保存只会固化污染。
- 对部分文本可尝试程序化逆向修复，但仓库关键说明、help 文案、测试描述等用户可见文本更稳妥的方式是人工按语义重写，避免把错误字符串再传播一轮。
- 需要谨慎区分应修复范围：
  - 源码、文档、测试、skill、计划文档应彻底修复。
- 运行产物 `artifacts/` 属于测试生成物，可直接删除后通过测试或 CLI 重建，无需纳入人工修复范围。
  - 第三方子模块 `third_party/paperlists/` 不应做无关清洗，除非确认仓库业务会直接消费其中文文本且该问题会外溢。

## System-Wide Impact

- **Interaction graph**: agent 或用户先读取 [.codex/skills/paper-analysis/SKILL.md](D:/Git_Repo/Paper-Analysis-New/.codex/skills/paper-analysis/SKILL.md)，再读取 [docs/agent-guide/quickstart.md](D:/Git_Repo/Paper-Analysis-New/docs/agent-guide/quickstart.md) 与 [docs/agent-guide/command-surface.md](D:/Git_Repo/Paper-Analysis-New/docs/agent-guide/command-surface.md)，随后经 [paper_analysis/cli/arxiv.py](D:/Git_Repo/Paper-Analysis-New/paper_analysis/cli/arxiv.py) / [paper_analysis/cli/quality.py](D:/Git_Repo/Paper-Analysis-New/paper_analysis/cli/quality.py) 执行命令，最终由 [paper_analysis/services/report_writer.py](D:/Git_Repo/Paper-Analysis-New/paper_analysis/services/report_writer.py) 和 [paper_analysis/services/ci_html_writer.py](D:/Git_Repo/Paper-Analysis-New/paper_analysis/services/ci_html_writer.py) 产出文本与 HTML。任一层的中文字符串污染都会沿链路扩散。
- **Error propagation**: 若 CLI help、失败 summary、测试 `record_step()` 文案本身乱码，则上层 `events.jsonl`、`*-latest.txt`、`local-ci-latest.html` 都会携带污染结果；这类错误不会抛异常，而是以“成功写出错误文本”的形式静默传播。
- **State lifecycle risks**: `artifacts/` 属于可丢弃测试产物，执行修复前可直接清理；后续只保留“源码/文档修复后重跑测试重建产物”的流程，避免新旧产物混杂导致误判。
- **API surface parity**: `conference`、`arxiv`、`quality`、`report` 四个稳定入口都含中文帮助文案与输出文案，不能只修 `arxiv` 链路，否则会继续破坏统一命令面体验。
- **Integration test scenarios**: 需要覆盖 skill 文档读取、CLI `--help` 输出、结构化失败输出、联网 e2e `events.jsonl`、HTML 审核页消费真实产物等跨层场景。

## SpecFlow Analysis

从用户流和产物流看，至少要覆盖以下流：

1. 人工阅读流：开发者/agent 直接打开 skill 与 guide 文档，应看到正常中文。
2. CLI 帮助流：用户运行 `py -m paper_analysis.cli.main <namespace> --help`，应看到正常中文说明。
3. 失败提示流：用户输入错误参数或缺文件时，`[FAIL]` 输出中的中文必须可读。
4. 报告生成流：`conference report` / `arxiv report` 生成的 `summary.md`、`stdout.txt`、`result.json` 中中文字段必须可读。
5. Codex 黑盒流：`codex exec --json` 事件流里的 agent message、command output、最终路径回复必须可读。
6. HTML 消费流：`quality local-ci` 生成的 HTML 审核页应能正常展示各阶段中文描述与报告摘录。

SpecFlow 发现的主要缺口：

- 当前没有一条“仓库中文文案健康检查”自动化规则纳入 `quality local-ci`，导致存量乱码能通过现有质量门禁。
- 当前“UTF-8 读取成功”与“中文内容语义正确”未被区分，测试只覆盖了前者。
- 当前没有定义“哪些目录允许程序化修复，哪些目录只能人工重写”的治理边界。

## Acceptance Criteria

- [ ] `.codex/skills/paper-analysis/SKILL.md`、`docs/agent-guide/quickstart.md`、`docs/agent-guide/command-surface.md`、`docs/engineering/testing-and-quality.md`、`docs/engineering/encoding-and-output.md` 中的中文内容恢复为可读 UTF-8 文本。
- [ ] [paper_analysis/cli/arxiv.py](D:/Git_Repo/Paper-Analysis-New/paper_analysis/cli/arxiv.py)、[paper_analysis/cli/quality.py](D:/Git_Repo/Paper-Analysis-New/paper_analysis/cli/quality.py)、[paper_analysis/services/report_writer.py](D:/Git_Repo/Paper-Analysis-New/paper_analysis/services/report_writer.py) 等用户可见文案密集文件中的中文字符串恢复为可读文本。
- [ ] [tests/e2e/test_codex_agent_flow.py](D:/Git_Repo/Paper-Analysis-New/tests/e2e/test_codex_agent_flow.py)、[tests/e2e/test_golden_paths.py](D:/Git_Repo/Paper-Analysis-New/tests/e2e/test_golden_paths.py)、[tests/integration/test_skill_contract.py](D:/Git_Repo/Paper-Analysis-New/tests/integration/test_skill_contract.py) 中的中文描述与断言文本恢复可读，并继续表达原有测试意图。
- [ ] 把中文乱码检测接入 `quality local-ci`，建议作为 `lint` 的一部分执行，至少能发现常见 mojibake 片段或“UTF-8 文件中出现高概率错误转码模式”的文本污染。
- [ ] 删除旧 `artifacts/` 后，`py -m paper_analysis.cli.main quality local-ci` 可成功重建所需测试产物，且其中关键中文展示正常。
- [ ] 重新生成 `artifacts/test-output/codex-arxiv-e2e/events.jsonl` 后，关键 agent message 中不再出现大面积乱码。
- [ ] CLI `--help`、失败路径、e2e 报告路径、HTML 审核页四类对外文本接口均有回归验证。

## Success Metrics

- 关键入口文件与核心 CLI 文案中不再出现典型乱码模式，如 `鎴`、`鍙`、`閺`、`浠`、`璇` 等成片异常片段。 <!-- lint: allow-mojibake -->
- 开发者在 PowerShell 与 Python `read_text(encoding="utf-8")` 两种常见读取方式下，看到的文本一致且可读。
- 现有质量检查和新增编码检查可以在乱码重新引入时稳定失败。

## Dependencies & Risks

- 风险 1：部分坏文本可能难以可靠逆向还原。
  - 应对：对关键接口文案优先人工重写，以语义正确优先于“尽量保留原句”。
- 风险 2：批量替换可能误伤本来正常的非中文内容。
  - 应对：先盘点候选文件，再按目录分批修复，并通过测试与 `git diff` 人审确认。
- 风险 3：测试生成物会掩盖真实源码变更，增加审阅噪音。
  - 应对：修复前直接清理 `artifacts/`，把“源码修复”和“重跑测试验证”拆成两个明确阶段执行。
- 风险 4：第三方子模块可能包含自身历史脏数据。
  - 应对：默认不触碰 `third_party/`，除非确认其文本会直接进入本仓库用户界面。

## Implementation Suggestions

### Phase 1: 建立盘点与检测脚本

- 设计并新增一个轻量级乱码检测脚本，例如 `scripts/quality/check_text_encoding.py`，或将其并入现有 `scripts/quality/lint.py`。
- 扫描范围优先覆盖：
  - `.codex/skills/**/*.md`
  - `docs/**/*.md`
  - `paper_analysis/**/*.py`
  - `tests/**/*.py`
- 检测策略建议包含：
  - 文件必须能按 UTF-8 读取。
  - 命中高概率 mojibake 片段时失败并输出文件路径与行号。
  - 允许维护白名单或显式豁免标记，避免误报测试样例、文档中的举例片段或第三方数据。
- 将该检测明确接入 `quality local-ci`：
  - 如果并入 `lint`，则 `py -m paper_analysis.cli.main quality lint` 与 `quality local-ci` 自动覆盖。
  - 如果单独成阶段，则需要同步更新 CLI 帮助、质量阶段说明和 HTML 审核页展示。

### Phase 2: 修复关键入口与对外接口文案

- 先修入口链：
  - [.codex/skills/paper-analysis/SKILL.md](D:/Git_Repo/Paper-Analysis-New/.codex/skills/paper-analysis/SKILL.md)
  - [docs/agent-guide/quickstart.md](D:/Git_Repo/Paper-Analysis-New/docs/agent-guide/quickstart.md)
  - [docs/agent-guide/command-surface.md](D:/Git_Repo/Paper-Analysis-New/docs/agent-guide/command-surface.md)
  - [docs/engineering/testing-and-quality.md](D:/Git_Repo/Paper-Analysis-New/docs/engineering/testing-and-quality.md)
  - [docs/engineering/encoding-and-output.md](D:/Git_Repo/Paper-Analysis-New/docs/engineering/encoding-and-output.md)
- 再修核心 CLI / service 文案：
  - [paper_analysis/cli/arxiv.py](D:/Git_Repo/Paper-Analysis-New/paper_analysis/cli/arxiv.py)
  - [paper_analysis/cli/quality.py](D:/Git_Repo/Paper-Analysis-New/paper_analysis/cli/quality.py)
  - 其他出现用户可见中文的 CLI 文件
  - [paper_analysis/services/report_writer.py](D:/Git_Repo/Paper-Analysis-New/paper_analysis/services/report_writer.py)

### Phase 3: 修复测试资产并补回归

- 修复 e2e / integration / unit 中的中文描述，确保测试名、`record_step()`、断言消息可读。
- 为新增乱码检测补单测或集成测试。
- 增加至少一条覆盖“若仓库出现典型乱码片段，则 `quality lint` / `quality local-ci` 失败”的回归用例。
- 增加至少一条覆盖“正常中文文本不会被误报”的回归用例。

### Phase 4: 重新生成真实产物并核验

- 先直接删除 `artifacts/`，不对历史测试产物做任何人工修复。
- 运行 `py -m paper_analysis.cli.main quality local-ci`。
- 重点核验：
  - 本地 CI 输出中明确包含中文乱码检测结果。
  - `artifacts/quality/local-ci-latest.html`
  - `artifacts/test-output/codex-arxiv-e2e/events.jsonl`
  - `artifacts/e2e/arxiv/latest/summary.md`
  - `artifacts/e2e/arxiv/latest/stdout.txt`

### Phase 5: 文档化治理边界

- 在 [docs/engineering/encoding-and-output.md](D:/Git_Repo/Paper-Analysis-New/docs/engineering/encoding-and-output.md) 或新增工程文档中写清：
  - “UTF-8 编码”与“中文文本正确”是两个不同层次的约束。
  - 哪些目录属于必须中文可读的对外面。
  - `artifacts/` 属于可删除可重建的测试产物，不纳入存量乱码人工修复范围。
  - 出现乱码时的推荐排查顺序：文件原文、Python 读写、子进程环境、终端显示、产物消费链路。
- 在 [docs/engineering/testing-and-quality.md](D:/Git_Repo/Paper-Analysis-New/docs/engineering/testing-and-quality.md) 中补充：
  - `quality local-ci` 包含中文乱码检测。
  - 乱码检测的扫描范围、失败示例与允许豁免的边界。

## Sources & References

- Repository guidance: [AGENTS.md](D:/Git_Repo/Paper-Analysis-New/AGENTS.md)
- Skill entry: [.codex/skills/paper-analysis/SKILL.md](D:/Git_Repo/Paper-Analysis-New/.codex/skills/paper-analysis/SKILL.md)
- Quickstart: [docs/agent-guide/quickstart.md](D:/Git_Repo/Paper-Analysis-New/docs/agent-guide/quickstart.md)
- Command surface: [docs/agent-guide/command-surface.md](D:/Git_Repo/Paper-Analysis-New/docs/agent-guide/command-surface.md)
- Testing spec: [docs/engineering/testing-and-quality.md](D:/Git_Repo/Paper-Analysis-New/docs/engineering/testing-and-quality.md)
- Encoding contract: [docs/engineering/encoding-and-output.md](D:/Git_Repo/Paper-Analysis-New/docs/engineering/encoding-and-output.md)
- Existing learning: [docs/solutions/integration-issues/cli-structured-failure-and-windows-utf8-compatibility.md](D:/Git_Repo/Paper-Analysis-New/docs/solutions/integration-issues/cli-structured-failure-and-windows-utf8-compatibility.md)
- CLI surface example: [paper_analysis/cli/arxiv.py](D:/Git_Repo/Paper-Analysis-New/paper_analysis/cli/arxiv.py)
- Quality pipeline: [paper_analysis/cli/quality.py](D:/Git_Repo/Paper-Analysis-New/paper_analysis/cli/quality.py)
- Report writer: [paper_analysis/services/report_writer.py](D:/Git_Repo/Paper-Analysis-New/paper_analysis/services/report_writer.py)
- Skill contract test: [tests/integration/test_skill_contract.py](D:/Git_Repo/Paper-Analysis-New/tests/integration/test_skill_contract.py)
- Codex e2e test: [tests/e2e/test_codex_agent_flow.py](D:/Git_Repo/Paper-Analysis-New/tests/e2e/test_codex_agent_flow.py)
