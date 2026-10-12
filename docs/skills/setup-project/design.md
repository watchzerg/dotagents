# setup-project 设计说明

维护 [`skills/setup-project`](../../../skills/setup-project/SKILL.md) 前先读本文。记录目标、阶段状态、关键决策和演进，只写代码与 git 历史看不出的意图；结构细节见 [docs-structure.md](../../../skills/setup-project/references/docs-structure.md)，Beads 依据见 [beads-init-research.md](beads-init-research.md)。

## 目标与边界

把个人新项目的初始化固化为可重复的步骤：Beads、Matt Pocock skills 前置检查、标准化文档结构、开发环境。安装在用户级，对调用时的当前工作目录生效。只服务个人项目，不做多版本兼容、不迁移已有项目的旧文档。

## 阶段状态

| 阶段 | 状态 | 实现方式 |
| --- | --- | --- |
| Beads 初始化（阶段 1 第 1 步） | 已确定 | `scripts/init_beads.py` |
| Matt setup 检查（阶段 0） | 已确定 | 检查 `docs/agents/issue-tracker.md` 与 `domain.md` 存在；`init_docs.py` 重复检查 |
| 文档结构（阶段 1 第 2 步 + 阶段 2） | 已确定，未经真实 agent 验收 | `templates/` + `scripts/init_docs.py` + SKILL.md 的合并与待填规则 |
| 工具链与门禁（阶段 1 第 3、5 步 + 阶段 3） | 已确定，uv、bun、uv+bun、swift 四种新项目已在临时项目真实跑通 gate-core（重排前由脚本运行，重排后由流程末尾运行，未重新真实验收） | `toolchain/stacks/` + `scripts/init_toolchain.py`；规范见 toolchain.md |
| 流程编排 | 2026-10-12 重排为脚本先行、agent 后置、末尾统一验证；未经真实 agent 验收 | SKILL.md 四个阶段 |

## 关键决策

- **脚本与提示混合**：确定性的事（检查前置、复制文件、不覆盖）交给标准库脚本并测试；需要读项目现状判断的事（合并已有 AGENTS.md、填 `<待填>`）交给 agent，规则写在 SKILL.md。放弃纯提示驱动，因为结构会漂移且无法测试。
- **缺失才创建，不用软链接**：文档进入目标项目后随项目持续改写，软链接会让所有项目共享一份。已有文件一律不碰，所以脚本可重复运行。
- **Matt setup 是前置而非内置**：`docs/agents/` 的三个文件由 Matt 的 setup 交互产生，本 skill 不复制也不模板化，只检查存在。原因是 tracker 选择和标签映射需要用户回答，且 Matt 的 skill 会自行更新这些文件。
- **根目录四个硬约束路径**：`GLOSSARY.md`、`docs/adr/`、`docs/agents/` 是 Matt skills 直接按路径读写的位置，`CODING_STANDARDS.md` 是 code-review 按名查找的；其余目录可按项目调整。
- **`## Agent skills` 块压缩进触发表**：Matt 的 setup 是本 skill 的前置，之后不再重跑，其三个指针并入触发表后该块被脚本移除。若有人重跑 Matt setup 追加了新块，再跑本 skill 会再次移除。
- **AGENTS.md 按节合并而非整文件跳过**：它与 Matt setup、用户共用，所以以二级标题为单位，缺的节追加、已有的节不动、标题外内容保留，重复运行无变更。其他模板文件只属于本 skill，整文件缺失才创建即可。
- **不设 `archive/`、`plans/`、ADR 索引**：参考项目里的归档层来自 Beads 之前的遗留文档；新项目用 tracker 承载增量，git 承载历史。
- **`<待填 时机：说明>` 协议**：初始化不编造项目内容，留显式标记并注明可填时机（初始化、阶段3、首个模块、按需；`阶段3` 沿用为"工具链落地后"的标记名，不随 SKILL.md 的阶段编号变动）；AGENTS.md 常驻约束要求每次交付前搜索并按时机填写，全部消失后该条自删。不另建待填清单文件：grep 即清单，独立文件会漂移。这是空项目里让文档"逐步长出来"的机制，也是因为用户在初始化时同样答不出架构类问题，所以不向用户询问。
- **AGENTS.md 只放指针**：触发表唯一，细则进正文；retro 产出的规则落 `CODING_STANDARDS.md`。已有项目的 `AGENTS.md` 里用户自写的细则节（如发布流程）也按此原则在收敛步迁入正文（2026-10-12 e2e 后定）：否则模板的防膨胀约束第一天就破例，且正文里"有发布流程时填"这类按需标记会因内容在别处而永远填不上。约束类节留下并入常驻约束；迁移整段原文不改写，触发表加行，报告逐条列出。放弃"原样保留不迁移"，因为搬运机制与收敛旧文档完全相同，不增加流程。

