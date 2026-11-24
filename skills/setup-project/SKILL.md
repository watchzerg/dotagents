---
name: setup-project
description: "Initialize a project from personal templates: Beads, standard docs structure, and a dev toolchain (any mix of uv, Node, Swift, or none) with gate-core and gate-full gates. Rerunnable: fills gaps, never overwrites. Use for /setup-project or requests to bootstrap a project or fill in its missing setup."
---

# 项目初始化

初始化目标是调用时当前工作目录所在的项目，脚本都在该目录运行；`<skill目录>` 指本 skill 的安装目录，只用于定位脚本与配套资源。

流程分四个阶段：只读检查 → 脚本落地 → agent 文档工作 → 统一验证与报告。用户要求初始化时按序执行全部阶段；只要求讨论时在阶段 0 之后停下，保持只读。脚本可重复运行，只补缺、不覆盖已有产物；脚本失败时报告错误并中止（唯一例外见阶段 1 第 5 步）。`references/` 下的文件在链接它的步骤到达时再读。全程不 commit，用户提交前自行审阅工作区。

## 阶段 0：前置检查（只读）

1. 当前目录是 Git 工作区的根目录。不在 Git 工作区时提醒用户先 `git init`，不代为执行。
2. `docs/agents/issue-tracker.md` 与 `docs/agents/domain.md` 存在。两者由 `setup-matt-pocock-skills` 写入；缺少任一时提醒用户先执行 `/setup-matt-pocock-skills` 再重新调用本 skill，不代为执行。

## 阶段 1：脚本落地

1. **Beads**：

   ```sh
   python3 "<skill目录>/scripts/init_beads.py"
   ```

   首次 `bd init` 会自动 Git commit，属于已确认行为。已有 `.beads` 时脚本改为 `bd bootstrap`，补齐新 clone 缺少的本地数据库。

2. **文档结构**（结构定义见 [references/docs-structure.md](references/docs-structure.md)）：

   ```sh
   python3 "<skill目录>/scripts/init_docs.py"
   ```

   脚本把 `templates/` 中缺失的文件复制到同名路径（只有空白的文件视为缺失），`AGENTS.md` 与 `docs/agents/testing.md` 按二级标题合并、缺的节追加。项目名取 `AGENTS.md` 的一级标题，没有则取目录名；用户明确给出别的名字时才加 `--name`。脚本会打印两样东西，记下供后续步骤使用：从 `AGENTS.md` 移除的 `## Agent skills` 节原文（阶段 2 第 1 步），以及仍含 `初始化` 标记的文件清单（第 4 步）。

