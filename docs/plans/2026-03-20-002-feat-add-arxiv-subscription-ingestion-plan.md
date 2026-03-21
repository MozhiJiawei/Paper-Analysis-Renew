---
title: feat: Add arXiv subscription ingestion
type: feat
status: active
date: 2026-03-20
---

# feat: Add arXiv subscription ingestion

## Overview

为现有 `arxiv` 业务链路补齐“订阅”这一核心输入模式：CLI 通过 arXiv 官方 API 拉取指定订阅范围内的论文，沿用现有偏好筛选与报告写出能力；在本阶段继续保持“推荐过滤”实现为空或最小占位，不新增独立 `recommend` 命名空间。

用户还要求两件事必须同时满足：

- e2e 测试运行时真实访问 arXiv API，而不是只消费本地样例。
- `example/fetch_arxiv_api.py` 的实现经验要被吸收进正式代码，开发完成后删除整个 `example/` 目录。

## Problem Statement / Motivation

当前 `ArxivPipeline` 仅从固定样例 `tests/fixtures/arxiv/sample_daily.json` 读取输入，`arxiv report` 与 `tests/e2e/test_golden_paths.py` 也都建立在静态样例之上。这与仓库“两条核心业务链路”中的第二条并不一致：系统目前只能演示“arXiv 日更筛选骨架”，还不能执行真实订阅拉取。

这带来几个直接问题：

- `arxiv` 命令没有真实外部数据源，无法验证 API 接入、限流、网络异常与真实字段映射。
- e2e 不能证明系统在联网情况下仍能稳定产出 `summary/json/csv/stdout`。
- `example/` 中已经存在可运行的 API 拉取原型，但它游离于正式 CLI 和测试体系之外，容易形成重复实现。

## Proposed Solution

在现有 `arxiv` 命名空间内新增“订阅拉取”能力，并让 `arxiv report`/`arxiv daily-filter` 可按参数切换输入来源：

1. 保留当前 fixture 模式作为离线回归基础。
2. 在 `paper_analysis/sources/arxiv/` 下引入正式 API 客户端与响应解析器，吸收 `example/fetch_arxiv_api.py` 的日期范围、分页、Atom 解析与字段标准化逻辑。
3. 在 `ArxivPipeline` 中增加显式 source mode，例如 `fixture` / `subscription-api`，统一输出 `Paper` 列表。
4. 给 `arxiv` CLI 增加订阅相关参数，但仍维持业务入口只在 `arxiv` 下，不新增第三命名空间。
5. 让至少一条 e2e 黄金路径真实访问 arXiv API，并控制为单连接、低频、小批量请求，符合官方限制。
6. 完成迁移后删除 `example/` 目录，把原型脚本与测试信息改写为正式实现和正式测试。

### Working Assumptions

为避免实现时反复讨论，第一版按以下假设落地：

- 订阅最小参数集以“单日窗口”表达，优先复用 `example/fetch_arxiv_api.py` 已验证的日期范围模型，而不是一开始做多 profile 订阅管理。
- `arxiv report` 与 `arxiv daily-filter` 共用同一组订阅参数；`report` 只是在成功后多一步写出产物。
- 真实联网 e2e 不断言固定论文标题，而是断言来源、数量下限、`paper_id`/`published_at`/`authors` 等结构字段。
- 保留 fixture 驱动的 unit/integration 回归，避免所有 arXiv 测试都绑死在外部网络上。

## Technical Considerations

- 架构影响
  - `paper_analysis/services/arxiv_pipeline.py` 需要从“只会读 fixture”演进为“调度不同 arXiv 输入源”的 pipeline。
  - 新的 API 访问与 Atom 解析不应直接塞进 CLI，应该放在 `paper_analysis/sources/arxiv/` 之下，符合仓库对真实来源适配的扩展方式。
- 数据建模影响
  - [paper_analysis/domain/paper.py](D:/Git_Repo/Paper-Analysis-New/paper_analysis/domain/paper.py) 要求标准化输出至少包含 `paper_id`、`title`、`abstract`、`source`、`venue`、`authors`、`tags`、`organization`、`published_at`。
  - arXiv Atom feed 中缺失的字段应使用稳定缺省值填充，例如 `organization=""`、`acceptance_status=""`、`venue="arXiv"`，避免 `Paper(**item)` 因字段不完整而失败。
- 性能影响
  - e2e 与真实订阅拉取必须严格限制请求频率与返回数量，避免因分页过深、等待过久导致 CI 不稳定。
  - 正式实现应尽量减少请求次数，优先使用小结果集和明确查询窗口。
- 安全与可靠性
  - 需要把网络失败、超时、HTTP 错误、XML 解析错误统一翻译为结构化 CLI 失败输出，延续现有 `CliInputError` 模式。
  - 必须显式设置 `User-Agent` 和 UTF-8 输出，避免请求被目标服务误判，也避免 Windows 下日志乱码。

