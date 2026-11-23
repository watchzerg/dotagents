## 环境

宿主工具：`mise` 与 Python 3.14+ 的 `python3`（运行 `scripts/check_docs.py` 与 `scripts/with_lock.py`）。mise 由系统包管理器（Homebrew、APT）维护，并按项目根 `mise.toml` 提供工具、环境变量与 task；`python3` 可由 uv 安装（`uv python install 3.14 --default`）。接入工具链时，对版本敏感的工具写进 `mise.toml` 的 `[tools]` 钉版本 line 并提交 `mise.lock`；项目环境变量写 `[env]`，本机私有值写不提交的 `mise.local.toml`。项目运行时与依赖管理尚未接入。

<待填 按需：接入工具链后记录宿主工具、运行时版本声明与安装方式>

## 命令与门禁

根 `mise.toml` 已建立命令契约，`mise tasks` 查看，但各 task 尚未接入本项目的工具链，当前一律非零退出并说明原因。接入时保留 task 名与职责：按 stack 把实现写成 `mise-tasks/<stack>/` 下的 file task（task 名 `<stack>:<name>`，接受 runner 参数用于定向），再让公开 task 用 `depends` 聚合；不留空命令。

| 命令 | 职责 |
| --- | --- |
| `mise run check-toolchain` | 核对实际运行时与版本声明，不同步依赖 |
| `mise run install` | 按锁定版本安装依赖，不升级宿主工具 |
| `mise run fmt` | 格式化并修复可自动修复的 lint；唯一修改文件的入口，不属于门禁 |
| `mise run lint` / `mise run typecheck` | 静态检查，不修改源码 |
| `mise run test` | 运行全部 core 测试；定向运行用 stack task 加参数 |
| `mise run test-full` | 运行全部 full 测试，经 `scripts/with_lock.py` 主机锁串行；定向运行用 stack task 加参数 |
| `mise run docs-check` | 文档链接与锚点、全量可达、索引登记、体量预算、标题骨架与 `covers` 有匹配，规则见[文档维护规则](../agents/documentation.md#自动检查)（已可用） |
| `mise run docs-affected [基准]` | 改动提示：列出相对基准（默认 `HEAD`）的改动命中 `covers` 的文档页，标出本次未修改的页；总是成功，不属于门禁，用法见[随交付同步](../agents/documentation.md#随交付同步)（已可用） |
| `mise run gate-core` | 工具链检查、docs-check、lint、typecheck 与全部 core 测试并行运行，任一失败即门禁失败 |
| `mise run gate-full` | gate-core 通过后在主机锁内运行全部 full 测试 |

`gate-core` 可在多个 worktree 同时运行；full 测试只经 `test-full` 类 task 运行，并用 `scripts/with_lock.py` 持有主机级锁自动排队。两个门禁都不接受筛选参数。

门禁通过只证明它收录的范围：`gate-core` 证明静态检查、文档检查与 core 测试通过，不证明真实服务、独占资源与部署形态下的行为；`gate-full` 再加上 full 测试收录的范围，不证明真实环境验收（`/acceptance`）。本项目没有 CI，门禁只在本机运行，结果由运行者在交付说明里如实报告；接入 CI 后在此写明哪道门禁在哪里跑。新增、改名或删除 task 时同步上表与调用它的脚本、文档。

<待填 按需：接入工具链后记录实际命令、运行时与版本声明来源>
