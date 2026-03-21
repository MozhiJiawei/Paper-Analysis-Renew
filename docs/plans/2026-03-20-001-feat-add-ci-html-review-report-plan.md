---
title: feat: Add CI HTML review report
type: feat
status: completed
date: 2026-03-20
---

# feat: Add CI HTML review report

## Summary

为 `quality local-ci` 增加一个面向人工审核的静态 HTML 汇总页，统一展示：

- 各测试阶段是否通过
- 阶段说明与执行过程
- `conference` / `arxiv` 两条 e2e 链路的推荐报告

最终实现选择：

- 保持 `quality local-ci` 为唯一统一入口
- 保持 `artifacts/e2e/<source>/latest/` 结构化报告契约不变
- 使用 `Jinja2` 模板渲染 HTML，避免继续堆积手写 HTML tag
- 不引入前端构建工具，不引入浏览器端运行时框架

## Key Changes

- `quality local-ci` 在执行每个阶段后收集结构化状态，并在成功或失败时都写出：
  - `artifacts/quality/local-ci-latest.html`
- HTML 页面继续复用既有产物：
  - `artifacts/quality/<stage>-latest.txt`
  - `artifacts/e2e/<source>/latest/result.json`
  - `artifacts/e2e/<source>/latest/summary.md`
  - `artifacts/e2e/<source>/latest/stdout.txt`
- HTML 生成器从 Python 大段字符串拼接改为：
  - Python 组装上下文
  - `Jinja2` 模板负责循环、条件渲染、折叠区域和表格结构
- 失败策略明确：
  - 某阶段失败时仍生成 HTML
  - 后续未执行阶段标记为“未执行”
  - 缺失 e2e 结构化产物时标记为“缺失”

## Public Interfaces / Dependencies

- CLI 命令面不变：
  - `quality local-ci`
  - `quality lint`
  - `quality typecheck`
  - `quality unit`
  - `quality integration`
  - `quality e2e`
- 输出契约新增但不替换：
  - `artifacts/quality/local-ci-latest.html`
- 运行时依赖新增：
  - `Jinja2>=3.1,<4`

## Test Plan

- 单元测试：
  - 模板渲染成功
  - 页面包含整体状态、阶段说明、e2e 推荐结果
  - 缺失 `result.json` 时正确显示“缺失”
- 集成测试：
  - `quality local-ci` 成功时生成 HTML
  - `quality local-ci` 失败时也生成 HTML
  - 失败后续阶段正确标记为“未执行”
- e2e 测试：
  - 基于真实 `conference report` / `arxiv report` 产物渲染 HTML
  - 页面中出现真实推荐论文标题与 e2e 区域
- 回归验证：
  - `py -m paper_analysis.cli.main quality local-ci` 全部通过

## Assumptions

- 允许为项目新增轻量 Python 运行时依赖 `Jinja2`
- 不新增 HTML 专用 CLI 子命令
- 不引入前端构建链
- 继续以 UTF-8、固定路径、静态可重复生成为约束
