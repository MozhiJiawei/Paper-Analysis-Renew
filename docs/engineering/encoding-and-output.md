# Encoding And Output

## 编码约定

- 所有代码、文档、JSON、Markdown、文本产物统一使用 UTF-8。
- 中文文本必须直接写入 UTF-8 文件，不依赖终端代码页猜测。

## 输出约定

报告统一写入：

```text
artifacts/e2e/<source>/latest/
  summary.md
  result.json
  stdout.txt
```

## 快照稳定性

- 字段顺序固定
- 阶段名固定
- 避免将时间戳、随机数等动态字段写入快照
