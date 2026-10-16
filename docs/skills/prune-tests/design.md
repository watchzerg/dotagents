# prune-tests 设计说明

维护 [`skills/prune-tests`](../../../skills/prune-tests/SKILL.md) 前先读本文。记录目标、关键决策、与 setup-project 的耦合和待验收项，只写代码与 git 历史看不出的意图。

## 目标与边界

让 agent 对当前项目的测试做一次激进精简：删掉边缘、重复、与实现细节耦合的用例，只留核心规则的代表性单元测试和主流程的集成验证，并把保留下来的测试放回正确的分层。它是一次性的清理动作，不是日常改测试或补测试；不改产品实现，不自动提交。

## 关键决策

- **与 setup-project 分层合同对接，但不强依赖**：skill 先读目标项目 `docs/agents/testing.md` 与 `docs/development/workflow.md` 的分层节，有分层就按 core/full 分别给保留标准；没有这些文档的项目退回首版的通用标准（核心单元测试 + 主流程集成测试）。这样 setup-project 初始化过的项目得到具体规则，其他项目仍能用。2026-10-17 由首版的项目无关规则改为分层版本。
- **core 的准入以“可并发”为硬标准**：gate-core 要能在多个 worktree 同时运行，所以 core 测试不能占固定端口、共享数据库、固定目录或桌面焦点，只能用自己申请的临时资源与进程内替身。这条由用户 2026-10-17 明确提出，与模板 workflow.md“测试分层与资源边界”一致，skill 里单列而不只引用，因为它是归属校正的判断依据。
- **full 的保留范围是 behaviors 主流程加真实接线的核心规则**：用户最初的提法是“gate-full 只覆盖 behaviors 主流程”。严格执行会删掉只能靠真实数据库或子进程证明的核心规则（x-media-saver 用临时 PostgreSQL 验证事务合同就是这类），而 testing.md 又禁止为了进 core 把这些边界 mock 掉。2026-10-17 用户选择保留第二类，条件是报告逐条给理由。
- **主流程清单来自文档，缺文档才推断**：读取顺序与 acceptance 一致：`docs/behaviors/` 优先，退到模块页“当前行为规格”，两处都没有才从代码推断并在报告注明。behaviors 在 full 中零覆盖的主题只列报告、不补测试，和 acceptance 的“未覆盖”口径一致，也符合 skill 不补测试的边界。
- **归属校正顺手做，但只对保留的测试**：清理本来就要逐个看测试，CODING_STANDARDS 也把归属正确列为 review 项，所以放错层的保留测试一并迁移。限制是只改位置和收录、不改替身，避免把 full 测试 mock 成 core 测试来“变快”。
- **保留范围写回 workflow.md 的 `## 回归覆盖与保留范围`**：x-media-saver 在一次精简后自发长出这一节，内容正好是 prune 的产物。采纳同名节作为固定落点，setup-project 模板加 `按需` 待填标记预留位置；没有该节的老项目由 skill 新建。
- **工具链自检测试不可删**：每个 stack 的工具链测试是 setup-project 用来避免 gate-core 零收集失败的，prune 若按“非核心规则”删掉会让门禁红灯，所以在 skill 里点名保护。
- **full 删空要删目录**：uv 与 bun 的 `test-full` recipe 以“目录下是否有该 stack 的测试文件”判定收录，目录不存在或只有其他 stack 文件才提示通过。skill 要求删空后删除目录并先跑收集命令，避免残留文件导致零收集失败。

## 与 setup-project 的耦合

- 读取：`docs/agents/testing.md` 分层节、`docs/development/workflow.md` 的“测试分层与资源边界”、`docs/behaviors/`、模块页“当前行为规格”与“代码与验证入口”、justfile 的 `test`/`test-full`/`gate-core`/`gate-full` 契约。
- 写入：`docs/development/workflow.md` 的 `## 回归覆盖与保留范围`，模块页“代码与验证入口”。
- 模板改动（2026-10-17）：`templates/docs/development/workflow.md` 新增 `## 回归覆盖与保留范围` 按需节；`templates/docs/agents/testing.md` 的“编写与变更”加一条，精简或大幅删减测试按 `/prune-tests` 执行并落到该节。

## 待验收

- 分层版本尚未在真实项目上运行。首个目标：在 x-media-saver 上重跑一次，核对它既有的“回归覆盖与保留范围”节能被识别并改写，事务合同类 full 测试按第二类保留且报告给出理由。
- 没有 behaviors/ 与 testing.md 的项目是否仍能顺畅走通用标准，需要一个非 setup-project 项目验证。
- bun 与 swift 的收集验证命令在 skill 里只给了示例，真实 stack 上以什么命令确认“仍被标准入口发现”待确认。

## 演进记录

| 日期 | 变更 | 依据 |
| --- | --- | --- |
| 2026-10-17 | 由项目无关的通用规则改为按 core/full 分层：约定来源读取顺序、core 可并发硬标准、full 的两类保留、归属校正、门禁收尾与空目录、工具链测试保护、文档同步落点、报告按层分列；description 改中文；setup-project 模板加 `回归覆盖与保留范围` 按需节与 testing.md 一条 | 本文关键决策 |
