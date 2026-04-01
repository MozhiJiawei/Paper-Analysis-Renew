---
date: 2026-03-31
topic: testing-quality-refactor
---

# 测试与质量门禁重构需求

## Problem Frame

当前仓库已经具备统一的 `quality local-ci` 入口，并通过 `lint -> typecheck -> unit -> integration -> e2e` 串起本地质量门禁。现状的优点是链路清晰、仓库约束明确、HTML 审核页可直接用于人工验收。

但从维护成本视角看，前两层门禁仍有明显改进空间：

- 当前 `lint` 更偏“文本与仓库规范检查”，尚未覆盖主流 Python 静态质量问题。
- 当前 `typecheck` 只检查公开函数是否写了类型注解，并不能验证类型是否正确。
- 代码坏味道如复杂度过高、重复逻辑、长函数、大文件等尚未形成清晰分层策略。

本次讨论先聚焦质量门禁最前面的两层，即 `lint -> typecheck`，目标是在不破坏现有统一入口与仓库特有约束的前提下，建立一套更可信、维护成本更低的静态质量策略。

## Requirements

- R1. 质量门禁需要继续保留统一入口 `py -m paper_analysis.cli.main quality local-ci`，不因工具替换而改变使用方式。
- R2. 仓库特有的文本与编码约束必须继续保留，至少包括 UTF-8、常见乱码片段、基础文本卫生等检查。
- R3. Python 通用静态检查应尽量交给成熟工具，而不是持续扩写自定义脚本。
- R4. `lint` 层应同时覆盖两类能力：
  - 仓库特有规则
  - Python 通用代码质量规则
- R5. `typecheck` 层应从“注解是否存在”逐步演进到“类型是否正确”的真实类型检查。
- R5a. 新方案中，真实类型检查不再保留独立 `typecheck` 阶段，而是并入统一的 `lint` 阶段执行。
- R6. 类型检查引入需要支持渐进式落地，优先覆盖最稳定、最结构化、最有收益的核心模块，不要求一次性全仓严格。
- R7. 代码坏味道检查需要分层治理，不把所有指标都直接做成硬门禁。
- R8. 对维护成本影响较大的通用坏味道中，复杂度检查可以较早纳入门禁；重复度、长函数、大文件等更适合作为报告或重构候选清单，而不是第一时间阻断 CI。
- R8a. 代码质量检查在第一阶段只负责报警和产出报告，不阻断 `quality local-ci`。
- R9. 门禁设计需要优先减少“形式合规但保护有限”的检查，避免团队为了过规则而增加样板注解或机械拆分代码。
- R10. 新方案需要让失败原因更容易解释：开发者应能快速区分“仓库规范失败”“Python lint 失败”“真实类型错误”“治理提示”这几类问题。

## Success Criteria

- `lint` 层既能继续拦截 UTF-8 / 乱码 / 文本卫生问题，也能覆盖常见 Python 静态质量问题。
- `typecheck` 层能发现当前 AST 注解存在性检查无法发现的真实类型问题。
- 团队对每类门禁的职责边界有清晰共识，不再把“注解存在性检查”误认为真实类型检查。
- 坏味道治理形成清晰分层：哪些必须拦，哪些只做报告，哪些暂不纳入。
- 新增规则不会明显抬高误报率或让测试与开发工作变成“为满足指标而重写代码”。

## Scope Boundaries

- 本轮记录只覆盖 `lint`、`typecheck` 和静态坏味道检查策略，不展开到 unit / integration / e2e 重构方案。
- 本轮不要求立即决定具体工具配置细节，如完整规则列表、阈值数值或全仓严格模式。
- 本轮不要求立刻废弃现有自定义脚本，但要求明确其后续定位。
- 本轮不把重复度、长函数、大文件等治理指标直接定为强门禁。

## Key Decisions

