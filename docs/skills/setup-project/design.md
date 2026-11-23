# setup-project 设计说明

维护 [`skills/setup-project`](../../../skills/setup-project/SKILL.md) 前先读本文。本文只记代码与 git 历史看不出的意图：现行决策及其理由、明确不做的事、待验收项。运行时规则以 SKILL.md 与 `references/` 为准，本文不复述；变更流水见 `git log`。Beads 参数依据见 [beads-init-research.md](beads-init-research.md)，真实 agent 验收做法见 [e2e.md](e2e.md)。

## 目标与边界

把个人新项目的初始化固化为可重复的步骤：Beads、Matt Pocock skills 前置检查、标准化文档结构、开发工具链与门禁。安装在用户级，对调用时的当前工作目录生效。只服务个人项目，不做多版本兼容；已有项目的旧文档收敛进标准结构，而不是迁移其历史。

## 关键决策

### 流程编排

- **脚本与提示混合**：确定性的事（检查前置、复制文件、不覆盖、拼合工具链）交给标准库脚本并测试；需要读项目现状判断的事（同义节合并、填 `<待填>`、收敛旧文档、补写模块页）交给 agent。纯提示驱动会让结构漂移且无法测试。
- **脚本先行、agent 后置、问题一次问完**：三个脚本连续运行，之后才做 agent 工作，最后统一跑文档检查与 `gate-core`。原先 agent 步骤夹在两个脚本之间：空项目（主用例）的判定必然退出码 3，加上项目描述就要打断用户两次；补写子 agent 会先填掉 `阶段3` 标记，脚本随后找不到标记而跳过依赖偏好。为此 `init_toolchain.py` 有 `--detect-only`，`init_docs.py` 末尾打印仍含 `初始化` 标记的文件，提问条件直接读它；脚本不跑门禁，门禁放在流程末尾才能覆盖 agent 对文档的改动。
- **全自动、不 commit**：收敛等 agent 工作不做执行前确认，工作区就是唯一审阅点，删除可由 git 恢复。x-media-saver 真实运行时 agent 曾在执行前问“成熟文档体系要不要全量收敛”并推荐轻量合并，所以 converge-docs.md 写明候选多少、文档多完善都不改变做法。
- **报告只把无法推荐的事项列为裁决**：media-glance 与 x-media-saver 两次运行都把 agent 自己已有推荐的事项交给用户裁决。现在有推荐的直接执行并列为已决。例外是项目已有约定（如 ADR）与标准结构冲突：一律列为裁决项、两边不动、默认推荐标准结构。来源是 kototoki 重跑时 agent 按项目 ADR 删掉了模板建的 `docs/research/INDEX.md` 并列为已决，而用户的意见是以标准结构为准。
- **旧版初始化项目重跑只给提示，不加流程**：这类重跑很少，不为它扩写 SKILL.md。`check_docs.py` 缺失才复制，旧版没有 `--affected` 时，`init_toolchain.py` 在缺少 `docs-affected` 的提示后直接写出做法；kototoki 重跑时 agent 曾自行设计 `--affected` 而没参照模板实现。

### Beads

- **`bd init` 参数**：`--non-interactive --init-if-missing --role maintainer --skip-agents --skip-hooks`。不装 Beads 的 agent 集成（`AGENTS.md` 由本 skill 管）与 hooks（不用 JSONL 工作流）。首次 `bd init` 无 pathspec 的自动 commit 没有开关，作为已确认行为接受。
- **已有 `.beads` 时执行 `bd bootstrap --yes`**：数据库是 embedded Dolt、不进 git，新 clone 只有 `.beads/` 配置，`bd` 一律报 `no beads database found`。原先见到 `.beads` 就跳过，问题拖到某个 skill 建票时才暴露（grok-media-saver 的 `/prune-tests` 留痕票因此没建成），而 bd 自带提示只指向 `bd init`，会在本地另起一个与远端分叉的空库。`bootstrap` 按 `sync.remote` 等来源恢复，数据库已在时只校验，符合只补缺。顺带把 `.beads` 设为 0700，消掉 bd 每次调用都打印的权限提示。模板 AGENTS.md 的票据行写有恢复命令，随项目进 git。

