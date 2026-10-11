## 运行时与工具链

Homebrew → mise → Bun。`mise.toml` 声明 Bun 的兼容版本 line，`mise.lock` 锁定经验证的精确构建；升级 Bun 时更新 line 并运行 `mise lock` 刷新。Bun 同时是运行时、包管理器、bundler 与测试 runner：`bun install --frozen-lockfile` 是标准安装步骤，`Bun.build` 是默认 bundler，`bun test` 是测试 runner。TypeScript 为唯一源码语言；Biome 负责格式化、lint（recommended 规则起步）与 import 排序，`tsc --noEmit` 是权威类型检查。当前不需要 Node，需要时再由 mise 管理。优先使用 Bun 与 Biome 已有的能力。

## 依赖政策

只在当前需求需要时引入依赖，先用 Bun 内置能力与标准 API。新增依赖用 `bun add`，提交更新后的 `bun.lock`，不手改 lock。`package.json` 中 Biome 精确锁定版本，其余直接依赖使用 caret range；`preinstall` 校验 Bun 版本 line，跨 line 运行必须失败；不因 lockfile 已精确解析而改用 manifest exact pin。单个前端应用不引入 workspaces。升级集中进行并跑完整门禁。

需要相应能力时优先选用：`react` + `react-dom`（页面）、`tailwindcss`（样式）、shadcn/ui（按需引入组件）、`zod`（运行时校验）。不要仅因清单存在而安装。

## 已选依赖

开发依赖：@biomejs/biome、typescript、@types/bun。运行依赖按需添加，并在此登记选择理由或 ADR 链接。
