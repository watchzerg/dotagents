# prune-tests 设计说明

维护 [`skills/prune-tests`](../../../skills/prune-tests/SKILL.md) 前先读本文。记录目标、关键决策、与 setup-project 的耦合和待验收项，只写代码与 git 历史看不出的意图。

## 目标与边界

让 agent 对当前项目的测试做一次激进精简：删掉边缘、重复、与实现细节耦合的用例，只留核心规则的代表性单元测试和主流程的集成验证，并把保留下来的测试放回正确的分层。它是一次性的清理动作，不是日常改测试或补测试；不改产品实现，不自动提交。

## 关键决策

- **与 setup-project 分层合同对接，但不强依赖**：skill 先读目标项目 `docs/agents/testing.md` 与 `docs/development/test-layers.md`，有分层就按 core/full 分别给保留标准；没有这些文档的项目退回首版的通用标准（核心单元测试 + 主流程集成测试）。这样 setup-project 初始化过的项目得到具体规则，其他项目仍能用。2026-10-17 由首版的项目无关规则改为分层版本。
- **core 的准入以“可并发”为硬标准**：gate-core 要能在多个 worktree 同时运行，所以 core 测试不能占固定端口、共享数据库、固定目录或桌面焦点，只能用自己申请的临时资源与进程内替身。这条由用户 2026-10-17 明确提出，与模板 `test-layers.md` 的分层合同一致，skill 里单列而不只引用，因为它是归属校正的判断依据。
- **full 的保留范围是 behaviors 主流程加真实接线的核心规则**：用户最初的提法是“gate-full 只覆盖 behaviors 主流程”。严格执行会删掉只能靠真实数据库或子进程证明的核心规则（x-media-saver 用临时 PostgreSQL 验证事务合同就是这类），而 testing.md 又禁止为了进 core 把这些边界 mock 掉。2026-10-17 用户选择保留第二类，条件是报告逐条给理由。
- **主流程清单来自文档，缺文档才推断**：读取顺序与 acceptance 一致：`docs/behaviors/` 优先，退到模块页“当前行为规格”，两处都没有才从代码推断并在报告注明。behaviors 在 full 中零覆盖的主题只列报告、不补测试，和 acceptance 的“未覆盖”口径一致，也符合 skill 不补测试的边界。
- **归属校正顺手做，但只对保留的测试**：清理本来就要逐个看测试，CODING_STANDARDS 也把归属正确列为 review 项，所以放错层的保留测试一并迁移。限制是只改位置和收录、不改替身，避免把 full 测试 mock 成 core 测试来“变快”。
- **保留范围写回固定落点**：x-media-saver 在一次精简后自发长出一节保留范围说明，内容正好是 prune 的产物，于是采纳为固定落点，setup-project 模板加 `按需` 待填标记预留位置。落点最初是 `workflow.md` 里的同名节，2026-11-11 改为 `docs/development/test-layers.md` 的保留范围部分，见下一条。
- **分层合同与保留范围独占一页，只认精确路径**（2026-11-11）：原先读 `workflow.md` 的分层节、写同页的保留范围节，都按节名定位。`workflow.md` 在目标项目里是改代码任务的必读页，这两节对一般任务用不上却每次被读到；节名又是隐性接口，项目把保留范围移到别的页后（bangou 在 `docs/clip/development.md`，x-media-saver 在 `docs/agents/testing.md`），skill 会在 `workflow.md` 里重建一节，内容分叉。改为两者合在 `docs/development/test-layers.md`：读和写是同一份合同的两半，放一页比各占一页少一个路径。skill 不设回退、不依赖节名，文件不存在就新建并接入索引；存量项目与本次改动一起迁移。
- **工具链自检测试不可删**：每个 stack 的工具链测试是 setup-project 用来避免 gate-core 零收集失败的，prune 若按“非核心规则”删掉会让门禁红灯，所以在 skill 里点名保护。
- **full 删空要删目录**：uv 与 node 的 `test-full` recipe 以“目录下是否有该 stack 的测试文件”判定收录，目录不存在或只有其他 stack 文件才提示通过。skill 要求删空后删除目录并先跑收集命令，避免残留文件导致零收集失败。
- **项目约定管结构，保留标准归 skill**：x-media-saver 的 testing.md 与模块边界文档写着 core 层“穷举规则表”，与 skill 压缩参数化矩阵的要求冲突；2026-10-17 的首次真实运行选择 skill 覆盖项目文档并把两处改成“每条规则保留代表行”。原先“命中即以项目约定为准”没有区分这两类，换一次运行可能反过来保留全部用例，因此在约定来源节明示：项目文档决定目录、入口、资源边界与串行约束，保留标准以 skill 为准，项目文档里的穷举要求按文档同步改写。
- **去留结论必须引用断言**：同一次运行里 Web/扩展层的分析子 agent 只看测试名就给出了方案，并自述未读正文；原规则“不能仅凭名称决定去留”是放在约定来源节末尾的禁令，没有落到执行步骤的完成标准里，委派时也没有传给子 agent。改为执行步骤中的正向标准：每条结论写明该测试断言的可观察结果及对应规则或主流程来源，委派分析时作为子 agent 交付标准，名称判断在产出中直接暴露为缺项。
- **按内容定位编辑，门禁由发起者运行**：同一次运行里 integration 子 agent 用行号范围 `sed -i` 删断言被 auto 模式权限分类器拒绝，`just test-full` 也被拒；主 agent 与 core 子 agent 用 Edit 工具或匹配内容的脚本编辑则全部顺利。行号范围删除在多 agent 并发编辑时本就脆弱，所以 skill 要求按内容定位，门禁与 full 测试由发起 skill 的 agent 运行。
- **只跑 `gate-full`**：模板与真实项目的 `gate-full` 都依赖 `gate-core`，原先基线和收尾都要求两者并跑，core 层每次重复一遍。改为只跑 `gate-full`，gate-core 耗时从输出或单独计时取。
- **结束时留一张已关闭的票**（2026-11-13）：`/optimize` 的三个主题都经 spec 与票据留痕，精简测试原先只在报告和 `test-layers.md` 里留下结果，查不到哪天删了多少。执行步骤末尾加一步，按项目 tracker 建一张票并立即关闭，记录各层前后的文件数、用例数与保留范围。由某张票据发起时（如 `/optimize arch` 拆出的测试精简票）记入那张票，不另建；没有 tracker 约定的项目跳过并在报告注明，保持“不强依赖 setup-project”。

