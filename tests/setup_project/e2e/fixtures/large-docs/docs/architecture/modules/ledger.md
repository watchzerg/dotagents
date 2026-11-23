---
covers:
  - src/demo_uv/ledger.py
---

# ledger

## 概述

账本模块，持有条目列表并计算余额。

## 细节

`Ledger.balance()` 对空账本返回 `Decimal("0")`；条目顺序即追加顺序。

## 测试

见 `tests/test_ledger.py`。
