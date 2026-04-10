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
7. 如果命令面、自然语言路由或 skill 触发语义发生变化，同时刷新 Codex 黑盒 e2e 的 prompt 与断言
8. 如果新增或修改跨仓评测 API，同时维护主仓与子仓两侧的真实 e2e，至少覆盖一次真实 `POST /v1/evaluation/annotate`

## 新增运维 / 调试型命令

1. 优先复用现有 `quality` / `report` 命名空间，不新增新的顶层命名空间
2. 如果命令涉及外部副作用（如 SMTP、Webhook、文件投递）：
  - 必须返回结构化结果
  - 必须避免把密钥写入日志或仓库
  - 建议写出最小运行产物，便于排障
3. 补齐至少一条单元测试覆盖核心错误翻译
4. 补齐至少一条集成测试覆盖 CLI 帮助页或结构化失败输出
5. 同步更新 skill、命令文档和自然语言路由示例

### 静态质量职责边界

- `quality lint` 是唯一静态质量入口，不再保留独立 `quality typecheck`
- 仓库特有文本规则保留在 `scripts/quality/lint.py`
- Python 通用静态问题优先交给 `ruff`
- 真实类型检查优先交给 `mypy`
- 治理类榜单默认只告警，不阻断 `quality lint`

## 维护 skill

以下变化必须同步更新 `.codex/skills/paper-analysis/`：

- 命令面变化
- 工作流变化
- 文档入口变化
- 自然语言路由示例与默认追问规则变化

## 维护自然语言入口契约

任何新增命令、修改命令语义或调整默认参数时，都必须同步更新以下位置，保持单一真相：

- `.codex/skills/paper-analysis/SKILL.md`
- `.codex/skills/paper-analysis/references/natural-language-routing.md`
- `docs/agent-guide/quickstart.md`
- `docs/agent-guide/command-surface.md`
- CLI `--help`

如果自然语言请求只能映射到现有 `conference` / `arxiv` / `quality` / `report` 之一，就不要新增新的顶层命名空间。

如果修改影响了 Codex 通过自然语言发现并调用 skill 的路径，也必须同步更新 `tests/e2e/` 中的 Codex 黑盒 e2e。
