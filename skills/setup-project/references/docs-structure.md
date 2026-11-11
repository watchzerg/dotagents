# 标准化文档结构

文档结构初始化（SKILL.md 阶段 1 第 2 步）固化的目录结构及其依据。模板正文在 `../templates/`，本文记录为什么这样分、哪些是硬约束。设计来源：mattpocock-skills 1.3.1 的路径约定，x-media-saver 与 media-glance 两个项目的实践对比（2026-10-11），以及这两个项目与 bangou 各自重构文档架构后的回收（2026-11-11）。

## 目录树

```text
<repo>/
├── README.md                        # 人类入口，只路由到 docs/INDEX.md
├── AGENTS.md                        # 常驻约束 + 唯一触发表（Matt 的三个指针已并入）
├── GLOSSARY.md                      # Matt 硬编码路径，必须在根目录
├── CODING_STANDARDS.md              # code-review 按名查找
└── docs/
    ├── INDEX.md                     # 冷启动路径 + 入口分工表，不含触发表
    ├── agents/                      # agent 按任务读取的规则
    │   ├── issue-tracker.md         #   Matt setup 产出，不在模板内
    │   ├── domain.md                #   Matt setup 产出，不在模板内
    │   ├── triage-labels.md         #   Matt setup 产出，不在模板内
    │   ├── testing.md
    │   └── documentation.md         # 三态规则、取舍原则、权威归属、页面模板、体量预算、自动检查
    ├── architecture/
    │   ├── INDEX.md                 # 总览、功能地图、模块地图、依赖、不变量
    │   ├── module-boundaries.md
    │   ├── collaborations.md        # 按需；超预算时一流程一页放 collaborations/
    │   └── modules/<module>.md      # 按需，六节固定；超预算时子页放 modules/<module>/
    ├── behaviors/<topic>.md         # 按需：用户可见行为跨模块或有非开发读者时；存量正文，非增量 spec
    ├── adr/
    │   ├── INDEX.md                 # 初始化即建：编号、标题、状态、取代关系、何时读
    │   └── NNNN-<slug>.md           # Matt 惰性创建，状态与取代关系进 frontmatter
    ├── research/
    │   ├── INDEX.md                 # 每条带状态、结论与去向、何时读
    │   ├── <topic>.md               # Matt research skill 落点
    │   └── acceptance/<topic>-<date>.md
    ├── development/
    │   ├── workflow.md              # 命令与门禁
    │   ├── technology-stack.md
    │   ├── test-layers.md           # 测试分层合同与保留范围，/prune-tests 按路径读写
    │   └── local-acceptance.md      # 环境契约，/acceptance 按路径读取
    ├── operations/                  # 按需：有可部署产物时
    └── changes/<topic>.md           # 按需：Markdown 增量规格，吸收后删除
```

## 硬约束

- `GLOSSARY.md`、`GLOSSARY-MAP.md`、`docs/adr/`、`docs/agents/` 是 Matt skills 直接按路径读写的位置，不可改名或移动。media-glance 把术语表放 `docs/glossary.md` 并靠改写 `domain.md` 兜底，只对读过 `domain.md` 的 skill 生效，不采用。
- `CODING_STANDARDS.md` 和 `CONTRIBUTING.md` 是 code-review 搜索编码规范时必须命中的文件名，位置不限，放根目录最稳。
- Matt 的 setup 会在 `AGENTS.md` 追加 `## Agent skills` 块。它是本 skill 的前置且之后不再重跑，所以其指针并入触发表，脚本移除该块；重跑 Matt setup 会再次追加，再跑本 skill 即可再次移除。
- `docs/development/test-layers.md` 与 `docs/development/local-acceptance.md` 分别是 `/prune-tests` 与 `/acceptance` 按精确路径读写的合同页，两个 skill 不设回退、不按节名查找，改名或移动后会被当成文件缺失而重新起草。每份合同独占一页，不放进 `workflow.md`：后者是改代码任务的必读页，这两份合同只在精简测试或真实环境验收时才用得上。
- Matt 的 `code-review` 按分支名在 `docs/`、`specs/`、`.scratch/` 下找 spec，`docs/changes/<topic>.md` 可被命中。

## 渐进发现的层次

| 层 | 何时读 | 内容 |
| --- | --- | --- |
| 0 常驻 | 每次会话 | `AGENTS.md`：几条约束加触发表，只放指针 |
| 1 按任务 | 触发表命中 | 该任务唯一的权威正文 |
| 2 下钻 | 沿正文链接 | 模块页 → 依赖模块、规格、代码与测试入口 |
| 3 冲突时 | 改变取舍或需要证据 | `adr/`、`research/` |
| 4 冷启动 | 无任务或未命中 | `docs/INDEX.md` 的阅读路径 |

每个 INDEX 只回答"去哪读"；每条规则只有一个权威落点；因此层次可以加深而常驻上下文不增长。

## 与两个参考项目的取舍

