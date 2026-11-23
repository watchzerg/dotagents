# 架构

demo_uv 是单进程命令行程序：入口 `demo_uv.main` 构造 `Ledger`，所有金额以 `Decimal` 存储。

持久化层把账本序列化为 JSON，文件位置由环境变量 `LEDGER_HOME` 决定，未设置时用 `~/.demo_uv`。
