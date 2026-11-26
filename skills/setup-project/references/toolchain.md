# 工具链与门禁

工具链判定与落地（SKILL.md 阶段 1 第 3、5 步）、existing 模式补齐 task（阶段 2 第 5 步）与门禁（阶段 3）的规范。

## 模型：项目是 stack 的集合

每个 stack 是 `toolchain/stacks/<name>/` 下的自包含模块，新增 stack 只需加目录并在脚本 `STACKS` 登记名字：

| 文件 | 作用 |
| --- | --- |
| `stack.json` | 标签、与其他 stack 同在时的子目录（`home_when_shared`）、宿主工具说明、`mise`（钉进根 `mise.toml` 的工具及版本 line）、安装命令（在根或 home 执行）、文档表格单元 |
| `root/mise-tasks/<name>/` | 该 stack 的 file task：`check-toolchain`、`install`、`fmt`、`lint`、`typecheck`、`test`、`test-full`，在项目里成为 `<name>:check-toolchain` 等；复制时保留可执行位（mise 只把可执行文件当作 file task） |
| `home/`、`root/` | 复制到 stack 目录与仓库根的文件；路径与内容都做占位符替换 |
| `gitignore` | 追加到根 `.gitignore` 的缺失行 |
| `overlay/` | 镜像项目根的文档片段，只含二级节正文 |

占位符：全局 `{{PROJECT_NAME}}`、`{{DIST_NAME}}`（小写连字符）、`{{MODULE_NAME}}`（PascalCase）；按 stack 的 `{{LABEL}}`、`{{HOME_DIR}}`（`.` 或子目录）、`{{HOME}}`（空或 `子目录/`）、`{{ROOT}}`（从 home 回到根的相对路径）。生成的 `mise.toml` 与 task 文件中不能残留 `{{`：mise 会把 `run` 里的 `{{` 当作 Tera 模板。

## stack 判定

| 证据 | stack |
| --- | --- |
| `uv.lock`，或 `pyproject.toml` 含 `[tool.uv]` | uv |
| 根或一级子目录的 `pnpm-lock.yaml` | node |
| `Package.swift`、`*.xcodeproj`、`*.xcworkspace` | swift |
| `Cargo.toml`、`go.mod`、`Gemfile`、`pom.xml`、`build.gradle*`、`CMakeLists.txt`，或只有 mise 配置文件 | 无预置 stack，但已有工具链 |
| 只有 `pyproject.toml` 或只有 `package.json`（含其他包管理器的 lockfile），或空项目 | 无法判定，退出码 3，由用户多选 |

多个证据同时命中就是多 stack 项目。`--stacks` 可多选覆盖判定；`none` 表示没有预置 stack，不能与其他值同用。stack 顺序固定为 uv、node、swift，与 `--stacks` 的书写顺序无关。

**模式**：任一强证据（lockfile、工程文件、`mise.toml` 等 mise 配置文件）存在即为 `existing`，否则为 `new`。`existing` 模式不创建工具链文件、不运行安装、不碰 mise 配置与 task，只做两件事：

- 填 `technology-stack.md` 的“依赖政策”节（公共正文加各 stack 片段）。因此该节只写对任何项目都成立的偏好；模板设置的配置事实（如 uv 的 `prerelease`、node 的 `preinstall`）写在“运行时与工具链”节。
- 补缺 `scripts/check_docs.py` 与 `scripts/with_lock.py`：两者只用标准库、与 stack 无关，前者让 `docs-check` 有实现，后者让已有的 full 测试入口能包进主机锁。

`--detect-only` 只做判定，打印 stack、模式、证据，`existing` 模式另列出 mise 配置缺少的契约 task，不写文件，退出码与正式运行一致。缺少的 task 按文件读取默认位置的 mise 配置的 `[tasks]` 与 `mise-tasks/` 等 file task 目录得出，不调用 mise，免得执行项目配置里需要 trust 的代码。

## 各 stack 落地

