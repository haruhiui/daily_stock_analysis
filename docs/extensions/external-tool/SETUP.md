# ExternalTool 扩展安装与 private 仓库授权指南

> 状态：已实现，等待首次受保护环境线上验收
> 目标读者：维护 DSA fork 和私有外部工具仓库的开发者
> 适用范围：本地 DSA UI 与 DSA GitHub Actions；不包含跨机器 HTTP 部署

## 1. 接入结论

第一阶段不通过端口 API 调用外部工具。两个运行环境都先把外部工具安装成标准 Python 包，再由 DSA 导入受保护配置指定的固定适配模块：

```python
import importlib
adapter = importlib.import_module("<外部工具适配模块>")
```

| 环境 | 安装方式 | 运行时调用 | 是否需要端口 |
| --- | --- | --- | --- |
| 本地 DSA | 同一虚拟环境执行 editable install | DSA FastAPI 进程直接导入 | 否 |
| GitHub Actions | 检出 private 仓库固定 commit 后普通安装 | DSA 批处理进程直接导入 | 否 |

不使用 `PYTHONPATH`，不让 DSA 根据环境变量扫描任意源码目录，也不启动第二套 FastAPI。这样本地电脑只需要运行 DSA；电脑关机时，由 GitHub-hosted runner 临时完成同样的安装和调用。

## 2. 本地安装

### 2.1 前置条件

- DSA 和 ExternalTool 使用兼容的 Python；当前 ExternalTool 声明 Python 3.10 及以上，DSA workflow 使用 Python 3.11。
- 已在本机分别检出 DSA fork 与外部工具仓库。
- 以下命令必须在 DSA 实际使用的 Python 虚拟环境中执行。

### 2.2 安装 editable package

```bash
python -m pip install -e "<外部工具工作区>/<外部工具包相对路径>[data,viz]"
```

editable install 只用于本地开发：修改 ExternalTool Python 代码后，无需重复复制文件或重新安装 wheel。`<外部工具工作区>` 是操作时填写的本机路径，只能出现在未提交的本地命令或配置中，不能写入仓库文档、测试 fixture 或已提交 `.env`。

DSA 本地 `.env` 最低配置：

```dotenv
EXTERNAL_TOOL_ENABLED=true
EXTERNAL_TOOL_DATA_DIR=./data/external-tool
EXTERNAL_TOOL_ADAPTER_MODULE=<外部工具适配模块>
```

`EXTERNAL_TOOL_DATA_DIR` 是行情和研究数据目录，不是源码目录。自动化报告配置只有在本地预览 Action 报告时才需要额外设置：

```dotenv
EXTERNAL_TOOL_AUTOMATION_CONFIG=<外部工具工作区>/<外部工具包相对路径>/automation/daily-report.yaml
```

该 `.env` 不得提交 Git。

### 2.3 验证

实现适配层后执行：

```bash
python -c "import importlib, os; adapter = importlib.import_module(os.environ['EXTERNAL_TOOL_ADAPTER_MODULE']); print(adapter.get_status())"
```

成功标志：输出包含受支持的合同版本和能力列表，且导入过程不启动网络请求、数据库迁移或 Web 端口。随后启动 DSA，只应看到一个 DSA FastAPI 服务；研究台通过 DSA 自己的 `/api/v1/external-tool/*` 路由工作。

## 3. GitHub Actions 读取私有外部工具仓库

### 3.1 为什么需要额外凭据

DSA workflow 自动获得的 `GITHUB_TOKEN` 权限局限于运行该 workflow 的 DSA 仓库，不能用于检出另一个 private 仓库。第一阶段使用只读 fine-grained personal access token；后续可迁移为 GitHub App installation token。

### 3.2 创建最小权限 Token

在 GitHub 的 personal access token 设置中创建 fine-grained token：

1. Resource owner 选择外部工具仓库所属账号或组织。
2. Repository access 选择“Only select repositories”，只选择外部工具仓库。
3. Repository permissions 只设置 `Contents: Read-only`；不要授予写入、Administration、Actions write 或其他无关权限。
4. 设置合理有效期。若组织要求审批，等待组织管理员批准后再测试。
5. 生成后立即保存，因为页面不会持续显示明文 Token。