## System-Wide Impact

- **Interaction graph**: `py -m paper_analysis.cli.main arxiv report ...` 调用 [paper_analysis/cli/arxiv.py](D:/Git_Repo/Paper-Analysis-New/paper_analysis/cli/arxiv.py)；CLI 进入 `ArxivPipeline.run()`；pipeline 根据参数选择 fixture loader 或新的 subscription API loader；结果交给 [paper_analysis/services/preference_ranker.py](D:/Git_Repo/Paper-Analysis-New/paper_analysis/services/preference_ranker.py)；最终由 [paper_analysis/services/report_writer.py](D:/Git_Repo/Paper-Analysis-New/paper_analysis/services/report_writer.py) 落盘到 `artifacts/e2e/arxiv/latest/`。CI HTML 审核页继续消费该目录下的真实产物。
- **Error propagation**: 网络层异常、HTTP 非 200、返回体为空、XML/Atom 解析失败、查询参数非法，都应在 source/pipeline 层转成 `CliInputError`，再由 [paper_analysis/cli/arxiv.py](D:/Git_Repo/Paper-Analysis-New/paper_analysis/cli/arxiv.py) 统一渲染 `[FAIL] scope=arxiv.*`。不要把 traceback 直接暴露到终端，延续 `docs/solutions/integration-issues/cli-structured-failure-and-windows-utf8-compatibility.md` 的规则。
- **State lifecycle risks**: e2e 与 CLI 都会写同一批 `artifacts/e2e/arxiv/latest/` 文件。如果联网调用失败，不能留下部分成功、部分缺失的假阳性产物。需要定义写出时机：只有拿到最终 `papers` 结果后再调用 `write_report`；失败路径不应覆盖上一次成功产物，或需要先明确清理策略。
- **API surface parity**: `arxiv daily-filter` 与 `arxiv report` 应共享同一订阅拉取逻辑，不能一个走真实 API、一个仍写死 fixture。`report --source arxiv` 与 CI HTML 读取路径无需新增接口，但要能消费新的真实产物。
- **Integration test scenarios**:
  - CLI 使用订阅参数成功访问真实 arXiv API，并生成四类产物。
  - API 超时或 4xx/5xx 时，CLI 返回结构化失败且无 traceback。
  - API 返回 0 条结果时，`daily-filter`/`report` 的 stdout、JSON、Markdown 行为明确且可回归。
  - 联网 e2e 生成的 `result.json` 可被 CI HTML 正常消费。
  - Windows UTF-8 环境下，联网失败日志仍可读。

## SpecFlow Analysis

### User Flow Overview

1. 用户运行 `arxiv daily-filter` 或 `arxiv report`，显式选择订阅输入参数。
2. CLI 校验参数，并将请求交给 `ArxivPipeline`。
3. pipeline 组合查询条件，调用 arXiv API，分页读取并解析 Atom feed。
4. 解析后的记录被标准化为 `Paper`，再交给共享偏好排序逻辑。
5. 若当前阶段“推荐过滤”保持为空实现，则系统仍应走完整个输入、标准化、报告链路，只是筛选规则最小化。
6. `daily-filter` 打印终端结果；`report` 额外写出结构化报告；e2e 用真实网络调用覆盖该路径。

### Missing Elements & Gaps

- **参数设计**: “订阅”在 CLI 上是按日期、日期目录格式、分类列表还是固定 profile 表达，当前需求没有完全钉死。
  - 规划默认采用“最小必要参数集”：`--source-mode subscription-api`、`--subscription-date <YYYY-MM/MM-DD>`，可选 `--category` 多值参数与 `--max-results` 上限；后续再扩展 profile 化订阅。
- **测试稳定性**: e2e 要求真实访问 API，但未规定离线或 arXiv 服务异常时的处置。
  - 规划默认把联网 e2e 设计为受控黄金路径；若网络不可达，测试应给出明确失败原因，而不是静默跳过。
- **结果规模**: 未规定单次订阅拉取上限。
  - 规划默认限制为小批量和可配置上限，避免 e2e 过慢或触发限流。
- **推荐空实现语义**: “保持推荐过滤实现为空”需要明确为空的边界。
  - 规划默认理解为：不新增复杂偏好/召回逻辑，但仍保留当前最小可运行的 shared ranking/输出契约；若必须彻底旁路评分，则要同步修改报告契约与现有测试。

### Critical Questions Requiring Clarification

1. **Important**: CLI 上的“订阅”是否以单日窗口为第一版主入口？
   - Why it matters: 直接决定参数命名、示例文档、测试基线和 source API 设计。
   - Default assumption: 第一版采用与 `example/fetch_arxiv_api.py` 一致的日期窗口输入，再为后续 profile 订阅留扩展点。
