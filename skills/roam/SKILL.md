---
name: roam
description: "Hand off all projects under a projects directory between machines: push (commit, git push, bd dolt push) or pull (fast-forward git, bd dolt pull or bootstrap)."
disable-model-invocation: true
---

# 换机同步

`/roam push` 在要离开的机器上运行，`/roam pull` 在新机器上运行；没给 `push` 或 `pull` 就问。可以附带总目录（包含各项目的目录）。

`scripts/roam.py` 负责全部确定性的检查、推送和拉取，输出 JSON 汇总。下文 `<脚本>` 指它的完整路径，`<总目录参数>` 是用户给了总目录时的 `--root "<总目录>"`，没给就省略（脚本依次找当前路径里名为 `projects` 的祖先目录、`~/projects`、`/data/projects`）。脚本只处理总目录下第一层的项目，每个项目只处理当前分支和 main（没有 main 时用 master）；未被 git 管理的项目跳过，没有 `.beads/` 的项目跳过 Dolt。

## push

1. 运行 `python3 <脚本> status <总目录参数>`。
2. 列出 `dirty` 非空且 `in_progress`、`detached` 都为假的项目：每个项目一行写项目名和改动摘要（用 `git -C <项目> diff HEAD --stat` 概括），把 `??` 开头的未跟踪文件逐个单独列出。没有这样的项目就跳到第 4 步。
3. 请用户确认一次提交哪些项目；用户可以剔除项目或文件。确认后逐个项目暂存确认的范围并提交，message 遵循该项目约定（看 `git log --oneline -5`），没有约定时用简体中文；标题一行约 50 字以内，细节写在正文里；不附 `Co-Authored-By` 等署名行。hook 失败时不绕过，记下原因，继续处理下一个项目。
4. 运行 `python3 <脚本> push <总目录参数>`，按[汇总](#汇总)报告。

## pull

1. 运行 `python3 <脚本> pull <总目录参数>`。脚本会先 fetch，再前进分支：当前分支能快进就快进，与远端分叉时试 rebase，有冲突立即回滚；非当前的 main 只做快进。有未提交改动、处于 merge 或 rebase 中途、处于 detached HEAD 的项目，git 部分整个跳过。Beads 有本地库时运行 `bd dolt pull`，有冲突时它会中止、不改数据；没有本地库（新 clone）时运行 `bd bootstrap` 从远端恢复。
2. 按[汇总](#汇总)报告。工作区有未提交改动的项目要放在最前面：这说明上次离开那台机器时漏推了。

## 汇总

依据脚本 JSON 如实报告，问题项放在最前面：

- `result` 为 `problem` 的项目：逐条转述 `problems`。冲突和分叉只报告，不动手合并。
- 已完成的项目：push 报告 `pushed`，pull 报告 `done`，以及 Dolt 结果；没有任何变化的项目合并成一行。
- `hints`（pull 的依赖变化、dotagents 的 skill 或 harness 配置安装器变化）：只提醒，不自动执行安装或 setup。
- `other_branches` 中 `ahead` 大于 0 或 `upstream` 为空的分支：列出来提醒用户，这些分支不由本 skill 处理。
- 跳过的项目（未被 git 管理）：合并成一行。

脚本退出码为 1 时表示有项目存在问题，其余项目已照常处理；退出码为 2 时找不到总目录，向用户要路径。
