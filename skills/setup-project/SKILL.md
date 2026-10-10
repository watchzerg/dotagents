---
name: setup-project
description: 按个人模板初始化新项目的 Beads 与标准化文档结构。阶段 1（Beads、Matt skills 检查）和阶段 2（文档结构）可执行，开发环境初始化仍待讨论。
---

# 项目初始化

维护本 skill 前先读 [references/design.md](references/design.md)。

本 skill 安装在目标机器的用户级，供各项目复用。用户需要初始化新项目时，先进入目标项目根目录，再调用本 skill。初始化目标始终是调用时当前工作目录所在的项目；执行脚本时保持该工作目录，skill 的安装目录仅用于定位脚本和配套资源。

用户请求初始化项目时按阶段顺序执行到最后一个已确定的阶段，完成后说明后续阶段尚未实现并停止；用户仅要求讨论时保持只读。每个阶段的脚本都可重复运行，已有产物不会被覆盖。

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

3. 搜索本次创建或合并的文件中的 `<待填 时机：说明>` 标记，按时机处理：`初始化` 类现在填写，只向用户问一次项目一句话描述，AGENTS.md、README、GLOSSARY 三处从同一答案展开；`首个模块` 类在项目已有代码时读代码填写，空项目保留；`阶段3` 和 `按需` 类保留。其余由项目迭代按 `AGENTS.md` 常驻约束逐步填写，不询问用户，不编造。

4. 报告创建、合并与跳过的文件、移除的节、仍保留的 `<待填>` 标记。

## 阶段 3：项目依赖初始化（待讨论）

1. 询问选择 uv 或 Bun，初始化对应配置文件，跑通 install，并将工具链约定写入 `docs/development/technology-stack.md`。
2. 创建 `justfile`，提供基本的 `gate-core` 与 `gate-full`，并将命令与测试分层写入 `docs/development/workflow.md` 和 `docs/agents/testing.md` 的待填位置。

依赖范围、命令定义、门禁边界后续讨论；配置、命令和对应文档作为同一项能力一起落地。
