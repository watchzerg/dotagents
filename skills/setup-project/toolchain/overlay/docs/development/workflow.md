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
| `just docs-check` | 文档链接、章节锚点与模块页可达性 |
| `just gate-core` | 工具链检查 → docs-check → lint → typecheck → 全部 core 测试，首错停止 |
| `just gate-full` | gate-core 后在主机锁内串行运行 full 测试：{{FULL}} |

`gate-core` 可在多个 worktree 同时运行。full 测试只经 `test-full` 或 `gate-full` 运行：两者都通过 `scripts/with_lock.py` 持有主机级锁（`~/.cache/gate-full.lock`），同一主机上的 full 自动排队，等待时打印持有者；不直接调用底层 runner 运行 `tests/full/`。两个门禁都不接受筛选参数。工具链、目录结构或门禁定义变化时运行 `gate-full`。

## 测试分层与资源边界

测试归属由目录与门禁入口固定维护，不由单次任务临时判断能否并行。

| 层级 | 位置与收录 | 准入 | 资源要求 |
| --- | --- | --- | --- |
| core | {{CORE}}；由 `just test` 与 `gate-core` 执行 | 单元测试和轻量、结果确定的测试，秒级完成；不启动真实服务、数据库、浏览器或桌面会话，不执行 E2E | 不依赖共享可变状态、固定端口、桌面焦点或共享浏览器 Profile；可跨 worktree 并行 |
| full | {{FULL}}；目录出现即由 `gate-full` 收录，目录存在而无测试视为失败；定向运行用 `just test-full` | 重型测试、真实基础设施集成、E2E 以及需要独占资源的测试；即使已隔离也按验证范围归入 | 尽量隔离：只监听 loopback、按实例分配端口、独立临时目录与数据库；主机锁保证同一时刻只有一个 full 入口在跑；成功、失败、取消路径都清理自身资源 |

core 不以"当前恰好没冲突"作为准入证据，要检查 fixture、子进程和输出路径的实际副作用；新增真实服务、共享状态或显著运行成本时重新分类。不得通过 skip、收集过滤或弱化断言让门禁通过，零匹配不是通过。新增或移动的测试必须被对应入口自动发现，并被无筛选的 `gate-full` 收录。
