---
title: refactor: 增强本地 CI 的 lint 能力
type: refactor
status: completed
date: 2026-04-02
origin: docs/brainstorms/2026-03-31-testing-quality-refactor-requirements.md
---

# refactor: 增强本地 CI 的 lint 能力

## Overview

本计划聚焦把仓库当前的静态质量门禁重构为“一个更可信、职责更清晰、维护成本更低”的 `quality lint` 总入口，同时保持 `py -m paper_analysis.cli.main quality local-ci` 这一稳定使用方式不变。方案直接承接来源文档已经确认的结论：仓库特有规则继续保留，自定义 `lint.py` 收缩为仓库规范检查；Python 通用静态质量交给 `ruff`；真实类型检查交给 `mypy`；静态质量统一收敛到 `lint` 阶段；旧的 `typecheck.py` 在迁移完成后直接删除；代码质量治理指标第一阶段只报警不阻断 `(see origin: docs/brainstorms/2026-03-31-testing-quality-refactor-requirements.md)`。

这不是一次“再加几个规则”的小修，而是一次静态质量职责拆分与命令面收敛：既要让开发者能更快理解失败来源，也要确保 HTML 审核页、逐用例 JSON、CLI `--help`、文档和 repo-local skill 一起跟上新的结构。

## Problem Statement / Motivation

当前仓库已经有清晰的本地质量链路：

- `quality local-ci` 按 `lint -> typecheck -> unit -> integration -> e2e` 串行执行 [paper_analysis/cli/quality.py](D:/Git_Repo/Paper-Analysis-New/paper_analysis/cli/quality.py)
- HTML 审核页会消费各阶段结果与逐用例 JSON [paper_analysis/services/ci_html_writer.py](D:/Git_Repo/Paper-Analysis-New/paper_analysis/services/ci_html_writer.py)
- 质量阶段的分类、标题与产物契约已经被测试覆盖 [paper_analysis/services/quality_case_support.py](D:/Git_Repo/Paper-Analysis-New/paper_analysis/services/quality_case_support.py) [tests/integration/test_quality_html.py](D:/Git_Repo/Paper-Analysis-New/tests/integration/test_quality_html.py)

但现状存在三类核心问题：

1. 当前 `scripts/quality/lint.py` 同时承担 UTF-8 / 文本卫生与 Python 文件基础格式检查，职责边界已经开始混杂 [scripts/quality/lint.py](D:/Git_Repo/Paper-Analysis-New/scripts/quality/lint.py)。
2. 当前 `scripts/quality/typecheck.py` 只能检查“公开函数是否写了注解”，并不能发现真实类型错误，容易制造形式合规的假安全感 [scripts/quality/typecheck.py](D:/Git_Repo/Paper-Analysis-New/scripts/quality/typecheck.py)。
3. 质量链路、HTML writer、逐用例分类和命令帮助文本都把 `typecheck` 当成长期独立阶段，这与来源文档已经确认的新方向冲突 `(see origin: docs/brainstorms/2026-03-31-testing-quality-refactor-requirements.md)`。

如果不做这次重构，仓库会持续停留在“自定义规则维护越来越重，但保护面仍偏弱”的状态；如果粗暴替换，又容易破坏当前稳定的失败语义、HTML 审核页与测试契约。

## Proposed Solution

采用“静态质量统一收敛到 `quality lint`、仓库特有规则与通用工具解耦、代码治理报告独立成不阻断附加输出”的方案。

### 1. 把静态质量统一收敛到 `quality lint`

新的阶段顺序调整为：

1. `lint`
2. `unit`
3. `integration`
4. `e2e`

其中 `lint` 内部固定拆成四段：

1. 编码类检查
2. `ruff`
3. `mypy`
4. 代码质量检查（报告型，不阻断）

这延续来源文档已确认的设计：真实类型检查不再占用独立 `typecheck` 阶段，而是并入统一 `lint` 阶段 `(see origin: docs/brainstorms/2026-03-31-testing-quality-refactor-requirements.md)`。

### 2. 收缩自定义 lint 脚本，只保留仓库特有规则

自定义脚本继续保留，但职责收缩为：

- 全仓 UTF-8 可读检查
- 常见乱码片段检测
- 非 Python 文本文件的尾随空格、Tab、文件末尾换行

