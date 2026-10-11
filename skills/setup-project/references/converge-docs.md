# 收敛已有文档

阶段 2 第 3 步的执行规范：把目标项目里标准结构之外的文档收敛进标准结构。全自动执行，不 commit，所有动作停在工作区并进报告，用户提交前通过 `git status` 审阅。

## 候选范围

候选 = 满足全部条件的文件：

- 扩展名为 `md`、`txt`、`rst`、`adoc`，或与某候选同目录且被其引用的附件（图片、HTML 原型、JSON 证据等）。
- 不在标准结构内：标准结构指模板创建的全部路径，以及 `docs/` 下按需目录（`adr/`、`architecture/modules/`、`architecture/collaborations.md`、`specs/`、`operations/`、`changes/`、`research/`）。
- 受 Git 管理或未被忽略：忽略规则排除的文件（缓存、输出、凭据）不是候选。
- 不在工具目录内：`.beads`、`.claude`、`.agents`、`.codex`、`.cursor`、`.github`、`.scratch`、`.out-of-scope`。
- 未在 `docs/INDEX.md` 的"项目特有入口"中登记。

主 agent 用一条命令列出候选，再传给子 agent：

```sh
git ls-files --cached --others --exclude-standard \
  | grep -E '\.(md|txt|rst|adoc)$' \
  | grep -vE '^(\.beads|\.claude|\.agents|\.codex|\.cursor|\.github|\.scratch|\.out-of-scope)/' \
  | sort
```

从结果中去掉标准结构路径和已登记路径。没有候选时整步跳过。候选超过 30 个时按顶层目录分批，每批独立走完分析与执行。

## 分类表

子 agent 读取每个候选的内容，按三态规则和讨论结论落点表归类。一个文件可拆成多条。

| 内容 | 动作 | 目标 |
| --- | --- | --- |
| 描述当前系统结构、模块职责、某能力的行为 | 合并改写 | `architecture/INDEX.md`、`module-boundaries.md` 或对应模块页；模块页不存在则按模板建页 |
| 某个决定的背景、选择与理由 | 迁移 | `docs/adr/NNNN-<slug>.md`，编号接续 |
| 调研、比较、实验、验收记录 | 移动 | `docs/research/`（验收进 `acceptance/`），登记索引 |
| 尚未实现的需求、计划、路线图 | 迁移 | tracker 票据；正在实施的放 `docs/changes/<topic>.md` |
| 术语解释 | 合并 | `GLOSSARY.md` |
| 开发、构建、测试说明 | 合并 | `docs/development/` 对应文件 |
| 部署、运行配置、发布说明 | 合并 | `docs/operations/`，不存在则创建 |
| 编码约定、评审标准 | 合并 | `CODING_STANDARDS.md`；流程约束进 `AGENTS.md` 常驻约束 |
| 根目录 `ARCHITECTURE.md`、`docs/glossary.md` 等同义异位文件 | 合并后删除 | 对应标准位置 |
| 已被当前正文吸收、或内容明显过时 | 删除 | 无；报告注明依据 |
| 子包 README、LICENSE、法律与第三方文件、无法判断的文件 | 保留并登记 | 原位；在 `docs/INDEX.md` 新增"项目特有入口"表登记路径与原因 |

同一文件内容跨多类时拆分到各目标，原文件删除或保留登记。合并时以标准位置的正文为骨架，不把旧文件整体粘贴进去；旧文件里的时点性描述归 research，不写进当前正文。

## 子 agent

派一个只读的 Explore 类子 agent，非 Fable 模型，中等思考强度。简报必须包含：候选清单、本文路径、`docs/agents/documentation.md` 路径、已填与未填的 `<待填` 标记清单。要求它读完每个候选后返回一张表，不做任何修改：

| 候选路径 | 分类 | 动作 | 目标路径 | 引用该文件的位置 | 可据此填写的待填标记 |
| --- | --- | --- | --- | --- | --- |

引用位置通过 grep 文件名和相对路径获得。可填写的待填标记只列能从该文件内容直接得出的。

## 执行顺序

主 agent 按表执行，顺序固定：

1. 先合并与迁移内容：创建或改写目标文件，ADR 编号接续，模块页按模板建。
2. 再移动与删除源文件。
3. 用 grep 找出所有指向旧路径的链接并改为新路径；被删除文件的链接改指吸收位置。
4. 在 `docs/INDEX.md` 登记保留的文件；在 `docs/research/INDEX.md` 登记迁入的研究。
5. 按表填写可填的 `<待填` 标记。
6. 把需要进 tracker 的计划项创建为票据，按 `docs/agents/issue-tracker.md` 操作。
7. 报告：每个候选的动作与目标、保留登记清单、删除清单及依据、更新的链接数、仍未填的标记。

不 commit。重跑时已登记和已迁移的文件不再是候选，因此第二次执行无动作。
