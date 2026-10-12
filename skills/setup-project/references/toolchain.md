# 工具链与门禁

阶段 3 的规范：stack 判定、每个 stack 落地的文件与命令、脚本如何把多个 stack 拼成一个项目、`gate-core` 与 `gate-full` 的定义。偏好来源：x-media-saver（uv + Bun）与 media-glance（Swift）两个项目的实践，2026-10-11 提取。

## 模型：项目是 stack 的集合

每个 stack 是 `toolchain/stacks/<name>/` 下的自包含模块，新增 stack 只需加目录并在脚本 `STACKS` 登记名字：

| 文件 | 作用 |
| --- | --- |
| `stack.json` | 标签、与其他 stack 同在时的子目录（`home_when_shared`）、宿主工具说明、安装命令（在根或 home 执行）、文档表格单元 |
| `recipes.just` | 该 stack 的私有 recipe：`<name>-check-toolchain`、`-install`、`-fmt`、`-lint`、`-typecheck`、`-test`、`-test-core`、`-test-full` |
| `home/`、`root/` | 复制到 stack 目录与仓库根的文件；路径与内容都做占位符替换 |
| `gitignore` | 追加到根 `.gitignore` 的缺失行 |
| `overlay/` | 镜像项目根的文档片段，只含二级节正文 |

占位符：全局 `{{PROJECT_NAME}}`、`{{DIST_NAME}}`（小写连字符）、`{{MODULE_NAME}}`（PascalCase）；按 stack 的 `{{LABEL}}`、`{{HOME_DIR}}`（`.` 或子目录）、`{{HOME}}`（空或 `子目录/`）、`{{ROOT}}`（从 home 回到根的相对路径）。生成的 justfile 中不能残留 `{{`，否则 just 会把它当作自己的插值。

## stack 判定

| 证据 | stack |
| --- | --- |
| `uv.lock`，或 `pyproject.toml` 含 `[tool.uv]` | uv |
| 根或一级子目录的 `bun.lock` / `bunfig.toml` | bun |
| `Package.swift`、`*.xcodeproj`、`*.xcworkspace` | swift |
| `Cargo.toml`、`go.mod`、`Gemfile`、`pom.xml`、`build.gradle*`、`CMakeLists.txt` | 无预置 stack，但已有工具链 |
| 只有 `pyproject.toml` 或只有 `package.json`，或空项目 | 无法判定，退出码 3，由用户多选 |

多个证据同时命中就是多 stack 项目。`--stacks` 可多选覆盖判定；`none` 表示没有预置 stack，不能与其他值同用。

**模式**：任一强证据（lockfile、工程文件、`justfile`）存在即为已有工具链，脚本不创建工具链文件、不运行安装、不碰 justfile，只填 `technology-stack.md` 的"依赖政策"节（各 stack 片段拼合）。否则为新项目。

## 各 stack 落地

| stack | 布局 | 工具链文件 | 安装命令 |
| --- | --- | --- | --- |
| uv | 根目录 | `.python-version`（minor line）、`pyproject.toml`（Ruff、ty、pytest，`package = false`）、`tests/core/test_toolchain.py` | `uv sync` |
| bun | 单独时根目录，与其他 stack 同在时 `frontend/`；`mise.toml` 始终在根 | `mise.toml`（Bun 版本 line）、`package.json`、`biome.json`、`tsconfig.json`、`scripts/check-bun.ts`、`tests/core/toolchain.test.ts` | `mise trust`、`mise install`、`mise lock`、`bun install`（在 home） |
| swift | 根目录 | `.xcode-version`（major line）、`.swift-format`、`Package.swift`（library target + `CoreTests` target 指向 `tests/core`）、`Sources/<Module>/<Module>.swift`、`tests/core/ToolchainTests.swift` | `swift package resolve` |
| 无预置 | 不落工具链文件 | `toolchain/none/justfile`、`scripts/check_docs.py` 与 `scripts/with_lock.py` | 无 |

工具链走 Homebrew → uv → Python、Homebrew → mise → Bun、Xcode 自带 Swift 工具链；Ruff/ty/pytest、Biome/`tsc --noEmit`/`bun test`、swift-format/`swift build`/Swift Testing 是各自的检查器与 runner。`scripts/check_docs.py` 与 `scripts/with_lock.py` 对所有新项目复制，只依赖 Python 3.14+ 标准库，recipe 用 `python3` 调用。所有文件缺失才创建。

uv+bun 选"后端根目录、前端子目录"：后端是仓库主体，`uv run` 与 `pyproject.toml` 在根目录最顺手；前端是独立构建的产物，子目录边界清楚。swift 新项目只落 SwiftPM package：`.xcodeproj` 无法可靠模板化，应用壳由用户在 Xcode 创建后把 package 作本地依赖，再把 `swift-*` recipe 切到 `xcodebuild`。

## 拼合规则

**justfile**：公共头（契约说明、`set positional-arguments`、`default`）+ 公开契约 recipe + 各 stack 的 `recipes.just` 原文（替换占位符）。公开 recipe 的生成规则：

