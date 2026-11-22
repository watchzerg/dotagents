## 开始使用

安装宿主工具：{{HOST_TOOLS}}。mise 用系统包管理器安装（macOS：`brew install mise`；Ubuntu：添加 mise 官方 apt 源后 `sudo apt install mise`），just 用全局 mise 配置安装（`mise use -g just@1`）。然后：

```bash
{{MISE_TRUST}}just install
just gate-core
```

{{LAYOUT}}命令说明见 [docs/development/workflow.md](docs/development/workflow.md)。
