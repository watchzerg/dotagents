# dotagents

集中维护个人用户级 `AGENTS.md` 和 skills。源文件保存在本仓库，通过软链接加载到用户目录。

## clone 后怎么用

1. 将本仓库 clone 到准备长期保留的位置，进入仓库目录。
2. 确保宿主已有 just 和 Bash。macOS 自带 Bash；缺少 just 时运行 `brew install just`（需先安装 Homebrew）。
3. 在本仓库中打开 Codex，调用：

   ```text
   $setup-dotagents
   ```

   也可以直接在仓库目录的终端执行：

   ```sh
   just setup
   ```

4. 完成后开启新的 Codex 会话，验证个人规则和 skills 已加载。

调用链为 `$setup-dotagents` → `just setup` → 链接脚本。日常应用配置只需执行 setup，不需要安装 uv、Python 开发依赖或运行 `just install`。

setup 会自动定位当前 checkout，建立并核验软链接。已有正确链接会跳过，可以重复执行；遇到已有文件、目录或指向其他位置的链接时，会在创建前报告冲突，不自动覆盖。创建过程中若发生权限或 I/O 错误，可能保留已创建的链接，解决问题后重新执行即可。

以后在原位置更新仓库内容，已有链接会直接指向更新后的文件；新增 skill 后再执行一次 setup。请保留 checkout：移动或删除它会使链接失效；移动后需先处理旧链接冲突，再执行 setup。

## 当前 skills

| 调用 | 作用 | 使用范围 |
| --- | --- | --- |
| [`$setup-dotagents`](.agents/skills/setup-dotagents/SKILL.md) | 将当前仓库的个人规则和 skills 应用到用户环境，检查并补齐加载入口。 | 仅本仓库 |
| [`$commit`](skills/commit/SKILL.md) | 将当前仓库的现有变更提交为一个本地 commit；默认包含全部未忽略变更，不自动测试或 push。 | setup 后用户级可用 |
| [`$prune-tests`](skills/prune-tests/SKILL.md) | 大幅精简测试，保留核心规则与主要流程的代表性用例，删除重复和非核心测试并验证结果。 | setup 后用户级可用 |

第三方 skills 由原安装工具管理，不纳入本仓库，也不由 setup 安装。

`$setup-dotagents` 完成链接后，还会检查当前会话是否提供 `setup-matt-pocock-skills`。未发现时会建议安装 Matt Pocock 的 skill 套件，因为 dotagents 后续很多能力会围绕该套件构建。此检查不影响 setup 成功，也不自动安装；仅检查会话可用列表，不代表系统安装清单。直接运行 `just setup` 只处理软链接，不执行这项会话检查。

## 加载关系

以下源文件路径相对于当前 checkout；实际建立的软链接使用绝对路径。

| 用户目录入口 | 软链接目标 |
| --- | --- |
| `~/.agents/AGENTS.md` | `global/AGENTS.md` |
| `~/.codex/AGENTS.md` | `~/.agents/AGENTS.md` |
| `~/.agents/skills/commit` | `skills/commit` |
| `~/.codex/skills/prune-tests` | `skills/prune-tests` |

设置了 `CODEX_HOME` 时，表中的 `~/.codex` 改用该绝对路径。`prune-tests` 沿用上述入口；`skills/` 下其他含 `SKILL.md` 的目录自动链接到 `~/.agents/skills/<name>`。

skill 逐个链接，用户级 skills 父目录保持为普通目录，已有第三方 skills、系统 skills 和插件缓存保留。项目级 `setup-dotagents` 不安装到用户目录。

## 仓库结构

```text
dotagents/
├── AGENTS.md                       # 本仓库的维护规则
├── global/AGENTS.md                # 跨项目生效的个人规则
├── .agents/skills/setup-dotagents/ # 项目级安装 skill 与脚本
├── skills/                        # 用户级个人 skills
│   ├── commit/
│   └── prune-tests/
├── tests/                         # 安装行为测试与 skill 格式校验
├── justfile
├── .python-version
├── pyproject.toml
└── uv.lock
```

在本仓库修改源文件并通过 Git 管理；根目录 `AGENTS.md` 不安装为全局规则。仓库不保存认证信息、会话数据或运行缓存。

## 开发与验证

仅在维护脚本或运行检查时准备开发环境：

```sh
brew install uv just
just install
just gate-full
```

宿主 uv/just 由 Homebrew 管理，项目 Python 补丁版本由 `.python-version` 固定，开发依赖由 `uv.lock` 锁定。`just install` 安装开发环境，`just setup` 应用个人配置。

| 命令 | 用途 |
| --- | --- |
| `just` | 列出可用命令 |
| `just check-toolchain` | 检查宿主工具和项目 Python 版本 |
| `just lint` / `just typecheck` | 检查 Python 格式、lint 和类型 |
| `just fmt` | 格式化并修复可自动修复的 lint |
| `just test` | 运行全部 pytest 测试，包括 skill 格式校验 |
| `just validate-skill` | 单独校验全部个人及项目级 skills |
| `just gate-full` | 顺序执行工具链、diff 格式、lint、类型检查及全部测试 |

测试自动发现 `tests/` 与 `skills/` 中的 `test_*.py`、`*_test.py`。skill 格式校验覆盖 `skills/` 和 `.agents/skills/`，依赖宿主 `~/.codex/skills/.system/skill-creator/scripts/quick_validate.py`；缺失时明确失败，不自动下载或跳过。自动检查不代表真实 agent 工作流已完成验收。
