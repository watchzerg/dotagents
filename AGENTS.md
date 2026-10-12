# dotagents

## 核心目标

集中维护和版本管理个人用户级 `AGENTS.md` 与个人 skills。以本仓库为源文件的唯一维护位置，用户目录通过软链接加载，避免多份副本漂移。

## 三层结构与使用流程

仓库内容按运行位置分三层，修改任何文件前先确认它属于哪一层：

| 层 | 内容 | 运行位置 | 作用 |
| --- | --- | --- | --- |
| 仓库维护 | 根目录 `AGENTS.md`、`docs/`、`tests/`、`justfile`、`pyproject.toml` | 仅本 checkout，需要开发环境 | 约束并验证本仓库自身的开发 |
| 安装器 | `.claude/skills/setup-dotagents/` | 仅本 checkout，只需 Python 3.14+ 标准库 | 把用户级内容软链接到当前用户环境 |
| 用户级内容 | `global/AGENTS.md`、`skills/` | 安装后，在目标机器的任意项目中 | 跨项目生效的个人规则与 skills |

用户级 skills 再分两类：`setup-project` 是可重复运行、只补缺不覆盖的项目初始化器，自带模板与 overlay，向调用时所在的目标项目写入文件；`commit`、`prune-tests` 等是日常反复调用的常规 skill，不产出项目结构。

使用顺序为：clone 本仓库并长期保留 → 在本仓库执行 `/setup-dotagents` → 在目标项目先执行 `/setup-matt-pocock-skills` 再执行 `/setup-project` → 日常按需调用常规 skills。完整步骤与链接映射见 `README.md`。由此产生的维护约束：

- 用户级内容在本仓库之外运行：脚本以 skill 自身目录定位资源，运行时只假设 Python 3.14+ 标准库，不引用本仓库的 `justfile`、`.venv`、`tests/` 或开发依赖，也不假设当前工作目录是本仓库。
- 本仓库不是 `setup-project` 的产物：不套用其模板结构，不向本仓库写入模板文件；修改模板和 overlay 只影响之后初始化的新项目，不回灌本仓库。
- 仓库中有三个用途不同的 `AGENTS.md`：根目录的约束本仓库维护；`global/AGENTS.md` 安装为用户级 `CLAUDE.md`；`skills/setup-project/templates/AGENTS.md` 是写入目标项目的模板。改动前先确认目标文件。
- 新增跨项目使用的 skill 放入 `skills/<name>/`，并重新执行 setup 建立链接；仅本仓库使用的 skill 放入 `.claude/skills/`，不安装到用户目录。
- `skills/<name>/` 整目录软链接到用户环境，因此只放运行时内容：`SKILL.md`、脚本、模板，以及 agent 执行时按需读取的 `references/`。维护材料放仓库维护层：测试在 `tests/<name 下划线形式>/`（如 `tests/setup_project/`），设计说明、调研等维护者文档在 `docs/skills/<name>/`。不在 skill 目录放测试、设计记录或其他只服务本仓库开发的文件，`SKILL.md` 也不写面向维护者的指令。

## 维护边界

- `skills/` 只收录个人维护的 skills，每个 skill 独立成目录，以 `SKILL.md` 为入口，运行时资源留在该目录内。修改某个 skill 前先读 `docs/skills/<name>/design.md`（如有），完成后把新的决策和待验收项记回该文件；新 skill 若有代码与 git 历史看不出的决策，新建该文件。
- 通过 `npx skills` 安装的第三方 skills 由原安装工具管理，不搬入本仓库；系统 skills、插件缓存、认证信息及会话数据同样不纳入。
- 修改仓库内的源文件，保留用户目录中的加载入口。移动或重命名已安装的文件、目录时，同步检查对应软链接；具体映射见 `README.md`。
- 目录职责或加载关系发生变化时，同步更新本文件与 `README.md`，保持说明简洁一致。

## 开发环境

- 工具链为 Homebrew → 宿主 uv/just → uv 管理的项目 Python → `.venv` 与依赖。本仓库不引入 mise（`setup-project` 模板中的 mise 配置只作用于目标项目），不在项目内安装或锁定 uv/just，不擅自升级宿主工具或修改相邻项目。
- `.python-version` 固定开发 Python 补丁版本，`uv.lock` 固定依赖。新环境先安装宿主工具，再运行 `just install` 和 `just check-toolchain`。
- 本仓库是开发环境，不发布为 Python 包。pytest、Ruff、ty 属于开发依赖，不自动成为 skill 运行时依赖；skill 的运行代码和专属资源放在各自目录内。

## 测试与验证

- `just test` 使用 pytest 自动发现 `tests/` 下的测试，`skills/` 不被收集：其中 `toolchain/` 下的测试文件是复制到目标项目的模板。测试文件使用 `test_*.py` 或 `*_test.py`；按 skill 分目录组织，测试内以相对本仓库的路径定位被测脚本，避免将各 skill 的脚本目录一起加入全局 `pythonpath`。
- 新增或迁移的 Python 测试必须被 `just test` 和无筛选的 `just gate-full` 收集并执行。不得通过 skip、吞掉退出码或仅运行单项测试来掩盖失败或未收集。
- 优先覆盖核心规则与代表性主流程。涉及文件、CLI 或进程边界时使用临时目录，避免修改真实用户配置。当前不引入强制 marker 分层或并行测试框架。
- 局部 Python 修改先运行相关测试、`just lint` 和 `just typecheck`；工具链、目录结构或跨 skill 约定变化时运行 `just gate-full`。
- `just gate-full` 顺序执行工具链检查、`git diff --check`、Ruff lint/format check、ty 和全部 pytest，首错停止。`just fmt` 会修改文件，不属于门禁。
- 纯文档变更核对说明、路径与实际行为，按需执行 `git diff --check`。格式校验和自动测试不代表真实 agent 已完成 skill 工作流验收，交付时区分验证范围。
