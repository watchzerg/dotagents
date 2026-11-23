# 模块划分

- `demo_uv.ledger`：账本与条目。
- `demo_uv.storage`：JSON 读写，对外只暴露 `load_ledger` 与 `save_ledger`。
- `demo_uv.cli`：参数解析，基于标准库 `argparse`。
