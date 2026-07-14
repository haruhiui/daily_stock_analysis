# DSA 托管 ExternalTool 扩展规范

> 状态：已批准，实施中
> 版本：0.1
> 适用范围：DSA fork 中的 ExternalTool 可选扩展、本地研究台、GitHub Actions 每日报告和邮件组合
> 实施门槛：本规范、ExternalTool 引擎规范和测试计划均评审通过前，不得开始功能实现

## 1. 目标

DSA 是唯一的用户界面、认证入口、任务宿主、报告组合器和通知中心；ExternalTool 是无 UI 依赖的可选量化引擎。用户在本地 DSA UI 中直接调用 ExternalTool，GitHub Actions 在无服务器、电脑关机时调用同一适配合同生成每日研究片段，并由 DSA 发送邮件。

扩展必须保持 opt-in、可移除、低耦合，方便持续把官方 DSA 更新 rebase 到个人 fork，同时让 ExternalTool 可以独立开发和发布。

## 2. 设计原则

1. **宿主与引擎分离**：DSA 不拥有量化算法，ExternalTool 不拥有 DSA UI。
2. **单一适配入口**：DSA 只导入 `EXTERNAL_TOOL_ADAPTER_MODULE` 指定的固定适配模块。
3. **功能关闭即零影响**：未启用或未安装 ExternalTool 时，DSA 原有 API、页面、任务和通知行为保持不变。
4. **功能目录隔离**：绝大部分自定义代码位于独立目录；修改官方高冲突文件只保留最小路由、导航和工作流挂载点。
5. **确定性优先**：注册的研究方法和每日报告由普通 Python 代码执行，不依赖 LLM 是否选择调用某个工具。
6. **同合同双入口**：本地 UI 与 GitHub Actions 调用同一适配合同，但生命周期和持久化定位明确区分。
7. **上游优先**：发生 rebase 冲突时先保留上游语义，再重新挂载扩展，不复制或冻结上游实现。

## 3. 产品定位

| 组件 | 运行时间 | 主要职责 | 明确不负责 |
| --- | --- | --- | --- |
| DSA 本地 UI | 用户电脑开机并启动 DSA 时 | 交互研究、自选列表、参数编辑、任务进度、图表和历史查看 | 电脑关机时持续运行 |
| DSA FastAPI | 本地 UI 或自托管服务运行时 | 鉴权、API、任务队列、适配调用和错误翻译 | 实现研究方法、公式、网格或回测算法 |
| ExternalTool | 被本地 DSA、CLI 或 Action 调用时 | 行情、指标、公式、网格、可注册研究方法、回测、结构化报告 | 页面、认证、邮件和 GitHub fork 同步 |
| GitHub Actions | 定时或手动批处理 | 安装固定版本引擎、生成 DSA 原生报告和 ExternalTool 片段、发邮件、上传 artifact | 提供常驻 Web UI 或持久服务器 |
| DSA 邮件通知 | Action 或本地任务完成后 | 组合大盘、个股、已启用研究方法和自定义信息并投递 | 作为量化计算真源 |

GitHub Actions 不能托管可交互 DSA UI。电脑关闭时仍可收到邮件和查看 Action artifact，但不能使用本地研究台。

ExternalTool 现有 Web UI 在第一阶段兼容保留但停止新增功能。DSA 研究台达到功能等价前不得直接删除旧 UI；达到功能等价后，旧 UI 下线作为独立变更评审，不能混入本次接入。

## 4. 总体调用关系

```text
本地交互：
DSA React UI
  -> /api/v1/external-tool/*
  -> DSA ExternalToolService
  -> EXTERNAL_TOOL_ADAPTER_MODULE 指定的适配模块
  -> ExternalTool 核心引擎

每日自动化：
GitHub Actions
  -> 安装固定版本 ExternalTool
  -> 固定适配模块的 generate_daily_report()
  -> DSA 报告组合器
  -> DSA EmailSender
```

