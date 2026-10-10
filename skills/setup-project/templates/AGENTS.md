# {{PROJECT_NAME}}

<待填 初始化：一句话说明项目是什么、给谁用>

## 常驻约束

- 交付满足当前需求的最小、清晰、可验证方案；默认面向当前代码和新启动的工作流，兼容或迁移仅在用户明确要求时纳入。
- 变更代码时按[随交付同步](docs/agents/documentation.md#随交付同步)更新受影响文档；完成报告区分实现、自动检查和未验证项。
- 每次交付前搜索 `<待填`：标记注明的时机已到，或本次任务产生了对应内容，就填写并删除标记；否则原样保留，不编造。时机含义见[待填标记](docs/agents/documentation.md#待填标记)。全部标记消失后删除本条。
- 本文只保留跨任务约束与触发入口；细则写入对应正文并在下表加行，不在此展开。
- 面向用户与供人审阅的文字用简体中文，代码标识、API 与配置键保留英文。

## 按任务读取

开始动作前读取命中行的正文，只展开受影响的章节；未命中时查[文档索引](docs/INDEX.md)，不预读整套文档。

| 触发条件 | 必读入口 |
| --- | --- |
| 设计、修改或 review 代码 | [架构总览](docs/architecture/INDEX.md)，再进受影响的模块页；模块页尚不存在时按[文档维护规则](docs/agents/documentation.md#随交付同步)建页 |
| 编写、修改、移动或 review 测试 | [测试设计与验收](docs/agents/testing.md) |
| 运行命令、选择门禁、调整依赖或工具链 | [开发工作流](docs/development/workflow.md)、[技术选型](docs/development/technology-stack.md) |
| 新增、移动、删除文档，或讨论形成明确结论 | [文档维护规则](docs/agents/documentation.md) |
| 涉及领域术语、数据模型或与 ADR 冲突 | [GLOSSARY.md](GLOSSARY.md)、[领域文档规则](docs/agents/domain.md) |
| 读取、创建或更新票据 | [tracker 约定](docs/agents/issue-tracker.md) |
| 分类票据或调整分诊标签 | [标签映射](docs/agents/triage-labels.md) |
| 调研、实验或复用已有结论 | [调研索引](docs/research/INDEX.md)；新产出放 `docs/research/` 并在索引登记 |
| review diff 的代码质量 | [CODING_STANDARDS.md](CODING_STANDARDS.md) |
