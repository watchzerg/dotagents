## 开始使用

安装宿主工具：{{HOST_TOOLS}}。mise 用系统包管理器安装（macOS：`brew install mise`；Ubuntu：添加 mise 官方 apt 源后 `sudo apt install mise`），项目所需的其余工具由 `mise run` 按 `mise.toml` 自动安装。然后：

```bash
mise run install
mise run gate-core
```

{{LAYOUT}}命令说明见 [docs/development/workflow.md](docs/development/workflow.md)，`mise tasks` 列出全部 task。
