# prune-tests 设计说明

维护 [`skills/prune-tests`](../../../skills/prune-tests/SKILL.md) 前先读本文。只记代码与 git 历史看不出的意图。

## 目标与边界

对当前项目的测试做一次激进精简：删掉边缘、重复、与实现细节耦合的用例，只留核心规则的代表性单元测试和主流程的集成验证，并把保留的测试放回正确分层。它是一次性清理，不是日常改测试或补测试；不改产品实现，不自动提交。

## 与 setup-project 的耦合

- 读取：`docs/agents/testing.md` 分层节、`docs/development/test-layers.md`、`docs/behaviors/`、模块页“当前行为规格”与“代码与验证入口”、`mise.toml` 与 `mise-tasks/` 的 `test`/`test-full`/`gate-core`/`gate-full` 契约；留痕时读 `docs/agents/issue-tracker.md`。
- 写入：`test-layers.md` 的保留范围部分、模块页“代码与验证入口”、tracker 中一张已关闭的留痕票。
- 模板侧：`templates/docs/development/test-layers.md` 含分层合同与 `按需` 的保留范围节；`templates/docs/agents/testing.md` 的“编写与变更”有一条指向 `/prune-tests` 与该页。

## 关键决策

- **按分层合同对接，但不强依赖 setup-project**：有 core/full 分层就分层给保留标准，没有就退回通用标准（核心单元测试 + 主流程集成测试），其他项目仍能用。
- **core 准入以“可并发”为硬标准**：gate-core 要在多个 worktree 同时运行。这条与模板 `test-layers.md` 一致，仍在 skill 里单列，因为它是归属校正的判断依据，且无分层文档的项目也要用。
- **full 保留 behaviors 主流程加真实接线的核心规则**：只留主流程会删掉只能靠真实数据库或子进程证明的规则（x-media-saver 用临时 PostgreSQL 验证事务合同），而 testing.md 禁止为进 core 把这些边界 mock 掉。用户选择保留第二类，条件是报告逐条给理由。
- **主流程清单来自文档，缺文档才推断**：读取顺序与 acceptance 一致（behaviors → 模块页 → 代码）；零覆盖的主题只列报告、不补测试，与 acceptance 的“未覆盖”口径一致。
- **项目约定管结构，保留标准归 skill**：x-media-saver 的项目文档要求 core “穷举规则表”，与压缩参数化矩阵冲突。若只写“命中即以项目约定为准”，换一次运行可能保留全部用例，所以明确分工，并让文档同步改写这类要求。
- **归属校正只对保留的测试顺手做**：清理本来要逐个看测试，归属也是 review 项。只改位置和收录、不改替身，避免把 full 测试 mock 成 core 来“变快”。
- **分层合同与保留范围独占 `test-layers.md`，只认精确路径**：原先按节名读写 `workflow.md`，一是让每个改代码任务多读两节用不上的内容，二是节名成了隐性接口，项目把保留范围挪走后 skill 会在原处重建一节导致分叉。读与写是同一份合同的两半，合一页；不设回退、不依赖节名，文件不存在就新建并接入索引。
- **工具链自检测试不可删**：它们是 setup-project 用来避免 gate-core 零收集失败的，按“非核心规则”删掉会让门禁变红。
- **full 删空要删目录**：uv 与 node 的 `test-full` 按“目录下是否有该 stack 的测试文件”判定收录，残留文件会零收集失败。
- **去留结论必须引用断言**：x-media-saver 运行中分析子 agent 只看测试名就给出方案。原来的“不能仅凭名称决定去留”是一句禁令，没落到步骤的完成标准、也没传给子 agent；改为正向交付标准后，名称判断在产出里直接暴露为缺项。
- **按内容定位编辑，门禁由发起者运行**：同次运行里子 agent 用行号范围 `sed -i` 删断言和直接跑 full 测试都被 auto 模式权限分类器拒绝；按内容编辑则顺利，且行号范围在多 agent 并发编辑时本就脆弱。
- **只跑 `gate-full`**：`gate-full` 依赖 `gate-core`，并跑两者会重复 core。
- **删除后的清理交给 typecheck 与 lint 定位、逐个删声明**：grok-media-saver 运行为删测试写了八个一次性脚本，接连出错（扫描器不认模板字符串 `${}`；删 `for` 包裹的测试只删了循环头；单参数 `test.each` 残留比较；Biome `--unsafe` 把未用函数改名为 `_name` 而不删；去下划线脚本截断多行签名）。这些具体坑只记在本文。
- **结束时留一张已关闭的票**：使 `/optimize` 与精简测试都有票据留痕，可查哪天删了多少。由票据发起时（如 `/optimize arch` 拆出的票）记入原票；没有 tracker 约定的项目跳过，保持不强依赖。先拿编号再关闭：同次运行把 create、解析 ID 与 close 串成一条命令，create 失败后 close 拿到空 ID，报错掩盖了真正的 `no beads database found`。该报错的恢复（`bd bootstrap`）归 setup-project 模板与 `init_beads.py`，本 skill 不重复。
- **报告给出删后耗时分布，只列不改**：grok-media-saver 删后 `gate-full` 仍要 105s，逐文件计时才发现约 70s 花在每个文件各启动一次 PostgreSQL 容器上（改为共用后 46s）。列为后续项以守住不扩大范围的边界。

## 运行参考

- x-media-saver（2026-10-17，分层版首次）：core 后端 417 → 109、Web 100 → 38、扩展 5 → 4、integration 49 → 35，`gate-full` 61s → 42s。agent 自发采用的形状有效：按层拆只读分析子 agent 并行出方案，主 agent 批准后由同批子 agent 在各自目录编辑，文档同步与门禁由主 agent 收口。不写进 SKILL.md，供下次对照。
- grok-media-saver（2026-11-22，无 behaviors 与 `test-layers.md`）：core 36 → 10、full 388 → 33，`gate-full` 409.9s → 105s，新建 `test-layers.md`。
- 本仓库（2026-11-22，通用标准）：120 → 40 个用例。本仓库不套用 setup-project 结构，保留范围写在 `docs/testing.md`，未新建 `test-layers.md`。

## 待验收

- 引用断言的去留结论、按内容定位编辑、只跑 `gate-full`、typecheck/lint 清理、耗时分布、分步建票这些措辞尚未在真实项目上重跑验证。
- 留痕票未经真实运行：Beads 上建后即关是否顺畅、由票据发起时是否正确记入原票。
- 待决：`test-layers.md` 不存在时一律新建，与刻意不用模板结构的项目（如本仓库）冲突；是否改为“项目另有落点时从其约定”。
- node 与 swift 上确认“仍被标准入口发现”的收集命令只给了示例，待真实 stack 确认。
