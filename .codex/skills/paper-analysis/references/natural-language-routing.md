# 自然语言路由

## 路由原则

- 只把请求映射到现有稳定入口：`conference`、`arxiv`、`quality`、`report`
- 不新增 `recommend` 命名空间
- 参数充足时直接执行
- 参数不足时只追问必要信息
- 默认用中文沟通，文本产物保持 UTF-8

## 意图到命令

### 顶会论文筛选

- 用户说：
  - “帮我筛 ICLR 2025 里符合我偏好的论文”
  - “看看 CVPR 2024 有哪些论文值得关注”
- 优先命令：
  - `py -m paper_analysis.cli.main conference filter --venue iclr --year 2025`
  - `py -m paper_analysis.cli.main conference report --venue cvpr --year 2024`
- 必要追问：
  - 缺 `venue` 时追问会议名
  - 缺 `year` 时追问年份

### arXiv 日更 / 订阅

- 用户说：
  - “帮我看今天的 arXiv AI 更新”
  - “拉一下 2026-05/05-23 的 arXiv cs.AI 订阅”
- 优先命令：
  - `py -m paper_analysis.cli.main arxiv report --subscription-date 2026-05/05-23 --category cs.AI`
  - `py -m paper_analysis.cli.main arxiv daily-filter --subscription-date 2026-05/05-23 --category cs.AI`
- 必要追问：
  - 缺 `subscription-date` 时追问订阅日期
- 默认处理：
  - 不主动补 `--source-mode subscription-api`；有 `--subscription-date` 时默认走 Gmail 订阅邮件
  - 未给分类时可省略 `--category`
  - 未给数量时使用 CLI 默认 `--max-results 10`
  - arXiv API 容易出现 429、长时间无响应或大分页不稳定，只有用户明确要求 API 排障时才显式传 `--source-mode subscription-api`

### arXiv 推荐质量审阅

- 用户说：
  - “帮我审一下今天 arXiv 有没有误推荐或漏推荐”
  - “用大模型挑战一下这次 arXiv 推荐效果”
- 优先命令：
  - `py -m paper_analysis.cli.main arxiv report --subscription-date 2026-05/05-23`
- 必要追问：
  - 缺 `subscription-date` 且无法从上下文确定时追问订阅日期
- 默认处理：
  - `arxiv report` 在订阅邮件模式下默认生成推荐报告和大模型蓝军审阅
  - 蓝军结论写回 `artifacts/e2e/arxiv/latest/summary.md` 与 `result.json`
  - 详细审阅产物写到 `artifacts/reviews/arxiv/latest/summary.md`、`result.json`、`stdout.txt`
  - 默认复用本次 Gmail 订阅邮件候选全集，不主动补 `--source-mode subscription-api`
  - 默认使用 OpenRouter `deepseek/deepseek-v4-pro`

### arXiv 数据集手动导入

- 用户说：
  - “把这天的 arXiv 推荐样本入数据集”
  - “确认后把 2026-05/05-23 的日更样本导入评测数据集”
- 优先命令：
  - `py -m paper_analysis.cli.main arxiv import-dataset --subscription-date 2026-05/05-23`
- 必要追问：
  - 缺 `subscription-date` 且无法从上下文确定时追问订阅日期
- 默认处理：
  - `arxiv report` 不默认入库
  - 入库必须通过 `arxiv import-dataset` 显式触发
  - 手动导入只读取同一个分日目录下的推荐报告和蓝军审阅产物；不存在时直接失败并提示先重跑 `arxiv report --subscription-date ... --fetch-all`
  - 手动导入会把推荐算法结论、蓝军结论和 ds-v4 边界负例写入数据集
  - 不主动补 `--source-mode subscription-api`

### 质量检查 / 回归验证

- 用户说：
  - “跑一下本地检查”
  - “帮我做一遍回归”
- 优先命令：
  - `py -m paper_analysis.cli.main quality local-ci`
- 必要追问：
  - 无。默认直接执行

### 邮件通道调试

- 用户说：
  - “帮我测试一下 QQ SMTP 能不能发邮件”
  - “给固定邮箱发一封测试邮件”
- 优先命令：
  - `py -m paper_analysis.cli.main quality send-test-email`
- 必要追问：
  - 无。默认从 `SMTP_HOST`、`SMTP_PORT`、`SMTP_USERNAME`、`SMTP_PASSWORD`、`SMTP_FROM`、`SMTP_TO` 读取配置
- 默认处理：
  - 保持单收件人模式
  - 不新增 `email` 顶层命名空间

### 查看最近报告

- 用户说：
  - “把最近的顶会报告给我看看”
  - “打开最近一次 arXiv 报告”
- 优先命令：
  - `py -m paper_analysis.cli.main report --source conference`
  - `py -m paper_analysis.cli.main report --source arxiv`
- 必要追问：
  - 缺来源时追问是 `conference` 还是 `arxiv`

## 禁止动作

- 不把“推荐”抽成新的 CLI 命名空间
- 不绕开 `conference` / `arxiv` 直接设计新的产品面
- 不在入口层跳过必需参数校验
