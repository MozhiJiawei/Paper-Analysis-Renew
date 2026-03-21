---
title: "稳定 quality local-ci HTML 报告的逐用例契约与可扩展展示"
category: "integration-issues"
date: 2026-03-20
tags:
  - python
  - quality-local-ci
  - html-report
  - unittest
  - ui
  - utf-8
  - local-links
  - case-awareness
  - status-semantics
---

# 稳定 quality local-ci HTML 报告的逐用例契约与可扩展展示

## 问题

在 `quality local-ci` 已经能生成 HTML 审核页之后，报告逐渐暴露出一组跨层问题：

1. 页面最初只按阶段汇总，拿不到稳定的逐用例数据，无法支撑“按用例点灯”。
2. 原始日志里出现 `[FAIL]` 时，人工会误以为测试失败，但很多集成测试本身是在验证“结构化失败输出”，测试其实是通过的。
3. E2E 回归测试一度会覆盖真实的 `artifacts/quality/local-ci-latest.html`，导致人打开的不是正式报告而是测试专用页面。
4. 页面使用大方块式用例展示，少量用例还能看，扩到 100~200 个时会明显失去可浏览性。
5. 单元测试和集成测试大量暴露英文方法名，和 E2E、质量检查的中文说明风格不一致。

这些问题叠加后，HTML 审核页虽然“能打开”，但既不可靠，也不适合作为大规模测试集合的人工审查入口。

## 现象

可直接观察到的症状包括：

- 页面会把阶段输出和测试真值混在一起，人工看到 `[FAIL]` 文案时容易误判整体失败。
- “单元测试”区一度出现空白，本质原因是测试产物污染了真实报告，而不是没有单元测试数据。
- 用例详情卡片过大，页签式大方块占地太多，页面拉得很长。
- 关联产物和测试脚本无法从 HTML 直接跳转本地文件。
- 单元测试和集成测试的标题、描述里会出现英文方法名，如 `test_build_subprocess_env_forces_utf8`。

## 根因

根因不是单一的模板问题，而是 HTML 报告链路里缺少“逐用例结构化契约”：

- `paper_analysis/cli/quality.py` 最初只收集阶段级结果，没有逐用例 JSON，模板只能消费整段 stdout。
- HTML 之前没有稳定的数据模型去表达：
  - 用例标题
  - 用例描述
  - 失败判定
  - 过程日志
  - 结果日志
  - 测试脚本链接
  - 关联产物链接
- 状态真值如果依赖日志关键词，就会和负路径测试天然冲突，因为“日志里的失败”不等于“测试失败”。
- 测试没有把展示型产物隔离到 `artifacts/test-output/...`，因此真实报告路径会被回归测试污染。
- 模板最初按“大卡片一条条展开”的思路组织页面，没有把“少量展示信息”和“详细信息”解耦，所以无法扩展到大集合。

## 解决方案

这次修复不是只改模板，而是把 `quality local-ci` 的 HTML 视图改成“逐用例结构化渲染”。

### 1. 引入逐用例结构化产物

新增逐阶段的 case JSON 契约：

```text
artifacts/quality/
  <stage>-latest.txt
  <stage>-cases-latest.json
  local-ci-latest.html
```

其中 `*-cases-latest.json` 记录每个用例的：

- `status`
- `title`
- `description`
- `failure_check`
- `process_log`
- `result_log`
- `script_path`
- `artifact_paths`

核心实现落在：

- `paper_analysis/services/quality_case_support.py`
- `scripts/quality/run_unittest_stage.py`
- `paper_analysis/cli/quality.py`

这让模板不再需要猜测 stdout，而是直接消费稳定视图模型。

### 2. 明确状态真值规则

HTML 页面的整体状态、分类状态和用例状态一律以真实测试结果为准，而不是看日志中是否出现 `[FAIL]`。

规则被固化为：

- `[FAIL]` 出现在结果日志里时，只说明“被测系统输出了失败语义”
- 如果测试断言通过，则该测试用例状态仍然是“通过”
- 阶段状态来自阶段执行结果
- 用例状态来自 unittest 结果对象或阶段回退记录

这避免了把“负路径验证成功”误显示成“报告失败”。

### 3. 隔离测试产物，防止污染真实报告

展示相关测试不再写真实的 `artifacts/quality/local-ci-latest.html`，而是落到：

```text
artifacts/test-output/...
```

例如 E2E 里验证 HTML 消费真实产物的测试，改为写入测试专用目录，而不是覆盖正式报告。

这解决了“单元测试区域看起来为空，实际是被测试页面替换”的问题。

### 4. 中文优先的用例标题与描述

逐用例标题和描述改为中文优先：

