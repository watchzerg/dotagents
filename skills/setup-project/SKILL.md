---
name: setup-project
description: 按个人模板初始化新项目的 Beads、标准化文档结构与开发工具链（uv、Bun、Swift 的任意组合，或无预置 stack），建立 gate-core 与 gate-full 门禁。
---

# 项目初始化

本 skill 安装在目标机器的用户级，供各项目复用。初始化目标始终是调用时当前工作目录所在的项目；执行脚本时保持该工作目录，skill 的安装目录仅用于定位脚本和配套资源，下文写作 `<skill目录>`。

流程分四个阶段：只读检查 → 脚本落地 → agent 文档工作 → 统一验证与报告。用户请求初始化时按顺序执行全部阶段；用户仅要求讨论时在阶段 0 之后停下，保持只读。每个脚本都可重复运行，已有产物不会被覆盖。脚本失败时报告错误并中止，不继续后续阶段。

## 阶段 0：前置检查（只读）

1. 当前目录在 Git 工作区内。
2. `docs/agents/issue-tracker.md` 与 `docs/agents/domain.md` 存在。两者由 `setup-matt-pocock-skills` 写入；缺少任一时提醒用户先执行 `/setup-matt-pocock-skills`，然后重新调用本 skill，不要代替用户执行。

## 阶段 1：脚本落地

1. **Beads**：

   ```sh
   python3 "<skill目录>/scripts/init_beads.py"
   ```

   已有 `.beads` 则跳过。首次 `bd init` 的自动 Git commit 属于已确认行为。

2. **文档结构**（结构定义见 [references/docs-structure.md](references/docs-structure.md)，模板在 `templates/`）：

   ```sh
   python3 "<skill目录>/scripts/init_docs.py"
   ```

   项目名默认取目录名，需要时加 `--name`。脚本把模板复制到同名路径，已存在的文件跳过；`AGENTS.md` 按二级标题合并，并移除 Matt setup 写入的 `## Agent skills` 节、打印其原文。记下打印出的内容，阶段 2 第 1 步要用。

3. **工具链判定**：

   ```sh
   python3 "<skill目录>/scripts/init_toolchain.py" --detect-only
   ```

   只打印 stack 集合、模式（`new` 或 `existing`）与证据，不写文件；`existing` 模式还会列出 justfile 缺少的契约 recipe，记下来供阶段 2 使用。退出码 3 表示无法判定，需要用户选择。判定规则见 [references/toolchain.md](references/toolchain.md#stack-判定)。

4. **一次性提问**：用一次提问同时收集下列答案，都不需要时不问：
   - `AGENTS.md` 仍含 `<待填 初始化` 标记时，问项目的一句话描述。
   - 上一步退出码 3 时，让用户多选 stack：uv、bun、swift 可任意组合，没有预置 stack 选 none。不替用户选。

5. **工具链落地**（各 stack 落什么、拼合规则与门禁定义见 [references/toolchain.md](references/toolchain.md)）：

   ```sh
   python3 "<skill目录>/scripts/init_toolchain.py"
   ```

   退出码 3 时带 `--stacks <答案>` 重跑，如 `--stacks uv bun`。`new` 模式复制工具链文件与工具链测试、拼出根 `justfile`、复制 `scripts/check_docs.py` 与 `scripts/with_lock.py`、追加 `.gitignore`、替换 `<待填 阶段3：…>` 标记并运行安装命令；`existing` 模式只把各 stack 的依赖偏好补进 `docs/development/technology-stack.md`，不碰任何工具链文件。脚本不运行门禁，门禁在阶段 3。

## 阶段 2：agent 文档工作

1. **复核 `AGENTS.md`**：若现有文件用别的标题写了与"常驻约束"或"按任务读取"同义的内容，合并同义节，保留用户措辞。若 `## Agent skills` 节在 `CLAUDE.md` 里，删除该节并让 `CLAUDE.md` 只保留一行 `@AGENTS.md`。阶段 1 移除的节若含项目特有说明（如 tracker 的特殊约定），写进对应的 `docs/agents/` 文件，不放回 `AGENTS.md`。

2. **填写 `初始化` 标记**：用阶段 1 收集的一句话描述，AGENTS.md、README、GLOSSARY 三处从同一答案展开。其余 `<待填 时机：说明>` 标记保留，由项目迭代按 `AGENTS.md` 常驻约束逐步填写，不询问用户，不编造。

3. **收敛已有文档**：按 [references/converge-docs.md](references/converge-docs.md) 列出标准结构之外的文档候选；没有候选则跳过。有候选时先派只读子 agent 分类，再派可写子 agent 按分类表执行合并与迁移，主 agent 修正链接、登记索引、建票据、填可填标记。不 commit，用户提交前自行审阅工作区。

4. **从代码补写文档**：项目已有代码时按 [references/document-code.md](references/document-code.md) 派可写子 agent 读取代码与配置，填写架构总览与模块边界的 `首个模块` 类标记、按模板建模块页；`existing` 模式下同时填写剩余的 `阶段3` 类标记，并为阶段 1 列出的缺少 recipe 返回实现建议。空项目跳过。

5. **补齐缺少的契约 recipe**（仅 `existing` 模式且项目有 justfile）：按 [references/toolchain.md](references/toolchain.md#命令契约) 和上一步的建议写入 justfile，用项目现有命令实现；没有对应能力的 recipe 写成非零退出并说明原因。不改动已有 recipe。

## 阶段 3：统一验证与报告

1. **文档检查**：`new` 模式运行 `just docs-check`；`existing` 模式在项目根目录运行：

   ```sh
   python3 "<skill目录>/toolchain/common/scripts/check_docs.py" .
   ```

   本次 agent 改动造成的错误修复后重跑；其余错误原样报告。

2. **门禁**：`new` 模式运行 `just gate-core`，失败原样报告，不标记为通过。`existing` 模式若本次补了 recipe，运行 `just --list` 确认 justfile 可解析；不运行项目自己的门禁。

3. **汇总报告**，一份覆盖全部阶段：
   - stack 与模式；创建、合并与跳过的文件；追加的 `.gitignore` 行。
   - `AGENTS.md` 追加与移除的节、合并的同义节。
   - 收敛结果：每个候选的动作与目标、保留登记清单、删除依据、更新的链接数。
   - 补写的模块页、已知差异、术语候选与 ADR 建议。
   - 补齐的 recipe。
   - 安装命令、文档检查、`gate-core` 的实际结果。
   - 仍保留的 `<待填>` 标记。
