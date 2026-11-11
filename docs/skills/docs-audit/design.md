# docs-audit 设计说明

维护 [`skills/docs-audit`](../../../skills/docs-audit/SKILL.md) 前先读本文。记录目标、关键决策、与 setup-project 的耦合和待验收项，只写代码与 git 历史看不出的意图。

## 目标与边界

补 `docs-check` 的缺口：机械检查只管链接、结构、体量与 `covers` 是否匹配文件，查不出正文与代码不符。本 skill 让 agent 逐条对照源码核对当前正文，文档错就地改，其余转票据。不改产品代码，不接门禁或 hook，不自动提交。

## 来源

两个项目各自独立做出了同一件事，2026-11-12 合并为本 skill：

- x-media-saver 的项目级 `doc-audit`（d1e114a）：diff 驱动，从基点找改动源文件所属模块页逐条核对；另有跑 docs-check、处理体量超限、复核调研与 ADR 索引状态列。
- media-glance 的项目级 `docs-drift-audit`（f9b4162）：抽样驱动，随机抽 3 页，只核对顺序与数值两类陈述；差异表加核对条数，非文档错转票据。首次运行抽 3 页 79 条陈述，发现两处文档错。

## 关键决策

- **一个 skill 两种模式**：diff 模式只看本次改动牵涉的页，抓新漂移；抽样模式不看 diff，抓早已积累、任何 diff 都不会再碰到的旧漂移。两者互补，只取一种会丢一半能力。
- **默认抽样模式**：diff 模式与模板随交付同步第 4 步的 `docs-affected` 提示重叠，日常交付已有入口；无参调用更常见的用途是“定期跑一次”，所以无参走抽样。用户 2026-11-12 确认。
- **抽样只核对顺序与数值**：沿用 media-glance 的窄口径，这两类可直接由代码证伪，判定可靠；定义、理由类句子核对成本高、结论含糊。diff 模式的核对维度沿用 x-media-saver 更宽的一套，因为范围已被 diff 限定。
- **不单列跑 docs-check 与体量处理两步**：x-media-saver 的第 1、4 步由 gate-core 中的 `docs-check` 兜底，skill 只在改过文档后跑一次，超预算时按模板拆页规则处理。
- **索引复核放抽样模式**：研究与 ADR 索引的状态列漂移与本次 diff 无关，属于定期维护；每次 diff 模式都复核太重。
- **抽页用 grep 而不扩展检查器**：media-glance 为抽页给检查器加了 `--sourced`；模板检查器不加，`grep '^covers:'` 已足够，避免为一个 skill 增加模板脚本接口。
- **判定五类**：合并两边的类别。media-glance 的“代码注释错”“需产品判断”与 x-media-saver 的“两处正文互相冲突”都保留；处理统一为转票据，不按 tracker 写死 Beads，没有 tracker 约定时只进报告。
- **子 agent 交付标准写进判定节**：沿用 prune-tests 的教训，委派核对时要求每条结论附源码文件与符号，避免子 agent 只读文档就给“一致”。

## 与 setup-project 的耦合

- 读取：`docs/agents/documentation.md`（随交付同步、体量预算与拆页、页面模板）、`docs/agents/issue-tracker.md`、页首 `covers`、`just docs-affected`、`docs/research/INDEX.md`、`docs/adr/INDEX.md`。
- 写入：当前正文与两个索引的行与元数据。
- 模板改动：`templates/docs/agents/documentation.md` 自动检查节末句加“或定期运行 `/docs-audit`”的指路，skill 正文不进模板。
- 退路：没有 `covers` 时按文件名在 `docs/architecture/` 搜归属页；没有 `docs-affected` 时用 git 命令自行匹配。

## 待验收

- 尚未在真实项目上运行。计划：media-glance 指定上次审过的三页跑抽样模式；x-media-saver 拿最近一段提交跑 diff 模式；两处都先看报告质量。
- 两个项目的旧 skill 清理与 media-glance 的 `sources` → `covers` 字段对齐已在各自 Beads 建票（media-glance-7by、x-media-saver-yzh），完成前两边仍用旧 skill。x-media-saver 没有 `covers`，会走退路。
- `sort -R` 在 macOS 与 Linux 的 coreutils 都可用；没有其他平台的验证。
