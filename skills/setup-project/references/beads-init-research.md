# Beads 初始化行为研究快照

研究日期：2026-10-09。用途：为 `setup-project` 阶段 1 的方案讨论提供依据；本文不是已确认的执行规范，也未在真实项目运行初始化。

## 版本与证据范围

`steveyegge/beads` 已重定向至官方 `gastownhall/beads`。查询时最新稳定发布为 **v1.3.1**，发布于 2026-09-30 23:37:36 UTC；另有 2026-10-05 发布的 **v1.3.2-rc.1**，它是 prerelease，不作为本次稳定版本基线。v1.3.1 对应 commit 为 `c1c4b642ac1c08d8c828007a1c2f96e47e43ef7c`；以下行为均以该 commit 的源码为准，不混用 `main` 文档。[稳定发布](https://github.com/gastownhall/beads/releases/tag/v1.3.1)、[最新稳定发布 API](https://api.github.com/repos/gastownhall/beads/releases/latest)、[RC 发布](https://github.com/gastownhall/beads/releases/tag/v1.3.2-rc.1)、[tag 对应 commit](https://api.github.com/repos/gastownhall/beads/git/tags/89f02da95627111df8c3ab7c24ef3897eecaa570)

验证范围：读取官方发布 API、固定版本源码及官方测试；未执行 `bd init`，未完成真实 agent 工作流验收。

## 非交互与重复初始化

| 参数或状态 | v1.3.1 行为 |
| --- | --- |
| `--non-interactive` | 跳过交互提示；优先级高于环境变量与 TTY 检测。无显式 flag 时依次检查 `BD_NON_INTERACTIVE`、`CI=true/1`、stdin 是否为 TTY。 |
| `--quiet` | 抑制输出；不能替代非交互模式。角色提示分支不检查 `quiet`，所以有 TTY 时仍可能询问角色。 |
| 普通重复 `init` | 检测到已有数据库时中止，不自动重新初始化。 |
| `--init-if-missing` | 仅将“已有数据库”转成退出 0 的跳过，发生在后续目录写入、集成安装与 Git 提交之前；不会更新已有安装。读取失败、无效 metadata 等错误仍失败。 |
| 已有 `.beads/` 目录 | 目录存在本身不足以触发跳过；例如 metadata 声明 embedded、但没有 `embeddeddolt/<db>/.dolt` 时可继续初始化。 |
| 显式 `--prefix` / `--database` | 若已有 metadata 记录的数据库名与请求不匹配，`--init-if-missing` 仍报错；`--database` 优先。未知数据库名则允许跳过。 |

来源：[参数声明](https://github.com/gastownhall/beads/blob/c1c4b642ac1c08d8c828007a1c2f96e47e43ef7c/cmd/bd/init.go#L2307-L2330)、[非交互检测](https://github.com/gastownhall/beads/blob/c1c4b642ac1c08d8c828007a1c2f96e47e43ef7c/cmd/bd/init.go#L2958-L2984)、[早期已有数据保护](https://github.com/gastownhall/beads/blob/c1c4b642ac1c08d8c828007a1c2f96e47e43ef7c/cmd/bd/init.go#L786-L814)、[数据库检测](https://github.com/gastownhall/beads/blob/c1c4b642ac1c08d8c828007a1c2f96e47e43ef7c/cmd/bd/init.go#L2472-L2665)、[跳过与名称匹配](https://github.com/gastownhall/beads/blob/c1c4b642ac1c08d8c828007a1c2f96e47e43ef7c/cmd/bd/init.go#L2757-L2845)。

边界：server metadata 存在但本地 `dolt/` 不存在时，官方保护逻辑会查询 server；server 不可达或查询报错时也允许继续，视为可 bootstrap 的 clone。因此不能把官方参数解释为“只要存在任何 `.beads` 状态都绝不修改”。若个人初始化流程要求保护任何已有 `.beads/`，需要单独讨论更严格的前置规则。[server 检测分支](https://github.com/gastownhall/beads/blob/c1c4b642ac1c08d8c828007a1c2f96e47e43ef7c/cmd/bd/init.go#L2556-L2593)

## 角色与 JSONL

- `--role` 仅接受 `maintainer` / `contributor`，用于无提示设置本仓库 `git config beads.role`。未指定角色且非交互时，已有角色保留；没有角色时默认 `maintainer`。[角色校验](https://github.com/gastownhall/beads/blob/c1c4b642ac1c08d8c828007a1c2f96e47e43ef7c/cmd/bd/init.go#L590-L611)、[角色设置](https://github.com/gastownhall/beads/blob/c1c4b642ac1c08d8c828007a1c2f96e47e43ef7c/cmd/bd/init.go#L1859-L1898)
- 交互模式会询问是否贡献他人仓库；默认否，即 `maintainer`；选择是会运行 contributor wizard。显式 `--contributor` 和 `--team` 都需要交互，与非交互模式组合会早期失败；`--role contributor` 本身不运行该 wizard。[角色提示](https://github.com/gastownhall/beads/blob/c1c4b642ac1c08d8c828007a1c2f96e47e43ef7c/cmd/bd/init.go#L3010-L3059)、[wizard 分支](https://github.com/gastownhall/beads/blob/c1c4b642ac1c08d8c828007a1c2f96e47e43ef7c/cmd/bd/init.go#L1900-L1935)
- 检测到 `upstream` remote 的 fork 时，即便非交互也可能自动配置 contributor routing、创建 `~/.beads-planning` 仓库、把角色改为 `contributor`；显式 `--role maintainer` 会阻止该 routing 自动配置。不过 fork 的 `.git/info/exclude` 自动配置仍是另一个独立分支。[fork routing](https://github.com/gastownhall/beads/blob/c1c4b642ac1c08d8c828007a1c2f96e47e43ef7c/cmd/bd/init_contributor.go#L265-L363)、[fork exclude](https://github.com/gastownhall/beads/blob/c1c4b642ac1c08d8c828007a1c2f96e47e43ef7c/cmd/bd/init.go#L1993-L2021)
- JSONL auto-export 默认关闭；交互模式才询问是否开启，默认否；非交互保留默认。启用后的目标默认为 `.beads/issues.jsonl`，`export.git-add` 也默认关闭。JSONL 用于 viewer / interchange / issue 迁移；Dolt remote 与 backup 承担同步和备份。[auto-export 默认配置](https://github.com/gastownhall/beads/blob/c1c4b642ac1c08d8c828007a1c2f96e47e43ef7c/internal/config/config.go#L326-L333)、[模板说明](https://github.com/gastownhall/beads/blob/c1c4b642ac1c08d8c828007a1c2f96e47e43ef7c/cmd/bd/init_templates.go#L79-L103)、[init 提示](https://github.com/gastownhall/beads/blob/c1c4b642ac1c08d8c828007a1c2f96e47e43ef7c/cmd/bd/init.go#L2024-L2042)

## 初始化副作用

- 创建 `.beads/`、数据库与 metadata/config/version 文件，补齐 `.beads/.gitignore` 和根 `.gitignore`；默认路径且当前不在 Git 仓库时还会 `git init`。数据库已有数据或 remote history 会触发对应保护、bootstrap 或拒绝分支。[目录与 Git 初始化](https://github.com/gastownhall/beads/blob/c1c4b642ac1c08d8c828007a1c2f96e47e43ef7c/cmd/bd/init.go#L1026-L1135)、[remote 安全规则](https://github.com/gastownhall/beads/blob/c1c4b642ac1c08d8c828007a1c2f96e47e43ef7c/cmd/bd/init_safety.go#L112-L167)
- 默认安装或更新 Git hooks 到 `.beads/hooks/`，设置本地 `core.hooksPath`；`--skip-hooks` 关闭这一项。管理 `pre-commit`、`post-merge`、`pre-push`、`post-checkout`、`prepare-commit-msg`，初始化时无需用户回答安装提示。[默认安装](https://github.com/gastownhall/beads/blob/c1c4b642ac1c08d8c828007a1c2f96e47e43ef7c/cmd/bd/init.go#L2044-L2079)、[hook 列表](https://github.com/gastownhall/beads/blob/c1c4b642ac1c08d8c828007a1c2f96e47e43ef7c/cmd/bd/hooks.go#L22-L24)、[hooksPath 写入](https://github.com/gastownhall/beads/blob/c1c4b642ac1c08d8c828007a1c2f96e47e43ef7c/cmd/bd/hooks.go#L1298-L1319)
- 默认创建或更新 `AGENTS.md`，并安装 Claude、Codex、Cursor 项目集成，包括共享 `.agents/skills/beads`。`--skip-agents` 同时关闭这些生成；不影响 Git hooks。[集成入口](https://github.com/gastownhall/beads/blob/c1c4b642ac1c08d8c828007a1c2f96e47e43ef7c/cmd/bd/init.go#L2091-L2148)、[Codex 项目安装](https://github.com/gastownhall/beads/blob/c1c4b642ac1c08d8c828007a1c2f96e47e43ef7c/cmd/bd/setup/codex.go#L81-L102)、[Cursor 共享 skill](https://github.com/gastownhall/beads/blob/c1c4b642ac1c08d8c828007a1c2f96e47e43ef7c/cmd/bd/setup/cursor.go#L155-L178)
- **会自动 Git 暂存并提交**：非 stealth、Git 仓库、local storage 条件下，暂存 `.beads/`、已有 agent 文件、`.claude/settings.json`、`CLAUDE.md`、整个 `.agents` / `.codex` / `.cursor` 和 `.gitignore`，再执行无 pathspec 的 `git commit`，bootstrap commit 绕过 Git hooks。**`--skip-agents`、`--skip-hooks`、`--quiet`、`--non-interactive` 均不关闭它。** 由无 pathspec 推断：先前已暂存的其他变更也可能进入该提交；源码并未隔离 index。[完整暂存与提交分支](https://github.com/gastownhall/beads/blob/c1c4b642ac1c08d8c828007a1c2f96e47e43ef7c/cmd/bd/init.go#L2150-L2205)
- 稳定版本没有单独的 `--no-commit` / `--skip-commit` 初始化参数。`--stealth` 会抑制上述 Git 提交，但同时隐藏 `.beads/`、改用 `.git/info/exclude`、跳过 hooks/agent 生成并持久化 `no-git-ops: true`；这不是单纯关闭提交，不宜为避开提交擅自选用。[参数集合](https://github.com/gastownhall/beads/blob/c1c4b642ac1c08d8c828007a1c2f96e47e43ef7c/cmd/bd/init.go#L2307-L2373)、[stealth 行为](https://github.com/gastownhall/beads/blob/c1c4b642ac1c08d8c828007a1c2f96e47e43ef7c/cmd/bd/init_stealth.go#L16-L61)、[no-git-ops 持久化](https://github.com/gastownhall/beads/blob/c1c4b642ac1c08d8c828007a1c2f96e47e43ef7c/cmd/bd/init.go#L1798-L1805)

## 对后续方案的建议

讨论中的普通个人项目初始化，可把 `--non-interactive`、`--init-if-missing`、`--role maintainer`、`--skip-agents` 作为候选参数；Git hooks 是否安装需单独确定，关闭时追加 `--skip-hooks`。保留输出可观察非致命 warning。这个组合仍会自动 Git commit，因此在确认提交策略前，不能把它描述为“仅初始化配置，保持未提交”。JSONL export 若没有具体 viewer 需求，保持默认关闭即可。

自动 Git commit、任何已有 `.beads/` 是否直接跳过、Git hooks 安装与 Beads agent 集成 ownership，仍需在阶段 1 讨论后确定；本快照未将这些选择写入 `SKILL.md`。

## 补充：Git 忽略规则与 hooks

`.beads/.gitignore` 排除 Dolt 数据目录、日志、锁、凭据、`backup/` 等，并未忽略整个 `.beads/`。模板明确保留 `config.yaml` 和 `metadata.json` 的 Git 跟踪；`.gitignore` 本身、`hooks/` 和 `issues.jsonl` 也没有被该模板排除。因此 `git add .beads/` 仍能暂存配置等文件，初始化的自动提交与这些忽略规则并不冲突。[官方模板](https://github.com/gastownhall/beads/blob/v1.3.1/cmd/bd/doctor/gitignore.go#L11-L99)

已在临时 Git 仓库用官方模板与空白示例文件验证：`git add .beads/` 暂存 `.gitignore`、`config.yaml`、`metadata.json`、`hooks/pre-commit`、`issues.jsonl`；数据库示例和日志示例被忽略。此验证没有运行 Beads 或创建 commit。

所有 Beads hooks 都先尝试运行对应的 chained hook。额外功能如下：[hook 实现](https://github.com/gastownhall/beads/blob/v1.3.1/cmd/bd/hooks.go#L1498-L1820)

| Hook | Beads 额外行为 |
| --- | --- |
| `pre-commit` | `export.auto=true` 且暂存区存在 `.beads` 路径等条件满足时导出 JSONL；仅在 `export.git-add=true` 且允许 Git 操作时自动暂存导出文件。 |
| `post-merge` | `import.auto=true`、无 Dolt sync remote、JSONL 存在且非空时导入 JSONL。 |
| `post-checkout` | 切换分支时执行与 post-merge 相同的条件导入；检出单个文件时不执行。 |
| `pre-push` | 仅运行 chained hook，没有额外的 Dolt push 或 JSONL 导出。 |
| `prepare-commit-msg` | 设置了 `BD_ACTOR` 时添加 `Executed-By:` trailer；跳过 merge 和已存在的 trailer。 |

`export.auto` 默认 false，但 `import.auto` 默认 true；JSONL interaction audit 与 events export 默认也关闭。若初始化约定为“不自动读写 JSONL”，可在新项目明确设置 `export.auto=false`、`import.auto=false`，并保持 `audit.enabled=false`、`events-export=false`。跳过 hooks 本身不能关闭写命令后的自动导出；反过来，安装 hooks 也不会强制开启导出。[配置默认值](https://github.com/gastownhall/beads/blob/v1.3.1/internal/config/config.go#L217-L338)、[导出说明](https://github.com/gastownhall/beads/blob/v1.3.1/cmd/bd/init_templates.go#L63-L101)

针对不使用 JSONL 工作流、也不需要 Beads commit trailer 的新项目，建议初始化追加 `--skip-hooks`。这是待确认方案，不卸载任何现有项目 hooks，也不改变上述首次初始化自动 Git commit 的行为。
