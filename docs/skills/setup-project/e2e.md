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
2. **真实运行**：runner 只实现了 Claude Code。在项目目录起 `claude -p "/setup-project"`（`--dangerously-skip-permissions`、`--no-session-persistence`、`--output-format stream-json`），transcript 落到 `transcript.jsonl`。`--append-system-prompt` 告诉 agent 这是非交互环境：不调用 AskUserQuestion，阶段 1 第 4 步的答案已预置，并在报告里加“本应提问”一节原文列出本来要问的问题。这是测试与真实使用唯一的偏差，“是否只问一次”由 reviewer 看这一节判断。模型默认 opus，拒绝 Fable 系列。
3. **确定性检查**（`checks.py`）：预期文件存在与否、两张合同页存在且有入链、existing 模式下工具链文件未被改动、`AGENTS.md` 的节结构与用户哨兵句、`CLAUDE.md` 只剩 `@AGENTS.md`、剩余 `<待填` 标记、描述关键词进入目标文件、契约 task 齐全、harness 自己重跑 `docs-check` 与 `gate-core`（existing 模式改跑项目里的 `check_docs.py`）、agent 没有 commit；transcript 层面检查运行成功、AskUserQuestion 调用为零、无权限拒绝、三个脚本按顺序运行。结果写入 `summary.md` 与 `checks.json`。
4. **幂等复跑**（`--rerun`）：同一项目再跑一次，文件哈希集合必须不变。
5. **reviewer**（`--review`）：另起只读 headless 会话，按 `review-prompt.md` 的七个问题对照 SKILL.md、fixture 基线、diff 与 transcript 给出 通过/有问题/不确定，写入 `review.md`，末尾列出对 SKILL.md 的改进建议。维护者只需读 `summary.md` 的 FAIL 行和 `review.md` 里非“通过”的条目。

## 用例表

| 用例 | fixture | 覆盖 |
| --- | --- | --- |
| `empty` | 只有 Matt 产物 | 主用例：判定退出码 3、一次提问、uv 新项目、`gate-core` |
| `uv-existing` | `uv init --package` 加模块与测试、`docs/old-notes.md`、`docs/setup.md`、含同义节 `## 约束` 与自定义节的 `AGENTS.md`、含 `## 代码风格` 的 `CLAUDE.md`、只有 `test`/`lint` task 的 `mise.toml` | existing 模式、同义节合并、`CLAUDE.md` 收口、旧文档收敛、从代码补写模块页、补齐 task |
| `node-new-with-code` | 只有 `src/*.ts`，无工具链文件 | 有代码但判定退出码 3，选 node 后 new 模式并补写模块页 |
| `swift-existing` | `swift package init` | existing 且无 mise task，只补依赖偏好与两个公共脚本 |
| `uv-node-new` | 空 | 多 stack 拼合，`frontend/` 布局 |
| `none-empty` | 空，Matt 产物不含 triage | none stack 的契约 task 非零退出、触发表无分诊行 |

加用例只需在 `cases.py` 加一个构造函数和一条 `Case`。

## 修改 skill 后怎么验

- 改脚本：先 `mise run test`，再跑受影响的一两个用例。
- 改 SKILL.md 或 references：跑 `empty` 与 `uv-existing` 并加 `--review`，看 reviewer 的“建议改进 SKILL.md 的点”。
- 改工具链模板：跑对应 stack 的用例，重点看 harness 自己跑的 `gate-core` 结果。
- 发布前：全部用例加 `--rerun --review`。

结论与发现记在 [design.md](design.md)：已固化的进关键决策，未验证的进待验收。参考开销（2026-10-12，opus）：`empty` 约 1.3 分钟、0.5 美元，`uv-existing` 约 5 分钟、1.6 美元，reviewer 各再约 2 到 3 分钟。
