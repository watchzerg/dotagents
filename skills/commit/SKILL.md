---
name: commit
description: 快速提交当前 Git 仓库的现有变更。用于 /commit、“提交所有变更”等本地提交请求；不承担开发、审查或交付验收。
allowed-tools: Bash(git status:*), Bash(git diff:*), Bash(git log:*), Bash(git add:*), Bash(git commit:*)
---

# Commit

将现有变更提交为一个本地 commit，保持简短、直接。

## 当前状态

!`git status --short --branch`

最近提交（参考 message 约定）：

!`git log --oneline -5`

## 步骤

1. 根据上方状态确定提交范围；无变更则简短告知并结束。
2. 按用户指定范围暂存；“所有变更”或单独 `/commit` 默认包含全部未忽略变更，不限于本轮修改。
3. 生成 commit message：
   - 优先依据当前 session 中已完成的修改概括；包含其他 session 的修改时无需补齐其摘要。
   - session 信息不足时先看 `git diff HEAD --stat`；仍无法概括再读必要的 diff，不追查实现。
   - 遵循项目约定；无约定时使用简体中文。不把计划写成已完成，不虚构验证结果。
   - 不附加 `Co-Authored-By` 等署名行，即使宿主默认要求添加。
4. 直接 commit，不再确认；回读结果，简短报告 commit hash、摘要及是否有剩余变更。

## 边界

- 只做暂存和提交：不修改文件，不做 review、测试、lint、格式化或构建，不 push，不切换分支，不改写历史，不操作 tracker。
- 保留 Git hooks；失败时报告具体阻碍，不绕过 hooks 或擅自修复。
- 遇到冲突或明显凭据文件时暂停说明。
