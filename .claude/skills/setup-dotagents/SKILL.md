---
name: setup-dotagents
description: 将当前 dotagents checkout 的个人规则和 skills 通过软链接应用到当前用户环境。用于 clone 后初始化新机器，或检查并补齐本仓库的加载入口。
---

# 应用 dotagents

直接执行 `python3 "<skill-dir>/scripts/setup.py"`，其中 `<skill-dir>` 为本 `SKILL.md` 所在目录的绝对路径。脚本根据自身位置定位 checkout，可从任意工作目录调用，不使用写死的机器路径。

- 运行时只需要 Python 3.14+ 标准库，不依赖 just、uv、第三方包或项目 `.venv`。缺少合适的 Python 时说明缺失，不自动安装或升级宿主工具。
- 用户要求执行 setup 即授权建立缺失的用户级链接。
- 脚本先检查全部入口：正确链接跳过，冲突时退出且不开始创建。遇到冲突，报告路径与现状，等待用户决定如何处理，不删除、覆盖或移动已有内容。
- 保持脚本定义的链接映射，不链接仓库根目录的 `AGENTS.md`，不整体替换用户 skills 父目录，也不把本安装 skill 安装到用户目录。
- 完成后根据脚本输出报告创建、已存在和失败情况。链接检查通过不等于新规则已在当前会话加载；提示开启新的 Claude Code 会话验证。

脚本位于 [scripts/setup.py](scripts/setup.py)。它只建立并核验链接，不安装第三方 skills、开发依赖或修改其他配置。

## 检查 Matt Pocock skills

软链接建立并核验成功后，检查当前 session 提供的可用 skills 列表中是否有名称为 `setup-matt-pocock-skills` 的 skill；若宿主给名称添加了插件命名空间，按实际 skill 名称识别。

- 找到时，简短报告该入口在当前会话可用；不据此声称整个套件已安装完整。
- 未找到时提醒用户：「当前会话未发现 `setup-matt-pocock-skills`。建议安装 Matt Pocock 的 skill 套件，因为 dotagents 后续很多能力会围绕该套件构建。如果已经安装，请检查是否启用或开启新会话后再确认。」
- 只依据当前会话的 skills 列表，不联网、不扫描磁盘、不查询特定安装工具的记录，也不自动安装。未发现该入口不影响 setup 成功，不等于系统中一定没有安装。
- 来源信息明确时可附带用户级或项目级范围，以加载入口而非软链接目标判断；插件来源无法确认范围时标注范围未确认，不为此追加调查。
