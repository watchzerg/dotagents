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
| 3 工具链与门禁 | 已确定，uv、bun、uv+bun、swift 四种新项目已在临时项目真实跑通 gate-core | `toolchain/stacks/` + `scripts/init_toolchain.py`；规范见 toolchain.md |

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

- **已有文档全自动收敛**：非空项目上，标准结构之外的文档由只读子 agent 分类、主 agent 执行合并或迁移，无法归类的保留原位并在 `docs/INDEX.md` 登记，使重跑幂等。不做执行前确认：本 skill 不 commit，工作区就是审阅点；删除可由 git 恢复。放弃"把删除改为移入 `docs/changes/`"，因为会污染增量目录。

- **从代码补写文档单独成步并派子 agent**：范围限于 `首个模块` 类标记、按模板的模块页，以及已有工具链时的 `阶段3` 类标记；只写代码可证实的内容，冲突记为已知差异，术语只报告不写。子 agent 直接写文件，因为模块页经主 agent 转写没有意义；主 agent 复核一致性与链接。

- **工具链按文件证据判定，已有工具链不改动**：lockfile、工程文件或 justfile 存在即视为已有，只补依赖偏好进文档；判定不出时退出码 3 交用户多选。新项目才创建工具链文件并运行安装。
- **工具链按 stack 模块化，不按组合枚举**：项目是 stack 的集合（uv、bun、swift），每个 stack 在 `toolchain/stacks/<name>/` 自包含（manifest、私有 recipe、文件、文档片段），脚本负责拼合：根 justfile 的公开契约 recipe 聚合各 stack 的私有 `<stack>-*` recipe，多 stack 时 `fmt`/`test` 以 stack 名作 scope；文档由公共正文加占位符与各 stack 片段拼成，多 stack 时片段加三级标题。放弃按 uv-bun 这类组合各写一份，因为偏好改一处要同步多处，且加 swift 后组合数爆炸。新增 stack 只需加一个目录并登记名字。
- **门禁契约固定，实现可换**：所有项目共用同一组公开 recipe 名；没有预置 stack 的项目 recipe 非零退出而非留空，沿用 Beadwork 的"验证未实现必须失败"。core/full 的定义写进目标项目文档正文，不只放 justfile 注释。
- **swift 新项目只落 SwiftPM package，不生成 Xcode 工程**：`.xcodeproj` 无法可靠模板化；core 测试用 Swift Testing 的 `CoreTests` target，应用壳由用户在 Xcode 创建后把 package 作本地依赖，再把 `swift-*` recipe 切到 `xcodebuild`。`swift test` 零匹配退出 0，所以 recipe 自己检查零匹配；`tests/full/` 需要同步在 Package.swift 声明 target，否则 SwiftPM 对空目录 target 每次构建都告警。
- **full 目录出现即收录**：`tests/full/` 不存在时 gate-full 打印提示而非失败，存在而无测试则失败。避免新项目的 gate-full 因零收集长期红灯，同时不给 skip 留口子。
- **模板目录从本仓库的 pytest 与 Ruff 中排除**：`toolchain/` 下的 `pyproject.toml` 与测试文件是复制到目标项目的模板，不是本仓库的配置与测试。
- **implement-spec 门禁靠触发词、审查项与主机锁，不加常驻约束**：目标是并行 worktree 的 ticket 只跑 `gate-core`，最终集成跑 `gate-full`，新测试持续遵守分层。规则正文在 testing.md，由触发表“执行 `implement-spec`”命中；分层归属的把关写进 CODING_STANDARDS，让 implement-spec 末尾的 code-review 检查。不复制 x-media-saver 的 6 条长版（通用流程常识）与收录表（和分层表重复）。x-media-saver 的做法是 full 测试在 ticket 阶段只写不跑，代价是 red → green 对 full 缺失、问题堆到最后才发现、implementer 有动机绕过规则；本 skill 改为给 `test-full` 与 `gate-full` 加主机级 `flock`，implementer 可定向跑自己的 full 测试并自动排队。选主机级而非仓库级，因为桌面与端口是主机资源，且各 worktree 的编译产物都在自己目录内。
- **技术偏好只进 stack 片段，项目特有内容不进模板**：x-media-saver 与 media-glance 的 structlog 接线、Chrome 扩展、libmpv、Docker、CI 不搬；搬的是工具链路线、依赖政策与新增依赖偏好清单。
- **运行时 Python 下限为 3.14**：skill 脚本与复制到目标项目的 `check_docs.py`、`with_lock.py` 都按 3.14+ 标准库编写，可直接使用最新语法，不再为 macOS 自带的 3.9 加 `from __future__` 之类的兼容；宿主 `python3` 由 uv `--default` 提供。代价是缺少 3.14 的机器会在解析阶段报语法错误，而非给出友好提示。

