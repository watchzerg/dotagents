# 测试保留范围

本页记录本仓库 `tests/` 精简后的保留范围，供删改测试或再次执行 `/prune-tests` 时对照。测试规则与门禁命令见根目录 `AGENTS.md` 的“测试与验证”。

## 保留范围（2026-11-22 `/prune-tests` 后）

- setup-dotagents：安装、幂等与冲突时零改动。
- dedupe-images：clean、plan/apply、目录去重、案例与 `apply-decisions`（含 `--check`）主流程，以及命名、页序列、交叉命名的代表用例。
- setup-project：各脚本的新建、已有文件只补缺不覆盖、AGENTS.md 合并、重跑无改动；各 stack 的新项目渲染与 existing 模式；模板 recipe 的 full 判定与 docs-affected、渲染文档通过 docs-check、门禁锁串行；check_docs 的各项规则各一例。

不再维护：错误输入与前置条件缺失、参数化变体矩阵、平台与挂载边界、系统杂项文件过滤、私有函数与回归细节。

产品行为合同不随测试删减而改变，完整门禁通过仅证明上述保留范围。
