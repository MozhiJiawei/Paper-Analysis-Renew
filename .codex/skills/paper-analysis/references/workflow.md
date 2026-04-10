# 工作流摘要

先做意图分流，再执行稳定 CLI：

1. 识别用户属于 `conference`、`arxiv`、`quality` 还是 `report`
2. 缺少关键参数时只追问必要信息
3. 参数齐全后执行现有命令
4. 输出终端摘要与报告产物

## 顶会筛选

1. 载入顶会样例或指定输入
2. 载入用户偏好
3. 通过共享偏好模型筛选与排序
4. 输出终端摘要与报告产物

对应命令：

```powershell
py -m paper_analysis.cli.main conference filter
py -m paper_analysis.cli.main conference report
```

## arXiv 日更筛选

1. 载入 arXiv 日更样例或指定输入
2. 载入用户偏好
3. 通过共享偏好模型筛选与排序
4. 输出终端摘要与报告产物

对应命令：

```powershell
py -m paper_analysis.cli.main arxiv daily-filter
py -m paper_analysis.cli.main arxiv report
```

## 质量门禁

```powershell
py -m paper_analysis.cli.main quality local-ci
```

执行顺序：

1. `lint`
2. `unit`
3. `integration`
4. `e2e`

`quality lint` 内部固定执行：

1. 仓库规范检查
2. `ruff`
3. `mypy`
4. 代码质量治理报告（仅告警）

## 邮件通道调试

```powershell
py -m paper_analysis.cli.main quality send-test-email
```

执行步骤：

1. 从环境变量读取 SMTP 配置
2. 校验必填字段
3. 构造 UTF-8 测试邮件
4. 发送到固定收件人并写出 `.eml` 与结果 JSON 产物

## 最近报告

```powershell
py -m paper_analysis.cli.main report --source conference
py -m paper_analysis.cli.main report --source arxiv
```
