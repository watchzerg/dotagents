## 运行时与工具链

Homebrew → mise → Node 与 pnpm。`mise.toml` 声明 Node 与 pnpm 的兼容版本 line，`mise.lock` 锁定经验证的精确构建；升级时更新 line 并运行 `mise lock` 刷新。pnpm 是包管理器，`pnpm install --frozen-lockfile` 是标准安装步骤。

TypeScript 为唯一源码语言；Vitest 是测试 runner；Biome 负责格式化、lint（recommended 规则起步）与 import 排序，`tsc --noEmit` 是权威类型检查。`package.json` 的 `preinstall` 校验 Node 版本 line，跨 line 运行必须失败。

应用层选型固定为 React + Vite + Tailwind CSS + shadcn/ui，组件测试用 React Testing Library；初始化只落工具链，这些依赖在写第一个页面时按依赖政策加入。

## 依赖政策

只在当前需求需要时引入依赖，先用平台与标准 API。新增依赖用 `pnpm add`，提交更新后的 `pnpm-lock.yaml`，不手改 lock。Biome 精确锁定版本，其余直接依赖使用 caret range；不因 lockfile 已精确解析而改用 manifest exact pin。单个前端应用不引入 workspaces。升级集中进行并跑完整门禁。

需要相应能力时按固定选型引入：`vite` + `@vitejs/plugin-react`（dev server 与构建）、`react` + `react-dom`（页面）、`tailwindcss` + `@tailwindcss/vite`（样式）、shadcn/ui（用其 CLI 按需把组件加入源码）、`@testing-library/react` + `jsdom`（组件测试，Vitest 环境设为 jsdom）、`zod`（运行时校验）。不要仅因清单存在而安装。

## 已选依赖

开发依赖：@biomejs/biome、typescript、vitest、@types/node。运行依赖按需添加，并在此登记选择理由或 ADR 链接。
