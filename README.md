# dotagents

集中维护个人用户级 `AGENTS.md` 和 skills。源文件保存在本仓库，通过软链接加载到用户目录。仓库的分层与维护规则见 [AGENTS.md](AGENTS.md)。

## clone 后怎么用

1. 将本仓库 clone 到准备长期保留的位置，进入仓库目录。
2. 确保 `python3` 为 3.14+（setup 只用标准库）。系统自带版本通常不满足：用系统包管理器安装 mise（macOS：`brew install mise`；Ubuntu：添加 mise 官方 apt 源后 `sudo apt install mise`），由 mise 提供 uv（`mise use -g uv@0.13`），再运行 `uv python install 3.14 --default`。
3. 在本仓库中打开 agent harness，调用 `/setup-dotagents`；harness 发现不了该 skill 时，直接执行脚本（可从任意目录用绝对路径调用）：

   ```sh
   python3 .agents/skills/setup-dotagents/scripts/setup.py
   ```

4. 开启新的 Claude Code、Antigravity CLI 或 Grok 会话（Antigravity CLI 中也可执行 `/skills reload`），验证个人规则和 skills 已加载。
5. 切换到目标项目，先执行 `/setup-matt-pocock-skills`，再执行 `/setup-project`；之后按需使用下表中的 skills。用 `/acceptance` 验收有 web 界面的项目时，需要 Chrome 已打开且当前 harness 的原生浏览器方案已连接（Claude Code 为 Claude in Chrome 扩展）。

setup 先检查全部入口：已有正确链接跳过，可以重复执行；遇到已有文件、目录或指向其他位置的链接时报告冲突并退出，不创建任何链接、不覆盖。创建中途出现权限或 I/O 错误时，已创建的链接会保留，解决后重新执行即可。`/setup-dotagents` 还会检查当前会话是否提供 `setup-matt-pocock-skills`，未发现时建议安装 Matt Pocock 的 skill 套件；该检查不影响 setup 结果，直接运行脚本时不执行。

之后在原位置更新仓库，链接直接指向更新后的文件；新增 skill 后再执行一次 setup。移动或删除 checkout 会使链接失效，移动后需先处理旧链接冲突再执行 setup。

## 当前 skills

| 调用 | 作用 | 使用范围 |
| --- | --- | --- |
| [`/setup-dotagents`](.agents/skills/setup-dotagents/SKILL.md) | 把本仓库的个人规则和 skills 链接到用户环境，检查并补齐加载入口。 | 仅本仓库 |
| [`/commit`](skills/commit/SKILL.md) | 把现有变更提交为一个本地 commit；默认包含全部未忽略变更，不附署名行，不测试、不 push。 | 用户级 |
| [`/docs-audit`](skills/docs-audit/SKILL.md) | 文档漂移审计：对照源码核对正文（默认随机抽页，传基准时核对改动命中的页面），文档错就地修正，其余转票据。 | 用户级 |
| [`/optimize`](skills/optimize/SKILL.md) | 项目优化流水线：`arch`、`docs`、`logs` 三个主题按规则表调研，命中项经 spec、拆票、实施、review、门禁后合入，只在建 spec 前停一次。要求目标项目有 Beads 与 `gate-core`、`gate-full`。 | 用户级 |
| [`/prune-tests`](skills/prune-tests/SKILL.md) | 按项目的 core/full 分层大幅精简测试，跑无筛选门禁验证并写回保留范围。 | 用户级 |
| [`/dedupe-images`](skills/dedupe-images/SKILL.md) | 图片库去重：清理非图片杂项，按内容哈希找出重复的图片与目录；有把握的移入回收站，拿不准的整理成案例由用户确认。不做相似图片识别；需要 macOS 15+ 或 Linux。 | 用户级 |
| [`/setup-project`](skills/setup-project/SKILL.md) | 初始化或补齐目标项目的 Beads、标准化文档结构与工具链（uv、Node、Swift 任意组合）及 `gate-core` / `gate-full` 门禁，并收敛已有文档。 | 用户级 |
| [`/acceptance`](skills/acceptance/SKILL.md) | 在本机真实环境按行为文档完整验收功能，偏差就地修复并重跑，直到零修复全量通过后写验收记录。推荐配合 `/goal /acceptance 直到打印"验收完成"，最多 80 轮` 运行。 | 用户级 |

“用户级”指 setup 后在任意项目可用。第三方 skills 由原安装工具管理，不纳入本仓库，也不由 setup 安装。

## 加载关系