- **已有文档全自动收敛**：非空项目上，标准结构之外的文档由只读子 agent 分类、主 agent 执行合并或迁移，无法归类的保留原位并在 `docs/INDEX.md` 登记，使重跑幂等。不做执行前确认：本 skill 不 commit，工作区就是审阅点；删除可由 git 恢复。放弃"把删除改为移入 `docs/changes/`"，因为会污染增量目录。

- **从代码补写文档单独成步并派子 agent**：范围限于 `首个模块` 类标记、按模板的模块页，以及已有工具链时的 `阶段3` 类标记；只写代码可证实的内容，冲突记为已知差异，术语只报告不写。子 agent 直接写文件，因为模块页经主 agent 转写没有意义；主 agent 复核一致性与链接。

- **工具链按文件证据判定，已有工具链不改动**：lockfile、工程文件或 justfile 存在即视为已有，只补依赖偏好进文档；判定不出时退出码 3 交用户多选。新项目才创建工具链文件并运行安装。仅有的例外是 `scripts/check_docs.py` 与 `scripts/with_lock.py` 在 existing 模式也补缺（前者 2026-10-12 e2e 后加，后者同日 media-glance 真实运行后加）：两者只用标准库、与 stack 无关；不补 check_docs 的话 `docs-check` 只能是空壳，不补 with_lock 的话已有项目的 full 测试入口永远拿不到主机锁，报告只能把"无主机锁"列为差异问用户。配套允许对已有 recipe 做两种最小改动：`gate-core` 追加 `check-toolchain docs-check` 依赖，full 测试入口包进锁；正文不改。随之约束被 existing 模式复制的"依赖政策"节只写对任何项目都成立的偏好，模板配置事实放"运行时与工具链"节。
- **项目名与空开头的 AGENTS.md 由脚本兜底**：项目名取 `--name`、`AGENTS.md` 一级标题、目录名，两个脚本同一规则，agent 不必记得传参；`AGENTS.md` 二级标题前没有内容（Matt setup 在空项目上的常态）时脚本补模板开头，保证总有标题与 `初始化` 标记；只有空白的文件（如 `uv init` 的空 README）视为缺失。都是 e2e 首轮暴露的、能用脚本确定性解决的问题。
- **工具链按 stack 模块化，不按组合枚举**：项目是 stack 的集合（uv、bun、swift），每个 stack 在 `toolchain/stacks/<name>/` 自包含（manifest、私有 recipe、文件、文档片段），脚本负责拼合：根 justfile 的公开契约 recipe 聚合各 stack 的私有 `<stack>-*` recipe，多 stack 时 `fmt`/`test` 以 stack 名作 scope；文档由公共正文加占位符与各 stack 片段拼成，多 stack 时片段加三级标题。放弃按 uv-bun 这类组合各写一份，因为偏好改一处要同步多处，且加 swift 后组合数爆炸。新增 stack 只需加一个目录并登记名字。
- **门禁契约固定，实现可换**：所有项目共用同一组公开 recipe 名；没有预置 stack 的项目 recipe 非零退出而非留空，沿用 Beadwork 的"验证未实现必须失败"。core/full 的定义写进目标项目文档正文，不只放 justfile 注释。
- **swift 新项目只落 SwiftPM package，不生成 Xcode 工程**：`.xcodeproj` 无法可靠模板化；core 测试用 Swift Testing 的 `CoreTests` target，应用壳由用户在 Xcode 创建后把 package 作本地依赖，再把 `swift-*` recipe 切到 `xcodebuild`。`swift test` 零匹配退出 0，所以 recipe 自己检查零匹配；`tests/full/` 需要同步在 Package.swift 声明 target，否则 SwiftPM 对空目录 target 每次构建都告警。
- **full 目录出现即收录**：`tests/full/` 不存在时 gate-full 打印提示而非失败，存在而无测试则失败。避免新项目的 gate-full 因零收集长期红灯，同时不给 skip 留口子。
- **模板目录从本仓库的 pytest 与 Ruff 中排除**：`toolchain/` 下的 `pyproject.toml` 与测试文件是复制到目标项目的模板，不是本仓库的配置与测试。
- **implement-spec 门禁靠触发词、审查项与主机锁，不加常驻约束**：目标是并行 worktree 的 ticket 只跑 `gate-core`，最终集成跑 `gate-full`，新测试持续遵守分层。规则正文在 testing.md，由触发表“执行 `implement-spec`”命中；分层归属的把关写进 CODING_STANDARDS，让 implement-spec 末尾的 code-review 检查。不复制 x-media-saver 的 6 条长版（通用流程常识）与收录表（和分层表重复）。x-media-saver 的做法是 full 测试在 ticket 阶段只写不跑，代价是 red → green 对 full 缺失、问题堆到最后才发现、implementer 有动机绕过规则；本 skill 改为给 `test-full` 与 `gate-full` 加主机级 `flock`，implementer 可定向跑自己的 full 测试并自动排队。选主机级而非仓库级，因为桌面与端口是主机资源，且各 worktree 的编译产物都在自己目录内。
- **技术偏好只进 stack 片段，项目特有内容不进模板**：x-media-saver 与 media-glance 的 structlog 接线、Chrome 扩展、libmpv、Docker、CI 不搬；搬的是工具链路线、依赖政策与新增依赖偏好清单。
- **脚本先行，agent 后置，问题一次问完**：三个脚本（Beads、文档结构、工具链）连续运行，之后才做收敛旧文档、补写模块页等 agent 工作，最后统一跑文档检查与 `gate-core`。原先 agent 步骤夹在 `init_docs.py` 与 `init_toolchain.py` 之间，有三个问题：空项目是主用例，判定必然退出码 3，加上项目描述就要在两个时点打断用户两次；补写文档的子 agent 在 existing 模式会先填 `阶段3` 标记，脚本随后找不到标记而跳过依赖偏好；子 agent 看到的工具链正文还是标记。为此 `init_toolchain.py` 加 `--detect-only`，在落地前把 stack 问题和项目描述合成一次提问；脚本内的 `gate-core` 运行移除，门禁只有流程末尾一个入口，覆盖 agent 对文档的改动。
- **收敛旧文档的执行也交子 agent**：原先只读子 agent 分类、主 agent 执行合并，但合并才是重活，要通读旧文档并以标准正文为骨架改写；与第 4 步"模块页经主 agent 转写没有意义"的理由相同，改为分类表返回后由可写子 agent 执行合并、迁移、移动、删除，主 agent 只做链接修正、索引登记、建票据与复核。分批时每批一个执行子 agent 并行，同一目标文件串行。
- **existing 模式也做机械文档检查**：已有工具链项目不复制 `check_docs.py`，但收敛与补写恰是这类项目的主要产出，原先链接正确性只靠主 agent 复核。`check_docs.py` 加可选的根目录参数，流程末尾直接调用 skill 自带副本检查目标项目。不运行这类项目自身的门禁：本次没改代码，其红绿与初始化无关，补过 recipe 时只验证 justfile 可解析。
- **缺少 recipe 的实现建议并入补写文档的子 agent**：它本来就要读 `pyproject.toml`、`package.json`、`justfile` 等配置，顺带返回建议，主 agent 落到 justfile，省一次独立分派。
- **2026-10-12 全面探查后的修正**（四个只读子 agent 分别审脚本、模板、工具链、指令文本，主 agent 核实后保留 25 条）。有取舍的几条：
  - full 测试按各 stack 自己的测试文件判定，不按目录存在：uv+swift 共用 `tests/full/` 时，按目录判定会让任一方加 full 测试就令另一方失败。`Package.swift` 的 `exclude` 改为按实际存在的非 Swift 文件动态计算，因为静态列表在文件不存在时 SwiftPM 会告警 Invalid Exclude；配套 `--manifest-cache none` 让新文件即时生效。
  - 去掉 `bun test --fail-on-empty`：bun 没有这个 flag 且静默忽略未知 flag，零匹配非零是 bun 的默认行为；禁用 `--pass-with-no-tests`。
  - 定向语义统一为"名字筛选在默认目录内筛，路径参数替换默认目录"：uv 用 `-o testpaths`，bun 因位置参数是并集，参数中有已存在路径时不再追加默认目录。
  - Biome 排除 `.beads/` 并启用 `vcs.useIgnoreFile`：`bd init` 写出的 `metadata.json` 无末尾换行，bun 单 stack 时 `just lint` 初始化完即红。`vcs.root` 用 `{{ROOT}}`，否则 `frontend/` 布局找不到 `.gitignore`。
  - `with_lock.py` 改为父进程持锁、子进程运行命令：原先锁 fd 可继承且 `execvp`，测试留下的后台进程会一直占住主机锁。终端前台时不重复转发 SIGINT，避免 pytest 类 runner 收到两次 Ctrl-C 硬中止。
  - `check_docs.py` 标题锚点从原始行计算、只去反引号：原先先删行内代码再算 slug，含代码的标题全部误报。
  - 安装失败固定返回 1 并提示 `just install`：new 模式先落地再安装，失败后重跑会被判为 existing 而静默跳过安装；安装失败是唯一不中止流程的脚本失败。
  - 一句话描述的提问条件改为三个文件任一含 `初始化` 标记：`AGENTS.md` 已存在时合并会丢弃模板开头，标记只剩 README 与 GLOSSARY，原条件在主用例下永不触发。
  - 收敛执行改为全部分类后再执行、tracker 类源文件建票后才删、按批预分配 ADR 编号段、目标文件重叠的批串行。
  - `阶段3` 标记在 none 模式由 none overlay 改写为 `按需`，不再残留"时机已到"的标记诱导编造。
  - `<待填` 清单改用带时机前缀的精确 pattern，规则正文里的 `<待填` 字样不再自命中，"全部消失后自删"才可能触发。
