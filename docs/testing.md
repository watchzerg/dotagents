# 测试保留范围

本仓库 `tests/` 精简后的保留范围，删改测试或再次执行 `/prune-tests` 前对照。测试规则见根目录 `AGENTS.md` 的“测试与验证”。

## 保留范围（2026-11-22 `/prune-tests` 后）

- setup-dotagents：安装（含 Codex 全局规则入口）、幂等与冲突时零改动。
- setup-harness：按 PATH 检测 harness、JSON 与 TOML 配置项合并且保留其他设置、幂等；冲突时零改动，`--force` 后覆盖。Codex 用例覆盖 `CODEX_HOME`、原生数组合并及多行数组覆盖。
- dedupe-images：clean、plan/apply、目录去重、案例与 `apply-decisions`（含 `--check`）主流程，以及命名、页序列、交叉命名的代表用例。
- setup-project：各脚本的新建、已有文件只补缺不覆盖、AGENTS.md 合并、重跑无改动；各 stack 的新项目渲染与 existing 模式；模板 recipe 的 full 判定与 docs-affected、渲染文档通过 docs-check、门禁锁串行；check_docs 的各项规则各一例。
- roam：push 推送领先分支、只对有 `.beads/` 的项目执行 Dolt；pull 快进、无冲突 rebase、冲突回滚、脏工作区跳过、非当前 main 快进、缺本地库时 bootstrap。

不再维护：错误输入与前置条件缺失、参数化变体矩阵、平台与挂载边界、系统杂项文件过滤、私有函数与回归细节。

完整门禁通过只证明上述保留范围；行为合同不因测试删减而改变。
