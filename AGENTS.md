# dotagents

## 核心目标

集中维护和版本管理个人用户级 `AGENTS.md` 与个人 skills。以本仓库为源文件的唯一维护位置，用户目录通过软链接加载，避免多份副本漂移。

## 目录布局

```text
dotagents/
├── AGENTS.md              # 本仓库的维护规则
├── README.md              # 使用说明、本机加载入口和链接关系
├── .python-version        # uv 管理的开发 Python 补丁版本
├── pyproject.toml         # Python 开发依赖和检查配置
├── uv.lock                # Python 依赖锁文件
├── justfile               # 安装、检查和测试入口
├── .agents/skills/setup-dotagents/  # 项目级安装 skill 及链接脚本
├── tests/                 # 仓库级测试与 skill 格式校验
├── global/
│   └── AGENTS.md          # 跨项目生效的用户级规则
└── skills/
    ├── commit/           # 个人本地提交 skill
    └── prune-tests/      # 个人测试精简 skill
```

## 维护边界

- 本文件只约束 dotagents 的维护；跨项目的个人规则写入 `global/AGENTS.md`。
- `skills/` 只收录个人维护的 skills，每个 skill 独立成目录，以 `SKILL.md` 为入口，配套资源留在该目录内。
- 通过 `npx skills` 安装的第三方 skills 由原安装工具管理，不搬入本仓库；系统 skills、插件缓存、认证信息及会话数据同样不纳入。
- 修改仓库内的源文件，保留用户目录中的加载入口。移动或重命名已安装的文件、目录时，同步检查对应软链接；具体映射见 `README.md`。
- 目录职责或加载关系发生变化时，同步更新本文件与 `README.md`，保持说明简洁一致。

- `.agents/skills/` 收录只在本仓库使用的项目级 skills；`setup-dotagents` 直接调用其 `scripts/setup.py`，不安装到用户目录。应用配置只依赖 Python 3.10+ 标准库，与依赖 uv/just 的开发环境分开。

## 开发环境

- 工具链为 Homebrew → 宿主 uv/just → uv 管理的项目 Python → `.venv` 与依赖。不引入 mise，不在项目内安装或锁定 uv/just，不擅自升级宿主工具或修改相邻项目。
- `.python-version` 固定开发 Python 补丁版本，`uv.lock` 固定依赖。新环境先安装宿主工具，再运行 `just install` 和 `just check-toolchain`。
- 本仓库是开发环境，不发布为 Python 包。pytest、PyYAML、Ruff、ty 属于开发依赖；开发环境可用的依赖不自动成为 skill 运行时依赖。
- skill 的 Python 运行代码和专属资源放在各自目录内。明确运行时 Python 和依赖要求，不依赖调用者恰好位于本仓库或已激活本项目 `.venv`。

## 测试与验证

- `just test` 使用 pytest 自动发现 `tests/` 和 `skills/` 下的测试。测试文件使用 `test_*.py` 或 `*_test.py`；按 skill 组织测试，避免将各 skill 的脚本目录一起加入全局 `pythonpath`。
- 新增或迁移的 Python 测试必须被 `just test` 和无筛选的 `just gate-full` 收集并执行。不得通过 skip、吞掉退出码或仅运行单项测试来掩盖失败或未收集。
- 优先覆盖核心规则与代表性主流程。涉及文件、CLI 或进程边界时使用临时目录，避免修改真实用户配置。当前不引入强制 marker 分层或并行测试框架。
- `tests/test_skills.py` 自动枚举 `skills/` 与 `.agents/skills/` 下所有 skill 目录，使用宿主 `~/.codex/skills/.system/skill-creator/scripts/quick_validate.py` 校验。此 validator 是未锁版本的宿主开发依赖；缺失时明确失败，不下载、复制或跳过。
- 局部 Python 修改先运行相关测试、`just lint` 和 `just typecheck`；工具链、目录结构或跨 skill 约定变化时运行 `just gate-full`。
- `just gate-full` 顺序执行工具链检查、`git diff --check`、Ruff lint/format check、ty 和全部 pytest（包含 skill 校验），首错停止。`just fmt` 会修改文件，不属于门禁。
- 纯文档变更核对说明、路径与实际行为，按需执行 `git diff --check`。格式校验和自动测试不代表真实 agent 已完成 skill 工作流验收，交付时区分验证范围。
