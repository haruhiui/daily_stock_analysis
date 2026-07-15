# ExternalTool 扩展设计文档

> 状态：代码与离线验收完成，等待首次受保护环境 Action/邮件验收
> 说明：本目录定义设计和验收合同；各功能是否可用以完成定义和测试证据为准

## 文档索引

- [`SPEC.md`](SPEC.md)：DSA、ExternalTool、本地 UI、GitHub Actions 和邮件的职责边界与集成合同。
- [`SETUP.md`](SETUP.md)：本地 editable install、私有外部工具仓库只读授权、Action checkout 与验证步骤。
- [`TEST_PLAN.md`](TEST_PLAN.md)：引擎、适配层、DSA 后端、Web、报告、Action 和 fork 维护的测试门禁。
- [`FORK_WORKFLOW.md`](FORK_WORKFLOW.md)：将个人扩展提交以线性补丁栈 rebase 到最新 `upstream/main` 顶部的维护流程。
- ExternalTool 仓库中的 `docs/specs/dsa-extension.md`：适配层、可扩展研究方法、独立每日报告生成器，以及示例方法的规范性定义。

## 评审顺序

1. 先确认产品定位和两个仓库的所有权边界。
2. 再确认示例研究方法的初始化、聚合周期和阈值定义。
3. 确认本地配置与 Action 配置第一阶段不自动同步。
4. 确认安装方式、桌面打包范围和研究台导航。
5. 最后确认测试门禁和 fork/rebase 流程。

上述规范已经批准并进入实现。实现中的合同变化必须先回写规范并重新评审，不能只修改代码或测试来绕过规范。

## 本地研究台

启用并安装扩展后，DSA 左侧导航显示“研究台”，页面地址为 `/research`。完整页面由外部工具随 Python 包提供，DSA 只加载通用页面清单并同源转发固定 JS/CSS 资源，因此新增或调整研究台功能通常不需要修改 DSA 前端。页面源码使用中性 `host-compatible` / `hosted surface` 命名，不携带宿主项目名称。

页面顶部显示外部研究引擎本地数据库中的只读研究自选列表，包含市场、类型、数据库最新行情日期、标签和备注；点击“用于研究”会把标的填入下方单标的工具，不会修改 DSA 自选或自动化配置。页面在 Shadow DOM 中隔离样式，并跟随宿主的浅色/深色主题和中英文设置。

研究自选下方的工具卡靠左排列，当前包含：

1. 公式画布；
2. 行情指标；
3. 网格优化；
4. 研究方法；
5. 量化策略回测；
6. 每日报告预览。

“研究方法”不写死任何具体方法。页面读取 `methods` API 返回的注册表和原始 JSON Schema，通用表单必须保留 Schema 属性名，不得把 `snake_case_parameter` 一类适配器参数自动改成 camelCase。新增普通方法只需在外部工具注册，不需要增加 DSA 路由或导航项。

ExternalTool 独立工作流和自动化可以使用自己维护的更大研究池做确定性筛选。DSA 的 `STOCK_LIST` 只控制 DSA 原生逐股深度分析，不要求覆盖 ExternalTool 研究池。筛选候选不会自动触发 DSA 分析或修改任何列表；`automation/daily-report.yaml` 是 Action 使用的独立版本化研究池快照。每日报告同时显示研究池数量以及各行情渠道的本次访问和可用日额度。

DSA 原有 `/backtest` 仍表示 AI 建议的历史验证；研究台中的“量化策略回测”是 ExternalTool 的确定性策略回测，两者名称、API 和结果互不混用。

公式画布直接使用脚本模式，不再提供表达式模式切换。函数速查由 ExternalTool 适配层按类型返回，运行结果中的折线、柱状图、背景区间、多子图和 K 线由 ExternalTool 托管页面使用自身图表组件渲染。DSA 只同源转发公式目录、任务和结果，不复制函数或图表实现。

## 每日自动化

DSA 每日 workflow 可以用只读 fine-grained PAT 从私有外部工具仓库检出固定 commit，并安装 Secret 指定的包相对路径。默认 `full` 模式复用 DSA 原有合并通知和 `EmailSender`，按“大盘 -> 个股 -> 已启用研究方法 -> 其他研究片段 -> 自定义 Markdown -> 数据源、截止日、限制与免责声明”的顺序发送一封邮件。扩展失败不会阻断原生报告，JSON/Markdown 诊断会进入 artifact。

启用步骤、固定 SHA、163 授权码和首次手动验收见 [`SETUP.md`](SETUP.md)。