### 文档结构

- **Matt setup 是前置而非内置**：`docs/agents/` 的三个文件由 Matt 的 setup 交互产生（tracker 选择与标签映射需要用户回答，Matt 的 skill 也会自行更新它们），本 skill 只检查存在。其 `## Agent skills` 块的三个指针已并入触发表，块由脚本移除。
- **硬约束路径**（见 docs-structure.md）由其他 skill 按路径读写，其余目录可按项目调整。media-glance 把术语表放 `docs/glossary.md`、靠改写 `domain.md` 兜底，只对读过 `domain.md` 的 skill 生效，不采用。
- **缺失才创建，不用软链接**：文档进入目标项目后随项目持续改写，软链接会让所有项目共享一份。只有空白的文件（如 `uv init` 的空 README）视为缺失。
- **`AGENTS.md` 与 `docs/agents/testing.md` 按节合并**：`AGENTS.md` 与 Matt setup、用户共用，所以以二级标题为单位，缺的节追加、已有的节不动，重复运行无变更。`testing.md` 也合并，因为模板 `CODING_STANDARDS.md` 链接它的 `#分层`，项目自带 testing.md 时整文件跳过会让 docs-check 一开始就红（media-glance 实测）。同义节由 agent 并入模板标题，否则下次脚本会再追加模板节。
- **项目名与空开头由脚本兜底**：项目名取 `--name`、`AGENTS.md` 一级标题、目录名，两个脚本同一规则，agent 不必记得传参；`AGENTS.md` 二级标题前没有内容（Matt setup 在空项目上的常态）时补模板开头，保证总有标题与 `初始化` 标记。
- **`<待填 时机：说明>` 协议**：初始化不编造项目内容，留显式标记并注明可填时机（`初始化`、`阶段3`、`首个模块`、`按需`；`阶段3` 是“工具链落地后”的标记名，不随 SKILL.md 阶段编号变动）。用户在初始化时同样答不出架构类问题，所以只问一句话描述。不另建待填清单文件：grep 即清单，独立文件会漂移；grep 用带时机前缀的精确 pattern，规则正文里的 `<待填` 字样不自命中，“全部消失后自删”才可能触发。none stack 的 `阶段3` 标记由 none overlay 改写为 `按需`，不残留诱导编造的标记。
- **`AGENTS.md` 只放指针**：触发表唯一，细则进正文，retro 产出的规则落 `CODING_STANDARDS.md`。已有项目里用户自写的细则节（如发布流程）也在收敛步迁入正文：否则防膨胀约束第一天就破例，正文里“有发布流程时填”这类标记也因内容在别处而永远填不上。约束类节并入常驻约束；能机械判定的代码规则也留在常驻约束并建议 lint 票据，因为 `CODING_STANDARDS.md` 只写工具查不出的判断类标准。
- **目录取舍**（对比 x-media-saver、media-glance 两个项目的实践）：

  | 分歧 | 选择 | 理由 |
  | --- | --- | --- |
  | 架构正文位置 | 全部在 `docs/architecture/`，根目录不放 `ARCHITECTURE.md` | x-media-saver 分散在三处；根目录只留生态按名查找的文件 |
  | 产品规格与模块页 | 默认只有模块页，行为规格是其一章；`behaviors/` 按需 | 两棵“当前真相”树的交叉链接是单人项目的负担 |
  | 用户可见行为目录名 | `behaviors/`，不用 `specs/` | Matt 的 implement-spec 与 code-review 把 spec 当增量规格；behaviors 与模块页“当前行为规格”同词 |
  | 增量与归档 | tracker 为主，`changes/` 兜底、吸收后删除；不设 `archive/`、`plans/` | git 保留历史；归档层是 Beads 之前遗留文档的产物 |
  | 研究与验收 | `research/` 常驻不归档，验收记录在 `research/acceptance/` | 证据自带时点，归档没有意义 |
  | development 与 operations | 以“改代码还是跑产物”划分；无可部署产物时不建 `operations/` | Docker 的 build 归 development、run 归 operations |