- **运行时 Python 下限为 3.14**：skill 脚本与复制到目标项目的 `check_docs.py`、`with_lock.py` 都按 3.14+ 标准库编写，可直接使用最新语法，不再为 macOS 自带的 3.9 加 `from __future__` 之类的兼容；宿主 `python3` 由 uv `--default` 提供。代价是缺少 3.14 的机器会在解析阶段报语法错误，而非给出友好提示。

- **2026-10-12 media-glance 真实 existing 运行（session 2495c23b）后的修正**。该项目自带七篇模块页、双语词汇表、`docs/plans/` 与一套 justfile，是首个非 fixture 的 existing 用例。运行本身通畅，摩擦来自一个模板缺陷和六个本可预先决定却推给用户裁决的问题，其中"7 个现有模块页仍是旧栏目"用户没看懂。据此：
  - `docs/agents/testing.md` 改为与 `AGENTS.md` 一样按节合并：模板 `CODING_STANDARDS.md` 链接它的 `#分层`，项目自带 testing.md 时整文件跳过会让 docs-check 第一条就红，任何有自己 testing.md 的旧项目都复现。同义节（如 `## 测试编写与变更`）由阶段 2 第 1 步按 AGENTS.md 同一规则并入。
  - 已有模块页章节与模板不一致时按模板重排，原有小标题降为三级保留锚点，每页一个子 agent 并行；用户选择迁移，且这正是第二轮实际做的事。
  - `docs/research/` 直接子级的验收与交付记录纳入候选，移入 `acceptance/<主题>-<日期>.md`：原候选规则把 `research/` 整体排除，8 份 `*-integration.md` 没被分类，分类子 agent 已点出结构不一致。
  - 术语合并只迁入项目特有条目，通用界面与编程词条列入报告删除清单：模板早有"只收项目特有概念"，但执行子 agent 把 86 条全部迁入，用户选择删减 47 条。
  - `AGENTS.md` 已有描述时不再提问，直接展开 README 与 GLOSSARY 的标记；existing 模式在多数项目上因此零提问。
  - 报告列出阶段 2 各步的执行或跳过及依据，裁决项写清文件、备选与推荐；references 在所在步骤读取而不预读。
  - 全局规则改为明确用 Agent 工具的 `model`、`effort` 参数：该次运行把 effort 写进了 prompt 文本。