## 明确不做

- 不生成模块页、ADR、调研文件的实例；这些由 Matt 的 skills 或日常迭代惰性创建。
- 不处理 `CLAUDE.md` 与 `AGENTS.md` 并存的合并，SKILL.md 只要求 agent 把块移到 AGENTS.md 并让 CLAUDE.md 指向它。

## 待验收

- 在一个真实新项目上让 agent 完整执行阶段 2 的第 2 到 4 步，检查合并是否保留用户内容、待填是否被编造。
- 在已有工具链的真实项目（如 media-glance、x-media-saver）上跑阶段 3，检查依赖偏好的补写与缺少 recipe 的提示是否准确；两者的临时克隆已验证判定与零改动，但它们没有阶段 2 标记，补写路径只在测试中覆盖。
- uv+swift、bun+swift 的组合只经过脚本测试，没有真实跑通；两者都在根目录时 `tests/core/` 会混放两种语言的测试文件。

## 演进记录

| 日期 | 变更 | 依据 |
| --- | --- | --- |
| 2026-10-09 | 阶段 1.1 Beads 脚本 | beads-init-research.md |
| 2026-10-11 | 阶段 2 文档结构：梳理 Matt skills 的全部读写路径，对比 x-media-saver 与 media-glance，确定目录树与渐进发现层次 | docs-structure.md |
| 2026-10-11 | review 后补充：合并重复的路径表、`<待填>` 协议、讨论结论落点表、AGENTS.md 防膨胀约束、模块页创建时机 | docs-structure.md 持续维护机制一节 |
| 2026-10-11 | 阶段 3：类型判定、四套工具链模板、justfile 契约、docs-check、文档正文替换；uv、bun、uv-bun 三种新项目真实跑通 gate-core | toolchain.md |
| 2026-10-12 | 对照 x-media-saver 的 implement-spec 门禁提交：触发表加“执行 `implement-spec`”、CODING_STANDARDS 加测试分层审查项；否决其余 4 条通用行为约束进模板。新增 `test-full` 契约与 `scripts/with_lock.py` 主机锁，full 测试可在 ticket 阶段定向运行 | toolchain.md 主机锁 |
| 2026-10-11 | 阶段 3 改为 stack 模块化：`--kind` 改 `--stacks` 多选，uv/bun 拆成独立模块并由脚本拼合 justfile 与文档，新增 swift stack（SwiftPM + swift-format + Swift Testing）；补回 x-media-saver 的通用偏好 | toolchain.md |
| 2026-10-11 | 新增第 4 步从代码补写文档：范围、证据标准、子 agent 分派与复核 | document-code.md |
| 2026-10-11 | 新增第 3 步收敛已有文档：候选范围、分类表、子 agent 简报与执行顺序 | converge-docs.md |
| 2026-10-11 | 待填标记带时机前缀，常驻约束改为交付前主动扫描并自删，取消"询问用户"兜底 | 本文关键决策 |
| 2026-10-11 | AGENTS.md 改为按节合并并移除 Matt 的 `## Agent skills` 块，triage 行随 `triage-labels.md` 存在与否 | 本文关键决策 |
| 2026-10-12 | 运行时 Python 下限从 3.10 提到 3.14，移除 `from __future__ import annotations` | 本文关键决策 |
