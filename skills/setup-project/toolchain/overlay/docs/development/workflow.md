## 环境

宿主工具：{{HOST_TOOLS}}。新环境先 `just install`，再 `just check-toolchain`。{{LAYOUT}}

## 命令与门禁

命令以根 `justfile` 为准，`just --list` 查看。验证类命令不修改源码；`fmt` 是唯一修改文件的入口，不属于门禁。{{SCOPE_NOTE}}

| 命令 | 作用 |
| --- | --- |
| `just check-toolchain` | 核对运行时与版本声明，不安装 |
| `just install` | 按 lock 安装，不升级宿主工具：{{INSTALL}} |
| `just fmt {{ARGS}}` | {{FMT}} |
| `just lint` | {{LINT}} |
| `just typecheck` | {{TYPECHECK}} |
| `just test {{ARGS}}` | 默认运行全部 core 测试；{{TEST}} |
| `just test-full {{ARGS}}` | 运行 full 测试，经主机锁串行；默认全部，传参定向同 `test` |
| `just docs-check` | 文档链接与锚点、全量可达、索引登记、体量预算与标题骨架，规则见[文档维护规则](../agents/documentation.md#自动检查) |
| `just gate-core` | 工具链检查 → docs-check → lint → typecheck → 全部 core 测试，首错停止 |
| `just gate-full` | gate-core 后在主机锁内串行运行 full 测试：{{FULL}} |

`gate-core` 可在多个 worktree 同时运行。full 测试只经 `test-full` 或 `gate-full` 运行：两者都通过 `scripts/with_lock.py` 持有主机级锁（`~/.cache/gate-full.lock`），同一主机上的 full 自动排队，等待时打印持有者；不直接调用底层 runner 运行 `tests/full/`。两个门禁都不接受筛选参数。工具链、目录结构或门禁定义变化时运行 `gate-full`。

门禁通过只证明它收录的范围：`gate-core` 证明静态检查、文档检查与 core 测试通过，不证明真实服务、独占资源与部署形态下的行为；`gate-full` 再加上 full 测试收录的范围，不证明真实环境验收（`/acceptance`）。本项目没有 CI，门禁只在本机运行，结果由运行者在交付说明里如实报告；接入 CI 后在此写明哪道门禁在哪里跑。新增、改名或删除 recipe 时同步上表与调用它的脚本、文档。
