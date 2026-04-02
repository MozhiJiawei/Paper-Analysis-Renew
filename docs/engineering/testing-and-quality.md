# Testing And Quality

## 当前策略

当前仓库的质量门禁以 `unittest` 和自定义质量脚本为基础，统一通过稳定的 CLI 入口执行。

- `unittest` 负责 unit、integration、e2e 测试
- `lint` 阶段统一执行仓库规范检查、`ruff`、`mypy` 与代码质量治理报告
- 仓库规范检查只负责 UTF-8、常见乱码片段，以及非 Python 文本文件的空白字符卫生规则
- `ruff` 负责 Python 通用静态质量，`mypy` 负责首批核心结构化模块的真实类型检查
- 代码质量治理报告默认只告警，不阻断 `quality lint`
- `Jinja2` 负责静态 HTML 审核页渲染

## 统一入口

```powershell
py -m paper_analysis.cli.main quality local-ci
```

执行顺序：

1. `lint`
2. `unit`
3. `integration`
4. `e2e`

执行完成后，除了终端输出，还会生成供人工审核的 HTML 汇总页：

```text
artifacts/quality/local-ci-latest.html
```

`quality lint` 内部固定拆成四段：

1. 仓库规范检查
2. `ruff`
3. `mypy`
4. 代码质量治理报告（只告警，不阻断）

补充约束：

- 需要通过 `subprocess.run(..., capture_output=True)` 抓取 CLI 输出的测试，优先依赖 CLI 自身的 UTF-8 标准输出配置，而不是把编码稳定性完全外包给调用方环境
- 如果测试或脚本继续拉起 Python 子进程，仍应显式传递 `PYTHONUTF8=1` 与 `PYTHONIOENCODING=utf-8`，避免 Windows 管道输出退回本地代码页

## 主仓与子仓边界

- 主仓 `quality local-ci` 只覆盖主仓能力：`conference`、`arxiv`、`report` 及其非数据集相关检查
- benchmark / annotation / 网页标注 / 评测数据 / 相关测试位于 `third_party/paper_analysis_dataset`
- 主仓不会因为未检出 `third_party/paper_analysis_dataset` 而失败
- 子仓测试需要在子仓上下文中单独执行
- benchmark 协议、标注规范与网页标注工作流文档统一位于 `third_party/paper_analysis_dataset/docs/benchmarks/`

## arXiv 联网 e2e 约定

`tests/e2e/` 中的 arXiv 黄金路径默认真实访问 arXiv 官方 API。这是仓库当前的明确要求，不是可选检查。

- `quality local-ci` 默认运行联网 arXiv e2e
- 执行环境默认假设外网稳定可达
- arXiv e2e 的目标是验证真实订阅抓取、结构化产物写出，以及 CI HTML 对真实产物的消费链路
- 断言应尽量关注来源、数量下限、关键字段存在性和产物稳定性，避免依赖易漂移的固定标题
- 联网实现必须遵守 arXiv API 的单连接、低频请求约束

## Codex 自然语言 e2e 约定

除了直接调用 CLI 的 arXiv 黄金路径，本仓库还要求保留一条面向 Codex 的黑盒 e2e：

- 通过 `codex exec --json` 运行
- prompt 不直接点名 skill，不手工给出 CLI 命令
- prompt 必须采用人类自然表达，只描述目标任务
- 用例目标是验证 Codex 在仓库内发现并使用 repo-local `.codex/skills/paper-analysis/SKILL.md`
- 至少覆盖一条最简单的 arXiv 联网报告任务

这条 e2e 的最低断言包括：

- 事件流中出现对 `.codex/skills/paper-analysis/SKILL.md` 的读取
- 事件流中成功执行 `py -m paper_analysis.cli.main arxiv report --source-mode subscription-api --subscription-date ...`
- `artifacts/e2e/arxiv/latest/summary.md`、`result.json`、`result.csv`、`stdout.txt` 全部生成
- `result.json["source"] == "arXiv"`，且结果数量大于等于 1

执行环境约束：