Python 文件上的通用格式和静态问题从这里移除，避免和 `ruff` 双重报错。这一点直接承接来源文档关于 “仓库独有约束留在自定义脚本，Python 通用问题交给成熟工具” 的结论 `(see origin: docs/brainstorms/2026-03-31-testing-quality-refactor-requirements.md)`。

### 3. 引入 `ruff` 承担 Python 通用静态质量

第一版 `ruff` 负责：

- 未使用导入
- 未使用变量
- 重复定义
- 明显可疑写法
- import 风格统一
- 基础复杂度规则

第一阶段应选择低争议、强信号的规则集合，避免一上来把仓库变成“为过格式规则大面积重写代码”的状态。

### 4. 引入 `mypy` 承担真实类型检查

`mypy` 第一阶段采用渐进覆盖：

- 优先覆盖 `paper_analysis/domain/`
- 优先覆盖 `paper_analysis/api/` 中的协议与结构化对象
- 优先覆盖 `paper_analysis/sources/arxiv/`
- 优先覆盖 `paper_analysis/services/report_writer.py`
- 可以补充其他结构化输入输出清晰、动态性较低的核心模块

默认不把以下目录纳入第一阶段强覆盖：

- `tests/`
- 复杂 CLI / subprocess 编排层
- 边界仍大量依赖 `dict[str, Any]` 的动态模块

迁移完成后直接删除 `scripts/quality/typecheck.py`，不保留长期兼容层。这是来源文档里已经确认并由本轮补充决策明确接受的迁移终点 `(see origin: docs/brainstorms/2026-03-31-testing-quality-refactor-requirements.md)`。

### 5. 增加代码质量治理报告，但第一阶段只报警不阻断

在 `quality lint` 内增加报告型子检查，默认只产出榜单与告警，不影响退出码。第一版建议覆盖：

- 圈复杂度
- 重复代码
- 长函数
- 大文件
- 模块依赖异味

工具方向沿用来源文档中已确定的建议：

- `radon` 负责复杂度
- `jscpd` 负责重复代码
- 长函数 / 大文件优先采用轻量统计或复用现有分析输出
- 模块依赖异味允许先用最小自定义脚本

报告只输出前 N 个最值得处理的问题点，避免把 HTML 和 artifact 变成一大堆难以消费的噪音。

### 6. 明确失败语义与展示契约

`quality lint` 需要把四类结果显式区分给开发者：

1. 仓库规范失败
2. Python lint 失败
3. 真实类型错误
4. 治理提示（仅告警）

这意味着需要同时调整：

- 阶段标准输出摘要
- `artifacts/quality/lint-latest.txt`
- `artifacts/quality/lint-cases-latest.json`
- HTML 审核页中“质量检查”大类的逐项展示

目标不是“隐藏复杂度”，而是让人一眼看懂哪一类问题导致失败、哪一类只是报告型提示。

## Technical Considerations

- 当前 `paper_analysis/cli/quality.py` 把 `QUALITY_STAGES` 固定为 `lint -> typecheck -> unit -> integration -> e2e`，并将非 unittest 阶段写成单 case artifact；这里需要改为只保留 `lint` 一个静态质量阶段，同时让 `lint` 自身能表达多个子检查的结构化结果 [paper_analysis/cli/quality.py](D:/Git_Repo/Paper-Analysis-New/paper_analysis/cli/quality.py)。
- 当前 `quality_case_support.py` 把 `typecheck` 归类到 `quality_checks`，并默认把 `lint` / `typecheck` 映射到独立脚本路径；这里需要改成支持 `lint.repo_rules`、`lint.ruff`、`lint.mypy`、`lint.quality_report` 一类的子 case 设计，或等价的可扩展结构 [paper_analysis/services/quality_case_support.py](D:/Git_Repo/Paper-Analysis-New/paper_analysis/services/quality_case_support.py)。
- 当前 `ci_html_writer.py` 的阶段说明仍写着“`typecheck` 检查公开函数的类型注解边界”；这里需要同步修改阶段描述，并为 `lint` 的子结果提供更细的展示文案 [paper_analysis/services/ci_html_writer.py](D:/Git_Repo/Paper-Analysis-New/paper_analysis/services/ci_html_writer.py)。
- 当前依赖声明只在 [pyproject.toml](D:/Git_Repo/Paper-Analysis-New/pyproject.toml) 中维护，因此 `ruff`、`mypy`、`radon`、`jscpd` 的接入路径需要在这里统一落地；同时要评估 `jscpd` 的运行方式是否通过 Python 依赖、Node 工具、或受控的外部命令封装接入。
- 仓库约定要求命令面变化必须同步更新 `.codex/skills/paper-analysis/SKILL.md`、`docs/agent-guide/command-surface.md`、CLI `--help`，且新增测试层级或规则层级时需要更新 `docs/engineering/extending-cli.md` 与 `docs/engineering/testing-and-quality.md` `(see origin: AGENTS.md)`。
- 需要继续保留 UTF-8 子进程环境注入与结构化失败输出的稳定性，避免新引入工具后破坏 Windows 兼容和 artifact 可读性 [docs/solutions/integration-issues/cli-structured-failure-and-windows-utf8-compatibility.md](D:/Git_Repo/Paper-Analysis-New/docs/solutions/integration-issues/cli-structured-failure-and-windows-utf8-compatibility.md)。
- HTML 审核页必须继续以结构化结果为状态真值，不能退回到解析日志关键词；这是当前质量报告链路的关键稳定模式 [docs/solutions/integration-issues/ci-html-review-report-scalability-and-case-awareness.md](D:/Git_Repo/Paper-Analysis-New/docs/solutions/integration-issues/ci-html-review-report-scalability-and-case-awareness.md)。

