# setup-harness 设计说明

把各 CLI agent harness 的个人配置还原到当前机器。目前覆盖 Claude Code、Antigravity CLI、Grok Build 和 Codex CLI 的 statusline。

## 关键决策（2026-11-24）

- **一个 skill 装全部 harness，放在 `.agents/skills/`**：配置只是写到 `~/.claude`、`~/.gemini`、`~/.grok` 下的文件，用哪个 harness 运行结果都一样；而且换机时只需运行一次，不必作为用户级 skill 常驻所有项目的上下文。
- **不并入 setup-dotagents**：setup-dotagents 的约定是只建软链接、有冲突就零改动退出；写配置项要修改用户已有的文件，规则不同。setup-dotagents 成功后会提示运行本 skill。
- **以 `setup-harness` 命名，一期不加子命令**：二期可能加入 statusline 以外的配置，名字不需要改。等出现第二类配置时，再加按类别筛选的参数；不带参数时仍然安装全部。
- **内容放 `harness/<harness>/`，脚本用软链接**：仓库里的脚本修改后，pull 即生效。配置项无法链接（同一文件里还有其他设置和运行状态），只合并 statusline 这一项。
- **配置里的命令路径写成 `~/...`**：settings 文件在不同机器之间可以通用。Claude Code 的 `CLAUDE_CONFIG_DIR` 不在家目录下时，改写为绝对路径。
- **按 PATH 上的 CLI 检测 harness**（`claude`、`agy`、`grok`）：不能用配置目录是否存在来判断，因为 setup-dotagents 会为规则链接预先创建 `~/.claude`、`~/.grok`。
- **配置项按整体比较，冲突时默认零改动**：现值与仓库不同（包括多出键）就算冲突，由 agent 转述后请用户确认，再用 `--force` 覆盖。本机想保留的改动，应先改回仓库。
- **TOML 只做文本层面的修改**：标准库只能读 TOML。没有该配置项时，在文件末尾追加 `[ui.status_line]` 段；需要覆盖时，替换这一段直到下一个表头。配置项是内联表或点号键时，报告为无法自动处理。写完后用 `tomllib` 重新解析，核验结果。
- **JSON 整文件重写**：保留键的顺序，缩进 2 格。只有配置项需要变化时才写文件。
- **不自动安装 jq**：脚本依赖 jq 与 git，缺 jq 时只提醒 macOS 和 Ubuntu 各自的安装命令。
- **首次导入不写迁移逻辑**：本机原有的脚本已复制进仓库，原文件由冲突检查加 `--force` 替换为链接。Claude Code 原来的 `statusline-command.sh` 改名为 `statusline.sh`，旧文件手动删除。
- **只允许用户调用**（2026-11-25）：设 `disable-model-invocation: true`，description 只作给人看的一行摘要。会改写用户目录下的 harness 配置，只在换机或还原时由用户发起；setup-dotagents 同样设置。

## Codex CLI（2026-11-27）

- 检测到 PATH 上的 `codex` 时，从 `harness/codex/statusline.toml` 读取 `tui.status_line` 数组并合并到 `$CODEX_HOME/config.toml`（默认 `~/.codex/config.toml`）。状态栏由 Codex 原生渲染。
- 沿用整项比较与 `--force`。写入前解析候选 TOML，核对只有目标键的值变化。无法安全合并的格式（如内联 `tui` 表）在预检阶段报错。

## 待验收

- Codex CLI 在交互终端中的实际渲染待验证。

- Ubuntu 上三个 statusline 脚本的实际渲染未验证；只修正了 Grok 脚本中 `stat` 的调用顺序（先试 GNU `-c`，再试 BSD `-f`）。
- 尚未在一台新机器上走完从 setup-dotagents 到 setup-harness 的完整流程。