- **三个项目重构后的回收**：x-media-saver、media-glance、bangou 由本模板初始化后各自重构了文档架构，诊断一致：问题在粒度与路由，不在规则本身；重构后文档总量都没减少，降的是每个任务必须读入的量。只回收至少两个项目独立做出、且对单项目新仓库成立的部分：
  - `check_docs.py` 从查链接升级为查结构：全量可达、`adr/` 与 `research/` 逐文件登记索引、体量预算、标题骨架。预算取 bangou 的数值；不设单节预算，因为模板的权威归属表本身就接近 x-media-saver 的 4 KB 单节上限。
  - 标题骨架全部必备且按序、无内容写一句白话（用户裁决）：不强制就无法校验。行为规格取 x-media-saver 的严格四节，不取 media-glance 的“首尾固定、中间每项能力一节”，后者让检查器只能查首尾。
  - ADR 索引初始化即建（用户裁决）：三个项目都自己建了，因为取代关系与“哪些仍有效”从文件名看不出；骨架随模板落地，检查器对 `adr/` 与 `research/` 用同一条规则。
  - 路由只留 `AGENTS.md` 触发表：三个项目各有两到三张表且行会漂移，重构时都删掉了总览里的第二张；触发表每行只指一个入口页，ADR 与调研声明为仅追溯时读。
  - 正文只写读代码得不到的内容，“代码与验证入口”不列源文件清单与测试用例名；配预算的拆页规则（枢纽页加同名子目录，不留重定向页）。
  - 调研索引每条带状态与何时读；历史证据不改写，唯一例外是被链接页面移动或拆分时改链接目标，否则第一次拆页就与链接检查冲突。
  - 写进目标项目的“阶段 3 填入”“Matt setup”等内部说法改为白话。
- **功能地图是行为规格之上的索引层，不取代它**：feature-map 类做法回答“有什么、在哪”，行为规格回答“做了之后应观察到什么”，后者是 `/acceptance` 的预期来源；只留地图时 agent 找得到位置却判断不了行为对错。地图做成架构总览里的一张表而非独立文件，登记时机沿用“首次被测试覆盖”。
- **skill 读写的项目合同独占一页**：`/prune-tests` 的分层合同与保留范围、`/acceptance` 的环境契约原先是 `workflow.md` 里的三节，skill 按节名读写。media-glance 实测改代码任务的共有必读量 16702 字符，这三节占 5632 而一般任务用不上；存量项目各自移动了某节，skill 按节名找不到就在 `workflow.md` 重建，内容分叉。现为 `test-layers.md` 与 `local-acceptance.md` 两页，skill 只认路径；分层合同与保留范围同页，因为它们是 `/prune-tests` 同一次运行的读和写。两页必须进文档图谱：`test-layers.md` 由 `agents/testing.md` 入链，`local-acceptance.md` 由 `workflow.md` 入链，都登记在 `docs/INDEX.md`。
- **源码到文档的映射取 bangou 的 `covers` 加只提示的 `docs-affected`**：要解决的是“改了某个源文件，该看哪几页”。三个项目各做了一套：x-media-saver 要求模块页逐个链接源文件（与“不写源文件清单”相反），media-glance 到符号粒度且配 894 行 Swift 专用脚本，bangou 是 frontmatter 的 `covers` glob 加 67 行脚本。业界调研显示显式的代码到文档映射不是主流，frontmatter glob 按路径加载规则的形式已被各 agent 工具普及；采纳 bangou 的形状，因为最轻且与 stack 无关。
  - `--affected` 并进 `check_docs.py`，existing 模式补缺的脚本仍只有一个。默认基准 `HEAD`（未提交改动与未跟踪文件），不猜默认分支名。
  - `docs-check` 只查每项 `covers` 至少匹配一个现存文件，防止代码移动后映射悄悄失效；不强制模块页声明 `covers`。
  - 不进门禁、退出码恒为 0：命中不等于必须改，强制会逼出“碰一下页面”的无效改动。
