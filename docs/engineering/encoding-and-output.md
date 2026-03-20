# Encoding And Output

## 编码约定

- 所有代码、文档、JSON、Markdown、CSV、HTML、文本产物统一使用 UTF-8
- 中文文本必须直接写入 UTF-8 文件，不依赖终端代码页猜测

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