源文件路径相对于当前 checkout；实际建立的软链接使用绝对路径。设置了 `CLAUDE_CONFIG_DIR` 时，表中的 `~/.claude` 改用该路径。

| 用户目录入口 | 软链接目标 |
| --- | --- |
| `~/.agents/AGENTS.md` | `global/AGENTS.md` |
| `~/.claude/CLAUDE.md` | `global/AGENTS.md` |
| `~/.gemini/AGENTS.md` | `global/AGENTS.md` |
| `~/.grok/AGENTS.md` | `global/AGENTS.md` |
| `~/.agents/skills/<name>` | `skills/<name>` |
| `~/.claude/skills/<name>` | `~/.agents/skills/<name>` |
| `~/.gemini/config/skills/<name>` | `~/.agents/skills/<name>` |

- `~/.agents/AGENTS.md` 是通用规则入口。Grok 只读 `~/.grok/` 下的规则，因此单独链接；它也读 `~/.claude/CLAUDE.md`，但按真实路径去重，只加载一次。Grok 直接读 `~/.agents/skills`，不另建 skill 链接。
- `skills/` 下每个含 `SKILL.md` 的目录逐个链接，经 `~/.agents/skills` 中转（与 `npx skills` 等工具的安装位置一致）。用户级 skills 父目录保持普通目录，已有的第三方 skills、系统 skills 和插件缓存不受影响。
- Linux 上文件名区分大小写，入口名须保持 `AGENTS.md`、`CLAUDE.md` 原样。

## 仓库结构

```text
dotagents/
├── AGENTS.md                       # 本仓库的维护规则（不安装为全局规则）
├── README.md                       # 使用说明、加载入口和链接关系
├── global/AGENTS.md                # 跨项目生效的个人规则，按上表安装
├── .agents/skills/setup-dotagents/ # 项目级安装 skill 与链接脚本
├── .claude/skills -> ../.agents/skills # 软链接，供 Claude Code 发现项目级 skill
├── skills/                         # 用户级个人 skills，按目录软链接，只含运行时内容
│   ├── acceptance/                 # 真实环境验收（清单与账本规则、环境契约规则、报告模板）
│   ├── commit/                     # 本地提交
│   ├── dedupe-images/              # 图片库去重（clean/plan/show/apply/apply-decisions 脚本）
│   ├── docs-audit/                 # 文档漂移审计
│   ├── optimize/                   # 项目优化流水线（主题规则表与 spec、拆票、实施的参考文件）
│   ├── prune-tests/                # 测试精简
│   └── setup-project/              # 项目初始化（Beads、文档结构模板、工具链模板）
├── docs/testing.md                 # 本仓库测试的保留范围，删改测试前阅读
├── docs/skills/<name>/             # 各 skill 的设计说明与调研，维护者阅读
├── tests/                          # 安装器测试与各 skill 脚本测试（tests/<name>/）
├── mise.toml / mise.lock           # uv 版本 line 与精确版本，以及开发任务
├── mise-tasks/                     # 需要转发多段参数的 mise 文件任务（fmt）
├── .python-version                 # 开发 Python 版本 line
├── pyproject.toml                  # 开发依赖与检查配置
└── uv.lock                         # 开发依赖锁文件
```

仓库不保存认证信息、会话数据或运行缓存。

## 开发与验证

仅在维护脚本或运行检查时需要开发环境（应用个人配置不需要）。用系统包管理器装好 mise 后：

```sh
mise run install
mise run gate-full
```

`mise run` 会按需安装 `mise.toml` 钉定的 uv 并放上 PATH。

| 命令 | 用途 |
| --- | --- |
| `mise tasks` | 列出可用任务 |
| `mise run check-toolchain` | 核对项目 Python 版本 line，不下载或安装 |
| `mise run lint` / `mise run typecheck` | 检查 Python 格式、lint 和类型 |
| `mise run fmt` | 格式化并修复可自动修复的 lint；默认作用于整个仓库，可传路径 |
| `mise run test` | 运行全部 pytest 测试；追加参数传给 pytest，如 `mise run test -k name` |
| `mise run gate-full` | 并行执行工具链、diff 格式、lint、类型检查及全部测试，忽略筛选参数 |
| `mise run e2e-setup-project` | 在临时项目上用 headless Claude Code 真实执行 `/setup-project` 并检查产物；不属于门禁，见 [docs/skills/setup-project/e2e.md](docs/skills/setup-project/e2e.md) |

测试与验证规则见 [AGENTS.md](AGENTS.md) 的“测试与验证”。