## System-Wide Impact

- **Interaction graph**:
  `quality local-ci -> quality lint -> repo rules / ruff / mypy / quality report -> artifacts/quality/* -> ci_html_writer -> local-ci-latest.html`
- **Error propagation**:
  `repo rules`、`ruff`、`mypy` 任一失败都应让 `quality lint` 失败；代码质量报告只能记为告警，不影响退出码。
- **State lifecycle risks**:
  如果只改 CLI 阶段名，不改逐用例 artifact 与 HTML writer，会出现阶段通过但页面显示错误、分类缺失、或脚本链接失真的问题。
- **API surface parity**:
  `quality lint`、`quality local-ci`、CLI `--help`、repo-local skill、文档和 HTML 审核页都属于对外可见接口，需要同轮迁移。
- **Integration test scenarios**:
  需要覆盖成功路径、失败路径、告警不阻断路径、以及旧 `typecheck` 移除后的命令面回归。

## Implementation Phases

### Phase 1: 固定新的静态质量命令面与工具入口

- 在 [pyproject.toml](D:/Git_Repo/Paper-Analysis-New/pyproject.toml) 中声明 `ruff`、`mypy`，并确定 `radon` / `jscpd` 的接入方式
- 重写 [paper_analysis/cli/quality.py](D:/Git_Repo/Paper-Analysis-New/paper_analysis/cli/quality.py) 的静态阶段定义，删除独立 `typecheck` 阶段
- 让 `quality local-ci` 顺序改为 `lint -> unit -> integration -> e2e`
- 移除 `quality typecheck` 子命令注册与帮助文本
- 明确 `quality lint` 的输出汇总格式与退出码规则

交付物：

- 更新后的 `quality` CLI 命令面
- 可执行的 `quality lint` 四段式总入口
- 删除 `quality typecheck` 后的 `--help` 输出

### Phase 2: 收缩自定义 lint，并引入 `ruff` / `mypy`

- 调整 [scripts/quality/lint.py](D:/Git_Repo/Paper-Analysis-New/scripts/quality/lint.py)，仅保留仓库特有规则
- 为 Python 文件通用静态问题引入 `ruff`
- 为核心模块引入第一阶段 `mypy` 配置
- 梳理哪些模块先纳入 `mypy` 覆盖，哪些模块暂时排除
- 删除 [scripts/quality/typecheck.py](D:/Git_Repo/Paper-Analysis-New/scripts/quality/typecheck.py)

交付物：

- 收缩后的仓库特有 lint 脚本
- 第一版 `ruff` 配置
- 第一版 `mypy` 配置和覆盖清单
- 已删除的旧 AST `typecheck.py`

### Phase 3: 增加报告型代码质量子检查

- 为 `quality lint` 增加复杂度、重复代码、长函数、大文件、模块依赖异味的报告型输出
- 统一定义报告 artifact 的命名与摘要格式
- 限制输出为前 N 个高信号问题，避免噪音失控
- 确保该子检查只在 stdout / artifact / HTML 中报警，不影响命令退出码