JSON/Markdown 报告是可审计的输出合同和 artifact，不是本地 UI 的唯一调用方式。

两个入口均采用 Python 包直接导入，不采用端口 API：

- 本地：先把外部工具 editable install 到 DSA 使用的同一 Python 虚拟环境，DSA 进程导入本地配置指定的固定适配模块。
- GitHub Actions：先从私有外部工具仓库只读检出并安装固定 commit 的 ExternalTool，再由 DSA 批处理进程导入同一适配层。
- DSA 不通过 `PYTHONPATH` 或运行时源码目录扫描加载代码；适配模块名必须来自本地配置或受保护的 Actions Secret，并通过点分模块名校验。

安装和 private 仓库授权步骤见 [`SETUP.md`](SETUP.md)。

## 5. DSA 代码隔离

### 5.1 后端目录

新增代码集中放置：

```text
src/extensions/external_tool/
├─ __init__.py
├─ contract.py
├─ errors.py
├─ loader.py
├─ service.py
├─ report_bridge.py
└─ task_handlers.py
```

职责：

- `loader.py`：导入 `EXTERNAL_TOOL_ADAPTER_MODULE` 指定的固定模块，检查模块名格式、合同版本和能力；不得从路径扫描或请求参数导入模块。
- `contract.py`：DSA 侧 Pydantic 请求/响应模型和支持的合同版本。
- `service.py`：薄服务门面，只做请求规范化、适配调用和返回值校验。
- `task_handlers.py`：把同步引擎调用包装进 DSA 既有任务队列。
- `report_bridge.py`：把 ExternalTool 报告片段交给 DSA 报告组合器，不负责重新计算。
- `errors.py`：稳定错误码、HTTP 状态和脱敏诊断。

唯一必要的官方后端挂载点：

```text
api/v1/endpoints/external_tool.py
api/v1/router.py
```

`api/v1/endpoints/external_tool.py` 只负责路由和依赖注入，不放业务逻辑。`api/v1/router.py` 只增加一次 router 注册。

### 5.2 前端目录

新增代码集中放置：

```text
apps/dsa-web/src/features/external-tool/
├─ api/
├─ components/
├─ hooks/
├─ pages/
├─ types/
└─ __tests__/
```

唯一必要的官方前端挂载点：

```text
apps/dsa-web/src/App.tsx
apps/dsa-web/src/components/layout/SidebarNav.tsx
apps/dsa-web/src/i18n/uiText.ts
```

挂载点不得包含业务状态、API 调用或页面实现。导航根据后端状态接口决定是否展示研究台；扩展异常不得破坏主导航。

### 5.3 禁止耦合

- 不复制 ExternalTool 的算法到 DSA。
- 不直接挂载 `external_tool_api` 的 FastAPI router。
- 不让浏览器直接访问第二个 ExternalTool 服务或端口。
- 不让 DSA 读取 ExternalTool SQLite 表结构。
- 不让 ExternalTool 读取 DSA 数据库、Cookie、任务队列或通知配置。
- 不修改 DSA 既有 AlphaSift 服务来承载 ExternalTool。
- 不把扩展代码散落到 DSA 原有分析、回测、设置和报告组件中。

## 6. 启用与状态

新增非敏感配置：

```text
EXTERNAL_TOOL_ENABLED=false
EXTERNAL_TOOL_DATA_DIR=
EXTERNAL_TOOL_AUTOMATION_CONFIG=
EXTERNAL_TOOL_CONTRACT_MIN=1
EXTERNAL_TOOL_CONTRACT_MAX=1
```

默认关闭。配置必须加入 `.env.example`、配置注册表和设置帮助。路径示例必须使用相对路径或通用占位符，不得写入本机绝对路径。`EXTERNAL_TOOL_AUTOMATION_CONFIG` 只在报告预览和 Action 批处理时需要，由调用环境显式指向 ExternalTool 检出目录中的版本化配置。

状态接口：

