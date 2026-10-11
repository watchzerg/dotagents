---
name: setup-project
description: 按个人模板初始化新项目的 Beads、标准化文档结构与开发工具链（uv、Bun、Swift 的任意组合，或无预置 stack），建立 gate-core 与 gate-full 门禁。
---

# 项目初始化

维护本 skill 前先读 [references/design.md](references/design.md)。

本 skill 安装在目标机器的用户级，供各项目复用。用户需要初始化新项目时，先进入目标项目根目录，再调用本 skill。初始化目标始终是调用时当前工作目录所在的项目；执行脚本时保持该工作目录，skill 的安装目录仅用于定位脚本和配套资源。

用户请求初始化项目时按阶段顺序执行全部阶段；用户仅要求讨论时保持只读。每个阶段的脚本都可重复运行，已有产物不会被覆盖。

## 阶段 1：前置条件

### 1.1 初始化 Beads（已确定）

在目标项目根目录调用，保持当前工作目录：

```sh
python3 "<skill目录>/scripts/init_beads.py"
```

脚本失败则报告错误并中止；成功后报告初始化或跳过结果。首次 `bd init` 的自动 Git commit 属于已确认行为。

### 1.2 检查 Matt Pocock skills 设置（已确定）

检查 `docs/agents/issue-tracker.md` 与 `docs/agents/domain.md` 是否存在。两者由 `setup-matt-pocock-skills` 写入；缺少任一时提醒用户先执行 `/setup-matt-pocock-skills`，然后重新调用本 skill，不要代替用户执行。阶段 2 的脚本会再次做同一检查。

## 阶段 2：文档结构初始化（已确定）

结构定义与依据见 [references/docs-structure.md](references/docs-structure.md)，模板正文在 `templates/`。

1. 在目标项目根目录运行，保持当前工作目录；项目名默认取目录名，需要时用 `--name` 指定：

   ```sh
   python3 "<skill目录>/scripts/init_docs.py"
   ```

   脚本把 `templates/` 下每个文件复制到项目同名路径，替换 `{{PROJECT_NAME}}`，已存在的文件跳过并逐项报告。`AGENTS.md` 例外：已存在时按二级标题合并，缺少的节追加，已有的节与标题外内容原样保留，Matt setup 写入的 `## Agent skills` 节被移除并打印原文（其指针已并入触发表）。`docs/agents/triage-labels.md` 不存在时触发表不含 triage 行。脚本可重复运行，第二次无变更。失败则报告错误并中止。

2. 检查合并后的 `AGENTS.md`：若现有文件用别的标题写了与"常驻约束"或"按任务读取"同义的内容，合并同义节，保留用户措辞；若 `## Agent skills` 节在 `CLAUDE.md` 里，删除该节并让 `CLAUDE.md` 只保留一行 `@AGENTS.md`。脚本移除的节若含项目特有说明（如 tracker 的特殊约定），把它写进对应的 `docs/agents/` 文件而不是放回 `AGENTS.md`。

3. 收敛已有文档：按 [references/converge-docs.md](references/converge-docs.md) 列出标准结构之外的文档候选；没有候选则跳过。有候选时派一个只读子 agent 读取并分类，主 agent 按返回的表合并、迁移、删除或保留登记，更新链接，不 commit。全部动作进报告，用户提交前自行审阅工作区。

4. 从代码补写文档：项目已有代码时按 [references/document-code.md](references/document-code.md) 派子 agent 读取代码与配置，填写架构总览、模块边界的 `首个模块` 类标记并按模板建模块页；已有工具链配置时一并填 `阶段3` 类标记。空项目跳过。

5. 处理剩余 `<待填 时机：说明>` 标记：`初始化` 类现在填写，只向用户问一次项目一句话描述，AGENTS.md、README、GLOSSARY 三处从同一答案展开；其余保留，由项目迭代按 `AGENTS.md` 常驻约束逐步填写，不询问用户，不编造。

6. 报告创建、合并与跳过的文件、移除的节、收敛结果、补写的模块页与已知差异、术语候选、仍保留的 `<待填>` 标记。

## 阶段 3：工具链与门禁（已确定）

stack 判定、各 stack 落什么、拼合规则与门禁定义见 [references/toolchain.md](references/toolchain.md)，模板在 `toolchain/`。

1. 在目标项目根目录运行，保持当前工作目录：

   ```sh
   python3 "<skill目录>/scripts/init_toolchain.py"
   ```

   脚本按文件证据判定项目由哪些 stack 组成（uv、bun、swift 的任意组合，或没有预置 stack）并区分模式：**已有工具链**（存在 lockfile、justfile 或其他语言的工程文件）只把各 stack 的依赖偏好补进 `docs/development/technology-stack.md`，不创建任何工具链文件，并列出 justfile 缺少的契约 recipe；**新项目**复制各 stack 的工具链文件与工具链测试，拼出根 `justfile`（公开契约 recipe 聚合各 stack 的私有 `<stack>-*` recipe），复制 `scripts/check_docs.py`，追加 `.gitignore`，运行安装命令，用拼合后的正文替换 `<待填 阶段3：…>` 标记，最后运行 `just gate-core`。退出码 3 表示无法判定。

2. 退出码 3 时向用户多选：uv、bun、swift 可任意组合，没有预置 stack 选 none；然后带 `--stacks <答案>` 重跑（如 `--stacks uv bun`）。不替用户选。

3. 已有工具链且脚本报告 justfile 缺少契约 recipe 时，按 [references/toolchain.md](references/toolchain.md#命令契约) 补齐缺少的 recipe，用项目现有命令实现；没有对应能力的 recipe 写成非零退出并说明原因。不改动已有 recipe。

4. 报告：类型与模式、创建与跳过的文件、填写的文档节、安装命令与 `gate-core` 的实际结果、仍保留的 `<待填>` 标记。`gate-core` 失败时原样报告，不标记为通过。
