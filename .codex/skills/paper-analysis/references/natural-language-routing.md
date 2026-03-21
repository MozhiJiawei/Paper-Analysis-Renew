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
  - “拉一下 2025-09/09-01 的 arXiv cs.AI 订阅”
- 优先命令：
  - `py -m paper_analysis.cli.main arxiv report --source-mode subscription-api --subscription-date 2025-09/09-01 --category cs.AI`
  - `py -m paper_analysis.cli.main arxiv daily-filter --source-mode subscription-api --subscription-date 2025-09/09-01 --category cs.AI`
- 必要追问：
  - 缺 `subscription-date` 时追问订阅日期
- 默认处理：
  - 未给分类时可省略 `--category`
  - 未给数量时使用 CLI 默认 `--max-results 10`

### 质量检查 / 回归验证

- 用户说：
  - “跑一下本地检查”
  - “帮我做一遍回归”
- 优先命令：
  - `py -m paper_analysis.cli.main quality local-ci`
- 必要追问：
  - 无。默认直接执行

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
