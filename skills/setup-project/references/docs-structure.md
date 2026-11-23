# 标准化文档结构

`init_docs.py`（SKILL.md 阶段 1 第 2 步）落地的目录结构、硬约束与模板自带的维护机制。模板正文在 `../templates/`，规则正文在模板的 `docs/agents/documentation.md`。

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

以下路径由其他 skill 按精确路径或文件名读写，不可改名或移动：

- `GLOSSARY.md`、`GLOSSARY-MAP.md`、`docs/adr/`、`docs/agents/`：Matt skills 直接读写。
- `CODING_STANDARDS.md`、`CONTRIBUTING.md`：code-review 搜索编码规范时按文件名命中。
- `docs/development/test-layers.md`、`docs/development/local-acceptance.md`：`/prune-tests` 与 `/acceptance` 的合同页，两个 skill 不设回退，找不到就当作缺失重新起草。
- `docs/changes/<topic>.md`：Matt 的 `code-review` 按分支名在 `docs/` 下找 spec，能命中这里。

Matt setup 在 `AGENTS.md` 写入的 `## Agent skills` 块由脚本移除，其指针已并入触发表；重跑 Matt setup 后再跑本 skill 即可再次移除。

## 渐进发现的层次

| 层 | 何时读 | 内容 |
| --- | --- | --- |
| 0 常驻 | 每次会话 | `AGENTS.md`：几条约束加触发表，只放指针 |
| 1 按任务 | 触发表命中 | 该任务唯一的权威正文 |
| 2 下钻 | 沿正文链接 | 模块页 → 依赖模块、规格、代码与测试入口 |
| 3 冲突时 | 改变取舍或需要证据 | `adr/`、`research/` |
| 4 冷启动 | 无任务或未命中 | `docs/INDEX.md` 的阅读路径 |

每个 INDEX 只回答“去哪读”，每条规则只有一个权威落点，所以层次可以加深而常驻上下文不增长。

## 模板自带的维护机制

目标项目里的 agent 靠文档自身携带的规则维护这套结构：

- **职责声明**：每篇正文开头说明本文负责什么、不负责什么、相关规则在哪。
- **`<待填 时机：说明>` 标记**：时机取 `初始化`、`阶段3`（工具链落地后）、`首个模块`、`按需`。`AGENTS.md` 常驻约束要求每次交付前搜索标记，时机已到或本次产生了内容就填并删，否则保留、不编造；全部消失后该条约束自删。架构总览为空时，第一个改代码的任务先补模块地图。
- **建页触发**：模块页在该职责的行为首次被测试覆盖时创建（脚手架自带的工具链测试除外）；功能地图登记沿用同一条件。
- **随交付同步**：切片完成时改写模块页、同步地图与边界、术语与 ADR、索引与触发表；无影响时说明判断。`CODING_STANDARDS.md` 把漏改模块页列为交付不完整，`mise run docs-affected` 按模块页 `covers` 列出改动命中却没改的页（只提示，不进门禁）。
- **`docs-check` 强制结构**：全部文档可从 `AGENTS.md` 到达、ADR 与调研逐个登记索引、单页 16 KB 与单行或单元格 400 字符的体量预算（`research/`、`adr/` 豁免）、模块页六节与行为规格四节的标题骨架、`covers` 每项有匹配。不设逐页豁免，超限只能精简或拆成枢纽页加子页。`docs-check` 纳入 `gate-core`。
- **AGENTS.md 只放指针**：细则进正文并在触发表加行，新规则落到 `CODING_STANDARDS.md` 或对应正文。
