---
title: "稳定 CLI 失败语义与 Windows UTF-8 兼容性"
category: "integration-issues"
date: 2026-03-19
tags:
  - python
  - cli
  - windows
  - encoding
  - quality-gate
  - repository-hygiene
---

# 稳定 CLI 失败语义与 Windows UTF-8 兼容性

## 问题

在项目第一版 Agent-first Python CLI 骨架落地后，出现了三个相关的可靠性问题：

1. `conference` 和 `arxiv` 在输入文件缺失、JSON 非法或结构不匹配时会直接抛 Python traceback。
2. `quality` 在 Windows 下执行失败阶段时，子进程输出编码不稳定，失败 artifact 可能出现乱码。
3. `__pycache__`、`.pyc` 和运行产物会污染工作区，增加 review 噪音和误提交风险。

这些问题都发生在“命令边界”和“运行时集成边界”上，而不是业务 happy path 本身。

## 现象

可直接复现的症状包括：

- 运行 `py -m paper_analysis.cli.main conference filter --input missing.json` 时，命令直接抛出 `FileNotFoundError` traceback，而不是输出结构化失败信息。
- `quality local-ci` 虽然在成功路径能通过，但失败路径生成的 `artifacts/quality/*-latest.txt` 曾出现中文乱码，说明父进程按 UTF-8 解码并不足以保证可读性。
- 在测试和脚本运行后，工作区会出现 `__pycache__`、`.pyc` 和 `artifacts/` 目录，容易被误加入提交。

## 根因

根因是多个边界层都缺少“稳定接口语义”的封装：

- `paper_analysis/shared/sample_loader.py` 直接做文件读取和 JSON 解析，没有把 `FileNotFoundError`、`JSONDecodeError` 或 schema 错误转换为 CLI 可消费的异常。
- `paper_analysis/cli/conference.py` 和 `paper_analysis/cli/arxiv.py` 直接调用 pipeline，没有在入口层把底层异常翻译成统一失败输出。
- `paper_analysis/cli/quality.py` 只在父进程里用 UTF-8 捕获子进程输出，但没有强制子进程也按 UTF-8 写出，Windows 下因此脆弱。
- 仓库缺少对 Python 缓存文件和运行产物的忽略规则，导致生成型文件自然流入工作区。

## 解决方案

这次修复采用了“小而明确的边界层”方案。

### 1. 统一 CLI 输入错误模型

新增 `paper_analysis/cli/common.py`，集中放置：

- `CliInputError`
- `read_json_file()`
- `print_cli_error()`

其中 `read_json_file()` 负责把底层文件/JSON 错误统一翻译成用户可理解的错误消息，`print_cli_error()` 负责输出稳定的失败格式：

```text
[FAIL] scope=conference.filter
summary: 输入文件不存在：missing.json
next: 检查 --input/--preferences 是否存在且为 UTF-8 JSON
```

### 2. 在共享加载层校验 JSON 结构

`paper_analysis/shared/sample_loader.py` 不再假设输入天然正确，而是显式校验：

- 论文输入必须是 JSON 数组
- 偏好输入必须是 JSON 对象
- 结构错误会转成 `CliInputError`

关键模式如下：

```python
raw = read_json_file(path)
if not isinstance(raw, list):
    raise CliInputError(f"论文输入必须是 JSON 数组：{path}")
```

### 3. 在 CLI 边界捕获并渲染失败语义

`paper_analysis/cli/conference.py` 和 `paper_analysis/cli/arxiv.py` 在调用 pipeline 时统一捕获 `CliInputError`，并给出 next-step 提示，而不是让 traceback 泄漏到终端。

模式如下：

```python
try:
    papers, _preferences = ConferencePipeline().run(args.input, args.preferences)
except CliInputError as exc:
    return print_cli_error(
        scope="conference.filter",
        message=str(exc),
        next_step="检查 --input/--preferences 是否存在且为 UTF-8 JSON",
    )
```

### 4. 强制质量子进程使用 UTF-8

`paper_analysis/cli/quality.py` 新增 `build_subprocess_env()`，在所有质量阶段子进程运行前注入：

```python
env["PYTHONUTF8"] = "1"
env["PYTHONIOENCODING"] = "utf-8"
```

这样父子进程都以 UTF-8 作为显式契约，Windows 下的失败输出和保存到 artifact 的文本会稳定得多。

### 5. 增加仓库 hygiene 规则

新增 `.gitignore`，忽略：

- `__pycache__/`
- `*.py[cod]`
- `artifacts/`

并清理了已有缓存文件和运行产物，避免后续误提交。

## 验证

本次修复通过以下方式验证：

- 负路径验证：`conference filter --input missing.json` 现在返回结构化失败输出，不再出现 traceback。
- 单元验证：`tests/unit/test_filtering.py` 断言质量子进程环境会强制注入 UTF-8。
- 集成验证：`tests/integration/test_pipelines.py` 覆盖缺失输入文件的 CLI 失败路径。
- 端到端验证：`tests/e2e/test_golden_paths.py` 继续覆盖 `conference report` 和 `arxiv report` 的成功路径。
- 全量门禁验证：`py -m paper_analysis.cli.main quality local-ci` 通过。

## 预防策略

后续在这个仓库里新增 CLI 能力时，默认遵循以下规则：

1. 所有外部输入都先经过共享加载层，再进入 pipeline。
2. 低层异常不直接暴露给终端，必须在 CLI 边界转成稳定失败输出。
3. 只要子进程会输出诊断文本，就把 UTF-8 当成显式运行时契约处理，而不是依赖系统默认编码。
4. 生成型文件默认不纳入版本控制；一旦出现新的缓存目录或运行产物，立即更新 `.gitignore`。
5. 命令的“happy path”和“failure path”都属于公共接口，需要一起测试和文档化。

## 建议测试清单

后续可继续补强的回归项：

- 缺失输入文件
- 非法 JSON
- schema 不匹配的 JSON
- 某个质量阶段故意失败时，artifact 中的中文文本可读且无乱码
- 工作区检查，确保不会跟踪 `__pycache__`、`.pyc` 或 `artifacts/`

## 相关文档

- `docs/engineering/testing-and-quality.md`
- `docs/engineering/encoding-and-output.md`
- `docs/agent-guide/command-surface.md`
- `README.md`
- `AGENTS.md`
- `docs/plans/2026-03-19-001-feat-agent-first-engineering-foundation-plan.md`

## 结论

这次问题表面上看是三个分散的小故障，实际上是同一个工程规律：CLI 和运行时边界如果不主动定义“失败语义、编码语义和产物边界”，系统在 happy path 之外就会变得不稳定。

把这些边界规则前置成共享模式后，后续再扩展 `conference`、`arxiv` 或新的质量阶段时，能明显减少重复踩坑。