交付物：

- 新的报告型质量检查 runner
- 附加 artifact 与摘要榜单
- 不阻断的退出码语义

### Phase 4: 迁移质量展示与回归测试

- 更新 [paper_analysis/services/quality_case_support.py](D:/Git_Repo/Paper-Analysis-New/paper_analysis/services/quality_case_support.py) 的阶段映射、标题与脚本路径规则
- 更新 [paper_analysis/services/ci_html_writer.py](D:/Git_Repo/Paper-Analysis-New/paper_analysis/services/ci_html_writer.py) 的阶段说明与质量大类展示逻辑
- 更新 [tests/unit/test_lint.py](D:/Git_Repo/Paper-Analysis-New/tests/unit/test_lint.py) 与新增 `ruff` / `mypy` / 报告型子检查覆盖
- 更新 [tests/integration/test_quality_html.py](D:/Git_Repo/Paper-Analysis-New/tests/integration/test_quality_html.py)，确保 HTML 能正确区分失败与告警
- 如有必要，补充 CLI 集成测试，验证 `quality typecheck` 已移除、`quality lint` 摘要符合新语义

交付物：

- 与新质量结构一致的逐用例 JSON
- 可读的 HTML 审核页
- 覆盖成功 / 失败 / 告警路径的测试集

### Phase 5: 同步文档与 repo-local skill

- 更新 [.codex/skills/paper-analysis/SKILL.md](D:/Git_Repo/Paper-Analysis-New/.codex/skills/paper-analysis/SKILL.md)
- 更新 [docs/agent-guide/command-surface.md](D:/Git_Repo/Paper-Analysis-New/docs/agent-guide/command-surface.md)
- 更新 [docs/engineering/testing-and-quality.md](D:/Git_Repo/Paper-Analysis-New/docs/engineering/testing-and-quality.md)
- 更新 [docs/engineering/extending-cli.md](D:/Git_Repo/Paper-Analysis-New/docs/engineering/extending-cli.md)
- 视需要更新 README 中的质量命令示例

交付物：

- 与实际命令面一致的技能文档与工程文档
- 新静态质量职责边界的文字说明

## SpecFlow Analysis

### User Flow Overview

1. 开发者运行 `py -m paper_analysis.cli.main quality lint`。
2. 系统先执行仓库特有规则检查，尽早发现 UTF-8、乱码和文本卫生问题。
3. 若仓库规则通过，系统继续执行 `ruff`，发现 Python 通用静态错误。
4. 若 `ruff` 通过，系统继续执行 `mypy`，发现真实类型问题。
5. 不论前三步是否全部通过，系统都尽量生成对应 artifact；若前三步都通过，再执行代码质量报告并给出治理榜单。
6. 开发者运行 `quality local-ci` 时，`lint` 的结构化结果被 HTML 审核页消费，后续 `unit / integration / e2e` 继续按现有机制执行。
7. 开发者在 HTML 中能区分“硬失败”和“仅告警”的质量结果，并据此决定先修阻断问题还是排期治理热点。

### Flow Permutations Matrix

| 场景 | 仓库规则 | `ruff` | `mypy` | 治理报告 | 预期结果 |
| --- | --- | --- | --- | --- | --- |
| 文档编码损坏 | 失败 | 未执行 | 未执行 | 可跳过 | `quality lint` 失败，摘要指向仓库规范 |
| Python 静态错误 | 通过 | 失败 | 未执行 | 可跳过 | `quality lint` 失败，摘要指向 `ruff` |
| 真实类型错误 | 通过 | 通过 | 失败 | 可跳过 | `quality lint` 失败，摘要指向 `mypy` |
| 只有复杂度/重复度问题 | 通过 | 通过 | 通过 | 告警 | `quality lint` 通过，但有治理提示 |
| 全部通过 | 通过 | 通过 | 通过 | 无或轻微告警 | `quality lint` 通过，HTML 显示质量检查通过 |

### Missing Elements & Gaps

- **Category**: Tool Bootstrap
  - **Gap Description**: `jscpd` 的落地方式尚未定死，是通过受控命令调用还是额外运行时封装。
  - **Impact**: 会影响依赖安装路径、开发体验与 CI 可重复性。
  - **Current Ambiguity**: 来源文档已给出工具方向，但未定最终接入形式。

