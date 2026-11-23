# 文档索引

本页只做路由：各入口回答什么问题，以及没有具体任务时从哪读起。按任务读取的入口在 [AGENTS.md](../AGENTS.md)。

## 冷启动阅读路径

1. [架构总览](architecture/INDEX.md)：系统由什么组成、有哪些功能。
2. 按需打开 `architecture/modules/` 中的模块页，再沿链接进代码与测试；术语对照 [GLOSSARY.md](../GLOSSARY.md)。
3. 追溯取舍时查 [ADR 索引](adr/INDEX.md)，需要证据时查[调研索引](research/INDEX.md)；两者是历史证据，不覆盖当前正文。

## 入口分工

| 入口 | 回答的问题 |
| --- | --- |
| [README](../README.md) | 怎么安装和使用 |
| [AGENTS.md](../AGENTS.md) | agent 的常驻约束和按任务读取入口 |
| [GLOSSARY.md](../GLOSSARY.md) | 领域术语是什么意思 |
| [CODING_STANDARDS.md](../CODING_STANDARDS.md) | diff 评审按什么判断 |
| [架构总览](architecture/INDEX.md) | 系统现在怎样组成；有哪些功能、各自的行为规格在哪 |
| [模块边界](architecture/module-boundaries.md) | 规则归谁、依赖方向与状态所有权 |
| `architecture/modules/` | 某个能力现在完整地怎样工作 |
| [ADR 索引](adr/INDEX.md) | 为什么做出重要决定，哪些已被取代 |
| [调研索引](research/INDEX.md) | 比较与验证的证据和适用条件，哪些已被吸收或取代 |
| [开发工作流](development/workflow.md) | 怎么开发、构建和验证 |
| [技术选型](development/technology-stack.md) | 用什么运行时、工具链与依赖 |
| [测试分层合同](development/test-layers.md) | 各层测试放哪、由哪个入口收录、占用哪些资源；精简测试后保留了什么 |
| [本地验收环境](development/local-acceptance.md) | 真实环境验收时怎么启动、停止、观测，哪些不能碰 |
| [测试设计与门禁](agents/testing.md) | 测试怎么写、归哪层、过哪道门禁 |
| [文档维护规则](agents/documentation.md) | 文档放哪、写什么、多大、怎么同步 |
| `agents/` 其余文件 | 工程 skills 的 tracker、分诊标签与领域文档约定 |

按需目录（`architecture/modules/`、`behaviors/`、`operations/`、`changes/`）在满足[创建时机](agents/documentation.md#权威归属与创建时机)时才建；建好后上表没有对应行的补一行。
