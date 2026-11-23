## 环境

宿主工具：{{HOST_TOOLS}}。mise 由系统包管理器（Homebrew、APT）维护，并按项目根 `mise.toml` 提供工具、环境变量与 task；`mise run` 会自动安装缺失的工具，不需要 shell 启用 `mise activate`。{{PIN_NOTE}}

项目环境变量写在 `mise.toml` 的 `[env]`，本机私有值写不提交的 `mise.local.toml`。新环境先 `mise trust`，再 `mise run install`、`mise run check-toolchain`。{{LAYOUT}}

## 命令与门禁

命令以 mise task 为准，`mise tasks` 查看。公开 task 定义在根 `mise.toml`，聚合各 stack 在 `mise-tasks/<stack>/` 下的 file task（task 名 `<stack>:<name>`）；`depends` 列出的 task 并行执行。公开 task 不接受参数，定向运行直接调用 stack task 并传 runner 参数：`mise run {{STACK}}:test [参数]`、`mise run {{STACK}}:test-full [参数]`、`mise run {{STACK}}:fmt [路径]`。{{SCOPE_NOTE}}验证类 task 不修改源码；`fmt` 是唯一修改文件的入口，不属于门禁。

| 命令 | 作用 |
| --- | --- |
| `mise run check-toolchain` | 核对运行时与版本声明，不同步依赖 |
| `mise run install` | 按 lock 安装，不升级宿主工具：{{INSTALL}} |
| `mise run fmt` | {{FMT}} |
| `mise run lint` | {{LINT}} |
| `mise run typecheck` | {{TYPECHECK}} |
| `mise run test` | 运行全部 core 测试；{{TEST}} |
| `mise run test-full` | 在主机锁内运行全部 full 测试；定向用 `{{STACK}}:test-full`，参数同 `test` |
| `mise run docs-check` | 文档链接与锚点、全量可达、索引登记、体量预算、标题骨架与 `covers` 有匹配，规则见[文档维护规则](../agents/documentation.md#自动检查) |
| `mise run docs-affected [基准]` | 改动提示：列出相对基准（默认 `HEAD`）的改动命中 `covers` 的文档页，标出本次未修改的页；总是成功，不属于门禁，用法见[随交付同步](../agents/documentation.md#随交付同步) |
| `mise run gate-core` | 工具链检查、docs-check、lint、typecheck 与全部 core 测试并行运行，任一失败即门禁失败 |
| `mise run gate-full` | gate-core 通过后在主机锁内运行 full 测试：{{FULL}} |

`gate-core` 可在多个 worktree 同时运行。full 测试只经 `test-full` 类 task 运行：各 stack 的 `test-full` 有测试时经 `scripts/with_lock.py` 持有主机级锁（`~/.cache/gate-full.lock`），同一主机上的 full 自动排队，等待时打印持有者；不直接调用底层 runner 运行 `tests/full/`。两个门禁都不接受筛选参数。工具链、目录结构或门禁定义变化时运行 `gate-full`。

门禁通过只证明它收录的范围：`gate-core` 证明静态检查、文档检查与 core 测试通过，不证明真实服务、独占资源与部署形态下的行为；`gate-full` 再加上 full 测试收录的范围，不证明真实环境验收（`/acceptance`）。本项目没有 CI，门禁只在本机运行，结果由运行者在交付说明里如实报告；接入 CI 后在此写明哪道门禁在哪里跑。新增、改名或删除 task 时同步上表与调用它的脚本、文档。
