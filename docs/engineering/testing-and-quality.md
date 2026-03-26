# Testing And Quality

## 当前策略

当前仓库的质量门禁以 `unittest` 和自定义质量脚本为基础，统一通过稳定的 CLI 入口执行。

- `unittest` 负责 unit、integration、e2e 测试
- `lint` 脚本检查 UTF-8、行尾空格、制表符、文件结尾换行，以及常见乱码片段（支持通过 `lint: allow-mojibake` 显式豁免）
- `typecheck` 脚本检查公开函数的类型注解边界
- `Jinja2` 负责静态 HTML 审核页渲染

## 统一入口

```powershell
py -m paper_analysis.cli.main quality local-ci
```

执行顺序：

1. `lint`
2. `typecheck`
3. `unit`
4. `integration`
5. `e2e`

执行完成后，除了终端输出，还会生成供人工审核的 HTML 汇总页：

```text
artifacts/quality/local-ci-latest.html
```

补充约束：

- 需要通过 `subprocess.run(..., capture_output=True)` 抓取 CLI 输出的测试，优先依赖 CLI 自身的 UTF-8 标准输出配置，而不是把编码稳定性完全外包给调用方环境
- 如果测试或脚本继续拉起 Python 子进程，仍应显式传递 `PYTHONUTF8=1` 与 `PYTHONIOENCODING=utf-8`，避免 Windows 管道输出退回本地代码页

## 主仓与子仓边界

- 主仓 `quality local-ci` 只覆盖主仓能力：`conference`、`arxiv`、`report` 及其非数据集相关检查
- benchmark / annotation / 网页标注 / 评测数据 / 相关测试位于 `third_party/paper_analysis_dataset`
- 主仓不会因为未检出 `third_party/paper_analysis_dataset` 而失败
- 子仓测试需要在子仓上下文中单独执行

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
  typecheck-latest.txt
  typecheck-cases-latest.json
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
- `local-ci-latest.html` 用于人工审核

## 状态判定约定

- 整体状态和点灯状态以真实测试结果为准
- 日志中的业务 `[FAIL]` 文案仅作为过程信息展示，不单独把用例或页面判为失败
- 负路径测试只要断言通过，就应显示为“通过”

## 测试分层

- `tests/unit/`：主仓共享领域模型、排序逻辑、报告写入等纯逻辑
- `tests/integration/`：CLI 与 pipeline 的跨层协作
- `tests/e2e/`：主仓顶会链路、arXiv 联网订阅链路、Codex 自然语言黑盒链路，以及审核页消费真实产物的链路
- `third_party/paper_analysis_dataset/tests/`：benchmark 数据协议、AI 预标、双人标注合并、网页标注、数据门禁等子仓专属测试

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
