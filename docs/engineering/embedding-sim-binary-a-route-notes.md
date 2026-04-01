---
title: embedding_similarity_binary A 路线实验记录
date: 2026-04-01
status: completed
---

# embedding_similarity_binary A 路线实验记录

## 目标

这条路线面向第一次 A/B 演练中的 A 方案，目标是：

- 只做 `positive / negative` 大类二分类
- 优先满足高召回
- 允许整体 accuracy 与 precision 低于更保守的版本

## 当前实现

- route: `embedding_similarity_binary`
- provider: Doubao
- embedding model: `doubao-embedding-vision-251215`
- 运行方式：
  - 文本输入通过 `DoubaoClient.embed_texts(...)`
  - 对 `doubao-embedding-vision-*` 自动走 multimodal embedding API
  - 客户端自动按批次拆分，避免单次 `input` 超过 256 条

当前决策方式保持为 recall-first：

- 先计算论文文本与 6 个正类原型的相似度
- 再计算与负类原型中心的相似度
- 若 `top_similarity >= 0.50` 且 `margin >= -0.01`，则判为 `positive`
- 否则判为 `negative`

当前版本尽量不叠加额外规则门禁，避免继续把正例压掉。

## 开发期观察

开发阶段只使用无标记论文：

- `D:\Git_Repo\Paper-Analysis-New\third_party\paperlists\`

观察结论：

- 更保守的版本能压误报，但会把真实 benchmark 中的正例大量压成 `negative`
- 放松到 recall-first 后，大类召回明显改善
- 这条路线当前更适合作为“高召回候选器”，而不是高 precision 的最终分类器

## 真实 benchmark 结果

全量 benchmark 通过子仓真实调用主仓评测 API 跑出，产物位于：

- `D:\Git_Repo\Paper-Analysis-New\third_party\paper_analysis_dataset\artifacts\test-output\evaluation-ab-e2e-embedding-route-full-v3\`

关键结果：

- `total_count = 750`
- `evaluated_count = 750`
- `request_error_count = 0`
- `protocol_error_count = 0`

大类 `positive / negative`：

- precision: `0.6186`
- recall: `0.9279`
- f1: `0.7423`

整体：

- overall accuracy: `0.2187`
- macro precision / recall / f1: `0.5606 / 0.5010 / 0.3698`
- micro precision / recall / f1: `0.6907 / 0.6907 / 0.6907`

## 当前判断

这条 A 路线已经达到“高召回二分类候选器”的阶段目标：

- 大类 recall 已超过 `0.9`
- precision 明显下降，但符合本轮 recall-first 目标
- 子类标签质量仍然偏弱，不应把它当成当前主胜负依据

如果继续演进，更合理的方向是：

- 保持这条路线做高召回召回器
- 在后续阶段增加更轻的二判层，而不是继续在本路线里堆规则