| stack | 布局 | 工具链文件 | 安装命令 |
| --- | --- | --- | --- |
| uv | 根目录 | `mise.toml` 的 `uv = "0.13"`、`mise-tasks/uv/`、`.python-version`（minor line）、`pyproject.toml`（Ruff、ty、pytest，`package = false`）、`tests/core/test_toolchain.py` | `mise exec -- uv sync` |
| node | 单独时根目录，与其他 stack 同在时 `frontend/`；`mise.toml` 与 `mise-tasks/` 始终在根 | `mise.toml` 的 `node = "26"`、`pnpm = "12"`、`mise-tasks/node/`、`package.json`（Biome、TypeScript、Vitest）、`biome.json`、`tsconfig.json`、`scripts/check-node.ts`、`tests/core/toolchain.test.ts` | `mise exec -- pnpm install`（在 home） |
| swift | 根目录 | `mise-tasks/swift/`、`.xcode-version`（major line）、`.swift-format`、`Package.swift`（library target + `CoreTests` target 指向 `tests/core`，按实际文件排除测试目录中的非 Swift 文件）、`Sources/<Module>/<Module>.swift`、`tests/core/ToolchainTests.swift` | `swift package resolve` |
| none | — | 只有 `toolchain/none/mise.toml` | 无 |

所有 `new` 项目另得根 `mise.toml`、`scripts/check_docs.py` 与 `scripts/with_lock.py`（只依赖 Python 3.14+ 标准库，task 用 `python3` 调用）。所有文件缺失才创建。每个 stack 自带一个真实的工具链测试（Python 版本符合 `.python-version`、Node 版本符合 `mise.toml`、Xcode 版本符合 `.xcode-version`），免得空测试集让 `gate-core` 以零收集失败。

工具来源：系统包管理器（Homebrew、APT）→ mise → uv → Python，mise → Node 与 pnpm，Xcode 自带 Swift 工具链。mise 同时承担工具、环境变量（`[env]`，本机私有值写 gitignore 的 `mise.local.toml`）与 task。各 stack 的 `mise` 字段按 uv、node 顺序合并进 `[tools]`；有钉住的工具时脚本在根目录先运行 `mise install`、`mise lock` 生成多平台 `mise.lock`，再运行各 stack 的安装命令（脚本进程的 PATH 里没有新装的工具，所以经 `mise exec --` 调用）。

- **不需要 `mise trust`**：生成的 `mise.toml` 只有普通 `[tools]`、`[tasks]` 与无模板的 `[env]`，mise 默认（非 paranoid）不要求 trust，`mise run`、`mise install`、`mise exec` 也会自动 trust 当前配置，所以流程与文档都不出现 `mise trust`。
- **task 内直接调用 `uv`、`pnpm`**：`mise run` 会自动安装缺失工具并放进 PATH，不依赖 shell 的 `mise activate`。因此 `check-toolchain` 只核对 mise 之外的版本声明（`.python-version`、`.xcode-version`），node 的只打印版本。
- **swift 仅支持 macOS**：`new` 模式选了 swift 而 PATH 上没有 `xcodebuild` 时，脚本不写文件并以退出码 1 结束；`existing` 模式不碰工具链文件，所以不检查。
- 检查器与 runner：uv 是 Ruff、ty、pytest；node 是 Biome、`tsc --noEmit`、Vitest；swift 是 swift-format、`swift build`、Swift Testing。

node stack 只落工具链，不落应用骨架：React、Vite、Tailwind CSS、shadcn/ui 与 React Testing Library 是固定选型，写在该 stack 的文档片段里，由项目在写第一个页面时加入。

uv+node 采用“后端根目录、前端子目录”：后端是仓库主体，`uv run` 与 `pyproject.toml` 在根目录最顺手；前端是独立构建的产物，子目录边界清楚。swift 新项目只落 SwiftPM package：应用壳由用户在 Xcode 创建后把 package 作本地依赖，再把 `swift:*` task 切到 `xcodebuild`。uv 与 swift 同在根目录时 `tests/` 混放两种语言：`Package.swift` 按实际存在的文件计算测试 target 的 `exclude`（静态列表在文件缺失时会告警 Invalid Exclude），swift task 用 `--manifest-cache none` 让新增文件即时生效。

## 拼合规则

**mise.toml**：契约说明头注释 + `[tools]`（钉住的工具，可为空）+ `[env]`（只有说明注释）+ 公开 task：

| task | 生成方式 |
| --- | --- |
| `check-toolchain`、`install`、`fmt`、`lint`、`typecheck`、`test`、`test-full` | 只有 `depends`，聚合各 stack 的同名 task：`depends = ["uv:lint", "node:lint"]` |
| `docs-check` | `run = "python3 scripts/check_docs.py"` |
| `docs-affected` | `run = "python3 scripts/check_docs.py --affected"`；内联 `run` 会把命令行参数追加在末尾，所以 `mise run docs-affected main` 即以 `main` 为基准 |
| `gate-core` | `depends = ["check-toolchain", "docs-check", "lint", "typecheck", "test"]` |
| `gate-full` | `depends = ["gate-core"]`，`run = [{ task = "test-full" }]`，gate-core 通过后才运行 full |