| 分歧 | 选择 | 理由 |
| --- | --- | --- |
| 架构正文位置 | 全部在 `docs/architecture/`，根目录不放 `ARCHITECTURE.md` | x-media-saver 分散在三处；根目录只留生态按名查找的文件 |
| 产品规格与模块页 | 默认只有模块页，行为规格是其一章；`behaviors/` 按需 | 两棵"当前真相"树的交叉链接是单人项目的负担 |
| 用户可见行为目录的命名 | `behaviors/`，不用 `specs/` | Matt 的 implement-spec 与 code-review 把 spec 当增量规格，`docs/specs/` 会被误读；behaviors 与模块页"当前行为规格"同词，表明它是该章的升格 |
| 功能清单 | 架构总览里一张功能地图表，每个功能一行并链接到行为规格；不建独立的 feature-map 文件，也不用它取代行为规格 | 地图回答"有什么、在哪"，行为规格回答"做了之后应观察到什么"，后者是 `/acceptance` 的预期来源；表只做索引就不会成为第二棵"当前真相"树 |
| 增量与归档 | tracker 为主，Markdown 兜底 `changes/`，吸收后删除；不设 `archive/`、`plans/` | git 保留历史；归档层及其 INDEX 是 Beads 之前遗留设计文档的产物 |
| 研究与验收 | `research/` 常驻不归档，验收记录在 `research/acceptance/` | 证据自带时点，归档没有意义 |
| 触发表 | 只在 `AGENTS.md` 一份，架构总览不设“按任务阅读” | 两个项目各有两到三张表，行会漂移；三个项目重构时都删掉了总览里的第二张路由表 |
| INDEX 数量 | `docs/`、`architecture/`、`research/`、`adr/` 四个 | 原先不建 ADR 索引，理由是文件名自描述；三个项目后来都自己建了，因为取代关系与“哪些仍有效”从文件名看不出。骨架随初始化建好，检查器不必区分有无索引 |
| 三态规则 | 只写在 `agents/documentation.md` | 两个项目在 INDEX 与维护规则里各写一遍 |
| development 与 operations | 以"改代码还是跑产物"划分；无可部署产物时不建 `operations/` | 运行配置与发布归 operations，Docker 的 build 归 development、run 归 operations |

## 持续维护机制

让项目里的 agent 按意图维护这套结构，靠的是文档自身携带的规则，而不是外部提醒：

- **每篇正文开头一段职责声明**：本文负责什么、不负责什么、相关规则在哪。agent 打开任何一篇都能判断内容是否放对了地方。
- **`<待填 时机：说明>` 协议**：初始化留下的标记是"尚未成形"的显式信号，自带可填时机。`AGENTS.md` 常驻约束规定每次交付前搜索标记，时机已到或本次产生了内容就填并删，否则保留，不编造；全部消失后该条自删。`grep` 即剩余清单，不另建文件。架构总览为空时，第一个改代码的任务先补模块地图再动手。
- **讨论结论的落点表**：`agents/documentation.md` 按结论类型指定唯一位置，避免另建纪要或塞进 AGENTS.md。
- **随交付同步清单**：切片完成时改写模块页、同步地图与边界、术语与 ADR、索引与触发表；无影响时说明判断。
- **建页触发可判定**：模块页在该职责的行为首次被测试覆盖时创建（脚手架自带的工具链测试除外），不用"有了可描述的行为"这类判断题，否则空项目里 agent 会一直推迟建页，后面的同步没有对象。触发表的测试行与权威归属表都写同一条件。
- **同步规则有第二道检出**：`CODING_STANDARDS.md` 列"改了行为、接口或位置却没同步模块页"为交付不完整，让 code-review 的标准轴能捞出漏改；`testing.md` 的 implement-spec 规则要求把同步链接传给 implementer 与 merger，多 agent 流程不丢约束。另有 `just docs-affected` 按模块页页首的 `covers` 列出改动命中却没改的页，只提示不进门禁；它把"该看哪页"从靠 agent 回忆变成可运行的命令，但页面改没改对仍要判断。这些仍是提示词层面的规则，`docs-check` 只验证结构与 `covers` 有匹配，查不出正文过时。
- **结构规则由 `docs-check` 强制**：全部文档可从 `AGENTS.md` 到达、ADR 与调研逐个登记索引、单页 16 KB 与单行或单元格 400 字符的体量预算、模块页六节与行为规格四节的标题骨架、`covers` 每项有匹配。规则正文只在 `agents/documentation.md`，脚本只实现。预算约束的是单个任务必须读入的量：三个参考项目重构后文档总量都没减少，降的是每任务加载量。不设逐页豁免名单，超限只能精简或拆成枢纽页加子页。
- **正文只写读代码得不到的内容**：`agents/documentation.md` 的取舍原则列出不写的东西（目录树、源文件清单、逐测试覆盖、票据流水等），模块页的“代码与验证入口”只留入口符号与未验证范围。
- **AGENTS.md 防膨胀**：常驻约束明文规定本文只放指针，细则进正文并在触发表加行。retro 建议的新规则因此落到 `CODING_STANDARDS.md` 或对应正文。
- **索引即存在**：`research/` 与 `adr/` 的新文件必须登记，未登记时 `docs-check` 失败，防止 Matt 的 skills 产出散落。调研索引每条带状态（现行、已吸收、已被取代、一次性记录）与何时读，让 agent 不必打开已被吸收的证据；历史证据不改写，唯一例外是被链接页面移动或拆分时改链接目标。
- **文档检查进门禁**：工具链落地时 justfile 提供 `docs-check` 并纳入 `gate-core`；`workflow.md` 的对应位置由 `阶段3` 标记占位。

## 初始化方式

模板按"缺失才创建"复制，`{{PROJECT_NAME}}` 替换为 `--name`、`AGENTS.md` 的一级标题或目录名（按此顺序），已有文件一律不覆盖（只有空白的文件视为缺失），因此可重复运行。`<待填 时机：说明>` 标记留给 agent 按项目实际填写；`AGENTS.md` 已存在时由脚本按二级标题合并，二级标题前没有内容时补模板开头（标题与 `初始化` 标记），agent 只处理同义节与 `CLAUDE.md`。不用软链接：这些文件进入目标项目后随项目迭代持续改写。