- **2026-10-13 x-media-saver 真实 existing 运行（session 8b7d9721）后的修正**。该项目是首个超过 30 个候选的真实用例：根目录 `ARCHITECTURE.md`、10 篇模块页、26 篇 `docs/archive/`、受 Git 管理的 `output/` 验收附件，约 45 个候选分两批、6 个子 agent，主流程 16 分钟，`docs-check` 一次通过。运行顺畅，摩擦来自 agent 在三处绕开了规则，而规则没写理由：
  - 执行前用 AskUserQuestion 问"成熟文档体系要不要全量收敛"并推荐轻量合并，与"全自动执行、工作区即审阅点"相反。converge-docs.md 补一句"候选数量与文档完善程度不改变做法"并带理由。
  - 第二个分类子 agent 未返回就派出第一个执行子 agent，分类子 agent 随后遇到文件已被移走、回报的行号失效。分批规则补上理由：执行会移动文件，未完成的分类里的引用位置随即失效。
  - 分类与执行子 agent 用裸 `grep -r` 查引用，被忽略目录 `.worktrees/`（完整仓库副本）与 `output/` 的 jsonl、日志灌满，四条结果各 33 万到 55 万字节。引用查找改为 `git grep -nF`，与候选清单的 `git ls-files` 对齐。
  - 报告列了 5 个裁决项，3 个 agent 自己已有推荐（可选 ADR 不建、增量规则改动只需说明、scratchpad 副本不必留）。报告规则改为有推荐的直接执行并列为已决，只有无法推荐的才裁决；被删源文件用 `git show HEAD:<path>` 对照。media-glance 已出现同一模式。
  - 顺手写明两处 agent 自行判断的做法：第 4 步在标记填完、模块页齐全且无缺 recipe 时跳过；full 入口包锁后用 `--collect-only` 之类确认测试集不变。
  - 用户事后删掉了迁入 `docs/research/acceptance/assets/` 的全部截图、日志与 jsonl（约 1.9MB），只留链接文字并注明删除日期。是否把"验收记录的二进制附件不迁入、删除并注明"写成通用规则，只有一个样本，留待下一个项目再定。
