---
title: feat: Tune standalone email delivery capability
type: feat
status: completed
date: 2026-04-10
origin: docs/brainstorms/2026-04-10-arxiv-subscription-minimal-launch-requirements.md
---

# feat: Tune standalone email delivery capability

## Overview

这份计划把“邮件发送能力”从 arXiv 订阅最小上线主计划中拆出来，单独作为一个可独立调试、独立验证、独立回归的能力建设项。

目标不是先完成完整订阅闭环，而是先把“给 `lijiawei14@huawei.com` 稳定发出一封结构化邮件”这件事单独打通，并形成后续业务链路可直接复用的发信基础设施。

拆分后的责任边界是：

- 本计划只负责邮件配置加载、连接认证、正文渲染、发送结果记录、失败诊断和最小回归。
- arXiv 订阅最小上线计划只负责消费“已经调好的邮件发送能力”，不再把 SMTP 调试和通道验证混在主链路里。

## Problem Statement / Motivation

当前仓库具备：

- 基础报告落盘能力 [paper_analysis/services/report_writer.py](D:/Git_Repo/Paper-Analysis-New/paper_analysis/services/report_writer.py:15)
- Jinja2 模板渲染模式 [paper_analysis/services/ci_html_writer.py](D:/Git_Repo/Paper-Analysis-New/paper_analysis/services/ci_html_writer.py:82)
- 真实 arXiv 订阅输入能力 [paper_analysis/cli/arxiv.py](D:/Git_Repo/Paper-Analysis-New/paper_analysis/cli/arxiv.py:88)

但还完全缺少邮件发送相关实现：

- 没有 `email_sender` service
- 没有 SMTP 配置契约
- 没有邮件模板
- 没有“只调试发信能力”的独立入口
- 没有发信成功/失败的结构化测试

如果继续把这部分工作混在主闭环里，会同时面对三类问题：

1. 抓取、推荐、邮件、HTML 任意一步失败都难以快速归因。
2. 邮件通道问题会拖慢主业务闭环推进。
3. 后续任何需要发邮件的能力都无法复用一个稳定基础设施。

## Proposed Solution

先落一个“与业务内容弱耦合”的独立邮件发送能力，再把业务报告作为其输入。

### 方案摘要

1. 新增统一邮件配置模型与加载逻辑，优先从环境变量或用户私有配置读取，不在仓库存放真实凭据。
2. 新增 `paper_analysis/services/email_sender.py`，封装 SMTP 连接、认证、发送、超时和错误翻译。
3. 新增最小邮件载荷模型，例如 `EmailMessagePayload`，让发信 service 不依赖 arXiv 领域对象。
4. 新增一个独立调试入口，支持发送测试邮件到 `lijiawei14@huawei.com`，用于单独验证通道是否可用。
5. 新增集成测试与可选手工 smoke test，确认发信能力“能配置、能发送、能失败得清楚”。

### 默认实现决策

- 协议：
  首版默认使用 SMTP over TLS / STARTTLS 适配器，不先引入厂商专有 API。
- 配置来源：
  优先读取环境变量；如需本地文件，使用用户私有目录配置，不写入仓库。
- 最小配置集合：
  `SMTP_HOST`、`SMTP_PORT`、`SMTP_USERNAME`、`SMTP_PASSWORD`、`SMTP_FROM`、`SMTP_TO`
- 发信策略：
  首版同步发送，不做队列、异步 worker 或消息总线。
- 失败策略：
  连接失败、认证失败、超时、收件人拒收都转成结构化错误；首版不做自动重试，只记录失败原因。
- 模板策略：
  邮件正文模板与 HTML 模板解耦，但都应支持消费统一结构化数据，以便后续业务复用。

## Technical Considerations

- 模块设计
  - 新增 `paper_analysis/services/email_sender.py`
  - 新增 `paper_analysis/domain/email_delivery.py` 或等价轻量模型
  - 可选新增 `paper_analysis/cli/email.py`，或在现有稳定入口下增加最小测试入口
- 配置边界
  - 不把真实 SMTP 凭据写入 `paper_analysis/config/`
  - 如需模板文件，可新增只含字段说明的示例配置文档
- 编码
  - 邮件主题和正文都必须显式使用 UTF-8
  - 中文正文、统计信息和无推荐提示要保证邮箱客户端可读
- 错误语义
  - 延续现有 `CliInputError` / 结构化失败输出规范
  - 区分“配置缺失”“连接失败”“认证失败”“发送失败”四类高频错误
- 模板复用
  - 可沿用 Jinja2 作为渲染技术，保持与现有 HTML 渲染栈一致 [paper_analysis/services/ci_html_writer.py](D:/Git_Repo/Paper-Analysis-New/paper_analysis/services/ci_html_writer.py:112)

## System-Wide Impact

- **Interaction graph**: 调试命令或业务命令先构造邮件载荷；邮件 service 加载 SMTP 配置；建立连接并认证；把主题和正文编码为 UTF-8 MIME 消息；发送到 `lijiawei14@huawei.com`；返回结构化发送结果给 CLI 或上层业务。
- **Error propagation**: 配置缺失在加载阶段失败；连接/认证/发送问题在 service 层翻译为稳定错误；CLI 只负责把这些错误渲染成用户可诊断的失败输出。
- **State lifecycle risks**: 发送邮件是外部副作用。必须至少记录一次发送尝试的时间、目标地址、结果状态和失败摘要，避免“到底发没发出去”不可追踪。
- **API surface parity**: 未来 arXiv 订阅、质量报告通知或其他邮件功能都应复用同一发信 service，而不是各自直接使用 `smtplib`。
- **Integration test scenarios**:
  - 配置完整时可成功构造 MIME 消息并调用 SMTP client
  - 配置缺失时给出结构化失败
  - 认证失败时给出结构化失败
  - 中文主题与正文使用 UTF-8 编码
  - 调试入口能向固定收件人发送一封最小测试邮件

