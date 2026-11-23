# docs-audit 设计说明

维护 [`skills/docs-audit`](../../../skills/docs-audit/SKILL.md) 前先读本文。只写代码与 git 历史看不出的意图。

## 目标与边界

补 `docs-check` 的缺口：机械检查只管链接、结构、体量与 `covers` 是否匹配文件，查不出正文与代码不符。本 skill 让 agent 逐条对照源码核对当前正文，文档错就地改，其余转票据。不改产品代码，不接门禁或 hook，不自动提交。

来源是两个项目各自做出的同一件事：x-media-saver 的 `doc-audit`（diff 驱动，核对维度宽，含索引复核）与 media-glance 的 `docs-drift-audit`（随机抽 3 页，只核对顺序与数值，非文档错转票据），合并为本 skill。

## 关键决策

- **一个 skill 两种模式**：diff 模式抓本次改动带来的新漂移；抽样模式抓早已积累、任何 diff 都不会再碰到的旧漂移。只取一种会丢一半能力。
- **默认抽样模式**：diff 模式与模板随交付同步里的 `docs-affected` 提示重叠，日常交付已有入口；无参调用的常见用途是定期跑一次。用户确认。
- **抽样只核对顺序与数值**：这两类可直接由代码证伪，判定可靠；定义、理由类核对成本高、结论含糊。diff 模式范围已被 diff 限定，用更宽的维度。
- **抽页只认页首 `covers`，用 awk 而不扩展检查器**：`grep '^covers:'` 会命中模板 `documentation.md` 正文里的 frontmatter 示例，凡由模板初始化的项目都会误抽该页（真实运行中发生过）。awk 只看首个 `---` 块即可，不为一个 skill 给模板检查器加接口。
- **抽样模式每页一个子 agent，交付标准是每条附源码文件与符号**：真实运行中，主 agent 自读十余个源文件时只报“约 30 条”，“一致”项没有逐条证据；每页委派的两个项目返回了逐条表格与精确条数。主 agent 只复核非一致结论。
- **判定五类**：保留两边的类别（代码注释错、需产品判断、正文冲突）。正文冲突限定为代码判不了的情况：代码支持其中一处时另一处就是文档错，否则会出现判成冲突又就地改、与“冲突原样保留”相悖的情况（真实运行中发生过）。
- **票据标签两档**：代码注释错范围明确，标 `ready-for-agent`；需产品判断、正文冲突与顺带发现的代码缺陷标 `needs-triage`。真实运行中同类问题出现过标签不一致。tracker 不写死 Beads，没有约定时只进报告。
- **顺带发现的代码缺陷单列**：真实运行中有的放差异表外、有的塞进差异表；统一为建票、报告单列。
- **索引复核只在抽样模式，看状态是否符合现状**：索引状态漂移与本次 diff 无关，属于定期维护。机械比对索引与 frontmatter 在三个项目都无发现（已有脚本生成或检查器兜底），唯一有用的发现是一条已落地仍写“已采纳”的 ADR，那是对照现状的判断；所以有兜底时跳过机械比对。
- **不单列跑 docs-check 与体量处理**：由 gate-core 中的 `docs-check` 兜底，skill 只在改过文档后跑一次，超预算时按模板拆页规则处理。

## 与 setup-project 的耦合

- 读取：`docs/agents/documentation.md`（随交付同步、体量预算与拆页、页面模板）、`docs/agents/issue-tracker.md`、页首 `covers`、`mise run docs-affected`、`docs/research/INDEX.md`、`docs/adr/INDEX.md`。
- 写入：当前正文与两个索引的行与元数据。
- 模板只在 `templates/docs/agents/documentation.md` 自动检查节末句留“或定期运行 `/docs-audit`”的指路，skill 正文不进模板。
- 退路：没有 `covers` 时按文件名在 `docs/architecture/` 搜归属页；没有 `docs-affected` 时用 git 命令自行匹配。

## 待验收

- 2026-11-13 在 bangou、x-media-saver、media-glance 各跑一次无参抽样模式：分别核对 136、73、约 60 条陈述；文档错就地改 6、0、1 处，代码注释错转票 2、1、1 张，需产品判断 1 张（bangou）；索引复核只在 media-glance 改了一条 ADR 状态。三个项目都已有 `covers`。
- 未经真实运行：diff 模式、无 `covers` 退路；上述运行后的修正（awk 抽页、每页子 agent、正文冲突判定、ADR 状态复核、标签两档），下次抽样重点看。
- 抽页命令在 Ubuntu（GNU awk、coreutils）与 macOS（系统 awk、`sort -R`）上用临时样例核对过，只认页首 `covers`；未在真实项目的 macOS 运行中验证。
- 两个来源项目的旧 skill 清理与 media-glance 的 `sources` → `covers` 字段对齐已在各自 Beads 建票（media-glance-7by、x-media-saver-yzh）。
