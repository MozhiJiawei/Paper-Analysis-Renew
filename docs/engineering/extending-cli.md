# Extending CLI

## 新增顶会来源

1. 优先扩展 `conference` 命名空间，不新增 `recommend`
2. 若接入真实来源，优先放在 `paper_analysis/sources/conference/`
3. 为来源补充最小可回归夹具，建议放在 `tests/fixtures/`
4. 补齐 unit / integration / e2e 测试
5. 更新 skill、命令文档和 CLI `--help`

### paperlists 约定

- 子模块路径固定为 `third_party/paperlists`
- 初始化命令：
  - `git submodule update --init --recursive`
- 新增会议适配时：
  - 在 `paperlists_loader.py` 增加会议别名和展示名
  - 在 `paperlists_parser.py` 扩展字段映射或 accepted 判定
  - 为该会议补充 fixture 和回归测试

## 新增 arXiv 筛选规则

1. 优先修改共享偏好模型或排序逻辑
2. 只有存在 arXiv 特有行为时，再扩展 `ArxivPipeline`
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
