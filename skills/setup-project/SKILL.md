---
name: setup-project
description: 按个人模板初始化新项目的 Beads、标准化文档结构与开发工具链（uv、Bun、Swift 的任意组合，或无预置 stack），建立 gate-core 与 gate-full 门禁。
---

# 项目初始化

本 skill 安装在目标机器的用户级，供各项目复用。初始化目标始终是调用时当前工作目录所在的项目；执行脚本时保持该工作目录，skill 的安装目录仅用于定位脚本和配套资源，下文写作 `<skill目录>`。

流程分四个阶段：只读检查 → 脚本落地 → agent 文档工作 → 统一验证与报告。用户请求初始化时按顺序执行全部阶段；用户仅要求讨论时在阶段 0 之后停下，保持只读。每个脚本都可重复运行，已有产物不会被覆盖。脚本失败时报告错误并中止，不继续后续阶段。

## 阶段 0：前置检查（只读）

1. 当前目录是 Git 工作区的根目录。不在 Git 工作区时提醒用户先 `git init`，不代为执行。
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

   项目名由脚本取 `AGENTS.md` 的一级标题，没有则取目录名；只有用户明确给出别的名字时才加 `--name`。脚本把模板复制到同名路径，已存在的文件跳过（只有空白的文件视为缺失）；`AGENTS.md` 按二级标题合并，二级标题前没有内容时补上模板开头，并移除 Matt setup 写入的 `## Agent skills` 节、打印其原文。记下打印出的内容，阶段 2 第 1 步要用。

