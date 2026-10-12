# 文档索引

本页是文档总入口，只负责路由：说明每个入口回答什么问题，以及没有具体任务时从哪读起。按任务读取的触发表在 [AGENTS.md](../AGENTS.md)，文档分类、权威归属与维护流程在[文档维护规则](agents/documentation.md)，本页不复制。

## 冷启动阅读路径

1. [架构总览](architecture/INDEX.md)：系统由什么组成、模块地图、依赖与不变量。
2. [模块边界](architecture/module-boundaries.md)：职责归属与依赖方向；对照 [GLOSSARY.md](../GLOSSARY.md) 理解术语。
3. 按需打开 `architecture/modules/` 中的模块页，再沿链接进代码与测试。
4. 涉及取舍时查 `adr/`；需要证据时查[调研索引](research/INDEX.md)。

## 入口分工

| 入口 | 回答的问题 |
| --- | --- |
| [README](../README.md) | 怎么安装和使用 |
| [AGENTS.md](../AGENTS.md) | agent 的常驻约束和按任务读取入口 |
| [GLOSSARY.md](../GLOSSARY.md) | 领域术语是什么意思 |
| [CODING_STANDARDS.md](../CODING_STANDARDS.md) | diff 评审按什么判断 |
| [架构总览](architecture/INDEX.md) | 系统现在怎样组成与运行 |
| [模块边界](architecture/module-boundaries.md) | 规则归谁、依赖方向与状态所有权 |
| `architecture/modules/` | 某个能力现在完整地怎样工作 |
| `adr/` | 为什么做出重要决定 |
| [调研索引](research/INDEX.md) | 比较与验证的证据和适用条件 |
| [开发工作流](development/workflow.md)、[技术选型](development/technology-stack.md) | 怎么开发、构建和验证 |
| [测试设计与验收](agents/testing.md) | 测试怎么写、归哪类、怎么验收 |
| [文档维护规则](agents/documentation.md) | 文档放哪、怎么同步 |
| `agents/` 其余文件 | 工程 skills 的 tracker 与领域文档约定（装了 triage 时还有标签映射） |

按需创建的目录：`specs/`、`operations/`、`changes/`、`adr/`、`architecture/modules/`。创建条件见[文档维护规则](agents/documentation.md#权威归属与创建时机)。
