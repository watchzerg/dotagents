# setup-project 端到端验收

单元测试只覆盖三个脚本；SKILL.md 交给 agent 的合并、收敛、补写与提问行为，只能让真实 agent 跑一遍才知道对不对。本文说明仓库维护层的 harness 怎么做这件事、结果怎么读。harness 不属于门禁，不被 `mise run test` 收集，需要网络与模型额度。

## 用法

```sh
mise run e2e-setup-project                      # 全部用例，opus，输出到系统临时目录
mise run e2e-setup-project empty uv-existing    # 只跑两个
mise run e2e-setup-project --review --rerun     # 加 reviewer 会话与幂等复跑
mise run e2e-setup-project --build-only --out /tmp/x   # 只造 fixture，人工进去跑
mise run e2e-setup-project --check-only --out /tmp/x   # 不重跑 agent，只重新检查已有产物
```

其余参数（`--model`、`--jobs`）见 `--help`。代码在 `tests/setup_project/e2e/`：`cases.py` 定义用例与 fixture，`checks.py` 做确定性检查，`run.py` 是入口，`review-prompt.md` 是 reviewer 简报，`fixtures/matt/` 是模拟的 Matt setup 产物。

## 做法

1. **fixture**：每个用例在 `<out>/<case>/<case>/` 造一个 Git 仓库（目录名即项目名），按用例构造源码、旧文档、已有 `AGENTS.md`/`CLAUDE.md`/`mise.toml`，放入模拟的 Matt setup 产物，最后 commit 一次作为基线。`setup-matt-pocock-skills` 标了 `disable-model-invocation`，agent 调不了，而本 skill 只检查其产物存在，所以用 fixture 代替。
2. **前置检查**：开跑前确认 `~/.claude/skills/setup-project`（设了 `CLAUDE_CONFIG_DIR` 时用它）解析到本 checkout，否则 headless 会话测到的是别处的 skill；并确认 `claude`、`git`、`mise`、`uv`、`bd` 及用例声明的额外命令（swift 用例的 `swift`、`xcodebuild`）在 PATH 上。不满足直接报错，不花额度。`--build-only`、`--check-only` 跳过此检查。
3. **真实运行**：runner 只实现了 Claude Code。在项目目录起 `claude -p "/setup-project"`（`--dangerously-skip-permissions`、`--no-session-persistence`、`--output-format stream-json`），transcript 落到 `transcript.jsonl`。`--append-system-prompt` 只告诉 agent 这是非交互环境：不调用 AskUserQuestion，阶段 1 第 4 步的答案已预置，在报告里加“本应提问”一节原文列出本来要问的问题，并把报告另存到用例目录。这是测试与真实使用唯一的偏差；“按阶段执行”“不 commit”等要求不写进追加提示，否则检查验证的是提示而不是 SKILL.md。“是否只问一次”由 reviewer 看这一节判断。模型默认 opus，拒绝 Fable 系列。
4. **确定性检查**（`checks.py`）：预期文件存在与否、两张合同页存在且有入链、existing 模式下工具链文件未被改动、`AGENTS.md` 的节结构与用户哨兵句、`CLAUDE.md` 只剩 `@AGENTS.md`、剩余 `<待填` 标记、描述关键词进入目标文件、契约 task 齐全、harness 自己重跑 `docs-check` 与 `gate-core`（existing 模式改跑项目里的 `check_docs.py`）、fixture 之后的提交只改动 `.beads/`（`bd init` 的自动提交，agent 本身不得 commit）；transcript 层面检查运行成功、AskUserQuestion 调用为零、无权限拒绝、三个脚本按顺序运行。结果写入 `summary.md` 与 `checks.json`。单个用例的构造或运行出错（含会话超时）只记为该用例失败，不中断其他用例。
5. **幂等复跑**（`--rerun`）：同一项目再跑一次：第二次会话同样要通过 transcript 层面的检查（避免会话没起来也算“无变化”），文件哈希集合必须不变。
6. **reviewer**（`--review`）：另起只读 headless 会话，按 `review-prompt.md` 的七个问题对照 SKILL.md、fixture 基线、diff 与 transcript 给出 通过/有问题/不确定，写入 `review.md`，末尾列出对 SKILL.md 的改进建议，最后一行 `VERDICTS:` 给出三类结论计数。

跑完后 `<out>/summary.md` 汇总每个用例的硬检查结果、失败项、耗时、费用与 reviewer 计数；维护者从这里进入，只读 FAIL 用例的 `summary.md` 与 reviewer 计数非零用例的 `review.md`。

## 用例表

| 用例 | fixture | 覆盖 |
| --- | --- | --- |
| `empty` | 只有 Matt 产物 | 主用例：判定退出码 3、一次提问、uv 新项目、`gate-core` |
| `uv-existing` | `uv init --package` 加模块与测试、`docs/old-notes.md`、`docs/setup.md`、含同义节 `## 约束` 与自定义节的 `AGENTS.md`、含 `## 代码风格` 的 `CLAUDE.md`、只有 `test`/`lint` task 的 `mise.toml` | existing 模式、同义节合并、`CLAUDE.md` 收口、旧文档收敛、从代码补写模块页、补齐 task |
| `node-new-with-code` | 只有 `src/*.ts`，无工具链文件 | 有代码但判定退出码 3，选 node 后 new 模式并补写模块页 |
| `swift-existing` | `swift package init` | existing 且无 mise task，只补依赖偏好与两个公共脚本 |
| `uv-node-new` | 空 | 多 stack 拼合，`frontend/` 布局 |
| `none-empty` | 空，Matt 产物不含 triage | none stack 的契约 task 非零退出、触发表无分诊行 |
| `uv-large-docs` | uv 工程加 `fixtures/large-docs/`：`docs/`、`design/`、`notes/` 与根目录共 30 多个候选，含附件、超 16 KiB 的运维手册、骨架不符的模块页、未登记的 ADR 与调研、验收记录、计划项；`.worktrees/`、`output/` 下有被忽略的副本 | 大批量收敛：内容哨兵（每份源文档的标志性片段须留在正文、术语表或票据里）、源文件迁走或登记、附件不丢、被忽略副本不动；分批与串行由 reviewer 判断 |
| `beads-clone` | 在临时 bare origin 上推送过 Beads 票据与 Dolt 数据的仓库重新 clone，只有 `.beads/` 配置 | `bd bootstrap` 从 origin 恢复原有票据而不是另起空库 |

加用例只需在 `cases.py` 加一个构造函数和一条 `Case`；需要专属检查时在 `checks.py` 的 `EXTRA_CHECKS` 按用例名登记。

## 修改 skill 后怎么验

- 改脚本：先 `mise run test`，再跑受影响的一两个用例；`init_beads.py` 对应 `beads-clone`。
- 改 SKILL.md 或 references：跑 `empty` 与 `uv-existing` 并加 `--review`，看 reviewer 的“建议改进 SKILL.md 的点”；改 `converge-docs.md` 或模板 `documentation.md` 时加跑 `uv-large-docs`。
- 改工具链模板：跑对应 stack 的用例，重点看 harness 自己跑的 `gate-core` 结果。
- 发布前：全部用例加 `--rerun --review`。

结论与发现记在 [design.md](design.md)：已固化的进关键决策，未验证的进待验收。每次运行的耗时与费用见总览页；量级参考（2026-10-12，opus）：`empty` 约 0.5 美元，`uv-existing` 约 1.6 美元，reviewer 各再约 2 到 3 分钟。
