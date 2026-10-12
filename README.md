# dotagents

集中维护个人用户级 `AGENTS.md` 和 skills。源文件保存在本仓库，通过软链接加载到用户目录。

## clone 后怎么用

1. 将本仓库 clone 到准备长期保留的位置，进入仓库目录。
2. 确保 `python3` 为 3.14+；setup 仅使用标准库。macOS 自带版本不满足，可用 `brew install uv && uv python install 3.14 --default` 或 `brew install python@3.14` 安装。
3. 在本仓库中打开 Claude Code，调用：

   ```text
   /setup-dotagents
   ```

   也可以直接在仓库目录的终端执行：

   ```sh
   python3 .claude/skills/setup-dotagents/scripts/setup.py
   ```

4. 完成后开启新的 Claude Code 会话，验证个人规则和 skills 已加载。
5. 切换到目标项目，先执行 `/setup-matt-pocock-skills`，再调用 `/setup-project` 初始化该项目；之后在各项目中按需使用 `/commit`、`/prune-tests` 等。

调用链为 `/setup-dotagents` → Python 链接脚本。脚本根据自身位置定位 checkout，也可从其他目录通过脚本绝对路径调用。日常应用配置不依赖 just、uv、第三方 Python 包或项目 `.venv`。

setup 会自动定位当前 checkout，建立并核验软链接。已有正确链接会跳过，可以重复执行；遇到已有文件、目录或指向其他位置的链接时，会在创建前报告冲突，不自动覆盖。创建过程中若发生权限或 I/O 错误，可能保留已创建的链接，解决问题后重新执行即可。

以后在原位置更新仓库内容，已有链接会直接指向更新后的文件；新增 skill 后再执行一次 setup。请保留 checkout：移动或删除它会使链接失效；移动后需先处理旧链接冲突，再执行 setup。

## 当前 skills

| 调用 | 作用 | 使用范围 |
| --- | --- | --- |
| [`/setup-dotagents`](.claude/skills/setup-dotagents/SKILL.md) | 将当前仓库的个人规则和 skills 应用到用户环境，检查并补齐加载入口。 | 仅本仓库 |
| [`/commit`](skills/commit/SKILL.md) | 将当前仓库的现有变更提交为一个本地 commit；默认包含全部未忽略变更，不附署名行，不自动测试或 push。 | setup 后用户级可用 |
| [`/prune-tests`](skills/prune-tests/SKILL.md) | 大幅精简测试，保留核心规则与主要流程的代表性用例，删除重复和非核心测试并验证结果。 | setup 后用户级可用 |
| [`/setup-project`](skills/setup-project/SKILL.md) | 检查 Matt skills 设置后，用 Python 脚本初始化 Beads、按模板建立标准化文档结构、按 stack 组合（uv、Bun、Swift）初始化工具链与 gate-core / gate-full 门禁；再由 agent 收敛已有文档、从代码补写模块页，最后统一运行文档检查与门禁。 | setup 后用户级可用 |

第三方 skills 由原安装工具管理，不纳入本仓库，也不由 setup 安装。

`/setup-dotagents` 完成链接后，还会检查当前会话是否提供 `setup-matt-pocock-skills`。未发现时会建议安装 Matt Pocock 的 skill 套件，因为 dotagents 后续很多能力会围绕该套件构建。此检查不影响 setup 成功，也不自动安装；仅检查会话可用列表，不代表系统安装清单。直接运行 `setup.py` 只处理软链接，不执行这项会话检查。

## 加载关系

以下源文件路径相对于当前 checkout；实际建立的软链接使用绝对路径。

| 用户目录入口 | 软链接目标 |
| --- | --- |
| `~/.claude/CLAUDE.md` | `global/AGENTS.md` |
| `~/.agents/skills/<name>` | `skills/<name>` |
| `~/.claude/skills/<name>` | `~/.agents/skills/<name>` |

设置了 `CLAUDE_CONFIG_DIR` 时，表中的 `~/.claude` 改用该绝对路径。`skills/` 下每个含 `SKILL.md` 的目录都按 `<name>` 建立上述两级链接；skills 经 `~/.agents/skills` 中转，与 `npx skills` 等工具的安装位置保持一致。

skill 逐个链接，用户级 skills 父目录保持为普通目录，已有第三方 skills、系统 skills 和插件缓存保留。项目级 `setup-dotagents` 不安装到用户目录。

## 仓库结构

```text
dotagents/
├── AGENTS.md                       # 本仓库的维护规则
├── README.md                       # 使用说明、加载入口和链接关系
├── global/AGENTS.md                # 跨项目生效的个人规则，安装为用户级 CLAUDE.md
├── .claude/skills/setup-dotagents/ # 项目级安装 skill 与链接脚本
├── skills/                         # 用户级个人 skills，按目录软链接，只含运行时内容
│   ├── commit/                     # 本地提交
│   ├── prune-tests/                # 测试精简
│   └── setup-project/              # 项目初始化（Beads、文档结构模板、工具链模板）
├── docs/skills/<name>/             # 各 skill 的设计说明与调研，维护者阅读
├── tests/                          # 安装器测试与各 skill 脚本测试（tests/<name>/）
├── justfile                        # 安装、检查和测试入口
├── .python-version                 # uv 管理的开发 Python 补丁版本
├── pyproject.toml                  # 开发依赖与检查配置
└── uv.lock                         # 开发依赖锁文件
```

在本仓库修改源文件并通过 Git 管理；根目录 `AGENTS.md` 不安装为全局规则。仓库维护、安装器、用户级内容三层的职责划分及维护约束见 [AGENTS.md](AGENTS.md)。仓库不保存认证信息、会话数据或运行缓存。

## 开发与验证

仅在维护脚本或运行检查时准备开发环境：

```sh
brew install uv just
just install
just gate-full
```

宿主 uv/just 由 Homebrew 管理，项目 Python 补丁版本由 `.python-version` 固定，开发依赖由 `uv.lock` 锁定。`just install` 安装开发环境；应用个人配置直接运行 setup skill 的 Python 脚本。

| 命令 | 用途 |
| --- | --- |
| `just` | 列出可用命令 |
| `just check-toolchain` | 检查宿主工具和项目 Python 版本 |
| `just lint` / `just typecheck` | 检查 Python 格式、lint 和类型 |
| `just fmt` | 格式化并修复可自动修复的 lint |
| `just test` | 运行全部 pytest 测试 |
| `just gate-full` | 顺序执行工具链、diff 格式、lint、类型检查及全部测试 |
| `just e2e-setup-project` | 在临时项目上用 headless Claude Code 真实执行 `/setup-project` 并检查产物；不属于门禁，见 [docs/skills/setup-project/e2e.md](docs/skills/setup-project/e2e.md) |

测试自动发现 `tests/` 中的 `test_*.py`、`*_test.py`；`skills/` 只含运行时内容，不放测试。自动检查不代表真实 agent 工作流已完成验收。