2. **Important**: 联网 e2e 是否允许在 arXiv 官方不可用时失败？
   - Why it matters: 影响 CI 策略和本地开发体验。
   - Default assumption: 允许失败，但失败信息必须结构化、可诊断。
3. **Nice-to-have**: 是否需要单独保留一个“离线 fixture e2e”作为非联网回归？
   - Why it matters: 能显著降低日常回归对外网依赖。
   - Default assumption: 保留现有 integration/unit fixture 回归，不再单独保留第二条 arXiv e2e。

### Recommended Next Steps

- 在计划实施前先固定订阅参数最小集合，避免 CLI 帮助文案反复变化。
- 先抽 source 层与解析器，再改 CLI 和 e2e，减少 `example/` 迁移时的重复。
- 把联网 e2e 的查询窗口控制到确定性较高、请求量较低的范围内。

## Acceptance Criteria

- [ ] `arxiv` 命名空间内新增正式订阅输入能力，不新增 `recommend` 或其他第三业务命名空间。
- [ ] [paper_analysis/services/arxiv_pipeline.py](D:/Git_Repo/Paper-Analysis-New/paper_analysis/services/arxiv_pipeline.py) 可根据参数从 fixture 或真实 arXiv API 拉取数据，并统一返回 `Paper` 列表。
- [ ] 正式 API 访问与解析代码落在新的 `paper_analysis/sources/arxiv/` 目录中，吸收 `example/fetch_arxiv_api.py` 的核心逻辑而不是继续依赖 `example/`。
- [ ] `arxiv daily-filter` 与 `arxiv report` 共用同一订阅拉取逻辑。
- [ ] 第一版 CLI 至少支持 `--source-mode subscription-api` 与 `--subscription-date`；若支持附加分类或数量控制，帮助文案与文档必须同步更新。
- [ ] `arxiv report` 在订阅模式下仍写出 `summary.md`、`result.json`、`result.csv`、`stdout.txt` 四类产物。
- [ ] 至少一条 [tests/e2e/test_golden_paths.py](D:/Git_Repo/Paper-Analysis-New/tests/e2e/test_golden_paths.py) 用例在运行时真实访问 arXiv API，并校验产物存在与核心字段合法。
- [ ] 联网失败、超时、解析失败时，CLI 返回结构化失败输出，无 traceback 泄漏。
- [ ] `example/` 目录在实现迁移完成后被删除。
- [ ] 与命令面相关的文档同步更新：
  - [D:/Git_Repo/Paper-Analysis-New/.codex/skills/paper-analysis/SKILL.md](D:/Git_Repo/Paper-Analysis-New/.codex/skills/paper-analysis/SKILL.md)
  - [docs/agent-guide/command-surface.md](D:/Git_Repo/Paper-Analysis-New/docs/agent-guide/command-surface.md)
  - CLI `--help`
- [ ] 若新增来源、规则或测试层级，更新 [docs/engineering/extending-cli.md](D:/Git_Repo/Paper-Analysis-New/docs/engineering/extending-cli.md)。

## Success Metrics

- 用户可通过稳定 CLI 命令拉取一次真实 arXiv 订阅结果，并产出可读报告。
- `tests/e2e/test_golden_paths.py` 能证明 `arxiv` 黄金路径已经联网而非仅依赖样例。
- `quality local-ci` 仍能汇总并展示 arXiv e2e 产物。
- 删除 `example/` 后，仓库不存在第二套平行实现。
- 正常与异常路径都能维持现有 CLI 结构化输出风格。

## Dependencies & Risks

- **外部依赖风险**: arXiv API 的可用性、返回延迟与兼容性变化会直接影响联网 e2e。
- **限流风险**: 官方要求 legacy arXiv API 全局不高于每 3 秒 1 次请求、单连接访问；测试必须围绕这个约束设计。依据官方 Terms of Use 与 API 文档推断，应避免并发请求与大分页。
- **字段映射风险**: Atom feed 字段与现有 `Paper` 模型并不一一对应，需要定义缺省值与标准化规则。
- **测试脆弱性**: 若断言真实返回的论文标题，测试会变脆；应更多断言结构、来源、数量下限、标识格式与关键字段存在性。

## Implementation Suggestions

### Phase 1: Source Layer

- 新增 `paper_analysis/sources/arxiv/api_client.py`
  - 负责构造查询、设置 `User-Agent`、执行请求、处理限流等待与错误翻译。
- 新增 `paper_analysis/sources/arxiv/atom_parser.py`
  - 负责把 Atom feed 转成仓库内标准字典或 `Paper` 输入载荷。