- 保留仓库特有 `lint`，但不继续把它扩成通用 Python lint：
  当前自定义 `lint.py` 很适合承担 UTF-8、乱码、文档与文本卫生这类仓库特有规范；若继续往里堆 Python 语义规则，会把它演化成高维护成本的自研 mini-linter。
- Python 通用代码质量检查应引入 `ruff`：
  `ruff` 更适合承接未使用导入、未使用变量、重复定义、可疑写法、部分复杂度规则等通用问题，规则成熟、速度快、认知成本低。
- 当前 AST `typecheck` 不应继续作为长期主方案扩张：
  它只能检查“有没有注解”，不能验证“注解是否正确”，容易制造虚假的质量安全感，也会鼓励形式化补注解。
- 真实类型检查应逐步转向 `mypy`：
  相比注解存在性检查，`mypy` 更能发现参数类型不匹配、返回类型不一致、Optional 未处理、容器元素类型错误、协议对象边界不自洽等真实问题。
- `mypy` 应采用渐进式接入：
  优先覆盖领域模型、协议对象、结构化输入输出更明确的核心模块，而不是一开始就全仓 strict。
- 现有 `scripts/quality/typecheck.py` 应以“迁移后删除”为默认目标：
  只要 `mypy` 已覆盖核心模块并能提供真实类型保护，旧的 AST 注解存在性检查应果断下线，不保留长期并行状态。
- 新静态质量门禁统一收敛到 `lint`：
  `lint` 内部顺序执行编码类检查、`ruff`、`mypy`，并将代码质量治理报告作为同一阶段的附加输出，而不再保留独立 `typecheck` 阶段。
- 代码质量检查第一阶段只报警不报错：
  重复度、长函数、大文件等治理指标用于暴露重构热点和生成报告，不应在第一阶段直接阻断 CI。
- 代码坏味道检查需要分成“硬门禁”和“治理报告”两层：
  复杂度过高属于较早值得拦截的风险；重复代码、长函数、大文件更适合作为报告型输出，用于发现重构热点，而不是一开始直接卡死 CI。
- 判断规则去留的原则应是：
  - 仓库独有约束留在自定义脚本
  - Python 通用静态问题优先交给成熟工具
  - 结构治理类指标优先用于发现热点，而不是优先阻断开发

## Candidate Deletions

- 应下线“自定义 Python 通用 lint 规则”这一演进方向：
  如果某条规则检查的是未使用导入、未使用变量、重复定义、可疑写法、导入风格或复杂度等 Python 通用问题，不应继续加到 `scripts/quality/lint.py`，而应交给 `ruff`。
- 应下线当前 AST `typecheck.py` 作为主 typecheck 的定位：
  它可以在迁移期短暂并行存在，但不应继续被视为长期主门禁，也不应继续扩写更多“注解存在性”规则。
- 应以下线 `scripts/quality/typecheck.py` 为默认迁移终点：
  如果 `mypy` 已接住真实类型检查能力，旧脚本不应继续留在 `quality` 命令面里占一个长期阶段。
- 应下线“公开函数必须先补注解才能过门禁”作为质量目标本身：
  这类规则只能推动形式合规，不能证明类型安全；后续应以真实类型检查结果替代“是否写了注解”。
- 应下线把重复度、长函数、大文件直接作为首批硬门禁的方案：
  它们更适合作为报告型治理指标，若直接阻断 CI，容易在测试、fixture、协议定义等位置产生高噪音。
- 应下线对同一类通用静态问题的双重维护：
  一旦 `ruff` 或 `mypy` 成为正式门禁，旧脚本中与其重复、但能力更弱的规则应移除，避免出现“两套规则同时维护、结论还不完全一致”的状态。

## Rule Triage

### Lint Rules To Keep

- 保留“全仓 UTF-8 可读”检查：
  这是仓库级硬约束，且覆盖 Python 之外的 Markdown、JSON、TOML、文档与 agent 配置文件，`ruff` 不能替代。
- 保留“常见乱码片段检测”：
  这是中文仓库特有的质量保护，属于成熟通用工具不会覆盖的规则。