```http
GET /api/v1/external-tool/status
```

返回至少区分：

- `disabled`：配置关闭；
- `missing`：包未安装；
- `incompatible`：合同版本不支持；
- `degraded`：部分可选能力不可用；
- `available`：可用。

状态检查不得自动执行 `pip install`。安装或升级由部署流程显式完成，避免 Web 请求执行供应链变更。

## 7. API 合同

第一阶段端点：

```text
GET  /api/v1/external-tool/status
GET  /api/v1/external-tool/capabilities
GET  /api/v1/external-tool/methods
GET  /api/v1/external-tool/methods/{method_id}/schema
POST /api/v1/external-tool/methods/{method_id}/tasks
POST /api/v1/external-tool/formulas/run/tasks
POST /api/v1/external-tool/market-indicators/tasks
POST /api/v1/external-tool/grid/tasks
POST /api/v1/external-tool/backtests/tasks
POST /api/v1/external-tool/daily-report/tasks
GET  /api/v1/external-tool/tasks/{task_id}
```

要求：

- 长任务统一返回 `202` 和 DSA 任务 ID。
- 任务状态复用 DSA 现有 `pending/processing/completed/failed` 生命周期。
- 进度显示 `x/y` 时，`x` 和 `y` 必须来自真实处理进度。
- 单标的失败进入结果的 `failed_items`，不能把整个批次直接标记失败；初始化、合同或全局数据源失败除外。
- API 返回 snake_case；前端 API 层负责转换，不在组件内手工转换。
- 所有错误使用 `external_tool_*` 稳定错误码。
- 增加新的 ExternalTool 研究方法时不得增加 DSA 后端路由；方法发现、输入 Schema 和执行统一走 `methods` 端点。

## 8. 本地研究台 UI

新增 `/research` 页面，使用 DSA 现有视觉系统和公共组件，不搬运 ExternalTool 原页面样式。

页面顶部为靠左对齐的研究工具卡，顺序固定：

1. 公式画布；
2. 行情指标；
3. 网格优化；
4. 研究方法；
5. 量化策略回测；
6. 每日报告预览。

选择“研究方法”后，页面根据适配层注册表展示方法列表。通用方法使用 Schema 表单及摘要、表格、时间序列渲染器，专用 renderer 必须注册在隔离扩展目录中。新增普通研究方法不得修改 DSA 主导航或路由。

选择工具后在同页下方加载对应工作区。公式画布默认第一项。长任务使用 DSA 任务进度和错误组件；结果默认包含表格、时间序列或图表及可解释字段，不只显示单个数字。

DSA 现有 `/backtest` 页面继续表示 DSA 历史信号验证；ExternalTool 回测命名为“量化策略回测”，不得混用结果或 API。

DSA 现有 `/screening` 页面继续承载 AlphaSift；ExternalTool 研究方法第一阶段位于研究台，避免把不同引擎强行耦合到同一页面。后续若合并入口，需另行评审统一筛选合同。

## 9. 自选列表与配置定位

### 9.1 本地交互

DSA 的 `STOCK_LIST` 和本次请求标的是 DSA 原生逐股 LLM 深度分析的真源，也可以作为 ExternalTool 研究方法的一次性输入，但不再被定义为 ExternalTool 全部研究范围的唯一真源。ExternalTool 可以维护独立且更大的研究池，用于确定性选股、筛选和回测；DSA 不读取其内部数据库表。

### 9.2 GitHub Actions

GitHub Actions 同时保留两套显式范围：DSA `STOCK_LIST` 控制 DSA 原生深度分析，ExternalTool 仓库内版本化的 `automation/daily-report.yaml` 控制 ExternalTool 自动化研究池。Runner 不读取用户电脑的 DSA `.env` 或 ExternalTool SQLite。

### 9.3 同步边界

DSA 深度分析列表、ExternalTool 本地研究池和自动化研究池是三个明确作用域，不承诺自动同步：

