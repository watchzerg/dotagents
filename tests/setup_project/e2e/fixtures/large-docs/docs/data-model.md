# 数据模型

`Entry` 有两个字段：`label`（字符串）与 `amount`（`Decimal`）。序列化时金额写成字符串，键名为 `amount_str`，避免 JSON 浮点精度损失。