采用 mise 的默认行为：`depends` 中的 task 并行执行，输出带 task 名前缀，任一失败即整体失败。只有 `depends` 的 task 静默忽略参数，所以公开 task 不承担定向，定向直接调用 stack task（`mise run uv:test -k 名称`）。stack task 是 file task，参数原样进入 `$@`；传给 runner 的 `--help` 会被 mise 截获，需写在 `--` 之后。

**文档**：`toolchain/overlay/` 是公共正文（README 开始使用、workflow 的环境与命令与门禁、test-layers 的分层与资源边界（含独占资源清单）、testing 的分层（只放各 stack 的测试位置）、technology-stack 的依赖政策（各 stack 共用的政策，stack 片段只追加选型）。表格单元占位符 `{{INSTALL}}`、`{{FMT}}`、`{{LINT}}`、`{{TYPECHECK}}`、`{{TEST}}`、`{{CORE}}`、`{{FULL}}` 由各 stack 的 `cells` 填入，多 stack 时写成 `标签：单元；标签：单元`；`{{HOST_TOOLS}}`、`{{PIN_NOTE}}`、`{{LAYOUT}}`、`{{STACK}}`（单 stack 是其名字，多 stack 是 `<stack>`）、`{{SCOPE_NOTE}}` 由 stack 集合推导。各 stack 的 `overlay/` 片段按同名节追加在公共正文之后，多 stack 时每段加 `### 标签`。只处理目标文档中仍含 `<待填 阶段3` 标记的同名节：删除该节中含标记的行，保留其余行，再把拼好的正文追加在节末。none 用 `toolchain/none/overlay/`，只写定义，命令与位置留 `按需` 标记。

## 命令契约

每个项目的根 `mise.toml` 提供同一组公开 task，名称与职责稳定，`mise tasks` 列出；接入新工具时只换 stack task 的实现：

| task | 职责 |
| --- | --- |
| `check-toolchain` | 核对 mise 之外的运行时与版本声明，不同步依赖：uv 加 `--no-project --no-python-downloads`，node 不跑 `pnpm install`，swift 只查 `xcodebuild -version`；mise 管理的工具由 `mise run` 按 `mise.toml` 与 `mise.lock` 保证 |
| `install` | 按 lock 安装，不升级宿主工具 |
| `fmt` | 唯一修改文件的入口，不属于门禁；`<stack>:fmt [路径]` 定向 |
| `lint`、`typecheck` | 静态检查 |
| `test` | 全部 core 测试；`<stack>:test [参数]` 定向 |
| `test-full` | 全部 full 测试，各 stack 有测试时持主机锁运行；`<stack>:test-full [参数]` 定向 |
| `docs-check` | 文档链接与锚点、全量可达、索引登记、体量预算、标题骨架、covers 有匹配 |
| `docs-affected [基准]` | 改动提示：列出改动命中 `covers` 的文档页并标出未修改的；总是成功，不属于门禁 |
| `gate-core` | check-toolchain、docs-check、lint、typecheck 与全部 core 测试并行，任一失败即失败 |
| `gate-full` | gate-core 通过后运行全部 full 测试 |

定向参数的语义：名称类筛选（pytest `-k`、`vitest run -t`、`swift test --filter`）在默认范围内筛选；路径（相对 stack 目录）替换默认目录，只运行给出的路径。pytest 的 full 默认范围经 `-o testpaths=tests/full` 指定；`vitest run` 的位置参数是并集筛选，task 在参数中有已存在的路径时不再附加默认目录；swift 未给 `--filter` 时 `swift:test` 补 `CoreTests`、`swift:test-full` 补 `FullTests`，并始终用 `--skip` 排除对方 target，避免 full 测试绕过主机锁。`uv:test` 与 `uv:test-full` 无参数时清除外部 `PYTEST_ADDOPTS`，门禁的全量运行不受环境里的筛选影响。

没有预置 stack 的 task 非零退出并说明原因，不留空命令：验证未实现必须失败，不能冒充通过。

## 门禁定义