不要使用账号密码，也不要为了方便创建对所有仓库长期有效的 classic PAT。

### 3.3 配置 DSA fork

进入 DSA fork 的 `Settings -> Secrets and variables -> Actions`：

| 类型 | 名称 | 值 |
| --- | --- | --- |
| Secret | `EXTERNAL_TOOL_REPO_TOKEN` | 上一步生成的只读 fine-grained PAT |
| Secret | `EXTERNAL_TOOL_PACKAGE_PATH` | 外部工具在私有仓库中的包相对路径 |
| Secret | `EXTERNAL_TOOL_ADAPTER_MODULE` | 安装后需要导入的固定适配模块名 |
| Variable | `EXTERNAL_TOOL_REPOSITORY` | 外部工具仓库的 `<owner>/<repository>` 标识 |
| Variable | `EXTERNAL_TOOL_REF` | 已通过合同测试的完整 40 位 commit SHA |
| Variable | `EXTERNAL_TOOL_ENABLED` | 启用时填写小写 `true`；默认不创建或填写 `false` |
| Secret | `EMAIL_PASSWORD` | 163 邮箱 SMTP 授权码，不是网页登录密码 |
| Variable 或 Secret | `EMAIL_SENDER` | 发件邮箱 |
| Variable 或 Secret | `EMAIL_RECEIVERS` | 收件邮箱，留空时沿用 DSA 既有默认行为 |

敏感值只放 Secret。仓库标识、发件人或收件人是否使用 Variable，取决于是否愿意让具有仓库读取权限的人看到这些非加密配置。

### 3.4 Workflow 检出与安装

每日 workflow 已保留第一次 DSA checkout，并通过 `.github/actions/setup-external-tool/action.yml` 挂载隔离的 private checkout 与安装步骤。主 workflow 只保留下面这段调用；`EXTERNAL_TOOL_REF` 必须由仓库 Variable 提供完整 40 位 SHA：

```yaml
permissions:
  contents: read

steps:
  - name: Checkout DSA
    uses: actions/checkout@v5

  - name: 安装可选外部工具
    id: external_tool_setup
    if: vars.EXTERNAL_TOOL_ENABLED == 'true'
    continue-on-error: true
    uses: ./.github/actions/setup-external-tool
    with:
      repository: ${{ vars.EXTERNAL_TOOL_REPOSITORY }}
      ref: ${{ vars.EXTERNAL_TOOL_REF }}
      token: ${{ secrets.EXTERNAL_TOOL_REPO_TOKEN }}
      package-path: ${{ secrets.EXTERNAL_TOOL_PACKAGE_PATH }}
      import-module: ${{ secrets.EXTERNAL_TOOL_ADAPTER_MODULE }}
```

实际 workflow 会在安装前校验变量和 checkout 的 `HEAD` 都是同一个完整 SHA。不得使用浮动 `main`/`master`，不得把 Token 插入 `https://<token>@github.com/...`，不得把 `.external/` 上传为 artifact 或缓存。安装完成后，DSA Action 入口直接调用适配层生成结构化片段，再交给 DSA 现有报告组合器和 `EmailSender`。

`full` 是定时任务的默认模式。扩展启用后，DSA 自动走已有合并通知路径，邮件顺序为大盘、个股、已启用研究方法、其他研究片段、自定义 Markdown、研究池范围与行情访问用量、数据源与截止日、限制和免责声明。`stocks-only` 会发送个股和扩展片段；显式 `market-only` 只运行大盘复盘，不调用 ExternalTool 每日报告。

private checkout 或安装步骤使用 fail-open：失败时仍继续 DSA 原生分析，合并报告中的“自定义研究”位置会显示脱敏失败摘要，`reports/external-tool/` 会保存失败 JSON/Markdown 供 artifact 排查。DSA 自身分析失败仍按原 workflow 规则报错，不能被扩展降级掩盖。

