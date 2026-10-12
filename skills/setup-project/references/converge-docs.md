# 收敛已有文档

阶段 2 第 3 步的执行规范：把目标项目里标准结构之外的文档收敛进标准结构。全自动执行，不 commit，所有动作停在工作区并进报告，用户提交前通过 `git status` 审阅。分工：只读子 agent 分类，可写子 agent 执行合并与迁移，主 agent 收尾。

## 候选范围

候选 = 满足全部条件的文件：

- 扩展名为 `md`、`txt`、`rst`、`adoc`，或与某候选同目录且被其引用的附件（图片、HTML 原型、JSON 证据等）。`txt` 只收录内容为说明文字的文件：`requirements*.txt`、`CMakeLists.txt` 等配置不是候选。
- 不在标准结构内：标准结构指模板创建的全部路径，`docs/agents/` 下 Matt setup 产出的全部文件，根目录的 `GLOSSARY-MAP.md`、`CLAUDE.md`、`CONTRIBUTING.md`、`LICENSE*`，以及 `docs/` 下按需目录（`adr/`、`architecture/modules/`、`architecture/collaborations.md`、`specs/`、`operations/`、`changes/`、`research/`）。
- 不在测试目录或 fixture 目录内（`tests/`、`fixtures/`）。
- 受 Git 管理或未被忽略：忽略规则排除的文件（缓存、输出、凭据）不是候选。
- 不在工具目录内：`.beads`、`.claude`、`.agents`、`.codex`、`.cursor`、`.github`、`.scratch`、`.out-of-scope`。
- 未在 `docs/INDEX.md` 的"项目特有入口"中登记。

主 agent 用一条命令列出候选，再传给子 agent：

```sh
git ls-files --cached --others --exclude-standard \
  | grep -E '\.(md|txt|rst|adoc)$' \
  | grep -vE '^(\.beads|\.claude|\.agents|\.codex|\.cursor|\.github|\.scratch|\.out-of-scope|docs/agents|tests|fixtures)/' \
  | grep -vE '^(GLOSSARY-MAP|CLAUDE|CONTRIBUTING)\.md$|^LICENSE|requirements[^/]*\.txt$|CMakeLists\.txt$' \
  | sort
```

从结果中去掉标准结构路径和已登记路径。

`AGENTS.md` 里用户自己写的二级节也是候选，包括阶段 2 第 1 步刚从 `CLAUDE.md` 并进来的节。上面的命令列不出它们，主 agent 另外用下面的命令列出全部二级标题，去掉模板节（`常驻约束`、`按任务读取`）后，以"`AGENTS.md#节标题`"的形式加入候选清单：

```sh
grep -n '^## ' AGENTS.md
```

另外两类候选在按需目录内，上面的命令同样列不出：

- `docs/research/` 直接子级中的验收或交付记录（里程碑集成记录、验收矩阵之类，内容是某次交付的结果而非调研结论）。主 agent 用 `ls docs/research/*.md` 过一遍标题与开头，按分类表移入 `acceptance/`。
- `docs/architecture/modules/*.md` 中二级标题与 `docs/agents/documentation.md` 模块页模板不一致的页。主 agent 用 `grep -n '^## ' docs/architecture/modules/*.md` 比对。

`AGENTS.md` 只放跨任务约束与触发表，细则进正文，所以这些节按下面规则分流：

- **约束类**（禁止什么、必须什么、一句话能判断是否违反）：并入 `## 常驻约束`，删除用户的原标题。其中能机械判定的代码规则（长度、类型标注之类）也先留在常驻约束，并在报告里建议接入 lint 或 typecheck 的票据；只有需要判断的评审标准才进 `CODING_STANDARDS.md`，与该文件"只写工具查不出的判断类标准"一致。
- **细则类**（流程、步骤、配置、背景说明）：按分类表迁入对应正文；不能归类的保留原节并在报告说明。

没有候选时整步跳过。候选超过 30 个时按顶层目录分批：全部批次先完成分类，再按下文执行。

## 分类表

子 agent 读取每个候选的内容，按三态规则和讨论结论落点表归类。一个文件可拆成多条。

