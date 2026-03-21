# Encoding And Output

## 编码约定

- 所有代码、文档、JSON、Markdown、CSV、HTML、文本产物统一使用 UTF-8
- 中文文本必须直接写入 UTF-8 文件，不依赖终端代码页猜测
- “文件内容是 UTF-8” 与 “进程 stdout/stderr 也是 UTF-8” 是两个不同层次的约束，二者都必须显式保证
- CLI 入口默认会在启动时重设 `stdout` / `stderr` 为 UTF-8；凡是由 Python 再拉起 Python 子进程的链路，都应显式注入 `PYTHONUTF8=1` 与 `PYTHONIOENCODING=utf-8`

## 乱码排查顺序

当中文显示异常时，按下面顺序排查，而不是直接假设源码文本已损坏：

1. 先用 Python `read_text(encoding="utf-8")` 验证文件原文是否正常
2. 再检查当前进程的 `stdout` / `stderr` 编码是否被终端或管道改写
3. 再检查 Python 子进程是否带上了 `PYTHONUTF8=1` 与 `PYTHONIOENCODING=utf-8`
4. 最后再看 `artifacts/` 中的下游产物是否只是消费了上游的错误输出

## 输出约定

e2e 报告统一写入：

```text
artifacts/e2e/<source>/latest/
  summary.md
  result.json
  result.csv
  stdout.txt
```

质量门禁统一写入：

```text
artifacts/quality/
  <stage>-latest.txt
  <stage>-cases-latest.json
  local-ci-latest.html
```

其中：
- `<stage>-latest.txt` 保存阶段级原始输出
- `<stage>-cases-latest.json` 保存逐用例结构化结果，包括状态、用例描述、失败判定、过程日志、结果日志、关联产物
- `local-ci-latest.html` 为面向人工审核的汇总页，会复用 `artifacts/e2e/<source>/latest/` 下的结构化报告内容

HTML 渲染实现使用 `Jinja2` 模板，而不是继续扩张 Python 内联 HTML 字符串。

## 快照稳定性

- 字段顺序固定
- 产物文件名固定
- 避免把时间戳、随机数等动态字段直接写入快照
- 如果需要随机抽样，必须允许固定 seed 保证可重放
- HTML 报告优先基于结构化 JSON 生成，避免依赖脆弱的终端文本解析
