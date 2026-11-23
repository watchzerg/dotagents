# 参与开发

改代码前先跑 `uv run pytest -x`，失败即停。

调试输出用环境变量 `LEDGER_DEBUG=1` 打开，会把每次 `Ledger.add` 的参数打到 stderr。
