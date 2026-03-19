# Testing And Quality

## 当前策略

当前仓库优先保证“零第三方依赖也能跑通基础门禁”。

因此基础实现采用：

- `unittest` 负责单元、集成、e2e 测试
- 自定义 `lint` 脚本检查 UTF-8、行尾空格、制表符和结尾换行
- 自定义 `typecheck` 脚本检查公开函数的类型注解边界

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

## 失败输出格式

```text
[FAIL] stage=integration
summary: ...
next: run `py -m paper_analysis.cli.main quality integration`
artifact: artifacts/quality/integration-latest.txt
```

## 测试分层

- `tests/unit/`：共享域模型、排序逻辑、报告写入等纯逻辑
- `tests/integration/`：CLI 与 pipeline 的跨层协作
- `tests/e2e/`：顶会与 arXiv 两条黄金路径

## 后续演进

当环境允许安装依赖后，可以把门禁平滑切换到：

- `pytest`
- `ruff`
- `mypy`

切换时仍要保持：

- 统一 `quality local-ci` 入口不变
- 失败输出格式不变
- 文档与 skill 同步更新