- **文档同步靠提示词层面的规则加一个只提示的命令**：`docs-check` 查不出正文过时。最可能的断点是空项目里建页条件若是判断题（“有了可描述的行为”），agent 会一直推迟，所以改为“行为首次被测试覆盖”；另有 `CODING_STANDARDS.md` 的漏改模块页判断项供 code-review 捞出，`testing.md` 的 implement-spec 规则把同步链接传给 implementer 与 merger。已积累的正文漂移由用户级 `/docs-audit` 核对，不进模板。

### 收敛已有文档与从代码补写

- **两步都交子 agent，主 agent 只收尾**：分类要通读全文，所以用通用子 agent 而非只读片段的检索型；合并与补写是重活，经主 agent 转写没有意义，由可写子 agent 直接写文件。主 agent 负责链接、索引、票据与复核。
- **分类独立**：简报只给候选与规则，不附主 agent 的预判（e2e 中 prompt 里已写好“这些是约束类”，分类失去独立性）。
- **分批先全部分类再执行**：执行会移动文件，x-media-saver 运行时第二个分类子 agent 未返回就开始执行，回报的引用位置随即失效。目标文件重叠的批串行，各批预分配 ADR 编号段。
- **引用查找用 `git grep -nF`**：x-media-saver 运行时裸 `grep -r` 扫进被忽略的 `.worktrees/` 与 `output/`，单次结果 33 万到 55 万字节。
- **候选扩到标准结构内**：`docs/research/` 直接子级的验收记录（media-glance 的 8 份 `*-integration.md` 原先没被分类）、骨架不符或超预算的已有页、未登记索引的文件。已有模块页按模板重排，原小标题降为三级保留锚点（media-glance 用户选择迁移）。
- **`CLAUDE.md` 的非 Agent-skills 节直接作为候选**，不先并入 `AGENTS.md` 再搬第二次；最后只留 `@AGENTS.md`。
- **合并不丢内容**：只有“已被吸收”“明显过时”可删并须引用依据；“冲突”限定为两者不能同时成立（e2e 中手动 `uv build` 与 CI 构建可以并存，却被列为裁决项）。术语只迁项目特有条目（media-glance 运行时 86 条全部迁入，用户删减 47 条）。票据照录原句加来源、优先级用默认值、暂缓项用延后状态（e2e 中“导出 CSV”被扩写成需求并自定 P3、P4）。ADR 背景与后果只用原话。
- **补写只写代码可证实的内容**：推得出但无测试覆盖的标“未验证”，类型标注不写成“必须”，模块边界只写观察到的依赖现状、不新增“不得……”规范，不补常识性环境说明、不把脚手架布局当代码事实；冲突记为已知差异，术语与 ADR 只报告。展开描述时不把用户答案与代码事实拼成代码没有的能力（e2e 中 README 写出“可命令行录入”，再把自造的差异交用户裁决）。
- **`workflow.md` 的命令与门禁由主 agent 在补齐 task 之后按实际用法填写**：补写子 agent 早于补 task 运行，按契约写会写出已有 `test` 并不支持的参数。缺少 task 的实现建议并入补写子 agent，因为它本来就要读这些配置。

### 工具链与门禁

