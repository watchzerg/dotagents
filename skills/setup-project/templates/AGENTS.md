# {{PROJECT_NAME}}

<待填 初始化：一句话说明项目是什么、给谁用>

## 常驻约束

- 交付满足当前需求的最小、清晰、可验证方案，抽象与扩展点等到出现第二个使用者再加；只针对当前代码、当前 schema 和新数据实现，兼容旧版本或迁移历史数据属于额外需求，先说明影响与新增复杂度，获用户批准后再纳入。
- 变更代码时按[随交付同步](docs/agents/documentation.md#随交付同步)更新受影响文档；完成报告区分实现、自动检查和未验证项。
- 每次交付前按[待填标记](docs/agents/documentation.md#待填标记)检查剩余标记，时机已到或本次产生了对应内容就填写。全部标记消失后删除本条。
- 本文只放跨任务约束与下表的入口；细则写进对应正文，再在下表加行。
- 面向用户及供人审阅的文字用简体中文，包括文档、计划、票据、PR、review 和代码注释；代码标识、API、配置键、CLI 参数、文件名、日志与错误消息保留英文。

## 按任务读取

动手前读命中行的入口（可命中多行），只展开受影响的章节；未命中时查[文档索引](docs/INDEX.md)。

| 触发条件 | 必读入口 |
| --- | --- |
| 设计、修改或 review 代码 | [架构总览](docs/architecture/INDEX.md)，再进受影响的模块页 |
| 编写、修改、移动或 review 测试，制定测试计划，执行 `implement-spec` | [测试设计与门禁](docs/agents/testing.md)；测试覆盖的行为还没有模块页时，按[随交付同步](docs/agents/documentation.md#随交付同步)建页 |
| 运行命令、选择门禁 | [开发工作流](docs/development/workflow.md) |
| 调整依赖或工具链 | [技术选型](docs/development/technology-stack.md) |
| 新增、移动、删除文档，或讨论形成明确结论 | [文档维护规则](docs/agents/documentation.md) |
| 涉及领域术语或数据模型 | [GLOSSARY.md](GLOSSARY.md)，写法见[领域文档规则](docs/agents/domain.md) |
| 改变已有取舍、与 ADR 冲突或新增 ADR | [ADR 索引](docs/adr/INDEX.md)，写法见[领域文档规则](docs/agents/domain.md) |
| 读取、创建或更新票据 | [tracker 约定](docs/agents/issue-tracker.md)；`bd` 报 `no beads database found` 时运行 `bd bootstrap` 从远端恢复，不用 `bd init` |
| 分类票据或调整分诊标签 | [标签映射](docs/agents/triage-labels.md) |
| 调研、实验或复用已有结论 | [调研索引](docs/research/INDEX.md) |
| review diff 的代码质量 | [CODING_STANDARDS.md](CODING_STANDARDS.md) |
