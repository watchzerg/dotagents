---
name: setup-harness
description: "Install this checkout's harness configs (statusline) into the current user environment."
disable-model-invocation: true
---

# 应用 harness 配置

用户要求执行即授权写入下述链接与配置项。

1. 执行 `python3 "<skill-dir>/scripts/setup_harness.py"`，`<skill-dir>` 为本 `SKILL.md` 所在目录的绝对路径。脚本只需 Python 3.14+ 标准库，可从任意工作目录调用；缺少合适的 Python 时说明缺失，不自动安装。脚本只处理 PATH 上能找到 CLI（`claude`、`agy`、`grok`）的 harness，对每个 harness：
   - 把仓库 `harness/<harness>/statusline.sh` 软链接到该 harness 的配置目录；
   - 在 `settings.json`（Claude Code、Antigravity CLI）或 `config.toml`（Grok Build）中写入指向该链接的 statusline 配置项，其余设置保持不变。
2. 退出码为 1 且报告“冲突”时，脚本没有做任何修改。逐条转述冲突：链接位置已有普通文件时，先用 `diff` 对比它和仓库脚本，把差异告诉用户；配置项不同时，转述现值与期望值。请用户确认是否以仓库为准覆盖，确认后加 `--force` 重新执行。用户想保留本机版本时，建议把它改回仓库再执行，不手工改链接或配置。
3. 报告“错误”（配置文件解析失败、链接位置是目录、TOML 中 `ui.status_line` 不是独立段）时，`--force` 也不会处理：报告路径与原因，等用户处理。
4. 成功后报告创建、写入与已存在的项，以及跳过的 harness。转述 jq 缺失提醒；提示开启新会话后生效，图标需要终端使用 Nerd Font。
