# Testing And Quality

## 当前策略

当前仓库优先保证“零第三方测试依赖也能跑通基础门禁”。

因此基础实现采用：

- `unittest` 负责单元、集成、e2e 测试
- 自定义 `lint` 脚本检查 UTF-8、行尾空格、制表符和结尾换行
- 自定义 `typecheck` 脚本检查公开函数的类型注解边界
- `Jinja2` 负责静态 HTML 审核页模板渲染

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

执行完成后，除终端输出外，还会生成供人类审核的 HTML 汇总页：

```text
artifacts/quality/local-ci-latest.html
```

该页面会展示：

- 每个测试阶段的通过/失败状态
- 阶段说明与执行过程
- `conference` / `arxiv` e2e 推荐报告

如果某阶段失败，HTML 也应尽量生成，并把未执行阶段标记为“未执行”。

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
  typecheck-latest.txt
  unit-latest.txt
  integration-latest.txt
  e2e-latest.txt
  local-ci-latest.html
```

其中：

- `*-latest.txt` 用于保留每个阶段的原始执行输出
- `local-ci-latest.html` 用于人工审核

## 测试分层

- `tests/unit/`：共享领域模型、排序逻辑、报告写入等纯逻辑
- `tests/integration/`：CLI 与 pipeline 的跨层协作
- `tests/e2e/`：顶会与 arXiv 两条黄金路径，以及推荐报告展示链路

## 后续演进

当环境允许安装依赖后，可以把门禁平滑切换到：

- `pytest`
- `ruff`
- `mypy`

切换时仍要保持：

- 统一 `quality local-ci` 入口不变
- 失败输出格式不变
- HTML 审核页产物路径不变
- 文档与 skill 同步更新
