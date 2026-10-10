# setup-project 设计说明

维护本 skill 前先读本文。记录目标、阶段状态、关键决策和演进，只写代码与 git 历史看不出的意图；结构细节见 [docs-structure.md](docs-structure.md)，Beads 依据见 [beads-init-research.md](beads-init-research.md)。

## 目标与边界

把个人新项目的初始化固化为可重复的步骤：Beads、Matt Pocock skills 前置检查、标准化文档结构、开发环境。安装在用户级，对调用时的当前工作目录生效。只服务个人项目，不做多版本兼容、不迁移已有项目的旧文档。

## 阶段状态

| 阶段 | 状态 | 实现方式 |
| --- | --- | --- |
| 1.1 Beads 初始化 | 已确定 | `scripts/init_beads.py` |
| 1.2 Matt setup 检查 | 已确定 | 检查 `docs/agents/issue-tracker.md` 与 `domain.md` 存在；阶段 2 脚本重复检查 |
| 2 文档结构 | 已确定，未经真实 agent 验收 | `templates/` + `scripts/init_docs.py` + SKILL.md 的合并与待填规则 |
| 3 开发环境 | 待讨论 | 预期产出 justfile、工具链文件，并填入 `docs/development/` 与 `testing.md` 的待填位 |

## 关键决策

- **脚本与提示混合**：确定性的事（检查前置、复制文件、不覆盖）交给标准库脚本并测试；需要读项目现状判断的事（合并已有 AGENTS.md、填 `<待填>`）交给 agent，规则写在 SKILL.md。放弃纯提示驱动，因为结构会漂移且无法测试。
- **缺失才创建，不用软链接**：文档进入目标项目后随项目持续改写，软链接会让所有项目共享一份。已有文件一律不碰，所以脚本可重复运行。
- **Matt setup 是前置而非内置**：`docs/agents/` 的三个文件由 Matt 的 setup 交互产生，本 skill 不复制也不模板化，只检查存在。原因是 tracker 选择和标签映射需要用户回答，且 Matt 的 skill 会自行更新这些文件。
- **根目录四个硬约束路径**：`GLOSSARY.md`、`docs/adr/`、`docs/agents/` 是 Matt skills 直接按路径读写的位置，`CODING_STANDARDS.md` 是 code-review 按名查找的；其余目录可按项目调整。
- **`## Agent skills` 块压缩进触发表**：Matt 的 setup 是本 skill 的前置，之后不再重跑，其三个指针并入触发表后该块被脚本移除。若有人重跑 Matt setup 追加了新块，再跑本 skill 会再次移除。
- **AGENTS.md 按节合并而非整文件跳过**：它与 Matt setup、用户共用，所以以二级标题为单位，缺的节追加、已有的节不动、标题外内容保留，重复运行无变更。其他模板文件只属于本 skill，整文件缺失才创建即可。
- **不设 `archive/`、`plans/`、ADR 索引**：参考项目里的归档层来自 Beads 之前的遗留文档；新项目用 tracker 承载增量，git 承载历史。
- **`<待填 时机：说明>` 协议**：初始化不编造项目内容，留显式标记并注明可填时机（初始化、阶段3、首个模块、按需）；AGENTS.md 常驻约束要求每次交付前搜索并按时机填写，全部消失后该条自删。不另建待填清单文件：grep 即清单，独立文件会漂移。这是空项目里让文档"逐步长出来"的机制，也是因为用户在初始化时同样答不出架构类问题，所以不向用户询问。
- **AGENTS.md 只放指针**：触发表唯一，细则进正文；retro 产出的规则落 `CODING_STANDARDS.md`。

## 明确不做

- 不生成模块页、ADR、调研文件的实例；这些由 Matt 的 skills 或日常迭代惰性创建。
- 不处理 `CLAUDE.md` 与 `AGENTS.md` 并存的合并，SKILL.md 只要求 agent 把块移到 AGENTS.md 并让 CLAUDE.md 指向它。
- 不提供文档链接检查工具；这属于阶段 3 的 justfile。

## 待验收

- 在一个真实新项目上让 agent 完整执行阶段 2 的第 2 到 4 步，检查合并是否保留用户内容、待填是否被编造。
- 阶段 3 落地后回看 `testing.md`、`workflow.md`、`technology-stack.md` 的待填位是否够用。

## 演进记录

| 日期 | 变更 | 依据 |
| --- | --- | --- |
| 2026-10-09 | 阶段 1.1 Beads 脚本 | beads-init-research.md |
| 2026-10-11 | 阶段 2 文档结构：梳理 Matt skills 的全部读写路径，对比 x-media-saver 与 media-glance，确定目录树与渐进发现层次 | docs-structure.md |
| 2026-10-11 | review 后补充：合并重复的路径表、`<待填>` 协议、讨论结论落点表、AGENTS.md 防膨胀约束、模块页创建时机 | docs-structure.md 持续维护机制一节 |
| 2026-10-11 | 待填标记带时机前缀，常驻约束改为交付前主动扫描并自删，取消"询问用户"兜底 | 本文关键决策 |
| 2026-10-11 | AGENTS.md 改为按节合并并移除 Matt 的 `## Agent skills` 块，triage 行随 `triage-labels.md` 存在与否 | 本文关键决策 |
