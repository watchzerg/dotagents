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

## 首轮真实运行后的修正（2026-11-13）

依据见[待验收](#待验收)记录的三次抽样运行。

- **抽页只认页首 `covers`**：`grep '^covers:'` 会命中模板 `documentation.md` 正文里的 frontmatter 示例，凡由模板初始化的项目都会误抽该页（media-glance 实际抽中，bangou 同样会命中）。改用 awk 只看首个 `---` 块；仍不扩展检查器。
- **抽样模式每页一个子 agent**：bangou、x-media-saver 每页派一个子 agent，返回逐条表格与精确条数；media-glance 由主 agent 自读十余个源文件，只报“约 30 条”，“一致”项没有逐条证据。改为默认每页委派，主 agent 只复核非一致结论。
- **正文冲突限定为代码判不了**：bangou 把“两处矛盾、代码支持一处”判成正文冲突后又就地改了，与“冲突原样保留”相悖。代码支持一处时另一处就是文档错。
- **ADR 复核改看状态是否符合现状**：三个项目的索引与 frontmatter 比对都无发现（media-glance 索引由脚本生成，bangou 检查器已校验）；唯一有用的发现是 media-glance 一条已落地仍写“已采纳”的 ADR，那是对照现状的判断。已有生成或检查兜底时跳过机械比对。
- **顺带发现的代码缺陷单列**：x-media-saver 与 bangou 都发现了与正文无关的缺陷，一个放差异表外、一个塞进差异表。统一为建 `needs-triage` 票据、报告单列。
- **票据标签写死两档**：同为代码注释错，x-media-saver 标 `needs-triage`，另两个标 `ready-for-agent`。注释错范围明确，定为 `ready-for-agent`；需产品判断、正文冲突与代码缺陷定为 `needs-triage`。

## 与 setup-project 的耦合

- 读取：`docs/agents/documentation.md`（随交付同步、体量预算与拆页、页面模板）、`docs/agents/issue-tracker.md`、页首 `covers`、`just docs-affected`、`docs/research/INDEX.md`、`docs/adr/INDEX.md`。
- 写入：当前正文与两个索引的行与元数据。
- 模板改动：`templates/docs/agents/documentation.md` 自动检查节末句加“或定期运行 `/docs-audit`”的指路，skill 正文不进模板。
- 退路：没有 `covers` 时按文件名在 `docs/architecture/` 搜归属页；没有 `docs-affected` 时用 git 命令自行匹配。

## 待验收

- 2026-11-13 在 bangou、x-media-saver、media-glance 各跑一次无参抽样模式：分别核对 136、73、约 60 条陈述；文档错就地改 6、0、1 处，代码注释错转票 2、1、1 张，需产品判断 1 张（bangou）；索引复核只在 media-glance 改了一条 ADR 状态。三个项目都已有 `covers`。diff 模式与无 `covers` 退路仍未经真实运行。
- 首轮运行后的修正（见上节）尚未经真实运行验证，下次抽样时重点看子 agent 简报、正文冲突判定与 ADR 状态复核。
- 两个项目的旧 skill 清理与 media-glance 的 `sources` → `covers` 字段对齐已在各自 Beads 建票（media-glance-7by、x-media-saver-yzh）。
- `sort -R` 在 macOS 与 Linux 的 coreutils 都可用；没有其他平台的验证。
