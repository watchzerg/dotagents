# 测试设计与门禁

编写、修改、移动或 review 测试，以及制定测试计划、执行 `implement-spec` 时按本文执行。命令与门禁见[开发工作流](../development/workflow.md)。

## 分层

各层的准入、位置、收录入口与资源边界以[测试分层合同](../development/test-layers.md#分层与资源边界)为准。层按资源与运行成本划分，不按测试种类：接真实依赖的集成测试与针对部署形态的系统测试（构建产物或镜像的启动、初始化与停止）都进 full，由 `gate-full` 收录。可重复且结果确定的验证写成自动化测试；依赖真实账号、真实外部服务或人工判断的留给真实环境验收（`/acceptance`），它不进门禁。“验收”只指后者，门禁的结果称通过或失败。

<待填 阶段3：本项目各层的位置>

## 编写与变更

1. 新增或移动测试前确定 core 或 full 归属，在测试计划中注明验证的行为、标准入口和资源需求。
2. 核心业务规则优先通过公开接口的单元测试验证；集成与端到端测试覆盖关键边界和代表性主流程。需要真实接线才能证明的行为放 full，不为进入 core 而 mock 掉待验证的边界。
3. 测试接入所属层的目录和 runner，由标准入口自动发现并被无筛选的门禁收录；以收集清单或运行输出里出现该测试为证，只新增文件、零匹配或沿用旧结果都不算。
4. review 核对分类、收录、资源清理与证据范围。失败和零匹配不是通过；不用 skip、收集过滤或弱化断言让门禁通过。
5. 精简测试用 `/prune-tests`，保留范围写在[测试分层合同](../development/test-layers.md#保留范围)。

## implement-spec 项目覆盖规则

1. 主 agent 派发前读本节，把本节、[测试分层合同](../development/test-layers.md)与[随交付同步](documentation.md#随交付同步)的链接传给 implementer、merger 和后续修复 agent。implementer 在自己的 worktree 内同步本 ticket 影响的模块页；多个 ticket 改同一页时，merger 像处理代码冲突一样处理文档冲突。
2. ticket 阶段的完整门禁只有 core：implementer 在自己的 worktree 内做 core 范围的定向 red → green，报告完成前在包含最新 integration branch 的代码上通过完整的 core 门禁。本 ticket 的 full 测试只经 `mise run <stack>:test-full` 定向运行（带主机锁时排队等待不是失败），不直接调用底层 runner。
3. 报告列出已运行的命令与结果，以及尚未运行的 full 测试与入口；“已集成、core 通过”与“完整门禁通过”分开记录，定向通过不记作完整门禁通过。
4. 所有 ticket 合并、code-review 修复完成后，主 agent 在最终 integration branch 运行无筛选的完整门禁，运行期间工作树不变；之后的任何改动都使结果失效，须重跑。通过前不关闭 spec、不将 PR 标记为 ready。
