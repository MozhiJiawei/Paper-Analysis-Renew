# A/B 脚手架与 Worktree 协作约定

## 目标

主线先冻结“论文筛选第一阶段大类二分类”的共享脚手架，让后续路线在各自 worktree 中独立补真实算法实现，而不反复改共享 runner、报表和产物协议。

## main 分支承载范围

`main` 只接收共享底座：

- `paper_analysis/evaluation/ab_protocol.py`
- `paper_analysis/evaluation/route_registry.py`
- `paper_analysis/evaluation/ab_runner.py`
- `paper_analysis/evaluation/ab_reporter.py`
- `paper_analysis/evaluation/errors.py`
- `paper_analysis/evaluation/routes/*.py` 中的 stub 路线定义
- 与脚手架直接相关的测试、fixture、工程文档

`main` 不承载：

- 真实训练好的本地分类器
- 真实 embedding 索引或近邻检索实现
- 真实外部 API 判别逻辑
- 两阶段真实召回与裁决编排

## 路线占位约定

主线当前固定四条占位路线：

- `local_classifier_stub`
- `embedding_retriever_stub`
- `llm_judge_stub`
- `two_stage_stub`

每条路线必须稳定暴露：

- `route_name`
- `algorithm_version`
- `capability_type`
- `implementation_status`
- `prepare()`
- `predict_many()`

未实现路线通过 `RouteNotImplementedError` 进入统一 `stub` 状态，而不是把 traceback 直接暴露给 runner 使用方。

## Runner 产物协议

每次运行统一写入：

- `artifacts/evaluation-ab/<run_id>/manifest.json`
- `artifacts/evaluation-ab/<run_id>/summary.md`
- `artifacts/evaluation-ab/<run_id>/leaderboard.json`
- `artifacts/evaluation-ab/<run_id>/routes/<route_name>/status.json`
- `artifacts/evaluation-ab/<run_id>/routes/<route_name>/predictions.jsonl`
- `artifacts/evaluation-ab/<run_id>/routes/<route_name>/metrics.json`

状态语义固定为：

- `ready`: 路线成功执行并返回合法预测
- `stub`: 路线已注册，但仍是未实现占位
- `failed`: 路线执行失败或违反协议
- `skipped`: 路线存在，但本次运行被显式跳过

即使路线尚未实现，也必须写出 `status.json`、空 `predictions.jsonl` 与空 `metrics.json`，保证后续真实实现无需再改产物结构。

## Worktree 实施方式

后续真实路线开发建议按“一条路线一个 worktree”推进：

1. 从主线最新代码创建独立 worktree。
2. 只替换对应的 `routes/<route>.py` 实现和该路线确实需要的少量配置。
3. 不在路线 worktree 中改共享 runner、summary、leaderboard 或 manifest schema，除非先回到主线讨论共享协议变更。
4. 用假实现或真实实现验证该路线能从 `stub` 变为 `ready`，同时不影响其他路线的状态归一化。

## 与公开 API 的关系

离线 A/B 脚手架当前不接管 `POST /v1/evaluation/annotate` 的默认预测器。

现阶段要求只有两点：

- 离线脚手架与公开 API 在 `algorithm_version` 和 `positive/negative` 语义上保持兼容
- 公开 API 现有 schema 与跨仓 e2e 不回归

后续如果要切换默认公开算法，应在共享脚手架稳定后单独规划，而不是与脚手架落地耦合提交。