| 内容 | 动作 | 目标 |
| --- | --- | --- |
| 描述当前系统结构、模块职责、某能力的行为 | 合并改写 | `architecture/INDEX.md`、`module-boundaries.md` 或对应模块页；模块页不存在则按模板建页 |
| 某个决定的背景、选择与理由 | 迁移 | `docs/adr/NNNN-<slug>.md`，编号接续；"背景"与"后果"只用源文档原话或代码能支撑的内容，不补动机、不补通用利弊、不把并列改写成因果 |
| 调研、比较、实验、验收记录 | 移动 | `docs/research/`；验收与交付记录进 `acceptance/<主题>-<日期>.md`，日期取正文记载的完成日，登记索引 |
| 尚未实现的需求、计划、路线图 | 迁移 | tracker 票据；正在实施的放 `docs/changes/<topic>.md` |
| 术语解释 | 合并 | `GLOSSARY.md`，只迁入项目特有术语和借通用说法描述本项目具体概念的条目；通用界面与编程词条不迁入，报告列出删除清单 |
| 开发、构建、测试说明 | 合并 | `docs/development/` 对应文件 |
| 部署、运行配置、发布说明 | 合并 | `docs/operations/`，不存在则创建 |
| 编码约定、评审标准 | 合并 | `CODING_STANDARDS.md`；流程约束进 `AGENTS.md` 常驻约束 |
| 根目录 `ARCHITECTURE.md`、`docs/glossary.md` 等同义异位文件 | 合并后删除 | 对应标准位置 |
| 已被当前正文吸收、或内容明显过时 | 删除 | 无；报告注明依据 |
| 子包 README、LICENSE、法律与第三方文件、无法判断的文件 | 保留并登记 | 原位；在 `docs/INDEX.md` 新增"项目特有入口"表登记路径与原因 |
| 章节与模板不一致的已有模块页 | 按模板重排 | 原页；二级标题改为模板的六节，原有小标题降为三级保留以维持锚点，事实、链接与已知差异原样搬入对应章节，不补写、不删减；每页一个可写子 agent 并行 |

同一文件内容跨多类时拆分到各目标，原文件删除或保留登记。`AGENTS.md` 的细则节迁移时整段原文搬入目标文件，不改写措辞；搬完必须删除 `AGENTS.md` 里的原节（留着就是两处重复），再在 `## 按任务读取` 表加一行指向新位置，正文里对应的 `<待填 按需：…>` 标记（如 workflow 的"发布"）用指向新位置的链接填写。疑点与待用户裁决的事项只写进最终报告，不在目标文档里加"待裁决"之类的标注。旧文档的内容与 `AGENTS.md` 或现有正文看似冲突时，仍按分类表合并到目标位置，并把疑点写进报告由用户裁决；不得以"冲突"为由丢弃。只有"已被当前正文吸收"或"内容明显过时"两种情况可以删除，报告要引用吸收位置或过时依据。合并时以标准位置的正文为骨架，不把旧文件整体粘贴进去；旧文件里的时点性描述归 research，不写进当前正文。

## 分类子 agent

派一个只读的通用子 agent，非 Fable 模型；不用 Explore 类，它只读片段，而分类需要通读全文。简报必须包含：候选清单、本文路径、`docs/agents/documentation.md` 路径、已填与未填的 `<待填` 标记清单。要求它读完每个候选后返回一张表，不做任何修改：

| 候选路径 | 分类 | 动作 | 目标路径 | 引用该文件的位置 | 可据此填写的待填标记 |
| --- | --- | --- | --- | --- | --- |

引用位置通过 grep 文件名和相对路径获得。可填写的待填标记只列能从该文件内容直接得出的。

## 执行子 agent

分类表返回后，派一个可写的通用子 agent，非 Fable 模型，执行下面执行顺序的第 1、2 步。合并需要通读旧文档并以标准正文为骨架改写，经主 agent 转写没有意义，因此由子 agent 直接写文件。简报必须包含：分类表、本文路径、`docs/agents/documentation.md` 路径、模块页模板所在位置、分配给它的 ADR 编号段。分类为 tracker 的源文件不由它删除。

分批时每批一个执行子 agent：主 agent 派发前比对各批的目标路径，目标文件有重叠的批（常见于 `GLOSSARY.md`、`architecture/INDEX.md`）串行，其余并行；为每批预分配互不重叠的 ADR 编号段，避免并行撞号。

子 agent 返回：改写或创建的目标文件、移动与删除的源文件、与分类表不一致的处理及原因。

## 执行顺序

顺序固定，第 1、2 步由执行子 agent 完成，第 3 到 7 步由主 agent 完成：

1. 先合并与迁移内容：创建或改写目标文件，ADR 编号接续，模块页按模板建，已有模块页按模板重排。
2. 再移动与删除源文件，包括删除已迁出的 `AGENTS.md` 节；源文件的每一句都已落入某个正文后才可删除，分类为 tracker 的源文件保留，待第 6 步建票后由主 agent 删除。
3. 用 grep 找出所有指向旧路径的链接并改为新路径；被删除文件的链接改指吸收位置。
4. 在 `docs/INDEX.md` 登记保留的文件，新建的按需目录（如 `operations/`）在入口分工表加行；在 `docs/research/INDEX.md` 登记迁入的研究。
5. 按表填写可填的 `<待填` 标记。
6. 把需要进 tracker 的计划项创建为票据，按 `docs/agents/issue-tracker.md` 操作；票据建好后删除这些源文件。
7. 复核子 agent 的返回与分类表一致，把每个候选的动作与目标（含从 `AGENTS.md` 迁出的节及其新位置）、保留登记清单、删除清单及依据、更新的链接数、仍未填的标记汇入最终报告。

不 commit。重跑时已登记和已迁移的文件不再是候选，因此第二次执行无动作。