- 保留“非 Python 文本文件基础卫生检查”：
  对 `docs/`、`.codex/`、`README.md`、`AGENTS.md` 以及 JSON/TOML 等非 Python 文件，继续检查尾随空格、Tab 和文件末尾换行是合理的。

### Lint Rules To Migrate

- Python 文件中的基础风格与静态问题迁移给 `ruff`：
  包括尾随空格、Tab、导入风格、未使用导入、未使用变量、重复定义、可疑写法等。
- Python 代码复杂度检查迁移给 `ruff`：
  复杂度属于 Python 代码质量问题，更适合纳入统一的 Python 静态检查工具，而不是继续堆进仓库特有 `lint.py`。
- 后续新增的 Python 通用质量规则默认迁移到 `ruff`：
  除非规则明确依赖本仓特有语义，否则不再新增到 `scripts/quality/lint.py`。

### Lint Rules To Delete

- 删除“让 `scripts/quality/lint.py` 同时承担仓库特有 lint 与 Python 通用 lint”这一职责混合状态：
  自定义脚本未来只保留仓库特有规则，不再承担通用 Python 语义检查。
- 删除 Python 文件上与 `ruff` 重复的基础格式检查：
  一旦 `ruff` 接管 Python 文件，旧脚本中对 Python 文件的尾随空格、Tab、末尾换行等重复实现应移除，避免双重报错。
- 删除未来在自定义 `lint.py` 中继续扩展 Python AST/语义规则的计划：
  这条演进路径会持续增加维护成本，应在方向上直接关闭。

## Quality Stage Design

- 新质量阶段应围绕“人能看懂失败原因”来设计，而不是围绕旧脚本名保留历史包袱。
- 新的静态质量结构默认收敛为：
  - `lint`：统一执行编码类检查、`ruff`、`mypy`
  - `unit`
  - `integration`
  - `e2e`
- `lint` 阶段内部需要显式区分四类结果：
  1. 编码类检查
  2. `ruff`
  3. `mypy`
  4. 代码质量检查（报告型，不阻断）
- 删除旧 `typecheck.py` 后，不再保留独立 `typecheck` 阶段或独立命令。
- HTML 审核页的“质量检查”大类继续保留，但其内部应明确展示：
  - 哪些子检查通过/失败
  - 哪些子检查只是报警
  - 代码质量报告是否产生告警但未阻断
- `quality local-ci` 的推荐顺序应变为：
  1. `lint`
  2. `unit`
  3. `integration`
  4. `e2e`
- 对单独运行命令而言，优先保持命令面简洁：
  - `quality lint` 作为静态质量总入口
  - 不再保留 `quality typecheck`
  - 如需调试子项，可在实现阶段再决定是否提供 lint 子项参数，而不是暴露新的顶层阶段名

## Command Surface Direction

- 命令面对外采用统一收敛方案：
  - `quality lint`：统一运行编码类检查、`ruff`、`mypy` 与代码质量报告
  - `quality unit`
  - `quality integration`
  - `quality e2e`
  - `quality local-ci`
- `quality typecheck` 从稳定命令面中删除。
- 代码质量检查虽然放在 `lint` 内，但默认只报警不报错；`quality lint` 的退出码只受编码类检查、`ruff` 与 `mypy` 影响。
- 不再考虑新增 `quality py-lint` 或保留旧 `quality typecheck` 兼容层。

## First-Cut Lint Checklist

- 第一版 `quality lint` 默认包含四个子检查：
  1. 编码类检查
  2. `ruff`
  3. `mypy`
  4. 代码质量报告
- 第一版目标不是“把所有能测的都测上”，而是优先形成职责清晰、噪音可控、后续可扩展的最小闭环。

### 1. 编码类检查

- 保留现有自定义脚本能力，但收缩职责到仓库特有规则：
  - 全仓 UTF-8 可读
  - 常见乱码片段检测
  - 非 Python 文本文件的尾随空格、Tab、文件末尾换行
