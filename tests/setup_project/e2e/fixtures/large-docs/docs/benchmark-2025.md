# 2025 年性能测试

在一万条条目上测 `Ledger.balance()`：Decimal 求和耗时 4.1 ms，float 求和 1.2 ms。结论：差距可忽略，继续用 Decimal。测试脚本 `bench/balance_bench.py`。