### 3.5 触发与信任边界

- private checkout 只允许在 `schedule`、维护者触发的 `workflow_dispatch` 或受保护默认分支上运行。
- 不得在来自未知 fork 的 `pull_request` 代码中向步骤注入 `EXTERNAL_TOOL_REPO_TOKEN`。
- 修改每日 workflow、安装脚本或扩展入口的人，实质上能够影响 private 源码如何被处理；DSA fork 的写权限必须只授予可信维护者。
- Token 到期或泄露时，先撤销旧 Token，再创建新 Token 并覆盖同名 Secret；不需要修改适配合同。

## 4. 163 邮箱授权码

DSA 已内置 `163.com -> smtp.163.com:465` 的 SSL 配置，不需要填写 SMTP 主机或端口，也不要新增邮件插件。

1. 登录 163 网页邮箱，打开“设置 -> POP3/SMTP/IMAP”。
2. 开启 IMAP/SMTP 或 POP3/SMTP 服务；按页面提示完成手机验证。
3. 复制页面生成的客户端授权码。该值只会用作 SMTP 客户端密码，不是邮箱网页登录密码。
4. 在 DSA fork 的 Actions Secret 中创建 `EMAIL_PASSWORD`，值为授权码。
5. 设置 `EMAIL_SENDER`；需要发给其他地址时设置逗号分隔的 `EMAIL_RECEIVERS`，留空则默认发给自己。

网易帮助中心当前说明第三方客户端应先开启“客户端授权密码”，并在客户端密码栏填写该授权密码；若网页入口调整，以[网易邮箱帮助中心的图文指引](https://help.mail.163.com/faqDetail.do?code=d7a5dc8471cd0c0e8b4b8f4f8e49998b374173cfe9171305fa1ce630d7f67ac2a5feb28b66796d3b)为准。

建议先用 `workflow_dispatch` 的 `full` 模式验证。日志应只显示“已配置”或认证结果，不应打印授权码。认证失败时重新生成授权码并覆盖同名 Secret，不要把授权码写进 `.env.example`、workflow 或 issue。

## 5. 常见失败

| 现象 | 检查项 |
| --- | --- |
| `Repository not found` | `EXTERNAL_TOOL_REPOSITORY`、Token 选择的仓库、组织审批状态 |
| checkout 返回 403 | Token 是否过期、是否有 `Contents: Read-only`、组织是否限制 PAT |
| `No module named external_tool` | pip 是否运行在 DSA 使用的同一 Python、安装路径是否包含 `pyproject.toml` |
| 合同版本不兼容 | DSA 支持范围与固定 commit 是否匹配；恢复上一个已验证 SHA |
| 本地可用但 Action 不可用 | 本地 editable install 不能自动同步；确认 private checkout 和固定 SHA |
| 163 返回认证错误 | 确认使用客户端授权码而非网页登录密码，并确认 SMTP 服务已开启 |
| 收到原生报告但自定义研究失败 | 下载 artifact 中的 `reports/external-tool/`，按稳定错误码排查 private checkout、安装或自动化配置 |

## 6. 官方参考

- [GitHub：`GITHUB_TOKEN` 的权限局限于当前 workflow 仓库](https://docs.github.com/en/actions/concepts/security/github_token)
- [actions/checkout：检出另一个 private 仓库需要自备 PAT](https://github.com/actions/checkout#checkout-multiple-repos-private)
- [GitHub：创建和管理 fine-grained personal access token](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens)
- [GitHub：跨仓库访问可使用 GitHub App installation token](https://docs.github.com/en/apps/creating-github-apps/authenticating-with-a-github-app/making-authenticated-api-requests-with-a-github-app-in-a-github-actions-workflow)
- [网易邮箱：第三方客户端授权密码图文指引](https://help.mail.163.com/faqDetail.do?code=d7a5dc8471cd0c0e8b4b8f4f8e49998b374173cfe9171305fa1ce630d7f67ac2a5feb28b66796d3b)
