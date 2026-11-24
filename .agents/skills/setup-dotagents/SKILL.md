---
name: setup-dotagents
description: "Symlink this dotagents checkout's personal rules and skills into the current user environment. Use after cloning on a new machine, or to check and restore missing load entries."
---

# 应用 dotagents

用户要求执行 setup 即授权建立缺失的用户级链接。

1. 执行 `python3 "<skill-dir>/scripts/setup.py"`，`<skill-dir>` 为本 `SKILL.md` 所在目录的绝对路径。脚本只需 Python 3.14+ 标准库，自行定位 checkout，可从任意工作目录调用；缺少合适的 Python 时说明缺失，不自动安装或升级宿主工具。
2. 脚本报告冲突并退出时（此时未创建任何链接），报告路径与现状，等待用户决定；已有内容保持原样，不删除、覆盖或移动。链接只由脚本建立，不手工补建或改动映射。
3. 成功后根据脚本输出报告创建与已存在的链接，并提示开启新的 Claude Code / Antigravity CLI / Grok 会话验证加载（Antigravity CLI 中可先执行 `/skills reload`）：当前会话不会因链接建立而加载新规则。
4. 检查当前会话的可用 skills 列表中是否有 `setup-matt-pocock-skills`（宿主加了插件命名空间时按实际名称识别）。只依据该列表，不联网、不扫描磁盘、不自动安装：
   - 找到时，简短报告该入口在当前会话可用，不据此声称整个套件已完整安装。
   - 未找到时提醒用户：「当前会话未发现 `setup-matt-pocock-skills`。建议安装 Matt Pocock 的 skill 套件，因为 dotagents 后续很多能力会围绕该套件构建。如果已经安装，请检查是否启用或开启新会话后再确认。」未找到不影响 setup 成功。
