# dotagents

管理个人用户级 `AGENTS.md` 和 skills。源文件保存在本仓库，用户目录通过软链接加载。

## 目录

```text
dotagents/
├── README.md
├── global/
│   └── AGENTS.md
└── skills/
    ├── commit/
    └── prune-tests/
```

`global/AGENTS.md` 是跨项目生效的个人规则。`skills/` 只保存个人维护的 skills：`commit` 和 `prune-tests`。

## 本机加载入口

以下仓库路径均相对于当前 checkout：

| 用户目录入口 | 软链接目标 |
| --- | --- |
| `~/.agents/AGENTS.md` | `global/AGENTS.md` |
| `~/.codex/AGENTS.md` | `~/.agents/AGENTS.md`（沿用原有链接） |
| `~/.agents/skills/commit` | `skills/commit` |
| `~/.codex/skills/prune-tests` | `skills/prune-tests` |

skill 按目录逐个链接，两个用户级 skills 父目录保留为普通目录。系统自带的 `~/.codex/skills/.system` 和插件缓存不纳入本仓库。

通过 `npx skills` 安装的第三方 skills（`find-docs`、`find-skills`、`gh`、`playwright`、`show-me`）保留在 `~/.agents/skills/` 中，由原安装工具管理，不纳入本仓库。

## 维护

- 在本仓库修改源文件，通过 Git 查看和管理变更。
- 本机链接使用绝对路径；移动 checkout 或换机器后，需要重新建立链接。
- 仓库不保存认证信息、会话数据或运行缓存。