## SpecFlow Analysis

### User Flow Overview

1. 开发者或调度任务先准备一份结构化邮件载荷。
2. CLI 或 service 读取 SMTP 配置。
3. 系统校验配置是否完整。
4. 系统建立 SMTP 连接并完成认证。
5. 系统渲染邮件主题和正文。
6. 系统发送邮件到 `lijiawei14@huawei.com`。
7. 终端输出成功信息或结构化失败摘要。

### Missing Elements & Gaps

- **独立调试入口缺失**: 目前无法只测邮件能力，不跑主业务。
  - 默认新增一个最小测试入口。
- **配置契约缺失**: 还没有明文规定哪些变量必填。
  - 默认固化最小 SMTP 环境变量集合。
- **发送结果记录缺失**: 当前没有运行元数据记录邮件是否真正发送成功。
  - 默认至少返回 `status/error_summary/recipient/sent_at`。

### Critical Questions Requiring Clarification

1. **Important**: 你的邮箱发信通道最终是企业 SMTP、163/QQ 邮箱 SMTP，还是其他供应商？
   - Why it matters: 会影响默认端口、TLS 模式和认证方式。
   - Default assumption: 先按标准 SMTP + 用户名密码认证抽象实现，具体供应商通过配置决定。
2. **Important**: 是否需要支持抄送/密送？
   - Why it matters: 会影响配置模型和 MIME 构造。
   - Default assumption: 首版只支持单收件人 `SMTP_TO`。
3. **Nice-to-have**: 是否需要保存 `.eml` 原文快照？
   - Why it matters: 对排查编码和模板问题很有帮助。
   - Default assumption: 建议保存到测试/运行产物目录，便于排查。

### Recommended Next Steps

- 先把 SMTP 配置契约写死，再写发送器，最后补调试入口。
- 先用 mock/假 SMTP server 跑通自动化，再做一次真实邮箱手工 smoke test。
- 把 MIME 生成与 SMTP 连接分开，测试会更稳定。

## Acceptance Criteria

- [ ] 新增统一邮件发送 service，且业务代码不直接调用底层 `smtplib`。
- [ ] 明确定义最小 SMTP 配置契约，并能从环境变量读取。
- [ ] 可以单独执行一条命令向 `lijiawei14@huawei.com` 发送测试邮件。
- [ ] 邮件主题与正文都能正确支持中文 UTF-8。
- [ ] 配置缺失、连接失败、认证失败、发送失败都返回结构化错误。
- [ ] 至少有一层自动化测试覆盖 MIME 生成和错误翻译。
- [ ] 至少保留一条可手工执行的真实邮箱 smoke test 路径。
- [ ] 邮件发送能力的使用说明被文档化，便于后续被 arXiv 订阅闭环直接复用。

## Success Metrics

- 仓库内可以不依赖 arXiv 业务链路，单独验证邮件发送是否可用。
- 当 SMTP 通道配置正确时，测试邮件能实际到达 `lijiawei14@huawei.com`。
- 当配置或通道异常时，开发者能在一次命令输出里看懂失败原因。
- 后续订阅闭环只需要传入结构化内容，不再重复处理 SMTP 细节。

## Dependencies & Risks

- **真实通道依赖**: 若没有可用 SMTP 账号或应用密码，这项能力无法在真实环境调通。
- **企业邮箱限制风险**: 某些企业邮箱可能限制 SMTP、端口或第三方登录，需要额外配置。
- **安全风险**: 若处理不当，凭据可能误写入日志或仓库；必须避免。
- **环境差异风险**: 本地调通不代表部署环境也能联通同样端口，需保留清晰诊断日志。

## Implementation Suggestions

### Phase 1: Config & Payload

- 新增 `paper_analysis/domain/email_delivery.py`
  - `EmailConfig`
  - `EmailMessagePayload`
  - `EmailSendResult`
- 新增配置加载器
  - 从环境变量读取
  - 校验必填字段

### Phase 2: Sender

- 新增 `paper_analysis/services/email_sender.py`
  - 构造 MIME 消息
  - UTF-8 编码主题和正文
  - 建立 SMTP 连接
  - 执行认证与发送
  - 翻译底层异常

### Phase 3: CLI, Tests, Docs

- 新增独立调试入口
  - 例如 `py -m paper_analysis.cli.main email send-test`
  - 或等价稳定入口
- 新增测试
  - `tests/unit/test_email_sender.py`
  - `tests/integration/test_email_delivery_cli.py`
- 更新文档
  - `docs/agent-guide/command-surface.md`
  - `docs/engineering/extending-cli.md`
  - 必要时补充邮件配置说明文档

## Sources & References

- **Origin document:** `docs/brainstorms/2026-04-10-arxiv-subscription-minimal-launch-requirements.md`
- **Internal references**
  - [paper_analysis/cli/arxiv.py](D:/Git_Repo/Paper-Analysis-New/paper_analysis/cli/arxiv.py:88)
  - [paper_analysis/services/report_writer.py](D:/Git_Repo/Paper-Analysis-New/paper_analysis/services/report_writer.py:15)
  - [paper_analysis/services/ci_html_writer.py](D:/Git_Repo/Paper-Analysis-New/paper_analysis/services/ci_html_writer.py:82)
- **Related work**
  - [2026-04-10-001-feat-arxiv-subscription-minimal-launch-plan.md](D:/Git_Repo/Paper-Analysis-New/docs/plans/2026-04-10-001-feat-arxiv-subscription-minimal-launch-plan.md)
