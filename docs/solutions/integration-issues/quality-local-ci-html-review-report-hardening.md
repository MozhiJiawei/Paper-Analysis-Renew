---
title: "quality local-ci HTML 审核页的安全与稳定性修复"
category: "integration-issues"
date: 2026-03-20
tags:
  - python
  - cli
  - quality-gate
  - jinja2
  - html
  - security
  - reliability
  - testing
---

# quality local-ci HTML 审核页的安全与稳定性修复

## 问题

给 `quality local-ci` 增加面向人工审核的静态 HTML 报告后，新增链路虽然能产出页面，但在 review 中暴露出 4 个边界问题：

1. `ci_report.html.j2` 没有实际启用 Jinja2 autoescape，浏览器打开 `artifacts/quality/local-ci-latest.html` 时存在 XSS 风险。
2. e2e 的 `result.json` 只处理了“缺失”场景，没有处理“存在但损坏”的场景，HTML 审核页可能直接生成失败。
3. 状态标签映射在 Python 和模板里各维护了一份，后续容易漂移。
4. `quality` 的单阶段分发保留了不可达的 fallback，增加了冗余控制流。

这个问题的主线不是单纯的模板实现，而是 `quality local-ci`、Jinja2 渲染、结构化 artifact 和失败语义在同一条集成链路上的稳定性。

## 现象

当时可观察到的风险和症状包括：

- `paper_analysis/services/ci_html_writer.py` 使用 `select_autoescape(("html", "xml"))`，但模板文件名是 `ci_report.html.j2`，Jinja2 实际不会对它启用默认 HTML 转义。
- 报告里来自阶段输出、`summary.md`、`stdout.txt`、论文标题和 reasons 的内容，都可能被原样插入 HTML。
- 任一 `artifacts/e2e/<source>/latest/result.json` 如果被截断、写坏或为空，`quality local-ci` 在写 HTML 时会抛 `JSONDecodeError`，导致审核页缺失。
- e2e 状态标签在模板内联了一份映射，而 stage 状态标签已经在 Python 里计算，职责边界不一致。
- `handle_single_stage()` 仍然扫描 `QUALITY_STAGES` 并保留未知阶段 fallback，但 CLI 注册面根本不会把未知阶段传到这里。

## 根因

### 1. 把 autoescape 绑定到了文件后缀猜测

我们把模板命名成了 `ci_report.html.j2`，但环境配置只依赖：

```python
select_autoescape(("html", "xml"))
```

这会让 `.html` 命中 autoescape，却不会让 `.html.j2` 命中。结果是“给人类在浏览器里打开”的静态报告，实际上按未转义 HTML 渲染了外部输入。

### 2. 把“缺失文件”和“损坏文件”混成了一个问题

e2e artifact loader 只把 `result.json` 缺失视为可降级状态，却假设“文件存在就一定能解析”。这在结构化产物被中断写入时是不成立的。

### 3. Python 和模板之间的展示契约没有收敛

stage 状态 label 已经由 Python 侧准备，但 e2e 仍在模板里硬编码一套状态映射，导致相同概念在两层重复定义。

### 4. 入口分发保留了不可达路径

`quality` 的单阶段执行由 argparse 只暴露固定 stage 名称，但运行时代码仍保留“未知 stage”的 fallback，这不是必要的防御，而是多余分支。

## 调查过程

这次排查按四步推进：

1. 先验证 Jinja2 行为，确认 `select_autoescape(("html", "xml"))("ci_report.html.j2")` 返回 `False`。
2. 用带 `<script>` 和原始 HTML tag 的 summary / output 构造回归测试，确认页面会把它们原样渲染。
3. 手工构造截断的 `result.json`，确认 `quality local-ci` 会在生成 HTML 时抛 `JSONDecodeError`。
4. 对照 `register()` 和 `handle_single_stage()`，确认未知阶段 fallback 没有真实调用入口。

## 解决方案

### 1. 对 HTML 报告显式开启 autoescape

Jinja2 环境改为显式开启转义，而不是依赖模板文件名启发式：

```python
def _build_environment() -> Environment:
    return Environment(
        loader=FileSystemLoader(TEMPLATE_DIR),
        autoescape=True,
        trim_blocks=True,
        lstrip_blocks=True,
    )
```

这样 `title`、stage output、`summary.md`、`stdout.txt` 和论文 metadata 都按文本渲染，浏览器打开报告时不会执行输入内容里的 markup。

### 2. 对损坏的 `result.json` 做降级，不中断 HTML 生成

在 e2e artifact loader 中捕获 `json.JSONDecodeError`，把 section 标记为 `failed`，并继续生成整个 HTML：