- **项目是 stack 的集合，不按组合枚举**：每个 stack 在 `toolchain/stacks/<name>/` 自包含，脚本拼合 `mise.toml` 与文档。按 uv-node 这类组合各写一份时偏好改一处要同步多处，加 swift 后组合数爆炸。
- **按文件证据判定，已有工具链不改动**：判定不出时退出码 3 交用户多选。existing 模式只补依赖偏好，以及两个与 stack 无关的标准库脚本：不补 `check_docs.py` 的话 `docs-check` 只能是空壳，不补 `with_lock.py` 的话已有项目的 full 测试入口永远拿不到主机锁。配套只允许对已有 task 做两种最小改动（`gate-core` 追加依赖、full 入口包锁），命令不改；已有 core 命令会收集 full 测试时也不改，因为收窄收集范围可能改变项目原有测试集，改为报告风险并列票据候选。existing 模式不运行项目门禁：本次没改代码，其红绿与初始化无关；报告写“未运行”，不预测失败点。
- **工具链分层：系统包管理器 → mise → 其余工具**：按用户统一的依赖管理规范，mise 由 Homebrew/APT 安装，uv、node、pnpm 由 mise 提供；项目只钉对版本敏感的工具，`mise.lock` 锁精确版本，Python 由 uv 按 `.python-version` 管理。各 stack 的钉版本合并成一份根 `mise.toml`，`mise install`、`mise lock` 在所有 stack 安装前统一执行一次，避免多 stack 时多份配置冲突。缺 mise 的提示只给系统包管理器的装法。
- **命令契约是 mise task，不再是 justfile**：用户决定工具、环境变量与 task 都经 mise 管理，目标项目不依赖 just；不兼容也不迁移已由 justfile 初始化的项目，`justfile` 不再作为已有工具链的证据。拥抱 mise 的默认行为，不在其上再包一层：
  - 各 stack 实现为 `mise-tasks/<stack>/` 下的 file task，名称空间 `<stack>:<name>`，参数直接进 `$@`。
  - 公开 task 只用 `depends` 聚合，默认并行；用户接受门禁子任务并行（core 本就要求可并行，full 由主机锁排队）。只有 `depends` 的 task 静默忽略参数，所以定向一律调 stack task。
  - `check-toolchain` 不核对 mise 管理的工具版本：`mise run` 会自动安装缺失工具并放进 PATH，用户接受这种自动安装。
  - 锁落在 `<stack>:test-full` 而不是公开 task：公开 task 只有 `depends`、没有命令可包；这样公开入口与定向运行都持锁。
  - 任何新项目都生成根 `mise.toml`（`[tools]` 可为空），契约入口在所有项目一致。
  - existing 模式用 `tomllib` 读配置判断缺少的 task，不调用 mise，免得执行需要 trust 的配置代码；读不到的引入方式由 agent 用 `mise tasks` 复核，不替用户 trust。
  - 不运行也不要求 `mise trust`：mise 默认（非 paranoid）下只含普通 `[tools]`、`[tasks]` 的配置不需要 trust，`mise run`、`mise install`、`mise exec` 还会自动 trust 当前配置。
