# Extending CLI

## 新增顶会来源

1. 在 `tests/fixtures/conference/` 增加稳定样例
2. 扩展 `ConferencePipeline`
3. 如需新动作，优先放在 `conference` 命名空间下
4. 补充 integration/e2e 测试
5. 更新 skill 与命令文档

## 新增 arXiv 筛选规则

1. 优先修改共享偏好模型或排序逻辑
2. 如确有 arXiv 特有行为，再扩展 `ArxivPipeline`
3. 补充回归测试
4. 更新相关文档

## 新增测试层级或门禁

1. 在 `paper_analysis/cli/quality.py` 注册阶段
2. 在 `scripts/quality/` 或 `tests/` 中补对应实现
3. 更新 `docs/engineering/testing-and-quality.md`

## 维护 skill

以下变化必须同步更新 `.codex/skills/paper-analysis/`：

- 命令面变化
- 工作流变化
- 文档入口变化
