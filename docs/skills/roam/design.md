# roam 设计说明

换机交接：离开旧机器时 `/roam push`，到新机器后 `/roam pull`，批量处理一个总目录下的全部项目。

## 关键决策（2026-11-24）

- **确定性动作全在脚本里**：`scripts/roam.py` 负责扫描、状态判断、push、pull、冲突回滚，输出 JSON；agent 只负责写提交信息、请用户确认、转述汇总。这样行为稳定，也能用临时 bare 仓库测试。
- **push 前汇总确认一次**：自动提交可能把半成品、凭据或该忽略的大文件带进去，所以先列出各项目改动摘要、逐个列出未跟踪文件，用户确认一次后再提交。提交信息与 `/commit` 一致：不附署名行。
- **冲突只回滚、不合并**：pull 时能快进就快进；当前分支和远端分叉时试 `git rebase`，一有冲突立即 `rebase --abort`，跳过并报告。非当前分支的 main 只快进（直接移动引用、不检出）。`bd dolt pull` 不带 `--strategy`，冲突时由 bd 自行中止。
- **pull 时工作区有改动就跳过 git 部分**：新机器上有未提交改动，说明上次离开时漏推了；stash 或强行合并会掩盖这个信号。
- **git 与 Dolt 各自独立执行**：git 部分被跳过或失败时，Dolt 照常 push/pull。两者数据互不依赖，单独失败也不会互相污染。
- **只处理当前分支和 main**（没有 main 时用 master）：其他本地分支只在汇总里提醒（有未推提交或没有 upstream），不推、不拉。
- **beads 状态在 git 步骤之后再判断**：`.beads/` 配置随 git 走，新机器上可能是这次 pull 才拉下来；数据库（embedded Dolt）不进 git，没有本地库时改为 `bd bootstrap --yes`，避免 `bd init` 另起一个和远端分叉的空库。
- **总目录查找顺序**：参数 → 当前路径里名为 `projects` 的最近祖先目录 → `~/projects` → `/data/projects`。只扫第一层子目录。
- **不处理新机器缺少的项目**：clone 哪些项目由调用者自己保证。
- **只允许用户调用**：会推送到外部，设 `disable-model-invocation: true`。
- **pull 后只提醒、不安装**：依赖或工具链文件有变化时提醒重新安装；dotagents 的 `skills/*/SKILL.md` 有变化时提醒重跑 setup-dotagents。

## 待验收

- 尚未在真实 agent 下完整跑过 `/roam push` 的确认与提交环节。
- `bd dolt pull` 遇到真实冲突时的中止行为只依据 `bd dolt pull --help`（bd 1.3.4），未实测。
- 需要凭据的 Dolt 远端（如 https）在新机器上首次 `bd bootstrap` 时的交互未验证；脚本设了 `BD_NON_INTERACTIVE=1`，需要交互时会以失败报告。