- **Category**: Mypy Scope
  - **Gap Description**: 第一阶段具体纳入哪些模块仍需要按当前代码结构细化。
  - **Impact**: 直接影响初始噪音、迁移成本与收益。
  - **Current Ambiguity**: 需求文档给了优先目录，但尚未形成最终 include / exclude 清单。

- **Category**: HTML Contract
  - **Gap Description**: 质量大类中是否以四个子 case 展示，还是保留一个阶段级 case + 详细日志，需要实现时定型。
  - **Impact**: 影响页面可读性与回归测试复杂度。
  - **Current Ambiguity**: 目标已清晰，但具体 view-model 形态仍可优化。

- **Category**: Report Artifacts
  - **Gap Description**: 报告型质量检查需要新增哪些 artifact 文件，以及是否单独存 `quality-report-latest.*`。
  - **Impact**: 会影响 HTML 附件链接与后续可扩展性。
  - **Current Ambiguity**: 需求文档只要求“有报告、有榜单、不阻断”，未固定文件名。

### Critical Questions Requiring Clarification

当前不再有阻断规划的关键问题；本计划按以下默认假设继续：

1. **Critical**: `ruff` 与 `mypy` 作为正式依赖进入主仓，并成为稳定 `quality` 命令面的一部分。
2. **Critical**: `scripts/quality/typecheck.py` 在迁移完成后直接删除，不保留长期兼容层。
3. **Important**: 代码质量报告默认继续生成结构化 artifact，并在 HTML 中体现“告警但不阻断”。
4. **Important**: `mypy` 采用渐进覆盖，不以第一次接入就覆盖所有测试和动态模块为目标。

### Recommended Next Steps

- 先固定 `quality lint` 的四段式执行器和退出码规则，再落工具配置。
- 优先完成 `quality.py`、`quality_case_support.py`、`ci_html_writer.py` 的契约迁移，避免工具先接进来但展示层失真。
- 以高结构化核心模块为起点引入 `mypy`，把初期噪音控制在可消化范围。
- 让报告型质量检查先交付“高信号榜单”，而不是一上来追求完整架构治理。

## Acceptance Criteria

- [ ] `py -m paper_analysis.cli.main quality local-ci` 仍是统一本地 CI 入口，顺序变为 `lint -> unit -> integration -> e2e`。
- [ ] `quality typecheck` 从稳定命令面删除，CLI `--help` 中不再出现该阶段。
- [ ] `quality lint` 成为唯一静态质量入口，并固定执行：仓库规则、`ruff`、`mypy`、代码质量报告。
- [ ] 自定义 [scripts/quality/lint.py](D:/Git_Repo/Paper-Analysis-New/scripts/quality/lint.py) 只保留 UTF-8、乱码片段、非 Python 文本卫生等仓库特有规则。
- [ ] Python 文件上的通用静态问题由 `ruff` 接管，不再在自定义脚本里重复维护。
- [ ] 第一阶段 `mypy` 能在至少一组核心结构化模块上发现真实类型错误。
- [ ] [scripts/quality/typecheck.py](D:/Git_Repo/Paper-Analysis-New/scripts/quality/typecheck.py) 被删除，且没有长期兼容层残留。
- [ ] 代码质量检查能输出复杂度、重复代码、长函数、大文件、模块依赖异味中的至少一组高信号榜单，并默认只报警不阻断。
- [ ] `quality lint` 的退出码只受仓库规则、`ruff`、`mypy` 影响，不受报告型检查影响。
- [ ] `artifacts/quality/lint-latest.txt` 与逐用例 JSON 能清晰区分仓库规范失败、`ruff` 失败、`mypy` 失败、治理告警。
- [ ] HTML 审核页仍可生成，并在“质量检查”大类中正确展示新的静态质量结构。
- [ ] `.codex/skills/paper-analysis/SKILL.md`、`docs/agent-guide/command-surface.md`、`docs/engineering/testing-and-quality.md`、`docs/engineering/extending-cli.md` 与实际命令面保持一致。

## Success Metrics

- 团队可以明确区分“仓库规范失败”“Python lint 失败”“真实类型错误”“治理告警”四类结果。
- `quality lint` 能发现当前 AST 注解存在性检查无法发现的真实类型问题。
- 自定义质量脚本不再沿着“自研 mini-linter”方向持续膨胀。
- 新接入的静态工具不会让 HTML 审核页、失败 artifact 或 UTF-8 输出稳定性回退。
- 初始噪音可控，开发者无需为“形式合规”大量补样板注解或机械拆函数。