- DSA 列表修改立即影响 DSA 原生深度分析，并只在用户显式选择时作为 ExternalTool 本次请求输入；
- ExternalTool 本地研究池用于更大范围的确定性筛选，不自动把全部标的送入 DSA；
- 自动化配置只有提交并推送到 ExternalTool 仓库后才影响 Action；
- ExternalTool 筛选候选是只读派生结果，不自动修改任一列表，也不自动触发 DSA 分析；
- 第一阶段 UI 提供自动化配置预览/导出和“尚未同步到 Action”的提示，不持有 GitHub Token，不自动 commit/push；
- 后续若增加 GitHub 同步，必须单独设计权限、审计和冲突处理。

DSA 与 ExternalTool 允许分别获取行情并保留各自的数据源、缓存、配额和失败语义。报告组合器只组合结构化结果，不在两个引擎之间隐式转发行情数据。

## 10. GitHub Actions

### 10.1 定位

Action 是一次性批处理，不启动 FastAPI 或 React。执行顺序：

1. 检出 DSA fork；
2. 安装 DSA 依赖；
3. 安装固定版本 ExternalTool；
4. 运行 DSA 原生个股和大盘分析；
5. 调用 ExternalTool 每日报告合同；
6. DSA 组合原生报告和自定义研究片段；
7. 由 DSA EmailSender 发送一封合并邮件；
8. 上传结构化 JSON、Markdown、日志和原生报告 artifact。

### 10.2 依赖安装

外部工具位于私有仓库。DSA workflow 自带的 `GITHUB_TOKEN` 只对 DSA 仓库有效，不能假定它能读取另一个 private 仓库。第一阶段采用第二次 `actions/checkout`：

- DSA 仓库 Secret `EXTERNAL_TOOL_REPO_TOKEN` 保存 fine-grained PAT；Token 只选择外部工具仓库，并仅授予 `Contents: read`，设置有效期和轮换提醒。
- DSA 仓库 Variable `EXTERNAL_TOOL_REPOSITORY` 保存 `<owner>/<repository>`，不得包含凭据。
- 第二次 checkout 固定完整 commit SHA、使用 sparse checkout 只取 `EXTERNAL_TOOL_PACKAGE_PATH` 指定的目录、设置独立 `path`，并关闭凭据持久化。
- 从检出目录执行普通 `pip install`；禁止把 Token 拼进 Git URL、pip 参数、cache key、artifact 或日志。
- workflow 只在受信任的 `schedule`、`workflow_dispatch` 或默认分支事件使用该 Secret，不得在不受信任的 pull request 代码上执行 private checkout。
- 长期可迁移到权限更易轮换的 GitHub App installation token；迁移不得改变 Python 适配合同。
- 不允许默认跟随 `master/main` 浮动安装；升级必须显式修改固定 SHA 并通过合同测试。

自定义 Action 逻辑放入独立 composite action 或脚本目录；上游 `00-daily-analysis.yml` 只保留最小 setup/输出挂载，避免复制整份上游环境变量映射。

### 10.3 报告组合

合并邮件顺序：

1. 大盘复盘；
2. DSA 个股分析；
3. 已启用的外部工具研究方法片段；
4. ExternalTool 其他研究片段；
5. 自定义 Markdown；
6. 研究池范围和行情访问用量；
7. 数据源、截止日、限制和免责声明。

ExternalTool 片段失败采用 fail-open：保留 DSA 原生邮件，在对应位置显示失败摘要。邮件、API Key 和仓库 Token 只从 GitHub Secrets 注入。

ExternalTool 结构化报告必须带 `research_universe` 和 `data_access_usage`。合并邮件在研究片段之后显示研究池数量和各行情渠道的本次访问数、操作明细；渠道提供日额度时同时显示今日累计、日上限和剩余。计量口径必须区分精确渠道请求、第三方客户端逻辑调用和无法可信计数，不得把未知值伪装为零，也不得输出本地计数器路径。