3. **工具链判定**：

   ```sh
   python3 "<skill目录>/scripts/init_toolchain.py" --detect-only
   ```

   不写文件，只打印 stack 集合、模式（`new` 或 `existing`）与证据；`existing` 模式还列出 mise 配置缺少的契约 task，记下供阶段 2 使用。退出码 3 表示无法判定、需要用户选择，此时模式必然是 `new`。判定规则见 [references/toolchain.md](references/toolchain.md#stack-判定)。

4. **一次性提问**：用一次结构化提问收集下列答案，都不需要时不问：
   - 上一步打印的 `初始化` 标记清单不为空，且 `AGENTS.md` 一级标题后、第一个二级标题前没有项目描述时，问项目的一句话描述（自由文本）。
   - 第 3 步退出码 3 时，让用户多选 stack：uv、node、swift 可任意组合（swift 仅支持 macOS，非 macOS 上不提供该选项），没有预置 stack 选 none；题干附上脚本打印的证据。不替用户选。

   用户不给描述时保留 `初始化` 标记并在报告列出；用户不选 stack 时到此停止，报告已完成的步骤。

5. **工具链落地**（各 stack 落地的文件、拼合规则与门禁定义见 [references/toolchain.md](references/toolchain.md)）：

   ```sh
   python3 "<skill目录>/scripts/init_toolchain.py"
   ```

   第 3 步退出码 3 时直接带 `--stacks <答案>` 运行（如 `--stacks uv node`），不先空跑。`new` 模式落地工具链文件、根 `mise.toml` 与 `mise-tasks/`，替换 `<待填 阶段3：…>` 标记并运行安装命令；`existing` 模式不碰任何工具链文件，只补缺 `scripts/check_docs.py` 与 `scripts/with_lock.py`，并把依赖偏好补进 `docs/development/technology-stack.md`。脚本不运行门禁。

   安装命令失败是唯一不中止流程的脚本失败：文件已落地，脚本返回 1 并打印恢复提示。告知用户安装缺少的宿主工具后在项目根目录运行 `mise run install`，不要重跑脚本（会判为 `existing` 而跳过安装）；继续阶段 2，阶段 3 把安装与 `gate-core` 记为未完成。

## 阶段 2：agent 文档工作

1. **复核按节合并的文件**：`AGENTS.md` 里内容是跨任务常驻约束或任务到文档的路由表、却用了别的标题的节是同义节。把其条目原样并入模板标题（`## 常驻约束`、`## 按任务读取`）之下并删除用户的同义标题；留着用户标题，下次脚本会再追加模板节。`docs/agents/testing.md` 同理（如 `## 测试编写与变更` 并入 `## 编写与变更`）。其余用户自写的节留给第 3 步收敛。阶段 1 移除的 `## Agent skills` 节若含项目特有说明（如 tracker 的特殊约定），写进对应的 `docs/agents/` 文件，不放回 `AGENTS.md`。

   `CLAUDE.md` 存在时，其 `## Agent skills` 节按同样规则处理，其余各节直接作为第 3 步的候选，不先并入 `AGENTS.md`；第 3 步完成后 `CLAUDE.md` 只保留一行 `@AGENTS.md`（Claude Code 的导入写法）。`CLAUDE.md` 不存在时不创建。

2. **填写 `初始化` 标记**：用阶段 1 收集的一句话描述，或 `AGENTS.md` 已有的描述，展开仍带 `初始化` 标记的位置（`AGENTS.md`、README、GLOSSARY 从同一答案展开）。展开只用用户的答案与代码事实，不把两者拼成代码没有实现的能力（描述说“命令行使用”、代码只有库函数时，不写“可在命令行录入”）；不描述 setup-project 自己的步骤或产物，用户答案提到的除外。没有标记的位置不动，`AGENTS.md` 已有描述时保留原文。其余 `<待填 时机：说明>` 标记保留，由项目迭代按 `AGENTS.md` 常驻约束填写，不询问用户、不编造。

3. **收敛已有文档**：按 [references/converge-docs.md](references/converge-docs.md) 执行：把标准结构之外的文档、`AGENTS.md` 与 `CLAUDE.md` 里的用户自写节、`docs/research/` 下的验收记录，以及文档检查报出的已有页面收敛进标准结构。没有候选则跳过。

4. **从代码补写文档**：已有代码指阶段 1 之前就存在的源码：`existing` 模式，或 `new` 模式下脚手架之外的源码。只有阶段 1 生成的脚手架（示例模块、工具链测试、`scripts/` 下的检查与锁脚本、各 stack 的配置与锁文件）时视为空项目，跳过。第 3 步已填完全部 `首个模块` 与 `阶段3` 标记、模块页齐全且没有缺少的 task 时也跳过；报告写明跳过依据。

   有代码时按 [references/document-code.md](references/document-code.md) 派子 agent 填写架构文档与模块页。之后主 agent 把脚本写入的“依赖政策”与 `AGENTS.md` 常驻约束对照，删去冲突的偏好条目（如项目禁止 ORM 而清单推荐 `sqlalchemy`）并在报告说明。

5. **补齐缺少的契约 task**（仅 `existing` 模式且项目有 mise 配置）：按 [references/toolchain.md](references/toolchain.md#补齐契约-task) 写入第 3 步列出、第 4 步给出实现建议的 task。脚本提示项目没有 mise task 时不创建，把提示写进报告。

   然后主 agent 填写 `docs/development/workflow.md` 的 `## 命令与门禁`：按 `mise tasks` 与各 task 的实际用法写，不照搬契约；已有 task 与契约不一致（如 `test` 不接受参数）时写实际用法，差异列为票据候选。

## 阶段 3：统一验证与报告

1. **文档检查**：`new` 模式运行 `mise run docs-check`；`existing` 模式在项目根目录运行 `python3 scripts/check_docs.py`。本次 agent 改动造成的错误修复后重跑；其余错误原样报告。

2. **门禁**：`new` 模式运行 `mise run gate-core`，失败原样报告，不标记为通过；stack 为 none 时它按设计在 `check-toolchain` 处失败，报告为“工具链未接入”，以 `docs-check` 的结果为准。`existing` 模式不运行项目自己的 lint、构建与测试；本次补了 task 时运行 `mise tasks` 确认配置可解析，再单独运行新增的 `mise run check-toolchain` 与 `mise run docs-check`。

3. **汇总报告**，一份覆盖全部阶段：
   - stack 与模式；创建、合并与跳过的文件；追加的 `.gitignore` 行。
   - 阶段 2 各步的执行或跳过及依据。
   - `AGENTS.md` 追加与移除的节、合并的同义节。
   - 收敛结果：每个候选的动作与目标、保留登记清单、删除依据、更新的链接数。
   - 补写的模块页、已知差异、术语候选与 ADR 建议。
   - 补齐的 task。
   - 安装命令、文档检查、`gate-core` 的实际结果。`existing` 模式写“未运行（existing 模式不运行项目门禁）”，不预测会在哪一步失败；没有安装步骤（stack 为 none 或 `existing` 模式）时写“无安装命令”，不写“成功”。错误来自前置 skill 的产物（如 `docs/agents/` 里的链接）时注明来源，交用户处理。
   - 仍保留的 `<待填>` 标记。
   - 已决与裁决：有推荐做法的事项直接按推荐执行，列为已决并写明依据；只有备选各有依据、无法推荐的才列为裁决项，逐条写清涉及的文件与备选做法，不用项目外读者看不懂的简称。项目已有约定（如 ADR）与标准结构冲突时一律列为裁决项，两边都不动，默认推荐标准结构。