- Python 文件上与 `ruff` 重复的基础格式检查从这里移除。

### 2. Ruff

- 第一版 `ruff` 负责：
  - Python 基础 lint
  - 未使用导入与未使用变量
  - 明显可疑写法
  - import 风格统一
  - 基础复杂度规则
- 第一版不追求一次开启大量风格化规则；应优先选择“低争议、强信号”的规则集合，减少大面积格式噪音。

### 3. Mypy

- 第一版 `mypy` 只覆盖核心、高结构化模块，不要求一开始覆盖测试目录和所有 CLI 拼装层。
- 优先候选模块：
  - `paper_analysis/domain/`
  - `paper_analysis/api/` 下的协议与结构化对象
  - `paper_analysis/sources/arxiv/`
  - `paper_analysis/services/report_writer.py`
  - 其他以结构化输入输出为主、动态行为较少的模块
- 第一版默认不强求：
  - `tests/`
  - 复杂 subprocess/CLI 编排层
  - 以 `dict[str, Any]` 和动态拼装为主、尚未整理边界的模块

### 4. 代码质量报告（只报警不报错）

- 第一版纳入以下指标：
  - 圈复杂度
  - 重复代码
  - 长函数
  - 大文件
  - 模块依赖异味
- 推荐实现方向：
  - 圈复杂度优先基于 `radon`
  - 重复代码优先基于 `jscpd`
  - 长函数与大文件优先采用轻量报告或复用复杂度工具输出，不急于做硬阈值门禁
  - 模块依赖异味可先用最小自定义脚本或轻量分析，不要求第一版就做到完整架构治理
- 第一版报告默认只生成告警与排序清单，不影响 `quality lint` 返回码。
- 报告输出应尽量聚焦前 N 个最值得处理的问题点，而不是完整倾倒所有指标明细。

## Tooling Direction

- 编码类检查继续使用仓库自定义脚本。
- Python 通用静态质量使用 `ruff`。
- 真实类型检查使用 `mypy`。
- 复杂度分析优先使用 `radon`。
- 重复代码检测优先使用 `jscpd`。
- 若后续需要补充死代码治理，可再评估 `vulture`，但不属于当前第一版范围。

## Final Lint Decisions

- `quality lint` 作为唯一静态质量入口：
  所有静态质量检查统一归并到 `quality lint`，不再拆出独立的 `quality typecheck` 或其他新的静态顶层阶段。
- `quality lint` 的四段式结构固定为：
  1. 编码类检查
  2. `ruff`
  3. `mypy`
  4. 代码质量检查（只报警不报错）
- `scripts/quality/typecheck.py` 迁移完成后直接删除：
  不保留长期兼容层，不再接受“注解存在性检查”作为主质量门禁。
- `quality typecheck` 从稳定命令面移除：
  真实类型检查能力由 `mypy` 并入 `quality lint` 承担。
- 自定义 `scripts/quality/lint.py` 收缩为仓库特有规则脚本：
  只保留 UTF-8、乱码片段、非 Python 文本文件基础卫生等项目约束，不再承担 Python 通用语义检查。
- Python 文件上的通用静态质量默认全部迁给 `ruff`：
  包括未使用导入、未使用变量、可疑写法、import 风格、基础复杂度，以及 Python 文件上的基础格式检查。
- `mypy` 只负责真实类型检查，不再额外保留“公开函数必须有注解”的独立硬规则：
  质量目标从“有没有写类型”切换为“类型是否正确、边界是否自洽”。
- 代码质量检查第一版只报警不报错：
  圈复杂度、重复代码、长函数、大文件、模块依赖异味等用于生成治理报告，不影响 `quality lint` 退出码。
- `quality lint` 的退出码只受前三类子检查影响：
  只有编码类检查、`ruff`、`mypy` 会让 `quality lint` 失败；代码质量报告只产生告警。