- **门禁契约固定，实现可换**：所有项目共用同一组公开 task 名；none 的 task 非零退出而非留空，沿用 Beadwork 的“验证未实现必须失败”。core/full 定义写进目标项目文档正文，不只放 `mise.toml` 注释。
- **两道门禁，不按测试种类加层**：评估过“单元、集成、系统、真实环境验收”四层方案后未采纳。门禁数量跟触发时机走，流程里只有单 ticket、最终集成、发布前三个时机，对应 `gate-core`、`gate-full` 与 `/acceptance`；集成测试与系统测试都进 full。某个项目的镜像构建让 `gate-full` 慢到影响最终集成时，在该项目内单加 task。模板里“验收”只指 `/acceptance`。
- **full 用主机锁而不是“ticket 阶段只写不跑”**：x-media-saver 的做法让 red → green 对 full 缺失、问题堆到最后，implementer 也有动机绕过规则；加主机级 `flock` 后 implementer 可定向跑自己的 full 测试并自动排队。选主机级而非仓库级，因为桌面与端口是主机资源，各 worktree 的编译产物都在自己目录内。full 不因“已隔离”而放开并行：是否真的隔离容易判断错。`with_lock.py` 由父进程持锁、子进程运行命令，原先锁 fd 可继承且 `execvp`，测试留下的后台进程会一直占锁；终端前台时不重复转发 SIGINT，避免 pytest 类 runner 收到两次 Ctrl-C 硬中止。
- **implement-spec 的门禁靠触发词、审查项与主机锁，不加常驻约束**：规则正文在 `testing.md`，由触发表“执行 `implement-spec`”命中；分层归属的把关写进 `CODING_STANDARDS.md`，由 implement-spec 末尾的 code-review 检查。不复制 x-media-saver 的 6 条长版（通用流程常识）与收录表（与分层表重复）。
- **full 按各 stack 自己的测试文件判定，出现即收录**：`tests/full/` 不存在时提示并通过，有该 stack 的测试文件而零收集则失败，既不让新项目的 gate-full 长期红灯，也不给 skip 留口子。按目录判定会让 uv+swift 共用 `tests/full/` 时任一方加测试就令另一方失败。
- **swift 只落 SwiftPM package，仅支持 macOS**：`.xcodeproj` 无法可靠模板化。`swift test` 零匹配退出 0，所以 task 自己检查零匹配；`tests/full/` 需要在 Package.swift 声明 target，否则 SwiftPM 对空目录 target 每次构建都告警。新项目选 swift 时检查 PATH 上的 `xcodebuild`（task 实际依赖的命令，而非平台名，测试可用替身覆盖）；existing 模式不检查，Linux 上用 swift.org 工具链的已有项目仍可补文档。
- **前端 stack 是 Node + pnpm，只落工具链**：直接替换原 Bun stack，不并存两套前端偏好。mise 管理 Node 与 pnpm 的版本 line，不写 `packageManager` 字段，版本来源只有 `mise.toml`；Node 没有内置 TOML 解析，版本自检用正则读 `mise.toml`。React、Vite、Tailwind CSS、shadcn/ui、React Testing Library 作为固定选型只写进依赖政策：空项目里的页面骨架是编造内容，且 shadcn 的初始化依赖项目自己的别名与样式入口。`bun.lock` 不是判定证据。Biome 排除 `.beads/` 并启用 `vcs.useIgnoreFile`：`bd init` 写出的 `metadata.json` 无末尾换行，否则 node 单 stack 初始化完 lint 即红。
- **安装失败返回 1 但不中止流程**：new 模式先落地再安装，失败后重跑会被判为 existing 而静默跳过安装，所以提示用户直接 `mise run install`。
- **运行时 Python 下限 3.14**：skill 脚本与复制到目标项目的脚本都按 3.14+ 标准库编写，不为旧版本做兼容；代价是缺少 3.14 的机器在解析阶段报语法错误。
- **共用政策只写一次**：依赖政策的通用部分（最少依赖、需要该能力时才按优先选型、批量升级后跑完整门禁）放公共 overlay，stack 片段只写各自选型，多 stack 时不再重复 N 份；独占资源清单只登记在 `test-layers.md`，`testing.md` 的 overlay 只给各 stack 的测试位置。
- **技术偏好只进 stack 片段，项目特有内容不进模板**：参考项目的 structlog 接线、Chrome 扩展、libmpv、Docker、CI 不搬，搬的是工具链路线、依赖政策与新增依赖偏好清单。“依赖政策”节会被 existing 模式复制，所以只写对任何项目都成立的偏好。
- **模板目录从本仓库的 pytest 与 Ruff 中排除**：`toolchain/` 下的 `pyproject.toml` 与测试文件是复制到目标项目的模板。

### 验收 harness

- **真实 agent 验收用 headless harness，而不是再写一个测试 skill**：`tests/setup_project/e2e/` 在临时 Git 项目上造 fixture、起 headless 会话执行 `/setup-project`、做确定性检查并派 reviewer，做法见 [e2e.md](e2e.md)。`setup-matt-pocock-skills` 标了 `disable-model-invocation`，其产物用 fixture 模拟；提问在非交互下由预置答案代替。属于仓库维护层，不进门禁，因为需要模型额度且结果有判断成分。

## 明确不做

- 不生成模块页、ADR、调研文件的实例；由 Matt 的 skills 或日常迭代惰性创建。
- 不为项目创建 `CLAUDE.md`：Claude Code 直接读取 `AGENTS.md`。
- 不设 `archive/`、`plans/`，不设逐页体量豁免名单（x-media-saver 建了又删，media-glance 的“只许减小”名单在并行分支上产生合并冲突），不设只报告不失败的检查模式（新项目没有迁移期）。
- 不做 ADR frontmatter 取代关系的双向一致检查：ADR 格式由 Matt 的 domain-modeling 决定。
- 不做反向覆盖（源码根下每个文件都须被 `covers` 认领）：它与“首次被测试覆盖才建页”冲突，新项目一开始就红，且要给每个 stack 定源码布局约定。
- 未回收：bangou 的按子系统分区（monorepo 特有）、media-glance 的页头元数据加生成索引（依赖专用脚本且无测试）、x-media-saver 的命令表与 task 双向核对和环境变量核对。
- 暂缓，等真实项目出现问题再做：`check_docs.py` 核对反引号路径（只抓改名，进门禁后误报会逼 agent 删反引号）；Stop hook 比较 diff（只对 Claude Code 生效，多轮任务每次停下都被挡）；阶段 0 校验 Matt 产物里的链接。
- 不兼容、不迁移由 justfile 契约初始化的项目。

