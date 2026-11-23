## 环境

Node 与 pnpm 由 mise 按根 `mise.toml` 的版本 line 提供、`mise.lock` 锁定精确版本，`mise run` 时自动安装并放进 PATH，不依赖全局安装；依赖由 `{{HOME}}package.json` 与 `{{HOME}}pnpm-lock.yaml` 锁定。
