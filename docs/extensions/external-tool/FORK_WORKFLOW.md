# DSA fork 上游同步与补丁栈维护流程

> 状态：已批准，实施中
> 适用对象：维护包含 ExternalTool 扩展的 DSA 个人 fork
> 目标：让自定义提交始终位于官方 `upstream/main` 顶部，降低长期同步成本

## 1. 远端与分支模型

远端约定：

```text
upstream  官方仓库，只拉取
origin    个人 fork，可推送
```

分支约定：

```text
upstream/main     官方基线
origin/main       个人 fork 默认分支和定时 Action 分支
main              本地个人补丁栈：upstream/main + 自定义线性提交
```

`main` 必须保持线性历史，不从 `upstream/main` 创建 merge commit。GitHub 定时 workflow 只读取默认分支，因此个人 fork 的默认分支需要指向包含自定义 Action 的 `main`。

初次建立远端时，应先确认当前工作区干净，再执行与实际 fork 地址对应的 remote 配置。规范和脚本不得写死个人账号或凭据。

## 2. 自定义提交分层

建议把扩展保持为少量、可独立重放的逻辑提交：

1. `feat(extension): add ExternalTool adapter backend`
2. `feat(web): add ExternalTool research workspace`
3. `feat(report): compose ExternalTool daily report`
4. `ci: install ExternalTool in daily workflow`
5. `docs: document ExternalTool extension and fork workflow`

测试应尽量与对应实现位于同一提交，避免 rebase 中出现“实现已重放但测试尚未重放”的中间状态。提交不得混入无关格式化或上游代码重构。

## 3. 每次同步上游的标准流程

### 3.1 同步前

```bash
git status --short
git fetch origin --prune
git fetch upstream --prune
git log --oneline --decorate --graph --max-count=30 --all
```

要求：

- 工作区和暂存区必须干净；
- 当前没有未完成的 merge、rebase 或 cherry-pick；
- 记录当前 `origin/main` SHA；
- 建议创建本地备份分支，例如 `backup/main-before-upstream-sync`；如同名已存在，应使用带日期或 SHA 的新名称。

### 3.2 Rebase

```bash
git switch main
git rebase upstream/main
```

结果必须是：

```text
upstream/main -- 自定义提交1 -- 自定义提交2 -- ... -- main
```

这就是“把自己的提交放到最新官方提交最上面”。不要使用 GitHub “Sync fork” 产生 merge commit，也不要把官方更新 merge 进自定义提交栈。

### 3.3 冲突处理

冲突时遵循：

1. 先理解上游新语义和测试，不机械选择 ours/theirs。
2. 官方核心文件优先保留上游结构，再重新挂载最小扩展入口。
3. 扩展目录优先保留自定义实现，再适配新的上游合同。
4. 工作流冲突不得复制旧版完整 workflow 覆盖新版；重新应用最小 composite action/步骤挂载。
5. 每解决一个逻辑提交的冲突，运行该提交最接近的目标测试，再执行 `git rebase --continue`。
6. 无法确认语义时执行 `git rebase --abort`，恢复后先更新规范或请求评审。

建议启用 Git 的冲突复用记录：

```bash
git config rerere.enabled true
```

## 4. Rebase 后验证

至少执行：

```bash
python -m pytest -m "not network"
cd apps/dsa-web
npm ci
npm run lint
npm run build
```

若变更只涉及扩展，可先跑 `TEST_PLAN.md` 中的目标测试；在推送默认分支前仍需确认 DSA 阻断型 CI 对应检查。GitHub Actions 工作流变更还必须执行 YAML/映射静态检查和一次手动 `workflow_dispatch` 验证。

验证完成后检查提交栈：

```bash
git log --oneline upstream/main..main
git diff --stat upstream/main...main
```

预期只出现个人扩展的逻辑提交和文件，不应包含被意外复制的上游提交。

## 5. 更新个人 fork

rebase 会重写自定义提交 SHA，因此推送必须使用：

```bash
git push --force-with-lease origin main
```

禁止使用 `git push --force`。`--force-with-lease` 发现远端出现未知新提交时会拒绝覆盖；此时重新 fetch、检查远端变化并重新评估，不得绕过保护。

建议对 `main` 启用：

- 必须通过 CI；
- 禁止直接无审查修改；
- 允许维护者在确认后使用 force-with-lease 完成 rebase；
- 不允许第三方在同步期间向同一分支追加提交。

## 6. 自动化上游检查

可新增只读的定时检查 workflow：

- fetch `upstream/main`；
- 比较 fork 基线是否落后；
- 输出落后提交数和变更文件；
- 创建或更新提醒，但不自动 rebase、不自动解决冲突、不自动 force push。

自动 rebase 默认不启用，因为 DSA 的配置、API、报告和 workflow 冲突需要语义评审。人工或 Agent 完成 rebase、测试和 review 后再推送。

## 7. ExternalTool 版本升级流程

ExternalTool 属于另一个仓库，不进入 DSA 补丁栈。DSA 只记录不可变版本或 commit SHA。

升级顺序：

1. 在 ExternalTool 仓库完成实现、测试和版本标记。
2. 在 DSA 功能分支只修改固定版本引用。
3. 运行适配合同、API、UI 和报告集成测试。
4. 合并为一个独立依赖升级提交。
5. 若失败，恢复上一固定版本，不回滚 DSA 原生数据库。

不要在每次 DSA upstream rebase 时顺手升级 ExternalTool；两类变化必须分开评审。

## 8. 回滚

- rebase 未完成：`git rebase --abort`。
- rebase 已完成但未推送：从同步前备份分支恢复或重新建立补丁栈。
- 已推送但发现问题：优先修复或将 `main` 重新 rebase/重置到已确认备份后使用 `--force-with-lease`，不得使用不受保护的强推。
- ExternalTool 运行问题：恢复上一固定引擎版本或关闭 `EXTERNAL_TOOL_ENABLED`；DSA 原生功能必须继续可用。

## 9. 每次同步检查清单

- [ ] `upstream` 指向官方仓库，`origin` 指向个人 fork。
- [ ] 工作区干净并记录同步前 SHA。
- [ ] 使用 `git rebase upstream/main`，没有 merge commit。
- [ ] 自定义提交仍是少量逻辑补丁。
- [ ] 官方核心文件没有被旧副本覆盖。
- [ ] 目标测试、Web 构建和必要 Action 验证通过。
- [ ] `upstream/main..main` 只包含自定义提交。
- [ ] 使用 `git push --force-with-lease`。
