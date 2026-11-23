## 环境

宿主工具：`mise` 与 Python 3.14+ 的 `python3`（运行 `scripts/check_docs.py` 与 `scripts/with_lock.py`，可用 `uv python install 3.14 --default` 安装）。mise 由系统包管理器（Homebrew、APT）安装，按根 `mise.toml` 提供工具、环境变量与 task。项目环境变量写 `[env]`，本机私有值写不提交的 `mise.local.toml`；接入工具链时，对版本敏感的工具写进 `[tools]` 钉版本 line 并提交 `mise.lock`。

<待填 按需：接入工具链后记录运行时版本声明与安装方式>

## 命令与门禁

根 `mise.toml` 已建立命令契约，`mise tasks` 查看；除 `docs-check` 与 `docs-affected` 外，各 task 尚未接入工具链，一律非零退出并说明原因。接入时保留 task 名与职责：实现写成 `mise-tasks/<stack>/` 下的 file task（task 名 `<stack>:<name>`，接受 runner 参数用于定向），公开 task 用 `depends` 聚合，不留空命令。公开 task 与两个门禁都不接受参数；`fmt` 是唯一修改文件的入口，不属于门禁。

| 命令 | 作用 |
| --- | --- |
| `mise run check-toolchain` | 核对运行时与版本声明，不同步依赖 |
| `mise run install` | 按 lock 安装，不升级宿主工具 |
| `mise run fmt` | 格式化并修复可自动修复的 lint |
| `mise run lint` / `mise run typecheck` | 静态检查 |
| `mise run test` | 运行全部 core 测试 |
| `mise run test-full` | 在主机锁内运行全部 full 测试 |
| `mise run docs-check` | 文档结构检查，规则见[自动检查](../agents/documentation.md#自动检查) |
| `mise run docs-affected [基准]` | 列出改动命中 `covers` 的文档页并标出本次未修改的；总是成功，不属于门禁，用法见[随交付同步](../agents/documentation.md#随交付同步) |
| `mise run gate-core` | check-toolchain、docs-check、lint、typecheck 与全部 core 测试并行，任一失败即失败 |
| `mise run gate-full` | gate-core 通过后在主机锁内运行全部 full 测试 |

`gate-core` 可在多个 worktree 同时运行。full 测试只经 `test-full` 类 task 运行，由 `scripts/with_lock.py` 持有主机级锁自动排队。

门禁通过只证明它收录的范围：`gate-core` 不证明真实服务、独占资源与部署形态下的行为，`gate-full` 不证明真实环境验收（`/acceptance`）。本项目没有 CI，门禁只在本机运行，运行者在交付说明里如实报告结果；接入 CI 后在此写明哪道门禁在哪里跑。新增、改名或删除 task 时同步上表与调用它的脚本、文档。

<待填 按需：接入工具链后记录各 task 的实际命令>