- 优先使用测试的 docstring
- 其次使用显式元数据
- 最后才回退到可读的中文句式

对应做法包括：

- 为 `tests/unit/`、`tests/integration/`、`tests/e2e/` 的关键测试补中文 docstring
- E2E 用例补充更完整的场景说明和失败判定
- 质量检查保持中文描述与阶段说明一致

这样页面里看到的是“验证排序逻辑优先保留命中主题与机构偏好的论文”，而不是英文方法名。

### 5. 把展示结构改成适合大列表的紧凑模式

最终页面保留三个大类大框：

- `质量检查`
- `单元测试`
- `E2E 测试`

但每个大类内部改成：

1. 紧凑列表
2. 搜索框
3. 状态筛选：`全部 / 失败 / 未执行 / 通过`
4. 单一详情区
5. 失败优先排序

也就是：

- 列表只负责快速定位
- 详情区只显示当前选中的一个用例
- 不再让每个用例都是一个大卡片

这让 100~200 个用例仍然可浏览，默认先看异常项，再按需查看通过项。

### 6. 本地文件链接直接从页面打开

在 writer 层统一序列化本地文件链接，模板只负责渲染：

- 关联产物链接
- 测试脚本链接

链接格式使用本地 `file:///...` URI，用户可以直接从 HTML 打开对应测试脚本或产物文件。

## 关键实现位置

- `paper_analysis/cli/quality.py`
- `paper_analysis/services/quality_case_support.py`
- `scripts/quality/run_unittest_stage.py`
- `paper_analysis/services/ci_html_writer.py`
- `paper_analysis/templates/ci_report.html.j2`

## 验证

这次修复通过以下方式验证：

- `py -m unittest tests.unit.test_ci_html_writer`
- `py -m unittest tests.integration.test_quality_html`
- `py -m unittest tests.e2e.test_golden_paths`
- `py -m paper_analysis.cli.main quality unit`
- `py -m paper_analysis.cli.main quality integration`
- `py -m paper_analysis.cli.main quality e2e`
- `py -m paper_analysis.cli.main quality local-ci`

重点回归点包括：

- 逐用例结构化 JSON 会稳定生成
- HTML 中的本地脚本链接和产物链接存在
- 日志中的 `[FAIL]` 不会把通过用例误判为失败
- 非法或缺失的 `result.json` 仍会生成 HTML，并显示正确状态
- 测试不会再覆盖真实 `local-ci-latest.html`
- 大类内的默认活动项和排序符合“失败优先”的约定

## 预防策略

### 1. 让模板只消费结构化数据

以后只要 HTML 需要新增展示能力，优先先扩展 writer/view-model，不要在模板里解析 stdout、拼路径或推导状态。

### 2. 把状态真值规则写成固定契约

- 状态来自测试结果，不来自日志关键词
- 负路径测试只要断言通过，就必须显示为“通过”
- 日志只是证据，不是状态源

### 3. 所有展示型测试都使用隔离产物目录

凡是会写 HTML、case JSON、报告附件的测试，都应该写到 `artifacts/test-output/...` 或临时目录，禁止写真实人工审核产物。

### 4. UI 默认按“异常优先”设计

面向人工审核的大列表页面，默认应该：

- 失败优先
- 可搜索
- 可筛选
- 单详情区

而不是把所有成功项都完整展开。

### 5. 中文展示是公共接口的一部分

如果页面面向中文审阅者，测试 docstring、阶段说明、页面文案都应视为“对外可见接口”，和功能逻辑一样需要维护。

## 建议测试清单

后续继续演进 HTML 审核页时，建议至少保留这些回归：

- 模板能渲染三大类与单详情区
- 搜索与筛选不会让详情区失去同步
- 失败优先排序稳定
- 本地链接可点击且路径正确
- case JSON 缺失时会正确回退到阶段级显示
- 中文 docstring 会优先进入标题和描述

## 相关文档

- `docs/engineering/testing-and-quality.md`
- `docs/engineering/encoding-and-output.md`
- `docs/engineering/extending-cli.md`
- `docs/solutions/integration-issues/cli-structured-failure-and-windows-utf8-compatibility.md`
- `docs/plans/2026-03-20-001-feat-add-ci-html-review-report-plan.md`

## 结论

这次问题表面上像是“HTML 展示不够好看”，但真正解决它，需要同时稳定：

- 质量阶段与 unittest 的集成边界
- HTML 对数据的消费契约
- 测试产物与正式产物的隔离
- 状态真值规则
- 大规模列表的审阅方式

把这些规则前置成结构化产物、明确语义和紧凑交互后，`quality local-ci` 的 HTML 审核页才真正从“能打开的页面”变成“可持续使用的审查工具”。
