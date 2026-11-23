# float 与 Decimal 比较

实验：连续累加 0.1 一万次，float 结果为 1000.0000000001588，Decimal 为 1000.0。结论：金额用 Decimal。实验脚本 `bench/float_drift.py`。
