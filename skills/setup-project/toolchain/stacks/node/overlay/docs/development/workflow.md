## 环境

Node 与 pnpm 由 mise 按根 `mise.toml` 的版本 line 安装并由 `mise.lock` 锁定精确版本，依赖由 `{{HOME}}package.json` 与 `{{HOME}}pnpm-lock.yaml` 锁定。node 与 pnpm 由 mise 按目录切换（shell 需启用 `mise activate` 或 mise shims），`just check-toolchain` 核对实际版本，不依赖与项目版本 line 不符的全局安装。
