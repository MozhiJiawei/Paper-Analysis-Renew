# Extending CLI

## 新增顶会来源

1. 优先扩展 `conference` 命名空间，不新增 `recommend`
2. 若接入真实来源，优先放在 `paper_analysis/sources/conference/`
3. 为来源补充最小可回归 fixture，建议放在 `tests/fixtures/`
4. 补齐 unit / integration / e2e 测试
5. 更新 skill、命令文档和 CLI `--help`

### paperlists 约定

- 子模块路径固定为 `third_party/paperlists`
- 初始化命令：
  - `git submodule update --init --recursive`
- 新增会议适配时：
  - 在 `paperlists_loader.py` 增加会议别名和展示名
  - 在 `paperlists_parser.py` 扩展字段映射和 accepted 判定
  - 为该会议补充 fixture 和回归测试

## 新增 arXiv 来源或规则

1. 优先扩展 `arxiv` 命名空间，不新增 `recommend`
2. 若只是调整共享偏好逻辑，优先修改共享排序 / 偏好模型
3. 若存在 arXiv 特有行为，再扩展 `ArxivPipeline`
4. 真实 arXiv 来源优先放在 `paper_analysis/sources/arxiv/`
5. 若接入订阅 API：
  - 在 source 层封装查询构造、请求执行、Atom 解析
  - 在 pipeline 层统一衔接共享偏好筛选，不绕开 `PreferenceRanker`
  - 在 CLI 层只负责参数校验和结构化失败输出
  - 维持单连接、低频请求，遵守 arXiv API 限流
6. 补充回归测试：
  - unit：日期解析、查询构造、Atom 解析
  - integration：pipeline/source mode 调度、共享筛选语义、结构化失败
  - e2e：至少一条黄金路径真实访问 arXiv API，且默认纳入 `quality local-ci`
7. 更新相关文档与 CLI `--help`

## 新增测试层级或门禁

1. 在 `paper_analysis/cli/quality.py` 注册阶段
2. 在 `scripts/quality/` 或 `tests/` 中补对应实现
3. 更新 `docs/engineering/testing-and-quality.md`
4. 如果新增或修改质量产物，同时更新 `docs/engineering/encoding-and-output.md`
5. 如果 HTML 审核页的展示契约变化，同时维护逐用例结构化产物契约
6. 如果新增联网 e2e，需在文档中明确其网络假设、执行入口和外部依赖边界

## 维护 skill

以下变化必须同步更新 `.codex/skills/paper-analysis/`：

- 命令面变化
- 工作流变化
- 文档入口变化
