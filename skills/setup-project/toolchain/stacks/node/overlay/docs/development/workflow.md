## 环境

Node 与 pnpm 由 mise 按根 `mise.toml` 的版本 line 安装并由 `mise.lock` 锁定精确版本，依赖由 `{{HOME}}package.json` 与 `{{HOME}}pnpm-lock.yaml` 锁定。仓库内的 node 与 pnpm 一律通过 `mise exec --` 执行，不依赖全局安装。