## 待验收

总体状态：2026-11-23 命令契约迁到 mise task 之后，没有跑过任何真实 agent 的 e2e；此前各轮 e2e（`empty`、`uv-existing` 等，最多到全部六个用例加 `--rerun`）与 media-glance、x-media-saver 两次真实 existing 运行的结论已固化进上面的决策。脚本行为由 pytest 覆盖；以下是仍未经真实 agent 或真实项目验证的部分。

- **mise task 契约**：在临时项目用真实 mise 手工跑过 uv+node 的 `gate-core`/`gate-full`（主机锁串行两个 stack 的 `test-full`，core 失败时 `gate-core` 非零）、swift 单 stack 的两道门禁、none 的 `gate-core` 按设计失败。未验证：SKILL.md 阶段 2 第 5 步与 toolchain.md 的补齐契约 task（`mise tasks` 复核、未 trust 时不替用户 trust、按文件补 task）在真实 agent 与真实项目上的表现；改过的模板与 overlay 文本。下次 e2e 至少跑 `empty`、`uv-existing`、`none-empty`。
- **多 stack 组合**：uv+swift 只经过脚本测试与渲染结果的单项验证，没有真实跑通完整门禁；node+swift 没有任何真实验证；两者都在根目录时 `tests/core/` 混放两种语言。动态 exclude 的 `Package.swift` 未在真实 full 测试场景下验收。
- **node stack**：单 stack 与 uv+node 新项目手工跑通过落地、安装与 `gate-full`；e2e 用例 `node-new-with-code`、`uv-node-new` 未在换 stack 后跑过。固定选型没有在真实项目中按文档加入并跑通门禁，Biome 对 Tailwind 指令与 shadcn 生成代码的兼容性未知。`vitest run -t` 零匹配时退出 0（只影响定向运行，门禁不接受筛选参数）。
- **收敛的大规模分支**：分批并行时目标文件重叠的批串行处理、超预算拆页、骨架不符的旧页重排，fixture 都太小未触发。x-media-saver 运行后加的四条措辞（不做执行前确认、分批理由、`git grep`、裁决项只列无法推荐的）未复验，已补 e2e 用例 `uv-large-docs`（30 多个候选、附件、超预算页、骨架不符模块页、被忽略的仓库副本），尚未真实运行。
- **验收记录的二进制附件**：x-media-saver 用户事后删掉了迁入 `research/acceptance/assets/` 的截图、日志与 jsonl（约 1.9 MB），只留链接文字。是否写成“二进制附件不迁入、删除并注明”的通用规则，等第二个样本。
- **描述与代码的差距**：用户描述与代码现状不一致时是否记为模块页的已知差异，SKILL.md 阶段 2 第 2 步（不拼成代码没有的能力）与 document-code.md（只记旧文档与代码的冲突）都没有明说。
- **真实开发会话里的文档同步**：e2e 只覆盖初始化。下一个用模板初始化的空项目跑过三到五个改代码的任务后回看：是否在行为首次被测试覆盖时建了模块页并登记功能地图、模块页是否随后续改动更新、是否写出合适的 `covers` 并运行 `docs-affected`、完成报告是否列出文档影响、400 字符行预算是否过紧、超预算时是拆页还是删内容。漏改的位置决定是否启用暂缓的路径核对或 Stop hook。
- **合同独占页**：真实项目上的 `/acceptance` 与 `/prune-tests` 未在 `test-layers.md`、`local-acceptance.md` 新路径下运行过。
- **`bd bootstrap`**：2026-11-23 在临时 bare origin（本地路径）上手工验证过：新 clone 运行 `init_beads.py` 走 bootstrap，原有票据恢复且不产生新提交；已补 e2e 用例 `beads-clone`，尚未在真实 agent 下运行。远端为需要凭据的 git 托管时的克隆耗时与凭据交互未知。
