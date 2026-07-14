# ExternalTool 扩展测试与验收计划

> 状态：代码与离线验收完成，等待首次受保护环境 Action/邮件验收
> 目标：证明 DSA 原生能力与 ExternalTool 扩展相互隔离，并覆盖多研究方法、本地 UI、GitHub Actions、报告和示例状态机的真实风险

## 1. 测试原则

- 测试分为 ExternalTool 引擎、适配合同、DSA 后端、DSA Web、报告/通知、GitHub Actions 和 fork 维护七层。
- 确定性测试默认离线；网络数据源测试单独标记，不作为算法正确性的唯一证据。
- DSA 后端测试使用假的适配模块或依赖注入验证宿主行为，不重新实现任何 ExternalTool 研究算法。
- ExternalTool 测试在没有 DSA 包的环境中运行。
- “未安装、关闭、版本不兼容、部分失败”与成功路径同等重要。
- UI 必须进行真实 headless 页面验证，不能只依赖组件测试和构建。

## 2. ExternalTool 引擎层

责任仓库：ExternalTool。

### 2.1 研究方法注册表

必须覆盖：

- `list_research_methods()` 返回稳定 ID、版本、输入 Schema 和输出视图；
- `get_research_method_schema()` 对未知 ID 返回稳定错误；
- `run_research_method()` 校验输入并返回通用结果合同；
- 注册两个结构不同的测试方法后，适配层仍通过同一入口发现和执行；
- 方法版本不兼容、可选依赖缺失和单方法失败可诊断；
- 新增普通方法不需要修改 DSA router、任务生命周期或报告组合器。

### 2.2 示例方法状态机

必须覆盖：

- 默认 `out` 与显式 `long` 初始化；
- 谷值回升小于、等于、大于阈值；
- 峰值回撤小于、等于、大于阈值；
- 连续峰值、连续谷值和反复转换；
- 每月最多一次转换且永不卖空；
- 周均值不能跨自然月；
- 月内周均值的平均可由 fixture 手工复算；
- 前复权股票与不复权指数；
- 部分月默认不产生正式事件；
- 历史不足、单月有效天数不足、停牌和缺失值；
- 非有限值、重复日期、乱序输入；
- 多股票批次中单项失败继续；
- 输出历史与最终状态一致。

### 2.3 其他研究能力回归

- 公式画布返回图形序列、表格和日志；
- 行情指标遵守复权和周期策略；
- 网格优化与策略回测仍使用各自既有不复权约束；
- 报告生成不改变核心计算结果。

建议命令：

```bash
python -m pytest tests/test_example_method.py tests/test_adapter_contract.py tests/test_daily_report.py -v
python -m pytest tests/test_api_contract.py -v
```

## 3. 适配合同层

责任仓库：ExternalTool，同时由 DSA 保存消费者合同 fixture。

| 场景 | 预期 |
| --- | --- |
| 仅导入配置指定的固定适配模块 | 不联网、不运行迁移、不启动线程 |
| 空数据库状态检查 | 返回合同版本和能力，不崩溃 |
| 列出两个测试研究方法 | DSA 经同一合同发现两者，无专用导入 |
| 运行未知 `method_id` | 返回稳定的 method-not-found 错误 |
| 正常调用 | 返回严格 JSON 可序列化值 |
| 可选依赖缺失 | 对应能力降级，状态可诊断 |
| 单标的失败 | 批次完成并返回 `failed_items` |
| 合同升级追加字段 | 旧 DSA 消费者仍能解析 |
| 主合同版本不兼容 | DSA 明确拒绝，不猜测字段 |
| 异常包含路径/Token | 返回结果完成脱敏 |

DSA 保存的消费者 fixture 只校验稳定字段，不冻结完整响应，避免阻止兼容追加字段。

## 4. DSA 后端层

责任仓库：DSA fork。

目标测试文件建议：

```text
tests/test_external_tool_extension_service.py
tests/test_external_tool_extension_api.py
tests/test_external_tool_report_bridge.py
tests/test_external_tool_task_handlers.py
```

