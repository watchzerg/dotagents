## 环境

Bun 由 mise 按根 `mise.toml` 的版本 line 安装并由 `mise.lock` 锁定精确版本，依赖由 `{{HOME}}package.json` 与 `{{HOME}}bun.lock` 锁定。仓库内的 Bun 一律通过 `mise exec -- bun` 执行，不依赖全局安装。