- `quality local-ci` 默认运行这条 Codex 黑盒 e2e
- 执行环境默认假设已安装并登录 `codex` CLI
- 由于该用例验证的是 agent 完成真实软件任务的能力，而非 Codex 沙箱策略，因此允许测试入口使用 `--dangerously-bypass-approvals-and-sandbox`
- prompt 中禁止显式写出“请加载某个 skill”之类指令；验证点是 agent 自主发现 skill 并正确路由任务

## HTML 审核页

HTML 审核页会展示：

- 三大类点灯视图：`质量检查`、`单元测试`、`E2E 测试`
- 每个用例的通过 / 失败 / 未执行状态
- 每个用例的描述、失败判定说明、过程日志、结果日志
- 阶段级原始输出
- `conference` / `arXiv` 的 e2e 报告附件

如果某阶段失败，HTML 也应尽量生成，并把后续未执行用例标记为“未执行”。

用例标题规范：

- HTML 审核页中的用例标题默认取自 `unittest` 用例方法的 docstring；没有 docstring 时会退回到方法名生成标题
- `tests/e2e/` 中的用例必须提供中文 docstring 标题，确保人在 HTML 审核页里能一眼看懂“这个用例在验什么”
- `tests/e2e/` 中的用例标题必须以前缀分类标签开头，当前只允许三类：
  - `【顶会】`
  - `【arxiv】`
  - `【推荐】`
- 分类标签代表仓库核心能力，选择规则如下：
  - 顶会论文筛选、顶会报告、paperlists 真实链路相关用例使用 `【顶会】`
  - arXiv 抓取、订阅、Codex 驱动 arXiv 任务相关用例使用 `【arxiv】`
  - 推荐算法、评测接口、跨仓评测、推荐结果消费链路相关用例使用 `【推荐】`
- 标题应优先写成“非技术读者也能立即看懂”的白话中文，直接描述结果，不要求读者理解测试实现
- 标题应直接描述用户能理解的结果，不要保留 `golden path`、`hits real endpoint`、`annotate`、`report`、`CLI` 一类偏实现细节的表述，除非不写这些词就会丢失业务含义
- 优先写成“XX 可以正常 YY”或“XX 可用”这类句式，避免“验证……黄金路径……真实调用……”这类审计腔标题
- 如果标题里出现 API、CLI、endpoint、artifact、schema 等词，必须先问一句：不用这些术语，产品/业务视角下这条测试到底在证明什么
- 推荐格式：
  - `【arxiv】arXiv API 可以正常获取论文。`
  - `【推荐】主仓推荐算法评测接口可用。`
  - `【推荐】子仓评测流程可以正常调用主仓推荐接口并生成报告。`

## 失败输出格式

```text
[FAIL] stage=integration
summary: ...
next: run `py -m paper_analysis.cli.main quality integration`
artifact: artifacts/quality/integration-latest.txt
```

## 质量产物

```text
artifacts/quality/
  lint-latest.txt
  lint-cases-latest.json
  lint-repo_rules-latest.txt
  lint-ruff-latest.txt
  lint-mypy-latest.txt
  lint-quality_report-latest.txt
  unit-latest.txt
  unit-cases-latest.json
  integration-latest.txt
  integration-cases-latest.json
  e2e-latest.txt
  e2e-cases-latest.json
  local-ci-latest.html
```

其中：

- `*-latest.txt` 保留每个阶段的原始 stdout / stderr
- `*-cases-latest.json` 保留该阶段的逐用例结构化结果
- `lint-cases-latest.json` 会细分为仓库规范失败、`ruff` 失败、`mypy` 失败和治理告警四类子结果
- `local-ci-latest.html` 用于人工审核

## 状态判定约定

- 整体状态和点灯状态以真实测试结果为准
- 日志中的业务 `[FAIL]` 文案仅作为过程信息展示，不单独把用例或页面判为失败
- 负路径测试只要断言通过，就应显示为“通过”

## 测试分层

- `tests/unit/`：主仓共享领域模型、排序逻辑、报告写入等纯逻辑
- `tests/integration/`：CLI 与 pipeline 的跨层协作
- `tests/e2e/`：主仓顶会链路、arXiv 联网订阅链路、Codex 自然语言黑盒链路，以及审核页消费真实产物的链路
- `tests/e2e/`：还包含评测 API 的真实批量 `POST /v1/evaluation/annotate` 黄金路径，以及子仓真实调用该 API 的跨仓链路
- `third_party/paper_analysis_dataset/tests/`：benchmark 数据协议、AI 预标、双人标注合并、网页标注、数据门禁等子仓专属测试