必须覆盖：

- `EXTERNAL_TOOL_ENABLED=false` 时不导入引擎；
- 包未安装时 DSA 启动、健康检查和原有 API 正常；
- 合同版本过低/过高；
- status、capabilities、研究方法列表/Schema/通用任务端点和其他工具端点；
- 增加第二个 fake method 时 DSA router 和 service 不修改；
- 任务 `pending -> processing -> completed/failed` 转换；
- 真实 `x/y` 进度与单项失败；
- 请求取消、超时和重复轮询；
- 错误码、HTTP 状态和诊断脱敏；
- DSA 传入自选列表，不读取 ExternalTool watchlist 表；
- 报告片段校验、排序和 fail-open；
- 未安装扩展时原有 analysis、history、backtest、alerts、settings API 合同不变。

目标命令：

```bash
python -m pytest tests/test_external_tool_extension_service.py -v
python -m pytest tests/test_external_tool_extension_api.py -v
python -m pytest tests/test_external_tool_report_bridge.py -v
python -m pytest tests/test_external_tool_task_handlers.py -v
./scripts/ci_gate.sh
```

## 5. DSA Web 层

责任仓库：DSA fork。

### 5.1 组件和页面测试

至少覆盖：

- 扩展关闭/缺失时导航不显示且其他导航可用；
- 扩展可用时显示“研究台”；
- 工具卡顺序和默认公式画布；
- 研究方法列表、通用 Schema 表单和通用结果 renderer；
- 示例方法的分类、阈值距离、数据日期、警告及聚合历史；
- 注入第二个 fake method 后可直接展示和执行，不增加页面路由；
- 任务提交、轮询、完成、部分失败、整体失败和取消；
- 本地列表与自动化列表作用域提示；
- “自动化配置未同步到 Action”提示；
- 浅色/深色下的状态颜色和文字对比；
- 桌面宽度和移动宽度无明显溢出；
- DSA 原有 AlphaSift `/screening` 和历史信号 `/backtest` 入口语义不变。

### 5.2 构建与真实页面

```bash
cd apps/dsa-web
npm ci
npm run lint
npm test -- --run src/features/external-tool
npm run build
```

随后后台启动 DSA API 和 Web，用 headless 浏览器验证：

- 页面能加载；
- 关键文案、工具卡和默认面板存在；
- 任一研究方法任务从提交到完成可见；
- 表格和图表非空；
- 控制台无未处理错误；
- 导航、卡片、结果区没有横向溢出；
- 扩展 API 失败时错误边界不影响主 Shell。

## 6. 报告与通知层

责任仓库：两个仓库分别验证生产与消费。

必须覆盖：

- ExternalTool JSON 与 Markdown 由同一结果渲染；
- DSA 合并顺序固定；
- 大盘、个股、已启用研究方法、自定义片段和免责声明齐全；
- 示例方法片段包含完整数据截止日和算法参数；
- ExternalTool 整体失败时仍发送 DSA 原生报告；
- 单片段失败显示失败摘要但不伪造数据；
- 163 邮件使用授权码且 Secrets 不出现在日志；
- HTML 邮件和纯文本 fallback 均可阅读；
- artifact 包含 JSON、Markdown 和脱敏日志；
- 非交易日不伪造当天报告。

邮件在线发送测试只在手动、受保护环境执行；普通 PR 测试使用 fake SMTP 或 sender mock，并校验最终 MIME 内容。

## 7. GitHub Actions 层

### 7.1 静态验证

- Workflow YAML 可解析；
- ExternalTool private checkout 使用完整固定 commit SHA；
- private 仓库 Token 仅来自 `EXTERNAL_TOOL_REPO_TOKEN` Secret，checkout 设置 `persist-credentials: false`；
- sparse checkout 只取 `EXTERNAL_TOOL_PACKAGE_PATH` 指定的目录，`.external/` 不进入 cache 或 artifact；
- workflow 不在不受信任的 pull request 路径注入 private Token；
- 安装后直接导入 Python 适配层，不启动第二个 API 端口；
- 不把任意 Secret/Variable 假设为自动注入；
- 扩展 setup 位于独立 action/脚本；
- ExternalTool 失败不会跳过 DSA 原生报告和 artifact 上传；
- timeout、cache 和 artifact retention 显式；
- cache 不包含凭据，且缓存缺失时任务可完全重建。