3. **工具链判定**：

   ```sh
   python3 "<skill目录>/scripts/init_toolchain.py" --detect-only
   ```

   只打印 stack 集合、模式（`new` 或 `existing`）与证据，不写文件；`existing` 模式还会列出 justfile 缺少的契约 recipe，记下来供阶段 2 使用。退出码 3 表示无法判定，需要用户选择，此时模式必然是 `new`。判定规则见 [references/toolchain.md](references/toolchain.md#stack-判定)。

4. **一次性提问**：用一次结构化提问同时收集下列答案，都不需要时不问：
   - `init_docs.py` 末尾列出的仍含 `<待填 初始化` 标记的文件不为空时，问项目的一句话描述（自由文本）。`AGENTS.md` 已有开头时脚本保留原文，不留标记，所以以脚本列出的文件为准，不按 `AGENTS.md` 是否存在推断。
   - 上一步退出码 3 时，让用户多选 stack：uv、bun、swift 可任意组合，没有预置 stack 选 none；题干附上脚本打印的证据。不替用户选。

   用户不给描述时保留 `初始化` 标记并在报告列出；用户不选 stack 时到此停止，报告已完成的步骤，不进入后续阶段。

5. **工具链落地**（各 stack 落什么、拼合规则与门禁定义见 [references/toolchain.md](references/toolchain.md)）：

   ```sh
   python3 "<skill目录>/scripts/init_toolchain.py"
   ```

   第 3 步退出码 3 时直接带 `--stacks <答案>` 运行，如 `--stacks uv bun`，不先空跑一次。`new` 模式复制工具链文件与工具链测试、拼出根 `justfile`、复制 `scripts/check_docs.py` 与 `scripts/with_lock.py`、追加 `.gitignore`、替换 `<待填 阶段3：…>` 标记并运行安装命令；`existing` 模式只补缺 `scripts/check_docs.py`、把各 stack 的依赖偏好补进 `docs/development/technology-stack.md`，不碰任何工具链文件。脚本不运行门禁，门禁在阶段 3。

   安装命令失败是唯一不中止流程的脚本失败：文件已落地，脚本返回 1 并打印恢复提示。告知用户安装缺少的宿主工具后在项目根目录运行 `just install`，不要重跑脚本（会判为 `existing` 而跳过安装）；继续阶段 2，阶段 3 把安装与 `gate-core` 记为未完成。

## 阶段 2：agent 文档工作

1. **复核 `AGENTS.md`**：同义节指内容是跨任务常驻约束，或是任务到文档的路由表，却用了别的标题。合并时保留模板标题（`## 常驻约束`、`## 按任务读取`），用户原有条目并入其下并保留措辞，删除用户的同义标题；若保留用户标题，下次脚本会再次追加模板节。其余用户自写的节不在此处处理：它们是第 3 步收敛的候选，按 [references/converge-docs.md](references/converge-docs.md#候选范围) 的约束类留下、细则类迁入正文。阶段 1 移除的 `## Agent skills` 节若含项目特有说明（如 tracker 的特殊约定），写进对应的 `docs/agents/` 文件，不放回 `AGENTS.md`。

   `CLAUDE.md` 存在时：其中的 `## Agent skills` 节按同样规则处理；其余内容按节并入 `AGENTS.md`，不丢弃，这些节随后与用户自写的节一起在第 3 步按约束类或细则类分流，不保留为独立节；最后让 `CLAUDE.md` 只保留一行 `@AGENTS.md`。`CLAUDE.md` 不存在时不创建，Claude Code 直接读取 `AGENTS.md`。

2. **填写 `初始化` 标记**：用阶段 1 收集的一句话描述填写仍带 `初始化` 标记的位置，AGENTS.md、README、GLOSSARY 从同一答案展开；展开只能用用户的答案与代码事实，不描述 setup-project 自己的执行步骤或产物（用户答案里提到的内容照用）。没有标记的位置不动：`AGENTS.md` 已有描述时保留原文，不用答案覆盖。其余 `<待填 时机：说明>` 标记保留，由项目迭代按 `AGENTS.md` 常驻约束逐步填写，不询问用户，不编造。

3. **收敛已有文档**：按 [references/converge-docs.md](references/converge-docs.md) 的两条命令列出候选：标准结构之外的文档，以及 `AGENTS.md` 里模板节之外的全部二级节（含第 1 步从 `CLAUDE.md` 并入的）；没有候选则跳过。有候选时先派只读子 agent 分类，再派可写子 agent 按分类表执行合并与迁移，主 agent 修正链接、登记索引、建票据、填可填标记。不 commit，用户提交前自行审阅工作区。

4. **从代码补写文档**：已有代码指阶段 1 之前就存在的源码，即 `existing` 模式，或 `new` 模式下脚手架之外的源码；只有阶段 1 生成的脚手架（示例模块、工具链测试、`scripts/` 下的检查与锁脚本、各 stack 的配置与锁文件）时视为空项目，跳过。有代码时按 [references/document-code.md](references/document-code.md) 派可写子 agent 读取代码与配置，填写架构总览与模块边界的 `首个模块` 类标记、按模板建模块页；`existing` 模式下同时填写剩余的 `阶段3` 类标记，并为阶段 1 列出的缺少 recipe 返回实现建议；主 agent 随后把脚本写入的"依赖政策"与 `AGENTS.md` 常驻约束对照，与约束冲突的偏好条目（如项目禁止 ORM 而清单推荐 `sqlalchemy`）删去并在报告说明。空项目跳过。

5. **补齐缺少的契约 recipe**（仅 `existing` 模式且项目有 justfile）：先用 `just --summary` 核对脚本列出的 recipe 确实不存在（脚本按文本匹配，`import` 进来的 recipe 看不到），再按 [references/toolchain.md](references/toolchain.md#命令契约) 和上一步的建议写入 justfile，用项目现有命令实现；`docs-check` 用阶段 1 补上的 `python3 scripts/check_docs.py` 实现；`check-toolchain` 不得使用会同步环境的命令，参考各 stack 的 `recipes.just`；没有对应能力的 recipe 写成非零退出并说明原因。不改动已有 recipe。脚本提示项目没有 justfile 时不创建，把提示写进报告。

## 阶段 3：统一验证与报告

1. **文档检查**：`new` 模式运行 `just docs-check`；`existing` 模式在项目根目录运行 `python3 scripts/check_docs.py`。

   本次 agent 改动造成的错误修复后重跑；其余错误原样报告。

2. **门禁**：`new` 模式运行 `just gate-core`，失败原样报告，不标记为通过；stack 为 none 时它会在 `check-toolchain` 处按设计失败，报告为"工具链未接入"，以 `docs-check` 的结果为准。`existing` 模式若本次补了 recipe，运行 `just --list` 确认 justfile 可解析；不运行项目自己的门禁。

3. **汇总报告**，一份覆盖全部阶段：
   - stack 与模式；创建、合并与跳过的文件；追加的 `.gitignore` 行。
   - `AGENTS.md` 追加与移除的节、合并的同义节。
   - 收敛结果：每个候选的动作与目标、保留登记清单、删除依据、更新的链接数。
   - 补写的模块页、已知差异、术语候选与 ADR 建议。
   - 补齐的 recipe。
   - 安装命令、文档检查、`gate-core` 的实际结果。
   - 仍保留的 `<待填>` 标记。