- 新增 `paper_analysis/sources/arxiv/subscription_loader.py`
  - 封装“按订阅窗口拉取论文列表”的高层入口。

### Phase 2: Pipeline & CLI

- 扩展 [paper_analysis/services/arxiv_pipeline.py](D:/Git_Repo/Paper-Analysis-New/paper_analysis/services/arxiv_pipeline.py)
  - 增加 source mode 与订阅参数透传。
- 扩展 [paper_analysis/cli/arxiv.py](D:/Git_Repo/Paper-Analysis-New/paper_analysis/cli/arxiv.py)
  - 新增订阅参数。
  - 推荐最小形态：
    - `--source-mode fixture|subscription-api`
    - `--subscription-date YYYY-MM/MM-DD`
    - `--category <term>` 可重复
    - `--max-results <int>`
  - 更新 `--help` 文案。
  - 维持 `CliInputError` 结构化失败模式。

### Phase 3: Tests & Docs

- 更新 [tests/integration/test_pipelines.py](D:/Git_Repo/Paper-Analysis-New/tests/integration/test_pipelines.py)
  - 覆盖订阅模式成功路径与失败路径。
  - 成功路径优先 mock 网络层或 source 层，避免 integration 测试直接依赖外网。
- 更新 [tests/e2e/test_golden_paths.py](D:/Git_Repo/Paper-Analysis-New/tests/e2e/test_golden_paths.py)
  - 真实联网访问 arXiv API。
  - 降低对具体标题的脆弱断言。
  - 断言建议：
    - `result.returncode == 0`
    - `result.json["source"] == "arXiv"`
    - `count >= 1`
    - 至少一篇论文包含非空 `paper_id`、`title`、`published_at`
    - `stdout.txt`、`summary.md`、`result.csv` 存在
- 更新命令面和扩展文档。
- 删除 `example/` 目录及其旧测试。

## Alternative Approaches Considered

### 方案 A：继续只用 fixture，避免联网测试

不采纳。

原因：

- 与用户“e2e 测试运行时会访问 arxiv 订阅的 API”的要求直接冲突。
- 无法验证真实查询参数、限流、网络错误与 Atom 解析。

### 方案 B：新增独立 `subscription` 或 `recommend` 命名空间

不采纳。

原因：

- 违反仓库约定：业务入口只允许 `conference` 和 `arxiv`。
- 会把共享推荐阶段误建成第三业务域，破坏现有命令面边界。

### 方案 C：保留 `example/` 作为长期参考实现

不采纳。

原因：

- 会形成正式代码与示例代码双轨维护。
- 与“开发完成后删除 example 目录”的明确要求冲突。

## Documentation Plan

- 更新 [D:/Git_Repo/Paper-Analysis-New/.codex/skills/paper-analysis/SKILL.md](D:/Git_Repo/Paper-Analysis-New/.codex/skills/paper-analysis/SKILL.md)，补充 arXiv 订阅命令与入口说明。
- 更新 [docs/agent-guide/command-surface.md](D:/Git_Repo/Paper-Analysis-New/docs/agent-guide/command-surface.md)，记录新增参数或新的 arXiv 行为。
- 更新 [docs/engineering/extending-cli.md](D:/Git_Repo/Paper-Analysis-New/docs/engineering/extending-cli.md)，说明如何扩展 arXiv 真实来源。
- 如有必要，补充测试/质量文档，说明联网 e2e 的定位与约束。

## Sources & References

- **Internal references**
  - [paper_analysis/services/arxiv_pipeline.py](D:/Git_Repo/Paper-Analysis-New/paper_analysis/services/arxiv_pipeline.py)
  - [paper_analysis/cli/arxiv.py](D:/Git_Repo/Paper-Analysis-New/paper_analysis/cli/arxiv.py)
  - [tests/e2e/test_golden_paths.py](D:/Git_Repo/Paper-Analysis-New/tests/e2e/test_golden_paths.py)
  - [tests/integration/test_pipelines.py](D:/Git_Repo/Paper-Analysis-New/tests/integration/test_pipelines.py)
  - [example/fetch_arxiv_api.py](D:/Git_Repo/Paper-Analysis-New/example/fetch_arxiv_api.py)
  - [docs/solutions/integration-issues/cli-structured-failure-and-windows-utf8-compatibility.md](D:/Git_Repo/Paper-Analysis-New/docs/solutions/integration-issues/cli-structured-failure-and-windows-utf8-compatibility.md)
- **External references**
  - arXiv API Basics: https://info.arxiv.org/help/api/basics.html
  - arXiv API User Manual: https://info.arxiv.org/help/api/user-manual.html
  - arXiv API Terms of Use: https://info.arxiv.org/help/api/tou.html
    - 关键约束：legacy arXiv API 使用方需控制在单连接、每 3 秒最多 1 次请求。