### 7.2 手动验收矩阵

| 模式 | ExternalTool | 预期 |
| --- | --- | --- |
| `full` | 成功 | 一封合并邮件和完整 artifact |
| `full` | 缺失 | DSA 原生邮件 + 扩展缺失摘要 |
| `full` | 部分股票失败 | 合并邮件 + 失败条目 |
| `market-only` | 可用 | 只运行大盘报告，不调用 ExternalTool 每日报告 |
| `stocks-only` | 可用 | 个股 + 已启用研究方法/自定义片段 |
| 非交易日 | 可用 | 按交易日策略跳过，不伪造当天数据 |
| `force_run` | 可用 | 明确标记强制运行和数据截止日 |

第一次上线前必须执行一次 `workflow_dispatch`，检查邮件、artifact、日志脱敏和运行时间。定时触发成功不能仅由本地模拟替代。

## 8. Fork/rebase 维护层

每次重要 DSA upstream 更新至少验证一次：

1. 在临时分支把自定义提交 rebase 到最新 `upstream/main`。
2. 确认无 merge commit，自定义提交全部位于顶部。
3. 运行扩展目标测试和上游阻断型 CI 对应检查。
4. 检查 `upstream/main...main` diff 只包含扩展所需改动。
5. 检查上游 `00-daily-analysis.yml`、API router、App route 和 Sidebar 变化没有被旧副本覆盖。
6. 只在验证后使用 `--force-with-lease` 更新 fork。

若同一上游文件连续多次发生冲突，应把逻辑继续下沉到扩展目录或 composite action，而不是长期重复解决大块冲突。

## 9. 安全与敏感信息测试

- 扫描 diff、日志和 artifact，不出现真实邮箱、授权码、Token、API Key、本机用户名路径和私有地址。
- 适配异常使用构造的敏感字符串 fixture，验证输出脱敏。
- GitHub cache 和测试快照不得保存 Secret。
- 构造 checkout 和 pip 日志，确认 Token 不出现在 URL、命令、异常和 artifact。
- 安装接口不可从未认证 Web 请求触发。
- 公式运行安全测试保持通过。

## 10. 发布门禁

实现 PR 只有在以下证据齐全时才能进入 review complete：

- 两个仓库的目标测试通过；
- DSA 阻断型 CI 通过；
- Web lint、测试、build 和 headless 页面验证通过；
- 报告 Markdown/HTML 截图和研究台浅色/深色截图齐全；
- 一次受保护的手动 Action 验收通过；
- 一次 upstream rebase 演练通过；
- 文档、配置示例和 CHANGELOG 同步；
- 已列出未执行的网络验证、风险和回滚方式。

## 11. 需求追踪

| 用户目标 | 规范/测试证据 |
| --- | --- |
| DSA 使用 ExternalTool 功能 | 适配合同 + DSA service/API/UI 测试 |
| ExternalTool 不再关注 UI | ExternalTool 无 UI 依赖测试 + DSA 研究台 |
| 本地 UI 与 Action 定位明确 | `SPEC.md` 第 3、9、10 节 + Action 矩阵 |
| 后续可增加其他方法 | 两个测试方法 + 通用 methods API/UI/report 测试 |
| 可注册研究方法示例 | 外部工具方法状态测试 + DSA 可解释结果 |
| 私有外部工具仓库接入 | `SETUP.md` + private checkout 静态/手动验收 |
| 独立每日报告 | 报告合同测试 + artifact 验收 |
| 方便维护 fork | 独立目录约束 + `FORK_WORKFLOW.md` + rebase 演练 |
| 邮箱报告 | MIME 测试 + 受保护手动发送验证 |