- **真实 agent 验收用 headless harness，而不是再写一个测试 skill**：`tests/setup_project/e2e/` 在临时 Git 项目上造 fixture、起 `claude -p "/setup-project"`、做确定性检查并派 reviewer 会话，入口 `just e2e-setup-project`，做法见 [e2e.md](e2e.md)。`setup-matt-pocock-skills` 标了 `disable-model-invocation`，agent 无法调用，所以其产物用 fixture 模拟；阶段 1 第 4 步的提问在非交互下由预置答案代替，agent 在报告里列出"本应提问"供 reviewer 核对。它属于仓库维护层，不进门禁、不被 pytest 收集，因为需要模型额度且结果有判断成分。

## 明确不做

- 不生成模块页、ADR、调研文件的实例；这些由 Matt 的 skills 或日常迭代惰性创建。
- 不为项目创建 `CLAUDE.md`：Claude Code 直接读取 `AGENTS.md`。`CLAUDE.md` 已存在时 SKILL.md 要求 agent 把其中内容按节并入 `AGENTS.md`，只留一行 `@AGENTS.md`，不丢弃用户内容。

## 待验收

验收方式见 [e2e.md](e2e.md)。2026-10-12 用 opus 跑通 `empty` 与 `uv-existing` 两个用例，硬检查全部通过，reviewer 七问无"有问题"级别的偏离；结论与发现：