## 与 setup-project 的耦合

- 读取：`docs/agents/testing.md` 分层节、`docs/development/test-layers.md`、`docs/behaviors/`、模块页“当前行为规格”与“代码与验证入口”、justfile 的 `test`/`test-full`/`gate-core`/`gate-full` 契约。
- 读取（留痕时）：`docs/agents/issue-tracker.md`。
- 写入：`docs/development/test-layers.md` 的保留范围部分，模块页“代码与验证入口”；tracker 中一张已关闭的留痕票。
- 模板改动：`templates/docs/development/test-layers.md` 含分层合同与 `按需` 的保留范围节（2026-10-17 起在 `workflow.md`，2026-11-11 移到本页）；`templates/docs/agents/testing.md` 的“编写与变更”有一条，精简或大幅删减测试按 `/prune-tests` 执行并落到该页。

## 真实运行记录

2026-10-17 在 x-media-saver 首次运行分层版本：既有的保留范围节被识别并改写，ledger 事务合同、真子进程 smoke、生产产物、执行锁 busy、临时 Git remote 发布等 full 测试按第二类保留且报告逐条给了理由；core 后端 417 → 109、Web 100 → 38、扩展 5 → 4、integration 49 → 35，无筛选 `gate-full` 通过，耗时 61s → 42s。agent 未经指令自发采用的执行形状：按层拆三个只读分析子 agent 并行出方案，主 agent 批准后由同一批子 agent 在各自目录内编辑，文档同步与门禁由主 agent 收口；该形状有效，不写进 SKILL.md，仅供下次对照。暴露的问题已记入关键决策的后四条。

## 待验收

- 修订后的执行步骤（引用断言的去留结论、按内容定位编辑、只跑 `gate-full`）尚未在真实项目上重跑验证。
- 留痕票这一步（2026-11-13 加）未经真实运行：建票后立即关闭在 Beads 上是否顺畅、由票据发起时是否正确改为记入原票，待下次运行确认。
- 没有 behaviors/ 与 testing.md 的项目是否仍能顺畅走通用标准，需要一个非 setup-project 项目验证。
- node 与 swift 的收集验证命令在 skill 里只给了示例，真实 stack 上以什么命令确认“仍被标准入口发现”待确认。

## 演进记录

| 日期 | 变更 | 依据 |
| --- | --- | --- |
| 2026-10-17 | 由项目无关的通用规则改为按 core/full 分层：约定来源读取顺序、core 可并发硬标准、full 的两类保留、归属校正、门禁收尾与空目录、工具链测试保护、文档同步落点、报告按层分列；description 改中文；setup-project 模板加保留范围按需节与 testing.md 一条 | 本文关键决策 |
| 2026-10-17 | x-media-saver 首次真实运行后的 retro：约定来源节明示项目约定管结构、保留标准归 skill；执行步骤新增“逐个读正文、结论引用断言”并作为委派交付标准，替换原禁令句；编辑按内容定位，门禁由发起者运行；基线与收尾只跑 `gate-full`；文档同步节改为模块页“代码与验证入口”内的说明项、full 目录不再写死 `tests/full/`、覆盖要求类表述一并同步 | 真实运行记录 |
| 2026-11-11 | 分层合同与保留范围由 `workflow.md` 的两节改为独占 `docs/development/test-layers.md`，只认该路径、不设回退，文件不存在时新建并接入索引；模板同步，四个存量项目随同迁移 | 本文关键决策 |
| 2026-11-13 | 执行步骤末尾加留痕：建一张已关闭的票记录前后文件数、用例数与保留范围；由票据发起时记入原票，无 tracker 约定时跳过；完成报告加票据编号 | [optimize 设计说明](../optimize/design.md)的衔接约定 |