## 评测 API e2e 约定

跨仓评测接口属于必须覆盖的真实 e2e 契约。

- 主仓 e2e 必须真实启动 `paper_analysis.api.evaluation_server`
- e2e 必须真实发送批量 `POST /v1/evaluation/annotate`
- 至少断言一次 200 响应、schema 合法、标签协议合法
- 响应中不得出现 `expected_label`、`ground_truth`、`split` 等评测数据泄露字段
- 至少保留一条跨仓 e2e：由 `third_party/paper_analysis_dataset` 的评测 CLI 真实调用主仓批量接口并生成脱敏报告

## A/B 脚手架跨仓最小 e2e 约定

当主仓开始落地论文筛选二分类 A/B 脚手架后，必须新增一条“最小真实交互集”跨仓 e2e，用来验证：

- 主仓 A/B 能力不会破坏现有 data 子仓评测框架
- 子仓真实资产可以驱动一次最小集评测
- e2e 报告中能直接看到算法指标，而不是只看到成功/失败状态

建议最小用例形态如下：

- 主仓真实启动 `paper_analysis.api.evaluation_server`
- 用显式 `--algorithm-version <ab-route-or-snapshot>` 启动服务，保留本次路线或快照标识
- 子仓真实执行：
  - `py -m paper_analysis_dataset.tools.evaluate_paper_filter_benchmark --base-url http://127.0.0.1:<port> --limit 55 --output-dir <child-output-dir>`
- 子仓评测 CLI 默认按批量协议工作，单次请求默认发送 50 条；当 `limit` 超过 50 时应自动拆成多批
- 输出目录建议放在：
  - `third_party/paper_analysis_dataset/artifacts/test-output/evaluation-ab-e2e-minimal/`

这条 e2e 的最低断言包括：

- 主仓服务真实收到子仓发起的评测请求，而不是只测本地假对象
- 子仓真实写出：
  - `report.json`
  - `summary.md`
  - `stdout.txt`
- `report.json["counts"]["evaluated_count"] >= 1`
- `report.json["overall"]` 中至少存在：
  - `macro_precision`
  - `macro_recall`
  - `macro_f1`
  - `micro_precision`
  - `micro_recall`
  - `micro_f1`
- `summary.md` 中必须能看到 `precision / recall / f1` 指标行
- 过程日志或附加 artifact 中必须保留本次服务启动使用的 `algorithm_version`
- `report.json` 与 `summary.md` 仍不得泄露 `paper_id`、`source_path`、`expected_label`、`ground_truth`、`split`

推荐在主仓 e2e 用例中额外保存这些 artifact，方便 HTML 审核页直接查看：

- 子仓 `report.json`
- 子仓 `summary.md`
- 子仓 `stdout.txt`
- 子仓 CLI `stdout/stderr`
- 主仓服务启动时的 `algorithm_version` 记录

当前主仓实现中，这条最小 e2e 默认使用：

- 子仓输出目录：`third_party/paper_analysis_dataset/artifacts/test-output/evaluation-ab-e2e-minimal/`
- 主仓附加 artifact：`service-launch.json`

最低断言保持不变：

- `report.json["overall"]` 必须包含 macro/micro precision、recall、f1
- `summary.md` 必须出现 `precision / recall / f1`
- `service-launch.json` 必须保留本次服务使用的 `algorithm_version`

如果主仓后续引入 A/B runner 的离线结果目录，这条跨仓最小 e2e 仍应继续依赖 data 子仓现有 `evaluate_paper_filter_benchmark` CLI，而不是改成只跑主仓内部模块。目标是确保“已有正式评测契约仍然可用”，不是另起一套只在主仓内部自洽的新检查。

## 后续演进

当环境允许安装更多依赖后，可以逐步切换到：

- `pytest`
- `ruff`
- `mypy`

切换时仍要保持：

- 统一 `quality local-ci` 入口不变
- 失败输出格式不变
- HTML 审核页产物路径不变
- 逐用例结构化产物契约不变
- 文档与 skill 同步更新
