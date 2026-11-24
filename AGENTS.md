# dotagents

## 核心目标

集中维护和版本管理个人用户级 `AGENTS.md` 与个人 skills。本仓库是源文件的唯一维护位置，用户目录通过软链接加载，避免多份副本漂移。使用步骤、链接映射与目录树见 `README.md`。

## 三层结构

修改任何文件前先确认它属于哪一层：

| 层 | 内容 | 运行位置 | 作用 |
| --- | --- | --- | --- |
| 仓库维护 | 根目录 `AGENTS.md`、`docs/`、`tests/`、`mise.toml`、`mise-tasks/`、`pyproject.toml` | 仅本 checkout，需要开发环境 | 约束并验证本仓库自身的开发 |
| 安装器 | `.agents/skills/setup-dotagents/`（`.claude/skills` 是指向 `.agents/skills` 的软链接） | 仅本 checkout，只需 Python 3.14+ 标准库 | 把用户级内容软链接到当前用户环境 |
| 用户级内容 | `global/AGENTS.md`、`skills/` | 安装后，在目标机器的任意项目中 | 跨项目生效的个人规则与 skills |

用户级 skills 中，`setup-project` 是可重复运行的项目初始化器，向调用时所在的目标项目写入模板与 overlay；其余（`commit`、`prune-tests` 等）是日常调用的常规 skill，不产出项目结构。

维护约束：

- 用户级内容在本仓库之外运行：脚本以 skill 自身目录定位资源，运行时只假设 Python 3.14+ 标准库，不引用本仓库的 mise 任务、`.venv`、`tests/` 或开发依赖，也不假设当前工作目录是本仓库。
- 本仓库不是 `setup-project` 的产物：不套用其模板结构，不向本仓库写入模板文件；修改模板和 overlay 只影响之后初始化的项目。
- 三个 `AGENTS.md` 用途不同，改动前先确认目标：根目录的约束本仓库维护；`global/AGENTS.md` 安装为用户级规则；`skills/setup-project/templates/AGENTS.md` 是写入目标项目的模板。
- 跨项目使用的 skill 放 `skills/<name>/`，重新执行 setup 建立链接；仅本仓库使用的 skill 放 `.agents/skills/`，不安装到用户目录，`.claude/skills` 中不另放文件。
- `skills/<name>/` 整目录链接到用户环境，只放运行时内容：`SKILL.md`、脚本、模板，以及 agent 执行时按需读取的 `references/`。测试放 `tests/<name 下划线形式>/`（如 `tests/setup_project/`），设计说明与调研放 `docs/skills/<name>/`；`SKILL.md` 只写给执行 skill 的 agent。
- `SKILL.md` frontmatter 的 `description` 常驻 agent 上下文，统一用英文：先写做什么，再写触发场景，必要时用一句话指向易混淆的相邻 skill；带 `disable-model-invocation: true` 的 skill 只写给人看的一行摘要，不列触发场景；值加双引号，因为英文冒号会破坏 YAML 解析。

## 维护边界

- `skills/` 只收录个人维护的 skills，每个 skill 独立成目录，以 `SKILL.md` 为入口。修改某个 skill 前先读 `docs/skills/<name>/design.md`（如有），完成后把新的决策和待验收项记回该文件；新 skill 若有代码与 git 历史看不出的决策，新建该文件。
- 第三方 skills（如 `npx skills` 安装的）、系统 skills、插件缓存、认证信息及会话数据不纳入本仓库。
- 移动或重命名已安装的文件、目录时，同步检查对应软链接与 `README.md` 的映射。
- 目录职责或加载关系变化时，同步更新本文件与 `README.md`。

## 开发环境

- 工具链为系统包管理器（Homebrew/APT）→ mise → uv → uv 管理的项目 Python → `.venv`。`mise.toml` 钉 uv 版本 line 并定义任务，`mise.lock`、`.python-version`、`uv.lock` 分别锁定 uv、Python line 与开发依赖；`mise tasks` 列出全部任务。需要向多条命令传参的任务放 `mise-tasks/` 文件任务。新环境运行 `mise run install` 和 `mise run check-toolchain`。
- 不擅自升级全局工具或修改相邻项目。
- 本仓库不发布为 Python 包。pytest、Ruff、ty 只是开发依赖，不成为 skill 运行时依赖。

## 测试与验证

- `mise run test` 只收集 `tests/` 下的 `test_*.py`、`*_test.py`；`skills/` 不被收集，其中 `toolchain/` 下的测试文件是复制到目标项目的模板。测试按 skill 分目录，以相对本仓库的路径定位被测脚本，不把各 skill 的脚本目录加入全局 `pythonpath`。
- 新增或迁移的测试必须被 `mise run test` 和 `mise run gate-full` 收集并执行；不得用 skip、吞掉退出码或只跑单项测试掩盖失败或未收集。
- 优先覆盖核心规则与代表性主流程。涉及文件、CLI 或进程边界时使用临时目录，不碰真实用户配置。不引入 marker 分层或并行测试框架。
- 删改测试或再次 `/prune-tests` 前先读 `docs/testing.md`，精简后的保留范围写回该页；完整门禁通过只证明该页列出的范围。
- 局部 Python 修改先运行相关测试、`mise run lint` 和 `mise run typecheck`；工具链、目录结构或跨 skill 约定变化时运行 `mise run gate-full`（无筛选的完整门禁）。`mise run fmt` 会修改文件，不属于门禁。
- 纯文档变更核对说明、路径与实际行为，按需执行 `git diff --check`。
- 自动检查不代表真实 agent 已完成 skill 工作流验收，交付时区分验证范围。修改 `setup-project` 的 SKILL.md、references 或工具链模板后，至少用 `mise run e2e-setup-project` 跑受影响的用例（不属于门禁），做法见 `docs/skills/setup-project/e2e.md`。