## Dependencies & Risks

### Dependencies

- 依赖 [pyproject.toml](D:/Git_Repo/Paper-Analysis-New/pyproject.toml) 作为工具依赖的统一落点。
- 依赖现有质量 HTML 契约继续工作 [paper_analysis/services/ci_html_writer.py](D:/Git_Repo/Paper-Analysis-New/paper_analysis/services/ci_html_writer.py)。
- 依赖现有逐用例 JSON 契约可被扩展而不是推倒重来 [paper_analysis/services/quality_case_support.py](D:/Git_Repo/Paper-Analysis-New/paper_analysis/services/quality_case_support.py)。
- 依赖仓库文档和 skill 与命令面同步更新 `(see origin: AGENTS.md)`。

### Risks

- **风险**: `mypy` 首轮覆盖过宽，噪音过高，导致接入阻力很大。
  - **缓解**: 仅覆盖高结构化核心模块，显式排除动态层与测试层。

- **风险**: `ruff` 与自定义 lint 保留重复规则，导致双重报错和定位成本上升。
  - **缓解**: 先做规则归属清单，再精简自定义脚本。

- **风险**: 代码质量报告输出过量明细，HTML 与 artifact 难以消费。
  - **缓解**: 只输出前 N 个高信号热点，保留榜单式摘要。

- **风险**: CLI 阶段改名后，HTML writer 或测试仍按旧 `typecheck` 阶段断言，造成回归。
  - **缓解**: 把命令面、writer、逐用例 JSON、帮助文本和测试作为同一迁移批次。

- **风险**: 新工具子进程输出编码不稳定，污染质量产物。
  - **缓解**: 沿用并验证现有 UTF-8 子进程环境注入模式。

## Sources & References

### Origin

- **Origin document:** [docs/brainstorms/2026-03-31-testing-quality-refactor-requirements.md](D:/Git_Repo/Paper-Analysis-New/docs/brainstorms/2026-03-31-testing-quality-refactor-requirements.md)
  - Key decisions carried forward:
    - 静态质量统一收敛到 `quality lint`
    - `ruff` 承担 Python 通用静态质量，`mypy` 承担真实类型检查
    - `scripts/quality/typecheck.py` 迁移完成后直接删除
    - 代码质量检查第一阶段只报警不阻断

### Internal References

- 当前质量命令入口: [paper_analysis/cli/quality.py](D:/Git_Repo/Paper-Analysis-New/paper_analysis/cli/quality.py)
- 当前逐用例契约: [paper_analysis/services/quality_case_support.py](D:/Git_Repo/Paper-Analysis-New/paper_analysis/services/quality_case_support.py)
- 当前 HTML writer: [paper_analysis/services/ci_html_writer.py](D:/Git_Repo/Paper-Analysis-New/paper_analysis/services/ci_html_writer.py)
- 当前仓库特有 lint: [scripts/quality/lint.py](D:/Git_Repo/Paper-Analysis-New/scripts/quality/lint.py)
- 即将删除的旧 typecheck: [scripts/quality/typecheck.py](D:/Git_Repo/Paper-Analysis-New/scripts/quality/typecheck.py)
- 现有 lint 单测: [tests/unit/test_lint.py](D:/Git_Repo/Paper-Analysis-New/tests/unit/test_lint.py)
- 现有质量 HTML 集成测试: [tests/integration/test_quality_html.py](D:/Git_Repo/Paper-Analysis-New/tests/integration/test_quality_html.py)
- 依赖配置入口: [pyproject.toml](D:/Git_Repo/Paper-Analysis-New/pyproject.toml)

### Institutional Learnings

- 失败语义与 UTF-8 稳定性: [docs/solutions/integration-issues/cli-structured-failure-and-windows-utf8-compatibility.md](D:/Git_Repo/Paper-Analysis-New/docs/solutions/integration-issues/cli-structured-failure-and-windows-utf8-compatibility.md)
- HTML 逐用例契约与状态真值: [docs/solutions/integration-issues/ci-html-review-report-scalability-and-case-awareness.md](D:/Git_Repo/Paper-Analysis-New/docs/solutions/integration-issues/ci-html-review-report-scalability-and-case-awareness.md)