```python
try:
    payload = json.loads(json_path.read_text(encoding="utf-8"))
except json.JSONDecodeError:
    return E2EReportSection(
        source=source,
        status="failed",
        summary_markdown=summary_markdown,
        stdout=stdout,
        count=0,
        papers=[],
        report_dir=str(report_dir),
        note="result.json 存在但无法解析，请检查对应 e2e 产物是否写入完整。",
    )
```

这保证了“尽量生成 HTML”的契约成立。即使结构化推荐结果坏掉，审核者仍能看到目录、summary 和 stdout。

### 3. 统一由 Python 提供状态标签

新增 e2e section 的 `status_label`，让模板只消费已准备好的展示字段：

```python
def _serialize_e2e_section(section: E2EReportSection) -> dict[str, object]:
    return {
        "source": section.source,
        "source_name": _source_name(section.source),
        "status": section.status,
        "status_label": section.status_label,
        "summary_markdown": section.summary_markdown,
        "stdout": section.stdout,
        "count": section.count,
        "papers": section.papers,
        "report_dir": section.report_dir,
        "note": section.note,
    }
```

模板侧收敛为：

```jinja2
<div class="pill status-{{ section.status }}">{{ section.status_label }}</div>
```

这也顺手去掉了模板里针对 `reasons is string` 的死代码分支。

### 4. 简化单阶段分发

`quality` 的单阶段执行不再线性扫描并保留不可达 fallback，而是直接从运行时 stage 列表生成映射：

```python
def _quality_stage_commands() -> dict[str, list[str]]:
    return dict(QUALITY_STAGES)


def handle_single_stage(args: Namespace) -> int:
    command = _quality_stage_commands()[args.stage_name]
    exit_code, _stage_result = _run_stage(args.stage_name, command)
    return exit_code
```

这样可以保留测试时对 `QUALITY_STAGES` 的替换能力，同时让可达路径更小、更清晰。

## 验证

本次修复通过以下方式验证：

- 单元测试：
  - `tests/unit/test_ci_html_writer.py`
  - 覆盖 XSS payload 被转义
  - 覆盖损坏 `result.json` 时页面仍能生成
- 集成测试：
  - `tests/integration/test_quality_html.py`
  - 覆盖成功、失败、跳过阶段和 malformed JSON 的 HTML 产出
- e2e 测试：
  - `tests/e2e/test_golden_paths.py`
  - 继续验证 HTML 报告可消费真实 `conference` / `arxiv` artifact
- 全量命令验证：

```powershell
py -m unittest tests.unit.test_ci_html_writer tests.integration.test_quality_html tests.e2e.test_golden_paths tests.integration.test_pipelines tests.integration.test_cli_help tests.unit.test_report_writer
py -m paper_analysis.cli.main quality local-ci
```

## 预防策略

后续在这个仓库里新增类似链路时，默认遵循以下规则：

1. 浏览器可打开的静态 HTML 报告一律按“不可信输入渲染”处理，显式启用 HTML escaping。
2. `Python` 负责准备数据契约，`Jinja2` 只负责展示；状态标签、默认说明和降级文案尽量不在模板里重复计算。
3. 结构化 artifact 至少区分 `missing`、`invalid`、`valid` 三种状态，不把“缺失”和“损坏”混成一种故障。
4. `quality local-ci` 这类门禁命令要坚持“失败时也尽量产出诊断页面”，而不是把审核页当成 happy path 的附属品。
5. CLI 单阶段入口优先用显式映射，不保留没有真实入口的 fallback。
6. 静态报告里出现的路径、stdout、summary、paper metadata 都应视为外部输入，不能假定内容安全或格式稳定。

## 建议测试清单

后续如果再扩 HTML 审核页，可优先补这些回归：

- `<script>`、`<img onerror=...>`、原始 tag 等 payload 的转义测试
- 缺失 `result.json`
- 损坏 `result.json`
- 某阶段失败后，后续阶段在 HTML 中显示为“未执行”
- 真实 `conference report` / `arxiv report` artifact 的端到端渲染
- 产物路径、编码、状态标签契约的稳定性测试

## 相关文档

- `docs/solutions/integration-issues/cli-structured-failure-and-windows-utf8-compatibility.md`
- `docs/engineering/testing-and-quality.md`
- `docs/engineering/encoding-and-output.md`
- `README.md`
- `docs/plans/2026-03-20-001-feat-add-ci-html-review-report-plan.md`

## 结论

这次问题表面上分散在模板、安全、artifact 读取和 CLI 分发四个点上，实际是同一个工程规律：只要一条质量门禁链路既要消费结构化产物、又要生成给人直接查看的静态页面，就必须把“转义策略、损坏降级、展示契约和失败语义”当成同一个边界问题来设计。

把这些规则收敛之后，`quality local-ci` 的 HTML 审核页才真正从“能生成”提升到“生成结果可安全打开、遇到坏数据也能稳定诊断”。