- **core**：各 stack home 下的 `tests/core/`。单元测试和轻量、结果确定的测试，秒级完成；不启动真实服务、数据库、浏览器或桌面会话，不执行 E2E；不依赖共享可变状态、固定端口、桌面焦点。因此 `gate-core` 可在多个 worktree 并行运行。
- **full**：各 stack home 下的 `tests/full/`。重型、真实基础设施集成、E2E 与独占资源测试；需要浏览器的测试以开发依赖引入 Playwright 并归入此层；需要登录时测试自备身份（现建测试用户或测试生成的 storageState，外部身份提供方用替身），不依赖真实账号或外部登录服务。尽量隔离，无法隔离的串行，同一主机排队。各 stack 按自己的测试文件判定是否有 full 测试（uv 与 swift 同在根目录时共用 `tests/`）：uv 看 `test_*.py`、`*_test.py`，node 看 Vitest 默认收集的 `*.test.*`、`*.spec.*`（`ts`、`tsx`、`js`、`jsx`），swift 看 `*.swift`。出现该 stack 的测试文件即被 `gate-full` 收录，此时零收集或零匹配视为失败；目录不存在或只有其他 stack 的文件时打印提示并通过。swift 有测试文件时还需在 `Package.swift` 声明 `FullTests` target，task 会检查。
- **主机锁**：full 测试占用端口、桌面焦点等主机级资源，所以按主机而非按仓库加锁，代价是不相关项目的 full 也会排队。`scripts/with_lock.py` 用 `fcntl.flock` 锁 `~/.cache/gate-full.lock`（`GATE_LOCK_FILE` 可覆盖）；各 stack 的 `test-full` 确认有测试后经它重新执行自身（`GATE_LOCK_HELD` 防重入），所以公开 `test-full`、`gate-full` 与定向的 `<stack>:test-full` 都持锁，多 stack 并行时各自排队。锁只由 `with_lock.py` 自身持有：命令作为子进程运行且不继承锁的文件描述符，命令退出即释放，留下的后台进程不会占锁；SIGINT/SIGTERM 转发给命令。等待时每 30 秒打印持有者，`--timeout` 超时退出码 75 表示稍后重试，等待中被中断退出码 130。直接调底层 runner 能绕过锁，这一条靠文档约束与 code-review。
- 两个门禁不接受筛选参数；不得用 skip、收集过滤或弱化断言让门禁通过，零匹配不是通过。`swift test` 零匹配只告警，task 自行判为失败；`vitest run` 没有匹配的测试文件时本身非零退出，不得加 `--passWithNoTests`；pytest 零收集本身非零。

这些定义写入目标项目的 `docs/development/workflow.md`、`test-layers.md`、`technology-stack.md` 与 `docs/agents/testing.md`。

## 补齐契约 task

`existing` 模式且项目有 mise 配置时，阶段 2 第 5 步按本节补齐脚本列出的缺少 task：

1. 先用 `mise tasks` 核对这些 task 确实不存在：脚本只按文件读取默认位置，include 等方式引入的 task 看不到。`mise tasks` 因配置用了模板、`_.source` 或 hooks 而报未 trust 时，不替用户 trust，以脚本结果为准，报告注明未经 `mise tasks` 复核。
2. 写入 `mise.toml` 的 `[tasks]` 或 `mise-tasks/` 下的 file task，跟随项目已有的写法，用项目现有命令实现，参考第 4 步子 agent 的建议与 `<skill目录>/toolchain/stacks/<stack>/root/mise-tasks/<stack>/` 的写法：
   - `docs-check`：`run = "python3 scripts/check_docs.py"`；`docs-affected`：`run = "python3 scripts/check_docs.py --affected"`。脚本提示已有的 `check_docs.py` 不支持 `--affected` 时按提示做。
   - `check-toolchain` 不用会同步环境的命令。
   - `test-full` 把项目现有的 full 测试命令包进 `python3 scripts/with_lock.py`；项目还没有 full 测试时与各 stack 的 `test-full` 一致：full 目录不存在时提示并以 0 退出，存在而无测试时失败。
   - 项目缺少对应工具（如没有 lint 工具）的 task 写成非零退出并说明原因。
3. 只追加 task，不改 `[settings]`、`[env]`、`[tools]` 等会影响已有 task 的配置。已有 task 只做两种改动：已有 `gate-core` 的 `depends` 追加 `check-toolchain`、`docs-check`；已有 `gate-full` 或 full 测试入口包上主机锁，包完用收集或干跑（如 pytest 的 `--collect-only`）确认测试集与包锁前一致。其余已有 task 的命令不动。
4. 已有的 core 测试命令（`test` 或 `gate-core` 所依赖的）会收集到 full 测试目录时（如不带路径的 `uv run pytest` 收集整个 `tests/`），命令同样不动，但报告写明“`gate-core` 会不经主机锁运行 full 测试”并列为票据候选：否则有了 full 测试后分层与主机锁都会悄悄失效。

## 不在范围内

CI workflow、Docker、发布流程、`env-facts`、依赖升级脚本、Xcode 工程生成。这些是项目特有能力，按需在项目里添加。