邮件不得新增第二套 SMTP 实现。163 邮箱继续复用 DSA 现有 `EmailSender` 自动识别的 `smtp.163.com:465` SSL 配置，使用 `EMAIL_SENDER`、`EMAIL_PASSWORD`（SMTP 授权码而非网页登录密码）和可选 `EMAIL_RECEIVERS`。GitHub Actions 必须显式映射这些固定变量，其中授权码只能来自 Secret；本地运行只写入未提交的 `.env`。

## 11. 安装模式

| 模式 | 安装方式 | 用途 |
| --- | --- | --- |
| 本地开发 | `pip install -e "<ExternalTool工作区>[data,viz]"` | 联调和快速迭代 |
| 本地稳定使用 | 从已检出的固定 commit 普通安装，未来可改用 private wheel | 减少本地漂移 |
| GitHub Actions | private 仓库固定 SHA 只读 checkout 后普通安装 | 可复现批处理 |
| DSA 桌面打包 | 明确收集 `external_tool` 包并执行导入探针 | 后续阶段，第一阶段可不包含 |

ExternalTool 是 private 可选依赖，不写入 DSA 基础 `requirements.txt` 的浮动 Git URL。安装由本地部署步骤或隔离 Action setup 显式执行；未来发布 private wheel 时另行评审依赖源和凭据边界。

## 12. 兼容与升级

- DSA 支持一个明确的适配合同版本范围。
- ExternalTool 响应版本过新或过旧时，DSA 返回 `external_tool_contract_incompatible` 并隐藏研究入口。
- DSA 不对未知字段报错，但不得依赖未知字段。
- ExternalTool 升级先运行适配合同测试，再运行 DSA 扩展测试和 UI 构建。
- 回退只需恢复上一固定 ExternalTool 版本；不得要求回滚 DSA 原生数据库。

## 13. 安全与隐私

- DSA 不提供“从任意 URL 安装 Python 包”的公开接口。
- Web 状态接口不得回显本地绝对路径、pip 命令中的凭据或 GitHub Token。
- 公式运行继续遵守 ExternalTool 公式运行时安全边界；不得因接入 DSA 放宽文件系统、进程或网络权限。
- 邮箱授权码只保存在 GitHub Secrets 或未提交的本地 `.env`。
- 报告和测试 fixture 不包含真实敏感信息。

## 14. 文档与变更要求

实现时必须同步：

- 本目录的使用说明、fork 维护流程和测试计划；
- DSA `.env.example`、设置帮助、部署说明和 `docs/CHANGELOG.md`；
- ExternalTool 适配层、研究方法注册指南、示例方法和自动化报告文档；
- 用户可见 API、页面和邮件变化的中英文文档影响评估；
- PR 描述中的 UI 和报告截图证据。

## 15. 完成定义

仅当以下条件全部满足，才可宣称集成完成：

- ExternalTool 在没有 DSA 的环境中仍能独立运行和测试；
- DSA 在没有 ExternalTool 的环境中原有测试、启动和页面不回归；
- 本地研究台通过 DSA API 直接调用适配层；
- Action 使用同一适配合同生成报告，不复制算法；
- 通用方法注册、执行和渲染至少通过两个测试方法验证；
- 示例研究方法结果提供可解释的聚合序列；
- ExternalTool 失败不阻断 DSA 原生日报；
- 文档、测试、Action artifact、浅色/深色 UI 和真实 headless 页面验证齐全；
- fork 已完成一次上游 rebase 演练且自定义提交仍位于上游提交顶部。

## 16. 待评审决策

1. 第一阶段 DSA 桌面安装包是否必须内置 ExternalTool，还是先支持源码本地 UI 与 GitHub Actions。
2. 第一阶段使用只读 fine-grained PAT；是否要求上线前改为 GitHub App installation token。
3. 本地自动化配置第一阶段只导出，是否接受不自动同步 GitHub。
4. 研究台是否独立增加一级导航，当前规范建议增加。