- 已验收：提问只发生一次且内容正确；同义节 `## 约束` 与 `CLAUDE.md` 的 `## 代码风格` 并入 `## 常驻约束` 且措辞未改，自定义节 `## 发布流程` 原样保留，`CLAUDE.md` 收口为 `@AGENTS.md`；旧文档 `old-notes.md` 拆成 ADR 与两张 `needs-triage` 票据、`setup.md` 并入 workflow 后删除；模块页与架构总览只写代码可证实的内容，AGENTS 要求的 JSON 持久化未实现被记为已知差异；缺少的 recipe 补齐且 `just --summary` 可解析；new 模式末尾 `gate-core` 真实通过。
- 首轮发现并已修（2026-10-12，待第二轮 e2e 复验）：AGENTS.md 空开头补模板头、空文件视为缺失、项目名取 AGENTS.md 标题（脚本）；existing 模式补缺 `check_docs.py` 并由 `docs-check` 调用（脚本与 toolchain.md）；`check-toolchain` 不得触发同步、参考 `recipes.just`（toolchain.md 与 SKILL.md）；看似冲突的旧文档内容只合并不丢弃、删除须引用依据（converge-docs.md）；uv 与 bun 的依赖偏好片段去掉模板配置事实（overlay）；描述只填有标记处、AGENTS.md 已有描述保留、展开不写初始化流程、退出码 3 时直接带 `--stacks`（SKILL.md）；配置里看出的缺口进报告不进正文（document-code.md）；子 agent 简报去掉无法执行的"中等思考强度"。第二轮 `empty` 复验通过后再补三处：`init_docs.py` 末尾打印仍含 `初始化` 标记的文件（阶段 1 第 4 步的提问条件直接读它，不再让 agent grep）、"空项目"的脚手架列全、"不写初始化流程本身"改为不描述 setup-project 自己的步骤。
- 同日定案并已改：`AGENTS.md` 的用户自写节纳入收敛候选（第二轮 e2e 发现 agent 只照 `git ls-files` 命令执行而漏掉这些节，于是补了列二级标题的第二条命令、明确迁出后删除原节、`CLAUDE.md` 并入的节同样分流、约束类再按"影响流程还是只影响代码写法"分到常驻约束或 `CODING_STANDARDS.md`、疑点只进报告、ADR 后果只写有依据的；`testing.md` 模板的"带主机锁"改为以 workflow 为准，因为 existing 模式没有 `with_lock.py`）。第三轮复验 B 通过：`## 发布流程` 迁入 `docs/operations/`、原节删除、触发表加行、workflow 发布标记填上；随后再按 review 补三点：能机械判定的代码规则留常驻约束并建议 lint 票据而不是进 `CODING_STANDARDS.md`（与该模板"只写判断类标准"一致）、existing 模式的依赖偏好要与常驻约束对照删冲突项、GLOSSARY 标记去掉"为什么存在"以免逼出编造。第四轮两个用例硬检查全过（`empty` 33/33，`uv-existing` 37/37），review 只剩 ADR 措辞推断之类的轻微项；据此再补 ADR 背景只用原话、源文件每句落地后才删、按需目录登记 INDEX 三条措辞，未再跑第五轮，约束类留下并入常驻约束，细则类整段迁入对应正文、触发表加行、"按需"标记用链接填（converge-docs.md 与 SKILL.md）；待第二轮 e2e 复验。
- 第五轮跑剩余四个用例并加 `--rerun`：`bun-new-with-code` 31/31、`swift-existing` 24/24、`uv-bun-new` 29/29 全过且幂等复跑无变更；`none-empty` 唯一 FAIL 来自 harness 自己的 fixture（无 triage 时 tracker 文件仍引用 `triage-labels.md`），已修。随 review 补：none 没有安装步骤时脚本与报告写"无安装命令"、证据标准禁止常识性环境说明与把脚手架布局当代码事实、INDEX 模板的"标签"措辞按 triage 是否存在。未采纳的建议（模块页门槛、existing 无 justfile 时 testing.md 的 just 段落处理、阶段 0 校验 Matt 产物链接）留待真实项目出现再定。
- 未验收：分批并行收敛时同一目标文件的串行处理（fixture 只有两篇旧文档，未触发分批）；uv+swift、bun+swift 组合仍未真实跑通。
- 已在 media-glance 上真实跑过 existing 模式（2026-10-12，session 2495c23b，opus，主流程约 15 分钟、7 个子 agent 约 72 万 token）：依赖偏好与常驻约束无冲突、缺少 recipe 的实现建议准确、`check_docs.py` 准确并暴露了 testing.md `#分层` 锚点缺陷；68 个文件的收敛结果经用户两轮裁决后提交。由此固化的七条规则见关键决策，尚未复跑 e2e 验证：testing.md 按节合并、existing 模式复制 `with_lock.py`、已有 gate 的最小改动、已有模块页重排、research 验收记录候选、术语删减、有描述不提问。x-media-saver 已于 2026-10-13 真实跑过（session 8b7d9721，见关键决策）：七条规则中 testing.md 按节合并、`with_lock.py` 补缺、已有 gate 的最小接线、有描述不提问四条在该次运行中生效且无摩擦；由该次运行新加的四条措辞（执行前确认、分批理由、`git grep`、裁决项只列无法推荐的）尚未复验，e2e 也没有超过 30 个候选、带附件与被忽略仓库副本的 fixture，无法自动复验。
- uv+swift、bun+swift 的组合只经过脚本测试和子 agent 对渲染结果的 `just`、`swift build`、`bun test` 单项验证，没有真实跑通完整 `gate-core`/`gate-full`；两者都在根目录时 `tests/core/` 会混放两种语言的测试文件。
- 重写后的 `with_lock.py` 与动态 exclude 的 `Package.swift` 未在真实 full 测试场景下验收。

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
| 2026-10-12 | 流程重排为脚本先行、agent 后置、末尾统一验证：`init_toolchain.py` 加 `--detect-only`、移除脚本内 `gate-core`；收敛执行交可写子 agent；`check_docs.py` 加根目录参数供 existing 模式调用；缺少 recipe 的建议并入补写子 agent；SKILL.md 删去复述脚本内部行为的段落 | 本文关键决策 |
| 2026-10-12 | 全面探查修正 25 条：脚本（锚点、锁、安装失败、复制忽略、recipe 识别）、工具链（Biome/.beads、per-stack full 判定、bun flag、定向语义、swift lock 安装、check-toolchain 不下载、none overlay）、指令（提问条件、同义节、CLAUDE.md、已有代码定义、收敛顺序与并行、候选排除）、模板与仓库文档漂移 | 本文关键决策 |
| 2026-10-12 | 按首轮 e2e 发现修 skill：脚本兜底项目名、空开头与空文件，existing 模式补 `check_docs.py`，契约与收敛规则补严，偏好片段去配置事实 | 本文关键决策与待验收 |
| 2026-10-12 | 新增端到端验收 harness `tests/setup_project/e2e/`（`just e2e-setup-project`），首轮跑通 `empty` 与 `uv-existing`，发现 AGENTS.md 空开头、空 README、existing 模式 docs-check 三个缺口 | e2e.md、本文待验收 |
| 2026-10-12 | 维护材料移出 skill 目录：测试移到 `tests/setup_project/`，本文与 beads-init-research.md 移到 `docs/skills/setup-project/`，skill 目录只保留运行时内容 | 根 AGENTS.md 三层结构 |
| 2026-10-12 | media-glance 真实 existing 运行复盘：`init_docs.py` 按节合并 testing.md，existing 模式复制 `with_lock.py` 并允许已有 gate 的最小接线，收敛候选加入已有模块页与 research 验收记录，术语只迁项目特有条目，有描述不提问，报告列跳过步骤 | 本文关键决策 |
| 2026-10-13 | x-media-saver 真实 existing 运行复盘：收敛不做执行前确认、分批先全部分类并写明理由、引用查找改 `git grep`、报告只把无法推荐的事项列为裁决、第 4 步跳过条件与包锁后的收集验证 | 本文关键决策 |
