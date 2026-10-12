# setup-project 端到端验收

单元测试只覆盖三个脚本；SKILL.md 里交给 agent 的合并、收敛、补写与提问行为，只能让真实 agent 跑一遍才知道对不对。本文说明怎么用仓库维护层的 harness 自动做这件事，以及结果怎么读。harness 不属于门禁，不被 `just test` 收集，需要网络与模型额度。

## 一句话用法

```sh
just e2e-setup-project                      # 全部用例，opus，输出到系统临时目录
just e2e-setup-project empty uv-existing    # 只跑两个
just e2e-setup-project --review --rerun     # 加 reviewer 会话与幂等复跑
just e2e-setup-project --build-only --out /tmp/x   # 只造 fixture，人工进去跑
```

代码在 `tests/setup_project/e2e/`：`cases.py` 定义用例与 fixture 构造，`checks.py` 做确定性检查，`run.py` 是入口，`review-prompt.md` 是 reviewer 简报，`fixtures/matt/` 是模拟的 Matt setup 产物。

## 做法

1. **fixture**：每个用例在 `<out>/<case>/<case>/` 造一个 Git 仓库（目录名即项目名，`init_docs.py` 默认取目录名），按用例构造源码、旧文档、已有 `AGENTS.md`/`CLAUDE.md`/justfile，再放入模拟的 Matt setup 产物（`docs/agents/` 三件套加 `## Agent skills` 块，按 Matt 的规则写进 `CLAUDE.md` 或 `AGENTS.md`），最后 commit 一次作为基线。`setup-matt-pocock-skills` 标了 `disable-model-invocation`，agent 调不了，而 `setup-project` 只检查其产物存在，所以用 fixture 代替。
2. **真实运行**：在项目目录起 `claude -p "/setup-project"`，`--dangerously-skip-permissions`、`--no-session-persistence`、`--output-format stream-json`，transcript 落到 `transcript.jsonl`。通过 `--append-system-prompt` 告诉 agent 这是非交互环境：不要调用 AskUserQuestion，阶段 1 第 4 步的答案（一句话描述、stack 选择）已预置，并在报告里加"本应提问"一节原文列出本来要问的问题。这是测试与真实使用唯一的偏差，"是否只问一次"由 reviewer 看这一节判断。模型默认 opus，`--model` 可换但拒绝 Fable 系列。
3. **确定性检查**（`checks.py`）：预期文件存在与否、existing 模式下工具链文件未被改动、`AGENTS.md` 无 `## Agent skills` 且有模板两节、用户原有条目的哨兵句仍在、`CLAUDE.md` 只剩 `@AGENTS.md`、剩余 `<待填` 标记的时机前缀合法且 `初始化`/`阶段3` 已消失、描述关键词进入三处、`just --summary` 含全部契约 recipe、harness 自己重跑 `just docs-check` 与 `just gate-core`（existing 模式改跑 skill 自带 `check_docs.py`）、agent 没有 commit；transcript 层面检查运行成功、AskUserQuestion 调用为零、无权限拒绝、三个脚本按顺序运行。结果写入 `summary.md` 与 `checks.json`。
4. **幂等复跑**（`--rerun`）：同一项目再跑一次 `/setup-project`，文件哈希集合必须不变。
5. **reviewer**（`--review`）：另起一个只读 headless 会话，按 `review-prompt.md` 的七个问题对照 SKILL.md、fixture 基线、diff 与 transcript 给出 通过/有问题/不确定，写入 `review.md`，末尾列出对 SKILL.md 的改进建议。维护者只需读 `summary.md` 的 FAIL 行和 `review.md` 里非"通过"的条目。

## 用例表

| 用例 | fixture | 覆盖 |
| --- | --- | --- |
| `empty` | 只有 Matt 产物 | 主用例：判定退出码 3、一次提问、uv 新项目、`gate-core` |
| `uv-existing` | `uv init --package` 加模块与测试、`docs/old-notes.md`、`docs/setup.md`、含同义节 `## 约束` 与自定义节的 `AGENTS.md`、含 `## 代码风格` 的 `CLAUDE.md`、只有 `test`/`lint` 的 justfile | existing 模式、同义节合并、`CLAUDE.md` 收口、旧文档收敛、从代码补写模块页、补齐 recipe |
| `bun-new-with-code` | 只有 `src/*.ts`，无工具链文件 | 有代码但判定退出码 3，选 bun 后 new 模式并补写模块页 |
| `swift-existing` | `swift package init` | existing 且无 justfile，只补依赖偏好与两个公共脚本 |
| `uv-bun-new` | 空 | 多 stack 拼合，`frontend/` 布局 |
| `none-empty` | 空，Matt 产物不含 triage | none stack 的契约 recipe 非零退出、触发表无分诊行 |

加用例只需在 `cases.py` 加一个构造函数和一条 `Case`。

## 修改 skill 后怎么验

- 改脚本：先 `just test`，再跑受影响的一两个用例。
- 改 SKILL.md 或 references：跑 `empty` 与 `uv-existing` 两个主用例并 `--review`，看 reviewer 的"建议改进 SKILL.md 的点"。
- 改工具链模板：跑对应 stack 的用例，重点看 harness 自己跑的 `gate-core` 结果。
- 发布前：全部用例加 `--rerun --review`，把结论回写到 [design.md](design.md) 的待验收一节。

## 验收记录

结论与发现统一记在 [design.md](design.md) 的待验收一节与演进记录，本文不重复。首轮（2026-10-12，opus）两个主用例的开销：`empty` 约 1.3 分钟、0.5 美元，`uv-existing` 约 5 分钟、1.6 美元，reviewer 各再约 2 到 3 分钟。
