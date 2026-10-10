# 标准化文档结构

阶段 2 固化的目录结构及其依据。模板正文在 `../templates/`，本文记录为什么这样分、哪些是硬约束。设计来源：mattpocock-skills 1.3.1 的路径约定，以及 x-media-saver 与 media-glance 两个项目的实践对比（2026-10-11）。

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
    │   └── documentation.md         # 三态规则、目录职责、权威归属、模块页模板
    ├── architecture/
    │   ├── INDEX.md                 # 总览、模块地图、依赖、不变量
    │   ├── module-boundaries.md
    │   ├── collaborations.md        # 按需
    │   └── modules/<module>.md      # 按需，含"当前行为规格"章节
    ├── specs/                       # 按需：行为跨模块或有非开发读者时
    ├── adr/NNNN-<slug>.md           # Matt 惰性创建，无 INDEX，状态进 frontmatter
    ├── research/
    │   ├── INDEX.md
    │   ├── <topic>.md               # Matt research skill 落点
    │   └── acceptance/<topic>-<date>.md
    ├── development/
    │   ├── workflow.md
    │   └── technology-stack.md
    ├── operations/                  # 按需：有可部署产物时
    └── changes/<topic>.md           # 按需：Markdown 增量规格，吸收后删除
```

## 硬约束

- `GLOSSARY.md`、`GLOSSARY-MAP.md`、`docs/adr/`、`docs/agents/` 是 Matt skills 直接按路径读写的位置，不可改名或移动。media-glance 把术语表放 `docs/glossary.md` 并靠改写 `domain.md` 兜底，只对读过 `domain.md` 的 skill 生效，不采用。
- `CODING_STANDARDS.md` 和 `CONTRIBUTING.md` 是 code-review 搜索编码规范时必须命中的文件名，位置不限，放根目录最稳。
- Matt 的 setup 会在 `AGENTS.md` 追加 `## Agent skills` 块。它是本 skill 的前置且之后不再重跑，所以其指针并入触发表，脚本移除该块；重跑 Matt setup 会再次追加，再跑本 skill 即可再次移除。
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
| 产品规格与模块页 | 默认只有模块页，行为规格是其一章；`specs/` 按需 | 两棵"当前真相"树的交叉链接是单人项目的负担 |
| 增量与归档 | tracker 为主，Markdown 兜底 `changes/`，吸收后删除；不设 `archive/`、`plans/` | git 保留历史；归档层及其 INDEX 是 Beads 之前遗留设计文档的产物 |
| 研究与验收 | `research/` 常驻不归档，验收记录在 `research/acceptance/` | 证据自带时点，归档没有意义 |
| 触发表 | 只在 `AGENTS.md` 一份 | 两个项目各有两到三张表，行会漂移 |
| INDEX 数量 | `docs/`、`architecture/`、`research/` 三个 | ADR 文件名自描述、靠扫描编号；archive 已去掉 |
| 三态规则 | 只写在 `agents/documentation.md` | 两个项目在 INDEX 与维护规则里各写一遍 |
| development 与 operations | 以"改代码还是跑产物"划分；无可部署产物时不建 `operations/` | 运行配置与发布归 operations，Docker 的 build 归 development、run 归 operations |

## 持续维护机制

让项目里的 agent 按意图维护这套结构，靠的是文档自身携带的规则，而不是外部提醒：

- **每篇正文开头一段职责声明**：本文负责什么、不负责什么、相关规则在哪。agent 打开任何一篇都能判断内容是否放对了地方。
- **`<待填 时机：说明>` 协议**：初始化留下的标记是"尚未成形"的显式信号，自带可填时机。`AGENTS.md` 常驻约束规定每次交付前搜索标记，时机已到或本次产生了内容就填并删，否则保留，不编造；全部消失后该条自删。`grep` 即剩余清单，不另建文件。架构总览为空时，第一个改代码的任务先补模块地图再动手。
- **讨论结论的落点表**：`agents/documentation.md` 按结论类型指定唯一位置，避免另建纪要或塞进 AGENTS.md。
- **随交付同步清单**：切片完成时改写模块页、同步地图与边界、术语与 ADR、索引与触发表；无影响时说明判断。
- **AGENTS.md 防膨胀**：常驻约束明文规定本文只放指针，细则进正文并在触发表加行。retro 建议的新规则因此落到 `CODING_STANDARDS.md` 或对应正文。
- **索引即存在**：`research/` 的新文件必须登记，未登记视为不存在，防止 Matt 的 research skill 产出散落。
- **链接检查**：阶段 3 的 justfile 应提供文档链接与锚点检查并纳入门禁；`workflow.md` 留有待填位置。

## 初始化方式

模板按"缺失才创建"复制，`{{PROJECT_NAME}}` 替换为目录名或 `--name`，已有文件一律不覆盖，因此可重复运行。`<待填：…>` 标记留给 agent 按项目实际填写；`AGENTS.md` 已存在时由脚本按二级标题合并，agent 只处理同义节与 `CLAUDE.md`。不用软链接：这些文件进入目标项目后随项目迭代持续改写。