| recipe | 生成方式 |
| --- | --- |
| `check-toolchain`、`install`、`lint`、`typecheck` | 依赖列表：`lint: uv-lint bun-lint` |
| `fmt *args`、`test *args` | 单 stack 直接转发 `just uv-fmt "$@"`；多 stack 无参数时执行私有聚合 recipe `fmt-all: uv-fmt bun-fmt`，有参数时第一个参数是 scope（stack 名），其余转发。不能写 `just uv-fmt bun-fmt`：可变参数 recipe 会把后一个名字当参数吞掉 |
| `docs-check` | `python3 scripts/check_docs.py` |
| `gate-core` | `check-toolchain docs-check lint typecheck` + 各 `<stack>-test-core` |
| `test-full *args` | 同 `fmt`/`test` 的转发，但整条命令包在 `python3 scripts/with_lock.py` 里 |
| `gate-full` | 依赖 `gate-core`，正文 `with_lock.py just test-full-all`（单 stack 直接是 `<stack>-test-full`） |

私有 recipe 标 `[private]`，`just --list` 只显示契约。stack 顺序固定为 uv、bun、swift，与 `--stacks` 的书写顺序无关。

**文档**：`toolchain/overlay/` 是公共正文（README 开始使用、workflow 的环境/命令与门禁/测试分层、testing 的分层），表格单元用占位符 `{{INSTALL}}`、`{{FMT}}`、`{{LINT}}`、`{{TYPECHECK}}`、`{{TEST}}`、`{{CORE}}`、`{{FULL}}` 由各 stack 的 `cells` 填入，多 stack 时写成 `标签：单元；标签：单元`；`{{HOST_TOOLS}}`、`{{LAYOUT}}`、`{{ARGS}}`、`{{SCOPE_NOTE}}` 由 stack 集合推导。各 stack 的 `overlay/` 片段按同名节追加在公共正文之后，多 stack 时每段加 `### 标签`。拼好的节替换目标文档中仍含 `<待填 阶段3>` 的同名节。没有预置 stack 时用 `toolchain/none/overlay/`，只写定义，命令与位置留 `按需` 标记。

## 命令契约

每个项目的 `justfile` 提供同一组公开 recipe，名称与职责稳定；接入新工具时只换私有 recipe 的实现：

| recipe | 职责 |
| --- | --- |
| `check-toolchain` | 核对运行时与版本声明，不安装 |
| `install` | 按 lock 安装，不升级宿主工具 |
| `fmt` | 唯一修改文件的入口，不属于门禁 |
| `lint`、`typecheck` | 静态检查 |
| `test [scope] [参数]` | 默认全部 core 测试，传参定向；多 stack 时先写 scope |
| `test-full [scope] [参数]` | full 测试，经主机锁串行；默认全部，传参定向 |
| `docs-check` | 文档链接、锚点、模块页可达性 |
| `gate-core` | check-toolchain → docs-check → lint → typecheck → 全部 core 测试，首错停止 |
| `gate-full` | gate-core 后串行运行全部 full 测试 |

没有预置 stack 的 recipe 保持非零退出并说明原因，不留空命令：验证未实现必须失败，不能冒充通过。

## 门禁定义

- **core**：各 stack home 下的 `tests/core/`。单元测试和轻量、结果确定的测试，秒级完成；不启动真实服务、数据库、浏览器或桌面会话，不执行 E2E；不依赖共享可变状态、固定端口、桌面焦点。因此 `gate-core` 可在多个 worktree 并行运行。
- **full**：各 stack home 下的 `tests/full/`。重型、真实基础设施集成、E2E 与独占资源测试；尽量隔离，无法隔离的串行；同一主机排队。目录出现即被 `gate-full` 收录，目录存在而无测试视为失败，目录不存在时打印提示。swift 的 `tests/full/` 需要同步在 `Package.swift` 声明 `FullTests` target，recipe 会检查。
- **主机锁**：full 测试占用端口、桌面等主机资源，不同 worktree 的编译产物各在自己目录内，真正共享的只有主机。`scripts/with_lock.py` 用 `fcntl.flock` 锁 `~/.cache/gate-full.lock`（`GATE_LOCK_FILE` 可覆盖），`test-full` 与 `gate-full` 都经它运行，私有 `<stack>-test-full` 不再加锁以免重入。等待时每 30 秒打印持有者，`--timeout` 超时退出码 75 表示稍后重试。按主机而非按仓库加锁，因为桌面焦点和固定端口是主机级资源；代价是不相关项目的 full 也会排队。锁只覆盖 `just` 入口，直接调底层 runner 仍能绕过，这一条留给文档约束与 code-review。
- 两个门禁不接受筛选参数；不得用 skip、收集过滤或弱化断言让门禁通过，零匹配不是通过。`swift test` 零匹配只告警，recipe 自行判为失败；`bun test` 用 `--fail-on-empty`；pytest 零收集本身非零。

这些定义写入目标项目的 `docs/development/workflow.md`、`technology-stack.md` 与 `docs/agents/testing.md`。

## 让门禁初始化完即通过

每个 stack 各带一个真实的工具链测试（Python 版本符合 `.python-version`、Bun 版本符合 `mise.toml`、Xcode 版本符合 `.xcode-version`），避免空测试集让 `gate-core` 以零收集失败。初始化最后运行 `just gate-core`，结果进报告。

## 不在范围内

CI workflow、Docker、发布流程、`env-facts`、依赖升级脚本、Xcode 工程生成。这些是项目特有能力，按需在项目里添加。