- 第一版工具栈固定为：
  - 编码类检查：仓库自定义脚本
  - Python 静态检查：`ruff`
  - 类型检查：`mypy`
  - 复杂度：`radon`
  - 重复代码：`jscpd`
- 第一版 `mypy` 采用渐进覆盖策略：
  先覆盖高结构化、核心业务模块，不要求一开始覆盖 `tests/`、CLI 编排层和动态性较强的模块。
- 第一版治理报告以“高信号榜单”而非“全量倾倒指标”为目标：
  重点输出最值得处理的前 N 个复杂函数、重复块、超长函数和超大文件，降低噪音。
- `lint` 的最终职责边界固定为：
  - 拦截静态质量硬错误
  - 输出代码质量治理告警
  - 不承担 unit / integration / e2e 的语义
- 规则去留的最终原则固定为：
  - 仓库独有约束留在自定义脚本
  - Python 通用静态问题交给成熟工具
  - 真实类型问题交给 `mypy`
  - 治理指标优先报告，不先阻断

## Alternatives Considered

- 继续扩写现有自定义 `lint.py` 与 `typecheck.py`：
  可保持工具面简单，但会持续增加自研规则维护成本，且很难达到主流静态工具的成熟度与覆盖度。
- 只保留当前自定义门禁，不引入新工具：
  可避免短期迁移成本，但无法覆盖大量通用 Python 静态问题，也无法建立真实类型检查能力。
- 一次性引入大量坏味道门禁：
  虽然看起来“全面”，但容易在测试文件、fixture、协议定义等位置产生高噪音，反而增加开发摩擦。

## Dependencies / Assumptions

- 仓库当前仍以 `unittest` 与自定义质量脚本为主。
- 当前 `lint.py` 已承担 UTF-8、乱码片段、文本卫生检查。
- 当前 `typecheck.py` 只检查公开函数和公开方法的类型注解存在性。
- 团队当前更关注“降低维护成本”，而不是单纯增加门禁数量。
- 现阶段允许采用成熟开源 Python 工具替换或补充现有门禁实现。

## Outstanding Questions

### Resolve Before Planning

- [Affects R4][User decision] `ruff` 与 `mypy` 是否接受作为正式依赖引入主仓，并纳入稳定的 `quality` 命令面。
- [Affects R5][User decision] 现有 `scripts/quality/typecheck.py` 是否按“迁移完成后直接删除”处理，而不是长期保留兼容层。

### Deferred to Planning

- [Affects R4][Technical] `quality lint` 内部应如何组织编码类检查、`ruff`、`mypy` 与代码质量报告的执行顺序、输出格式与失败汇总。
- [Affects R4][Technical] `scripts/quality/lint.py` 在迁移后是继续保留现名，还是重命名为更准确的仓库特有检查脚本。
- [Affects R5][Technical] 在 `mypy` 接管前，旧 `typecheck.py` 的最短迁移窗口应如何设计，才能避免重复噪音。
- [Affects R6][Technical] `mypy` 第一阶段最适合覆盖哪些目录或模块，才能以最低噪音获得最高收益。
- [Affects R6][Technical] 是否需要为结构化产物补充 `TypedDict`、dataclass 或更清晰的返回类型，以提高 `mypy` 收益。
- [Affects R8][Technical] 复杂度规则应由 `ruff` 内建规则承担，还是补充独立报告脚本做趋势跟踪。
- [Affects R8][Needs research] 重复代码、长函数、大文件等治理报告采用哪种工具或最小实现最适合当前仓库。
- [Affects R10][Technical] HTML 审核页是否需要展示更细的静态检查分类，帮助人类快速区分失败来源。
- [Affects R10][Technical] `paper_analysis.cli.quality`、`quality_case_support.py` 与 `ci_html_writer.py` 需要如何调整阶段名映射，才能兼容新的静态检查结构。

## Next Steps

→ 继续脑暴并收敛 `ruff` / `mypy` 的仓库内接入方式、覆盖范围与坏味道分层策略，然后再进入实现规划。
