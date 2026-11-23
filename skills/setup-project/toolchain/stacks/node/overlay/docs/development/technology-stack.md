## 运行时与工具链

mise → Node 与 pnpm。根 `mise.toml` 钉 Node 与 pnpm 的兼容版本 line，`mise.lock` 锁定精确版本；升级时更新 line 并运行 `mise lock`。`package.json` 的 `preinstall` 校验 Node 版本 line，跨 line 运行即失败。

TypeScript 为唯一源码语言；Biome 负责格式化、lint（recommended 规则起步）与 import 排序，`tsc --noEmit` 是权威类型检查，Vitest 是测试 runner。

应用层选型固定为 React + Vite + Tailwind CSS + shadcn/ui，组件测试用 React Testing Library；初始化只落工具链，这些依赖在写第一个页面时加入。

## 依赖政策

新增依赖用 `pnpm add`，提交更新后的 `pnpm-lock.yaml`，不手改 lock，安装用 `pnpm install --frozen-lockfile`。Biome 精确锁定版本，其余直接依赖用 caret range。单个前端应用不引入 workspaces。

优先选型：`vite` + `@vitejs/plugin-react`（dev server 与构建）、`react` + `react-dom`（页面）、`tailwindcss` + `@tailwindcss/vite`（样式）、shadcn/ui（用其 CLI 按需把组件加入源码）、`@testing-library/react` + `jsdom`（组件测试，Vitest 环境设为 jsdom）、`zod`（运行时校验）。

## 已选依赖

开发依赖：@biomejs/biome、typescript、vitest、@types/node。
