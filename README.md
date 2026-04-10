# Paper-Analysis-New

一个面向 Codex / Agent 的论文筛选基础仓库。

当前聚焦两条业务链路：

1. 从顶会论文集合中筛选论文
2. 从 arXiv 每日更新中筛选论文

“推荐”不是独立命名空间，而是两条链路共享的内部阶段能力。

## 当前能力

- 统一 CLI：`py -m paper_analysis.cli.main`
- 顶会命名空间：`conference`
- arXiv 命名空间：`arxiv`
- 质量门禁入口：`quality local-ci`
- SMTP 测试邮件入口：`quality send-test-email`
- 评测 API 服务：`py -m paper_analysis.api.evaluation_server`
- 顶会真实数据源：`third_party/paperlists` 子模块
- CI HTML 审核页：`artifacts/quality/local-ci-latest.html`
- HTML 模板渲染：`Jinja2`

## 快速开始

查看帮助：

```powershell
py -m paper_analysis.cli.main --help
```

初始化 `paperlists` 子模块：

```powershell
git submodule update --init --recursive
```

运行顶会真实数据报告：

```powershell
py -m paper_analysis.cli.main conference report --venue iclr --year 2025
```

运行 arXiv 报告：

```powershell
py -m paper_analysis.cli.main arxiv report
```

运行本地质量门禁：

```powershell
py -m paper_analysis.cli.main quality local-ci
```

发送 SMTP 测试邮件：

```powershell
py -m paper_analysis.cli.main quality send-test-email
```

启动本地评测 API：

```powershell
py -m paper_analysis.api.evaluation_server --port 8765
```

执行完成后，可直接打开：

```text
artifacts/quality/local-ci-latest.html
```

该页面会汇总测试阶段状态、执行输出，以及 `conference` / `arxiv` 的 e2e 推荐报告。

测试邮件命令会把发送结果和 `.eml` 快照写到：

```text
artifacts/email/send-test-latest/
```

## 文档入口

- `AGENTS.md`
- `docs/agent-guide/quickstart.md`
- `docs/agent-guide/command-surface.md`
- `docs/engineering/testing-and-quality.md`
- `docs/engineering/encoding-and-output.md`
- `docs/engineering/extending-cli.md`

## 说明

当前实现优先保证：

- 中文输出可读
- UTF-8 编码一致
- CLI 与文档对齐
- 在不依赖第三方 Python 包的环境中也能跑通基础验证
- 主仓与数据集子仓可仅通过 HTTP API 进行评测交互
